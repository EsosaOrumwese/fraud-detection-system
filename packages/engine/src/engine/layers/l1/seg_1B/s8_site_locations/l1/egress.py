"""Deterministic egress kernel for Segment 1B state-8."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

import polars as pl

from ..exceptions import err
from ..l0.datasets import S7SiteSynthesisPartition

SiteKey = Tuple[int, str, int]


@dataclass(frozen=True)
class ByCountryStats:
    """Per-country parity counters."""

    rows_s7: int
    rows_s8: int
    parity_ok: bool

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "rows_s7": self.rows_s7,
            "rows_s8": self.rows_s8,
            "parity_ok": self.parity_ok,
        }


@dataclass(frozen=True)
class S8Outcome:
    """Output payload from the egress kernel."""

    frame: pl.DataFrame
    rows_s7: int
    rows_s8: int
    parity_ok: bool
    schema_fail_count: int
    path_embed_mismatches: int
    writer_sort_violations: int
    order_leak_indicators: int
    by_country: Dict[str, ByCountryStats]


def compute_site_locations(*, synthesis: S7SiteSynthesisPartition) -> S8Outcome:
    """Compute site_locations rows and validation counters."""

    s7_frame = synthesis.frame
    rows_s7 = s7_frame.height

    if rows_s7 == 0:
        empty = pl.DataFrame(
            {
                "merchant_id": pl.Series([], dtype=pl.UInt64),
                "legal_country_iso": pl.Series([], dtype=pl.Utf8),
                "site_order": pl.Series([], dtype=pl.Int64),
                "lon_deg": pl.Series([], dtype=pl.Float64),
                "lat_deg": pl.Series([], dtype=pl.Float64),
            }
        )
        return S8Outcome(
            frame=empty,
            rows_s7=0,
            rows_s8=0,
            parity_ok=True,
            schema_fail_count=0,
            path_embed_mismatches=0,
            writer_sort_violations=0,
            order_leak_indicators=0,
            by_country={},
        )

    s7_keys = _key_set(s7_frame)
    if len(s7_keys) != rows_s7:
        raise err("E803_DUP_KEY", "s7_site_synthesis contains duplicate primary keys")

    s8_frame = (
        s7_frame.select(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("lon_deg").cast(pl.Float64),
                pl.col("lat_deg").cast(pl.Float64),
            ]
        )
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )

    rows_s8 = s8_frame.height
    s8_keys = _key_set(s8_frame)
    parity_ok = s7_keys == s8_keys
    if not parity_ok:
        missing = s7_keys - s8_keys
        extra = s8_keys - s7_keys
        if missing:
            raise err("E801_ROW_MISSING", f"site_locations missing {len(missing)} rows present in s7_site_synthesis")
        if extra:
            raise err("E802_ROW_EXTRA", f"site_locations contains {len(extra)} rows not present in s7_site_synthesis")

    writer_sort_violations = 0
    if s8_frame.rows() != s8_frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows():
        writer_sort_violations = 1

    by_country: Dict[str, ByCountryStats] = {}
    s7_per_country = (
        s7_frame.group_by("legal_country_iso")
        .len()
        .rename({"len": "rows_s7"})
        .with_columns(pl.col("legal_country_iso").str.to_uppercase())
    )
    s8_per_country = (
        s8_frame.group_by("legal_country_iso")
        .len()
        .rename({"len": "rows_s8"})
        .with_columns(pl.col("legal_country_iso").str.to_uppercase())
    )
    merged = s7_per_country.join(s8_per_country, on="legal_country_iso", how="full").fill_null(0)
    for row in merged.iter_rows(named=True):
        iso = str(row["legal_country_iso"])
        rows_iso_s7 = int(row.get("rows_s7", 0))
        rows_iso_s8 = int(row.get("rows_s8", 0))
        by_country[iso] = ByCountryStats(
            rows_s7=rows_iso_s7,
            rows_s8=rows_iso_s8,
            parity_ok=rows_iso_s7 == rows_iso_s8,
        )

    return S8Outcome(
        frame=s8_frame,
        rows_s7=rows_s7,
        rows_s8=rows_s8,
        parity_ok=parity_ok,
        schema_fail_count=0,
        path_embed_mismatches=0,
        writer_sort_violations=writer_sort_violations,
        order_leak_indicators=0,
        by_country=by_country,
    )


def _key_set(frame: pl.DataFrame) -> set[SiteKey]:
    return {
        (
            int(row[0]),
            str(row[1]).upper(),
            int(row[2]),
        )
        for row in frame.select(["merchant_id", "legal_country_iso", "site_order"]).iter_rows()
    }


__all__ = ["S8Outcome", "ByCountryStats", "compute_site_locations"]
