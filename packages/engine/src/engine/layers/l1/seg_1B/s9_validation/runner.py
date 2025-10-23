"""Runner scaffolding for Segment 1B S9 validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .contexts import S9DeterministicContext, S9ValidationResult
from .loader import load_deterministic_context


@dataclass(frozen=True)
class RunnerConfig:
    """Identity inputs required to execute S9."""

    base_path: Path
    seed: int
    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    dictionary: Mapping[str, object] | None = None


@dataclass(frozen=True)
class S9RunResult:
    """Outcome of the S9 runner."""

    context: S9DeterministicContext
    result: S9ValidationResult | None = None


class S9ValidationRunner:
    """High-level orchestrator for S9."""

    def run(self, config: RunnerConfig) -> S9RunResult:
        context = load_deterministic_context(
            base_path=config.base_path,
            seed=config.seed,
            parameter_hash=config.parameter_hash,
            manifest_fingerprint=config.manifest_fingerprint,
            run_id=config.run_id,
            dictionary=config.dictionary,
        )
        raise NotImplementedError("S9 runner execution not implemented yet")


__all__ = ["RunnerConfig", "S9RunResult", "S9ValidationRunner"]
