"""Validation helpers for S3 requirements."""

from __future__ import annotations

from typing import Iterable, Set

import polars as pl

from ..exceptions import err


REQUIRED_OUTLET_COLUMNS = frozenset({"merchant_id", "legal_country_iso", "site_order"})


def validate_outlet_columns(frame: pl.DataFrame) -> None:
    """Ensure mandatory outlet columns are present."""

    missing = REQUIRED_OUTLET_COLUMNS.difference(frame.columns)
    if missing:
        raise err(
            "E305_SCHEMA_INVALID",
            f"outlet_catalogue missing required columns: {sorted(missing)}",
        )


def validate_path_embeddings(
    frame: pl.DataFrame, *, manifest_fingerprint: str, seed: str
) -> None:
    """Enforce path↔embed equality for lineage columns."""

    if "manifest_fingerprint" not in frame.columns:
        raise err(
            "E306_TOKEN_MISMATCH",
            "outlet_catalogue missing manifest_fingerprint column for path↔embed check",
        )

    mismatched_fp = (
        frame.select(pl.col("manifest_fingerprint").cast(str).unique())
        .get_column("manifest_fingerprint")
        .to_list()
    )
    if any(value != manifest_fingerprint for value in mismatched_fp):
        raise err(
            "E306_TOKEN_MISMATCH",
            "outlet_catalogue manifest_fingerprint column does not match partition token",
        )

    if "global_seed" in frame.columns:
        observed_seeds = (
            frame.select(pl.col("global_seed").cast(str).unique())
            .get_column("global_seed")
            .to_list()
        )
        if any(value != str(seed) for value in observed_seeds):
            raise err(
                "E306_TOKEN_MISMATCH",
                "outlet_catalogue global_seed column does not match seed partition token",
            )


def aggregate_site_requirements(frame: pl.DataFrame) -> pl.DataFrame:
    """Aggregate per-merchant / per-country counts and enforce site-order integrity."""

    validate_outlet_columns(frame)

    frame = frame.with_columns(
        [
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("legal_country_iso").cast(pl.Utf8),
            pl.col("site_order").cast(pl.Int64),
        ]
    )

    grouped = (
        frame.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            pl.len().alias("n_sites"),
            pl.col("site_order").min().alias("site_order_min"),
            pl.col("site_order").max().alias("site_order_max"),
            pl.col("site_order").n_unique().alias("site_order_unique"),
        )
    )

    issues = grouped.filter(
        (pl.col("site_order_min") != 1)
        | (pl.col("site_order_max") != pl.col("n_sites"))
        | (pl.col("site_order_unique") != pl.col("n_sites"))
    )
    if issues.height > 0:
        sample = issues.select(
            pl.col("merchant_id"),
            pl.col("legal_country_iso"),
            pl.col("site_order_min"),
            pl.col("site_order_max"),
            pl.col("site_order_unique"),
            pl.col("n_sites"),
        ).to_dicts()
        raise err(
            "E314_SITE_ORDER_INTEGRITY",
            f"site_order integrity violation for pairs: {sample[:3]}",
        )

    return grouped.select(["merchant_id", "legal_country_iso", "n_sites"])


def ensure_positive_counts(frame: pl.DataFrame) -> None:
    """Ensure no zero-count rows are emitted."""

    if frame.is_empty():
        return
    if (frame.get_column("n_sites") < 1).any():
        raise err("E304_ZERO_SITES_ROW", "attempted to emit a zero-count requirements row")


def ensure_iso_fk(frame: pl.DataFrame, iso_codes: Set[str]) -> None:
    """Validate ISO codes against the canonical ingress table."""

    observed = set(frame.get_column("legal_country_iso").to_list())
    lowercase = [code for code in observed if code != code.upper()]
    if lowercase:
        raise err(
            "E302_FK_COUNTRY",
            f"requirements output contains non-uppercase ISO codes: {sorted(lowercase)}",
        )

    missing = sorted(code for code in observed if code not in iso_codes)
    if missing:
        raise err(
            "E302_FK_COUNTRY",
            f"requirements output contains ISO codes not present in canonical table: {missing}",
        )


def ensure_weights_coverage(
    frame: pl.DataFrame,
    tile_weight_countries: Iterable[str],
) -> None:
    """Ensure every requirements country is present in the tile weights partition."""

    coverage = set(tile_weight_countries)
    missing = sorted(
        code for code in frame.get_column("legal_country_iso").to_list() if code not in coverage
    )
    if missing:
        raise err(
            "E303_MISSING_WEIGHTS",
            f"tile_weights partition missing coverage for countries: {missing}",
        )
