import pytest
import numpy as np
from datetime import date

from fraud_detection.simulator.temporal import sample_timestamps  # type: ignore

def test_custom_time_deterministic_zero_std():
    """
    When a single component with std=0 is used, every timestamp offset
    should equal that component’s mean_hour, and repeated calls are identical.
    """
    start = end = date(2025, 7, 1)
    count, seed = 10, 42
    # mean at 14.25h = 14:15:00
    comps = [{"mean_hour": 14.25, "std_hours": 0.0, "weight": 1.0}]

    # Non-chunked
    ts1 = sample_timestamps(
        total_rows=count,
        start_date=start,
        end_date=end,
        seed=seed,
        time_components=comps
    )
    ts2 = sample_timestamps(
        total_rows=count,
        start_date=start,
        end_date=end,
        seed=seed,
        time_components=comps
    )
    # Determinism
    np.testing.assert_array_equal(ts1, ts2)

    # All times equal 14:15:00
    days = ts1.astype("datetime64[D]")
    offsets = ts1 - days
    expected = np.timedelta64(int(14.25 * 3600), "s")
    assert np.all(offsets == expected)

def test_chunked_vs_nonchunked_identical_custom_time():
    """
    With a non-uniform time_components mixture, chunking must not alter the final sequence.
    """
    start = end = date(2025, 8, 1)
    count, seed = 100, 123
    comps = [
        {"mean_hour":  6.0, "std_hours": 0.1, "weight": 0.7},
        {"mean_hour": 18.0, "std_hours": 0.2, "weight": 0.3},
    ]

    ts_no_chunk = sample_timestamps(
        total_rows=count,
        start_date=start,
        end_date=end,
        seed=seed,
        time_components=comps
    )
    ts_chunked = sample_timestamps(
        total_rows=count,
        start_date=start,
        end_date=end,
        seed=seed,
        time_components=comps,
        chunk_size=25
    )

    np.testing.assert_array_equal(ts_no_chunk, ts_chunked)

@pytest.mark.parametrize("chunk_size", [1, 50, 200])
def test_chunk_size_exact_and_large_values(chunk_size):
    """
    chunk_size values of 1, equal to count, and greater than count
    should all produce identical output to the no-chunk default.
    """
    start = end = date(2025, 9, 10)
    count, seed = 50, 7
    comps = [{"mean_hour": 12.0, "std_hours": 0.5, "weight": 1.0}]

    ts_default = sample_timestamps(
        total_rows=count,
        start_date=start,
        end_date=end,
        seed=seed,
        time_components=comps
    )
    ts_chunked = sample_timestamps(
        total_rows=count,
        start_date=start,
        end_date=end,
        seed=seed,
        time_components=comps,
        chunk_size=chunk_size
    )

    np.testing.assert_array_equal(ts_default, ts_chunked)

def test_unknown_distribution_type_still_errors():
    """
    Ensures that distribution_type validation remains in effect
    when chunking/time-components are provided.
    """
    with pytest.raises(ValueError):
        sample_timestamps(
            total_rows=5,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 1),
            seed=0,
            distribution_type="nope",
            chunk_size=2
        )
