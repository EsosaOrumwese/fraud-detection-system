#!/usr/bin/env python3
"""Collect run-scoped PR3 runtime surfaces from the live EKS workers."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def archive_existing(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    hist = path.parent / "attempt_history"
    hist.mkdir(parents=True, exist_ok=True)
    (hist / f"{path.stem}.{stamp}{path.suffix}").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def run(cmd: list[str], *, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def get_json(cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = run(cmd, timeout=timeout, check=True)
    text = proc.stdout.strip()
    return json.loads(text) if text else {}


def exec_json(namespace: str, pod: str, script: str, env_map: dict[str, str]) -> tuple[dict[str, Any], str]:
    env_bits = [f"{key}={value}" for key, value in sorted(env_map.items())]
    proc = run(
        ["kubectl", "exec", "-n", namespace, pod, "--", "env", *env_bits, "python", "-c", script],
        timeout=180,
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
def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


COMPONENTS: dict[str, dict[str, Any]] = {
    "csfb": {
        "app": "fp-pr3-csfb",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/context_store_flow_binding/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/context_store_flow_binding/health/last_health.json",
        "threshold_defaults": {
            "watermark_age_seconds": {"amber": 120.0, "red": 300.0},
            "checkpoint_age_seconds": {"amber": 120.0, "red": 300.0},
            "join_misses": {"amber": 1, "red": 10},
            "binding_conflicts": {"amber": 1, "red": 5},
            "apply_failures_hard": {"amber": 1, "red": 10},
        },
    },
    "ieg": {
        "app": "fp-pr3-ieg",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/identity_entity_graph/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/identity_entity_graph/health/last_health.json",
        "threshold_defaults": {
            "watermark_age_seconds": {"amber": 120.0, "red": 300.0},
            "checkpoint_age_seconds": {"amber": 120.0, "red": 300.0},
            "apply_failure_count": {"amber": 1, "red": 100},
            "backpressure_hits_delta_max": 0,
        },
    },
    "ofp": {
        "app": "fp-pr3-ofp",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/online_feature_plane/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/online_feature_plane/health/last_health.json",
        "threshold_defaults": {
            "watermark_age_seconds": {"amber": 120.0, "red": 300.0},
            "checkpoint_age_seconds": {"amber": 120.0, "red": 300.0},
            "lag_seconds": {"amber": 120.0, "red": 300.0},
            "missing_features": {"amber": 1, "red": 10},
            "snapshot_failures": {"amber": 1, "red": 5},
        },
    },
    "dl": {
        "app": "fp-pr3-dl",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/degrade_ladder/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/degrade_ladder/health/last_health.json",
        "threshold_defaults": {
            "decision_mode": "NORMAL",
            "required_signal_states_ok": True,
        },
    },
    "df": {
        "app": "fp-pr3-df",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/decision_fabric/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/decision_fabric/health/last_health.json",
        "threshold_defaults": {
            "publish_quarantine_total_delta_max": 0,
            "hard_fail_closed_total_delta_max": 0,
        },
    },
    "al": {
        "app": "fp-pr3-al",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/action_layer/observability/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/action_layer/health/last_health.json",
        "threshold_defaults": {
            "queue_depth": {"amber": 100, "red": 1000},
            "lag_events": {"amber": 10, "red": 100},
            "publish_quarantine_total_delta_max": 0,
            "publish_ambiguous_total_delta_max": 0,
        },
    },
    "dla": {
        "app": "fp-pr3-dla",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/decision_log_audit/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/decision_log_audit/health/last_health.json",
        "threshold_defaults": {
            "checkpoint_age_seconds": {"amber": 120.0, "red": 300.0},
            "quarantine_total": {"amber": 1, "red": 25},
            "append_failure_total": {"amber": 1, "red": 5},
            "replay_divergence_total": {"amber": 1, "red": 1},
        },
    },
    "archive_writer": {
        "app": "fp-pr3-archive-writer",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/archive_writer/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/archive_writer/health/last_health.json",
        "threshold_defaults": {
            "write_error_total_delta_max": 0,
            "payload_mismatch_total_delta_max": 0,
        },
    },
    "case_trigger": {
        "app": "fp-pr3-case-trigger",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/case_trigger/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/case_trigger/health/last_health.json",
        "threshold_defaults": {
            "publish_quarantine_total_delta_max": 0,
            "publish_ambiguous_total_delta_max": 0,
            "payload_mismatch_total_delta_max": 0,
        },
    },
    "case_mgmt": {
        "app": "fp-pr3-case-mgmt",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/case_mgmt/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/case_mgmt/health/last_health.json",
        "threshold_defaults": {
            "mismatches_total_delta_max": 0,
            "anomalies_total_delta_max": 0,
        },
    },
    "label_store": {
        "app": "fp-pr3-label-store",
        "metrics_path": "runs/fraud-platform/{platform_run_id}/label_store/metrics/last_metrics.json",
        "health_path": "runs/fraud-platform/{platform_run_id}/label_store/health/last_health.json",
        "threshold_defaults": {
            "rejected_delta_max": 0,
            "pending_backlog_red": 500.0,
        },
    },
}

CASE_LABEL_COMPONENTS = {"case_trigger", "case_mgmt", "label_store"}


def component_namespace(component: str, *, runtime_namespace: str, case_labels_namespace: str) -> str:
    if component in CASE_LABEL_COMPONENTS:
        return str(case_labels_namespace or runtime_namespace).strip()
    return str(runtime_namespace).strip()


REMOTE_SCRIPT = r"""
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

