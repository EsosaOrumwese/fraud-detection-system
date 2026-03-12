from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_param(name: str, default: str = "") -> str:
    try:
        value = dbutils.widgets.get(name)  # type: ignore[name-defined]  # noqa: F821
        if value is not None:
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name, default)).strip()


def main() -> None:
    spec_json = _get_param("phase5_spec_json")
    build_snapshot_json = _get_param("phase5_build_snapshot_json")
    if not spec_json or not build_snapshot_json:
        raise RuntimeError("PHASE5B_QUALITY_INPUTS_REQUIRED")

    spec = json.loads(spec_json)
    build = json.loads(build_snapshot_json)
    blockers: list[str] = []

    allowed_outputs = sorted([str(item).strip() for item in (spec.get("allowed_outputs") or []) if str(item).strip()])
    intended_outputs = sorted([str(item).strip() for item in (((build.get("semantic_basis") or {}).get("intended_outputs")) or []) if str(item).strip()])
    output_roles = dict(((build.get("semantic_basis") or {}).get("output_roles")) or {})
    required_checks = [str(item).strip() for item in (spec.get("required_checks") or []) if str(item).strip()]
    validation_checks = dict(((build.get("semantic_basis") or {}).get("sixb_validation_checks")) or {})
    validation_status = str(((build.get("semantic_basis") or {}).get("sixb_validation_status")) or "").strip().upper()
    label_asof_utc = str(((build.get("semantic_basis") or {}).get("label_asof_utc")) or "").strip()
    slice_metrics = dict(build.get("slice_metrics") or {})
    events = dict(slice_metrics.get("events") or {})
    event_labels = dict(slice_metrics.get("event_labels") or {})
    flow_truth_labels = dict(slice_metrics.get("flow_truth_labels") or {})
    case_timeline = dict(slice_metrics.get("case_timeline") or {})

    if intended_outputs != allowed_outputs:
        blockers.append("PHASE5.B40_INTENDED_OUTPUTS_UNAUTHORIZED")
    if any(str(output_roles.get(name) or "").strip() != "business_traffic" for name in intended_outputs):
        blockers.append("PHASE5.B41_OUTPUT_ROLE_MISMATCH")
    if validation_status not in {"PASS", "WARN"}:
        blockers.append(f"PHASE5.B42_6B_STATUS_RED:{validation_status or 'UNSET'}")
    for check_name in required_checks:
        if str(validation_checks.get(check_name) or "").strip().upper() != "PASS":
            blockers.append(f"PHASE5.B43_REQUIRED_CHECK_RED:{check_name}")

    event_rows = int(events.get("row_count") or 0)
    event_label_rows = int(event_labels.get("row_count") or 0)
    flow_label_rows = int(flow_truth_labels.get("row_count") or 0)
    case_rows = int(case_timeline.get("row_count") or 0)
    case_count = int(case_timeline.get("distinct_case_count") or 0)
    fraud_event_count = int(events.get("fraud_event_count") or 0)
    fraud_truth_event_count = int(event_labels.get("fraud_truth_event_count") or 0)
    fraud_truth_flow_count = int(flow_truth_labels.get("fraud_truth_flow_count") or 0)
    campaign_count = int(events.get("distinct_campaign_count") or 0)
    max_event_ts_utc = str(events.get("max_ts_utc") or "").strip()

    if event_rows <= 0:
        blockers.append("PHASE5.B44_EVENTS_SLICE_EMPTY")
    if event_label_rows <= 0:
        blockers.append("PHASE5.B45_EVENT_LABELS_SLICE_EMPTY")
    if event_rows != event_label_rows:
        blockers.append(f"PHASE5.B46_EVENT_LABEL_PARITY_RED:{event_rows}!={event_label_rows}")
    if flow_label_rows <= 0:
        blockers.append("PHASE5.B47_FLOW_LABELS_SLICE_EMPTY")
    if case_rows <= 0 or case_count <= 0:
        blockers.append("PHASE5.B48_CASE_TIMELINE_EMPTY")
    if fraud_event_count <= 0:
        blockers.append("PHASE5.B49_NO_FRAUD_EVENTS_VISIBLE")
    if fraud_truth_event_count <= 0:
        blockers.append("PHASE5.B50_NO_FRAUD_EVENT_LABELS_VISIBLE")
    if fraud_truth_flow_count <= 0:
        blockers.append("PHASE5.B51_NO_FRAUD_FLOW_LABELS_VISIBLE")
    if campaign_count <= 0:
        blockers.append("PHASE5.B52_NO_CAMPAIGN_COVERAGE_VISIBLE")
    if max_event_ts_utc and label_asof_utc and max_event_ts_utc > label_asof_utc:
        blockers.append(f"PHASE5.B53_EVENT_HORIZON_EXCEEDS_LABEL_ASOF:{max_event_ts_utc}>{label_asof_utc}")

    summary = {
        "phase": "PHASE5",
        "subphase": "PHASE5B_QUALITY",
        "generated_at_utc": now_utc(),
        "execution_id": str(spec.get("execution_id") or "").strip(),
        "platform_run_id": str(spec.get("platform_run_id") or "").strip(),
        "overall_pass": len(blockers) == 0,
        "blocker_ids": blockers,
        "impact_metrics": {
            "event_rows": event_rows,
            "event_label_rows": event_label_rows,
            "flow_label_rows": flow_label_rows,
            "case_timeline_rows": case_rows,
            "distinct_case_count": case_count,
            "fraud_event_count": fraud_event_count,
            "fraud_truth_event_count": fraud_truth_event_count,
            "fraud_truth_flow_count": fraud_truth_flow_count,
            "distinct_campaign_count": campaign_count,
        },
        "time_bounds": {
            "event_min_ts_utc": str(events.get("min_ts_utc") or "").strip(),
            "event_max_ts_utc": max_event_ts_utc,
            "case_min_ts_utc": str(case_timeline.get("min_ts_utc") or "").strip(),
            "case_max_ts_utc": str(case_timeline.get("max_ts_utc") or "").strip(),
            "label_asof_utc": label_asof_utc,
        },
        "assessment": (
            "Phase 5.B bounded OFS dataset-basis quality is green on the current current-world slice."
            if len(blockers) == 0
            else "Phase 5.B bounded OFS dataset-basis quality is red; the current world cannot yet be treated as a training-safe dataset basis without remediation."
        ),
        "notes": [
            "This quality gate scores the current-world OFS slice directly against the rebuilt Phase 5 semantic-admission standard.",
            "A red result here is a useful learning-plane blocker, not a harness excuse.",
        ],
    }
    print(json.dumps(summary, ensure_ascii=True))
    try:
        dbutils.notebook.exit(json.dumps(summary, ensure_ascii=True))  # type: ignore[name-defined]  # noqa: F821
    except Exception:
        pass


if __name__ == "__main__":
    main()
