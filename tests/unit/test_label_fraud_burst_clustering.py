import numpy as np
import polars as pl
import pytest

from fraud_detection.simulator.labeler import label_fraud  # type: ignore


def make_test_df(n_rows: int) -> pl.DataFrame:
    """
    Create a minimal DataFrame with:
      - event_time spaced hourly from a fixed epoch
      - constant amount, merch_risk, card_risk
      - single merchant_id so bursts target the same merchant
    """
    base = np.datetime64("2025-01-01T00:00:00", "ns")
    times = base + np.arange(n_rows) * np.timedelta64(1, "h")
    return pl.DataFrame(
        {
            "event_time": times,
            "amount": [1.0] * n_rows,
            "merch_risk": [0.0] * n_rows,
            "card_risk": [0.0] * n_rows,
            "merchant_id": [1] * n_rows,
        }
    )


@pytest.mark.parametrize("n_rows", [100, 200, 1000])
def test_label_fraud_exact_count_and_boolean(n_rows):
    df = make_test_df(n_rows)
    fraud_rate = 0.2

    out = label_fraud(
        df,
        fraud_rate,
        seed=42,
        w_amount=0.0,
        w_mrisk=0.0,
        w_crisk=0.0,
        w_night=0.0,
        burst_factor=5,
        burst_window_s=3600,
    )
    labels = out["label_fraud"].to_list()

    # All labels are booleans
    assert all(isinstance(x, bool) for x in labels)

    # Exactly round(50 * 0.2) = 10 frauds
    assert sum(labels) == round(n_rows * fraud_rate)


def test_label_fraud_burst_clusters_within_window():
    df = make_test_df(100)
    fraud_rate = 0.1
    burst_window_s = 7200  # 2 hours
    burst_factor = 4

    out = label_fraud(
        df,
        fraud_rate,
        seed=123,
        w_amount=0.0,
        w_mrisk=0.0,
        w_crisk=0.0,
        w_night=0.0,
        burst_factor=burst_factor,
        burst_window_s=burst_window_s,
    )
    labels = np.array(out["label_fraud"].to_list())
    # Convert event_time to int64 nanoseconds
    times = out["event_time"].to_numpy().astype("datetime64[ns]").astype("int64")

    # Total count is exact
    assert labels.sum() == round(df.height * fraud_rate)

    # Identify clusters of True labels where consecutive frauds occur within the window
    true_idxs = np.nonzero(labels)[0]
    assert true_idxs.size > 0  # sanity

    clusters = []
    cluster = [true_idxs[0]]
    for prev_idx, curr_idx in zip(true_idxs, true_idxs[1:]):
        if abs(times[curr_idx] - times[prev_idx]) <= burst_window_s * 1_000_000_000:
            cluster.append(curr_idx)
        else:
            clusters.append(cluster)
            cluster = [curr_idx]
    clusters.append(cluster)

    # Each cluster must be no larger than burst_factor
    for c in clusters:
        assert len(c) <= burst_factor
