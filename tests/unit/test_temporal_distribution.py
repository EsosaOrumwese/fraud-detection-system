import pytest
import numpy as np
from datetime import date
from numpy.random import default_rng

from fraud_detection.simulator.temporal import (  # type: ignore
    get_distribution,
    TemporalDistribution,
    GaussianMixtureDistribution,
    sample_timestamps,
    _DEFAULT_TIME_COMPONENTS,
)
from fraud_detection.simulator.config import TimeComponentConfig  # type: ignore

def test_registry_contains_gaussian():
    # The factory must know about "gaussian"
    cls = get_distribution("gaussian")
    assert issubclass(cls, TemporalDistribution)

def test_get_distribution_unknown_raises():
    with pytest.raises(ValueError) as exc:
        get_distribution("not_a_real_type")
    msg = str(exc.value).lower()
    assert "unknown distribution_type" in msg
    assert "gaussian" in msg  # hints at supported keys

@pytest.mark.parametrize("components", [
    # as dicts
    [{"mean_hour": 5.0, "std_hours": 1.0, "weight": 1.0}],
    # as TimeComponentConfig instances
    [TimeComponentConfig(mean_hour=5.0, std_hours=1.0, weight=1.0)],
])
def test_gaussian_init_accepts_dicts_and_configs(components):
    # Should produce non-error and consistent arrays
    seed = 42
    rng1 = default_rng(seed)
    rng2 = default_rng(seed)
    dist = GaussianMixtureDistribution(components)
    # Both component types must yield identical sample streams
    out1 = dist.sample(10, rng1)
    rng2 = default_rng(seed)
    out2 = dist.sample(10, rng2)
    assert out1.dtype == np.int64
    assert out1.shape == (10,)
    np.testing.assert_array_equal(out1, out2)

def test_sample_timestamps_default_vs_explicit_default_components():
    start, end = date(2025, 1, 1), date(2025, 1, 5)
    count, seed = 100, 1234
    # default (no override)
    ts1 = sample_timestamps(count, start, end, seed)
    # explicit default components must match
    ts2 = sample_timestamps(
        count, start, end, seed,
        distribution_type="gaussian",
        time_components=_DEFAULT_TIME_COMPONENTS,
    )
    np.testing.assert_array_equal(ts1, ts2)

def test_sample_timestamps_shape_and_range():
    start, end = date(2025, 2, 10), date(2025, 2, 12)
    count, seed = 50, 2025
    ts = sample_timestamps(count, start, end, seed)
    # shape and dtype
    assert ts.shape == (count,)
    assert ts.dtype == "datetime64[ns]"
    # all days within [start, end]
    days = ts.astype("datetime64[D]")
    assert days.min() >= np.datetime64(start, "D")
    assert days.max() <= np.datetime64(end, "D")

def test_sample_timestamps_unknown_distribution():
    with pytest.raises(ValueError):
        sample_timestamps(
            total_rows=1,
            start_date=date(2025,1,1),
            end_date=date(2025,1,1),
            seed=0,
            distribution_type="bogus_type",
        )
