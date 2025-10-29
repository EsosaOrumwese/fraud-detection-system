"""Aggregation facade for Segment 1B State-4."""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping
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
    workers: int = 1


def build_allocation(context: AggregationContext) -> AllocationResult:
    """Compute per-tile allocations with streaming safeguards."""

    logger = logging.getLogger(__name__)
    requirements = context.requirements.frame.sort(["legal_country_iso", "merchant_id"])
    country_rank = (
        requirements.group_by("legal_country_iso")
        .agg(pl.col("merchant_id").min().alias("min_merchant"))
        .sort(["min_merchant", "legal_country_iso"])
    )
    countries = [str(code) for code in country_rank.get_column("legal_country_iso").to_list()]
    total_countries = len(countries)
    workers_configured = max(1, context.workers)
    workers = max(1, min(workers_configured, total_countries or 1))

    logger.info(
        "S4: building allocation (countries=%d, requirements_rows=%d, dp=%d, workers=%d)",
        total_countries,
        requirements.height,
        context.dp,
        workers,
    )

    _ensure_iso_fk(requirements, context.iso_table)

    temp_dir = _create_temp_dir(context.tile_weights.path.parent)
    writer = _AllocationBatchWriter(temp_dir=temp_dir)

    rows_emitted = 0
    shortfall_total = 0
    ties_broken_total = 0
    alloc_sum_equals_requirements = True
    merchant_summaries: dict[int, dict[str, int]] = {}
    country_timings: list[dict[str, object]] = []
    requirements_by_country: Dict[str, pl.DataFrame] = {
        country_iso: requirements.filter(pl.col("legal_country_iso") == country_iso)
        for country_iso in countries
    }

    def _process_country(country_iso: str, country_requirements: pl.DataFrame) -> tuple[AllocationCountryResult, int, float]:
        start = time.perf_counter()
        weights_df = context.tile_weights.collect_country(country_iso)
        index_df = context.tile_index.collect_country(country_iso)
        result = allocate_country_sites(
            requirements=country_requirements,
            tile_weights=weights_df,
            tile_index=index_df,
            dp=context.dp,
        )
        duration = time.perf_counter() - start
        return result, int(country_requirements.height), duration

    def _consume_result(
        idx: int,
        country_iso: str,
        requirements_rows: int,
        result: AllocationCountryResult,
        duration: float,
    ) -> None:
        nonlocal rows_emitted, shortfall_total, ties_broken_total, alloc_sum_equals_requirements

        if not result.frame.is_empty():
            writer.append(result.frame)
            rows_emitted += result.frame.height
            merge_merchant_summaries(merchant_summaries, result.frame)

        shortfall_total += result.shortfall_total
        ties_broken_total += result.ties_broken_total
        alloc_sum_equals_requirements = alloc_sum_equals_requirements and result.alloc_sum_equals_requirements
        country_timings.append(
            {
                "country_iso": country_iso,
                "requirements_rows": requirements_rows,
                "rows_emitted": int(result.frame.height),
                "wall_clock_seconds": float(duration),
            }
        )

        if (
            idx == 1
            or idx == total_countries
            or idx % 10 == 0
        ):
            logger.info(
                "S4: processed %d/%d countries (latest=%s merchants=%d rows_emitted=%d total_rows=%d wall_clock=%.2fs)",
                idx,
                total_countries,
                country_iso,
                requirements_rows,
                result.frame.height,
                rows_emitted,
                duration,
            )

    if total_countries == 0:
        logger.info("S4: no countries to allocate; emitting empty plan")
    elif workers == 1 or total_countries == 1:
        for idx, country_iso in enumerate(countries, start=1):
            result, requirements_rows, duration = _process_country(
                country_iso, requirements_by_country[country_iso]
            )
            _consume_result(idx, country_iso, requirements_rows, result, duration)
    else:
        logger.info("S4: enabling threaded allocation (workers=%d)", workers)
        pending: Dict[str, tuple[AllocationCountryResult, int, float]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_country, country_iso, requirements_by_country[country_iso]): country_iso
                for country_iso in countries
            }
            next_index = 0
            for future in concurrent.futures.as_completed(futures):
                country_iso = futures[future]
                pending[country_iso] = future.result()
                while next_index < total_countries:
                    expected_iso = countries[next_index]
                    if expected_iso not in pending:
                        break
                    result, requirements_rows, duration = pending.pop(expected_iso)
                    _consume_result(next_index + 1, expected_iso, requirements_rows, result, duration)
                    next_index += 1

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
        workers_used=workers,
        country_timings=country_timings,
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
