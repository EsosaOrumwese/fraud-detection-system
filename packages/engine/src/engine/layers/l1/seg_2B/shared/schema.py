"""Schema utilities for Segment 2B."""

from __future__ import annotations

import copy
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..s0_gate.exceptions import err

_SHARED_DEFS: Mapping[str, Any] | None = None
_LAYER1_DOC: Mapping[str, Any] | None = None


def _schema_root() -> Path:
    repo_root = Path(__file__).resolve()
    for parent in repo_root.parents:
        if parent.name == "packages":
            return parent.parent / "contracts" / "schemas" / "layer1"
    raise err("E_SCHEMA_RESOLUTION_FAILED", "unable to determine schema root")


def _load_shared_defs() -> Mapping[str, Any]:
    global _SHARED_DEFS
    if _SHARED_DEFS is None:
        doc = _load_layer1_document()
        defs = doc.get("$defs")
        if not isinstance(defs, Mapping):
            raise err(
                "E_SCHEMA_RESOLUTION_FAILED",
                "shared layer1 schema bundle missing $defs mapping",
            )
        _SHARED_DEFS = defs
    return _SHARED_DEFS


def load_schema_document() -> Mapping[str, Any]:
    """Load the Segment 2B schema bundle."""

    schema_path = _schema_root() / "schemas.2B.yaml"
    if not schema_path.exists():
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"segment 2B schema bundle '{schema_path}' missing",
        )
    document = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, Mapping):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"segment 2B schema bundle '{schema_path}' must decode to a mapping",
        )
    return document


def _load_layer1_document() -> Mapping[str, Any]:
    global _LAYER1_DOC
    if _LAYER1_DOC is None:
        shared_path = _schema_root() / "schemas.layer1.yaml"
        if not shared_path.exists():
            raise err(
                "E_SCHEMA_RESOLUTION_FAILED",
                f"shared layer1 schema bundle '{shared_path}' missing",
            )
        doc = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}
        if not isinstance(doc, Mapping):
            raise err(
                "E_SCHEMA_RESOLUTION_FAILED",
                f"layer1 schema bundle '{shared_path}' must decode to a mapping",
            )
        _LAYER1_DOC = doc
    return _LAYER1_DOC


def _ensure_defs(target: MutableMapping[str, Any], new_defs: Mapping[str, Any]) -> None:
    defs = target.setdefault("$defs", {})
    if not isinstance(defs, MutableMapping):
        raise err("E_SCHEMA_RESOLUTION_FAILED", "$defs must be a mapping")
    for key, value in new_defs.items():
        if key not in defs:
            defs[key] = value


def _rewrite_shared_refs(node: Any) -> None:
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "$ref" and isinstance(value, str) and value.startswith("schemas.layer1.yaml#/$defs/"):
                name = value.split("/")[-1]
                node[key] = f"#/$defs/{name}"
            else:
                _rewrite_shared_refs(value)
    elif isinstance(node, list):
        for item in node:
            _rewrite_shared_refs(item)


def _resolve_pointer(document: Mapping[str, Any], parts: list[str]) -> Mapping[str, Any] | None:
    node: Any = document
    for raw in parts:
        key = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, Mapping) else None


def load_schema(ref: str) -> Mapping[str, Any]:
    """Resolve ``ref`` (JSON pointer) inside the Segment 2B schema bundle."""

    if not ref.startswith("#/"):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"schema ref '{ref}' must be an internal JSON pointer",
        )
    parts = ref[2:].split("/") if len(ref) > 2 else []
    document = load_schema_document()
    node = _resolve_pointer(document, parts)
    source_doc = document
    if node is None:
        layer1_doc = _load_layer1_document()
        node = _resolve_pointer(layer1_doc, parts)
        source_doc = layer1_doc
    if not isinstance(node, Mapping):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"schema '{ref}' does not resolve to an object definition",
        )

    result: MutableMapping[str, Any] = copy.deepcopy(node)
    if isinstance(source_doc, Mapping) and "$defs" in source_doc:
        doc_defs = source_doc.get("$defs", {})
        if isinstance(doc_defs, Mapping):
            _ensure_defs(result, doc_defs)
    _ensure_defs(result, _load_shared_defs())
    _rewrite_shared_refs(result)
    return result


__all__ = ["load_schema_document", "load_schema"]

