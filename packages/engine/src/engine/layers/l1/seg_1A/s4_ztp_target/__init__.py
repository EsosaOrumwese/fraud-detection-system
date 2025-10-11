"""Public surface for Layer-1 Segment 1A state-4 ZTP target sampling."""

from .contexts import S4DeterministicContext, S4HyperParameters, S4MerchantTarget
from .l0 import (
    CONTEXT,
    MODULE_NAME,
    STREAM_POISSON_COMPONENT,
    STREAM_TRACE,
    STREAM_ZTP_FINAL,
    STREAM_ZTP_REJECTION,
    STREAM_ZTP_RETRY_EXHAUSTED,
    SUBSTREAM_LABEL,
    ZTPEventWriter,
)
from .l1 import (
    A_ZERO_REASON,
    ExhaustionPolicy,
    FrozenLambdaRegime,
    REGIME_THRESHOLD,
    Regime,
    SamplerOutcome,
    compute_lambda_regime,
    derive_poisson_substream,
    run_sampler,
)
from .l2 import (
    S4DeterministicArtefacts,
    S4RunResult,
    S4ZTPTargetRunner,
    ZTPFinalRecord,
    build_deterministic_context,
)
from .l3 import FAILURE_CODES, StreamContract, stream_contracts
from .l3.validator import validate_s4_run

__all__ = [
    # Context primitives
    "S4DeterministicContext",
    "S4HyperParameters",
    "S4MerchantTarget",
    # L0
    "CONTEXT",
    "MODULE_NAME",
    "SUBSTREAM_LABEL",
    "STREAM_POISSON_COMPONENT",
    "STREAM_ZTP_REJECTION",
    "STREAM_ZTP_RETRY_EXHAUSTED",
    "STREAM_ZTP_FINAL",
    "STREAM_TRACE",
    "ZTPEventWriter",
    # L1 kernels
    "A_ZERO_REASON",
    "ExhaustionPolicy",
    "FrozenLambdaRegime",
    "Regime",
    "REGIME_THRESHOLD",
    "SamplerOutcome",
    "compute_lambda_regime",
    "derive_poisson_substream",
    "run_sampler",
    # L2 orchestration
    "S4DeterministicArtefacts",
    "S4RunResult",
    "S4ZTPTargetRunner",
    "ZTPFinalRecord",
    "build_deterministic_context",
    # L3 contracts/validation
    "FAILURE_CODES",
    "StreamContract",
    "stream_contracts",
    "validate_s4_run",
]
