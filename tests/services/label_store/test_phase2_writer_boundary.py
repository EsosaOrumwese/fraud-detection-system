from __future__ import annotations

from pathlib import Path

from fraud_detection.label_store import (
    LS_WRITE_ACCEPTED,
    LS_WRITE_REJECTED,
    REASON_ASSERTION_COMMITTED_NEW,
    REASON_ASSERTION_REPLAY_MATCH,
    REASON_CONTRACT_INVALID,
    REASON_MISSING_EVIDENCE_REFS,
    REASON_PAYLOAD_HASH_MISMATCH,
    LabelStoreWriterBoundary,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T183000Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _label_subject_key() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T183000Z",
        "event_id": "evt_decision_trigger_001",
    }


def _assertion_payload(*, label_value: str = "FRAUD_CONFIRMED") -> dict[str, object]:
    return {
        "case_timeline_event_id": "a" * 32,
        "label_subject_key": _label_subject_key(),
        "pins": _pins(),
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": "2026-02-09T18:10:00.000000Z",
        "observed_time": "2026-02-09T18:32:00.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "label_payload": {"notes": "confirmed by analyst"},
    }


def test_phase2_writer_boundary_accepts_new_assertion_and_persists_record(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase2.sqlite")
    result = writer.write_label_assertion(_assertion_payload())
    assert result.status == LS_WRITE_ACCEPTED
    assert result.reason_code == REASON_ASSERTION_COMMITTED_NEW
    assert result.label_assertion_id is not None
    assert result.assertion_ref is not None

    stored = writer.lookup_assertion(label_assertion_id=result.label_assertion_id)
    assert stored is not None
    assert stored.replay_count == 0
    assert stored.mismatch_count == 0
    assert stored.assertion_ref.endswith(f"{result.label_assertion_id}.json")


def test_phase2_writer_boundary_duplicate_replay_is_deterministic(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase2.sqlite")
    first = writer.write_label_assertion(_assertion_payload())
    second = writer.write_label_assertion(_assertion_payload())

    assert first.status == LS_WRITE_ACCEPTED
    assert second.status == LS_WRITE_ACCEPTED
    assert second.reason_code == REASON_ASSERTION_REPLAY_MATCH
    assert second.label_assertion_id == first.label_assertion_id
    assert second.assertion_ref == first.assertion_ref
    assert second.replay_count == 1

    stored = writer.lookup_assertion(label_assertion_id=first.label_assertion_id or "")
    assert stored is not None
    assert stored.replay_count == 1
    assert stored.mismatch_count == 0


def test_phase2_writer_boundary_payload_hash_mismatch_is_fail_closed(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase2.sqlite")
    first = writer.write_label_assertion(_assertion_payload(label_value="FRAUD_CONFIRMED"))
    mismatch = writer.write_label_assertion(_assertion_payload(label_value="LEGIT_CONFIRMED"))

    assert first.status == LS_WRITE_ACCEPTED
    assert mismatch.status == LS_WRITE_REJECTED
    assert mismatch.reason_code == REASON_PAYLOAD_HASH_MISMATCH
    assert mismatch.label_assertion_id == first.label_assertion_id

    stored = writer.lookup_assertion(label_assertion_id=first.label_assertion_id or "")
    assert stored is not None
    assert stored.mismatch_count == 1
    assert writer.mismatch_count(label_assertion_id=first.label_assertion_id or "") == 1


def test_phase2_writer_boundary_rejects_invalid_contract_payload(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase2.sqlite")
    payload = _assertion_payload()
    pins = dict(payload["pins"])  # type: ignore[index]
    pins.pop("scenario_run_id")
    payload["pins"] = pins

    result = writer.write_label_assertion(payload)
    assert result.status == LS_WRITE_REJECTED
    assert result.reason_code is not None
    assert result.reason_code.startswith(REASON_CONTRACT_INVALID)


def test_phase2_writer_boundary_rejects_missing_evidence_refs(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase2.sqlite")
    payload = _assertion_payload()
    payload["evidence_refs"] = []
    result = writer.write_label_assertion(payload)
    assert result.status == LS_WRITE_REJECTED
    assert result.reason_code == REASON_MISSING_EVIDENCE_REFS
