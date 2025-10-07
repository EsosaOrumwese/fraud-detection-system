"""Custom exceptions and failure taxonomy for S0 foundations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Tuple


class FailureCategory(Enum):
    """High-level failure buckets taken from §S0.9."""

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
    "E_AUTHORITY_BREACH": (FailureCategory.F6_AUTHORITY, "non_authoritative_schema_ref"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Carries structured context for an S0 error."""

    code: str
    detail: str

    def as_message(self) -> str:
        return f"{self.code}: {self.detail}"

    @property
    def failure_category(self) -> FailureCategory:
        return _FAILURE_CODE_MAP.get(self.code, (FailureCategory.F8_VALIDATION, self.code))[0]

    @property
    def failure_code(self) -> str:
        return _FAILURE_CODE_MAP.get(self.code, (FailureCategory.F8_VALIDATION, self.code))[1]


class S0Error(RuntimeError):
    """Base runtime error for S0 that preserves the canonical code."""

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
