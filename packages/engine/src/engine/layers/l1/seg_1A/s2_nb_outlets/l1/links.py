"""NB2 link computation utilities for S2.

S2 consumes the column-frozen design vectors produced in S0 and the governed
coefficient bundles (`beta_mu`, `beta_phi`) to evaluate the Negative Binomial
links for merchants that cleared the hurdle.  The arithmetic mirrors the
numeric policy enforced in S0/S1: binary64, Neumaier-compensated dot products,
and exponentiation without fast-math shortcuts.  The resulting parameters feed
the stochastic Gamma/Poisson sampling steps implemented in later layers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.design import (
    DesignVectors,
    DispersionCoefficients,
    HurdleCoefficients,
)


@dataclass(frozen=True)
class NBLinks:
    """Deterministic NB2 parameters for a single merchant."""

    eta_mu: float
    eta_phi: float
    mu: float
    phi: float


def _neumaier_dot(left: Sequence[float], right: Sequence[float]) -> float:
    """Serial Neumaier dot product that preserves numeric policy."""

    if len(left) != len(right):
        raise err(
            "E_S2_SHAPE_MISMATCH",
            f"vector length mismatch (coefficients={len(left)}, design={len(right)})",
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


def compute_nb_links(
    *,
    beta_mu: Sequence[float],
    beta_phi: Sequence[float],
    design_mean: Sequence[float],
    design_dispersion: Sequence[float],
) -> NBLinks:
    """Compute NB2 mean/dispersion parameters in binary64."""

    eta_mu = _neumaier_dot(beta_mu, design_mean)
    eta_phi = _neumaier_dot(beta_phi, design_dispersion)
    mu = math.exp(eta_mu)
    phi = math.exp(eta_phi)
    if not (math.isfinite(mu) and math.isfinite(phi) and mu > 0.0 and phi > 0.0):
        raise err(
            "ERR_S2_NUMERIC_INVALID",
            f"invalid NB parameters (mu={mu!r}, phi={phi!r})",
        )
    return NBLinks(eta_mu=eta_mu, eta_phi=eta_phi, mu=mu, phi=phi)


def compute_links_from_design(
    design: DesignVectors,
    *,
    hurdle: HurdleCoefficients,
    dispersion: DispersionCoefficients,
) -> NBLinks:
    """Convenience wrapper that consumes S0 design dataclasses."""

    return compute_nb_links(
        beta_mu=hurdle.beta_mu,
        beta_phi=dispersion.beta_phi,
        design_mean=design.x_nb_mean,
        design_dispersion=design.x_nb_dispersion,
    )


__all__ = ["NBLinks", "compute_nb_links", "compute_links_from_design"]
