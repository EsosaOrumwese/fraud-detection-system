import json
from pathlib import Path

from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile


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
    _write_yaml(catalogue, {"version": "1.0", "outputs": []})
    _write_yaml(gate_map, {"version": "1.0", "gates": []})

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
    )
    return IngestionGate.build(wiring)


def test_run_facts_s3_ref(monkeypatch, tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    payload = {
        "pins": {"manifest_fingerprint": "a" * 64, "run_id": "a" * 32},
        "output_roles": {},
        "locators": [],
        "gate_receipts": [],
        "instance_receipts": [],
    }

    class _Body:
        def read(self):
            return json.dumps(payload, ensure_ascii=True).encode("utf-8")

    class _Client:
        def get_object(self, Bucket, Key):
            return {"Body": _Body()}

    def _client(*args, **kwargs):
        return _Client()

    import boto3

    monkeypatch.setattr(boto3, "client", _client)
    status = gate.admit_pull_with_state("s3://bucket/run_facts.json", run_id="a" * 32, message_id="m1")
    assert status["status"] in {"COMPLETED", "PARTIAL"}
