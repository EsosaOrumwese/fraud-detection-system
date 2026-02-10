from __future__ import annotations

import pytest

from fraud_detection.context_store_flow_binding.contracts import (
    ContextStoreFlowBindingContractError,
    FlowBindingRecord,
    JoinFrameKey,
    QueryRequest,
    QueryResponse,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260207T000000Z",
        "scenario_run_id": "a" * 32,
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "scenario_id": "scenario-1",
        "seed": 7,
        "run_id": "a" * 32,
    }


def test_join_frame_key_valid_and_normalized() -> None:
    key = JoinFrameKey.from_mapping(
        {
            "platform_run_id": "platform_20260207T000000Z",
            "scenario_run_id": "a" * 32,
            "merchant_id": "m-1",
            "arrival_seq": "42",
            "run_id": "a" * 32,
        }
    )
    assert key.arrival_seq == 42
    assert key.as_dict()["merchant_id"] == "m-1"


def test_join_frame_key_missing_required_field_fails_closed() -> None:
    with pytest.raises(ContextStoreFlowBindingContractError):
        JoinFrameKey.from_mapping(
            {
                "platform_run_id": "platform_20260207T000000Z",
                "scenario_run_id": "a" * 32,
                "arrival_seq": 2,
            }
        )


def test_query_request_requires_exactly_one_selector() -> None:
    with pytest.raises(ContextStoreFlowBindingContractError):
        QueryRequest.from_mapping(
            {
                "request_id": "req-1",
                "query_kind": "resolve_flow_binding",
                "pins": _pins(),
            }
        )
    with pytest.raises(ContextStoreFlowBindingContractError):
        QueryRequest.from_mapping(
            {
                "request_id": "req-2",
                "query_kind": "resolve_flow_binding",
                "flow_id": "flow-1",
                "join_frame_key": {
                    "platform_run_id": "platform_20260207T000000Z",
                    "scenario_run_id": "a" * 32,
                    "merchant_id": "m-1",
                    "arrival_seq": 1,
                },
                "pins": _pins(),
            }
        )


def test_flow_binding_record_rejects_non_authoritative_source_event_type() -> None:
    with pytest.raises(ContextStoreFlowBindingContractError):
        FlowBindingRecord.from_mapping(
            {
                "flow_id": "flow-1",
                "join_frame_key": {
                    "platform_run_id": "platform_20260207T000000Z",
                    "scenario_run_id": "a" * 32,
                    "merchant_id": "m-1",
                    "arrival_seq": 1,
                },
                "source_event": {
                    "event_id": "e" * 64,
                    "event_type": "arrival_events_5B",
                    "ts_utc": "2026-02-07T00:00:00.000000Z",
                    "eb_ref": {
                        "topic": "fp.bus.context.arrival_events.v1",
                        "partition": 0,
                        "offset": "1",
                        "offset_kind": "file_line",
                    },
                },
                "authoritative_source_event_type": "arrival_events_5B",
                "payload_hash": "d" * 64,
                "pins": _pins(),
                "bound_at_utc": "2026-02-07T00:00:00.000000Z",
            }
        )


def test_query_response_valid_contract_shape() -> None:
    response = QueryResponse.from_mapping(
        {
            "request_id": "req-3",
            "status": "READY",
            "reason_codes": ["READY"],
            "pins": _pins(),
            "resolved_at_utc": "2026-02-07T00:00:00.000000Z",
            "flow_id": "flow-1",
        }
    )
    assert response.status == "READY"
    assert response.as_dict()["reason_codes"] == ["READY"]
