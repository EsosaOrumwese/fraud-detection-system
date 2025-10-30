"""Dataset loaders for Segment 1B state-7 site synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl
import pyarrow.dataset as ds

from engine.layers.l1.seg_1B.s0_gate.l1.verification import (
    VerifiedBundle,
    verify_bundle,
    verify_outlet_catalogue_lineage,
)

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err


@dataclass(frozen=True)
class S5AssignmentPartition:
    """S5 assignment rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class S6JitterPartition:
    """S6 jitter rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class TileBoundsPartition:
    """Tile bounds partition providing per-ISO access."""

    path: Path
    file_paths: tuple[Path, ...]
    dataset: ds.Dataset
    has_legacy_schema: bool

    def collect_country(
        self,
        iso: str,
        *,
        tile_ids: list[int] | tuple[int, ...] | set[int] | pl.Series | None = None,
    ) -> pl.DataFrame:
        iso = str(iso).upper()
        if not iso:
            return _empty_tile_bounds_frame()

        filter_expr = ds.field("country_iso") == iso
        if tile_ids is not None:
            if isinstance(tile_ids, pl.Series):
                ids_iter = {int(x) for x in tile_ids.to_list()}
            else:
                ids_iter = {int(x) for x in tile_ids}
            if not ids_iter:
                return _empty_tile_bounds_frame()
            filter_expr = filter_expr & ds.field("tile_id").isin(sorted(ids_iter))

        table = self.dataset.to_table(filter=filter_expr)
        if table.num_rows == 0:
            return _empty_tile_bounds_frame()

        frame = pl.from_arrow(table, rechunk=False)
        cols_lower = {name.lower() for name in frame.columns}

        frame = frame.with_columns(pl.col("tile_id").cast(pl.UInt64))

        if {"min_lon_deg", "max_lon_deg", "min_lat_deg", "max_lat_deg", "centroid_lon_deg", "centroid_lat_deg"}.issubset(
            cols_lower
        ):
            return (
                frame.select(
                    [
                        pl.col("tile_id"),
                        pl.col("min_lon_deg").cast(pl.Float64),
                        pl.col("max_lon_deg").cast(pl.Float64),
                        pl.col("min_lat_deg").cast(pl.Float64),
                        pl.col("max_lat_deg").cast(pl.Float64),
                        pl.col("centroid_lon_deg").cast(pl.Float64),
                        pl.col("centroid_lat_deg").cast(pl.Float64),
                    ]
                )
                .sort("tile_id")
            )

        if {"west_lon", "east_lon", "south_lat", "north_lat"}.issubset(cols_lower):
            return (
                frame.with_columns(
                    [
                        pl.col("west_lon").cast(pl.Float64).alias("min_lon_deg"),
                        pl.col("east_lon").cast(pl.Float64).alias("max_lon_deg"),
                        pl.col("south_lat").cast(pl.Float64).alias("min_lat_deg"),
                        pl.col("north_lat").cast(pl.Float64).alias("max_lat_deg"),
                        ((pl.col("west_lon") + pl.col("east_lon")) / 2.0).alias("centroid_lon_deg"),
                        ((pl.col("south_lat") + pl.col("north_lat")) / 2.0).alias("centroid_lat_deg"),
                    ]
                )
                .select(
                    [
                        pl.col("tile_id"),
                        pl.col("min_lon_deg"),
                        pl.col("max_lon_deg"),
                        pl.col("min_lat_deg"),
                        pl.col("max_lat_deg"),
                        pl.col("centroid_lon_deg"),
                        pl.col("centroid_lat_deg"),
                    ]
                )
                .sort("tile_id")
            )

        raise err(
            "E799_INTERNAL",
            "tile_bounds partition missing expected geometry columns for ISO "
            f"{iso}: available {sorted(frame.columns)}",
        )


@dataclass(frozen=True)
class OutletCataloguePartition:
    """Outlet catalogue rows scoped by seed/fingerprint."""

    path: Path
    frame: pl.DataFrame


@dataclass(frozen=True)
class VerifiedGate:
    """1A consumer gate verification artefacts."""

    bundle_dir: Path
    bundle: VerifiedBundle
    flag_sha256_hex: str


def verify_consumer_gate(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object] | None = None,
) -> VerifiedGate:
    """Verify the fingerprint-scoped 1A validation bundle before reading 1A egress."""

    dictionary = dictionary or load_dictionary()
    bundle_path = resolve_dataset_path(
        "validation_bundle_1A",
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    if not bundle_path.exists():
        raise err(
            "E708_1A_COVERAGE_FAIL",
            f"validation bundle for fingerprint '{manifest_fingerprint}' missing at '{bundle_path}'",
        )

    bundle = verify_bundle(bundle_path)
    return VerifiedGate(bundle_dir=bundle_path, bundle=bundle, flag_sha256_hex=bundle.flag_sha256_hex)


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
            "E705_PARTITION_OR_IDENTITY",
            f"s5_site_tile_assignment partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(str(dataset_path / "*.parquet"))
        .select(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("tile_id").cast(pl.UInt64),
            ]
        )
        .collect()
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )
    return S5AssignmentPartition(path=dataset_path, frame=frame)


def load_s6_jitter(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> S6JitterPartition:
    """Load S6 jitter deltas for the target identity."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "s6_site_jitter",
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
            "E705_PARTITION_OR_IDENTITY",
            f"s6_site_jitter partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(str(dataset_path / "*.parquet"))
        .select(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("tile_id").cast(pl.UInt64),
                pl.col("delta_lon_deg").cast(pl.Float64),
                pl.col("delta_lat_deg").cast(pl.Float64),
            ]
        )
        .collect()
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )
    return S6JitterPartition(path=dataset_path, frame=frame)


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
            "E709_TILE_FK_VIOLATION",
            f"tile_bounds partition missing at '{dataset_path}'",
        )

    file_paths = tuple(sorted(dataset_path.glob("*.parquet")))
    if not file_paths:
        raise err(
            "E709_TILE_FK_VIOLATION",
            f"tile_bounds partition '{dataset_path}' contains no parquet files",
        )

    dataset = ds.dataset(file_paths, format="parquet")
    schema_names = {name.lower() for name in dataset.schema.names}
    has_legacy = {
        "min_lon_deg",
        "max_lon_deg",
        "min_lat_deg",
        "max_lat_deg",
        "centroid_lon_deg",
        "centroid_lat_deg",
    }.issubset(schema_names)

    return TileBoundsPartition(
        path=dataset_path,
        file_paths=file_paths,
        dataset=dataset,
        has_legacy_schema=has_legacy,
    )

