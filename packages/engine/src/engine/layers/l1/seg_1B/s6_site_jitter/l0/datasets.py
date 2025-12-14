"""Dataset loaders for Segment 1B state-6 site jitter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

import polars as pl
import pyarrow.dataset as ds

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    CountryPolygons,
    IsoCountryTable,
    load_country_polygons as _load_country_polygons,
    load_iso_countries as _load_iso_countries,
)

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err
from ...s4_alloc_plan.l0.datasets import TileIndexPartition, load_tile_index


@dataclass(frozen=True)
class S5AssignmentPartition:
    """S5 assignment rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class TileBoundsPartition:
    """Tile bounds partition scoped by parameter hash."""

    path: Path
    file_paths: tuple[Path, ...]
    dataset: ds.Dataset

    def collect_country(self, iso: str) -> pl.DataFrame:
        iso = str(iso).upper()
        if not iso:
            return _empty_tile_bounds_frame()

        canonical_cols = [
            "country_iso",
            "tile_id",
            "min_lon_deg",
            "max_lon_deg",
            "min_lat_deg",
            "max_lat_deg",
            "centroid_lon_deg",
            "centroid_lat_deg",
        ]
        legacy_cols = [
            "country_iso",
            "tile_id",
            "west_lon",
            "east_lon",
            "south_lat",
            "north_lat",
        ]
        schema_lookup = {name.lower(): name for name in self.dataset.schema.names}

        if all(col in schema_lookup for col in (name.lower() for name in canonical_cols)):
            columns = [schema_lookup[col.lower()] for col in canonical_cols]
            table = self.dataset.to_table(columns=columns, filter=ds.field("country_iso") == iso)
            if table.num_rows == 0:
                return _empty_tile_bounds_frame()
            frame = pl.from_arrow(table, rechunk=False).with_columns(
                [
                    pl.col(columns[0]).cast(pl.Utf8).alias("country_iso"),
                    pl.col(columns[1]).cast(pl.UInt64).alias("tile_id"),
                    pl.col(columns[2]).cast(pl.Float64).alias("min_lon_deg"),
                    pl.col(columns[3]).cast(pl.Float64).alias("max_lon_deg"),
                    pl.col(columns[4]).cast(pl.Float64).alias("min_lat_deg"),
                    pl.col(columns[5]).cast(pl.Float64).alias("max_lat_deg"),
                    pl.col(columns[6]).cast(pl.Float64).alias("centroid_lon_deg"),
                    pl.col(columns[7]).cast(pl.Float64).alias("centroid_lat_deg"),
                ]
            )
            return frame.select(canonical_cols).sort("tile_id")

        if all(col in schema_lookup for col in (name.lower() for name in legacy_cols)):
            columns = [schema_lookup[col.lower()] for col in legacy_cols]
            table = self.dataset.to_table(columns=columns, filter=ds.field("country_iso") == iso)
            if table.num_rows == 0:
                return _empty_tile_bounds_frame()
            frame = pl.from_arrow(table, rechunk=False).with_columns(
                [
                    pl.col(columns[0]).cast(pl.Utf8).alias("country_iso"),
                    pl.col(columns[1]).cast(pl.UInt64).alias("tile_id"),
                    pl.col(columns[2]).cast(pl.Float64).alias("min_lon_deg"),
                    pl.col(columns[3]).cast(pl.Float64).alias("max_lon_deg"),
                    pl.col(columns[4]).cast(pl.Float64).alias("min_lat_deg"),
                    pl.col(columns[5]).cast(pl.Float64).alias("max_lat_deg"),
                    ((pl.col(columns[2]) + pl.col(columns[3])) / 2.0).alias("centroid_lon_deg"),
                    ((pl.col(columns[4]) + pl.col(columns[5])) / 2.0).alias("centroid_lat_deg"),
                ]
            )
            return frame.select(canonical_cols).sort("tile_id")

        raise err(
            "E606_FK_TILE_INDEX",
            f"tile_bounds partition missing expected geometry columns for ISO {iso}: "
            f"{sorted(self.dataset.schema.names)}",
        )


def _empty_tile_bounds_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "country_iso": pl.Series([], dtype=pl.Utf8),
            "tile_id": pl.Series([], dtype=pl.UInt64),
            "min_lon_deg": pl.Series([], dtype=pl.Float64),
            "max_lon_deg": pl.Series([], dtype=pl.Float64),
            "min_lat_deg": pl.Series([], dtype=pl.Float64),
            "max_lat_deg": pl.Series([], dtype=pl.Float64),
            "centroid_lon_deg": pl.Series([], dtype=pl.Float64),
            "centroid_lat_deg": pl.Series([], dtype=pl.Float64),
        }
    )


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

    file_paths = tuple(sorted(dataset_path.glob("*.parquet")))
    if not file_paths:
        raise err(
            "E606_FK_TILE_INDEX",
            f"tile_bounds partition '{dataset_path}' contains no parquet files",
        )
    dataset = ds.dataset(file_paths, format="parquet")
    return TileBoundsPartition(path=dataset_path, file_paths=file_paths, dataset=dataset)


def load_tile_index_partition(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileIndexPartition:
    """Load the streaming tile index partition shared with other states."""

    return load_tile_index(
        base_path=base_path,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )


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
