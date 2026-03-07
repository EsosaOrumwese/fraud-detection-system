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

from fraud_detection.decision_fabric.registry import RegistryScopeKey, RegistrySnapshot
from fraud_detection.decision_fabric.worker import load_worker_config
from fraud_detection.event_bus.kafka import build_kafka_reader
from fraud_detection.platform_runtime import RUNS_ROOT

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
snapshot = RegistrySnapshot.load(cfg.registry_snapshot_ref)
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
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "scenario_run_id_hint": cfg.scenario_run_id_hint,
    "event_bus_start_position": cfg.event_bus_start_position,
    "registry_snapshot_ref": str(cfg.registry_snapshot_ref),
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
from fraud_detection.context_store_flow_binding.observability import CsfbObservabilityReporter
from fraud_detection.event_bus.kafka import build_kafka_reader

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
policy = CsfbInletPolicy.load(profile_path)
reader = build_kafka_reader(client_id="pr3-csfb-warm-gate")
topic_partitions = {topic: reader.list_partitions(topic) for topic in policy.context_topics}
reporter = CsfbObservabilityReporter.build(locator=policy.projection_db_dsn, stream_id=policy.stream_id)
snapshot = reporter.collect(platform_run_id=policy.required_platform_run_id)
print(json.dumps({
    "required_platform_run_id": policy.required_platform_run_id,
    "event_bus_start_position": policy.event_bus_start_position,
    "projection_db_dsn": policy.projection_db_dsn,
    "stream_id": policy.stream_id,
    "context_topics": list(policy.context_topics),
    "topic_partitions": topic_partitions,
    "metrics": snapshot.get("metrics", {}),
    "checkpoints": snapshot.get("checkpoints", {}),
    "health_state": snapshot.get("health_state"),
    "health_reasons": snapshot.get("health_reasons", []),
}))
"""


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


def dl_bootstrap_pending(dl_probe: dict[str, Any], csfb_probe: dict[str, Any]) -> bool:
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
    if not gap_items.issubset(allowed_bootstrap_gaps):
        return False
    metrics = dict(csfb_probe.get("metrics", {}) or {})
    health_reasons = {str(item).strip() for item in (csfb_probe.get("health_reasons") or []) if str(item).strip()}
    no_context_activity = all(int(metrics.get(key, 0) or 0) == 0 for key in ("join_hits", "join_misses", "binding_conflicts"))
    missing_watermark = {"WATERMARK_MISSING", "CHECKPOINT_MISSING"}.issubset(health_reasons)
    return no_context_activity and missing_watermark


def pod_status(namespace: str, app: str) -> dict[str, Any]:
    pods = get_json(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={app}", "-o", "json"], timeout=120)
    items = list(pods.get("items", []) or [])
    if not items:
        return {"app": app, "pod_missing": True}
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
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--settle-seconds", type=int, default=30)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    root.mkdir(parents=True, exist_ok=True)
    out_path = root / f"g3a_{str(args.state_id).strip().lower()}_runtime_warm_gate.json"

    blockers: list[str] = []
    components = [
        "fp-pr3-csfb",
        "fp-pr3-ieg",
        "fp-pr3-ofp",
        "fp-pr3-dl",
        "fp-pr3-df",
        "fp-pr3-al",
        "fp-pr3-dla",
        "fp-pr3-archive-writer",
    ]
    pre_status = [pod_status(args.namespace, app) for app in components]
    for row in pre_status:
        if row.get("pod_missing"):
            blockers.append(f"PR3.{args.state_id}.WARM.B01_POD_MISSING:{row['app']}")
            continue
        if row.get("phase") != "Running" or not bool(row.get("ready")):
            blockers.append(f"PR3.{args.state_id}.WARM.B02_POD_NOT_READY:{row['app']}")

    df_probe, df_probe_error = ({}, "")
    csfb_probe, csfb_probe_error = ({}, "")
    dl_probe, dl_probe_error = ({}, "")
    node_health_rows: list[dict[str, Any]] = []
    dl_bootstrap_pending_flag = False
    if not blockers:
        csfb_status = next(row for row in pre_status if row.get("app") == "fp-pr3-csfb")
        csfb_probe, csfb_probe_error = exec_json(
            args.namespace,
            str(csfb_status["pod_name"]),
            CSFB_WARM_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
        if csfb_probe_error:
            blockers.append(f"PR3.{args.state_id}.WARM.B03_CSFB_PROBE_FAILED:{csfb_probe_error}")
        else:
            if str(csfb_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                blockers.append(
                    f"PR3.{args.state_id}.WARM.B04_CSFB_PLATFORM_RUN_SCOPE_MISMATCH:"
                    f"{csfb_probe.get('required_platform_run_id')}"
                )
            topic_partitions = dict(csfb_probe.get("topic_partitions") or {})
            for topic in csfb_probe.get("context_topics") or []:
                if not list(topic_partitions.get(topic) or []):
                    blockers.append(f"PR3.{args.state_id}.WARM.B05_CSFB_TOPIC_METADATA_UNREADABLE:{topic}")

        df_status = next(row for row in pre_status if row.get("app") == "fp-pr3-df")
        df_probe, df_probe_error = exec_json(
            args.namespace,
            str(df_status["pod_name"]),
            DF_WARM_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
        if df_probe_error:
            blockers.append(f"PR3.{args.state_id}.WARM.B06_DF_PROBE_FAILED:{df_probe_error}")
        else:
            if str(df_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                blockers.append(
                    f"PR3.{args.state_id}.WARM.B07_PLATFORM_RUN_SCOPE_MISMATCH:"
                    f"{df_probe.get('required_platform_run_id')}"
                )
            if not bool(df_probe.get("required_scopes_present")):
                blockers.append(f"PR3.{args.state_id}.WARM.B08_DF_SCOPE_BRIDGE_MISSING")
            if not list(df_probe.get("kafka_partitions") or []):
                blockers.append(f"PR3.{args.state_id}.WARM.B09_DF_KAFKA_METADATA_UNREADABLE")
            checkpoint_partitions = sorted(int(item) for item in list(df_probe.get("checkpoint_partitions") or []))
            kafka_partitions = sorted(int(item) for item in list(df_probe.get("kafka_partitions") or []))
            if checkpoint_partitions != kafka_partitions:
                blockers.append(f"PR3.{args.state_id}.WARM.B09A_DF_CHECKPOINT_BOUNDARY_MISSING")
            metrics_payload = dict(df_probe.get("metrics_payload") or {})
            health_payload = dict(df_probe.get("health_payload") or {})
            if bool(metrics_payload.get("__missing__")):
                blockers.append(f"PR3.{args.state_id}.WARM.B09B_DF_METRICS_SURFACE_MISSING")
            if bool(health_payload.get("__missing__")):
                blockers.append(f"PR3.{args.state_id}.WARM.B09C_DF_HEALTH_SURFACE_MISSING")
            if str(metrics_payload.get("platform_run_id") or "").strip() not in {"", args.platform_run_id}:
                blockers.append(f"PR3.{args.state_id}.WARM.B09D_DF_METRICS_SCOPE_MISMATCH")
            if str(health_payload.get("platform_run_id") or "").strip() not in {"", args.platform_run_id}:
                blockers.append(f"PR3.{args.state_id}.WARM.B09E_DF_HEALTH_SCOPE_MISMATCH")

        dl_status = next(row for row in pre_status if row.get("app") == "fp-pr3-dl")
        dl_probe, dl_probe_error = exec_json(
            args.namespace,
            str(dl_status["pod_name"]),
            DL_WARM_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
        if dl_probe_error:
            blockers.append(f"PR3.{args.state_id}.WARM.B10_DL_PROBE_FAILED:{dl_probe_error}")
        else:
            if not bool(dl_probe.get("record_present")):
                blockers.append(f"PR3.{args.state_id}.WARM.B11_DL_POSTURE_MISSING")
            elif dl_bootstrap_pending(dl_probe, csfb_probe):
                dl_bootstrap_pending_flag = True
            elif str(((dl_probe.get('decision') or {}).get('mode') or '')).strip().upper() == "FAIL_CLOSED":
                blockers.append(f"PR3.{args.state_id}.WARM.B12_DL_FAIL_CLOSED")

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

    if not blockers and args.settle_seconds > 0:
        time.sleep(args.settle_seconds)

    post_status = [pod_status(args.namespace, app) for app in components]
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
        "namespace": args.namespace,
        "profile_path": args.profile_path,
        "settle_seconds": args.settle_seconds,
        "pre_status": pre_status,
        "csfb_probe": csfb_probe,
        "csfb_probe_error": csfb_probe_error,
        "dl_probe": dl_probe,
        "dl_bootstrap_pending": dl_bootstrap_pending_flag,
        "dl_probe_error": dl_probe_error,
        "df_probe": df_probe,
        "df_probe_error": df_probe_error,
        "node_health": node_health_rows,
        "post_status": post_status,
        "overall_pass": len(blockers) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    dump_json(out_path, payload)
    print(json.dumps(payload, indent=2))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
