#!/usr/bin/env python3
"""Bounded Phase 7 ML day-2 operator-surface probe."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(cmd: list[str], *, timeout: int = 240, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def select_running_pod(namespace: str, app: str) -> str:
    payload = json.loads(run(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={app}", "-o", "json"]).stdout)
    for item in payload.get("items") or []:
        status = dict(item.get("status") or {})
        if str(status.get("phase") or "").strip() != "Running":
            continue
        conditions = list(status.get("conditions") or [])
        ready = any(
            str(cond.get("type") or "").strip() == "Ready" and str(cond.get("status") or "").strip() == "True"
            for cond in conditions
        )
        if ready:
            name = str(((item.get("metadata") or {}).get("name")) or "").strip()
            if name:
                return name
    raise RuntimeError(f"PHASE7_POD_UNAVAILABLE:{namespace}:{app}")


REMOTE_RUNTIME_DRIFT_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.decision_fabric.registry import RegistryResolutionPolicy, RegistryScopeKey, RegistrySnapshot
from fraud_detection.decision_fabric.worker import load_worker_config

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
snapshot = RegistrySnapshot.load(cfg.registry_snapshot_ref)
policy = RegistryResolutionPolicy.load(cfg.registry_policy_ref)
fraud_scope = RegistryScopeKey(environment="dev_full", mode="fraud", bundle_slot="primary").canonical_key()

record = snapshot.records_by_scope.get(fraud_scope)
fallback = policy.explicit_fallback_by_scope.get(fraud_scope)
print(json.dumps({
    "registry_snapshot_ref": str(cfg.registry_snapshot_ref),
    "registry_policy_ref": str(cfg.registry_policy_ref),
    "policy_id": policy.policy_rev.policy_id,
    "policy_revision": policy.policy_rev.revision,
    "fraud_primary": None if record is None else {
        "bundle_id": record.bundle_ref["bundle_id"],
        "bundle_version": record.bundle_ref["bundle_version"],
        "registry_ref": record.bundle_ref["registry_ref"],
    },
    "fraud_policy_fallback": None if fallback is None else dict(fallback),
}))
"""


def exec_json(namespace: str, pod: str, script: str, env_map: dict[str, str]) -> tuple[dict[str, Any], str]:
    env_bits = [f"{key}={value}" for key, value in sorted(env_map.items())]
    proc = run(["kubectl", "exec", "-n", namespace, pod, "--", "env", *env_bits, "python", "-c", script], check=False)
    if proc.returncode != 0:
        return {}, proc.stderr.strip() or proc.stdout.strip()
    text = proc.stdout.strip()
    if not text:
        return {}, ""
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return {}, f"json_decode_error:{exc}"


def placeholder_flag(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in ("rotate-me", "example", "placeholder", "changeme", "todo"))


