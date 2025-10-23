"""Prepare inputs for Segment 1B State-4 allocation plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ..exceptions import err
from ..l0.datasets import (
    IsoCountryTable,
    S3RequirementsPartition,
    TileIndexPartition,
    TileWeightsPartition,
    load_iso_countries,
    load_s3_requirements,
    load_tile_index,
    load_tile_weights,
)
from .config import RunnerConfig


@dataclass(frozen=True)
class PreparedInputs:
    """Resolved inputs for S4 execution."""

    config: RunnerConfig
    dictionary: Mapping[str, object]
    requirements: S3RequirementsPartition
    tile_weights: TileWeightsPartition
    tile_index: TileIndexPartition
    iso_table: IsoCountryTable
    iso_version: str | None


def prepare_inputs(config: RunnerConfig) -> PreparedInputs:
    """Resolve and validate all deterministic inputs for S4."""

    dictionary = config.dictionary or _load_default_dictionary(config.data_root)

    requirements = load_s3_requirements(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    tile_weights = load_tile_weights(
        base_path=config.data_root,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    tile_index = load_tile_index(
        base_path=config.data_root,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    iso_table, iso_version = load_iso_countries(
        base_path=config.data_root,
        dictionary=dictionary,
    )

    return PreparedInputs(
        config=config,
        dictionary=dictionary,
        requirements=requirements,
        tile_weights=tile_weights,
        tile_index=tile_index,
        iso_table=iso_table,
        iso_version=iso_version,
    )


def _load_default_dictionary(base_path: Path) -> Mapping[str, object]:
    from ...shared.dictionary import load_dictionary as _load_dict

    return _load_dict()


__all__ = ["PreparedInputs", "prepare_inputs"]
