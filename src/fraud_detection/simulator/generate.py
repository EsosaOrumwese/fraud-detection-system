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

import sys
from pathlib import Path

from fraud_detection.simulator.core import generate_dataframe, write_parquet
from fraud_detection.simulator.cli import main as _cli_main
from fraud_detection.simulator.config import load_config

# Back-compat API: generate_dataset(total_rows, out_dir) → writes & returns a Parquet path
def generate_dataset(total_rows: int, out_dir: Path, fraud_rate: float) -> Path:
    """
    Generate `total_rows` synthetic transactions and write them as a Parquet file under `out_dir`.
    """
    # 1) Load your standard YAML config
    cfg = load_config(Path("project_config/generator_config.yaml"))
    # 2) Override just the row-count and output directory
    cfg.total_rows = total_rows
    cfg.out_dir     = out_dir
    cfg.fraud_rate  = fraud_rate

    # 3) Generate the DataFrame
    df = generate_dataframe(cfg)

    # 4) Ensure directory exists and write
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"dataset_{total_rows}.parquet"
    write_parquet(df, out_path)
    return out_path

__all__ = ["generate_dataset", "write_parquet", "main"]


def main() -> None:
    """CLI entrypoint for backwards compatibility."""
    return _cli_main()


if __name__ == "__main__":
    sys.exit(main())  # type: ignore
