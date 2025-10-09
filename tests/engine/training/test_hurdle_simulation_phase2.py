from __future__ import annotations

from pathlib import Path

import polars as pl
import polars.testing as plt

from engine.training.hurdle import (
    MerchantUniverseSources,
    load_simulation_config,
    simulate_hurdle_corpus,
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


def test_simulate_hurdle_corpus_reproducible() -> None:
    config = load_simulation_config(
        Path("config/models/hurdle/hurdle_simulation.priors.yaml")
    )
    corpus = simulate_hurdle_corpus(sources=_sources(), config=config)
    corpus_repeat = simulate_hurdle_corpus(sources=_sources(), config=config)

    plt.assert_frame_equal(corpus.logistic, corpus_repeat.logistic)
    plt.assert_frame_equal(corpus.nb_mean, corpus_repeat.nb_mean)
    plt.assert_frame_equal(corpus.brand_aliases, corpus_repeat.brand_aliases)


def test_simulate_hurdle_corpus_structure() -> None:
    config = load_simulation_config(
        Path("config/models/hurdle/hurdle_simulation.priors.yaml")
    )
    corpus = simulate_hurdle_corpus(sources=_sources(), config=config)

    assert corpus.logistic.height > 0
    assert set(corpus.logistic["channel"].unique()) <= {"CP", "CNP"}
    assert corpus.logistic["is_multi"].dtype == pl.Boolean

    if corpus.nb_mean.height > 0:
        assert corpus.nb_mean["k_domestic"].min() >= 2

    summary = corpus.summary()
    assert summary["rows_logistic"] == corpus.logistic.height
    assert summary["rows_nb"] == corpus.nb_mean.height
