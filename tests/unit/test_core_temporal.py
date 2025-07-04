import pandas as pd  # type: ignore
import polars as pl
import pytest
from datetime import date
from pathlib import Path

from fraud_detection.simulator.core import generate_dataframe  # type: ignore
from fraud_detection.simulator.config import load_config, GeneratorConfig  # type: ignore

def test_generate_dataframe_injection_of_timestamps(tmp_path):
    cfg = load_config(Path("project_config/generator_config.yaml"))
    # make this a small chunk for testing
    cfg.total_rows = 100
    # force the one-day window we expect
    cfg.temporal.start_date = date(2025, 6, 1)
    cfg.temporal.end_date   = date(2025, 6, 1)
    df = generate_dataframe(cfg)
    # Check type & shape
    assert isinstance(df, pl.DataFrame)
    assert df.height == 100
    # event_time column exists and has the correct datetime64[ns, UTC] dtype
    assert df.schema["event_time"] == pl.Datetime("ns", "UTC")
    # All values on the correct date
    pd_ts = df["event_time"].to_pandas()
    assert (pd_ts.dt.date == date(2025,6,1)).all()

def test_temporal_error_propagation():
    # error when end_date is before start_date
    cfg = load_config(Path("project_config/generator_config.yaml"))
    cfg.temporal.start_date = date(2025, 6, 2)
    cfg.temporal.end_date   = date(2025, 6, 1)
    with pytest.raises(ValueError) as exc:
        generate_dataframe(cfg)
    assert "Temporal sampling failed" in str(exc.value)
