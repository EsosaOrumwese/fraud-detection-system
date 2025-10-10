"""Philox substream helpers for S2 NB outlet sampling."""

from __future__ import annotations

from ...s0_foundations.l1.rng import PhiloxEngine, PhiloxState, PhiloxSubstream, comp_u64

GAMMA_MODULE_NAME = "1A.nb_and_dirichlet_sampler"
POISSON_MODULE_NAME = "1A.nb_poisson_component"
FINAL_MODULE_NAME = "1A.nb_sampler"

GAMMA_SUBSTREAM_LABEL = "gamma_nb"
POISSON_SUBSTREAM_LABEL = "poisson_nb"
FINAL_SUBSTREAM_LABEL = "nb_final"


def derive_gamma_substream(engine: PhiloxEngine, *, merchant_id: int) -> PhiloxSubstream:
    """Return the deterministic Gamma substream for a merchant."""

    components = (comp_u64(int(merchant_id)),)
    return engine.derive_substream(GAMMA_SUBSTREAM_LABEL, components)


def derive_poisson_substream(engine: PhiloxEngine, *, merchant_id: int) -> PhiloxSubstream:
    """Return the deterministic Poisson substream for a merchant."""

    components = (comp_u64(int(merchant_id)),)
    return engine.derive_substream(POISSON_SUBSTREAM_LABEL, components)


def derive_final_substream(engine: PhiloxEngine, *, merchant_id: int) -> PhiloxSubstream:
    """Return the non-consuming finalisation substream for a merchant."""

    components = (comp_u64(int(merchant_id)),)
    return engine.derive_substream(FINAL_SUBSTREAM_LABEL, components)


def counters(state: PhiloxState) -> tuple[int, int]:
    """Return the (hi, lo) counter words for logging/envelope construction."""

    return state.counter_hi, state.counter_lo


__all__ = [
    "FINAL_MODULE_NAME",
    "FINAL_SUBSTREAM_LABEL",
    "GAMMA_MODULE_NAME",
    "GAMMA_SUBSTREAM_LABEL",
    "POISSON_MODULE_NAME",
    "POISSON_SUBSTREAM_LABEL",
    "counters",
    "derive_final_substream",
    "derive_gamma_substream",
    "derive_poisson_substream",
]
