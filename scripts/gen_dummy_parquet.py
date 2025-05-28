#!/usr/bin/env python
"""
Generate a one-row Parquet where every column
has a valid dummy value so that all non-null
and type expectations pass.
"""
import yaml  # type: ignore
import pandas as pd  # type: ignore
from pathlib import Path

spec = yaml.safe_load(
    Path("config/transaction_schema.yaml").read_text(encoding="utf-8")
)

row = {}
for f in spec["fields"]:
    name = f["name"]
    dt = f["dtype"]
    if dt == "string":
        row[name] = ""  # empty string is valid
    elif dt == "int":
        row[name] = 0  # type: ignore
    elif dt == "float":
        row[name] = 0.0  # type: ignore
    elif dt == "bool":
        row[name] = False  # type: ignore
    elif dt == "datetime":
        # pick an arbitrary valid timestamp
        row[name] = pd.Timestamp("2000-01-01T00:00:00Z")
    elif dt == "enum":
        # use the first allowed value
        row[name] = f["enum"][0]
    else:
        row[name] = None  # type: ignore

df = pd.DataFrame([row])
Path("tmp").mkdir(exist_ok=True)
df.to_parquet("tmp/dummy.parquet")
print("✓ Generated dummy parquet at tmp/dummy.parquet")
