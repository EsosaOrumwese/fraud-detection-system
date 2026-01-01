"""Load sealed reference inputs required by S5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import pandas as pd

__all__ = [
    "ShareSurface",
    "LegalTender",
    "ShareDataPaths",
    "DEFAULT_PATHS",
    "ShareLoader",
    "IsoLegalTenderLoader",
    "load_settlement_shares",
    "load_ccy_country_shares",
    "load_iso_legal_tender",
]


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


@dataclass(frozen=True)
class ShareDataPaths:
    settlement_shares: Path
    ccy_country_shares: Path
    iso_legal_tender: Path


DEFAULT_PATHS = ShareDataPaths(
    settlement_shares=Path("reference/network/settlement_shares/2024Q4/settlement_shares.parquet"),
    ccy_country_shares=Path("reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet"),
    iso_legal_tender=Path("reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet"),
)


class ShareLoader(Protocol):
    def load_settlement_shares(self) -> list[ShareSurface]: ...
    def load_ccy_country_shares(self) -> list[ShareSurface]: ...


class IsoLegalTenderLoader(Protocol):
    def load_iso_legal_tender(self) -> list[LegalTender]: ...


def load_settlement_shares(path: Path | None = None) -> list[ShareSurface]:
    """Return the sealed settlement share surface as dataclasses."""

    return list(_iter_share_file(path or DEFAULT_PATHS.settlement_shares))


def load_ccy_country_shares(path: Path | None = None) -> list[ShareSurface]:
    """Return the currency→country prior share surface."""

    return list(_iter_share_file(path or DEFAULT_PATHS.ccy_country_shares))


def load_iso_legal_tender(path: Path | None = None) -> list[LegalTender]:
    """Return the ISO2→legal tender lookup table."""

    file_path = path or DEFAULT_PATHS.iso_legal_tender
    df = pd.read_parquet(file_path, columns=["country_iso", "primary_ccy"])
    tenders: list[LegalTender] = [
        LegalTender(country_iso=str(row.country_iso), primary_ccy=str(row.primary_ccy))
        for row in df.itertuples(index=False)
    ]
    return tenders


def _iter_share_file(path: Path) -> Iterator[ShareSurface]:
    df = pd.read_parquet(path, columns=["currency", "country_iso", "share", "obs_count"])
    for row in df.itertuples(index=False):
        yield ShareSurface(
            currency=str(row.currency),
            country_iso=str(row.country_iso),
            share=float(row.share),
            obs_count=int(row.obs_count),
        )
