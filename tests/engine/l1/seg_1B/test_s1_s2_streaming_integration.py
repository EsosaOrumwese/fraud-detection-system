from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import polars as pl
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from engine.layers.l1.seg_1B.s1_tile_index import RunnerConfig as S1RunnerConfig, S1TileIndexRunner
from engine.layers.l1.seg_1B.s2_tile_weights import (
    RunnerConfig as S2RunnerConfig,
    S2TileWeightsRunner,
    S2TileWeightsValidator,
    ValidatorConfig,
)


def _build_dictionary() -> dict[str, object]:
    return {
        "reference_data": {
            "iso3166_canonical_2024": {
                "path": "reference/iso/iso3166_canonical.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                "version": "test",
            },
            "world_countries": {
                "path": "reference/spatial/world_countries.parquet",
                "schema_ref": "schemas.ingress.layer1.yaml#/world_countries",
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
            "tile_bounds": {
                "path": "data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/",
                "partitioning": ["parameter_hash"],
                "ordering": ["country_iso", "tile_id"],
                "schema_ref": "schemas.1B.yaml#/prep/tile_bounds",
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


def _write_world_polygons(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    geometries = [box(-2.0, -2.0, 0.0, 2.0), box(0.0, -2.0, 2.0, 2.0)]
    gdf = gpd.GeoDataFrame({"country_iso": ["AA", "BB"]}, geometry=geometries, crs="EPSG:4326")
    gdf.to_parquet(path)


def _write_population_raster(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(-2.0, 2.0, 1.0, 1.0)
    data = np.array(
        [
            [5.0, 5.0, 0.0, 0.0],
            [5.0, 5.0, 0.0, 0.0],
            [0.0, 0.0, 4.0, 4.0],
            [0.0, 0.0, 4.0, 4.0],
        ],
        dtype=np.float32,
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs={"proj": "longlat", "datum": "WGS84", "no_defs": True},
        transform=transform,
    ) as dataset:
        dataset.write(data, 1)


def test_multi_worker_s1_and_streaming_s2(tmp_path: Path) -> None:
    data_root = tmp_path
    dictionary = _build_dictionary()

    _write_iso_table(data_root / "reference/iso/iso3166_canonical.parquet")
    _write_world_polygons(data_root / "reference/spatial/world_countries.parquet")
    _write_population_raster(data_root / "reference/rasters/population.tif")

    parameter_hash = "integration"
    s1_runner = S1TileIndexRunner()
    s1_result = s1_runner.run(
        S1RunnerConfig(
            data_root=data_root,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
            workers=2,
        )
    )

    tile_index_df = (
        pl.scan_parquet(str(s1_result.tile_index_path / "*.parquet"))
        .collect()
        .sort(["country_iso", "tile_id"])
    )
    assert tile_index_df.height > 0
    assert set(tile_index_df.get_column("country_iso").to_list()) == {"AA", "BB"}

    report_payload = json.loads(s1_result.report_path.read_text(encoding="utf-8"))
    assert report_payload["pat"]["workers_used"] >= 2

    s2_runner = S2TileWeightsRunner()
    prepared = s2_runner.prepare(
        S2RunnerConfig(
            data_root=data_root,
            parameter_hash=parameter_hash,
            basis="uniform",
            dp=2,
            dictionary=dictionary,
        )
    )
    masses = s2_runner.compute_masses(prepared)
    s2_runner.measure_baselines(prepared)
    quantised = s2_runner.quantise(prepared, masses)
    s2_result = s2_runner.materialise(prepared, quantised)

    tile_weights_df = (
        pl.scan_parquet(str(s2_result.tile_weights_path / "*.parquet"))
        .collect()
        .sort(["country_iso", "tile_id"])
    )
    assert tile_weights_df.height == tile_index_df.height
    assert tile_weights_df.get_column("weight_fp").sum() == 200  # two countries, dp=2 -> 100 each

    validator = S2TileWeightsValidator()
    validator.validate(
        ValidatorConfig(
            data_root=data_root,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
            run_report_path=s2_result.report_path,
        )
    )
