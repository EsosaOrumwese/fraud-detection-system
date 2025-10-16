"""Selection kernel scaffolding for S6 foreign-set selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .policy import SelectionPolicy


@dataclass(frozen=True)
class SelectedCountry:
    merchant_id: int
    country_iso: str
    key: float | None
    selected: bool
    selection_order: int | None


def select_foreign_set(
    *,
    policy: SelectionPolicy,
    candidates: Iterable[object],
) -> Sequence[SelectedCountry]:
    """Run the S6 selection algorithm (placeholder)."""

    raise NotImplementedError("S6 selection kernel not yet implemented")
