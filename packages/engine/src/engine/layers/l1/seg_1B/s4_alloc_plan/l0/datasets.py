"""Dataset loaders for Segment 1B State-4 allocation plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

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
    frame: pl.DataFrame
    dp: int


@dataclass(frozen=True)
class TileIndexPartition:
    """Eligible tile universe for the parameter hash."""

    path: Path
    frame: pl.DataFrame


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

    frame = (
        pl.scan_parquet(_parquet_pattern(dataset_path))
        .select(
            [
                "country_iso",
                "tile_id",
                "weight_fp",
                "dp",
            ]
        )
        .collect()
    )

    if "dp" not in frame.columns or frame.get_column("dp").is_null().any():
        raise err(
            "E402_WEIGHTS_MISSING",
            "tile_weights partition missing dp column or contains nulls",
        )
    dp_values = frame.get_column("dp").unique().to_list()
    if len(dp_values) != 1:
        raise err(
            "E402_WEIGHTS_MISSING",
            f"tile_weights partition expected single dp value, found {dp_values}",
        )

    return TileWeightsPartition(path=dataset_path, frame=frame, dp=int(dp_values[0]))


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

    frame = (
        pl.scan_parquet(_parquet_pattern(dataset_path))
        .select(["country_iso", "tile_id"])
        .collect()
    )
    return TileIndexPartition(path=dataset_path, frame=frame)


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
