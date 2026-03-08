#!/usr/bin/env python3
"""Build PR3-S4 bounded correctness evidence and soak authorization."""

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


def replay_advisory_only(snapshot: dict[str, Any], component: str, max_checkpoint: float, max_lag: float) -> bool:
    if component not in {"csfb", "ieg", "ofp"}:
        return False
    if health_state(snapshot, component).upper() not in {"RED", "FAILED", "UNHEALTHY"}:
        return False
    if set(health_reasons(snapshot, component)) != {"WATERMARK_TOO_OLD"}:
        return False
    checkpoint = summary_value(snapshot, component, "checkpoint_age_seconds")
    if checkpoint is None or checkpoint > max_checkpoint:
        return False
    lag = summary_value(snapshot, component, "lag_seconds")
    if lag is not None and lag > max_lag:
        return False
    if component == "csfb":
        return (summary_value(snapshot, component, "join_misses") or 0.0) == 0.0 and (
            summary_value(snapshot, component, "binding_conflicts") or 0.0
        ) == 0.0 and (summary_value(snapshot, component, "apply_failures_hard") or 0.0) == 0.0
    if component == "ofp":
        return lag is not None and lag <= max_lag
    return (summary_value(snapshot, component, "apply_failure_count") or 0.0) == 0.0 and (
        summary_value(snapshot, component, "backpressure_hits") or 0.0
    ) == 0.0


def select_snapshots(snapshots: list[dict[str, Any]], platform_run_id: str) -> list[dict[str, Any]]:
    selected = [row for row in snapshots if str(row.get("platform_run_id", "")).strip() == platform_run_id]
    labels = {str(row.get("snapshot_label", "")).strip().lower() for row in selected}
    if not selected or "pre" not in labels or "post" not in labels:
        raise RuntimeError("PR3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED")
    return selected


def latest_snapshot(snapshots: list[dict[str, Any]], label: str) -> dict[str, Any]:
    target = str(label).strip().lower()
    for row in snapshots:
        if str(row.get("snapshot_label", "")).strip().lower() == target:
            return row
    return snapshots[-1]


def delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = summary_value(pre, component, field)
    end = summary_value(post, component, field)
    if end is None:
        return None
    if start is None:
        start = 0.0
    return float(end - start)


