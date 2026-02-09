"""CaseTrigger writer-side contract checks (Phase 1)."""

from __future__ import annotations

from typing import Any, Mapping

from fraud_detection.case_mgmt.contracts import CaseMgmtContractError, CaseTrigger

from .config import CaseTriggerPolicy
from .taxonomy import (
    CaseTriggerTaxonomyError,
    ensure_required_evidence_ref_types,
    ensure_source_class_allowed_for_trigger_type,
    ensure_supported_source_class,
)


class CaseTriggerContractError(ValueError):
    """Raised when CaseTrigger writer-side contract checks fail."""


def validate_case_trigger_payload(
    payload: Mapping[str, Any],
    *,
    source_class: str,
    policy: CaseTriggerPolicy | None = None,
) -> CaseTrigger:
    normalized_source = _validate_source_class(source_class)
    trigger = _parse_case_trigger(payload)
    _validate_taxonomy(trigger, normalized_source)
    if policy is not None:
        _validate_policy(trigger, normalized_source, policy)
    return trigger


def _parse_case_trigger(payload: Mapping[str, Any]) -> CaseTrigger:
    try:
        return CaseTrigger.from_payload(payload)
    except CaseMgmtContractError as exc:
        raise CaseTriggerContractError(
            f"invalid CaseTrigger payload: {exc}"
        ) from exc


def _validate_source_class(source_class: str) -> str:
    try:
        return ensure_supported_source_class(source_class)
    except CaseTriggerTaxonomyError as exc:
        raise CaseTriggerContractError(str(exc)) from exc


def _validate_taxonomy(trigger: CaseTrigger, source_class: str) -> None:
    try:
        ensure_source_class_allowed_for_trigger_type(trigger.trigger_type, source_class)
        ensure_required_evidence_ref_types(
            trigger.trigger_type,
            (ref.ref_type for ref in trigger.evidence_refs),
        )
    except CaseTriggerTaxonomyError as exc:
        raise CaseTriggerContractError(str(exc)) from exc


def _validate_policy(trigger: CaseTrigger, source_class: str, policy: CaseTriggerPolicy) -> None:
    rule = policy.rule_for_trigger_type(trigger.trigger_type)
    if rule is None:
        raise CaseTriggerContractError(
            "policy does not define rule for trigger_type: "
            f"{trigger.trigger_type!r}"
        )
    if source_class not in rule.source_classes:
        raise CaseTriggerContractError(
            "policy source class mismatch for trigger_type: "
            f"trigger_type={trigger.trigger_type!r}, source_class={source_class!r}, "
            f"allowed={sorted(rule.source_classes)!r}"
        )
    seen_ref_types = {ref.ref_type for ref in trigger.evidence_refs}
    missing_ref_types = sorted(set(rule.required_evidence_ref_types) - seen_ref_types)
    if missing_ref_types:
        raise CaseTriggerContractError(
            "policy required evidence refs missing for trigger_type "
            f"{trigger.trigger_type!r}: {missing_ref_types!r}"
        )
    missing_pins = policy.missing_required_pins(trigger.pins)
    if missing_pins:
        raise CaseTriggerContractError(
            "policy required pins missing from CaseTrigger pins: "
            f"{missing_pins!r}"
        )
