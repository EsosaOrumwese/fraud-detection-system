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
from ..l0.policy import BaseWeightPolicy, ThresholdsPolicy, evaluate_base_weight
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
    *,
    merchant: MerchantContext,
    policy: BaseWeightPolicy,
    merchant_tags: Tuple[str, ...],
) -> Tuple[List[PriorRow], Optional[List[Decimal]]]:
    priors: List[PriorRow] = []
    weights: List[Decimal] = []
    scored_any = False
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
        if score is None:
            weights.append(Decimal("0"))
            continue
        if score < Decimal("0"):
            raise err("ERR_S3_PRIOR_DOMAIN", "prior score produced negative weight")
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

    num_candidates = len(ranked)
    if num_candidates == 0:
        if n_outlets != 0:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                "no candidates available to satisfy outlet count",
            )
        return [], []

    floors_map = policy.floors if policy else {}
    ceilings_map = policy.ceilings if policy else {}

    floors: List[int] = []
    ceilings: List[Optional[int]] = []
    for candidate in ranked:
        iso = candidate.country_iso
        floor_value = int(floors_map.get(iso, 0))
        if floor_value < 0:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"floor for {iso} must be non-negative",
            )
        ceiling_value_raw = ceilings_map.get(iso)
        ceiling_value = None if ceiling_value_raw is None else int(ceiling_value_raw)
        if ceiling_value is not None and ceiling_value < floor_value:
            raise err(
                "ERR_S3_INTEGER_FEASIBILITY",
                f"ceiling for {iso} below its floor",
            )
        floors.append(floor_value)
        ceilings.append(ceiling_value)

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
