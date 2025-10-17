"""Persistence helpers for the S8 outlet catalogue pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .types import OutletCatalogueRow, SequenceFinalizeEvent, SiteSequenceOverflowEvent


@dataclass
class PersistConfig:
    """Configuration for persisting S8 outputs."""

    seed: int
    manifest_fingerprint: str
    output_dir: Path
    parameter_hash: str


def write_outlet_catalogue(
    rows: Sequence[OutletCatalogueRow],
    *,
    config: PersistConfig,
    dictionary: Mapping[str, object] | None = None,
) -> Path:
    """Persist the `outlet_catalogue` parquet partition."""
    raise NotImplementedError("S8 persistence has not been implemented yet.")


def write_sequence_events(
    *,
    sequence_finalize: Sequence[SequenceFinalizeEvent],
    overflow_events: Sequence[SiteSequenceOverflowEvent],
    config: PersistConfig,
) -> Mapping[str, Path]:
    """Write RNG event streams produced by S8."""
    raise NotImplementedError("S8 RNG event persistence has not been implemented yet.")


def write_validation_bundle(
    *,
    bundle_dir: Path,
    metrics_payload: Mapping[str, object],
    rng_accounting_payload: Mapping[str, object],
) -> Path:
    """Produce the validation artefacts mandated by the spec."""
    raise NotImplementedError("S8 validation bundle writer has not been implemented yet.")


__all__ = [
    "PersistConfig",
    "write_outlet_catalogue",
    "write_sequence_events",
    "write_validation_bundle",
]
