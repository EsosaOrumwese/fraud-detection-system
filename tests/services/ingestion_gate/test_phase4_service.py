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
            "schema_root": "docs/model_spec/platform/contracts",
            "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
            "engine_catalogue_path": str(catalogue),
            "gate_map_path": str(gate_map),
            "event_bus_path": str(tmp_path / "bus"),
        },
    }
    profile_path = tmp_path / "profile.yaml"
    _write_yaml(profile_path, profile)
    return profile_path


def test_service_push_only(tmp_path: Path) -> None:
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
