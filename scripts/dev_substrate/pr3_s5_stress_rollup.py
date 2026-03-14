#!/usr/bin/env python3
"""Build PR3-S5 bounded stress evidence from live runtime artifacts."""

from __future__ import annotations

import argparse
import json
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


def summary_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


def summary_text(snapshot: dict[str, Any], component: str, field: str) -> str:
    value = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))
    return str(value or "").strip()


def health_state(snapshot: dict[str, Any], component: str) -> str:
    return str((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_state") or "UNKNOWN")


def health_reasons(snapshot: dict[str, Any], component: str) -> list[str]:
    raw = ((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get("health_reasons"))
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def is_missing(snapshot: dict[str, Any], component: str) -> bool:
    payloads = ((snapshot.get("components") or {}).get(component) or {})
    for key in ("metrics_payload", "health_payload"):
        payload = payloads.get(key) or {}
        if payload.get("__missing__") or payload.get("__unreadable__"):
            return True
    return False


def delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = summary_value(pre, component, field)
    end = summary_value(post, component, field)
    if end is None:
        return None
    if start is None:
        start = 0.0
    return float(end - start)


def replay_advisory_only(snapshot: dict[str, Any], component: str, max_checkpoint: float, max_lag: float) -> bool:
    if component not in {"csfb", "ieg", "ofp", "dla"}:
        return False
    if health_state(snapshot, component).upper() not in {"RED", "FAILED", "UNHEALTHY", "AMBER"}:
        return False
    reasons = set(health_reasons(snapshot, component))
    checkpoint = summary_value(snapshot, component, "checkpoint_age_seconds")
    if checkpoint is None or checkpoint > max_checkpoint:
        return False
    lag = summary_value(snapshot, component, "lag_seconds")
    if lag is not None and lag > max_lag:
        return False
    if component == "csfb":
        return reasons == {"WATERMARK_TOO_OLD"} and (summary_value(snapshot, component, "binding_conflicts") or 0.0) == 0.0
    if component == "ieg":
        return reasons == {"WATERMARK_TOO_OLD"} and (summary_value(snapshot, component, "apply_failure_count") or 0.0) == 0.0
    if component == "ofp":
        if reasons == {"WATERMARK_REPLAY_ADVISORY"}:
            return (
                (summary_value(snapshot, component, "snapshot_failures") or 0.0) == 0.0
                and (summary_value(snapshot, component, "missing_features") or 0.0) == 0.0
            )
        if reasons == {"WATERMARK_TOO_OLD"}:
            return (summary_value(snapshot, component, "snapshot_failures") or 0.0) == 0.0
        if reasons != {"WATERMARK_TOO_OLD", "MISSING_FEATURES_RED"}:
            return False
        if (summary_value(snapshot, component, "snapshot_failures") or 0.0) > 0.0:
            return False
        if (summary_value(snapshot, "df", "missing_context_total") or 0.0) > 0.0:
            return False
        if (summary_value(snapshot, "df", "hard_fail_closed_total") or 0.0) > 0.0:
            return False
        return summary_text(snapshot, "dl", "decision_mode").upper() in {"NORMAL", "STEP_UP_ONLY"}
    return reasons in ({"UNRESOLVED_AMBER"}, {"UNRESOLVED_AMBER", "WATERMARK_TOO_OLD"}) and (
        (summary_value(snapshot, component, "append_failure_total") or 0.0) == 0.0
        and (summary_value(snapshot, component, "replay_divergence_total") or 0.0) == 0.0
    )


def select_snapshots(snapshots: list[dict[str, Any]], platform_run_id: str) -> list[dict[str, Any]]:
    selected = [row for row in snapshots if str(row.get("platform_run_id", "")).strip() == platform_run_id]
    labels = {str(row.get("snapshot_label", "")).strip().lower() for row in selected}
    if not selected or "stress_pre" not in labels or "stress_post" not in labels:
        raise RuntimeError("PR3.S5.STRESS.B01_WINDOW_NOT_EXECUTED")
    return selected


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    target = str(label).strip().lower()
    for row in reversed(snapshots):
        if str(row.get("snapshot_label", "")).strip().lower() == target:
            return row
    return snapshots[-1]


def build_component_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for component in (
        "csfb",
        "ieg",
        "ofp",
        "dl",
        "df",
        "al",
        "dla",
        "archive_writer",
        "case_trigger",
        "case_mgmt",
        "label_store",
    ):
        out[component] = dict((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S5")
    ap.add_argument("--artifact-prefix", default="g3a_stress")
    ap.add_argument("--expected-stress-eps", type=float, default=6000.0)
    ap.add_argument("--min-processed-events", type=float, default=1800000.0)
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
    learning_summary = load_optional_json(root / "g3a_correctness_learning_summary.json") or {"overall_pass": False}
    ops_gov_summary = load_optional_json(root / "g3a_correctness_ops_gov_summary.json") or {"overall_pass": False}
    cost_receipt = load_optional_json(root / "g3a_stress_cost_receipt.json") or {"overall_pass": False}
    snapshots = sorted(
        [load_json(path) for path in root.glob("g3a_s5_component_snapshot_*.json")],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )

    platform_run_id = str((((manifest or {}).get("identity") or {}).get("platform_run_id") or "")).strip()
    blockers: list[str] = []
    notes: list[str] = []

    if summary is None or manifest is None:
        blockers.append("PR3.S5.STRESS.B01_WINDOW_NOT_EXECUTED")
        scorecard = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "window_label": "stress",
            "overall_pass": False,
            "blocker_ids": blockers,
            "notes": ["Stress runtime artifacts are missing."],
        }
        receipt = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "verdict": "HOLD_REMEDIATE",
            "next_state": "PR3-S5",
            "open_blockers": len(blockers),
            "blocker_ids": blockers,
        }
        authorization = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "authorized": False,
            "reason": "Bounded stress window is not green.",
            "blocker_ids": blockers,
        }
        dump_json(root / "g3a_stress_scorecard.json", scorecard)
        dump_json(root / "g3a_stress_component_snapshot.json", {"snapshot": {}})
        dump_json(root / "g3a_stress_cross_plane_report.json", {"blocker_ids": blockers})
        dump_json(root / "g3a_stress_authorization.json", authorization)
        dump_json(root / "g3a_stress_execution_receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
        return

    selected = select_snapshots(snapshots, platform_run_id)
    pre = latest_snapshot(selected, "stress_pre")
    post = latest_snapshot(selected, "stress_post")
    observed = dict(summary.get("observed") or {})
    admitted_eps = float(observed.get("observed_admitted_eps", 0.0) or 0.0)
    admitted_total = float(observed.get("admitted_request_count", 0.0) or 0.0)
    error_rate = float(observed.get("error_rate_ratio", 0.0) or 0.0)
    error_4xx = float(observed.get("4xx_rate_ratio", 0.0) or 0.0)
    error_5xx = float(observed.get("5xx_rate_ratio", 0.0) or 0.0)
    p95 = to_float(observed.get("latency_p95_ms"))
    p99 = to_float(observed.get("latency_p99_ms"))

    if admitted_eps < args.expected_stress_eps:
        blockers.append(f"PR3.S5.STRESS.B02_THROUGHPUT_SHORTFALL:observed={admitted_eps:.3f}:target={args.expected_stress_eps:.3f}")
    if admitted_total < args.min_processed_events:
        blockers.append(f"PR3.S5.STRESS.B03_SAMPLE_MINIMA_SHORTFALL:observed={admitted_total:.0f}:required={args.min_processed_events:.0f}")
    if error_rate > args.max_error_rate_ratio:
        blockers.append(f"PR3.S5.STRESS.B04_ERROR_RATE_BREACH:observed={error_rate:.6f}:max={args.max_error_rate_ratio:.6f}")
    if error_4xx > args.max_4xx_ratio:
        blockers.append(f"PR3.S5.STRESS.B05_4XX_BREACH:observed={error_4xx:.6f}:max={args.max_4xx_ratio:.6f}")
    if error_5xx > args.max_5xx_ratio:
        blockers.append(f"PR3.S5.STRESS.B06_5XX_BREACH:observed={error_5xx:.6f}:max={args.max_5xx_ratio:.6f}")
    if p95 is None or p95 > args.max_latency_p95_ms:
        blockers.append(f"PR3.S5.STRESS.B07_P95_LATENCY_BREACH:observed={p95}:max={args.max_latency_p95_ms:.3f}")
    if p99 is None or p99 > args.max_latency_p99_ms:
        blockers.append(f"PR3.S5.STRESS.B08_P99_LATENCY_BREACH:observed={p99}:max={args.max_latency_p99_ms:.3f}")

    for component in ("csfb", "ieg", "ofp", "dl", "df", "al", "dla", "archive_writer", "case_trigger", "case_mgmt", "label_store"):
        if is_missing(post, component):
            blockers.append(f"PR3.S5.STRESS.B09_COMPONENT_SURFACE_MISSING:{component}")
            continue
        state = health_state(post, component).upper()
        if state in {"RED", "FAILED", "UNHEALTHY", "AMBER"} and not replay_advisory_only(
            post, component, args.max_checkpoint_p99_seconds, args.max_lag_p99_seconds
        ):
            blockers.append(f"PR3.S5.STRESS.B10_COMPONENT_HEALTH_RED:{component}:{state}")

    lag_checks = {
        "ofp_lag_p99": summary_value(post, "ofp", "lag_seconds"),
        "ofp_checkpoint_age": summary_value(post, "ofp", "checkpoint_age_seconds"),
        "ieg_checkpoint_age": summary_value(post, "ieg", "checkpoint_age_seconds"),
        "dla_checkpoint_age": summary_value(post, "dla", "checkpoint_age_seconds"),
    }
    for key, value in lag_checks.items():
        if value is None:
            continue
        limit = args.max_lag_p99_seconds if "lag" in key else args.max_checkpoint_p99_seconds
        if value > limit:
            blockers.append(f"PR3.S5.STRESS.B11_RUNTIME_FRESHNESS_BREACH:{key}:observed={value}:max={limit}")

    metrics = {
        "csfb_join_hits_delta": delta(pre, post, "csfb", "join_hits"),
        "ieg_events_seen_delta": delta(pre, post, "ieg", "events_seen"),
        "ofp_events_applied_delta": delta(pre, post, "ofp", "events_applied"),
        "df_decisions_total_delta": delta(pre, post, "df", "decisions_total"),
        "df_hard_fail_closed_delta": delta(pre, post, "df", "hard_fail_closed_total")
        if summary_value(post, "df", "hard_fail_closed_total") is not None
        else delta(pre, post, "df", "fail_closed_total"),
        "df_publish_quarantine_delta": delta(pre, post, "df", "publish_quarantine_total"),
        "al_intake_total_delta": delta(pre, post, "al", "intake_total"),
        "al_publish_quarantine_delta": delta(pre, post, "al", "publish_quarantine_total"),
        "al_publish_ambiguous_delta": delta(pre, post, "al", "publish_ambiguous_total"),
        "dla_append_success_delta": delta(pre, post, "dla", "append_success_total"),
        "dla_append_failure_delta": delta(pre, post, "dla", "append_failure_total"),
        "dla_replay_divergence_delta": delta(pre, post, "dla", "replay_divergence_total"),
        "archive_archived_delta": delta(pre, post, "archive_writer", "archived_total"),
        "archive_write_error_delta": delta(pre, post, "archive_writer", "write_error_total"),
        "archive_payload_mismatch_delta": delta(pre, post, "archive_writer", "payload_mismatch_total"),
        "case_trigger_delta": delta(pre, post, "case_trigger", "triggers_seen"),
        "cases_created_delta": delta(pre, post, "case_mgmt", "cases_created"),
        "labels_accepted_delta": delta(pre, post, "label_store", "accepted"),
        "labels_rejected_delta": delta(pre, post, "label_store", "rejected"),
    }

    for key in ("ieg_events_seen_delta", "ofp_events_applied_delta", "df_decisions_total_delta", "al_intake_total_delta", "dla_append_success_delta", "archive_archived_delta"):
        if (metrics[key] or 0.0) <= 0.0:
            blockers.append(f"PR3.S5.STRESS.B12_CROSS_PLANE_IDLE:{key}")
    if (metrics["df_hard_fail_closed_delta"] or 0.0) > 0.0:
        blockers.append(f"PR3.S5.STRESS.B13_DF_HARD_FAIL_CLOSED_NONZERO:delta={metrics['df_hard_fail_closed_delta']}")
    if (metrics["df_publish_quarantine_delta"] or 0.0) > 0.0:
        blockers.append(f"PR3.S5.STRESS.B14_DF_QUARANTINE_NONZERO:delta={metrics['df_publish_quarantine_delta']}")
    if (metrics["al_publish_quarantine_delta"] or 0.0) > 0.0 or (metrics["al_publish_ambiguous_delta"] or 0.0) > 0.0:
        blockers.append("PR3.S5.STRESS.B15_AL_INTEGRITY_NONZERO")
    if (metrics["dla_append_failure_delta"] or 0.0) > 0.0 or (metrics["dla_replay_divergence_delta"] or 0.0) > 0.0:
        blockers.append("PR3.S5.STRESS.B16_DLA_INTEGRITY_NONZERO")
    if (metrics["archive_write_error_delta"] or 0.0) > 0.0 or (metrics["archive_payload_mismatch_delta"] or 0.0) > 0.0:
        blockers.append("PR3.S5.STRESS.B17_ARCHIVE_INTEGRITY_NONZERO")
    if (metrics["df_decisions_total_delta"] or 0.0) > 0.0 and (metrics["case_trigger_delta"] or 0.0) <= 0.0:
        blockers.append("PR3.S5.STRESS.B18_CASE_TRIGGER_UNEXERCISED")
    if (metrics["case_trigger_delta"] or 0.0) > 0.0 and (metrics["cases_created_delta"] or 0.0) <= 0.0:
        blockers.append("PR3.S5.STRESS.B19_CASE_MGMT_UNEXERCISED")
    if (metrics["cases_created_delta"] or 0.0) > 0.0 and (metrics["labels_accepted_delta"] or 0.0) <= 0.0:
        blockers.append("PR3.S5.STRESS.B20_LABEL_STORE_UNEXERCISED")
    if (metrics["labels_rejected_delta"] or 0.0) > 0.0:
        blockers.append(f"PR3.S5.STRESS.B21_LABEL_REJECTED_NONZERO:delta={metrics['labels_rejected_delta']}")
    if not bool(learning_summary.get("overall_pass")):
        blockers.append("PR3.S5.STRESS.B22_LEARNING_CARRY_FORWARD_RED")
    if not bool(ops_gov_summary.get("overall_pass")):
        blockers.append("PR3.S5.STRESS.B23_OPS_GOV_CARRY_FORWARD_RED")
    if not bool(cost_receipt.get("overall_pass")):
        blockers.append("PR3.S5.STRESS.B24_COST_OR_IDLESAFE_RED")

    cross_plane = {
        "runtime_spine": "PASS" if not any("STRESS.B0" in item or "STRESS.B1" in item for item in blockers) else "HOLD_REMEDIATE",
        "case_label_management": "PASS"
        if not any("CASE_" in item or "LABEL_" in item for item in blockers)
        else "HOLD_REMEDIATE",
        "learning_evolution": "PASS" if bool(learning_summary.get("overall_pass")) else "HOLD_REMEDIATE",
        "ops_gov": "PASS" if bool(ops_gov_summary.get("overall_pass")) else "HOLD_REMEDIATE",
    }
    if len(blockers) == 0:
        notes.append("Bounded stress stayed inside throughput, latency, integrity, and carry-forward plane posture.")
    else:
        notes.append("Bounded stress is red; soak remains blocked until the failed stress boundary is remediated.")

    scorecard = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "window_label": "stress",
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
        "cross_plane": cross_plane,
        "learning_impact_metrics": dict(learning_summary.get("impact_metrics") or {}),
        "ops_gov_impact_metrics": dict(ops_gov_summary.get("impact_metrics") or {}),
        "overall_pass": len(blockers) == 0,
        "blocker_ids": blockers,
        "notes": notes,
    }
    component_snapshot = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "snapshot": build_component_projection(post),
    }
    cross_plane_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "cross_plane": cross_plane,
        "metrics": metrics,
        "learning_summary_ref": "g3a_correctness_learning_summary.json",
        "ops_gov_summary_ref": "g3a_correctness_ops_gov_summary.json",
        "cost_receipt_ref": "g3a_stress_cost_receipt.json",
        "notes": notes,
    }
    authorization = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "authorized": len(blockers) == 0,
        "reason": "Bounded stress gate is green." if len(blockers) == 0 else "Bounded stress gate remains red; soak stays blocked.",
        "blocker_ids": blockers,
    }
    receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PR3_S5_STRESS_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S5" if len(blockers) > 0 else "PR3-S5-SOAK",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
    }

    dump_json(root / "g3a_stress_scorecard.json", scorecard)
    dump_json(root / "g3a_stress_component_snapshot.json", component_snapshot)
    dump_json(root / "g3a_stress_cross_plane_report.json", cross_plane_report)
    dump_json(root / "g3a_stress_authorization.json", authorization)
    dump_json(root / "g3a_stress_execution_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
