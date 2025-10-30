"""Failure taxonomy for Segment 1B state-3 (site requirements)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Tuple


class FailureCategory(Enum):
    """High-level error categories used for S3 failure records."""

    INPUT = "input_validation"
    COVERAGE = "coverage_integrity"
    SCHEMA = "schema_conformance"
    LINEAGE = "lineage_integrity"
    WRITER = "writer_hygiene"
    DETERMINISM = "determinism"
    CONTRACT = "contract_violation"
    INTEGRITY = "data_integrity"


_FAILURE_CODE_MAP: Mapping[str, Tuple[FailureCategory, str]] = {
    "E301_NO_PASS_FLAG": (FailureCategory.INPUT, "missing_gate_pass"),
    "E302_FK_COUNTRY": (FailureCategory.INPUT, "iso_fk_violation"),
    "E303_MISSING_WEIGHTS": (FailureCategory.COVERAGE, "tile_weight_missing"),
    "E304_ZERO_SITES_ROW": (FailureCategory.INTEGRITY, "zero_sites_not_allowed"),
    "E305_SCHEMA_INVALID": (FailureCategory.SCHEMA, "schema_validation_failed"),
    "E305_SCHEMA_EXTRAS": (FailureCategory.SCHEMA, "schema_extras_detected"),
    "E306_TOKEN_MISMATCH": (FailureCategory.LINEAGE, "path_embed_mismatch"),
    "E307_PK_DUPLICATE": (FailureCategory.SCHEMA, "primary_key_violation"),
    "E308_COUNTS_MISMATCH": (FailureCategory.INTEGRITY, "count_mismatch"),
    "E309_ZERO_SITES_ROW": (FailureCategory.INTEGRITY, "zero_sites_not_allowed"),
    "E310_UNSORTED": (FailureCategory.WRITER, "writer_sort_violation"),
    "E311_DISALLOWED_READ": (FailureCategory.INPUT, "disallowed_input_surface"),
    "E312_ORDER_AUTHORITY_VIOLATION": (FailureCategory.CONTRACT, "order_authority_violation"),
    "E313_NONDETERMINISTIC_OUTPUT": (FailureCategory.DETERMINISM, "nondeterministic_output"),
    "E314_SITE_ORDER_INTEGRITY": (FailureCategory.INTEGRITY, "site_order_integrity"),
    "E_RECEIPT_SCHEMA_INVALID": (FailureCategory.SCHEMA, "receipt_schema_invalid"),
    "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL": (
        FailureCategory.WRITER,
        "immutable_partition_conflict",
    ),
}


@dataclass(frozen=True)
class ErrorContext:
    """Structured payload describing an S3 failure."""

    code: str
    category: FailureCategory
    reason: str
    detail: str


class S3Error(RuntimeError):
    """Exception carrying the canonical S3 error context."""

    def __init__(self, context: ErrorContext) -> None:
        super().__init__(f"{context.code}: {context.detail}")
        self.context = context


def err(code: str, detail: str) -> S3Error:
    """Build an ``S3Error`` with canonical metadata."""

    if code not in _FAILURE_CODE_MAP:
        raise ValueError(f"unknown S3 failure code '{code}'")
    category, reason = _FAILURE_CODE_MAP[code]
    context = ErrorContext(code=code, category=category, reason=reason, detail=detail)
    return S3Error(context)


__all__ = ["FailureCategory", "ErrorContext", "S3Error", "err"]
