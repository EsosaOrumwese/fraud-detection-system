"""Schema utilities for Segment 3B."""

from __future__ import annotations

import copy
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..s0_gate.exceptions import err

_LAYER1_DOC: Mapping[str, Any] | None = None


def _schema_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == "packages":
            return parent.parent / "contracts" / "schemas" / "layer1"
    raise err("E_SCHEMA_RESOLUTION_FAILED", "unable to resolve schema root for Segment 3B")


def _load_layer1_document() -> Mapping[str, Any]:
    global _LAYER1_DOC
    if _LAYER1_DOC is None:
        shared_path = _schema_root() / "schemas.layer1.yaml"
        if not shared_path.exists():
            raise err(
                "E_SCHEMA_RESOLUTION_FAILED",
                f"layer1 schema bundle '{shared_path}' missing",
            )
        payload = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, Mapping):
            raise err(
                "E_SCHEMA_RESOLUTION_FAILED",
                f"layer1 schema bundle '{shared_path}' must decode to a mapping",
            )
        _LAYER1_DOC = payload
    return _LAYER1_DOC


def load_schema_document() -> Mapping[str, Any]:
    """Load the Segment 3B schema bundle."""

    schema_path = _schema_root() / "schemas.3B.yaml"
    if not schema_path.exists():
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"segment 3B schema bundle '{schema_path}' missing",
        )
    payload = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"segment 3B schema bundle '{schema_path}' must decode to a mapping",
        )
    return payload


def _ensure_defs(target: MutableMapping[str, Any], defs: Mapping[str, Any]) -> None:
    container = target.setdefault("$defs", {})
    if not isinstance(container, MutableMapping):
        raise err("E_SCHEMA_RESOLUTION_FAILED", "$defs must decode to a mapping")
    for key, value in defs.items():
        if key not in container:
            container[key] = value


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
    """Resolve ``ref`` (JSON pointer) inside the Segment 3B schema bundle."""

    if not ref.startswith("#/"):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"schema ref '{ref}' must be an internal JSON pointer",
        )
    parts = ref[2:].split("/") if len(ref) > 2 else []
    segment_doc = load_schema_document()
    node = _resolve_pointer(segment_doc, parts)
    source_doc = segment_doc
    if node is None:
        layer1_doc = _load_layer1_document()
        node = _resolve_pointer(layer1_doc, parts)
        source_doc = layer1_doc
    if not isinstance(node, Mapping):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"schema ref '{ref}' did not resolve to an object definition",
        )

    resolved: MutableMapping[str, Any] = copy.deepcopy(node)
    defs = source_doc.get("$defs")
    if isinstance(defs, Mapping):
        _ensure_defs(resolved, defs)
    defs_obj = resolved.get("$defs")
    if isinstance(defs_obj, MutableMapping):
        _ensure_defs(resolved, defs_obj)
    _rewrite_shared_refs(resolved)
    return resolved


__all__ = ["load_schema_document", "load_schema"]
