#!/usr/bin/env python3
"""Score the bounded Phase 8 full-platform integrated validation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def int_or_default(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def main() -> None:
    ap = argparse.ArgumentParser(description="Bounded Phase 8 integrated rollup")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-phase6-execution-id", required=True)
    ap.add_argument("--source-platform-run-id", required=True)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_phase6_execution_id

    phase6_receipt = load_json(source_root / "phase6_learning_coupled_receipt.json")
    phase6_summary = load_json(source_root / "phase6_learning_coupled_summary.json")
    phase6_manifest = load_json(source_root / "phase6_registry_surface_manifest.json")
    phase7_receipt = load_json(root / "phase7_ops_gov_meta_receipt.json")
    phase7_summary = load_json(root / "phase7_ops_gov_meta_summary.json")
    alert_drill = load_json(root / "phase7_alert_runbook_drill.json")
    ml_day2 = load_json(root / "phase7_ml_day2_operator_surface.json")
    idle_drill = load_json(root / "phase7_idle_restart_drill.json")

    blockers: list[str] = []

    if str(phase6_receipt.get("verdict") or "").strip() != "PHASE6_READY":
        blockers.append("PHASE8_A_PHASE6_BACKBONE_NOT_GREEN")
    if str(phase7_receipt.get("verdict") or "").strip() != "PHASE7_READY":
        blockers.append("PHASE8_B_PHASE7_COUPLING_NOT_GREEN")
    if str(phase6_summary.get("platform_run_id") or "").strip() != str(args.source_platform_run_id).strip():
        blockers.append("PHASE8_A_PLATFORM_RUN_ID_DRIFT")
    if str(phase7_summary.get("source_platform_run_id") or "").strip() != str(args.source_platform_run_id).strip():
        blockers.append("PHASE8_B_SOURCE_PLATFORM_RUN_ID_DRIFT")
    if str(phase7_summary.get("source_phase6_execution_id") or "").strip() != str(args.source_phase6_execution_id).strip():
        blockers.append("PHASE8_B_SOURCE_PHASE6_DRIFT")

    envelope = dict(phase6_summary.get("envelope") or {})
    windows = dict(envelope.get("windows") or {})
    for label in ("steady", "burst", "recovery"):
        window = dict(windows.get(label) or {})
        if str(window.get("status") or "").strip() != "GREEN":
            blockers.append(f"PHASE8_A_WINDOW_NOT_GREEN:{label}")
        if float(window.get("4xx_total") or 0.0) != 0.0:
            blockers.append(f"PHASE8_A_4XX_PRESENT:{label}")
        if float(window.get("5xx_total") or 0.0) != 0.0:
            blockers.append(f"PHASE8_A_5XX_PRESENT:{label}")

    component_deltas = {str(key): float(value or 0.0) for key, value in dict(phase6_summary.get("component_deltas") or {}).items()}
    required_deltas = [
        "df_decisions_total_delta",
        "al_intake_total_delta",
        "dla_append_success_total_delta",
        "case_trigger_triggers_seen_delta",
        "case_mgmt_cases_created_delta",
        "label_store_accepted_delta",
    ]
    for key in required_deltas:
        if component_deltas.get(key, 0.0) <= 0.0:
            blockers.append(f"PHASE8_A_COMPONENT_DARK:{key}")

    integrity = {str(key): float(value or 0.0) for key, value in dict(phase6_summary.get("integrity") or {}).items()}
    for key, value in integrity.items():
        if value != 0.0:
            blockers.append(f"PHASE8_A_INTEGRITY_RED:{key}")

    timing = dict(phase6_summary.get("timing") or {})
    decision_to_case = dict(timing.get("decision_to_case") or {})
    case_to_label = dict(timing.get("case_to_label") or {})
    thresholds = dict(timing.get("thresholds") or {})
    if int(decision_to_case.get("count") or 0) <= 0:
        blockers.append("PHASE8_A_DECISION_TO_CASE_EMPTY")
    if int(case_to_label.get("count") or 0) <= 0:
        blockers.append("PHASE8_A_CASE_TO_LABEL_EMPTY")
    if float(decision_to_case.get("p95_seconds") or 0.0) > float(thresholds.get("decision_to_case_p95_max_seconds") or 0.0):
        blockers.append("PHASE8_A_DECISION_TO_CASE_P95_RED")
    if float(case_to_label.get("p95_seconds") or 0.0) > float(thresholds.get("case_to_label_p95_max_seconds") or 0.0):
        blockers.append("PHASE8_A_CASE_TO_LABEL_P95_RED")

    learning_authority = dict(phase6_summary.get("learning_authority") or {})
    phase5_receipt = dict(learning_authority.get("phase5_receipt") or {})
    phase5_governance = dict(learning_authority.get("phase5_governance") or {})
    phase5_metrics = dict((learning_authority.get("phase5_metrics") or {}).get("overall") or {})
    if str(phase5_receipt.get("verdict") or "").strip() != "PHASE5_READY":
        blockers.append("PHASE8_A_PHASE5_AUTHORITY_NOT_GREEN")
    if str(phase5_governance.get("gate_decision") or "").strip() != "PASS":
        blockers.append("PHASE8_A_LEARNING_GATE_NOT_PASS")
    if str(phase5_governance.get("publish_decision") or "").strip() != "ELIGIBLE":
        blockers.append("PHASE8_A_LEARNING_NOT_ELIGIBLE")
    if str(phase5_governance.get("publication_status") or "").strip() != "PUBLISHED":
        blockers.append("PHASE8_A_BUNDLE_NOT_PUBLISHED")
    if str(phase5_governance.get("rollback_validation_status") or "").strip() != "VALIDATED":
        blockers.append("PHASE8_A_ROLLBACK_VALIDATION_RED")
    if int(phase5_metrics.get("rows") or 0) <= 0:
        blockers.append("PHASE8_A_PHASE5_METRICS_EMPTY")

    expected_bundle = dict(phase6_manifest.get("promoted_bundle") or {})
    runtime_probe = dict(ml_day2.get("runtime_probe") or {})
    actual_bundle = dict(runtime_probe.get("fraud_primary") or {})
    fraud_policy_fallback = dict(runtime_probe.get("fraud_policy_fallback") or {})
    if not bool(alert_drill.get("overall_pass")):
        blockers.append("PHASE8_B_ALERT_DRILL_NOT_GREEN")
    if not bool(ml_day2.get("overall_pass")):
        blockers.append("PHASE8_B_ML_DAY2_NOT_GREEN")
    if not bool(idle_drill.get("overall_pass")):
        blockers.append("PHASE8_B_IDLE_DRILL_NOT_GREEN")
    if int_or_default(idle_drill.get("node_count_after_idle"), -1) != 0:
        blockers.append("PHASE8_B_IDLE_NOT_ZERO")
    if actual_bundle.get("bundle_id") != expected_bundle.get("bundle_id") or actual_bundle.get("bundle_version") != expected_bundle.get("bundle_version"):
        blockers.append("PHASE8_B_ACTIVE_BUNDLE_DRIFT")
    if fraud_policy_fallback.get("bundle_id") != expected_bundle.get("bundle_id") or fraud_policy_fallback.get("bundle_version") != expected_bundle.get("bundle_version"):
        blockers.append("PHASE8_B_ACTIVE_POLICY_FALLBACK_DRIFT")
    if str(runtime_probe.get("policy_revision") or "").strip() != str(phase6_manifest.get("promoted_policy_revision") or "").strip():
        blockers.append("PHASE8_B_POLICY_REVISION_DRIFT")

    reconstruction = dict(phase7_summary.get("run_reconstruction") or {})
    if int(reconstruction.get("required_local_files_present") or 0) != int(reconstruction.get("required_local_file_total") or 0):
        blockers.append("PHASE8_B_LOCAL_RECONSTRUCTION_INCOMPLETE")
    if int(reconstruction.get("readable_phase5_refs") or 0) != int(reconstruction.get("phase5_ref_total") or 0):
        blockers.append("PHASE8_B_PHASE5_READBACK_INCOMPLETE")

    observability = dict(phase7_summary.get("observability") or {})
    freshness = dict(observability.get("metric_freshness") or {})
    for key, payload in freshness.items():
        if not bool((payload or {}).get("fresh")):
            blockers.append(f"PHASE8_B_METRIC_STALE:{key}")

    handles = dict((phase7_summary.get("identity_and_drift") or {}).get("ssm_resolution") or {})
    for key, payload in handles.items():
        row = dict(payload or {})
        if not bool(row.get("resolved")):
            blockers.append(f"PHASE8_B_HANDLE_UNRESOLVED:{key}")
        if bool(row.get("placeholder_like")):
            blockers.append(f"PHASE8_B_HANDLE_PLACEHOLDER:{key}")

    integrated_story = {
        "ingress": {
            "steady_eps": float(((windows.get("steady") or {}).get("observed_admitted_eps")) or 0.0),
            "burst_eps": float(((windows.get("burst") or {}).get("observed_admitted_eps")) or 0.0),
            "recovery_eps": float(((windows.get("recovery") or {}).get("observed_admitted_eps")) or 0.0),
        },
        "runtime_participation": component_deltas,
        "integrity": integrity,
        "timing": {
            "decision_to_case_p95_seconds": float(decision_to_case.get("p95_seconds") or 0.0),
            "case_to_label_p95_seconds": float(case_to_label.get("p95_seconds") or 0.0),
        },
        "learning_truth": {
            "bundle_id": str(expected_bundle.get("bundle_id") or ""),
            "bundle_version": str(expected_bundle.get("bundle_version") or ""),
            "phase5_auc_roc": float(phase5_metrics.get("auc_roc") or 0.0),
            "phase5_precision_at_50": float(phase5_metrics.get("precision_at_50") or 0.0),
            "phase5_log_loss": float(phase5_metrics.get("log_loss") or 0.0),
        },
        "ops_governance": {
            "critical_alarm_count": len(list(observability.get("present_alarm_names") or [])),
            "runbook_linked": bool(observability.get("operations_markdown")) and bool(observability.get("cost_markdown")),
            "post_restore_active_bundle": actual_bundle,
            "policy_revision": str(runtime_probe.get("policy_revision") or ""),
            "phase5_readable_refs": int(reconstruction.get("readable_phase5_refs") or 0),
        },
    }

    summary = {
        "phase": "PHASE8",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "source_platform_run_id": args.source_platform_run_id,
        "phase6_verdict": str(phase6_receipt.get("verdict") or ""),
        "phase7_verdict": str(phase7_receipt.get("verdict") or ""),
        "integrated_story": integrated_story,
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    receipt = {
        "phase": "PHASE8",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "platform_run_id": args.source_platform_run_id,
        "verdict": "PHASE8_READY" if summary["overall_pass"] else "PHASE8_HOLD",
        "next_phase": "PHASE9" if summary["overall_pass"] else "PHASE8",
        "open_blockers": len(summary["blocker_ids"]),
        "blocker_ids": summary["blocker_ids"],
    }
    dump_json(root / "phase8_integrated_summary.json", summary)
    dump_json(root / "phase8_integrated_receipt.json", receipt)

    if not summary["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
