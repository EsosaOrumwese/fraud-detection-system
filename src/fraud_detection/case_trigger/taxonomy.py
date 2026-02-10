"""CaseTrigger taxonomy guards (Phase 1)."""

from __future__ import annotations

from collections.abc import Iterable


SUPPORTED_CASE_TRIGGER_TYPES: tuple[str, ...] = (
    "DECISION_ESCALATION",
    "ACTION_FAILURE",
    "ANOMALY",
    "EXTERNAL_SIGNAL",
    "MANUAL_ASSERTION",
)

SUPPORTED_SOURCE_CLASSES: tuple[str, ...] = (
    "DF_DECISION",
    "AL_OUTCOME",
    "DLA_AUDIT",
    "EXTERNAL_SIGNAL",
    "MANUAL_ASSERTION",
)

TRIGGER_ALLOWED_SOURCE_CLASSES: dict[str, tuple[str, ...]] = {
    "DECISION_ESCALATION": ("DF_DECISION",),
    "ACTION_FAILURE": ("AL_OUTCOME",),
    "ANOMALY": ("DLA_AUDIT",),
    "EXTERNAL_SIGNAL": ("EXTERNAL_SIGNAL",),
    "MANUAL_ASSERTION": ("MANUAL_ASSERTION",),
}

TRIGGER_REQUIRED_EVIDENCE_REF_TYPES: dict[str, tuple[str, ...]] = {
    "DECISION_ESCALATION": ("DECISION", "DLA_AUDIT_RECORD"),
    "ACTION_FAILURE": ("ACTION_OUTCOME", "DLA_AUDIT_RECORD"),
    "ANOMALY": ("DLA_AUDIT_RECORD",),
    "EXTERNAL_SIGNAL": ("EXTERNAL_REF",),
    "MANUAL_ASSERTION": ("EXTERNAL_REF",),
}


class CaseTriggerTaxonomyError(ValueError):
    """Raised when CaseTrigger taxonomy checks fail."""


def ensure_supported_case_trigger_type(trigger_type: str) -> str:
    normalized = str(trigger_type or "").strip()
    if normalized not in SUPPORTED_CASE_TRIGGER_TYPES:
        raise CaseTriggerTaxonomyError(
            "case trigger type not allowed: "
            f"{normalized!r}"
        )
    return normalized


def ensure_supported_source_class(source_class: str) -> str:
    normalized = str(source_class or "").strip()
    if normalized not in SUPPORTED_SOURCE_CLASSES:
        raise CaseTriggerTaxonomyError(
            "case trigger source class not allowed: "
            f"{normalized!r}"
        )
    return normalized


def allowed_source_classes_for_trigger_type(trigger_type: str) -> tuple[str, ...]:
    normalized = ensure_supported_case_trigger_type(trigger_type)
    return TRIGGER_ALLOWED_SOURCE_CLASSES[normalized]


def required_evidence_ref_types_for_trigger_type(trigger_type: str) -> tuple[str, ...]:
    normalized = ensure_supported_case_trigger_type(trigger_type)
    return TRIGGER_REQUIRED_EVIDENCE_REF_TYPES[normalized]


def ensure_source_class_allowed_for_trigger_type(trigger_type: str, source_class: str) -> tuple[str, str]:
    normalized_type = ensure_supported_case_trigger_type(trigger_type)
    normalized_source = ensure_supported_source_class(source_class)
    allowed = allowed_source_classes_for_trigger_type(normalized_type)
    if normalized_source not in allowed:
        raise CaseTriggerTaxonomyError(
            "source class is not allowed for trigger type: "
            f"trigger_type={normalized_type!r}, source_class={normalized_source!r}, "
            f"allowed={sorted(allowed)!r}"
        )
    return normalized_type, normalized_source


def missing_required_evidence_ref_types(
    trigger_type: str,
    evidence_ref_types: Iterable[str],
) -> tuple[str, ...]:
    required = set(required_evidence_ref_types_for_trigger_type(trigger_type))
    observed = {str(value or "").strip() for value in evidence_ref_types if str(value or "").strip()}
    missing = sorted(required - observed)
    return tuple(missing)


def ensure_required_evidence_ref_types(trigger_type: str, evidence_ref_types: Iterable[str]) -> None:
    normalized_type = ensure_supported_case_trigger_type(trigger_type)
    missing = missing_required_evidence_ref_types(normalized_type, evidence_ref_types)
    if missing:
        raise CaseTriggerTaxonomyError(
            "required evidence ref types missing for trigger type "
            f"{normalized_type!r}: {list(missing)!r}"
        )
