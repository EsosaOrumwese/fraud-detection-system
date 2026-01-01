"""Deterministic allocation helpers for Segment 1B State-4."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import polars as pl

from ..exceptions import err


@dataclass(frozen=True)
class AllocationCountryResult:
    """Allocation outcome for a single country."""

    frame: pl.DataFrame
    shortfall_total: int
    ties_broken_total: int
    alloc_sum_equals_requirements: bool


@dataclass(frozen=True)
class AllocationResult:
    """Streaming allocation artefacts aggregated across all countries."""

    temp_dir: Path
    rows_emitted: int
    pairs_total: int
    merchants_total: int
    shortfall_total: int
    ties_broken_total: int
    alloc_sum_equals_requirements: bool
    merchant_summaries: list[dict[str, object]]
    workers_used: int
    country_timings: list[dict[str, object]]


def allocate_country_sites(
    *,
    requirements: pl.DataFrame,
    tile_weights: pl.DataFrame,
    tile_index: pl.DataFrame,
    dp: int,
) -> AllocationCountryResult:
    """Allocate site counts for a single country."""

    if requirements.is_empty():
        return AllocationCountryResult(
            frame=_empty_allocation_frame(),
            shortfall_total=0,
            ties_broken_total=0,
            alloc_sum_equals_requirements=True,
        )

    country_iso = requirements.item(0, "legal_country_iso")

    if tile_weights.is_empty():
        raise err(
            "E402_WEIGHTS_MISSING",
            f"tile_weights missing coverage for country '{country_iso}'",
        )
    if tile_index.is_empty():
        raise err(
            "E408_COVERAGE_MISSING",
            f"tile_index missing coverage for country '{country_iso}'",
        )

    weight_tiles = tile_weights.get_column("tile_id").to_numpy()
    index_tiles = tile_index.get_column("tile_id").to_numpy()
    if weight_tiles.size != index_tiles.size or not np.array_equal(weight_tiles, index_tiles):
        raise err(
            "E408_COVERAGE_MISSING",
            f"tile_weights contain tiles absent from tile_index for country '{country_iso}'",
        )

    weights_fp = tile_weights.get_column("weight_fp").to_numpy().astype(np.uint64, copy=False)
    tile_ids = weight_tiles.astype(np.uint64, copy=False)
    K = np.uint64(10**dp)

    merchants = requirements.get_column("merchant_id").to_numpy().astype(np.uint64, copy=False)
    n_sites = requirements.get_column("n_sites").to_numpy().astype(np.int64, copy=False)

    frames: list[pl.DataFrame] = []
    shortfall_total = 0
    ties_broken_total = 0
    alloc_sum_equals_requirements = True

    product_buffer = np.empty(weights_fp.shape[0], dtype=np.uint64)
    allocation_buffer = np.empty(weights_fp.shape[0], dtype=np.int64)
    residue_buffer = np.empty(weights_fp.shape[0], dtype=np.int64)

    for merchant_id, sites_required in zip(merchants, n_sites):
        if sites_required <= 0:
            raise err(
                "E403_SHORTFALL_MISMATCH",
                f"merchant {merchant_id} in country '{country_iso}' requested non-positive sites",
            )

        np.multiply(weights_fp, np.uint64(sites_required), out=product_buffer, casting="unsafe")
        np.floor_divide(product_buffer, K, out=allocation_buffer, casting="unsafe")
        np.remainder(product_buffer, K, out=residue_buffer, casting="unsafe")

        allocation = allocation_buffer
        base_sum = int(allocation.sum())
        shortfall = int(sites_required - base_sum)
        if shortfall < 0:
            raise err(
                "E403_SHORTFALL_MISMATCH",
                f"base allocations exceed required counts for merchant {merchant_id} in '{country_iso}'",
            )

        ties = 0

        if shortfall > 0:
            if shortfall > allocation.size:
                raise err(
                    "E403_SHORTFALL_MISMATCH",
                    f"insufficient tiles to distribute shortfall for merchant {merchant_id} in '{country_iso}'",
                )
            order = np.lexsort((tile_ids, -residue_buffer))
            selection = order[:shortfall]
            allocation[selection] = allocation[selection] + 1
            selected_residue = residue_buffer[selection]
            ties = int(len(selected_residue) - np.unique(selected_residue).size)

        if allocation.sum() != sites_required:
            alloc_sum_equals_requirements = False
            raise err(
                "E403_SHORTFALL_MISMATCH",
                f"final allocations do not sum to requirements for merchant {merchant_id} in '{country_iso}'",
            )

        positive_mask = allocation > 0
        if positive_mask.any():
            frames.append(
                pl.DataFrame(
                    {
                        "merchant_id": pl.Series(
                            np.full(int(positive_mask.sum()), merchant_id, dtype=np.uint64)
                        ),
                        "legal_country_iso": pl.Series(
                            [country_iso] * int(positive_mask.sum()), dtype=pl.Utf8
                        ),
                        "tile_id": pl.Series(tile_ids[positive_mask], dtype=pl.UInt64),
                        "n_sites_tile": pl.Series(
                            allocation[positive_mask].astype(np.int64, copy=False),
                            dtype=pl.Int64,
                        ),
                    }
                )
            )

        shortfall_total += shortfall
        ties_broken_total += ties

    if frames:
        frame = pl.concat(frames, how="vertical").sort(["merchant_id", "legal_country_iso", "tile_id"])
    else:
        frame = _empty_allocation_frame()

    return AllocationCountryResult(
        frame=frame,
        shortfall_total=shortfall_total,
        ties_broken_total=ties_broken_total,
        alloc_sum_equals_requirements=alloc_sum_equals_requirements,
    )


def _empty_allocation_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "merchant_id": pl.Series([], dtype=pl.UInt64),
            "legal_country_iso": pl.Series([], dtype=pl.Utf8),
            "tile_id": pl.Series([], dtype=pl.UInt64),
            "n_sites_tile": pl.Series([], dtype=pl.Int64),
        }
    )


def merge_merchant_summaries(
    destination: Dict[int, Dict[str, int]],
    frame: pl.DataFrame,
) -> None:
    """Accumulate per-merchant observability metrics."""

    if frame.is_empty():
        return
    summary = (
        frame.group_by("merchant_id")
        .agg(
            [
                pl.n_unique("legal_country_iso").alias("countries"),
                pl.col("n_sites_tile").sum().alias("n_sites_total"),
                pl.len().alias("pairs"),
            ]
        )
    )
    for row in summary.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        current = destination.setdefault(
            merchant_id,
            {"countries": 0, "n_sites_total": 0, "pairs": 0},
        )
        current["countries"] += int(row["countries"])
        current["n_sites_total"] += int(row["n_sites_total"])
        current["pairs"] += int(row["pairs"])


def serialise_merchant_summaries(
    summaries: Dict[int, Dict[str, int]],
) -> list[dict[str, object]]:
    """Convert aggregated merchant summaries into run-report payload."""

    return [
        {
            "merchant_id": merchant_id,
            "countries": values["countries"],
            "n_sites_total": values["n_sites_total"],
            "pairs": values["pairs"],
        }
        for merchant_id, values in sorted(summaries.items())
    ]


__all__ = [
    "AllocationCountryResult",
    "AllocationResult",
    "allocate_country_sites",
    "merge_merchant_summaries",
    "serialise_merchant_summaries",
]
