from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1B.s3_requirements import (
    AggregationResult,
    RunnerConfig,
    S3Error,
    S3RequirementsRunner,
    S3RequirementsValidator,
    S3RunResult,
    S3ValidatorConfig,
)


@pytest.fixture()
def dictionary() -> dict[str, object]:
    return {
        "datasets": {
            "outlet_catalogue": {
                "path": "data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/",
                "partitioning": ["seed", "fingerprint"],
                "ordering": ["merchant_id", "legal_country_iso", "site_order"],
                "schema_ref": "schemas.1A.yaml#/egress/outlet_catalogue",
            },
            "tile_weights": {
                "path": "data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_weights",
            },
            "s0_gate_receipt_1B": {
                "path": "data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json",
                "partitioning": ["fingerprint"],
                "schema_ref": "schemas.1B.yaml#/s0_gate_receipt",
            },
            "s3_requirements": {
                "path": "data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/",
                "partitioning": ["seed", "fingerprint", "parameter_hash"],
                "ordering": ["merchant_id", "legal_country_iso"],
                "schema_ref": "schemas.1B.yaml#/plan/s3_requirements",
            },
        },
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "test",
            }
        },
    }


def _write_receipt(path: Path, manifest_fingerprint: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "validation_bundle_path": f"data/layer1/1A/validation/fingerprint={manifest_fingerprint}/",
        "flag_sha256_hex": "deadbeef" * 8,
        "verified_at_utc": "2025-10-22T22:15:00.000000Z",
        "sealed_inputs": [
            {"id": "outlet_catalogue", "schema_ref": "schemas.1A.yaml#/egress/outlet_catalogue"},
            {"id": "tile_weights", "schema_ref": "schemas.1B.yaml#/prep/tile_weights"},
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_iso(path: Path, codes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"country_iso": codes}).write_parquet(path)


def _write_tile_weights(path: Path, rows: list[tuple[str, int]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"country_iso": [r[0] for r in rows], "tile_id": [r[1] for r in rows]}).write_parquet(
        path / "part-00000.parquet"
    )


def _write_outlet_catalogue(
    path: Path,
    seed: str,
    manifest_fingerprint: str,
    rows: list[tuple[int, str, int]],
    *,
    include_global_seed: bool = True,
    override_manifest: str | None = None,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "merchant_id": [r[0] for r in rows],
            "legal_country_iso": [r[1] for r in rows],
            "site_order": [r[2] for r in rows],
            "manifest_fingerprint": [
                override_manifest if override_manifest is not None else manifest_fingerprint
            ]
            * len(rows),
        }
    )
    if include_global_seed:
        frame = frame.with_columns(pl.lit(seed).alias("global_seed"))
    frame.write_parquet(path / "part-00000.parquet")


def _build_config(
    *,
    tmp_path: Path,
    dictionary: dict[str, object],
    manifest_fingerprint: str,
    seed: str,
    parameter_hash: str,
) -> RunnerConfig:
    return RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )


def test_prepare_and_aggregate_success(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB", "US"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0), ("US", 0), ("US", 1)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [
            (1, "GB", 1),
            (1, "GB", 2),
            (1, "US", 1),
            (1, "US", 2),
            (2, "US", 1),
        ],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    aggregation = runner.aggregate(prepared)
    result = runner.materialise(prepared, aggregation)

    assert result.rows_emitted == 3
    assert result.merchants_total == 2
    assert result.countries_total == 2
    assert result.requirements_path.exists()
    assert result.report_path.exists()

    validator = S3RequirementsValidator()
    validator.validate(
        S3ValidatorConfig(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
        )
    )


def test_prepare_missing_receipt(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "GB", 1)],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    with pytest.raises(S3Error) as excinfo:
        runner.prepare(config)
    assert excinfo.value.context.code == "E301_NO_PASS_FLAG"


