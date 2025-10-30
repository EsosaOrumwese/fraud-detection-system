"""Helpers to derive the optional merchant_currency cache (κₘ) for S5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple

from ..s0_foundations.exceptions import S0Error, err
from .contexts import MerchantCurrencyInput

__all__ = [
    "MerchantCurrencyRecord",
    "derive_merchant_currency",
]

_SOURCE_INGRESS = "ingress_share_vector"
_SOURCE_LEGAL_TENDER = "home_primary_legal_tender"
_EPSILON = 1e-12


@dataclass(frozen=True)
class MerchantCurrencyRecord:
    """Resolved κₘ row to be persisted in the merchant_currency cache."""

    merchant_id: int
    kappa: str
    source: str
    tie_break_used: bool


def derive_merchant_currency(
    merchants: Sequence[MerchantCurrencyInput],
    legal_tender_map: Mapping[str, str],
) -> Tuple[MerchantCurrencyRecord, ...]:
    """Derive κₘ per merchant, respecting precedence and tie-breaking rules.

    Parameters
    ----------
    merchants:
        Iterable of merchant inputs surfaced from sealed S0 context.
    legal_tender_map:
        Mapping from ISO2 -> primary legal tender currency for fallback.

    Returns
    -------
    tuple[MerchantCurrencyRecord, ...]
        Ordered by merchant_id ascending.

    Raises
    ------
    S0Error
        When cardinality is breached, the share vector is invalid, or κₘ cannot
        be resolved from available sources.
    """

    records: list[MerchantCurrencyRecord] = []
    seen: set[int] = set()

    for merchant in merchants:
        merchant_id = int(merchant.merchant_id)
        if merchant_id in seen:
            raise err(
                "E_MCURR_CARDINALITY",
                f"duplicate merchant_id {merchant_id} encountered while deriving κₘ",
            )
        seen.add(merchant_id)

        share_vector = merchant.share_vector or {}
        share_candidates = _normalise_share_vector(share_vector)

        if share_candidates:
            kappa, tie_break = _select_from_share_vector(share_candidates)
            source = _SOURCE_INGRESS
        else:
            kappa = _resolve_from_legal_tender(merchant.home_country_iso, legal_tender_map)
            tie_break = False
            source = _SOURCE_LEGAL_TENDER

        records.append(
            MerchantCurrencyRecord(
                merchant_id=merchant_id,
                kappa=kappa,
                source=source,
                tie_break_used=tie_break,
            )
        )

    return tuple(sorted(records, key=lambda row: row.merchant_id))


def _normalise_share_vector(
    vector: Mapping[str, float],
) -> Mapping[str, float]:
    """Normalise share vector codes and guard basic domain assumptions."""

    normalised: dict[str, float] = {}
    for currency, raw_value in vector.items():
        if currency is None:
            continue
        code = str(currency).upper().strip()
        if not code:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise err(
                "E_MCURR_RESOLUTION",
                f"share vector for currency '{currency}' is not numeric: {raw_value}",
            ) from exc
        normalised[code] = value
    return normalised


def _select_from_share_vector(
    vector: Mapping[str, float],
) -> Tuple[str, bool]:
    """Select κₘ from share vector using max share then lexicographic tie-break."""

    if not vector:
        raise err(
            "E_MCURR_RESOLUTION",
            "share vector provided but contains no resolvable currencies",
        )

    max_share = max(vector.values())
    winners = [
        code
        for code, value in vector.items()
        if abs(value - max_share) <= max(_EPSILON, abs(max_share) * _EPSILON)
    ]
    winners.sort()
    return winners[0], len(winners) > 1


def _resolve_from_legal_tender(
    home_country_iso: str,
    legal_tender_map: Mapping[str, str],
) -> str:
    """Fallback to the canonical legal tender mapping."""

    iso = home_country_iso.upper().strip()
    if not iso:
        raise err("E_MCURR_RESOLUTION", "merchant home_country_iso is empty")
    try:
        currency = legal_tender_map[iso]
    except KeyError as exc:
        raise err(
            "E_MCURR_RESOLUTION",
            f"no legal tender mapping available for country ISO '{iso}'",
        ) from exc
    return currency.upper().strip()
