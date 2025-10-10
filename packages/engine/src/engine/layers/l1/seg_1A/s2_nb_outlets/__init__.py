"""Public surface for Layer-1 Segment 1A state-2 NB outlet preparation."""

from .l1.links import NBLinks, compute_links_from_design, compute_nb_links
from .l2.deterministic import (
    S2DeterministicContext,
    S2DeterministicRow,
    build_deterministic_context,
)
from .l2.runner import NBFinalRecord, S2NegativeBinomialRunner, S2RunResult
from .l3.validator import validate_nb_run

__all__ = [
    "NBFinalRecord",
    "NBLinks",
    "S2DeterministicContext",
    "S2DeterministicRow",
    "S2NegativeBinomialRunner",
    "S2RunResult",
    "build_deterministic_context",
    "compute_links_from_design",
    "compute_nb_links",
    "validate_nb_run",
]
