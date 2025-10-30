"""RNG helpers for Segment 1B state-6 in-pixel jitter."""

from __future__ import annotations

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import (
    PhiloxEngine,
    PhiloxSubstream,
    comp_iso,
    comp_u64,
)

MODULE_NAME = "1B.S6.jitter"
SUBSTREAM_LABEL = "in_cell_jitter"


def derive_jitter_substream(
    engine: PhiloxEngine,
    *,
    merchant_id: int,
    legal_country_iso: str,
    site_order: int,
    parameter_hash: str,
) -> PhiloxSubstream:
    """Derive the Philox substream for a site's jitter attempts."""

    components = (
        ("string", "segment:1B"),
        ("string", "state:s6"),
        comp_u64(int(merchant_id)),
        comp_iso(legal_country_iso),
        comp_u64(int(site_order)),
        ("string", parameter_hash),
    )
    return engine.derive_substream(SUBSTREAM_LABEL, components)


__all__ = ["MODULE_NAME", "SUBSTREAM_LABEL", "derive_jitter_substream"]
