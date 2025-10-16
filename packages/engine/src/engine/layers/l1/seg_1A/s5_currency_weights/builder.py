"""Core smoothing/blending logic for S5."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Tuple

from .loader import ShareSurface
from .policy import CurrencyOverrides, SmoothingPolicy

__all__ = [
    "QuantisationError",
    "ZeroMassError",
    "WeightRow",
    "CurrencyResult",
    "build_weights",
]


getcontext().prec = 50  # high precision for quantisation arithmetic


class ZeroMassError(RuntimeError):
    """Raised when a currency has zero effective mass (Σ weights cannot be normalised)."""


class QuantisationError(RuntimeError):
    """Raised when fixed-dp quantisation cannot produce an exact decimal group sum."""


@dataclass(frozen=True)
class WeightRow:
    currency: str
    country_iso: str
    weight: float


@dataclass(frozen=True)
class CurrencyResult:
    currency: str
    weights: List[WeightRow]
    n_eff: float
    degrade_mode: str
    degrade_reason: Optional[str]


def build_weights(
    settlement_shares: Iterable[ShareSurface],
    ccy_shares: Iterable[ShareSurface],
    policy: SmoothingPolicy,
) -> list[CurrencyResult]:
    """Return the per-currency S5 results according to §6 of the spec."""

    settlement_map = _group_by_currency(settlement_shares)
    ccy_map = _group_by_currency(ccy_shares)

    all_currencies = sorted(set(settlement_map.keys()) | set(ccy_map.keys()))
    results: list[CurrencyResult] = []

    for currency in all_currencies:
        settle_rows = settlement_map.get(currency, {})
        ccy_rows = ccy_map.get(currency, {})

        if not settle_rows and not ccy_rows:
            # No rows available from either surface; nothing to emit.
            continue

        union_isos = sorted(
            set(settle_rows.keys()) | set(ccy_rows.keys()) |
            set(policy.alpha_iso.get(currency, {}).keys()) |
            set(policy.min_share_iso.get(currency, {}).keys())
        )
        if not union_isos:
            continue

        params = _resolve_currency_params(policy, currency)
        degrade_mode, degrade_reason = _detect_degrade_mode(settle_rows, ccy_rows)

        weights, n_eff = _build_currency(
            currency=currency,
            union_isos=union_isos,
            settle_rows=settle_rows,
            ccy_rows=ccy_rows,
            params=params,
            dp=policy.dp,
        )

        results.append(
            CurrencyResult(
                currency=currency,
                weights=weights,
                n_eff=n_eff,
                degrade_mode=degrade_mode,
                degrade_reason=degrade_reason,
            )
        )

    return results


# --------------------------------------------------------------------------- #
# Internal helpers


@dataclass(frozen=True)
class _CurrencyParams:
    blend_weight: float
    base_alpha: float
    obs_floor: float
    min_share: float
    shrink_exponent: float
    alpha_iso: Mapping[str, float]
    min_share_iso: Mapping[str, float]


def _group_by_currency(shares: Iterable[ShareSurface]) -> Dict[str, Dict[str, ShareSurface]]:
    grouped: Dict[str, Dict[str, ShareSurface]] = defaultdict(dict)
    for row in shares:
        grouped[row.currency][row.country_iso] = row
    return grouped


def _detect_degrade_mode(
    settlement_rows: Mapping[str, ShareSurface],
    ccy_rows: Mapping[str, ShareSurface],
) -> Tuple[str, Optional[str]]:
    if settlement_rows and ccy_rows:
        return "none", None
    if ccy_rows and not settlement_rows:
        return "ccy_only", "SRC_MISSING_SETTLEMENT"
    if settlement_rows and not ccy_rows:
        return "settlement_only", "SRC_MISSING_CCY"
    return "none", None


def _resolve_currency_params(policy: SmoothingPolicy, currency: str) -> _CurrencyParams:
    overrides: Optional[CurrencyOverrides] = policy.per_currency.get(currency)

    def _resolve(key: str):
        if overrides is not None:
            value = getattr(overrides, key)
            if value is not None:
                return value
        return getattr(policy.defaults, key)

    blend_weight = float(_resolve("blend_weight"))
    base_alpha = float(_resolve("alpha"))
    obs_floor = float(_resolve("obs_floor"))
    min_share = float(_resolve("min_share"))
    shrink_exponent = float(_resolve("shrink_exponent"))

    alpha_iso = policy.alpha_iso.get(currency, {})
    min_share_iso = policy.min_share_iso.get(currency, {})

    return _CurrencyParams(
        blend_weight=blend_weight,
        base_alpha=base_alpha,
        obs_floor=obs_floor,
        min_share=min_share,
        shrink_exponent=shrink_exponent,
        alpha_iso=alpha_iso,
        min_share_iso=min_share_iso,
    )


def _build_currency(
    *,
    currency: str,
    union_isos: Iterable[str],
    settle_rows: Mapping[str, ShareSurface],
    ccy_rows: Mapping[str, ShareSurface],
    params: _CurrencyParams,
    dp: int,
) -> Tuple[List[WeightRow], float]:
    blend = params.blend_weight

    # Pre-compute sums of obs counts for N0.
    sum_obs_settle = float(sum(row.obs_count for row in settle_rows.values()))
    sum_obs_ccy = float(sum(row.obs_count for row in ccy_rows.values()))

    effective_shares: Dict[str, float] = {}
    settlement_shares: Dict[str, float] = {}
    ccy_shares: Dict[str, float] = {}

    for iso in union_isos:
        settle_share = settle_rows.get(iso)
        ccy_share = ccy_rows.get(iso)

        s_share = float(settle_share.share) if settle_share else 0.0
        c_share = float(ccy_share.share) if ccy_share else 0.0

        settlement_shares[iso] = s_share
        ccy_shares[iso] = c_share

        effective_shares[iso] = blend * c_share + (1.0 - blend) * s_share

    # Effective evidence mass (§6.3).
    shrink_exp = params.shrink_exponent if params.shrink_exponent >= 1.0 else 1.0
    n0 = blend * sum_obs_ccy + (1.0 - blend) * sum_obs_settle
    n_eff_candidate = n0 ** (1.0 / shrink_exp) if n0 > 0.0 else 0.0
    n_eff = max(params.obs_floor, n_eff_candidate)

    # Resolve alpha per ISO and compute posterior (§6.4).
    alpha_by_iso: Dict[str, float] = {}
    for iso in union_isos:
        alpha_override = params.alpha_iso.get(iso)
        alpha_by_iso[iso] = float(alpha_override) if alpha_override is not None else params.base_alpha

    alpha_sum = sum(alpha_by_iso.values())
    denom = n_eff + alpha_sum
    if denom <= 0.0:
        raise ZeroMassError(f"No effective mass for currency {currency}")

    posterior: Dict[str, float] = {}
    for iso in union_isos:
        posterior[iso] = (effective_shares[iso] * n_eff + alpha_by_iso[iso]) / denom

    # Apply minimum shares (§6.5).
    min_share_by_iso: Dict[str, float] = {}
    for iso in union_isos:
        min_override = params.min_share_iso.get(iso)
        min_share_by_iso[iso] = float(min_override) if min_override is not None else params.min_share

    floor_sum = sum(min_share_by_iso.values())
    excess = {iso: max(posterior[iso] - min_share_by_iso[iso], 0.0) for iso in union_isos}
    excess_sum = sum(excess.values())

    if floor_sum >= 1.0 - 1e-12:
        if floor_sum <= 0.0:
            raise ZeroMassError(f"Zero mass after floors for currency {currency}")
        probabilities = {iso: min_share_by_iso[iso] / floor_sum for iso in union_isos}
    else:
        residual = 1.0 - floor_sum
        if excess_sum > 0.0:
            probabilities = {
                iso: min_share_by_iso[iso] + residual * (excess[iso] / excess_sum)
                for iso in union_isos
            }
        elif floor_sum > 0.0:
            # No excess mass; distribute residual proportionally to floors.
            probabilities = {
                iso: min_share_by_iso[iso] + residual * (min_share_by_iso[iso] / floor_sum)
                for iso in union_isos
            }
        else:
            # No floors and no excess (posterior nearly zero) – fall back to posterior normalised.
            post_sum = sum(posterior.values())
            if post_sum <= 0.0:
                raise ZeroMassError(f"Zero mass after floors for currency {currency}")
            probabilities = {iso: posterior[iso] / post_sum for iso in union_isos}

    # Final normalisation guard against floating drift.
    total_prob = sum(probabilities.values())
    if total_prob <= 0.0:
        raise ZeroMassError(f"Zero mass after floors for currency {currency}")
    probabilities = {iso: probabilities[iso] / total_prob for iso in union_isos}

    # Quantise (§6.7).
    quantised = _quantise_probabilities(probabilities, dp)

    weight_rows = [
        WeightRow(currency=currency, country_iso=iso, weight=quantised[iso])
        for iso in sorted(quantised.keys())
    ]
    return weight_rows, n_eff


def _quantise_probabilities(probabilities: Mapping[str, float], dp: int) -> Dict[str, float]:
    factor = Decimal(10) ** dp
    iso_list = list(probabilities.keys())

    raw_values: list[Decimal] = []
    int_ulps: list[int] = []
    remainders: list[Decimal] = []

    for iso in iso_list:
        value = Decimal(str(probabilities[iso])) * factor
        rounded = int(value.to_integral_value(rounding=ROUND_HALF_EVEN))
        remainder = value - Decimal(rounded)
        raw_values.append(value)
        int_ulps.append(rounded)
        remainders.append(remainder)

    total = sum(int_ulps)
    target = int(factor)

    if total < target:
        diff = target - total
        order = sorted(
            range(len(iso_list)),
            key=lambda i: (-remainders[i], iso_list[i]),
        )
        for idx in order[:diff]:
            int_ulps[idx] += 1
    elif total > target:
        diff = total - target
        order = sorted(
            range(len(iso_list)),
            key=lambda i: (remainders[i], _iso_desc_key(iso_list[i])),
        )
        for idx in order[:diff]:
            int_ulps[idx] -= 1

    if sum(int_ulps) != target:
        raise QuantisationError("Unable to achieve fixed-dp sum after adjustments")

    quantised: Dict[str, float] = {}
    for iso, ulp in zip(iso_list, int_ulps):
        quantised[iso] = float(Decimal(ulp) / factor)

    return quantised


def _iso_desc_key(iso: str) -> Tuple[int, ...]:
    """Return a tuple that sorts ISO codes in descending lexical order."""

    return tuple(-ord(ch) for ch in iso)
