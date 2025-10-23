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
