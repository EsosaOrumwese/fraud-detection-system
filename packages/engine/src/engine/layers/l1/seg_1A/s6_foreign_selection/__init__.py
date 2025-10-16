"""Layer 1 / Segment 1A State 6 foreign-set selection package."""

from .contexts import S6DeterministicContext
from .loader import load_deterministic_context
from .policy import SelectionPolicy, SelectionOverrides, load_policy
from .runner import S6RunOutputs, S6Runner
from .types import (
    CandidateInput,
    CandidateSelection,
    MerchantSelectionInput,
    MerchantSelectionResult,
)
from .validate import S6ValidationError, validate_outputs

__all__ = [
    "CandidateInput",
    "CandidateSelection",
    "MerchantSelectionInput",
    "MerchantSelectionResult",
    "S6DeterministicContext",
    "S6RunOutputs",
    "S6Runner",
    "S6ValidationError",
    "validate_outputs",
    "SelectionOverrides",
    "SelectionPolicy",
    "load_deterministic_context",
    "load_policy",
]
