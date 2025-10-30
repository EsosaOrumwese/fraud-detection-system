"""Failure taxonomy for Segment 1B state-6 (site jitter)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """Categorised failure domains for S6 errors."""

    INPUT = "input_validation"
    GEOMETRY = "geometry"
    RNG = "rng_envelope"
    WRITER = "writer_hygiene"
    INTERNAL = "internal"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E601_ROW_MISSING": (FailureCategory.INPUT, "row_missing"),
    "E602_ROW_EXTRA": (FailureCategory.INPUT, "row_extra"),
    "E603_DUP_KEY": (FailureCategory.INPUT, "duplicate_key"),
    "E604_PARTITION_OR_IDENTITY": (FailureCategory.WRITER, "partition_or_identity"),
    "E605_SORT_VIOLATION": (FailureCategory.WRITER, "sort_violation"),
    "E606_FK_TILE_INDEX": (FailureCategory.INPUT, "fk_tile_index"),
    "E607_POINT_OUTSIDE_PIXEL": (FailureCategory.GEOMETRY, "point_outside_pixel"),
    "E608_POINT_OUTSIDE_COUNTRY": (FailureCategory.GEOMETRY, "point_outside_country"),
    "E609_RNG_EVENT_COUNT": (FailureCategory.RNG, "rng_event_count"),
    "E610_RNG_BUDGET_OR_COUNTERS": (FailureCategory.RNG, "rng_budget_or_counters"),
    "E611_LOG_PARTITION_LAW": (FailureCategory.RNG, "log_partition_law"),
    "E612_DICT_SCHEMA_MISMATCH": (FailureCategory.INPUT, "dict_schema_mismatch"),
    "E613_RESAMPLE_EXHAUSTED": (FailureCategory.GEOMETRY, "resample_exhausted"),
    "E699_NOT_IMPLEMENTED": (FailureCategory.INTERNAL, "not_implemented"),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S6 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S6Error(RuntimeError):
    """Raised when S6 encounters a contract violation."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S6Error:
    """Create an ``S6Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S6 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S6Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S6Error", "err"]
