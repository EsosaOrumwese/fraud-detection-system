"""Load contract dictionaries, registries, and schema packs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from engine.contracts.source import ContractSource
from engine.core.errors import ContractError


@dataclass(frozen=True)
class DatasetEntry:
    dataset_id: str
    entry: dict[str, Any]


@dataclass(frozen=True)
class ArtifactEntry:
    name: str
    entry: dict[str, Any]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ContractError(f"Missing contract file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_dataset_dictionary(source: ContractSource, segment: str) -> tuple[Path, dict[str, Any]]:
    path = source.resolve_dataset_dictionary(segment)
    return path, _load_yaml(path)


def load_artefact_registry(source: ContractSource, segment: str) -> tuple[Path, dict[str, Any]]:
    path = source.resolve_artefact_registry(segment)
    return path, _load_yaml(path)


def load_schema_pack(source: ContractSource, segment: str, kind: str) -> tuple[Path, dict[str, Any]]:
    path = source.resolve_schema_pack(segment, kind)
    return path, _load_yaml(path)


def find_dataset_entry(dictionary: dict[str, Any], dataset_id: str) -> DatasetEntry:
    for section, value in dictionary.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and item.get("id") == dataset_id:
                return DatasetEntry(dataset_id=dataset_id, entry=item)
    raise ContractError(f"Dataset ID not found in dictionary: {dataset_id}")


def find_artifact_entry(registry: dict[str, Any], artifact_name: str) -> ArtifactEntry:
    subsegments = registry.get("subsegments", [])
    for subsegment in subsegments:
        for artifact in subsegment.get("artifacts", []):
            if artifact.get("name") == artifact_name:
                return ArtifactEntry(name=artifact_name, entry=artifact)
    raise ContractError(f"Artifact name not found in registry: {artifact_name}")


def artifact_dependency_closure(
    registry: dict[str, Any], artifact_names: Iterable[str]
) -> list[ArtifactEntry]:
    resolved: dict[str, ArtifactEntry] = {}
    stack = list(artifact_names)
    while stack:
        name = stack.pop()
        if name in resolved:
            continue
        entry = find_artifact_entry(registry, name)
        resolved[name] = entry
        deps = entry.entry.get("dependencies") or []
        for dep in deps:
            if dep not in resolved:
                stack.append(dep)
    return [resolved[name] for name in sorted(resolved.keys())]
