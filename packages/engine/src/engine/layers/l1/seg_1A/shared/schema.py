"""Schema loader helpers for Segment 1A validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..s0_foundations.exceptions import err
from .dictionary import get_repo_root

_SCHEMA_DOCS: dict[str, dict[str, Any]] = {}


def load_schema(schema_ref: str) -> Mapping[str, Any]:
    """Load a schema reference and normalize table definitions to JSON Schema."""

    file_name, pointer = _split_schema_ref(schema_ref)
    document = _schema_document(file_name)
    node = _resolve_pointer(document, pointer)
    return normalize_schema(node, document)


def normalize_schema(node: Any, document: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a JSON-Schema-ready payload for a node in a schema pack."""

    return _normalize_schema(node, document)


def _schema_document(file_name: str) -> dict[str, Any]:
    document = _SCHEMA_DOCS.get(file_name)
    if document is not None:
        return document
    path = _schema_file_path(file_name)
    if not path.exists():
        raise err("E_SCHEMA_NOT_FOUND", f"schema file '{file_name}' not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".yaml", ".yml"}:
            payload = yaml.safe_load(handle) or {}
        else:
            payload = json.load(handle)
    if not isinstance(payload, dict):
        raise err("E_SCHEMA_FORMAT", f"schema file '{path}' must decode to a mapping")
    _SCHEMA_DOCS[file_name] = payload
    return payload


def _schema_file_path(file_name: str) -> Path:
    repo_root = get_repo_root()
    candidate = (repo_root / "contracts" / "schemas" / file_name).resolve()
    if candidate.exists():
        return candidate
    if file_name in {
        "schemas.1A.yaml",
        "schemas.layer1.yaml",
        "schemas.ingress.layer1.yaml",
    }:
        candidate = (
            repo_root / "contracts" / "schemas" / "layer1" / file_name
        ).resolve()
        if candidate.exists():
            return candidate
    candidate = (repo_root / file_name).resolve()
    if candidate.exists():
        return candidate
    return (repo_root / "contracts" / "schemas" / file_name).resolve()


def _split_schema_ref(schema_ref: str) -> tuple[str, str]:
    if "#" in schema_ref:
        file_name, pointer = schema_ref.split("#", 1)
    else:
        file_name, pointer = schema_ref, ""
    pointer = pointer or ""
    if pointer and not pointer.startswith("/") and pointer != "#":
        pointer = f"/{pointer}"
    if pointer == "#":
        pointer = ""
    return file_name, pointer


def _resolve_pointer(document: Mapping[str, Any], pointer: str) -> Any:
    if not pointer:
        return document
    parts = pointer.lstrip("/").split("/")
    node: Any = document
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, Mapping) and part in node:
            node = node[part]
        else:
            raise err("E_SCHEMA_INVALID", f"schema pointer '{pointer}' missing '{part}'")
    return node


def _normalize_schema(node: Any, document: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(node, Mapping) and node.get("type") in {"table", "geotable"}:
        return _table_to_json_schema(node, document)
    if isinstance(node, Mapping) and "$defs" not in node and "$defs" in document:
        normalized = dict(node)
        normalized["$defs"] = document.get("$defs", {})
        return normalized
    if isinstance(node, Mapping):
        return dict(node)
    raise err("E_SCHEMA_INVALID", "schema node must be a mapping")


def _table_to_json_schema(
    table_def: Mapping[str, Any], document: Mapping[str, Any]
) -> Mapping[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for column_def in table_def.get("columns", []):
        name = column_def.get("name")
        if not name:
            continue
        column_schema = _column_to_schema(column_def)
        if column_def.get("nullable", False):
            column_schema = {"anyOf": [column_schema, {"type": "null"}]}
        else:
            required.append(name)
        properties[name] = column_schema

    return {
        "$schema": document.get(
            "$schema", "https://json-schema.org/draft/2020-12/schema"
        ),
        "$defs": document.get("$defs", {}),
        "type": "array",
        "items": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


def _column_to_schema(column_def: Mapping[str, Any]) -> Mapping[str, Any]:
    if "$ref" in column_def:
        return {"$ref": column_def["$ref"]}

    column_type = column_def.get("type")
    if column_type in (None, "any"):
        schema: dict[str, Any] = {}
    elif column_type in {"int32", "int64", "uint32", "uint64", "integer"}:
        schema = {"type": "integer"}
    elif column_type in {"float32", "float64", "number", "double"}:
        schema = {"type": "number"}
    elif column_type == "boolean":
        schema = {"type": "boolean"}
    else:
        schema = {"type": column_type}

    for key in ("pattern", "minimum", "maximum", "enum", "const"):
        if key in column_def:
            schema[key] = column_def[key]
    return schema


__all__ = ["load_schema", "normalize_schema"]
