import pytest
import numpy as np
from datetime import date

from fraud_detection.simulator.temporal import sample_timestamps  # type: ignore

def test_deterministic_uniform_seed():
    """Same seed + uniform settings always yields identical arrays."""
    start, end = date(2025, 1, 1), date(2025, 1, 7)
    count, seed = 25, 42

    ts1 = sample_timestamps(count, start, end, seed=seed)
    ts2 = sample_timestamps(count, start, end, seed=seed)

    np.testing.assert_array_equal(ts1, ts2)


def test_chunked_vs_nonchunked_identical_uniform():
    """With no weekday_weights, chunk_size splits or not must give same result."""
    start, end = date(2025, 2, 10), date(2025, 2, 20)
    count, seed = 50, 2025

    ts_no_chunk = sample_timestamps(count, start, end, seed=seed)
    ts_chunked = sample_timestamps(
        count, start, end, seed=seed, chunk_size=10
    )

    np.testing.assert_array_equal(ts_no_chunk, ts_chunked)


def test_chunked_vs_nonchunked_identical_weighted():
    """With a non-uniform weekday_weights, chunking must still match."""
    # Choose a 7-day span
    start, end = date(2025, 3, 1), date(2025, 3, 7)
    count, seed = 40, 2025
    # Weight all Mondays only (weekday() 0 → Monday)
    weights = {0: 1.0}

    ts_no_chunk = sample_timestamps(
        count, start, end, seed=seed, weekday_weights=weights
    )
    ts_chunked = sample_timestamps(
        count, start, end, seed=seed,
        weekday_weights=weights, chunk_size=5
    )

    np.testing.assert_array_equal(ts_no_chunk, ts_chunked)


def test_single_weekday_forces_date():
    """If only one weekday has non-zero weight, all sampled dates must be that weekday."""
    # Span two weeks to be sure
    start, end = date(2025, 4, 1), date(2025, 4, 14)
    count, seed = 30, 123
    # Pick Wednesday only (weekday()==2)
    weights = {2: 1.0}

    ts = sample_timestamps(
        count, start, end, seed=seed, weekday_weights=weights
    )
    # Strip time to day precision
    days = ts.astype("datetime64[D]")
    # All days must have weekday()==2
    for d in np.unique(days):
        assert int(d.astype(object).weekday()) == 2


def test_invalid_zero_sum_weekday_weights_raises():
    """Providing weights that sum to zero must error."""
    start, end = date(2025, 5, 1), date(2025, 5, 7)
    with pytest.raises(ValueError):
        sample_timestamps(
            total_rows=10,
            start_date=start,
            end_date=end,
            seed=0,
            weekday_weights={0: 0.0, 1: 0.0},
        )


def test_date_range_and_dtype():
    """All outputs lie within [start_date, end_date] and dtype is datetime64[ns]."""
    start, end = date(2025, 6, 5), date(2025, 6, 10)
    count, seed = 15, 999

    ts = sample_timestamps(count, start, end, seed=seed)
    assert ts.shape == (count,)
    assert ts.dtype == "datetime64[ns]"

    days = ts.astype("datetime64[D]")
    assert days.min() >= np.datetime64(start, "D")
    assert days.max() <= np.datetime64(end, "D")
