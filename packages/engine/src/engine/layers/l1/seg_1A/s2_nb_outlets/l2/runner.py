"""Stochastic runner for S2 negative binomial outlet counts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.rng import PhiloxEngine
from ..l1 import rng as nb_rng
from .deterministic import S2DeterministicContext
from .output import NBEventWriter


@dataclass(frozen=True)
class NBFinalRecord:
    """Accepted NB outlet count and associated replay metadata."""

    merchant_id: int
    mu: float
    phi: float
    n_outlets: int
    nb_rejections: int
    attempts: int


@dataclass(frozen=True)
class S2RunResult:
    """Return value for the S2 NB sampler."""

    deterministic: S2DeterministicContext
    finals: Tuple[NBFinalRecord, ...]
    gamma_events_path: Path
    poisson_events_path: Path
    final_events_path: Path
    trace_path: Path


class S2NegativeBinomialRunner:
    """Generate NB outlet counts for multi-site merchants."""

    def run(
        self,
        *,
        base_path: Path,
        deterministic: S2DeterministicContext,
    ) -> S2RunResult:
        base_path = base_path.expanduser().resolve()
        engine = PhiloxEngine(
            seed=deterministic.seed,
            manifest_fingerprint=deterministic.manifest_fingerprint,
        )
        writer = NBEventWriter(
            base_path=base_path / "logs" / "rng",
            seed=deterministic.seed,
            parameter_hash=deterministic.parameter_hash,
            manifest_fingerprint=deterministic.manifest_fingerprint,
            run_id=deterministic.run_id,
        )

        finals: list[NBFinalRecord] = []
        for row in deterministic.rows:
            gamma_substream = nb_rng.derive_gamma_substream(
                engine, merchant_id=row.merchant_id
            )
            poisson_substream = nb_rng.derive_poisson_substream(
                engine, merchant_id=row.merchant_id
            )
            final_substream = nb_rng.derive_final_substream(
                engine, merchant_id=row.merchant_id
            )

            rejection_count = 0
            attempts = 0
            accepted = False

            while not accepted:
                attempts += 1
                gamma_before = gamma_substream.snapshot()
                gamma_blocks_before = gamma_substream.blocks
                gamma_draws_before = gamma_substream.draws
                gamma_value = gamma_substream.gamma(row.links.phi)
                gamma_after = gamma_substream.snapshot()
                gamma_blocks_used = gamma_substream.blocks - gamma_blocks_before
                gamma_draws_used = gamma_substream.draws - gamma_draws_before

                writer.write_gamma_component(
                    merchant_id=row.merchant_id,
                    counter_before=gamma_before,
                    counter_after=gamma_after,
                    blocks_used=int(gamma_blocks_used),
                    draws_used=int(gamma_draws_used),
                    alpha=row.links.phi,
                    gamma_value=gamma_value,
                )

                lam = (row.links.mu / row.links.phi) * gamma_value
                if not (math.isfinite(lam) and lam > 0.0):
                    raise err(
                        "ERR_S2_NUMERIC_INVALID",
                        f"invalid Poisson mean for merchant {row.merchant_id}: lambda={lam!r}",
                    )

                poisson_before = poisson_substream.snapshot()
                poisson_blocks_before = poisson_substream.blocks
                poisson_draws_before = poisson_substream.draws
                k_value = poisson_substream.poisson(lam)
                poisson_after = poisson_substream.snapshot()
                poisson_blocks_used = poisson_substream.blocks - poisson_blocks_before
                poisson_draws_used = poisson_substream.draws - poisson_draws_before

                writer.write_poisson_component(
                    merchant_id=row.merchant_id,
                    attempt_index=attempts,
                    counter_before=poisson_before,
                    counter_after=poisson_after,
                    blocks_used=int(poisson_blocks_used),
                    draws_used=int(poisson_draws_used),
                    lam=lam,
                    k=int(k_value),
                )

                if k_value >= 2:
                    final_before = final_substream.snapshot()
                    final_after = final_substream.snapshot()
                    writer.write_final_event(
                        merchant_id=row.merchant_id,
                        counter_before=final_before,
                        counter_after=final_after,
                        mu=row.links.mu,
                        phi=row.links.phi,
                        n_outlets=int(k_value),
                        nb_rejections=rejection_count,
                    )
                    finals.append(
                        NBFinalRecord(
                            merchant_id=row.merchant_id,
                            mu=row.links.mu,
                            phi=row.links.phi,
                            n_outlets=int(k_value),
                            nb_rejections=rejection_count,
                            attempts=attempts,
                        )
                    )
                    accepted = True
                else:
                    rejection_count += 1

        return S2RunResult(
            deterministic=deterministic,
            finals=tuple(finals),
            gamma_events_path=writer.gamma_events_path,
            poisson_events_path=writer.poisson_events_path,
            final_events_path=writer.final_events_path,
            trace_path=writer.trace_path,
        )


__all__ = ["NBFinalRecord", "S2NegativeBinomialRunner", "S2RunResult"]
