"""Custom exceptions and failure taxonomy used across S0 foundations.

The end-state design requires that every failure bubble up with a stable
category/code pair so that validation bundles, monitoring and downstream
pipelines can react deterministically.  This module centralises that mapping
and exposes a tiny ``S0Error`` wrapper which preserves the canonical failure
context while still behaving like a normal ``RuntimeError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Tuple


class FailureCategory(Enum):
    """High-level failure buckets defined in the S0.9 specification.

    The names mirror the language in the design document so that validation
    dashboards and documentation stay in sync.  We intentionally keep the Enum
    small and immutable rather than deriving it dynamically from the mapping
    below; that way reviewers can audit the allowed categories at a glance.
    """

    F1_INGRESS = "ingress_schema_violation"
    F2_PARAMETERS = "param_file_missing"
    F3_NUMERIC = "hurdle_nonfinite"
    F4_RNG = "rng_envelope_violation"
    F5_PARTITION = "partition_mismatch"
    F6_AUTHORITY = "non_authoritative_schema_ref"
    F7_NUMERIC_POLICY = "numeric_rounding_mode"
    F8_VALIDATION = "validation_bundle_error"
    F9_IO = "io_write_failure"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E_INGRESS_SCHEMA": (FailureCategory.F1_INGRESS, "ingress_schema_violation"),
    "E_CHANNEL_VALUE": (FailureCategory.F1_INGRESS, "ingress_channel_symbol"),
    "E_FK_HOME_ISO": (FailureCategory.F1_INGRESS, "ingress_iso_fk"),
    "E_PARAM_MISSING": (FailureCategory.F2_PARAMETERS, "param_file_missing"),
    "E_PARAM_EMPTY": (FailureCategory.F2_PARAMETERS, "param_file_missing"),
    "E_PARAM_NONASCII_NAME": (FailureCategory.F2_PARAMETERS, "param_non_ascii"),
    "E_PARAM_HASH_ABSENT": (FailureCategory.F2_PARAMETERS, "param_hash_absent"),
    "E_PI_NAN_OR_INF": (FailureCategory.F3_NUMERIC, "hurdle_nonfinite"),
    "E_GDP_NONPOS": (FailureCategory.F3_NUMERIC, "gdp_non_positive"),
    "E_ELIG_RULE_BAD_CHANNEL": (FailureCategory.F3_NUMERIC, "eligibility_rule_error"),
    "E_ELIG_RULE_BAD_ISO": (FailureCategory.F3_NUMERIC, "eligibility_rule_error"),
    "E_ELIG_RULE_BAD_MCC": (FailureCategory.F3_NUMERIC, "eligibility_rule_error"),
    "E_AUTHORITY_BREACH": (
        FailureCategory.F6_AUTHORITY,
        "non_authoritative_schema_ref",
    ),
    "E_SCHEMA_NOT_FOUND": (FailureCategory.F6_AUTHORITY, "schema_not_found"),
    "E_SCHEMA_FORMAT": (FailureCategory.F6_AUTHORITY, "schema_invalid_json"),
    "E_SCHEMA_POINTER": (FailureCategory.F6_AUTHORITY, "schema_pointer_missing"),
    "E_PARTITION_COLUMN_MISSING": (
        FailureCategory.F5_PARTITION,
        "partition_column_missing",
    ),
    "E_RNG_BUDGET": (FailureCategory.F4_RNG, "rng_budget_violation"),
    "E_RNG_COUNTER": (FailureCategory.F4_RNG, "rng_counter_mismatch"),
    "E_PARTITION_MISMATCH": (FailureCategory.F5_PARTITION, "partition_mismatch"),
    "E_NUMERIC_POLICY_MISSING": (
        FailureCategory.F7_NUMERIC_POLICY,
        "numeric_policy_missing",
    ),
    "E_NUMERIC_POLICY_VALUE": (
        FailureCategory.F7_NUMERIC_POLICY,
        "numeric_policy_value",
    ),
    "E_GOVERNANCE_MISSING": (
        FailureCategory.F2_PARAMETERS,
        "governance_artifact_missing",
    ),
    "E_JSON_STRUCTURE": (FailureCategory.F6_AUTHORITY, "json_structure_invalid"),
    "E_MATH_PROFILE_MISSING": (
        FailureCategory.F7_NUMERIC_POLICY,
        "math_profile_missing",
    ),
    "E_MATH_PROFILE_FUNCTIONS": (
        FailureCategory.F7_NUMERIC_POLICY,
        "math_profile_functions",
    ),
    "E_MATH_PROFILE_ARTIFACTS": (
        FailureCategory.F7_NUMERIC_POLICY,
        "math_profile_artifacts",
    ),
    "E_RUNID_COLLISION_EXHAUSTED": (
        FailureCategory.F2_PARAMETERS,
        "runid_collision_exhausted",
    ),
    "E_INPUT_SCHEMA": (
        FailureCategory.F1_INGRESS,
        "s5_input_schema_violation",
    ),
    "E_INPUT_SUM": (
        FailureCategory.F1_INGRESS,
        "s5_input_sum_violation",
    ),
    "E_POLICY_DOMAIN": (
        FailureCategory.F2_PARAMETERS,
        "s5_policy_domain",
    ),
    "E_PARTITION_EXISTS": (
        FailureCategory.F5_PARTITION,
        "s5_partition_exists",
    ),
    "E_MCURR_CARDINALITY": (
        FailureCategory.F1_INGRESS,
        "s5_merchant_currency_cardinality",
    ),
    "E_MCURR_RESOLUTION": (
        FailureCategory.F1_INGRESS,
        "s5_merchant_currency_resolution",
    ),
    "E_VALIDATION_MISMATCH": (FailureCategory.F8_VALIDATION, "validation_mismatch"),
    "E_VALIDATION_DIGEST": (
        FailureCategory.F8_VALIDATION,
        "validation_digest_mismatch",
    ),
    "E_VALIDATION_SCHEMA": (
        FailureCategory.F8_VALIDATION,
        "validation_schema_mismatch",
    ),
    "E_VALIDATION_NUMERIC": (
        FailureCategory.F7_NUMERIC_POLICY,
        "numeric_policy_value",
    ),
    "E_DATASET_NOT_FOUND": (FailureCategory.F9_IO, "dataset_missing"),
    "E_DATASET_EMPTY": (FailureCategory.F9_IO, "dataset_empty"),
    "E_DATASET_IO": (FailureCategory.F9_IO, "dataset_read_failure"),
    "E_PARAM_IO": (FailureCategory.F2_PARAMETERS, "param_file_missing"),
    "E_YAML_ROOT": (FailureCategory.F2_PARAMETERS, "yaml_root_not_mapping"),
    "ERR_S2_CORRIDOR_POLICY_MISSING": (
        FailureCategory.F8_VALIDATION,
        "s2_corridor_policy_missing",
    ),
    "ERR_S2_CORRIDOR_EMPTY": (
        FailureCategory.F8_VALIDATION,
        "s2_corridor_empty",
    ),
    "ERR_S2_CORRIDOR_BREACH": (
        FailureCategory.F8_VALIDATION,
        "s2_corridor_breach",
    ),
    "ERR_S3_AUTHORITY_MISSING": (
        FailureCategory.F6_AUTHORITY,
        "s3_authority_missing",
    ),
    "ERR_S3_PRECONDITION": (
        FailureCategory.F8_VALIDATION,
        "s3_precondition",
    ),
    "ERR_S3_PARTITION_MISMATCH": (
        FailureCategory.F5_PARTITION,
        "s3_partition_mismatch",
    ),
    "ERR_S3_VOCAB_INVALID": (
        FailureCategory.F1_INGRESS,
        "s3_vocab_invalid",
    ),
    "ERR_S3_RULE_LADDER_INVALID": (
        FailureCategory.F6_AUTHORITY,
        "s3_rule_ladder_invalid",
    ),
    "ERR_S3_SCHEMA_VALIDATION": (
        FailureCategory.F8_VALIDATION,
        "s3_schema_validation",
    ),
    "ERR_S3_PRIOR_DISABLED": (
        FailureCategory.F8_VALIDATION,
        "s3_prior_disabled",
    ),
    "ERR_S4_BRANCH_PURITY": (
        FailureCategory.F8_VALIDATION,
        "s4_branch_purity",
    ),
    "ERR_S4_FEATURE_DOMAIN": (
        FailureCategory.F3_NUMERIC,
        "s4_feature_domain",
    ),
    "ERR_S4_NUMERIC_INVALID": (
        FailureCategory.F3_NUMERIC,
        "s4_numeric_invalid",
    ),
    "ERR_S4_POLICY_INVALID": (
        FailureCategory.F2_PARAMETERS,
        "s4_policy_invalid",
    ),
    "ERR_S4_PARTIAL_RESUME": (
        FailureCategory.F8_VALIDATION,
        "s4_partial_resume",
    ),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S0 failure.

    ``code`` refers to the local ``E_*`` identifier raised by the code; the
    helper properties map that identifier onto the formal failure taxonomy so
    that callers can emit a single, well-formed JSON record.
    """

    code: str
    detail: str

    def as_message(self) -> str:
        return f"{self.code}: {self.detail}"

    @property
    def failure_category(self) -> FailureCategory:
        return _FAILURE_CODE_MAP.get(
            self.code, (FailureCategory.F8_VALIDATION, self.code)
        )[0]

    @property
    def failure_code(self) -> str:
        return _FAILURE_CODE_MAP.get(
            self.code, (FailureCategory.F8_VALIDATION, self.code)
        )[1]


class S0Error(RuntimeError):
    """Base runtime error that preserves the canonical failure context."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(context.as_message())
        self.context = context

    def failure_record(self) -> Dict[str, str]:
        return {
            "code": self.context.code,
            "detail": self.context.detail,
            "failure_category": self.context.failure_category.value,
            "failure_code": self.context.failure_code,
        }


def err(code: str, detail: str) -> S0Error:
    """Utility to build an :class:`S0Error` with minimal ceremony."""

    return S0Error(ErrorContext(code=code, detail=detail))


__all__ = ["ErrorContext", "S0Error", "err", "FailureCategory"]
