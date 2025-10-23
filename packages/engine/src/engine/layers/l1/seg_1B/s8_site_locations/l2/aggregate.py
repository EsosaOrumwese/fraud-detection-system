"""Aggregation utilities for Segment 1B state-8."""

from __future__ import annotations

from dataclasses import dataclass

from ..l0.datasets import S7SiteSynthesisPartition
from ..l1.egress import S8Outcome, compute_site_locations
from .prepare import PreparedInputs


@dataclass(frozen=True)
class S8Context:
    """Execution context for the egress kernel."""

    synthesis: S7SiteSynthesisPartition


def build_context(prepared: PreparedInputs) -> S8Context:
    """Construct the execution context for S8."""

    return S8Context(synthesis=prepared.synthesis)


def execute_egress(context: S8Context) -> S8Outcome:
    """Execute the S8 egress kernel."""

    return compute_site_locations(synthesis=context.synthesis)


__all__ = ["S8Context", "build_context", "execute_egress"]
