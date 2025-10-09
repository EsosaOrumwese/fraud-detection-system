"""Orchestration for S1 hurdle event emission."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.design import DesignVectors, iter_design_vectors
from ...s0_foundations.l1.rng import PhiloxEngine
from ...s0_foundations.l2.output import S0Outputs
from ...s0_foundations.l2.runner import SealedFoundations
from ..l1.probability import hurdle_probability
from ..l1.rng import counters, derive_hurdle_substream
from .output import HurdleEventWriter


@dataclass(frozen=True)
class HurdleDecision:
    """Deterministic replay bundle for a single merchant."""

    merchant_id: int
    eta: float
    pi: float
    deterministic: bool
    is_multi: bool
    u: float | None
    rng_counter_before: Tuple[int, int]
    rng_counter_after: Tuple[int, int]
    draws: int
    blocks: int


@dataclass(frozen=True)
class S1RunResult:
    """Summary of the S1 hurdle run."""

    seed: int
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    decisions: Tuple[HurdleDecision, ...]
    multi_merchant_ids: Tuple[int, ...]
    events_path: Path
    trace_path: Path


class S1HurdleRunner:
    """High-level orchestrator that emits the hurdle Bernoulli stream."""

    def run(
        self,
        *,
        base_path: Path,
        sealed: SealedFoundations,
        outputs: S0Outputs,
        seed: int,
        run_id: str,
    ) -> S1RunResult:
        parameter_hash = sealed.parameter_hash.parameter_hash
        manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint
        engine = PhiloxEngine(
            seed=seed,
            manifest_fingerprint=sealed.manifest_fingerprint.manifest_fingerprint_bytes,
        )
        writer = HurdleEventWriter(
            base_path=base_path / "logs" / "rng",
            seed=seed,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            run_id=run_id,
        )

        decisions: List[HurdleDecision] = []
        multi_ids: List[int] = []
        vectors = self._design_vectors(sealed, outputs)

        for vector in vectors:
            probability = hurdle_probability(
                coefficients=outputs.hurdle_coefficients.beta,
                design_vector=vector.x_hurdle,
            )
            substream = derive_hurdle_substream(
                engine,
                merchant_id=vector.merchant_id,
            )
            before_state = substream.snapshot()
            blocks_before = substream.blocks
            draws_before = substream.draws

            if probability.deterministic:
                u_value = None
                is_multi = probability.pi == 1.0
            else:
                u_value = substream.uniform()
                if not (0.0 < u_value < 1.0):
                    raise err(
                        "E_RNG_BUDGET",
                        f"uniform not in (0,1) for merchant {vector.merchant_id}",
                    )
                is_multi = u_value < probability.pi

            after_state = substream.snapshot()
            blocks = substream.blocks - blocks_before
            draws = substream.draws - draws_before

            writer.write_event(
                merchant_id=vector.merchant_id,
                pi=probability.pi,
                eta=probability.eta,
                deterministic=probability.deterministic,
                is_multi=is_multi,
                u_value=u_value,
                bucket_id=vector.bucket,
                counter_before=before_state,
                counter_after=after_state,
                draws=draws,
                blocks=blocks,
            )

            decision = HurdleDecision(
                merchant_id=vector.merchant_id,
                eta=probability.eta,
                pi=probability.pi,
                deterministic=probability.deterministic,
                is_multi=is_multi,
                u=u_value,
                rng_counter_before=counters(before_state),
                rng_counter_after=counters(after_state),
                draws=draws,
                blocks=blocks,
            )
            decisions.append(decision)
            if is_multi:
                multi_ids.append(vector.merchant_id)

        if not decisions:
            raise err("E_DATASET_EMPTY", "no hurdle design vectors available for S1")

        return S1RunResult(
            seed=seed,
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            decisions=tuple(decisions),
            multi_merchant_ids=tuple(multi_ids),
            events_path=writer.events_path,
            trace_path=writer.trace_path,
        )

    @staticmethod
    def _design_vectors(
        sealed: SealedFoundations,
        outputs: S0Outputs,
    ) -> Iterable[DesignVectors]:
        return iter_design_vectors(
            sealed.context,
            hurdle=outputs.hurdle_coefficients,
            dispersion=outputs.dispersion_coefficients,
        )


__all__ = ["HurdleDecision", "S1HurdleRunner", "S1RunResult"]
