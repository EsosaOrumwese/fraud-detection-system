#!/usr/bin/env python3
"""
Render Markdown data dictionary from YAML schema.
Usage:
    poetry run python scripts/schema_to_md.py \
        > docs/data-dictionary/schema_v0.1.0.md
"""
import io
import sys
from pathlib import Path

import yaml  # type: ignore

# 1) Ensure our output is really UTF-8:
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 2) Read the schema as UTF-8 (and strip any BOM if present)
schema_path = Path("schema/transaction_schema.yaml")
with schema_path.open("r", encoding="utf-8-sig") as f:
    schema = yaml.safe_load(f)

# 3) Build the MD
version = schema.get("version", "0.0.0")
desc = schema.get("description", "").strip()

# If downstream tools really hate the em-dash, swap it for a hyphen here.
header = f"# Data Dictionary - v{version}\n\n{desc}\n\n"

table_head = (
    "| Name | Type | Null? | Description |\n" "|------|------|-------|-------------|\n"
)

rows = []
for f in schema["fields"]:
    # escape any pipes in your descriptions so the table doesn't break
    desc = f["description"].replace("|", r"\|")  # type: ignore
    rows.append(
        f"| `{f['name']}` | {f['dtype']} | {f['nullable']} | {desc} |"  # type: ignore
    )

print(header + table_head + "\n".join(rows))
