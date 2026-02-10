from __future__ import annotations

import pytest

from fraud_detection.archive_writer.contracts import ArchiveEventRecord, ArchiveWriterContractError


def _envelope() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260210T000000Z",
        "scenario_run_id": "scenario_001",
        "manifest_fingerprint": "abc123",
        "parameter_hash": "def456",
        "scenario_id": "baseline_v1",
        "event_id": "evt_001",
        "event_type": "traffic_fraud",
        "ts_utc": "2026-02-10T00:00:00Z",
        "payload": {"k": "v"},
    }


def test_archive_event_record_builds_with_required_fields() -> None:
    record = ArchiveEventRecord.from_bus_record(
        envelope=_envelope(),
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="101",
        offset_kind="kinesis_sequence",
    )
    assert record.platform_run_id == "platform_20260210T000000Z"
    assert record.origin_offset.offset == "101"
    assert len(record.payload_hash) == 64


def test_archive_event_record_fails_when_missing_required_pin() -> None:
    bad = _envelope()
    bad["manifest_fingerprint"] = ""
    with pytest.raises(ArchiveWriterContractError):
        ArchiveEventRecord.from_bus_record(
            envelope=bad,
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="101",
            offset_kind="kinesis_sequence",
        )
