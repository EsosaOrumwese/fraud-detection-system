"""Validation helpers for S7 integer allocation outputs."""

from __future__ import annotations

from typing import Sequence

from ..s0_foundations.exceptions import err
from .types import MerchantAllocationResult

__all__ = ["validate_results"]


def validate_results(results: Sequence[MerchantAllocationResult]) -> None:
    """Perform structural checks on allocation results."""

    for merchant in results:
        _validate_merchant(merchant)


def _validate_merchant(merchant: MerchantAllocationResult) -> None:
    if not merchant.domain_allocations:
        raise err(
            "E_S7_DOMAIN_EMPTY",
            f"merchant {merchant.merchant_id} has empty allocation domain",
        )

    total = sum(item.allocated_count for item in merchant.domain_allocations)
    if total != merchant.total_outlets:
        raise err(
            "INTEGER_SUM_MISMATCH",
            f"Σ counts {total} != N {merchant.total_outlets} for merchant {merchant.merchant_id}",
        )

    share_sum = sum(item.share for item in merchant.domain_allocations)
    if not (0.0 <= share_sum <= 1.0000001):
        raise err(
            "E_S7_SHARE_INVALID",
            f"share sum outside [0,1] for merchant {merchant.merchant_id}: {share_sum}",
        )
    if abs(share_sum - 1.0) > 1e-6:
        raise err(
            "E_S7_SHARE_INVALID",
            f"share sum deviates from 1 by more than 1e-6 for merchant {merchant.merchant_id}: {share_sum}",
        )

    residual_ranks = sorted(item.residual_rank for item in merchant.domain_allocations)
    expected = list(range(1, len(merchant.domain_allocations) + 1))
    if residual_ranks != expected:
        raise err(
            "E_RESIDUAL_QUANTISATION",
            f"residual ranks for merchant {merchant.merchant_id} are not contiguous from 1",
        )

    for alloc in merchant.domain_allocations:
        if alloc.allocated_count < 0:
            raise err(
                "INTEGER_SUM_MISMATCH",
                f"negative allocation for merchant {merchant.merchant_id} iso {alloc.country_iso}",
            )
        if alloc.upper_bound is not None and alloc.allocated_count > alloc.upper_bound:
            raise err(
                "E_BOUNDS_CAP_EXHAUSTED",
                f"allocation for {alloc.country_iso} exceeds upper bound",
            )
        if alloc.allocated_count < alloc.lower_bound:
            raise err(
                "E_BOUNDS_INFEASIBLE",
                f"allocation for {alloc.country_iso} violates lower bound",
            )
