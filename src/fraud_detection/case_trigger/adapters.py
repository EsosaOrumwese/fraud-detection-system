"""CaseTrigger source adapters and eligibility gates (Phase 2)."""

from __future__ import annotations

from typing import Any, Mapping

from fraud_detection.action_layer.contracts import ActionLayerContractError, ActionOutcome
from fraud_detection.case_mgmt.contracts import CaseTrigger
from fraud_detection.decision_fabric.contracts import DecisionFabricContractError, DecisionResponse
from fraud_detection.decision_log_audit.contracts import AuditRecord, DecisionLogAuditContractError

from .config import CaseTriggerPolicy
from .contracts import CaseTriggerContractError, validate_case_trigger_payload
from .taxonomy import ensure_supported_source_class


DEFAULT_CASE_EVENT_CLASS = "traffic_fraud"
AL_TRIGGERABLE_FAILURE_STATUSES: frozenset[str] = frozenset({"FAILED", "DENIED"})


class CaseTriggerAdapterError(ValueError):
    """Raised when CaseTrigger source adaptation fails."""


def adapt_case_trigger_from_source(
    *,
    source_class: str,
    source_payload: Mapping[str, Any],
    policy: CaseTriggerPolicy | None = None,
    event_class: str = DEFAULT_CASE_EVENT_CLASS,
    observed_time: str | None = None,
    audit_record_id: str | None = None,
    source_event_id: str | None = None,
) -> CaseTrigger:
    normalized_source = _normalize_source_class(source_class)
    if normalized_source == "DF_DECISION":
        return adapt_from_df_decision(
            decision_payload=source_payload,
            audit_record_id=audit_record_id,
            policy=policy,
            event_class=event_class,
            observed_time=observed_time,
        )
    if normalized_source == "AL_OUTCOME":
        return adapt_from_al_outcome(
            outcome_payload=source_payload,
            audit_record_id=audit_record_id,
            source_event_id=source_event_id,
            policy=policy,
            event_class=event_class,
            observed_time=observed_time,
        )
    if normalized_source == "DLA_AUDIT":
        return adapt_from_dla_audit(
            audit_payload=source_payload,
            policy=policy,
            event_class=event_class,
            observed_time=observed_time,
            source_event_id=source_event_id,
        )
    if normalized_source == "EXTERNAL_SIGNAL":
        return adapt_from_external_signal(
            source_payload=source_payload,
            policy=policy,
            observed_time=observed_time,
        )
    if normalized_source == "MANUAL_ASSERTION":
        return adapt_from_manual_assertion(
            source_payload=source_payload,
            policy=policy,
            observed_time=observed_time,
        )
    raise CaseTriggerAdapterError(f"unsupported CaseTrigger source_class: {normalized_source!r}")


def adapt_from_df_decision(
    *,
    decision_payload: Mapping[str, Any],
    audit_record_id: str | None,
    policy: CaseTriggerPolicy | None = None,
    event_class: str = DEFAULT_CASE_EVENT_CLASS,
    observed_time: str | None = None,
) -> CaseTrigger:
    decision = _parse_decision_response(decision_payload)
    payload = decision.as_dict()
    pins = _as_mapping(payload.get("pins"), "decision.pins")
    source_event = _as_mapping(payload.get("source_event"), "decision.source_event")

    platform_run_id = _require_non_empty_string(
        pins.get("platform_run_id"),
        "decision.pins.platform_run_id",
    )
    event_id = _require_non_empty_string(
        source_event.get("event_id"),
        "decision.source_event.event_id",
    )
    decision_id = _require_non_empty_string(payload.get("decision_id"), "decision.decision_id")
    audit_ref = _require_non_empty_string(audit_record_id, "audit_record_id")
    decision_observed_time = _require_non_empty_string(
        observed_time or payload.get("decided_at_utc"),
        "decision.decided_at_utc",
    )
    normalized_event_class = _require_non_empty_string(event_class, "event_class")

    case_trigger_payload = {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": f"decision:{decision_id}",
        "case_subject_key": {
            "platform_run_id": platform_run_id,
            "event_class": normalized_event_class,
            "event_id": event_id,
        },
        "pins": dict(pins),
        "observed_time": decision_observed_time,
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": decision_id},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": audit_ref},
        ],
        "trigger_payload": {
            "source_contract": "decision_response",
            "decision_kind": str(payload.get("decision_kind") or ""),
            "decision_action_kind": str(_as_mapping(payload.get("decision"), "decision.decision").get("action_kind") or ""),
        },
    }
    return _validate_adapter_output(
        case_trigger_payload,
        source_class="DF_DECISION",
        policy=policy,
    )


