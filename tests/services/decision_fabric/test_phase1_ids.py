from __future__ import annotations

from fraud_detection.decision_fabric.ids import (
    deterministic_action_idempotency_key,
    deterministic_action_intent_event_id,
    deterministic_decision_id,
    deterministic_decision_response_event_id,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260207T102700Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _bundle_ref() -> dict[str, object]:
    return {"bundle_id": "a" * 64, "bundle_version": "2026.02.07", "registry_ref": "registry://active"}


def _origin_offset() -> dict[str, object]:
    return {
        "topic": "topic.rtdl.traffic",
        "partition": 1,
        "offset": "10",
        "offset_kind": "kafka_offset",
    }


def test_deterministic_decision_id_is_stable_for_same_origin_offset() -> None:
    reordered_origin_offset = {
        "stream": "topic.rtdl.traffic",
        "partition": 1,
        "offset": "10",
        "offset_kind": "kafka_offset",
    }
    left = deterministic_decision_id(
        source_event_id="evt_100",
        platform_run_id="platform_20260207T102700Z",
        decision_scope="merchant_risk",
        bundle_ref=_bundle_ref(),
        origin_offset=_origin_offset(),
    )
    right = deterministic_decision_id(
        source_event_id="evt_100",
        platform_run_id="platform_20260207T102700Z",
        decision_scope="merchant_risk",
        bundle_ref={"registry_ref": "registry://active", "bundle_version": "2026.02.07", "bundle_id": "a" * 64},
        origin_offset=reordered_origin_offset,
    )
    assert left == right
    assert len(left) == 32


def test_decision_id_changes_when_origin_offset_changes() -> None:
    first = deterministic_decision_id(
        source_event_id="evt_100",
        platform_run_id="platform_20260207T102700Z",
        decision_scope="merchant_risk",
        bundle_ref=_bundle_ref(),
        origin_offset=_origin_offset(),
    )
    second = deterministic_decision_id(
        source_event_id="evt_100",
        platform_run_id="platform_20260207T102700Z",
        decision_scope="merchant_risk",
        bundle_ref=_bundle_ref(),
        origin_offset={"topic": "topic.rtdl.traffic", "partition": 1, "offset": "11", "offset_kind": "kafka_offset"},
    )
    assert first != second


def test_decision_response_event_id_changes_with_scope() -> None:
    first = deterministic_decision_response_event_id(
        source_event_id="evt_100",
        decision_scope="merchant_risk",
        pins=_pins(),
    )
    second = deterministic_decision_response_event_id(
        source_event_id="evt_100",
        decision_scope="instrument_risk",
        pins=_pins(),
    )
    assert first != second
    assert len(first) == 64


def test_action_identity_changes_with_domain() -> None:
    event_a = deterministic_action_intent_event_id(
        source_event_id="evt_100",
        action_domain="txn_disposition",
        pins=_pins(),
    )
    event_b = deterministic_action_intent_event_id(
        source_event_id="evt_100",
        action_domain="case_queue",
        pins=_pins(),
    )
    key_a = deterministic_action_idempotency_key(
        source_event_id="evt_100",
        action_domain="txn_disposition",
        pins=_pins(),
    )
    key_b = deterministic_action_idempotency_key(
        source_event_id="evt_100",
        action_domain="case_queue",
        pins=_pins(),
    )
    assert event_a != event_b
    assert key_a != key_b
    assert len(key_a) == 64
