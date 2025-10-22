from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import polars as pl
import pytest
from pyproj import Geod
from rasterio.transform import from_origin
from shapely.geometry import Polygon

from engine.layers.l1.seg_1B.s1_tile_index import (
    RunnerConfig,
    S1TileIndexRunner,
    S1TileIndexValidator,
    ValidatorConfig,
)
from engine.layers.l1.seg_1B.s1_tile_index.l0 import loaders as loader_module
from engine.layers.l1.seg_1B.s1_tile_index.l2 import runner as runner_module
from engine.layers.l1.seg_1B.s1_tile_index.l3 import validator as validator_module


@pytest.fixture()
def sample_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RunnerConfig, dict[str, object], Path]:
    data_root = tmp_path
    reference_dir = data_root / "reference"
    (reference_dir / "iso").mkdir(parents=True)
    (reference_dir / "spatial").mkdir(parents=True)

    # ISO table
    iso_df = pl.DataFrame({"country_iso": ["AA"]})
    iso_path = reference_dir / "iso" / "iso3166_canonical.parquet"
    iso_df.write_parquet(iso_path)

    # Country polygon covering [0, 2] x [0, 2]
    polygon = Polygon([(0, 0), (0, 2), (2, 2), (2, 0)])
    gdf = gpd.GeoDataFrame({"country_iso": ["AA"], "geometry": [polygon]}, crs="EPSG:4326")
    world_path = reference_dir / "spatial" / "world_countries.parquet"
    gdf.to_parquet(world_path)

    # Population raster: 2x2 grid covering the polygon extent
    raster_path = reference_dir / "spatial" / "population.tif"
    raster_path.touch()
    transform = from_origin(0, 2, 1, 1)  # west, north, pixel width, pixel height
    geod = Geod(ellps="WGS84")

    class _DummyCRS:
        @property
        def is_geographic(self) -> bool:
            return True

    population_raster = loader_module.PopulationRaster(
        path=raster_path,
        transform=transform,
        width=2,
        height=2,
        crs=_DummyCRS(),  # type: ignore[arg-type]
        nodata=None,
        geod=geod,
    )

    monkeypatch.setattr(loader_module, "load_population_raster", lambda path: population_raster)
    monkeypatch.setattr(runner_module, "load_population_raster", lambda path: population_raster)
    monkeypatch.setattr(validator_module, "load_population_raster", lambda path: population_raster)

    dictionary = {
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
                "path": "reference/spatial/population.tif",
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
        },
    }

    config = RunnerConfig(
        data_root=data_root,
        parameter_hash="abc123",
        inclusion_rule="center",
        dictionary=dictionary,
    )
    return config, dictionary, data_root


def test_runner_and_validator(sample_environment: tuple[RunnerConfig, dict[str, object], Path]) -> None:
    config, dictionary, data_root = sample_environment

    runner = S1TileIndexRunner()
    result = runner.run(config)

    assert result.tile_index_path.exists()
    assert result.tile_bounds_path.exists()

    tile_index_df = pl.read_parquet(result.tile_index_path / "part-00000.parquet")
    assert tile_index_df.height == 4  # 2x2 grid fully inside the polygon
    assert set(tile_index_df["country_iso"]) == {"AA"}
    assert set(tile_index_df["inclusion_rule"]) == {"center"}

    validator = S1TileIndexValidator()
    validator.validate(
        ValidatorConfig(
            data_root=data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
    )

    # Ensure determinism receipt recorded in report matches partition hash
    report_path = result.report_path
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["determinism_receipt"]["partition_path"] == str(result.tile_index_path)
    assert isinstance(report["determinism_receipt"]["sha256_hex"], str)
    assert report["pat"]["countries_processed"] == 1
    assert report["pat"]["cells_included_total"] == 4
