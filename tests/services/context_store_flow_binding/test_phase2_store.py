from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from fraud_detection.context_store_flow_binding.contracts import FlowBindingRecord
from fraud_detection.context_store_flow_binding.store import (
    ContextStoreFlowBindingConflictError,
    build_store,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260207T000000Z",
        "scenario_run_id": "a" * 32,
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "scenario_id": "scenario-1",
        "seed": 7,
    }


def _flow_binding(*, payload_hash: str) -> FlowBindingRecord:
    return FlowBindingRecord.from_mapping(
        {
            "flow_id": "flow-1",
            "join_frame_key": {
                "platform_run_id": "platform_20260207T000000Z",
                "scenario_run_id": "a" * 32,
                "merchant_id": "m-1",
                "arrival_seq": 1,
            },
            "source_event": {
                "event_id": "evt-1",
                "event_type": "s2_flow_anchor_baseline_6B",
                "ts_utc": "2026-02-07T00:00:00.000000Z",
                "eb_ref": {
                    "topic": "fp.bus.context.flow_anchors.v1",
                    "partition": 0,
                    "offset": "1",
                    "offset_kind": "file_line",
                },
            },
            "authoritative_source_event_type": "s2_flow_anchor_baseline_6B",
            "payload_hash": payload_hash,
            "pins": _pins(),
            "bound_at_utc": "2026-02-07T00:00:00.000000Z",
        }
    )


def test_phase2_bootstrap_creates_required_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "csfb.sqlite"
    build_store(locator=db_path, stream_id="csfb")
    with sqlite3.connect(str(db_path)) as conn:
        tables = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert "csfb_join_frames" in tables
    assert "csfb_flow_bindings" in tables
    assert "csfb_join_apply_failures" in tables
    assert "csfb_join_checkpoints" in tables


def test_phase2_flow_binding_idempotency_and_hash_conflict(tmp_path: Path) -> None:
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb")
    first = store.upsert_flow_binding(record=_flow_binding(payload_hash="d" * 64))
    assert first == "inserted"

    same = store.upsert_flow_binding(record=_flow_binding(payload_hash="d" * 64))
    assert same == "noop"

    with pytest.raises(ContextStoreFlowBindingConflictError):
        store.upsert_flow_binding(record=_flow_binding(payload_hash="e" * 64))


def test_phase2_apply_checkpoint_rolls_back_on_conflict(tmp_path: Path) -> None:
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb")

    result = store.apply_flow_binding_and_checkpoint(
        record=_flow_binding(payload_hash="d" * 64),
        topic="fp.bus.context.flow_anchors.v1",
        partition_id=0,
        next_offset="2",
        offset_kind="file_line",
        watermark_ts_utc="2026-02-07T00:00:01.000000Z",
    )
    assert result.status == "inserted"
    assert result.checkpoint_status == "inserted"
    assert store.get_checkpoint(topic="fp.bus.context.flow_anchors.v1", partition_id=0).next_offset == "2"

    with pytest.raises(ContextStoreFlowBindingConflictError):
        store.apply_flow_binding_and_checkpoint(
            record=_flow_binding(payload_hash="e" * 64),
            topic="fp.bus.context.flow_anchors.v1",
            partition_id=0,
            next_offset="3",
            offset_kind="file_line",
            watermark_ts_utc="2026-02-07T00:00:02.000000Z",
        )

    # Checkpoint must not advance when apply fails in same transaction.
    checkpoint = store.get_checkpoint(topic="fp.bus.context.flow_anchors.v1", partition_id=0)
    assert checkpoint is not None
    assert checkpoint.next_offset == "2"
