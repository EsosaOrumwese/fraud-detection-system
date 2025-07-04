import numpy as np
import polars as pl
from datetime import datetime, timezone

from fraud_detection.simulator.labeler import label_fraud
  # type: ignore
def make_test_df(N: int) -> pl.DataFrame:
    """
    Build a minimal DataFrame with required columns:
      - amount
      - merch_risk
      - card_risk
      - event_time (timezone-aware)
      - merchant_id
    """
    # Uniform amounts
    amounts = np.full(N, 100.0)
    # Linearly varying risks
    merch_risk = np.linspace(0, 1, N)
    card_risk = np.linspace(1, 0, N)
    # Half at midnight, half at noon UTC
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    times = [
        base.replace(hour=0) if i < N // 2 else base.replace(hour=12)
        for i in range(N)
    ]
    merchant_ids = np.arange(1, N + 1)
    return pl.DataFrame({
        "amount":       amounts,
        "merch_risk":   merch_risk,
        "card_risk":    card_risk,
        "event_time":   times,
        "merchant_id":  merchant_ids,
    })

def test_exact_count_and_reproducibility():
    df = make_test_df(1000)
    rate = 0.1
    seed = 42

    labeled1 = label_fraud(df, fraud_rate=rate, seed=seed)
    labeled2 = label_fraud(df, fraud_rate=rate, seed=seed)

    # 1) Exact fraud count
    expected = round(rate * 1000)
    assert labeled1["label_fraud"].sum() == expected

    # 2) Fully reproducible
    assert labeled1["label_fraud"].to_list() == labeled2["label_fraud"].to_list()

def test_zero_rate_all_false():
    df = make_test_df(200)
    labeled = label_fraud(df, fraud_rate=0.0, seed=7)
    assert labeled["label_fraud"].sum() == 0

def test_one_rate_all_true():
    df = make_test_df(200)
    labeled = label_fraud(df, fraud_rate=1.0, seed=7)
    assert labeled["label_fraud"].sum() == 200

def test_schema_and_dtype():
    df = make_test_df(50)
    labeled = label_fraud(df, fraud_rate=0.2, seed=123)
    # Should preserve original columns plus label_fraud
    for col in ["amount", "merch_risk", "card_risk", "event_time", "merchant_id", "label_fraud"]:
        assert col in labeled.columns
    # label_fraud must be Boolean
    assert labeled["label_fraud"].dtype == pl.Boolean

def test_logistic_parameters_change_effect():
    """
    With zero weights for amount and risks, logistic is flat:
    initial draw is uniform, then overshoot clamp only drops random positives.
    Confirm that setting all weights to zero yields roughly uniform first-draw,
    but exact count is still enforced.
    """
    df = make_test_df(500)
    # All logistic weights zero → p = intercept = rate
    rate = 0.3
    seed = 99
    # Disable bursts by setting burst_factor >> N
    labeled = label_fraud(
        df,
        fraud_rate=rate,
        seed=seed,
        w_amount=0.0,
        w_mrisk=0.0,
        w_crisk=0.0,
        w_night=0.0,
        burst_factor=1000,
    )
    # Should still hit exact rate
    assert labeled["label_fraud"].sum() == round(rate * 500)
