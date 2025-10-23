"""Dataset loaders for Segment 1B State-5 site→tile assignment."""

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
from ...s4_alloc_plan.l0.datasets import (
    TileIndexPartition,
    load_tile_index,
)


@dataclass(frozen=True)
class S4AllocPlanPartition:
    """S4 allocation plan rows scoped by seed/fingerprint/parameter hash."""

    path: Path
    frame: pl.DataFrame


def load_s4_alloc_plan(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> S4AllocPlanPartition:
    """Load the S4 allocation plan for this run identity."""

    dictionary = dictionary or load_dictionary()
    dataset_path = resolve_dataset_path(
        "s4_alloc_plan",
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
            "E501_ALLOC_PLAN_MISSING",
            f"s4_alloc_plan partition missing at '{dataset_path}'",
        )

    frame = (
        pl.scan_parquet(_parquet_pattern(dataset_path))
        .select(
            [
                "merchant_id",
                "legal_country_iso",
                "tile_id",
                "n_sites_tile",
            ]
        )
        .collect()
    )
    return S4AllocPlanPartition(path=dataset_path, frame=frame)


def load_tile_index_partition(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object] | None = None,
) -> TileIndexPartition:
    """Proxy to the shared tile index loader for convenience."""

    return load_tile_index(
        base_path=base_path,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )


def load_iso_countries(
    *,
    base_path: Path,
    dictionary: Mapping[str, object] | None = None,
) -> tuple[IsoCountryTable, str | None]:
    """Load the ISO canonical table and reported version."""

    dictionary = dictionary or load_dictionary()
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
    table = _load_iso_countries(dataset_path)
    entry = dictionary.get("reference_data", {}).get("iso3166_canonical_2024", {})
    version = entry.get("version") if isinstance(entry, Mapping) else None
    return table, version  # type: ignore[return-value]


def _parquet_pattern(path: Path) -> str:
    if path.is_dir():
        return str(path / "*.parquet")
    if path.suffix == ".parquet":
        return str(path)
    raise err(
        "E506_SCHEMA_INVALID",
        f"path '{path}' is neither parquet file nor directory",
    )


__all__ = [
    "IsoCountryTable",
    "S4AllocPlanPartition",
    "TileIndexPartition",
    "load_iso_countries",
    "load_s4_alloc_plan",
    "load_tile_index_partition",
]
