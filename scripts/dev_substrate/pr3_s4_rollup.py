#!/usr/bin/env python3
"""Build PR3-S4 soak/drill evidence from runtime soak artifacts."""

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


def summarize_series(values: list[float]) -> dict[str, float | None]:
    return {
        "count": float(len(values)),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def snapshot_generated_at(snapshot: dict[str, Any]) -> datetime | None:
    return parse_utc(snapshot.get("generated_at_utc"))


def snapshot_platform_run_id(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("platform_run_id", "")).strip()


def health_state(snapshot: dict[str, Any], component: str) -> str:
    return str((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_state") or "UNKNOWN")


def health_reasons(snapshot: dict[str, Any], component: str) -> list[str]:
    raw = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_reasons"))
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def snap_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


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
    return float(end - start)


def replay_health_is_advisory_only(
    snapshot: dict[str, Any],
    *,
    component: str,
    max_checkpoint_p99_seconds: float,
    max_lag_p99_seconds: float,
) -> bool:
    if component not in {"ieg", "ofp"}:
        return False
    state = health_state(snapshot, component).upper()
    reasons = set(health_reasons(snapshot, component))
    if state not in {"RED", "FAILED", "UNHEALTHY"}:
        return False
    if reasons != {"WATERMARK_TOO_OLD"}:
        return False
    checkpoint_age = snap_value(snapshot, component, "checkpoint_age_seconds")
    if checkpoint_age is None or checkpoint_age > max_checkpoint_p99_seconds:
        return False
    if component == "ofp":
        lag_seconds = snap_value(snapshot, component, "lag_seconds")
        if lag_seconds is None or lag_seconds > max_lag_p99_seconds:
            return False
    if component == "ieg":
        apply_failures = snap_value(snapshot, component, "apply_failure_count")
        backpressure_hits = snap_value(snapshot, component, "backpressure_hits")
        if (apply_failures or 0.0) > 0.0:
            return False
        if (backpressure_hits or 0.0) > 0.0:
            return False
    return True


def select_attempt_snapshots(snapshots: list[dict[str, Any]], *, expected_platform_run_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = str(expected_platform_run_id).strip()
    if not expected:
        raise RuntimeError("PR3.S4.B21_PLATFORM_RUN_ID_MISSING")
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
        raise RuntimeError(f"PR3.S4.B21_COMPONENT_SNAPSHOTS_MISSING:platform_run_id={expected}")
    if "pre" not in labels:
        raise RuntimeError(f"PR3.S4.B21_COMPONENT_SNAPSHOT_PRE_MISSING:platform_run_id={expected}")
    if "post" not in labels:
        raise RuntimeError(f"PR3.S4.B21_COMPONENT_SNAPSHOT_POST_MISSING:platform_run_id={expected}")
    return selected, meta


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    for row in snapshots:
        if str(row.get("snapshot_label", "")).strip().lower() == label:
            return row
    return snapshots[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description="Build PR3-S4 soak rollup and drill bundle.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S4")
    ap.add_argument("--artifact-prefix", default="g3a_s4")
    ap.add_argument("--expected-soak-eps", type=float, default=3000.0)
    ap.add_argument("--min-processed-events", type=float, default=5400000.0)
    ap.add_argument("--max-error-rate-ratio", type=float, default=0.002)
    ap.add_argument("--max-4xx-ratio", type=float, default=0.002)
    ap.add_argument("--max-5xx-ratio", type=float, default=0.0)
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--max-lag-p99-seconds", type=float, default=5.0)
    ap.add_argument("--max-checkpoint-p99-seconds", type=float, default=30.0)
    ap.add_argument("--budget-envelope-usd", type=float, default=250.0)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    summary = load_json(root / f"{args.artifact_prefix}_wsp_runtime_summary.json")
    manifest = load_json(root / f"{args.artifact_prefix}_wsp_runtime_manifest.json")
    ingress_bins_payload = load_json(root / f"{args.artifact_prefix}_ingress_bins.json")
    ingress_bins = list(ingress_bins_payload.get("bins", []))
    charter = load_json(root / "g3a_run_charter.active.json")
    all_snapshots = sorted(
        [load_json(path) for path in root.glob(f"g3a_{str(args.state_id).strip().lower()}_component_snapshot_*.json")],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )
    if not all_snapshots:
        raise RuntimeError("PR3.S4.B21_COMPONENT_SNAPSHOTS_MISSING")
    manifest_platform_run_id = str((((manifest.get("identity") or {}).get("platform_run_id")) or "")).strip()
    snapshots, attempt_scope = select_attempt_snapshots(all_snapshots, expected_platform_run_id=manifest_platform_run_id)

    blockers: list[str] = []
    notes: list[str] = []

    observed = dict(summary.get("observed", {}) or {})
    performance_window = dict(summary.get("performance_window", {}) or {})
    admitted_eps = float(observed.get("observed_admitted_eps", 0.0) or 0.0)
    error_rate = float(observed.get("error_rate_ratio", 1.0) or 0.0)
    error_4xx = float(observed.get("4xx_rate_ratio", 1.0) or 0.0)
    error_5xx = float(observed.get("5xx_rate_ratio", 1.0) or 0.0)
    latency_p95 = to_float(observed.get("latency_p95_ms"))
    latency_p99 = to_float(observed.get("latency_p99_ms"))
    admitted_total = float(observed.get("admitted_request_count", 0.0) or 0.0)

    if admitted_eps < float(args.expected_soak_eps):
        blockers.append(f"PR3.S4.B22_SOAK_THROUGHPUT_SHORTFALL:observed={admitted_eps:.3f}:target={float(args.expected_soak_eps):.3f}")
    if admitted_total < float(args.min_processed_events):
        blockers.append(f"PR3.S4.B22_SOAK_SAMPLE_MINIMA_SHORTFALL:observed={admitted_total:.0f}:required={float(args.min_processed_events):.0f}")
    if error_rate > float(args.max_error_rate_ratio):
        blockers.append(f"PR3.S4.B22_SOAK_ERROR_RATE_BREACH:observed={error_rate:.6f}:max={float(args.max_error_rate_ratio):.6f}")
    if error_4xx > float(args.max_4xx_ratio):
        blockers.append(f"PR3.S4.B22_SOAK_4XX_BREACH:observed={error_4xx:.6f}:max={float(args.max_4xx_ratio):.6f}")
    if error_5xx > float(args.max_5xx_ratio):
        blockers.append(f"PR3.S4.B22_SOAK_5XX_BREACH:observed={error_5xx:.6f}:max={float(args.max_5xx_ratio):.6f}")
    if latency_p95 is None or latency_p95 > float(args.max_latency_p95_ms):
        blockers.append(f"PR3.S4.B22_SOAK_P95_LATENCY_BREACH:observed={latency_p95}:max={float(args.max_latency_p95_ms):.3f}")
    if latency_p99 is None or latency_p99 > float(args.max_latency_p99_ms):
        blockers.append(f"PR3.S4.B22_SOAK_P99_LATENCY_BREACH:observed={latency_p99}:max={float(args.max_latency_p99_ms):.3f}")

    pre = latest_snapshot(snapshots, "pre")
    post = latest_snapshot(snapshots, "post")
    series_defs = {
        "ofp.lag_seconds": ("ofp", "lag_seconds"),
        "ofp.checkpoint_age_seconds": ("ofp", "checkpoint_age_seconds"),
        "ieg.checkpoint_age_seconds": ("ieg", "checkpoint_age_seconds"),
        "dla.checkpoint_age_seconds": ("dla", "checkpoint_age_seconds"),
        "archive.backlog_events": ("archive_writer", "backlog_events"),
        "df.fail_closed_total": ("df", "fail_closed_total"),
        "df.publish_quarantine_total": ("df", "publish_quarantine_total"),
        "al.publish_quarantine_total": ("al", "publish_quarantine_total"),
        "al.publish_ambiguous_total": ("al", "publish_ambiguous_total"),
        "dla.append_failure_total": ("dla", "append_failure_total"),
        "dla.replay_divergence_total": ("dla", "replay_divergence_total"),
        "archive.write_error_total": ("archive_writer", "write_error_total"),
        "archive.payload_mismatch_total": ("archive_writer", "payload_mismatch_total"),
        "case_trigger.triggers_seen": ("case_trigger", "triggers_seen"),
        "case_trigger.publish_quarantine_total": ("case_trigger", "publish_quarantine_total"),
        "case_trigger.publish_ambiguous_total": ("case_trigger", "publish_ambiguous_total"),
        "case_trigger.replay_mismatch_total": ("case_trigger", "replay_mismatch_total"),
        "case_mgmt.case_triggers": ("case_mgmt", "case_triggers"),
        "case_mgmt.cases_created": ("case_mgmt", "cases_created"),
        "case_mgmt.payload_mismatches": ("case_mgmt", "payload_mismatches"),
        "label_store.pending": ("label_store", "pending"),
        "label_store.accepted": ("label_store", "accepted"),
        "label_store.rejected": ("label_store", "rejected"),
    }
    time_series: dict[str, dict[str, Any]] = {}
    for metric_id, (component, field) in series_defs.items():
        numeric = [float(v) for snap in snapshots if (v := snap_value(snap, component, field)) is not None]
        time_series[metric_id] = {
            "summary": summarize_series(numeric),
            "series": [
                {
                    "snapshot_label": snap.get("snapshot_label"),
                    "generated_at_utc": snap.get("generated_at_utc"),
                    "value": snap_value(snap, component, field),
                }
                for snap in snapshots
            ],
        }

    for component in ("ieg", "ofp", "df", "al", "dla", "archive_writer", "case_trigger", "case_mgmt", "label_store"):
        if payload_missing(post, component, "metrics") or payload_missing(post, component, "health"):
            blockers.append(f"PR3.S4.B21_COMPONENT_SURFACE_MISSING:{component}")
        state = health_state(post, component).upper()
        if state in {"RED", "FAILED", "UNHEALTHY"}:
            if replay_health_is_advisory_only(
                post,
                component=component,
                max_checkpoint_p99_seconds=float(args.max_checkpoint_p99_seconds),
                max_lag_p99_seconds=float(args.max_lag_p99_seconds),
            ):
                notes.append(
                    f"Replay advisory only for {component}: WATERMARK_TOO_OLD present while checkpoint/lag integrity remained within threshold."
                )
            else:
                blockers.append(f"PR3.S4.B22_COMPONENT_HEALTH_RED:{component}:{state}")

    if (time_series["ofp.lag_seconds"]["summary"]["p99"] or 0.0) > float(args.max_lag_p99_seconds):
        blockers.append(
            f"PR3.S4.B22_OFP_LAG_P99_BREACH:observed={time_series['ofp.lag_seconds']['summary']['p99']}:max={float(args.max_lag_p99_seconds):.3f}"
        )
    checkpoint_max = max(
        (time_series["ofp.checkpoint_age_seconds"]["summary"]["p99"] or 0.0),
        (time_series["ieg.checkpoint_age_seconds"]["summary"]["p99"] or 0.0),
        (time_series["dla.checkpoint_age_seconds"]["summary"]["p99"] or 0.0),
    )
    if checkpoint_max > float(args.max_checkpoint_p99_seconds):
        blockers.append(f"PR3.S4.B22_CHECKPOINT_P99_BREACH:observed={checkpoint_max}:max={float(args.max_checkpoint_p99_seconds):.3f}")

    df_decisions_delta = counter_delta(pre, post, "df", "decisions_total") or 0.0
    case_trigger_delta = counter_delta(pre, post, "case_trigger", "triggers_seen")
    case_created_delta = counter_delta(pre, post, "case_mgmt", "cases_created")
    label_accepted_delta = counter_delta(pre, post, "label_store", "accepted")
    if df_decisions_delta > 0 and (case_trigger_delta is None or case_trigger_delta <= 0):
        blockers.append(f"PR3.S4.B22_CASE_TRIGGER_UNEXERCISED:df_decisions_delta={df_decisions_delta}:case_trigger_delta={case_trigger_delta}")
    if (case_trigger_delta or 0.0) > 0 and (case_created_delta is None or case_created_delta <= 0):
        blockers.append(f"PR3.S4.B22_CASE_MGMT_UNEXERCISED:case_trigger_delta={case_trigger_delta}:cases_created_delta={case_created_delta}")
    if (case_created_delta or 0.0) > 0 and (label_accepted_delta is None or label_accepted_delta <= 0):
        blockers.append(f"PR3.S4.B22_LABEL_STORE_UNEXERCISED:cases_created_delta={case_created_delta}:labels_accepted_delta={label_accepted_delta}")

    for component, field, code in [
        ("df", "publish_quarantine_total", "PR3.S4.B24_REPLAY_INTEGRITY_DF_QUARANTINE_NONZERO"),
        ("df", "fail_closed_total", "PR3.S4.B24_REPLAY_INTEGRITY_DF_FAIL_CLOSED_NONZERO"),
        ("al", "publish_quarantine_total", "PR3.S4.B24_REPLAY_INTEGRITY_AL_QUARANTINE_NONZERO"),
        ("al", "publish_ambiguous_total", "PR3.S4.B24_REPLAY_INTEGRITY_AL_AMBIGUOUS_NONZERO"),
        ("dla", "append_failure_total", "PR3.S4.B24_REPLAY_INTEGRITY_DLA_APPEND_NONZERO"),
        ("dla", "replay_divergence_total", "PR3.S4.B24_REPLAY_INTEGRITY_DLA_DIVERGENCE_NONZERO"),
        ("archive_writer", "write_error_total", "PR3.S4.B24_REPLAY_INTEGRITY_ARCHIVE_WRITE_NONZERO"),
        ("archive_writer", "payload_mismatch_total", "PR3.S4.B24_REPLAY_INTEGRITY_ARCHIVE_PAYLOAD_NONZERO"),
        ("case_trigger", "replay_mismatch_total", "PR3.S4.B24_REPLAY_INTEGRITY_CASE_TRIGGER_MISMATCH_NONZERO"),
        ("case_trigger", "publish_quarantine_total", "PR3.S4.B24_REPLAY_INTEGRITY_CASE_TRIGGER_QUARANTINE_NONZERO"),
        ("case_trigger", "publish_ambiguous_total", "PR3.S4.B24_REPLAY_INTEGRITY_CASE_TRIGGER_AMBIGUOUS_NONZERO"),
        ("case_mgmt", "payload_mismatches", "PR3.S4.B24_REPLAY_INTEGRITY_CASE_MGMT_MISMATCH_NONZERO"),
        ("label_store", "rejected", "PR3.S4.B24_REPLAY_INTEGRITY_LABEL_REJECT_NONZERO"),
    ]:
        value = counter_delta(pre, post, component, field)
        if value is None or value > 0:
            blockers.append(f"{code}:delta={value}")

    eps_bins = [to_float(row.get("observed_admitted_eps")) or 0.0 for row in ingress_bins]
    if eps_bins:
        split = max(1, len(eps_bins) // 2)
        early = eps_bins[:split]
        late = eps_bins[split:]
        early_avg = sum(early) / float(len(early)) if early else 0.0
        late_avg = sum(late) / float(len(late)) if late else 0.0
        if early_avg > 0.0 and late_avg < (early_avg * 0.90):
            blockers.append(f"PR3.S4.B22_SOAK_DRIFT_BREACH:early_avg={early_avg:.3f}:late_avg={late_avg:.3f}")
    else:
        blockers.append("PR3.S4.B22_SOAK_DRIFT_BREACH:ingress_bins_missing")

    required_cohorts = list(charter.get("cohorts_required", []) or [])
    cohort_manifest = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "window_ref": "runs/dev_substrate/dev_full/road_to_prod/run_control/pr1_20260305T174744Z/pr1_g2_cohort_profile.json",
        "required_cohorts": required_cohorts,
        "overall_pass": len(required_cohorts) == 5,
        "notes": [
            "Runtime campaign uses the PR1-pinned realism window and cohort contract.",
            "Per-cohort runtime deltas are not yet separately isolated in the PR3 soak dispatcher.",
        ],
    }
    cohort_results = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "required_cohorts": required_cohorts,
        "observed_runtime_surface": {
            "observed_admitted_eps": admitted_eps,
            "error_rate_ratio": error_rate,
            "latency_p95_ms": latency_p95,
            "latency_p99_ms": latency_p99,
        },
        "overall_pass": False,
        "blocker_ids": ["PR3.S4.B23_REQUIRED_COHORT_DELTA_UNPROVEN"],
        "notes": [
            "G2 cohort coverage is pinned, but S4 does not yet have cohort-isolated runtime deltas.",
        ],
    }
    blockers.append("PR3.S4.B23_REQUIRED_COHORT_DELTA_UNPROVEN")

    replay_drill = {
        "drill_id": "replay_integrity",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "scenario": "duplicate/replay cohort observed during soak with duplicate-sensitive counters held at zero growth",
        "expected_behavior": "No duplicate side effects, no replay divergence, no case/label mismatch growth.",
        "observed_outcome": {
            "df_decisions_delta": df_decisions_delta,
            "case_trigger_delta": case_trigger_delta,
            "case_created_delta": case_created_delta,
            "label_accepted_delta": label_accepted_delta,
        },
        "integrity_checks": {
            "df_fail_closed_delta": counter_delta(pre, post, "df", "fail_closed_total"),
            "al_publish_ambiguous_delta": counter_delta(pre, post, "al", "publish_ambiguous_total"),
            "dla_replay_divergence_delta": counter_delta(pre, post, "dla", "replay_divergence_total"),
            "case_trigger_replay_mismatch_delta": counter_delta(pre, post, "case_trigger", "replay_mismatch_total"),
            "case_mgmt_payload_mismatch_delta": counter_delta(pre, post, "case_mgmt", "payload_mismatches"),
            "label_store_rejected_delta": counter_delta(pre, post, "label_store", "rejected"),
        },
        "overall_pass": not any("PR3.S4.B24_" in row for row in blockers),
        "blocker_ids": [row for row in sorted(set(blockers)) if "PR3.S4.B24_" in row],
    }

    recovery_receipt_path = root / "pr3_s3_execution_receipt.json"
    recovery_scorecard_path = root / "g3a_scorecard_recovery.json"
    recovery_bound_path = root / "g3a_recovery_bound_report.json"
    if recovery_receipt_path.exists() and recovery_scorecard_path.exists() and recovery_bound_path.exists():
        recovery_receipt = load_json(recovery_receipt_path)
        recovery_scorecard = load_json(recovery_scorecard_path)
        recovery_bound = load_json(recovery_bound_path)
        lag_recovery_drill = {
            "drill_id": "lag_recovery",
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": manifest_platform_run_id,
            "scenario": "Carry-forward of PR3-S3 strict burst-to-recovery drill on the same G3A execution scope.",
            "expected_behavior": "Recovery to stable within the pinned 180s bound without RTDL integrity breaches.",
            "observed_outcome": {
                "recovery_receipt_verdict": recovery_receipt.get("verdict"),
                "recovery_seconds": recovery_bound.get("recovery_seconds"),
                "recovery_bound_seconds": recovery_bound.get("thresholds", {}).get("max_recovery_seconds"),
                "ingress": recovery_scorecard.get("ingress", {}),
            },
            "overall_pass": str(recovery_receipt.get("verdict")) == "PR3_S3_READY",
            "blocker_ids": ([] if str(recovery_receipt.get("verdict")) == "PR3_S3_READY" else ["PR3.S4.B25_LAG_RECOVERY_DRILL_FAIL"]),
        }
        if not lag_recovery_drill["overall_pass"]:
            blockers.append("PR3.S4.B25_LAG_RECOVERY_DRILL_FAIL")
    else:
        lag_recovery_drill = {
            "drill_id": "lag_recovery",
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": manifest_platform_run_id,
            "overall_pass": False,
            "blocker_ids": ["PR3.S4.B25_LAG_RECOVERY_DRILL_FAIL"],
            "notes": ["Required PR3-S3 recovery artifacts missing."],
        }
        blockers.append("PR3.S4.B25_LAG_RECOVERY_DRILL_FAIL")

    schema_drill = {
        "drill_id": "schema_evolution",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "overall_pass": False,
        "blocker_ids": ["PR3.S4.B26_SCHEMA_DRILL_UNEXECUTED"],
        "notes": ["Fresh schema evolution drill artifact is not yet materialized in this S4 attempt."],
    }
    dependency_drill = {
        "drill_id": "dependency_degrade",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "overall_pass": False,
        "blocker_ids": ["PR3.S4.B26_DEPENDENCY_DRILL_UNEXECUTED"],
        "notes": ["Fresh dependency degrade drill artifact is not yet materialized in this S4 attempt."],
    }
    blockers.extend(["PR3.S4.B26_SCHEMA_DRILL_UNEXECUTED", "PR3.S4.B26_DEPENDENCY_DRILL_UNEXECUTED"])

    cost_receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "budget_envelope_usd": float(args.budget_envelope_usd),
        "attributed_spend_usd": None,
        "idle_safe_verified": False,
        "overall_pass": False,
        "blocker_ids": ["PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL"],
        "notes": ["Attributable runtime cost receipt and idle-safe verification are not yet materialized in this S4 attempt."],
    }
    cost_drill = {
        "drill_id": "cost_guardrail_idle_safe",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "overall_pass": False,
        "blocker_ids": ["PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL"],
        "notes": ["Cost/idle-safe drill awaits dedicated S4 cost attribution + residual-scan execution."],
    }
    blockers.append("PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL")

    scorecard = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "scenario_run_id": str((((manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip(),
        "window_label": "soak",
        "runtime_path_active": "CANONICAL_REMOTE_WSP_REPLAY",
        "attempt_scope": attempt_scope,
        "performance_window": performance_window,
        "campaign": manifest.get("campaign", {}),
        "ingress": {
            "observed_admitted_eps": admitted_eps,
            "admitted_request_count": admitted_total,
            "error_rate_ratio": error_rate,
            "4xx_rate_ratio": error_4xx,
            "5xx_rate_ratio": error_5xx,
            "latency_p95_ms": latency_p95,
            "latency_p99_ms": latency_p99,
            "covered_metric_seconds": performance_window.get("covered_metric_seconds"),
        },
        "thresholds": {
            "expected_soak_eps": args.expected_soak_eps,
            "min_processed_events": args.min_processed_events,
            "max_error_rate_ratio": args.max_error_rate_ratio,
            "max_4xx_ratio": args.max_4xx_ratio,
            "max_5xx_ratio": args.max_5xx_ratio,
            "max_latency_p95_ms": args.max_latency_p95_ms,
            "max_latency_p99_ms": args.max_latency_p99_ms,
            "max_lag_p99_seconds": args.max_lag_p99_seconds,
            "max_checkpoint_p99_seconds": args.max_checkpoint_p99_seconds,
        },
        "cross_plane": {
            "case_trigger_delta": case_trigger_delta,
            "cases_created_delta": case_created_delta,
            "labels_accepted_delta": label_accepted_delta,
            "learning_scope_note": "Learning/evolution is not materially exercised inside this S4 runtime lane; later pack closure remains required.",
        },
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
        "notes": notes,
    }

    drift_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": manifest_platform_run_id,
        "ingress_bin_count": len(ingress_bins),
        "ingress_bins_ref": str(root / f"{args.artifact_prefix}_ingress_bins.json"),
        "ofp_lag_seconds": time_series["ofp.lag_seconds"]["summary"],
        "ofp_checkpoint_age_seconds": time_series["ofp.checkpoint_age_seconds"]["summary"],
        "ieg_checkpoint_age_seconds": time_series["ieg.checkpoint_age_seconds"]["summary"],
        "dla_checkpoint_age_seconds": time_series["dla.checkpoint_age_seconds"]["summary"],
        "archive_backlog_events": time_series["archive.backlog_events"]["summary"],
        "overall_pass": not any("PR3.S4.B22_" in row for row in blockers),
        "blocker_ids": [row for row in sorted(set(blockers)) if "PR3.S4.B22_" in row],
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
        "verdict": "PR3_S4_READY" if len(set(blockers)) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S5" if len(set(blockers)) == 0 else "PR3-S4",
        "open_blockers": len(set(blockers)),
        "blocker_ids": sorted(set(blockers)),
        "attempt_scope": attempt_scope,
        "evidence_refs": {
            "scorecard_ref": str(root / "g3a_scorecard_soak.json"),
            "drift_report_ref": str(root / "g3a_soak_drift_report.json"),
            "cohort_manifest_ref": str(root / "g3a_cohort_manifest.json"),
            "cohort_results_ref": str(root / "g3a_cohort_results.json"),
            "replay_drill_ref": str(root / "g3a_drill_replay_integrity.json"),
            "lag_recovery_drill_ref": str(root / "g3a_drill_lag_recovery.json"),
            "schema_drill_ref": str(root / "g3a_drill_schema_evolution.json"),
            "dependency_drill_ref": str(root / "g3a_drill_dependency_degrade.json"),
            "cost_drill_ref": str(root / "g3a_drill_cost_guardrail.json"),
            "cost_receipt_ref": str(root / "g3a_runtime_cost_receipt.json"),
        },
    }

    dump_json(root / "g3a_scorecard_soak.json", scorecard)
    dump_json(root / "g3a_soak_drift_report.json", drift_report)
    dump_json(root / "g3a_cohort_manifest.json", cohort_manifest)
    dump_json(root / "g3a_cohort_results.json", cohort_results)
    dump_json(root / "g3a_drill_replay_integrity.json", replay_drill)
    dump_json(root / "g3a_drill_lag_recovery.json", lag_recovery_drill)
    dump_json(root / "g3a_drill_schema_evolution.json", schema_drill)
    dump_json(root / "g3a_drill_dependency_degrade.json", dependency_drill)
    dump_json(root / "g3a_drill_cost_guardrail.json", cost_drill)
    dump_json(root / "g3a_runtime_cost_receipt.json", cost_receipt)
    dump_json(root / "pr3_s4_execution_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
