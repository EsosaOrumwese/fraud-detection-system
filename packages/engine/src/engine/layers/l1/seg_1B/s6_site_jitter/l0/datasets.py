"""Dataset loaders for Segment 1B state-6 site jitter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    CountryPolygons,
    IsoCountryTable,
    load_country_polygons as _load_country_polygons,
    load_iso_countries as _load_iso_countries,
)

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err
from ...s4_alloc_plan.l0.datasets import TileIndexPartition


@dataclass(frozen=True)
class S5AssignmentPartition:
    """S5 assignment rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class TileBoundsPartition:
    """Tile bounds partition scoped by parameter hash."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class WorldCountriesPartition:
    """World country polygons used for PIP checks."""

    path: Path
    polygons: CountryPolygons


def load_s5_assignments(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> S5AssignmentPartition:
    """Load S5 site→tile assignments for the target identity."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "s5_site_tile_assignment",
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
            "E601_ROW_MISSING",
            f"s5_site_tile_assignment partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(str(dataset_path / "*.parquet"))
        .select(
            [
                "merchant_id",
                "legal_country_iso",
                "site_order",
                "tile_id",
            ]
        )
        .collect()
    )
    return S5AssignmentPartition(path=dataset_path, frame=frame)


def load_tile_bounds(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileBoundsPartition:
    """Load the S1 tile bounds partition."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "tile_bounds",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E606_FK_TILE_INDEX",
            f"tile_bounds partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(str(dataset_path / "*.parquet"))
        .select(
            [
                "country_iso",
                "tile_id",
                "west_lon",
                "east_lon",
                "south_lat",
                "north_lat",
            ]
        )
        .collect()
    )
    return TileBoundsPartition(path=dataset_path, frame=frame)


def load_tile_index_partition(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileIndexPartition:
    """Load tile index rows with centroid metadata for the parameter set."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "tile_index",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E606_FK_TILE_INDEX",
            f"tile_index partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(str(dataset_path / "*.parquet"))
        .select(
            [
                "country_iso",
                "tile_id",
                "centroid_lon",
                "centroid_lat",
            ]
        )
        .collect()
    )
    return TileIndexPartition(path=dataset_path, frame=frame)


def load_world_countries(
    *,
    base_path: Path,
    dictionary: Mapping[str, object] | None = None,
) -> WorldCountriesPartition:
    """Load the world country polygons used for point-in-country checks."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "world_countries",
        base_path=base_path,
        template_args={},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E606_FK_TILE_INDEX",
            f"world_countries surface missing at '{dataset_path}'",
        )
    polygons = _load_country_polygons(dataset_path)
    return WorldCountriesPartition(path=dataset_path, polygons=polygons)


def load_iso_countries(
    *,
    base_path: Path,
    dictionary: Mapping[str, object] | None = None,
) -> Tuple[IsoCountryTable, str | None]:
    """Load the ISO canonical table and version string."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "iso3166_canonical_2024",
        base_path=base_path,
        template_args={},
        dictionary=dictionary,
    )
    if not dataset_path.exists():
        raise err(
            "E606_FK_TILE_INDEX",
            f"iso3166_canonical_2024 surface missing at '{dataset_path}'",
        )
    table = _load_iso_countries(dataset_path)
    entry = dictionary.get("reference_data", {}).get("iso3166_canonical_2024", {})
    version = None
    if isinstance(entry, Mapping):
        raw_version = entry.get("version")
        if isinstance(raw_version, str):
            version = raw_version
    return table, version


__all__ = [
    "S5AssignmentPartition",
    "TileBoundsPartition",
    "TileIndexPartition",
    "WorldCountriesPartition",
    "load_iso_countries",
    "load_s5_assignments",
    "load_tile_bounds",
    "load_tile_index_partition",
    "load_world_countries",
]
