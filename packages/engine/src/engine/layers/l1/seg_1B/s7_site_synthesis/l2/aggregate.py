"""Aggregation utilities for Segment 1B state-7."""

from __future__ import annotations

from dataclasses import dataclass

from ..l0.datasets import OutletCataloguePartition, S5AssignmentPartition, S6JitterPartition, TileBoundsPartition
from ..l1.synthesis import S7Outcome, compute_site_synthesis
from .prepare import PreparedInputs


@dataclass(frozen=True)
class S7Context:
    """Execution context for the synthesis kernel."""

    assignments: S5AssignmentPartition
    jitter: S6JitterPartition
    tile_bounds: TileBoundsPartition
    outlet_catalogue: OutletCataloguePartition


def build_context(prepared: PreparedInputs) -> S7Context:
    """Construct the synthesis execution context."""

    return S7Context(
        assignments=prepared.assignments,
        jitter=prepared.jitter,
        tile_bounds=prepared.tile_bounds,
        outlet_catalogue=prepared.outlet_catalogue,
    )


def execute_synthesis(context: S7Context) -> S7Outcome:
    """Execute the S7 synthesis kernel."""

    return compute_site_synthesis(
        assignments=context.assignments,
        jitter=context.jitter,
        tile_bounds=context.tile_bounds,
        outlet_catalogue=context.outlet_catalogue,
    )


__all__ = ["S7Context", "build_context", "execute_synthesis"]
