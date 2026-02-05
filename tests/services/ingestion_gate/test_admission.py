from pathlib import Path

import pytest

from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _build_gate(
    tmp_path: Path,
    *,
    required_pins: list[str] | None = None,
) -> IngestionGate:
    schema_policy = tmp_path / "schema_policy.yaml"
    class_map = tmp_path / "class_map.yaml"
    partitioning = tmp_path / "partitioning.yaml"
    catalogue = tmp_path / "catalogue.yaml"
    gate_map = tmp_path / "gate_map.yaml"

    _write_yaml(
        schema_policy,
        {
            "version": "0.1.0",
            "default_action": "quarantine",
            "policies": [
                {
                    "event_type": "test_event",
                    "class": "traffic",
                    "schema_version_required": False,
                }
            ],
        },
    )
    if required_pins is None:
        required_pins = ["manifest_fingerprint"]
    _write_yaml(
        class_map,
        {
            "version": "0.1.0",
            "classes": {"traffic": {"required_pins": required_pins}},
            "event_types": {"test_event": "traffic"},
        },
    )
    _write_yaml(
        partitioning,
        {
            "version": "0.1.0",
            "profiles": {
                "ig.partitioning.v0.traffic": {
                    "stream": "fp.bus.traffic.v1",
                    "key_precedence": ["event_id"],
                    "hash_algo": "sha256",
                },
                "ig.partitioning.v0.audit": {
                    "stream": "fp.bus.audit.v1",
                    "key_precedence": ["event_id"],
                    "hash_algo": "sha256",
                },
            },
        },
    )
    _write_yaml(
        catalogue,
        {
            "version": "1.0",
            "outputs": [
                {
                    "output_id": "test_event",
                    "path_template": "data/test_event/part.jsonl",
                    "primary_key": ["flow_id"],
                    "read_requires_gates": [],
                    "scope": "scope_manifest_fingerprint",
                }
            ],
        },
    )
    _write_yaml(gate_map, {"version": "1.0", "gates": []})

    wiring = WiringProfile(
        profile_id="test",
        object_store_root=str(tmp_path / "store"),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        admission_db_path=str(tmp_path / "ig_admission.db"),
        engine_root_path=None,
        health_probe_interval_seconds=0,
        health_deny_on_amber=False,
        health_amber_sleep_seconds=0,
        bus_publish_failure_threshold=2,
        metrics_flush_seconds=0,
        quarantine_spike_threshold=10,
        quarantine_spike_window_seconds=60,
        schema_root="docs/model_spec/platform/contracts",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        engine_catalogue_path=str(catalogue),
        gate_map_path=str(gate_map),
        partitioning_profiles_ref=str(partitioning),
        partitioning_profile_id="ig.partitioning.v0.traffic",
        schema_policy_ref=str(schema_policy),
        class_map_ref=str(class_map),
        policy_rev="test-v0",
        event_bus_kind="file",
        event_bus_path=str(tmp_path / "bus"),
    )
    return IngestionGate.build(wiring)


def _envelope(event_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "test_event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "platform_run_id": "platform_20260101T000000Z",
        "scenario_run_id": "b" * 32,
        "run_id": "b" * 32,
        "payload": {"flow_id": event_id},
    }


def test_duplicate_does_not_republish(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    envelope = _envelope("evt-1")

    receipt1 = gate.admit_push(envelope)
    receipt2 = gate.admit_push(envelope)

    assert receipt1.payload["decision"] == "ADMIT"
    assert receipt2.payload["decision"] == "DUPLICATE"
    bus_log = tmp_path / "bus" / "fp.bus.traffic.v1" / "partition=0.jsonl"
    assert bus_log.exists()
    assert len(bus_log.read_text(encoding="utf-8").splitlines()) == 1


def test_push_with_run_scoped_pins_does_not_require_ready(tmp_path: Path) -> None:
    gate = _build_gate(
        tmp_path,
        required_pins=[
            "platform_run_id",
            "scenario_run_id",
            "manifest_fingerprint",
            "parameter_hash",
            "seed",
            "scenario_id",
            "run_id",
        ],
    )
    envelope = _envelope("evt-2")
    envelope.update(
        {
            "parameter_hash": "c" * 64,
            "seed": 7,
            "scenario_id": "scenario-1",
            "run_id": "b" * 32,
        }
    )
    receipt = gate.admit_push(envelope)
    assert receipt.payload["decision"] == "ADMIT"


def test_missing_required_pin_quarantines(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path, required_pins=["manifest_fingerprint", "run_id"])
    envelope = _envelope("evt-3")
    envelope.pop("run_id", None)
    decision, _receipt = gate.admit_push_with_decision(envelope)
    assert decision.decision == "QUARANTINE"
    assert "PINS_MISSING" in decision.reason_codes
