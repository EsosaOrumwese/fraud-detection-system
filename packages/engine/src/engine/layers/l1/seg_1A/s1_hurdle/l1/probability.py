"""Logistic hurdle probability helpers (S1.2).

This module implements the fixed-order Neumaier dot product and the
two-branch logistic required by the S1 specification.  It operates on the
column-frozen hurdle design vectors produced by S0, guaranteeing that the
probabilities we emit can be replayed exactly by the validation harness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ...s0_foundations.exceptions import err


@dataclass(frozen=True)
class HurdleProbability:
    """Container for the logistic score of a single merchant."""

    eta: float
    pi: float
    deterministic: bool


def _neumaier_dot(left: Sequence[float], right: Sequence[float]) -> float:
    """Two-term compensated dot product with deterministic ordering."""

    if len(left) != len(right):
        raise err(
            "E_DSGN_SHAPE_MISMATCH",
            f"hurdle design length {len(right)} does not match coefficients {len(left)}",
        )

    total = 0.0
    compensation = 0.0
    for beta_i, x_i in zip(left, right):
        product = float(beta_i) * float(x_i)
        temp = total + product
        if abs(total) >= abs(product):
            compensation += (total - temp) + product
        else:
            compensation += (product - temp) + total
        total = temp
    return total + compensation


def _logistic_two_branch(eta: float) -> float:
    """Overflow-safe logistic that never clamps by hand."""

    if eta >= 0.0:
        z = math.exp(-eta)
        return 1.0 / (1.0 + z)
    z = math.exp(eta)
    return z / (1.0 + z)


def hurdle_probability(
    *,
    coefficients: Sequence[float],
    design_vector: Sequence[float],
) -> HurdleProbability:
    """Compute (eta, pi) for the hurdle Bernoulli using S1.2 rules."""

    eta = _neumaier_dot(coefficients, design_vector)
    pi = _logistic_two_branch(eta)
    if not math.isfinite(pi):
        raise err("E_PI_NAN_OR_INF", f"hurdle probability non-finite (eta={eta!r})")
    deterministic = pi == 0.0 or pi == 1.0
    return HurdleProbability(eta=eta, pi=pi, deterministic=deterministic)


__all__ = ["HurdleProbability", "hurdle_probability"]
