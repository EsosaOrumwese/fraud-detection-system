"""Inclusion predicate evaluation for S1 Tile Index."""

from __future__ import annotations

from enum import Enum
from shapely.geometry import Point

from ..l0.loaders import CountryPolygon
from .geometry import TileMetrics


class InclusionRule(str, Enum):
    """Supported inclusion predicates for S1."""

    CENTER = "center"
    ANY_OVERLAP = "any_overlap"

    @classmethod
    def parse(cls, value: str) -> "InclusionRule":
        try:
            return cls(value)
        except ValueError as err:
            allowed = ", ".join(rule.value for rule in cls)
            raise ValueError(f"Unsupported inclusion rule '{value}'. Allowed values: {allowed}") from err


def evaluate_inclusion(rule: InclusionRule, country: CountryPolygon, metrics: TileMetrics) -> bool:
    """Return True if the tile satisfies the inclusion predicate for the country."""

    if rule is InclusionRule.CENTER:
        point = Point(metrics.centroid_lon, metrics.centroid_lat)
        return country.prepared.covers(point)

    tile_polygon = metrics.to_polygon()
    intersection = country.geometry.intersection(tile_polygon)
    return intersection.area > 0.0


__all__ = ["InclusionRule", "evaluate_inclusion"]
