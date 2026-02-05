import json
import os
from pathlib import Path

import pytest

from fraud_detection.ingestion_gate.admission import IngestionGate
from fraud_detection.ingestion_gate.config import WiringProfile
from fraud_detection.ingestion_gate.ops_index import OpsIndex
from fraud_detection.ingestion_gate.store import LocalObjectStore
from fraud_detection.platform_runtime import platform_run_root

RUN_ID = "platform_20260101T000000Z"


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _candidate_sr_roots(repo_root: Path) -> list[Path]:
    roots: list[Path] = []
    env_root = os.getenv("SR_ARTIFACTS_ROOT") or os.getenv("SR_LEDGER_ROOT")
    if env_root:
        roots.append(Path(env_root))
    # repo-local runs default
    run_root = platform_run_root(create_if_missing=False)
    if run_root:
        roots.append(run_root / "sr")
    return roots


def _find_run_facts(root: Path) -> Path | None:
    candidates = list(root.glob("run_facts_view/*.json"))
    return candidates[0] if candidates else None


def _find_run_status(root: Path) -> Path | None:
    candidates = list(root.glob("run_status/*.json"))
    return candidates[0] if candidates else None


def _load_sr_pins(sr_root: Path) -> dict | None:
    facts = _find_run_facts(sr_root)
    if facts and facts.exists():
        payload = json.loads(facts.read_text(encoding="utf-8"))
        return payload.get("pins")
    status = _find_run_status(sr_root)
    if not status or not status.exists():
        return None
    status_payload = json.loads(status.read_text(encoding="utf-8"))
    facts_ref = status_payload.get("facts_view_ref")
    if not facts_ref:
        return None
    facts_path = Path(facts_ref)
    if not facts_path.is_absolute():
        facts_path = sr_root / facts_ref
    if facts_path.exists():
        payload = json.loads(facts_path.read_text(encoding="utf-8"))
        return payload.get("pins")
    return None


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


def test_ops_rebuild_smoke_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("PLATFORM_RUN_ID", RUN_ID)
    pins = None
    for root in _candidate_sr_roots(repo_root):
        if root.exists():
            pins = _load_sr_pins(root)
            if pins:
                break
    if not pins:
        pytest.skip(
            "No SR run_facts_view/run_status found under runs/fraud-platform/<platform_run_id>/sr; "
            "set SR_ARTIFACTS_ROOT to enable smoke test"
        )
    gate = _build_gate(tmp_path)

    envelope = {
        "event_id": (pins.get("run_id") or "smoke") + "-smoke",
        "event_type": "smoke.event",
        "ts_utc": "2026-01-01T00:00:00.000000Z",
        "manifest_fingerprint": pins.get("manifest_fingerprint", "0" * 64),
        "parameter_hash": pins.get("parameter_hash"),
        "seed": pins.get("seed"),
        "run_id": pins.get("run_id"),
        "payload": {"source": "runs_smoke"},
    }

    gate.admit_push(envelope)

    # rebuild into a fresh ops db to simulate loss
    store = LocalObjectStore(tmp_path / "store")
    rebuild_db = tmp_path / "ops_rebuild.db"
    index = OpsIndex(rebuild_db)
    receipts_prefix = f"fraud-platform/{RUN_ID}/ig/receipts"
    quarantine_prefix = f"fraud-platform/{RUN_ID}/ig/quarantine"
    index.rebuild_from_store(store, receipts_prefix=receipts_prefix, quarantine_prefix=quarantine_prefix)

    lookup = index.lookup_event(envelope["event_id"])
    assert lookup is not None
