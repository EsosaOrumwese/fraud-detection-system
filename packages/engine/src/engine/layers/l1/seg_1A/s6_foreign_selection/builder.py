"""Selection kernel for S6 foreign-set selection."""

from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

from .policy import SelectionOverrides, SelectionPolicy
from .types import (
    CandidateInput,
    CandidateSelection,
    MerchantSelectionInput,
    MerchantSelectionResult,
)

UniformProvider = Callable[[int, str, int], float]


def select_foreign_set(
    *,
    policy: SelectionPolicy,
    merchants: Iterable[MerchantSelectionInput],
    uniform_provider: UniformProvider,
) -> Sequence[MerchantSelectionResult]:
    """Run the S6 selection algorithm for the provided merchants."""

    results: list[MerchantSelectionResult] = []
    for merchant in merchants:
        result = _select_for_merchant(
            merchant=merchant,
            overrides=policy.resolve_for_currency(merchant.settlement_currency),
            uniform_provider=uniform_provider,
        )
        results.append(result)
    return results


def _select_for_merchant(
    *,
    merchant: MerchantSelectionInput,
    overrides: SelectionOverrides,
    uniform_provider: UniformProvider,
) -> MerchantSelectionResult:
    foreign_candidates = _ordered_foreign_candidates(merchant.candidates)
    domain_total = len(foreign_candidates)
    if not foreign_candidates:
        return _empty_result(
            merchant=merchant,
            overrides=overrides,
            reason_code="NO_CANDIDATES",
            domain_total=0,
        )

    if merchant.k_target <= 0:
        return _empty_result(
            merchant=merchant,
            overrides=overrides,
            reason_code="K_ZERO",
            domain_total=domain_total,
        )

    truncated = False
    considered = foreign_candidates
    if overrides.max_candidates_cap > 0 and len(considered) > overrides.max_candidates_cap:
        considered = considered[: overrides.max_candidates_cap]
        truncated = True

    if overrides.zero_weight_rule == "exclude":
        considered = [row for row in considered if row.weight > 0.0]

    eligible = [row for row in considered if row.weight > 0.0]

    if not eligible:
        reason = "ZERO_WEIGHT_DOMAIN"
        if truncated:
            reason = "CAPPED_BY_MAX_CANDIDATES"
        return _empty_result(
            merchant=merchant,
            overrides=overrides,
            reason_code=reason,
            domain_total=domain_total,
            domain_considered=len(considered),
            zero_weight_considered=len(considered) - len(eligible),
        )

    normalised_weights = _renormalise_weights(eligible)
    candidates_outcome: list[CandidateSelection] = []

    for row in considered:
        norm_weight = normalised_weights.get(row.country_iso, 0.0)
        is_eligible = row.weight > 0.0
        uniform_value: float | None = None
        key_value: float | None = None

        if is_eligible or overrides.zero_weight_rule == "include":
            # Draw a uniform deviate when the candidate participates in logging.
            uniform_value = uniform_provider(
                row.merchant_id, row.country_iso, row.candidate_rank
            )

        if is_eligible:
            key_value = _gumbel_key(norm_weight, uniform_value)

        candidates_outcome.append(
            CandidateSelection(
                merchant_id=row.merchant_id,
                country_iso=row.country_iso,
                candidate_rank=row.candidate_rank,
                weight=row.weight,
                weight_normalised=norm_weight,
                uniform=uniform_value,
                key=key_value,
                eligible=is_eligible,
                selected=False,
                selection_order=None,
            )
        )

    selected = _select_top_k(
        candidates=[candidate for candidate in candidates_outcome if candidate.eligible],
        k_target=merchant.k_target,
    )
    selected_candidates, ties_resolved = selected

    selection_lookup = {
        (candidate.country_iso, candidate.candidate_rank): (idx + 1)
        for idx, candidate in enumerate(selected_candidates)
    }

    realised = len(selected_candidates)
    shortfall = realised < merchant.k_target

    for idx, candidate in enumerate(candidates_outcome):
        selection_order = selection_lookup.get((candidate.country_iso, candidate.candidate_rank))
        candidates_outcome[idx] = CandidateSelection(
            merchant_id=candidate.merchant_id,
            country_iso=candidate.country_iso,
            candidate_rank=candidate.candidate_rank,
            weight=candidate.weight,
            weight_normalised=candidate.weight_normalised,
            uniform=candidate.uniform,
            key=candidate.key,
            eligible=candidate.eligible,
            selected=selection_order is not None,
            selection_order=selection_order,
        )

    reason_code = "none"
    if truncated:
        reason_code = "CAPPED_BY_MAX_CANDIDATES"
    elif shortfall:
        reason_code = "none"

    return MerchantSelectionResult(
        merchant_id=merchant.merchant_id,
        settlement_currency=merchant.settlement_currency,
        k_target=merchant.k_target,
        k_realised=realised,
        shortfall=shortfall,
        reason_code=reason_code,
        overrides=overrides,
        truncated_by_cap=truncated,
        candidates=tuple(candidates_outcome),
        domain_total=domain_total,
        domain_considered=len(considered),
        domain_eligible=len(eligible),
        zero_weight_considered=max(0, len(considered) - len(eligible)),
        expected_events=len(considered),
        ties_resolved=ties_resolved,
        policy_cap_applied=truncated,
        cap_value=overrides.max_candidates_cap,
    )


