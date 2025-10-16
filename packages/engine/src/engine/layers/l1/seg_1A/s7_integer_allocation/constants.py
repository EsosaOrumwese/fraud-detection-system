"""Frozen identifiers for S7 integer allocation."""

from __future__ import annotations

MODULE_INTEGERISATION = "1A.integerisation"
MODULE_DIRICHLET = "1A.dirichlet_allocator"

SUBSTREAM_LABEL_RESIDUAL = "residual_rank"
SUBSTREAM_LABEL_DIRICHLET = "dirichlet_gamma_vector"

STREAM_RESIDUAL_RANK = "residual_rank"
STREAM_DIRICHLET_GAMMA = "dirichlet_gamma_vector"

TRACE_FILENAME = "rng_trace_log.jsonl"

__all__ = [
    "MODULE_DIRICHLET",
    "MODULE_INTEGERISATION",
    "STREAM_DIRICHLET_GAMMA",
    "STREAM_RESIDUAL_RANK",
    "SUBSTREAM_LABEL_DIRICHLET",
    "SUBSTREAM_LABEL_RESIDUAL",
    "TRACE_FILENAME",
]
