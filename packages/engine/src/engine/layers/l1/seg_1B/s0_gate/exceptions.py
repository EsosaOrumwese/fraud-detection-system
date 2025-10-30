"""Failure taxonomy for Segment 1B state-0 gate.

The expanded specification enumerates canonical error codes that must bubble
up deterministically so downstream validation bundles can reason about
failures.  This module keeps that mapping in one place and offers a small
``err`` helper for callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """High-level buckets mirrored from the specification."""

    GATE = "gate_integrity"
    ACCESS = "access_control"
    LINEAGE = "lineage_violation"
    RECEIPT = "receipt_publish"
    REFERENCE = "reference_surface"
    IO = "io_error"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    # Gate & bundle integrity
    "E_BUNDLE_MISSING": (FailureCategory.GATE, "validation_bundle_missing"),
    "E_INDEX_MISSING": (FailureCategory.GATE, "validation_index_missing"),
    "E_INDEX_INVALID": (FailureCategory.GATE, "validation_index_invalid"),
    "E_PASS_MISSING": (FailureCategory.GATE, "passed_flag_missing"),
    "E_FLAG_FORMAT_INVALID": (FailureCategory.GATE, "passed_flag_format"),
    "E_FLAG_HASH_MISMATCH": (FailureCategory.GATE, "passed_flag_mismatch"),
    # Access-control
    "E_OUTLET_CATALOGUE_FORBIDDEN_BEFORE_PASS": (
        FailureCategory.ACCESS,
        "forbidden_read_before_pass",
    ),
    "E_FORBIDDEN_SURFACE_READ": (
        FailureCategory.ACCESS,
        "forbidden_reference_read",
    ),
    # Lineage rules
    "E_PATH_EMBED_MISMATCH": (FailureCategory.LINEAGE, "path_embed_mismatch"),
    "E_PARTITION_MISPLACED": (FailureCategory.LINEAGE, "partition_misaligned"),
    # Receipt publish
    "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL": (
        FailureCategory.RECEIPT,
        "receipt_partition_exists",
    ),
    "E_RECEIPT_SCHEMA_INVALID": (
        FailureCategory.RECEIPT,
        "receipt_schema_invalid",
    ),
    # Reference surfaces / dictionary resolution
    "E_REFERENCE_SURFACE_MISSING": (
        FailureCategory.REFERENCE,
        "reference_surface_missing",
    ),
    "E_SCHEMA_RESOLUTION_FAILED": (
        FailureCategory.REFERENCE,
        "schema_resolution_failed",
    ),
    "E_DICTIONARY_RESOLUTION_FAILED": (
        FailureCategory.REFERENCE,
        "dictionary_resolution_failed",
    ),
    # Generic IO (used sparingly when the spec does not provide a dedicated code)
    "E_IO": (FailureCategory.IO, "io_error"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S0 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S0GateError(RuntimeError):
    """Exception carrying the canonical error context."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S0GateError:
    """Build an ``S0GateError`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S0 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S0GateError(context)


__all__ = ["FailureCategory", "ErrorContext", "S0GateError", "err"]
