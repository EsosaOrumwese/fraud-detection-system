"""Envelope + payload schema enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from .config import SchemaPolicy
from .errors import IngestionError
from .schemas import SchemaRegistry


@dataclass
class SchemaEnforcer:
    envelope_registry: SchemaRegistry
    payload_registry_root: Path
    policy: SchemaPolicy
    _payload_schema_cache: dict[str, tuple[dict[str, Any], Registry]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def validate_envelope(self, envelope: dict[str, Any]) -> None:
        try:
            self.envelope_registry.validate("canonical_event_envelope.schema.yaml", envelope)
        except Exception as exc:  # pragma: no cover - defensive
            raise IngestionError("ENVELOPE_INVALID") from exc

    def validate_payload(self, event_type: str, envelope: dict[str, Any]) -> None:
        entry = self.policy.for_event(event_type)
        if entry is None:
            raise IngestionError("SCHEMA_POLICY_MISSING")
        schema_version = envelope.get("schema_version")
        if entry.schema_version_required and not schema_version:
            raise IngestionError("SCHEMA_VERSION_REQUIRED")
        if entry.allowed_schema_versions and schema_version not in entry.allowed_schema_versions:
            raise IngestionError("SCHEMA_VERSION_NOT_ALLOWED")
        if entry.payload_schema_ref:
            schema, registry = self._resolve_payload_schema(entry.payload_schema_ref)
            try:
                _validate_with_schema(schema, envelope.get("payload", {}), registry=registry)
            except ValueError as exc:
                raise IngestionError("SCHEMA_FAIL") from exc

    def _resolve_payload_schema(self, schema_ref: str) -> tuple[dict[str, Any], Registry]:
        cached = self._payload_schema_cache.get(schema_ref)
        if cached is not None:
            return cached
        resolved = _load_schema_ref(self.payload_registry_root, schema_ref)
        self._payload_schema_cache[schema_ref] = resolved
        return resolved


def _load_schema_ref(root: Path, schema_ref: str) -> tuple[dict[str, Any], Registry]:
    path_str, _, fragment = schema_ref.partition("#")
    raw_path = Path(path_str)
    if raw_path.is_absolute() or path_str.startswith("docs/") or path_str.startswith("docs\\"):
        path = raw_path.resolve()
    else:
        path = (root / path_str).resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    _normalize_nullable(data)
    base_uri = path.as_uri()
    schema_for_validation = data
    if fragment:
        schema_for_validation = {"$ref": f"{base_uri}#{fragment}"}
    if isinstance(data, dict):
        schema_id = data.get("$id")
        if not schema_id or not urlparse(schema_id).scheme:
            data = dict(data)
            data["$id"] = base_uri
    registry = SchemaRegistry(root)
    registry_obj = Registry(retrieve=registry._retrieve_resource)
    registry_obj = registry_obj.with_resource(
        base_uri,
        Resource.from_contents(data, default_specification=DRAFT202012),
    )
    return schema_for_validation, registry_obj


def _validate_with_schema(
    schema: dict[str, Any], payload: dict[str, Any], *, registry: Registry
) -> None:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(f"Payload schema validation failed: {messages}")


def _normalize_nullable(node: Any) -> None:
    if isinstance(node, dict):
        nullable = node.pop("nullable", False)
        if nullable:
            if "$ref" in node:
                ref = node.pop("$ref")
                meta = dict(node)
                node.clear()
                node.update(meta)
                node["anyOf"] = [{"$ref": ref}, {"type": "null"}]
            elif "type" in node:
                node_type = node["type"]
                if isinstance(node_type, list):
                    if "null" not in node_type:
                        node_type.append("null")
                else:
                    node["type"] = [node_type, "null"]
            else:
                node["type"] = ["null"]
        for value in node.values():
            _normalize_nullable(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_nullable(item)
