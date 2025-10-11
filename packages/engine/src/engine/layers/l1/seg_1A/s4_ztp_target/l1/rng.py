"""Philox substream helpers for the S4 ZTP sampler."""

from __future__ import annotations

from ...s0_foundations.l1.rng import PhiloxEngine, PhiloxSubstream, comp_u64
from ..l0 import constants as c


def derive_poisson_substream(
    engine: PhiloxEngine,
    *,
    merchant_id: int,
) -> PhiloxSubstream:
    """Return the deterministic ZTP Poisson substream for a merchant."""

    components = (comp_u64(int(merchant_id)),)
    return engine.derive_substream(c.SUBSTREAM_LABEL, components)


__all__ = ["derive_poisson_substream"]
