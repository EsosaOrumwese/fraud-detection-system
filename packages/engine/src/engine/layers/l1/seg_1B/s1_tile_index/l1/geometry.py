"""Geometry utilities for S1 Tile Index."""

from __future__ import annotations

from dataclasses import dataclass
from shapely.geometry import Polygon

from ..l0.loaders import PopulationRaster, TileBounds


@dataclass(frozen=True)
class TileMetrics:
    """Derived geometric properties for a single raster cell."""

    raster_row: int
    raster_col: int
    tile_id: int
    centroid_lon: float
    centroid_lat: float
    pixel_area_m2: float
    bounds: TileBounds

    def to_polygon(self) -> Polygon:
        return self.bounds.to_polygon()


def compute_tile_metrics(raster: PopulationRaster, row: int, col: int) -> TileMetrics:
    """Compute deterministic identifiers and geometry for a raster cell."""

    tile_id = raster.tile_id(row, col)
    centroid_lon, centroid_lat = raster.tile_centroid(row, col)
    bounds = raster.tile_bounds(row, col)
    area = raster.tile_area(row, col)
    return TileMetrics(
        raster_row=row,
        raster_col=col,
        tile_id=tile_id,
        centroid_lon=centroid_lon,
        centroid_lat=centroid_lat,
        pixel_area_m2=area,
        bounds=bounds,
    )


__all__ = ["TileMetrics", "compute_tile_metrics"]
