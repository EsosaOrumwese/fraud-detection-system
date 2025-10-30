"""Input preparation for Segment 1B state-7."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ...shared.dictionary import load_dictionary
from ..exceptions import err
from ..l0.datasets import (
    OutletCataloguePartition,
    S5AssignmentPartition,
    S6JitterPartition,
    TileBoundsPartition,
    VerifiedGate,
    load_outlet_catalogue,
    load_s5_assignments,
    load_s6_jitter,
    load_tile_bounds,
    verify_consumer_gate,
)
from .config import RunnerConfig


@dataclass(frozen=True)
class PreparedInputs:
    """Resolved inputs required for site synthesis."""

    dictionary: Mapping[str, object]
    gate: VerifiedGate
    assignments: S5AssignmentPartition
    jitter: S6JitterPartition
    tile_bounds: TileBoundsPartition
    outlet_catalogue: OutletCataloguePartition
    manifest_fingerprint: str
    parameter_hash: str
    seed: str
    data_root: Path


def prepare_inputs(config: RunnerConfig) -> PreparedInputs:
    """Resolve dictionary-backed inputs and perform gate verification."""

    dictionary = config.dictionary or load_dictionary()

    gate = verify_consumer_gate(
        base_path=config.data_root,
        manifest_fingerprint=config.manifest_fingerprint,
        dictionary=dictionary,
    )

    assignments = load_s5_assignments(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )
    jitter = load_s6_jitter(
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
    outlet_catalogue = load_outlet_catalogue(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        dictionary=dictionary,
    )

    if assignments.frame.is_empty():
        raise err(
            "E701_ROW_MISSING",
            "s5_site_tile_assignment contains no rows for the requested identity",
        )

    return PreparedInputs(
        dictionary=dictionary,
        gate=gate,
        assignments=assignments,
        jitter=jitter,
        tile_bounds=tile_bounds,
        outlet_catalogue=outlet_catalogue,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        seed=config.seed,
        data_root=config.data_root,
    )


__all__ = ["PreparedInputs", "prepare_inputs"]
