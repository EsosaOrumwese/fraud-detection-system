#!/usr/bin/env python3
"""Build PR3-S5 soak evidence from live runtime artifacts."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(math.ceil(len(ordered) * q)) - 1))
    return float(ordered[idx])


def summary_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


def health_state(snapshot: dict[str, Any], component: str) -> str:
    return str((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_state") or "UNKNOWN")


def health_reasons(snapshot: dict[str, Any], component: str) -> list[str]:
    raw = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_reasons"))
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = summary_value(pre, component, field)
    end = summary_value(post, component, field)
    if end is None:
        return None
    if start is None:
        start = 0.0
    return float(end - start)


def is_missing(snapshot: dict[str, Any], component: str) -> bool:
    payloads = ((snapshot.get("components") or {}).get(component) or {})
    for key in ("metrics_payload", "health_payload"):
        payload = payloads.get(key) or {}
        if payload.get("__missing__") or payload.get("__unreadable__"):
            return True
    return False


def replay_advisory_only(snapshot: dict[str, Any], component: str, max_checkpoint: float, max_lag: float) -> bool:
    state = health_state(snapshot, component).upper()
    if state not in {"RED", "FAILED", "UNHEALTHY", "AMBER"}:
        return False
    reasons = set(health_reasons(snapshot, component))
    checkpoint = summary_value(snapshot, component, "checkpoint_age_seconds")
    if checkpoint is None or checkpoint > max_checkpoint:
        return False
    lag = summary_value(snapshot, component, "lag_seconds")
    if lag is not None and lag > max_lag:
        return False
    if component == "ofp":
        if reasons == {"WATERMARK_TOO_OLD"}:
            return (summary_value(snapshot, component, "snapshot_failures") or 0.0) == 0.0
        return reasons == {"WATERMARK_TOO_OLD", "MISSING_FEATURES_RED"} and (summary_value(snapshot, component, "snapshot_failures") or 0.0) == 0.0
    if component == "ieg":
        return reasons == {"WATERMARK_TOO_OLD"} and (summary_value(snapshot, component, "apply_failure_count") or 0.0) == 0.0
    if component == "csfb":
        return reasons == {"WATERMARK_TOO_OLD"} and (summary_value(snapshot, component, "binding_conflicts") or 0.0) == 0.0
    if component == "dla":
        return reasons in ({"UNRESOLVED_AMBER"}, {"UNRESOLVED_AMBER", "WATERMARK_TOO_OLD"}) and (
            (summary_value(snapshot, component, "append_failure_total") or 0.0) == 0.0
            and (summary_value(snapshot, component, "replay_divergence_total") or 0.0) == 0.0
        )
    return False


def select_snapshots(snapshots: list[dict[str, Any]], platform_run_id: str) -> list[dict[str, Any]]:
    selected = [row for row in snapshots if str(row.get("platform_run_id", "")).strip() == platform_run_id]
    labels = {str(row.get("snapshot_label", "")).strip().lower() for row in selected}
    if not selected or "soak_pre" not in labels or "soak_post" not in labels:
        raise RuntimeError("PR3.S5.SOAK.B01_WINDOW_NOT_EXECUTED")
    return selected


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    target = str(label).strip().lower()
    for row in reversed(snapshots):
        if str(row.get("snapshot_label", "")).strip().lower() == target:
            return row
    return snapshots[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S5")
    ap.add_argument("--artifact-prefix", default="g3a_soak")
    ap.add_argument("--expected-soak-eps", type=float, default=3000.0)
    ap.add_argument("--min-processed-events", type=float, default=5400000.0)
    ap.add_argument("--max-error-rate-ratio", type=float, default=0.002)
    ap.add_argument("--max-4xx-ratio", type=float, default=0.002)
    ap.add_argument("--max-5xx-ratio", type=float, default=0.0)
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--max-lag-p99-seconds", type=float, default=5.0)
    ap.add_argument("--max-checkpoint-p99-seconds", type=float, default=30.0)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    prefix = str(args.artifact_prefix).strip()
    summary = load_optional_json(root / f"{prefix}_wsp_runtime_summary.json")
    manifest = load_optional_json(root / f"{prefix}_wsp_runtime_manifest.json")
    ingress_bins = (load_optional_json(root / f"{prefix}_ingress_bins.json") or {}).get("bins", [])
    cost_receipt = load_optional_json(root / "g3a_runtime_cost_receipt.json") or {"overall_pass": False}
    snapshots = sorted(
        [load_json(path) for path in root.glob("g3a_s5_component_snapshot_*.json")],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )

    platform_run_id = str((((manifest or {}).get("identity") or {}).get("platform_run_id") or "")).strip()
    blockers: list[str] = []
    notes: list[str] = []

    if summary is None or manifest is None:
        blockers.append("PR3.S5.SOAK.B01_WINDOW_NOT_EXECUTED")
        scorecard = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "window_label": "soak",
            "overall_pass": False,
            "blocker_ids": blockers,
        }
        receipt = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "verdict": "HOLD_REMEDIATE",
            "open_blockers": len(blockers),
            "blocker_ids": blockers,
        }
        dump_json(root / "g3a_scorecard_soak.json", scorecard)
        dump_json(root / "g3a_soak_drift_report.json", {"blocker_ids": blockers})
        dump_json(root / "g3a_soak_execution_receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
        return

    selected = select_snapshots(snapshots, platform_run_id)
    pre = latest_snapshot(selected, "soak_pre")
    post = latest_snapshot(selected, "soak_post")

    observed = dict(summary.get("observed") or {})
    admitted_eps = float(observed.get("observed_admitted_eps", 0.0) or 0.0)
    admitted_total = float(observed.get("admitted_request_count", 0.0) or 0.0)
    error_rate = float(observed.get("error_rate_ratio", 0.0) or 0.0)
    error_4xx = float(observed.get("4xx_rate_ratio", 0.0) or 0.0)
    error_5xx = float(observed.get("5xx_rate_ratio", 0.0) or 0.0)
    p95 = to_float(observed.get("latency_p95_ms"))
    p99 = to_float(observed.get("latency_p99_ms"))

    if admitted_eps < args.expected_soak_eps:
        blockers.append(f"PR3.S5.SOAK.B02_THROUGHPUT_SHORTFALL:observed={admitted_eps:.3f}:target={args.expected_soak_eps:.3f}")
    if admitted_total < args.min_processed_events:
        blockers.append(f"PR3.S5.SOAK.B03_SAMPLE_MINIMA_SHORTFALL:observed={admitted_total:.0f}:required={args.min_processed_events:.0f}")
    if error_rate > args.max_error_rate_ratio:
        blockers.append(f"PR3.S5.SOAK.B04_ERROR_RATE_BREACH:observed={error_rate:.6f}:max={args.max_error_rate_ratio:.6f}")
    if error_4xx > args.max_4xx_ratio:
        blockers.append(f"PR3.S5.SOAK.B05_4XX_BREACH:observed={error_4xx:.6f}:max={args.max_4xx_ratio:.6f}")
    if error_5xx > args.max_5xx_ratio:
        blockers.append(f"PR3.S5.SOAK.B06_5XX_BREACH:observed={error_5xx:.6f}:max={args.max_5xx_ratio:.6f}")
    if p95 is None or p95 > args.max_latency_p95_ms:
        blockers.append(f"PR3.S5.SOAK.B07_P95_LATENCY_BREACH:observed={p95}:max={args.max_latency_p95_ms:.3f}")
    if p99 is None or p99 > args.max_latency_p99_ms:
        blockers.append(f"PR3.S5.SOAK.B08_P99_LATENCY_BREACH:observed={p99}:max={args.max_latency_p99_ms:.3f}")

    for component in ("csfb", "ieg", "ofp", "dl", "df", "al", "dla", "archive_writer", "case_trigger", "case_mgmt", "label_store"):
        if is_missing(post, component):
            blockers.append(f"PR3.S5.SOAK.B09_COMPONENT_SURFACE_MISSING:{component}")
            continue
        state = health_state(post, component).upper()
        if state in {"RED", "FAILED", "UNHEALTHY", "AMBER"} and not replay_advisory_only(
            post, component, args.max_checkpoint_p99_seconds, args.max_lag_p99_seconds
        ):
            blockers.append(f"PR3.S5.SOAK.B10_COMPONENT_HEALTH_RED:{component}:{state}")

    metrics = {
        "df_hard_fail_closed_delta": delta(pre, post, "df", "hard_fail_closed_total")
        if summary_value(post, "df", "hard_fail_closed_total") is not None
        else delta(pre, post, "df", "fail_closed_total"),
        "df_publish_quarantine_delta": delta(pre, post, "df", "publish_quarantine_total"),
        "al_publish_quarantine_delta": delta(pre, post, "al", "publish_quarantine_total"),
        "al_publish_ambiguous_delta": delta(pre, post, "al", "publish_ambiguous_total"),
        "dla_append_failure_delta": delta(pre, post, "dla", "append_failure_total"),
        "dla_replay_divergence_delta": delta(pre, post, "dla", "replay_divergence_total"),
        "archive_write_error_delta": delta(pre, post, "archive_writer", "write_error_total"),
        "archive_payload_mismatch_delta": delta(pre, post, "archive_writer", "payload_mismatch_total"),
        "case_trigger_delta": delta(pre, post, "case_trigger", "triggers_seen"),
        "cases_created_delta": delta(pre, post, "case_mgmt", "cases_created"),
        "labels_accepted_delta": delta(pre, post, "label_store", "accepted"),
        "labels_rejected_delta": delta(pre, post, "label_store", "rejected"),
    }
    for key in (
        "df_hard_fail_closed_delta",
        "df_publish_quarantine_delta",
        "al_publish_quarantine_delta",
        "al_publish_ambiguous_delta",
        "dla_append_failure_delta",
        "dla_replay_divergence_delta",
        "archive_write_error_delta",
        "archive_payload_mismatch_delta",
    ):
        if (metrics[key] or 0.0) > 0.0:
            blockers.append(f"PR3.S5.SOAK.B11_INTEGRITY_NONZERO:{key}:delta={metrics[key]}")
    if (metrics["labels_rejected_delta"] or 0.0) > 0.0:
        blockers.append(f"PR3.S5.SOAK.B12_LABEL_REJECTED_NONZERO:delta={metrics['labels_rejected_delta']}")

    eps_bins = [to_float(row.get("observed_admitted_eps")) or 0.0 for row in ingress_bins]
    if eps_bins:
        split = max(1, len(eps_bins) // 2)
        early_avg = sum(eps_bins[:split]) / float(len(eps_bins[:split]))
        late_avg = sum(eps_bins[split:]) / float(len(eps_bins[split:]))
        if early_avg > 0.0 and late_avg < early_avg * 0.90:
            blockers.append(f"PR3.S5.SOAK.B13_DRIFT_BREACH:early_avg={early_avg:.3f}:late_avg={late_avg:.3f}")
    else:
        blockers.append("PR3.S5.SOAK.B13_DRIFT_BREACH:ingress_bins_missing")

    lag_series = [
        summary_value(snap, "ofp", "lag_seconds")
        for snap in selected
        if summary_value(snap, "ofp", "lag_seconds") is not None
    ]
    checkpoint_series = [
        max(
            summary_value(snap, "ofp", "checkpoint_age_seconds") or 0.0,
            summary_value(snap, "ieg", "checkpoint_age_seconds") or 0.0,
            summary_value(snap, "dla", "checkpoint_age_seconds") or 0.0,
        )
        for snap in selected
    ]
    lag_p99 = percentile(lag_series, 0.99)
    checkpoint_p99 = percentile(checkpoint_series, 0.99)
    if lag_p99 is not None and lag_p99 > args.max_lag_p99_seconds:
        blockers.append(f"PR3.S5.SOAK.B14_LAG_P99_BREACH:observed={lag_p99}:max={args.max_lag_p99_seconds}")
    if checkpoint_p99 is not None and checkpoint_p99 > args.max_checkpoint_p99_seconds:
        blockers.append(f"PR3.S5.SOAK.B15_CHECKPOINT_P99_BREACH:observed={checkpoint_p99}:max={args.max_checkpoint_p99_seconds}")
    if not bool(cost_receipt.get("overall_pass")):
        blockers.append("PR3.S5.SOAK.B16_COST_OR_IDLESAFE_RED")

    if len(blockers) == 0:
        notes.append("Conditional soak held throughput, latency, integrity, and drift posture inside the pinned envelope.")
    else:
        notes.append("Conditional soak is red and cannot be claimed in the pack verdict.")

    scorecard = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "window_label": "soak",
        "ingress": {
            "observed_admitted_eps": admitted_eps,
            "admitted_request_count": admitted_total,
            "error_rate_ratio": error_rate,
            "4xx_rate_ratio": error_4xx,
            "5xx_rate_ratio": error_5xx,
            "latency_p95_ms": p95,
            "latency_p99_ms": p99,
            "covered_metric_seconds": ((summary.get("performance_window") or {}).get("covered_metric_seconds")),
        },
        "component_deltas": metrics,
        "runtime_freshness": {"lag_p99": lag_p99, "checkpoint_p99": checkpoint_p99},
        "overall_pass": len(blockers) == 0,
        "blocker_ids": blockers,
        "notes": notes,
    }
    drift_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "lag_p99": lag_p99,
        "checkpoint_p99": checkpoint_p99,
        "ingress_bin_count": len(eps_bins),
        "overall_pass": not any("DRIFT_BREACH" in item for item in blockers),
        "blocker_ids": [item for item in blockers if "DRIFT_BREACH" in item],
    }
    receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PR3_S5_SOAK_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
    }

    dump_json(root / "g3a_scorecard_soak.json", scorecard)
    dump_json(root / "g3a_soak_drift_report.json", drift_report)
    dump_json(root / "g3a_soak_execution_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
