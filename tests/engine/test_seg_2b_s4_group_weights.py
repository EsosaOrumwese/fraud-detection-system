import hashlib
import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_2B.s0_gate import S0GateError
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
  - id: sealed_inputs_v1
    path: data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json
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


def _write_site_timezones(base: Path, seed: int, manifest: str) -> Path:
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
    return dest.parent


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

def _write_sealed_inventory(
    base: Path,
    manifest: str,
    seed: int,
    seg2a_manifest: str,
    tz_dir: Path,
) -> list[dict]:
    rows = [
        {
            "asset_id": "site_timezones",
            "version_tag": f"{seed}.{seg2a_manifest}",
            "sha256_hex": _sha256_dir(tz_dir),
            "path": f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={seg2a_manifest}/",
            "partition": ["seed", "fingerprint"],
            "schema_ref": "schemas.2A.yaml#/egress/site_timezones",
        },
    ]
    dest = base / f"data/layer1/2B/sealed_inputs/fingerprint={manifest}/sealed_inputs_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def _write_receipt(base: Path, seed: int, manifest: str, sealed_rows: list[dict]) -> None:
    payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": "f" * 64,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "e" * 64,
        "verified_at_utc": "2025-11-09T00:00:00.000000Z",
        "sealed_inputs": [
            {"id": row["asset_id"], "partition": row["partition"], "schema_ref": row["schema_ref"]}
            for row in sealed_rows
        ],
    }
    dest = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256_dir(path: Path) -> str:
    sha = hashlib.sha256()
    if not path.exists():
        return sha.hexdigest()
    for entry in sorted(path.rglob("*")):
        if entry.is_file():
            sha.update(entry.relative_to(path).as_posix().encode("utf-8"))
            with entry.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    sha.update(chunk)
    return sha.hexdigest()


def test_s4_group_weights_runner_emits_mix(tmp_path: Path) -> None:
    manifest = "a" * 64
    seg2a_manifest = "b" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_site_weights(tmp_path, seed, manifest)
    tz_dir = _write_site_timezones(tmp_path, seed, seg2a_manifest)
    _write_s3_day_effects(tmp_path, seed, manifest)
    sealed_rows = _write_sealed_inventory(tmp_path, manifest, seed, seg2a_manifest, tz_dir)
    _write_receipt(tmp_path, seed, manifest, sealed_rows)

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
    tz_dir = _write_site_timezones(tmp_path, seed, seg2a_manifest)
    _write_s3_day_effects(tmp_path, seed, manifest)
    sealed_rows = _write_sealed_inventory(tmp_path, manifest, seed, seg2a_manifest, tz_dir)
    _write_receipt(tmp_path, seed, manifest, sealed_rows)
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


def test_s4_group_weights_fails_when_base_share_not_one(tmp_path: Path) -> None:
    manifest = "e" * 64
    seg2a_manifest = "f" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    df = pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "site_order": [1],
            "p_weight": [0.5],
        }
    )
    dest = tmp_path / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)
    tz_dir = _write_site_timezones(tmp_path, seed, seg2a_manifest)
    _write_s3_day_effects(tmp_path, seed, manifest)
    sealed_rows = _write_sealed_inventory(tmp_path, manifest, seed, seg2a_manifest, tz_dir)
    _write_receipt(tmp_path, seed, manifest, sealed_rows)
    runner = S4GroupWeightsRunner()
    with pytest.raises(S0GateError) as exc:
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
    assert exc.value.code == "2B-S4-052"


def test_s4_group_weights_detects_missing_tz_group_rows(tmp_path: Path) -> None:
    manifest = "1" * 64
    seg2a_manifest = "2" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    df_weights = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "p_weight": [0.6, 0.4],
        }
    )
    weights_path = tmp_path / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    df_weights.write_parquet(weights_path)
    df_tz = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "tzid": ["America/New_York", "Europe/London"],
        }
    )
    tz_path = tmp_path / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={seg2a_manifest}/part-00000.parquet"
    tz_path.parent.mkdir(parents=True, exist_ok=True)
    df_tz.write_parquet(tz_path)
    df = pl.DataFrame(
        {
            "merchant_id": [1],
            "utc_day": ["2025-01-01"],
            "tz_group_id": ["America/New_York"],
            "gamma": [1.0],
        }
    )
    dest = tmp_path / f"data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)
    tz_dir = tz_path.parent
    sealed_rows = _write_sealed_inventory(tmp_path, manifest, seed, seg2a_manifest, tz_dir)
    _write_receipt(tmp_path, seed, manifest, sealed_rows)
    runner = S4GroupWeightsRunner()
    with pytest.raises(S0GateError) as exc:
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
    assert exc.value.code == "2B-S4-050"
