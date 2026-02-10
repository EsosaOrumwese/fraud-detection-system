"""Context Store + FlowBinding policy loader (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .taxonomy import ensure_authoritative_flow_binding_event_type


class ContextStoreFlowBindingConfigError(ValueError):
    """Raised when CSFB policy config is invalid."""


@dataclass(frozen=True)
class ContextStoreFlowBindingPolicy:
    version: str
    policy_id: str
    revision: str
    query_schema_version: str
    required_pins: tuple[str, ...]
    require_seed: bool
    authoritative_flow_binding_event_types: tuple[str, ...]
    content_digest: str


def load_policy(path: Path) -> ContextStoreFlowBindingPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContextStoreFlowBindingConfigError("CSFB policy must be a mapping")

    version = _require_non_empty_str(payload.get("version"), "version")
    policy_id = _require_non_empty_str(payload.get("policy_id"), "policy_id")
    revision = _require_non_empty_str(payload.get("revision"), "revision")
    query_schema_version = _require_non_empty_str(payload.get("query_schema_version"), "query_schema_version")
    required_pins = tuple(_load_required_pins(payload.get("required_pins")))
    require_seed = bool(payload.get("require_seed", True))
    if require_seed and "seed" not in required_pins:
        raise ContextStoreFlowBindingConfigError(
            "required_pins must include seed when require_seed=true"
        )
    authoritative = tuple(_load_authoritative_event_types(payload.get("authoritative_flow_binding_event_types")))

    canonical_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "query_schema_version": query_schema_version,
        "required_pins": list(required_pins),
        "require_seed": require_seed,
        "authoritative_flow_binding_event_types": list(authoritative),
    }
    canonical = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return ContextStoreFlowBindingPolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        query_schema_version=query_schema_version,
        required_pins=required_pins,
        require_seed=require_seed,
        authoritative_flow_binding_event_types=authoritative,
        content_digest=content_digest,
    )


def _load_required_pins(value: Any) -> list[str]:
    pins = _as_non_empty_list(value, "required_pins")
    normalized = [_require_non_empty_str(item, f"required_pins[{index}]") for index, item in enumerate(pins)]
    unique = sorted(set(normalized))
    required = {
        "platform_run_id",
        "scenario_run_id",
        "manifest_fingerprint",
        "parameter_hash",
        "scenario_id",
    }
    if not required.issubset(set(unique)):
        missing = sorted(required - set(unique))
        raise ContextStoreFlowBindingConfigError(
            f"required_pins missing mandatory entries: {','.join(missing)}"
        )
    return unique


def _load_authoritative_event_types(value: Any) -> list[str]:
    entries = _as_non_empty_list(value, "authoritative_flow_binding_event_types")
    normalized = []
    for index, item in enumerate(entries):
        event_type = _require_non_empty_str(item, f"authoritative_flow_binding_event_types[{index}]")
        try:
            normalized.append(ensure_authoritative_flow_binding_event_type(event_type))
        except ValueError as exc:
            raise ContextStoreFlowBindingConfigError(str(exc)) from exc
    return sorted(set(normalized))


def _as_non_empty_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ContextStoreFlowBindingConfigError(f"{field_name} must be a non-empty list")
    return list(value)


def _require_non_empty_str(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContextStoreFlowBindingConfigError(f"{field_name} must be non-empty")
    return text
