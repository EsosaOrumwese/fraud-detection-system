"""Public surface for Layer-1 Segment 1A state-0 foundations.

This package is intentionally small: it re-exports the core builders,
orchestrators, and validation helpers so that higher layers (CLI, tests,
future pipelines) can import a concise API without needing to understand the
folder layout under ``l0``/``l1``/``l2``/``l3``.  Keeping these exports explicit
also provides a single place for future reviewers to confirm what “state-0”
actually exposes to the rest of the engine.
"""

from .l1.context import MerchantUniverse, RunContext, SchemaAuthority, SchemaRef
from .l1.merchants import build_run_context
from .l1.hashing import (
    compute_manifest_fingerprint,
    compute_parameter_hash,
    compute_run_id,
    ManifestFingerprintResult,
    ParameterHashResult,
    normalise_git_commit,
)
from .l1.design import (
    DesignDictionaries,
    HurdleCoefficients,
    DispersionCoefficients,
    DesignVectors,
    iter_design_vectors,
    design_dataframe,
    load_hurdle_coefficients,
    load_dispersion_coefficients,
)
from .l1.eligibility import (
    CrossborderEligibility,
    load_crossborder_eligibility,
    evaluate_eligibility,
)
from .l1.diagnostics import build_hurdle_diagnostics
from .l1.numeric import (
    load_numeric_policy,
    load_math_profile_manifest,
    build_numeric_policy_attestation,
)
from .l1.rng import (
    PhiloxEngine,
    PhiloxState,
    PhiloxSubstream,
    comp_u64,
    comp_iso,
    comp_index,
)
from .l2.failure import emit_failure_record
from .l2.output import S0Outputs, write_outputs
from .l2.runner import S0FoundationsRunner, SealedFoundations, S0RunResult
from .l2.rng_logging import RNGLogWriter, rng_event
from .l3.validator import validate_outputs

__all__ = [
    "MerchantUniverse",
    "RunContext",
    "SchemaAuthority",
    "SchemaRef",
    "build_run_context",
    "compute_parameter_hash",
    "ParameterHashResult",
    "compute_manifest_fingerprint",
    "ManifestFingerprintResult",
    "compute_run_id",
    "normalise_git_commit",
    "DesignDictionaries",
    "HurdleCoefficients",
    "DispersionCoefficients",
    "DesignVectors",
    "iter_design_vectors",
    "design_dataframe",
    "load_hurdle_coefficients",
    "load_dispersion_coefficients",
    "load_numeric_policy",
    "load_math_profile_manifest",
    "build_numeric_policy_attestation",
    "CrossborderEligibility",
    "load_crossborder_eligibility",
    "evaluate_eligibility",
    "build_hurdle_diagnostics",
    "PhiloxEngine",
    "PhiloxState",
    "PhiloxSubstream",
    "comp_u64",
    "comp_iso",
    "comp_index",
    "S0Outputs",
    "write_outputs",
    "RNGLogWriter",
    "rng_event",
    "emit_failure_record",
    "validate_outputs",
    "S0FoundationsRunner",
    "SealedFoundations",
    "S0RunResult",
]