def load_outlet_catalogue(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object] | None = None,
) -> OutletCataloguePartition:
    """Load the outlet catalogue after verifying the consumer gate."""

    dictionary = dictionary or load_dictionary()
    path = verify_outlet_catalogue_lineage(
        base_path=base_path,
        dictionary=dictionary,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
    )

    frame = (
        pl.scan_parquet(str(path / "*.parquet"))
        .select(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
            ]
        )
        .collect()
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )
    return OutletCataloguePartition(path=path, frame=frame)


__all__ = [
    "OutletCataloguePartition",
    "S5AssignmentPartition",
    "S6JitterPartition",
    "TileBoundsPartition",
    "VerifiedGate",
    "load_outlet_catalogue",
    "load_s5_assignments",
    "load_s6_jitter",
    "load_tile_bounds",
    "verify_consumer_gate",
]


def _empty_tile_bounds_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "tile_id": pl.Series([], dtype=pl.UInt64),
            "min_lon_deg": pl.Series([], dtype=pl.Float64),
            "max_lon_deg": pl.Series([], dtype=pl.Float64),
            "min_lat_deg": pl.Series([], dtype=pl.Float64),
            "max_lat_deg": pl.Series([], dtype=pl.Float64),
            "centroid_lon_deg": pl.Series([], dtype=pl.Float64),
            "centroid_lat_deg": pl.Series([], dtype=pl.Float64),
        }
    )
