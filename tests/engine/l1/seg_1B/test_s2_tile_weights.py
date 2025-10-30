from __future__ import annotations

from pathlib import Path
import json

import polars as pl
import pytest

from engine.layers.l1.seg_1B.s2_tile_weights import (
    RunnerConfig,
    S2Error,
    S2TileWeightsRunner,
    S2TileWeightsValidator,
    ValidatorConfig,
)
from engine.layers.l1.seg_1B.s2_tile_weights.l3 import build_run_report


@pytest.fixture()
def dictionary() -> dict[str, object]:
    return {
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "test",
            },
            "population_raster_2025": {
                "path": "reference/rasters/population.tif",
                "schema_ref": "schemas.ingress.layer1.yaml#/population_raster_2025",
                "version": "test",
            },
        },
        "datasets": {
            "tile_index": {
                "path": "data/layer1/1B/tile_index/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_index",
                "version": "{parameter_hash}",
            },
            "tile_weights": {
                "path": "data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_weights",
                "version": "{parameter_hash}",
            },
        },
    }


def _write_iso_table(path: Path, *, countries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"country_iso": countries}).write_parquet(path)


def _write_tile_index_partition(
    base_path: Path,
    parameter_hash: str,
    *,
    records: list[dict[str, object]],
) -> Path:
    partition_dir = base_path / f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records).write_parquet(partition_dir / "part-00000.parquet")
    return partition_dir


def _read_quantised(temp_dir: Path) -> pl.DataFrame:
    return (
        pl.scan_parquet(str(temp_dir / "*.parquet"))
        .collect()
        .sort(["country_iso", "tile_id"])
    )


def _read_partition(path: Path) -> pl.DataFrame:
    return (
        pl.scan_parquet(str(path / "*.parquet"))
        .collect()
        .sort(["country_iso", "tile_id"])
    )


def test_prepare_inputs_happy_path(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet", countries=["AA", "BB"])
    _write_tile_index_partition(
        data_root,
        "abc123",
        records=[
            {"country_iso": "AA", "tile_id": 0, "raster_row": 0, "raster_col": 0, "pixel_area_m2": 10.0},
            {"country_iso": "AA", "tile_id": 1, "raster_row": 0, "raster_col": 1, "pixel_area_m2": 12.0},
            {"country_iso": "BB", "tile_id": 0, "raster_row": 1, "raster_col": 0, "pixel_area_m2": 9.5},
        ],
    )

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="abc123",
            basis="area_m2",
            dp=3,
            dictionary=dictionary,
        )
    )

    assert prepared.governed.basis == "area_m2"
    assert prepared.governed.dp == 3
    assert prepared.tile_index.rows == 3
    assert prepared.iso_table.codes == frozenset({"AA", "BB"})
    assert prepared.pat.bytes_read_tile_index_total == prepared.tile_index.byte_size
    assert prepared.pat.vector_bytes_reference > 0


def test_prepare_inputs_missing_tile_index(
    tmp_path: Path, dictionary: dict[str, object]
) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet", countries=["AA"])

    runner = S2TileWeightsRunner()
    with pytest.raises(S2Error) as excinfo:
        runner.prepare(
            RunnerConfig(
                data_root=data_root,
                parameter_hash="missing",
                basis="uniform",
                dp=2,
                dictionary=dictionary,
            )
        )
    assert excinfo.value.context.code == "E101_TILE_INDEX_MISSING"


