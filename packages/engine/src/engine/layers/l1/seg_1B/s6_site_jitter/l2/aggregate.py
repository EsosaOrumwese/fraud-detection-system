"""Aggregation utilities for Segment 1B state-6."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine

from ..exceptions import err
from ..l1.jitter import (
    CountryPolygonRecord,
    TileBoundsRecord,
    TileCentroidRecord,
    compute_jitter,
)
from ..l1.jitter import JitterOutcome
from .prepare import PreparedInputs


@dataclass(frozen=True)
class JitterContext:
    """Execution context for the jitter kernel."""

    prepared: PreparedInputs
    engine: PhiloxEngine
    seed_int: int
    run_id: str


def build_context(prepared: PreparedInputs) -> JitterContext:
    """Construct the Philox engine and run identity."""

    try:
        seed_int = int(prepared.seed)
    except ValueError as exc:  # pragma: no cover - defensive
        raise err("E610_RNG_BUDGET_OR_COUNTERS", f"seed '{prepared.seed}' must be a base-10 integer") from exc
    if not (0 <= seed_int < 2**64):
        raise err("E610_RNG_BUDGET_OR_COUNTERS", f"seed {seed_int} outside [0, 2^64)")

    engine = PhiloxEngine(
        seed=seed_int,
        manifest_fingerprint=prepared.manifest_fingerprint,
    )
    run_id = uuid4().hex
    return JitterContext(prepared=prepared, engine=engine, seed_int=seed_int, run_id=run_id)


def execute_jitter(context: JitterContext) -> JitterOutcome:
    """Execute the jitter kernel and return the outcome payload."""

    prepared = context.prepared
    assignments = prepared.assignments.frame

    tile_bounds_map = {
        (row["country_iso"], int(row["tile_id"])): TileBoundsRecord(
            west_lon=float(row["west_lon"]),
            east_lon=float(row["east_lon"]),
            south_lat=float(row["south_lat"]),
            north_lat=float(row["north_lat"]),
        )
        for row in prepared.tile_bounds.frame.iter_rows(named=True)
    }

    tile_centroid_map = {
        (row["country_iso"], int(row["tile_id"])): TileCentroidRecord(
            lon=float(row["centroid_lon"]),
            lat=float(row["centroid_lat"]),
        )
        for row in prepared.tile_index.frame.iter_rows(named=True)
    }

    country_polygon_map = {
        country.country_iso: CountryPolygonRecord(
            prepared=country.prepared,
            geometry=country.geometry,
        )
        for country in prepared.country_polygons.polygons
    }

    return compute_jitter(
        engine=context.engine,
        manifest_fingerprint=prepared.manifest_fingerprint,
        seed_int=context.seed_int,
        run_id=context.run_id,
        parameter_hash=prepared.parameter_hash,
        assignments=assignments,
        tile_bounds=tile_bounds_map,
        tile_centroids=tile_centroid_map,
        country_polygons=country_polygon_map,
    )


__all__ = ["JitterContext", "build_context", "execute_jitter"]
