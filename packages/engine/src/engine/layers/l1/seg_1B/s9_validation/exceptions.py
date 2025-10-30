"""Failure taxonomy for Segment 1B state-9 validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """High-level groupings aligned with the S9 specification."""

    PARITY = "parity"
    SCHEMA = "schema"
    IDENTITY = "identity"
    WRITER = "writer_sort"
    RNG = "rng_contract"
    BUNDLE = "validation_bundle"
    PUBLISH = "publish_posture"
    CONTRACT = "contract_discipline"
    INTERNAL = "internal"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E901_ROW_MISSING": (FailureCategory.PARITY, "row_missing"),
    "E902_ROW_EXTRA": (FailureCategory.PARITY, "row_extra"),
    "E903_DUP_KEY": (FailureCategory.SCHEMA, "duplicate_primary_key"),
    "E904_EGRESS_SCHEMA_VIOLATION": (FailureCategory.SCHEMA, "egress_schema_violation"),
    "E905_PARTITION_OR_IDENTITY": (FailureCategory.IDENTITY, "partition_or_identity_mismatch"),
    "E906_WRITER_SORT_VIOLATION": (FailureCategory.WRITER, "writer_sort_violation"),
    "E907_RNG_BUDGET_OR_COUNTERS": (FailureCategory.RNG, "rng_budget_or_counter_mismatch"),
    "E908_BUNDLE_CONTENTS_MISSING": (FailureCategory.BUNDLE, "bundle_contents_missing"),
    "E909_INDEX_INVALID": (FailureCategory.BUNDLE, "bundle_index_invalid"),
    "E910_FLAG_BAD_OR_MISSING": (FailureCategory.BUNDLE, "passed_flag_invalid"),
    "E911_FINALITY_OR_ORDER_LEAK": (FailureCategory.CONTRACT, "finality_or_order_leak"),
    "E912_IDENTITY_COHERENCE": (FailureCategory.IDENTITY, "identity_coherence_violation"),
    "E913_ATOMIC_PUBLISH_VIOLATION": (FailureCategory.PUBLISH, "atomic_publish_violation"),
    "E999_INTERNAL": (FailureCategory.INTERNAL, "internal_error"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S9 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S9ValidationError(RuntimeError):
    """Raised when Segment 1B S9 validation encounters a contract violation."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S9ValidationError:
    """Create an ``S9ValidationError`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S9 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S9ValidationError(context)


__all__ = ["FailureCategory", "ErrorContext", "S9ValidationError", "err"]
