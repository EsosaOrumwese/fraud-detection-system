"""Persistence utilities for S5 outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .builder import CurrencyResult, WeightRow

__all__ = [
    "PersistConfig",
    "write_ccy_country_weights",
    "write_validation_receipt",
]


@dataclass
class PersistConfig:
    parameter_hash: str
    output_dir: Path
    emit_validation: bool = True


def write_ccy_country_weights(
    results: Iterable[CurrencyResult],
    config: PersistConfig,
) -> Path:
    """Persist the currency→country weights cache to parquet."""

    result_list = list(results)

    records: List[dict] = []
    for result in result_list:
        for row in result.weights:
            records.append(
                {
                    "parameter_hash": config.parameter_hash,
                    "currency": row.currency,
                    "country_iso": row.country_iso,
                    "weight": row.weight,
                    "obs_count": result.obs_count,
                }
            )

    df = pd.DataFrame.from_records(
        records,
        columns=["parameter_hash", "currency", "country_iso", "weight", "obs_count"],
    )
    df = df.sort_values(["currency", "country_iso"]).reset_index(drop=True)

    target_dir = (
        config.output_dir
        / "ccy_country_weights_cache"
        / f"parameter_hash={config.parameter_hash}"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "part-0000.parquet"
    df.to_parquet(path, index=False)

    if config.emit_validation:
        write_validation_receipt(result_list, config, target_dir)

    return path


def write_validation_receipt(
    results: Iterable[CurrencyResult],
    config: PersistConfig,
    target_dir: Path | None = None,
) -> Path:
    """Write the S5 validation receipt alongside the weights cache."""

    dest_dir = (
        target_dir
        if target_dir is not None
        else config.output_dir
        / "ccy_country_weights_cache"
        / f"parameter_hash={config.parameter_hash}"
    )
    dest_dir.mkdir(parents=True, exist_ok=True)

    receipt = {
        "parameter_hash": config.parameter_hash,
        "currencies": [
            {
                "currency": result.currency,
                "n_eff": result.n_eff,
                "obs_count": result.obs_count,
                "degrade_mode": result.degrade_mode,
                "degrade_reason": result.degrade_reason,
            }
            for result in results
        ],
    }

    receipt_path = dest_dir / "S5_VALIDATION.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    passed_flag = dest_dir / "_passed.flag"
    passed_flag.write_text("PASS\n", encoding="utf-8")

    return receipt_path
