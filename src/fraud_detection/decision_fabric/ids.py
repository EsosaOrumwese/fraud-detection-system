"""Deterministic identity helpers for Decision Fabric artifacts (Phase 1)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


DECISION_ID_RECIPE_V1 = "df.decision_id.v2"
DECISION_RESPONSE_EVENT_ID_RECIPE_V1 = "df.decision_response.event_id.v1"
ACTION_INTENT_EVENT_ID_RECIPE_V1 = "df.action_intent.event_id.v1"
ACTION_INTENT_IDEMPOTENCY_RECIPE_V1 = "df.action_intent.idempotency_key.v1"

PIN_SCOPE_FIELDS: tuple[str, ...] = (
    "platform_run_id",
    "scenario_run_id",
    "manifest_fingerprint",
    "parameter_hash",
    "scenario_id",
    "seed",
)


def deterministic_decision_id(
    *,
    source_event_id: str,
    platform_run_id: str,
    decision_scope: str,
    bundle_ref: Mapping[str, Any],
    origin_offset: Mapping[str, Any],
) -> str:
    """Build deterministic 32-hex decision_id for a source event and decision basis."""
    payload = {
        "source_event_id": str(source_event_id),
        "platform_run_id": str(platform_run_id),
        "decision_scope": str(decision_scope),
        "bundle_ref": _stable_bundle_ref(bundle_ref),
        "origin_offset": _stable_origin_offset(origin_offset),
    }
    return _hash_with_recipe(DECISION_ID_RECIPE_V1, payload)[:32]


def deterministic_decision_response_event_id(
    *,
    source_event_id: str,
    decision_scope: str,
    pins: Mapping[str, Any],
) -> str:
    payload = {
        "source_event_id": str(source_event_id),
        "decision_scope": str(decision_scope),
        "pin_scope": _stable_pin_scope(pins),
    }
    return _hash_with_recipe(DECISION_RESPONSE_EVENT_ID_RECIPE_V1, payload)


def deterministic_action_intent_event_id(
    *,
    source_event_id: str,
    action_domain: str,
    pins: Mapping[str, Any],
) -> str:
    payload = {
        "source_event_id": str(source_event_id),
        "action_domain": str(action_domain),
        "pin_scope": _stable_pin_scope(pins),
    }
    return _hash_with_recipe(ACTION_INTENT_EVENT_ID_RECIPE_V1, payload)


def deterministic_action_idempotency_key(
    *,
    source_event_id: str,
    action_domain: str,
    pins: Mapping[str, Any],
) -> str:
    payload = {
        "source_event_id": str(source_event_id),
        "action_domain": str(action_domain),
        "pin_scope": _stable_pin_scope(pins),
    }
    return _hash_with_recipe(ACTION_INTENT_IDEMPOTENCY_RECIPE_V1, payload)


def _hash_with_recipe(recipe: str, payload: Mapping[str, Any]) -> str:
    canonical = _canonical_json({"recipe": recipe, "payload": dict(payload)})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stable_pin_scope(pins: Mapping[str, Any]) -> dict[str, str]:
    return {key: str(pins.get(key) or "") for key in PIN_SCOPE_FIELDS}


def _stable_bundle_ref(bundle_ref: Mapping[str, Any]) -> dict[str, str]:
    return {
        "bundle_id": str(bundle_ref.get("bundle_id") or ""),
        "bundle_version": str(bundle_ref.get("bundle_version") or ""),
        "registry_ref": str(bundle_ref.get("registry_ref") or ""),
    }


def _stable_origin_offset(origin_offset: Mapping[str, Any]) -> dict[str, Any]:
    topic = str(origin_offset.get("topic") or origin_offset.get("stream") or "").strip()
    partition = int(origin_offset.get("partition", 0))
    return {
        "topic": topic,
        "partition": partition,
        "offset": str(origin_offset.get("offset") or ""),
        "offset_kind": str(origin_offset.get("offset_kind") or ""),
    }


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
