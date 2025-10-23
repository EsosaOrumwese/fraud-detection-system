"""Failure taxonomy scaffolding for Segment 1B state-4 (allocation plan)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """Placeholder categories for S4 failures (refine during implementation)."""

    INPUT = "input_validation"
    ALLOCATION = "allocation_integrity"
    WRITER = "writer_hygiene"
    DETERMINISM = "determinism"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "S4_NOT_IMPLEMENTED": (FailureCategory.ALLOCATION, "state_not_implemented"),
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
