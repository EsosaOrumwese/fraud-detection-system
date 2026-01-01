"""Common data structures for S8 outlet catalogue materialisation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutletCatalogueRow:
    """Single `outlet_catalogue` row ready for persistence."""

    manifest_fingerprint: str
    merchant_id: int
    site_id: str
    home_country_iso: str
    legal_country_iso: str
    single_vs_multi_flag: bool
    raw_nb_outlet_draw: int
    final_country_outlet_count: int
    site_order: int
    global_seed: int


@dataclass(frozen=True)
class SequenceFinalizeEvent:
    """Payload written to the `sequence_finalize` RNG event stream."""

    merchant_id: int
    country_iso: str
    start_sequence: str
    end_sequence: str
    site_count: int


@dataclass(frozen=True)
class SiteSequenceOverflowEvent:
    """Guardrail event for site-id space exhaustion."""

    merchant_id: int
    country_iso: str
    attempted_count: int
    max_seq: int
    overflow_by: int
    severity: str


__all__ = [
    "OutletCatalogueRow",
    "SequenceFinalizeEvent",
    "SiteSequenceOverflowEvent",
]
