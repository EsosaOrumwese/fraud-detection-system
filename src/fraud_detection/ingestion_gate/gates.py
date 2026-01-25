"""Gate map helpers for required gate expansion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class GateEntry:
    gate_id: str
    authorizes_outputs: list[str]
    upstream_gate_dependencies: list[str]
    required_by_components: list[str]


class GateMap:
    def __init__(self, gate_map_path: Path) -> None:
        data = yaml.safe_load(gate_map_path.read_text(encoding="utf-8"))
        self._gates: dict[str, GateEntry] = {}
        for entry in data.get("gates", []):
            gate_id = entry["gate_id"]
            self._gates[gate_id] = GateEntry(
                gate_id=gate_id,
                authorizes_outputs=list(entry.get("authorizes_outputs") or []),
                upstream_gate_dependencies=list(entry.get("upstream_gate_dependencies") or []),
                required_by_components=list(entry.get("required_by_components") or []),
            )

    def required_gate_set(self, output_ids: list[str]) -> list[str]:
        required: set[str] = set()
        for gate_id, entry in self._gates.items():
            if entry.required_by_components and "ingestion_gate" not in entry.required_by_components:
                continue
            if any(output_id in entry.authorizes_outputs for output_id in output_ids):
                required.add(gate_id)
        # expand upstream deps
        changed = True
        while changed:
            changed = False
            for gate_id in list(required):
                deps = self._gates.get(gate_id)
                if not deps:
                    continue
                for dep in deps.upstream_gate_dependencies:
                    if dep not in required:
                        required.add(dep)
                        changed = True
        return sorted(required)

    def has_gate(self, gate_id: str) -> bool:
        return gate_id in self._gates
