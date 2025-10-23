"""Input preparation for Segment 1B state-6."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from ..exceptions import err
from ..l0.datasets import (
    S5AssignmentPartition,
    TileBoundsPartition,
    TileIndexPartition,
    WorldCountriesPartition,
    load_iso_countries,
    load_s5_assignments,
    load_tile_bounds,
    load_tile_index_partition,
    load_world_countries,
)
from ...shared.dictionary import load_dictionary
from ...s1_tile_index.l0.loaders import IsoCountryTable
from .config import RunnerConfig


@dataclass(frozen=True)
class PreparedInputs:
    """Resolved inputs required for jitter computation."""

    dictionary: Mapping[str, object]
    assignments: S5AssignmentPartition
    tile_bounds: TileBoundsPartition
    tile_index: TileIndexPartition
    country_polygons: WorldCountriesPartition
    iso_table: IsoCountryTable
    iso_version: Optional[str]
    manifest_fingerprint: str
    parameter_hash: str
    seed: str
    data_root: Path


def prepare_inputs(config: RunnerConfig) -> PreparedInputs:
    """Resolve dictionary-backed inputs and perform sanity checks."""

    dictionary = config.dictionary or load_dictionary()

    assignments = load_s5_assignments(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    tile_bounds = load_tile_bounds(
        base_path=config.data_root,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    tile_index = load_tile_index_partition(
        base_path=config.data_root,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    world_countries = load_world_countries(
        base_path=config.data_root,
        dictionary=dictionary,
    )
    iso_table, iso_version = load_iso_countries(
        base_path=config.data_root,
        dictionary=dictionary,
    )

    if assignments.frame.is_empty():
        raise err("E601_ROW_MISSING", "s5_site_tile_assignment contains no rows for the requested identity")

    return PreparedInputs(
        dictionary=dictionary,
        assignments=assignments,
        tile_bounds=tile_bounds,
        tile_index=tile_index,
        country_polygons=world_countries,
        iso_table=iso_table,
        iso_version=iso_version,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        seed=config.seed,
        data_root=config.data_root,
    )


__all__ = ["PreparedInputs", "prepare_inputs"]

