"""Hurdle RNG helpers (S1.3).

S1 consumes at most one open-interval uniform from the shared Philox engine.
This module exposes the fixed label used for the hurdle Bernoulli stream and
wraps the S0 substream derivation helpers so orchestrators can remain agnostic
to the hashing details.
"""

from __future__ import annotations

from typing import Sequence

from ...s0_foundations.l1.rng import (
    PhiloxEngine,
    PhiloxState,
    PhiloxSubstream,
    comp_u64,
)

HURDLE_MODULE_NAME = "1A.hurdle_sampler"
HURDLE_SUBSTREAM_LABEL = "hurdle_bernoulli"


def derive_hurdle_substream(
    engine: PhiloxEngine,
    *,
    merchant_id: int,
) -> PhiloxSubstream:
    """Derive the deterministic Philox substream for a single merchant."""

    components: Sequence[tuple[str, object]] = (comp_u64(int(merchant_id)),)
    return engine.derive_substream(HURDLE_SUBSTREAM_LABEL, components)


def counters(state: PhiloxState) -> tuple[int, int]:
    """Return the (hi, lo) counter words for logging/envelope construction."""

    return state.counter_hi, state.counter_lo


__all__ = [
    "HURDLE_MODULE_NAME",
    "HURDLE_SUBSTREAM_LABEL",
    "derive_hurdle_substream",
    "counters",
]
