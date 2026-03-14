#!/usr/bin/env python3
"""Score the bounded Phase 9 full-platform stress authorization slice."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Bounded Phase 9 stress rollup")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-phase6-execution-id", required=True)
    ap.add_argument("--source-platform-run-id", required=True)
    ap.add_argument("--min-admitted-events", type=int, default=2000000)
    ap.add_argument("--max-admitted-events", type=int, default=5000000)
    ap.add_argument("--min-steady-seconds", type=int, default=600)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_phase6_execution_id

    phase6_receipt = load_json(source_root / "phase6_learning_coupled_receipt.json")
    phase6_summary = load_json(source_root / "phase6_learning_coupled_summary.json")
    phase6_manifest = load_json(source_root / "phase6_registry_surface_manifest.json")
    candidate_probe = load_json(source_root / "phase6_candidate_bundle_probe.json")
    alert_drill = load_json(root / "phase7_alert_runbook_drill.json")
    ml_day2 = load_json(root / "phase7_ml_day2_operator_surface.json")
    operator_surface = load_json(root / "phase9_stress_operator_surface.json")

    blockers: list[str] = []
    if str(phase6_receipt.get("verdict") or "").strip() != "PHASE6_READY":
        blockers.append("PHASE9_B_SOURCE_PHASE6_NOT_GREEN")
    if str(phase6_summary.get("platform_run_id") or "").strip() != str(args.source_platform_run_id).strip():
        blockers.append("PHASE9_B_PLATFORM_RUN_ID_DRIFT")
    if not bool(alert_drill.get("overall_pass")):
        blockers.append("PHASE9_C_ALERT_DRILL_NOT_GREEN")
    if not bool(ml_day2.get("overall_pass")):
        blockers.append("PHASE9_C_ML_DAY2_NOT_GREEN")
    if not bool(operator_surface.get("overall_pass")):
        blockers.append("PHASE9_C_OPERATOR_SURFACE_NOT_GREEN")
    if not bool(candidate_probe.get("overall_pass")):
        blockers.append("PHASE9_B_RTDL_BUNDLE_PROBE_NOT_GREEN")

    envelope = dict(phase6_summary.get("envelope") or {})
    windows = dict(envelope.get("windows") or {})
    total_admitted = 0
    for label in ("steady", "burst", "recovery"):
        window = dict(windows.get(label) or {})
        total_admitted += int(window.get("admitted_request_count") or 0)
        if str(window.get("status") or "").strip() != "GREEN":
            blockers.append(f"PHASE9_B_WINDOW_NOT_GREEN:{label}")
        if float(window.get("4xx_total") or 0.0) != 0.0:
            blockers.append(f"PHASE9_B_4XX_PRESENT:{label}")
        if float(window.get("5xx_total") or 0.0) != 0.0:
            blockers.append(f"PHASE9_B_5XX_PRESENT:{label}")

    steady = dict(windows.get("steady") or {})
    if float(steady.get("covered_seconds") or 0.0) < float(args.min_steady_seconds):
        blockers.append("PHASE9_B_STEADY_WINDOW_TOO_SHORT")
    if total_admitted < args.min_admitted_events:
        blockers.append("PHASE9_B_VOLUME_TOO_LOW")
    if total_admitted > args.max_admitted_events:
        blockers.append("PHASE9_B_VOLUME_TOO_HIGH")

    component_deltas = {str(key): float(value or 0.0) for key, value in dict(phase6_summary.get("component_deltas") or {}).items()}
    for key in (
        "df_decisions_total_delta",
        "al_intake_total_delta",
        "dla_append_success_total_delta",
        "case_trigger_triggers_seen_delta",
        "case_mgmt_cases_created_delta",
        "label_store_accepted_delta",
    ):
        if component_deltas.get(key, 0.0) <= 0.0:
            blockers.append(f"PHASE9_B_COMPONENT_DARK:{key}")

    integrity = {str(key): float(value or 0.0) for key, value in dict(phase6_summary.get("integrity") or {}).items()}
    for key, value in integrity.items():
        if value != 0.0:
            blockers.append(f"PHASE9_B_INTEGRITY_RED:{key}")

    timing = dict(phase6_summary.get("timing") or {})
    decision_to_case = dict(timing.get("decision_to_case") or {})
    case_to_label = dict(timing.get("case_to_label") or {})
    thresholds = dict(timing.get("thresholds") or {})
    if int(decision_to_case.get("count") or 0) <= 0:
        blockers.append("PHASE9_B_DECISION_TO_CASE_EMPTY")
    if int(case_to_label.get("count") or 0) <= 0:
        blockers.append("PHASE9_B_CASE_TO_LABEL_EMPTY")
    if float(decision_to_case.get("p95_seconds") or 0.0) > float(thresholds.get("decision_to_case_p95_max_seconds") or 0.0):
        blockers.append("PHASE9_B_DECISION_TO_CASE_P95_RED")
    if float(case_to_label.get("p95_seconds") or 0.0) > float(thresholds.get("case_to_label_p95_max_seconds") or 0.0):
        blockers.append("PHASE9_B_CASE_TO_LABEL_P95_RED")

    expected_bundle = dict(phase6_manifest.get("promoted_bundle") or {})
    runtime_probe = dict(ml_day2.get("runtime_probe") or {})
    actual_bundle = dict(runtime_probe.get("fraud_primary") or {})
    if actual_bundle.get("bundle_id") != expected_bundle.get("bundle_id") or actual_bundle.get("bundle_version") != expected_bundle.get("bundle_version"):
        blockers.append("PHASE9_C_ACTIVE_BUNDLE_DRIFT")
    if str(runtime_probe.get("policy_revision") or "").strip() != str(phase6_manifest.get("promoted_policy_revision") or "").strip():
        blockers.append("PHASE9_C_ACTIVE_POLICY_DRIFT")

    recent_attempts = [dict(row or {}) for row in list(candidate_probe.get("recent_attempts") or [])]
    accepted_attempts = [row for row in recent_attempts if bool(row.get("accepted"))]
    event_types = {str(row.get("event_type") or "").strip() for row in accepted_attempts if str(row.get("event_type") or "").strip()}
    reason_codes = {str(row.get("reason_code") or "").strip() for row in accepted_attempts if str(row.get("reason_code") or "").strip()}
    if not accepted_attempts:
        blockers.append("PHASE9_B_RTDL_DECISION_SAMPLE_EMPTY")
    if "decision_response" not in event_types:
        blockers.append("PHASE9_B_RTDL_DECISION_RESPONSE_MISSING")
    if "action_intent" not in event_types:
        blockers.append("PHASE9_B_RTDL_ACTION_INTENT_MISSING")
    if reason_codes and reason_codes != {"ACCEPT"}:
        blockers.append("PHASE9_B_RTDL_REASON_CODE_DRIFT")

    learning_authority = dict(phase6_summary.get("learning_authority") or {})
    phase5_metrics = dict(learning_authority.get("phase5_metrics") or {})
    overall_metrics = dict(phase5_metrics.get("overall") or {})
    cohort_metrics = dict(phase5_metrics.get("cohorts") or {})
    dataset_sampling = dict((operator_surface.get("learning_basis") or {}).get("dataset_sampling") or {})
    event_scan = dict(dataset_sampling.get("event_scan") or {})
    auc_roc = float(overall_metrics.get("auc_roc") or 0.0)
    precision_at_50 = float(overall_metrics.get("precision_at_50") or 0.0)
    if int(overall_metrics.get("rows") or 0) <= 0 or int(overall_metrics.get("positives") or 0) <= 0 or int(overall_metrics.get("negatives") or 0) <= 0:
        blockers.append("PHASE9_B_LEARNING_EVAL_DEGENERATE")
    if auc_roc <= 0.5:
        blockers.append("PHASE9_B_LEARNING_AUC_NOT_MEANINGFUL")
    if precision_at_50 <= 0.5:
        blockers.append("PHASE9_B_LEARNING_PRECISION_NOT_MEANINGFUL")
    for cohort in ("weekday_lt_5", "weekday_ge_5", "campaign_absent"):
        if cohort not in cohort_metrics:
            blockers.append(f"PHASE9_B_LEARNING_COHORT_MISSING:{cohort}")
    if int(event_scan.get("campaign_present_rows") or 0) <= 0:
        blockers.append("PHASE9_B_LEARNING_RARE_REGIME_ERASED")

    reconstruction = dict(operator_surface.get("run_reconstruction") or {})
    if int(reconstruction.get("required_local_files_present") or 0) != int(reconstruction.get("required_local_file_total") or 0):
        blockers.append("PHASE9_C_LOCAL_RECONSTRUCTION_INCOMPLETE")
    if int(reconstruction.get("readable_phase5_refs") or 0) != int(reconstruction.get("phase5_ref_total") or 0):
        blockers.append("PHASE9_C_PHASE5_READBACK_INCOMPLETE")

    freshness = dict((operator_surface.get("observability") or {}).get("metric_freshness") or {})
    for key, payload in freshness.items():
        if not bool((payload or {}).get("fresh")):
            blockers.append(f"PHASE9_C_METRIC_STALE:{key}")

    handles = dict((operator_surface.get("identity_and_handles") or {}).get("ssm_resolution") or {})
    for key, payload in handles.items():
        row = dict(payload or {})
        if not bool(row.get("resolved")):
            blockers.append(f"PHASE9_C_HANDLE_UNRESOLVED:{key}")
        if bool(row.get("placeholder_like")):
            blockers.append(f"PHASE9_C_HANDLE_PLACEHOLDER:{key}")

    summary = {
        "phase": "PHASE9",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "source_platform_run_id": args.source_platform_run_id,
        "stress_story": {
            "admitted_request_count_total": total_admitted,
            "steady_eps": float((steady.get("observed_admitted_eps")) or 0.0),
            "steady_p95_ms": float((steady.get("latency_p95_ms")) or 0.0),
            "steady_p99_ms": float((steady.get("latency_p99_ms")) or 0.0),
            "burst_eps": float(((windows.get("burst") or {}).get("observed_admitted_eps")) or 0.0),
            "recovery_eps": float(((windows.get("recovery") or {}).get("observed_admitted_eps")) or 0.0),
            "runtime_participation": component_deltas,
            "integrity": integrity,
            "timing": {
                "decision_to_case_p95_seconds": float(decision_to_case.get("p95_seconds") or 0.0),
                "case_to_label_p95_seconds": float(case_to_label.get("p95_seconds") or 0.0),
            },
            "operator_surface": {
                "critical_alarm_count": len(list((operator_surface.get("observability") or {}).get("present_alarm_names") or [])),
                "phase5_readable_refs": int(reconstruction.get("readable_phase5_refs") or 0),
                "post_stress_active_bundle": actual_bundle,
                "policy_revision": str(runtime_probe.get("policy_revision") or ""),
            },
            "semantic_story": {
                "rtdl_recent_event_types": sorted(event_types),
                "rtdl_recent_reason_codes": sorted(reason_codes),
                "accepted_recent_attempts": len(accepted_attempts),
                "case_trigger_delta": float(component_deltas.get("case_trigger_triggers_seen_delta") or 0.0),
                "cases_created_delta": float(component_deltas.get("case_mgmt_cases_created_delta") or 0.0),
                "labels_accepted_delta": float(component_deltas.get("label_store_accepted_delta") or 0.0),
                "phase5_auc_roc": auc_roc,
                "phase5_precision_at_50": precision_at_50,
                "campaign_present_rows": int(event_scan.get("campaign_present_rows") or 0),
                "feature_asof_utc": str(event_scan.get("feature_asof_utc") or ""),
            },
        },
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    receipt = {
        "phase": "PHASE9",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "platform_run_id": args.source_platform_run_id,
        "verdict": "PHASE9_READY" if summary["overall_pass"] else "PHASE9_HOLD",
        "next_phase": "LONG_STRESS_AUTHORIZED" if summary["overall_pass"] else "PHASE9",
        "open_blockers": len(summary["blocker_ids"]),
        "blocker_ids": summary["blocker_ids"],
    }
    dump_json(root / "phase9_stress_summary.json", summary)
    dump_json(root / "phase9_stress_receipt.json", receipt)

    if not summary["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
