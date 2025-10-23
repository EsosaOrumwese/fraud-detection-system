"""Failure taxonomy scaffolding for Segment 1B state-4 (allocation plan)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """Failure categories carried by S4 errors."""

    INPUT = "input_validation"
    ALLOCATION = "allocation_integrity"
    WRITER = "writer_hygiene"
    DETERMINISM = "determinism"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E401_REQUIREMENTS_MISSING": (FailureCategory.INPUT, "requirements_missing"),
    "E402_WEIGHTS_MISSING": (FailureCategory.INPUT, "tile_weights_missing"),
    "E403_SHORTFALL_MISMATCH": (FailureCategory.ALLOCATION, "sum_to_n_violation"),
    "E404_TIE_BREAK": (FailureCategory.ALLOCATION, "tie_break_violation"),
    "E405_SCHEMA_INVALID": (FailureCategory.WRITER, "schema_conformance_failed"),
    "E406_SORT_INVALID": (FailureCategory.WRITER, "sort_order_violation"),
    "E407_PK_DUPLICATE": (FailureCategory.WRITER, "primary_key_violation"),
    "E408_COVERAGE_MISSING": (FailureCategory.INPUT, "tile_coverage_missing"),
    "E409_DETERMINISM": (FailureCategory.DETERMINISM, "determinism_violation"),
    "E410_TOKEN_MISMATCH": (FailureCategory.INPUT, "path_embed_mismatch"),
    "E411_IMMUTABLE_CONFLICT": (FailureCategory.WRITER, "immutable_conflict"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S4 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S4Error(RuntimeError):
    """Exception carrying the canonical S4 error context."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S4Error:
    """Build an ``S4Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S4 failure code '{code}' (taxonomy to be defined)")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S4Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S4Error", "err"]
