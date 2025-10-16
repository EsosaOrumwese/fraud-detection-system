"""Validation helpers for S5 datasets."""

from __future__ import annotations

from typing import Iterable

from .builder import WeightRow


def validate_weights(rows: Iterable[WeightRow]) -> None:
    """TODO: enforce schema-derived checks (Σ=1, union coverage, PK uniqueness)."""
    raise NotImplementedError
