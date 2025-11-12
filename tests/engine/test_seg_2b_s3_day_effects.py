import json
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_2B.s0_gate.l0.filesystem import (
    aggregate_sha256,
    expand_files,
    hash_files,
)
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
  - id: sealed_inputs_v1
    path: data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/sealed_inputs_v1
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


def _write_site_timezones(base: Path, seed: int, manifest: str) -> Path:
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
    return dest.parent


def _write_policy(base: Path) -> None:
    payload = {
        "version_tag": "test",
        "rng_engine": "philox_4x32_10",
        "rng_stream_id": "integration_stream",
        "sigma_gamma": 0.1,
        "day_range": {"start_day": "2025-01-01", "end_day": "2025-01-02"},
        "draws_per_row": 1,
        "record_fields": [
            "gamma",
            "log_gamma",
            "sigma_gamma",
            "rng_stream_id",
            "rng_counter_lo",
            "rng_counter_hi",
        ],
        "created_utc_policy_echo": True,
        "rng_key_hi": 123456789,
        "rng_key_lo": 987654321,
        "base_counter_hi": 0,
        "base_counter_lo": 0,
    }
    dest = base / "contracts/policies/l1/seg_2B/day_effect_policy_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def _write_sealed_inventory(
    base: Path,
    manifest: str,
    seed: int,
    seg2a_manifest: str,
    tz_dir: Path,
    policy_path: Path,
) -> list[dict]:
    rows = [
        {
            "asset_id": "site_timezones",
            "version_tag": f"{seed}.{seg2a_manifest}",
            "sha256_hex": _sealed_digest(tz_dir),
            "path": f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={seg2a_manifest}/",
            "partition": ["seed", "fingerprint"],
            "schema_ref": "schemas.2A.yaml#/egress/site_timezones",
        },
        {
            "asset_id": "day_effect_policy_v1",
            "version_tag": "2025.11",
            "sha256_hex": _sealed_digest(policy_path),
            "path": "contracts/policies/l1/seg_2B/day_effect_policy_v1.json",
            "partition": [],
            "schema_ref": "schemas.2B.yaml#/policy/day_effect_policy_v1",
        },
    ]
    dest = base / f"data/layer1/2B/sealed_inputs/fingerprint={manifest}/sealed_inputs_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def _write_receipt(
    base: Path,
    seed: int,
    manifest: str,
    sealed_rows: list[dict],
) -> None:
    payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": "f" * 64,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "e" * 64,
        "verified_at_utc": "2025-11-08T00:00:00.000000Z",
        "sealed_inputs": [
            {"id": row["asset_id"], "partition": row["partition"], "schema_ref": row["schema_ref"]}
            for row in sealed_rows
        ],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
        "determinism_receipt": {
            "policy_ids": ["day_effect_policy_v1"],
            "policy_digests": [
                row["sha256_hex"]
                for row in sealed_rows
                if row["asset_id"] == "day_effect_policy_v1"
            ],
        },
    }
    dest = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sealed_digest(path: Path) -> str:
    files = expand_files(path)
    digests = hash_files(files, error_prefix="TEST_S3")
    return aggregate_sha256(digests)


def test_s3_day_effects_runner_emits_factors(tmp_path: Path) -> None:
    manifest = "c" * 64
    seg2a_manifest = "d" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    tz_dir = _write_site_timezones(tmp_path, seed, seg2a_manifest)
    policy_path = _write_policy(tmp_path)
    sealed_rows = _write_sealed_inventory(
        tmp_path,
        manifest,
        seed,
        seg2a_manifest,
        tz_dir,
        policy_path,
    )
    _write_receipt(tmp_path, seed, manifest, sealed_rows)

    runner = S3DayEffectsRunner()
    result = runner.run(
        S3DayEffectsInputs(
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
    assert df.height == 4  # 1 merchant * 2 tz groups * 2 days
    assert set(df.columns) == {
        "merchant_id",
        "utc_day",
        "tz_group_id",
        "gamma",
        "log_gamma",
        "sigma_gamma",
        "rng_stream_id",
        "rng_counter_hi",
        "rng_counter_lo",
        "created_utc",
    }
    assert df["gamma"].min() > 0
    assert df["tz_group_id"].n_unique() == 2
    assert set(df["tz_group_id"].to_list()) == {"America/New_York", "Europe/London"}
    assert set(df["utc_day"].to_list()) == {"2025-01-01", "2025-01-02"}
    ordered = df.sort(["merchant_id", "utc_day", "tz_group_id"])
    counters = [
        (int(row["rng_counter_hi"]) << 64) + int(row["rng_counter_lo"])
        for row in ordered.iter_rows(named=True)
    ]
    assert counters == sorted(counters)
    assert result.run_report_path.exists()
    report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report["rng_accounting"]["rows_expected"] == 4
    assert report["rng_accounting"]["rows_written"] == 4
    assert report["inputs_summary"]["tz_groups_total"] == 2


def test_s3_day_effects_runner_resume(tmp_path: Path) -> None:
    manifest = "d" * 64
    seg2a_manifest = "e" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    tz_dir = _write_site_timezones(tmp_path, seed, seg2a_manifest)
    policy_path = _write_policy(tmp_path)
    sealed_rows = _write_sealed_inventory(
        tmp_path,
        manifest,
        seed,
        seg2a_manifest,
        tz_dir,
        policy_path,
    )
    _write_receipt(tmp_path, seed, manifest, sealed_rows)
    runner = S3DayEffectsRunner()
    runner.run(
        S3DayEffectsInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            seg2a_manifest_fingerprint=seg2a_manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )
    resumed = runner.run(
        S3DayEffectsInputs(
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
