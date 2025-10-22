"""Segment 1B package exports."""

from .s0_gate.l2.runner import S0GateRunner, GateInputs, GateResult
from .s1_tile_index import (
    InclusionRule,
    RunnerConfig as S1RunnerConfig,
    S1RunResult,
    S1TileIndexRunner,
    S1TileIndexValidator,
    ValidatorConfig as S1ValidatorConfig,
)
from .s2_tile_weights import (
    MassComputation,
    PatCounters,
    PreparedInputs,
    RunnerConfig as S2RunnerConfig,
    S2Error,
    S2RunResult,
    S2TileWeightsRunner,
    S2TileWeightsValidator,
    ValidatorConfig as S2ValidatorConfig,
)

__all__ = [
    "S0GateRunner",
    "GateInputs",
    "GateResult",
    "InclusionRule",
    "S1RunnerConfig",
    "S1RunResult",
    "S1TileIndexRunner",
    "S1TileIndexValidator",
    "S1ValidatorConfig",
    "MassComputation",
    "PatCounters",
    "PreparedInputs",
    "S2RunnerConfig",
    "S2RunResult",
    "S2TileWeightsRunner",
    "S2TileWeightsValidator",
    "S2ValidatorConfig",
    "S2Error",
]
