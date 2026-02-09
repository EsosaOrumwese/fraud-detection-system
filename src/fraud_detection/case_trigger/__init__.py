"""CaseTrigger contract and taxonomy surfaces (Phase 1)."""

from .adapters import (
    AL_TRIGGERABLE_FAILURE_STATUSES,
    DEFAULT_CASE_EVENT_CLASS,
    CaseTriggerAdapterError,
    adapt_case_trigger_from_source,
    adapt_from_al_outcome,
    adapt_from_df_decision,
    adapt_from_dla_audit,
    adapt_from_external_signal,
    adapt_from_manual_assertion,
)
from .config import (
    CaseTriggerConfigError,
    CaseTriggerPolicy,
    CaseTriggerRule,
    load_trigger_policy,
)
from .contracts import CaseTriggerContractError, validate_case_trigger_payload
from .taxonomy import (
    SUPPORTED_CASE_TRIGGER_TYPES,
    SUPPORTED_SOURCE_CLASSES,
    TRIGGER_ALLOWED_SOURCE_CLASSES,
    TRIGGER_REQUIRED_EVIDENCE_REF_TYPES,
    CaseTriggerTaxonomyError,
    allowed_source_classes_for_trigger_type,
    ensure_required_evidence_ref_types,
    ensure_source_class_allowed_for_trigger_type,
    ensure_supported_case_trigger_type,
    ensure_supported_source_class,
    missing_required_evidence_ref_types,
    required_evidence_ref_types_for_trigger_type,
)

__all__ = [
    "SUPPORTED_CASE_TRIGGER_TYPES",
    "SUPPORTED_SOURCE_CLASSES",
    "AL_TRIGGERABLE_FAILURE_STATUSES",
    "DEFAULT_CASE_EVENT_CLASS",
    "TRIGGER_ALLOWED_SOURCE_CLASSES",
    "TRIGGER_REQUIRED_EVIDENCE_REF_TYPES",
    "CaseTriggerAdapterError",
    "CaseTriggerConfigError",
    "CaseTriggerContractError",
    "CaseTriggerPolicy",
    "CaseTriggerRule",
    "CaseTriggerTaxonomyError",
    "adapt_case_trigger_from_source",
    "adapt_from_al_outcome",
    "adapt_from_df_decision",
    "adapt_from_dla_audit",
    "adapt_from_external_signal",
    "adapt_from_manual_assertion",
    "allowed_source_classes_for_trigger_type",
    "ensure_required_evidence_ref_types",
    "ensure_source_class_allowed_for_trigger_type",
    "ensure_supported_case_trigger_type",
    "ensure_supported_source_class",
    "load_trigger_policy",
    "missing_required_evidence_ref_types",
    "required_evidence_ref_types_for_trigger_type",
    "validate_case_trigger_payload",
]
