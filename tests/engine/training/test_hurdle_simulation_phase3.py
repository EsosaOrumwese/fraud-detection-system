from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from engine.training.hurdle import (
    MerchantUniverseSources,
    load_simulation_config,
    materialise_simulated_corpus,
)


def _latest_partition(root: Path) -> Path:
    partitions = sorted(p for p in root.iterdir() if p.is_dir())
    if not partitions:
        raise RuntimeError(f"no partitions found under {root}")
    return partitions[-1]


def _sources() -> MerchantUniverseSources:
    merchant_root = Path("reference/layer1/transaction_schema_merchant_ids")
    iso_root = Path("reference/layer1/iso_canonical")
    gdp_root = Path("reference/economic/world_bank_gdp_per_capita")
    bucket_root = Path("reference/economic/gdp_bucket_map")
    return MerchantUniverseSources(
        merchant_table=_latest_partition(merchant_root) / "transaction_schema_merchant_ids.parquet",
        iso_table=_latest_partition(iso_root) / "iso_canonical.parquet",
        gdp_table=_latest_partition(gdp_root) / "gdp.parquet",
        bucket_table=_latest_partition(bucket_root) / "gdp_bucket_map.parquet",
    )


def test_materialise_simulated_corpus(tmp_path: Path) -> None:
    config_path = Path("config/models/hurdle/hurdle_simulation.priors.yaml")
    sources = _sources()
    timestamp = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    artefacts = materialise_simulated_corpus(
        output_base=tmp_path,
        config_path=config_path,
        sources=sources,
        timestamp=timestamp,
    )

    assert artefacts.manifest_path.exists()
    logistic = pl.read_parquet(artefacts.dataset_paths["logistic"])
    nb_mean = pl.read_parquet(artefacts.dataset_paths["nb_mean"])

    manifest = json.loads(artefacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["simulation_config"]["config_path"] == str(config_path)
    assert manifest["simulation_config"]["rng"]["seed"] == load_simulation_config(config_path).rng.seed
    assert manifest["summary"]["rows_logistic"] == logistic.height
    assert manifest["summary"]["rows_nb"] == nb_mean.height
