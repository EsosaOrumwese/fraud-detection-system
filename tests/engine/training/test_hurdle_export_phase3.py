from __future__ import annotations

import yaml
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.training.hurdle import (
    MerchantUniverseSources,
    generate_export_bundle,
)
from engine.layers.l1.seg_1A.s0_foundations import (
    load_hurdle_coefficients,
    load_dispersion_coefficients,
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


def test_generate_export_bundle(tmp_path: Path) -> None:
    config_path = Path("config/models/hurdle/hurdle_simulation.priors.yaml")
    run_base = tmp_path / "runs"
    output_dir = tmp_path / "exports"
    timestamp = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)

    bundle = generate_export_bundle(
        config_path=config_path,
        sources=_sources(),
        run_base=run_base,
        output_dir=output_dir,
        version="2025-10-09",
        timestamp=timestamp,
    )

    assert bundle.hurdle_yaml.exists()
    assert bundle.dispersion_yaml.exists()

    hurdle_doc = yaml.safe_load(bundle.hurdle_yaml.read_text(encoding="utf-8"))
    disp_doc = yaml.safe_load(bundle.dispersion_yaml.read_text(encoding="utf-8"))

    assert hurdle_doc["version"] == "2025-10-09"
    assert disp_doc["version"] == "2025-10-09"
    assert "beta" in hurdle_doc and "beta_mu" in hurdle_doc
    assert "beta_phi" in disp_doc

    hurdle = load_hurdle_coefficients(hurdle_doc)
    dispersion = load_dispersion_coefficients(
        disp_doc,
        reference=hurdle.dictionaries,
    )

    assert np.allclose(hurdle.beta, bundle.fit.beta)
    assert np.allclose(hurdle.beta_mu, bundle.fit.beta_mu)
    assert np.allclose(dispersion.beta_phi, bundle.fit.beta_phi)
