"""Core smoothing/blending logic for S5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .loader import ShareSurface
from .policy import SmoothingPolicy


@dataclass(frozen=True)
class WeightRow:
    currency: str
    country_iso: str
    weight: float


def build_weights(
    settlement_shares: Iterable[ShareSurface],
    ccy_shares: Iterable[ShareSurface],
    policy: SmoothingPolicy,
) -> list[WeightRow]:
    """TODO: deterministic smoothing implementation."""
    raise NotImplementedError
