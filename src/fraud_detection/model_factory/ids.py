"""Deterministic identity helpers for Model Factory Phase 1."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


MF_TRAIN_RUN_KEY_RECIPE_V1 = "mf.train_run_key.v1"
MF_TRAIN_RUN_ID_RECIPE_V1 = "mf.train_run_id.v1"


def canonical_train_run_key_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return canonical TrainRunKey payload for deterministic identity."""
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    normalized = {
        "intent_kind": str(payload.get("intent_kind") or ""),
        "platform_run_id": str(payload.get("platform_run_id") or ""),
        "dataset_manifest_refs": _normalize_strings(payload.get("dataset_manifest_refs")),
        "training_config_ref": str(payload.get("training_config_ref") or ""),
        "governance_profile_ref": str(payload.get("governance_profile_ref") or ""),
        "target_scope": _normalize_mapping(payload.get("target_scope")),
        "policy_revision": str(payload.get("policy_revision") or ""),
        "config_revision": str(payload.get("config_revision") or ""),
        "mf_code_release_id": str(payload.get("mf_code_release_id") or ""),
    }
    return _normalize_generic(normalized)


def train_run_key(payload: Mapping[str, Any]) -> str:
    canonical = canonical_train_run_key_payload(payload)
    envelope = {"recipe": MF_TRAIN_RUN_KEY_RECIPE_V1, "payload": canonical}
    encoded = json.dumps(envelope, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def deterministic_train_run_id(train_run_key_value: str) -> str:
    key = str(train_run_key_value or "").strip()
    if len(key) < 8:
        raise ValueError("train_run_key must be at least 8 characters")
    envelope = {
        "recipe": MF_TRAIN_RUN_ID_RECIPE_V1,
        "payload": {"train_run_key": key},
    }
    encoded = json.dumps(envelope, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"tr_{digest[:32]}"


def _normalize_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = sorted({str(item).strip() for item in value if str(item).strip()})
    return items


def _normalize_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _normalize_generic(dict(value))


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

