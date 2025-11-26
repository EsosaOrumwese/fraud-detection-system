"""Exceptions for Segment 3B S0 gate."""

class S0GateError(RuntimeError):
    """Raised when the 3B gate encounters a validation or IO failure."""


def err(code: str, message: str) -> S0GateError:
    return S0GateError(f"{code}: {message}")


__all__ = ["S0GateError", "err"]
