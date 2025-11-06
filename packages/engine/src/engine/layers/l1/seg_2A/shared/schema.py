"""Schema utilities for Segment 2A."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from ..s0_gate.exceptions import err


def _schema_root() -> Path:
    repo_root = Path(__file__).resolve()
    for parent in repo_root.parents:
        if parent.name == "packages":
            return parent.parent / "contracts" / "schemas" / "layer1"
    raise err("E_SCHEMA_RESOLUTION_FAILED", "unable to determine schema root")


def load_schema_document() -> Mapping[str, Any]:
    """Load the Segment 2A schema bundle."""

    schema_path = _schema_root() / "schemas.2A.yaml"
    if not schema_path.exists():
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"segment 2A schema bundle '{schema_path}' missing",
        )
    document = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, Mapping):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"segment 2A schema bundle '{schema_path}' must decode to a mapping",
        )
    return document


def load_schema(ref: str) -> Mapping[str, Any]:
    """Resolve ``ref`` (JSON pointer) inside the Segment 2A schema bundle."""

    if not ref.startswith("#/"):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"schema ref '{ref}' must be an internal JSON pointer",
        )
    parts = ref[2:].split("/") if len(ref) > 2 else []
    document = load_schema_document()
    node: Any = document
    for raw in parts:
        key = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, Mapping) or key not in node:
            raise err(
                "E_SCHEMA_RESOLUTION_FAILED",
                f"schema pointer '{ref}' cannot be resolved at '{key}'",
            )
        node = node[key]
    if not isinstance(node, Mapping):
        raise err(
            "E_SCHEMA_RESOLUTION_FAILED",
            f"schema '{ref}' does not resolve to an object definition",
        )
    if "$defs" in document and "$defs" not in node:
        merged = dict(node)
        merged["$defs"] = document["$defs"]
        return merged
    return node


__all__ = ["load_schema_document", "load_schema"]
