import hashlib
import json
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
    scope: str = "scope_seed_parameter_hash",
    engine_root_path: Path | None = None,
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
                }
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
                    "scope": scope,
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

    wiring = WiringProfile(
        profile_id="test",
        object_store_root=str(tmp_path / "store"),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        admission_db_path=str(tmp_path / "ig_admission.db"),
        sr_ledger_prefix="fraud-platform/sr",
        engine_root_path=str(engine_root_path) if engine_root_path else None,
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


def _write_run_facts(
    tmp_path: Path,
    locator_path: Path,
    *,
    gate_receipts: list[dict],
    instance_receipts: list[dict] | None = None,
) -> Path:
    payload = {
        "run_id": "b" * 32,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "c" * 64,
            "seed": 7,
            "scenario_id": "scenario-1",
            "run_id": "b" * 32,
        },
        "locators": [{"output_id": "test_event", "path": str(locator_path)}],
        "output_roles": {"test_event": "business_traffic"},
        "gate_receipts": gate_receipts,
        "instance_receipts": instance_receipts or [],
        "policy_rev": {"policy_id": "sr_policy", "revision": "v0", "content_digest": "d" * 64},
        "bundle_hash": "e" * 64,
        "plan_ref": "ref/plan",
        "record_ref": "ref/record",
        "status_ref": "ref/status",
    }
    path = tmp_path / "run_facts_view.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_sr_ready(store_root: Path, run_id: str, facts_payload: dict) -> None:
    prefix = store_root / "fraud-platform" / "sr"
    status_path = prefix / "run_status" / f"{run_id}.json"
    facts_path = prefix / "run_facts_view" / f"{run_id}.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    status_payload = {
        "run_id": run_id,
        "state": "READY",
        "updated_at_utc": "2026-01-01T00:00:00Z",
        "record_ref": "ref/record",
        "facts_view_ref": f"fraud-platform/sr/run_facts_view/{run_id}.json",
    }
    status_path.write_text(json.dumps(status_payload), encoding="utf-8")
    facts_path.write_text(json.dumps(facts_payload), encoding="utf-8")


def _write_output(path: Path) -> None:
    rows = [
        {
            "flow_id": "flow-1",
            "ts_utc": "2026-01-01T00:00:00.000000Z",
            "merchant_id": "m-1",
        }
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _write_gate_artifacts(root: Path, manifest_fingerprint: str) -> None:
    bundle_dir = root / "gates" / manifest_fingerprint / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    data_path = bundle_dir / "bundle.txt"
    data = b"gate-bundle"
    data_path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    passed_flag = root / "gates" / manifest_fingerprint / "_passed.flag"
    passed_flag.parent.mkdir(parents=True, exist_ok=True)
    passed_flag.write_text(f"sha256_hex={digest}", encoding="utf-8")


def test_duplicate_does_not_republish(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    envelope = {
        "event_id": "evt-1",
        "event_type": "test_event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "payload": {},
    }

    receipt1 = gate.admit_push(envelope)
    receipt2 = gate.admit_push(envelope)

    assert receipt1.payload["decision"] == "ADMIT"
    assert receipt2.payload["decision"] == "DUPLICATE"
    bus_log = tmp_path / "bus" / "fp.bus.traffic.v1" / "partition=0.jsonl"
    assert bus_log.exists()
    assert len(bus_log.read_text(encoding="utf-8").splitlines()) == 1


def test_missing_gate_receipt_quarantines(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path)
    output_path = tmp_path / "output.jsonl"
    _write_output(output_path)
    run_facts_path = _write_run_facts(tmp_path, output_path, gate_receipts=[])

    receipts = gate.admit_pull(run_facts_path)
    assert receipts == []

    quarantine_dir = tmp_path / "store" / "fraud-platform" / "ig" / "quarantine"
    files = list(quarantine_dir.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert "GATE_MISSING" in payload["reason_codes"]


def test_missing_instance_receipt_quarantines(tmp_path: Path) -> None:
    gate = _build_gate(tmp_path, scope="scope_seed_parameter_hash")
    output_path = tmp_path / "output.jsonl"
    _write_output(output_path)
    gate_receipts = [
        {"gate_id": "gate.test.validation", "status": "PASS", "scope": {"manifest_fingerprint": "a" * 64}},
    ]
    run_facts_path = _write_run_facts(
        tmp_path,
        output_path,
        gate_receipts=gate_receipts,
        instance_receipts=[],
    )

    receipts = gate.admit_pull(run_facts_path)
    assert receipts == []
    quarantine_dir = tmp_path / "store" / "fraud-platform" / "ig" / "quarantine"
    payload = json.loads(list(quarantine_dir.glob("*.json"))[0].read_text(encoding="utf-8"))
    assert "INSTANCE_PROOF_MISSING" in payload["reason_codes"]


def test_push_requires_ready_run(tmp_path: Path) -> None:
    gate = _build_gate(
        tmp_path,
        scope="scope_seed_parameter_hash",
        required_pins=["manifest_fingerprint", "parameter_hash", "seed", "scenario_id", "run_id"],
    )
    envelope = {
        "event_id": "evt-2",
        "event_type": "test_event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "scenario_id": "scenario-1",
        "run_id": "b" * 32,
        "payload": {"flow_id": "flow-1"},
    }

    with pytest.raises(RuntimeError):
        gate.admit_push(envelope)

    facts_payload = {
        "run_id": "b" * 32,
        "pins": {
            "manifest_fingerprint": "a" * 64,
            "parameter_hash": "c" * 64,
            "seed": 7,
            "scenario_id": "scenario-1",
            "run_id": "b" * 32,
        },
        "locators": [],
        "output_roles": {},
        "gate_receipts": [],
        "instance_receipts": [],
        "policy_rev": {"policy_id": "sr_policy", "revision": "v0", "content_digest": "d" * 64},
        "bundle_hash": "e" * 64,
        "plan_ref": "ref/plan",
        "record_ref": "ref/record",
        "status_ref": "ref/status",
    }
    _write_sr_ready(tmp_path / "store", envelope["run_id"], facts_payload)
    receipt = gate.admit_push(envelope)
    assert receipt.payload["decision"] == "ADMIT"


def test_gate_rehash_verification_passes(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine_root"
    _write_gate_artifacts(engine_root, "a" * 64)
    gate = _build_gate(tmp_path, engine_root_path=engine_root)

    output_path = tmp_path / "output.jsonl"
    _write_output(output_path)
    gate_receipts = [
        {"gate_id": "gate.test.validation", "status": "PASS", "scope": {"manifest_fingerprint": "a" * 64}},
    ]
    instance_receipts = [
        {
            "output_id": "test_event",
            "status": "PASS",
            "scope": {"manifest_fingerprint": "a" * 64},
            "target_ref": {"output_id": "test_event", "path": str(output_path)},
            "target_digest": {"algo": "sha256", "hex": "f" * 64},
        }
    ]
    run_facts_path = _write_run_facts(
        tmp_path,
        output_path,
        gate_receipts=gate_receipts,
        instance_receipts=instance_receipts,
    )

    receipts = gate.admit_pull(run_facts_path)
    assert len(receipts) == 1
    assert receipts[0].payload["decision"] == "ADMIT"
