"""Persistence scaffolding for S6 foreign-set selection outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .builder import SelectedCountry


def write_membership(
    *,
    destination: Path,
    rows: Iterable[SelectedCountry],
) -> Path:
    """Persist the optional membership surface (placeholder)."""

    raise NotImplementedError("S6 membership writer not yet implemented")


def write_receipt(*, destination: Path, payload: dict) -> Path:
    """Write S6_VALIDATION.json + _passed.flag (placeholder)."""

    raise NotImplementedError("S6 receipt writer not yet implemented")
