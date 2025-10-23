"""Input preparation for Segment 1B state-8."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ...shared.dictionary import load_dictionary
from ..l0.datasets import S7SiteSynthesisPartition, load_s7_site_synthesis
from .config import RunnerConfig


@dataclass(frozen=True)
class PreparedInputs:
    """Resolved inputs required for site_locations egress."""

    dictionary: Mapping[str, object]
    synthesis: S7SiteSynthesisPartition
    manifest_fingerprint: str
    parameter_hash: str
    seed: str
    data_root: Path


def prepare_inputs(config: RunnerConfig) -> PreparedInputs:
    """Resolve dictionary-backed inputs for S8."""

    dictionary = config.dictionary or load_dictionary()
    synthesis = load_s7_site_synthesis(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )

    return PreparedInputs(
        dictionary=dictionary,
        synthesis=synthesis,
        manifest_fingerprint=config.manifest_fingerprint,
        parameter_hash=config.parameter_hash,
        seed=config.seed,
        data_root=config.data_root,
    )


__all__ = ["PreparedInputs", "prepare_inputs"]
