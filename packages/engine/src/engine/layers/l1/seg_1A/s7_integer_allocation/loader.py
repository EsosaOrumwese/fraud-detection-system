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
from .policy import BoundsPolicy, IntegerisationPolicy
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
            bounds=policy.bounds,
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
    bounds: BoundsPolicy | None,
) -> Sequence[DomainMember]:
    domain: list[DomainMember] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_rank):
        iso = candidate.country_iso.upper()
        if not candidate.is_home and iso not in selected:
            continue
        lower = bounds.lower_bound(iso) if bounds is not None else 0
        upper = bounds.upper_bound(iso) if bounds is not None else None
        if upper is not None and upper < lower:
            raise err(
                "E_BOUNDS_INFEASIBLE",
                f"bounds infeasible for merchant {merchant_id}: "
                f"upper {upper} < lower {lower} for ISO {iso}",
            )
        domain.append(
            DomainMember(
                country_iso=iso,
                candidate_rank=int(candidate.candidate_rank),
                is_home=bool(candidate.is_home),
                weight=float(candidate.weight),
                lower_bound=int(lower),
                upper_bound=None if upper is None else int(upper),
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

    return domain


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
