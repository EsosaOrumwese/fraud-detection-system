"""Persistence utilities for S5 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .builder import WeightRow


@dataclass
class PersistConfig:
    parameter_hash: str
    output_dir: Path


def write_ccy_country_weights(
    rows: Iterable[WeightRow],
    config: PersistConfig,
) -> None:
    """TODO: write parquet + receipt."""
    raise NotImplementedError
