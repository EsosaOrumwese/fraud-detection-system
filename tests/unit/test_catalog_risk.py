import numpy as np
import pytest
import polars as pl

from fraud_detection.simulator.catalog import (  # type: ignore
    generate_merchant_catalog,
    generate_card_catalog,
)


def test_merchant_catalog_risk_and_weights():
    df = generate_merchant_catalog(
        num_merchants=5,
        zipf_exponent=1.0,
        seed=42,
        risk_alpha=2.0,
        risk_beta=5.0,
    )
    # Columns & types
    assert list(df.columns) == ["merchant_id", "weight", "risk", "mcc_code"]
    assert df.schema["merchant_id"] == pl.Int32
    assert df.schema["weight"] == pl.Float64
    assert df.schema["risk"] == pl.Float64
    assert df.schema["mcc_code"] == pl.Int32

    # Length & sums
    assert df.height == 5
    assert pytest.approx(1.0, rel=1e-12) == df["weight"].sum()
    # Risk bounded [0,1]
    assert df["risk"].min() >= 0
    assert df["risk"].max() <= 1

    # Reproducibility: same seed ⇒ same risk array
    df2 = generate_merchant_catalog(
        num_merchants=5,
        zipf_exponent=1.0,
        seed=42,
        risk_alpha=2.0,
        risk_beta=5.0,
    )
    np.testing.assert_array_almost_equal(
        df["risk"].to_numpy(),
        df2["risk"].to_numpy(),
    )


def test_card_catalog_risk_and_pan_hash():
    df = generate_card_catalog(
        num_cards=5,
        zipf_exponent=1.0,
        seed=123,
        risk_alpha=2.0,
        risk_beta=5.0,
    )
    # Columns & types
    assert list(df.columns) == ["card_id", "weight", "risk", "pan_hash"]
    assert df.schema["card_id"] == pl.Int32
    assert df.schema["weight"] == pl.Float64
    assert df.schema["risk"] == pl.Float64
    assert df.schema["pan_hash"] == pl.Utf8

    # Length, weight sum, risk bounds
    assert df.height == 5
    assert pytest.approx(1.0, rel=1e-12) == df["weight"].sum()
    assert df["risk"].min() >= 0
    assert df["risk"].max() <= 1

    # pan_hash uniqueness
    pan_list = df["pan_hash"].to_list()
    assert len(pan_list) == len(set(pan_list))

    # Seed reproducibility: same seed ⇒ same pan_hash sequence
    df2 = generate_card_catalog(
        num_cards=5,
        zipf_exponent=1.0,
        seed=123,
        risk_alpha=2.0,
        risk_beta=5.0,
    )
    assert pan_list == df2["pan_hash"].to_list()
