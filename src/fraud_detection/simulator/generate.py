#!/usr/bin/env python3
"""
Legacy entrypoint for the fraud simulator.

Re-exports:
- generate_dataset: the core DataFrame generator (alias for generate_dataframe)
- write_parquet: write-to-Parquet helper
- main: the CLI entrypoint

This lets existing code (Airflow DAGs, Makefile, tests) that do:
    from fraud_detection.simulator.generate import generate_dataset
continue to work unmodified.
"""

from pathlib import Path
import sys

from fraud_detection.simulator.core import generate_dataframe, write_parquet
from fraud_detection.simulator.cli import main as _cli_main

# Maintain the old API name
generate_dataset = generate_dataframe

__all__ = ["generate_dataset", "write_parquet", "main"]

def main() -> None:
    """CLI entrypoint for backwards compatibility."""
    return _cli_main()

if __name__ == "__main__":
    sys.exit(main())  # type: ignore