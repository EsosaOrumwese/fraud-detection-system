#!/usr/bin/env python3
"""Synthesize PR3-S2 burst/backpressure evidence from ingress and runtime snapshots."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    bounded = min(max(float(q), 0.0), 1.0)
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(math.ceil(len(ordered) * bounded)) - 1))
    return float(ordered[idx])


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_series(values: list[float]) -> dict[str, float | None]:
    return {
        "count": float(len(values)),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
        "min": min(values) if values else None,
    }


def snap_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


def health_state(snapshot: dict[str, Any], component: str) -> str:
    return str((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_state") or "UNKNOWN")


def snapshot_platform_run_id(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("platform_run_id", "")).strip()


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    for row in snapshots:
        if str(row.get("snapshot_label", "")).strip().lower() == label:
            return row
    return snapshots[-1]


def snapshot_generated_at(snapshot: dict[str, Any]) -> datetime | None:
    return parse_utc(snapshot.get("generated_at_utc"))


def select_counter_window_bounds(
    snapshots: list[dict[str, Any]],
    *,
    measurement_start_utc: datetime | None,
    measurement_end_utc: datetime | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not snapshots:
        raise RuntimeError("PR3.S2.B12_COMPONENT_SNAPSHOTS_MISSING")

    ordered = sorted(
        [row for row in snapshots if snapshot_generated_at(row) is not None],
        key=lambda row: snapshot_generated_at(row) or datetime.min.replace(tzinfo=timezone.utc),
    )
    if not ordered:
        raise RuntimeError("PR3.S2.B12_COMPONENT_SNAPSHOT_TIMESTAMPS_UNREADABLE")

    baseline = ordered[0]
    baseline_mode = "earliest_available"
    if measurement_start_utc is not None:
        at_or_before_start = [row for row in ordered if (snapshot_generated_at(row) or measurement_start_utc) <= measurement_start_utc]
        if at_or_before_start:
            baseline = at_or_before_start[-1]
            baseline_mode = "latest_at_or_before_measurement_start"
        else:
            at_or_after_start = [row for row in ordered if (snapshot_generated_at(row) or measurement_start_utc) >= measurement_start_utc]
            if at_or_after_start:
                baseline = at_or_after_start[0]
                baseline_mode = "earliest_at_or_after_measurement_start"

    window_end = ordered[-1]
    window_end_mode = "latest_available"
    if measurement_end_utc is not None:
        at_or_before_end = [row for row in ordered if (snapshot_generated_at(row) or measurement_end_utc) <= measurement_end_utc]
        if at_or_before_end:
            window_end = at_or_before_end[-1]
            window_end_mode = "latest_at_or_before_measurement_end"
        else:
            at_or_after_end = [row for row in ordered if (snapshot_generated_at(row) or measurement_end_utc) >= measurement_end_utc]
            if at_or_after_end:
                window_end = at_or_after_end[0]
                window_end_mode = "earliest_at_or_after_measurement_end"

    baseline_ts = snapshot_generated_at(baseline)
    end_ts = snapshot_generated_at(window_end)
    meta = {
        "baseline_snapshot_label": baseline.get("snapshot_label"),
        "baseline_snapshot_generated_at_utc": baseline.get("generated_at_utc"),
        "baseline_selection_mode": baseline_mode,
        "window_end_snapshot_label": window_end.get("snapshot_label"),
        "window_end_snapshot_generated_at_utc": window_end.get("generated_at_utc"),
        "window_end_selection_mode": window_end_mode,
        "measurement_start_utc": measurement_start_utc.isoformat().replace("+00:00", "Z") if measurement_start_utc else None,
        "measurement_end_utc": measurement_end_utc.isoformat().replace("+00:00", "Z") if measurement_end_utc else None,
        "baseline_gap_seconds_from_measurement_start": (
            abs((measurement_start_utc - baseline_ts).total_seconds()) if measurement_start_utc and baseline_ts else None
        ),
        "window_end_gap_seconds_from_measurement_end": (
            abs((measurement_end_utc - end_ts).total_seconds()) if measurement_end_utc and end_ts else None
        ),
    }
    return baseline, window_end, meta


def payload_missing(snapshot: dict[str, Any], component: str, payload_kind: str) -> bool:
    payload = ((((snapshot.get("components") or {}).get(component) or {}).get(f"{payload_kind}_payload")) or {})
    return bool(payload.get("__missing__")) or bool(payload.get("__unreadable__"))


def counter_delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = snap_value(pre, component, field)
    end = snap_value(post, component, field)
    if end is None:
        return None
    if start is None and payload_missing(pre, component, "metrics"):
        start = 0.0
    if start is None:
        return None
    return end - start


def select_attempt_snapshots(
    snapshots: list[dict[str, Any]],
    *,
    expected_platform_run_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = str(expected_platform_run_id).strip()
    if not expected:
        raise RuntimeError("PR3.S2.B12_PLATFORM_RUN_ID_MISSING")

    selected = [row for row in snapshots if snapshot_platform_run_id(row) == expected]
    observed_other = sorted({snapshot_platform_run_id(row) for row in snapshots if snapshot_platform_run_id(row) and snapshot_platform_run_id(row) != expected})
    labels = [str(row.get("snapshot_label", "")).strip().lower() for row in selected]
    meta = {
        "expected_platform_run_id": expected,
        "selected_count": len(selected),
        "excluded_snapshot_count": len(snapshots) - len(selected),
        "excluded_platform_run_ids": observed_other,
        "labels": labels,
    }
    if not selected:
        raise RuntimeError(f"PR3.S2.B12_COMPONENT_SNAPSHOTS_MISSING:platform_run_id={expected}")
    if "pre" not in labels:
        raise RuntimeError(f"PR3.S2.B12_COMPONENT_SNAPSHOT_PRE_MISSING:platform_run_id={expected}")
    if "post" not in labels:
        raise RuntimeError(f"PR3.S2.B12_COMPONENT_SNAPSHOT_POST_MISSING:platform_run_id={expected}")
    return selected, meta


def main() -> None:
    ap = argparse.ArgumentParser(description="Build PR3-S2 burst/backpressure rollup.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S2")
    ap.add_argument("--artifact-prefix", default="g3a_s2")
    ap.add_argument("--expected-burst-eps", type=float, default=6000.0)
    ap.add_argument("--max-error-rate-ratio", type=float, default=0.002)
    ap.add_argument("--max-4xx-ratio", type=float, default=0.002)
    ap.add_argument("--max-5xx-ratio", type=float, default=0.0)
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    summary = load_json(root / f"{args.artifact_prefix}_wsp_runtime_summary.json")
    manifest = load_json(root / f"{args.artifact_prefix}_wsp_runtime_manifest.json")
    all_snapshots = sorted(
        [load_json(path) for path in root.glob(f"g3a_{str(args.state_id).strip().lower()}_component_snapshot_*.json")],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )
    if not all_snapshots:
        raise RuntimeError(f"PR3.{args.state_id}.B12_COMPONENT_SNAPSHOTS_MISSING")
    manifest_platform_run_id = str((((manifest.get("identity") or {}).get("platform_run_id")) or "")).strip()
    snapshots, attempt_scope = select_attempt_snapshots(
        all_snapshots,
        expected_platform_run_id=manifest_platform_run_id,
    )

    blockers: list[str] = []
    ingress = dict(summary.get("observed", {}) or {})
    performance_window = dict(summary.get("performance_window", {}) or {})
    measurement_start_utc = parse_utc(performance_window.get("measurement_start_utc"))
    measurement_end_utc = parse_utc(
        performance_window.get("measurement_target_end_utc") or performance_window.get("metric_effective_end_utc")
    )
    admitted_eps = float(ingress.get("observed_admitted_eps", 0.0) or 0.0)
    error_rate = float(ingress.get("error_rate_ratio", 1.0) or 0.0)
    error_4xx = float(ingress.get("4xx_rate_ratio", 1.0) or 0.0)
    error_5xx = float(ingress.get("5xx_rate_ratio", 1.0) or 0.0)
    latency_p95 = to_float(ingress.get("latency_p95_ms"))
    latency_p99 = to_float(ingress.get("latency_p99_ms"))

    if admitted_eps < float(args.expected_burst_eps):
        blockers.append(f"PR3.{args.state_id}.B14_BURST_THROUGHPUT_SHORTFALL:observed={admitted_eps:.3f}:target={float(args.expected_burst_eps):.3f}")
    if error_rate > float(args.max_error_rate_ratio):
        blockers.append(f"PR3.{args.state_id}.B14_BURST_ERROR_RATE_BREACH:observed={error_rate:.6f}:max={float(args.max_error_rate_ratio):.6f}")
    if error_4xx > float(args.max_4xx_ratio):
        blockers.append(f"PR3.{args.state_id}.B14_BURST_4XX_BREACH:observed={error_4xx:.6f}:max={float(args.max_4xx_ratio):.6f}")
    if error_5xx > float(args.max_5xx_ratio):
        blockers.append(f"PR3.{args.state_id}.B14_BURST_5XX_BREACH:observed={error_5xx:.6f}:max={float(args.max_5xx_ratio):.6f}")
    if latency_p95 is None or latency_p95 > float(args.max_latency_p95_ms):
        blockers.append(f"PR3.{args.state_id}.B14_BURST_P95_LATENCY_BREACH:observed={latency_p95}:max={float(args.max_latency_p95_ms):.3f}")
    if latency_p99 is None or latency_p99 > float(args.max_latency_p99_ms):
        blockers.append(f"PR3.{args.state_id}.B14_BURST_P99_LATENCY_BREACH:observed={latency_p99}:max={float(args.max_latency_p99_ms):.3f}")

    pre = latest_snapshot(snapshots, "pre")
    post = latest_snapshot(snapshots, "post")
    window_counter_start, window_counter_end, counter_window_meta = select_counter_window_bounds(
        snapshots,
        measurement_start_utc=measurement_start_utc,
        measurement_end_utc=measurement_end_utc,
    )
    series_defs = {
        "ieg.backpressure_hits": ("ieg", "backpressure_hits"),
        "ieg.checkpoint_age_seconds": ("ieg", "checkpoint_age_seconds"),
        "ieg.watermark_age_seconds": ("ieg", "watermark_age_seconds"),
        "ofp.lag_seconds": ("ofp", "lag_seconds"),
        "ofp.checkpoint_age_seconds": ("ofp", "checkpoint_age_seconds"),
        "ofp.watermark_age_seconds": ("ofp", "watermark_age_seconds"),
        "ofp.missing_features": ("ofp", "missing_features"),
        "ofp.snapshot_failures": ("ofp", "snapshot_failures"),
        "df.publish_quarantine_total": ("df", "publish_quarantine_total"),
        "df.fail_closed_total": ("df", "fail_closed_total"),
        "al.publish_quarantine_total": ("al", "publish_quarantine_total"),
        "al.publish_ambiguous_total": ("al", "publish_ambiguous_total"),
        "al.queue_depth": ("al", "queue_depth"),
        "al.lag_events": ("al", "lag_events"),
        "dla.checkpoint_age_seconds": ("dla", "checkpoint_age_seconds"),
        "dla.quarantine_total": ("dla", "quarantine_total"),
        "dla.append_failure_total": ("dla", "append_failure_total"),
        "dla.replay_divergence_total": ("dla", "replay_divergence_total"),
        "archive.backlog_events": ("archive_writer", "backlog_events"),
        "archive.write_error_total": ("archive_writer", "write_error_total"),
        "archive.payload_mismatch_total": ("archive_writer", "payload_mismatch_total"),
        "archive.archived_total": ("archive_writer", "archived_total"),
        "archive.seen_total": ("archive_writer", "seen_total"),
    }
    time_series: dict[str, dict[str, Any]] = {}
    for metric_id, (component, field) in series_defs.items():
        values = [snap_value(snapshot, component, field) for snapshot in snapshots]
        numeric = [float(v) for v in values if v is not None]
        time_series[metric_id] = {
            "series": [
                {
                    "snapshot_label": snap.get("snapshot_label"),
                    "generated_at_utc": snap.get("generated_at_utc"),
                    "value": snap_value(snap, component, field),
                }
                for snap in snapshots
            ],
            "summary": summarize_series(numeric),
        }

    for component in ("ieg", "ofp", "df", "al", "dla", "archive_writer"):
        if payload_missing(post, component, "metrics") or payload_missing(post, component, "health"):
            blockers.append(f"PR3.{args.state_id}.B15_COMPONENT_SURFACE_MISSING:{component}")

    for metric_id, max_allowed in [
        ("ieg.checkpoint_age_seconds", 300.0),
        ("ofp.lag_seconds", 300.0),
        ("ofp.checkpoint_age_seconds", 300.0),
        ("dla.checkpoint_age_seconds", 300.0),
    ]:
        observed = time_series[metric_id]["summary"]["max"]
        if observed is None or float(observed) > max_allowed:
            blockers.append(f"PR3.{args.state_id}.B15_BACKPRESSURE_POSTURE_UNPROVEN:{metric_id}:observed={observed}:max={max_allowed}")

    def delta(component: str, field: str) -> float | None:
        return counter_delta(window_counter_start, window_counter_end, component, field)

    ieg_apply_failure_delta = delta("ieg", "apply_failure_count")
    if ieg_apply_failure_delta is None or ieg_apply_failure_delta > 0:
        blockers.append(f"PR3.{args.state_id}.B15_IEG_APPLY_FAILURE_NONZERO:delta={ieg_apply_failure_delta}")

    ieg_backpressure_delta = delta("ieg", "backpressure_hits")
    if ieg_backpressure_delta is None:
        blockers.append(f"PR3.{args.state_id}.B15_BACKPRESSURE_POSTURE_UNPROVEN:ieg_backpressure_delta_unreadable")
    elif ieg_backpressure_delta > 0:
        blockers.append(f"PR3.{args.state_id}.B15_BACKPRESSURE_POSTURE_UNPROVEN:ieg_backpressure_delta={ieg_backpressure_delta:.0f}:max=0")

    for component, field, code in [
        ("df", "publish_quarantine_total", "PR3.{state}.B15_DF_QUARANTINE_NONZERO"),
        ("df", "fail_closed_total", "PR3.{state}.B15_DF_FAIL_CLOSED_NONZERO"),
        ("al", "publish_quarantine_total", "PR3.{state}.B15_AL_QUARANTINE_NONZERO"),
        ("al", "publish_ambiguous_total", "PR3.{state}.B15_AL_AMBIGUOUS_NONZERO"),
        ("dla", "append_failure_total", "PR3.{state}.B15_DLA_APPEND_FAILURE_NONZERO"),
        ("dla", "replay_divergence_total", "PR3.{state}.B15_DLA_REPLAY_DIVERGENCE_NONZERO"),
        ("archive_writer", "write_error_total", "PR3.{state}.B16_ARCHIVE_SINK_BACKPRESSURE_FAIL"),
        ("archive_writer", "payload_mismatch_total", "PR3.{state}.B16_ARCHIVE_SINK_PAYLOAD_MISMATCH"),
    ]:
        value = delta(component, field)
        if value is None or value > 0:
            blockers.append(code.format(state=args.state_id) + f":delta={value}")

    archived_delta = delta("archive_writer", "archived_total")
    if archived_delta is None or archived_delta <= 0:
        blockers.append(f"PR3.{args.state_id}.B16_ARCHIVE_SINK_BACKPRESSURE_FAIL:archived_total_delta={archived_delta}")

    archive_peak = time_series["archive.backlog_events"]["summary"]["max"]
    archive_final = snap_value(post, "archive_writer", "backlog_events")

    scorecard = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "scenario_run_id": str((((manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip(),
        "window_label": "burst",
        "runtime_path_active": "CANONICAL_REMOTE_WSP_REPLAY",
        "attempt_scope": attempt_scope,
        "counter_window": counter_window_meta,
        "campaign": manifest.get("campaign", {}),
        "ingress": {
            "measurement_surface_mode": (((summary.get("notes") or {}).get("ingress_metric_surface") or {}).get("mode")),
            "observed_admitted_eps": admitted_eps,
            "request_count_total": ingress.get("request_count_total"),
            "admitted_request_count": ingress.get("admitted_request_count"),
            "4xx_total": ingress.get("4xx_total"),
            "5xx_total": ingress.get("5xx_total"),
            "error_rate_ratio": error_rate,
            "4xx_rate_ratio": error_4xx,
            "5xx_rate_ratio": error_5xx,
            "latency_p95_ms": latency_p95,
            "latency_p99_ms": latency_p99,
            "covered_metric_seconds": ((summary.get("performance_window") or {}).get("covered_metric_seconds")),
        },
        "thresholds": {
            "expected_burst_eps": args.expected_burst_eps,
            "max_error_rate_ratio": args.max_error_rate_ratio,
            "max_4xx_ratio": args.max_4xx_ratio,
            "max_5xx_ratio": args.max_5xx_ratio,
            "max_latency_p95_ms": args.max_latency_p95_ms,
            "max_latency_p99_ms": args.max_latency_p99_ms,
        },
        "overall_pass": len(blockers) == 0,
        "blocker_ids": sorted(set(blockers)),
    }

    component_health = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "scenario_run_id": str((((manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip(),
        "sample_count": len(snapshots),
        "attempt_scope": attempt_scope,
        "counter_window": counter_window_meta,
        "components": {
            component: {
                "states": [health_state(snapshot, component) for snapshot in snapshots],
                "latest_summary": (((post.get("components") or {}).get(component) or {}).get("summary") or {}),
                "latest_threshold_defaults": (((post.get("components") or {}).get(component) or {}).get("threshold_defaults") or {}),
            }
            for component in ("ieg", "ofp", "df", "al", "dla", "archive_writer")
        },
        "time_series": time_series,
    }

    backpressure_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "counter_window": counter_window_meta,
        "ieg_backpressure_delta": ieg_backpressure_delta,
        "ieg_apply_failure_count_delta": ieg_apply_failure_delta,
        "ofp_lag_seconds": time_series["ofp.lag_seconds"]["summary"],
        "ofp_checkpoint_age_seconds": time_series["ofp.checkpoint_age_seconds"]["summary"],
        "ieg_checkpoint_age_seconds": time_series["ieg.checkpoint_age_seconds"]["summary"],
        "dla_checkpoint_age_seconds": time_series["dla.checkpoint_age_seconds"]["summary"],
        "df_publish_quarantine_total_delta": delta("df", "publish_quarantine_total"),
        "df_fail_closed_total_delta": delta("df", "fail_closed_total"),
        "al_publish_quarantine_total_delta": delta("al", "publish_quarantine_total"),
        "al_publish_ambiguous_total_delta": delta("al", "publish_ambiguous_total"),
        "overall_pass": not any("B15" in item for item in blockers),
        "blocker_ids": [item for item in sorted(set(blockers)) if "B15" in item],
    }

    archive_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "counter_window": counter_window_meta,
        "archive_backlog_peak_events": archive_peak,
        "archive_backlog_final_events": archive_final,
        "archive_write_error_total_delta": delta("archive_writer", "write_error_total"),
        "archive_payload_mismatch_total_delta": delta("archive_writer", "payload_mismatch_total"),
        "archive_archived_total_delta": archived_delta,
        "archive_seen_total_delta": delta("archive_writer", "seen_total"),
        "overall_pass": not any("B16" in item for item in blockers),
        "blocker_ids": [item for item in sorted(set(blockers)) if "B16" in item],
    }

    receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "scenario_run_id": str((((manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip(),
        "verdict": f"PR3_{args.state_id}_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S3" if len(blockers) == 0 else "PR3-S2",
        "open_blockers": len(set(blockers)),
        "blocker_ids": sorted(set(blockers)),
        "attempt_scope": attempt_scope,
        "counter_window": counter_window_meta,
        "evidence_refs": {
            "scorecard_ref": str(root / "g3a_scorecard_burst.json"),
            "component_health_ref": str(root / "g3a_component_health_burst.json"),
            "backpressure_ref": str(root / "g3a_burst_backpressure_report.json"),
            "archive_ref": str(root / "g3a_archive_sink_backpressure_report.json"),
        },
    }

    dump_json(root / "g3a_scorecard_burst.json", scorecard)
    dump_json(root / "g3a_component_health_burst.json", component_health)
    dump_json(root / "g3a_burst_backpressure_report.json", backpressure_report)
    dump_json(root / "g3a_archive_sink_backpressure_report.json", archive_report)
    dump_json(root / "pr3_s2_execution_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
