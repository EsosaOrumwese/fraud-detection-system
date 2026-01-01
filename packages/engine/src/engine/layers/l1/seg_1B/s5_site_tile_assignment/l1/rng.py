"""RNG helpers for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import (
    PhiloxEngine,
    PhiloxSubstream,
    comp_iso,
    comp_u64,
)


MODULE_NAME = "1B.S5.assigner"
SUBSTREAM_LABEL = "site_tile_assign"


def derive_site_tile_substream(
    engine: PhiloxEngine,
    *,
    merchant_id: int,
    legal_country_iso: str,
    parameter_hash: str,
) -> PhiloxSubstream:
    """Derive the Philox substream for a pair's assignment draws."""

    components = (
        ("string", "segment:1B"),
        ("string", "state:s5"),
        comp_u64(int(merchant_id)),
        comp_iso(legal_country_iso),
        ("string", parameter_hash),
    )
    return engine.derive_substream(SUBSTREAM_LABEL, components)


__all__ = ["MODULE_NAME", "SUBSTREAM_LABEL", "derive_site_tile_substream"]
