#!/usr/bin/env python3
"""
Bump schema version.
Usage:
    poetry run python scripts/bump_schema_version.py patch
"""
import sys
import pathlib
import yaml  # type: ignore

kind = sys.argv[1] if len(sys.argv) > 1 else "patch"
path = pathlib.Path("config/transaction_schema.yaml")
doc = yaml.safe_load(path.read_text())

major, minor, patch = map(int, doc["version"].split("."))
if kind == "major":
    major, minor, patch = major + 1, 0, 0
elif kind == "minor":
    minor, patch = minor + 1, 0
else:
    patch += 1

doc["version"] = f"{major}.{minor}.{patch}"
path.write_text(yaml.safe_dump(doc, sort_keys=False))
print(f"Bumped to v{doc['version']}")
