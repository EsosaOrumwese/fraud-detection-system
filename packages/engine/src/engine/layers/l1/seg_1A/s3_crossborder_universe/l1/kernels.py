"""Pure kernels for the S3 cross-border universe state (L1)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from ...s0_foundations.exceptions import err
from ..l0 import (
    build_candidate_seeds,
    evaluate_rule_ladder,
    load_rule_ladder,
    rank_candidates,
)
from ..l0.policy import BaseWeightPolicy, ThresholdsPolicy
from ..l0.types import (
    CountRow,
    PriorRow,
    RankedCandidateRow,
    RuleLadder,
    SequenceRow,
)
from ..l2.deterministic import MerchantContext, S3DeterministicContext


@dataclass(frozen=True)
class S3FeatureToggles:
    """Feature switches for optional S3 lanes."""

    priors_enabled: bool = False
    integerisation_enabled: bool = False
    sequencing_enabled: bool = False

    def validate(self) -> None:
        if self.sequencing_enabled and not self.integerisation_enabled:
            raise err(
                "ERR_S3_PRECONDITION",
                "sequencing_enabled requires integerisation_enabled",
            )


@dataclass(frozen=True)
class S3MerchantOutput:
    """Pure result for a merchant after running S3 kernels."""

    merchant_id: int
    ranked_candidates: Tuple[RankedCandidateRow, ...]
    eligible_crossborder: bool
    priors: Tuple[PriorRow, ...] | None = None
    counts: Tuple[CountRow, ...] | None = None
    sequence: Tuple[SequenceRow, ...] | None = None


@dataclass(frozen=True)
class S3KernelResult:
    """Aggregated S3 L1 output across merchants."""

    ranked_candidates: Tuple[RankedCandidateRow, ...]
    priors: Tuple[PriorRow, ...] | None = None
    counts: Tuple[CountRow, ...] | None = None
    sequence: Tuple[SequenceRow, ...] | None = None


def build_rule_ladder(artefact_path: Path) -> RuleLadder:
    """Read and parse the governed rule ladder artefact."""

    return load_rule_ladder(artefact_path)


def _quantize_decimal(value: Decimal, dp: int) -> Decimal:
    exponent = Decimal(1).scaleb(-dp)
    return value.quantize(exponent, rounding=ROUND_HALF_EVEN)


def _format_fixed_dp(value: Decimal, dp: int) -> str:
    quantized = _quantize_decimal(value, dp)
    return f"{quantized:.{dp}f}"


def _compute_priors(
    ranked: Sequence[RankedCandidateRow],
    policy: BaseWeightPolicy,
) -> Tuple[List[PriorRow], List[Decimal]]:
    priors: List[PriorRow] = []
    weights: List[Decimal] = []
    for candidate in ranked:
        weight = policy.base_home if candidate.is_home else policy.base_foreign
        for tag in candidate.filter_tags:
            multiplier = policy.tag_multipliers.get(tag, Decimal("1"))
            weight *= multiplier
        if weight < policy.min_weight:
            weight = policy.min_weight
        if weight < policy.normalisation_floor:
            weight = policy.normalisation_floor
        quant = _quantize_decimal(weight, policy.dp)
        if quant < Decimal("0"):
            raise err("ERR_S3_PRIOR_DOMAIN", "prior score produced negative weight")
        priors.append(
            PriorRow(
                merchant_id=candidate.merchant_id,
                country_iso=candidate.country_iso,
                base_weight_dp=_format_fixed_dp(quant, policy.dp),
                dp=policy.dp,
            )
        )
        weights.append(quant)
    return priors, weights


def _build_overrides_map(
    policy: ThresholdsPolicy | None,
) -> Tuple[dict[str, int | None], dict[str, int | None]]:
    lower: dict[str, int | None] = {}
    upper: dict[str, int | None] = {}
    if policy is None:
        return lower, upper
    for override in policy.overrides:
        for iso in override.countries:
            if override.lower is not None:
                lower[iso] = override.lower
            if override.upper is not None:
                upper[iso] = override.upper
    return lower, upper


def _compute_integerised_counts(
    ranked: Sequence[RankedCandidateRow],
    *,
    n_outlets: int,
    weights: Optional[Sequence[Decimal]],
    policy: ThresholdsPolicy | None,
) -> Tuple[List[CountRow], List[int]]:
    if n_outlets < 0:
        raise err("ERR_S3_INTEGER_FEASIBILITY", "S2 outlet count must be non-negative")
    dp_resid = policy.residual_dp if policy else 8

    default_lower = policy.default_lower if policy else 0
    default_upper = policy.default_upper if policy else 10**9
    lower_override, upper_override = _build_overrides_map(policy)

    lower_bounds: List[int] = []
    upper_bounds: List[int] = []
    for candidate in ranked:
        iso = candidate.country_iso
        lower = lower_override.get(iso, default_lower)
        upper = upper_override.get(iso, default_upper)
        lower = lower if lower is not None else default_lower
        upper = upper if upper is not None else default_upper
        if lower < 0 or upper < 0:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "bounds must be non-negative integers",
            )
        if upper < lower:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"upper bound {upper} below lower bound {lower} for {iso}",
            )
        lower_bounds.append(lower)
        upper_bounds.append(upper)

    lower_sum = sum(lower_bounds)
    upper_sum = sum(upper_bounds)
    if lower_sum > n_outlets:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "sum of lower bounds exceeds available outlets",
        )
    if upper_sum < n_outlets:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "sum of upper bounds below required outlets",
        )

    counts = lower_bounds[:]
    capacities = [u - c for u, c in zip(upper_bounds, counts)]
    remaining = n_outlets - sum(counts)

    num_candidates = len(ranked)
    if weights is None:
        weights = [Decimal("1")] * num_candidates
    elif len(weights) != num_candidates:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "weights length mismatch for integerisation",
        )

    residuals: List[Decimal] = [Decimal("0")] * num_candidates

    capacity_flag = {idx for idx, cap in enumerate(capacities) if cap > 0}
    available_indices = sorted(capacity_flag)
    if remaining > 0 and not available_indices:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "no capacity available for remaining outlets",
        )

    if remaining > 0 and available_indices:
        total_weight = sum(weights[idx] for idx in available_indices)
        if total_weight <= Decimal("0"):
            raise err(
                "ERR_S3_WEIGHT_ZERO",
                "sum of prior weights is zero for integerisation",
            )
        remaining_decimal = Decimal(remaining)
        floors_used = 0
        for idx in available_indices:
            share = weights[idx] / total_weight
            ideal = remaining_decimal * share
            floor = int(ideal.to_integral_value(rounding=ROUND_DOWN))
            if floor > capacities[idx]:
                floor = capacities[idx]
            counts[idx] += floor
            capacities[idx] -= floor
            residual = ideal - Decimal(floor)
            if capacities[idx] > 0:
                residuals[idx] = _quantize_decimal(residual, dp_resid)
            else:
                residuals[idx] = Decimal("0")
            floors_used += floor
        remaining_units = remaining - floors_used
        if remaining_units > 0:
            order = sorted(
                (
                    idx
                    for idx in available_indices
                    if capacities[idx] > 0
                ),
                key=lambda idx: (
                    -residuals[idx],
                    ranked[idx].country_iso,
                    ranked[idx].candidate_rank,
                    idx,
                ),
            )
            for idx in order[:remaining_units]:
                if capacities[idx] <= 0:
                    continue
                counts[idx] += 1
                capacities[idx] -= 1
    # Assign residual ranks (1-based) using deterministic ordering
    order_all = sorted(
        range(num_candidates),
        key=lambda idx: (
            0 if idx in capacity_flag else 1,
            -residuals[idx],
            ranked[idx].country_iso,
            ranked[idx].candidate_rank,
            idx,
        ),
    )
    residual_rank = {idx: position + 1 for position, idx in enumerate(order_all)}

    total = sum(counts)
    if total != n_outlets:
        raise err(
            "ERR_S3_INTEGER_SUM_MISMATCH",
            f"integerised counts sum {total} != N {n_outlets}",
        )
    for idx, count in enumerate(counts):
        if count < 0:
            raise err(
                "ERR_S3_INTEGER_NEGATIVE",
                f"negative count for {ranked[idx].country_iso}",
            )
        if count > upper_bounds[idx]:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"count exceeds upper bound for {ranked[idx].country_iso}",
            )

    count_rows: List[CountRow] = []
    for idx, (candidate, count) in enumerate(zip(ranked, counts)):
        count_rows.append(
            CountRow(
                merchant_id=candidate.merchant_id,
                country_iso=candidate.country_iso,
                count=count,
                residual_rank=residual_rank[idx],
            )
        )
    return count_rows, counts


def _build_sequence_rows(
    ranked: Sequence[RankedCandidateRow],
    counts: Sequence[int],
) -> List[SequenceRow]:
    rows: List[SequenceRow] = []
    for candidate, count in zip(ranked, counts):
        for order in range(1, count + 1):
            if order > 999_999:
                raise err(
                    "ERR_S3_SITE_SEQUENCE_OVERFLOW",
                    f"site_order {order} exceeds 6-digit capacity",
                )
            rows.append(
                SequenceRow(
                    merchant_id=candidate.merchant_id,
                    country_iso=candidate.country_iso,
                    site_order=order,
                    site_id=f"{order:06d}",
                )
            )
    return rows


def evaluate_merchant(
    *,
    merchant: MerchantContext,
    iso_universe: Iterable[str],
    ladder: RuleLadder,
    toggles: S3FeatureToggles,
    base_weight_policy: BaseWeightPolicy | None,
    thresholds_policy: ThresholdsPolicy | None,
) -> S3MerchantOutput:
    """Execute S3 kernels for a single merchant (deterministic, pure)."""

    evaluation = evaluate_rule_ladder(
        ladder,
        merchant_id=merchant.merchant_id,
        home_country_iso=merchant.home_country_iso,
        channel=merchant.channel,
        mcc=merchant.mcc,
        n_outlets=merchant.n_outlets,
    )
    seeds = build_candidate_seeds(
        ladder,
        evaluation,
        merchant_id=merchant.merchant_id,
        home_country_iso=merchant.home_country_iso,
        iso_universe=iso_universe,
    )
    ranked = rank_candidates(ladder, seeds=seeds)

    priors_rows: Tuple[PriorRow, ...] | None = None
    weights: Optional[List[Decimal]] = None
    if toggles.priors_enabled:
        if base_weight_policy is None:
            raise err(
                "ERR_S3_PRIOR_DISABLED",
                "priors toggled on but no base-weight policy provided",
            )
        priors, weights = _compute_priors(ranked, base_weight_policy)
        priors_rows = tuple(priors)

    counts_rows: Tuple[CountRow, ...] | None = None
    sequence_rows: Tuple[SequenceRow, ...] | None = None
    if toggles.integerisation_enabled:
        count_rows_list, counts = _compute_integerised_counts(
            ranked,
            n_outlets=merchant.n_outlets,
            weights=weights,
            policy=thresholds_policy,
        )
        counts_rows = tuple(count_rows_list)
        if toggles.sequencing_enabled:
            sequence_rows = tuple(_build_sequence_rows(ranked, counts))

    return S3MerchantOutput(
        merchant_id=merchant.merchant_id,
        ranked_candidates=ranked,
        eligible_crossborder=evaluation.eligible_crossborder,
        priors=priors_rows,
        counts=counts_rows,
        sequence=sequence_rows,
    )


def run_kernels(
    *,
    deterministic: S3DeterministicContext,
    artefact_path: Path,
    toggles: S3FeatureToggles,
    base_weight_policy: BaseWeightPolicy | None = None,
    thresholds_policy: ThresholdsPolicy | None = None,
) -> S3KernelResult:
    """Evaluate S3 L1 kernels across the deterministic merchant slice."""

    toggles.validate()
    if toggles.priors_enabled and base_weight_policy is None:
        raise err(
            "ERR_S3_PRIOR_DISABLED",
            "priors enabled but no base-weight policy loaded",
        )
    ladder = load_rule_ladder(artefact_path)
    iso_universe = deterministic.iso_countries

    ranked_rows: List[RankedCandidateRow] = []
    prior_rows: List[PriorRow] = []
    count_rows: List[CountRow] = []
    sequence_rows: List[SequenceRow] = []

    for merchant in deterministic.merchants:
        merchant_output = evaluate_merchant(
            merchant=merchant,
            iso_universe=iso_universe,
            ladder=ladder,
            toggles=toggles,
            base_weight_policy=base_weight_policy,
            thresholds_policy=thresholds_policy,
        )
        ranked_rows.extend(merchant_output.ranked_candidates)
        if merchant_output.priors:
            prior_rows.extend(merchant_output.priors)
        if merchant_output.counts:
            count_rows.extend(merchant_output.counts)
        if merchant_output.sequence:
            sequence_rows.extend(merchant_output.sequence)

    return S3KernelResult(
        ranked_candidates=tuple(ranked_rows),
        priors=tuple(prior_rows) if prior_rows else None,
        counts=tuple(count_rows) if count_rows else None,
        sequence=tuple(sequence_rows) if sequence_rows else None,
    )


__all__ = [
    "S3FeatureToggles",
    "S3KernelResult",
    "build_rule_ladder",
    "evaluate_merchant",
    "run_kernels",
]
