"""Decision Log & Audit intake policy loader (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DecisionLogAuditIntakeRule:
    event_type: str
    schema_versions: tuple[str, ...]
    payload_contract: str


@dataclass(frozen=True)
class DecisionLogAuditIntakePolicy:
    version: str
    policy_id: str
    revision: str
    admitted_topics: tuple[str, ...]
    rules: tuple[DecisionLogAuditIntakeRule, ...]
    required_pins: tuple[str, ...]
    require_seed: bool
    required_platform_run_id: str | None
    content_digest: str

    def allowed_schema_versions(self, event_type: str) -> tuple[str, ...] | None:
        normalized = str(event_type or "").strip()
        for rule in self.rules:
            if rule.event_type == normalized:
                return rule.schema_versions
        return None

    def payload_contract(self, event_type: str) -> str | None:
        normalized = str(event_type or "").strip()
        for rule in self.rules:
            if rule.event_type == normalized:
                return rule.payload_contract
        return None

    def missing_required_pins(self, envelope: dict[str, Any]) -> list[str]:
        missing = [pin for pin in self.required_pins if envelope.get(pin) in (None, "")]
        if not self.require_seed and "seed" in missing:
            missing = [pin for pin in missing if pin != "seed"]
        return missing


class DecisionLogAuditConfigError(ValueError):
    """Raised when DLA intake policy payloads are invalid."""


def load_intake_policy(path: Path) -> DecisionLogAuditIntakePolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DecisionLogAuditConfigError("DLA intake policy must be a mapping")

    version = str(payload.get("version") or "").strip()
    policy_id = str(payload.get("policy_id") or "").strip()
    revision = str(payload.get("revision") or "").strip()
    if not version or not policy_id or not revision:
        raise DecisionLogAuditConfigError("DLA intake policy requires version, policy_id, revision")

    intake = payload.get("intake")
    if not isinstance(intake, dict):
        raise DecisionLogAuditConfigError("intake must be a mapping")

    admitted_topics = _to_non_empty_list(intake.get("admitted_topics"), "admitted_topics")
    rules = _parse_rules(intake.get("event_allowlist"))
    required_pins = tuple(sorted(set(_to_non_empty_list(intake.get("required_pins"), "required_pins"))))
    require_seed = bool(intake.get("require_seed", True))
    required_platform_run_id_raw = str(intake.get("required_platform_run_id") or "").strip()
    required_platform_run_id = required_platform_run_id_raw or None

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "admitted_topics": sorted(admitted_topics),
        "event_allowlist": [
            {
                "event_type": item.event_type,
                "schema_versions": list(item.schema_versions),
                "payload_contract": item.payload_contract,
            }
            for item in sorted(rules, key=lambda value: value.event_type)
        ],
        "required_pins": list(required_pins),
        "require_seed": require_seed,
        "required_platform_run_id": required_platform_run_id,
    }
    canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return DecisionLogAuditIntakePolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        admitted_topics=tuple(sorted(admitted_topics)),
        rules=tuple(sorted(rules, key=lambda value: value.event_type)),
        required_pins=required_pins,
        require_seed=require_seed,
        required_platform_run_id=required_platform_run_id,
        content_digest=content_digest,
    )


def _parse_rules(value: Any) -> tuple[DecisionLogAuditIntakeRule, ...]:
    if not isinstance(value, list) or not value:
        raise DecisionLogAuditConfigError("event_allowlist must be a non-empty list")
    rules: list[DecisionLogAuditIntakeRule] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DecisionLogAuditConfigError(f"event_allowlist[{index}] must be a mapping")
        event_type = str(item.get("event_type") or "").strip()
        if not event_type:
            raise DecisionLogAuditConfigError(f"event_allowlist[{index}] missing event_type")
        if event_type in seen:
            raise DecisionLogAuditConfigError(f"event_allowlist contains duplicate event_type: {event_type}")
        schema_versions = tuple(sorted(set(_to_non_empty_list(item.get("schema_versions"), f"event_allowlist[{index}].schema_versions"))))
        payload_contract = str(item.get("payload_contract") or "").strip()
        if not payload_contract:
            raise DecisionLogAuditConfigError(f"event_allowlist[{index}] missing payload_contract")
        seen.add(event_type)
        rules.append(
            DecisionLogAuditIntakeRule(
                event_type=event_type,
                schema_versions=schema_versions,
                payload_contract=payload_contract,
            )
        )
    return tuple(rules)


def _to_non_empty_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DecisionLogAuditConfigError(f"{field_name} must be a non-empty list")
    normalized: list[str] = []
    for index, item in enumerate(value):
        text = str(item or "").strip()
        if not text:
            raise DecisionLogAuditConfigError(f"{field_name}[{index}] must be non-empty")
        normalized.append(text)
    return normalized
