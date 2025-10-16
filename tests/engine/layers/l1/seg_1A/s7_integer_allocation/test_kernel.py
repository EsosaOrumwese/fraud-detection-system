from __future__ import annotations

import pytest

from pathlib import Path

from engine.layers.l1.seg_1A.s7_integer_allocation.kernel import allocate_merchants
from engine.layers.l1.seg_1A.s7_integer_allocation.policy import (
    BoundsPolicy,
    IntegerisationPolicy,
)
from engine.layers.l1.seg_1A.s7_integer_allocation.types import (
    DomainMember,
    MerchantAllocationInput,
)


def _policy(
    *,
    dirichlet_enabled: bool = False,
    dirichlet_alpha0: float | None = None,
    bounds_enabled: bool = False,
    bounds: BoundsPolicy | None = None,
):
    return IntegerisationPolicy(
        policy_semver="1.0.0",
        policy_version="2025-10-16",
        dp_resid=8,
        dirichlet_enabled=dirichlet_enabled,
        dirichlet_alpha0=dirichlet_alpha0,
        bounds_enabled=bounds_enabled,
        bounds=bounds,
    )


def test_allocate_merchants_basic() -> None:
    merchant = MerchantAllocationInput(
        merchant_id=1,
        settlement_currency="USD",
        total_outlets=5,
        k_target=1,
        k_realised=1,
        shortfall=False,
        domain=(
            DomainMember(
                country_iso="US",
                candidate_rank=0,
                is_home=True,
                weight=0.6,
                lower_bound=0,
                upper_bound=None,
            ),
            DomainMember(
                country_iso="CA",
                candidate_rank=1,
                is_home=False,
                weight=0.4,
                lower_bound=0,
                upper_bound=None,
            ),
        ),
    )

    results = allocate_merchants((merchant,), policy=_policy())

    assert len(results) == 1
    allocation = results[0]
    counts = {entry.country_iso: entry.allocated_count for entry in allocation.domain_allocations}
    assert counts == {"US": 3, "CA": 2}
    residual_ranks = {
        entry.country_iso: entry.residual_rank for entry in allocation.domain_allocations
    }
    assert residual_ranks == {"US": 2, "CA": 1}
    assert allocation.remainder == 0


def test_allocate_merchants_respects_bounds() -> None:
    merchant = MerchantAllocationInput(
        merchant_id=2,
        settlement_currency="USD",
        total_outlets=4,
        k_target=1,
        k_realised=1,
        shortfall=False,
        domain=(
            DomainMember(
                country_iso="US",
                candidate_rank=0,
                is_home=True,
                weight=0.5,
                lower_bound=2,
                upper_bound=3,
            ),
            DomainMember(
                country_iso="CA",
                candidate_rank=1,
                is_home=False,
                weight=0.5,
                lower_bound=0,
                upper_bound=2,
            ),
        ),
    )

    policy = _policy(bounds_enabled=False)
    results = allocate_merchants((merchant,), policy=policy)
    counts = {entry.country_iso: entry.allocated_count for entry in results[0].domain_allocations}
    assert counts == {"US": 2, "CA": 2}

    infeasible = MerchantAllocationInput(
        merchant_id=3,
        settlement_currency="USD",
        total_outlets=1,
        k_target=0,
        k_realised=0,
        shortfall=False,
        domain=(
            DomainMember(
                country_iso="US",
                candidate_rank=0,
                is_home=True,
                weight=1.0,
                lower_bound=2,
                upper_bound=3,
            ),
        ),
    )

    infeasible_policy = _policy(
        bounds_enabled=True,
        bounds=BoundsPolicy(
            path=Path("bounds.yaml"),
            floors={"US": 2},
            ceilings={"US": 3},
        ),
    )

    with pytest.raises(Exception):
        allocate_merchants((infeasible,), policy=infeasible_policy)
