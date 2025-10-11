"""Frozen identifiers for the S4 ZTP sampler logs.

Keeping the literals in one place prevents drift between emitters,
validators, and higher layers. The values mirror the authoritative
specification in `docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s4.expanded.md`.
"""

from __future__ import annotations

MODULE_NAME = "1A.ztp_sampler"
SUBSTREAM_LABEL = "poisson_component"
CONTEXT = "ztp"

# Dataset identifiers / directory names resolved via the dataset dictionary.
STREAM_POISSON_COMPONENT = "poisson_component"
STREAM_ZTP_REJECTION = "ztp_rejection"
STREAM_ZTP_RETRY_EXHAUSTED = "ztp_retry_exhausted"
STREAM_ZTP_FINAL = "ztp_final"
STREAM_TRACE = "rng_trace_log"

__all__ = [
    "MODULE_NAME",
    "SUBSTREAM_LABEL",
    "CONTEXT",
    "STREAM_POISSON_COMPONENT",
    "STREAM_ZTP_REJECTION",
    "STREAM_ZTP_RETRY_EXHAUSTED",
    "STREAM_ZTP_FINAL",
    "STREAM_TRACE",
]
