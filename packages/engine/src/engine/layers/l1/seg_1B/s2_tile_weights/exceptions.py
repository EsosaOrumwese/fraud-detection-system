"""Failure taxonomy for Segment 1B state-2 (tile weights)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """High-level buckets mirrored from the S2 specification."""

    INPUT = "input_validation"
    NORMALISATION = "normalisation"
    DETERMINISM = "determinism"
    WRITER = "writer_hygiene"
    PERFORMANCE = "performance_envelope"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E101_TILE_INDEX_MISSING": (FailureCategory.INPUT, "tile_index_missing_or_invalid"),
    "E102_FK_MISMATCH": (FailureCategory.INPUT, "foreign_key_mismatch"),
    "E103_ZERO_COUNTRY": (FailureCategory.NORMALISATION, "zero_country_universe"),
    "E104_ZERO_MASS": (FailureCategory.NORMALISATION, "zero_mass_no_fallback"),
    "E105_NORMALIZATION": (FailureCategory.NORMALISATION, "normalisation_violation"),
    "E106_MONOTONICITY": (FailureCategory.NORMALISATION, "monotonicity_violation"),
    "E107_DETERMINISM": (FailureCategory.DETERMINISM, "determinism_violation"),
    "E108_WRITER_HYGIENE": (FailureCategory.WRITER, "writer_hygiene_failure"),
    "E109_PERF_BUDGET": (FailureCategory.PERFORMANCE, "performance_budget_exceeded"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S2 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S2Error(RuntimeError):
    """Exception carrying the canonical S2 error context."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S2Error:
    """Build an ``S2Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S2 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S2Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S2Error", "err"]

