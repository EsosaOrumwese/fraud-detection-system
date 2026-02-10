"""MF Phase 7 taxonomy helpers for fail-closed negative-path validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


MF_FAILURE_TAXONOMY_V0: Final[dict[str, tuple[str, ...]]] = {
    "INPUT_ADMISSION": (
        "MANIFEST_REF_MISSING",
        "REQUEST_INVALID",
        "RUN_SCOPE_INVALID",
    ),
    "RESOLUTION": (
        "MANIFEST_UNRESOLVED",
        "MANIFEST_INVALID",
        "TRAINING_PROFILE_UNRESOLVED",
        "GOVERNANCE_PROFILE_UNRESOLVED",
        "TRAINING_PROFILE_INVALID",
        "GOVERNANCE_PROFILE_INVALID",
        "FEATURE_SCHEMA_INCOMPATIBLE",
    ),
    "EVIDENCE": (
        "EVIDENCE_REF_MISSING",
        "EVIDENCE_UNRESOLVED",
        "EVAL_REPORT_UNRESOLVED",
        "EVAL_REPORT_INVALID",
        "EVAL_REPORT_MISMATCH",
        "GATE_INVALID",
        "GATE_DECISION_MISMATCH",
    ),
    "IMMUTABILITY": (
        "MANIFEST_IMMUTABILITY_VIOLATION",
        "RESOLVED_TRAIN_PLAN_IMMUTABILITY_VIOLATION",
        "EXECUTION_RECORD_IMMUTABILITY_VIOLATION",
        "TRAIN_ARTIFACT_IMMUTABILITY_VIOLATION",
        "EVAL_REPORT_IMMUTABILITY_VIOLATION",
        "EVIDENCE_PACK_IMMUTABILITY_VIOLATION",
        "TRAIN_EVAL_RECEIPT_IMMUTABILITY_VIOLATION",
        "GATE_RECEIPT_IMMUTABILITY_VIOLATION",
        "PUBLISH_ELIGIBILITY_IMMUTABILITY_VIOLATION",
        "BUNDLE_PACKAGE_IMMUTABILITY_VIOLATION",
        "REGISTRY_EVENT_IMMUTABILITY_VIOLATION",
        "PUBLISH_RECEIPT_IMMUTABILITY_VIOLATION",
    ),
    "PUBLISH": (
        "PUBLISH_NOT_ELIGIBLE",
        "BUNDLE_PUBLICATION_INVALID",
        "REGISTRY_EVENT_INVALID",
        "PUBLISH_CONFLICT",
    ),
    "POLICY": (
        "LEAKAGE_GUARD_VIOLATION",
    ),
}

MF_RETRYABLE_FAILURE_CODES_V0: Final[frozenset[str]] = frozenset(
    {
        "MANIFEST_UNRESOLVED",
        "TRAINING_PROFILE_UNRESOLVED",
        "GOVERNANCE_PROFILE_UNRESOLVED",
        "EVIDENCE_UNRESOLVED",
    }
)

_CODE_TO_CATEGORY: dict[str, str] = {}
for _category_name, _codes in MF_FAILURE_TAXONOMY_V0.items():
    for _code in _codes:
        normalized = str(_code).strip().upper()
        if normalized in _CODE_TO_CATEGORY and _CODE_TO_CATEGORY[normalized] != _category_name:
            raise ValueError(f"duplicate failure code {normalized!r} in taxonomy")
        _CODE_TO_CATEGORY[normalized] = _category_name


@dataclass(frozen=True)
class MfFailureClassification:
    code: str
    category: str
    known: bool
    retryable: bool


def classify_failure_code(code: str) -> MfFailureClassification:
    normalized = _normalize_code(code)
    category = _CODE_TO_CATEGORY.get(normalized, "UNKNOWN")
    known = category != "UNKNOWN"
    return MfFailureClassification(
        code=normalized,
        category=category,
        known=known,
        retryable=normalized in MF_RETRYABLE_FAILURE_CODES_V0,
    )


def is_known_failure_code(code: str) -> bool:
    return classify_failure_code(code).known


def known_failure_codes() -> tuple[str, ...]:
    return tuple(sorted(_CODE_TO_CATEGORY))


def failure_taxonomy_snapshot() -> dict[str, tuple[str, ...]]:
    return {category: tuple(codes) for category, codes in MF_FAILURE_TAXONOMY_V0.items()}


def _normalize_code(code: str) -> str:
    return str(code or "").strip().upper() or "UNKNOWN"
