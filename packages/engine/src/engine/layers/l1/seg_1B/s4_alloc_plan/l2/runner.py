"""Runner for Segment 1B State-4 allocation plan."""

from __future__ import annotations

import logging
from typing import Mapping, Optional

from .aggregate import AggregationContext, build_allocation
from .config import RunnerConfig
from .materialise import S4RunResult, materialise_allocation
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

        prepared = prepare_inputs(config)
        logger = logging.getLogger(__name__)
        logger.info(
            "S4: prepared inputs (requirements_rows=%d, dp=%d)",
            prepared.requirements.frame.height,
            prepared.tile_weights.dp,
        )
        context = AggregationContext(
            requirements=prepared.requirements,
            tile_weights=prepared.tile_weights,
            tile_index=prepared.tile_index,
            iso_table=prepared.iso_table,
            dp=prepared.tile_weights.dp,
        )
        allocation = build_allocation(context)
        logger.info(
            "S4: allocation context complete (rows_emitted=%d, merchants=%d, pairs=%d, shortfall=%d)",
            allocation.rows_emitted,
            allocation.merchants_total,
            allocation.pairs_total,
            allocation.shortfall_total,
        )
        return materialise_allocation(
            prepared=prepared,
            allocation=allocation,
            iso_version=prepared.iso_version,
        )


__all__ = ["S4AllocPlanRunner"]
