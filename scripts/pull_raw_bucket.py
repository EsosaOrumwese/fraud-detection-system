#!/usr/bin/env python
"""
scripts/pull_raw_bucket.py

Fetch the SSM parameter "/fraud/raw_bucket_name", cache it to .env via get_param(),
and print the environment‐variable assignment so Make or CI can pick it up.

Usage:
    poetry run python scripts/pull_raw_bucket.py
"""
import sys

import pathlib

# ─────────────────────────────────────────────────────────────────────────────
# Add the project root to sys.path so that "fraud_detection" is importable
# ─────────────────────────────────────────────────────────────────────────────
# Assume this script lives at <project_root>/scripts/pull_raw_bucket.py

PROJECT_ROOT = pathlib.Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fraud_detection.utils.param_store import get_param  # noqa: E402


def main():
    try:
        bucket = get_param("/fraud/raw_bucket_name")
    except Exception as e:
        print(
            f"Error: could not read /fraud/raw_bucket_name from SSM ({e})",
            file=sys.stderr,
        )
        sys.exit(1)

    # get_param already wrote "FRAUD_RAW_BUCKET_NAME=<value>" into .env.
    # We still echo it so Make or CI can grab it if needed.
    print(f"FRAUD_RAW_BUCKET_NAME={bucket}")


if __name__ == "__main__":
    main()
