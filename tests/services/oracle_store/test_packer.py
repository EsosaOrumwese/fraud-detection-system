from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.oracle_store.config import OraclePolicy, OracleProfile, OracleWiring
from fraud_detection.oracle_store.packer import OraclePackError, OraclePackPacker


def _profile(tmp_path: Path) -> OracleProfile:
    wiring = OracleWiring(
        profile_id="local",
        object_store_root=str(tmp_path),
        object_store_endpoint=None,
        object_store_region=None,
        object_store_path_style=None,
        schema_root="docs/model_spec/platform/contracts",
        engine_catalogue_path="docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        gate_map_path="docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        oracle_root=str(tmp_path),
    )
    policy = OraclePolicy(policy_rev="local", require_gate_pass=True)
    return OracleProfile(policy=policy, wiring=wiring)


def _run_facts(pack_root: Path) -> dict:
    locator_path = pack_root / "data/layer2/5B/arrival_events/seed=42/part-000.parquet"
    locator_path.parent.mkdir(parents=True, exist_ok=True)
    locator_path.write_text("dummy", encoding="utf-8")
    return {
        "run_id": "abcd" * 8,
        "pins": {
            "manifest_fingerprint": "c" * 64,
            "parameter_hash": "1" * 64,
            "scenario_id": "baseline_v1",
            "seed": 42,
            "run_id": "abcd" * 8,
        },
        "locators": [
            {
                "output_id": "arrival_events_5B",
                "path": str(locator_path),
                "content_digest": {"algo": "sha256", "hex": "0" * 64},
            }
        ],
        "output_roles": {"arrival_events_5B": "business_traffic"},
        "gate_receipts": [],
        "policy_rev": {"policy_id": "sr_policy", "revision": "v0", "content_digest": "f" * 64},
        "bundle_hash": "a" * 64,
        "plan_ref": "fraud-platform/sr/run_plan/abcd.json",
        "record_ref": "fraud-platform/sr/run_record/abcd.jsonl",
        "status_ref": "fraud-platform/sr/run_status/abcd.json",
    }


def test_packer_writes_manifest_and_seal(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    pack_root = tmp_path / "pack-root"
    pack_root.mkdir(parents=True, exist_ok=True)
    packer = OraclePackPacker(profile)
    facts = _run_facts(pack_root)
    result = packer.seal_from_run_facts(facts, engine_release="engine-test")
    manifest_path = pack_root / "_oracle_pack_manifest.json"
    seal_path = pack_root / "_SEALED.json"
    assert manifest_path.exists()
    assert seal_path.exists()
    assert result["pack_root"].endswith("pack-root")

    # idempotent
    packer.seal_from_run_facts(facts, engine_release="engine-test")


def test_packer_detects_manifest_mismatch(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    pack_root = tmp_path / "pack-root"
    pack_root.mkdir(parents=True, exist_ok=True)
    packer = OraclePackPacker(profile)
    facts = _run_facts(pack_root)
    packer.seal_from_run_facts(facts, engine_release="engine-a")
    with pytest.raises(OraclePackError):
        packer.seal_from_run_facts(facts, engine_release="engine-b")
