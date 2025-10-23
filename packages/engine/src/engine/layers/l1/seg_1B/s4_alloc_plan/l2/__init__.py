"""L2 orchestration for Segment 1B State-4."""

from .aggregate import AggregationContext, build_allocation
from .config import RunnerConfig
from .materialise import S4RunResult, materialise_allocation
from .prepare import PreparedInputs, prepare_inputs
from .runner import S4AllocPlanRunner

__all__ = [
    "AggregationContext",
    "RunnerConfig",
    "S4RunResult",
    "PreparedInputs",
    "S4AllocPlanRunner",
    "build_allocation",
    "materialise_allocation",
    "prepare_inputs",
]

