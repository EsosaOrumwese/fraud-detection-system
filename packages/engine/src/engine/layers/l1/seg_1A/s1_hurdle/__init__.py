"""Public surface for Layer-1 Segment 1A state-1 hurdle logic."""

from .l1.probability import HurdleProbability, hurdle_probability
from .l1.rng import (
    HURDLE_MODULE_NAME,
    HURDLE_SUBSTREAM_LABEL,
    counters,
    derive_hurdle_substream,
)
from .l2.runner import HurdleDecision, HurdleDesignRow, S1HurdleRunner, S1RunResult

__all__ = [
    "HURDLE_MODULE_NAME",
    "HURDLE_SUBSTREAM_LABEL",
    "HurdleDecision",
    "HurdleDesignRow",
    "HurdleProbability",
    "S1HurdleRunner",
    "S1RunResult",
    "counters",
    "derive_hurdle_substream",
    "hurdle_probability",
]
