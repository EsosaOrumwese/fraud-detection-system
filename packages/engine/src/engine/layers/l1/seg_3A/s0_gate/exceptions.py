"""Exceptions for Segment 3A S0 gate."""

from __future__ import annotations


class S0GateError(RuntimeError):
    """Base exception for 3A S0 gate failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def err(code: str, message: str) -> S0GateError:
    """Helper to raise structured S0 errors consistently."""

    return S0GateError(code=code, message=message)


__all__ = ["S0GateError", "err"]
