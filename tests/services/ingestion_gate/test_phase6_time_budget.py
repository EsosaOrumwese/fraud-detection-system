import json
from pathlib import Path

import pytest

from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _build_gate(tmp_path: Path, *, pull_time_budget_seconds: float) -> tuple[IngestionGate, str]:
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
                    "path_template": "data/test_event/part.jsonl",
                    "primary_key": ["flow_id"],
                    "read_requires_gates": [],
                    "scope": "scope_seed_parameter_hash",
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
                    "passed_flag_path_template": "gates/{manifest_fingerprint}/_passed.flag",
                    "bundle_root_template": "gates/{manifest_fingerprint}/bundle",
                    "verification_method": {
                        "kind": "sha256_bundle_digest",
                        "digest_field": "sha256_hex",
                        "ordering": "ascii_lex",
                        "exclude_filenames": [],
                    },
                }
            ],
        },
    )

    store_root = tmp_path / "store"
    run_id = "b" * 32
    run_facts = {
        "run_id": run_id,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "c" * 64,
            "seed": 7,
            "scenario_id": "scenario-1",
            "run_id": run_id,
        },
        "locators": [
            {"output_id": "test_event", "path": str(tmp_path / "output.jsonl")},
        ],
        "output_roles": {"test_event": "business_traffic"},
        "gate_receipts": [],
        "instance_receipts": [],
        "policy_rev": {"policy_id": "sr_policy", "revision": "v0", "content_digest": "d" * 64},
        "bundle_hash": "e" * 64,
        "plan_ref": "ref/plan",
        "record_ref": "ref/record",
        "status_ref": "ref/status",
    }
    run_facts_path = store_root / "fraud-platform" / "sr" / "run_facts_view" / f"{run_id}.json"
    run_facts_path.parent.mkdir(parents=True, exist_ok=True)
    run_facts_path.write_text(json.dumps(run_facts), encoding="utf-8")

    wiring = WiringProfile(
        profile_id="test",
        object_store_root=str(store_root),
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
        pull_time_budget_seconds=pull_time_budget_seconds,
    )
    return IngestionGate.build(wiring), run_id


def test_pull_time_budget_exceeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate, run_id = _build_gate(tmp_path, pull_time_budget_seconds=0.1)
    facts_ref = f"fraud-platform/sr/run_facts_view/{run_id}.json"

    values = iter([100.0, 100.2, 100.3])
    monkeypatch.setattr(
        "fraud_detection.ingestion_gate.admission.time.monotonic",
        lambda: next(values, 100.3),
    )

    status = gate.admit_pull_with_state(facts_ref, run_id=run_id, message_id="msg-1")

    assert status["status"] == "PARTIAL"
    assert status["outputs_failed"]
    assert status["outputs_failed"][0]["reason_code"] == "TIME_BUDGET_EXCEEDED"
