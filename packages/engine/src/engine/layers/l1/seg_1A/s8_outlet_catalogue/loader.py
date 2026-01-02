"""Load deterministic inputs required by the S8 pipeline."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence

import pandas as pd

from ..s0_foundations.l1.context import MerchantUniverse
from ..s0_foundations.exceptions import err
from ..s1_hurdle.l2.runner import HurdleDecision
from ..s2_nb_outlets.l2.runner import NBFinalRecord
from ..s7_integer_allocation.types import MerchantAllocationResult
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from ..shared.passed_flag import parse_passed_flag
from .contexts import (
    CountrySequencingInput,
    MerchantSequencingInput,
    S8DeterministicContext,
)

__all__ = ["load_deterministic_context"]

MAX_SEQUENCE = 999_999
logger = logging.getLogger(__name__)


def _load_parquet(path: Path, *, columns: Sequence[str]) -> pd.DataFrame:
    try:
        return pd.read_parquet(path, columns=list(columns))
    except FileNotFoundError as exc:
        raise err(
            "E_S8_INPUT_MISSING",
            f"required input parquet missing at '{path}'",
        ) from exc


def _resolve_optional_parquet(
    dataset_id: str,
    *,
    base_path: Path,
    template_args: Mapping[str, object],
    dictionary: Mapping[str, object],
) -> Path | None:
    candidate = resolve_dataset_path(
        dataset_id,
        base_path=base_path,
        template_args=template_args,
        dictionary=dictionary,
    )
    if candidate.exists():
        return candidate
    parent = candidate.parent
    if parent.exists():
        # attempt to find alternate shards
        shard_candidates = sorted(parent.glob(candidate.name.replace("00000", "*.parquet")))
        if shard_candidates:
            return shard_candidates[0]
    return None


def _verify_s6_pass(
    *,
    base_path: Path,
    seed: int,
    parameter_hash: str,
    dictionary: Mapping[str, object],
) -> Path:
    receipt_dir = resolve_dataset_path(
        "s6_validation_receipt",
        base_path=base_path,
        template_args={"seed": seed, "parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    receipt_path = receipt_dir / "S6_VALIDATION.json"
    flag_path = receipt_dir / "_passed.flag"
    if not receipt_path.exists() or not flag_path.exists():
        raise err(
            "E_S8_S6_GATE",
            f"S6 PASS receipt missing for seed={seed}, parameter_hash={parameter_hash}",
        )
    payload = receipt_path.read_text(encoding="utf-8")
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    try:
        actual = parse_passed_flag(flag_path.read_text(encoding="ascii"))
    except ValueError as exc:
        raise err("E_S8_S6_GATE", f"S6 _passed.flag malformed at '{flag_path}'") from exc
    if expected != actual:
        raise err(
            "E_S8_S6_GATE",
            "S6 PASS receipt hash mismatch detected while preparing S8 context",
        )
    return receipt_dir


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
    dictionary: Mapping[str, object] | None = None,
) -> S8DeterministicContext:
    """Resolve upstream artefacts and build the immutable S8 context."""

    base_path = Path(base_path).expanduser().resolve()
    dictionary = dictionary or load_dictionary()
    decision_lookup = {int(decision.merchant_id): decision for decision in hurdle_decisions}
    nb_lookup = {int(record.merchant_id): int(record.n_outlets) for record in nb_finals}
    s7_lookup = {int(result.merchant_id): result for result in s7_results}

    candidate_path = resolve_dataset_path(
        "s3_candidate_set",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    candidate_frame = _load_parquet(
        candidate_path,
        columns=["merchant_id", "country_iso", "candidate_rank", "is_home"],
    )
    candidate_lookup: MutableMapping[int, MutableMapping[str, int]] = {}
    for row in candidate_frame.itertuples(index=False):
        candidate_lookup.setdefault(int(row.merchant_id), {})[str(row.country_iso).upper()] = int(row.candidate_rank)

    s6_membership_path = _resolve_optional_parquet(
        "s6_membership",
        base_path=base_path,
        template_args={"seed": seed, "parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    membership_lookup: MutableMapping[int, MutableMapping[str, bool]] | None = None
    source_paths: dict[str, Path] = {"s3_candidate_set": candidate_path}
    counts_source = "s7_in_memory"

    if s6_membership_path is not None:
        _verify_s6_pass(
            base_path=base_path,
            seed=seed,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
        )
        membership_frame = pd.read_parquet(
            s6_membership_path,
            columns=["merchant_id", "country_iso"],
        )
        membership_lookup = {}
        for row in membership_frame.itertuples(index=False):
            membership_lookup.setdefault(int(row.merchant_id), {})[str(row.country_iso).upper()] = True
        source_paths["s6_membership"] = s6_membership_path

    counts_path = _resolve_optional_parquet(
        "s3_integerised_counts",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    s3_counts_lookup: Mapping[int, Mapping[str, int]] | None = None
    if counts_path is not None:
        columns = ["merchant_id", "country_iso", "count"]
        counts_frame = pd.read_parquet(counts_path, columns=columns)
        counts_map: MutableMapping[int, MutableMapping[str, int]] = {}
        for row in counts_frame.itertuples(index=False):
            counts_map.setdefault(int(row.merchant_id), {})[str(row.country_iso).upper()] = int(row.count)
        s3_counts_lookup = counts_map
        counts_source = "s3_integerised_counts"
        source_paths["s3_integerised_counts"] = counts_path

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
                logger.warning(
                    "S8 missing S7 allocation; defaulting to home-only allocation for merchant %s",
                    merchant_id,
                )
                candidate_rank = candidate_lookup.get(merchant_id, {}).get(home_country_iso, 0)
                domain_inputs = (
                    CountrySequencingInput(
                        legal_country_iso=home_country_iso,
                        candidate_rank=int(candidate_rank),
                        allocated_count=int(nb_record),
                        is_home=True,
                    ),
                )
                raw_nb = nb_record
            else:
                domain_inputs = _build_domain_inputs(
                    allocation=allocation,
                    expected_total=nb_record,
                    merchant_id=merchant_id,
                    s3_counts_lookup=s3_counts_lookup,
                    candidate_lookup=candidate_lookup,
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
        candidate_lookup={merchant: dict(country_map) for merchant, country_map in candidate_lookup.items()},
        membership_lookup=None if membership_lookup is None else {merchant: dict(flags) for merchant, flags in membership_lookup.items()},
        counts_source=counts_source,
        source_paths=(
            {key: value for key, value in source_paths.items() if isinstance(value, Path)}
            if source_paths
            else {}
        ),
    )


def _build_domain_inputs(
    *,
    allocation: MerchantAllocationResult,
    expected_total: int,
    merchant_id: int,
    s3_counts_lookup: Mapping[int, Mapping[str, int]] | None,
    candidate_lookup: Mapping[int, Mapping[str, int]],
) -> tuple[CountrySequencingInput, ...]:
    domain_inputs: list[CountrySequencingInput] = []
    total = 0
    home_count = 0
    seen_ranks: set[int] = set()
    counts_map = s3_counts_lookup.get(merchant_id) if s3_counts_lookup is not None else None
    candidate_map = candidate_lookup.get(merchant_id, {})
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

        iso = str(entry.country_iso).upper()
        candidate_rank = candidate_map.get(iso)
        if candidate_rank is None:
            raise err(
                "E_S8_CANDIDATE_MISSING",
                f"S3 candidate set missing iso '{iso}' for merchant_id={merchant_id}",
            )

        if counts_map is not None:
            allocated = counts_map.get(iso)
            if allocated is None:
                raise err(
                    "E_S8_COUNTS_SOURCE_MISSING",
                    f"s3_integerised_counts missing iso '{iso}' for merchant_id={merchant_id}",
                )
        else:
            allocated = int(entry.allocated_count)

        if allocated <= 0:
            logger.warning(
                "S8 allocation zero/negative; dropping country %s for merchant %s",
                iso,
                merchant_id,
            )
            continue
        is_home = bool(entry.is_home)
        if is_home:
            home_count += 1
        domain_inputs.append(
            CountrySequencingInput(
                legal_country_iso=iso,
                candidate_rank=int(candidate_rank),
                allocated_count=int(allocated),
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
