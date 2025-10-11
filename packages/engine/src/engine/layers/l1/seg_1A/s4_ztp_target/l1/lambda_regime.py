"""Binary64 link computation and regime selection for S4."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from ...s0_foundations.exceptions import err
from ..contexts import S4HyperParameters

Regime = Literal["inversion", "ptrs"]
REGIME_THRESHOLD = 10.0


@dataclass(frozen=True)
class FrozenLambdaRegime:
    """Binary64 lambda plus regime name (constant per merchant)."""

    lambda_extra: float
    regime: Regime


def compute_lambda_regime(
    *,
    hyperparams: S4HyperParameters,
    n_outlets: int,
    feature_value: float,
) -> FrozenLambdaRegime:
    """Compute lambda_extra and regime according to the S4 spec."""

    if n_outlets < 2:
        raise err(
            "ERR_S4_BRANCH_PURITY",
            f"S4 requires N>=2 for multi-site merchants (n_outlets={n_outlets})",
        )
    if not math.isfinite(feature_value) or feature_value < 0.0 or feature_value > 1.0:
        raise err(
            "ERR_S4_FEATURE_DOMAIN",
            f"S4 feature must lie in [0,1]; got {feature_value!r}",
        )

    theta2 = hyperparams.theta2 or 0.0
    eta = (
        float(hyperparams.theta0)
        + float(hyperparams.theta1) * math.log(float(n_outlets))
        + float(theta2) * float(feature_value)
    )
    lambda_extra = math.exp(eta)
    if not (math.isfinite(lambda_extra) and lambda_extra > 0.0):
        raise err(
            "ERR_S4_NUMERIC_INVALID",
            f"non-positive or non-finite lambda_extra (eta={eta!r}, lambda={lambda_extra!r})",
        )
    regime: Regime = "inversion" if lambda_extra < REGIME_THRESHOLD else "ptrs"
    return FrozenLambdaRegime(lambda_extra=lambda_extra, regime=regime)


__all__ = ["FrozenLambdaRegime", "Regime", "REGIME_THRESHOLD", "compute_lambda_regime"]
