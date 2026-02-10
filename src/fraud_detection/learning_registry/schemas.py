"""Schema loader/validator for learning+registry contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator


class LearningRegistrySchemaError(ValueError):
    """Raised when learning/registry schema validation fails."""


_DEFAULT_ROOT = Path("docs/model_spec/platform/contracts/learning_registry")


@dataclass(frozen=True)
class LearningRegistrySchemaRegistry:
    root: Path = _DEFAULT_ROOT

    def validate(self, schema_name: str, payload: Mapping[str, Any]) -> None:
        schema = self._load_schema(schema_name)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(dict(payload)), key=lambda item: list(item.path))
        if not errors:
            return
        first = errors[0]
        path = ".".join(str(item) for item in first.path) or "<root>"
        raise LearningRegistrySchemaError(f"{schema_name}:{path}:{first.message}")

    def _load_schema(self, schema_name: str) -> dict[str, Any]:
        name = str(schema_name or "").strip()
        if not name:
            raise LearningRegistrySchemaError("schema_name is required")
        path = self.root / name
        if not path.exists():
            raise LearningRegistrySchemaError(f"schema not found: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise LearningRegistrySchemaError(f"schema is not a mapping: {path}")
        return payload
