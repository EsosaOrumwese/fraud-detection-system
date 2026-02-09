"""Deterministic identity and canonical hashing helpers for Case Management."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


CASE_ID_RECIPE_V1 = "cm.case_id.v1"
CASE_TRIGGER_ID_RECIPE_V1 = "cm.case_trigger_id.v1"
CASE_TIMELINE_EVENT_ID_RECIPE_V1 = "cm.case_timeline_event_id.v1"
CASE_TRIGGER_PAYLOAD_HASH_RECIPE_V1 = "cm.case_trigger_payload_hash.v1"
CASE_TIMELINE_PAYLOAD_HASH_RECIPE_V1 = "cm.case_timeline_payload_hash.v1"

CASE_SUBJECT_KEY_FIELDS: tuple[str, ...] = (
    "platform_run_id",
    "event_class",
    "event_id",
)


def deterministic_case_id(*, case_subject_key: Mapping[str, Any]) -> str:
    stable_subject = _stable_case_subject_key(case_subject_key)
    return _hash_with_recipe(CASE_ID_RECIPE_V1, stable_subject)[:32]


def deterministic_case_trigger_id(
    *,
    case_id: str,
    trigger_type: str,
    source_ref_id: str,
) -> str:
    payload = {
        "case_id": str(case_id),
        "trigger_type": str(trigger_type),
        "source_ref_id": str(source_ref_id),
    }
    return _hash_with_recipe(CASE_TRIGGER_ID_RECIPE_V1, payload)[:32]


def deterministic_case_timeline_event_id(
    *,
    case_id: str,
    timeline_event_type: str,
    source_ref_id: str,
) -> str:
    payload = {
        "case_id": str(case_id),
        "timeline_event_type": str(timeline_event_type),
        "source_ref_id": str(source_ref_id),
    }
    return _hash_with_recipe(CASE_TIMELINE_EVENT_ID_RECIPE_V1, payload)[:32]


def canonical_case_trigger_payload_hash(payload: Mapping[str, Any]) -> str:
    normalized = {
        "case_subject_key": _stable_case_subject_key(_as_mapping(payload.get("case_subject_key"))),
        "trigger_type": str(payload.get("trigger_type") or ""),
        "source_ref_id": str(payload.get("source_ref_id") or ""),
        "pins": _normalize_pins(payload.get("pins")),
        "observed_time": str(payload.get("observed_time") or ""),
        "evidence_refs": _normalize_evidence_refs(payload.get("evidence_refs")),
        "trigger_payload": _normalize_generic(payload.get("trigger_payload") or {}),
    }
    return _hash_with_recipe(CASE_TRIGGER_PAYLOAD_HASH_RECIPE_V1, normalized)


def canonical_case_timeline_payload_hash(payload: Mapping[str, Any]) -> str:
    normalized = {
        "case_id": str(payload.get("case_id") or ""),
        "timeline_event_type": str(payload.get("timeline_event_type") or ""),
        "source_ref_id": str(payload.get("source_ref_id") or ""),
        "pins": _normalize_pins(payload.get("pins")),
        "observed_time": str(payload.get("observed_time") or ""),
        "evidence_refs": _normalize_evidence_refs(payload.get("evidence_refs")),
        "timeline_payload": _normalize_generic(payload.get("timeline_payload") or {}),
        "case_subject_key": _normalize_optional_subject(payload.get("case_subject_key")),
    }
    return _hash_with_recipe(CASE_TIMELINE_PAYLOAD_HASH_RECIPE_V1, normalized)


def _normalize_optional_subject(value: Any) -> dict[str, str] | None:
    if value in (None, ""):
        return None
    return _stable_case_subject_key(_as_mapping(value))


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _stable_case_subject_key(subject: Mapping[str, Any]) -> dict[str, str]:
    return {field: str(subject.get(field) or "") for field in CASE_SUBJECT_KEY_FIELDS}


def _normalize_pins(value: Any) -> dict[str, Any]:
    return _normalize_generic(_as_mapping(value))


def _normalize_evidence_refs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        refs.append(
            {
                "ref_type": str(item.get("ref_type") or ""),
                "ref_id": str(item.get("ref_id") or ""),
                "ref_scope": str(item.get("ref_scope") or ""),
            }
        )
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"], item["ref_scope"]))
    return refs


def _normalize_generic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_generic(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_normalize_generic(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _hash_with_recipe(recipe: str, payload: Mapping[str, Any]) -> str:
    canonical = _canonical_json({"recipe": recipe, "payload": _normalize_generic(dict(payload))})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
