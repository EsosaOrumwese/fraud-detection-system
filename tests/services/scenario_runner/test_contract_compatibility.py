from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
INTERFACE_ROOT = REPO_ROOT / "docs/model_spec/data-engine/interface_pack"
CATALOGUE_PATH = INTERFACE_ROOT / "engine_outputs.catalogue.yaml"
GATE_MAP_PATH = INTERFACE_ROOT / "engine_gates.map.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _split_ref(ref: str) -> tuple[str, str]:
    if "#" not in ref:
        return ref, ""
    file_part, pointer = ref.split("#", 1)
    return file_part, pointer


def _resolve_pointer(doc: Any, pointer: str) -> Any:
    if not pointer or pointer == "#":
        return doc
    if not pointer.startswith("/"):
        raise AssertionError(f"Unsupported schema pointer: {pointer}")
    node: Any = doc
    for part in pointer.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise AssertionError(f"Invalid list index in pointer: {pointer}") from exc
            node = node[index]
        elif isinstance(node, dict):
            if part not in node:
                raise AssertionError(f"Missing pointer segment '{part}' in {pointer}")
            node = node[part]
        else:
            raise AssertionError(f"Pointer '{pointer}' traversed into non-container value")
    return node


def _resolve_ref(repo_root: Path, ref: str, cache: dict[Path, Any]) -> None:
    file_part, pointer = _split_ref(ref)
    if not file_part:
        raise AssertionError(f"Schema ref missing file part: {ref}")
    path = Path(file_part)
    if not path.is_absolute():
        path = (repo_root / file_part).resolve()
    if not path.exists():
        raise AssertionError(f"Ref file not found: {path}")
    data = cache.get(path)
    if data is None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cache[path] = data
    _resolve_pointer(data, pointer)


def test_interface_pack_catalogue_gate_consistency() -> None:
    catalogue = _load_yaml(CATALOGUE_PATH)
    gate_map = _load_yaml(GATE_MAP_PATH)

    outputs = catalogue.get("outputs", [])
    gates = gate_map.get("gates", [])

    output_ids = [entry.get("output_id") for entry in outputs]
    gate_ids = [entry.get("gate_id") for entry in gates]

    errors: list[str] = []

    missing_output_ids = [output_id for output_id in output_ids if not output_id]
    if missing_output_ids:
        errors.append("Missing output_id entries detected in catalogue.")

    if len(set(output_ids)) != len(output_ids):
        errors.append("Duplicate output_id entries detected in catalogue.")

    if len(set(gate_ids)) != len(gate_ids):
        errors.append("Duplicate gate_id entries detected in gate map.")

    referenced_gates = {
        gate_id
        for entry in outputs
        for gate_id in (entry.get("read_requires_gates") or [])
    }
    unknown_gates = sorted(gate_id for gate_id in referenced_gates if gate_id not in gate_ids)
    if unknown_gates:
        errors.append(f"Catalogue references unknown gate_ids: {unknown_gates}")

    referenced_outputs = {
        output_id
        for entry in gates
        for output_id in (entry.get("authorizes_outputs") or [])
    }
    unknown_outputs = sorted(output_id for output_id in referenced_outputs if output_id not in output_ids)
    if unknown_outputs:
        errors.append(f"Gate map references unknown output_ids: {unknown_outputs}")

    empty_gate_outputs = [entry.get("gate_id") for entry in gates if not entry.get("authorizes_outputs")]
    if empty_gate_outputs:
        errors.append(f"Gates with no authorizes_outputs: {empty_gate_outputs}")

    missing_deps: list[str] = []
    for entry in gates:
        for dep in entry.get("upstream_gate_dependencies", []) or []:
            if dep not in gate_ids:
                missing_deps.append(f"{entry.get('gate_id')} -> {dep}")
    if missing_deps:
        errors.append(f"Missing upstream gate dependencies: {missing_deps}")

    if errors:
        raise AssertionError("Interface pack consistency failures:\n- " + "\n- ".join(errors))


def test_interface_pack_refs_resolve() -> None:
    catalogue = _load_yaml(CATALOGUE_PATH)
    gate_map = _load_yaml(GATE_MAP_PATH)
    cache: dict[Path, Any] = {}

    ref_fields = [
        "schema_ref",
        "dictionary_ref",
    ]
    gate_ref_fields = [
        "index_schema_ref",
        "receipt_schema_ref",
    ]

    errors: list[str] = []

    for entry in catalogue.get("outputs", []):
        for field in ref_fields:
            ref = entry.get(field)
            if not ref:
                continue
            try:
                _resolve_ref(REPO_ROOT, ref, cache)
            except AssertionError as exc:
                errors.append(f"{entry.get('output_id')} {field}: {exc}")

    for entry in gate_map.get("gates", []):
        for field in gate_ref_fields:
            ref = entry.get(field)
            if not ref:
                continue
            try:
                _resolve_ref(REPO_ROOT, ref, cache)
            except AssertionError as exc:
                errors.append(f"{entry.get('gate_id')} {field}: {exc}")

    if errors:
        raise AssertionError("Interface pack ref resolution failures:\n- " + "\n- ".join(errors))
