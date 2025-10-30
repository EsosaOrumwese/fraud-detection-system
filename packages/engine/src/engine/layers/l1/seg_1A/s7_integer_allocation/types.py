"""Common data structures for the S7 integer allocation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DomainMember:
    """Domain entry (home + selected foreigns) presented to the allocation kernel."""

    country_iso: str
    candidate_rank: int
    is_home: bool
    weight: float
    lower_bound: int
    upper_bound: int | None


@dataclass(frozen=True)
class MerchantAllocationInput:
    """Deterministic inputs required to allocate counts for a merchant."""

    merchant_id: int
    settlement_currency: str
    total_outlets: int
    k_target: int
    k_realised: int
    shortfall: bool
    domain: Sequence[DomainMember]


@dataclass(frozen=True)
class DomainAllocation:
    """Per-country allocation outcome."""

    country_iso: str
    candidate_rank: int
    is_home: bool
    weight: float
    share: float
    lower_bound: int
    upper_bound: int | None
    base_count: int
    allocated_count: int
    residual: float
    residual_rank: int


@dataclass(frozen=True)
class MerchantAllocationResult:
    """Final allocation result for a merchant."""

    merchant_id: int
    settlement_currency: str
    total_outlets: int
    k_target: int
    k_realised: int
    shortfall: bool
    domain_allocations: Sequence[DomainAllocation]
    remainder: int
    bounds_enforced: bool


__all__ = [
    "DomainAllocation",
    "DomainMember",
    "MerchantAllocationInput",
    "MerchantAllocationResult",
]
