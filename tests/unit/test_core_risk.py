import numpy as np
import pytest
import polars as pl
from pathlib import Path
from datetime import date

from fraud_detection.simulator.core import generate_dataframe  # type: ignore
from fraud_detection.simulator.config import (  # type: ignore
    CatalogConfig,
    TemporalConfig,
    GeneratorConfig,
)
from fraud_detection.simulator.catalog import generate_card_catalog  # type: ignore

def make_generator_config(tmp_path: Path) -> GeneratorConfig:
    catalog = CatalogConfig(
        num_customers=3,
        customer_zipf_exponent=1.0,
        num_merchants=3,
        merchant_zipf_exponent=1.0,
        merchant_risk_alpha=2.0,
        merchant_risk_beta=5.0,
        num_cards=3,
        card_zipf_exponent=1.0,
        card_risk_alpha=2.0,
        card_risk_beta=5.0,
    )
    temporal = TemporalConfig(start_date=date(2025,6,1), end_date=date(2025,6,1))
    return GeneratorConfig(
        total_rows=500,
        fraud_rate=0.5,
        seed=7,
        catalog=catalog,
        temporal=temporal,
        out_dir=tmp_path,   # unused by generate_dataframe
        s3_upload=False,
    )

def test_generate_dataframe_core_columns_and_types(tmp_path):
    cfg = make_generator_config(tmp_path)
    df = generate_dataframe(
        total_rows=cfg.total_rows,
        catalog_cfg=cfg.catalog,
        fraud_rate=cfg.fraud_rate,
        seed=cfg.seed,
        start_date=cfg.temporal.start_date,
        end_date=cfg.temporal.end_date,
    )
    # Core columns exist
    for col in ["transaction_id", "event_time", "customer_id",
                "merchant_id", "card_pan_hash", "label_fraud"]:
        assert col in df.columns

    # Types
    assert df["transaction_id"].dtype == pl.Utf8
    assert df["event_time"].dtype == pl.Datetime
    assert df["customer_id"].dtype == pl.Int64
    assert df["merchant_id"].dtype == pl.Int64
    assert df["card_pan_hash"].dtype == pl.Utf8
    assert df["label_fraud"].dtype == pl.Boolean

def test_card_pan_hash_matches_catalog(tmp_path):
    cfg = make_generator_config(tmp_path)
    # regenerate card catalog for pan_hash reference
    card_cat = generate_card_catalog(
        num_cards=cfg.catalog.num_cards,
        zipf_exponent=cfg.catalog.card_zipf_exponent,
        seed=cfg.seed,
        risk_alpha=cfg.catalog.card_risk_alpha,
        risk_beta=cfg.catalog.card_risk_beta,
    )
    pan_set = set(card_cat["pan_hash"].to_list())

    df = generate_dataframe(
        total_rows=cfg.total_rows,
        catalog_cfg=cfg.catalog,
        fraud_rate=cfg.fraud_rate,
        seed=cfg.seed,
        start_date=cfg.temporal.start_date,
        end_date=cfg.temporal.end_date,
    )
    # Every card_pan_hash in the output should come from the catalog
    out_hashes = df["card_pan_hash"].to_list()
    assert set(out_hashes).issubset(pan_set)

def test_reproducibility(tmp_path):
    cfg = make_generator_config(tmp_path)
    df1 = generate_dataframe(
        total_rows=cfg.total_rows,
        catalog_cfg=cfg.catalog,
        fraud_rate=cfg.fraud_rate,
        seed=cfg.seed,
        start_date=cfg.temporal.start_date,
        end_date=cfg.temporal.end_date,
    )
    df2 = generate_dataframe(
        total_rows=cfg.total_rows,
        catalog_cfg=cfg.catalog,
        fraud_rate=cfg.fraud_rate,
        seed=cfg.seed,
        start_date=cfg.temporal.start_date,
        end_date=cfg.temporal.end_date,
    )
    # DataFrames should be exactly equal
    assert df1.to_pandas().equals(df2.to_pandas())
