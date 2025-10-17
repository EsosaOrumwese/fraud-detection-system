"""Core sequencing logic for S8 outlet catalogue generation."""

from __future__ import annotations

from typing import Sequence, Tuple

from .contexts import S8DeterministicContext, S8Metrics
from .types import OutletCatalogueRow, SequenceFinalizeEvent, SiteSequenceOverflowEvent


def build_outlet_catalogue(
    context: S8DeterministicContext,
) -> Tuple[
    Sequence[OutletCatalogueRow],
    Sequence[SequenceFinalizeEvent],
    Sequence[SiteSequenceOverflowEvent],
    S8Metrics,
]:
    """Transform the deterministic context into outlet rows and instrumentation events."""
    raise NotImplementedError("S8 kernel has not been implemented yet.")


__all__ = [
    "build_outlet_catalogue",
]
