"""Deterministic identity helpers for Offline Feature Plane Phase 1."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


OFS_DATASET_FINGERPRINT_RECIPE_V1 = "ofs.dataset_fingerprint.v1"
OFS_DATASET_MANIFEST_ID_RECIPE_V1 = "ofs.dataset_manifest_id.v1"


def canonical_dataset_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(identity, Mapping):
        raise ValueError("identity must be a mapping")
    replay_basis = _normalize_replay_basis(identity.get("replay_basis"))
    normalized = {
        "platform_run_id": str(identity.get("platform_run_id") or ""),
        "scenario_run_ids": _normalize_strings(identity.get("scenario_run_ids")),
        "replay_basis": replay_basis,
        "label_basis": _normalize_mapping(identity.get("label_basis")),
        "feature_definition_set": _normalize_mapping(identity.get("feature_definition_set")),
        "join_scope": _normalize_mapping(identity.get("join_scope")),
        "filters": _normalize_mapping(identity.get("filters")),
        "policy_revision": str(identity.get("policy_revision") or ""),
        "config_revision": str(identity.get("config_revision") or ""),
        "ofs_code_release_id": str(identity.get("ofs_code_release_id") or ""),
    }
    return _normalize_generic(normalized)


def dataset_fingerprint(identity: Mapping[str, Any]) -> str:
    canonical = canonical_dataset_identity(identity)
    payload = {"recipe": OFS_DATASET_FINGERPRINT_RECIPE_V1, "payload": canonical}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def deterministic_dataset_manifest_id(dataset_fingerprint_value: str) -> str:
    fingerprint = str(dataset_fingerprint_value or "").strip()
    if len(fingerprint) < 8:
        raise ValueError("dataset_fingerprint must be at least 8 characters")
    payload = {
        "recipe": OFS_DATASET_MANIFEST_ID_RECIPE_V1,
        "payload": {"dataset_fingerprint": fingerprint},
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"dm_{digest[:32]}"


def _normalize_replay_basis(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "topic": str(item.get("topic") or ""),
                "partition": int(item.get("partition") or 0),
                "offset_kind": str(item.get("offset_kind") or ""),
                "start_offset": str(item.get("start_offset") or ""),
                "end_offset": str(item.get("end_offset") or ""),
            }
        )
    rows.sort(
        key=lambda row: (
            row["topic"],
            row["partition"],
            row["offset_kind"],
            row["start_offset"],
            row["end_offset"],
        )
    )
    return rows


def _normalize_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    return sorted(items)


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
