"""Orchestrator for the S8 outlet catalogue pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .contexts import S8DeterministicContext, S8Metrics


@dataclass(frozen=True)
class S8RunOutputs:
    """Materialised artefacts emitted by the S8 runner."""

    deterministic: S8DeterministicContext
    catalogue_path: Path
    sequence_finalize_path: Path | None
    sequence_overflow_path: Path | None
    validation_bundle_path: Path | None
    metrics: S8Metrics
    stage_log_path: Path | None = None
    auxiliary_paths: Mapping[str, Path] | None = None


class S8Runner:
    """Execute the S8 pipeline end-to-end."""

    def run(
        self,
        *,
        base_path: Path,
        parameter_hash: str,
        manifest_fingerprint: str,
        seed: int,
        run_id: str,
    ) -> S8RunOutputs:
        """Run the S8 pipeline using governed artefacts resolved from `base_path`."""
        raise NotImplementedError("S8 runner has not been implemented yet.")


__all__ = [
    "S8RunOutputs",
    "S8Runner",
]
