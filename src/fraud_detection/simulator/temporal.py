"""
Temporal sampler for synthetic events, with diurnal patterns.
"""

from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import numpy as np
from numpy.random import Generator, default_rng


# Pre‐computed Gaussian‐mixture parameters (seconds since midnight)
_TEMPORAL_MEANS = np.array([9, 13, 20], dtype=float) * 3600
_TEMPORAL_STDS  = np.array([2, 1, 3], dtype=float) * 3600
_TEMPORAL_PROBS = np.array([0.4, 0.3, 0.3], dtype=float)

def sample_timestamps(
    total_rows: int,
    start_date: date,
    end_date: date,
    seed: Optional[int] = None,
) -> np.ndarray:  # type: ignore
    """
    Generate timestamps between start_date and end_date with a diurnal mixture.

    - Samples dates uniformly across range.
    - Samples time-of-day from a 3-component Gaussian mixture:
        * Morning (centred 09:00, σ=2h)
        * Afternoon (13:00, σ=1h)
        * Evening (20:00, σ=3h)
    - Clips within [00:00, 23:59:59].

    Parameters
    ----------
    total_rows : int
        Number of timestamps to generate (must be ≥0).
    start_date : date
        Inclusive start date.
    end_date : date
        Inclusive end date.
    seed : Optional[int]
        RNG seed for reproducibility.

    Returns
    -------
    np.ndarray
        1D array of length `total_rows` with dtype datetime64[ns].

    Raises
    ------
    ValueError
        If total_rows < 0 or end_date < start_date.
    """
    if total_rows < 0:
        raise ValueError(f"total_rows must be ≥0; got {total_rows}")
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    rng: Generator = default_rng(seed)

    # Build list of candidate dates
    days = (end_date - start_date).days + 1
    # Sample day offsets [0, days)
    day_offsets = rng.integers(0, days, size=total_rows)

    # Mixture proportions for time-of-day
    comp = rng.choice(3, size=total_rows, p=_TEMPORAL_PROBS)

    # Vectorized normal draws per component (seconds since midnight)
    secs = rng.normal(loc=_TEMPORAL_MEANS[comp], scale=_TEMPORAL_STDS[comp], size=total_rows)
    secs = np.clip(secs, 0, 24 * 3600 - 1).round().astype(np.int64)

    # Build numpy.datetime64 arrays
    base_dates = np.datetime64(start_date, "D") + day_offsets.astype("timedelta64[D]")
    time_offsets = secs.astype("timedelta64[s]")
    # Sum gives dtype datetime64[ns]
    timestamps = (base_dates.astype("datetime64[ns]") + time_offsets.astype("timedelta64[ns]"))

    return timestamps