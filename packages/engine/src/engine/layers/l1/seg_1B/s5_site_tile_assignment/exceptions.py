"""Failure taxonomy scaffolding for Segment 1B state-5 (site→tile assignment)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """Failure categories carried by S5 errors."""

    INPUT = "input_validation"
    RNG = "rng_envelope"
    ASSIGNMENT = "assignment_integrity"
    WRITER = "writer_hygiene"
    INTERNAL = "internal"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E500_NOT_IMPLEMENTED": (FailureCategory.INTERNAL, "not_implemented"),
    "E501_ALLOC_PLAN_MISSING": (FailureCategory.INPUT, "alloc_plan_missing"),
    "E501_INVALID_SEED": (FailureCategory.INPUT, "invalid_seed"),
    "E408_COVERAGE_MISSING": (FailureCategory.INPUT, "coverage_missing"),
    "E301_NO_PASS_FLAG": (FailureCategory.INPUT, "gate_missing"),
    "E302_FK_COUNTRY": (FailureCategory.ASSIGNMENT, "fk_country_violation"),
    "E502_PK_DUPLICATE_SITE": (FailureCategory.ASSIGNMENT, "pk_duplicate_site"),
    "E503_TILE_QUOTA_MISMATCH": (FailureCategory.ASSIGNMENT, "tile_quota_mismatch"),
    "E504_SUM_TO_N_MISMATCH": (FailureCategory.ASSIGNMENT, "sum_to_n_mismatch"),
    "E505_TILE_NOT_IN_INDEX": (FailureCategory.INPUT, "tile_not_in_index"),
    "E507_RNG_EVENT_MISMATCH": (FailureCategory.RNG, "rng_event_mismatch"),
    "E508_TOKEN_MISMATCH": (FailureCategory.WRITER, "token_mismatch"),
    "E509_UNSORTED": (FailureCategory.WRITER, "unsorted_output"),
    "E506_SCHEMA_INVALID": (FailureCategory.WRITER, "schema_invalid"),
    "E506_SCHEMA_EXTRAS": (FailureCategory.WRITER, "schema_extras"),
    "E414_WEIGHT_TAMPER": (FailureCategory.ASSIGNMENT, "weight_tamper"),
    "E410_NONDETERMINISTIC_OUTPUT": (FailureCategory.WRITER, "determinism_receipt_mismatch"),
    "E515_RUN_REPORT_MISSING_FIELDS": (FailureCategory.WRITER, "run_report_missing_fields"),
    "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL": (
        FailureCategory.WRITER,
        "immutable_partition_conflict",
    ),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S5 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S5Error(RuntimeError):
    """Exception carrying the canonical S5 error context."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S5Error:
    """Build an ``S5Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S5 failure code '{code}' (taxonomy to be extended)")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S5Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S5Error", "err"]
