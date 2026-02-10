"""Identity-hints extraction for IEG (v0)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class IdentityHint:
    identifier_type: str
    identifier_value: str
    entity_type: str
    entity_id: str | None
    source_event_id: str


@dataclass(frozen=True)
class HintRule:
    identifier_type: str
    path: str
    entity_type: str | None = None


@dataclass(frozen=True)
class HintSpec:
    mode: str
    mappings: list[HintRule]


@dataclass(frozen=True)
class IdentityHintsPolicy:
    default_mode: str
    specs: dict[str, HintSpec]

    @classmethod
    def load(cls, path: Path) -> "IdentityHintsPolicy":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        default_mode = str(data.get("default_mode") or "observed_identifiers")
        specs: dict[str, HintSpec] = {}
        for event_type, spec in (data.get("event_types") or {}).items():
            mode = str(spec.get("mode") or default_mode)
            mappings: list[HintRule] = []
            for entry in spec.get("mappings") or []:
                mappings.append(
                    HintRule(
                        identifier_type=str(entry.get("identifier_type")),
                        path=str(entry.get("path")),
                        entity_type=entry.get("entity_type"),
                    )
                )
            specs[str(event_type)] = HintSpec(mode=mode, mappings=mappings)
        return cls(default_mode=default_mode, specs=specs)

    def for_event(self, event_type: str) -> HintSpec:
        return self.specs.get(event_type) or HintSpec(mode=self.default_mode, mappings=[])


def extract_identity_hints(envelope: dict[str, Any], policy: IdentityHintsPolicy) -> list[IdentityHint]:
    event_type = str(envelope.get("event_type") or "")
    spec = policy.for_event(event_type)
    if spec.mode == "field_map":
        hints: list[IdentityHint] = []
        for mapping in spec.mappings:
            value = _get_path(envelope, mapping.path)
            if value in (None, ""):
                continue
            hints.append(
                IdentityHint(
                    identifier_type=mapping.identifier_type,
                    identifier_value=str(value),
                    entity_type=str(mapping.entity_type or mapping.identifier_type),
                    entity_id=None,
                    source_event_id=str(envelope.get("event_id") or ""),
                )
            )
        return hints
    return _normalize_observed_identifiers(envelope)


def _normalize_observed_identifiers(envelope: dict[str, Any]) -> list[IdentityHint]:
    payload = envelope.get("payload") or {}
    observed = payload.get("observed_identifiers")
    if not isinstance(observed, list):
        return []
    hints: list[IdentityHint] = []
    for item in observed:
        if not isinstance(item, dict):
            continue
        identifier_type = item.get("identifier_type") or item.get("type")
        identifier_value = item.get("identifier_value") or item.get("value")
        if not identifier_type or identifier_value in (None, ""):
            continue
        entity_type = item.get("entity_type") or identifier_type
        entity_id = item.get("entity_id") or None
        hints.append(
            IdentityHint(
                identifier_type=str(identifier_type),
                identifier_value=str(identifier_value),
                entity_type=str(entity_type),
                entity_id=str(entity_id) if entity_id else None,
                source_event_id=str(envelope.get("event_id") or ""),
            )
        )
    return hints


def _get_path(envelope: dict[str, Any], path: str) -> Any | None:
    if not path:
        return None
    parts = path.split(".")
    current: Any = envelope
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
