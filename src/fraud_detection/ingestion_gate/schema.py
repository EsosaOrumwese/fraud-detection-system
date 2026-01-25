"""Envelope + payload schema enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import SchemaPolicy
from .errors import IngestionError
from .schemas import SchemaRegistry


@dataclass
class SchemaEnforcer:
    envelope_registry: SchemaRegistry
    payload_registry_root: Path
    policy: SchemaPolicy

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
            schema = _load_schema_ref(self.payload_registry_root, entry.payload_schema_ref)
            try:
                _validate_with_schema(schema, envelope.get("payload", {}))
            except ValueError as exc:
                raise IngestionError("SCHEMA_FAIL") from exc


def _load_schema_ref(root: Path, schema_ref: str) -> dict[str, Any]:
    path_str, _, fragment = schema_ref.partition("#")
    path = (root / path_str).resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if fragment.startswith("/"):
        parts = [part for part in fragment.lstrip("/").split("/") if part]
        for part in parts:
            if not isinstance(data, dict) or part not in data:
                raise ValueError("SCHEMA_REF_INVALID")
            data = data[part]
    return data


def _validate_with_schema(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ValueError(f"Payload schema validation failed: {messages}")