def derive_bundle_surface(
    probe: dict[str, Any],
    *,
    fallback_bundle: dict[str, Any],
    fallback_ref: str = "",
) -> dict[str, Any]:
    direct = dict(probe.get("fraud_primary") or {})
    if direct:
        return direct
    if fallback_bundle:
        return dict(fallback_bundle)
    ref = str(fallback_ref or probe.get("expected_bundle_ref") or "").strip()
    if not ref.startswith("bundle://") or "@" not in ref:
        return {}
    text = ref[len("bundle://") :]
    bundle_id, _, bundle_version = text.partition("@")
    if not bundle_id or not bundle_version:
        return {}
    return {
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "registry_ref": str((fallback_bundle or {}).get("registry_ref") or ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Bounded Phase 7 ML day-2 operator-surface probe")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-phase6-execution-id", required=True)
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--rtdl-namespace", default="fraud-platform-rtdl")
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_phase6_execution_id
    source_manifest = load_json(source_root / "phase6_registry_surface_manifest.json")
    rollback_probe = load_json(source_root / "phase6_rollback_bundle_probe.json")
    restore_probe = load_json(source_root / "phase6_restore_bundle_probe.json")

    ssm = boto3.client("ssm", region_name=args.aws_region)
    sm = boto3.client("sagemaker", region_name=args.aws_region)

    blockers: list[str] = []

    runtime_probe = {}
    runtime_probe_error = ""
    try:
        df_pod = select_running_pod(args.rtdl_namespace, "fp-pr3-df")
        runtime_probe, runtime_probe_error = exec_json(
            args.rtdl_namespace,
            df_pod,
            REMOTE_RUNTIME_DRIFT_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
    except Exception as exc:  # noqa: BLE001
        runtime_probe_error = str(exc)
    if runtime_probe_error:
        blockers.append(f"PHASE7_C_RUNTIME_PROBE_FAIL:{runtime_probe_error}")

    expected = dict(source_manifest.get("promoted_bundle") or {})
    actual = dict(runtime_probe.get("fraud_primary") or {})
    if not runtime_probe_error and (
        actual.get("bundle_id") != expected.get("bundle_id")
        or actual.get("bundle_version") != expected.get("bundle_version")
    ):
        blockers.append("PHASE7_C_ACTIVE_BUNDLE_DRIFT")
    if not runtime_probe_error and str(runtime_probe.get("policy_revision") or "").strip() != str(
        source_manifest.get("promoted_policy_revision") or ""
    ).strip():
        blockers.append("PHASE7_C_ACTIVE_POLICY_DRIFT")

    mlflow_uri = ""
    mlflow_error = ""
    try:
        mlflow_uri = str(
            ssm.get_parameter(Name="/fraud-platform/dev_full/mlflow/tracking_uri", WithDecryption=False)["Parameter"]["Value"]
        )
        if placeholder_flag(mlflow_uri):
            blockers.append("PHASE7_C_MLFLOW_TRACKING_URI_PLACEHOLDER")
    except (BotoCoreError, ClientError) as exc:
        mlflow_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PHASE7_C_MLFLOW_TRACKING_URI_UNRESOLVED")

    exec_role_arn = ""
    exec_role_error = ""
    try:
        exec_role_arn = str(
            ssm.get_parameter(Name="/fraud-platform/dev_full/sagemaker/model_exec_role_arn", WithDecryption=False)["Parameter"]["Value"]
        )
        if placeholder_flag(exec_role_arn):
            blockers.append("PHASE7_C_SAGEMAKER_EXEC_ROLE_PLACEHOLDER")
    except (BotoCoreError, ClientError) as exc:
        exec_role_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PHASE7_C_SAGEMAKER_EXEC_ROLE_UNRESOLVED")

    package_groups = []
    package_group_error = ""
    try:
        package_groups = [
            str(row.get("ModelPackageGroupName") or "")
            for row in sm.list_model_package_groups(MaxResults=100).get("ModelPackageGroupSummaryList") or []
        ]
        if "fraud-platform-dev-full-models" not in package_groups:
            blockers.append("PHASE7_C_MODEL_PACKAGE_GROUP_MISSING")
    except (BotoCoreError, ClientError) as exc:
        package_group_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PHASE7_C_MODEL_PACKAGE_GROUP_LIST_FAIL")

    endpoints = []
    endpoint_error = ""
    try:
        endpoints = [
            {"name": str(row.get("EndpointName") or ""), "status": str(row.get("EndpointStatus") or "")}
            for row in sm.list_endpoints(MaxResults=100).get("Endpoints") or []
        ]
    except (BotoCoreError, ClientError) as exc:
        endpoint_error = f"{type(exc).__name__}:{exc}"

    rollback_bundle = derive_bundle_surface(
        rollback_probe,
        fallback_bundle=dict(source_manifest.get("previous_bundle") or {}),
        fallback_ref=str(rollback_probe.get("expected_bundle_ref") or ""),
    )
    restore_bundle = derive_bundle_surface(
        restore_probe,
        fallback_bundle=dict(source_manifest.get("promoted_bundle") or {}),
        fallback_ref=str(restore_probe.get("expected_bundle_ref") or ""),
    )
    if not rollback_bundle:
        blockers.append("PHASE7_C_ROLLBACK_AUTHORITY_MISSING")
    if not restore_bundle:
        blockers.append("PHASE7_C_RESTORE_AUTHORITY_MISSING")

    summary = {
        "phase": "PHASE7",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "serving_mode": "EKS_DECISION_FABRIC_RUNTIME",
        "runtime_probe": runtime_probe,
        "runtime_probe_error": runtime_probe_error,
        "expected_promoted_bundle": expected,
        "expected_policy_revision": str(source_manifest.get("promoted_policy_revision") or ""),
        "managed_learning_surfaces": {
            "mlflow_tracking_uri": mlflow_uri,
            "mlflow_tracking_uri_error": mlflow_error,
            "sagemaker_model_exec_role_arn": exec_role_arn,
            "sagemaker_model_exec_role_error": exec_role_error,
            "model_package_groups": package_groups,
            "model_package_group_error": package_group_error,
            "sagemaker_endpoints": endpoints,
            "sagemaker_endpoint_list_error": endpoint_error,
        },
        "mitigation_surfaces": {
            "rollback_bundle": rollback_bundle,
            "restore_bundle": restore_bundle,
            "allowed_actions": [
                "rollback",
                "degrade",
                "pause_promotion_or_learning",
                "investigate_data_or_label_quality",
            ],
        },
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    receipt = {
        "phase": "PHASE7",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "verdict": "PHASE7_ML_DAY2_READY" if summary["overall_pass"] else "PHASE7_ML_DAY2_HOLD",
        "open_blockers": len(summary["blocker_ids"]),
        "blocker_ids": summary["blocker_ids"],
    }
    dump_json(root / "phase7_ml_day2_operator_surface.json", summary)
    dump_json(root / "phase7_ml_day2_operator_surface_receipt.json", receipt)

    if not summary["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
