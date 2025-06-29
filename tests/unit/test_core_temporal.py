import pandas as pd  # type: ignore
import polars as pl
import pytest
from datetime import date

from fraud_detection.simulator.core import generate_dataframe  # type: ignore

def test_generate_dataframe_injection_of_timestamps(tmp_path):
    cfg = dict(total_rows=100,
               fraud_rate=0.0,
               seed=123,
               start_date=date(2025,6,1),
               end_date=date(2025,6,1))
    df = generate_dataframe(**cfg)
    # Check type & shape
    assert isinstance(df, pl.DataFrame)
    assert df.height == 100
    # event_time column exists and has the correct datetime64[ns, UTC] dtype
    assert df.schema["event_time"] == pl.Datetime("ns", "UTC")
    # All values on the correct date
    pd_ts = df["event_time"].to_pandas()
    assert (pd_ts.dt.date == date(2025,6,1)).all()

def test_temporal_error_propagation():
    # end_date < start_date
    with pytest.raises(ValueError) as exc:
        generate_dataframe(total_rows=10, catalog_cfg=, fraud_rate=0.5, seed=0, start_date=date(2025, 6, 5),
                           end_date=date(2025, 6, 1))
    assert "Temporal sampling failed" in str(exc.value)
