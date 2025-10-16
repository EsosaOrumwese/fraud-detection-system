"""Data loading scaffolding for S6 foreign-set selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..s5_currency_weights import CurrencyResult


@dataclass(frozen=True)
class CandidateRecord:
    """Placeholder structure representing an S3 candidate row."""

    merchant_id: int
    country_iso: str
    candidate_rank: int
    is_home: bool


def load_inputs(*, parameter_hash: str) -> tuple[Iterable[CandidateRecord], Iterable[CurrencyResult]]:
    """Load S3/S4/S5 inputs required by S6.

    The concrete implementation will resolve the governed artefacts, enforce
    schema constraints, and surface Philox counter state for selection.
    """

    raise NotImplementedError("S6 loader not yet implemented")
