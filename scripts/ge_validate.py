#!/usr/bin/env python
"""
Validate a Parquet or CSV file against txn_schema_suite using
Great Expectations 1.4.5’s V1 ValidationDefinition API.
"""
import sys
from pathlib import Path

import pandas as pd  # type: ignore
import great_expectations as gx
from great_expectations.core.validation_definition import ValidationDefinition
from great_expectations.exceptions import DataContextError

# ─── 1) Parse & load your data file ───────────────────────────────────────────
if len(sys.argv) != 2:
    sys.exit("Usage: ge_validate.py <file.{parquet|csv}>")

file_path = Path(sys.argv[1])
if not file_path.exists():
    sys.exit(f"ERROR: file not found: {file_path}")

if file_path.suffix == ".parquet":
    df = pd.read_parquet(file_path)
elif file_path.suffix == ".csv":
    df = pd.read_csv(file_path)
else:
    sys.exit("ERROR: supported formats: .parquet, .csv")

# ─── 2) Load your GX context & suite ──────────────────────────────────────────
ctx = gx.get_context(context_root_dir="great_expectations")
suite = ctx.suites.get(
    "txn_schema_suite"
)  # ctx.get_expectation_suite("txn_schema_suite")

# ─── 3) Ensure an in-memory Pandas DataFrame DataSource is registered ────────
DS_NAME = "runtime_pandas"
ASSET_NAME = "batch_df_asset"
BATCH_DEF = "whole_dataframe_batch"

# Fetch or add the Pandas datasource
try:
    pandas_ds = ctx.data_sources.get(DS_NAME)
except Exception:
    pandas_ds = ctx.data_sources.add_pandas(name=DS_NAME)

# Fetch or add the DataFrame asset
try:
    df_asset = pandas_ds.get_asset(ASSET_NAME)
except Exception:
    df_asset = pandas_ds.add_dataframe_asset(name=ASSET_NAME)  # type: ignore

# Fetch or add the single “whole dataframe” Batch Definition
if not any(bd.name == BATCH_DEF for bd in df_asset.batch_definitions):
    df_asset.add_batch_definition_whole_dataframe(name=BATCH_DEF)

# Retrieve that BatchDefinition
batch_def = df_asset.get_batch_definition(BATCH_DEF)

# ─── 4) Build a ValidationDefinition linking batch_def ↔ suite ───────────────
VD_NAME = "validate_txn_schema"
try:
    vd = ctx.validation_definitions.get(name=VD_NAME)
except DataContextError:
    vd = ctx.validation_definitions.add(
        ValidationDefinition(
            name=VD_NAME,
            data=batch_def,
            suite=suite,
        )
    )

# ─── 5) Run it with our in-memory DataFrame ─────────────────────────────────
# For a dataframe asset, the batch_parameter key is "dataframe"
# noinspection PyTypeChecker
results = vd.run(
    batch_parameters={"dataframe": df},
    result_format={"result_format": "BASIC"}
)
# After running validation, to print out the failed expectations:
for r in results["results"]:
    if not r["success"]:
        ep = r["expectation_config"]              # this is an ExpectationConfiguration
        # access attributes, not dictionary keys:
        print(f"✗ {ep.type} failed on {ep.kwargs}")

print(f"Validation success: {results.success}")
sys.exit(0 if results.success else 1)
