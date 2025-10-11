"""Logic-level helpers for the S4 ZTP sampler."""

from .lambda_regime import (
    REGIME_THRESHOLD,
    FrozenLambdaRegime,
    Regime,
    compute_lambda_regime,
)
from .rng import derive_poisson_substream
from .sampler import A_ZERO_REASON, ExhaustionPolicy, SamplerOutcome, run_sampler

__all__ = [
    "A_ZERO_REASON",
    "ExhaustionPolicy",
    "FrozenLambdaRegime",
    "Regime",
    "REGIME_THRESHOLD",
    "SamplerOutcome",
    "compute_lambda_regime",
    "derive_poisson_substream",
    "run_sampler",
]
