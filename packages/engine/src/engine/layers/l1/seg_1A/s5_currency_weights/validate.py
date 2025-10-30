"""Validation helpers for S5 datasets."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

__all__ = ["ValidationError", "validate_weights_df"]


class ValidationError(ValueError):
    """Raised when persisted S5 outputs violate the contract."""


def validate_weights_df(df: pd.DataFrame, *, parameter_hash: str, tolerance: float = 1e-6) -> None:
    """Validate the persisted weights cache for basic invariants.

    Parameters
    ----------
    df: DataFrame containing the persisted rows.
    parameter_hash: Expected parameter hash that must match the embedded column.
    tolerance: Allowed absolute tolerance when checking group sums.
    """

    required_cols = {"parameter_hash", "currency", "country_iso", "weight"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValidationError(f"weights dataframe missing columns: {sorted(missing)}")

    if df.empty:
        return

    unique_hashes = df["parameter_hash"].unique()
    if len(unique_hashes) != 1 or unique_hashes[0] != parameter_hash:
        raise ValidationError("embedded parameter_hash does not match partition")

    if df.duplicated(subset=["currency", "country_iso"]).any():
        raise ValidationError("duplicate (currency, country_iso) rows detected")

    if not ((df["weight"] >= -tolerance) & (df["weight"] <= 1.0 + tolerance)).all():
        raise ValidationError("weights must lie within [0, 1]")

    if "obs_count" in df.columns and (df["obs_count"] < 0).any():
        raise ValidationError("obs_count must be non-negative")

    grouped = df.groupby("currency")
    for currency, group in grouped:
        total = group["weight"].sum()
        if abs(total - 1.0) > tolerance:
            raise ValidationError(f"weight sum for {currency} outside tolerance: {total}")
        if group["weight"].isna().any():
            raise ValidationError(f"NaN weights detected for {currency}")
