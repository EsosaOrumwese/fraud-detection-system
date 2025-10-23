"""Deterministic jitter kernel for Segment 1B state-6."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Mapping, Tuple

import polars as pl
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import PreparedGeometry

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine

from ..exceptions import err
from .rng import MODULE_NAME, SUBSTREAM_LABEL, derive_jitter_substream


@dataclass(frozen=True)
class TileBoundsRecord:
    west_lon: float
    east_lon: float
    south_lat: float
    north_lat: float


@dataclass(frozen=True)
class TileCentroidRecord:
    lon: float
    lat: float


@dataclass(frozen=True)
class CountryPolygonRecord:
    prepared: PreparedGeometry
    geometry: BaseGeometry


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

    dataset_rows: list[Mapping[str, object]] = []
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

    for row in assignments.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        iso_code = str(row["legal_country_iso"]).upper()
        site_order = int(row["site_order"])
        tile_id = int(row["tile_id"])
        key = (iso_code, tile_id)

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

        site_outside_pixel = 0
        site_outside_country = 0
        attempts = 0
        accepted_delta: Tuple[float, float] | None = None
        while attempts < MAX_ATTEMPTS:
            attempts += 1
            before_state = substream.snapshot()
            before_blocks = substream.blocks
            before_draws = substream.draws

            u_lon = substream.uniform()
            u_lat = substream.uniform()

            after_state = substream.snapshot()
            blocks_consumed = substream.blocks - before_blocks
            draws_consumed = substream.draws - before_draws
            if blocks_consumed != 1 or draws_consumed != 2:
                raise err(
                    "E610_RNG_BUDGET_OR_COUNTERS",
                    f"site ({merchant_id},{iso_code},{site_order}) consumed "
                    f"{blocks_consumed} blocks / {draws_consumed} draws",
                )

            lon = _interpolate_lon(bounds.west_lon, bounds.east_lon, u_lon)
            lat = bounds.south_lat + u_lat * (bounds.north_lat - bounds.south_lat)
            inside_pixel = _point_inside_pixel(lon, lat, bounds)
            if not inside_pixel:
                outside_pixel += 1
                site_outside_pixel += 1

            inside_country = _point_inside_country(lon, lat, polygon_record)
            if not inside_country:
                outside_country += 1
                site_outside_country += 1

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
                "attempt_index": attempts,
                "accepted": inside_pixel and inside_country,
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

            if inside_pixel and inside_country:
                accepted_delta = (delta_lon, delta_lat)
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
        dataset_rows.append(
            {
                "merchant_id": merchant_id,
                "legal_country_iso": iso_code,
                "site_order": site_order,
                "tile_id": tile_id,
                "delta_lat_deg": delta_lat,
                "delta_lon_deg": delta_lon,
                "manifest_fingerprint": manifest_fingerprint,
            }
        )

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
        stats["outside_pixel"] += site_outside_pixel
        stats["outside_country"] += site_outside_country

    events_total = len(rng_events)
    counter_span = _counter_span(first_counter, last_counter)

    frame = (
        pl.DataFrame(dataset_rows)
        .with_columns(
            [
                pl.col("merchant_id").cast(pl.Int64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("tile_id").cast(pl.UInt64),
                pl.col("delta_lat_deg").cast(pl.Float64),
                pl.col("delta_lon_deg").cast(pl.Float64),
                pl.col("manifest_fingerprint").cast(pl.Utf8).str.to_lowercase(),
            ]
        )
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )

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
        sites_total=assignments.height,
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


def _point_inside_pixel(lon: float, lat: float, bounds: TileBoundsRecord) -> bool:
    min_lon, max_lon = bounds.west_lon, bounds.east_lon
    min_lat, max_lat = bounds.south_lat, bounds.north_lat
    if max_lon < min_lon:
        max_lon += 360.0
        lon = lon if lon >= min_lon else lon + 360.0
    return (
        min_lon - EPSILON <= lon <= max_lon + EPSILON
        and min_lat - EPSILON <= lat <= max_lat + EPSILON
    )


def _point_inside_country(lon: float, lat: float, polygon: CountryPolygonRecord) -> bool:
    point = Point(lon, lat)
    if polygon.prepared.contains(point):
        return True
    if polygon.geometry.touches(point):
        return True
    return False


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
