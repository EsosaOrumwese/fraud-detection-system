"""
Temporal sampler for synthetic events, with diurnal patterns.
"""

from __future__ import annotations
from datetime import date
from typing import Optional, Dict, List

import numpy as np
import abc
from numpy.random import Generator, default_rng

# Registry for pluggable temporal distributions
__registry: dict[str, type["TemporalDistribution"]] = {}

def register_distribution(name: str):
    def _inner(cls: type["TemporalDistribution"]):
        __registry[name] = cls
        return cls
    return _inner

def get_distribution(name: str) -> type["TemporalDistribution"]:
    try:
        return __registry[name]
    except KeyError:
        raise ValueError(f"Unknown distribution_type {name!r}; supported: {list(__registry)}")

class TemporalDistribution(abc.ABC):
    """Interface for time-of-day sampling strategies."""

    @abc.abstractmethod
    def sample(self, count: int, rng: Generator, **params) -> np.ndarray:
        """Return `count` offsets in seconds since midnight."""
        ...

# Default mixture components for backward compatibility
_DEFAULT_TIME_COMPONENTS = [
    {"mean_hour": 9.0, "std_hours": 2.0, "weight": 0.4},
    {"mean_hour":13.0, "std_hours": 1.0, "weight": 0.3},
    {"mean_hour":20.0, "std_hours": 3.0, "weight": 0.3},
]


def sample_timestamps(
    total_rows: int,
    start_date: date,
    end_date: date,
    seed: Optional[int] = None,
    distribution_type: str = "gaussian",
    time_components: Optional[list[dict]] = None,
    weekday_weights: Optional[Dict[int, float]] = None,
    chunk_size: Optional[int] = None,
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
    distribution_type : str
        Type of distribution to use.
    time_components : List[dict]
        List of time components to use.
    weekday_weights : Dict[int, float]
        Weight of each time component.
    chunk_size : int
        Number of timestamps to generate at a time.

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

    # 1) Build all calendar dates
    num_days = (end_date - start_date).days + 1
    all_dates = np.datetime64(start_date, "D") + np.arange(
        num_days, dtype="timedelta64[D]"
    )

    # 2) Compute per-date probabilities if weights provided
    if weekday_weights is not None:
        w = np.array([
            weekday_weights.get(
                int(dt.astype("datetime64[D]").astype(object).weekday()),
                0.0
            )
            for dt in all_dates
        ], dtype=float)
        total_w = w.sum()
        if total_w <= 0:
            raise ValueError("Sum of weekday_weights must be > 0")
        per_date_p = w / total_w
    else:
        per_date_p = None

    # 3) Prepare time-of-day sampler & pre-generate all time offsets
    dist_cls = get_distribution(distribution_type)
    comps    = time_components if time_components is not None else _DEFAULT_TIME_COMPONENTS
    dist     = dist_cls(comps)
    secs_all  = dist.sample(total_rows, rng)
    times_all = secs_all.astype("timedelta64[s]").astype("timedelta64[ns]")

    # 4) Assemble final timestamps in chunk-bounded batches
    if chunk_size is not None and total_rows > chunk_size:
        parts, offset, remaining = [], 0, total_rows
        while remaining > 0:
            n = min(chunk_size, remaining)
            # date sampling
            if per_date_p is None:
                idx = rng.integers(0, num_days, size=n)
            else:
                idx = rng.choice(num_days, size=n, p=per_date_p)

            dates_chunk = all_dates[idx].astype("datetime64[ns]")
            times_chunk = times_all[offset : offset + n]
            parts.append(dates_chunk + times_chunk)

            offset    += n
            remaining -= n
        return np.concatenate(parts)

    # single-shot or no chunking
    if per_date_p is None:
        idx = rng.integers(0, num_days, size=total_rows)
    else:
        idx = rng.choice(num_days, size=total_rows, p=per_date_p)
    dates = all_dates[idx].astype("datetime64[ns]")
    return dates + times_all



@register_distribution("gaussian")
class GaussianMixtureDistribution(TemporalDistribution):
    def __init__(self, components: list[dict]):
        """Initialize Gaussian‐mixture using dicts or TimeComponentConfig instances."""
        means, stds, weights = [], [], []
        for c in components:
            if isinstance(c, dict):
                means.append(c["mean_hour"])
                stds.append(c["std_hours"])
                weights.append(c["weight"])
            else:
                # assume Pydantic TimeComponentConfig
                means.append(c.mean_hour)
                stds.append(c.std_hours)
                weights.append(c.weight)
        # convert to seconds
        self.means   = np.array(means,   dtype=float) * 3600
        self.stds    = np.array(stds,    dtype=float) * 3600
        self.weights = np.array(weights, dtype=float)

    def sample(self, count: int, rng: Generator, **params) -> np.ndarray:
        # pick a component index per draw
        idx = rng.choice(len(self.weights), size=count, p=self.weights)
        # draw from the corresponding Gaussians
        secs = rng.normal(loc=self.means[idx], scale=self.stds[idx], size=count)
        # clip to [0, 24h) and round
        return np.clip(secs, 0, 24 * 3600 - 1).round().astype(np.int64)
