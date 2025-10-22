"""Fixed-dp quantisation for S2 tile weights."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, getcontext
from typing import Iterable, List

import polars as pl

from ..exceptions import err

# Ensure sufficient precision for accumulating weights before scaling.
getcontext().prec = 28


@dataclass(frozen=True)
class QuantisationResult:
    """Quantised weights and per-country normalisation summaries."""

    frame: pl.DataFrame
    summaries: list[dict[str, object]]


def quantise_tile_weights(*, mass_frame: pl.DataFrame, dp: int) -> QuantisationResult:
    """Apply largest-remainder quantisation at precision ``dp`` per country."""

    if dp < 0:
        raise ValueError("dp must be non-negative")
    if mass_frame.height == 0:
        empty = mass_frame.with_columns(
            pl.lit(dp).cast(pl.UInt32).alias("dp"),
            pl.lit(0, dtype=pl.UInt64).alias("weight_fp"),
            pl.lit(False).alias("zero_mass_fallback"),
        )
        return QuantisationResult(frame=empty, summaries=[])

    K = Decimal(10) ** dp
    K_int = int(K)

    records: List[dict[str, object]] = []
    summaries: List[dict[str, object]] = []

    grouped = mass_frame.sort(["country_iso", "tile_id"]).partition_by("country_iso", as_dict=True)
    for country_iso, country_df in grouped.items():
        rows = country_df.to_dicts()
        if not rows:
            continue

        masses = [Decimal(str(row["mass"])) for row in rows]
        total_mass = sum(masses)
        fallback = False
        if total_mass <= 0:
            fallback = True
            masses = [Decimal(1) for _ in masses]
            total_mass = Decimal(len(masses))

        weights = [mass / total_mass for mass in masses]
        quotas = [weight * K for weight in weights]

        base = [int(quota.to_integral_value(rounding=ROUND_FLOOR)) for quota in quotas]
        residues = [quota - Decimal(base[idx]) for idx, quota in enumerate(quotas)]
        shortfall = K_int - sum(base)

        # Largest residues first, tie-break ascending tile_id.
        ranked = sorted(
            range(len(rows)),
            key=lambda idx: (-residues[idx], int(rows[idx]["tile_id"])),
        )
        for idx in ranked[:shortfall]:
            base[idx] += 1

        if sum(base) != K_int:
            raise err(
                "E105_NORMALIZATION",
                f"quantisation sum mismatch for country {country_iso}",
            )

        _enforce_monotonicity(country_iso, masses, base)

        summaries.append(
            {
                "country_iso": country_iso,
                "tiles": len(rows),
                "mass_sum": float(total_mass),
                "prequant_sum_real": float(sum(weights)),
                "K": K_int,
                "postquant_sum_fp": sum(base),
                "residue_allocations": shortfall,
                "zero_mass_fallback": fallback,
            }
        )

        for idx, row in enumerate(rows):
            record = dict(row)
            record["dp"] = dp
            record["weight_fp"] = base[idx]
            record["zero_mass_fallback"] = fallback
            record["weight_real"] = float(weights[idx])
            record["residue"] = float(residues[idx])
            records.append(record)

    result_frame = pl.DataFrame(records).with_columns(
        pl.col("tile_id").cast(pl.UInt64),
        pl.col("weight_fp").cast(pl.UInt64),
        pl.col("dp").cast(pl.UInt32),
        pl.col("zero_mass_fallback").cast(pl.Boolean),
        pl.col("weight_real").cast(pl.Float64),
        pl.col("residue").cast(pl.Float64),
    )
    result_frame = result_frame.sort(["country_iso", "tile_id"])
    return QuantisationResult(frame=result_frame, summaries=summaries)


def _enforce_monotonicity(country_iso: str, masses: Iterable[Decimal], weights_fp: List[int]) -> None:
    """Ensure monotonicity and residue stability constraints."""

    masses_list = list(masses)
    for i, mass_a in enumerate(masses_list):
        for j, mass_b in enumerate(masses_list):
            if mass_a < mass_b:
                continue
            diff = weights_fp[j] - weights_fp[i]
            if diff > 1:
                raise err(
                    "E106_MONOTONICITY",
                    f"monotonicity violation for country {country_iso}: tile index {j} outranks {i}",
                )


__all__ = ["QuantisationResult", "quantise_tile_weights"]

