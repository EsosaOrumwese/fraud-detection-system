#!/usr/bin/env python3
"""Execute Phase 6 coupled runtime-learning readiness on the live dev_full boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = str(env.get("PYTHONPATH") or "").strip()
    roots = os.pathsep.join([str(SRC_ROOT), str(REPO_ROOT)])
    env["PYTHONPATH"] = roots if not existing else roots + os.pathsep + existing
    return env


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cmd(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], check=True, env=child_env())


def run_cli(args: list[str], *, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False, env=child_env())
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(args)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inherit_phase4_envelope(*, summary: dict[str, Any], args: argparse.Namespace) -> None:
    campaign = dict(summary.get("campaign") or {})
    rate_plan = list(campaign.get("rate_plan_per_lane") or [])
    first_step = dict(rate_plan[0]) if rate_plan else {}
    target_eps = float(first_step.get("target_eps") or 0.0)
    initial_tokens = float(first_step.get("initial_tokens") or 0.0)
    burst_step_initial_tokens = campaign.get("burst_step_initial_tokens")
    if burst_step_initial_tokens is None and len(rate_plan) >= 3:
        burst_step_initial_tokens = dict(rate_plan[2]).get("initial_tokens")
    inherited = {
        "lane_count": int(campaign["lane_count"]) if campaign.get("lane_count") is not None else args.lane_count,
        "steady_seconds": int(campaign["steady_seconds"]) if campaign.get("steady_seconds") is not None else args.steady_seconds,
        "burst_seconds": int(campaign["burst_seconds"]) if campaign.get("burst_seconds") is not None else args.burst_seconds,
        "recovery_seconds": int(campaign["recovery_seconds"]) if campaign.get("recovery_seconds") is not None else args.recovery_seconds,
        "presteady_seconds": int(campaign["presteady_seconds"]) if campaign.get("presteady_seconds") is not None else args.presteady_seconds,
        "presteady_eps": float(campaign["presteady_eps"]) if campaign.get("presteady_eps") is not None else args.presteady_eps,
        "steady_eps": float(campaign["steady_eps"]) if campaign.get("steady_eps") is not None else args.steady_eps,
        "burst_eps": float(campaign["burst_eps"]) if campaign.get("burst_eps") is not None else args.burst_eps,
        "stream_speedup": float(campaign["stream_speedup"]) if campaign.get("stream_speedup") is not None else args.stream_speedup,
        "short_upward_transition_lane_stagger_seconds": float(campaign["short_upward_transition_lane_stagger_seconds"])
        if campaign.get("short_upward_transition_lane_stagger_seconds") is not None
        else args.short_upward_transition_lane_stagger_seconds,
        "burst_step_initial_tokens": float(burst_step_initial_tokens)
        if burst_step_initial_tokens is not None
        else args.burst_step_initial_tokens,
        "target_burst_seconds": float(first_step.get("burst_seconds") or args.target_burst_seconds),
        "target_initial_tokens": float(initial_tokens / target_eps) if target_eps > 0.0 else float(args.target_initial_tokens),
    }
    for key, value in inherited.items():
        setattr(args, key, value)


def archive_copy(src: Path, dest: Path) -> None:
    if not src.exists():
        raise RuntimeError(f"phase6_expected_artifact_missing:{src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def fresh_execution_id() -> str:
    return f"phase6_learning_coupled_{utc_stamp()}"


def fresh_platform_run_id() -> str:
    return f"platform_{utc_stamp()}"


def fresh_scenario_run_id(*, execution_id: str, window_label: str, platform_run_id: str) -> str:
    seed = f"{execution_id}:{window_label}:{platform_run_id}"
    return hashlib.md5(seed.encode("utf-8"), usedforsecurity=False).hexdigest()


def stop_wsp_tasks(region: str, receipt_path: Path, reason: str) -> None:
    code = f"""
from datetime import datetime, timezone
import json
from pathlib import Path
import boto3

ecs = boto3.client('ecs', region_name={region!r})
cluster = 'fraud-platform-dev-full-wsp-ephemeral'
task_arns = ecs.list_tasks(cluster=cluster, desiredStatus='RUNNING').get('taskArns', [])
stopped = []
if task_arns:
    described = ecs.describe_tasks(cluster=cluster, tasks=task_arns).get('tasks', [])
    for task in described:
        task_arn = str(task.get('taskArn') or '').strip()
        if not task_arn:
            continue
        ecs.stop_task(cluster=cluster, task=task_arn, reason={reason!r}[:255])
        stopped.append(task_arn.rsplit('/', 1)[-1])
