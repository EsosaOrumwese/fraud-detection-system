"""Common data structures for the S6 foreign-set selection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .policy import SelectionOverrides


@dataclass(frozen=True)
class CandidateInput:
    """S3/S5-enriched candidate row made available to the kernel."""

    merchant_id: int
    country_iso: str
    candidate_rank: int
    weight: float
    is_home: bool


@dataclass(frozen=True)
class MerchantSelectionInput:
    """Context required to run selection for a single merchant."""

    merchant_id: int
    settlement_currency: str
    k_target: int
    candidates: Sequence[CandidateInput]


@dataclass(frozen=True)
class CandidateSelection:
    """Per-candidate outcome produced by the kernel."""

    merchant_id: int
    country_iso: str
    candidate_rank: int
    weight: float
    weight_normalised: float
    uniform: float | None
    key: float | None
    eligible: bool
    selected: bool
    selection_order: int | None


@dataclass(frozen=True)
class MerchantSelectionResult:
    """Final decision state for a merchant."""

    merchant_id: int
    settlement_currency: str
    k_target: int
    k_realised: int
    shortfall: bool
    reason_code: str
    overrides: SelectionOverrides
    truncated_by_cap: bool
    candidates: Sequence[CandidateSelection]
    domain_total: int
    domain_considered: int
    domain_eligible: int
    zero_weight_considered: int
    expected_events: int
    ties_resolved: int
    policy_cap_applied: bool
    cap_value: int


__all__ = [
    "CandidateInput",
    "MerchantSelectionInput",
    "CandidateSelection",
    "MerchantSelectionResult",
]
