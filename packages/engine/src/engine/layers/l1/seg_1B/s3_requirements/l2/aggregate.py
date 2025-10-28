"""Aggregation logic for S3 requirements."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import IsoCountryTable

from ..exceptions import err
from ..l0.datasets import TileWeightsPartition
from ..l1.validators import (
    aggregate_site_requirements,
    ensure_iso_fk,
    ensure_positive_counts,
    ensure_weights_coverage,
)


@dataclass(frozen=True)
class AggregationResult:
    """In-memory representation of S3 requirements prior to materialisation."""

    frame: pl.DataFrame
    source_rows_total: int

    @property
    def rows_emitted(self) -> int:
        return self.frame.height

    @property
    def merchants_total(self) -> int:
        if self.frame.is_empty():
            return 0
        return self.frame.select(pl.col("merchant_id").n_unique()).item()  # type: ignore[no-any-return]

    @property
    def countries_total(self) -> int:
        if self.frame.is_empty():
            return 0
        return self.frame.select(pl.col("legal_country_iso").n_unique()).item()  # type: ignore[no-any-return]


def compute_requirements(
    *,
    outlet_frame: pl.DataFrame,
    iso_table: IsoCountryTable,
    tile_weights: TileWeightsPartition,
) -> AggregationResult:
    """Compute deterministic requirements from the outlet catalogue."""

    grouped = aggregate_site_requirements(outlet_frame)
    grouped = grouped.sort(["merchant_id", "legal_country_iso"])

    ensure_positive_counts(grouped)
    ensure_iso_fk(grouped, set(iso_table.codes))

    synthetic_codes = frozenset(
        iso_table.table
        .with_columns(pl.col("region").cast(pl.Utf8).str.to_uppercase().alias("region_norm"))
        .filter(pl.col("region_norm") == "SYNTHETIC")
        .get_column("country_iso")
        .to_list()
    )
    if synthetic_codes:
        grouped = grouped.filter(~pl.col("legal_country_iso").is_in(sorted(synthetic_codes)))

    if tile_weights.frame.is_empty():
        raise err(
            "E303_MISSING_WEIGHTS",
            "tile_weights partition contains no rows; cannot satisfy coverage requirement",
        )
    coverage_countries = tile_weights.frame.get_column("country_iso").cast(pl.Utf8).to_list()
    ensure_weights_coverage(grouped, coverage_countries, ignored_countries=synthetic_codes)

    return AggregationResult(frame=grouped, source_rows_total=int(outlet_frame.height))


__all__ = ["AggregationResult", "compute_requirements"]
