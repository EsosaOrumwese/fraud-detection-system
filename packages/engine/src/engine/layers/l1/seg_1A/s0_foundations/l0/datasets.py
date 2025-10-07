"""Input helpers for S0 datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import polars as pl
import yaml

from ..exceptions import err


def load_parquet_table(path: Path) -> pl.DataFrame:
    """Load a Parquet dataset from a file or directory."""

    if path.is_file():
        return pl.read_parquet(path)
    if path.is_dir():
        pattern = str(path / "*.parquet")
        lf = pl.scan_parquet(pattern)
        try:
            return lf.collect()
        except FileNotFoundError as exc:
            raise err(
                "E_DATASET_EMPTY", f"no Parquet files found under '{path}'"
            ) from exc
    raise err("E_DATASET_NOT_FOUND", f"dataset path '{path}' does not exist")


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise err("E_PARAM_IO", f"YAML artefact '{path}' not found")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise err("E_YAML_ROOT", f"YAML artefact '{path}' must decode to a mapping")
    return data


__all__ = ["load_parquet_table", "load_yaml"]
