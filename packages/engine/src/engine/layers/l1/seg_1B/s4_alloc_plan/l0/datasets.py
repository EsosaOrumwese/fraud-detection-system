"""Dataset loaders for Segment 1B State-4 allocation plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    IsoCountryTable,
    load_iso_countries as _load_iso_countries,
)

from ...shared.dictionary import get_dataset_entry, load_dictionary, resolve_dataset_path
from ..exceptions import err


@dataclass(frozen=True)
class S3RequirementsPartition:
    """S3 requirements rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class TileWeightsPartition:
    """Tile weights with fixed-dp values scoped by parameter hash."""

    path: Path
    file_paths: tuple[Path, ...]
    dataset: ds.Dataset
    dp: int

    def collect_country(self, iso: str) -> pl.DataFrame:
        table = self.dataset.to_table(
            columns=["country_iso", "tile_id", "weight_fp", "dp"],
            filter=ds.field("country_iso") == iso,
        )
        if table.num_rows == 0:
            return pl.DataFrame(
                {
                    "country_iso": pl.Series([], dtype=pl.Utf8),
                    "tile_id": pl.Series([], dtype=pl.UInt64),
                    "weight_fp": pl.Series([], dtype=pl.UInt64),
                    "dp": pl.Series([], dtype=pl.UInt32),
                }
            )
        frame = pl.from_arrow(table, rechunk=False)
        return frame.with_columns(pl.col("dp").cast(pl.UInt32)).sort("tile_id")


@dataclass(frozen=True)
class TileIndexPartition:
    """Eligible tile universe for the parameter hash."""

    path: Path
    file_paths: tuple[Path, ...]
    dataset: ds.Dataset

    def collect_country(self, iso: str, columns: tuple[str, ...] | None = None) -> pl.DataFrame:
        requested = columns or ("country_iso", "tile_id")
        table = self.dataset.to_table(
            columns=list(requested),
            filter=ds.field("country_iso") == iso,
        )
        if table.num_rows == 0:
            empty_payload: dict[str, pl.Series] = {}
            for name in requested:
                if name == "country_iso":
                    empty_payload[name] = pl.Series([], dtype=pl.Utf8)
                elif name == "tile_id":
                    empty_payload[name] = pl.Series([], dtype=pl.UInt64)
                else:
                    empty_payload[name] = pl.Series([], dtype=pl.Float64)
            return pl.DataFrame(empty_payload)
        frame = pl.from_arrow(table, rechunk=False)
        updates = []
        if "country_iso" in frame.columns:
            updates.append(pl.col("country_iso").cast(pl.Utf8))
        if "tile_id" in frame.columns:
            updates.append(pl.col("tile_id").cast(pl.UInt64))
        if updates:
            frame = frame.with_columns(updates)
        if "tile_id" in frame.columns:
            frame = frame.sort("tile_id")
        return frame


def load_s3_requirements(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> S3RequirementsPartition:
    """Load the S3 requirements partition for this run."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "s3_requirements",
        base_path=base_path,
        template_args={
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        },
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E401_REQUIREMENTS_MISSING",
            f"s3_requirements partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(_parquet_pattern(dataset_path))
        .select(["merchant_id", "legal_country_iso", "n_sites"])
        .collect()
    )
    return S3RequirementsPartition(path=dataset_path, frame=frame)


def load_tile_weights(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileWeightsPartition:
    """Load S2 tile weights (fixed-dp) for this parameter hash."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "tile_weights",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E402_WEIGHTS_MISSING",
            f"tile_weights partition missing at '{dataset_path}'",
        )

    file_paths = tuple(sorted(dataset_path.glob("*.parquet")))
    if not file_paths:
        raise err(
            "E402_WEIGHTS_MISSING",
            f"tile_weights partition '{dataset_path}' contains no parquet files",
        )

    dp_values: set[int] = set()
    for file_path in file_paths:
        parquet_file = pq.ParquetFile(file_path)
        for row_group_index in range(parquet_file.num_row_groups):
            table = parquet_file.read_row_group(row_group_index, columns=["dp"])
            dp_values.update(int(value) for value in table.column("dp").to_pylist())
            if len(dp_values) > 1 or dp_values:
                break
        if dp_values:
            break

    if not dp_values:
        raise err(
            "E402_WEIGHTS_MISSING",
            "tile_weights partition missing dp column or contains nulls",
        )
    if len(dp_values) != 1:
        raise err(
            "E402_WEIGHTS_MISSING",
            f"tile_weights partition expected single dp value, found {dp_values}",
        )

    dataset = ds.dataset(file_paths, format="parquet")
    return TileWeightsPartition(
        path=dataset_path,
        file_paths=file_paths,
        dataset=dataset,
        dp=next(iter(dp_values)),
    )


def load_tile_index(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileIndexPartition:
    """Load the tile index partition (eligible tiles)."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "tile_index",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E408_COVERAGE_MISSING",
            f"tile_index partition missing at '{dataset_path}'",
        )

    file_paths = tuple(sorted(dataset_path.glob("*.parquet")))
    if not file_paths:
        raise err(
            "E408_COVERAGE_MISSING",
            f"tile_index partition '{dataset_path}' contains no parquet files",
        )
    dataset = ds.dataset(file_paths, format="parquet")
    return TileIndexPartition(path=dataset_path, file_paths=file_paths, dataset=dataset)


def load_iso_countries(
    *,
    base_path: Path,
    dictionary: Mapping[str, object] | None = None,
) -> tuple[IsoCountryTable, str | None]:
    """Load ISO table alongside its declared version."""

    dictionary = dictionary or load_dictionary()
    entry = get_dataset_entry("iso3166_canonical_2024", dictionary=dictionary)
    dataset_path = resolve_dataset_path(
        "iso3166_canonical_2024",
        base_path=base_path,
        template_args={},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E408_COVERAGE_MISSING",
            f"iso3166_canonical_2024 surface missing at '{dataset_path}'",
        )
    iso_table = _load_iso_countries(dataset_path)
    version = entry.get("version") if isinstance(entry, Mapping) else None
    return iso_table, version  # type: ignore[return-value]


def _parquet_pattern(path: Path) -> str:
    if path.is_dir():
        return str(path / "*.parquet")
    if path.suffix == ".parquet":
        return str(path)
    raise err(
        "E405_SCHEMA_INVALID",
        f"path '{path}' is neither parquet file nor directory",
    )


__all__ = [
    "IsoCountryTable",
    "S3RequirementsPartition",
    "TileIndexPartition",
    "TileWeightsPartition",
    "load_iso_countries",
    "load_s3_requirements",
    "load_tile_index",
    "load_tile_weights",
]
