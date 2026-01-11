"""Adapt schema packs to JSON Schema for validation."""

from __future__ import annotations

from typing import Any, Iterable

from jsonschema import Draft202012Validator

from engine.core.errors import ContractError, SchemaValidationError


_TYPE_MAP = {
    "int64": "integer",
    "int32": "integer",
    "int16": "integer",
    "int8": "integer",
    "uint64": "integer",
    "float64": "number",
    "float32": "number",
    "string": "string",
    "boolean": "boolean",
    "date": "string",
    "datetime": "string",
}


def _column_schema(column: dict[str, Any]) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    ref = column.get("$ref")
    if ref:
        schema = {"$ref": ref}
    else:
        col_type = column.get("type")
        if not col_type:
            raise ContractError(f"Column missing type or $ref: {column}")
        if col_type not in _TYPE_MAP:
            raise ContractError(f"Unsupported column type '{col_type}' for JSON Schema adapter.")
        schema = {"type": _TYPE_MAP[col_type]}
        if col_type == "date":
            schema["format"] = "date"
        if col_type == "datetime":
            schema["format"] = "date-time"
    for key in ("pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "enum", "minLength", "maxLength"):
        if key in column:
            schema[key] = column[key]
    if column.get("nullable"):
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _table_row_schema(
    schema_pack: dict[str, Any], table_name: str, strict: bool = True
) -> dict[str, Any]:
    table = schema_pack.get(table_name)
    if not table:
        raise ContractError(f"Table '{table_name}' not found in schema pack.")
    if table.get("type") not in ("table", "stream", "geotable", "raster"):
        raise ContractError(
            f"Unsupported schema type for '{table_name}': {table.get('type')}"
        )
    columns = table.get("columns") or []
    if not columns:
        raise ContractError(f"Table '{table_name}' has no columns defined.")
    properties: dict[str, Any] = {}
    required: list[str] = []
    for column in columns:
        name = column.get("name")
        if not name:
            raise ContractError(f"Column missing name in '{table_name}'.")
        properties[name] = _column_schema(column)
        required.append(name)
    row_schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
        "type": "object",
        "properties": properties,
        "required": required,
    }
    if strict:
        row_schema["additionalProperties"] = False
    return row_schema


def table_to_jsonschema(
    schema_pack: dict[str, Any], table_name: str, strict: bool = True
) -> dict[str, Any]:
    row_schema = _table_row_schema(schema_pack, table_name, strict=strict)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
        "type": "array",
        "items": {
            key: value
            for key, value in row_schema.items()
            if key not in ("$schema", "$id")
        },
    }


def validate_dataframe(
    rows: Iterable[dict[str, Any]],
    schema_pack: dict[str, Any],
    table_name: str,
    max_errors: int = 5,
) -> None:
    schema = table_to_jsonschema(schema_pack, table_name)
    row_schema = _table_row_schema(schema_pack, table_name)
    validator = Draft202012Validator(row_schema)
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        for error in validator.iter_errors(row):
            field = ".".join(str(part) for part in error.path) if error.path else ""
            errors.append(
                {
                    "row_index": index,
                    "field": field,
                    "message": error.message,
                }
            )
            if len(errors) >= max_errors:
                break
        if errors and len(errors) >= max_errors:
            break
    if errors:
        lines = [
            f"row {item['row_index']}: {item['field']} {item['message']}".strip()
            for item in errors
        ]
        raise SchemaValidationError(
            "Ingress schema validation failed:\n" + "\n".join(lines), errors
        )
