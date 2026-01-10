"""Orchestration for S1 hurdle event emission."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence, Tuple

from ...s0_foundations.exceptions import S0Error, err
from ...s0_foundations.l1.design import DesignVectors
from ...s0_foundations.l1.rng import PhiloxEngine
from ...shared.dictionary import load_dictionary, resolve_rng_audit_path
from ..l1.probability import hurdle_probability
from ..l1.rng import HURDLE_MODULE_NAME, HURDLE_SUBSTREAM_LABEL, counters, derive_hurdle_substream
from ..l3.catalogue import GatedStream, load_gated_streams, write_hurdle_catalogue
from .output import HurdleEventWriter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HurdleDesignRow:
    """Minimal hurdle design row consumed by the S1 runner."""

    merchant_id: int
    bucket_id: int
    design_vector: Tuple[float, ...]


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
    gated_streams: Tuple[GatedStream, ...]
    catalogue_path: Path


class S1HurdleRunner:
    """High-level orchestrator that emits the hurdle Bernoulli stream."""

    @staticmethod
    def _log_progress(message: str, start_time: float, last_checkpoint: float) -> float:
        """Emit a deterministic progress log with cumulative and step timing."""

        now = time.perf_counter()
        total = now - start_time
        delta = now - last_checkpoint
        logger.info("S1: %s (elapsed=%.2fs, delta=%.2fs)", message, total, delta)
        return now

    def run(
        self,
        *,
        base_path: Path,
        manifest_fingerprint: str,
        parameter_hash: str,
        beta: Sequence[float],
        design_rows: Iterable[HurdleDesignRow],
        seed: int,
        run_id: str,
    ) -> S1RunResult:
        start_perf = time.perf_counter()
        last_checkpoint = start_perf
        last_checkpoint = self._log_progress("run initialised", start_perf, last_checkpoint)

        self._ensure_audit_exists(base_path, seed, parameter_hash, run_id)
        engine = PhiloxEngine(seed=seed, manifest_fingerprint=manifest_fingerprint)
        writer = HurdleEventWriter(
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            run_id=run_id,
        )

        last_checkpoint = self._log_progress("configured RNG writer", start_perf, last_checkpoint)

        decisions: List[HurdleDecision] = []
        multi_ids: List[int] = []
        seen_any = False

        for row in design_rows:
            seen_any = True
            probability = hurdle_probability(
                coefficients=beta,
                design_vector=row.design_vector,
            )
            substream = derive_hurdle_substream(
                engine,
                merchant_id=row.merchant_id,
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
                        f"uniform not in (0,1) for merchant {row.merchant_id}",
                    )
                is_multi = u_value < probability.pi

            after_state = substream.snapshot()
            blocks = substream.blocks - blocks_before
            draws = substream.draws - draws_before

            writer.write_event(
                merchant_id=row.merchant_id,
                pi=probability.pi,
                eta=probability.eta,
                deterministic=probability.deterministic,
                is_multi=is_multi,
                u_value=u_value,
                bucket_id=row.bucket_id,
                counter_before=before_state,
                counter_after=after_state,
                draws=draws,
                blocks=blocks,
            )

            decision = HurdleDecision(
                merchant_id=row.merchant_id,
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
                multi_ids.append(row.merchant_id)

        if not seen_any:
            raise err("E_DATASET_EMPTY", "no hurdle design rows available for S1")

        last_checkpoint = self._log_progress(
            f"emitted hurdle events (total={len(decisions)}, multi={len(multi_ids)})",
            start_perf,
            last_checkpoint,
        )

        try:
            gated_streams = load_gated_streams(gated_by=HURDLE_SUBSTREAM_LABEL)
        except S0Error:
            gated_streams = ()
        catalogue_path = write_hurdle_catalogue(
            base_path=base_path,
            parameter_hash=parameter_hash,
            module=HURDLE_MODULE_NAME,
            substream_label=HURDLE_SUBSTREAM_LABEL,
            multi_merchant_ids=multi_ids,
            gated_streams=gated_streams,
        )

        last_checkpoint = self._log_progress("wrote hurdle catalogue", start_perf, last_checkpoint)

        last_checkpoint = self._log_progress("completed run", start_perf, last_checkpoint)

        return S1RunResult(
            seed=seed,
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            decisions=tuple(decisions),
            multi_merchant_ids=tuple(multi_ids),
            events_path=writer.events_path,
            trace_path=writer.trace_path,
            gated_streams=gated_streams,
            catalogue_path=catalogue_path,
        )

    @staticmethod
    def from_design_vectors(vectors: Iterable[DesignVectors]) -> Iterator[HurdleDesignRow]:
        logger.info("S1: deriving design rows from sealed vectors")
        for vector in vectors:
            yield HurdleDesignRow(
                merchant_id=vector.merchant_id,
                bucket_id=vector.bucket,
                design_vector=tuple(vector.x_hurdle),
            )

    @staticmethod
    def _ensure_audit_exists(
        base_path: Path, seed: int, parameter_hash: str, run_id: str
    ) -> None:
        dictionary = load_dictionary()
        audit_path = resolve_rng_audit_path(
            base_path=base_path.resolve(),
            seed=seed,
            parameter_hash=parameter_hash,
            run_id=run_id,
            dictionary=dictionary,
        )
        if not audit_path.exists():
            raise err(
                "E_RNG_COUNTER",
                "rng audit log missing for hurdle run "
                f"(seed={seed}, parameter_hash={parameter_hash}, run_id={run_id})",
            )


__all__ = [
    "HurdleDecision",
    "HurdleDesignRow",
    "S1HurdleRunner",
    "S1RunResult",
]
