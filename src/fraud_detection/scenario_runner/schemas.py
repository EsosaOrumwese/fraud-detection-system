"""SR JSON Schema registry + validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml
from jsonschema import Draft202012Validator, RefResolver


@dataclass
class SchemaRegistry:
    root: Path

    def __post_init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._paths: dict[str, Path] = {}

    def load(self, name: str) -> dict[str, Any]:
        if name in self._cache:
            return self._cache[name]
        path = (self.root / name).resolve()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._cache[name] = data
        self._paths[name] = path
        return data

    def validate(self, name: str, payload: dict[str, Any]) -> None:
        schema = self.load(name)
        resolver = RefResolver(
            base_uri=self._paths[name].as_uri(),
            referrer=schema,
            handlers={"file": self._load_yaml_ref},
        )
        validator = Draft202012Validator(schema, resolver=resolver)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        if errors:
            messages = "; ".join(error.message for error in errors)
            raise ValueError(f"Schema validation failed for {name}: {messages}")

    def _load_yaml_ref(self, uri: str) -> Any:
        parsed = urlparse(uri)
        path_str = unquote(parsed.path)
        if path_str.startswith("/") and len(path_str) > 2 and path_str[2] == ":":
            path_str = path_str.lstrip("/")
        path = Path(path_str)
        if not path.exists():
            parts = list(path.parts)
            if "interface_pack" in parts:
                parts.remove("interface_pack")
                fallback = Path(*parts)
                if fallback.exists():
                    path = fallback
        return yaml.safe_load(path.read_text(encoding="utf-8"))
