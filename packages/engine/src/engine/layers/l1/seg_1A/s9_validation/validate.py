"""Thin shim that re-exports the S9 validation implementation."""

from __future__ import annotations

from . import validator_core as _core

validate_outputs = _core.validate_outputs
_verify_rng_budgets = _core._verify_rng_budgets
get_repo_root = _core.get_repo_root
_schema_file_path = _core._schema_file_path
_resolve_pointer = _core._resolve_pointer
_split_schema_ref = _core._split_schema_ref

__all__ = list(getattr(_core, "__all__", ["validate_outputs"]))
if "_verify_rng_budgets" not in __all__:
    __all__.append("_verify_rng_budgets")
if "get_repo_root" not in __all__:
    __all__.append("get_repo_root")
for name in ("_schema_file_path", "_resolve_pointer", "_split_schema_ref"):
    if name not in __all__:
        __all__.append(name)
