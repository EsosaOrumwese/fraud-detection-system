from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.label_store import (
    LS_WRITE_ACCEPTED,
    REASON_ASSERTION_COMMITTED_NEW,
    REASON_ASSERTION_REPLAY_MATCH,
    LabelStoreAdapterError,
    LabelStoreWriterBoundary,
    ingest_label_from_source,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T201000Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _subject(event_id: str) -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T201000Z",
        "event_id": event_id,
    }


def _cm_assertion_payload() -> dict[str, object]:
    return {
        "case_timeline_event_id": "a" * 32,
        "label_subject_key": _subject("evt_cm_001"),
        "pins": _pins(),
        "label_type": "fraud_disposition",
        "label_value": "FRAUD_CONFIRMED",
        "effective_time": "2026-02-09T20:11:00.000000Z",
        "observed_time": "2026-02-09T20:12:00.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
    }


def _external_payload() -> dict[str, object]:
    return {
        "provider_id": "chargeback_net",
        "external_ref_id": "cbk_20260209_0001",
        "label_subject_key": _subject("evt_ext_001"),
        "pins": _pins(),
        "label_type": "chargeback_status",
        "label_value": "CHARGEBACK",
        "effective_time": "2026-02-09T20:01:00.000000Z",
        "observed_time": "2026-02-09T20:14:00.000000Z",
        "evidence_refs": [
            {"ref_type": "EXTERNAL_REF", "ref_id": "chargeback_net:cbk_20260209_0001"},
        ],
    }


def _engine_payload() -> dict[str, object]:
    return {
        "engine_bundle_id": "bundle_rtdl_v0",
        "truth_record_id": "truth_evt_0001",
        "label_subject_key": _subject("evt_engine_001"),
        "pins": _pins(),
        "label_type": "fraud_disposition",
        "label_value": "FRAUD_SUSPECTED",
        "effective_time": "2026-02-09T20:15:00.000000Z",
        "observed_time": "2026-02-09T20:16:00.000000Z",
        "decision_id": "dec_0001",
        "audit_record_id": "audit_0001",
    }


def test_phase5_cm_assertion_adapter_is_pass_through_and_idempotent(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase5.sqlite")
    first = ingest_label_from_source(
        source_class="CM_ASSERTION",
        source_payload=_cm_assertion_payload(),
        writer=writer,
    )
    second = ingest_label_from_source(
        source_class="CM_ASSERTION",
        source_payload=_cm_assertion_payload(),
        writer=writer,
    )

    assert first.write_result.status == LS_WRITE_ACCEPTED
    assert first.write_result.reason_code == REASON_ASSERTION_COMMITTED_NEW
    assert second.write_result.status == LS_WRITE_ACCEPTED
    assert second.write_result.reason_code == REASON_ASSERTION_REPLAY_MATCH
    assert first.assertion.label_assertion_id == second.assertion.label_assertion_id


def test_phase5_external_adapter_maps_provenance_and_replays_deterministically(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase5.sqlite")
    first = ingest_label_from_source(
        source_class="EXTERNAL_ADJUDICATION",
        source_payload=_external_payload(),
        writer=writer,
    )
    second = ingest_label_from_source(
        source_class="EXTERNAL_ADJUDICATION",
        source_payload=_external_payload(),
        writer=writer,
    )

    assert first.write_result.status == LS_WRITE_ACCEPTED
    assert first.write_result.reason_code == REASON_ASSERTION_COMMITTED_NEW
    assert second.write_result.reason_code == REASON_ASSERTION_REPLAY_MATCH
    assert first.assertion.case_timeline_event_id == second.assertion.case_timeline_event_id

    timeline = writer.list_timeline(
        platform_run_id=_subject("evt_ext_001")["platform_run_id"],
        event_id=_subject("evt_ext_001")["event_id"],
        label_type="chargeback_status",
    )
    assert len(timeline) == 1
    assert timeline[0].source_type == "EXTERNAL"
    assert timeline[0].actor_id == "EXTERNAL::chargeback_net"
    refs = {(item["ref_type"], item["ref_id"]) for item in timeline[0].evidence_refs}
    assert ("EXTERNAL_REF", "chargeback_net:cbk_20260209_0001") in refs


def test_phase5_engine_adapter_maps_system_provenance_and_supports_replay(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase5.sqlite")
    first = ingest_label_from_source(
        source_class="ENGINE_TRUTH",
        source_payload=_engine_payload(),
        writer=writer,
    )
    second = ingest_label_from_source(
        source_class="ENGINE_TRUTH",
        source_payload=_engine_payload(),
        writer=writer,
    )

    assert first.write_result.status == LS_WRITE_ACCEPTED
    assert first.write_result.reason_code == REASON_ASSERTION_COMMITTED_NEW
    assert second.write_result.reason_code == REASON_ASSERTION_REPLAY_MATCH

    timeline = writer.list_timeline(
        platform_run_id=_subject("evt_engine_001")["platform_run_id"],
        event_id=_subject("evt_engine_001")["event_id"],
        label_type="fraud_disposition",
    )
    assert len(timeline) == 1
    assert timeline[0].source_type == "SYSTEM"
    assert timeline[0].actor_id == "SYSTEM::engine_truth_writer::bundle_rtdl_v0"
    refs = {(item["ref_type"], item["ref_id"]) for item in timeline[0].evidence_refs}
    assert ("EXTERNAL_REF", "engine_truth:bundle_rtdl_v0:truth_evt_0001") in refs
    assert ("DECISION", "dec_0001") in refs
    assert ("DLA_AUDIT_RECORD", "audit_0001") in refs


def test_phase5_adapter_fails_closed_on_unsupported_source() -> None:
    with pytest.raises(LabelStoreAdapterError, match="unsupported source_class"):
        ingest_label_from_source(
            source_class="UNKNOWN_SOURCE",
            source_payload={},
            writer=LabelStoreWriterBoundary(":memory:"),
        )


def test_phase5_external_adapter_fails_closed_on_missing_ref_identity(tmp_path: Path) -> None:
    writer = LabelStoreWriterBoundary(tmp_path / "label_store_phase5.sqlite")
    with pytest.raises(LabelStoreAdapterError, match="external.external_ref_id is required"):
        ingest_label_from_source(
            source_class="EXTERNAL_ADJUDICATION",
            source_payload={
                "provider_id": "chargeback_net",
                "label_subject_key": _subject("evt_ext_missing_ref"),
                "pins": _pins(),
                "label_type": "chargeback_status",
                "label_value": "PENDING",
                "effective_time": "2026-02-09T20:21:00.000000Z",
                "observed_time": "2026-02-09T20:22:00.000000Z",
            },
            writer=writer,
        )

