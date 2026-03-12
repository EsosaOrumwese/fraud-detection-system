#!/usr/bin/env python3
"""Application-level warm gate for PR3 runtime before burst injection."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def run(cmd: list[str], *, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def get_json(cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = run(cmd, timeout=timeout, check=True)
    text = proc.stdout.strip()
    return json.loads(text) if text else {}


def parse_timestamp(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def exec_json(namespace: str, pod: str, script: str, env_map: dict[str, str]) -> tuple[dict[str, Any], str]:
    env_bits = [f"{key}={value}" for key, value in sorted(env_map.items())]
    proc = run(
        ["kubectl", "exec", "-n", namespace, pod, "--", "env", *env_bits, "python", "-c", script],
        timeout=240,
        check=False,
    )
    if proc.returncode != 0:
        return {}, proc.stderr.strip() or proc.stdout.strip()
    text = proc.stdout.strip()
    if not text:
        return {}, ""
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return {}, f"json_decode_error:{exc}"


DF_WARM_SCRIPT = r"""
import json
import sqlite3
from pathlib import Path

from fraud_detection.decision_fabric.registry import RegistryResolutionPolicy, RegistryScopeKey, RegistrySnapshot
from fraud_detection.decision_fabric.worker import load_worker_config
from fraud_detection.event_bus.kafka import build_kafka_reader
from fraud_detection.platform_runtime import RUNS_ROOT

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
snapshot = RegistrySnapshot.load(cfg.registry_snapshot_ref)
policy = RegistryResolutionPolicy.load(cfg.registry_policy_ref)
reader = build_kafka_reader(client_id="pr3-df-warm-gate")
topic = "fp.bus.traffic.fraud.v1"
partitions = reader.list_partitions(topic)
checkpoint_path = Path(cfg.consumer_checkpoint_path)
checkpoint_partitions = []
if checkpoint_path.exists():
    with sqlite3.connect(checkpoint_path) as conn:
        checkpoint_partitions = [
            int(row[0])
            for row in conn.execute(
                "SELECT partition_id FROM df_worker_consumer_checkpoints WHERE stream_id = ? AND topic = ? ORDER BY partition_id",
                (cfg.stream_id, topic),
            ).fetchall()
        ]
run_root = RUNS_ROOT / str(cfg.platform_run_id or "_unknown")
metrics_path = run_root / "decision_fabric" / "metrics" / "last_metrics.json"
health_path = run_root / "decision_fabric" / "health" / "last_health.json"
def load_json(path):
    if not path.exists():
        return {"__missing__": True, "__path__": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"__unreadable__": True, "__path__": str(path), "__error__": str(exc)}
required = [
    RegistryScopeKey(environment="dev_full", mode="fraud", bundle_slot="primary").canonical_key(),
    RegistryScopeKey(environment="dev_full", mode="baseline", bundle_slot="primary").canonical_key(),
]
present = sorted(snapshot.records_by_scope.keys())
policy_scopes = {scope: dict(bundle_ref) for scope, bundle_ref in policy.explicit_fallback_by_scope.items()}
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "scenario_run_id_hint": cfg.scenario_run_id_hint,
    "event_bus_start_position": cfg.event_bus_start_position,
    "registry_policy_ref": str(cfg.registry_policy_ref),
    "registry_snapshot_ref": str(cfg.registry_snapshot_ref),
    "policy_id": policy.policy_rev.policy_id,
    "policy_revision": policy.policy_rev.revision,
    "explicit_fallback_by_scope": policy_scopes,
    "snapshot_id": snapshot.snapshot_id,
    "snapshot_digest": snapshot.snapshot_digest,
    "required_scopes_present": all(scope in snapshot.records_by_scope for scope in required),
    "required_scopes": required,
    "present_scopes": present,
    "kafka_topic": topic,
    "kafka_partitions": partitions,
    "checkpoint_path": str(checkpoint_path),
    "checkpoint_partitions": checkpoint_partitions,
    "metrics_path": str(metrics_path),
    "metrics_payload": load_json(metrics_path),
    "health_path": str(health_path),
    "health_payload": load_json(health_path),
}))
"""

DL_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.degrade_ladder.worker import load_worker_config
from fraud_detection.degrade_ladder.store import build_store

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
store = build_store(cfg.store_dsn, stream_id=cfg.stream_id)
record = store.read_current(scope_key=cfg.scope_key)
payload = {
    "scope_key": cfg.scope_key,
    "stream_id": cfg.stream_id,
    "store_dsn": cfg.store_dsn,
    "record_present": record is not None,
}
if record is not None:
    payload["decision"] = record.decision.as_dict()
    payload["updated_at_utc"] = record.updated_at_utc
print(json.dumps(payload))
"""

CSFB_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.context_store_flow_binding.intake import CsfbInletPolicy
from fraud_detection.event_bus.kafka import build_kafka_reader

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
policy = CsfbInletPolicy.load(profile_path)
reader = build_kafka_reader(client_id="pr3-csfb-warm-gate")
topic_partitions = {topic: reader.list_partitions(topic) for topic in policy.context_topics}
print(json.dumps({
    "required_platform_run_id": policy.required_platform_run_id,
    "event_bus_start_position": policy.event_bus_start_position,
    "stream_id": policy.stream_id,
    "context_topics": list(policy.context_topics),
    "topic_partitions": topic_partitions,
}))
"""

COMPONENT_SURFACE_SCRIPT = r"""
import json
import os
from pathlib import Path