def test_quantise_uniform_small_dataset(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet", countries=["AA", "BB"])
    _write_tile_index_partition(
        data_root,
        "abc123",
        records=[
            {"country_iso": "AA", "tile_id": 0, "raster_row": 0, "raster_col": 0, "pixel_area_m2": 10.0},
            {"country_iso": "AA", "tile_id": 1, "raster_row": 0, "raster_col": 1, "pixel_area_m2": 12.0},
            {"country_iso": "BB", "tile_id": 5, "raster_row": 1, "raster_col": 0, "pixel_area_m2": 9.5},
        ],
    )

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="abc123",
            basis="uniform",
            dp=2,
            dictionary=dictionary,
        )
    )
    masses = runner.compute_masses(prepared)
    runner.measure_baselines(prepared)
    quantised = runner.quantise(prepared, masses)

    quantised_frame = _read_quantised(quantised.temp_dir)
    assert quantised_frame.height == quantised.rows_emitted
    assert set(quantised_frame.columns) == {
        "country_iso",
        "tile_id",
        "weight_fp",
        "dp",
        "zero_mass_fallback",
    }

    aa_sum = int(
        quantised_frame.filter(pl.col("country_iso") == "AA").get_column("weight_fp").sum()
    )
    bb_sum = int(
        quantised_frame.filter(pl.col("country_iso") == "BB").get_column("weight_fp").sum()
    )
    assert aa_sum == 100
    assert bb_sum == 100
    assert quantised.rows_emitted == 3
    assert len(quantised.summaries) == 2

    result = runner.materialise(prepared, quantised)
    materialised = _read_partition(result.tile_weights_path)
    assert materialised.height == 3
    assert materialised.sort(["country_iso", "tile_id"]).rows() == quantised_frame.rows()


def test_quantise_zero_mass_fallback(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet", countries=["AA"])
    _write_tile_index_partition(
        data_root,
        "fallback",
        records=[
            {"country_iso": "AA", "tile_id": 0, "raster_row": 0, "raster_col": 0, "pixel_area_m2": 0.0},
            {"country_iso": "AA", "tile_id": 1, "raster_row": 0, "raster_col": 1, "pixel_area_m2": 0.0},
        ],
    )

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="fallback",
            basis="area_m2",
            dp=3,
            dictionary=dictionary,
        )
    )
    masses = runner.compute_masses(prepared)
    runner.measure_baselines(prepared)
    quantised = runner.quantise(prepared, masses)
    frame = _read_quantised(quantised.temp_dir)

    assert frame.get_column("zero_mass_fallback").all()
    assert frame.filter(pl.col("country_iso") == "AA").get_column("weight_fp").sum() == 1000


def test_materialise_and_validate(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet", countries=["AA", "BB"])
    _write_tile_index_partition(
        data_root,
        "abc123",
        records=[
            {"country_iso": "AA", "tile_id": 0, "raster_row": 0, "raster_col": 0, "pixel_area_m2": 10.0},
            {"country_iso": "AA", "tile_id": 1, "raster_row": 0, "raster_col": 1, "pixel_area_m2": 12.0},
            {"country_iso": "BB", "tile_id": 2, "raster_row": 1, "raster_col": 0, "pixel_area_m2": 9.5},
        ],
    )

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="abc123",
            basis="uniform",
            dp=2,
            dictionary=dictionary,
        )
    )
    masses = runner.compute_masses(prepared)
    runner.measure_baselines(prepared)
    quantised = runner.quantise(prepared, masses)
    result = runner.materialise(prepared, quantised)

    dataset_df = _read_partition(result.tile_weights_path)
    assert dataset_df.height == 3
    assert dataset_df.get_column("weight_fp").sum() == 200

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["rows_emitted"] == 3
    assert report["pat"]["rows_emitted"] == 3

    validator = S2TileWeightsValidator()
    validator.validate(
        ValidatorConfig(
            data_root=data_root,
            parameter_hash="abc123",
            dictionary=dictionary,
            run_report_path=result.report_path,
        )
    )

    with pytest.raises(S2Error):
        runner.materialise(prepared, quantised)


def test_build_run_report(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet", countries=["AA"])
    _write_tile_index_partition(
        data_root,
        "abc123",
        records=[
            {"country_iso": "AA", "tile_id": 0, "raster_row": 0, "raster_col": 0, "pixel_area_m2": 10.0},
        ],
    )

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="abc123",
            basis="uniform",
            dp=2,
            dictionary=dictionary,
        )
    )
    masses = runner.compute_masses(prepared)
    runner.measure_baselines(prepared)
    quantised = runner.quantise(prepared, masses)

    report = build_run_report(
        prepared=prepared,
        quantised=quantised,
        determinism_receipt={"partition_path": "dummy", "sha256_hex": "deadbeef"},
    )

    assert report["basis"] == "uniform"
    assert report["dp"] == 2
    assert report["rows_emitted"] == quantised.rows_emitted
    assert report["countries_total"] == len(quantised.summaries)
    assert report["normalisation_summaries"] == quantised.summaries
