"""Event classification for IEG projection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

GRAPH_MUTATING = "GRAPH_MUTATING"
GRAPH_IRRELEVANT = "GRAPH_IRRELEVANT"
GRAPH_UNUSABLE = "GRAPH_UNUSABLE"


@dataclass(frozen=True)
class ClassificationMap:
    default_action: str
    graph_mutating: set[str]
    graph_irrelevant: set[str]

    @classmethod
    def load(cls, path: Path) -> "ClassificationMap":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        default_action = str(data.get("default_action") or GRAPH_UNUSABLE).upper()
        mutating = {str(item) for item in data.get("graph_mutating", [])}
        irrelevant = {str(item) for item in data.get("graph_irrelevant", [])}
        return cls(
            default_action=default_action,
            graph_mutating=mutating,
            graph_irrelevant=irrelevant,
        )

    def classify(self, event_type: str) -> str:
        if event_type in self.graph_mutating:
            return GRAPH_MUTATING
        if event_type in self.graph_irrelevant:
            return GRAPH_IRRELEVANT
        return self.default_action
