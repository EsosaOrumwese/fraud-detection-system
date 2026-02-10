from __future__ import annotations

from fraud_detection.case_mgmt.ids import (
    canonical_case_timeline_payload_hash,
    canonical_case_trigger_payload_hash,
    deterministic_case_id,
    deterministic_case_timeline_event_id,
    deterministic_case_trigger_id,
)


def _case_subject_key() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T153000Z",
        "event_class": "traffic_fraud",
        "event_id": "evt_decision_trigger_001",
    }


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T153000Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def test_case_id_is_stable_for_same_subject() -> None:
    subject_a = _case_subject_key()
    subject_b = {"event_id": "evt_decision_trigger_001", "event_class": "traffic_fraud", "platform_run_id": "platform_20260209T153000Z"}
    assert deterministic_case_id(case_subject_key=subject_a) == deterministic_case_id(case_subject_key=subject_b)


def test_case_trigger_id_changes_with_source_ref() -> None:
    case_id = deterministic_case_id(case_subject_key=_case_subject_key())
    first = deterministic_case_trigger_id(
        case_id=case_id,
        trigger_type="DECISION_ESCALATION",
        source_ref_id="decision:dec_001",
    )
    second = deterministic_case_trigger_id(
        case_id=case_id,
        trigger_type="DECISION_ESCALATION",
        source_ref_id="decision:dec_002",
    )
    assert first != second


def test_case_timeline_event_id_changes_with_type() -> None:
    case_id = deterministic_case_id(case_subject_key=_case_subject_key())
    first = deterministic_case_timeline_event_id(
        case_id=case_id,
        timeline_event_type="CASE_TRIGGERED",
        source_ref_id="decision:dec_001",
    )
    second = deterministic_case_timeline_event_id(
        case_id=case_id,
        timeline_event_type="LABEL_PENDING",
        source_ref_id="decision:dec_001",
    )
    assert first != second


def test_case_trigger_payload_hash_is_order_stable_for_evidence_refs() -> None:
    payload_a = {
        "case_subject_key": _case_subject_key(),
        "trigger_type": "ANOMALY",
        "source_ref_id": "anomaly:hash_mismatch",
        "pins": _pins(),
        "observed_time": "2026-02-09T15:30:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_002"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }
    payload_b = {
        **payload_a,
        "evidence_refs": [
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
            {"ref_type": "DECISION", "ref_id": "dec_002"},
        ],
    }
    assert canonical_case_trigger_payload_hash(payload_a) == canonical_case_trigger_payload_hash(payload_b)


def test_case_timeline_payload_hash_changes_when_payload_changes() -> None:
    case_id = deterministic_case_id(case_subject_key=_case_subject_key())
    payload_a = {
        "case_id": case_id,
        "timeline_event_type": "CASE_TRIGGERED",
        "source_ref_id": "decision:dec_001",
        "pins": _pins(),
        "observed_time": "2026-02-09T15:31:00.000000Z",
        "evidence_refs": [{"ref_type": "DECISION", "ref_id": "dec_001"}],
        "timeline_payload": {"queue": "fraud_high_risk"},
        "case_subject_key": _case_subject_key(),
    }
    payload_b = {
        **payload_a,
        "timeline_payload": {"queue": "fraud_default"},
    }
    assert canonical_case_timeline_payload_hash(payload_a) != canonical_case_timeline_payload_hash(payload_b)
