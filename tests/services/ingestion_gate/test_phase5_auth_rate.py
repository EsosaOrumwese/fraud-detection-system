from pathlib import Path

import pytest
import werkzeug

from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.security import build_service_token
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
            "classes": {"traffic": {"required_pins": ["platform_run_id", "scenario_run_id", "manifest_fingerprint"]}},
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
            "schema_root": "docs/model_spec/platform/contracts",
            "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
            "engine_catalogue_path": str(files["catalogue"]),
            "gate_map_path": str(files["gate_map"]),
            "event_bus_path": str(tmp_path / "bus"),
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
        "platform_run_id": "platform_20260101T000000Z",
        "scenario_run_id": "b" * 32,
        "run_id": "b" * 32,
        "payload": {"flow_id": event_id},
    }


def _test_client(app):
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3"
    return app.test_client()


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
    client = _test_client(app)

    resp = client.post("/v1/ingest/push", json=_envelope("evt-1"))
    assert resp.status_code == 401

    resp_ok = client.post("/v1/ingest/push", json=_envelope("evt-2"), headers={"X-IG-Api-Key": "key-1"})
    assert resp_ok.status_code == 200
    assert resp_ok.get_json()["decision"] == "ADMIT"
    actor = resp_ok.get_json()["receipt"].get("actor")
    assert actor is not None
    assert actor["actor_id"] == "SYSTEM::key-1"
    assert actor["source_type"] == "SYSTEM"


def test_push_accepts_service_token_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IG_SERVICE_TOKEN_SECRETS", "test-secret-1")
    profile_path = _write_profile(
        tmp_path,
        security={
            "auth_mode": "service_token",
            "api_key_header": "X-IG-Service-Token",
            "auth_allowlist": ["world_stream_producer"],
            "service_token_secrets_env": "IG_SERVICE_TOKEN_SECRETS",
        },
    )
    token = build_service_token("world_stream_producer", "test-secret-1")
    app = create_app(str(profile_path))
    client = _test_client(app)

    denied = client.post("/v1/ingest/push", json=_envelope("evt-token-denied"))
    assert denied.status_code == 401

    admitted = client.post(
        "/v1/ingest/push",
        json=_envelope("evt-token-ok"),
        headers={"X-IG-Service-Token": token},
    )
    assert admitted.status_code == 200
    receipt = admitted.get_json()["receipt"]
    actor = receipt.get("actor")
    assert actor is not None
    assert actor["actor_id"] == "SYSTEM::world_stream_producer"
    assert actor["source_type"] == "SYSTEM"


def test_push_rate_limit(tmp_path: Path) -> None:
    profile_path = _write_profile(
        tmp_path,
        security={"push_rate_limit_per_minute": 1},
    )
    app = create_app(str(profile_path))
    client = _test_client(app)

    first = client.post("/v1/ingest/push", json=_envelope("evt-10"))
    assert first.status_code == 200
    second = client.post("/v1/ingest/push", json=_envelope("evt-11"))
    assert second.status_code == 429


def test_profile_rejects_legacy_pull_wiring(tmp_path: Path) -> None:
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
            "schema_root": "docs/model_spec/platform/contracts",
            "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
            "engine_catalogue_path": str(files["catalogue"]),
            "gate_map_path": str(files["gate_map"]),
            "event_bus_path": str(tmp_path / "bus"),
            "ready_lease": {"backend": "postgres"},
        },
    }
    profile_path = tmp_path / "profile.yaml"
    _write_yaml(profile_path, profile)
    with pytest.raises(ValueError) as excinfo:
        WiringProfile.load(profile_path)
    assert "PULL_WIRING_DEPRECATED" in str(excinfo.value)
