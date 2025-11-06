"""Schema validation helpers for Segment 2A S0."""

from __future__ import annotations

from jsonschema import Draft202012Validator, ValidationError

from ...shared.schema import load_schema
from ..exceptions import err


def validate_receipt_payload(payload: dict) -> None:
    """Validate the gate receipt payload against the canonical schema."""

    schema = load_schema("#/validation/s0_gate_receipt_v1")
    validator = Draft202012Validator(schema)
    try:
        validator.validate(payload)
    except ValidationError as exc:
        raise err(
            "E_RECEIPT_SCHEMA_INVALID",
            f"receipt payload violates schema: {exc.message}",
        ) from exc


__all__ = ["validate_receipt_payload"]
