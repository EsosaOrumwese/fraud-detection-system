"""Deterministic jitter kernel for Segment 1B state-6."""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Mapping, Tuple

import numpy as np
import polars as pl
from shapely import vectorized
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.prepared import PreparedGeometry

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine

from ..exceptions import err
from .rng import MODULE_NAME, SUBSTREAM_LABEL, derive_jitter_substream


@dataclass(frozen=True)
class TileBoundsRecord:
    min_lon_deg: float
    max_lon_deg: float
    min_lat_deg: float
    max_lat_deg: float


@dataclass(frozen=True)
class TileCentroidRecord:
    lon: float
    lat: float


@dataclass(frozen=True)
class CountryPolygonRecord:
    prepared: PreparedGeometry
    geometry: BaseGeometry
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@dataclass(frozen=True)
class JitterOutcome:
    """Output payload from the jitter kernel."""

    frame: pl.DataFrame
    rng_events: list[dict]
    sites_total: int
    events_total: int
    outside_pixel: int
    outside_country: int
    fk_tile_index_failures: int
    path_embed_mismatches: int
    by_country: Dict[str, Dict[str, object]]
    counter_span: int
    first_counter: Tuple[int, int] | None
    last_counter: Tuple[int, int] | None
    attempt_histogram: Dict[int, int]
    resample_sites: int
    resample_events: int


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


MAX_ATTEMPTS = 64
EPSILON = 1e-12
VECTOR_MODE_TRIGGER = 4
VECTOR_BATCH_SIZE = 8


