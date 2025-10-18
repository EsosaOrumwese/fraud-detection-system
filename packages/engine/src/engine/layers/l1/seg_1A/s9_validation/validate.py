"""Thin shim that re-exports the S9 validation implementation."""

from __future__ import annotations

from . import validator_core as _core

validate_outputs = _core.validate_outputs
_verify_rng_budgets = _core._verify_rng_budgets

__all__ = list(getattr(_core, "__all__", ["validate_outputs"]))
if "_verify_rng_budgets" not in __all__:
    __all__.append("_verify_rng_budgets")
