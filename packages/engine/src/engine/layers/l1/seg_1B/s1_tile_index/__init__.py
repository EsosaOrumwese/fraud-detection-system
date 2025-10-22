"""Segment 1B — State 1 (Tile Index) primitives."""

from .l0.loaders import (
    CountryPolygon,
    CountryPolygons,
    IsoCountryTable,
    LoaderError,
    PopulationRaster,
    TileBounds,
    load_country_polygons,
    load_iso_countries,
    load_population_raster,
)
from .l1.geometry import TileMetrics, compute_tile_metrics
from .l1.predicates import InclusionRule, evaluate_inclusion

__all__ = [
    "CountryPolygon",
    "CountryPolygons",
    "IsoCountryTable",
    "LoaderError",
    "PopulationRaster",
    "TileBounds",
    "TileMetrics",
    "InclusionRule",
    "compute_tile_metrics",
    "evaluate_inclusion",
    "load_country_polygons",
    "load_iso_countries",
    "load_population_raster",
]
