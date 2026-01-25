"""Engine outputs catalogue loader and renderer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class OutputEntry:
    output_id: str
    path_template: str
    partitions: list[str]
    scope: str
    read_requires_gates: list[str]
    availability: str


class OutputCatalogue:
    def __init__(self, catalogue_path: Path) -> None:
        data = yaml.safe_load(catalogue_path.read_text(encoding="utf-8"))
        entries = data.get("outputs", [])
        self._entries = {
            entry["output_id"]: OutputEntry(
                output_id=entry["output_id"],
                path_template=str(entry["path_template"]).strip(),
                partitions=entry.get("partitions", []),
                scope=entry.get("scope", ""),
                read_requires_gates=entry.get("read_requires_gates", []),
                availability=entry.get("availability", "required"),
            )
            for entry in entries
        }

    def get(self, output_id: str) -> OutputEntry:
        return self._entries[output_id]

    def has(self, output_id: str) -> bool:
        return output_id in self._entries
