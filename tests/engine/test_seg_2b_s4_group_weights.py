import json
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_2B.s4_group_weights import (
    S4GroupWeightsInputs,
    S4GroupWeightsRunner,
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
  - id: site_timezones
    path: data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
  - id: s3_day_effects
    path: data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
  - id: s4_group_weights
    path: data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
    partitioning: [fingerprint]
"""
    dictionary_path = path / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _write_s1_site_weights(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1, 2],
            "legal_country_iso": ["US", "US", "GB"],
            "site_order": [1, 2, 1],
            "p_weight": [0.6, 0.4, 1.0],
        }
    )
    dest = base / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_site_timezones(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1, 2],
            "legal_country_iso": ["US", "US", "GB"],
            "site_order": [1, 2, 1],
            "tzid": ["America/New_York", "Europe/London", "Europe/London"],
        }
    )
    dest = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_s3_day_effects(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1, 1, 1, 2],
            "utc_day": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02", "2025-01-01"],
            "tz_group_id": [
                "America/New_York",
                "Europe/London",
                "America/New_York",
                "Europe/London",
                "Europe/London",
            ],
            "gamma": [1.0, 1.2, 0.9, 1.1, 0.95],
        }
    )
    dest = base / f"data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_receipt(base: Path, manifest: str) -> None:
    payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": "2025110601",
        "parameter_hash": "f" * 64,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "e" * 64,
        "verified_at_utc": "2025-11-09T00:00:00.000000Z",
        "sealed_inputs": [],
    }
    dest = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_s4_group_weights_runner_emits_mix(tmp_path: Path) -> None:
    manifest = "a" * 64
    seg2a_manifest = "b" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    _write_site_timezones(tmp_path, seed, seg2a_manifest)
    _write_s3_day_effects(tmp_path, seed, manifest)
    _write_receipt(tmp_path, manifest)

    runner = S4GroupWeightsRunner()
    result = runner.run(
        S4GroupWeightsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            seg2a_manifest_fingerprint=seg2a_manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )

    assert result.output_path.exists()
    part_path = next(result.output_path.glob("*.parquet"))
    df = pl.read_parquet(part_path)
    assert df.height == 5
    grouped = (
        df.group_by(["merchant_id", "utc_day"])
        .agg(pl.col("p_group").sum().alias("total"))
        .to_dicts()
    )
    assert all(abs(row["total"] - 1.0) < 1e-9 for row in grouped)
    assert set(df.columns) == {
        "merchant_id",
        "utc_day",
        "tz_group_id",
        "p_group",
        "base_share",
        "gamma",
        "created_utc",
        "mass_raw",
        "denom_raw",
    }
    report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report["counts"]["rows_total"] == 5
    assert report["output"]["id"] == "s4_group_weights"


def test_s4_group_weights_runner_resume(tmp_path: Path) -> None:
    manifest = "c" * 64
    seg2a_manifest = "d" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    _write_site_timezones(tmp_path, seed, seg2a_manifest)
    _write_s3_day_effects(tmp_path, seed, manifest)
    _write_receipt(tmp_path, manifest)
    runner = S4GroupWeightsRunner()
    runner.run(
        S4GroupWeightsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            seg2a_manifest_fingerprint=seg2a_manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )
    resumed = runner.run(
        S4GroupWeightsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            seg2a_manifest_fingerprint=seg2a_manifest,
            dictionary_path=dictionary_path,
            resume=True,
            emit_run_report_stdout=False,
        )
    )
    assert resumed.resumed is True