def compute_jitter(
    *,
    engine: PhiloxEngine,
    manifest_fingerprint: str,
    seed_int: int,
    run_id: str,
    parameter_hash: str,
    assignments: pl.DataFrame,
    tile_bounds: Mapping[Tuple[str, int], TileBoundsRecord],
    tile_centroids: Mapping[Tuple[str, int], TileCentroidRecord],
    country_polygons: Mapping[str, CountryPolygonRecord],
) -> JitterOutcome:
    """Compute jitter deltas and RNG events for every site."""

    logger = logging.getLogger(__name__)
    frame = assignments.select(
        [
            pl.col("merchant_id").cast(pl.UInt64).alias("merchant_id"),
            pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase().alias("legal_country_iso"),
            pl.col("site_order").cast(pl.Int64).alias("site_order"),
            pl.col("tile_id").cast(pl.UInt64).alias("tile_id"),
        ]
    )

    merchant_ids = frame.get_column("merchant_id").to_list()
    iso_codes = frame.get_column("legal_country_iso").to_list()
    site_orders = frame.get_column("site_order").to_list()
    tile_ids = frame.get_column("tile_id").to_list()
    total_sites = len(merchant_ids)

    result_merchant_ids: list[int] = []
    result_iso_codes: list[str] = []
    result_site_orders: list[int] = []
    result_tile_ids: list[int] = []
    result_delta_lat: list[float] = []
    result_delta_lon: list[float] = []
    result_manifest: list[str] = []
    rng_events: list[dict] = []
    outside_pixel = 0
    outside_country = 0
    fk_tile_index_failures = 0
    path_embed_mismatches = 0
    per_country: Dict[str, Dict[str, object]] = {}
    first_counter: Tuple[int, int] | None = None
    last_counter: Tuple[int, int] | None = None
    attempts_hist: Counter[int] = Counter()
    resample_sites = 0
    resample_events = 0
    current_iso: str | None = None
    iso_start_time: float | None = None
    country_site_targets: Dict[str, int] = Counter(iso_codes)
    total_countries = len(country_site_targets)
    completed_countries = 0
    tile_ids_by_iso: Dict[str, set[int]] = {}
    tile_full_cover: Dict[str, set[int]] = {}

    tile_groups = (
        frame.group_by("legal_country_iso")
        .agg(pl.col("tile_id").unique())
        .to_dicts()
    )
    for row in tile_groups:
        iso = str(row["legal_country_iso"])
        ids = {int(value) for value in row["tile_id"]}
        tile_ids_by_iso[iso] = ids

    for merchant_id, iso_code, site_order, tile_id in zip(
        merchant_ids, iso_codes, site_orders, tile_ids, strict=True
    ):
        merchant_id = int(merchant_id)
        iso_code = str(iso_code)
        site_order = int(site_order)
        tile_id = int(tile_id)
        key = (iso_code, tile_id)

        if iso_code != current_iso:
            if current_iso is not None:
                stats_prev = per_country.get(current_iso)
                if stats_prev is not None:
                    completed_countries += 1
                    iso_elapsed = time.perf_counter() - iso_start_time if iso_start_time is not None else 0.0
                    logger.info(
                        "S6: jitter country %d/%d complete (iso=%s, sites=%d, rng_events=%d, elapsed=%.2fs)",
                        completed_countries,
                        total_countries,
                        current_iso,
                        stats_prev["sites"],
                        stats_prev["rng_events"],
                        iso_elapsed,
                    )
                if hasattr(tile_bounds, "release_iso"):
                    tile_bounds.release_iso(current_iso)
                if hasattr(tile_centroids, "release_iso"):
                    tile_centroids.release_iso(current_iso)
            current_iso = iso_code
            iso_start_time = time.perf_counter()
            expected_sites = country_site_targets.get(iso_code, 0)
            logger.info(
                "S6: jitter country %d/%d start (iso=%s, planned_sites=%d)",
                completed_countries + 1,
                total_countries,
                iso_code,
                expected_sites,
            )
            if hasattr(tile_bounds, "prime_iso"):
                tile_bounds.prime_iso(iso_code)
            if hasattr(tile_centroids, "prime_iso"):
                tile_centroids.prime_iso(iso_code)
            if iso_code not in tile_full_cover:
                tile_full_cover[iso_code] = _compute_full_cover_tiles(
                    iso_code=iso_code,
                    tile_ids=tile_ids_by_iso.get(iso_code, set()),
                    tile_bounds=tile_bounds,
                    polygon_record=country_polygons.get(iso_code),
                )

        bounds = tile_bounds.get(key)
        centroid = tile_centroids.get(key)
        polygon_record = country_polygons.get(iso_code)

        if bounds is None or centroid is None or polygon_record is None:
            fk_tile_index_failures += 1
            raise err(
                "E606_FK_TILE_INDEX",
                f"tile bounds or centroid missing for {(iso_code, tile_id)}",
            )

        substream = derive_jitter_substream(
            engine,
            merchant_id=merchant_id,
            legal_country_iso=iso_code,
            site_order=site_order,
            parameter_hash=parameter_hash,
        )

        attempts = 0
        accepted_delta: Tuple[float, float] | None = None
        vector_mode = False

        while attempts < MAX_ATTEMPTS:
            if not vector_mode:
                attempt_index = attempts + 1
                before_state = substream.snapshot()
                before_blocks = substream.blocks
                before_draws = substream.draws

                u_lon, u_lat = substream.uniform_pair()

                after_state = substream.snapshot()
                blocks_consumed = substream.blocks - before_blocks
                draws_consumed = substream.draws - before_draws
                if blocks_consumed != 1 or draws_consumed != 2:
                    raise err(
                        "E610_RNG_BUDGET_OR_COUNTERS",
                        f"site ({merchant_id},{iso_code},{site_order}) consumed "
                        f"{blocks_consumed} blocks / {draws_consumed} draws",
                    )

                lon = _interpolate_lon(bounds.min_lon_deg, bounds.max_lon_deg, u_lon)
                lat = bounds.min_lat_deg + u_lat * (bounds.max_lat_deg - bounds.min_lat_deg)
                inside_pixel = _point_inside_pixel(lon, lat, bounds)
                inside_country = (
                    tile_id in tile_full_cover.get(iso_code, set())
                    or _point_inside_country(lon, lat, polygon_record)
                )

                delta_lon = _normalise_delta(lon - centroid.lon)
                delta_lat = lat - centroid.lat

                event_payload = {
                    "merchant_id": merchant_id,
                    "legal_country_iso": iso_code,
                    "site_order": site_order,
                    "sigma_lat_deg": 0.0,
                    "sigma_lon_deg": 0.0,
                    "delta_lat_deg": delta_lat,
                    "delta_lon_deg": delta_lon,
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "seed": seed_int,
                    "run_id": run_id,
                    "module": MODULE_NAME,
                    "substream_label": SUBSTREAM_LABEL,
                    "ts_utc": _utc_timestamp(),
                    "rng_counter_before_hi": int(before_state.counter_hi),
                    "rng_counter_before_lo": int(before_state.counter_lo),
                    "rng_counter_after_hi": int(after_state.counter_hi),
                    "rng_counter_after_lo": int(after_state.counter_lo),
                    "blocks": 1,
                    "draws": "2",
                }
                rng_events.append(event_payload)

                if first_counter is None:
                    first_counter = (int(before_state.counter_hi), int(before_state.counter_lo))
                last_counter = (int(after_state.counter_hi), int(after_state.counter_lo))

                attempts = attempt_index
                if inside_pixel and inside_country:
                    accepted_delta = (delta_lon, delta_lat)
                    break

                if attempts >= VECTOR_MODE_TRIGGER:
                    vector_mode = True
                continue

            attempts_before_batch = attempts
            batch_size = min(VECTOR_BATCH_SIZE, MAX_ATTEMPTS - attempts)
            batch_meta: list[dict] = []
            u_lon_batch = np.empty(batch_size, dtype=np.float64)
            u_lat_batch = np.empty(batch_size, dtype=np.float64)

            for idx in range(batch_size):
                before_state = substream.snapshot()
                before_blocks = substream.blocks
                before_draws = substream.draws

                u_lon_val, u_lat_val = substream.uniform_pair()

                after_state = substream.snapshot()
                blocks_consumed = substream.blocks - before_blocks
                draws_consumed = substream.draws - before_draws
                if blocks_consumed != 1 or draws_consumed != 2:
                    raise err(
                        "E610_RNG_BUDGET_OR_COUNTERS",
                        f"site ({merchant_id},{iso_code},{site_order}) consumed "
                        f"{blocks_consumed} blocks / {draws_consumed} draws",
                    )

                batch_meta.append(
                    {
                        "before_state": before_state,
                        "after_state": after_state,
                        "before_blocks": before_blocks,
                        "before_draws": before_draws,
                    }
                )
                u_lon_batch[idx] = u_lon_val
                u_lat_batch[idx] = u_lat_val
                attempts += 1

                if attempts >= MAX_ATTEMPTS:
                    batch_size = idx + 1
                    u_lon_batch = u_lon_batch[:batch_size]
                    u_lat_batch = u_lat_batch[:batch_size]
                    batch_meta = batch_meta[:batch_size]
                    break

            lon_batch = _vector_interpolate_lon(bounds.min_lon_deg, bounds.max_lon_deg, u_lon_batch)
            lat_batch = bounds.min_lat_deg + u_lat_batch * (bounds.max_lat_deg - bounds.min_lat_deg)
            pixel_mask = _vector_inside_pixel(lon_batch, lat_batch, bounds)
            if tile_id in tile_full_cover.get(iso_code, set()):
                country_mask = np.ones_like(lon_batch, dtype=bool)
            else:
                country_mask = _vector_inside_country(lon_batch, lat_batch, polygon_record)
            accepted_mask = pixel_mask & country_mask

            accepted_index: int | None = None
            accepted_meta: dict | None = None

            for idx, meta in enumerate(batch_meta):
                attempt_index = attempts_before_batch + idx + 1
                delta_lon = _normalise_delta(lon_batch[idx] - centroid.lon)
                delta_lat = lat_batch[idx] - centroid.lat
                accepted_flag = bool(accepted_mask[idx])

                event_payload = {
                    "merchant_id": merchant_id,
                    "legal_country_iso": iso_code,
                    "site_order": site_order,
                    "sigma_lat_deg": 0.0,
                    "sigma_lon_deg": 0.0,
                    "delta_lat_deg": delta_lat,
                    "delta_lon_deg": delta_lon,
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "seed": seed_int,
                    "run_id": run_id,
                    "module": MODULE_NAME,
                    "substream_label": SUBSTREAM_LABEL,
                    "ts_utc": _utc_timestamp(),
                    "rng_counter_before_hi": int(meta["before_state"].counter_hi),
                    "rng_counter_before_lo": int(meta["before_state"].counter_lo),
                    "rng_counter_after_hi": int(meta["after_state"].counter_hi),
                    "rng_counter_after_lo": int(meta["after_state"].counter_lo),
                    "blocks": 1,
                    "draws": "2",
                }
                rng_events.append(event_payload)

                if first_counter is None:
                    first_counter = (
                        int(meta["before_state"].counter_hi),
                        int(meta["before_state"].counter_lo),
                    )
                last_counter = (
                    int(meta["after_state"].counter_hi),
                    int(meta["after_state"].counter_lo),
                )

                if accepted_flag:
                    accepted_delta = (delta_lon, delta_lat)
                    accepted_index = idx
                    accepted_meta = meta
                    attempts = attempts_before_batch + idx + 1
                    break

            if accepted_index is not None and accepted_meta is not None:
                substream.counter_hi = accepted_meta["after_state"].counter_hi
                substream.counter_lo = accepted_meta["after_state"].counter_lo
                setattr(substream, "_blocks_consumed", accepted_meta["before_blocks"] + 1)
                setattr(substream, "_draws_consumed", accepted_meta["before_draws"] + 2)
                break

            if attempts >= MAX_ATTEMPTS:
                break

        if accepted_delta is None:
            raise err(
                "E613_RESAMPLE_EXHAUSTED",
                f"resample exhausted for site ({merchant_id},{iso_code},{site_order})",
            )

        attempts_hist[attempts] += 1
        if attempts > 1:
            resample_sites += 1
            resample_events += attempts - 1

        delta_lon, delta_lat = accepted_delta
        result_merchant_ids.append(merchant_id)
        result_iso_codes.append(iso_code)
        result_site_orders.append(site_order)
        result_tile_ids.append(tile_id)
        result_delta_lat.append(delta_lat)
        result_delta_lon.append(delta_lon)
        result_manifest.append(manifest_fingerprint)

        stats = per_country.setdefault(
            iso_code,
            {
                "sites": 0,
                "rng_events": 0,
                "rng_draws": 0,
                "outside_pixel": 0,
                "outside_country": 0,
            },
        )
        stats["sites"] += 1
        stats["rng_events"] += attempts
        stats["rng_draws"] += attempts * 2

    events_total = len(rng_events)
    counter_span = _counter_span(first_counter, last_counter)

    if current_iso is not None:
        stats_prev = per_country.get(current_iso)
        if stats_prev is not None:
            completed_countries += 1
            iso_elapsed = time.perf_counter() - iso_start_time if iso_start_time is not None else 0.0
            logger.info(
                "S6: jitter country %d/%d complete (iso=%s, sites=%d, rng_events=%d, elapsed=%.2fs)",
                completed_countries,
                total_countries,
                current_iso,
                stats_prev["sites"],
                stats_prev["rng_events"],
                iso_elapsed,
            )
        if hasattr(tile_bounds, "release_iso"):
            tile_bounds.release_iso(current_iso)
        if hasattr(tile_centroids, "release_iso"):
            tile_centroids.release_iso(current_iso)

    frame = pl.DataFrame(
        {
            "merchant_id": pl.Series(result_merchant_ids, dtype=pl.UInt64),
            "legal_country_iso": pl.Series(result_iso_codes, dtype=pl.Utf8),
            "site_order": pl.Series(result_site_orders, dtype=pl.Int64),
            "tile_id": pl.Series(result_tile_ids, dtype=pl.UInt64),
            "delta_lat_deg": pl.Series(result_delta_lat, dtype=pl.Float64),
            "delta_lon_deg": pl.Series(result_delta_lon, dtype=pl.Float64),
            "manifest_fingerprint": pl.Series(result_manifest, dtype=pl.Utf8),
        }
    ).with_columns(
        [
            pl.col("legal_country_iso").str.to_uppercase(),
            pl.col("manifest_fingerprint").str.to_lowercase(),
        ]
    ).sort(["merchant_id", "legal_country_iso", "site_order"])

    by_country_serialisable = {
        iso: {
            "sites": stats["sites"],
            "rng_events": stats["rng_events"],
            "rng_draws": str(stats["rng_draws"]),
            "outside_pixel": stats["outside_pixel"],
            "outside_country": stats["outside_country"],
        }
        for iso, stats in per_country.items()
    }

    return JitterOutcome(
        frame=frame,
        rng_events=rng_events,
        sites_total=total_sites,
        events_total=events_total,
        outside_pixel=outside_pixel,
        outside_country=outside_country,
        fk_tile_index_failures=fk_tile_index_failures,
        path_embed_mismatches=path_embed_mismatches,
        by_country=by_country_serialisable,
        counter_span=counter_span,
        first_counter=first_counter,
        last_counter=last_counter,
        attempt_histogram=dict(attempts_hist),
        resample_sites=resample_sites,
        resample_events=resample_events,
    )


