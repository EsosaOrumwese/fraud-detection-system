"""Prepare inputs for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ..exceptions import err
from ..l0.datasets import (
    IsoCountryTable,
    S4AllocPlanPartition,
    TileIndexPartition,
    load_iso_countries,
    load_s4_alloc_plan,
    load_tile_index_partition,
)
from .config import RunnerConfig


@dataclass(frozen=True)
class PreparedInputs:
    """Resolved inputs required for S5 execution."""

    config: RunnerConfig
    dictionary: Mapping[str, object]
    alloc_plan: S4AllocPlanPartition
    tile_index: TileIndexPartition
    iso_table: IsoCountryTable
    iso_version: str | None


def prepare_inputs(config: RunnerConfig) -> PreparedInputs:
    """Resolve dictionary-backed inputs and perform basic validation."""

    dictionary = config.dictionary or _load_default_dictionary(config.data_root)

    alloc_plan = load_s4_alloc_plan(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    tile_index = load_tile_index_partition(
        base_path=config.data_root,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    iso_table, iso_version = load_iso_countries(
        base_path=config.data_root,
        dictionary=dictionary,
    )

    if alloc_plan.frame.is_empty():
        raise err(
            "E504_SUM_TO_N_MISMATCH",
            "s4_alloc_plan contains no rows for the requested identity",
        )

    return PreparedInputs(
        config=config,
        dictionary=dictionary,
        alloc_plan=alloc_plan,
        tile_index=tile_index,
        iso_table=iso_table,
        iso_version=iso_version,
    )


def _load_default_dictionary(base_path: Path) -> Mapping[str, object]:
    from ...shared.dictionary import load_dictionary as _load_dict

    return _load_dict()


__all__ = ["PreparedInputs", "prepare_inputs"]
