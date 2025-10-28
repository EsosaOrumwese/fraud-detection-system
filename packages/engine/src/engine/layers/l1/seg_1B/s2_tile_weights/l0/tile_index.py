"""Low-level helpers for loading and streaming the S1 tile_index partition for S2."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

import numpy as np
import polars as pl
import pyarrow.parquet as pq

from ...shared.dictionary import resolve_dataset_path
from ..exceptions import S2Error, err

_DEFAULT_TILE_COLUMNS = (
    "country_iso",
    "tile_id",
    "pixel_area_m2",
    "raster_row",
    "raster_col",
)


@dataclass
class TileIndexPartition:
    """Metadata describing a ``tile_index`` partition scoped by ``parameter_hash``."""

    parameter_hash: str
    path: Path
    frame: pl.DataFrame | None
    byte_size: int
    file_paths: tuple[Path, ...]
    row_count: int
    _country_cache: frozenset[str] | None = field(default=None, init=False, repr=False)

    @property
    def rows(self) -> int:
        """Number of rows materialised or estimated for the partition."""

        if self.frame is not None:
            return self.frame.height
        return self.row_count

    @property
    def country_set(self) -> frozenset[str]:
        """Distinct ISO countries present in the partition."""

        if self.frame is not None:
            return frozenset(self.frame.get_column("country_iso").to_list())  # type: ignore[no-any-return]
        if self._country_cache is None:
            country_codes: set[str] = set()
            for batch in iter_tile_index_countries(self, columns=("country_iso",)):
                country_codes.add(batch.iso)
            self._country_cache = frozenset(country_codes)
        return self._country_cache


@dataclass
class CountryTileBatch:
    """Container for a single country's tile data."""

    iso: str
    tile_id: np.ndarray
    pixel_area_m2: np.ndarray | None
    raster_row: np.ndarray | None
    raster_col: np.ndarray | None

    @property
    def rows(self) -> int:
        return int(self.tile_id.size)


def load_tile_index_partition(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object],
    eager: bool = True,
) -> TileIndexPartition:
    """Resolve the ``tile_index`` partition for ``parameter_hash``."""

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

    parquet_files = tuple(sorted(p for p in partition_dir.glob("*.parquet") if p.is_file()))
    if not parquet_files:
        raise err(
            "E101_TILE_INDEX_MISSING",
            f"tile_index partition '{partition_dir}' contains no parquet files",
        )

    byte_size = sum(int(p.stat().st_size) for p in parquet_files)
    row_count = 0
    for file_path in parquet_files:
        parquet_file = pq.ParquetFile(file_path)
        row_count += parquet_file.metadata.num_rows

    frame: pl.DataFrame | None = None
    if eager:
        try:
            frame = pl.read_parquet(parquet_files)
        except Exception as exc:  # noqa: BLE001 - surfaced as contract failure
            raise err(
                "E101_TILE_INDEX_MISSING",
                f"failed to read tile_index partition '{partition_dir}': {exc}",
            ) from exc

        _ensure_expected_columns(frame, partition_dir)
        frame = _normalise_frame(frame)

    return TileIndexPartition(
        parameter_hash=parameter_hash,
        path=partition_dir,
        frame=frame,
        byte_size=byte_size,
        file_paths=parquet_files,
        row_count=row_count,
    )


def iter_tile_index_countries(
    partition: TileIndexPartition,
    *,
    columns: Sequence[str] | None = None,
) -> Iterator[CountryTileBatch]:
    """Stream the tile index partition one country at a time."""

    required = tuple(columns or _DEFAULT_TILE_COLUMNS)
    if "country_iso" not in required:
        required = ("country_iso",) + tuple(col for col in required if col != "country_iso")

    current_iso: str | None = None
    tile_parts: list[np.ndarray] = []
    area_parts: list[np.ndarray] = []
    row_parts: list[np.ndarray] = []
    col_parts: list[np.ndarray] = []

    def _yield_batch() -> CountryTileBatch | None:
        nonlocal current_iso, tile_parts, area_parts, row_parts, col_parts
        if current_iso is None or not tile_parts:
            return None
        tile_id = np.concatenate(tile_parts).astype(np.uint64, copy=False)
        pixel_area = (
            np.concatenate(area_parts).astype(np.float64, copy=False) if area_parts else None
        )
        raster_row = (
            np.concatenate(row_parts).astype(np.uint32, copy=False) if row_parts else None
        )
        raster_col = (
            np.concatenate(col_parts).astype(np.uint32, copy=False) if col_parts else None
        )
        batch = CountryTileBatch(
            iso=current_iso,
            tile_id=tile_id,
            pixel_area_m2=pixel_area,
            raster_row=raster_row,
            raster_col=raster_col,
        )
        tile_parts = []
        area_parts = []
        row_parts = []
        col_parts = []
        current_iso = None
        return batch

    for file_path in partition.file_paths:
        parquet_file = pq.ParquetFile(file_path)
        for row_group_index in range(parquet_file.num_row_groups):
            table = parquet_file.read_row_group(row_group_index, columns=required)
            if table.num_rows == 0:
                continue
            frame = pl.from_arrow(table, rechunk=False)
            iso_array = frame.get_column("country_iso").to_numpy()
            if iso_array.size == 0:
                continue
            boundaries = np.flatnonzero(iso_array[1:] != iso_array[:-1]) + 1
            split_indices = np.concatenate(([0], boundaries, [iso_array.size]))
            for start, end in zip(split_indices[:-1], split_indices[1:]):
                segment = frame.slice(start, end - start)
                iso_value = segment.item(0, "country_iso")
                if current_iso is None:
                    current_iso = iso_value
                elif iso_value != current_iso:
                    batch = _yield_batch()
                    if batch is not None:
                        yield batch
                    current_iso = iso_value

                tile_parts.append(segment.get_column("tile_id").to_numpy())
                if "pixel_area_m2" in segment.columns:
                    area_parts.append(segment.get_column("pixel_area_m2").to_numpy())
                if "raster_row" in segment.columns:
                    row_parts.append(segment.get_column("raster_row").to_numpy())
                if "raster_col" in segment.columns:
                    col_parts.append(segment.get_column("raster_col").to_numpy())

    final_batch = _yield_batch()
    if final_batch is not None:
        yield final_batch


def _ensure_expected_columns(frame: pl.DataFrame, partition_dir: Path) -> None:
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


def _normalise_frame(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.col("country_iso").cast(pl.Utf8).str.to_uppercase(),
        pl.col("tile_id").cast(pl.UInt64),
        pl.col("pixel_area_m2").cast(pl.Float64),
        pl.col("raster_row").cast(pl.UInt32),
        pl.col("raster_col").cast(pl.UInt32),
    )


__all__ = [
    "TileIndexPartition",
    "CountryTileBatch",
    "iter_tile_index_countries",
    "load_tile_index_partition",
]