def _interpolate_lon(west: float, east: float, u: float) -> float:
    """Interpolate longitude respecting dateline wrapping."""

    width = east - west
    if width < 0.0:
        width += 360.0
    lon = west + u * width
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lon


def _vector_interpolate_lon(west: float, east: float, u: np.ndarray) -> np.ndarray:
    """Vectorised longitude interpolation for jitter resamples."""

    u = np.asarray(u, dtype=np.float64)
    width = east - west
    if width < 0.0:
        lon = west + u * (width + 360.0)
    else:
        lon = west + u * width
    lon = ((lon + 180.0) % 360.0) - 180.0
    return lon


def _point_inside_pixel(lon: float, lat: float, bounds: TileBoundsRecord) -> bool:
    min_lon, max_lon = bounds.min_lon_deg, bounds.max_lon_deg
    min_lat, max_lat = bounds.min_lat_deg, bounds.max_lat_deg
    if max_lon < min_lon:
        max_lon += 360.0
        lon = lon if lon >= min_lon else lon + 360.0
    return (
        min_lon - EPSILON <= lon <= max_lon + EPSILON
        and min_lat - EPSILON <= lat <= max_lat + EPSILON
    )


def _vector_inside_pixel(lon: np.ndarray, lat: np.ndarray, bounds: TileBoundsRecord) -> np.ndarray:
    """Vectorised in-pixel check."""

    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    min_lon, max_lon = bounds.min_lon_deg, bounds.max_lon_deg
    min_lat, max_lat = bounds.min_lat_deg, bounds.max_lat_deg
    if max_lon < min_lon:
        lon_cmp = np.where(lon >= min_lon, lon, lon + 360.0)
        max_lon_cmp = max_lon + 360.0
    else:
        lon_cmp = lon
        max_lon_cmp = max_lon
    return (
        (lon_cmp >= (min_lon - EPSILON))
        & (lon_cmp <= (max_lon_cmp + EPSILON))
        & (lat >= (min_lat - EPSILON))
        & (lat <= (max_lat + EPSILON))
    )


