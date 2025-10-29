"""Aggregation facade for Segment 1B State-4."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Mapping
from uuid import uuid4

import polars as pl

from ..exceptions import err
from ..l0.datasets import (
    IsoCountryTable,
    S3RequirementsPartition,
    TileIndexPartition,
    TileWeightsPartition,
)
from ..l1.allocation import (
    AllocationResult,
    allocate_country_sites,
    merge_merchant_summaries,
    serialise_merchant_summaries,
)


@dataclass(frozen=True)
class AggregationContext:
    """Input surfaces prepared for allocation."""

    requirements: S3RequirementsPartition
    tile_weights: TileWeightsPartition
    tile_index: TileIndexPartition
    iso_table: IsoCountryTable
    dp: int


def build_allocation(context: AggregationContext) -> AllocationResult:
    """Compute per-tile allocations with streaming safeguards."""

    logger = logging.getLogger(__name__)
    requirements = context.requirements.frame.sort(["legal_country_iso", "merchant_id"])
    country_order = (
        requirements.group_by("legal_country_iso")
        .agg(pl.col("merchant_id").min().alias("min_merchant"))
        .sort(["min_merchant", "legal_country_iso"])
        .get_column("legal_country_iso")
        .to_list()
    )
    countries = [str(code) for code in country_order]
    total_countries = len(countries)

    logger.info(
        "S4: building allocation (countries=%d, requirements_rows=%d, dp=%d)",
        total_countries,
        requirements.height,
        context.dp,
    )

    _ensure_iso_fk(requirements, context.iso_table)

    temp_dir = _create_temp_dir(context.tile_weights.path.parent)
    writer = _AllocationBatchWriter(temp_dir=temp_dir)

    rows_emitted = 0
    shortfall_total = 0
    ties_broken_total = 0
    alloc_sum_equals_requirements = True
    merchant_summaries: dict[int, dict[str, int]] = {}

    for idx, country_iso in enumerate(countries, start=1):
        country_requirements = requirements.filter(pl.col("legal_country_iso") == country_iso)
        weights_df = context.tile_weights.collect_country(country_iso).sort("tile_id")
        index_df = context.tile_index.collect_country(country_iso).sort("tile_id")

        result = allocate_country_sites(
            requirements=country_requirements,
            tile_weights=weights_df,
            tile_index=index_df,
            dp=context.dp,
        )

        if not result.frame.is_empty():
            writer.append(result.frame)
            rows_emitted += result.frame.height
            merge_merchant_summaries(merchant_summaries, result.frame)

        shortfall_total += result.shortfall_total
        ties_broken_total += result.ties_broken_total
        alloc_sum_equals_requirements = alloc_sum_equals_requirements and result.alloc_sum_equals_requirements

        if (
            idx == 1
            or idx == total_countries
            or idx % 10 == 0
        ):
            logger.info(
                "S4: processed %d/%d countries (latest=%s merchants=%d rows_emitted=%d total_rows=%d)",
                idx,
                total_countries,
                country_iso,
                int(country_requirements.height),
                result.frame.height,
                rows_emitted,
            )

    writer.close()

    merchant_summaries_serialised = serialise_merchant_summaries(merchant_summaries)
    merchants_total = int(requirements.select(pl.col("merchant_id").n_unique()).item()) if not requirements.is_empty() else 0

    return AllocationResult(
        temp_dir=temp_dir,
        rows_emitted=rows_emitted,
        pairs_total=int(requirements.height),
        merchants_total=merchants_total,
        shortfall_total=shortfall_total,
        ties_broken_total=ties_broken_total,
        alloc_sum_equals_requirements=alloc_sum_equals_requirements,
        merchant_summaries=merchant_summaries_serialised,
    )


def _ensure_iso_fk(requirements: pl.DataFrame, iso_table: IsoCountryTable) -> None:
    observed = set(requirements.get_column("legal_country_iso").to_list())
    if not observed.issubset(iso_table.codes):
        missing = sorted(observed.difference(iso_table.codes))
        raise err(
            "E408_COVERAGE_MISSING",
            f"s3_requirements references ISO codes absent from canonical table: {missing}",
        )


def _create_temp_dir(base_path: Path) -> Path:
    temp_dir = base_path / f".tmp.s4_alloc_plan.{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    return temp_dir


class _AllocationBatchWriter:
    """Append-only parquet writer for streaming allocation output."""

    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self._shard_index = 0
        self._closed = False

    def append(self, frame: pl.DataFrame) -> None:
        if self._closed:
            raise RuntimeError("Cannot append to closed allocation writer")
        if frame.is_empty():
            return
        shard_path = self.temp_dir / f"part-{self._shard_index:05d}.parquet"
        frame.write_parquet(shard_path, compression="zstd")
        self._shard_index += 1

    def close(self) -> None:
        if self._closed:
            return
        if self._shard_index == 0:
            _AllocationBatchWriter._write_empty(self.temp_dir)
        self._closed = True

    @staticmethod
    def _write_empty(temp_dir: Path) -> None:
        _empty_allocation_frame().write_parquet(temp_dir / "part-00000.parquet", compression="zstd")


def _empty_allocation_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "merchant_id": pl.Series([], dtype=pl.UInt64),
            "legal_country_iso": pl.Series([], dtype=pl.Utf8),
            "tile_id": pl.Series([], dtype=pl.UInt64),
            "n_sites_tile": pl.Series([], dtype=pl.Int64),
        }
    )


__all__ = ["AggregationContext", "build_allocation"]
