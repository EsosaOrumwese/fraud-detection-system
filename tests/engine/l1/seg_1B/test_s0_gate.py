from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B.s0_gate import GateInputs, S0GateRunner
from engine.layers.l1.seg_1B.s0_gate.l0.bundle import compute_index_digest, load_index
from engine.layers.l1.seg_1B.s0_gate.exceptions import S0GateError


FINGERPRINT = "a" * 64
PARAM_HASH = "b" * 64
SEED = "12345"


def _baseline_dictionary() -> dict:
    return {
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical/iso.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
            },
            "world_countries": {
                "path": "reference/spatial/world_countries/world.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/world_countries",
            },
            "population_raster_2025": {
                "path": "reference/spatial/population/population.tif",
                "schema_ref": "schemas.ingress.layer1.yaml#/population_raster_2025",
            },
            "tz_world_2025a": {
                "path": "reference/spatial/tz_world/tz.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/tz_world_2025a",
            },
            "validation_bundle_1A": {
                "path": "data/layer1/1A/validation/fingerprint={manifest_fingerprint}/",
                "schema_ref": "schemas.1A.yaml#/validation/validation_bundle",
            },
            "outlet_catalogue": {
                "path": "data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/",
                "schema_ref": "schemas.1A.yaml#/egress/outlet_catalogue",
            },
            "s3_candidate_set": {
                "path": "data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/s3.parquet",
                "schema_ref": "schemas.1A.yaml#/s3/candidate_set",
            },
        },
        "datasets": {
            "s0_gate_receipt_1B": {
                "path": "data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json",
                "schema_ref": "schemas.1B.yaml#/validation/s0_gate_receipt",
            }
        },
    }


def _create_validation_bundle(bundle_dir: Path) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "MANIFEST.json").write_text("{}", encoding="utf-8")
    index_payload = [
        {"artifact_id": "manifest", "kind": "text", "path": "MANIFEST.json"},
        {"artifact_id": "index", "kind": "index", "path": "index.json"},
    ]
    (bundle_dir / "index.json").write_text(json.dumps(index_payload, indent=2), encoding="utf-8")

    index = load_index(bundle_dir)
    digest = compute_index_digest(bundle_dir, index)
    (bundle_dir / "_passed.flag").write_text(f"sha256_hex = {digest}\n", encoding="utf-8")


def _create_outlet_catalogue(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "legal_country_iso": ["GB", "GB"],
            "site_order": [0, 1],
            "manifest_fingerprint": [FINGERPRINT, FINGERPRINT],
            "global_seed": [int(SEED), int(SEED)],
        }
    )
    frame.write_parquet(path / "part-00000.parquet")


def _touch_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"stub")


def prepare_environment(tmp_path: Path) -> tuple[GateInputs, dict, Path]:
    base_dict = _baseline_dictionary()
    base_path = tmp_path
    output_path = tmp_path

    bundle_dir = base_path / f"data/layer1/1A/validation/fingerprint={FINGERPRINT}"
    _create_validation_bundle(bundle_dir)

    outlet_path = base_path / f"data/layer1/1A/outlet_catalogue/seed={SEED}/fingerprint={FINGERPRINT}"
    _create_outlet_catalogue(outlet_path)

    s3_path = (
        base_path / f"data/layer1/1A/s3_candidate_set/parameter_hash={PARAM_HASH}/s3.parquet"
    )
    _touch_reference(s3_path)
    _touch_reference(base_path / "reference/iso/iso3166_canonical/iso.parquet")
    _touch_reference(base_path / "reference/spatial/world_countries/world.parquet")
    _touch_reference(base_path / "reference/spatial/population/population.tif")
    _touch_reference(base_path / "reference/spatial/tz_world/tz.parquet")

    inputs = GateInputs(
        base_path=base_path,
        output_base_path=output_path,
        manifest_fingerprint=FINGERPRINT,
        seed=SEED,
        parameter_hash=PARAM_HASH,
        dictionary=base_dict,
    )
    return inputs, base_dict, bundle_dir


def test_gate_success(tmp_path: Path) -> None:
    inputs, dictionary, bundle_dir = prepare_environment(tmp_path)
    runner = S0GateRunner()
    result = runner.run(inputs)

    assert result.receipt_path.exists()
    payload = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert payload["manifest_fingerprint"] == FINGERPRINT
    expected_digest = compute_index_digest(bundle_dir, load_index(bundle_dir))
    assert payload["flag_sha256_hex"] == expected_digest
    sealed_ids = {item["id"] for item in payload["sealed_inputs"]}
    assert {"outlet_catalogue", "s3_candidate_set"} <= sealed_ids


def test_gate_fails_on_hash_mismatch(tmp_path: Path) -> None:
    inputs, _, _ = prepare_environment(tmp_path)
    flag_path = inputs.base_path / f"data/layer1/1A/validation/fingerprint={FINGERPRINT}/_passed.flag"
    flag_path.write_text("sha256_hex = " + "0" * 64, encoding="utf-8")

    runner = S0GateRunner()
    with pytest.raises(S0GateError) as caught:
        runner.run(inputs)
    assert caught.value.context.code == "E_FLAG_HASH_MISMATCH"


def test_gate_is_idempotent(tmp_path: Path) -> None:
    inputs, _, _ = prepare_environment(tmp_path)
    runner = S0GateRunner()
    first = runner.run(inputs)
    second = runner.run(inputs)
    assert first.receipt_path == second.receipt_path


def test_gate_detects_receipt_mismatch(tmp_path: Path) -> None:
    inputs, _, _ = prepare_environment(tmp_path)
    receipt_path = (
        inputs.output_base_path
        / f"data/layer1/1B/s0_gate_receipt/fingerprint={FINGERPRINT}/s0_gate_receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("{}", encoding="utf-8")

    runner = S0GateRunner()
    with pytest.raises(S0GateError) as caught:
        runner.run(inputs)
    assert caught.value.context.code == "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL"
