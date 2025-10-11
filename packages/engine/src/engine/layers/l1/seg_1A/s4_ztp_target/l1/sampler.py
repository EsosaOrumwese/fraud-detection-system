"""Attempt loop for the S4 Zero-Truncated Poisson sampler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxSubstream
from ..contexts import S4HyperParameters, S4MerchantTarget
from ..l0 import writer as l0_writer
from .lambda_regime import FrozenLambdaRegime

ExhaustionPolicy = Literal["abort", "downgrade_domestic"]

A_ZERO_REASON = "no_admissible"


@dataclass(frozen=True)
class SamplerOutcome:
    """Summary of the S4 ZTP sampler for one merchant."""

    merchant_id: int
    lambda_extra: float
    regime: str
    attempts: int
    rejections: int
    k_target: int | None
    exhausted: bool
    policy: ExhaustionPolicy
    reason: str | None


def run_sampler(
    *,
    merchant: S4MerchantTarget,
    lambda_regime: FrozenLambdaRegime,
    hyperparams: S4HyperParameters,
    admissible_foreign_count: int,
    poisson_substream: PhiloxSubstream,
    writer: l0_writer.ZTPEventWriter,
) -> SamplerOutcome:
    """Run the ZTP sampler for a merchant and emit RNG logs."""

    policy = hyperparams.exhaustion_policy
    if policy not in {"abort", "downgrade_domestic"}:
        raise err(
            "ERR_S4_POLICY_INVALID",
            f"unsupported exhaustion policy '{policy}'",
        )

    max_attempts = int(hyperparams.max_zero_attempts)
    if max_attempts <= 0:
        raise err(
            "ERR_S4_POLICY_INVALID",
            f"max_zero_attempts must be positive (got {max_attempts})",
        )

    # Short-circuit when no admissible foreign countries exist.
    if admissible_foreign_count == 0:
        state = poisson_substream.snapshot()
        writer.write_ztp_final(
            merchant_id=merchant.merchant_id,
            counter_before=state,
            counter_after=state,
            blocks_used=0,
            lambda_extra=lambda_regime.lambda_extra,
            k_target=0,
            attempts=0,
            regime=lambda_regime.regime,
            exhausted=False,
            reason=A_ZERO_REASON,
        )
        return SamplerOutcome(
            merchant_id=merchant.merchant_id,
            lambda_extra=lambda_regime.lambda_extra,
            regime=lambda_regime.regime,
            attempts=0,
            rejections=0,
            k_target=0,
            exhausted=False,
            policy=policy,
            reason=A_ZERO_REASON,
        )

    if admissible_foreign_count < 0:
        raise err(
            "ERR_S4_BRANCH_PURITY",
            f"admissible foreign count cannot be negative (A={admissible_foreign_count})",
        )

    attempts = 0
    rejections = 0

    while attempts < max_attempts:
        attempts += 1
        before_state = poisson_substream.snapshot()
        blocks_before = poisson_substream.blocks
        draws_before = poisson_substream.draws
        k_value = int(poisson_substream.poisson(lambda_regime.lambda_extra))
        after_state = poisson_substream.snapshot()
        blocks_used = int(poisson_substream.blocks - blocks_before)
        draws_used = int(poisson_substream.draws - draws_before)

        writer.write_poisson_attempt(
            merchant_id=merchant.merchant_id,
            attempt_index=attempts,
            counter_before=before_state,
            counter_after=after_state,
            blocks_used=blocks_used,
            draws_used=draws_used,
            lam=lambda_regime.lambda_extra,
            k=k_value,
        )

        if k_value > 0:
            writer.write_ztp_final(
                merchant_id=merchant.merchant_id,
                counter_before=after_state,
                counter_after=after_state,
                blocks_used=0,
                lambda_extra=lambda_regime.lambda_extra,
                k_target=k_value,
                attempts=attempts,
                regime=lambda_regime.regime,
                exhausted=False,
            )
            return SamplerOutcome(
                merchant_id=merchant.merchant_id,
                lambda_extra=lambda_regime.lambda_extra,
                regime=lambda_regime.regime,
                attempts=attempts,
                rejections=rejections,
                k_target=k_value,
                exhausted=False,
                policy=policy,
                reason=None,
            )

        rejections += 1
        writer.write_ztp_rejection(
            merchant_id=merchant.merchant_id,
            attempt_index=attempts,
            counter_before=after_state,
            counter_after=after_state,
            blocks_used=0,
            lambda_extra=lambda_regime.lambda_extra,
        )

    # Cap reached without acceptance.
    final_state = poisson_substream.snapshot()
    if policy == "abort":
        writer.write_ztp_retry_exhausted(
            merchant_id=merchant.merchant_id,
            counter_before=final_state,
            counter_after=final_state,
            blocks_used=0,
            lambda_extra=lambda_regime.lambda_extra,
            attempts=max_attempts,
            aborted=True,
        )
        return SamplerOutcome(
            merchant_id=merchant.merchant_id,
            lambda_extra=lambda_regime.lambda_extra,
            regime=lambda_regime.regime,
            attempts=max_attempts,
            rejections=rejections,
            k_target=None,
            exhausted=True,
            policy=policy,
            reason=None,
        )

    writer.write_ztp_final(
        merchant_id=merchant.merchant_id,
        counter_before=final_state,
        counter_after=final_state,
        blocks_used=0,
        lambda_extra=lambda_regime.lambda_extra,
        k_target=0,
        attempts=max_attempts,
        regime=lambda_regime.regime,
        exhausted=True,
    )
    return SamplerOutcome(
        merchant_id=merchant.merchant_id,
        lambda_extra=lambda_regime.lambda_extra,
        regime=lambda_regime.regime,
        attempts=max_attempts,
        rejections=rejections,
        k_target=0,
        exhausted=True,
        policy=policy,
        reason=None,
    )


__all__ = ["SamplerOutcome", "run_sampler", "ExhaustionPolicy", "A_ZERO_REASON"]
