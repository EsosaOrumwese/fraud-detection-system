from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import polars as pl
import pytest

from engine.layers.l1.seg_1B.s2_tile_weights import (
    MassComputation,
    RunnerConfig,
    S2Error,
    S2RunResult,
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


def _write_iso_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"country_iso": ["AA", "BB"]}).write_parquet(path)


def _write_tile_index_partition(base_path: Path, parameter_hash: str) -> Path:
    partition_dir = (
        base_path / f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "country_iso": ["AA", "AA", "BB"],
            "tile_id": [0, 1, 0],
            "raster_row": [0, 0, 1],
            "raster_col": [0, 1, 0],
            "pixel_area_m2": [10.0, 12.0, 9.5],
        }
    )
    frame.write_parquet(partition_dir / "part-00000.parquet")
    return partition_dir


def test_prepare_inputs_happy_path(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    iso_path = data_root / "reference/iso/iso3166_canonical.parquet"
    _write_iso_table(iso_path)
    _write_tile_index_partition(data_root, "abc123")

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
    assert prepared.tile_index.path.exists()
    assert prepared.iso_table.codes == frozenset({"AA", "BB"})
    assert prepared.pat.countries_processed == 0
    assert prepared.pat.bytes_read_tile_index_total > 0
    assert prepared.pat.bytes_read_vectors_total > 0


def test_prepare_inputs_missing_tile_index(
    tmp_path: Path, dictionary: dict[str, object]
) -> None:
    data_root = tmp_path
    iso_path = data_root / "reference/iso/iso3166_canonical.parquet"
    _write_iso_table(iso_path)

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


def test_compute_masses_uniform(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")

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

    mass_result = runner.compute_masses(prepared)
    assert isinstance(mass_result, MassComputation)
    assert mass_result.frame.get_column("mass").to_list() == [1.0, 1.0, 1.0]


def test_compute_masses_population(
    tmp_path: Path, dictionary: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")
    values = np.array([[5.0, 2.0], [0.0, 3.5]], dtype="float64")
    population_path = data_root / "reference/rasters/population.tif"
    population_path.parent.mkdir(parents=True, exist_ok=True)

    class _StubDataset:
        def __init__(self, array: np.ndarray) -> None:
            self._array = array
            self.nodata = None

        def read(self, band: int, out_dtype: str = "float64") -> np.ndarray:
            assert band == 1
            return self._array.astype(out_dtype)

        def __enter__(self) -> "_StubDataset":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(
        "engine.layers.l1.seg_1B.s2_tile_weights.l1.masses.load_population_raster",
        lambda path: SimpleNamespace(path=population_path),
    )
    monkeypatch.setattr(
        "engine.layers.l1.seg_1B.s2_tile_weights.l1.masses.rasterio.open",
        lambda path: _StubDataset(values),
    )

    runner = S2TileWeightsRunner()
    prepared = runner.prepare(
        RunnerConfig(
            data_root=data_root,
            parameter_hash="abc123",
            basis="population",
            dp=2,
            dictionary=dictionary,
        )
    )

    mass_result = runner.compute_masses(prepared)
    assert mass_result.frame.get_column("mass").to_list() == [5.0, 2.0, 0.0]
    assert prepared.pat.bytes_read_raster_total > 0


def test_quantise_weights(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")

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
    quantised = runner.quantise(prepared, masses)

    aa_weights = (
        quantised.frame.filter(pl.col("country_iso") == "AA").get_column("weight_fp").to_list()
    )
    bb_weights = (
        quantised.frame.filter(pl.col("country_iso") == "BB").get_column("weight_fp").to_list()
    )
    assert aa_weights == [50, 50]
    assert bb_weights == [100]
    assert len(quantised.summaries) == 2
    assert not any(entry["zero_mass_fallback"] for entry in quantised.summaries)
    assert set(quantised.frame.get_column("dp").to_list()) == {2}
    assert not quantised.frame.get_column("zero_mass_fallback").any()
    assert sum(aa_weights) == 100
    assert sum(bb_weights) == 100
    assert len(quantised.summaries) == 2


def test_quantise_zero_mass_fallback(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")

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
    zero_mass_frame = masses.frame.with_columns(pl.lit(0.0).alias("mass"))
    quantised = runner.quantise(prepared, MassComputation(frame=zero_mass_frame))

    assert quantised.frame.get_column("zero_mass_fallback").all()
    aa_weights = (
        quantised.frame.filter(pl.col("country_iso") == "AA").get_column("weight_fp").to_list()
    )
    bb_weights = (
        quantised.frame.filter(pl.col("country_iso") == "BB").get_column("weight_fp").to_list()
    )
    assert aa_weights == [50, 50]
    assert bb_weights == [100]


def test_build_run_report(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")

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
    quantised = runner.quantise(prepared, masses)

    report = build_run_report(
        prepared=prepared,
        quantised=quantised,
        determinism_receipt={"partition_path": "dummy", "sha256_hex": "deadbeef"},
    )
    assert report["basis"] == "uniform"
    assert report["dp"] == 2
    assert report["rows_emitted"] == quantised.frame.height
    assert report["countries_total"] == len(quantised.summaries)
    assert report["pat"]["rows_emitted"] == quantised.frame.height
    assert report["ingress_versions"]["iso3166"] == "test"
    assert report["ingress_versions"]["population_raster"] is None
    assert report["normalisation_summaries"] == quantised.summaries

def test_materialise_and_validate(tmp_path: Path, dictionary: dict[str, object]) -> None:
    data_root = tmp_path
    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_tile_index_partition(data_root, "abc123")

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

    prepared.pat.io_baseline_ti_bps = 1_000_000.0
    prepared.pat.io_baseline_vectors_bps = 1_000_000.0
    prepared.pat.wall_clock_seconds_total = 1.0
    prepared.pat.cpu_seconds_total = 0.5
    prepared.pat.max_worker_rss_bytes = 50_000_000
    prepared.pat.open_files_peak = 32
    prepared.pat.workers_used = 2
    prepared.pat.chunk_size = 128

    masses = runner.compute_masses(prepared)
    quantised = runner.quantise(prepared, masses)
    result = runner.materialise(prepared, quantised)

    assert result.tile_weights_path.exists()
    dataset_df = pl.read_parquet(result.tile_weights_path / "part-00000.parquet")
    assert dataset_df.height == quantised.frame.height
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["determinism_receipt"]["sha256_hex"] == result.determinism_receipt["sha256_hex"]

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