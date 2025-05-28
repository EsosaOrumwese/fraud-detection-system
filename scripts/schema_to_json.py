#!/usr/bin/env python3
"""
Convert YAML spec → JSON-Schema draft-07.
Usage:
    poetry run python scripts/schema_to_json.py
Output:
    config/transaction_schema.json
"""
import json
import sys
from pathlib import Path

import yaml  # type: ignore

# Load YAML
yaml_path = Path("config/transaction_schema.yaml")
with yaml_path.open("r", encoding="utf-8-sig") as f:
    schema = yaml.safe_load(f)

# Base JSON‐Schema skeleton
out = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": f"Transaction schema v{schema['version']}",
    "description": schema.get("description", "").strip(),
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

dtype_map = {
    "string": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "datetime": "string",
    "enum": "string",
}

# Build each property
for field in schema["fields"]:
    base_type = dtype_map[field["dtype"]]
    prop: dict = {}

    # Type (with null if allowed)
    if field["nullable"]:
        prop["type"] = [base_type, "null"]
    else:
        prop["type"] = base_type

    # Formats & enums
    if field["dtype"] == "datetime":
        prop["format"] = "date-time"
    if field.get("enum"):
        prop["enum"] = field["enum"]

    # Description
    prop["description"] = field.get("description", "")

    # Record 'requiredness'
    if not field["nullable"]:
        out["required"].append(field["name"])

    out["properties"][field["name"]] = prop

# Write JSON Schema
json_path = Path("config/transaction_schema.json")
json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"Wrote {json_path}", file=sys.stderr)
