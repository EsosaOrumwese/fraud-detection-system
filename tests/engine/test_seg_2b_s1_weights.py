import json
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_2B.s1_weights import S1WeightsInputs, S1WeightsRunner


def _write_dictionary(path: Path) -> Path:
    payload = """
version: test
catalogue:
  dictionary_version: test
  registry_version: test
datasets:
  - id: site_locations
    path: data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.1B.yaml#/egress/site_locations
  - id: s1_site_weights
    path: data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s1_site_weights
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/s0_gate_receipt_v1
policies:
  - id: alias_layout_policy_v1
    path: contracts/policies/l1/seg_2B/alias_layout_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/alias_layout_policy_v1
"""
    dictionary_path = path / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _write_site_locations(base: Path, seed: int, manifest: str) -> Path:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1, 2],
            "legal_country_iso": ["US", "US", "GB"],
            "site_order": [1, 2, 1],
        }
    )
    dest = base / f"data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)
    return dest


def _write_policy(base: Path) -> Path:
    payload = {
        "version_tag": "test",
        "weight_source": {"id": "uniform", "mode": "uniform"},
        "floor_spec": {"mode": "absolute", "value": 0.0, "fallback": "uniform"},
        "cap_spec": {"mode": "none"},
        "normalisation_epsilon": 1e-12,
        "quantised_bits": 16,
        "quantisation_epsilon": 1e-9,
        "tiny_negative_epsilon": 1e-15,
    }
    path = base / "contracts/policies/l1/seg_2B/alias_layout_policy_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_receipt(base: Path, seed: int, manifest: str) -> Path:
    payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": "f" * 64,
        "validation_bundle_path": "data/layer1/1B/validation/fingerprint=dummy/bundle",
        "flag_sha256_hex": "e" * 64,
        "verified_at_utc": "2025-11-08T00:00:00.000000Z",
        "sealed_inputs": [],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
        "determinism_receipt": {"policy_ids": [], "policy_digests": []},
    }
    dest = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def test_s1_weights_runner_emits_uniform_weights(tmp_path: Path) -> None:
    manifest = "a" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_site_locations(tmp_path, seed, manifest)
    _write_policy(tmp_path)
    _write_receipt(tmp_path, seed, manifest)

    runner = S1WeightsRunner()
    result = runner.run(
        S1WeightsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )
    output_file = result.output_path / "part-00000.parquet"
    assert output_file.exists()
    df = pl.read_parquet(output_file)
    weights = df.sort(["merchant_id", "site_order"]).get_column("p_weight").to_list()
    assert weights == [0.5, 0.5, 1.0]
    assert df["weight_source"].unique().to_list() == ["uniform"]
    assert df["floor_applied"].any() is False
    assert result.run_report_path.exists()
    run_report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert run_report["component"] == "2B.S1"


def test_s1_weights_runner_resume(tmp_path: Path) -> None:
    manifest = "b" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_site_locations(tmp_path, seed, manifest)
    _write_policy(tmp_path)
    _write_receipt(tmp_path, seed, manifest)
    runner = S1WeightsRunner()
    runner.run(
        S1WeightsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
        )
    )
    resumed = runner.run(
        S1WeightsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=True,
        )
    )
    assert resumed.resumed is True
