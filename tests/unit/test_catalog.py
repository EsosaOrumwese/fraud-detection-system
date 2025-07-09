import numpy as np
import pytest
import polars as pl

from fraud_detection.simulator.catalog import (  # type: ignore
    _zipf_weights,
    generate_customer_catalog,
    generate_merchant_catalog,
    generate_card_catalog,
    sample_entities,
)


def test_zipf_weights_sum_to_one_and_invalid():
    # Valid cases: sums to 1
    for n, s in [(1, 1.0), (10, 1.2), (100, 2.0)]:
        w = _zipf_weights(n, s)
        assert pytest.approx(1.0, rel=1e-12) == w.sum()
        assert w.shape == (n,)
    # Invalid parameters
    with pytest.raises(ValueError):
        _zipf_weights(0, 1.2)
    with pytest.raises(ValueError):
        _zipf_weights(10, 0.0)
    with pytest.raises(ValueError):
        _zipf_weights(10, -1.0)


# @pytest.mark.parametrize(
#     "func,col",
#     [
#         (generate_customer_catalog, "customer_id"),
#         (generate_merchant_catalog, "merchant_id"),
#         (generate_card_catalog, "card_id"),
#     ],
# )
def test_customer_catalog_columns_and_dtype():
    df = generate_customer_catalog(num_customers=5, zipf_exponent=1.5)
    assert list(df.columns) == ["customer_id", "weight"]
    assert df.height == 5
    assert df["customer_id"].dtype in (pl.Int32, pl.Int64)
    assert df["weight"].dtype == pl.Float64
    assert pytest.approx(1.0, rel=1e-12) == df["weight"].sum()


def test_merchant_catalog_columns_and_dtype():
    df = generate_merchant_catalog(num_merchants=5, zipf_exponent=1.5)
    assert list(df.columns) == ["merchant_id", "weight", "risk", "mcc_code"]
    assert df.height == 5
    assert df["merchant_id"].dtype in (pl.Int32, pl.Int64)
    assert df["weight"].dtype == pl.Float64
    assert df["risk"].dtype == pl.Float64
    assert df["mcc_code"].dtype == pl.Int32


def test_card_catalog_columns_and_dtype():
    df = generate_card_catalog(num_cards=5, zipf_exponent=1.5)
    assert list(df.columns) == ["card_id", "weight", "risk", "pan_hash"]
    assert df.height == 5
    assert df["card_id"].dtype in (pl.Int32, pl.Int64)
    assert df["weight"].dtype == pl.Float64
    assert df["risk"].dtype == pl.Float64
    assert df["pan_hash"].dtype == pl.Utf8


def test_sample_entities_basic_and_errors():
    # Build a tiny catalog
    df = generate_customer_catalog(num_customers=3, zipf_exponent=1.0)
    # Valid sampling
    out = sample_entities(df, "customer_id", size=10, seed=42)
    assert isinstance(out, np.ndarray)
    assert out.shape == (10,)
    # All sampled IDs within the catalog
    assert set(out).issubset(set(df["customer_id"].to_list()))
    # Invalid cases
    with pytest.raises(ValueError):
        sample_entities(pl.DataFrame({"foo": [1, 2]}), "foo", size=5)
    with pytest.raises(ValueError):
        sample_entities(df, "customer_id", size=-1)
    # Zero-weight catalog
    zero_df = pl.DataFrame({"customer_id": [1, 2, 3], "weight": [0.0, 0.0, 0.0]})
    with pytest.raises(ValueError):
        sample_entities(zero_df, "customer_id", size=1)


def test_sampling_skew_heavy_tail():
    # Large catalog to see Zipf effect
    N = 100
    df = generate_merchant_catalog(num_merchants=N, zipf_exponent=1.2)
    # Draw many samples
    samples = sample_entities(df, "merchant_id", size=100_000, seed=123)
    counts = np.bincount(samples)[1:]  # merchant_id runs 1..N
    # Check that top-ranked merchant > 10th-ranked > 50th-ranked
    assert counts[0] > counts[9] > counts[49]
