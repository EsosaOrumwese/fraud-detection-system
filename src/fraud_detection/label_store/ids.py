"""Deterministic identity and payload hashing helpers for Label Store."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


LABEL_ASSERTION_ID_RECIPE_V1 = "ls.label_assertion_id.v1"
LABEL_ASSERTION_PAYLOAD_HASH_RECIPE_V1 = "ls.label_assertion_payload_hash.v1"

LABEL_SUBJECT_KEY_FIELDS: tuple[str, ...] = ("platform_run_id", "event_id")


def deterministic_label_assertion_id(
    *,
    case_timeline_event_id: str,
    label_subject_key: Mapping[str, Any],
    label_type: str,
) -> str:
    payload = {
        "case_timeline_event_id": str(case_timeline_event_id),
        "label_subject_key": _stable_label_subject_key(label_subject_key),
        "label_type": str(label_type),
    }
    return _hash_with_recipe(LABEL_ASSERTION_ID_RECIPE_V1, payload)[:32]


def canonical_label_assertion_payload_hash(
    *,
    label_subject_key: Mapping[str, Any],
    label_type: str,
    label_value: str,
    effective_time: str,
    observed_time: str,
    source_type: str,
    actor_id: str | None,
    evidence_refs: list[Mapping[str, Any]],
) -> str:
    normalized = {
        "label_subject_key": _stable_label_subject_key(label_subject_key),
        "label_type": str(label_type),
        "label_value": str(label_value),
        "effective_time": str(effective_time),
        "observed_time": str(observed_time),
        "source_type": str(source_type),
        "actor_id": str(actor_id or ""),
        "evidence_refs": _normalize_evidence_refs(evidence_refs),
    }
    return _hash_with_recipe(LABEL_ASSERTION_PAYLOAD_HASH_RECIPE_V1, normalized)


def _stable_label_subject_key(subject: Mapping[str, Any]) -> dict[str, str]:
    return {field: str(subject.get(field) or "") for field in LABEL_SUBJECT_KEY_FIELDS}


def _normalize_evidence_refs(value: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for item in value:
        refs.append(
            {
                "ref_type": str(item.get("ref_type") or ""),
                "ref_id": str(item.get("ref_id") or ""),
                "ref_scope": str(item.get("ref_scope") or ""),
            }
        )
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"], item["ref_scope"]))
    return refs


def _hash_with_recipe(recipe: str, payload: Mapping[str, Any]) -> str:
    canonical = _canonical_json({"recipe": recipe, "payload": _normalize_generic(dict(payload))})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
