"""Dataclasses used within the S9 validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import polars as pl


@dataclass(frozen=True)
class S9InputSurfaces:
    """Resolved surfaces required by the validator."""

    outlet_catalogue: pl.DataFrame
    s3_candidate_set: pl.DataFrame
    s3_integerised_counts: pl.DataFrame | None = None
    s6_membership: pl.DataFrame | None = None
    nb_final_events: pd.DataFrame | None = None
    sequence_finalize_events: pd.DataFrame | None = None


@dataclass(frozen=True)
class S9DeterministicContext:
    """Immutable execution context shared across S9 steps."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    surfaces: S9InputSurfaces
    upstream_manifest: Mapping[str, object] | None = None
    source_paths: Mapping[str, Sequence[Path]] = field(default_factory=dict)


@dataclass
class S9ValidationMetrics:
    """Accumulator for validation metrics recorded in the bundle summary."""

    merchants_total: int = 0
    merchants_validated: int = 0
    merchants_failed: int = 0
    rows_total: int = 0
    sequence_events: int = 0
    nb_final_events: int = 0
    membership_rows: int | None = None


@dataclass
class S9ValidationResult:
    """Outcome of the S9 validation stage."""

    passed: bool
    failures: Sequence["ErrorContext"]
    metrics: S9ValidationMetrics
    summary: Mapping[str, object]
    rng_accounting: Mapping[str, object]
    failures_by_code: Mapping[str, int]
    counts_source: str
    membership_source: str
    egress_writer_sort_ok: bool


__all__ = [
    "S9InputSurfaces",
    "S9DeterministicContext",
    "S9ValidationMetrics",
    "S9ValidationResult",
]
