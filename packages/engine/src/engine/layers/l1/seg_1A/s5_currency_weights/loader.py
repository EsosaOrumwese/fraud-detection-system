"""Load reference surfaces required by S5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ShareSurface:
    currency: str
    country_iso: str
    share: float
    obs_count: int


@dataclass(frozen=True)
class LegalTender:
    country_iso: str
    primary_ccy: str


class ShareLoader(Protocol):
    def load_settlement_shares(self) -> list[ShareSurface]: ...
    def load_ccy_country_shares(self) -> list[ShareSurface]: ...


class IsoLegalTenderLoader(Protocol):
    def load_iso_legal_tender(self) -> list[LegalTender]: ...