platform_run_id = os.environ["FP_PLATFORM_RUN_ID"]
metrics_path = Path(os.environ["FP_METRICS_PATH"].format(platform_run_id=platform_run_id))
health_path = Path(os.environ["FP_HEALTH_PATH"].format(platform_run_id=platform_run_id))

def load_json(path: Path):
    if not path.exists():
        return {"__missing__": True, "__path__": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"__unreadable__": True, "__path__": str(path), "__error__": str(exc)}

print(json.dumps({
    "platform_run_id": platform_run_id,
    "metrics_path": str(metrics_path),
    "health_path": str(health_path),
    "metrics_payload": load_json(metrics_path),
    "health_payload": load_json(health_path),
}))
"""

CASE_TRIGGER_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.case_trigger.worker import load_worker_config

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "scenario_run_id": cfg.scenario_run_id,
    "event_bus_start_position": cfg.event_bus_start_position,
    "stream_id": cfg.stream_id,
    "admitted_topics": list(cfg.admitted_topics),
}))
"""

CASE_MGMT_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.case_mgmt.worker import load_worker_config

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "scenario_run_id": cfg.scenario_run_id,
    "event_bus_start_position": cfg.event_bus_start_position,
    "stream_id": cfg.stream_id,
    "admitted_topics": list(cfg.admitted_topics),
}))
"""

LABEL_STORE_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.label_store.worker import load_worker_config

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "scenario_run_id": cfg.scenario_run_id,
    "stream_id": cfg.stream_id,
}))
"""

