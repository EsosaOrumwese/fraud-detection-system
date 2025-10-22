"""Segment 1B — State 2 (Tile Weights) public surface."""

from .exceptions import S2Error
from .l2.runner import (
    GovernedParameters,
    MassComputation,
    QuantisationResult,
    PatCounters,
    PreparedInputs,
    RunnerConfig,
    S2TileWeightsRunner,
)

__all__ = [
    "GovernedParameters",
    "MassComputation",
    "QuantisationResult",
    "PatCounters",
    "PreparedInputs",
    "RunnerConfig",
    "S2Error",
    "S2TileWeightsRunner",
]