def adapt_from_al_outcome(
    *,
    outcome_payload: Mapping[str, Any],
    audit_record_id: str | None,
    source_event_id: str | None,
    policy: CaseTriggerPolicy | None = None,
    event_class: str = DEFAULT_CASE_EVENT_CLASS,
    observed_time: str | None = None,
) -> CaseTrigger:
    outcome = _parse_action_outcome(outcome_payload)
    payload = outcome.as_dict()
    pins = _as_mapping(payload.get("pins"), "outcome.pins")

    status = _require_non_empty_string(payload.get("status"), "outcome.status")
    if status not in AL_TRIGGERABLE_FAILURE_STATUSES:
        raise CaseTriggerAdapterError(
            "AL outcome is not a failure-class signal for ACTION_FAILURE trigger: "
            f"status={status!r}, allowed={sorted(AL_TRIGGERABLE_FAILURE_STATUSES)!r}"
        )

    platform_run_id = _require_non_empty_string(
        pins.get("platform_run_id"),
        "outcome.pins.platform_run_id",
    )
    event_id = _require_non_empty_string(source_event_id, "source_event_id")
    outcome_id = _require_non_empty_string(payload.get("outcome_id"), "outcome.outcome_id")
    action_id = _require_non_empty_string(payload.get("action_id"), "outcome.action_id")
    audit_ref = _require_non_empty_string(audit_record_id, "audit_record_id")
    outcome_observed_time = _require_non_empty_string(
        observed_time or payload.get("completed_at_utc"),
        "outcome.completed_at_utc",
    )
    normalized_event_class = _require_non_empty_string(event_class, "event_class")

    case_trigger_payload = {
        "trigger_type": "ACTION_FAILURE",
        "source_ref_id": f"action_outcome:{outcome_id}",
        "case_subject_key": {
            "platform_run_id": platform_run_id,
            "event_class": normalized_event_class,
            "event_id": event_id,
        },
        "pins": dict(pins),
        "observed_time": outcome_observed_time,
        "evidence_refs": [
            {"ref_type": "ACTION_OUTCOME", "ref_id": outcome_id},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": audit_ref},
        ],
        "trigger_payload": {
            "source_contract": "action_outcome",
            "status": status,
            "action_id": action_id,
            "action_kind": str(payload.get("action_kind") or ""),
        },
    }
    return _validate_adapter_output(
        case_trigger_payload,
        source_class="AL_OUTCOME",
        policy=policy,
    )


def adapt_from_dla_audit(
    *,
    audit_payload: Mapping[str, Any],
    policy: CaseTriggerPolicy | None = None,
    event_class: str = DEFAULT_CASE_EVENT_CLASS,
    observed_time: str | None = None,
    source_event_id: str | None = None,
) -> CaseTrigger:
    audit = _parse_audit_record(audit_payload)
    payload = audit.as_dict()
    pins = _as_mapping(payload.get("pins"), "audit.pins")
    decision_event = _as_mapping(payload.get("decision_event"), "audit.decision_event")

    platform_run_id = _require_non_empty_string(
        pins.get("platform_run_id"),
        "audit.pins.platform_run_id",
    )
    event_id = _require_non_empty_string(
        source_event_id or decision_event.get("event_id"),
        "audit.decision_event.event_id",
    )
    normalized_event_class = _require_non_empty_string(event_class, "event_class")
    audit_observed_time = _require_non_empty_string(
        observed_time or payload.get("recorded_at_utc"),
        "audit.recorded_at_utc",
    )
    audit_id = _require_non_empty_string(payload.get("audit_id"), "audit.audit_id")

    trigger_payload = {
        "source_contract": "audit_record",
        "decision_event_type": str(decision_event.get("event_type") or ""),
        "degrade_mode": str(_as_mapping(payload.get("degrade_posture"), "audit.degrade_posture").get("mode") or ""),
    }

    case_trigger_payload = {
        "trigger_type": "ANOMALY",
        "source_ref_id": f"audit:{audit_id}",
        "case_subject_key": {
            "platform_run_id": platform_run_id,
            "event_class": normalized_event_class,
            "event_id": event_id,
        },
        "pins": dict(pins),
        "observed_time": audit_observed_time,
        "evidence_refs": [
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": audit_id},
        ],
        "trigger_payload": trigger_payload,
    }
    return _validate_adapter_output(
        case_trigger_payload,
        source_class="DLA_AUDIT",
        policy=policy,
    )


