"""Policy parsing and validation scaffolding for S6 foreign-set selection.

The real implementation will mirror the binding requirements captured in
docs/model_spec/data-engine/specs/state-flow/1A/state.1A.s6.expanded.md §4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class SelectionOverrides:
    """Effective overrides resolved for a specific currency."""

    emit_membership_dataset: bool
    max_candidates_cap: int
    zero_weight_rule: str


@dataclass(frozen=True)
class SelectionPolicy:
    """Container for the resolved S6 policy (global + overrides)."""

    emit_membership_dataset: bool
    log_all_candidates: bool
    max_candidates_cap: int
    zero_weight_rule: str
    per_currency: Mapping[str, SelectionOverrides]


def load_policy(path: str | Path) -> SelectionPolicy:
    """Load and validate the S6 selection policy (placeholder)."""

    raise NotImplementedError("S6 policy loader not yet implemented")
