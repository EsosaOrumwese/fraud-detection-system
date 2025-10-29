"""Aggregation utilities for Segment 1B state-6."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Tuple
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
    assignments = prepared.assignments.frame.sort(["legal_country_iso", "merchant_id", "site_order"])
    required_countries = [str(code).upper() for code in assignments.get_column("legal_country_iso").unique().to_list()]

    logger = logging.getLogger(__name__)
    logger.info(
        "S6: jitter starting (countries=%d, sites=%d)",
        len(required_countries),
        assignments.height,
    )

    tile_bounds_cache = _TileBoundsCache(prepared.tile_bounds)
    tile_centroid_cache = _TileCentroidCache(prepared.tile_index)

    country_polygon_map = {
        country.country_iso: CountryPolygonRecord(
            prepared=country.prepared,
            geometry=country.geometry,
        )
        for country in prepared.country_polygons.polygons
    }

    outcome = compute_jitter(
        engine=context.engine,
        manifest_fingerprint=prepared.manifest_fingerprint,
        seed_int=context.seed_int,
        run_id=context.run_id,
        parameter_hash=prepared.parameter_hash,
        assignments=assignments,
        tile_bounds=tile_bounds_cache,
        tile_centroids=tile_centroid_cache,
        country_polygons=country_polygon_map,
    )

    logger.info(
        "S6: jitter completed (sites=%d, rng_events=%d, outside_country=%d, outside_pixel=%d)",
        outcome.sites_total,
        outcome.events_total,
        outcome.outside_country,
        outcome.outside_pixel,
    )

    return outcome


__all__ = ["JitterContext", "build_context", "execute_jitter"]


class _TileBoundsCache:
    """Lazy loader for tile bounds keyed by ISO + tile."""

    def __init__(self, partition) -> None:
        self._partition = partition
        self._cache: Dict[str, Dict[int, TileBoundsRecord]] = {}

    def get(self, key: Tuple[str, int], default=None) -> TileBoundsRecord | None:
        iso, tile_id = key
        iso = str(iso).upper()
        cache = self._cache.get(iso)
        if cache is None:
            cache = self._load_iso(iso)
            self._cache[iso] = cache
        return cache.get(int(tile_id), default)

    def prime_iso(self, iso: str) -> None:
        iso = str(iso).upper()
        if iso not in self._cache:
            self._cache[iso] = self._load_iso(iso)

    def release_iso(self, iso: str) -> None:
        self._cache.pop(str(iso).upper(), None)

    def _load_iso(self, iso: str) -> Dict[int, TileBoundsRecord]:
        frame = self._partition.collect_country(iso)
        return {
            int(row["tile_id"]): TileBoundsRecord(
                west_lon=float(row["west_lon"]),
                east_lon=float(row["east_lon"]),
                south_lat=float(row["south_lat"]),
                north_lat=float(row["north_lat"]),
            )
            for row in frame.iter_rows(named=True)
        }


class _TileCentroidCache:
    """Lazy loader for tile centroids keyed by ISO + tile."""

    def __init__(self, partition) -> None:
        self._partition = partition
        self._cache: Dict[str, Dict[int, TileCentroidRecord]] = {}

    def get(self, key: Tuple[str, int], default=None) -> TileCentroidRecord | None:
        iso, tile_id = key
        iso = str(iso).upper()
        cache = self._cache.get(iso)
        if cache is None:
            cache = self._load_iso(iso)
            self._cache[iso] = cache
        return cache.get(int(tile_id), default)

    def prime_iso(self, iso: str) -> None:
        iso = str(iso).upper()
        if iso not in self._cache:
            self._cache[iso] = self._load_iso(iso)

    def release_iso(self, iso: str) -> None:
        self._cache.pop(str(iso).upper(), None)

    def _load_iso(self, iso: str) -> Dict[int, TileCentroidRecord]:
        frame = self._partition.collect_country(
            iso,
            columns=("country_iso", "tile_id", "centroid_lon", "centroid_lat"),
        )
        return {
            int(row["tile_id"]): TileCentroidRecord(
                lon=float(row["centroid_lon"]),
                lat=float(row["centroid_lat"]),
            )
            for row in frame.iter_rows(named=True)
        }
