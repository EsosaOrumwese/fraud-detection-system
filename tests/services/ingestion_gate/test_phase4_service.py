import json
from pathlib import Path

from fraud_detection.ingestion_gate.service import create_app


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_profile(tmp_path: Path) -> Path:
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

    profile = {
        "profile_id": "test",
        "policy": {
            "policy_rev": "test-v0",
            "partitioning_profiles_ref": str(partitioning),
            "partitioning_profile_id": "ig.partitioning.v0.traffic",
            "schema_policy_ref": str(schema_policy),
            "class_map_ref": str(class_map),
        },
        "wiring": {
            "object_store": {"root": str(tmp_path / "store")},
            "admission_db_path": str(tmp_path / "ig_admission.db"),
            "sr_ledger_prefix": "fraud-platform/sr",
            "schema_root": "docs/model_spec/platform/contracts",
            "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
            "engine_catalogue_path": str(catalogue),
            "gate_map_path": str(gate_map),
            "event_bus_path": str(tmp_path / "bus"),
            "control_bus": {"kind": "file", "root": str(tmp_path / "control_bus"), "topic": "fp.bus.control.v1"},
        },
    }
    profile_path = tmp_path / "profile.yaml"
    _write_yaml(profile_path, profile)
    return profile_path


def _write_run_facts(tmp_path: Path, run_id: str) -> str:
    store_root = tmp_path / "store"
    output_path = tmp_path / "data" / "test_event" / "part.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([{"flow_id": "1", "ts_utc": "2026-01-01T00:00:00.000000Z"}], ensure_ascii=True),
        encoding="utf-8",
    )
    run_facts_ref = f"fraud-platform/sr/run_facts_view/{run_id}.json"
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
    return run_facts_ref


def test_service_push_and_pull(tmp_path: Path) -> None:
    profile_path = _write_profile(tmp_path)
    app = create_app(str(profile_path))
    client = app.test_client()

    envelope = {
        "event_id": "evt-1",
        "event_type": "test_event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "payload": {"flow_id": "evt-1"},
    }
    push_resp = client.post("/v1/ingest/push", json=envelope)
    assert push_resp.status_code == 200
    assert push_resp.get_json()["decision"] == "ADMIT"

    run_id = "b" * 32
    run_facts_ref = _write_run_facts(tmp_path, run_id)
    pull_resp = client.post("/v1/ingest/pull", json={"run_facts_ref": run_facts_ref, "run_id": run_id})
    assert pull_resp.status_code == 200
    assert pull_resp.get_json()["status"] in {"COMPLETED", "PARTIAL"}
