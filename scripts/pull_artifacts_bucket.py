#!/usr/bin/env python3
"""
scripts/pull_artifacts_bucket.py

Fetch the SSM parameter "/fraud/artifacts_bucket_name", cache it to .env via get_param(),
and print the environment‐variable assignment so Make or CI can pick it up.

Usage:
    poetry run python scripts/pull_artifacts_bucket.py
"""
import sys
import pathlib
from fraud_detection.utils.param_store import get_param  # type: ignore # noqa: E402


PROJECT_ROOT = pathlib.Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    try:
        bucket = get_param("/fraud/artifacts_bucket_name")
    except Exception as e:
        print(
            f"Error: could not read /fraud/artifacts_bucket_name from SSM ({e})",
            file=sys.stderr,
        )
        sys.exit(1)

    # get_param already wrote "FRAUD_ARTIFACTS_BUCKET_NAME=<value>" into .env.
    # We still echo it so Make or CI can grab it if needed.
    print(f"FRAUD_ARTIFACTS_BUCKET_NAME={bucket}")


if __name__ == "__main__":
    main()
