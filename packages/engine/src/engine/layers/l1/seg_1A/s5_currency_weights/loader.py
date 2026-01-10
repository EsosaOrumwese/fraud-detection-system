"""Load sealed reference inputs required by S5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import pandas as pd

from ..shared.dictionary import get_repo_root, load_dictionary, resolve_dataset_path
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


def _default_paths() -> ShareDataPaths:
    dictionary = load_dictionary()
    repo_root = get_repo_root()
    return ShareDataPaths(
        settlement_shares=resolve_dataset_path(
            "settlement_shares_2024Q4",
            base_path=repo_root,
            template_args={},
            dictionary=dictionary,
        ),
        ccy_country_shares=resolve_dataset_path(
            "ccy_country_shares_2024Q4",
            base_path=repo_root,
            template_args={},
            dictionary=dictionary,
        ),
        iso_legal_tender=resolve_dataset_path(
            "iso_legal_tender_2024",
            base_path=repo_root,
            template_args={},
            dictionary=dictionary,
        ),
    )


DEFAULT_PATHS = _default_paths()


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
    try:
        df = pd.read_parquet(file_path, columns=["country_iso", "primary_ccy"])
        currency_column = "primary_ccy"
    except Exception:
        df = pd.read_parquet(file_path, columns=["country_iso", "currency"])
        currency_column = "currency"
    tenders: list[LegalTender] = [
        LegalTender(
            country_iso=str(row.country_iso),
            primary_ccy=str(getattr(row, currency_column)),
        )
        for row in df.itertuples(index=False, name="IsoTenderRow")
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
