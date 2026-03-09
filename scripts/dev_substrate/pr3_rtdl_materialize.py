#!/usr/bin/env python3
"""Materialize the PR3 RTDL/decision/archive runtime on remote EKS."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import yaml


REGISTRY = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
SCENARIO_RUN_ID_RX = re.compile(r"^[a-f0-9]{32}$")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def archive_existing(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    hist = path.parent / "attempt_history"
    hist.mkdir(parents=True, exist_ok=True)
    hist_path = hist / f"{path.stem}.{stamp}{path.suffix}"
    hist_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def parse_registry(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    rx = re.compile(r"^\*\s*`([^`]+)`")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        m = rx.match(line)
        if not m:
            continue
        body = m.group(1)
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def run(cmd: list[str], *, input_text: str | None = None, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def kubectl_apply(document: dict[str, Any]) -> None:
    run(["kubectl", "apply", "-f", "-"], input_text=json.dumps(document), timeout=300, check=True)


def kubectl_delete(kind: str, name: str, namespace: str) -> None:
    run(["kubectl", "delete", kind, name, "-n", namespace, "--ignore-not-found=true"], timeout=180, check=False)


def get_json(cmd: list[str], *, timeout: int = 120) -> dict[str, Any]:
    proc = run(cmd, timeout=timeout, check=True)
    text = proc.stdout.strip()
    return json.loads(text) if text else {}


def resolve_task_image(ecs: Any, *, family: str, region: str) -> str:
    resp = ecs.describe_task_definition(taskDefinition=family)
    task_def = resp.get("taskDefinition", {})
    containers = task_def.get("containerDefinitions", [])
    if not containers:
        raise RuntimeError(f"no container definitions found in task definition {family}")
    image = str(containers[0].get("image", "")).strip()
    if not image:
        raise RuntimeError(f"image not found in task definition {family}")
    return image


def build_aurora_dsn(*, endpoint: str, username: str, password: str, db_name: str, port: int) -> str:
    return (
        f"postgresql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{endpoint}:{int(port)}/{db_name}?sslmode=require"
    )


def resolve_ssm_parameters(ssm: Any, *, names: list[str]) -> dict[str, str]:
    resp = ssm.get_parameters(Names=names, WithDecryption=True)
    values = {
        str(row.get("Name", "")).strip(): str(row.get("Value", "")).strip()
        for row in resp.get("Parameters", [])
    }
    missing = [name for name in names if not values.get(name)]
    if missing:
        raise RuntimeError(f"missing_ssm_parameters:{','.join(missing)}")
    return values


def secret_manifest(namespace: str, name: str, string_data: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace},
        "type": "Opaque",
        "stringData": string_data,
    }


def config_map_manifest(namespace: str, name: str, data: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": namespace},
        "data": data,
    }


def namespace_manifest(name: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": name},
    }


def _ensure_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.setdefault(key, {})
    if not isinstance(value, dict):
        raise RuntimeError(f"profile field {key} must be a mapping")
    return value


def _materialize_run_scoped_profile(
    profile_payload: dict[str, Any],
    *,
    platform_run_id: str,
    scenario_run_id: str,
    mounted_df_snapshot_ref: str,
    mounted_dla_policy_ref: str,
) -> dict[str, Any]:
    payload = json.loads(json.dumps(profile_payload))

    df_payload = _ensure_mapping(payload, "df")
    df_policy = _ensure_mapping(df_payload, "policy")
    df_policy["registry_snapshot_ref"] = mounted_df_snapshot_ref

    dla_payload = _ensure_mapping(payload, "dla")
    dla_policy = _ensure_mapping(dla_payload, "policy")
    dla_policy["intake_policy_ref"] = mounted_dla_policy_ref
    dla_wiring = _ensure_mapping(dla_payload, "wiring")
    dla_wiring["required_platform_run_id"] = platform_run_id
    dla_wiring["stream_id"] = f"dla.intake.v0::{platform_run_id}"
    dla_wiring["event_bus_start_position"] = "latest"

    for component in (
        "context_store_flow_binding",
        "ieg",
        "ofp",
        "df",
        "al",
        "archive_writer",
        "case_trigger",
        "case_mgmt",
        "label_store",
        "ofs",
        "mf",
    ):
        comp_payload = payload.get(component)
        if not isinstance(comp_payload, dict):
            continue
        wiring = _ensure_mapping(comp_payload, "wiring")
        wiring["required_platform_run_id"] = platform_run_id

    label_store_payload = _ensure_mapping(payload, "label_store")
    label_store_wiring = _ensure_mapping(label_store_payload, "wiring")
    label_store_wiring["scenario_run_id"] = scenario_run_id

    for component, request_prefix in (
        ("ofs", f"{platform_run_id}/ofs/job_requests"),
        ("mf", f"{platform_run_id}/mf/job_requests"),
    ):
        comp_payload = payload.get(component)
        if not isinstance(comp_payload, dict):
            continue
        wiring = _ensure_mapping(comp_payload, "wiring")
        wiring["request_prefix"] = request_prefix

    return payload


def service_account_manifest(namespace: str, name: str, role_arn: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "annotations": {"eks.amazonaws.com/role-arn": role_arn},
        },
    }


def env_ref(name: str, secret_name: str, key: str) -> dict[str, Any]:
    return {
        "name": name,
        "valueFrom": {
            "secretKeyRef": {"name": secret_name, "key": key}
        },
    }


def plain_env(name: str, value: str) -> dict[str, Any]:
    return {"name": name, "value": value}


def normalize_container_path(raw_path: str) -> str:
    text = str(raw_path or "").strip().replace("\\", "/")
    if not text:
        raise RuntimeError("container path must be non-empty")
    if not text.startswith("/"):
        text = "/" + text.lstrip("/")
    return PurePosixPath(text).as_posix()


def deployment_manifest(
    *,
    namespace: str,
    name: str,
    service_account: str,
    image: str,
    command: list[str],
    env: list[dict[str, Any]],
    volume_mounts: list[dict[str, Any]],
    volumes: list[dict[str, Any]],
    cpu_request: str,
    cpu_limit: str,
    mem_request: str,
    mem_limit: str,
    labels: dict[str, str],
) -> dict[str, Any]:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": {
            "replicas": 1,
            "revisionHistoryLimit": 2,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {**labels, "app": name}},
                "spec": {
                    "serviceAccountName": service_account,
                    "restartPolicy": "Always",
                    "containers": [
                        {
                            "name": "worker",
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": command,
                            "env": env,
                            "volumeMounts": volume_mounts,
                            "resources": {
                                "requests": {"cpu": cpu_request, "memory": mem_request},
                                "limits": {"cpu": cpu_limit, "memory": mem_limit},
                            },
                        }
                    ],
                    "volumes": volumes,
                },
            },
        },
    }


def rollout_status(namespace: str, name: str, *, timeout_seconds: int) -> tuple[bool, str]:
    proc = run(
        ["kubectl", "rollout", "status", f"deployment/{name}", "-n", namespace, f"--timeout={timeout_seconds}s"],
        timeout=timeout_seconds + 30,
        check=False,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def collect_deployment_status(namespace: str, name: str) -> dict[str, Any]:
    deployment = get_json(["kubectl", "get", "deployment", name, "-n", namespace, "-o", "json"], timeout=120)
    pods = get_json(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={name}", "-o", "json"], timeout=120)
    items = list(pods.get("items", []))
    pod_rows = []
    for pod in items:
        statuses = list(pod.get("status", {}).get("containerStatuses", []) or [])
        restarts = int(sum(int(row.get("restartCount", 0) or 0) for row in statuses))
        pod_rows.append(
            {
                "name": str(pod.get("metadata", {}).get("name", "")).strip(),
                "phase": str(pod.get("status", {}).get("phase", "")).strip(),
                "pod_ip": str(pod.get("status", {}).get("podIP", "")).strip(),
                "host_ip": str(pod.get("status", {}).get("hostIP", "")).strip(),
                "restarts": restarts,
                "ready": all(bool(row.get("ready")) for row in statuses) if statuses else False,
                "image": str((statuses[0].get("image") if statuses else "") or "").strip(),
            }
        )
    return {
        "namespace": namespace,
        "deployment": {
            "name": name,
            "namespace": namespace,
            "ready_replicas": int(deployment.get("status", {}).get("readyReplicas", 0) or 0),
            "updated_replicas": int(deployment.get("status", {}).get("updatedReplicas", 0) or 0),
            "available_replicas": int(deployment.get("status", {}).get("availableReplicas", 0) or 0),
            "observed_generation": int(deployment.get("status", {}).get("observedGeneration", 0) or 0),
        },
        "pods": pod_rows,
    }


def tail_logs(namespace: str, pod_name: str, *, tail: int = 80) -> str:
    proc = run(["kubectl", "logs", pod_name, "-n", namespace, "--tail", str(tail)], timeout=120, check=False)
    return (proc.stdout or proc.stderr or "").strip()


def validate_run_identity(*, platform_run_id: str, scenario_run_id: str) -> list[str]:
    blockers: list[str] = []
    if not str(platform_run_id).strip():
        blockers.append("PR3.RUNTIME.B00_PLATFORM_RUN_ID_EMPTY")
    if not SCENARIO_RUN_ID_RX.fullmatch(str(scenario_run_id).strip()):
        blockers.append(f"PR3.RUNTIME.B00_INVALID_SCENARIO_RUN_ID:{str(scenario_run_id).strip() or 'empty'}")
    return blockers


def main() -> int:
    ap = argparse.ArgumentParser(description="Materialize PR3 runtime workers on remote EKS.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--scenario-run-id", required=True)
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--namespace", default="")
    ap.add_argument("--case-labels-namespace", default="")
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    ap.add_argument("--profile-source-path", default="config/platform/profiles/dev_full.yaml")
    ap.add_argument("--df-registry-snapshot-source-path", default="config/platform/df/registry_snapshot_dev_full_v0.yaml")
    ap.add_argument("--dla-intake-policy-source-path", default="config/platform/dla/intake_policy_v0.yaml")
    ap.add_argument("--wsp-task-family", default="fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--image-uri", default="")
    ap.add_argument("--aurora-db-name", default="fraud_platform")
    ap.add_argument("--aurora-port", type=int, default=5432)
    ap.add_argument("--ig-ingest-url", default="https://ehwznd2uw7.execute-api.eu-west-2.amazonaws.com/v1/ingest/push")
    ap.add_argument("--ig-api-key-ssm-path", default="/fraud-platform/dev_full/ig/api_key")
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    registry = parse_registry(REGISTRY)
    namespace = str(args.namespace or registry.get("EKS_NAMESPACE_RTDL", "")).strip() or "fraud-platform-rtdl"
    case_labels_namespace = (
        str(args.case_labels_namespace or registry.get("EKS_NAMESPACE_CASE_LABELS", "")).strip()
        or "fraud-platform-case-labels"
    )
    pr3_root = Path(args.run_control_root) / args.pr3_execution_id
    pr3_root.mkdir(parents=True, exist_ok=True)
    manifest_path = pr3_root / "g3a_runtime_materialization_manifest.json"
    summary_path = pr3_root / "g3a_runtime_materialization_summary.json"
    archive_existing(manifest_path)
    archive_existing(summary_path)

    blockers: list[str] = []
    notes: list[str] = []
    blockers.extend(
        validate_run_identity(
            platform_run_id=args.platform_run_id,
            scenario_run_id=args.scenario_run_id,
        )
    )

    ssm_paths = [
        str(registry.get("SSM_AURORA_ENDPOINT_PATH", "")).strip(),
        str(registry.get("SSM_AURORA_USERNAME_PATH", "")).strip(),
        str(registry.get("SSM_AURORA_PASSWORD_PATH", "")).strip(),
        str(args.ig_api_key_ssm_path).strip(),
    ]
    required_handles = [
        "ROLE_EKS_IRSA_RTDL",
        "ROLE_EKS_IRSA_DECISION_LANE",
        "ROLE_EKS_IRSA_CASE_LABELS",
        "MSK_BOOTSTRAP_BROKERS_SASL_IAM",
        "FP_BUS_RTDL_V1",
        "FP_BUS_AUDIT_V1",
    ]
    for handle in required_handles:
        if not str(registry.get(handle, "")).strip():
            blockers.append(f"PR3.RUNTIME.B01_HANDLE_MISSING:{handle}")

    if blockers:
        dump_json(
            summary_path,
            {
                "phase": "PR3",
                "state": "S1_RUNTIME",
                "generated_at_utc": now_utc(),
                "generated_by": args.generated_by,
                "version": args.version,
                "execution_id": args.pr3_execution_id,
                "overall_pass": False,
                "blocker_ids": blockers,
                "notes": notes,
            },
        )
        return 1

    ecs = boto3.client("ecs", region_name=args.region)
    ssm = boto3.client("ssm", region_name=args.region)

    try:
        resolved_ssm = resolve_ssm_parameters(ssm, names=ssm_paths)
    except RuntimeError as exc:
        blockers.append(f"PR3.RUNTIME.B02_SSM_UNRESOLVED:{exc}")
        resolved_ssm = {}

    try:
        image_uri = str(args.image_uri).strip() or resolve_task_image(ecs, family=args.wsp_task_family, region=args.region)
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"PR3.RUNTIME.B03_IMAGE_UNRESOLVED:{type(exc).__name__}")
        image_uri = ""

    if blockers:
        dump_json(
            summary_path,
            {
                "phase": "PR3",
                "state": "S1_RUNTIME",
                "generated_at_utc": now_utc(),
                "generated_by": args.generated_by,
                "version": args.version,
                "execution_id": args.pr3_execution_id,
                "overall_pass": False,
                "blocker_ids": blockers,
                "notes": notes,
            },
        )
        return 1

    aurora_dsn = build_aurora_dsn(
        endpoint=resolved_ssm[str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip()],
        username=resolved_ssm[str(registry["SSM_AURORA_USERNAME_PATH"]).strip()],
        password=resolved_ssm[str(registry["SSM_AURORA_PASSWORD_PATH"]).strip()],
        db_name=args.aurora_db_name,
        port=args.aurora_port,
    )
    ig_api_key = resolved_ssm[str(args.ig_api_key_ssm_path).strip()]

    labels = {
        "fp.phase": "PR3",
        "fp.track": "road_to_prod",
        "fp.platform_run_id": args.platform_run_id,
    }
    secret_name = "fp-pr3-runtime-secrets"
    profile_configmap_name = "fp-pr3-runtime-profile"
    # Match the pre-materialized IRSA trust subjects instead of inventing new
    # service-account names that bypass the pinned IAM posture.
    rtdl_sa = "rtdl"
    decision_sa = "decision-lane"
    case_labels_sa = "case-labels"
    profile_path_in_container = normalize_container_path(args.profile_path)
    profile_mount_dir = str(PurePosixPath(profile_path_in_container).parent)

    profile_source_path = Path(args.profile_source_path)
    if not profile_source_path.exists():
        raise RuntimeError(f"profile source path missing: {profile_source_path}")
    snapshot_source_path = Path(args.df_registry_snapshot_source_path)
    if not snapshot_source_path.exists():
        raise RuntimeError(f"DF registry snapshot source path missing: {snapshot_source_path}")
    dla_policy_source_path = Path(args.dla_intake_policy_source_path)
    if not dla_policy_source_path.exists():
        raise RuntimeError(f"DLA intake policy source path missing: {dla_policy_source_path}")
    profile_payload = yaml.safe_load(profile_source_path.read_text(encoding="utf-8"))
    if not isinstance(profile_payload, dict):
        raise RuntimeError(f"profile source path invalid YAML mapping: {profile_source_path}")
    mounted_snapshot_ref = str(PurePosixPath(profile_mount_dir) / snapshot_source_path.name)
    mounted_dla_policy_ref = str(PurePosixPath(profile_mount_dir) / dla_policy_source_path.name)
    profile_payload = _materialize_run_scoped_profile(
        profile_payload,
        platform_run_id=args.platform_run_id,
        scenario_run_id=args.scenario_run_id,
        mounted_df_snapshot_ref=mounted_snapshot_ref,
        mounted_dla_policy_ref=mounted_dla_policy_ref,
    )
    profile_text = yaml.safe_dump(profile_payload, sort_keys=False)
    snapshot_text = snapshot_source_path.read_text(encoding="utf-8")
    dla_policy_text = dla_policy_source_path.read_text(encoding="utf-8")

    for ns in {namespace, case_labels_namespace}:
        kubectl_apply(namespace_manifest(ns))

    kubectl_apply(service_account_manifest(namespace, rtdl_sa, str(registry["ROLE_EKS_IRSA_RTDL"]).strip()))
    kubectl_apply(service_account_manifest(namespace, decision_sa, str(registry["ROLE_EKS_IRSA_DECISION_LANE"]).strip()))
    kubectl_apply(
        service_account_manifest(case_labels_namespace, case_labels_sa, str(registry["ROLE_EKS_IRSA_CASE_LABELS"]).strip())
    )
    for ns in {namespace, case_labels_namespace}:
        kubectl_apply(
            config_map_manifest(
                ns,
                profile_configmap_name,
                {
                    "dev_full.yaml": profile_text,
                    snapshot_source_path.name: snapshot_text,
                    dla_policy_source_path.name: dla_policy_text,
                },
            )
        )

    secret_data = {
        "KAFKA_BOOTSTRAP_SERVERS": str(registry["MSK_BOOTSTRAP_BROKERS_SASL_IAM"]).strip(),
        "KAFKA_AWS_REGION": args.region,
        "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
        "KAFKA_SASL_MECHANISM": "OAUTHBEARER",
        "KAFKA_REQUEST_TIMEOUT_MS": "30000",
        "KAFKA_POLL_TIMEOUT_MS": "500",
        "KAFKA_MAX_POLL_RECORDS": "500",
        "OBJECT_STORE_REGION": args.region,
        "PLATFORM_RUN_ID": args.platform_run_id,
        "ACTIVE_PLATFORM_RUN_ID": args.platform_run_id,
        "ACTIVE_SCENARIO_RUN_ID": args.scenario_run_id,
        "DL_SCENARIO_RUN_ID": args.scenario_run_id,
        "DF_SCENARIO_RUN_ID": args.scenario_run_id,
        "AL_SCENARIO_RUN_ID": args.scenario_run_id,
        "DLA_SCENARIO_RUN_ID": args.scenario_run_id,
        "CASE_TRIGGER_SCENARIO_RUN_ID": args.scenario_run_id,
        "CASE_MGMT_SCENARIO_RUN_ID": args.scenario_run_id,
        "LABEL_STORE_SCENARIO_RUN_ID": args.scenario_run_id,
        "DF_PUBLISH_MODE": "internal_bus",
        "AL_PUBLISH_MODE": "internal_bus",
        "CASE_TRIGGER_PUBLISH_MODE": "internal_bus",
        "CSFB_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "IEG_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "OFP_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "DF_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "AL_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "DLA_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "ARCHIVE_WRITER_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "CASE_TRIGGER_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "CASE_MGMT_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "LABEL_STORE_REQUIRED_PLATFORM_RUN_ID": args.platform_run_id,
        "DF_IG_API_KEY": ig_api_key,
        "AL_IG_API_KEY": ig_api_key,
        "CASE_TRIGGER_IG_API_KEY": ig_api_key,
        "IG_API_KEY": ig_api_key,
        "IG_INGEST_URL": args.ig_ingest_url,
        "CSFB_PROJECTION_DSN": aurora_dsn,
        "IEG_PROJECTION_DSN": aurora_dsn,
        "OFP_PROJECTION_DSN": aurora_dsn,
        "OFP_SNAPSHOT_INDEX_DSN": aurora_dsn,
        "DL_POSTURE_DSN": aurora_dsn,
        "DL_OUTBOX_DSN": aurora_dsn,
        "DL_OPS_DSN": aurora_dsn,
        "DF_REPLAY_DSN": aurora_dsn,
        "DF_CHECKPOINT_DSN": aurora_dsn,
        "AL_LEDGER_DSN": aurora_dsn,
        "AL_OUTCOMES_DSN": aurora_dsn,
        "AL_REPLAY_DSN": aurora_dsn,
        "AL_CHECKPOINT_DSN": aurora_dsn,
        "DLA_INDEX_DSN": aurora_dsn,
        "ARCHIVE_WRITER_LEDGER_DSN": aurora_dsn,
        "CASE_TRIGGER_REPLAY_DSN": aurora_dsn,
        "CASE_TRIGGER_CHECKPOINT_DSN": aurora_dsn,
        "CASE_TRIGGER_PUBLISH_STORE_DSN": aurora_dsn,
        "CASE_MGMT_LOCATOR": aurora_dsn,
        "LABEL_STORE_LOCATOR": aurora_dsn,
    }
    for ns in {namespace, case_labels_namespace}:
        kubectl_apply(secret_manifest(ns, secret_name, secret_data))

    common_secret_env = [
        env_ref("AWS_REGION", secret_name, "KAFKA_AWS_REGION"),
        env_ref("AWS_DEFAULT_REGION", secret_name, "KAFKA_AWS_REGION"),
        env_ref("KAFKA_BOOTSTRAP_SERVERS", secret_name, "KAFKA_BOOTSTRAP_SERVERS"),
        env_ref("KAFKA_AWS_REGION", secret_name, "KAFKA_AWS_REGION"),
        env_ref("KAFKA_SECURITY_PROTOCOL", secret_name, "KAFKA_SECURITY_PROTOCOL"),
        env_ref("KAFKA_SASL_MECHANISM", secret_name, "KAFKA_SASL_MECHANISM"),
        env_ref("KAFKA_REQUEST_TIMEOUT_MS", secret_name, "KAFKA_REQUEST_TIMEOUT_MS"),
        env_ref("KAFKA_POLL_TIMEOUT_MS", secret_name, "KAFKA_POLL_TIMEOUT_MS"),
        env_ref("KAFKA_MAX_POLL_RECORDS", secret_name, "KAFKA_MAX_POLL_RECORDS"),
        env_ref("OBJECT_STORE_REGION", secret_name, "OBJECT_STORE_REGION"),
        env_ref("PLATFORM_RUN_ID", secret_name, "PLATFORM_RUN_ID"),
        env_ref("ACTIVE_PLATFORM_RUN_ID", secret_name, "ACTIVE_PLATFORM_RUN_ID"),
        env_ref("ACTIVE_SCENARIO_RUN_ID", secret_name, "ACTIVE_SCENARIO_RUN_ID"),
        env_ref("DF_SCENARIO_RUN_ID", secret_name, "DF_SCENARIO_RUN_ID"),
        env_ref("AL_SCENARIO_RUN_ID", secret_name, "AL_SCENARIO_RUN_ID"),
        env_ref("DLA_SCENARIO_RUN_ID", secret_name, "DLA_SCENARIO_RUN_ID"),
        env_ref("CASE_TRIGGER_SCENARIO_RUN_ID", secret_name, "CASE_TRIGGER_SCENARIO_RUN_ID"),
        env_ref("CASE_MGMT_SCENARIO_RUN_ID", secret_name, "CASE_MGMT_SCENARIO_RUN_ID"),
        env_ref("LABEL_STORE_SCENARIO_RUN_ID", secret_name, "LABEL_STORE_SCENARIO_RUN_ID"),
        env_ref("DF_PUBLISH_MODE", secret_name, "DF_PUBLISH_MODE"),
        env_ref("AL_PUBLISH_MODE", secret_name, "AL_PUBLISH_MODE"),
        env_ref("CASE_TRIGGER_PUBLISH_MODE", secret_name, "CASE_TRIGGER_PUBLISH_MODE"),
        plain_env("PYTHONUNBUFFERED", "1"),
    ]
    profile_volume_mounts = [
        {
            "name": "runtime-profile",
            "mountPath": profile_mount_dir,
            "readOnly": True,
        }
    ]
    profile_volumes = [
        {
            "name": "runtime-profile",
            "configMap": {"name": profile_configmap_name},
        }
    ]

    workloads = [
        {
            "name": "fp-pr3-csfb",
            "service_account": rtdl_sa,
            "command": ["python", "-m", "fraud_detection.context_store_flow_binding.intake", "--policy", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("CSFB_REQUIRED_PLATFORM_RUN_ID", secret_name, "CSFB_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("CSFB_PROJECTION_DSN", secret_name, "CSFB_PROJECTION_DSN"),
            ],
            "cpu_request": "500m",
            "cpu_limit": "2",
            "mem_request": "1Gi",
            "mem_limit": "4Gi",
            "lane": "RTDL_CORE",
        },
        {
            "name": "fp-pr3-ieg",
            "namespace": namespace,
            "service_account": rtdl_sa,
            "command": ["python", "-m", "fraud_detection.identity_entity_graph.projector", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("CSFB_REQUIRED_PLATFORM_RUN_ID", secret_name, "CSFB_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("CSFB_PROJECTION_DSN", secret_name, "CSFB_PROJECTION_DSN"),
                env_ref("IEG_REQUIRED_PLATFORM_RUN_ID", secret_name, "IEG_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("IEG_PROJECTION_DSN", secret_name, "IEG_PROJECTION_DSN"),
            ],
            "cpu_request": "500m",
            "cpu_limit": "2",
            "mem_request": "1Gi",
            "mem_limit": "4Gi",
            "lane": "RTDL_CORE",
        },
        {
            "name": "fp-pr3-ofp",
            "namespace": namespace,
            "service_account": rtdl_sa,
            "command": ["python", "-m", "fraud_detection.online_feature_plane.projector", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("CSFB_REQUIRED_PLATFORM_RUN_ID", secret_name, "CSFB_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("CSFB_PROJECTION_DSN", secret_name, "CSFB_PROJECTION_DSN"),
                env_ref("OFP_REQUIRED_PLATFORM_RUN_ID", secret_name, "OFP_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("OFP_PROJECTION_DSN", secret_name, "OFP_PROJECTION_DSN"),
                env_ref("OFP_SNAPSHOT_INDEX_DSN", secret_name, "OFP_SNAPSHOT_INDEX_DSN"),
            ],
            "cpu_request": "500m",
            "cpu_limit": "2",
            "mem_request": "1Gi",
            "mem_limit": "4Gi",
            "lane": "RTDL_CORE",
        },
        {
            "name": "fp-pr3-archive-writer",
            "namespace": namespace,
            "service_account": rtdl_sa,
            "command": ["python", "-m", "fraud_detection.archive_writer.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("ARCHIVE_WRITER_REQUIRED_PLATFORM_RUN_ID", secret_name, "ARCHIVE_WRITER_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("ARCHIVE_WRITER_LEDGER_DSN", secret_name, "ARCHIVE_WRITER_LEDGER_DSN"),
            ],
            "cpu_request": "250m",
            "cpu_limit": "1",
            "mem_request": "512Mi",
            "mem_limit": "2Gi",
            "lane": "ARCHIVE",
        },
        {
            "name": "fp-pr3-dl",
            "namespace": namespace,
            "service_account": decision_sa,
            "command": ["python", "-m", "fraud_detection.degrade_ladder.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("DL_SCENARIO_RUN_ID", secret_name, "DL_SCENARIO_RUN_ID"),
                env_ref("CSFB_PROJECTION_DSN", secret_name, "CSFB_PROJECTION_DSN"),
                env_ref("IEG_PROJECTION_DSN", secret_name, "IEG_PROJECTION_DSN"),
                env_ref("OFP_PROJECTION_DSN", secret_name, "OFP_PROJECTION_DSN"),
                env_ref("OFP_SNAPSHOT_INDEX_DSN", secret_name, "OFP_SNAPSHOT_INDEX_DSN"),
                env_ref("DL_POSTURE_DSN", secret_name, "DL_POSTURE_DSN"),
                env_ref("DL_OUTBOX_DSN", secret_name, "DL_OUTBOX_DSN"),
                env_ref("DL_OPS_DSN", secret_name, "DL_OPS_DSN"),
            ],
            "cpu_request": "250m",
            "cpu_limit": "1",
            "mem_request": "512Mi",
            "mem_limit": "2Gi",
            "lane": "DECISION",
        },
        {
            "name": "fp-pr3-df",
            "namespace": namespace,
            "service_account": decision_sa,
            "command": ["python", "-m", "fraud_detection.decision_fabric.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("CSFB_REQUIRED_PLATFORM_RUN_ID", secret_name, "CSFB_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("CSFB_PROJECTION_DSN", secret_name, "CSFB_PROJECTION_DSN"),
                env_ref("IEG_REQUIRED_PLATFORM_RUN_ID", secret_name, "IEG_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("IEG_PROJECTION_DSN", secret_name, "IEG_PROJECTION_DSN"),
                env_ref("OFP_REQUIRED_PLATFORM_RUN_ID", secret_name, "OFP_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("OFP_PROJECTION_DSN", secret_name, "OFP_PROJECTION_DSN"),
                env_ref("OFP_SNAPSHOT_INDEX_DSN", secret_name, "OFP_SNAPSHOT_INDEX_DSN"),
                env_ref("DF_REQUIRED_PLATFORM_RUN_ID", secret_name, "DF_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("DF_REPLAY_DSN", secret_name, "DF_REPLAY_DSN"),
                env_ref("DF_CHECKPOINT_DSN", secret_name, "DF_CHECKPOINT_DSN"),
                env_ref("DL_POSTURE_DSN", secret_name, "DL_POSTURE_DSN"),
                env_ref("DF_IG_API_KEY", secret_name, "DF_IG_API_KEY"),
                env_ref("IG_INGEST_URL", secret_name, "IG_INGEST_URL"),
            ],
            "cpu_request": "500m",
            "cpu_limit": "2",
            "mem_request": "1Gi",
            "mem_limit": "3Gi",
            "lane": "DECISION",
        },
        {
            "name": "fp-pr3-al",
            "namespace": namespace,
            "service_account": decision_sa,
            "command": ["python", "-m", "fraud_detection.action_layer.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("AL_REQUIRED_PLATFORM_RUN_ID", secret_name, "AL_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("AL_LEDGER_DSN", secret_name, "AL_LEDGER_DSN"),
                env_ref("AL_OUTCOMES_DSN", secret_name, "AL_OUTCOMES_DSN"),
                env_ref("AL_REPLAY_DSN", secret_name, "AL_REPLAY_DSN"),
                env_ref("AL_CHECKPOINT_DSN", secret_name, "AL_CHECKPOINT_DSN"),
                env_ref("AL_IG_API_KEY", secret_name, "AL_IG_API_KEY"),
                env_ref("IG_INGEST_URL", secret_name, "IG_INGEST_URL"),
            ],
            "cpu_request": "500m",
            "cpu_limit": "2",
            "mem_request": "1Gi",
            "mem_limit": "3Gi",
            "lane": "DECISION",
        },
        {
            "name": "fp-pr3-dla",
            "namespace": namespace,
            "service_account": decision_sa,
            "command": ["python", "-m", "fraud_detection.decision_log_audit.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("DLA_REQUIRED_PLATFORM_RUN_ID", secret_name, "DLA_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("DLA_INDEX_DSN", secret_name, "DLA_INDEX_DSN"),
            ],
            "cpu_request": "250m",
            "cpu_limit": "1",
            "mem_request": "512Mi",
            "mem_limit": "2Gi",
            "lane": "DECISION",
        },
        {
            "name": "fp-pr3-case-trigger",
            "namespace": case_labels_namespace,
            "service_account": case_labels_sa,
            "command": ["python", "-m", "fraud_detection.case_trigger.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("CASE_TRIGGER_REQUIRED_PLATFORM_RUN_ID", secret_name, "CASE_TRIGGER_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("CASE_TRIGGER_REPLAY_DSN", secret_name, "CASE_TRIGGER_REPLAY_DSN"),
                env_ref("CASE_TRIGGER_CHECKPOINT_DSN", secret_name, "CASE_TRIGGER_CHECKPOINT_DSN"),
                env_ref("CASE_TRIGGER_PUBLISH_STORE_DSN", secret_name, "CASE_TRIGGER_PUBLISH_STORE_DSN"),
                env_ref("CASE_TRIGGER_IG_API_KEY", secret_name, "CASE_TRIGGER_IG_API_KEY"),
                env_ref("IG_INGEST_URL", secret_name, "IG_INGEST_URL"),
            ],
            "cpu_request": "250m",
            "cpu_limit": "1",
            "mem_request": "512Mi",
            "mem_limit": "2Gi",
            "lane": "CASE_LABELS",
        },
        {
            "name": "fp-pr3-case-mgmt",
            "namespace": case_labels_namespace,
            "service_account": case_labels_sa,
            "command": ["python", "-m", "fraud_detection.case_mgmt.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("CASE_MGMT_REQUIRED_PLATFORM_RUN_ID", secret_name, "CASE_MGMT_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("CASE_MGMT_LOCATOR", secret_name, "CASE_MGMT_LOCATOR"),
                env_ref("LABEL_STORE_LOCATOR", secret_name, "LABEL_STORE_LOCATOR"),
            ],
            "cpu_request": "250m",
            "cpu_limit": "1",
            "mem_request": "512Mi",
            "mem_limit": "2Gi",
            "lane": "CASE_LABELS",
        },
        {
            "name": "fp-pr3-label-store",
            "namespace": case_labels_namespace,
            "service_account": case_labels_sa,
            "command": ["python", "-m", "fraud_detection.label_store.worker", "--profile", profile_path_in_container],
            "env": common_secret_env
            + [
                env_ref("LABEL_STORE_REQUIRED_PLATFORM_RUN_ID", secret_name, "LABEL_STORE_REQUIRED_PLATFORM_RUN_ID"),
                env_ref("LABEL_STORE_SCENARIO_RUN_ID", secret_name, "LABEL_STORE_SCENARIO_RUN_ID"),
                env_ref("LABEL_STORE_LOCATOR", secret_name, "LABEL_STORE_LOCATOR"),
            ],
            "cpu_request": "250m",
            "cpu_limit": "1",
            "mem_request": "512Mi",
            "mem_limit": "2Gi",
            "lane": "CASE_LABELS",
        },
    ]

    for workload in workloads:
        doc = deployment_manifest(
            namespace=str(workload["namespace"]),
            name=str(workload["name"]),
            service_account=str(workload["service_account"]),
            image=image_uri,
            command=list(workload["command"]),
            env=list(workload["env"]),
            volume_mounts=profile_volume_mounts,
            volumes=profile_volumes,
            cpu_request=str(workload["cpu_request"]),
            cpu_limit=str(workload["cpu_limit"]),
            mem_request=str(workload["mem_request"]),
            mem_limit=str(workload["mem_limit"]),
            labels={**labels, "fp.workload": str(workload["name"]), "fp.lane": str(workload["lane"])},
        )
        kubectl_apply(doc)

    rollout_results = []
    for workload in workloads:
        workload_namespace = str(workload["namespace"])
        ok, detail = rollout_status(workload_namespace, str(workload["name"]), timeout_seconds=300)
        rollout_results.append({"name": workload["name"], "namespace": workload_namespace, "ok": ok, "detail": detail})
        if not ok:
            blockers.append(f"PR3.RUNTIME.B04_ROLLOUT_FAILED:{workload['name']}")

    deployment_statuses = [
        collect_deployment_status(str(workload["namespace"]), str(workload["name"])) for workload in workloads
    ]
    failure_logs = {}
    if blockers:
        for status in deployment_statuses:
            status_namespace = str(status.get("namespace", "")).strip() or namespace
            for pod in status.get("pods", []):
                if not bool(pod.get("ready")):
                    failure_logs[f"{status_namespace}/{pod['name']}"] = tail_logs(status_namespace, str(pod["name"]))

    manifest = {
        "phase": "PR3",
        "state": "S1_RUNTIME",
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "namespaces": {
            "rtdl": namespace,
            "case_labels": case_labels_namespace,
        },
        "image_uri": image_uri,
        "profile_path": profile_path_in_container,
        "df_registry_snapshot_source_path": str(snapshot_source_path),
        "df_registry_snapshot_mounted_ref": mounted_snapshot_ref,
        "dla_intake_policy_source_path": str(dla_policy_source_path),
        "dla_intake_policy_mounted_ref": mounted_dla_policy_ref,
        "secret_name": secret_name,
        "profile_configmap_name": profile_configmap_name,
        "service_accounts": {
            "rtdl": {"name": rtdl_sa, "namespace": namespace, "role_arn": str(registry["ROLE_EKS_IRSA_RTDL"]).strip()},
            "decision": {
                "name": decision_sa,
                "namespace": namespace,
                "role_arn": str(registry["ROLE_EKS_IRSA_DECISION_LANE"]).strip(),
            },
            "case_labels": {
                "name": case_labels_sa,
                "namespace": case_labels_namespace,
                "role_arn": str(registry["ROLE_EKS_IRSA_CASE_LABELS"]).strip(),
            },
        },
        "workloads": [
            {
                "name": workload["name"],
                "namespace": workload["namespace"],
                "lane": workload["lane"],
                "command": workload["command"],
                "resources": {
                    "cpu_request": workload["cpu_request"],
                    "cpu_limit": workload["cpu_limit"],
                    "mem_request": workload["mem_request"],
                    "mem_limit": workload["mem_limit"],
                },
            }
            for workload in workloads
        ],
        "handles": {
            "MSK_BOOTSTRAP_BROKERS_SASL_IAM": str(registry["MSK_BOOTSTRAP_BROKERS_SASL_IAM"]).strip(),
            "FP_BUS_RTDL_V1": str(registry["FP_BUS_RTDL_V1"]).strip(),
            "FP_BUS_AUDIT_V1": str(registry["FP_BUS_AUDIT_V1"]).strip(),
            "FP_BUS_CASE_TRIGGERS_V1": str(registry["FP_BUS_CASE_TRIGGERS_V1"]).strip(),
            "FP_BUS_LABELS_EVENTS_V1": str(registry["FP_BUS_LABELS_EVENTS_V1"]).strip(),
        },
    }
    summary = {
        "phase": "PR3",
        "state": "S1_RUNTIME",
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "overall_pass": len(blockers) == 0,
        "blocker_ids": sorted(set(blockers)),
        "rollout_results": rollout_results,
        "deployment_statuses": deployment_statuses,
        "failure_logs": failure_logs,
        "notes": notes,
    }
    dump_json(manifest_path, manifest)
    dump_json(summary_path, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
