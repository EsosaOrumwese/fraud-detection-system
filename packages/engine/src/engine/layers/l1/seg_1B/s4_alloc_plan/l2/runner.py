"""Runner for Segment 1B State-4 allocation plan."""

from __future__ import annotations

import logging
from typing import Mapping, Optional

from .aggregate import AggregationContext, build_allocation
from .config import RunnerConfig
from .materialise import S4RunResult, materialise_allocation
from ...shared.dictionary import load_dictionary, resolve_dataset_path
import json
import time
from .prepare import PreparedInputs, prepare_inputs


class S4AllocPlanRunner:
    """High-level orchestration for the S4 allocation plan."""

    def run(
        self,
        config: RunnerConfig,
        *,
        dictionary: Optional[Mapping[str, object]] = None,
    ) -> S4RunResult:
        if dictionary is not None:
            config = RunnerConfig(
                data_root=config.data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
            )
        try:
            prepared = prepare_inputs(config)
            logger = logging.getLogger(__name__)
            logger.info(
                "S4: prepared inputs (requirements_rows=%d, dp=%d, workers=%d)",
                prepared.requirements.frame.height,
                prepared.tile_weights.dp,
                prepared.config.workers,
            )
            context = AggregationContext(
                requirements=prepared.requirements,
                tile_weights=prepared.tile_weights,
                tile_index=prepared.tile_index,
                iso_table=prepared.iso_table,
                dp=prepared.tile_weights.dp,
                workers=prepared.config.workers,
            )
            allocation = build_allocation(context)
            logger.info(
                "S4: allocation context complete (rows_emitted=%d, merchants=%d, pairs=%d, shortfall=%d)",
                allocation.rows_emitted,
                allocation.merchants_total,
                allocation.pairs_total,
                allocation.shortfall_total,
            )
        except Exception as exc:
            _emit_failure_event_from_config(config=config, dictionary=config.dictionary, failure=exc)
            raise
        return materialise_allocation(
            prepared=prepared,
            allocation=allocation,
            iso_version=prepared.iso_version,
        )


def _emit_failure_event_from_config(
    *,
    config: RunnerConfig,
    dictionary: Mapping[str, object] | None,
    failure: Exception,
) -> None:
    dictionary = dictionary or load_dictionary()
    try:
        event_path = resolve_dataset_path(
            "s4_failure_event",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
    except Exception:
        return
    event_path.parent.mkdir(parents=True, exist_ok=True)
    code = getattr(getattr(failure, "context", None), "code", None)
    payload = {
        "event": "S4_ERROR",
        "code": code if isinstance(code, str) else "E410_NONDETERMINISTIC_OUTPUT",
        "at": _utc_now_rfc3339_micros(),
        "seed": str(config.seed),
        "manifest_fingerprint": config.manifest_fingerprint,
        "parameter_hash": config.parameter_hash,
    }
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _utc_now_rfc3339_micros() -> str:
    now = time.time()
    seconds = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(now))
    micros = int((now % 1) * 1_000_000)
    return f"{seconds}{micros:06d}Z"


__all__ = ["S4AllocPlanRunner"]
