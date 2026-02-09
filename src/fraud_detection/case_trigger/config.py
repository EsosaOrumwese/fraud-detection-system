"""CaseTrigger trigger policy loader (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from fraud_detection.case_mgmt.contracts import EVIDENCE_REF_TYPES as SUPPORTED_EVIDENCE_REF_TYPES

from .taxonomy import (
    SUPPORTED_CASE_TRIGGER_TYPES,
    ensure_supported_case_trigger_type,
    ensure_supported_source_class,
)


@dataclass(frozen=True)
class CaseTriggerRule:
    trigger_type: str
    source_classes: tuple[str, ...]
    required_evidence_ref_types: tuple[str, ...]


@dataclass(frozen=True)
class CaseTriggerPolicy:
    version: str
    policy_id: str
    revision: str
    trigger_rules: tuple[CaseTriggerRule, ...]
    required_pins: tuple[str, ...]
    require_seed: bool
    content_digest: str

    def rule_for_trigger_type(self, trigger_type: str) -> CaseTriggerRule | None:
        normalized = str(trigger_type or "").strip()
        for rule in self.trigger_rules:
            if rule.trigger_type == normalized:
                return rule
        return None

    def missing_required_pins(self, pins: dict[str, Any]) -> list[str]:
        missing = [pin for pin in self.required_pins if pins.get(pin) in (None, "")]
        if not self.require_seed and "seed" in missing:
            missing = [item for item in missing if item != "seed"]
        return missing


class CaseTriggerConfigError(ValueError):
    """Raised when CaseTrigger trigger policy payloads are invalid."""


def load_trigger_policy(path: Path) -> CaseTriggerPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaseTriggerConfigError("CaseTrigger trigger policy must be a mapping")

    version = str(payload.get("version") or "").strip()
    policy_id = str(payload.get("policy_id") or "").strip()
    revision = str(payload.get("revision") or "").strip()
    if not version or not policy_id or not revision:
        raise CaseTriggerConfigError(
            "CaseTrigger trigger policy requires version, policy_id, revision"
        )

    trigger_policy = payload.get("case_trigger")
    if not isinstance(trigger_policy, dict):
        raise CaseTriggerConfigError("case_trigger must be a mapping")

    trigger_rules = _parse_trigger_rules(trigger_policy.get("trigger_rules"))
    required_pins = tuple(
        sorted(
            {
                item
                for item in _to_non_empty_list(
                    trigger_policy.get("required_pins"),
                    "required_pins",
                )
            }
        )
    )
    require_seed = bool(trigger_policy.get("require_seed", True))

    configured = {rule.trigger_type for rule in trigger_rules}
    missing = sorted(set(SUPPORTED_CASE_TRIGGER_TYPES) - configured)
    if missing:
        raise CaseTriggerConfigError(
            "trigger_rules must define all supported trigger types; "
            f"missing={missing!r}"
        )

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "trigger_rules": [
            {
                "trigger_type": rule.trigger_type,
                "source_classes": list(rule.source_classes),
                "required_evidence_ref_types": list(rule.required_evidence_ref_types),
            }
            for rule in sorted(trigger_rules, key=lambda item: item.trigger_type)
        ],
        "required_pins": list(required_pins),
        "require_seed": require_seed,
    }
    canonical = json.dumps(
        digest_payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return CaseTriggerPolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        trigger_rules=tuple(sorted(trigger_rules, key=lambda item: item.trigger_type)),
        required_pins=required_pins,
        require_seed=require_seed,
        content_digest=content_digest,
    )


def _parse_trigger_rules(value: Any) -> tuple[CaseTriggerRule, ...]:
    if not isinstance(value, list) or not value:
        raise CaseTriggerConfigError("trigger_rules must be a non-empty list")
    rules: list[CaseTriggerRule] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise CaseTriggerConfigError(f"trigger_rules[{index}] must be a mapping")
        trigger_type = ensure_supported_case_trigger_type(item.get("trigger_type"))
        if trigger_type in seen:
            raise CaseTriggerConfigError(
                "trigger_rules contains duplicate trigger_type: "
                f"{trigger_type!r}"
            )
        source_classes = tuple(
            sorted(
                {
                    ensure_supported_source_class(source_class)
                    for source_class in _to_non_empty_list(
                        item.get("source_classes"),
                        f"trigger_rules[{index}].source_classes",
                    )
                }
            )
        )
        required_evidence_ref_types = tuple(
            sorted(
                {
                    _ensure_supported_evidence_ref_type(ref_type)
                    for ref_type in _to_non_empty_list(
                        item.get("required_evidence_ref_types"),
                        f"trigger_rules[{index}].required_evidence_ref_types",
                    )
                }
            )
        )
        seen.add(trigger_type)
        rules.append(
            CaseTriggerRule(
                trigger_type=trigger_type,
                source_classes=source_classes,
                required_evidence_ref_types=required_evidence_ref_types,
            )
        )
    return tuple(rules)


def _to_non_empty_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise CaseTriggerConfigError(f"{field_name} must be a non-empty list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        text = str(item or "").strip()
        if not text:
            raise CaseTriggerConfigError(f"{field_name}[{index}] must be non-empty")
        normalized.append(text)
    return normalized


def _ensure_supported_evidence_ref_type(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in SUPPORTED_EVIDENCE_REF_TYPES:
        raise CaseTriggerConfigError(
            "unsupported required_evidence_ref_type in policy: "
            f"{normalized!r}; allowed={sorted(SUPPORTED_EVIDENCE_REF_TYPES)!r}"
        )
    return normalized
