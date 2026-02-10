"""Decision Fabric trigger policy loader (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DecisionTriggerRule:
    event_type: str
    schema_versions: tuple[str, ...]


@dataclass(frozen=True)
class DecisionTriggerPolicy:
    version: str
    policy_id: str
    revision: str
    admitted_traffic_topics: tuple[str, ...]
    trigger_rules: tuple[DecisionTriggerRule, ...]
    blocked_event_types: tuple[str, ...]
    blocked_event_type_prefixes: tuple[str, ...]
    required_pins: tuple[str, ...]
    require_seed: bool
    content_digest: str

    def allowed_schema_versions(self, event_type: str) -> tuple[str, ...] | None:
        normalized = str(event_type or "").strip()
        for rule in self.trigger_rules:
            if rule.event_type == normalized:
                return rule.schema_versions
        return None

    def is_blocked_event_type(self, event_type: str) -> bool:
        normalized = str(event_type or "").strip()
        if not normalized:
            return False
        if normalized in self.blocked_event_types:
            return True
        for prefix in self.blocked_event_type_prefixes:
            if normalized.startswith(prefix):
                return True
        return False

    def missing_required_pins(self, envelope: dict[str, Any]) -> list[str]:
        missing = [pin for pin in self.required_pins if envelope.get(pin) in (None, "")]
        if not self.require_seed and "seed" in missing:
            missing = [pin for pin in missing if pin != "seed"]
        return missing


class DecisionFabricConfigError(ValueError):
    """Raised when DF trigger policy payloads are invalid."""


def load_trigger_policy(path: Path) -> DecisionTriggerPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DecisionFabricConfigError("DF trigger policy must be a mapping")

    version = str(payload.get("version") or "").strip()
    policy_id = str(payload.get("policy_id") or "").strip()
    revision = str(payload.get("revision") or "").strip()
    if not version or not policy_id or not revision:
        raise DecisionFabricConfigError("DF trigger policy requires version, policy_id, revision")

    decision_trigger = payload.get("decision_trigger")
    if not isinstance(decision_trigger, dict):
        raise DecisionFabricConfigError("decision_trigger must be a mapping")

    topics = _to_non_empty_list(decision_trigger.get("admitted_traffic_topics"), "admitted_traffic_topics")
    trigger_rules = _parse_trigger_rules(decision_trigger.get("trigger_allowlist"))

    blocked_event_types = tuple(
        sorted({item for item in _to_non_empty_list(decision_trigger.get("blocked_event_types"), "blocked_event_types")})
    )
    blocked_event_type_prefixes = tuple(
        sorted(
            {
                item
                for item in _to_non_empty_list(
                    decision_trigger.get("blocked_event_type_prefixes"),
                    "blocked_event_type_prefixes",
                )
            }
        )
    )
    required_pins = tuple(
        sorted({item for item in _to_non_empty_list(decision_trigger.get("required_pins"), "required_pins")})
    )
    require_seed = bool(decision_trigger.get("require_seed", True))

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "admitted_traffic_topics": sorted(topics),
        "trigger_allowlist": [
            {"event_type": rule.event_type, "schema_versions": list(rule.schema_versions)}
            for rule in sorted(trigger_rules, key=lambda item: item.event_type)
        ],
        "blocked_event_types": list(blocked_event_types),
        "blocked_event_type_prefixes": list(blocked_event_type_prefixes),
        "required_pins": list(required_pins),
        "require_seed": require_seed,
    }
    canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return DecisionTriggerPolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        admitted_traffic_topics=tuple(sorted(topics)),
        trigger_rules=tuple(sorted(trigger_rules, key=lambda item: item.event_type)),
        blocked_event_types=blocked_event_types,
        blocked_event_type_prefixes=blocked_event_type_prefixes,
        required_pins=required_pins,
        require_seed=require_seed,
        content_digest=content_digest,
    )


def _parse_trigger_rules(value: Any) -> tuple[DecisionTriggerRule, ...]:
    if not isinstance(value, list) or not value:
        raise DecisionFabricConfigError("trigger_allowlist must be a non-empty list")
    rules: list[DecisionTriggerRule] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DecisionFabricConfigError(f"trigger_allowlist[{index}] must be a mapping")
        event_type = str(item.get("event_type") or "").strip()
        if not event_type:
            raise DecisionFabricConfigError(f"trigger_allowlist[{index}] missing event_type")
        if event_type in seen:
            raise DecisionFabricConfigError(f"trigger_allowlist contains duplicate event_type: {event_type}")
        schema_versions = _to_non_empty_list(item.get("schema_versions"), f"trigger_allowlist[{index}].schema_versions")
        seen.add(event_type)
        rules.append(DecisionTriggerRule(event_type=event_type, schema_versions=tuple(sorted(set(schema_versions)))))
    return tuple(rules)


def _to_non_empty_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DecisionFabricConfigError(f"{field_name} must be a non-empty list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        text = str(item or "").strip()
        if not text:
            raise DecisionFabricConfigError(f"{field_name}[{index}] must be non-empty")
        normalized.append(text)
    return normalized
