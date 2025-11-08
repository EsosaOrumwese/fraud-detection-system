import json
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_2B.s3_day_effects import (
    S3DayEffectsInputs,
    S3DayEffectsRunner,
)


def _write_dictionary(path: Path) -> Path:
    payload = """
version: test
catalogue:
  dictionary_version: test
  registry_version: test
datasets:
  - id: s1_site_weights
    path: data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s1_site_weights
  - id: site_timezones
    path: data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2A.yaml#/egress/site_timezones
  - id: s3_day_effects
    path: data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s3_day_effects
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/s0_gate_receipt_v1
policies:
  - id: day_effect_policy_v1
    path: contracts/policies/l1/seg_2B/day_effect_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/day_effect_policy_v1
"""
    dictionary_path = path / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _write_s1_site_weights(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "p_weight": [0.5, 0.5],
            "quantised_bits": [16, 16],
        }
    )
    dest = base / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_site_timezones(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "tzid": ["America/New_York", "Europe/London"],
        }
    )
    dest = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_policy(base: Path) -> None:
    payload = {
        "version_tag": "test",
        "sigma_gamma": 0.1,
        "clip_bounds": [-0.25, 0.25],
        "utc_day_start": "2025-01-01",
        "utc_day_count": 2,
        "rng_key_hi": 123456789,
        "rng_key_lo": 987654321,
        "rng_counter_start_hi": 0,
        "rng_counter_start_lo": 0,
        "rng_stream_id": "integration_stream",
    }
    dest = base / "contracts/policies/l1/seg_2B/day_effect_policy_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_receipt(base: Path, seed: int, manifest: str) -> None:
    payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": "f" * 64,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "e" * 64,
        "verified_at_utc": "2025-11-08T00:00:00.000000Z",
        "sealed_inputs": [],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
        "determinism_receipt": {"policy_ids": [], "policy_digests": []},
    }
    dest = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_s3_day_effects_runner_emits_factors(tmp_path: Path) -> None:
    manifest = "c" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    _write_site_timezones(tmp_path, seed, manifest)
    _write_policy(tmp_path)
    _write_receipt(tmp_path, seed, manifest)

    runner = S3DayEffectsRunner()
    result = runner.run(
        S3DayEffectsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )

    assert result.output_path.exists()
    df = pl.read_parquet(result.output_path)
    assert df.height == 4  # 1 merchant * 2 tz groups * 2 days
    assert df["gamma"].min() > 0
    assert df["tz_group_id"].n_unique() == 2
    assert set(df["tzid"].unique().to_list()) == {"America/New_York", "Europe/London"}
    assert set(df["legal_country_iso"].unique().to_list()) == {"US"}
    assert result.run_report_path.exists()


def test_s3_day_effects_runner_resume(tmp_path: Path) -> None:
    manifest = "d" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    _write_site_timezones(tmp_path, seed, manifest)
    _write_policy(tmp_path)
    _write_receipt(tmp_path, seed, manifest)
    runner = S3DayEffectsRunner()
    runner.run(
        S3DayEffectsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )
    resumed = runner.run(
        S3DayEffectsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=True,
            emit_run_report_stdout=False,
        )
    )
    assert resumed.resumed is True
