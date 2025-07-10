import numpy as np
import pytest
from datetime import date, timedelta

from fraud_detection.simulator.temporal import sample_timestamps  # type: ignore


def test_sample_timestamps_length_and_type():
    start, end = date(2025, 6, 1), date(2025, 6, 3)
    ts = sample_timestamps(100, start, end, seed=123)
    # length & dtype
    assert isinstance(ts, np.ndarray)
    assert ts.dtype == "datetime64[ns]"
    assert ts.shape == (100,)


def test_seed_reproducibility():
    a = sample_timestamps(50, date(2025, 6, 1), date(2025, 6, 1), seed=42)
    b = sample_timestamps(50, date(2025, 6, 1), date(2025, 6, 1), seed=42)
    assert np.array_equal(a, b)


def test_date_bounds_and_errors():
    # all timestamps within range
    start, end = date(2025, 6, 1), date(2025, 6, 1)
    ts = sample_timestamps(20, start, end, seed=7)
    assert ts.min() >= np.datetime64(start, "ns")
    assert ts.max() < np.datetime64(end + timedelta(days=1), "ns")

    # negative rows
    with pytest.raises(ValueError):
        sample_timestamps(-1, start, end, seed=0)
    # end before start
    bad_start, bad_end = date(2025, 6, 2), date(2025, 6, 1)
    with pytest.raises(ValueError):
        sample_timestamps(10, bad_start, bad_end, seed=0)


def test_diurnal_pattern_presence():
    # Over many samples, ensure peaks exist around morning/afternoon/evening
    start, end = date(2025, 6, 1), date(2025, 6, 1)
    ts = sample_timestamps(50000, start, end, seed=99)
    hours = ts.astype("datetime64[h]").astype(int) % 24
    # Compute histogram for hours
    hist = np.bincount(hours, minlength=24)
    # Check that morning bin (~9h) > midnight bin (~0h)
    assert hist[9] > hist[0]
    # Afternoon (~13h) > early morning (~6h)
    assert hist[13] > hist[6]
    # Evening (~20h) > early morning (~6h)
    assert hist[20] > hist[6]
