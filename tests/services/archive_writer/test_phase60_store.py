from __future__ import annotations

from fraud_detection.archive_writer.store import (
    ARCHIVE_OBS_DUPLICATE,
    ARCHIVE_OBS_NEW,
    ARCHIVE_OBS_PAYLOAD_MISMATCH,
    ArchiveWriterLedger,
)


def test_archive_writer_ledger_observe_and_checkpoint(tmp_path) -> None:
    locator = str(tmp_path / "archive_ledger.sqlite")
    ledger = ArchiveWriterLedger(locator=locator, stream_id="archive_writer.v0::platform_test")

    first = ledger.observe(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="10",
        offset_kind="kinesis_sequence",
        payload_hash="a" * 64,
        archive_ref="s3://fraud-platform/platform_test/archive/events/topic=foo/partition=0/offset_kind=kinesis_sequence/offset=10.json",
        observed_at_utc="2026-02-10T00:00:00Z",
    )
    assert first.outcome == ARCHIVE_OBS_NEW

    dup = ledger.observe(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="10",
        offset_kind="kinesis_sequence",
        payload_hash="a" * 64,
        archive_ref=first.archive_ref or "",
        observed_at_utc="2026-02-10T00:00:01Z",
    )
    assert dup.outcome == ARCHIVE_OBS_DUPLICATE

    mismatch = ledger.observe(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="10",
        offset_kind="kinesis_sequence",
        payload_hash="b" * 64,
        archive_ref=first.archive_ref or "",
        observed_at_utc="2026-02-10T00:00:02Z",
    )
    assert mismatch.outcome == ARCHIVE_OBS_PAYLOAD_MISMATCH

    assert ledger.next_offset(topic="fp.bus.traffic.fraud.v1", partition=0) is None
    ledger.advance(topic="fp.bus.traffic.fraud.v1", partition=0, offset="10", offset_kind="kinesis_sequence")
    next_offset = ledger.next_offset(topic="fp.bus.traffic.fraud.v1", partition=0)
    assert next_offset == ("10", "kinesis_sequence")
