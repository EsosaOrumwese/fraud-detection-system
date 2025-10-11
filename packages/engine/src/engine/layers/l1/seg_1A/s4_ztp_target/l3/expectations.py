"""Validator contracts for S4 (scaffolding).

This module centralises the dataset/schema anchors and the failure vocabulary
the eventual validator will enforce. Keeping this separate makes it easier to
unit-test and to reason about future additive fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ..l0 import constants as c


@dataclass(frozen=True)
class StreamContract:
    """Dataset + schema binding plus whether the stream should consume RNG."""

    dataset_id: str
    schema_ref: str
    consuming: bool
    description: str


def stream_contracts() -> Tuple[StreamContract, ...]:
    """Return the expected RNG streams for S4."""

    return (
        StreamContract(
            dataset_id="rng_event_poisson_component",
            schema_ref="schemas.layer1.yaml#/rng/events/poisson_component",
            consuming=True,
            description="Consuming Poisson attempts (context='ztp').",
        ),
        StreamContract(
            dataset_id="rng_event_ztp_rejection",
            schema_ref="schemas.layer1.yaml#/rng/events/ztp_rejection",
            consuming=False,
            description="Non-consuming rejection markers following zero attempts.",
        ),
        StreamContract(
            dataset_id="rng_event_ztp_retry_exhausted",
            schema_ref="schemas.layer1.yaml#/rng/events/ztp_retry_exhausted",
            consuming=False,
            description="Non-consuming cap markers when policy='abort'.",
        ),
        StreamContract(
            dataset_id="rng_event_ztp_final",
            schema_ref="schemas.layer1.yaml#/rng/events/ztp_final",
            consuming=False,
            description="Non-consuming finaliser fixing K_target.",
        ),
        StreamContract(
            dataset_id="rng_trace_log",
            schema_ref="schemas.layer1.yaml#/rng/core/rng_trace_log",
            consuming=False,
            description="Cumulative trace for module/substream.",
        ),
    )


FAILURE_CODES = {
    "ERR_S4_BRANCH_PURITY",
    "ERR_S4_FEATURE_DOMAIN",
    "ERR_S4_NUMERIC_INVALID",
    "ERR_S4_POLICY_INVALID",
    "NUMERIC_INVALID",  # merchant-scoped failure vocabulary (values-only records)
    "BRANCH_PURITY",
    "A_ZERO_MISSHANDLED",
    "ATTEMPT_GAPS",
    "FINAL_MISSING",
    "MULTIPLE_FINAL",
    "CAP_WITH_FINAL_ABORT",
    "TRACE_MISSING",
    "REGIME_INVALID",
    "RNG_ACCOUNTING",
}
"""Failure codes (producer + validator) the L3 layer must recognise."""


__all__ = ["FAILURE_CODES", "StreamContract", "stream_contracts"]