def test_site_order_integrity_failure(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [
            (1, "GB", 1),
            (1, "GB", 3),
        ],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    with pytest.raises(S3Error) as excinfo:
        runner.aggregate(prepared)
    assert excinfo.value.context.code == "E314_SITE_ORDER_INTEGRITY"


def test_iso_fk_violation(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "US", 1)],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    with pytest.raises(S3Error) as excinfo:
        runner.aggregate(prepared)
    assert excinfo.value.context.code == "E302_FK_COUNTRY"


def test_tile_weight_coverage_violation(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB", "US"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "GB", 1), (1, "US", 1)],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    with pytest.raises(S3Error) as excinfo:
        runner.aggregate(prepared)
    assert excinfo.value.context.code == "E303_MISSING_WEIGHTS"


def test_path_embed_mismatch(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "GB", 1)],
        override_manifest="c" * 64,
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    with pytest.raises(S3Error) as excinfo:
        runner.prepare(config)
    assert excinfo.value.context.code == "E306_TOKEN_MISMATCH"


def test_materialise_immutable_conflict(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "GB", 1)],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    aggregation = runner.aggregate(prepared)
    runner.materialise(prepared, aggregation)

    modified_frame = aggregation.frame.with_columns((pl.col("n_sites") + 1).alias("n_sites"))
    modified_aggregation = AggregationResult(frame=modified_frame, source_rows_total=aggregation.source_rows_total)

    with pytest.raises(S3Error) as excinfo:
        runner.materialise(prepared, modified_aggregation)
    assert excinfo.value.context.code == "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL"


def test_validator_detects_count_mismatch(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "GB", 1)],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    aggregation = runner.aggregate(prepared)
    result = runner.materialise(prepared, aggregation)

    parquet_files = list(result.requirements_path.glob("*.parquet"))
    assert parquet_files
    frame = pl.read_parquet(parquet_files[0])
    frame = frame.with_columns((pl.col("n_sites") + 1).alias("n_sites"))
    frame.write_parquet(parquet_files[0])

    validator = S3RequirementsValidator()
    with pytest.raises(S3Error) as excinfo:
        validator.validate(
            S3ValidatorConfig(
                data_root=tmp_path,
                seed=seed,
                manifest_fingerprint=manifest,
                parameter_hash=parameter_hash,
                dictionary=dictionary,
            )
        )
    assert excinfo.value.context.code == "E308_COUNTS_MISMATCH"


def test_validator_detects_determinism_mismatch(tmp_path: Path, dictionary: dict[str, object]) -> None:
    manifest = "a" * 64
    seed = "12345"
    parameter_hash = "b" * 64

    _write_receipt(
        tmp_path / f"data/layer1/1B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json",
        manifest,
    )
    _write_iso(tmp_path / "reference/iso/iso3166_canonical.parquet", ["GB"])
    _write_tile_weights(
        tmp_path / f"data/layer1/1B/tile_weights/parameter_hash={parameter_hash}",
        [("GB", 0)],
    )
    _write_outlet_catalogue(
        tmp_path / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}",
        seed,
        manifest,
        [(1, "GB", 1)],
    )

    config = _build_config(
        tmp_path=tmp_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    runner = S3RequirementsRunner()
    prepared = runner.prepare(config)
    aggregation = runner.aggregate(prepared)
    result = runner.materialise(prepared, aggregation)

    report_payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    report_payload["determinism_receipt"]["sha256_hex"] = "badc0de"
    result.report_path.write_text(json.dumps(report_payload), encoding="utf-8")

    validator = S3RequirementsValidator()
    with pytest.raises(S3Error) as excinfo:
        validator.validate(
            S3ValidatorConfig(
                data_root=tmp_path,
                seed=seed,
                manifest_fingerprint=manifest,
                parameter_hash=parameter_hash,
                dictionary=dictionary,
            )
        )
    assert excinfo.value.context.code == "E313_NONDETERMINISTIC_OUTPUT"

