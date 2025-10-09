"""Helpers for building the merchant universe used by hurdle simulations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_1A.s0_foundations.l0.datasets import load_parquet_table

_CHANNEL_MAP = {
    "card_present": "CP",
    "card_not_present": "CNP",
}


@dataclass(frozen=True)
class MerchantUniverseSources:
    """Concrete file locations required to re-open the merchant ingress surface."""

    merchant_table: Path
    iso_table: Path
    gdp_table: Path
    bucket_table: Path

    def resolve(self) -> "MerchantUniverseSources":
        return MerchantUniverseSources(
            merchant_table=self.merchant_table.expanduser().resolve(),
            iso_table=self.iso_table.expanduser().resolve(),
            gdp_table=self.gdp_table.expanduser().resolve(),
            bucket_table=self.bucket_table.expanduser().resolve(),
        )


def load_enriched_universe(
    sources: MerchantUniverseSources,
    *,
    drop_missing: bool = True,
) -> pl.DataFrame:
    """Return the merchant universe enriched with bucket and GDP attributes."""

    resolved = sources.resolve()

    merchants = load_parquet_table(resolved.merchant_table).with_columns(
        [
            pl.col("merchant_id").cast(pl.Int64, strict=False),
            pl.col("home_country_iso").alias("country_iso"),
            pl.col("channel").replace(_CHANNEL_MAP).alias("channel"),
        ]
    )

    bucket_lookup = (
        load_parquet_table(resolved.bucket_table)
        .rename({"bucket_id": "gdp_bucket"})
        .with_columns(pl.col("gdp_bucket").cast(pl.Int32, strict=False))
    )
    gdp_lookup = load_parquet_table(resolved.gdp_table).rename(
        {"country_iso": "country_iso", "gdp_pc_usd_2015": "gdp_pc_usd_2015"}
    )

    enriched = (
        merchants.join(bucket_lookup.select("country_iso", "gdp_bucket"), on="country_iso", how="left")
        .join(gdp_lookup.select("country_iso", "gdp_pc_usd_2015"), on="country_iso", how="left")
        .with_columns(pl.col("gdp_pc_usd_2015").cast(pl.Float64, strict=False))
        .with_columns(pl.col("gdp_pc_usd_2015").log().alias("ln_gdp_pc_usd_2015"))
    )

    if drop_missing:
        enriched = enriched.filter(
            pl.col("gdp_pc_usd_2015").is_not_null() & pl.col("gdp_bucket").is_not_null()
        )

    return enriched.select(
        [
            "merchant_id",
            "mcc",
            "channel",
            "country_iso",
            "gdp_bucket",
            "gdp_pc_usd_2015",
            "ln_gdp_pc_usd_2015",
        ]
    )
