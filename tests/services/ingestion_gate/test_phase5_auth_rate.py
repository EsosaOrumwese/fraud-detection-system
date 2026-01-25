import json
from pathlib import Path

import pytest

from fraud_detection.ingestion_gate.control_bus import FileControlBusReader, ReadyConsumer
from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.pull_state import PullRunStore
from fraud_detection.ingestion_gate.schemas import SchemaRegistry
from fraud_detection.ingestion_gate.service import create_app


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _base_profile_files(tmp_path: Path) -> dict[str, Path]:
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
            "policies": [{"event_type": "test_event", "class": "traffic", "schema_version_required": False}],
        },
    )
    _write_yaml(
        class_map,
        {
            "version": "0.1.0",
            "classes": {"traffic": {"required_pins": ["manifest_fingerprint"]}},
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
                    "path_template": "data/test_event/part.json",
                    "primary_key": ["flow_id"],
                    "read_requires_gates": [],
                    "scope": "scope_manifest_fingerprint",
                }
            ],
        },
    )
    _write_yaml(gate_map, {"version": "1.0", "gates": []})
    return {
        "schema_policy": schema_policy,
        "class_map": class_map,
        "partitioning": partitioning,
        "catalogue": catalogue,
        "gate_map": gate_map,
    }


def _write_profile(tmp_path: Path, security: dict | None = None) -> Path:
    files = _base_profile_files(tmp_path)
    profile = {
        "profile_id": "test",
        "policy": {
            "policy_rev": "test-v0",
            "partitioning_profiles_ref": str(files["partitioning"]),
            "partitioning_profile_id": "ig.partitioning.v0.traffic",
            "schema_policy_ref": str(files["schema_policy"]),
            "class_map_ref": str(files["class_map"]),
        },
        "wiring": {
            "object_store": {"root": str(tmp_path / "store")},
            "admission_db_path": str(tmp_path / "ig_admission.db"),
            "sr_ledger_prefix": "fraud-platform/sr",
            "schema_root": "docs/model_spec/platform/contracts",
            "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
            "engine_catalogue_path": str(files["catalogue"]),
            "gate_map_path": str(files["gate_map"]),
            "event_bus_path": str(tmp_path / "bus"),
            "control_bus": {"kind": "file", "root": str(tmp_path / "control_bus"), "topic": "fp.bus.control.v1"},
        },
    }
    if security:
        profile["wiring"]["security"] = security
    profile_path = tmp_path / "profile.yaml"
    _write_yaml(profile_path, profile)
    return profile_path


def _envelope(event_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "test_event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "payload": {"flow_id": event_id},
    }


def test_push_requires_api_key(tmp_path: Path) -> None:
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("key-1\n", encoding="utf-8")
    profile_path = _write_profile(
        tmp_path,
        security={
            "auth_mode": "api_key",
            "api_key_header": "X-IG-Api-Key",
            "auth_allowlist_ref": str(allowlist),
        },
    )
    app = create_app(str(profile_path))
    client = app.test_client()

    resp = client.post("/v1/ingest/push", json=_envelope("evt-1"))
    assert resp.status_code == 401

    resp_ok = client.post("/v1/ingest/push", json=_envelope("evt-2"), headers={"X-IG-Api-Key": "key-1"})
    assert resp_ok.status_code == 200
    assert resp_ok.get_json()["decision"] == "ADMIT"


def test_push_rate_limit(tmp_path: Path) -> None:
    profile_path = _write_profile(
        tmp_path,
        security={"push_rate_limit_per_minute": 1},
    )
    app = create_app(str(profile_path))
    client = app.test_client()

    first = client.post("/v1/ingest/push", json=_envelope("evt-10"))
    assert first.status_code == 200
    second = client.post("/v1/ingest/push", json=_envelope("evt-11"))
    assert second.status_code == 429


def test_ready_allowlist_blocks(tmp_path: Path) -> None:
    files = _base_profile_files(tmp_path)
    wiring = WiringProfile(
        profile_id="test",
        object_store_root=str(tmp_path / "store"),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        admission_db_path=str(tmp_path / "ig_admission.db"),
        sr_ledger_prefix="fraud-platform/sr",
        engine_root_path=None,
        health_probe_interval_seconds=0,
        health_deny_on_amber=False,
        health_amber_sleep_seconds=0,
        bus_publish_failure_threshold=2,
        metrics_flush_seconds=0,
        quarantine_spike_threshold=3,
        quarantine_spike_window_seconds=60,
        schema_root="docs/model_spec/platform/contracts",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        engine_catalogue_path=str(files["catalogue"]),
        gate_map_path=str(files["gate_map"]),
        partitioning_profiles_ref=str(files["partitioning"]),
        partitioning_profile_id="ig.partitioning.v0.traffic",
        schema_policy_ref=str(files["schema_policy"]),
        class_map_ref=str(files["class_map"]),
        policy_rev="test-v0",
        event_bus_kind="file",
        event_bus_path=str(tmp_path / "bus"),
        control_bus_kind="file",
        control_bus_root=str(tmp_path / "control_bus"),
        control_bus_topic="fp.bus.control.v1",
        ready_allowlist_run_ids=["allowed"],
    )
    gate = IngestionGate.build(wiring)

    run_id = "b" * 32
    control_root = Path(tmp_path / "control_bus" / "fp.bus.control.v1")
    control_root.mkdir(parents=True, exist_ok=True)
    message_id = "msg-1"
    ready_payload = {"run_id": run_id, "facts_view_ref": "fraud-platform/sr/run_facts_view/x.json", "bundle_hash": "b" * 64}
    envelope = {
        "topic": "fp.bus.control.v1",
        "message_id": message_id,
        "published_at_utc": "2026-01-01T00:00:00.000000Z",
        "attributes": {},
        "partition_key": run_id,
        "payload": ready_payload,
    }
    (control_root / f"{message_id}.json").write_text(json.dumps(envelope, ensure_ascii=True), encoding="utf-8")
    registry = SchemaRegistry(Path("docs/model_spec/platform/contracts/scenario_runner"))
    reader = FileControlBusReader(Path(tmp_path / "control_bus"), "fp.bus.control.v1", registry=registry)
    consumer = ReadyConsumer(gate, reader, PullRunStore(gate.store))
    result = consumer.poll_once()
    assert result[0]["status"] == "SKIPPED_UNAUTHORIZED"
