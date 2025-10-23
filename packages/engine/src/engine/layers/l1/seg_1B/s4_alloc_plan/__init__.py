"""Segment 1B State-4 (allocation plan) exports."""

from .exceptions import S4Error, err
from .l1 import AllocationResult, allocate_sites
from .l2 import (
    AggregationContext,
    PreparedInputs,
    RunnerConfig,
    S4AllocPlanRunner,
    S4RunResult,
    build_allocation,
    materialise_allocation,
    prepare_inputs,
)
from .l3 import S4AllocPlanValidator, ValidatorConfig, build_run_report

__all__ = [
    "AggregationContext",
    "AllocationResult",
    "PreparedInputs",
    "RunnerConfig",
    "S4AllocPlanRunner",
    "S4AllocPlanValidator",
    "S4Error",
    "S4RunResult",
    "ValidatorConfig",
    "allocate_sites",
    "build_allocation",
    "build_run_report",
    "err",
    "materialise_allocation",
    "prepare_inputs",
]

