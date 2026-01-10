from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.training.hurdle import (
    MerchantUniverseSources,
    build_design_matrices,
    load_persisted_corpus,
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
    iso_root = Path("reference/iso/iso3166_canonical")
    gdp_root = Path("reference/economic/world_bank_gdp_per_capita")
    bucket_root = Path("reference/economic/gdp_bucket_map")
    return MerchantUniverseSources(
        merchant_table=_latest_partition(merchant_root) / "transaction_schema_merchant_ids.parquet",
        iso_table=_latest_partition(iso_root) / "iso3166.parquet",
        gdp_table=_latest_partition(gdp_root) / "gdp.parquet",
        bucket_table=_latest_partition(bucket_root) / "gdp_bucket_map.parquet",
    )


def test_build_design_matrices(tmp_path: Path) -> None:
    config_path = Path("config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml")
    sources = _sources()
    timestamp = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    artefacts = materialise_simulated_corpus(
        output_base=tmp_path,
        config_path=config_path,
        sources=sources,
        timestamp=timestamp,
    )

    corpus = load_persisted_corpus(artefacts.manifest_path)
    matrices = build_design_matrices(corpus)

    dicts = matrices.dictionaries
    assert len(dicts.channel) <= 2

    expected_h_cols = 1 + len(dicts.mcc) + len(dicts.channel) + len(dicts.gdp_bucket)
    assert matrices.x_hurdle.shape[1] == expected_h_cols
    assert matrices.x_nb_mean.shape[1] == 1 + len(dicts.mcc) + len(dicts.channel)
    assert matrices.x_dispersion.shape[1] == 1 + len(dicts.mcc) + len(dicts.channel) + 1

    # logistic labels align with design rows
    assert matrices.x_hurdle.shape[0] == matrices.y_hurdle.shape[0] == len(matrices.hurdle_brand_ids)
    assert matrices.x_nb_mean.shape[0] == matrices.y_nb.shape[0] == matrices.x_dispersion.shape[0]

    # Ensure design matrices are full rank in intercept column
    assert np.all(matrices.x_hurdle[:, 0] == 1.0)
    assert np.all(matrices.x_nb_mean[:, 0] == 1.0)
    assert np.all(matrices.x_dispersion[:, 0] == 1.0)
