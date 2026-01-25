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


def _find_run_receipt(root: Path) -> Path | None:
    matches = list(root.glob("runs/**/run_receipt.json"))
    return matches[0] if matches else None


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
            "policies": [{"event_type": "smoke.event", "class": "traffic", "schema_version_required": False}],
        },
    )
    _write_yaml(
        class_map,
        {
            "version": "0.1.0",
            "classes": {"traffic": {"required_pins": ["manifest_fingerprint"]}},
            "event_types": {"smoke.event": "traffic"},
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
            "outputs": [],
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
        profile_id="smoke",
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
        quarantine_spike_threshold=5,
        quarantine_spike_window_seconds=60,
        schema_root="docs/model_spec/platform/contracts",
        engine_contracts_root="docs/model_spec/data-engine/interface_pack/contracts",
        engine_catalogue_path=str(catalogue),
        gate_map_path=str(gate_map),
        partitioning_profiles_ref=str(partitioning),
        partitioning_profile_id="ig.partitioning.v0.traffic",
        schema_policy_ref=str(schema_policy),
        class_map_ref=str(class_map),
        policy_rev="smoke-v0",
        event_bus_kind="file",
        event_bus_path=str(tmp_path / "bus"),
    )
    return IngestionGate.build(wiring)


def test_ops_rebuild_smoke_runs(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    run_receipt = _find_run_receipt(repo_root)
    if run_receipt is None:
        pytest.skip("No runs/**/run_receipt.json found for smoke test")

    receipt = json.loads(run_receipt.read_text(encoding="utf-8"))
    gate = _build_gate(tmp_path)

    envelope = {
        "event_id": receipt.get("run_id", "smoke") + "-smoke",
        "event_type": "smoke.event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": receipt.get("manifest_fingerprint", "0" * 64),
        "parameter_hash": receipt.get("parameter_hash"),
        "seed": receipt.get("seed"),
        "run_id": receipt.get("run_id"),
        "payload": {"source": "runs_smoke"},
    }

    gate.admit_push(envelope)

    # rebuild into a fresh ops db to simulate loss
    store = LocalObjectStore(tmp_path / "store")
    rebuild_db = tmp_path / "ops_rebuild.db"
    index = OpsIndex(rebuild_db)
    index.rebuild_from_store(store)

    lookup = index.lookup_event(envelope["event_id"])
    assert lookup is not None
