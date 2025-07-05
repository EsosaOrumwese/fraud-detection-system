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
from datetime import date

from fraud_detection.simulator.core import generate_dataframe, write_parquet
from fraud_detection.simulator.cli import main as _cli_main
from fraud_detection.simulator.config import load_config, GeneratorConfig


def generate_dataset(cfg: GeneratorConfig) -> Path:
    """
    Generate `total_rows` synthetic transactions and write them as a Parquet file under `out_dir`.
    """
    # 1) Generate the DataFrame
    df = generate_dataframe(cfg)

    # 2) Get filename
    today = date.today()
    year = today.year
    month = f"{today.month:02d}"
    filename = f"payments_{cfg.total_rows:_}_{today.isoformat()}.parquet"

    # 2) Ensure directory exists and write
    local_dir = cfg.out_dir / "payments" / f"year={year}" / f"month={month}"
    # cfg.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = local_dir / filename
    write_parquet(df, out_path)
    return out_path

__all__ = ["generate_dataset", "write_parquet", "main"]


def main() -> None:
    """CLI entrypoint for backwards compatibility."""
    return _cli_main()


if __name__ == "__main__":
    sys.exit(main())  # type: ignore
