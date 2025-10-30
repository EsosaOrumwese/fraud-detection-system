"""Deterministic context definitions for S7 integer allocation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .types import DomainMember, MerchantAllocationInput


@dataclass(frozen=True)
class S7DeterministicContext:
    """Immutable execution context shared across the S7 pipeline."""

    parameter_hash: str
    manifest_fingerprint: str
    seed: int
    run_id: str
    policy_path: Path
    merchants: Sequence[MerchantAllocationInput]
    artefact_digests: Mapping[str, str] | None = None


__all__ = [
    "DomainMember",
    "MerchantAllocationInput",
    "S7DeterministicContext",
]
