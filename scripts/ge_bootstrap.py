#!/usr/bin/env python
"""
Bootstrap a GE 1.4.5 FileDataContext and build an ExpectationSuite
that mirrors your YAML schema.
"""
import sys
from pathlib import Path

import yaml  # type: ignore
import great_expectations as gx
from great_expectations.core.expectation_suite import ExpectationSuite
from great_expectations.expectations.core import (
    ExpectColumnToExist,
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeOfType,
    ExpectColumnValuesToBeInSet,
)

# ─── Constants ─────────────────────────────────────────────────────────────────
SCHEMA_PATH = Path("config/transaction_schema.yaml")  # Your source schema
CTX_DIR = Path("great_expectations")  # GE project folder
SUITE_NAME = "txn_schema_suite"  # Suite identifier

# ─── 1) Load YAML schema ───────────────────────────────────────────────────────
if not SCHEMA_PATH.exists():
    sys.exit(f"ERROR: schema not found at {SCHEMA_PATH}")
spec = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))

# ─── 2) Initialize / load the GE Data Context ─────────────────────────────────
ctx = gx.get_context(context_root_dir=str(CTX_DIR))

# ─── 3) Remove any existing suite of the same name ────────────────────────────
if any(s.name == SUITE_NAME for s in ctx.suites.all()):
    ctx.suites.delete(name=SUITE_NAME)

# ─── 4) Create a fresh ExpectationSuite object and register it ───────────────
suite = ExpectationSuite(name=SUITE_NAME)
suite = ctx.suites.add(suite)

# ─── 5) Map your YAML dtypes → pandas dtypes for GE dtype checks ──────────────
dtype_map = {
    "string": "object",
    "int": "int64",
    "float": "float64",
    "bool": "bool",
    "datetime": "Timestamp",
    "enum": "object",
}

# ─── 6) Loop through fields and add expectations ───────────────────────────────
for field in spec["fields"]:
    col = field["name"]

    # a) Column must exist
    suite.add_expectation(ExpectColumnToExist(column=col))

    # b) Column must not have nulls (if nullable=False)
    if not field["nullable"]:
        suite.add_expectation(ExpectColumnValuesToNotBeNull(column=col))

    # c) Column values must match the expected pandas dtype
    suite.add_expectation(
        ExpectColumnValuesToBeOfType(
            column=col,
            type_=dtype_map[field["dtype"]],
            # ignore_row_if="all_values_are_missing",
        )
    )

    # d) If the field is an enum, values must be in that set
    if field.get("enum"):
        suite.add_expectation(
            ExpectColumnValuesToBeInSet(
                column=col,
                value_set=field["enum"],
                # ignore_row_if="all_values_are_missing",
            )
        )

# ─── Done: report how many expectations were created ──────────────────────────
print(
    f"✓ Expectation suite '{SUITE_NAME}' created with {len(suite.expectations)} expectations"
)