def _point_inside_country(lon: float, lat: float, polygon: CountryPolygonRecord) -> bool:
    if (
        lon < polygon.min_lon - EPSILON
        or lon > polygon.max_lon + EPSILON
        or lat < polygon.min_lat - EPSILON
        or lat > polygon.max_lat + EPSILON
    ):
        return False
    point = Point(lon, lat)
    if polygon.prepared.contains(point):
        return True
    if polygon.geometry.touches(point):
        return True
    return False


def _vector_inside_country(lon: np.ndarray, lat: np.ndarray, polygon: CountryPolygonRecord) -> np.ndarray:
    """Vectorised point-in-country check with bounding-box short circuit."""

    lon = np.asarray(lon, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    mask = (
        (lon >= polygon.min_lon - EPSILON)
        & (lon <= polygon.max_lon + EPSILON)
        & (lat >= polygon.min_lat - EPSILON)
        & (lat <= polygon.max_lat + EPSILON)
    )
    if not bool(mask.any()):
        return np.zeros_like(lon, dtype=bool)
    contains = vectorized.contains(polygon.geometry, lon[mask], lat[mask])
    touches = vectorized.touches(polygon.geometry, lon[mask], lat[mask])
    result = np.zeros_like(lon, dtype=bool)
    result[mask] = np.logical_or(contains, touches)
    return result


def _compute_full_cover_tiles(
    *,
    iso_code: str,
    tile_ids: Iterable[int],
    tile_bounds: Mapping[Tuple[str, int], TileBoundsRecord],
    polygon_record: CountryPolygonRecord | None,
) -> set[int]:
    """Identify tiles fully covered by the country polygon to skip per-site checks."""

    if polygon_record is None:
        return set()
    covered: set[int] = set()
    geometry = polygon_record.geometry
    for tile_id in tile_ids:
        bounds = tile_bounds.get((iso_code, tile_id))
        if bounds is None:
            continue
        if bounds.max_lon_deg < bounds.min_lon_deg:
            # Dateline-crossing tiles are not safe to short-circuit.
            continue
        if (
            bounds.min_lon_deg < polygon_record.min_lon - EPSILON
            or bounds.max_lon_deg > polygon_record.max_lon + EPSILON
            or bounds.min_lat_deg < polygon_record.min_lat - EPSILON
            or bounds.max_lat_deg > polygon_record.max_lat + EPSILON
        ):
            continue
        tile_box = box(
            bounds.min_lon_deg,
            bounds.min_lat_deg,
            bounds.max_lon_deg,
            bounds.max_lat_deg,
        )
        if geometry.covers(tile_box):
            covered.add(int(tile_id))
    return covered


def _normalise_delta(delta: float) -> float:
    if delta > 180.0:
        delta -= 360.0
    if delta < -180.0:
        delta += 360.0
    return delta


def _counter_span(
    first_counter: Tuple[int, int] | None, last_counter: Tuple[int, int] | None
) -> int:
    if first_counter is None or last_counter is None:
        return 0
    first = (first_counter[0] << 64) | first_counter[1]
    last = (last_counter[0] << 64) | last_counter[1]
    return max(0, last - first)


__all__ = ["JitterOutcome", "compute_jitter", "TileBoundsRecord", "TileCentroidRecord", "CountryPolygonRecord"]
