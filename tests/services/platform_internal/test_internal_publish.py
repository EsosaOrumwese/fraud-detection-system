from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.platform_internal_publish import (
    InternalCanonicalEventPublisher,
    InternalEventPublishError,
)


def _envelope(event_id: str, event_type: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": "v1",
        "ts_utc": "2026-03-08T13:40:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "seed": 7,
        "scenario_id": "fraud_synth_v1",
        "platform_run_id": "platform_20260308T134000Z",
        "scenario_run_id": "c" * 32,
        "payload": {"source_event": {"event_id": "evt_source_1"}, "pins": {"platform_run_id": "platform_20260308T134000Z", "scenario_run_id": "c" * 32, "manifest_fingerprint": "a" * 64, "parameter_hash": "b" * 64, "seed": 7, "scenario_id": "fraud_synth_v1"}},
    }


def test_internal_publisher_routes_rtdl_decisions_to_native_bus(tmp_path: Path) -> None:
    publisher = InternalCanonicalEventPublisher(
        event_bus_kind="file",
        event_bus_root=str(tmp_path / "eb"),
        event_bus_stream=None,
        event_bus_region=None,
        event_bus_endpoint_url=None,
        class_map_ref="config/platform/ig/class_map_v0.yaml",
        partitioning_profiles_ref="config/platform/ig/partitioning_profiles_v0.yaml",
    )

    envelope = _envelope("evt_dec_1", "decision_response")
    envelope["payload"] = {
        "decision_id": "d" * 32,
        "source_event": {"event_id": "evt_source_1"},
        "pins": dict(envelope["payload"]["pins"]),  # type: ignore[index]
    }
    result = publisher.publish_envelope(envelope)

    assert result.event_class == "rtdl_decision"
    assert result.partition_profile_id == "ig.partitioning.v0.rtdl.decision"
    record_path = tmp_path / "eb" / "fp.bus.rtdl.v1" / "partition=0.jsonl"
    rows = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["payload"]["event_id"] == "evt_dec_1"


def test_internal_publisher_routes_case_triggers_to_case_bus(tmp_path: Path) -> None:
    publisher = InternalCanonicalEventPublisher(
        event_bus_kind="file",
        event_bus_root=str(tmp_path / "eb"),
        event_bus_stream=None,
        event_bus_region=None,
        event_bus_endpoint_url=None,
        class_map_ref="config/platform/ig/class_map_v0.yaml",
        partitioning_profiles_ref="config/platform/ig/partitioning_profiles_v0.yaml",
    )

    envelope = _envelope("evt_case_1", "case_trigger")
    envelope["payload"] = {
        "case_trigger_id": "t" * 32,
        "case_subject_key": {"event_id": "evt_source_1"},
        "pins": {
            "platform_run_id": "platform_20260308T134000Z",
            "scenario_run_id": "c" * 32,
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "b" * 64,
            "seed": 7,
            "scenario_id": "fraud_synth_v1",
        },
    }
    result = publisher.publish_envelope(envelope)

    assert result.event_class == "case_trigger"
    assert result.partition_profile_id == "ig.partitioning.v0.case.trigger"
    record_path = tmp_path / "eb" / "fp.bus.case.triggers.v1" / "partition=0.jsonl"
    rows = [json.loads(line) for line in record_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["payload"]["event_type"] == "case_trigger"


def test_internal_publisher_fails_closed_on_missing_required_pins(tmp_path: Path) -> None:
    publisher = InternalCanonicalEventPublisher(
        event_bus_kind="file",
        event_bus_root=str(tmp_path / "eb"),
        event_bus_stream=None,
        event_bus_region=None,
        event_bus_endpoint_url=None,
        class_map_ref="config/platform/ig/class_map_v0.yaml",
        partitioning_profiles_ref="config/platform/ig/partitioning_profiles_v0.yaml",
    )

    envelope = _envelope("evt_dec_2", "decision_response")
    envelope.pop("scenario_run_id")
    payload = dict(envelope["payload"])  # type: ignore[index]
    pins = dict(payload["pins"])  # type: ignore[index]
    pins.pop("scenario_run_id")
    payload["pins"] = pins
    envelope["payload"] = payload

    with pytest.raises(InternalEventPublishError, match="REQUIRED_PINS_MISSING"):
        publisher.publish_envelope(envelope)
