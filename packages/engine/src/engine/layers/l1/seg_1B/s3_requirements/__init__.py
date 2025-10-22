"""Segment 1B State-3 (site requirements) public exports."""

from .exceptions import S3Error, err
from .l2.aggregate import AggregationResult, compute_requirements
from .l2.config import RunnerConfig
from .l2.materialise import S3RunResult, materialise_requirements
from .l2.prepare import PreparedInputs, S3RequirementsRunner, prepare_inputs
from .l3 import S3RequirementsValidator, ValidatorConfig as _S3ValidatorConfig, build_run_report

S3ValidatorConfig = _S3ValidatorConfig

__all__ = [
    "AggregationResult",
    "PreparedInputs",
    "RunnerConfig",
    "S3RunResult",
    "S3Error",
    "S3RequirementsRunner",
    "S3RequirementsValidator",
    "S3ValidatorConfig",
    "build_run_report",
    "compute_requirements",
    "materialise_requirements",
    "err",
    "prepare_inputs",
]