payload = {{
    'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    'cluster': cluster,
    'stopped_tasks': stopped,
    'stopped_task_count': len(stopped),
    'reason': {reason!r},
}}
Path({str(receipt_path)!r}).write_text(json.dumps(payload, indent=2) + "\\n", encoding='utf-8')
"""
    subprocess.run([sys.executable, "-c", code], check=True, env=child_env())


def normalized_bundle_ref(bundle_ref: dict[str, Any]) -> dict[str, str]:
    bundle_id = str(bundle_ref.get("bundle_id") or "").strip().lower()
    bundle_version = str(bundle_ref.get("bundle_version") or "").strip()
    registry_ref = str(bundle_ref.get("registry_ref") or "").strip()
    if not bundle_id:
        bundle_id = "0" * 64
    elif len(bundle_id) != 64 or any(ch not in "0123456789abcdef" for ch in bundle_id):
        bundle_id = hashlib.sha256(
            json.dumps(
                {
                    "legacy_bundle_id": bundle_id,
                    "bundle_version": bundle_version,
                    "registry_ref": registry_ref,
                },
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    payload = {"bundle_id": bundle_id}
    if bundle_version:
        payload["bundle_version"] = bundle_version
    if registry_ref:
        payload["registry_ref"] = registry_ref
    return payload


def s3_json(ref: str, *, region: str) -> dict[str, Any]:
    parsed = urlparse(str(ref).strip())
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise RuntimeError(f"phase6_invalid_s3_ref:{ref}")
    s3 = boto3.client("s3", region_name=region)
    obj = s3.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
    return json.loads(obj["Body"].read().decode("utf-8"))


def bump_revision(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("r") and text[1:].isdigit():
        return f"r{int(text[1:]) + 1}"
    return f"{text}.phase6" if text else "r1"


def stage_registry_surfaces(
    *,
    root: Path,
    execution_id: str,
    phase5_summary: dict[str, Any],
    aws_region: str,
    base_policy_path: Path,
    base_snapshot_path: Path,
) -> dict[str, Any]:
    promoted_dir = root / "registry_surfaces"
    promoted_dir.mkdir(parents=True, exist_ok=True)

    base_policy = yaml.safe_load(base_policy_path.read_text(encoding="utf-8")) or {}
    base_snapshot = yaml.safe_load(base_snapshot_path.read_text(encoding="utf-8")) or {}
    lifecycle_ref = str((((phase5_summary.get("refs") or {}).get("registry_lifecycle_event_ref")) or "")).strip()
    lifecycle_event = s3_json(lifecycle_ref, region=aws_region)
    promoted_bundle = normalized_bundle_ref(
        {
            "bundle_id": str((((phase5_summary.get("governance") or {}).get("bundle_id")) or "")).strip(),
            "bundle_version": str((((phase5_summary.get("governance") or {}).get("bundle_version")) or "")).strip(),
            "registry_ref": str((((phase5_summary.get("refs") or {}).get("registry_bundle_ref")) or "")).strip(),
        }
    )
    previous_bundle = normalized_bundle_ref(dict((phase5_summary.get("governance") or {}).get("previous_active_bundle") or {}))

    promoted_policy = json.loads(json.dumps(base_policy))
    promoted_revision = bump_revision(str(promoted_policy.get("revision") or "r0"))
    promoted_policy["revision"] = promoted_revision
    explicit = dict(((promoted_policy.get("fallback") or {}).get("explicit_by_scope")) or {})
    explicit["dev_full|fraud|primary|"] = promoted_bundle
    explicit["dev_full|baseline|primary|"] = promoted_bundle
    promoted_policy.setdefault("fallback", {})["explicit_by_scope"] = explicit

    promoted_snapshot = json.loads(json.dumps(base_snapshot))
    promoted_snapshot["snapshot_id"] = f"df.registry.snapshot.dev_full.phase6.{execution_id}"
    for record in promoted_snapshot.get("records") or []:
        scope = dict(record.get("scope") or {})
        if str(scope.get("environment") or "").strip() != "dev_full":
            continue
        if str(scope.get("mode") or "").strip() not in {"fraud", "baseline"}:
            continue
        record["bundle_ref"] = promoted_bundle
        record["last_known_good_bundle_ref"] = previous_bundle
        record["registry_event_id"] = str(lifecycle_event.get("registry_event_id") or "").strip()
        record["activated_at_utc"] = str(lifecycle_event.get("ts_utc") or now_utc()).strip()
        record["policy_rev"] = {
            "policy_id": str(promoted_policy.get("policy_id") or "df.registry_resolution.v0").strip(),
            "revision": promoted_revision,
        }

    rollback_policy = json.loads(json.dumps(base_policy))
    rollback_snapshot = json.loads(json.dumps(base_snapshot))

    promoted_policy_path = promoted_dir / "registry_resolution_policy.promoted.yaml"
    promoted_snapshot_path = promoted_dir / "registry_snapshot.promoted.yaml"
    rollback_policy_path = promoted_dir / "registry_resolution_policy.rollback.yaml"
    rollback_snapshot_path = promoted_dir / "registry_snapshot.rollback.yaml"

    promoted_policy_path.write_text(yaml.safe_dump(promoted_policy, sort_keys=False), encoding="utf-8")
    promoted_snapshot_path.write_text(yaml.safe_dump(promoted_snapshot, sort_keys=False), encoding="utf-8")
    rollback_policy_path.write_text(yaml.safe_dump(rollback_policy, sort_keys=False), encoding="utf-8")
    rollback_snapshot_path.write_text(yaml.safe_dump(rollback_snapshot, sort_keys=False), encoding="utf-8")

    return {
        "promoted_policy_path": str(promoted_policy_path),
        "promoted_snapshot_path": str(promoted_snapshot_path),
        "rollback_policy_path": str(rollback_policy_path),
        "rollback_snapshot_path": str(rollback_snapshot_path),
        "promoted_bundle": promoted_bundle,
        "previous_bundle": previous_bundle,
        "promoted_policy_id": str(promoted_policy.get("policy_id") or "df.registry_resolution.v0").strip(),
        "promoted_policy_revision": promoted_revision,
        "rollback_policy_id": str(rollback_policy.get("policy_id") or "df.registry_resolution.v0").strip(),
        "rollback_policy_revision": str(rollback_policy.get("revision") or "").strip(),
        "lifecycle_event": lifecycle_event,
    }


def ensure_runtime_capacity(*, cluster_name: str, nodegroup_name: str, region: str, desired: int, minimum: int, maximum: int) -> None:
    eks = boto3.client("eks", region_name=region)
    eks.update_nodegroup_config(
        clusterName=cluster_name,
        nodegroupName=nodegroup_name,
        scalingConfig={"minSize": int(minimum), "maxSize": int(maximum), "desiredSize": int(desired)},
    )


def wait_for_nodes(*, namespace: str, timeout_seconds: int) -> None:
    deadline = time.time() + max(60, int(timeout_seconds))
    last_error = ""
    while time.time() < deadline:
        try:
            payload = json.loads(run_cli(["kubectl", "get", "nodes", "-o", "json"], timeout=120).stdout)
            ready = 0
            for item in payload.get("items") or []:
                conditions = (item.get("status") or {}).get("conditions") or []
                if any(
                    str(cond.get("type") or "").strip() == "Ready" and str(cond.get("status") or "").strip() == "True"
                    for cond in conditions
                ):
                    ready += 1
            if ready > 0:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(10)
    raise RuntimeError(f"phase6_nodes_not_ready:{namespace}:{last_error}")


def scale_coredns(replicas: int) -> None:
    run_cli(["kubectl", "scale", "deploy", "-n", "kube-system", "coredns", f"--replicas={int(replicas)}"], timeout=180)
    run_cli(["kubectl", "rollout", "status", "deploy/coredns", "-n", "kube-system", "--timeout=180s"], timeout=240)


def write_charter(
    path: Path,
    *,
    execution_id: str,
    platform_run_id: str,
    rollback_platform_run_id: str,
    restore_platform_run_id: str,
    source_execution_id: str,
    phase5_execution_id: str,
    scenario_run_id: str,
    rollback_scenario_run_id: str,
    restore_scenario_run_id: str,
    window_start_ts_utc: str,
    window_end_ts_utc: str,
) -> None:
    payload = {
        "phase": "PHASE6",
        "generated_at_utc": now_utc(),
        "generated_by": "phase6-learning-coupled-readiness",
        "version": "1.0.0",
        "execution_id": execution_id,
        "mission_id": "dev_full_phase6_learning_coupled",
        "mission_binding": {
            "window_start_ts_utc": window_start_ts_utc,
            "window_end_ts_utc": window_end_ts_utc,
            "as_of_time_utc": window_end_ts_utc,
            "label_maturity_lag": "3d",
        },
        "phase6_slice": {
            "source_execution_id": source_execution_id,
            "phase5_execution_id": phase5_execution_id,
            "platform_run_id": platform_run_id,
            "rollback_platform_run_id": rollback_platform_run_id,
            "restore_platform_run_id": restore_platform_run_id,
            "scenario_run_id": scenario_run_id,
            "rollback_scenario_run_id": rollback_scenario_run_id,
            "restore_scenario_run_id": restore_scenario_run_id,
            "goal": "bounded_runtime_bundle_adoption_rollback_restore",
        },
    }
    write_json(path, payload)


def materialize_runtime(
    *,
    execution_id: str,
    run_control_root: str,
    platform_run_id: str,
    scenario_run_id: str,
    aws_region: str,
    namespace: str,
    case_labels_namespace: str,
    df_policy_source_path: Path,
    df_snapshot_source_path: Path,
) -> None:
    run_cmd(
        [
            "scripts/dev_substrate/pr3_rtdl_materialize.py",
            "--run-control-root",
            run_control_root,
            "--pr3-execution-id",
            execution_id,
            "--platform-run-id",
            platform_run_id,
            "--scenario-run-id",
            scenario_run_id,
            "--region",
            aws_region,
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--df-registry-policy-source-path",
            str(df_policy_source_path),
            "--df-registry-snapshot-source-path",
            str(df_snapshot_source_path),
        ]
    )


def warm_gate_runtime(
    *,
    execution_id: str,
    run_control_root: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
    expected_case_label_scenario_run_id: str,
) -> None:
    run_cmd(
        [
            "scripts/dev_substrate/pr3_runtime_warm_gate.py",
            "--run-control-root",
            run_control_root,
            "--pr3-execution-id",
            execution_id,
            "--state-id",
            "S4",
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--platform-run-id",
            platform_run_id,
            "--expected-case-label-scenario-run-id",
            expected_case_label_scenario_run_id,
        ]
    )


def warm_gate_transition_advisory(payload: dict[str, Any]) -> bool:
    blockers = {str(item).strip() for item in (payload.get("blocker_ids") or []) if str(item).strip()}
    return bool(blockers) and blockers.issubset({"PR3.S4.WARM.B12K_OFP_NOT_OPERATIONALLY_READY"})


def capture_snapshot(
    *,
    execution_id: str,
    run_control_root: str,
    state_id: str,
    snapshot_label: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
) -> None:
    run_cmd(
        [
            "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
            "--run-control-root",
            run_control_root,
            "--pr3-execution-id",
            execution_id,
            "--state-id",
            state_id,
            "--snapshot-label",
            snapshot_label,
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--platform-run-id",
            platform_run_id,
        ]
    )


def dispatch_short_activation(
    *,
    execution_id: str,
    run_control_root: str,
    aws_region: str,
    platform_run_id: str,
    scenario_run_id: str,
    artifact_prefix: str,
    window_label: str,
    lane_count: int,
    target_request_rate_eps: float,
    duration_seconds: int,
    stream_speedup: float,
    output_concurrency: int,
    ig_push_concurrency: int,
    http_pool_maxsize: int,
    traffic_output_ids: str,
    context_output_ids: str,
) -> None:
    run_cmd(
        [
            "scripts/dev_substrate/pr3_wsp_replay_dispatch.py",
            "--run-control-root",
            run_control_root,
            "--pr3-execution-id",
            execution_id,
            "--state-id",
            "P6",
            "--window-label",
            window_label,
            "--artifact-prefix",
            artifact_prefix,
            "--blocker-prefix",
            "PHASE6.COUPLED",
            "--region",
            aws_region,
            "--platform-run-id",
            platform_run_id,
            "--scenario-run-id",
            scenario_run_id,
            "--checkpoint-attempt-id",
            utc_stamp(),
            "--lane-count",
            str(lane_count),
            "--expected-window-eps",
            "0",
            "--target-request-rate-eps",
            str(target_request_rate_eps),
            "--duration-seconds",
            str(duration_seconds),
            "--warmup-seconds",
            "0",
            "--early-cutoff-seconds",
            "15",
            "--early-cutoff-floor-ratio",
            "0.5",
            "--stream-speedup",
            str(stream_speedup),
            "--output-concurrency",
            str(output_concurrency),
            "--ig-push-concurrency",
            str(ig_push_concurrency),
            "--http-pool-maxsize",
            str(http_pool_maxsize),
            "--traffic-output-ids",
            traffic_output_ids,
            "--context-output-ids",
            context_output_ids,
            "--skip-runtime-identity-probe",
            "--allow-runtime-identity-reuse",
            "--skip-final-threshold-check",
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute Phase 6 coupled runtime-learning readiness.")
    ap.add_argument("--execution-id", default="")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="fraud-platform-case-labels")
    ap.add_argument("--source-execution-id", default="phase4_case_label_coupled_20260312T003302Z")
    ap.add_argument("--phase5-execution-id", default="phase5_learning_managed_20260312T071600Z")
    ap.add_argument("--scenario-id", default="baseline_v1")
    ap.add_argument("--window-start-ts-utc", default="2026-02-26T00:00:00Z")
    ap.add_argument("--window-end-ts-utc", default="2026-03-05T00:00:00Z")
    ap.add_argument("--lane-count", type=int, default=54)
    ap.add_argument("--prewarm-duration-seconds", type=int, default=45)
    ap.add_argument("--prewarm-target-request-rate-eps", type=float, default=1500.0)
    ap.add_argument("--prewarm-ig-push-concurrency", type=int, default=1)
    ap.add_argument("--post-prewarm-settle-seconds", type=int, default=10)
    ap.add_argument("--scored-activation-duration-seconds", type=int, default=20)
    ap.add_argument("--scored-activation-target-request-rate-eps", type=float, default=1500.0)
    ap.add_argument("--scored-activation-ig-push-concurrency", type=int, default=1)
    ap.add_argument("--post-scored-activation-settle-seconds", type=int, default=10)
    ap.add_argument("--steady-seconds", type=int, default=90)
    ap.add_argument("--burst-seconds", type=int, default=2)
    ap.add_argument("--recovery-seconds", type=int, default=180)
    ap.add_argument("--presteady-seconds", type=int, default=60)
    ap.add_argument("--presteady-eps", type=float, default=1500.0)
    ap.add_argument("--steady-eps", type=float, default=3000.0)
    ap.add_argument("--burst-eps", type=float, default=6000.0)
    ap.add_argument("--recovery-bound-seconds", type=float, default=180.0)
    ap.add_argument("--recovery-bin-seconds", type=int, default=30)
    ap.add_argument("--stream-speedup", type=float, default=52.9)
    ap.add_argument("--output-concurrency", type=int, default=4)
    ap.add_argument("--ig-push-concurrency", type=int, default=1)
    ap.add_argument("--http-pool-maxsize", type=int, default=512)
    ap.add_argument("--target-burst-seconds", type=float, default=0.25)
    ap.add_argument("--target-initial-tokens", type=float, default=0.25)
    ap.add_argument("--burst-step-initial-tokens", type=float, default=-1.0)
    ap.add_argument("--short-upward-transition-blend", type=float, default=(1.0 / 3.0))
    ap.add_argument("--short-upward-transition-lane-stagger-seconds", type=float, default=0.0)
    ap.add_argument("--traffic-output-ids", default="s3_event_stream_with_fraud_6B")
    ap.add_argument("--context-output-ids", default="arrival_events_5B,s1_arrival_entities_6B,s3_flow_anchor_with_fraud_6B")
    ap.add_argument("--wsp-task-cpu", type=int, default=256)
    ap.add_argument("--wsp-task-memory", type=int, default=1024)
    ap.add_argument("--cost-budget-envelope-usd", type=float, default=15.0)
    ap.add_argument("--rollback-activation-duration-seconds", type=int, default=20)
    ap.add_argument("--rollback-activation-target-request-rate-eps", type=float, default=1500.0)
    ap.add_argument("--restore-activation-duration-seconds", type=int, default=20)
    ap.add_argument("--restore-activation-target-request-rate-eps", type=float, default=1500.0)
    ap.add_argument("--candidate-steady-warm-extension-seconds", type=int, default=60)
    ap.add_argument("--cluster-name", default="fraud-platform-dev-full")
    ap.add_argument("--nodegroup-name", default="fraud-platform-dev-full-m6f-workers")
    ap.add_argument("--nodegroup-desired-size", type=int, default=4)
    ap.add_argument("--nodegroup-min-size", type=int, default=2)
    ap.add_argument("--nodegroup-max-size", type=int, default=8)
    args = ap.parse_args()

    execution_id = str(args.execution_id).strip() or fresh_execution_id()
    root = Path(args.run_control_root) / execution_id
    root.mkdir(parents=True, exist_ok=True)

    source_root = Path(args.run_control_root) / str(args.source_execution_id).strip()
    phase5_root = Path(args.run_control_root) / str(args.phase5_execution_id).strip()
    phase4_receipt = load_json(source_root / "phase4_coupled_readiness_receipt.json")
    phase4_envelope = load_json(source_root / "phase4_coupled_envelope_summary.json")
    phase5_summary = load_json(phase5_root / "phase5_learning_managed_summary.json")
    phase5_receipt = load_json(phase5_root / "phase5_learning_managed_receipt.json")
    if str(phase4_receipt.get("verdict") or "").strip().upper() != "PHASE4_READY":
        raise RuntimeError("PHASE6.A01_SOURCE_PHASE4_NOT_GREEN")
    if str(phase5_receipt.get("verdict") or "").strip().upper() != "PHASE5_READY":
        raise RuntimeError("PHASE6.A02_PHASE5_NOT_GREEN")
    inherit_phase4_envelope(summary=phase4_envelope, args=args)

    platform_run_id = fresh_platform_run_id()
    scenario_run_id = fresh_scenario_run_id(execution_id=execution_id, window_label="phase6_coupled", platform_run_id=platform_run_id)
    prewarm_scenario_run_id = fresh_scenario_run_id(execution_id=execution_id, window_label="phase6_coupled_prewarm", platform_run_id=platform_run_id)
    time.sleep(1)
    rollback_platform_run_id = fresh_platform_run_id()
    rollback_scenario_run_id = fresh_scenario_run_id(
        execution_id=execution_id, window_label="phase6_coupled_rollback", platform_run_id=rollback_platform_run_id
    )
    time.sleep(1)
    restore_platform_run_id = fresh_platform_run_id()
    restore_scenario_run_id = fresh_scenario_run_id(
        execution_id=execution_id, window_label="phase6_coupled_restore", platform_run_id=restore_platform_run_id
    )

    write_charter(
        root / "g6a_run_charter.active.json",
        execution_id=execution_id,
        platform_run_id=platform_run_id,
        rollback_platform_run_id=rollback_platform_run_id,
        restore_platform_run_id=restore_platform_run_id,
        source_execution_id=str(args.source_execution_id).strip(),
        phase5_execution_id=str(args.phase5_execution_id).strip(),
        scenario_run_id=scenario_run_id,
        rollback_scenario_run_id=rollback_scenario_run_id,
        restore_scenario_run_id=restore_scenario_run_id,
        window_start_ts_utc=str(args.window_start_ts_utc).strip(),
        window_end_ts_utc=str(args.window_end_ts_utc).strip(),
    )
    write_json(
        root / "g3a_run_charter.active.json",
        load_json(root / "g6a_run_charter.active.json"),
    )
    write_json(
        root / "phase6_runtime_identity.json",
        {
            "generated_at_utc": now_utc(),
            "execution_id": execution_id,
            "platform_run_id": platform_run_id,
            "rollback_platform_run_id": rollback_platform_run_id,
            "restore_platform_run_id": restore_platform_run_id,
            "scenario_run_id": scenario_run_id,
            "prewarm_scenario_run_id": prewarm_scenario_run_id,
            "rollback_scenario_run_id": rollback_scenario_run_id,
            "restore_scenario_run_id": restore_scenario_run_id,
        },
    )

    registry_surfaces = stage_registry_surfaces(
        root=root,
        execution_id=execution_id,
        phase5_summary=phase5_summary,
        aws_region=args.aws_region,
        base_policy_path=REPO_ROOT / "config/platform/df/registry_resolution_policy_v0.yaml",
        base_snapshot_path=REPO_ROOT / "config/platform/df/registry_snapshot_dev_full_v0.yaml",
    )
    write_json(root / "phase6_registry_surface_manifest.json", registry_surfaces)

    try:
        ensure_runtime_capacity(
            cluster_name=str(args.cluster_name).strip(),
            nodegroup_name=str(args.nodegroup_name).strip(),
            region=str(args.aws_region).strip(),
            desired=int(args.nodegroup_desired_size),
            minimum=int(args.nodegroup_min_size),
            maximum=int(args.nodegroup_max_size),
        )
        wait_for_nodes(namespace=str(args.namespace).strip(), timeout_seconds=900)
        scale_coredns(2)

        initial_runtime_scenario_run_id = prewarm_scenario_run_id if int(args.prewarm_duration_seconds) > 0 else scenario_run_id
        materialize_runtime(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            platform_run_id=platform_run_id,
            scenario_run_id=initial_runtime_scenario_run_id,
            aws_region=args.aws_region,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            df_policy_source_path=Path(str(registry_surfaces["promoted_policy_path"])),
            df_snapshot_source_path=Path(str(registry_surfaces["promoted_snapshot_path"])),
        )
        archive_copy(root / "g3a_runtime_materialization_manifest.json", root / "phase6_candidate_runtime_materialization_manifest.json")
        archive_copy(root / "g3a_runtime_materialization_summary.json", root / "phase6_candidate_runtime_materialization_summary.json")

        run_cmd(
            [
                "scripts/dev_substrate/pr3_control_plane_bootstrap.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--platform-run-id",
                platform_run_id,
                "--aws-region",
                args.aws_region,
                "--scenario-id",
                args.scenario_id,
                "--namespace",
                args.namespace,
                "--bootstrap-summary-name",
                "phase6_control_plane_bootstrap.json",
            ]
        )
        warm_gate_runtime(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
            expected_case_label_scenario_run_id=initial_runtime_scenario_run_id,
        )
        archive_copy(root / "g3a_s4_runtime_warm_gate.json", root / "phase6_candidate_runtime_warm_gate.json")

        stop_wsp_tasks(args.aws_region, root / "phase6_candidate_preflight_wsp_cleanup.json", "Phase6 candidate preflight WSP cleanup")
        if int(args.prewarm_duration_seconds) > 0:
            dispatch_short_activation(
                execution_id=execution_id,
                run_control_root=args.run_control_root,
                aws_region=args.aws_region,
                platform_run_id=platform_run_id,
                scenario_run_id=prewarm_scenario_run_id,
                artifact_prefix="phase6_coupled_prewarm",
                window_label="phase6_coupled_prewarm",
                lane_count=int(args.lane_count),
                target_request_rate_eps=float(args.prewarm_target_request_rate_eps),
                duration_seconds=int(args.prewarm_duration_seconds),
                stream_speedup=float(args.stream_speedup),
                output_concurrency=int(args.output_concurrency),
                ig_push_concurrency=int(args.prewarm_ig_push_concurrency),
                http_pool_maxsize=int(args.http_pool_maxsize),
                traffic_output_ids=str(args.traffic_output_ids).strip(),
                context_output_ids=str(args.context_output_ids).strip(),
            )
            stop_wsp_tasks(args.aws_region, root / "phase6_candidate_prewarm_wsp_cleanup.json", "Phase6 candidate prewarm WSP cleanup")
            materialize_runtime(
                execution_id=execution_id,
                run_control_root=args.run_control_root,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                aws_region=args.aws_region,
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
                df_policy_source_path=Path(str(registry_surfaces["promoted_policy_path"])),
                df_snapshot_source_path=Path(str(registry_surfaces["promoted_snapshot_path"])),
            )
            archive_copy(root / "g3a_runtime_materialization_manifest.json", root / "phase6_candidate_runtime_materialization_manifest.json")
            archive_copy(root / "g3a_runtime_materialization_summary.json", root / "phase6_candidate_runtime_materialization_summary.json")
            if int(args.scored_activation_duration_seconds) > 0:
                dispatch_short_activation(
                    execution_id=execution_id,
                    run_control_root=args.run_control_root,
                    aws_region=args.aws_region,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    artifact_prefix="phase6_candidate_activation",
                    window_label="phase6_candidate_activation",
                    lane_count=int(args.lane_count),
                    target_request_rate_eps=float(args.scored_activation_target_request_rate_eps),
                    duration_seconds=int(args.scored_activation_duration_seconds),
                    stream_speedup=float(args.stream_speedup),
                    output_concurrency=int(args.output_concurrency),
                    ig_push_concurrency=int(args.scored_activation_ig_push_concurrency),
                    http_pool_maxsize=int(args.http_pool_maxsize),
                    traffic_output_ids=str(args.traffic_output_ids).strip(),
                    context_output_ids=str(args.context_output_ids).strip(),
                )
                stop_wsp_tasks(args.aws_region, root / "phase6_candidate_activation_wsp_cleanup.json", "Phase6 candidate activation WSP cleanup")
                time.sleep(max(0, int(args.post_scored_activation_settle_seconds)))
            time.sleep(max(0, int(args.post_prewarm_settle_seconds)))
            time.sleep(max(0, int(args.candidate_steady_warm_extension_seconds)))

        capture_snapshot(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            state_id="P6",
            snapshot_label="pre",
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
        )
        run_cmd(
            [
                "scripts/dev_substrate/phase0_control_ingress_envelope.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--state-id",
                "P6",
                "--artifact-prefix",
                "phase6_coupled",
                "--blocker-prefix",
                "PHASE6.COUPLED",
                "--window-label",
                "phase6_coupled",
                "--summary-phase",
                "PHASE6",
                "--ready-verdict",
                "PHASE6B_READY",
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--generated-by",
                "phase6-learning-coupled-readiness",
                "--steady-seconds",
                str(args.steady_seconds),
                "--burst-seconds",
                str(args.burst_seconds),
                "--recovery-seconds",
                str(args.recovery_seconds),
                "--presteady-seconds",
                str(args.presteady_seconds),
                "--presteady-eps",
                str(args.presteady_eps),
                "--steady-eps",
                str(args.steady_eps),
                "--burst-eps",
                str(args.burst_eps),
                "--recovery-bound-seconds",
                str(args.recovery_bound_seconds),
                "--recovery-bin-seconds",
                str(args.recovery_bin_seconds),
                "--lane-count",
                str(args.lane_count),
                "--stream-speedup",
                str(args.stream_speedup),
                "--output-concurrency",
                str(args.output_concurrency),
                "--ig-push-concurrency",
                str(args.ig_push_concurrency),
                "--http-pool-maxsize",
                str(args.http_pool_maxsize),
                "--target-burst-seconds",
                str(args.target_burst_seconds),
                "--target-initial-tokens",
                str(args.target_initial_tokens),
                "--burst-step-initial-tokens",
                str(args.burst_step_initial_tokens),
                "--short-upward-transition-blend",
                str(args.short_upward_transition_blend),
                "--short-upward-transition-lane-stagger-seconds",
                str(args.short_upward_transition_lane_stagger_seconds),
                "--traffic-output-ids",
                args.traffic_output_ids,
                "--context-output-ids",
                args.context_output_ids,
                "--region",
                args.aws_region,
                "--max-latency-p95-ms",
                "350",
                "--max-latency-p99-ms",
                "700",
            ]
        )
        capture_snapshot(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            state_id="P6",
            snapshot_label="post",
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
        )
        run_cmd(
            [
                "scripts/dev_substrate/pr3_s4_cost_guardrail.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--state-id",
                "P6",
                "--artifact-prefix",
                "phase6_coupled",
                "--aws-region",
                args.aws_region,
                "--cluster",
                "fraud-platform-dev-full-wsp-ephemeral",
                "--wsp-task-cpu",
                str(args.wsp_task_cpu),
                "--wsp-task-memory",
                str(args.wsp_task_memory),
                "--budget-envelope-usd",
                str(args.cost_budget_envelope_usd),
                "--receipt-path",
                "phase6_coupled_cost_receipt.json",
                "--drill-path",
                "phase6_coupled_cost_guardrail.json",
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/phase4_case_label_timing_probe.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--namespace",
                args.case_labels_namespace,
                "--artifact-prefix",
                "phase6_coupled",
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/phase6_runtime_bundle_probe.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--namespace",
                args.namespace,
                "--artifact-prefix",
                "phase6_candidate",
                "--expected-bundle-id",
                str(registry_surfaces["promoted_bundle"]["bundle_id"]),
                "--expected-bundle-version",
                str(registry_surfaces["promoted_bundle"]["bundle_version"]),
                "--expected-policy-id",
                str(registry_surfaces["promoted_policy_id"]),
                "--expected-policy-revision",
                str(registry_surfaces["promoted_policy_revision"]),
            ]
        )

        materialize_runtime(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            platform_run_id=rollback_platform_run_id,
            scenario_run_id=rollback_scenario_run_id,
            aws_region=args.aws_region,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            df_policy_source_path=Path(str(registry_surfaces["rollback_policy_path"])),
            df_snapshot_source_path=Path(str(registry_surfaces["rollback_snapshot_path"])),
        )
        archive_copy(root / "g3a_runtime_materialization_manifest.json", root / "phase6_rollback_runtime_materialization_manifest.json")
        archive_copy(root / "g3a_runtime_materialization_summary.json", root / "phase6_rollback_runtime_materialization_summary.json")
        try:
            warm_gate_runtime(
                execution_id=execution_id,
                run_control_root=args.run_control_root,
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
                platform_run_id=rollback_platform_run_id,
                expected_case_label_scenario_run_id=rollback_scenario_run_id,
            )
        except subprocess.CalledProcessError:
            rollback_warm_gate = load_json(root / "g3a_s4_runtime_warm_gate.json")
            if not warm_gate_transition_advisory(rollback_warm_gate):
                raise
        archive_copy(root / "g3a_s4_runtime_warm_gate.json", root / "phase6_rollback_runtime_warm_gate.json")
        dispatch_short_activation(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            aws_region=args.aws_region,
            platform_run_id=rollback_platform_run_id,
            scenario_run_id=rollback_scenario_run_id,
            artifact_prefix="phase6_rollback_activation",
            window_label="phase6_rollback_activation",
            lane_count=int(args.lane_count),
            target_request_rate_eps=float(args.rollback_activation_target_request_rate_eps),
            duration_seconds=int(args.rollback_activation_duration_seconds),
            stream_speedup=float(args.stream_speedup),
            output_concurrency=int(args.output_concurrency),
            ig_push_concurrency=int(args.ig_push_concurrency),
            http_pool_maxsize=int(args.http_pool_maxsize),
            traffic_output_ids=str(args.traffic_output_ids).strip(),
            context_output_ids=str(args.context_output_ids).strip(),
        )
        stop_wsp_tasks(args.aws_region, root / "phase6_rollback_wsp_cleanup.json", "Phase6 rollback WSP cleanup")
        run_cmd(
            [
                "scripts/dev_substrate/phase6_runtime_bundle_probe.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--platform-run-id",
                rollback_platform_run_id,
                "--scenario-run-id",
                rollback_scenario_run_id,
                "--namespace",
                args.namespace,
                "--artifact-prefix",
                "phase6_rollback",
                "--expected-bundle-id",
                str(registry_surfaces["previous_bundle"]["bundle_id"]),
                "--expected-bundle-version",
                str(registry_surfaces["previous_bundle"]["bundle_version"]),
                "--expected-policy-id",
                str(registry_surfaces["rollback_policy_id"]),
                "--expected-policy-revision",
                str(registry_surfaces["rollback_policy_revision"]),
            ]
        )

        materialize_runtime(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            platform_run_id=restore_platform_run_id,
            scenario_run_id=restore_scenario_run_id,
            aws_region=args.aws_region,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            df_policy_source_path=Path(str(registry_surfaces["promoted_policy_path"])),
            df_snapshot_source_path=Path(str(registry_surfaces["promoted_snapshot_path"])),
        )
        archive_copy(root / "g3a_runtime_materialization_manifest.json", root / "phase6_restore_runtime_materialization_manifest.json")
        archive_copy(root / "g3a_runtime_materialization_summary.json", root / "phase6_restore_runtime_materialization_summary.json")
        try:
            warm_gate_runtime(
                execution_id=execution_id,
                run_control_root=args.run_control_root,
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
                platform_run_id=restore_platform_run_id,
                expected_case_label_scenario_run_id=restore_scenario_run_id,
            )
        except subprocess.CalledProcessError:
            restore_warm_gate = load_json(root / "g3a_s4_runtime_warm_gate.json")
            if not warm_gate_transition_advisory(restore_warm_gate):
                raise
        archive_copy(root / "g3a_s4_runtime_warm_gate.json", root / "phase6_restore_runtime_warm_gate.json")
        dispatch_short_activation(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            aws_region=args.aws_region,
            platform_run_id=restore_platform_run_id,
            scenario_run_id=restore_scenario_run_id,
            artifact_prefix="phase6_restore_activation",
            window_label="phase6_restore_activation",
            lane_count=int(args.lane_count),
            target_request_rate_eps=float(args.restore_activation_target_request_rate_eps),
            duration_seconds=int(args.restore_activation_duration_seconds),
            stream_speedup=float(args.stream_speedup),
            output_concurrency=int(args.output_concurrency),
            ig_push_concurrency=int(args.ig_push_concurrency),
            http_pool_maxsize=int(args.http_pool_maxsize),
            traffic_output_ids=str(args.traffic_output_ids).strip(),
            context_output_ids=str(args.context_output_ids).strip(),
        )
        stop_wsp_tasks(args.aws_region, root / "phase6_restore_wsp_cleanup.json", "Phase6 restore WSP cleanup")
        run_cmd(
            [
                "scripts/dev_substrate/phase6_runtime_bundle_probe.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--platform-run-id",
                restore_platform_run_id,
                "--scenario-run-id",
                restore_scenario_run_id,
                "--namespace",
                args.namespace,
                "--artifact-prefix",
                "phase6_restore",
                "--expected-bundle-id",
                str(registry_surfaces["promoted_bundle"]["bundle_id"]),
                "--expected-bundle-version",
                str(registry_surfaces["promoted_bundle"]["bundle_version"]),
                "--expected-policy-id",
                str(registry_surfaces["promoted_policy_id"]),
                "--expected-policy-revision",
                str(registry_surfaces["promoted_policy_revision"]),
            ]
        )

        run_cmd(
            [
                "scripts/dev_substrate/phase6_learning_coupled_rollup.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--phase5-execution-id",
                str(args.phase5_execution_id).strip(),
            ]
        )
    finally:
        stop_wsp_tasks(args.aws_region, root / "phase6_final_wsp_cleanup.json", "Phase6 final WSP cleanup")


if __name__ == "__main__":
    main()
