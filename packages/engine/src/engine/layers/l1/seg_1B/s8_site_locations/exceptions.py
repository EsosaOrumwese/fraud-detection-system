"""Failure taxonomy for Segment 1B state-8 (site_locations egress)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """Categorised failure domains for S8 errors."""

    INPUT = "input_validation"
    OUTPUT = "egress_validation"
    IDENTITY = "identity"
    WRITER = "writer_hygiene"
    ORDER = "order_authority"
    INTERNAL = "internal"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E801_ROW_MISSING": (FailureCategory.INPUT, "s8_row_missing"),
    "E802_ROW_EXTRA": (FailureCategory.INPUT, "s8_row_extra"),
    "E803_DUP_KEY": (FailureCategory.OUTPUT, "duplicate_primary_key"),
    "E804_SCHEMA_VIOLATION": (FailureCategory.OUTPUT, "schema_violation"),
    "E805_PARTITION_OR_IDENTITY": (FailureCategory.IDENTITY, "partition_or_identity_mismatch"),
    "E806_WRITER_SORT_VIOLATION": (FailureCategory.WRITER, "writer_sort_violation"),
    "E807_ORDER_LEAK": (FailureCategory.ORDER, "order_leak"),
    "E808_DICT_SCHEMA_MISMATCH": (FailureCategory.IDENTITY, "dictionary_schema_mismatch"),
    "E809_PARTITION_SHIFT_VIOLATION": (FailureCategory.IDENTITY, "partition_shift_violation"),
    "E810_PUBLISH_POSTURE": (FailureCategory.WRITER, "publish_posture_violation"),
    "E811_FINAL_FLAG_MISMATCH": (FailureCategory.IDENTITY, "final_flag_mismatch"),
    "E812_RESOLUTION_DISCIPLINE": (FailureCategory.IDENTITY, "resolution_discipline"),
    "E899_INTERNAL": (FailureCategory.INTERNAL, "internal_error"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S8 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S8Error(RuntimeError):
    """Raised when S8 encounters a contract violation."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S8Error:
    """Create an ``S8Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S8 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S8Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S8Error", "err"]
