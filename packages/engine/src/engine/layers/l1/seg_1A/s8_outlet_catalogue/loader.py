"""Load deterministic inputs required by the S8 pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from ..s0_foundations.exceptions import err
from ..s0_foundations.l1.context import MerchantUniverse
from ..s1_hurdle.l2.runner import HurdleDecision
from ..s2_nb_outlets.l2.runner import NBFinalRecord
from ..s7_integer_allocation.types import MerchantAllocationResult
from .contexts import (
    CountrySequencingInput,
    MerchantSequencingInput,
    S8DeterministicContext,
)

__all__ = ["load_deterministic_context"]


def load_deterministic_context(
    *,
    base_path: Path,
    parameter_hash: str,
    manifest_fingerprint: str,
    seed: int,
    run_id: str,
    merchant_universe: MerchantUniverse,
    hurdle_decisions: Sequence[HurdleDecision],
    nb_finals: Sequence[NBFinalRecord],
    s7_results: Sequence[MerchantAllocationResult],
) -> S8DeterministicContext:
    """Resolve upstream artefacts and build the immutable S8 context."""

    base_path = Path(base_path).expanduser().resolve()
    _ = base_path  # placeholder for future path-derived lookups
    decision_lookup = {int(decision.merchant_id): decision for decision in hurdle_decisions}
    nb_lookup = {int(record.merchant_id): int(record.n_outlets) for record in nb_finals}
    s7_lookup = {int(result.merchant_id): result for result in s7_results}

    merchants: list[MerchantSequencingInput] = []
    seen_merchant_ids: set[int] = set()

    for row in merchant_universe.merchants.to_dicts():
        merchant_id = int(row["merchant_id"])
        if merchant_id in seen_merchant_ids:
            raise err(
                "E_S8_DUPLICATE_MERCHANT",
                f"duplicate merchant entry detected for merchant_id={merchant_id}",
            )
        seen_merchant_ids.add(merchant_id)
        home_country_iso = str(row["home_country_iso"]).upper()

        decision = decision_lookup.get(merchant_id)
        if decision is None:
            raise err(
                "E_S8_HURDLE_MISSING",
                f"S1 hurdle decision missing for merchant_id={merchant_id}",
            )
        is_multi = bool(decision.is_multi)

        if is_multi:
            nb_record = nb_lookup.get(merchant_id)
            if nb_record is None:
                raise err(
                    "E_S8_NB_MISSING",
                    f"S2 nb_final result missing for merchant_id={merchant_id}",
                )
            if nb_record < 2:
                raise err(
                    "E_S8_N_INVALID",
                    f"S2 nb_final.n_outlets must be >=2 for merchant_id={merchant_id}",
                )
            allocation = s7_lookup.get(merchant_id)
            if allocation is None:
                raise err(
                    "E_S8_S7_MISSING",
                    f"S7 allocation result missing for merchant_id={merchant_id}",
                )
            domain_inputs = _build_domain_inputs(
                allocation=allocation,
                expected_total=nb_record,
                merchant_id=merchant_id,
            )
            raw_nb = nb_record
        else:
            domain_inputs = (
                CountrySequencingInput(
                    legal_country_iso=home_country_iso,
                    candidate_rank=0,
                    allocated_count=1,
                    is_home=True,
                ),
            )
            raw_nb = 1

        merchants.append(
            MerchantSequencingInput(
                merchant_id=merchant_id,
                home_country_iso=home_country_iso,
                single_vs_multi_flag=is_multi,
                raw_nb_outlet_draw=int(raw_nb),
                global_seed=int(seed),
                domain=tuple(domain_inputs),
            )
        )

    if not merchants:
        raise err(
            "E_S8_NO_MERCHANTS",
            f"no merchants discovered for parameter_hash={parameter_hash}",
        )

    sorted_merchants = tuple(sorted(merchants, key=lambda item: item.merchant_id))

    return S8DeterministicContext(
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        run_id=run_id,
        merchants=sorted_merchants,
        source_paths={},
    )


def _build_domain_inputs(
    *,
    allocation: MerchantAllocationResult,
    expected_total: int,
    merchant_id: int,
) -> tuple[CountrySequencingInput, ...]:
    domain_inputs: list[CountrySequencingInput] = []
    total = 0
    home_count = 0
    seen_ranks: set[int] = set()
    for entry in sorted(
        allocation.domain_allocations, key=lambda item: int(item.candidate_rank)
    ):
        rank = int(entry.candidate_rank)
        if rank in seen_ranks:
            raise err(
                "E_S8_DUPLICATE_RANK",
                f"duplicate candidate_rank={rank} for merchant_id={merchant_id}",
            )
        seen_ranks.add(rank)
        allocated = int(entry.allocated_count)
        if allocated <= 0:
            raise err(
                "E_S8_ALLOCATION_INVALID",
                "final_country_outlet_count must be >=1 "
                f"(merchant_id={merchant_id}, country={entry.country_iso}, count={allocated})",
            )
        if allocated > 999_999:
            raise err(
                "E_S8_ALLOCATION_OVERFLOW",
                f"final_country_outlet_count exceeds bound "
                f"(merchant_id={merchant_id}, country={entry.country_iso}, count={allocated})",
            )
        is_home = bool(entry.is_home)
        if is_home:
            home_count += 1
        domain_inputs.append(
            CountrySequencingInput(
                legal_country_iso=str(entry.country_iso).upper(),
                candidate_rank=rank,
                allocated_count=allocated,
                is_home=is_home,
            )
        )
        total += allocated

    if not domain_inputs:
        raise err(
            "E_S8_DOMAIN_EMPTY",
            f"S7 domain empty for merchant_id={merchant_id}",
        )
    if home_count != 1:
        raise err(
            "E_S8_HOME_MISMATCH",
            f"expected exactly one home entry for merchant_id={merchant_id}, found {home_count}",
        )
    if total != expected_total:
        raise err(
            "E_S8_SUM_LAW",
            "sum of final_country_outlet_count does not match nb_final.n_outlets "
            f"(merchant_id={merchant_id}, expected={expected_total}, actual={total})",
        )

    return tuple(domain_inputs)
