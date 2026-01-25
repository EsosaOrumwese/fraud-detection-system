import json
from pathlib import Path

from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.control_bus import FileControlBusReader, ReadyConsumer
from fraud_detection.ingestion_gate.pull_state import PullRunStore
from fraud_detection.ingestion_gate.schemas import SchemaRegistry


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _build_gate(tmp_path: Path) -> IngestionGate:
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
    _write_yaml(
        gate_map,
        {
            "version": "1.0",
            "gates": [],
        },
    )

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
        engine_catalogue_path=str(catalogue),
        gate_map_path=str(gate_map),
        partitioning_profiles_ref=str(partitioning),
        partitioning_profile_id="ig.partitioning.v0.traffic",
        schema_policy_ref=str(schema_policy),
        class_map_ref=str(class_map),
        policy_rev="test-v0",
        event_bus_kind="file",
        event_bus_path=str(tmp_path / "bus"),
        control_bus_kind="file",
        control_bus_root=str(tmp_path / "control_bus"),
        control_bus_topic="fp.bus.control.v1",
    )
    return IngestionGate.build(wiring)


def test_ready_consumer_processes_ready(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    store_root = Path(tmp_path / "store")
    run_id = "a" * 32
    run_facts_ref = f"fraud-platform/sr/run_facts_view/{run_id}.json"

    output_path = tmp_path / "data" / "test_event" / "part.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([{"flow_id": "1", "ts_utc": "2026-01-01T00:00:00.000000Z"}], ensure_ascii=True),
        encoding="utf-8",
    )

    run_facts = {
        "pins": {"manifest_fingerprint": "a" * 64, "run_id": run_id},
        "output_roles": {"test_event": "business_traffic"},
        "locators": [{"output_id": "test_event", "path": str(output_path)}],
        "gate_receipts": [],
        "instance_receipts": [],
    }
    facts_path = store_root / run_facts_ref
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.write_text(json.dumps(run_facts, ensure_ascii=True), encoding="utf-8")

    control_root = Path(tmp_path / "control_bus" / "fp.bus.control.v1")
    control_root.mkdir(parents=True, exist_ok=True)
    message_id = "msg-1"
    ready_payload = {"run_id": run_id, "facts_view_ref": run_facts_ref, "bundle_hash": "b" * 64}
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
    assert result[0]["status"] in {"COMPLETED", "PARTIAL"}
    status_path = store_root / f"fraud-platform/ig/pull_runs/run_id={run_id}.json"
    assert status_path.exists()

    second = consumer.poll_once()
    assert second[0]["status"] == "SKIPPED_DUPLICATE"