payload = {
    "metrics": load_json(metrics_path),
    "health": load_json(health_path),
}
print(json.dumps(payload))
"""


def pick_summary(component: str, metrics_payload: dict[str, Any], health_payload: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(metrics_payload.get("metrics", {}) or {}) if isinstance(metrics_payload, dict) else {}
    summary: dict[str, Any] = {
        "health_state": health_payload.get("health_state"),
        "health_reasons": health_payload.get("health_reasons"),
    }
    if component == "csfb":
        summary.update(
            {
                "join_hits": to_float(metrics.get("join_hits")),
                "join_misses": to_float(metrics.get("join_misses")),
                "binding_conflicts": to_float(metrics.get("binding_conflicts")),
                "apply_failures_hard": to_float(metrics.get("apply_failures_hard")),
                "checkpoint_age_seconds": to_float(metrics_payload.get("checkpoint_age_seconds"))
                or to_float(health_payload.get("checkpoint_age_seconds")),
                "watermark_age_seconds": to_float(metrics_payload.get("watermark_age_seconds"))
                or to_float(health_payload.get("watermark_age_seconds")),
                "lag_seconds": to_float(metrics_payload.get("lag_seconds")),
            }
        )
    elif component == "ieg":
        summary.update(
            {
                "backpressure_hits": to_float(metrics_payload.get("backpressure_hits")),
                "apply_failure_count": to_float(metrics_payload.get("apply_failure_count")),
                "checkpoint_age_seconds": to_float(metrics_payload.get("checkpoint_age_seconds"))
                or to_float(health_payload.get("checkpoint_age_seconds")),
                "watermark_age_seconds": to_float(metrics_payload.get("watermark_age_seconds"))
                or to_float(health_payload.get("watermark_age_seconds")),
                "events_seen": to_float(metrics.get("events_seen")),
            }
        )
    elif component == "ofp":
        summary.update(
            {
                "lag_seconds": to_float(metrics_payload.get("lag_seconds")),
                "checkpoint_age_seconds": to_float(metrics_payload.get("checkpoint_age_seconds")),
                "watermark_age_seconds": to_float(metrics_payload.get("watermark_age_seconds")),
                "missing_features": to_float(metrics.get("missing_features")),
                "snapshot_failures": to_float(metrics.get("snapshot_failures")),
                "duplicates": to_float(metrics.get("duplicates")),
                "events_applied": to_float(metrics.get("events_applied")),
            }
        )
    elif component == "df":
        lat = dict(metrics_payload.get("latency_ms", {}) or {})
        summary.update(
            {
                "decisions_total": to_float(metrics.get("decisions_total")),
                "degrade_total": to_float(metrics.get("degrade_total")),
                "step_up_total": to_float(metrics.get("step_up_total")),
                "explicit_fallback_total": to_float(metrics.get("explicit_fallback_total")),
                "missing_context_total": to_float(metrics.get("missing_context_total")),
                "resolver_failures_total": to_float(metrics.get("resolver_failures_total")),
                "fail_closed_total": to_float(metrics.get("fail_closed_total")),
                "hard_fail_closed_total": to_float(metrics.get("hard_fail_closed_total"))
                if metrics.get("hard_fail_closed_total") is not None
                else to_float(metrics.get("fail_closed_total")),
                "publish_quarantine_total": to_float(metrics.get("publish_quarantine_total")),
                "latency_p95_ms": to_float(lat.get("p95")),
                "latency_p99_ms": to_float(lat.get("p99")),
            }
        )
    elif component == "dl":
        required_signal_states = dict(metrics_payload.get("required_signal_states", {}) or {})
        summary.update(
            {
                "decision_mode": metrics_payload.get("decision_mode"),
                "posture_seq": to_float(metrics_payload.get("posture_seq")),
                "required_signal_states": required_signal_states,
                "bad_required_signals": health_payload.get("bad_required_signals"),
            }
        )
    elif component == "al":
        signals = dict(health_payload.get("signals", {}) or {})
        summary.update(
            {
                "intake_total": to_float(metrics.get("intake_total")),
                "publish_quarantine_total": to_float(metrics.get("publish_quarantine_total")),
                "publish_ambiguous_total": to_float(metrics.get("publish_ambiguous_total")),
                "queue_depth": to_float(signals.get("queue_depth")),
                "lag_events": to_float(signals.get("lag_events")),
                "error_rate": to_float(signals.get("error_rate")),
            }
        )
    elif component == "dla":
        summary.update(
            {
                "checkpoint_age_seconds": to_float(metrics_payload.get("checkpoint_age_seconds"))
                or to_float(health_payload.get("checkpoint_age_seconds")),
                "watermark_age_seconds": to_float(metrics_payload.get("watermark_age_seconds"))
                or to_float(health_payload.get("watermark_age_seconds")),
                "quarantine_total": to_float(metrics.get("quarantine_total")),
                "append_failure_total": to_float(metrics.get("append_failure_total")),
                "replay_divergence_total": to_float(metrics.get("replay_divergence_total")),
                "append_success_total": to_float(metrics.get("append_success_total")),
            }
        )
    elif component == "archive_writer":
        seen = to_float(metrics.get("seen_total")) or 0.0
        archived = to_float(metrics.get("archived_total")) or 0.0
        summary.update(
            {
                "seen_total": seen,
                "archived_total": archived,
                "duplicate_total": to_float(metrics.get("duplicate_total")),
                "payload_mismatch_total": to_float(metrics.get("payload_mismatch_total")),
                "write_error_total": to_float(metrics.get("write_error_total")),
                "backlog_events": max(0.0, seen - archived),
            }
        )
    elif component == "case_trigger":
        summary.update(
            {
                "triggers_seen": to_float(metrics.get("triggers_seen")),
                "published": to_float(metrics.get("published"))
                if metrics.get("published") is not None
                else to_float(metrics.get("publish_admitted_total")),
                "publish_admitted_total": to_float(metrics.get("publish_admitted_total")),
                "duplicates": to_float(metrics.get("duplicates")),
                "quarantine": to_float(metrics.get("quarantine"))
                if metrics.get("quarantine") is not None
                else to_float(metrics.get("publish_quarantine_total")),
                "payload_mismatch_total": to_float(metrics.get("payload_mismatch_total")),
                "publish_quarantine_total": to_float(metrics.get("publish_quarantine_total")),
                "publish_ambiguous_total": to_float(metrics.get("publish_ambiguous_total")),
                "replay_mismatch_total": to_float(metrics.get("payload_mismatch_total")),
            }
        )
    elif component == "case_mgmt":
        anomalies = dict(health_payload.get("anomalies", {}) or {})
        summary.update(
            {
                "case_triggers": to_float(metrics.get("case_triggers")),
                "cases_created": to_float(metrics.get("cases_created")),
                "timeline_events": to_float(metrics.get("timeline_events")),
                "timeline_events_appended": to_float(metrics.get("timeline_events_appended")),
                "case_replays": to_float(metrics.get("case_replays")),
                "label_assertions": to_float(metrics.get("label_assertions")),
                "labels_pending": to_float(metrics.get("labels_pending")),
                "labels_accepted": to_float(metrics.get("labels_accepted")),
                "labels_rejected": to_float(metrics.get("labels_rejected")),
                "label_status_pending": to_float(metrics.get("label_status_pending")),
                "label_status_accepted": to_float(metrics.get("label_status_accepted")),
                "label_status_rejected": to_float(metrics.get("label_status_rejected")),
                "evidence_pending": to_float(metrics.get("evidence_pending")),
                "evidence_unavailable": to_float(metrics.get("evidence_unavailable")),
                "payload_mismatches": to_float(metrics.get("payload_mismatches")),
                "anomalies_total": to_float(anomalies.get("total")),
            }
        )
    elif component == "label_store":
        summary.update(
            {
                "pending": to_float(metrics.get("pending")),
                "accepted": to_float(metrics.get("accepted")),
                "rejected": to_float(metrics.get("rejected")),
                "duplicate": to_float(metrics.get("duplicate")),
                "timeline_rows": to_float(metrics.get("timeline_rows")),
                "payload_hash_mismatch": to_float(metrics.get("payload_hash_mismatch")),
                "dedupe_tuple_collision": to_float(metrics.get("dedupe_tuple_collision")),
                "missing_evidence_refs": to_float(metrics.get("missing_evidence_refs")),
                "reconciliation_anomalies": to_float(metrics.get("reconciliation_anomalies")),
                "anomalies_total": to_float((health_payload.get("anomalies") or {}).get("total")),
            }
        )
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect PR3 runtime component surfaces from EKS.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S2")
    ap.add_argument("--snapshot-label", required=True)
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="")
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    root.mkdir(parents=True, exist_ok=True)
    out_path = root / f"g3a_{str(args.state_id).strip().lower()}_component_snapshot_{str(args.snapshot_label).strip().lower()}.json"
    archive_existing(out_path)

    snapshot: dict[str, Any] = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "snapshot_label": args.snapshot_label,
        "platform_run_id": args.platform_run_id,
        "namespaces": {
            "runtime": args.namespace,
            "case_labels": str(args.case_labels_namespace or args.namespace).strip(),
        },
        "components": {},
        "blocker_ids": [],
    }

    for component, spec in COMPONENTS.items():
        namespace = component_namespace(
            component,
            runtime_namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
        )
        pods = get_json(
            ["kubectl", "get", "pods", "-n", namespace, "-l", f"app={spec['app']}", "-o", "json"],
            timeout=120,
        )
        items = list(pods.get("items", []))
        if not items:
            snapshot["blocker_ids"].append(f"PR3.{args.state_id}.RUNTIME.B01_COMPONENT_POD_MISSING:{component}")
            snapshot["components"][component] = {"pod_missing": True, "namespace": namespace}
            continue
        pod = items[0]
        pod_name = str(pod.get("metadata", {}).get("name", "")).strip()
        container_statuses = list(pod.get("status", {}).get("containerStatuses", []) or [])
        metrics_payload, metrics_error = exec_json(
            namespace,
            pod_name,
            REMOTE_SCRIPT,
            {
                "FP_PLATFORM_RUN_ID": args.platform_run_id,
                "FP_METRICS_PATH": str(spec["metrics_path"]),
                "FP_HEALTH_PATH": str(spec["health_path"]),
            },
        )
        if metrics_error:
            snapshot["blocker_ids"].append(f"PR3.{args.state_id}.RUNTIME.B02_COMPONENT_SURFACE_UNREADABLE:{component}:{metrics_error}")
        payload_metrics = dict(metrics_payload.get("metrics", {}) or {})
        payload_health = dict(metrics_payload.get("health", {}) or {})
        snapshot["components"][component] = {
            "app": spec["app"],
            "namespace": namespace,
            "pod_name": pod_name,
            "pod_phase": pod.get("status", {}).get("phase"),
            "restart_count": int(sum(int(row.get("restartCount", 0) or 0) for row in container_statuses)),
            "image": str((container_statuses[0].get("image") if container_statuses else "") or "").strip(),
            "threshold_defaults": spec["threshold_defaults"],
            "metrics_path": str(spec["metrics_path"]).format(platform_run_id=args.platform_run_id),
            "health_path": str(spec["health_path"]).format(platform_run_id=args.platform_run_id),
            "metrics_payload": payload_metrics,
            "health_payload": payload_health,
            "summary": pick_summary(component, payload_metrics, payload_health),
        }

    dump_json(out_path, snapshot)
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
