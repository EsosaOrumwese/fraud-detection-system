import json
from pathlib import Path

import pytest

from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.ops_index import OpsIndex
from fraud_detection.ingestion_gate.store import LocalObjectStore


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _build_gate(tmp_path: Path, *, deny_on_amber: bool = False) -> IngestionGate:
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
                {"event_type": "test_event", "class": "traffic", "schema_version_required": False},
                {"event_type": "ig.policy.activation", "class": "audit", "schema_version_required": False},
                {"event_type": "ig.quarantine.spike", "class": "audit", "schema_version_required": False},
            ],
        },
    )
    _write_yaml(
        class_map,
        {
            "version": "0.1.0",
            "classes": {
                "traffic": {"required_pins": ["platform_run_id", "scenario_run_id", "manifest_fingerprint"]},
                "audit": {"required_pins": ["platform_run_id", "scenario_run_id", "manifest_fingerprint"]},
            },
            "event_types": {"test_event": "traffic", "ig.policy.activation": "audit", "ig.quarantine.spike": "audit"},
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
    _write_yaml(
        gate_map,
        {
            "version": "1.0",
            "gates": [
                {
                    "gate_id": "gate.test.validation",
                    "authorizes_outputs": ["test_event"],
                    "upstream_gate_dependencies": [],
                    "required_by_components": ["ingestion_gate"],
                }
            ],
        },
    )

    wiring = WiringProfile(
        profile_id="test",
        object_store_root=str(tmp_path / "store"),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        admission_db_path=str(tmp_path / "ig_admission.db"),
        engine_root_path=None,
        health_probe_interval_seconds=0,
        health_bus_probe_mode="none",
        health_deny_on_amber=deny_on_amber,
        health_amber_sleep_seconds=0,
        bus_publish_failure_threshold=2,
        metrics_flush_seconds=0,
        quarantine_spike_threshold=3,
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


def test_replay_duplicate_stability(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    envelope = _envelope("evt-1")

    first = gate.admit_push(envelope)
    eb_ref = first.payload.get("eb_ref") or {}
    assert eb_ref.get("offset_kind") == "file_line"
    assert eb_ref.get("published_at_utc")
    for _ in range(5):
        dup = gate.admit_push(envelope)
        assert dup.payload["decision"] == "DUPLICATE"
        assert dup.payload["eb_ref"] == first.payload["eb_ref"]
        evidence = dup.payload.get("evidence_refs") or []
        assert any(item.get("kind") == "receipt_ref" for item in evidence)

    log_path = tmp_path / "bus" / "fp.bus.traffic.v1" / "partition=0.jsonl"
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 1

    index = OpsIndex(tmp_path / "ig_admission.db")
    lookup = index.lookup_event("evt-1")
    assert lookup is not None
    assert lookup["receipt_id"] == first.payload["receipt_id"]


def test_health_red_blocks_intake(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path, deny_on_amber=True)
    # force bus health unknown -> AMBER -> denied when configured
    gate.health.bus = object()
    with pytest.raises(RuntimeError):
        gate.admit_push(_envelope("evt-2"))


def test_ops_index_rebuild_after_delete(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    gate.admit_push(_envelope("evt-3"))

    store = LocalObjectStore(tmp_path / "store")
    index = OpsIndex(tmp_path / "ops_rebuild.db")
    index.rebuild_from_store(store)
    assert index.lookup_event("evt-3") is not None
