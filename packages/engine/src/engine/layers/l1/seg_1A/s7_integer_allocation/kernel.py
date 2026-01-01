"""Core deterministic allocation logic for S7."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from ..s0_foundations.exceptions import err
from .policy import IntegerisationPolicy, ResidualQuantisationPolicy
from .types import DomainAllocation, DomainMember, MerchantAllocationInput, MerchantAllocationResult

__all__ = ["allocate_merchants"]


@dataclass(frozen=True)
class _AllocationScratch:
    members: Sequence[DomainMember]
    shares: Sequence[float]
    floors: Sequence[int]
    counts: List[int]
    residuals: Sequence[float]
    residual_order: Sequence[int]


def allocate_merchants(
    merchants: Sequence[MerchantAllocationInput],
    *,
    policy: IntegerisationPolicy,
) -> Sequence[MerchantAllocationResult]:
    """Apply largest-remainder integer allocation across all merchants."""

    results: list[MerchantAllocationResult] = []
    for merchant in merchants:
        scratch = _prepare_allocation(
            merchant,
            bounds_enabled=policy.bounds_enabled,
            residual_policy=policy.residual_policy,
        )
        counts = scratch.counts[:]
        remainder = merchant.total_outlets - sum(counts)
        if remainder < 0:
            raise err(
                "E_INTEGER_SUM_NEGATIVE",
                f"negative remainder for merchant {merchant.merchant_id}: {remainder}",
            )
        counts = _distribute_remainder(
            merchant=merchant,
            scratch=scratch,
            remainder=remainder,
            bounds_enabled=policy.bounds_enabled,
            tiebreak_keys=policy.residual_policy.tiebreak_keys,
        )

        domain_allocations: list[DomainAllocation] = []
        for idx, member in enumerate(scratch.members):
            domain_allocations.append(
                DomainAllocation(
                    country_iso=member.country_iso,
                    candidate_rank=member.candidate_rank,
                    is_home=member.is_home,
                    weight=member.weight,
                    share=scratch.shares[idx],
                    lower_bound=member.lower_bound,
                    upper_bound=member.upper_bound,
                    base_count=scratch.floors[idx],
                    allocated_count=counts[idx],
                    residual=scratch.residuals[idx],
                    residual_rank=int(scratch.residual_order[idx]),
                )
            )

        results.append(
            MerchantAllocationResult(
                merchant_id=merchant.merchant_id,
                settlement_currency=merchant.settlement_currency,
                total_outlets=merchant.total_outlets,
                k_target=merchant.k_target,
                k_realised=merchant.k_realised,
                shortfall=merchant.shortfall,
                domain_allocations=tuple(domain_allocations),
                remainder=remainder,
                bounds_enforced=policy.bounds_enabled,
            )
        )

    return tuple(results)


def _prepare_allocation(
    merchant: MerchantAllocationInput,
    *,
    bounds_enabled: bool,
    residual_policy: ResidualQuantisationPolicy,
) -> _AllocationScratch:
    members = list(merchant.domain)
    if not members:
        raise err(
            "E_S7_DOMAIN_EMPTY",
            f"allocation domain empty for merchant {merchant.merchant_id}",
        )
    total_weight = sum(member.weight for member in members)
    if total_weight <= 0.0:
        raise err(
            "E_ZERO_SUPPORT",
            f"restricted S5 weights sum to 0 for merchant {merchant.merchant_id}",
        )

    shares = [member.weight / total_weight for member in members]
    raw_targets = [merchant.total_outlets * share for share in shares]
    floors = [math.floor(value) for value in raw_targets]
    residuals = [
        _quantise_residual(
            raw - floor,
            residual_policy=residual_policy,
        )
        for raw, floor in zip(raw_targets, floors)
    ]

    if bounds_enabled:
        adjusted = []
        for base, member in zip(floors, members, strict=False):
            candidate = max(base, member.lower_bound)
            if member.upper_bound is not None and candidate > member.upper_bound:
                raise err(
                    "E_BOUNDS_INFEASIBLE",
                    f"bounds infeasible for ISO {member.country_iso}: "
                    f"lower {member.lower_bound}, upper {member.upper_bound}, "
                    f"base {base}",
                )
            adjusted.append(candidate)
        floors = adjusted

    counts = floors[:]
    order = _residual_ranking(
        members=members,
        residuals=residuals,
        merchant_id=merchant.merchant_id,
        tiebreak_keys=residual_policy.tiebreak_keys,
    )
    return _AllocationScratch(
        members=tuple(members),
        shares=tuple(shares),
        floors=tuple(floors),
        counts=counts,
        residuals=tuple(residuals),
        residual_order=order,
    )


def _distribute_remainder(
    *,
    merchant: MerchantAllocationInput,
    scratch: _AllocationScratch,
    remainder: int,
    bounds_enabled: bool,
    tiebreak_keys: Sequence[str],
) -> List[int]:
    counts = scratch.counts[:]
    members = scratch.members

    if bounds_enabled:
        feasibility = sum(member.lower_bound for member in members)
        if feasibility > merchant.total_outlets:
            raise err(
                "E_BOUNDS_INFEASIBLE",
                f"floors exceed total outlets for merchant {merchant.merchant_id}",
            )

    if remainder == 0:
        return counts

    ranked_indices = _residual_sort_indices(
        members=members,
        residuals=scratch.residuals,
        merchant_id=merchant.merchant_id,
        tiebreak_keys=tiebreak_keys,
    )
    remaining = remainder
    for index in ranked_indices:
        if remaining == 0:
            break
        upper = members[index].upper_bound
        if upper is not None and counts[index] >= upper:
            continue
        counts[index] += 1
        remaining -= 1

    if remaining != 0:
        raise err(
            "E_BOUNDS_CAP_EXHAUSTED",
            f"unable to allocate remainder for merchant {merchant.merchant_id} "
            f"(remaining={remaining})",
        )
    return counts


def _quantise_residual(
    value: float,
    *,
    residual_policy: ResidualQuantisationPolicy,
) -> float:
    if residual_policy.forbid_nan_inf and not math.isfinite(value):
        raise err("E_RESIDUAL_POLICY", "residual is non-finite")
    if residual_policy.enforce_residual_domain:
        lower, upper = residual_policy.residual_domain
        if value < lower or value > upper:
            raise err(
                "E_RESIDUAL_POLICY",
                f"residual {value!r} outside [{lower}, {upper}]",
            )
    scale = 10.0 ** residual_policy.dp_resid
    rounded = round(value * scale)
    return rounded / scale


def _residual_sort_indices(
    *,
    members: Sequence[DomainMember],
    residuals: Sequence[float],
    merchant_id: int,
    tiebreak_keys: Sequence[str],
) -> Sequence[int]:
    indexed = list(enumerate(zip(members, residuals, range(len(members)), strict=False)))

    def _tiebreak_values(member: DomainMember) -> tuple[object, ...]:
        values: list[object] = []
        for key in tiebreak_keys:
            if key == "country_iso_asc":
                values.append(member.country_iso)
            elif key == "candidate_rank_asc":
                values.append(int(member.candidate_rank))
            elif key == "merchant_id_asc":
                values.append(int(merchant_id))
            else:
                raise err(
                    "E_RESIDUAL_POLICY",
                    f"tiebreak key '{key}' not available for S7 residual sorting",
                )
        return tuple(values)

    indexed.sort(
        key=lambda item: (
            -item[1][1],
            *_tiebreak_values(item[1][0]),
            item[0],
        )
    )
    return tuple(index for index, _ in indexed)


def _residual_ranking(
    *,
    members: Sequence[DomainMember],
    residuals: Sequence[float],
    merchant_id: int,
    tiebreak_keys: Sequence[str],
) -> Sequence[int]:
    order = _residual_sort_indices(
        members=members,
        residuals=residuals,
        merchant_id=merchant_id,
        tiebreak_keys=tiebreak_keys,
    )
    ranks = [0] * len(members)
    for rank, index in enumerate(order, start=1):
        ranks[index] = rank
    return tuple(ranks)
