from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fraud_detection.context_store_flow_binding.contracts import FlowBindingRecord, JoinFrameKey
from fraud_detection.context_store_flow_binding.query import ContextStoreFlowBindingQueryService
from fraud_detection.context_store_flow_binding.store import build_store


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260207T020000Z",
        "scenario_run_id": "a" * 32,
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "scenario_id": "baseline_v1",
        "seed": 7,
        "run_id": "d" * 32,
    }


def _join_key() -> JoinFrameKey:
    return JoinFrameKey.from_mapping(
        {
            "platform_run_id": "platform_20260207T020000Z",
            "scenario_run_id": "a" * 32,
            "merchant_id": "m-1",
            "arrival_seq": 1,
            "run_id": "d" * 32,
        }
    )


def _source_event(*, event_id: str, event_type: str, topic: str, offset: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": "2026-02-07T02:00:00.000000Z",
        "eb_ref": {
            "topic": topic,
            "partition": 0,
            "offset": offset,
            "offset_kind": "file_line",
        },
    }


def _seed_ready_state(tmp_path: Path):
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb.v0")
    join_key = _join_key()
    frame_payload = {
        "join_frame_key": join_key.as_dict(),
        "arrival_event": {"merchant_id": "m-1", "arrival_seq": 1},
        "flow_anchor": {"flow_id": "flow-1", "merchant_id": "m-1", "arrival_seq": 1},
        "context_complete": True,
    }
    frame_hash = hashlib.sha256(
        json.dumps(frame_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    join_source = _source_event(
        event_id="1" * 64,
        event_type="arrival_events_5B",
        topic="fp.bus.context.arrival_events.v1",
        offset="5",
    )
    store.upsert_join_frame(
        join_frame_key=join_key,
        payload_hash=frame_hash,
        frame_payload=frame_payload,
        source_event=join_source,
    )
    binding = FlowBindingRecord.from_mapping(
        {
            "flow_id": "flow-1",
            "join_frame_key": join_key.as_dict(),
            "source_event": _source_event(
                event_id="2" * 64,
                event_type="s2_flow_anchor_baseline_6B",
                topic="fp.bus.context.flow_anchor.baseline.v1",
                offset="9",
            ),
            "authoritative_source_event_type": "s2_flow_anchor_baseline_6B",
            "payload_hash": "e" * 64,
            "pins": _pins(),
            "bound_at_utc": "2026-02-07T02:00:02.000000Z",
        }
    )
    store.upsert_flow_binding(record=binding)
    store.advance_checkpoint(
        topic="fp.bus.context.arrival_events.v1",
        partition_id=0,
        next_offset="6",
        offset_kind="file_line",
        watermark_ts_utc="2026-02-07T02:00:00.000000Z",
    )
    return store, join_key


def test_phase5_resolve_flow_binding_ready_returns_evidence(tmp_path: Path) -> None:
    store, join_key = _seed_ready_state(tmp_path)
    service = ContextStoreFlowBindingQueryService(store=store, stream_id="csfb.v0")
    response = service.query(
        {
            "request_id": "req-1",
            "query_kind": "resolve_flow_binding",
            "flow_id": "flow-1",
            "pins": _pins(),
        }
    )
    assert response["status"] == "READY"
    assert response["reason_codes"] == ["READY"]
    assert response["flow_id"] == "flow-1"
    assert response["join_frame_key"] == join_key.as_dict()
    assert response["flow_binding"]["flow_id"] == "flow-1"
    kinds = {item["kind"] for item in response.get("evidence_refs", [])}
    assert "flow_binding_source_event" in kinds
    assert "join_frame_source_event" in kinds
    assert "join_checkpoint" in kinds


def test_phase5_resolve_flow_binding_missing_binding_is_fail_closed(tmp_path: Path) -> None:
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb.v0")
    service = ContextStoreFlowBindingQueryService(store=store, stream_id="csfb.v0")
    response = service.query(
        {
            "request_id": "req-2",
            "query_kind": "resolve_flow_binding",
            "flow_id": "missing-flow",
            "pins": _pins(),
        }
    )
    assert response["status"] == "MISSING_BINDING"
    assert response["reason_codes"] == ["FLOW_BINDING_NOT_FOUND"]


def test_phase5_resolve_flow_binding_missing_join_frame_is_explicit(tmp_path: Path) -> None:
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb.v0")
    join_key = _join_key()
    binding = FlowBindingRecord.from_mapping(
        {
            "flow_id": "flow-orphan",
            "join_frame_key": join_key.as_dict(),
            "source_event": _source_event(
                event_id="3" * 64,
                event_type="s2_flow_anchor_baseline_6B",
                topic="fp.bus.context.flow_anchor.baseline.v1",
                offset="3",
            ),
            "authoritative_source_event_type": "s2_flow_anchor_baseline_6B",
            "payload_hash": "f" * 64,
            "pins": _pins(),
            "bound_at_utc": "2026-02-07T02:01:00.000000Z",
        }
    )
    store.upsert_flow_binding(record=binding)
    service = ContextStoreFlowBindingQueryService(store=store, stream_id="csfb.v0")
    response = service.query(
        {
            "request_id": "req-3",
            "query_kind": "resolve_flow_binding",
            "flow_id": "flow-orphan",
            "pins": _pins(),
        }
    )
    assert response["status"] == "MISSING_JOIN_FRAME"
    assert response["reason_codes"] == ["JOIN_FRAME_NOT_FOUND"]


def test_phase5_fetch_join_frame_ready_without_binding(tmp_path: Path) -> None:
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb.v0")
    join_key = _join_key()
    frame_payload = {
        "join_frame_key": join_key.as_dict(),
        "arrival_event": {"merchant_id": "m-1", "arrival_seq": 1},
        "context_complete": False,
    }
    frame_hash = hashlib.sha256(
        json.dumps(frame_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    store.upsert_join_frame(
        join_frame_key=join_key,
        payload_hash=frame_hash,
        frame_payload=frame_payload,
        source_event=_source_event(
            event_id="4" * 64,
            event_type="arrival_events_5B",
            topic="fp.bus.context.arrival_events.v1",
            offset="0",
        ),
    )
    service = ContextStoreFlowBindingQueryService(store=store, stream_id="csfb.v0")
    response = service.query(
        {
            "request_id": "req-4",
            "query_kind": "fetch_join_frame",
            "join_frame_key": join_key.as_dict(),
            "pins": _pins(),
        }
    )
    assert response["status"] == "READY"
    assert response["reason_codes"] == ["READY"]
    assert response["join_frame_key"] == join_key.as_dict()
    assert "flow_binding" not in response


def test_phase5_pin_mismatch_returns_conflict(tmp_path: Path) -> None:
    store, _ = _seed_ready_state(tmp_path)
    service = ContextStoreFlowBindingQueryService(store=store, stream_id="csfb.v0")
    bad_pins = dict(_pins())
    bad_pins["parameter_hash"] = "0" * 64
    response = service.query(
        {
            "request_id": "req-5",
            "query_kind": "resolve_flow_binding",
            "flow_id": "flow-1",
            "pins": bad_pins,
        }
    )
    assert response["status"] == "CONFLICT"
    assert response["reason_codes"] == ["PINS_MISMATCH"]


def test_phase5_invalid_request_returns_invalid_request_status_when_pins_present(tmp_path: Path) -> None:
    store = build_store(locator=tmp_path / "csfb.sqlite", stream_id="csfb.v0")
    service = ContextStoreFlowBindingQueryService(store=store, stream_id="csfb.v0")
    response = service.query(
        {
            "request_id": "req-6",
            "query_kind": "resolve_flow_binding",
            "pins": _pins(),
        }
    )
    assert response["status"] == "INVALID_REQUEST"
    assert response["reason_codes"] == ["INVALID_REQUEST"]
