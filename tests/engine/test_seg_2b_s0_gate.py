import hashlib
import json
from pathlib import Path

import pytest

from engine.layers.l1.seg_2B.s0_gate import GateInputs, S0GateRunner
from engine.layers.l1.seg_2B.s0_gate.exceptions import S0GateError


def _write_validation_bundle(base: Path, manifest: str) -> Path:
    bundle_dir = base / f"data/layer1/1B/validation/fingerprint={manifest}/bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    payload_path = bundle_dir / "payload.txt"
    payload_path.write_text("payload", encoding="utf-8")
    index_payload = {
        "artifacts": [
            {"artifact_id": "bundle_payload", "path": "payload.txt"},
            {"artifact_id": "bundle_index", "path": "index.json"},
        ]
    }
    index_path = bundle_dir / "index.json"
    index_path.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")
    digest = hashlib.sha256()
    for relative in ("index.json", "payload.txt"):
        digest.update((bundle_dir / relative).read_bytes())
    (bundle_dir / "_passed.flag").write_text(
        f"sha256_hex = {digest.hexdigest()}\n", encoding="utf-8"
    )
    return bundle_dir


def _write_site_locations(base: Path, seed: int, manifest: str) -> Path:
    path = (
        base
        / f"data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("site-locations", encoding="utf-8")
    return path


def _write_dictionary(tmp_path: Path, manifest: str) -> Path:
    dictionary_yaml = f"""
version: 'test'
catalogue:
  dictionary_version: 'test'
  registry_version: 'test'
reference_data:
  - id: site_locations
    path: data/layer1/1B/site_locations/seed={{seed}}/fingerprint={{manifest_fingerprint}}/
    partitioning: [seed, fingerprint]
    version: "{{{{seed}}}}.{{{{manifest_fingerprint}}}}"
    schema_ref: schemas.1B.yaml#/egress/site_locations
policies:
  - id: route_rng_policy_v1
    path: config/layer1/2B/policy/route_rng_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/route_rng_policy_v1
    partitioning: []
    version: "2025.11"
  - id: alias_layout_policy_v1
    path: config/layer1/2B/policy/alias_layout_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/alias_layout_policy_v1
    partitioning: []
    version: "2025.11"
  - id: day_effect_policy_v1
    path: config/layer1/2B/policy/day_effect_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/day_effect_policy_v1
    partitioning: []
    version: "2025.11"
  - id: virtual_edge_policy_v1
    path: config/layer1/2B/policy/virtual_edge_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/virtual_edge_policy_v1
    partitioning: []
    version: "2025.11"
datasets:
  - id: validation_bundle_1B
    path: data/layer1/1B/validation/fingerprint={{manifest_fingerprint}}/bundle
    partitioning: [fingerprint]
    version: "{{{{manifest_fingerprint}}}}"
    schema_ref: schemas.1B.yaml#/validation/validation_bundle_1B
  - id: validation_passed_flag_1B
    path: data/layer1/1B/validation/fingerprint={{manifest_fingerprint}}/_passed.flag
    partitioning: [fingerprint]
    version: "{{{{manifest_fingerprint}}}}"
    schema_ref: schemas.layer1.yaml#/validation/passed_flag
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={{manifest_fingerprint}}/s0_gate_receipt.json
    partitioning: [fingerprint]
    version: "{{{{manifest_fingerprint}}}}"
    schema_ref: schemas.2B.yaml#/validation/s0_gate_receipt_v1
  - id: sealed_inputs_v1
    path: data/layer1/2B/sealed_inputs/fingerprint={{manifest_fingerprint}}/sealed_inputs_v1.json
    partitioning: [fingerprint]
    version: "{{{{manifest_fingerprint}}}}"
    schema_ref: schemas.2B.yaml#/validation/sealed_inputs_v1
"""
    dictionary_path = tmp_path / "dictionary.yaml"
    dictionary_path.write_text(dictionary_yaml.strip(), encoding="utf-8")
    return dictionary_path


def test_gate_runner_writes_receipt_and_inventory(tmp_path: Path) -> None:
    manifest = "a" * 64
    seed = 2025110601
    bundle_dir = _write_validation_bundle(tmp_path, manifest)
    _write_site_locations(tmp_path, seed, manifest)
    dictionary_path = _write_dictionary(tmp_path, manifest)

    runner = S0GateRunner()
    result = runner.run(
        GateInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            seg2a_manifest_fingerprint="f" * 64,
            parameter_hash="b" * 64,
            git_commit_hex="c" * 40,
            dictionary_path=dictionary_path,
            validation_bundle_path=bundle_dir,
        )
    )

    receipt_payload = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt_payload["manifest_fingerprint"] == manifest
    assert receipt_payload["parameter_hash"] == "b" * 64
    assert receipt_payload["flag_sha256_hex"] == result.flag_sha256_hex
    assert len(receipt_payload["sealed_inputs"]) >= 5

    inventory_rows = json.loads(result.inventory_path.read_text(encoding="utf-8"))
    asset_ids = [row["asset_id"] for row in inventory_rows]
    assert "site_locations" in asset_ids
    for policy_id in _REQUIRED_POLICY_IDS:
        assert policy_id in asset_ids

    report_path = (
        tmp_path
        / "reports"
        / "l1"
        / "s0_gate"
        / f"fingerprint={manifest}"
        / "run_report.json"
    )
    assert report_path.exists()
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["component"] == "2B.S0"
    assert report_payload["gate"]["bundle_index_count"] == 2
    assert len(report_payload["validators"]) == 16
    assert report_payload["summary"]["overall_status"] == "PASS"


def test_gate_runner_detects_flag_mismatch(tmp_path: Path) -> None:
    manifest = "b" * 64
    seed = 2025110601
    bundle_dir = _write_validation_bundle(tmp_path, manifest)
    # Corrupt the flag
    (bundle_dir / "_passed.flag").write_text("sha256_hex = " + "0" * 64 + "\n", encoding="utf-8")
    _write_site_locations(tmp_path, seed, manifest)
    dictionary_path = _write_dictionary(tmp_path, manifest)

    runner = S0GateRunner()
    with pytest.raises(S0GateError) as excinfo:
        runner.run(
            GateInputs(
                data_root=tmp_path,
                seed=seed,
                manifest_fingerprint=manifest,
                seg2a_manifest_fingerprint="f" * 64,
                parameter_hash="d" * 64,
                git_commit_hex="e" * 40,
                dictionary_path=dictionary_path,
                validation_bundle_path=bundle_dir,
            )
        )
    assert excinfo.value.code == "2B-S0-011"


# Required policy IDs (kept in sync with runner constant)
_REQUIRED_POLICY_IDS = (
    "route_rng_policy_v1",
    "alias_layout_policy_v1",
    "day_effect_policy_v1",
    "virtual_edge_policy_v1",
)