def _ordered_foreign_candidates(candidates: Sequence[CandidateInput]) -> list[CandidateInput]:
    filtered = [row for row in candidates if not row.is_home]
    return sorted(filtered, key=lambda row: row.candidate_rank)


def _empty_result(
    *,
    merchant: MerchantSelectionInput,
    overrides: SelectionOverrides,
    reason_code: str,
    domain_total: int,
    domain_considered: int | None = None,
    zero_weight_considered: int = 0,
) -> MerchantSelectionResult:
    considered = domain_total if domain_considered is None else domain_considered
    return MerchantSelectionResult(
        merchant_id=merchant.merchant_id,
        settlement_currency=merchant.settlement_currency,
        k_target=merchant.k_target,
        k_realised=0,
        shortfall=merchant.k_target > 0,
        reason_code=reason_code,
        overrides=overrides,
        truncated_by_cap=False,
        candidates=tuple(),
        domain_total=domain_total,
        domain_considered=considered,
        domain_eligible=0,
        zero_weight_considered=zero_weight_considered,
        expected_events=considered,
        ties_resolved=0,
        policy_cap_applied=False,
        cap_value=overrides.max_candidates_cap,
    )


def _renormalise_weights(eligible: Sequence[CandidateInput]) -> dict[str, float]:
    total = sum(row.weight for row in eligible)
    if total <= 0.0:
        return {}
    return {
        row.country_iso: row.weight / total
        for row in eligible
    }


def _gumbel_key(weight: float, uniform: float | None) -> float:
    if uniform is None or uniform <= 0.0 or uniform >= 1.0:
        raise ValueError("uniform deviate must lie in (0, 1)")
    if weight <= 0.0:
        raise ValueError("weight must be > 0 when computing gumbel key")
    return math.log(weight) - math.log(-math.log(uniform))


def _select_top_k(
    *,
    candidates: Sequence[CandidateSelection],
    k_target: int,
) -> tuple[list[CandidateSelection], int]:
    if not candidates or k_target <= 0:
        return [], 0

    sorted_candidates = sorted(
        candidates,
        key=lambda candidate: (
            -candidate.key if candidate.key is not None else float("-inf"),
            candidate.candidate_rank,
            candidate.country_iso,
        ),
    )
    ties_resolved = 0
    last_key: float | None = None
    for candidate in sorted_candidates:
        if candidate.key is None:
            continue
        current_key = candidate.key
        if last_key is not None and math.isclose(current_key, last_key, rel_tol=0.0, abs_tol=1e-12):
            ties_resolved += 1
        last_key = current_key
    selected = sorted_candidates[: min(k_target, len(sorted_candidates))]
    return selected, ties_resolved


__all__ = [
    "UniformProvider",
    "select_foreign_set",
]
