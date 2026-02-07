from __future__ import annotations

from pathlib import Path

from fraud_detection.decision_fabric.config import load_trigger_policy
from fraud_detection.decision_fabric.inlet import (
    INLET_ACCEPT,
    INLET_EVENT_TYPE_NOT_ALLOWED,
    INLET_LOOP_PREVENTION,
    INLET_MISSING_REQUIRED_PINS,
    INLET_NON_TRAFFIC_TOPIC,
    INLET_SCHEMA_VERSION_NOT_ALLOWED,
    INLET_SCHEMA_VERSION_REQUIRED,
    DecisionFabricInlet,
    DfBusInput,
)


def _valid_envelope() -> dict[str, object]:
    return {
        "event_id": "evt_100",
        "event_type": "s3_event_stream_with_fraud_6B",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T10:45:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "seed": 7,
        "scenario_id": "scenario.v0",
        "platform_run_id": "platform_20260207T104500Z",
        "scenario_run_id": "1" * 32,
        "run_id": "1" * 32,
        "payload": {"flow_id": "flow-100", "amount": 100.5},
    }


def _inlet() -> DecisionFabricInlet:
    policy = load_trigger_policy(Path("config/platform/df/trigger_policy_v0.yaml"))
    return DecisionFabricInlet(policy)


def test_accepts_allowed_traffic_trigger_and_captures_source_eb_ref() -> None:
    inlet = _inlet()
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=2,
            offset="901",
            offset_kind="kinesis_sequence",
            payload=_valid_envelope(),
            published_at_utc="2026-02-07T10:45:01.000000Z",
        )
    )
    assert result.accepted is True
    assert result.reason_code == INLET_ACCEPT
    assert result.candidate is not None
    assert result.candidate.source_event_id == "evt_100"
    assert result.candidate.source_eb_ref.as_dict()["offset"] == "901"


def test_rejects_non_traffic_topic_even_for_valid_event() -> None:
    inlet = _inlet()
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.context.arrival_events.v1",
            partition=0,
            offset="77",
            offset_kind="kinesis_sequence",
            payload=_valid_envelope(),
        )
    )
    assert result.accepted is False
    assert result.reason_code == INLET_NON_TRAFFIC_TOPIC


def test_rejects_event_type_not_in_trigger_allowlist() -> None:
    inlet = _inlet()
    envelope = _valid_envelope()
    envelope["event_type"] = "arrival_events_5B"
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="78",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == INLET_EVENT_TYPE_NOT_ALLOWED


def test_loop_prevention_blocks_df_or_al_event_families() -> None:
    inlet = _inlet()
    envelope = _valid_envelope()
    envelope["event_type"] = "decision_response"
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="79",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == INLET_LOOP_PREVENTION


def test_rejects_when_required_pins_missing() -> None:
    inlet = _inlet()
    envelope = _valid_envelope()
    envelope.pop("parameter_hash")
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="80",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == INLET_MISSING_REQUIRED_PINS


def test_rejects_when_schema_version_missing() -> None:
    inlet = _inlet()
    envelope = _valid_envelope()
    envelope.pop("schema_version")
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="81",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == INLET_SCHEMA_VERSION_REQUIRED


def test_rejects_when_schema_version_not_allowed() -> None:
    inlet = _inlet()
    envelope = _valid_envelope()
    envelope["schema_version"] = "v2"
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="82",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == INLET_SCHEMA_VERSION_NOT_ALLOWED


def test_accepts_nested_envelope_shape() -> None:
    inlet = _inlet()
    result = inlet.evaluate(
        DfBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=4,
            offset="902",
            offset_kind="kinesis_sequence",
            payload={"envelope": _valid_envelope()},
            published_at_utc="2026-02-07T10:45:02.000000Z",
        )
    )
    assert result.accepted is True
    assert result.reason_code == INLET_ACCEPT
