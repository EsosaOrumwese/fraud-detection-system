"""Deterministic context definitions for state-5 currency→country weights."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class S5DeterministicContext:
    """Immutable execution context shared across S5 pipeline stages."""

    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    seed: int
    policy_path: Path
    settlement_shares_path: Path | None = None
    ccy_country_shares_path: Path | None = None
    iso_legal_tender_path: Path | None = None
    artefact_digests: Mapping[str, str] | None = None


@dataclass(frozen=True)
class S5PolicyMetadata:
    """Metadata captured during N0 policy resolution."""

    path: Path
    digest_hex: str
    version: str
    semver: str


__all__ = [
    "S5DeterministicContext",
    "S5PolicyMetadata",
]