def adapt_from_external_signal(
    *,
    source_payload: Mapping[str, Any],
    policy: CaseTriggerPolicy | None = None,
    observed_time: str | None = None,
) -> CaseTrigger:
    payload = dict(source_payload)
    ref_id = _require_non_empty_string(
        payload.get("external_ref_id") or payload.get("ref_id"),
        "external_ref_id",
    )
    case_subject_key = _as_mapping(payload.get("case_subject_key"), "case_subject_key")
    pins = _as_mapping(payload.get("pins"), "pins")
    external_observed_time = _require_non_empty_string(
        observed_time or payload.get("observed_time"),
        "observed_time",
    )
    trigger_payload = _as_optional_mapping(payload.get("trigger_payload"))

    case_trigger_payload = {
        "trigger_type": "EXTERNAL_SIGNAL",
        "source_ref_id": f"external:{ref_id}",
        "case_subject_key": case_subject_key,
        "pins": pins,
        "observed_time": external_observed_time,
        "evidence_refs": [
            {"ref_type": "EXTERNAL_REF", "ref_id": ref_id},
        ],
        "trigger_payload": trigger_payload,
    }
    return _validate_adapter_output(
        case_trigger_payload,
        source_class="EXTERNAL_SIGNAL",
        policy=policy,
    )


def adapt_from_manual_assertion(
    *,
    source_payload: Mapping[str, Any],
    policy: CaseTriggerPolicy | None = None,
    observed_time: str | None = None,
) -> CaseTrigger:
    payload = dict(source_payload)
    ref_id = _require_non_empty_string(
        payload.get("manual_assertion_id") or payload.get("ref_id"),
        "manual_assertion_id",
    )
    case_subject_key = _as_mapping(payload.get("case_subject_key"), "case_subject_key")
    pins = _as_mapping(payload.get("pins"), "pins")
    manual_observed_time = _require_non_empty_string(
        observed_time or payload.get("observed_time"),
        "observed_time",
    )
    trigger_payload = _as_optional_mapping(payload.get("trigger_payload"))

    case_trigger_payload = {
        "trigger_type": "MANUAL_ASSERTION",
        "source_ref_id": f"manual:{ref_id}",
        "case_subject_key": case_subject_key,
        "pins": pins,
        "observed_time": manual_observed_time,
        "evidence_refs": [
            {"ref_type": "EXTERNAL_REF", "ref_id": ref_id},
        ],
        "trigger_payload": trigger_payload,
    }
    return _validate_adapter_output(
        case_trigger_payload,
        source_class="MANUAL_ASSERTION",
        policy=policy,
    )


def _parse_decision_response(payload: Mapping[str, Any]) -> DecisionResponse:
    try:
        return DecisionResponse.from_payload(payload)
    except DecisionFabricContractError as exc:
        raise CaseTriggerAdapterError(
            f"DF decision payload failed contract validation: {exc}"
        ) from exc


def _parse_action_outcome(payload: Mapping[str, Any]) -> ActionOutcome:
    try:
        return ActionOutcome.from_payload(payload)
    except ActionLayerContractError as exc:
        raise CaseTriggerAdapterError(
            f"AL outcome payload failed contract validation: {exc}"
        ) from exc


def _parse_audit_record(payload: Mapping[str, Any]) -> AuditRecord:
    try:
        return AuditRecord.from_payload(payload)
    except DecisionLogAuditContractError as exc:
        raise CaseTriggerAdapterError(
            f"DLA audit payload failed contract validation: {exc}"
        ) from exc


def _validate_adapter_output(
    payload: Mapping[str, Any],
    *,
    source_class: str,
    policy: CaseTriggerPolicy | None,
) -> CaseTrigger:
    try:
        return validate_case_trigger_payload(
            payload,
            source_class=source_class,
            policy=policy,
        )
    except CaseTriggerContractError as exc:
        raise CaseTriggerAdapterError(
            f"CaseTrigger payload from adapter failed validation: {exc}"
        ) from exc


def _normalize_source_class(source_class: str) -> str:
    try:
        return ensure_supported_source_class(source_class)
    except ValueError as exc:
        raise CaseTriggerAdapterError(str(exc)) from exc


def _as_mapping(payload: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CaseTriggerAdapterError(f"{field_name} must be a mapping")
    return dict(payload)


def _as_optional_mapping(payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}


def _require_non_empty_string(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseTriggerAdapterError(f"{field_name} must be a non-empty string")
    return text
