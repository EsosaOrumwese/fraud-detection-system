"""Deterministic context definitions for the S4 ZTP target state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple


@dataclass(frozen=True)
class S4HyperParameters:
    """Governed coefficients and policy knobs for the S4 ZTP sampler."""

    theta0: float
    theta1: float
    theta2: float | None = None  # optional feature weight (defaults handled upstream)
    max_zero_attempts: int = 64
    exhaustion_policy: str = "abort"  # {"abort", "downgrade_domestic"}
    default_feature_value: float = 0.0
    source_path: Path | None = None
    semver: str | None = None


@dataclass(frozen=True)
class S4MerchantTarget:
    """Per-merchant deterministic inputs required by the S4 kernel."""

    merchant_id: int
    n_outlets: int  # N from S2
    admissible_foreign_count: int  # A from S3
    is_multi: bool
    is_eligible: bool
    feature_value: float  # X in [0,1]


@dataclass(frozen=True)
class S4DeterministicContext:
    """Bundle handed to the S4 kernel for all eligible merchants."""

    parameter_hash: str
    manifest_fingerprint: str
    seed: int
    run_id: str
    hyperparams: S4HyperParameters
    merchants: Tuple[S4MerchantTarget, ...]
    feature_name: str = "x"  # Optional descriptive name for the feature map
    feature_source_path: Path | None = None
    artefact_digests: Mapping[str, str] | None = None  # optional audit trail

    def by_merchant(self) -> Mapping[int, S4MerchantTarget]:
        """Access merchant contexts keyed by merchant id."""

        return {merchant.merchant_id: merchant for merchant in self.merchants}


__all__ = [
    "S4DeterministicContext",
    "S4HyperParameters",
    "S4MerchantTarget",
]
