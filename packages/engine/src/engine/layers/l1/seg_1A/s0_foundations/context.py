"""Run context structures for Segment 1A S0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import polars as pl


@dataclass(frozen=True)
class MerchantUniverse:
    frame: pl.DataFrame
    iso_set: set[str]


@dataclass(frozen=True)
class RunContext:
    merchants: MerchantUniverse
    gdp_per_capita: Mapping[str, float]
    gdp_bucket_map: Mapping[str, int]
    channel_map: Mapping[str, str]
    merchant_u64_column: str = "merchant_u64"
