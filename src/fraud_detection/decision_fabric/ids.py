"""Deterministic identity helpers for Decision Fabric artifacts (Phase 1)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


DECISION_ID_RECIPE_V1 = "df.decision_id.v1"
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
    decision_scope: str,
    bundle_ref: Mapping[str, Any],
    eb_offset_basis: Mapping[str, Any],
) -> str:
    """Build deterministic 32-hex decision_id for a source event and decision basis."""
    payload = {
        "source_event_id": str(source_event_id),
        "decision_scope": str(decision_scope),
        "bundle_ref": _stable_bundle_ref(bundle_ref),
        "eb_offset_basis": _stable_eb_offset_basis(eb_offset_basis),
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


def _stable_eb_offset_basis(eb_offset_basis: Mapping[str, Any]) -> dict[str, Any]:
    offsets_raw = eb_offset_basis.get("offsets")
    offsets: list[dict[str, Any]] = []
    if isinstance(offsets_raw, list):
        offsets = sorted(
            [
                {
                    "partition": int(item.get("partition", 0)),
                    "offset": str(item.get("offset") or ""),
                }
                for item in offsets_raw
                if isinstance(item, Mapping)
            ],
            key=lambda item: (item["partition"], item["offset"]),
        )
    return {
        "stream": str(eb_offset_basis.get("stream") or ""),
        "offset_kind": str(eb_offset_basis.get("offset_kind") or ""),
        "basis_digest": str(eb_offset_basis.get("basis_digest") or ""),
        "offsets": offsets,
    }


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
