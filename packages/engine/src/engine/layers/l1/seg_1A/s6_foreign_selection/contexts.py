"""Deterministic context definitions for S6 foreign-set selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .types import MerchantSelectionInput


@dataclass(frozen=True)
class S6DeterministicContext:
    """Immutable execution context shared across S6 pipeline stages."""

    parameter_hash: str
    manifest_fingerprint: str
    seed: int
    run_id: str
    merchants: Sequence[MerchantSelectionInput]
    policy_path: Path
    artefact_digests: Mapping[str, str] | None = None


__all__ = [
    "S6DeterministicContext",
]
