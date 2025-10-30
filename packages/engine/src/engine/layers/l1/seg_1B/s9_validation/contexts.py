"""Dataclasses carried across the Segment 1B S9 validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import polars as pl

from .exceptions import ErrorContext


@dataclass(frozen=True)
class S9InputSurfaces:
    """Resolved upstream artefacts consumed by the validator."""

    s7_site_synthesis: pl.DataFrame
    site_locations: pl.DataFrame
    rng_events: Mapping[str, pd.DataFrame]
    rng_audit_log: pd.DataFrame | None = None
    rng_trace_log: pd.DataFrame | None = None


@dataclass(frozen=True)
class S9DeterministicContext:
    """Immutable context assembled from sealed inputs."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    dictionary: Mapping[str, object]
    surfaces: S9InputSurfaces
    source_paths: Mapping[str, Sequence[Path]] = field(default_factory=dict)
    lineage_paths: Mapping[str, Path] = field(default_factory=dict)


@dataclass
class S9ValidationResult:
    """Outcome of the validation battery."""

    passed: bool
    failures: Sequence[ErrorContext]
    summary: Mapping[str, object]
    rng_accounting: Mapping[str, object]


__all__ = [
    "S9InputSurfaces",
    "S9DeterministicContext",
    "S9ValidationResult",
]
