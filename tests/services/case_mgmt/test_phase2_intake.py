from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.case_mgmt import (
    CASE_CREATED,
    CASE_EXISTING,
    INTAKE_DUPLICATE_TRIGGER,
    INTAKE_NEW_TRIGGER,
    INTAKE_TRIGGER_PAYLOAD_MISMATCH,
    TIMELINE_APPENDED,
    TIMELINE_NOOP,
    CaseTriggerIntakeError,
    CaseTriggerIntakeLedger,
)


def _trigger_payload(
    *,
    source_ref_id: str = "decision:dec_001",
    severity: str = "HIGH",
) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T163000Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_case_trigger_001",
        },
        "pins": {
            "platform_run_id": "platform_20260209T163000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-09T16:30:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": suffix},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{suffix}"},
        ],
        "trigger_payload": {"severity": severity},
    }


def test_phase2_intake_creates_case_and_appends_timeline(tmp_path: Path) -> None:
    intake = CaseTriggerIntakeLedger(tmp_path / "cm_case_intake.sqlite")
    first = intake.ingest_case_trigger(
        payload=_trigger_payload(source_ref_id="decision:dec_001"),
        ingested_at_utc="2026-02-09T16:30:01.000000Z",
    )
    assert first.outcome == INTAKE_NEW_TRIGGER
    assert first.case_status == CASE_CREATED
    assert first.timeline_status == TIMELINE_APPENDED

    second = intake.ingest_case_trigger(
        payload=_trigger_payload(source_ref_id="decision:dec_002"),
        ingested_at_utc="2026-02-09T16:30:02.000000Z",
    )
    assert second.outcome == INTAKE_NEW_TRIGGER
    assert second.case_status == CASE_EXISTING
    assert second.timeline_status == TIMELINE_APPENDED
    assert second.case_id == first.case_id

    case_row = intake.lookup_case(first.case_id)
    assert case_row is not None
    assert case_row.trigger_count == 2
    assert case_row.case_subject_key["event_id"] == "evt_case_trigger_001"

    timeline = intake.list_timeline_events(first.case_id)
    assert len(timeline) == 2
    assert {item.timeline_event_type for item in timeline} == {"CASE_TRIGGERED"}
    assert {item.source_ref_id for item in timeline} == {
        first.case_trigger_id,
        second.case_trigger_id,
    }


def test_phase2_intake_duplicate_trigger_is_noop(tmp_path: Path) -> None:
    intake = CaseTriggerIntakeLedger(tmp_path / "cm_case_intake.sqlite")
    payload = _trigger_payload()
    first = intake.ingest_case_trigger(
        payload=payload,
        ingested_at_utc="2026-02-09T16:31:01.000000Z",
    )
    assert first.outcome == INTAKE_NEW_TRIGGER

    duplicate = intake.ingest_case_trigger(
        payload=payload,
        ingested_at_utc="2026-02-09T16:31:02.000000Z",
    )
    assert duplicate.outcome == INTAKE_DUPLICATE_TRIGGER
    assert duplicate.case_status == CASE_EXISTING
    assert duplicate.timeline_status == TIMELINE_NOOP
    assert duplicate.replay_count == 1
    assert duplicate.mismatch_count == 0

    case_row = intake.lookup_case(first.case_id)
    assert case_row is not None
    assert case_row.trigger_count == 1
    assert len(intake.list_timeline_events(first.case_id)) == 1


def test_phase2_intake_payload_mismatch_fails_closed(tmp_path: Path) -> None:
    intake = CaseTriggerIntakeLedger(tmp_path / "cm_case_intake.sqlite")
    first_payload = _trigger_payload()
    first = intake.ingest_case_trigger(
        payload=first_payload,
        ingested_at_utc="2026-02-09T16:32:01.000000Z",
    )
    assert first.outcome == INTAKE_NEW_TRIGGER

    mismatch_payload = _trigger_payload(severity="CRITICAL")
    mismatch = intake.ingest_case_trigger(
        payload=mismatch_payload,
        ingested_at_utc="2026-02-09T16:32:02.000000Z",
    )
    assert mismatch.outcome == INTAKE_TRIGGER_PAYLOAD_MISMATCH
    assert mismatch.timeline_status == TIMELINE_NOOP
    assert mismatch.mismatch_count == 1

    trigger_row = intake.lookup_trigger(first.case_trigger_id)
    assert trigger_row is not None
    assert trigger_row.mismatch_count == 1
    assert len(intake.list_timeline_events(first.case_id)) == 1


def test_phase2_intake_rejects_invalid_case_trigger_contract(tmp_path: Path) -> None:
    intake = CaseTriggerIntakeLedger(tmp_path / "cm_case_intake.sqlite")
    invalid_payload = _trigger_payload()
    pins = dict(invalid_payload["pins"])  # type: ignore[index]
    pins.pop("scenario_run_id")
    invalid_payload["pins"] = pins

    with pytest.raises(CaseTriggerIntakeError):
        intake.ingest_case_trigger(
            payload=invalid_payload,
            ingested_at_utc="2026-02-09T16:33:01.000000Z",
        )
