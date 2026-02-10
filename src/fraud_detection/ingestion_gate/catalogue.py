"""Engine output catalogue loader (minimal for IG)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class OutputEntry:
    output_id: str
    path_template: str
    primary_key: list[str]
    read_requires_gates: list[str]
    scope: str | None = None
    schema_ref: str | None = None


class OutputCatalogue:
    def __init__(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._entries: dict[str, OutputEntry] = {}
        for item in data.get("outputs", []):
            output_id = item["output_id"]
            entry = OutputEntry(
                output_id=output_id,
                path_template=item.get("path_template", ""),
                primary_key=list(item.get("primary_key") or []),
                read_requires_gates=list(item.get("read_requires_gates") or []),
                scope=item.get("scope"),
                schema_ref=item.get("schema_ref"),
            )
            self._entries[output_id] = entry

    def get(self, output_id: str) -> OutputEntry:
        if output_id not in self._entries:
            raise KeyError(f"Unknown output_id: {output_id}")
        return self._entries[output_id]
