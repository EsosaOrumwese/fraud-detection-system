"""Exception helpers for Segment 2B state-0 gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class S0GateError(Exception):
    """Structured error raised by the 2B gate."""

    code: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.code}: {self.detail}"


def err(code: str, detail: str) -> S0GateError:
    """Factory to create a :class:`S0GateError` with consistent formatting."""

    return S0GateError(code=code, detail=detail)


__all__ = ["S0GateError", "err"]

