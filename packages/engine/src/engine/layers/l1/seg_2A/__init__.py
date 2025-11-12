"""Public exports for Layer-1 Segment 2A.

The segment is entering implementation; the modules exposed here provide the
surface that higher layers (CLI, tests, orchestration) can depend on without
knowing the internal folder layout.  Only lightweight types are exported for
now while the states are under active build.
"""

from .s0_gate import (
    GateInputs as S0GateInputs,
    GateOutputs as S0GateOutputs,
    S0GateRunner,
    SealedAsset as S0SealedAsset,
)
from .s1_provisional import (
    ProvisionalLookupInputs,
    ProvisionalLookupResult,
    ProvisionalLookupRunner,
)
from .s2_overrides import OverridesInputs, OverridesResult, OverridesRunner
from .s3_timetable import TimetableInputs, TimetableResult, TimetableRunner
from .s4_legality import LegalityInputs, LegalityResult, LegalityRunner
from .s5_validation import ValidationInputs, ValidationResult, ValidationRunner

__all__ = [
    "S0GateInputs",
    "S0GateOutputs",
    "S0GateRunner",
    "S0SealedAsset",
    "ProvisionalLookupInputs",
    "ProvisionalLookupResult",
    "ProvisionalLookupRunner",
    "OverridesInputs",
    "OverridesResult",
    "OverridesRunner",
    "TimetableInputs",
    "TimetableResult",
    "TimetableRunner",
    "LegalityInputs",
    "LegalityResult",
    "LegalityRunner",
    "ValidationInputs",
    "ValidationResult",
    "ValidationRunner",
]
