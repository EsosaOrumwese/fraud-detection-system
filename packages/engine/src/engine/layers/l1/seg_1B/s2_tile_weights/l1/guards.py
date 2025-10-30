"""Ingress guard-rails for S2 tile weights."""

from __future__ import annotations

from typing import Iterable

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import IsoCountryTable

from ..exceptions import err
from ..l0.tile_index import TileIndexPartition


def ensure_iso_coverage(partition: TileIndexPartition, iso_codes: Iterable[str]) -> None:
    """Assert that all country codes in ``tile_index`` are present in the ISO table."""

    iso_set = frozenset(code.upper() for code in iso_codes)
    unknown = sorted(partition.country_set.difference(iso_set))
    if unknown:
        raise err(
            "E102_FK_MISMATCH",
            f"tile_index contains country_iso values not present in ISO surface: {unknown}",
        )


def ensure_primary_key_integrity(partition: TileIndexPartition) -> None:
    """Guarantee ``(country_iso, tile_id)`` uniqueness within the partition."""

    frame = partition.frame
    if frame is None:
        return
    duplicates = frame.select(
        (
            (pl.col("country_iso") == pl.col("country_iso").shift(1))
            & (pl.col("tile_id") == pl.col("tile_id").shift(1))
        ).fill_null(False)
    ).to_series()
    if bool(duplicates.any()):
        raise err(
            "E101_TILE_INDEX_MISSING",
            "tile_index partition violates primary key uniqueness on (country_iso, tile_id)",
        )


def ensure_sorted_by_dictionary(partition: TileIndexPartition) -> None:
    """Confirm the partition is sorted by the dictionary's writer order."""

    frame = partition.frame
    if frame is None:
        return
    iso_backslide = frame.select(
        (pl.col("country_iso") < pl.col("country_iso").shift(1)).fill_null(False)
    ).to_series()
    if bool(iso_backslide.any()):
        raise err(
            "E101_TILE_INDEX_MISSING",
            "tile_index partition must be sorted by ['country_iso', 'tile_id']",
        )
    tile_backslide = frame.select(
        (
            (pl.col("country_iso") == pl.col("country_iso").shift(1))
            & (pl.col("tile_id") < pl.col("tile_id").shift(1))
        ).fill_null(False)
    ).to_series()
    if bool(tile_backslide.any()):
        raise err(
            "E101_TILE_INDEX_MISSING",
            "tile_index partition must be sorted by ['country_iso', 'tile_id']",
        )


def validate_tile_index(
    *,
    partition: TileIndexPartition,
    iso_table: IsoCountryTable,
) -> None:
    """Run the S2 ingress validation suite over ``tile_index``."""

    ensure_sorted_by_dictionary(partition)
    ensure_primary_key_integrity(partition)
    ensure_iso_coverage(partition, iso_table.codes)


__all__ = [
    "ensure_iso_coverage",
    "ensure_primary_key_integrity",
    "ensure_sorted_by_dictionary",
    "validate_tile_index",
]
