"""Custom exceptions for S0 foundations (Layer 1, Segment 1A).

These error identifiers mirror the normative abort codes defined in
`docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s0.expanded.md`.
Keeping the codes close to the spec makes it easy for downstream
validation to map raised errors back to the authoritative document.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorContext:
    """Carries structured context for an S0 error.

    The spec repeatedly calls for precise abort codes.  We expose the
    code and machine-readable details so orchestrators can surface rich
    diagnostics without having to parse free-form strings.
    """

    code: str
    detail: str

    def as_message(self) -> str:
        return f"{self.code}: {self.detail}"


class S0Error(RuntimeError):
    """Base runtime error for S0 that preserves the canonical code."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(context.as_message())
        self.context = context


def err(code: str, detail: str) -> S0Error:
    """Utility to build an :class:`S0Error` with minimal ceremony."""

    return S0Error(ErrorContext(code=code, detail=detail))


__all__ = ["ErrorContext", "S0Error", "err"]
