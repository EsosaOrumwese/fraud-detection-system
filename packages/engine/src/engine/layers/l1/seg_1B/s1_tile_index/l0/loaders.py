"""Low-level loaders and geometry helpers for Segment 1B S1 (Tile Index).

This module is intentionally free of any inclusion logic.  It provides strongly
typed accessors for the sealed ingress artefacts (ISO table, country polygons,
population raster) so that higher layers can build deterministic kernels on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping

import geopandas as gpd
import polars as pl
import rasterio
from pyproj import Geod
from rasterio.crs import CRS
from rasterio.transform import Affine
from rasterio.transform import xy as transform_xy
from shapely.geometry import BaseGeometry, Polygon
from shapely.prepared import PreparedGeometry, prep as prepare_geometry


class LoaderError(RuntimeError):
    """Domain-specific error raised when sealed artefacts are inconsistent."""


@dataclass(frozen=True)
class IsoCountryTable:
    """Wrapper around the ISO canonical table consumed by S1."""

    table: pl.DataFrame

    @property
    def codes(self) -> frozenset[str]:
        """Return the set of ISO alpha-2 codes present in the table."""
        return frozenset(self.table.get_column("country_iso").to_list())  # type: ignore[no-any-return]


@dataclass(frozen=True)
class CountryPolygon:
    """Prepared geometry for an ISO-3166 country."""

    country_iso: str
    geometry: BaseGeometry
    prepared: PreparedGeometry


@dataclass(frozen=True)
class CountryPolygons:
    """Container for prepared country polygons keyed by ISO code."""

    _items: Mapping[str, CountryPolygon]

    def __getitem__(self, country_iso: str) -> CountryPolygon:
        return self._items[country_iso]

    def __iter__(self) -> Iterable[CountryPolygon]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)


@dataclass(frozen=True)
class TileBounds:
    """Axis-aligned bounding box for a raster cell in lon/lat degrees."""

    west: float
    south: float
    east: float
    north: float

    def to_polygon(self) -> Polygon:
        """Return a shapely polygon representing the cell footprint."""
        return Polygon(
            [
                (self.west, self.north),
                (self.east, self.north),
                (self.east, self.south),
                (self.west, self.south),
                (self.west, self.north),
            ]
        )


@dataclass(frozen=True)
class PopulationRaster:
    """Metadata necessary to derive geometry from the population raster."""

    path: Path
    transform: Affine
    width: int  # number of columns (ncols)
    height: int  # number of rows (nrows)
    crs: CRS
    nodata: float | int | None
    geod: Geod

    @property
    def ncols(self) -> int:
        return self.width

    @property
    def nrows(self) -> int:
        return self.height

    def ensure_valid_indices(self, row: int, col: int) -> None:
        if not (0 <= row < self.height and 0 <= col < self.width):
            raise LoaderError(f"Raster indices out of range (row={row}, col={col})")

    def tile_id(self, row: int, col: int) -> int:
        self.ensure_valid_indices(row, col)
        return row * self.width + col

    def tile_centroid(self, row: int, col: int) -> tuple[float, float]:
        self.ensure_valid_indices(row, col)
        lon, lat = transform_xy(self.transform, row, col, offset="center")
        return float(lon), float(lat)

    def tile_bounds(self, row: int, col: int) -> TileBounds:
        self.ensure_valid_indices(row, col)
        west_ul, north_ul = transform_xy(self.transform, row, col, offset="ul")
        east_lr, south_lr = transform_xy(self.transform, row, col, offset="lr")
        # Normalise ordering
        west_val = float(min(west_ul, east_lr))
        east_val = float(max(west_ul, east_lr))
        south_val = float(min(south_lr, north_ul))
        north_val = float(max(south_lr, north_ul))
        return TileBounds(west=west_val, south=south_val, east=east_val, north=north_val)

    def tile_polygon(self, row: int, col: int) -> Polygon:
        return self.tile_bounds(row, col).to_polygon()

    def tile_area(self, row: int, col: int) -> float:
        bounds = self.tile_bounds(row, col)
        lons = [bounds.west, bounds.east, bounds.east, bounds.west, bounds.west]
        lats = [bounds.north, bounds.north, bounds.south, bounds.south, bounds.north]
        area, _ = self.geod.polygon_area_perimeter(lons, lats)
        return abs(area)


def load_iso_countries(path: Path) -> IsoCountryTable:
    """Load the ISO canonical reference surface."""

    if not path.exists():
        raise LoaderError(f"ISO table '{path}' not found")
    frame = pl.read_parquet(path)
    if "country_iso" not in frame.columns:
        raise LoaderError("ISO table must include a 'country_iso' column")
    frame = frame.with_columns(pl.col("country_iso").cast(pl.Utf8).str.to_uppercase())
    return IsoCountryTable(table=frame)


def load_country_polygons(path: Path) -> CountryPolygons:
    """Load and prepare country polygons from the GeoParquet reference."""

    if not path.exists():
        raise LoaderError(f"Country polygon dataset '{path}' not found")
    gdf = gpd.read_parquet(path)
    if "country_iso" not in gdf.columns:
        raise LoaderError("Country polygon dataset must include a 'country_iso' column")
    if gdf.crs is None or not CRS.from_user_input(gdf.crs).is_geographic:
        raise LoaderError("Country polygon dataset must declare a geographic CRS (WGS84)")
    gdf["country_iso"] = gdf["country_iso"].str.upper()
    grouped = gdf.groupby("country_iso", dropna=False)
    polygons: Dict[str, CountryPolygon] = {}
    for iso_code, frame in grouped:
        if not iso_code or iso_code.strip() == "":
            raise LoaderError("Encountered empty country_iso in country polygons dataset")
        geometry = frame.geometry.unary_union
        if geometry.is_empty:
            raise LoaderError(f"Geometry for country '{iso_code}' is empty")
        polygons[iso_code] = CountryPolygon(
            country_iso=iso_code,
            geometry=geometry,
            prepared=prepare_geometry(geometry),
        )
    return CountryPolygons(polygons)


def load_population_raster(path: Path) -> PopulationRaster:
    """Load raster metadata required to derive tile geometry."""

    if not path.exists():
        raise LoaderError(f"Population raster '{path}' not found")
    with rasterio.open(path) as dataset:
        if dataset.crs is None:
            raise LoaderError("Population raster must declare a CRS (expected EPSG:4326)")
        if dataset.width <= 0 or dataset.height <= 0:
            raise LoaderError("Population raster must have positive dimensions")
        crs = dataset.crs
        if not crs.is_geographic:
            raise LoaderError("Population raster must be in a geographic CRS (WGS84)")
        geod = Geod.from_crs(crs)
        return PopulationRaster(
            path=path,
            transform=dataset.transform,
            width=dataset.width,
            height=dataset.height,
            crs=crs,
            nodata=dataset.nodata,
            geod=geod,
        )


__all__ = [
    "CountryPolygon",
    "CountryPolygons",
    "IsoCountryTable",
    "LoaderError",
    "PopulationRaster",
    "TileBounds",
    "load_country_polygons",
    "load_iso_countries",
    "load_population_raster",
]
