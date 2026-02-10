from __future__ import annotations

from fraud_detection.label_store.ids import (
    canonical_label_assertion_payload_hash,
    deterministic_label_assertion_id,
)


def _subject() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T153000Z",
        "event_id": "evt_decision_trigger_001",
    }


def test_label_assertion_id_is_stable_for_same_inputs() -> None:
    first = deterministic_label_assertion_id(
        case_timeline_event_id="a" * 32,
        label_subject_key=_subject(),
        label_type="fraud_disposition",
    )
    second = deterministic_label_assertion_id(
        case_timeline_event_id="a" * 32,
        label_subject_key={"event_id": "evt_decision_trigger_001", "platform_run_id": "platform_20260209T153000Z"},
        label_type="fraud_disposition",
    )
    assert first == second
    assert len(first) == 32


def test_label_assertion_id_changes_with_label_type() -> None:
    first = deterministic_label_assertion_id(
        case_timeline_event_id="a" * 32,
        label_subject_key=_subject(),
        label_type="fraud_disposition",
    )
    second = deterministic_label_assertion_id(
        case_timeline_event_id="a" * 32,
        label_subject_key=_subject(),
        label_type="chargeback_status",
    )
    assert first != second


def test_payload_hash_is_order_stable_for_evidence_refs() -> None:
    refs_a = [
        {"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"},
        {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
    ]
    refs_b = [
        {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        {"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"},
    ]
    first = canonical_label_assertion_payload_hash(
        label_subject_key=_subject(),
        label_type="fraud_disposition",
        label_value="FRAUD_CONFIRMED",
        effective_time="2026-02-09T15:10:00.000000Z",
        observed_time="2026-02-09T15:32:00.000000Z",
        source_type="HUMAN",
        actor_id="HUMAN::investigator_001",
        evidence_refs=refs_a,
    )
    second = canonical_label_assertion_payload_hash(
        label_subject_key=_subject(),
        label_type="fraud_disposition",
        label_value="FRAUD_CONFIRMED",
        effective_time="2026-02-09T15:10:00.000000Z",
        observed_time="2026-02-09T15:32:00.000000Z",
        source_type="HUMAN",
        actor_id="HUMAN::investigator_001",
        evidence_refs=refs_b,
    )
    assert first == second


def test_payload_hash_changes_with_label_value() -> None:
    first = canonical_label_assertion_payload_hash(
        label_subject_key=_subject(),
        label_type="fraud_disposition",
        label_value="FRAUD_CONFIRMED",
        effective_time="2026-02-09T15:10:00.000000Z",
        observed_time="2026-02-09T15:32:00.000000Z",
        source_type="HUMAN",
        actor_id="HUMAN::investigator_001",
        evidence_refs=[{"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"}],
    )
    second = canonical_label_assertion_payload_hash(
        label_subject_key=_subject(),
        label_type="fraud_disposition",
        label_value="LEGIT_CONFIRMED",
        effective_time="2026-02-09T15:10:00.000000Z",
        observed_time="2026-02-09T15:32:00.000000Z",
        source_type="HUMAN",
        actor_id="HUMAN::investigator_001",
        evidence_refs=[{"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"}],
    )
    assert first != second
