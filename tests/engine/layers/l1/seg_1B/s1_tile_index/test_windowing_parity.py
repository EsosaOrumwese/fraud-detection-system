"""Regression tests for the S1 tile index enumerator after Track 1 changes."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from affine import Affine
from pyproj import Geod
from rasterio.crs import CRS
from shapely.geometry import Point, Polygon
from shapely.prepared import prep

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    CountryPolygon,
    CountryPolygons,
    IsoCountryTable,
    PopulationRaster,
)
from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import (
    InclusionRule,
    S1TileIndexRunner,
    _raster_window_for_geometry,
)


class _StubWriter:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def append_row(self, **row: object) -> None:
        self.rows.append(dict(row))


def _make_raster(width: int = 20, height: int = 20) -> PopulationRaster:
    transform = Affine.translation(0, 10) * Affine.scale(1, -1)
    return PopulationRaster(
        path=Path("stub.tif"),
        transform=transform,
        width=width,
        height=height,
        crs=CRS.from_epsg(4326),
        nodata=None,
        geod=Geod(ellps="WGS84"),
    )


def _make_country_polygons(polys: dict[str, Polygon]) -> CountryPolygons:
    prepared = {
        iso: CountryPolygon(country_iso=iso, geometry=poly, prepared=prep(poly))
        for iso, poly in polys.items()
    }
    return CountryPolygons(prepared)


def _brute_force_tiles(
    raster: PopulationRaster,
    country: CountryPolygon,
    inclusion_rule: InclusionRule,
) -> list[dict]:
    results: list[dict] = []
    for row in range(raster.nrows):
        for col in range(raster.ncols):
            bounds = raster.tile_bounds(row, col)
            if inclusion_rule is InclusionRule.CENTER:
                lon, lat = raster.tile_centroid(row, col)
                included = country.prepared.covers(Point(lon, lat))
            else:
                included = country.geometry.intersects(bounds.to_polygon())
            if not included:
                continue
            results.append(
                {
                    "country_iso": country.country_iso,
                    "tile_id": raster.tile_id(row, col),
                    "inclusion_rule": inclusion_rule.value,
                    "raster_row": row,
                    "raster_col": col,
                    "centroid_lon": raster.tile_centroid(row, col)[0],
                    "centroid_lat": raster.tile_centroid(row, col)[1],
                    "pixel_area_m2": raster.tile_area(row, col),
                }
            )
    return results


@pytest.mark.parametrize(
    "polygon",
    [
        Polygon([(2, 8), (6, 8), (6, 4), (2, 4)]),
        Polygon([(1, 9), (9, 9), (9, 1), (1, 1)]).difference(
            Polygon([(3, 7), (7, 7), (7, 3), (3, 3)])
        ),
    ],
)
@pytest.mark.parametrize("rule", [InclusionRule.CENTER, InclusionRule.ANY_OVERLAP])
def test_vectorized_enumerator_matches_bruteforce(polygon: Polygon, rule: InclusionRule) -> None:
    raster = _make_raster()
    iso_table = IsoCountryTable(pl.DataFrame({"country_iso": ["AA"]}))
    countries = _make_country_polygons({"AA": polygon})
    runner = S1TileIndexRunner()
    tile_stub = _StubWriter()
    bounds_stub = _StubWriter()

    summaries, rows = runner._enumerate_tiles(  # type: ignore[attr-defined]
        rule,
        iso_table,
        countries,
        raster,
        tile_writer=tile_stub,
        bounds_writer=bounds_stub,
    )

    brute_force = _brute_force_tiles(raster, countries["AA"], rule)
    assert rows == len(brute_force)
    assert len(tile_stub.rows) == len(brute_force)
    vectorized_ids = sorted(row["tile_id"] for row in tile_stub.rows)
    legacy_ids = sorted(row["tile_id"] for row in brute_force)
    assert vectorized_ids == legacy_ids
    assert "AA" in summaries
    assert summaries["AA"].cells_included == len(brute_force)


def test_windowing_tightens_bounds() -> None:
    raster = _make_raster(width=50, height=50)
    polygon = Polygon([(10, 5), (20, 5), (20, -5), (10, -5)])
    row_min, row_max, col_min, col_max = _raster_window_for_geometry(raster, polygon)
    # The polygon is entirely within rows 5..15 of the 50x50 grid.
    assert 0 <= row_min <= row_max < raster.nrows
    assert 0 <= col_min <= col_max < raster.ncols
    assert (row_max - row_min) < raster.nrows // 2
    assert (col_max - col_min) < raster.ncols // 2
