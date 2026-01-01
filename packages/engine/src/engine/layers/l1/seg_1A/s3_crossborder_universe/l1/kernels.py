"""Pure kernels for the S3 cross-border universe state (L1)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
import logging

from ...s0_foundations.exceptions import err
from ..l0 import (
    build_candidate_seeds,
    evaluate_rule_ladder,
    load_rule_ladder,
    rank_candidates,
)
from ..constants import SITE_SEQUENCE_LIMIT
from ..l0.policy import (
    BaseWeightPolicy,
    BoundsPolicy,
    ThresholdsPolicy,
    evaluate_base_weight,
)
from ..l0.types import (
    CountRow,
    PriorRow,
    RankedCandidateRow,
    RuleLadder,
    SequenceRow,
)
from ..l2.deterministic import MerchantContext, S3DeterministicContext

logger = logging.getLogger(__name__)


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
    *,
    merchant: MerchantContext,
    policy: BaseWeightPolicy,
    merchant_tags: Tuple[str, ...],
) -> Tuple[List[PriorRow], Optional[List[Decimal]]]:
    evaluations: List[Tuple[RankedCandidateRow, Optional[Decimal]]] = []
    for candidate in ranked:
        score = evaluate_base_weight(
            policy,
            merchant_id=merchant.merchant_id,
            home_country_iso=merchant.home_country_iso,
            channel=merchant.channel,
            mcc=merchant.mcc,
            n_outlets=merchant.n_outlets,
            country_iso=candidate.country_iso,
            is_home=candidate.is_home,
            candidate_rank=candidate.candidate_rank,
            filter_tags=candidate.filter_tags,
            merchant_tags=merchant_tags,
        )
        if score is not None and score < Decimal("0"):
            raise err("ERR_S3_PRIOR_DOMAIN", "prior score produced negative weight")
        evaluations.append((candidate, score))

    priors: List[PriorRow] = []
    weights: List[Decimal] = []
    scored_any = False
    for candidate, score in evaluations:
        if score is None:
            weights.append(Decimal("0"))
            continue
        quant = _quantize_decimal(score, policy.dp)
        priors.append(
            PriorRow(
                merchant_id=candidate.merchant_id,
                country_iso=candidate.country_iso,
                base_weight_dp=_format_fixed_dp(quant, policy.dp),
                dp=policy.dp,
            )
        )
        weights.append(quant)
        scored_any = True

    weight_list: Optional[List[Decimal]]
    if not ranked:
        weight_list = []
    elif not scored_any:
        weight_list = None
    else:
        weight_list = weights
    return priors, weight_list


def _derive_threshold_bounds(
    policy: ThresholdsPolicy,
    ranked: Sequence[RankedCandidateRow],
    *,
    n_outlets: int,
) -> tuple[List[int], List[Optional[int]]]:
    if not policy.enabled:
        return [0 for _ in ranked], [None for _ in ranked]

    num_candidates = len(ranked)
    if num_candidates == 0:
        return [], []

    home_indices = [idx for idx, row in enumerate(ranked) if row.is_home]
    if len(home_indices) != 1:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "candidate set must contain exactly one home row for bounds",
        )
    home_index = home_indices[0]

    L_home = min(int(policy.home_min), int(n_outlets))
    if (
        policy.force_at_least_one_foreign_if_foreign_present
        and num_candidates > 1
        and n_outlets >= 2
    ):
        U_home = int(n_outlets) - 1
    else:
        U_home = int(n_outlets)

    if policy.min_one_per_country_when_feasible and n_outlets >= num_candidates and n_outlets >= 2:
        L_foreign = 1
    else:
        L_foreign = 0

    if policy.foreign_cap_mode == "n_minus_home_min":
        U_foreign = max(L_foreign, int(n_outlets) - L_home)
    else:
        U_foreign = int(n_outlets)

    floors: List[int] = []
    ceilings: List[Optional[int]] = []
    for idx, _row in enumerate(ranked):
        if idx == home_index:
            floors.append(L_home)
            ceilings.append(U_home)
        else:
            floors.append(L_foreign)
            ceilings.append(U_foreign)

    floor_sum = sum(floors)
    ceiling_sum = sum(ceiling for ceiling in ceilings if ceiling is not None)
    if floor_sum > n_outlets or ceiling_sum < n_outlets:
        if policy.on_infeasible == "fail":
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "integer bounds infeasible for merchant",
            )
    return floors, ceilings


def _compute_integerised_counts(
    ranked: Sequence[RankedCandidateRow],
    *,
    n_outlets: int,
    weights: Optional[Sequence[Decimal]],
    policy: ThresholdsPolicy | None,
    bounds_policy: BoundsPolicy | None = None,
) -> Tuple[List[CountRow], List[int]]:
    if n_outlets < 0:
        raise err("ERR_S3_INTEGER_FEASIBILITY", "S2 outlet count must be non-negative")
    dp_resid = 8

    num_candidates = len(ranked)
    if num_candidates == 0:
        if n_outlets != 0:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "no candidates available to satisfy outlet count",
            )
        return [], []

    if policy is None:
        floors = [0 for _ in ranked]
        ceilings = [None for _ in ranked]
    else:
        floors, ceilings = _derive_threshold_bounds(policy, ranked, n_outlets=n_outlets)

    def _country_cap(iso: str) -> Optional[int]:
        if bounds_policy is None:
            return SITE_SEQUENCE_LIMIT
        return bounds_policy.cap_for(iso)

    for idx, candidate in enumerate(ranked):
        iso = candidate.country_iso
        floor_value = floors[idx]
        ceiling_value = ceilings[idx]
        cap_value = _country_cap(iso)
        if cap_value is not None:
            if cap_value <= 0:
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    f"cap for {iso} must be positive",
                )
            if ceiling_value is None:
                ceiling_value = cap_value
            else:
                ceiling_value = min(ceiling_value, cap_value)
        if ceiling_value is not None and ceiling_value < floor_value:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"ceiling for {iso} below its floor",
            )
        floors[idx] = floor_value
        ceilings[idx] = ceiling_value

    floor_sum = sum(floors)
    if floor_sum > n_outlets:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "sum of lower bounds exceeds available outlets",
        )

    counts = floors[:]
    remaining = n_outlets - floor_sum

    cap_remaining: List[int] = []
    for floor_value, ceiling_value in zip(floors, ceilings):
        if ceiling_value is None:
            cap_remaining.append(max(0, n_outlets - floor_value))
        else:
            cap_remaining.append(ceiling_value - floor_value)

    weights_seq: Optional[List[Decimal]]
    if weights is None:
        weights_seq = None
    else:
        weights_seq = [Decimal(weight) for weight in weights]
        if len(weights_seq) != num_candidates:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "weights length mismatch for integerisation",
            )
        if any(weight < Decimal("0") for weight in weights_seq):
            raise err(
                "ERR_S3_WEIGHT_ZERO",
                "prior weights must be non-negative",
            )
        if sum(weights_seq) <= Decimal("0"):
            raise err(
                "ERR_S3_WEIGHT_ZERO",
                "sum of prior weights is zero",
            )

    residuals: List[Decimal] = [Decimal("0")] * num_candidates

    eligible = [idx for idx, cap in enumerate(cap_remaining) if cap > 0]
    if remaining > 0 and not eligible:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "no capacity available for remaining outlets",
        )

    bump_set: set[int] = set()
    if eligible:
        if weights_seq is None:
            eligible_weights = [Decimal("1")] * len(eligible)
            weight_sum = Decimal(len(eligible))
        else:
            eligible_weights = [weights_seq[idx] for idx in eligible]
            weight_sum = sum(eligible_weights)
            if weight_sum <= Decimal("0"):
                raise err(
                    "ERR_S3_WEIGHT_ZERO",
                    "sum of prior weights is zero for integerisation",
                )
        remaining_decimal = Decimal(remaining)
        floors_used = 0
        for idx, weight in zip(eligible, eligible_weights):
            share = weight / weight_sum if weight_sum else Decimal("0")
            ideal = remaining_decimal * share
            floor_amt = int(ideal.to_integral_value(rounding=ROUND_DOWN))
            if floor_amt > cap_remaining[idx]:
                floor_amt = cap_remaining[idx]
            counts[idx] += floor_amt
            cap_remaining[idx] -= floor_amt
            residual = ideal - Decimal(floor_amt)
            if cap_remaining[idx] > 0:
                residuals[idx] = _quantize_decimal(residual, dp_resid)
            floors_used += floor_amt
        remaining_units = remaining - floors_used

        eligible_for_bump = [idx for idx in eligible if cap_remaining[idx] > 0]
        if remaining_units > 0 and not eligible_for_bump:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "no capacity available for remaining outlets",
            )

        if remaining_units > 0:
            order = sorted(
                eligible_for_bump,
                key=lambda idx: (
                    -residuals[idx],
                    ranked[idx].country_iso,
                    ranked[idx].candidate_rank,
                    idx,
                ),
            )
            if remaining_units > len(order):
                raise err(
                    "ERR_S3_INTEGER_FEASIBILITY",
                    "residual capacity exhausted before distributing all outlets",
                )
            for idx in order[:remaining_units]:
                counts[idx] += 1
                cap_remaining[idx] -= 1
            bump_set = set(order)

        order_all = sorted(
            range(num_candidates),
            key=lambda idx: (
                0 if idx in bump_set else 1 if idx in eligible else 2,
                -residuals[idx],
                ranked[idx].country_iso,
                ranked[idx].candidate_rank,
                idx,
            ),
        )
    else:
        order_all = list(range(num_candidates))

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
        if count < floors[idx]:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"count falls below floor for {ranked[idx].country_iso}",
            )
        ceiling_value = ceilings[idx]
        if ceiling_value is not None and count > ceiling_value:
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
        if count > SITE_SEQUENCE_LIMIT:
            logger.error(
                "S3 sequence overflow (merchant=%s, country=%s, count=%s)",
                candidate.merchant_id,
                candidate.country_iso,
                count,
            )
            raise err(
                "ERR_S3_SITE_SEQUENCE_OVERFLOW",
                (
                    "site_order demand exceeds 6-digit capacity "
                    f"(merchant={candidate.merchant_id}, "
                    f"country={candidate.country_iso}, count={count})"
                ),
            )
        for order in range(1, count + 1):
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
    bounds_policy: BoundsPolicy | None,
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
        priors, weight_list = _compute_priors(
            ranked,
            merchant=merchant,
            policy=base_weight_policy,
            merchant_tags=evaluation.merchant_tags,
        )
        priors_rows = tuple(priors)
        weights = weight_list

    counts_rows: Tuple[CountRow, ...] | None = None
    sequence_rows: Tuple[SequenceRow, ...] | None = None
    if toggles.integerisation_enabled:
        count_rows_list, counts = _compute_integerised_counts(
            ranked,
            n_outlets=merchant.n_outlets,
            weights=weights,
            policy=thresholds_policy,
            bounds_policy=bounds_policy,
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
    bounds_policy: BoundsPolicy | None = None,
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
            bounds_policy=bounds_policy,
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