def build_lag_recovery_drill(root: Path, state_id: str, execution_id: str, platform_run_id: str) -> dict[str, Any]:
    recovery_receipt_path = root / "pr3_s3_execution_receipt.json"
    recovery_scorecard_path = root / "g3a_scorecard_recovery.json"
    recovery_bound_path = root / "g3a_recovery_bound_report.json"
    if recovery_receipt_path.exists() and recovery_scorecard_path.exists() and recovery_bound_path.exists():
        recovery_receipt = load_json(recovery_receipt_path)
        recovery_scorecard = load_json(recovery_scorecard_path)
        recovery_bound = load_json(recovery_bound_path)
        overall_pass = str(recovery_receipt.get("verdict") or "").strip() == "PR3_S3_READY" and bool(
            recovery_bound.get("recovery_bound_met")
        )
        return {
            "drill_id": "lag_recovery",
            "phase": "PR3",
            "state": state_id,
            "generated_at_utc": now_utc(),
            "execution_id": execution_id,
            "platform_run_id": platform_run_id,
            "scenario": "Carry-forward of PR3-S3 strict burst-to-recovery drill on the same G3A execution scope.",
            "expected_behavior": "Recovery to stable within the pinned 180s bound without RTDL integrity breaches.",
            "observed_outcome": {
                "recovery_receipt_verdict": recovery_receipt.get("verdict"),
                "recovery_seconds": recovery_bound.get("recovery_seconds"),
                "recovery_bound_seconds": recovery_bound.get("thresholds", {}).get("max_recovery_seconds"),
                "recovery_bound_met": recovery_bound.get("recovery_bound_met"),
                "ingress": recovery_scorecard.get("ingress", {}),
            },
            "overall_pass": overall_pass,
            "blocker_ids": [] if overall_pass else ["PR3.B25_LAG_RECOVERY_DRILL_FAIL"],
        }
    return {
        "drill_id": "lag_recovery",
        "phase": "PR3",
        "state": state_id,
        "generated_at_utc": now_utc(),
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "overall_pass": False,
        "blocker_ids": ["PR3.B25_LAG_RECOVERY_DRILL_FAIL"],
        "notes": ["Required PR3-S3 recovery artifacts missing."],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S4")
    ap.add_argument("--artifact-prefix", default="g3a_correctness")
    ap.add_argument("--expected-correctness-eps", type=float, default=600.0)
    ap.add_argument("--min-processed-events", type=float, default=50000.0)
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
    charter = load_json(root / "g3a_run_charter.active.json")
    control_bootstrap = load_optional_json(root / "g3a_control_plane_bootstrap.json") or {"overall_pass": False}
    learning_summary = load_optional_json(root / "g3a_correctness_learning_summary.json") or {"overall_pass": False}
    ops_gov_summary = load_optional_json(root / "g3a_correctness_ops_gov_summary.json") or {"overall_pass": False}
    snapshots = sorted(
        [load_json(path) for path in root.glob(f"g3a_{str(args.state_id).strip().lower()}_component_snapshot_*.json")],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )
    platform_run_id = str((((manifest or {}).get("identity") or {}).get("platform_run_id") or "")).strip()
    if control_bootstrap.get("platform_run_id"):
        platform_run_id = str(control_bootstrap.get("platform_run_id") or "").strip() or platform_run_id
    if summary is None or manifest is None:
        blockers = ["PR3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED"]
        if not bool(control_bootstrap.get("overall_pass")):
            blockers.append("PR3.B20_CONTROL_BOOTSTRAP_FAIL")
        if not bool(learning_summary.get("overall_pass")):
            blockers.append("PR3.B29_LEARNING_BOUND_FAIL")
        if not bool(ops_gov_summary.get("overall_pass")):
            blockers.append("PR3.B30_OPS_GOV_BOUND_FAIL")
        blockers.append("PR3.B28_SOAK_NOT_AUTHORIZED")
        notes = [
            "Correctness runtime artifacts were missing, so the rollup degraded to blocker-only receipt emission.",
            f"Missing artifacts: {', '.join(name for name, payload in ((f'{prefix}_wsp_runtime_summary.json', summary), (f'{prefix}_wsp_runtime_manifest.json', manifest)) if payload is None)}",
        ]
        cross_plane = {
            "control_bootstrap": "PASS" if bool(control_bootstrap.get("overall_pass")) else "HOLD_REMEDIATE",
            "runtime_spine": "HOLD_REMEDIATE",
            "case_label_management": "HOLD_REMEDIATE",
            "learning_evolution": "PASS" if bool(learning_summary.get("overall_pass")) else "HOLD_REMEDIATE",
            "ops_gov": "PASS" if bool(ops_gov_summary.get("overall_pass")) else "HOLD_REMEDIATE",
        }
        lag_recovery_drill = load_optional_json(root / "g3a_drill_lag_recovery.json") or build_lag_recovery_drill(
            root, args.state_id, args.pr3_execution_id, platform_run_id
        )
        scorecard = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "window_label": "correctness",
            "control_bootstrap": {
                "overall_pass": bool(control_bootstrap.get("overall_pass")),
                "scenario_run_id": control_bootstrap.get("scenario_run_id"),
                "facts_view_ref": ((control_bootstrap.get("sr") or {}).get("facts_view_ref")),
                "status_ref": ((control_bootstrap.get("sr") or {}).get("status_ref")),
            },
            "ingress": {},
            "component_deltas": {},
            "cross_plane": cross_plane,
            "overall_pass": False,
            "blocker_ids": sorted(set(blockers)),
            "notes": notes,
        }
        component_snapshot = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "snapshot": {},
        }
        cross_plane_report = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "cross_plane": cross_plane,
            "metrics": {},
            "integrity": {},
            "control_bootstrap": control_bootstrap,
            "learning_summary": learning_summary,
            "ops_gov_summary": ops_gov_summary,
            "notes": notes,
        }
        replay_drill = {
            "drill_id": "replay_integrity",
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "observed_outcome": {},
            "overall_pass": False,
            "blocker_ids": ["PR3.B24_REPLAY_OR_INTEGRITY_DRILL_FAIL"],
        }
        soak_authorization = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "authorized": False,
            "reason": "S4 bounded correctness gate remains red; soak stays blocked.",
        }
        receipt = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "verdict": "HOLD_REMEDIATE",
            "next_state": "PR3-S4",
            "open_blockers": len(set(blockers)),
            "blocker_ids": sorted(set(blockers)),
        }
        dump_json(root / "g3a_correctness_scorecard.json", scorecard)
        dump_json(root / "g3a_correctness_component_snapshot.json", component_snapshot)
        dump_json(root / "g3a_correctness_cross_plane_report.json", cross_plane_report)
        dump_json(root / "g3a_drill_replay_integrity.json", replay_drill)
        dump_json(root / "g3a_drill_lag_recovery.json", lag_recovery_drill)
        dump_json(root / "g3a_soak_authorization.json", {**soak_authorization, "blocker_ids": sorted(set(blockers))})
        dump_json(root / "pr3_s4_execution_receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
        return

    try:
        selected = select_snapshots(snapshots, platform_run_id)
    except RuntimeError:
        blockers = ["PR3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED", "PR3.B22_CROSS_PLANE_PARTICIPATION_UNPROVEN:snapshots_missing"]
        if not bool(control_bootstrap.get("overall_pass")):
            blockers.append("PR3.B20_CONTROL_BOOTSTRAP_FAIL")
        if not bool(learning_summary.get("overall_pass")):
            blockers.append("PR3.B29_LEARNING_BOUND_FAIL")
        if not bool(ops_gov_summary.get("overall_pass")):
            blockers.append("PR3.B30_OPS_GOV_BOUND_FAIL")
        blockers.append("PR3.B28_SOAK_NOT_AUTHORIZED")
        notes = [
            "Correctness runtime snapshots were incomplete, so the rollup degraded to blocker-only receipt emission.",
            f"Observed snapshot count for platform_run_id '{platform_run_id}': {len([row for row in snapshots if str(row.get('platform_run_id', '')).strip() == platform_run_id])}",
        ]
        cross_plane = {
            "control_bootstrap": "PASS" if bool(control_bootstrap.get("overall_pass")) else "HOLD_REMEDIATE",
            "runtime_spine": "HOLD_REMEDIATE",
            "case_label_management": "HOLD_REMEDIATE",
            "learning_evolution": "PASS" if bool(learning_summary.get("overall_pass")) else "HOLD_REMEDIATE",
            "ops_gov": "PASS" if bool(ops_gov_summary.get("overall_pass")) else "HOLD_REMEDIATE",
        }
        lag_recovery_drill = load_optional_json(root / "g3a_drill_lag_recovery.json") or build_lag_recovery_drill(
            root, args.state_id, args.pr3_execution_id, platform_run_id
        )
        scorecard = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "window_label": str((summary.get("window_label") if summary else "") or "correctness"),
            "control_bootstrap": {
                "overall_pass": bool(control_bootstrap.get("overall_pass")),
                "scenario_run_id": control_bootstrap.get("scenario_run_id"),
                "facts_view_ref": ((control_bootstrap.get("sr") or {}).get("facts_view_ref")),
                "status_ref": ((control_bootstrap.get("sr") or {}).get("status_ref")),
            },
            "ingress": dict((summary or {}).get("observed") or {}),
            "component_deltas": {},
            "cross_plane": cross_plane,
            "overall_pass": False,
            "blocker_ids": sorted(set(blockers)),
            "notes": notes,
        }
        component_snapshot = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "snapshot": {},
        }
        cross_plane_report = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "cross_plane": cross_plane,
            "metrics": {},
            "integrity": {},
            "control_bootstrap": control_bootstrap,
            "learning_summary": learning_summary,
            "ops_gov_summary": ops_gov_summary,
            "notes": notes,
        }
        replay_drill = {
            "drill_id": "replay_integrity",
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "observed_outcome": {},
            "overall_pass": False,
            "blocker_ids": ["PR3.B24_REPLAY_OR_INTEGRITY_DRILL_FAIL"],
        }
        soak_authorization = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "authorized": False,
            "reason": "S4 bounded correctness gate remains red; soak stays blocked.",
        }
        receipt = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "verdict": "HOLD_REMEDIATE",
            "next_state": "PR3-S4",
            "open_blockers": len(set(blockers)),
            "blocker_ids": sorted(set(blockers)),
        }
        dump_json(root / "g3a_correctness_scorecard.json", scorecard)
        dump_json(root / "g3a_correctness_component_snapshot.json", component_snapshot)
        dump_json(root / "g3a_correctness_cross_plane_report.json", cross_plane_report)
        dump_json(root / "g3a_drill_replay_integrity.json", replay_drill)
        dump_json(root / "g3a_drill_lag_recovery.json", lag_recovery_drill)
        dump_json(root / "g3a_soak_authorization.json", {**soak_authorization, "blocker_ids": sorted(set(blockers))})
        dump_json(root / "pr3_s4_execution_receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
        return
    pre = latest_snapshot(selected, "pre")
    post = latest_snapshot(selected, "post")

    blockers: list[str] = []
    notes: list[str] = []
    observed = dict(summary.get("observed") or {})
    admitted_eps = float(observed.get("observed_admitted_eps", 0.0) or 0.0)
    admitted_total = float(observed.get("admitted_request_count", 0.0) or 0.0)
    error_rate = float(observed.get("error_rate_ratio", 0.0) or 0.0)
    error_4xx = float(observed.get("4xx_rate_ratio", 0.0) or 0.0)
    error_5xx = float(observed.get("5xx_rate_ratio", 0.0) or 0.0)
    p95 = to_float(observed.get("latency_p95_ms"))
    p99 = to_float(observed.get("latency_p99_ms"))
    if admitted_eps < args.expected_correctness_eps or admitted_total < args.min_processed_events:
        blockers.append("PR3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED")
    if error_rate > args.max_error_rate_ratio or error_4xx > args.max_4xx_ratio or error_5xx > args.max_5xx_ratio:
        blockers.append("PR3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED")
    if p95 is None or p95 > args.max_latency_p95_ms or p99 is None or p99 > args.max_latency_p99_ms:
        blockers.append("PR3.B21_CORRECTNESS_WINDOW_NOT_EXECUTED")
    if not bool(control_bootstrap.get("overall_pass")):
        blockers.append("PR3.B20_CONTROL_BOOTSTRAP_FAIL")

    for component in ("csfb", "ieg", "ofp", "dl", "df", "al", "dla", "archive_writer", "case_trigger", "case_mgmt", "label_store"):
        if is_missing(post, component):
            blockers.append(f"PR3.B22_CROSS_PLANE_PARTICIPATION_UNPROVEN:{component}:missing")
            continue
        state = health_state(post, component).upper()
        if state in {"RED", "FAILED", "UNHEALTHY"} and not replay_advisory_only(
            post, component, args.max_checkpoint_p99_seconds, args.max_lag_p99_seconds
        ):
            blockers.append(f"PR3.B22_CROSS_PLANE_PARTICIPATION_UNPROVEN:{component}:health_red")

    metrics = {
        "csfb_join_hits_delta": delta(pre, post, "csfb", "join_hits"),
        "ieg_events_seen_delta": delta(pre, post, "ieg", "events_seen"),
        "ofp_events_applied_delta": delta(pre, post, "ofp", "events_applied"),
        "df_decisions_total_delta": delta(pre, post, "df", "decisions_total"),
        "al_intake_total_delta": delta(pre, post, "al", "intake_total"),
        "dla_append_success_total_delta": delta(pre, post, "dla", "append_success_total"),
        "archive_archived_total_delta": delta(pre, post, "archive_writer", "archived_total"),
        "case_trigger_triggers_seen_delta": delta(pre, post, "case_trigger", "triggers_seen"),
        "case_mgmt_case_triggers_delta": delta(pre, post, "case_mgmt", "case_triggers"),
        "case_mgmt_cases_created_delta": delta(pre, post, "case_mgmt", "cases_created"),
        "case_mgmt_case_replays_delta": delta(pre, post, "case_mgmt", "case_replays"),
        "label_store_pending_delta": delta(pre, post, "label_store", "pending"),
        "label_store_accepted_delta": delta(pre, post, "label_store", "accepted"),
        "label_store_rejected_delta": delta(pre, post, "label_store", "rejected"),
    }
    required_positive = (
        "csfb_join_hits_delta",
        "ieg_events_seen_delta",
        "ofp_events_applied_delta",
        "df_decisions_total_delta",
        "al_intake_total_delta",
        "dla_append_success_total_delta",
        "archive_archived_total_delta",
        "case_trigger_triggers_seen_delta",
    )
    for key in required_positive:
        if (metrics[key] or 0.0) <= 0.0:
            blockers.append(f"PR3.B22_CROSS_PLANE_PARTICIPATION_UNPROVEN:{key}")
    if not any((metrics[name] or 0.0) > 0.0 for name in ("case_mgmt_case_triggers_delta", "case_mgmt_cases_created_delta", "case_mgmt_case_replays_delta")):
        blockers.append("PR3.B22_CROSS_PLANE_PARTICIPATION_UNPROVEN:case_mgmt")
    if not any((metrics[name] or 0.0) > 0.0 for name in ("label_store_pending_delta", "label_store_accepted_delta", "label_store_rejected_delta")):
        blockers.append("PR3.B22_CROSS_PLANE_PARTICIPATION_UNPROVEN:label_store")

    integrity = {
        "df_fail_closed_delta": delta(pre, post, "df", "fail_closed_total"),
        "df_publish_quarantine_delta": delta(pre, post, "df", "publish_quarantine_total"),
        "al_publish_quarantine_delta": delta(pre, post, "al", "publish_quarantine_total"),
        "al_publish_ambiguous_delta": delta(pre, post, "al", "publish_ambiguous_total"),
        "dla_append_failure_delta": delta(pre, post, "dla", "append_failure_total"),
        "dla_replay_divergence_delta": delta(pre, post, "dla", "replay_divergence_total"),
        "archive_write_error_delta": delta(pre, post, "archive_writer", "write_error_total"),
        "archive_payload_mismatch_delta": delta(pre, post, "archive_writer", "payload_mismatch_total"),
        "case_trigger_publish_quarantine_delta": delta(pre, post, "case_trigger", "publish_quarantine_total"),
        "case_trigger_publish_ambiguous_delta": delta(pre, post, "case_trigger", "publish_ambiguous_total"),
        "case_trigger_replay_mismatch_delta": delta(pre, post, "case_trigger", "replay_mismatch_total"),
        "case_mgmt_payload_mismatch_delta": delta(pre, post, "case_mgmt", "payload_mismatches"),
        "label_store_rejected_delta": metrics["label_store_rejected_delta"],
    }
    if any(value is None or value > 0.0 for value in integrity.values()):
        blockers.append("PR3.B24_REPLAY_OR_INTEGRITY_DRILL_FAIL")

    if len(list(charter.get("cohorts_required") or [])) < 5:
        blockers.append("PR3.B23_REQUIRED_COHORT_DELTA_UNPROVEN")
    else:
        notes.append("S4 correctness covers the pinned realism cohort set; cohort-isolated deltas stay a later stress/soak proof surface.")

    schema_drill = load_optional_json(root / "g3a_drill_schema_evolution.json") or {"overall_pass": False}
    dependency_drill = load_optional_json(root / "g3a_drill_dependency_degrade.json") or {"overall_pass": False}
    lag_recovery_drill = load_optional_json(root / "g3a_drill_lag_recovery.json") or build_lag_recovery_drill(
        root, args.state_id, args.pr3_execution_id, platform_run_id
    )
    cost_drill = load_optional_json(root / "g3a_drill_cost_guardrail.json") or {"overall_pass": False}
    cost_receipt = load_optional_json(root / "g3a_correctness_cost_receipt.json") or {"overall_pass": False}
    if not bool(schema_drill.get("overall_pass")) or not bool(dependency_drill.get("overall_pass")):
        blockers.append("PR3.B26_SCHEMA_OR_DEPENDENCY_DRILL_FAIL")
    if not bool(lag_recovery_drill.get("overall_pass")):
        blockers.append("PR3.B25_LAG_RECOVERY_DRILL_FAIL")
    if not bool(cost_drill.get("overall_pass")) or not bool(cost_receipt.get("overall_pass")):
        blockers.append("PR3.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL")
    if not bool(learning_summary.get("overall_pass")):
        blockers.append("PR3.B29_LEARNING_BOUND_FAIL")
    if not bool(ops_gov_summary.get("overall_pass")):
        blockers.append("PR3.B30_OPS_GOV_BOUND_FAIL")

    learning_ready = bool(learning_summary.get("overall_pass"))
    ops_ready = bool(ops_gov_summary.get("overall_pass")) and all(
        bool(item.get("overall_pass")) for item in (schema_drill, dependency_drill, lag_recovery_drill, cost_drill, cost_receipt)
    )
    notes.append("Learning/evolution is direct in S4 only when OFS, MF, and MPR all produce green receipts on the active run scope.")
    notes.append("Ops/gov is direct in S4 only when run-scoped conformance/observability receipts are green alongside schema/dependency/recovery/cost drills.")

    cross_plane = {
        "control_bootstrap": "PASS" if bool(control_bootstrap.get("overall_pass")) else "HOLD_REMEDIATE",
        "runtime_spine": "PASS" if not any(item.startswith(("PR3.B21", "PR3.B22")) for item in blockers) else "HOLD_REMEDIATE",
        "case_label_management": "PASS"
        if not any("case_trigger" in item or "case_mgmt" in item or "label_store" in item for item in blockers)
        else "HOLD_REMEDIATE",
        "learning_evolution": "PASS" if learning_ready else "HOLD_REMEDIATE",
        "ops_gov": "PASS" if ops_ready else "HOLD_REMEDIATE",
    }

    scorecard = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "window_label": str(summary.get("window_label") or "correctness"),
        "control_bootstrap": {
            "overall_pass": bool(control_bootstrap.get("overall_pass")),
            "scenario_run_id": control_bootstrap.get("scenario_run_id"),
            "facts_view_ref": ((control_bootstrap.get("sr") or {}).get("facts_view_ref")),
            "status_ref": ((control_bootstrap.get("sr") or {}).get("status_ref")),
        },
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
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
        "notes": notes,
    }
    component_snapshot = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "snapshot": post,
    }
    cross_plane_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "cross_plane": cross_plane,
        "metrics": metrics,
        "integrity": integrity,
        "control_bootstrap": control_bootstrap,
        "learning_summary": learning_summary,
        "ops_gov_summary": ops_gov_summary,
        "notes": notes,
    }
    replay_drill = {
        "drill_id": "replay_integrity",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "observed_outcome": integrity,
        "overall_pass": "PR3.B24_REPLAY_OR_INTEGRITY_DRILL_FAIL" not in blockers,
        "blocker_ids": [] if "PR3.B24_REPLAY_OR_INTEGRITY_DRILL_FAIL" not in blockers else ["PR3.B24_REPLAY_OR_INTEGRITY_DRILL_FAIL"],
    }
    soak_authorization = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "authorized": len(set(blockers)) == 0,
        "reason": "S4 bounded correctness gate is green." if len(set(blockers)) == 0 else "S4 bounded correctness gate remains red; soak stays blocked.",
    }
    if not soak_authorization["authorized"]:
        blockers.append("PR3.B28_SOAK_NOT_AUTHORIZED")
    receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "verdict": "PR3_S4_READY" if len(set(blockers)) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S5" if len(set(blockers)) == 0 else "PR3-S4",
        "open_blockers": len(set(blockers)),
        "blocker_ids": sorted(set(blockers)),
    }

    dump_json(root / "g3a_correctness_scorecard.json", scorecard)
    dump_json(root / "g3a_correctness_component_snapshot.json", component_snapshot)
    dump_json(root / "g3a_correctness_cross_plane_report.json", cross_plane_report)
    dump_json(root / "g3a_drill_replay_integrity.json", replay_drill)
    dump_json(root / "g3a_drill_lag_recovery.json", lag_recovery_drill)
    dump_json(root / "g3a_soak_authorization.json", {**soak_authorization, "blocker_ids": sorted(set(blockers))})
    dump_json(root / "pr3_s4_execution_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
