"""Pure kernels for the S3 cross-border universe state (L1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from ...s0_foundations.exceptions import err
from ..l0 import (
    build_candidate_seeds,
    evaluate_rule_ladder,
    load_rule_ladder,
    rank_candidates,
)
from ..l0.types import RankedCandidateRow, RuleLadder
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


@dataclass(frozen=True)
class S3KernelResult:
    """Aggregated S3 L1 output across merchants."""

    ranked_candidates: Tuple[RankedCandidateRow, ...]

def build_rule_ladder(artefact_path: Path) -> RuleLadder:
    """Read and parse the governed rule ladder artefact."""

    return load_rule_ladder(artefact_path)


def evaluate_merchant(
    *,
    merchant: MerchantContext,
    iso_universe: Iterable[str],
    ladder: RuleLadder,
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
    return S3MerchantOutput(
        merchant_id=merchant.merchant_id,
        ranked_candidates=ranked,
        eligible_crossborder=evaluation.eligible_crossborder,
    )


def run_kernels(
    *,
    deterministic: S3DeterministicContext,
    artefact_path: Path,
    toggles: S3FeatureToggles,
) -> S3KernelResult:
    """Evaluate S3 L1 kernels across the deterministic merchant slice."""

    toggles.validate()
    ladder = load_rule_ladder(artefact_path)
    iso_universe = deterministic.iso_countries
    ranked_rows: list[RankedCandidateRow] = []
    for merchant in deterministic.merchants:
        merchant_output = evaluate_merchant(
            merchant=merchant,
            iso_universe=iso_universe,
            ladder=ladder,
        )
        ranked_rows.extend(merchant_output.ranked_candidates)
    return S3KernelResult(ranked_candidates=tuple(ranked_rows))