DLA_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.worker import load_worker_config

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
policy = load_intake_policy(cfg.policy_ref)
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "event_bus_start_position": cfg.event_bus_start_position,
    "stream_id": cfg.stream_id,
    "policy_ref": str(cfg.policy_ref),
    "admitted_topics": list(policy.admitted_topics),
    "policy_required_platform_run_id": policy.required_platform_run_id,
}))
"""

COMPONENT_SURFACE_PATHS: dict[str, dict[str, str]] = {
    "ieg": {
        "metrics_path": "runs/fraud-platform/{platform_run_id}/identity_entity_graph/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/identity_entity_graph/health/last_health.json",
    },
    "ofp": {
        "metrics_path": "runs/fraud-platform/{platform_run_id}/online_feature_plane/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/online_feature_plane/health/last_health.json",
    },
}


def summarize_pod(pod: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(pod.get("metadata", {}) or {})
    status = dict(pod.get("status", {}) or {})
    statuses = list(status.get("containerStatuses", []) or [])
    return {
        "pod_name": str(metadata.get("name", "")).strip(),
        "phase": str(status.get("phase", "")).strip(),
        "reason": str(status.get("reason", "")).strip(),
        "ready": all(bool(row.get("ready")) for row in statuses) if statuses else False,
        "restart_count": int(sum(int(row.get("restartCount", 0) or 0) for row in statuses)),
        "node_name": str(pod.get("spec", {}).get("nodeName", "")).strip(),
        "start_time": str(status.get("startTime", "")).strip(),
        "creation_timestamp": str(metadata.get("creationTimestamp", "")).strip(),
        "deletion_timestamp": str(metadata.get("deletionTimestamp", "")).strip(),
    }


def select_active_pod(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def sort_key(row: dict[str, Any]) -> tuple[int, int, int, datetime, datetime]:
        return (
            1 if not row.get("deletion_timestamp") else 0,
            1 if row.get("phase") == "Running" else 0,
            1 if bool(row.get("ready")) else 0,
            parse_timestamp(str(row.get("start_time") or "")),
            parse_timestamp(str(row.get("creation_timestamp") or "")),
        )

    return sorted(rows, key=sort_key, reverse=True)[0]


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def state_sequence(state_id: str) -> int:
    text = str(state_id or "").strip().upper()
    if text.startswith("S"):
        text = text[1:]
    try:
        return int(text)
    except ValueError:
        return 0


def replay_advisory_only(component: str, probe: dict[str, Any], *, max_checkpoint_seconds: float, max_lag_seconds: float) -> bool:
    health_payload = dict(probe.get("health_payload") or {})
    metrics_payload = dict(probe.get("metrics_payload") or {})
    state = str(health_payload.get("health_state") or "").strip().upper()
    reasons = {str(item).strip() for item in (health_payload.get("health_reasons") or []) if str(item).strip()}
    if state not in {"RED", "FAILED", "UNHEALTHY"}:
        return False
    if reasons != {"WATERMARK_TOO_OLD"}:
        return False
    checkpoint_age = to_float(health_payload.get("checkpoint_age_seconds"))
    if checkpoint_age is None:
        checkpoint_age = to_float(metrics_payload.get("checkpoint_age_seconds"))
    if checkpoint_age is None or checkpoint_age > max_checkpoint_seconds:
        return False
    if component == "ofp":
        lag_seconds = to_float(metrics_payload.get("lag_seconds"))
        if lag_seconds is None or lag_seconds > max_lag_seconds:
            return False
    if component == "ieg":
        if (to_float(health_payload.get("apply_failure_count")) or 0.0) > 0.0:
            return False
        if (to_float(health_payload.get("backpressure_hits")) or 0.0) > 0.0:
            return False
    return True


def bootstrap_marker_only(reasons: list[Any] | tuple[Any, ...] | set[Any], allowed: set[str]) -> bool:
    normalized = {str(item).strip() for item in reasons if str(item).strip()}
    return bool(normalized) and normalized.issubset(allowed)


def zero_df_activity(df_probe: dict[str, Any]) -> bool:
    metrics_payload = dict(df_probe.get("metrics_payload") or {})
    if bool(metrics_payload.get("__missing__")):
        return False
    metrics = dict(metrics_payload.get("metrics") or {})
    required_zero_fields = (
        "decisions_total",
        "degrade_total",
        "fail_closed_total",
        "missing_context_total",
        "publish_admit_total",
        "publish_duplicate_total",
        "publish_quarantine_total",
        "resolver_failures_total",
    )
    return all((to_float(metrics.get(field)) or 0.0) == 0.0 for field in required_zero_fields)


def ieg_bootstrap_pending(ieg_probe: dict[str, Any]) -> bool:
    metrics_payload = dict(ieg_probe.get("metrics_payload") or {})
    health_payload = dict(ieg_probe.get("health_payload") or {})
    if bool(metrics_payload.get("__missing__")) and bool(health_payload.get("__missing__")):
        return True
    if str(health_payload.get("health_state") or "").strip().upper() not in {"", "AMBER", "YELLOW"}:
        return False
    if not bootstrap_marker_only(
        list(health_payload.get("health_reasons") or []),
        {"WATERMARK_MISSING", "CHECKPOINT_MISSING"},
    ):
        return False
    return (to_float(health_payload.get("apply_failure_count")) or 0.0) == 0.0 and (
        to_float(health_payload.get("backpressure_hits")) or 0.0
    ) == 0.0


def ofp_bootstrap_pending(ofp_probe: dict[str, Any]) -> bool:
    metrics_payload = dict(ofp_probe.get("metrics_payload") or {})
    health_payload = dict(ofp_probe.get("health_payload") or {})
    if bool(metrics_payload.get("__missing__")) and bool(health_payload.get("__missing__")):
        return True
    if str(health_payload.get("health_state") or "").strip().upper() not in {"", "AMBER", "YELLOW"}:
        return False
    return bootstrap_marker_only(
        list(health_payload.get("health_reasons") or []),
        {"WATERMARK_MISSING", "CHECKPOINT_MISSING"},
    )


def pretraffic_bootstrap_allowed(
    state_id: str,
    attempt_blockers: list[str],
    *,
    dl_bootstrap_pending_flag: bool,
    df_probe: dict[str, Any],
    ieg_probe: dict[str, Any],
    ofp_probe: dict[str, Any],
) -> tuple[bool, str]:
    if state_sequence(state_id) < 4:
        return False, ""
    if not dl_bootstrap_pending_flag:
        return False, ""
    base_id = f"PR3.{state_id}.WARM."
    allowed_blockers = {
        f"{base_id}B12A_DL_BOOTSTRAP_PENDING",
        f"{base_id}B12C_IEG_METRICS_SURFACE_MISSING",
        f"{base_id}B12D_IEG_HEALTH_SURFACE_MISSING",
        f"{base_id}B12F_IEG_NOT_OPERATIONALLY_READY",
        f"{base_id}B12H_OFP_METRICS_SURFACE_MISSING",
        f"{base_id}B12I_OFP_HEALTH_SURFACE_MISSING",
        f"{base_id}B12K_OFP_NOT_OPERATIONALLY_READY",
    }
    blocker_set = set(attempt_blockers)
    if not blocker_set or not blocker_set.issubset(allowed_blockers):
        return False, ""
    if not zero_df_activity(df_probe):
        return False, ""
    if not ieg_bootstrap_pending(ieg_probe):
        return False, ""
    if not ofp_bootstrap_pending(ofp_probe):
        return False, ""
    return True, f"{base_id}A01_PRETRAFFIC_BOOTSTRAP_PENDING_ALLOWED"


def scenario_transition_oft_ready(
    ofp_probe: dict[str, Any],
    *,
    max_checkpoint_seconds: float,
    max_lag_seconds: float,
) -> bool:
    health_payload = dict(ofp_probe.get("health_payload") or {})
    metrics_payload = dict(ofp_probe.get("metrics_payload") or {})
    if str(health_payload.get("health_state") or "").strip().upper() not in {"RED", "FAILED", "UNHEALTHY"}:
        return False
    reasons = {str(item).strip() for item in (health_payload.get("health_reasons") or []) if str(item).strip()}
    if not reasons or not reasons.issubset({"WATERMARK_TOO_OLD", "STALE_GRAPH_VERSION_RED"}):
        return False
    checkpoint_age = to_float(health_payload.get("checkpoint_age_seconds"))
    if checkpoint_age is None:
        checkpoint_age = to_float(metrics_payload.get("checkpoint_age_seconds"))
    if checkpoint_age is None or checkpoint_age > max_checkpoint_seconds:
        return False
    lag_seconds = to_float(metrics_payload.get("lag_seconds"))
    if lag_seconds is None or lag_seconds > max_lag_seconds:
        return False
    metrics = dict(metrics_payload.get("metrics") or {})
    if (to_float(metrics.get("missing_features")) or 0.0) != 0.0:
        return False
    if (to_float(metrics.get("snapshot_failures")) or 0.0) != 0.0:
        return False
    if (to_float(metrics.get("stale_graph_version")) or 0.0) <= 0.0:
        return False
    return True


def scenario_transition_allowed(
    state_id: str,
    attempt_blockers: list[str],
    *,
    expected_case_label_scenario_run_id: str,
    df_probe: dict[str, Any],
    ieg_probe: dict[str, Any],
    ofp_probe: dict[str, Any],
    case_trigger_probe: dict[str, Any],
    case_mgmt_probe: dict[str, Any],
    label_store_probe: dict[str, Any],
    max_checkpoint_seconds: float,
    max_lag_seconds: float,
) -> tuple[bool, str]:
    if state_sequence(state_id) < 4:
        return False, ""
    expected = str(expected_case_label_scenario_run_id or "").strip()
    if not expected:
        return False, ""
    base_id = f"PR3.{state_id}.WARM."
    allowed_blockers = {f"{base_id}B12K_OFP_NOT_OPERATIONALLY_READY"}
    blocker_set = set(attempt_blockers)
    if not blocker_set or not blocker_set.issubset(allowed_blockers):
        return False, ""
    if not zero_df_activity(df_probe):
        return False, ""
    if str(case_trigger_probe.get("scenario_run_id") or "").strip() != expected:
        return False, ""
    if str(case_mgmt_probe.get("scenario_run_id") or "").strip() != expected:
        return False, ""
    if str(label_store_probe.get("scenario_run_id") or "").strip() != expected:
        return False, ""
    if str(ieg_probe.get("probe_error") or "").strip():
        return False, ""
    if not scenario_transition_oft_ready(
        ofp_probe,
        max_checkpoint_seconds=max_checkpoint_seconds,
        max_lag_seconds=max_lag_seconds,
    ):
        return False, ""
    return True, f"{base_id}A02_SCENARIO_TRANSITION_OFP_STALE_GRAPH_ALLOWED"


def probe_component_surface(namespace: str, pod_name: str, component: str, platform_run_id: str) -> tuple[dict[str, Any], str]:
    paths = COMPONENT_SURFACE_PATHS[component]
    return exec_json(
        namespace,
        pod_name,
        COMPONENT_SURFACE_SCRIPT,
        {
            "FP_PLATFORM_RUN_ID": platform_run_id,
            "FP_METRICS_PATH": paths["metrics_path"],
            "FP_HEALTH_PATH": paths["health_path"],
        },
    )


def probe_worker_config(namespace: str, pod_name: str, script: str, profile_path: str) -> tuple[dict[str, Any], str]:
    return exec_json(
        namespace,
        pod_name,
        script,
        {"FP_PROFILE_PATH": profile_path},
    )


def node_health(node_name: str) -> dict[str, Any]:
    if not node_name:
        return {"node_name": node_name, "node_missing": True}
    node = get_json(["kubectl", "get", "node", node_name, "-o", "json"], timeout=120)
    conditions = list(node.get("status", {}).get("conditions", []) or [])
    cond_map = {
        str(item.get("type", "")).strip(): {
            "status": str(item.get("status", "")).strip(),
            "reason": str(item.get("reason", "")).strip(),
            "message": str(item.get("message", "")).strip(),
        }
        for item in conditions
    }
    return {
        "node_name": node_name,
        "ready": str(cond_map.get("Ready", {}).get("status", "")).strip() == "True",
        "memory_pressure": str(cond_map.get("MemoryPressure", {}).get("status", "")).strip() == "True",
        "disk_pressure": str(cond_map.get("DiskPressure", {}).get("status", "")).strip() == "True",
        "pid_pressure": str(cond_map.get("PIDPressure", {}).get("status", "")).strip() == "True",
        "taints": list(node.get("spec", {}).get("taints", []) or []),
    }


def dl_bootstrap_pending(dl_probe: dict[str, Any]) -> bool:
    decision = dict(dl_probe.get("decision", {}) or {})
    if str(decision.get("mode") or "").strip().upper() != "FAIL_CLOSED":
        return False
    reason = str(decision.get("reason") or "").strip()
    marker = "required_signal_gap:"
    if marker not in reason:
        return False
    gap_suffix = reason.split(marker, 1)[1].split(";", 1)[0].strip()
    gap_items = {item.strip() for item in gap_suffix.split(",") if item.strip()}
    if not gap_items:
        return False
    allowed_bootstrap_gaps = {"eb_consumer_lag", "ieg_health", "ofp_health"}
    return gap_items.issubset(allowed_bootstrap_gaps)


def pod_status(namespace: str, app: str) -> dict[str, Any]:
    pods = get_json(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={app}", "-o", "json"], timeout=120)
    items = list(pods.get("items", []) or [])
    if not items:
        return {"app": app, "namespace": namespace, "pod_missing": True}
    candidates = [summarize_pod(item) for item in items]
    selected = select_active_pod(candidates)
    anomalies = [
        row
        for row in candidates
        if row.get("pod_name") != selected.get("pod_name")
        and (
            row.get("phase") in {"Failed", "Succeeded"}
            or row.get("reason") in {"Evicted"}
            or bool(row.get("deletion_timestamp"))
        )
    ]
    payload = {
        "app": app,
        "namespace": namespace,
        **selected,
        "candidate_pod_count": len(candidates),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:10],
    }
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Warm-gate PR3 runtime before injection.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S2")
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="")
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--expected-case-label-scenario-run-id", default="")
    ap.add_argument("--settle-seconds", type=int, default=30)
    ap.add_argument("--runtime-ready-timeout-seconds", type=int, default=180)
    ap.add_argument("--probe-interval-seconds", type=int, default=15)
    ap.add_argument("--max-operational-checkpoint-seconds", type=float, default=30.0)
    ap.add_argument("--max-operational-lag-seconds", type=float, default=5.0)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    root.mkdir(parents=True, exist_ok=True)
    out_path = root / f"g3a_{str(args.state_id).strip().lower()}_runtime_warm_gate.json"

    blockers: list[str] = []
    case_labels_namespace = str(args.case_labels_namespace or args.namespace).strip()
    runtime_components = [
        {"app": "fp-pr3-csfb", "namespace": args.namespace},
        {"app": "fp-pr3-ieg", "namespace": args.namespace},
        {"app": "fp-pr3-ofp", "namespace": args.namespace},
        {"app": "fp-pr3-dl", "namespace": args.namespace},
        {"app": "fp-pr3-df", "namespace": args.namespace},
        {"app": "fp-pr3-al", "namespace": args.namespace},
        {"app": "fp-pr3-dla", "namespace": args.namespace},
        {"app": "fp-pr3-archive-writer", "namespace": args.namespace},
    ]
    if state_sequence(args.state_id) >= 4:
        runtime_components.extend(
            [
                {"app": "fp-pr3-case-trigger", "namespace": case_labels_namespace},
                {"app": "fp-pr3-case-mgmt", "namespace": case_labels_namespace},
                {"app": "fp-pr3-label-store", "namespace": case_labels_namespace},
            ]
        )
    pre_status = [pod_status(str(spec["namespace"]), str(spec["app"])) for spec in runtime_components]
    for row in pre_status:
        if row.get("pod_missing"):
            blockers.append(f"PR3.{args.state_id}.WARM.B01_POD_MISSING:{row['app']}")
            continue
        if row.get("phase") != "Running" or not bool(row.get("ready")):
            blockers.append(f"PR3.{args.state_id}.WARM.B02_POD_NOT_READY:{row['app']}")

    df_probe, df_probe_error = ({}, "")
    csfb_probe, csfb_probe_error = ({}, "")
    dl_probe, dl_probe_error = ({}, "")
    ieg_probe, ieg_probe_error = ({}, "")
    ofp_probe, ofp_probe_error = ({}, "")
    case_trigger_probe, case_trigger_probe_error = ({}, "")
    case_mgmt_probe, case_mgmt_probe_error = ({}, "")
    label_store_probe, label_store_probe_error = ({}, "")
    dla_probe, dla_probe_error = ({}, "")
    node_health_rows: list[dict[str, Any]] = []
    dl_bootstrap_pending_flag = False
    if not blockers:
        node_names = sorted(
            {
                str(row.get("node_name") or "").strip()
                for row in pre_status
                for row in [row] + list(row.get("anomalies") or [])
                if str(row.get("node_name") or "").strip()
            }
        )
        node_health_rows = [node_health(node_name) for node_name in node_names]
        for node_row in node_health_rows:
            node_name = str(node_row.get("node_name") or "").strip()
            if bool(node_row.get("node_missing")):
                blockers.append(f"PR3.{args.state_id}.WARM.B13_NODE_MISSING:{node_name}")
                continue
            if not bool(node_row.get("ready")):
                blockers.append(f"PR3.{args.state_id}.WARM.B14_NODE_NOT_READY:{node_name}")
            if bool(node_row.get("disk_pressure")):
                blockers.append(f"PR3.{args.state_id}.WARM.B15_NODE_DISK_PRESSURE:{node_name}")

    probe_attempts: list[dict[str, Any]] = []
    advisory_ids: list[str] = []
    if not blockers:
        deadline = time.time() + max(0, int(args.runtime_ready_timeout_seconds))
        while True:
            attempt_blockers: list[str] = []
            attempt_advisory_ids: list[str] = []
            attempt_started = now_utc()

            csfb_status = next(row for row in pre_status if row.get("app") == "fp-pr3-csfb")
            csfb_probe, csfb_probe_error = exec_json(
                str(csfb_status["namespace"]),
                str(csfb_status["pod_name"]),
                CSFB_WARM_SCRIPT,
                {"FP_PROFILE_PATH": args.profile_path},
            )
            if csfb_probe_error:
                attempt_blockers.append(f"PR3.{args.state_id}.WARM.B03_CSFB_PROBE_FAILED:{csfb_probe_error}")
            else:
                if str(csfb_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                    attempt_blockers.append(
                        f"PR3.{args.state_id}.WARM.B04_CSFB_PLATFORM_RUN_SCOPE_MISMATCH:"
                        f"{csfb_probe.get('required_platform_run_id')}"
                    )
                topic_partitions = dict(csfb_probe.get("topic_partitions") or {})
                for topic in csfb_probe.get("context_topics") or []:
                    if not list(topic_partitions.get(topic) or []):
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B05_CSFB_TOPIC_METADATA_UNREADABLE:{topic}")

            df_status = next(row for row in pre_status if row.get("app") == "fp-pr3-df")
            df_probe, df_probe_error = exec_json(
                str(df_status["namespace"]),
                str(df_status["pod_name"]),
                DF_WARM_SCRIPT,
                {"FP_PROFILE_PATH": args.profile_path},
            )
            if df_probe_error:
                attempt_blockers.append(f"PR3.{args.state_id}.WARM.B06_DF_PROBE_FAILED:{df_probe_error}")
            else:
                if str(df_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                    attempt_blockers.append(
                        f"PR3.{args.state_id}.WARM.B07_PLATFORM_RUN_SCOPE_MISMATCH:"
                        f"{df_probe.get('required_platform_run_id')}"
                    )
                if not bool(df_probe.get("required_scopes_present")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B08_DF_SCOPE_BRIDGE_MISSING")
                if not list(df_probe.get("kafka_partitions") or []):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B09_DF_KAFKA_METADATA_UNREADABLE")
                checkpoint_partitions = sorted(int(item) for item in list(df_probe.get("checkpoint_partitions") or []))
                kafka_partitions = sorted(int(item) for item in list(df_probe.get("kafka_partitions") or []))
                if checkpoint_partitions != kafka_partitions:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B09A_DF_CHECKPOINT_BOUNDARY_MISSING")
                metrics_payload = dict(df_probe.get("metrics_payload") or {})
                health_payload = dict(df_probe.get("health_payload") or {})
                if bool(metrics_payload.get("__missing__")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B09B_DF_METRICS_SURFACE_MISSING")
                if bool(health_payload.get("__missing__")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B09C_DF_HEALTH_SURFACE_MISSING")
                if str(metrics_payload.get("platform_run_id") or "").strip() not in {"", args.platform_run_id}:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B09D_DF_METRICS_SCOPE_MISMATCH")
                if str(health_payload.get("platform_run_id") or "").strip() not in {"", args.platform_run_id}:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B09E_DF_HEALTH_SCOPE_MISMATCH")

            dl_status = next(row for row in pre_status if row.get("app") == "fp-pr3-dl")
            dl_probe, dl_probe_error = exec_json(
                str(dl_status["namespace"]),
                str(dl_status["pod_name"]),
                DL_WARM_SCRIPT,
                {"FP_PROFILE_PATH": args.profile_path},
            )
            dl_bootstrap_pending_flag = False
            if dl_probe_error:
                attempt_blockers.append(f"PR3.{args.state_id}.WARM.B10_DL_PROBE_FAILED:{dl_probe_error}")
            else:
                if not bool(dl_probe.get("record_present")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B11_DL_POSTURE_MISSING")
                else:
                    dl_bootstrap_pending_flag = dl_bootstrap_pending(dl_probe)
                    if dl_bootstrap_pending_flag:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12A_DL_BOOTSTRAP_PENDING")
                    elif str(((dl_probe.get('decision') or {}).get('mode') or '')).strip().upper() == "FAIL_CLOSED":
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12_DL_FAIL_CLOSED")

            ieg_status = next(row for row in pre_status if row.get("app") == "fp-pr3-ieg")
            ieg_probe, ieg_probe_error = probe_component_surface(
                str(ieg_status["namespace"]),
                str(ieg_status["pod_name"]),
                "ieg",
                args.platform_run_id,
            )
            if ieg_probe_error:
                attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12B_IEG_PROBE_FAILED:{ieg_probe_error}")
            else:
                ieg_metrics = dict(ieg_probe.get("metrics_payload") or {})
                ieg_health = dict(ieg_probe.get("health_payload") or {})
                if bool(ieg_metrics.get("__missing__")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12C_IEG_METRICS_SURFACE_MISSING")
                if bool(ieg_health.get("__missing__")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12D_IEG_HEALTH_SURFACE_MISSING")
                if str(ieg_health.get("platform_run_id") or "").strip() not in {"", args.platform_run_id}:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12E_IEG_SCOPE_MISMATCH")
                elif str(ieg_health.get("health_state") or "").strip().upper() in {"RED", "FAILED", "UNHEALTHY"} and not replay_advisory_only(
                    "ieg",
                    ieg_probe,
                    max_checkpoint_seconds=float(args.max_operational_checkpoint_seconds),
                    max_lag_seconds=float(args.max_operational_lag_seconds),
                ):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12F_IEG_NOT_OPERATIONALLY_READY")

            ofp_status = next(row for row in pre_status if row.get("app") == "fp-pr3-ofp")
            ofp_probe, ofp_probe_error = probe_component_surface(
                str(ofp_status["namespace"]),
                str(ofp_status["pod_name"]),
                "ofp",
                args.platform_run_id,
            )
            if ofp_probe_error:
                attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12G_OFP_PROBE_FAILED:{ofp_probe_error}")
            else:
                ofp_metrics = dict(ofp_probe.get("metrics_payload") or {})
                ofp_health = dict(ofp_probe.get("health_payload") or {})
                if bool(ofp_metrics.get("__missing__")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12H_OFP_METRICS_SURFACE_MISSING")
                if bool(ofp_health.get("__missing__")):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12I_OFP_HEALTH_SURFACE_MISSING")
                if str(ofp_health.get("platform_run_id") or "").strip() not in {"", args.platform_run_id}:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12J_OFP_SCOPE_MISMATCH")
                elif str(ofp_health.get("health_state") or "").strip().upper() in {"RED", "FAILED", "UNHEALTHY"} and not replay_advisory_only(
                    "ofp",
                    ofp_probe,
                    max_checkpoint_seconds=float(args.max_operational_checkpoint_seconds),
                    max_lag_seconds=float(args.max_operational_lag_seconds),
                ):
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12K_OFP_NOT_OPERATIONALLY_READY")

            if state_sequence(args.state_id) >= 4:
                case_trigger_status = next(row for row in pre_status if row.get("app") == "fp-pr3-case-trigger")
                case_trigger_probe, case_trigger_probe_error = probe_worker_config(
                    str(case_trigger_status["namespace"]),
                    str(case_trigger_status["pod_name"]),
                    CASE_TRIGGER_WARM_SCRIPT,
                    args.profile_path,
                )
                if case_trigger_probe_error:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12L_CASE_TRIGGER_PROBE_FAILED:{case_trigger_probe_error}")
                else:
                    if str(case_trigger_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12M_CASE_TRIGGER_SCOPE_MISMATCH")
                    if not str(case_trigger_probe.get("scenario_run_id") or "").strip():
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12N_CASE_TRIGGER_SCENARIO_MISSING")
                    elif (
                        str(args.expected_case_label_scenario_run_id or "").strip()
                        and str(case_trigger_probe.get("scenario_run_id") or "").strip()
                        != str(args.expected_case_label_scenario_run_id).strip()
                    ):
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12N1_CASE_TRIGGER_SCENARIO_MISMATCH")
                    if list(case_trigger_probe.get("admitted_topics") or []) != ["fp.bus.rtdl.v1"]:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12O_CASE_TRIGGER_TOPIC_DRIFT")

                case_mgmt_status = next(row for row in pre_status if row.get("app") == "fp-pr3-case-mgmt")
                case_mgmt_probe, case_mgmt_probe_error = probe_worker_config(
                    str(case_mgmt_status["namespace"]),
                    str(case_mgmt_status["pod_name"]),
                    CASE_MGMT_WARM_SCRIPT,
                    args.profile_path,
                )
                if case_mgmt_probe_error:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12P_CASE_MGMT_PROBE_FAILED:{case_mgmt_probe_error}")
                else:
                    if str(case_mgmt_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12Q_CASE_MGMT_SCOPE_MISMATCH")
                    if not str(case_mgmt_probe.get("scenario_run_id") or "").strip():
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12R_CASE_MGMT_SCENARIO_MISSING")
                    elif (
                        str(args.expected_case_label_scenario_run_id or "").strip()
                        and str(case_mgmt_probe.get("scenario_run_id") or "").strip()
                        != str(args.expected_case_label_scenario_run_id).strip()
                    ):
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12R1_CASE_MGMT_SCENARIO_MISMATCH")
                    if list(case_mgmt_probe.get("admitted_topics") or []) != ["fp.bus.case.triggers.v1"]:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12S_CASE_MGMT_TOPIC_DRIFT")

                label_store_status = next(row for row in pre_status if row.get("app") == "fp-pr3-label-store")
                label_store_probe, label_store_probe_error = probe_worker_config(
                    str(label_store_status["namespace"]),
                    str(label_store_status["pod_name"]),
                    LABEL_STORE_WARM_SCRIPT,
                    args.profile_path,
                )
                if label_store_probe_error:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12T_LABEL_STORE_PROBE_FAILED:{label_store_probe_error}")
                else:
                    if str(label_store_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12U_LABEL_STORE_SCOPE_MISMATCH")
                    if not str(label_store_probe.get("scenario_run_id") or "").strip():
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12V_LABEL_STORE_SCENARIO_MISSING")
                    elif (
                        str(args.expected_case_label_scenario_run_id or "").strip()
                        and str(label_store_probe.get("scenario_run_id") or "").strip()
                        != str(args.expected_case_label_scenario_run_id).strip()
                    ):
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12V1_LABEL_STORE_SCENARIO_MISMATCH")

                dla_status = next(row for row in pre_status if row.get("app") == "fp-pr3-dla")
                dla_probe, dla_probe_error = probe_worker_config(
                    str(dla_status["namespace"]),
                    str(dla_status["pod_name"]),
                    DLA_WARM_SCRIPT,
                    args.profile_path,
                )
                if dla_probe_error:
                    attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12W_DLA_PROBE_FAILED:{dla_probe_error}")
                else:
                    if str(dla_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12X_DLA_SCOPE_MISMATCH")
                    if list(dla_probe.get("admitted_topics") or []) != ["fp.bus.rtdl.v1"]:
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12Y_DLA_TOPIC_DRIFT")
                    if "::" not in str(dla_probe.get("stream_id") or "").strip():
                        attempt_blockers.append(f"PR3.{args.state_id}.WARM.B12Z_DLA_STREAM_UNSCOPED")

            pretraffic_allowed, pretraffic_advisory = pretraffic_bootstrap_allowed(
                args.state_id,
                attempt_blockers,
                dl_bootstrap_pending_flag=dl_bootstrap_pending_flag,
                df_probe=df_probe,
                ieg_probe=ieg_probe,
                ofp_probe=ofp_probe,
            )
            if pretraffic_allowed:
                attempt_advisory_ids.append(pretraffic_advisory)
                advisory_ids.append(pretraffic_advisory)
                attempt_blockers = []
            else:
                transition_allowed, transition_advisory = scenario_transition_allowed(
                    args.state_id,
                    attempt_blockers,
                    expected_case_label_scenario_run_id=str(args.expected_case_label_scenario_run_id).strip(),
                    df_probe=df_probe,
                    ieg_probe=ieg_probe,
                    ofp_probe=ofp_probe,
                    case_trigger_probe=case_trigger_probe,
                    case_mgmt_probe=case_mgmt_probe,
                    label_store_probe=label_store_probe,
                    max_checkpoint_seconds=float(args.max_operational_checkpoint_seconds),
                    max_lag_seconds=float(args.max_operational_lag_seconds),
                )
                if transition_allowed:
                    attempt_advisory_ids.append(transition_advisory)
                    advisory_ids.append(transition_advisory)
                    attempt_blockers = []

            probe_attempts.append(
                {
                    "attempt_started_utc": attempt_started,
                    "blocker_ids": sorted(set(attempt_blockers)),
                    "advisory_ids": sorted(set(attempt_advisory_ids)),
                    "dl_bootstrap_pending": dl_bootstrap_pending_flag,
                    "df_metrics_present": not bool(dict(df_probe.get("metrics_payload") or {}).get("__missing__")),
                    "ieg_metrics_present": not bool(dict(ieg_probe.get("metrics_payload") or {}).get("__missing__")),
                    "ofp_metrics_present": not bool(dict(ofp_probe.get("metrics_payload") or {}).get("__missing__")),
                    "df_zero_activity": zero_df_activity(df_probe),
                    "ieg_bootstrap_pending": ieg_bootstrap_pending(ieg_probe),
                    "ofp_bootstrap_pending": ofp_bootstrap_pending(ofp_probe),
                }
            )
            blockers = attempt_blockers
            if not blockers:
                break
            if time.time() >= deadline:
                break
            time.sleep(max(1, int(args.probe_interval_seconds)))

    if not blockers and args.settle_seconds > 0:
        time.sleep(args.settle_seconds)

    post_status = [pod_status(str(spec["namespace"]), str(spec["app"])) for spec in runtime_components]
    if not blockers:
        for before, after in zip(pre_status, post_status, strict=False):
            if after.get("pod_missing"):
                blockers.append(f"PR3.{args.state_id}.WARM.B16_POD_DISAPPEARED:{after['app']}")
                continue
            if after.get("phase") != "Running" or not bool(after.get("ready")):
                blockers.append(f"PR3.{args.state_id}.WARM.B17_POD_NOT_STABLE:{after['app']}")
            if int(after.get("restart_count", 0) or 0) > int(before.get("restart_count", 0) or 0):
                blockers.append(f"PR3.{args.state_id}.WARM.B18_RESTART_DURING_SETTLE:{after['app']}")

    payload = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "platform_run_id": args.platform_run_id,
        "namespaces": {
            "runtime": args.namespace,
            "case_labels": case_labels_namespace,
        },
        "profile_path": args.profile_path,
        "expected_case_label_scenario_run_id": str(args.expected_case_label_scenario_run_id).strip(),
        "settle_seconds": args.settle_seconds,
        "pre_status": pre_status,
        "csfb_probe": csfb_probe,
        "csfb_probe_error": csfb_probe_error,
        "dl_probe": dl_probe,
        "dl_bootstrap_pending": dl_bootstrap_pending_flag,
        "dl_probe_error": dl_probe_error,
        "df_probe": df_probe,
        "df_probe_error": df_probe_error,
        "ieg_probe": ieg_probe,
        "ieg_probe_error": ieg_probe_error,
        "ofp_probe": ofp_probe,
        "ofp_probe_error": ofp_probe_error,
        "case_trigger_probe": case_trigger_probe,
        "case_trigger_probe_error": case_trigger_probe_error,
        "case_mgmt_probe": case_mgmt_probe,
        "case_mgmt_probe_error": case_mgmt_probe_error,
        "label_store_probe": label_store_probe,
        "label_store_probe_error": label_store_probe_error,
        "dla_probe": dla_probe,
        "dla_probe_error": dla_probe_error,
        "probe_attempts": probe_attempts,
        "runtime_ready_timeout_seconds": args.runtime_ready_timeout_seconds,
        "probe_interval_seconds": args.probe_interval_seconds,
        "node_health": node_health_rows,
        "post_status": post_status,
        "advisory_ids": sorted(set(advisory_ids)),
        "overall_pass": len(blockers) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    dump_json(out_path, payload)
    print(json.dumps(payload, indent=2))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
