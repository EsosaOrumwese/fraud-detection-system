"""Aggregation utilities for Segment 1B state-6."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Tuple
from uuid import uuid4

import numpy as np
import pyarrow.dataset as ds

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


def build_context(prepared: PreparedInputs, *, run_id_override: str | None = None) -> JitterContext:
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
    if run_id_override is not None:
        run_id = str(run_id_override).strip()
        if not run_id:
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "run_id_override must be non-empty when provided")
    else:
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

    country_polygon_map = {}
    for country in prepared.country_polygons.polygons:
        min_lon, min_lat, max_lon, max_lat = country.geometry.bounds
        country_polygon_map[country.country_iso] = CountryPolygonRecord(
            prepared=country.prepared,
            geometry=country.geometry,
            min_lon=float(min_lon),
            min_lat=float(min_lat),
            max_lon=float(max_lon),
            max_lat=float(max_lat),
        )

    jitter_start = time.perf_counter()
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

    jitter_elapsed = time.perf_counter() - jitter_start
    logger.info(
        "S6: jitter completed (sites=%d, rng_events=%d, outside_country=%d, outside_pixel=%d, elapsed=%.2fs)",
        outcome.sites_total,
        outcome.events_total,
        outcome.outside_country,
        outcome.outside_pixel,
        jitter_elapsed,
    )

    return outcome


__all__ = ["JitterContext", "build_context", "execute_jitter"]




@dataclass(frozen=True)
class _TileBoundsArray:
    tile_ids: np.ndarray
    west: np.ndarray
    east: np.ndarray
    south: np.ndarray
    north: np.ndarray
    index_map: Dict[int, int]

    def lookup(self, tile_id: int) -> TileBoundsRecord | None:
        idx = self.index_map.get(int(tile_id))
        if idx is None:
            return None
        return TileBoundsRecord(
            west_lon=float(self.west[idx]),
            east_lon=float(self.east[idx]),
            south_lat=float(self.south[idx]),
            north_lat=float(self.north[idx]),
        )


@dataclass(frozen=True)
class _TileCentroidArray:
    tile_ids: np.ndarray
    lon: np.ndarray
    lat: np.ndarray
    index_map: Dict[int, int]

    def lookup(self, tile_id: int) -> TileCentroidRecord | None:
        idx = self.index_map.get(int(tile_id))
        if idx is None:
            return None
        return TileCentroidRecord(
            lon=float(self.lon[idx]),
            lat=float(self.lat[idx]),
        )

class _TileBoundsCache:
    """Lazy loader for tile bounds keyed by ISO + tile."""

    def __init__(self, partition) -> None:
        self._partition = partition
        self._cache: Dict[str, _TileBoundsArray] = {}

    def get(self, key: Tuple[str, int], default=None) -> TileBoundsRecord | None:
        iso, tile_id = key
        iso = str(iso).upper()
        cache = self._cache.get(iso)
        if cache is None:
            cache = self._load_iso(iso)
            self._cache[iso] = cache
        return cache.lookup(int(tile_id)) if cache is not None else default

    def prime_iso(self, iso: str) -> None:
        iso = str(iso).upper()
        if iso not in self._cache:
            self._cache[iso] = self._load_iso(iso)

    def release_iso(self, iso: str) -> None:
        self._cache.pop(str(iso).upper(), None)

    def _load_iso(self, iso: str) -> _TileBoundsArray:
        table = self._partition.dataset.to_table(
            columns=["tile_id", "west_lon", "east_lon", "south_lat", "north_lat"],
            filter=ds.field("country_iso") == iso,
        )
        if table.num_rows == 0:
            empty = np.empty(0, dtype=np.float64)
            return _TileBoundsArray(
                tile_ids=np.empty(0, dtype=np.uint64),
                west=empty,
                east=empty,
                south=empty,
                north=empty,
                index_map={},
            )

        tile_ids = np.asarray(table.column("tile_id").to_numpy(zero_copy_only=False), dtype=np.uint64)
        west = np.asarray(table.column("west_lon").to_numpy(zero_copy_only=False), dtype=np.float64)
        east = np.asarray(table.column("east_lon").to_numpy(zero_copy_only=False), dtype=np.float64)
        south = np.asarray(table.column("south_lat").to_numpy(zero_copy_only=False), dtype=np.float64)
        north = np.asarray(table.column("north_lat").to_numpy(zero_copy_only=False), dtype=np.float64)

        if tile_ids.size:
            order = np.argsort(tile_ids, kind="mergesort")
            tile_ids = tile_ids[order]
            west = west[order]
            east = east[order]
            south = south[order]
            north = north[order]
            index_map = {int(tile_id): int(idx) for idx, tile_id in enumerate(tile_ids)}
        else:
            index_map = {}

        return _TileBoundsArray(tile_ids=tile_ids, west=west, east=east, south=south, north=north, index_map=index_map)


class _TileCentroidCache:
    """Lazy loader for tile centroids keyed by ISO + tile."""

    def __init__(self, partition) -> None:
        self._partition = partition
        self._cache: Dict[str, _TileCentroidArray] = {}

    def get(self, key: Tuple[str, int], default=None) -> TileCentroidRecord | None:
        iso, tile_id = key
        iso = str(iso).upper()
        cache = self._cache.get(iso)
        if cache is None:
            cache = self._load_iso(iso)
            self._cache[iso] = cache
        return cache.lookup(int(tile_id)) if cache is not None else default

    def prime_iso(self, iso: str) -> None:
        iso = str(iso).upper()
        if iso not in self._cache:
            self._cache[iso] = self._load_iso(iso)

    def release_iso(self, iso: str) -> None:
        self._cache.pop(str(iso).upper(), None)

    def _load_iso(self, iso: str) -> _TileCentroidArray:
        table = self._partition.dataset.to_table(
            columns=["tile_id", "centroid_lon", "centroid_lat"],
            filter=ds.field("country_iso") == iso,
        )
        if table.num_rows == 0:
            empty = np.empty(0, dtype=np.float64)
            return _TileCentroidArray(
                tile_ids=np.empty(0, dtype=np.uint64),
                lon=empty,
                lat=empty,
                index_map={},
            )

        tile_ids = np.asarray(table.column("tile_id").to_numpy(zero_copy_only=False), dtype=np.uint64)
        lon = np.asarray(table.column("centroid_lon").to_numpy(zero_copy_only=False), dtype=np.float64)
        lat = np.asarray(table.column("centroid_lat").to_numpy(zero_copy_only=False), dtype=np.float64)

        if tile_ids.size:
            order = np.argsort(tile_ids, kind="mergesort")
            tile_ids = tile_ids[order]
            lon = lon[order]
            lat = lat[order]
            index_map = {int(tile_id): int(idx) for idx, tile_id in enumerate(tile_ids)}
        else:
            index_map = {}

        return _TileCentroidArray(tile_ids=tile_ids, lon=lon, lat=lat, index_map=index_map)
