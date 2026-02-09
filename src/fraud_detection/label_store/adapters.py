"""Label Store ingest adapters for CM and external/engine truth lanes (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Protocol

from .contracts import LabelAssertion, LabelStoreContractError
from .writer_boundary import LabelStoreWriteResult


SUPPORTED_INGEST_SOURCE_CLASSES: frozenset[str] = frozenset(
    {
        "CM_ASSERTION",
        "EXTERNAL_ADJUDICATION",
        "ENGINE_TRUTH",
    }
)
DERIVED_CASE_EVENT_RECIPE_V1 = "ls.adapter.case_timeline_event_id.v1"


class LabelStoreAdapterError(ValueError):
    """Raised when source adaptation to LabelAssertion fails."""


class LabelStoreWriter(Protocol):
    def write_label_assertion(self, assertion_payload: Mapping[str, Any]) -> LabelStoreWriteResult:
        ...


@dataclass(frozen=True)
class LabelStoreAdapterResult:
    source_class: str
    source_ref_id: str
    assertion: LabelAssertion
    write_result: LabelStoreWriteResult


def ingest_label_from_source(
    *,
    source_class: str,
    source_payload: Mapping[str, Any],
    writer: LabelStoreWriter,
) -> LabelStoreAdapterResult:
    normalized = _normalize_source_class(source_class)
    payload = _as_mapping(source_payload, "source_payload")

    if normalized == "CM_ASSERTION":
        assertion, source_ref_id = _adapt_cm_assertion(payload)
    elif normalized == "EXTERNAL_ADJUDICATION":
        assertion, source_ref_id = _adapt_external_adjudication(payload)
    else:
        assertion, source_ref_id = _adapt_engine_truth(payload)

    write_result = writer.write_label_assertion(assertion.as_dict())
    return LabelStoreAdapterResult(
        source_class=normalized,
        source_ref_id=source_ref_id,
        assertion=assertion,
        write_result=write_result,
    )


def _adapt_cm_assertion(payload: Mapping[str, Any]) -> tuple[LabelAssertion, str]:
    assertion = _parse_assertion(payload, "CM_ASSERTION")
    return assertion, f"case_event:{assertion.case_timeline_event_id}"


def _adapt_external_adjudication(payload: Mapping[str, Any]) -> tuple[LabelAssertion, str]:
    provider = _required_text(
        payload.get("provider_id") or payload.get("provider") or payload.get("external_system"),
        "external.provider_id",
    )
    external_ref_id = _required_text(
        payload.get("external_ref_id") or payload.get("ref_id"),
        "external.external_ref_id",
    )
    label_subject_key = _as_mapping(payload.get("label_subject_key"), "external.label_subject_key")
    pins = _as_mapping(payload.get("pins"), "external.pins")
    label_type = _required_text(payload.get("label_type"), "external.label_type")
    label_value = _required_text(payload.get("label_value"), "external.label_value")
    effective_time = _required_text(payload.get("effective_time"), "external.effective_time")
    observed_time = _required_text(payload.get("observed_time"), "external.observed_time")

    source_ref_id = f"external:{provider}:{external_ref_id}"
    provided_source_type = _optional_text(payload.get("source_type"))
    if provided_source_type and provided_source_type != "EXTERNAL":
        raise LabelStoreAdapterError("external.source_type must be EXTERNAL when provided")
    source_type = "EXTERNAL"
    actor_id = _optional_text(payload.get("actor_id")) or f"EXTERNAL::{provider}"

    evidence_refs = _normalize_evidence_refs(payload.get("evidence_refs"), field_name="external.evidence_refs")
    _append_ref_if_missing(
        evidence_refs,
        ref_type="EXTERNAL_REF",
        ref_id=f"{provider}:{external_ref_id}",
    )
    eb_offset = _optional_text(payload.get("eb_origin_offset"))
    if eb_offset:
        _append_ref_if_missing(evidence_refs, ref_type="EB_ORIGIN_OFFSET", ref_id=eb_offset)

    case_timeline_event_id = _optional_text(payload.get("case_timeline_event_id")) or _derived_case_timeline_event_id(
        writer_namespace=f"external.{provider}",
        source_ref_id=source_ref_id,
        label_subject_key=label_subject_key,
        label_type=label_type,
    )
    assertion_payload = {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": dict(label_subject_key),
        "pins": dict(pins),
        "label_type": label_type,
        "label_value": label_value,
        "effective_time": effective_time,
        "observed_time": observed_time,
        "source_type": source_type,
        "actor_id": actor_id,
        "evidence_refs": evidence_refs,
        "label_payload": _optional_mapping(payload.get("label_payload")),
    }
    assertion = _parse_assertion(assertion_payload, "EXTERNAL_ADJUDICATION")
    return assertion, source_ref_id


def _adapt_engine_truth(payload: Mapping[str, Any]) -> tuple[LabelAssertion, str]:
    bundle_id = _required_text(
        payload.get("engine_bundle_id") or payload.get("bundle_id"),
        "engine.engine_bundle_id",
    )
    truth_record_id = _required_text(
        payload.get("truth_record_id") or payload.get("source_record_id") or payload.get("ref_id"),
        "engine.truth_record_id",
    )
    label_subject_key = _as_mapping(payload.get("label_subject_key"), "engine.label_subject_key")
    pins = _as_mapping(payload.get("pins"), "engine.pins")
    label_type = _required_text(payload.get("label_type"), "engine.label_type")
    label_value = _required_text(payload.get("label_value"), "engine.label_value")
    effective_time = _required_text(payload.get("effective_time"), "engine.effective_time")
    observed_time = _required_text(payload.get("observed_time"), "engine.observed_time")

    source_ref_id = f"engine_truth:{bundle_id}:{truth_record_id}"
    provided_source_type = _optional_text(payload.get("source_type"))
    if provided_source_type and provided_source_type != "SYSTEM":
        raise LabelStoreAdapterError("engine.source_type must be SYSTEM when provided")
    source_type = "SYSTEM"
    actor_id = _optional_text(payload.get("actor_id")) or f"SYSTEM::engine_truth_writer::{bundle_id}"

    evidence_refs = _normalize_evidence_refs(payload.get("evidence_refs"), field_name="engine.evidence_refs")
    _append_ref_if_missing(evidence_refs, ref_type="EXTERNAL_REF", ref_id=source_ref_id)
    decision_id = _optional_text(payload.get("decision_id"))
    if decision_id:
        _append_ref_if_missing(evidence_refs, ref_type="DECISION", ref_id=decision_id)
    audit_record_id = _optional_text(payload.get("audit_record_id"))
    if audit_record_id:
        _append_ref_if_missing(evidence_refs, ref_type="DLA_AUDIT_RECORD", ref_id=audit_record_id)
    action_outcome_id = _optional_text(payload.get("action_outcome_id"))
    if action_outcome_id:
        _append_ref_if_missing(evidence_refs, ref_type="ACTION_OUTCOME", ref_id=action_outcome_id)
    eb_offset = _optional_text(payload.get("eb_origin_offset"))
    if eb_offset:
        _append_ref_if_missing(evidence_refs, ref_type="EB_ORIGIN_OFFSET", ref_id=eb_offset)

    case_timeline_event_id = _optional_text(payload.get("case_timeline_event_id")) or _derived_case_timeline_event_id(
        writer_namespace=f"engine_truth.{bundle_id}",
        source_ref_id=source_ref_id,
        label_subject_key=label_subject_key,
        label_type=label_type,
    )
    assertion_payload = {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": dict(label_subject_key),
        "pins": dict(pins),
        "label_type": label_type,
        "label_value": label_value,
        "effective_time": effective_time,
        "observed_time": observed_time,
        "source_type": source_type,
        "actor_id": actor_id,
        "evidence_refs": evidence_refs,
        "label_payload": _optional_mapping(payload.get("label_payload")),
    }
    assertion = _parse_assertion(assertion_payload, "ENGINE_TRUTH")
    return assertion, source_ref_id


def _parse_assertion(payload: Mapping[str, Any], lane: str) -> LabelAssertion:
    try:
        return LabelAssertion.from_payload(payload)
    except LabelStoreContractError as exc:
        raise LabelStoreAdapterError(f"{lane} payload failed LabelAssertion contract validation: {exc}") from exc


def _normalize_source_class(source_class: str) -> str:
    normalized = _required_text(source_class, "source_class")
    if normalized not in SUPPORTED_INGEST_SOURCE_CLASSES:
        raise LabelStoreAdapterError(
            f"unsupported source_class={normalized!r}; expected one of {sorted(SUPPORTED_INGEST_SOURCE_CLASSES)!r}"
        )
    return normalized


def _derived_case_timeline_event_id(
    *,
    writer_namespace: str,
    source_ref_id: str,
    label_subject_key: Mapping[str, Any],
    label_type: str,
) -> str:
    canonical = _canonical_json(
        {
            "recipe": DERIVED_CASE_EVENT_RECIPE_V1,
            "payload": {
                "writer_namespace": str(writer_namespace),
                "source_ref_id": str(source_ref_id),
                "label_subject_key": {
                    "platform_run_id": str(label_subject_key.get("platform_run_id") or ""),
                    "event_id": str(label_subject_key.get("event_id") or ""),
                },
                "label_type": str(label_type),
            },
        }
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _normalize_evidence_refs(value: Any, *, field_name: str) -> list[dict[str, str]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise LabelStoreAdapterError(f"{field_name} must be a list when provided")
    refs: list[dict[str, str]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise LabelStoreAdapterError(f"{field_name}[{idx}] must be a mapping")
        ref_type = _required_text(item.get("ref_type"), f"{field_name}[{idx}].ref_type")
        ref_id = _required_text(item.get("ref_id"), f"{field_name}[{idx}].ref_id")
        ref_scope = _optional_text(item.get("ref_scope"))
        row = {"ref_type": ref_type, "ref_id": ref_id}
        if ref_scope:
            row["ref_scope"] = ref_scope
        refs.append(row)
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"], str(item.get("ref_scope") or "")))
    return refs


def _append_ref_if_missing(refs: list[dict[str, str]], *, ref_type: str, ref_id: str) -> None:
    for item in refs:
        if item.get("ref_type") == ref_type and item.get("ref_id") == ref_id:
            return
    refs.append({"ref_type": str(ref_type), "ref_id": str(ref_id)})
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"], str(item.get("ref_scope") or "")))


def _as_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise LabelStoreAdapterError(f"{field_name} must be a mapping")
    return dict(value)


def _optional_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LabelStoreAdapterError(f"{field_name} is required")
    return text


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

