"""Segment 1B State-4 (allocation plan) exports."""

from .exceptions import S4Error, err
from .l1 import (
    AllocationCountryResult,
    AllocationResult,
    allocate_country_sites,
    merge_merchant_summaries,
    serialise_merchant_summaries,
)
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

# Backwards compatibility alias
allocate_sites = allocate_country_sites

__all__ = [
    "AggregationContext",
    "AllocationCountryResult",
    "AllocationResult",
    "PreparedInputs",
    "RunnerConfig",
    "S4AllocPlanRunner",
    "S4AllocPlanValidator",
    "S4Error",
    "S4RunResult",
    "ValidatorConfig",
    "allocate_country_sites",
    "allocate_sites",
    "merge_merchant_summaries",
    "serialise_merchant_summaries",
    "build_allocation",
    "build_run_report",
    "err",
    "materialise_allocation",
    "prepare_inputs",
]

