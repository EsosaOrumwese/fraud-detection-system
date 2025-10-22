"""Low-level helpers for loading the S1 tile_index partition for S2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from ...shared.dictionary import resolve_dataset_path
from ..exceptions import S2Error, err


@dataclass
class TileIndexPartition:
    """Materialised ``tile_index`` partition scoped by ``parameter_hash``."""

    parameter_hash: str
    path: Path
    frame: pl.DataFrame
    byte_size: int

    @property
    def rows(self) -> int:
        """Number of rows materialised from the partition."""

        return self.frame.height

    @property
    def country_set(self) -> frozenset[str]:
        """Distinct ISO countries present in the partition."""

        return frozenset(self.frame.get_column("country_iso").to_list())  # type: ignore[no-any-return]


def load_tile_index_partition(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object],
    ) -> TileIndexPartition:
    """Resolve and load the ``tile_index`` partition for ``parameter_hash``."""

    partition_dir = resolve_dataset_path(
        "tile_index",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if not partition_dir.exists() or not partition_dir.is_dir():
        raise err(
            "E101_TILE_INDEX_MISSING",
            f"tile_index partition '{partition_dir}' is missing or not a directory",
        )

    parquet_files = sorted(p for p in partition_dir.glob("*.parquet") if p.is_file())
    if not parquet_files:
        raise err(
            "E101_TILE_INDEX_MISSING",
            f"tile_index partition '{partition_dir}' contains no parquet files",
        )

    try:
        frame = pl.read_parquet(parquet_files)
    except Exception as exc:  # noqa: BLE001 - surfaced as contract failure
        raise err(
            "E101_TILE_INDEX_MISSING",
            f"failed to read tile_index partition '{partition_dir}': {exc}",
        ) from exc

    byte_size = sum(int(p.stat().st_size) for p in parquet_files)

    expected_columns = {
        "country_iso",
        "tile_id",
        "pixel_area_m2",
        "raster_row",
        "raster_col",
    }
    missing = expected_columns.difference(set(frame.columns))
    if missing:
        raise err(
            "E101_TILE_INDEX_MISSING",
            f"tile_index partition at '{partition_dir}' missing columns: {sorted(missing)}",
        )

    # Normalise canonical types needed downstream.
    frame = frame.with_columns(
        pl.col("country_iso").cast(pl.Utf8).str.to_uppercase(),
        pl.col("tile_id").cast(pl.UInt64),
        pl.col("pixel_area_m2").cast(pl.Float64),
        pl.col("raster_row").cast(pl.UInt32),
        pl.col("raster_col").cast(pl.UInt32),
    )

    return TileIndexPartition(
        parameter_hash=parameter_hash,
        path=partition_dir,
        frame=frame,
        byte_size=byte_size,
    )


__all__ = ["TileIndexPartition", "load_tile_index_partition"]
