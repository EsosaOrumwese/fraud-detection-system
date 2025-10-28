"""Deterministic allocation kernels for Segment 1B State-4."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import polars as pl

from ..exceptions import err


@dataclass(frozen=True)
class AllocationResult:
    """Allocation output and summary statistics."""

    frame: pl.DataFrame
    rows_emitted: int
    pairs_total: int
    merchants_total: int
    shortfall_total: int
    ties_broken_total: int
    alloc_sum_equals_requirements: bool


def allocate_sites(
    requirements: pl.DataFrame,
    tile_weights: pl.DataFrame,
    tile_index: pl.DataFrame,
    *,
    dp: int,
) -> AllocationResult:
    """Compute integer allocations per tile that sum to S3 requirements."""

    logger = logging.getLogger(__name__)
    if requirements.is_empty():
        logger.info("S4: allocation kernel received empty requirements; emitting empty result")
        return AllocationResult(
            frame=pl.DataFrame(
                schema={
                    "merchant_id": pl.UInt64,
                    "legal_country_iso": pl.Utf8,
                    "tile_id": pl.UInt64,
                    "n_sites_tile": pl.Int64,
                }
            ),
            rows_emitted=0,
            pairs_total=0,
            merchants_total=0,
            shortfall_total=0,
            ties_broken_total=0,
            alloc_sum_equals_requirements=True,
        )

    requirements = requirements.select(
        [
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("legal_country_iso").cast(pl.Utf8),
            pl.col("n_sites").cast(pl.Int64),
        ]
    )

    weights = tile_weights.select(
        [
            pl.col("country_iso").cast(pl.Utf8),
            pl.col("tile_id").cast(pl.UInt64),
            pl.col("weight_fp").cast(pl.Int64),
        ]
    )
    index = tile_index.select(
        [
            pl.col("country_iso").cast(pl.Utf8),
            pl.col("tile_id").cast(pl.UInt64),
        ]
    )
    logger.info(
        "S4: allocation kernel inputs (requirements_rows=%d, tile_weights_rows=%d, tile_index_rows=%d, dp=%d)",
        requirements.height,
        weights.height,
        index.height,
        dp,
    )

    # Coverage: every weight must have a corresponding tile index entry.
    missing_tiles = (
        weights.join(index, on=["country_iso", "tile_id"], how="anti").height
    )
    if missing_tiles:
        raise err(
            "E408_COVERAGE_MISSING",
            "tile_weights contain tiles absent from tile_index",
        )

    joined = requirements.join(
        weights,
        left_on="legal_country_iso",
        right_on="country_iso",
        how="left",
    )
    logger.info("S4: join completed (joined_rows=%d)", joined.height)
    if joined.get_column("tile_id").is_null().any():
        raise err(
            "E402_WEIGHTS_MISSING",
            "tile_weights missing coverage for at least one requirements pair",
        )

    K = 10 ** dp
    product = pl.col("weight_fp") * pl.col("n_sites")
    joined = joined.with_columns(
        [
            product.alias("product"),
            (product // K).alias("base_allocation"),
            (product % K).alias("residue"),
        ]
    )

    base_sums = (
        joined.group_by(["merchant_id", "legal_country_iso", "n_sites"])
        .agg(pl.col("base_allocation").sum().alias("base_sum"), pl.len().alias("tile_count"))
        .with_columns(
            (pl.col("n_sites") - pl.col("base_sum")).alias("shortfall")
        )
    )

    if (base_sums.get_column("shortfall") < 0).any():
        raise err("E403_SHORTFALL_MISMATCH", "base allocations exceed required counts")

    if (
        (base_sums.get_column("shortfall") > base_sums.get_column("tile_count"))
        .any()
    ):
        raise err(
            "E403_SHORTFALL_MISMATCH",
            "insufficient tiles to distribute shortfall",
        )

    joined = joined.join(
        base_sums.select(
            ["merchant_id", "legal_country_iso", "base_sum", "shortfall"]
        ),
        on=["merchant_id", "legal_country_iso"],
        how="left",
    )

    # Sort by residue desc, tile_id asc for deterministic bump order.
    joined = joined.with_columns(
        pl.col("residue").cast(pl.Int64).alias("residue_int")
    ).sort(
        ["merchant_id", "legal_country_iso", "residue_int", "tile_id"],
        descending=[False, False, True, False],
    )

    joined = joined.with_columns(
        (pl.cum_count("tile_id").over(["merchant_id", "legal_country_iso"]) - 1).alias("order")
    )

    joined = joined.with_columns(
        (pl.col("order") < pl.col("shortfall"))
        .cast(pl.Int64)
        .alias("bump"),
    )

    joined = joined.with_columns(
        (pl.col("base_allocation") + pl.col("bump")).alias("n_sites_tile")
    )
    logger.info("S4: base allocations computed (rows=%d)", joined.height)

    # Sum-to-n verification.
    totals = (
        joined.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            [
                pl.col("n_sites_tile").sum().alias("alloc_sum"),
                pl.col("n_sites").first().alias("n_sites"),
            ]
        )
    )
    if (totals.get_column("alloc_sum") != totals.get_column("n_sites")).any():
        raise err(
            "E403_SHORTFALL_MISMATCH",
            "final allocations do not sum to S3 requirements",
        )

    shortfall_total = int(base_sums.get_column("shortfall").sum())

    bump_df = joined.filter(pl.col("bump") == 1)
    if bump_df.is_empty():
        ties_broken_total = 0
    else:
        tie_counts = (
            bump_df.group_by(["merchant_id", "legal_country_iso"])
            .agg(
                [
                    pl.col("residue").count().alias("count"),
                    pl.col("residue").n_unique().alias("unique_residues"),
                ]
            )
            .with_columns(
                (pl.col("count") - pl.col("unique_residues")).alias("ties")
            )
        )
        ties_broken_total = int(tie_counts.get_column("ties").sum())

    final_frame = (
        joined.select(
            [
                "merchant_id",
                "legal_country_iso",
                "tile_id",
                "n_sites_tile",
            ]
        )
        .filter(pl.col("n_sites_tile") > 0)
        .sort(["merchant_id", "legal_country_iso", "tile_id"])
    )

    merchants_total = int(requirements.get_column("merchant_id").n_unique())
    pairs_total = int(
        requirements.select(pl.col("merchant_id"), pl.col("legal_country_iso")).unique().height
    )
    alloc_sum_equals_requirements = bool(
        (totals.get_column("alloc_sum") == totals.get_column("n_sites")).all()
    )
    logger.info(
        "S4: allocation kernel finished (rows_emitted=%d, merchants=%d, pairs=%d, shortfall=%d, ties_broken=%d)",
        final_frame.height,
        merchants_total,
        pairs_total,
        shortfall_total,
        ties_broken_total,
    )

    return AllocationResult(
        frame=final_frame,
        rows_emitted=final_frame.height,
        pairs_total=pairs_total,
        merchants_total=merchants_total,
        shortfall_total=shortfall_total,
        ties_broken_total=ties_broken_total,
        alloc_sum_equals_requirements=alloc_sum_equals_requirements,
    )


__all__ = ["AllocationResult", "allocate_sites"]
