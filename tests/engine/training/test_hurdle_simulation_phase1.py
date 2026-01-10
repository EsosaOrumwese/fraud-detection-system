from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from engine.training.hurdle import (
    MerchantUniverseSources,
    load_enriched_universe,
    load_simulation_config,
)


def _latest_partition(root: Path) -> Path:
    partitions = sorted(p for p in root.iterdir() if p.is_dir())
    if not partitions:
        raise RuntimeError(f"no partitions found under {root}")
    return partitions[-1]


def test_load_simulation_config() -> None:
    config_path = Path("config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml")
    cfg = load_simulation_config(config_path)

    assert cfg.rng.seed > 0
    assert cfg.hurdle.bucket_offset(5) > cfg.hurdle.bucket_offset(1)
    assert cfg.nb_mean.channel_offset("CNP") < 0.0
    assert cfg.dispersion.gdp_log_slope < 0.0


def test_load_enriched_universe() -> None:
    merchant_root = Path("reference/layer1/transaction_schema_merchant_ids")
    iso_root = Path("reference/iso/iso3166_canonical")
    gdp_root = Path("reference/economic/world_bank_gdp_per_capita")
    bucket_root = Path("reference/economic/gdp_bucket_map")

    sources = MerchantUniverseSources(
        merchant_table=_latest_partition(merchant_root) / "transaction_schema_merchant_ids.parquet",
        iso_table=_latest_partition(iso_root) / "iso3166.parquet",
        gdp_table=_latest_partition(gdp_root) / "gdp.parquet",
        bucket_table=_latest_partition(bucket_root) / "gdp_bucket_map.parquet",
    )

    df = load_enriched_universe(sources)

    expected_columns = {
        "merchant_id",
        "mcc",
        "channel",
        "country_iso",
        "gdp_bucket",
        "gdp_pc_usd_2015",
        "ln_gdp_pc_usd_2015",
    }
    assert expected_columns.issubset(set(df.columns))

    sample = df.select(["gdp_pc_usd_2015", "ln_gdp_pc_usd_2015"]).head(10)
    nulls = sample.null_count().select(pl.all().sum()).row(0)[0]
    assert nulls == 0

    for row in sample.iter_rows(named=True):
        assert math.isclose(
            row["ln_gdp_pc_usd_2015"],
            math.log(row["gdp_pc_usd_2015"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
