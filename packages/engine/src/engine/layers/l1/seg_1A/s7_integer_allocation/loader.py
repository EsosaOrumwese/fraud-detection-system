"""Deterministic context builder for S7 integer allocation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence

from ..s0_foundations.exceptions import err
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from ..s6_foreign_selection.loader import verify_s5_pass
from ..s6_foreign_selection.types import MerchantSelectionResult
from ..s6_foreign_selection.contexts import S6DeterministicContext
from ..s2_nb_outlets.l2.runner import NBFinalRecord
from .contexts import S7DeterministicContext
from .policy import IntegerisationPolicy, ThresholdsPolicy
from .types import DomainMember, MerchantAllocationInput

__all__ = [
    "build_deterministic_context",
]


@dataclass(frozen=True)
class _SelectionIndex:
    results: Mapping[int, MerchantSelectionResult]
    totals: Mapping[int, int]


def build_deterministic_context(
    *,
    base_path: Path,
    parameter_hash: str,
    manifest_fingerprint: str,
    seed: int,
    run_id: str,
    policy_path: Path,
    nb_finals: Sequence[NBFinalRecord],
    s6_context: S6DeterministicContext,
    s6_results: Sequence[MerchantSelectionResult],
    policy: IntegerisationPolicy,
    dictionary: Mapping[str, object] | None = None,
    artefact_digests: Mapping[str, str] | None = None,
) -> S7DeterministicContext:
    """Assemble the deterministic inputs required by S7."""

    base_path = Path(base_path).expanduser().resolve()
    dictionary = dictionary or load_dictionary()
    _enforce_s5_pass(base_path=base_path, parameter_hash=parameter_hash, dictionary=dictionary)

    selection_index = _SelectionIndex(
        results={result.merchant_id: result for result in s6_results},
        totals={record.merchant_id: record.n_outlets for record in nb_finals},
    )

    merchants: list[MerchantAllocationInput] = []
    for merchant in s6_context.merchants:
        merchant_id = merchant.merchant_id
        if merchant_id not in selection_index.totals:
            raise err(
                "E_S7_N_MISSING",
                f"nb_final total missing for merchant {merchant_id}",
            )
        total_outlets = selection_index.totals[merchant_id]
        selection = selection_index.results.get(merchant_id)
        if selection is None:
            raise err(
                "E_S7_SELECTION_MISSING",
                f"S6 selection outputs missing for merchant {merchant_id}",
            )
        selected = {
            candidate.country_iso.upper()
            for candidate in selection.candidates
            if candidate.selected
        }
        domain_members = _build_domain_members(
            merchant_id=merchant_id,
            candidates=merchant.candidates,
            selected=selected,
            total_outlets=total_outlets,
            thresholds=policy.thresholds if policy.bounds_enabled else None,
        )
        merchants.append(
            MerchantAllocationInput(
                merchant_id=merchant_id,
                settlement_currency=selection.settlement_currency,
                total_outlets=total_outlets,
                k_target=selection.k_target,
                k_realised=selection.k_realised,
                shortfall=selection.shortfall,
                domain=tuple(domain_members),
            )
        )

    return S7DeterministicContext(
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        run_id=run_id,
        policy_path=Path(policy_path).expanduser().resolve(),
        merchants=tuple(merchants),
        artefact_digests=dict(artefact_digests or {}),
    )


def _build_domain_members(
    *,
    merchant_id: int,
    candidates: Sequence,
    selected: set[str],
    total_outlets: int,
    thresholds: ThresholdsPolicy | None,
) -> Sequence[DomainMember]:
    domain: list[DomainMember] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_rank):
        iso = candidate.country_iso.upper()
        if not candidate.is_home and iso not in selected:
            continue
        domain.append(
            DomainMember(
                country_iso=iso,
                candidate_rank=int(candidate.candidate_rank),
                is_home=bool(candidate.is_home),
                weight=float(candidate.weight),
                lower_bound=0,
                upper_bound=None,
            )
        )

    if not domain:
        raise err(
            "E_S7_DOMAIN_EMPTY",
            f"domain empty for merchant {merchant_id}; expected at least home country",
        )

    # Ensure home is present exactly once.
    home_count = sum(1 for item in domain if item.is_home)
    if home_count != 1:
        raise err(
            "E_S7_HOME_DOMAIN",
            f"expected exactly one home entry for merchant {merchant_id}, found {home_count}",
        )

    if thresholds is not None:
        return _apply_threshold_bounds(domain, thresholds, total_outlets, merchant_id)

    return domain


def _resolve_bounds(
    *,
    thresholds: ThresholdsPolicy | None,
    iso: str,
    is_home: bool,
    total_outlets: int,
    domain_size: int,
) -> tuple[int, int | None]:
    if thresholds is None or not thresholds.enabled:
        return 0, None

    if is_home:
        lower = min(thresholds.home_min, total_outlets)
        if (
            thresholds.force_at_least_one_foreign_if_foreign_present
            and domain_size > 1
            and total_outlets >= 2
        ):
            upper = total_outlets - 1
        else:
            upper = total_outlets
    else:
        if thresholds.min_one_per_country_when_feasible and total_outlets >= domain_size and total_outlets >= 2:
            lower = 1
        else:
            lower = 0
        if thresholds.foreign_cap_mode == "n_minus_home_min":
            upper = max(lower, total_outlets - min(thresholds.home_min, total_outlets))
        else:
            upper = total_outlets
    return int(lower), int(upper)


def _apply_threshold_bounds(
    domain: Sequence[DomainMember],
    thresholds: ThresholdsPolicy,
    total_outlets: int,
    merchant_id: int,
) -> Sequence[DomainMember]:
    domain_size = len(domain)
    bounds = []
    for member in domain:
        lower, upper = _resolve_bounds(
            thresholds=thresholds,
            iso=member.country_iso,
            is_home=member.is_home,
            total_outlets=total_outlets,
            domain_size=domain_size,
        )
        if upper is not None and upper < lower:
            raise err(
                "E_BOUNDS_INFEASIBLE",
                f"bounds infeasible for merchant {merchant_id}: upper {upper} < lower {lower} for ISO {member.country_iso}",
            )
        bounds.append((lower, upper))

    floor_sum = sum(lower for lower, _ in bounds)
    ceiling_sum = sum(
        (upper if upper is not None else total_outlets) for _, upper in bounds
    )
    if floor_sum > total_outlets or ceiling_sum < total_outlets:
        if thresholds.on_infeasible == "fail":
            raise err(
                "E_BOUNDS_INFEASIBLE",
                f"threshold infeasible for merchant {merchant_id} (L_sum={floor_sum}, U_sum={ceiling_sum}, N={total_outlets})",
            )

    updated: list[DomainMember] = []
    for member, (lower, upper) in zip(domain, bounds, strict=False):
        updated.append(
            DomainMember(
                country_iso=member.country_iso,
                candidate_rank=member.candidate_rank,
                is_home=member.is_home,
                weight=member.weight,
                lower_bound=int(lower),
                upper_bound=None if upper is None else int(upper),
            )
        )
    return updated


def _enforce_s5_pass(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object],
) -> None:
    weights_path = resolve_dataset_path(
        "ccy_country_weights_cache",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    verify_s5_pass(weights_path.parent)
