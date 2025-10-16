"""Runner scaffolding for S6 foreign-set selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .policy import SelectionPolicy


@dataclass(frozen=True)
class S6RunOutputs:
    """Placeholder return type capturing S6 artefact paths."""

    events_path: Path | None
    membership_path: Path | None
    receipt_path: Path | None


def run_s6(*, base_path: Path, policy: SelectionPolicy) -> S6RunOutputs:
    """Execute S6 selection (placeholder)."""

    raise NotImplementedError("S6 runner not yet implemented")
