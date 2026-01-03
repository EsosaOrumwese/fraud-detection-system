from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.training.hurdle import (
    MerchantUniverseSources,
    build_design_matrices,
    fit_hurdle_coefficients,
    load_persisted_corpus,
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


def test_fit_hurdle_coefficients(tmp_path: Path) -> None:
    config_path = Path("config/models/hurdle/hurdle_simulation.priors.yaml")
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
    fit = fit_hurdle_coefficients(matrices)

    assert fit.diagnostics.logistic_converged
    assert len(fit.beta) == matrices.x_hurdle.shape[1]
    assert len(fit.beta_mu) == matrices.x_nb_mean.shape[1]
    assert len(fit.beta_phi) == matrices.x_dispersion.shape[1]
    assert np.isfinite(fit.beta).all()
    assert np.isfinite(fit.beta_mu).all()
    assert np.isfinite(fit.beta_phi).all()
