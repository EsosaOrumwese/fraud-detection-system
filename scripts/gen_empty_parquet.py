#!/usr/bin/env python
"""
Generate an empty Parquet with exactly the columns in your YAML schema.
"""
import yaml  # type: ignore
import pandas as pd  # type: ignore
from pathlib import Path

# Load schema
spec = yaml.safe_load(Path("config/transaction_schema.yaml")
                      .read_text(encoding="utf-8"))

# Build empty DataFrame
df = pd.DataFrame({f["name"]: [] for f in spec["fields"]})

# Ensure tmp/ exists and write
Path("tmp").mkdir(exist_ok=True)
df.to_parquet("tmp/empty.parquet")
print("✓ Generated empty parquet at tmp/empty.parquet")
