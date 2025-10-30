"""Deterministic synthesis kernel for Segment 1B state-7."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

import polars as pl

from ..exceptions import err
from ..l0.datasets import (
    OutletCataloguePartition,
    S5AssignmentPartition,
    S6JitterPartition,
    TileBoundsPartition,
)

SiteKey = Tuple[int, str, int]


@dataclass(frozen=True)
class ByCountryStats:
    """Per-country validation counters."""

    sites_s7: int
    fk_tile_fail: int
    outside_pixel: int
    coverage_1a_miss: int

    def to_dict(self) -> dict[str, int]:
        return {
            "sites_s7": self.sites_s7,
            "fk_tile_fail": self.fk_tile_fail,
            "outside_pixel": self.outside_pixel,
            "coverage_1a_miss": self.coverage_1a_miss,
        }


@dataclass(frozen=True)
class S7Outcome:
    """Output payload from the synthesis kernel."""

    frame: pl.DataFrame
    sites_total_s5: int
    sites_total_s6: int
    sites_total_s7: int
    parity_s5_s7_ok: bool
    parity_s5_s6_ok: bool
    fk_tile_ok_count: int
    fk_tile_fail_count: int
    inside_pixel_ok_count: int
    inside_pixel_fail_count: int
    coverage_ok_count: int
    coverage_miss_count: int
    by_country: Dict[str, ByCountryStats]


def compute_site_synthesis(
    *,
    assignments: S5AssignmentPartition,
    jitter: S6JitterPartition,
    tile_bounds: TileBoundsPartition,
    outlet_catalogue: OutletCataloguePartition,
) -> S7Outcome:
    """Compute S7 site synthesis rows and validation counters."""

    s5 = assignments.frame
    s6 = jitter.frame
    outlet = outlet_catalogue.frame

    keys = ["merchant_id", "legal_country_iso", "site_order"]

    _assert_no_duplicates(s5, keys, code="E703_DUP_KEY", label="s5_site_tile_assignment")
    _assert_no_duplicates(s6, keys, code="E703_DUP_KEY", label="s6_site_jitter")

    missing_in_s6 = s5.join(s6, on=keys, how="anti")
    if missing_in_s6.height:
        raise err(
            "E701_ROW_MISSING",
            f"s6_site_jitter missing {missing_in_s6.height} site rows present in s5_site_tile_assignment",
        )

    extra_in_s6 = s6.join(s5, on=keys, how="anti")
    if extra_in_s6.height:
        raise err(
            "E702_ROW_EXTRA",
            f"s6_site_jitter contains {extra_in_s6.height} site rows not present in s5_site_tile_assignment",
        )

    s6_renamed = s6.rename(
        {
            "tile_id": "tile_id_s6",
            "delta_lon_deg": "delta_lon_deg_s6",
            "delta_lat_deg": "delta_lat_deg_s6",
        }
    )
    joined = s5.join(s6_renamed, on=keys, how="inner")
    # sanity: ensure tile_id matches S5 vs S6 (should be identical)
    mismatch_tile = joined.filter(pl.col("tile_id") != pl.col("tile_id_s6"))
    if mismatch_tile.height:
        raise err(
            "E799_INTERNAL",
            "tile_id mismatch between S5 assignments and S6 jitter",
        )

    joined = joined.with_columns(
        [
            pl.col("delta_lon_deg_s6").alias("delta_lon_deg"),
            pl.col("delta_lat_deg_s6").alias("delta_lat_deg"),
        ]
    ).select(
        [
            pl.col("merchant_id"),
            pl.col("legal_country_iso"),
            pl.col("site_order"),
            pl.col("tile_id"),
            pl.col("delta_lon_deg"),
            pl.col("delta_lat_deg"),
        ]
    )

    enriched_parts: list[pl.DataFrame] = []
    for iso_frame in joined.partition_by("legal_country_iso", maintain_order=True):
        if iso_frame.height == 0:
            continue
        iso_value = str(iso_frame.item(0, "legal_country_iso"))
        tile_frame = tile_bounds.collect_country(
            iso_value,
            tile_ids=iso_frame.get_column("tile_id").unique(),
        )
        if tile_frame.is_empty():
            missing = iso_frame.height
            raise err(
                "E709_TILE_FK_VIOLATION",
                f"{missing} S7 rows reference tiles missing from tile_bounds for ISO {iso_value}",
            )
        enriched_iso = iso_frame.join(tile_frame, on="tile_id", how="left")
        enriched_parts.append(enriched_iso)

    if not enriched_parts:
        enriched = pl.DataFrame()
    else:
        enriched = pl.concat(enriched_parts, how="vertical")

    missing_tile = enriched.filter(pl.col("centroid_lon_deg").is_null())
    if missing_tile.height:
        raise err(
            "E709_TILE_FK_VIOLATION",
            f"{missing_tile.height} S7 rows reference tiles missing from tile_bounds",
        )

    records = []
    inside_ok = 0
    inside_fail = 0
    fk_tile_ok = enriched.height
    by_country: Dict[str, ByCountryStats] = {}

    for row in enriched.iter_rows(named=True):
        lon_deg = float(row["centroid_lon_deg"]) + float(row["delta_lon_deg"])
        lat_deg = float(row["centroid_lat_deg"]) + float(row["delta_lat_deg"])

        if not _point_inside_pixel(
            lon_deg,
            lat_deg,
            float(row["min_lon_deg"]),
            float(row["max_lon_deg"]),
            float(row["min_lat_deg"]),
            float(row["max_lat_deg"]),
        ):
            inside_fail += 1
            raise err(
                "E707_POINT_OUTSIDE_PIXEL",
                f"reconstructed point ({lon_deg},{lat_deg}) outside tile bounds for "
                f"({row['legal_country_iso']}, {row['tile_id']})",
            )

        inside_ok += 1
        iso = str(row["legal_country_iso"])
        stats = by_country.get(iso)
        if stats is None:
            stats = ByCountryStats(sites_s7=0, fk_tile_fail=0, outside_pixel=0, coverage_1a_miss=0)
        by_country[iso] = ByCountryStats(
            sites_s7=stats.sites_s7 + 1,
            fk_tile_fail=stats.fk_tile_fail,
            outside_pixel=stats.outside_pixel,
            coverage_1a_miss=stats.coverage_1a_miss,
        )

        records.append(
            {
                "merchant_id": int(row["merchant_id"]),
                "legal_country_iso": iso,
                "site_order": int(row["site_order"]),
                "tile_id": int(row["tile_id"]),
                "lon_deg": lon_deg,
                "lat_deg": lat_deg,
            }
        )

    s7_frame = (
        pl.DataFrame(records)
        .with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("tile_id").cast(pl.UInt64),
                pl.col("lon_deg").cast(pl.Float64),
                pl.col("lat_deg").cast(pl.Float64),
            ]
        )
        .sort(keys)
    )

    s7_keys = _to_site_key_set(s7_frame)
    outlet_keys = _to_site_key_set(outlet)

    missing_in_outlet = s7_keys - outlet_keys
    extra_outlet = outlet_keys - s7_keys
    coverage_miss = len(missing_in_outlet) + len(extra_outlet)
    if coverage_miss:
        for iso, stats in by_country.items():
            # keep dictionary updated with misses when possible
            misses_for_iso = sum(1 for key in missing_in_outlet if key[1] == iso)
            by_country[iso] = ByCountryStats(
                sites_s7=stats.sites_s7,
                fk_tile_fail=stats.fk_tile_fail,
                outside_pixel=stats.outside_pixel,
                coverage_1a_miss=stats.coverage_1a_miss + misses_for_iso,
            )
        raise err(
            "E708_1A_COVERAGE_FAIL",
            "S7 site keys do not match outlet_catalogue coverage "
            f"(missing_in_outlet={len(missing_in_outlet)}, extra_outlet={len(extra_outlet)})",
        )

    coverage_ok = len(s7_keys)

    parity_s5_s7_ok = s7_keys == _to_site_key_set(s5)
    parity_s5_s6_ok = s7_keys == _to_site_key_set(s6)

    return S7Outcome(
        frame=s7_frame,
        sites_total_s5=s5.height,
        sites_total_s6=s6.height,
        sites_total_s7=s7_frame.height,
        parity_s5_s7_ok=parity_s5_s7_ok,
        parity_s5_s6_ok=parity_s5_s6_ok,
        fk_tile_ok_count=fk_tile_ok,
        fk_tile_fail_count=0,
        inside_pixel_ok_count=inside_ok,
        inside_pixel_fail_count=inside_fail,
        coverage_ok_count=coverage_ok,
        coverage_miss_count=0,
        by_country=by_country,
    )


def _assert_no_duplicates(frame: pl.DataFrame, keys: list[str], *, code: str, label: str) -> None:
    dupes = (
        frame.group_by(keys)
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
    )
    if dupes.height:
        raise err(code, f"{label} contains {dupes.height} duplicate primary keys")


def _point_inside_pixel(
    lon_deg: float,
    lat_deg: float,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
) -> bool:
    """Inclusive rectangle test with dateline handling."""

    lon = lon_deg
    if max_lon < min_lon:
        adjusted_max = max_lon + 360.0
        lon = lon if lon >= min_lon else lon + 360.0
        max_lon = adjusted_max
    epsilon = 1e-9
    lon_ok = (min_lon - epsilon) <= lon <= (max_lon + epsilon)
    lat_ok = (min_lat - epsilon) <= lat_deg <= (max_lat + epsilon)
    return lon_ok and lat_ok


def _to_site_key_set(frame: pl.DataFrame) -> set[SiteKey]:
    return {
        (
            int(row[0]),
            str(row[1]).upper(),
            int(row[2]),
        )
        for row in frame.select(["merchant_id", "legal_country_iso", "site_order"]).iter_rows()
    }


__all__ = ["S7Outcome", "ByCountryStats", "compute_site_synthesis"]
