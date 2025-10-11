"""Orchestrator for the S4 Zero-Truncated Poisson target sampler."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxEngine
from ..contexts import S4DeterministicContext, S4MerchantTarget
from ..l0 import writer as l0_writer
from ..l1 import (
    SamplerOutcome,
    compute_lambda_regime,
    derive_poisson_substream,
    run_sampler,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZTPFinalRecord:
    """Accepted outcome (or exhaustion marker) for a merchant."""

    merchant_id: int
    lambda_extra: float
    regime: str
    attempts: int
    rejections: int
    k_target: int | None
    exhausted: bool
    policy: str
    reason: str | None


@dataclass(frozen=True)
class S4RunResult:
    """Artifacts produced by the S4 sampler."""

    deterministic: S4DeterministicContext
    finals: Tuple[ZTPFinalRecord, ...]
    poisson_events_path: Path
    rejection_events_path: Path
    retry_exhausted_events_path: Path
    final_events_path: Path
    trace_path: Path


class S4ZTPTargetRunner:
    """Drive the S4 attempt loop for all eligible merchants."""

    def run(
        self,
        *,
        base_path: Path,
        deterministic: S4DeterministicContext,
    ) -> S4RunResult:
        base_path = base_path.expanduser().resolve()
        engine = PhiloxEngine(
            seed=deterministic.seed,
            manifest_fingerprint=deterministic.manifest_fingerprint,
        )
        writer = l0_writer.ZTPEventWriter(
            base_path=base_path,
            seed=deterministic.seed,
            parameter_hash=deterministic.parameter_hash,
            manifest_fingerprint=deterministic.manifest_fingerprint,
            run_id=deterministic.run_id,
        )

        start_perf = time.perf_counter()
        last_checkpoint = start_perf

        def log_progress(message: str) -> None:
            nonlocal last_checkpoint
            now = time.perf_counter()
            total = now - start_perf
            delta = now - last_checkpoint
            logger.info("S4: %s (elapsed=%.2fs, delta=%.2fs)", message, total, delta)
            last_checkpoint = now

        log_progress(f"run initialised (merchants={len(deterministic.merchants)})")

        finals: list[ZTPFinalRecord] = []
        for merchant in deterministic.merchants:
            if not _merchant_in_scope(merchant):
                continue

            lambda_regime = compute_lambda_regime(
                hyperparams=deterministic.hyperparams,
                n_outlets=merchant.n_outlets,
                feature_value=merchant.feature_value,
            )
            poisson_substream = derive_poisson_substream(
                engine, merchant_id=merchant.merchant_id
            )

            outcome = run_sampler(
                merchant=merchant,
                lambda_regime=lambda_regime,
                hyperparams=deterministic.hyperparams,
                admissible_foreign_count=merchant.admissible_foreign_count,
                poisson_substream=poisson_substream,
                writer=writer,
            )
            finals.append(
                ZTPFinalRecord(
                    merchant_id=outcome.merchant_id,
                    lambda_extra=outcome.lambda_extra,
                    regime=outcome.regime,
                    attempts=outcome.attempts,
                    rejections=outcome.rejections,
                    k_target=outcome.k_target,
                    exhausted=outcome.exhausted,
                    policy=outcome.policy,
                    reason=outcome.reason,
                )
            )

        log_progress(f"emitted s4 events (processed_merchants={len(finals)})")
        log_progress("completed run")

        return S4RunResult(
            deterministic=deterministic,
            finals=tuple(finals),
            poisson_events_path=writer.poisson_events_path,
            rejection_events_path=writer.rejection_events_path,
            retry_exhausted_events_path=writer.retry_exhausted_events_path,
            final_events_path=writer.final_events_path,
            trace_path=writer.trace_path,
        )


def _merchant_in_scope(merchant: S4MerchantTarget) -> bool:
    """Ensure the merchant satisfies branch purity gates."""

    if not merchant.is_multi or not merchant.is_eligible:
        return False
    if merchant.n_outlets < 2:
        raise err(
            "ERR_S4_BRANCH_PURITY",
            f"S4 received merchant {merchant.merchant_id} with n_outlets={merchant.n_outlets}",
        )
    return True


__all__ = ["S4RunResult", "S4ZTPTargetRunner", "ZTPFinalRecord"]
