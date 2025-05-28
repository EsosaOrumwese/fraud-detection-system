"""
Quick integrity checks so schema drift breaks CI immediately.
Run with:  poetry run pytest -q tests/unit/test_schema_yaml.py
"""

import yaml  # type: ignore
from pathlib import Path
import pytest

SCHEMA = Path("config/transaction_schema.yaml")
SPEC = yaml.safe_load(SCHEMA.read_text())
ALLOWED_DTYPES = {"string", "int", "float", "bool", "datetime", "enum"}


def test_field_count():
    assert len(SPEC["fields"]) == 24, "Schema must have exactly 24 fields"


def test_unique_names():
    names = [f["name"] for f in SPEC["fields"]]
    assert len(names) == len(set(names)), "Duplicate field names detected"


@pytest.mark.parametrize("field", SPEC["fields"])
def test_dtype_valid(field):
    assert field["dtype"] in ALLOWED_DTYPES, f"{field['name']} bad dtype"
