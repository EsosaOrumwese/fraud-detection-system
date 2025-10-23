"""Failure taxonomy for Segment 1B state-7 (site synthesis)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """Categorised failure domains for S7 errors."""

    INPUT = "input_validation"
    COVERAGE = "coverage"
    GEOMETRY = "geometry"
    WRITER = "writer_hygiene"
    IDENTITY = "identity"
    INTERNAL = "internal"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E701_ROW_MISSING": (FailureCategory.INPUT, "s5_row_missing_in_s7"),
    "E702_ROW_EXTRA": (FailureCategory.INPUT, "s7_row_not_in_s5"),
    "E703_DUP_KEY": (FailureCategory.INPUT, "s7_duplicate_primary_key"),
    "E704_SCHEMA_VIOLATION": (FailureCategory.WRITER, "schema_violation"),
    "E705_PARTITION_OR_IDENTITY": (FailureCategory.IDENTITY, "partition_or_identity_mismatch"),
    "E706_WRITER_SORT_VIOLATION": (FailureCategory.WRITER, "writer_sort_violation"),
    "E707_POINT_OUTSIDE_PIXEL": (FailureCategory.GEOMETRY, "reconstructed_point_outside_pixel"),
    "E708_1A_COVERAGE_FAIL": (FailureCategory.COVERAGE, "outlet_catalogue_coverage_failure"),
    "E709_TILE_FK_VIOLATION": (FailureCategory.INPUT, "tile_fk_violation"),
    "E710_ORDER_LEAK": (FailureCategory.IDENTITY, "order_authority_violation"),
    "E711_DICT_SCHEMA_MISMATCH": (FailureCategory.INPUT, "dictionary_schema_mismatch"),
    "E712_ATOMIC_PUBLISH_VIOLATION": (FailureCategory.WRITER, "atomic_publish_violation"),
    "E799_INTERNAL": (FailureCategory.INTERNAL, "internal_error"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S7 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S7Error(RuntimeError):
    """Raised when S7 encounters a contract violation."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S7Error:
    """Create an ``S7Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S7 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S7Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S7Error", "err"]
