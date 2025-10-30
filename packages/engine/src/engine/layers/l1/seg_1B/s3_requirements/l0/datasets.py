"""Dataset loaders for S3 requirements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    IsoCountryTable,
    load_iso_countries as _load_iso_countries,
)

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err


@dataclass(frozen=True)
class OutletCataloguePartition:
    """Materialised outlet catalogue slice scoped by seed and fingerprint."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class TileWeightsPartition:
    """Tile weights slice scoped by parameter hash."""

    path: Path
    frame: pl.DataFrame


def load_outlet_catalogue_partition(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object] | None = None,
) -> OutletCataloguePartition:
    """Load the outlet catalogue partition authorised for this run."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "outlet_catalogue",
        base_path=base_path,
        template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E301_NO_PASS_FLAG",
            f"outlet_catalogue partition missing at '{dataset_path}'",
        )

    pattern = _parquet_pattern(dataset_path, dataset_id="outlet_catalogue")
    try:
        frame = (
            pl.scan_parquet(pattern)
            .select(
                [
                    "merchant_id",
                    "legal_country_iso",
                    "site_order",
                    "manifest_fingerprint",
                    "global_seed",
                ]
            )
            .collect()
        )
    except pl.exceptions.ColumnNotFoundError:
        # Reload without optional columns and rely on downstream validation.
        frame = (
            pl.scan_parquet(pattern)
            .select(["merchant_id", "legal_country_iso", "site_order", "manifest_fingerprint"])
            .collect()
        )

    return OutletCataloguePartition(path=dataset_path, frame=frame)


def load_tile_weights_partition(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileWeightsPartition:
    """Load the S2 tile weights partition for coverage checks."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "tile_weights",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E303_MISSING_WEIGHTS",
            f"tile_weights partition missing at '{dataset_path}'",
        )

    pattern = _parquet_pattern(dataset_path, dataset_id="tile_weights")
    frame = (
        pl.scan_parquet(pattern)
        .select(["country_iso", "tile_id"])
        .collect()
    )
    return TileWeightsPartition(path=dataset_path, frame=frame)


def load_iso_countries(
    *,
    base_path: Path,
    dictionary: Mapping[str, object] | None = None,
) -> IsoCountryTable:
    """Load the canonical ISO-3166 country table."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "iso3166_canonical_2024",
        base_path=base_path,
        template_args={},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E302_FK_COUNTRY",
            f"iso3166_canonical_2024 surface missing at '{dataset_path}'",
        )
    return _load_iso_countries(dataset_path)


def _parquet_pattern(path: Path, *, dataset_id: str) -> str:
    if path.is_dir():
        return str(path / "*.parquet")
    if path.suffix == ".parquet":
        return str(path)
    raise err(
        "E311_DISALLOWED_READ",
        f"{dataset_id} path '{path}' is neither directory nor parquet file",
    )


__all__ = [
    "IsoCountryTable",
    "OutletCataloguePartition",
    "TileWeightsPartition",
    "load_iso_countries",
    "load_outlet_catalogue_partition",
    "load_tile_weights_partition",
]
