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
    PreparedInputs as S2PreparedInputs,
    RunnerConfig as S2RunnerConfig,
    S2Error,
    S2RunResult,
    S2TileWeightsRunner,
    S2TileWeightsValidator,
    ValidatorConfig as S2ValidatorConfig,
)
from .s3_requirements import (
    AggregationResult as S3AggregationResult,
    PreparedInputs as S3PreparedInputs,
    RunnerConfig as S3RunnerConfig,
    S3Error,
    S3RequirementsRunner,
    compute_requirements as s3_compute_requirements,
    prepare_inputs as s3_prepare_inputs,
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
    "S2PreparedInputs",
    "S2RunnerConfig",
    "S2RunResult",
    "S2TileWeightsRunner",
    "S2TileWeightsValidator",
    "S2ValidatorConfig",
    "S2ValidatorConfig",
    "S2Error",
    "S3AggregationResult",
    "S3PreparedInputs",
    "S3RunnerConfig",
    "S3RequirementsRunner",
    "S3Error",
    "s3_compute_requirements",
    "s3_prepare_inputs",
]
