from __future__ import annotations

from pathlib import Path
import json

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


def _write_run_receipt(pack_root: Path) -> None:
    receipt = {
        "manifest_fingerprint": "c" * 64,
        "parameter_hash": "1" * 64,
        "seed": 42,
        "run_id": "abcd" * 8,
    }
    (pack_root / "run_receipt.json").write_text(
        json.dumps(receipt, sort_keys=True), encoding="utf-8"
    )


def test_packer_writes_manifest_and_seal(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    pack_root = tmp_path / "pack-root"
    pack_root.mkdir(parents=True, exist_ok=True)
    packer = OraclePackPacker(profile)
    _write_run_receipt(pack_root)
    result = packer.seal_from_engine_run(
        str(pack_root), scenario_id="baseline_v1", engine_release="engine-test"
    )
    manifest_path = pack_root / "_oracle_pack_manifest.json"
    seal_path = pack_root / "_SEALED.json"
    assert manifest_path.exists()
    assert seal_path.exists()
    assert result["pack_root"].endswith("pack-root")

    # idempotent
    packer.seal_from_engine_run(
        str(pack_root), scenario_id="baseline_v1", engine_release="engine-test"
    )


def test_packer_detects_manifest_mismatch(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    pack_root = tmp_path / "pack-root"
    pack_root.mkdir(parents=True, exist_ok=True)
    packer = OraclePackPacker(profile)
    _write_run_receipt(pack_root)
    packer.seal_from_engine_run(
        str(pack_root), scenario_id="baseline_v1", engine_release="engine-a"
    )
    with pytest.raises(OraclePackError):
        packer.seal_from_engine_run(
            str(pack_root), scenario_id="baseline_v1", engine_release="engine-b"
        )
