"""State-0 foundations for Layer-1 Segment 1A."""

from .l1.context import MerchantUniverse, RunContext, SchemaAuthority
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

__all__ = [
    "MerchantUniverse",
    "RunContext",
    "SchemaAuthority",
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
]
