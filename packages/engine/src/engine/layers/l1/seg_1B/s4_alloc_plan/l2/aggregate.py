"""Aggregation facade for Segment 1B State-4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import polars as pl

from ..exceptions import err
from ..l0.datasets import (
    IsoCountryTable,
    S3RequirementsPartition,
    TileIndexPartition,
    TileWeightsPartition,
)
from ..l1.allocation import AllocationResult, allocate_sites


@dataclass(frozen=True)
class AggregationContext:
    """Input surfaces prepared for allocation."""

    requirements: S3RequirementsPartition
    tile_weights: TileWeightsPartition
    tile_index: TileIndexPartition
    iso_table: IsoCountryTable
    dp: int


def build_allocation(context: AggregationContext) -> AllocationResult:
    """Compute per-tile allocations with validation guards."""

    _ensure_iso_fk(context.requirements.frame, context.iso_table)
    result = allocate_sites(
        requirements=context.requirements.frame,
        tile_weights=context.tile_weights.frame,
        tile_index=context.tile_index.frame,
        dp=context.dp,
    )
    if result.rows_emitted and result.frame.is_empty():
        raise err("E403_SHORTFALL_MISMATCH", "allocation produced empty dataset unexpectedly")
    return result


def _ensure_iso_fk(requirements: pl.DataFrame, iso_table: IsoCountryTable) -> None:
    observed = set(requirements.get_column("legal_country_iso").to_list())
    if not observed.issubset(iso_table.codes):
        missing = sorted(observed.difference(iso_table.codes))
        raise err(
            "E408_COVERAGE_MISSING",
            f"s3_requirements references ISO codes absent from canonical table: {missing}",
        )


__all__ = ["AggregationContext", "build_allocation"]
