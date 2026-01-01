"""Deterministic helpers for Layer-3 generation."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable, Sequence


def stable_int_hash(*parts: object) -> int:
    """Return a stable non-negative integer hash for the given parts."""

    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:16], 16)


def stable_uniform(*parts: object) -> float:
    """Return a deterministic U(0,1) float using sha256."""

    value = stable_int_hash(*parts)
    return (value + 1) / (16**16 + 1)


def largest_remainder(weights: Sequence[float], total: int, *, min_floor: int = 0) -> list[int]:
    """Allocate integer counts using largest remainder with a floor."""

    if total < 0:
        raise ValueError("total must be non-negative")
    if not weights:
        return []
    if any(weight < 0 for weight in weights):
        raise ValueError("weights must be non-negative")
    weight_sum = sum(weights)
    if weight_sum <= 0:
        return [min_floor] * len(weights)

    scaled = [weight / weight_sum * total for weight in weights]
    floors = [max(min_floor, math.floor(value)) for value in scaled]
    allocated = sum(floors)
    remainder = total - allocated

    remainders = [(idx, scaled[idx] - math.floor(scaled[idx])) for idx in range(len(weights))]
    if remainder > 0:
        for idx, _ in sorted(remainders, key=lambda item: (-item[1], item[0]))[:remainder]:
            floors[idx] += 1
    elif remainder < 0:
        shortfall = -remainder
        candidates = [
            (idx, scaled[idx] - math.floor(scaled[idx]))
            for idx in range(len(weights))
            if floors[idx] > min_floor
        ]
        for idx, _ in sorted(candidates, key=lambda item: (item[1], item[0]))[:shortfall]:
            floors[idx] -= 1
    return floors


def normalise(weights: Iterable[float]) -> list[float]:
    """Return weights normalised to sum to 1.0 (fallback to uniform)."""

    weights = list(weights)
    total = sum(weights)
    if total <= 0:
        if not weights:
            return []
        return [1.0 / len(weights)] * len(weights)
    return [value / total for value in weights]

def normal_icdf(u: float) -> float:
    """Approximate the inverse CDF of the standard normal distribution."""

    if not 0.0 < u < 1.0:
        raise ValueError("normal_icdf expects 0 < u < 1")

    # Coefficients from Peter J. Acklam's approximation.
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    plow = 0.02425
    phigh = 1.0 - plow

    if u < plow:
        q = math.sqrt(-2.0 * math.log(u))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if u > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - u))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )

    q = u - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


__all__ = ["largest_remainder", "normal_icdf", "normalise", "stable_int_hash", "stable_uniform"]
