import math

import numpy as np
import polars as pl

from fraud_detection.simulator.catalog import generate_customer_catalog


def test_customer_zipf_top_10_percent_skew():
    """
    The Zipf distribution used should produce a heavy tail:
    the top 10% of customers (by weight) must account for >50% of total weight.
    """
    num_customers = 1000
    zipf_exponent = 1.2

    # Generate the catalog (Polars DataFrame with columns "customer_id", "weight")
    cust_cat: pl.DataFrame = generate_customer_catalog(
        num_customers=num_customers,
        zipf_exponent=zipf_exponent,
    )
    # Extract weights as a NumPy array
    weights = cust_cat["weight"].to_numpy()

    # Sanity checks
    assert weights.shape[0] == num_customers, "Catalog length mismatch"
    assert np.isclose(weights.sum(), 1.0, atol=1e-8), "Weights do not sum to 1.0"

    # Sort descending and sum the top 10%
    sorted_w = np.sort(weights)[::-1]
    top_n = math.ceil(num_customers * 0.10)
    top_sum = sorted_w[:top_n].sum()

    assert top_sum > 0.5, f"Top 10% weights sum to {top_sum:.3f}, expected > 0.5"
