"""SR JSON Schema registry + validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


@dataclass
class SchemaRegistry:
    root: Path

    def __post_init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        if name in self._cache:
            return self._cache[name]
        path = self.root / name
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._cache[name] = data
        return data

    def validate(self, name: str, payload: dict[str, Any]) -> None:
        schema = self.load(name)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        if errors:
            messages = "; ".join(error.message for error in errors)
            raise ValueError(f"Schema validation failed for {name}: {messages}")
