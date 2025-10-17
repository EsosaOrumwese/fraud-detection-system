"""Validation logic for the S9 replay gate."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from ..s0_foundations.exceptions import ErrorContext, S0Error, err
from .contexts import (
    S9DeterministicContext,
    S9ValidationMetrics,
    S9ValidationResult,
)

__all__ = ["validate_outputs"]


def validate_outputs(context: S9DeterministicContext) -> S9ValidationResult:
    """Run the S9 validation battery and return the consolidated result."""

    failures: list[ErrorContext] = []
    failure_counts: dict[str, int] = defaultdict(int)
    metrics = S9ValidationMetrics()

    outlet = context.surfaces.outlet_catalogue.to_pandas()
    candidate_set = context.surfaces.s3_candidate_set.to_pandas()
    counts_df = (
        context.surfaces.s3_integerised_counts.to_pandas()
        if context.surfaces.s3_integerised_counts is not None
        else None
    )
    membership_df = (
        context.surfaces.s6_membership.to_pandas()
        if context.surfaces.s6_membership is not None
        else None
    )
    nb_final_df = context.surfaces.nb_final_events
    sequence_df = context.surfaces.sequence_finalize_events

    metrics.rows_total = int(len(outlet))
    metrics.merchants_total = int(outlet["merchant_id"].nunique()) if "merchant_id" in outlet else 0

    counts_source = "s3_integerised_counts" if counts_df is not None else "residual_rank"
    membership_source = "s6_membership" if membership_df is not None else "gumbel_key"

    def record_failure(exc: S0Error) -> None:
        failures.append(exc.context)
        failure_counts[exc.context.code] += 1

    if outlet.empty:
        record_failure(err("E_DATASET_EMPTY", "outlet_catalogue is empty"))

    try:
        _check_manifest_seed_alignment(
            outlet,
            manifest_fingerprint=context.manifest_fingerprint,
            seed=context.seed,
        )
    except S0Error as exc:
        record_failure(exc)

    try:
        _check_candidate_ranks(candidate_set)
    except S0Error as exc:
        record_failure(exc)

    expected_counts = (
        _build_counts_from_integerised(counts_df) if counts_df is not None else {}
    )

    if not expected_counts and nb_final_df is not None and not nb_final_df.empty:
        expected_counts = _build_counts_from_nb_final(nb_final_df)

    try:
        block_counts, merchant_totals = _check_outlet_sequences(
            outlet,
            expected_counts=expected_counts,
            sequence_events=sequence_df,
            metrics=metrics,
        )
        egress_writer_sort_ok = _check_writer_sort(outlet)
    except S0Error as exc:
        record_failure(exc)
        block_counts = {}
        merchant_totals = {}
        egress_writer_sort_ok = False

    if nb_final_df is not None and not nb_final_df.empty:
        try:
            _check_nb_sum_law(nb_final_df, merchant_totals)
        except S0Error as exc:
            record_failure(exc)

    if membership_df is not None:
        try:
            _check_membership_alignment(outlet, membership_df)
            metrics.membership_rows = int(len(membership_df))
        except S0Error as exc:
            record_failure(exc)
    else:
        metrics.membership_rows = 0

    metrics.merchants_validated = metrics.merchants_total if not failures else 0
    metrics.merchants_failed = 0 if not failures else metrics.merchants_total

    summary = {
        "seed": context.seed,
        "parameter_hash": context.parameter_hash,
        "manifest_fingerprint": context.manifest_fingerprint,
        "run_id": context.run_id,
        "decision": "PASS" if not failures else "FAIL",
        "rows_total": metrics.rows_total,
        "merchants_total": metrics.merchants_total,
        "merchants_failed": metrics.merchants_failed,
        "sequence_blocks": len(block_counts),
        "failures": [
            {
                "code": failure.code,
                "detail": failure.detail,
            }
            for failure in failures
        ],
        "failures_by_code": dict(sorted(failure_counts.items())),
        "counts_source": counts_source,
        "membership_source": membership_source,
        "egress_writer_sort": egress_writer_sort_ok,
    }

    rng_accounting: Dict[str, object] = {
        "runs": [
            {
                "seed": context.seed,
                "parameter_hash": context.parameter_hash,
                "run_id": context.run_id,
            }
        ],
        "nb_final_events": int(len(nb_final_df)) if nb_final_df is not None else 0,
        "sequence_finalize_events": int(len(sequence_df)) if sequence_df is not None else 0,
    }

    return S9ValidationResult(
        passed=not failures,
        failures=tuple(failures),
        metrics=metrics,
        summary=summary,
        rng_accounting=rng_accounting,
        failures_by_code=summary["failures_by_code"],
        counts_source=counts_source,
        membership_source=membership_source,
        egress_writer_sort_ok=egress_writer_sort_ok,
    )


def _check_manifest_seed_alignment(outlet, *, manifest_fingerprint: str, seed: int) -> None:
    if "manifest_fingerprint" in outlet.columns:
        mismatched = outlet["manifest_fingerprint"] != manifest_fingerprint
        if bool(mismatched.any()):
            raise err("E_PATH_EMBED_MISMATCH", "manifest_fingerprint column mismatch detected")
    if "global_seed" in outlet.columns:
        mismatched = outlet["global_seed"] != seed
        if bool(mismatched.any()):
            raise err("E_PATH_EMBED_MISMATCH", "global_seed column mismatch detected")


def _check_candidate_ranks(candidate_set: pd.DataFrame) -> None:
    if candidate_set.empty:
        raise err("E_S3_EMPTY", "s3_candidate_set is empty")
    grouped = candidate_set.groupby("merchant_id")
    for merchant_id, frame in grouped:
        if "candidate_rank" not in frame:
            raise err("E_S3_RANK_MISSING", "candidate_rank column missing in s3_candidate_set")
        ranks = sorted(frame["candidate_rank"].tolist())
        if not ranks or ranks[0] != 0:
            raise err("E_S3_HOME_NOT_ZERO", f"merchant {merchant_id} missing rank 0 home entry")
        expected = list(range(len(ranks)))
        if ranks != expected:
            raise err("E_S3_RANK_GAPS", f"merchant {merchant_id} candidate ranks not contiguous")


def _build_counts_from_integerised(rows) -> Mapping[tuple[int, str], int]:
    if rows is None or rows.empty:
        return {}
    counts: dict[tuple[int, str], int] = {}
    for merchant_id, country_iso, count in zip(
        rows["merchant_id"], rows["country_iso"], rows["count"], strict=False
    ):
        counts[(int(merchant_id), str(country_iso))] = int(count)
    return counts


def _build_counts_from_nb_final(rows: pd.DataFrame) -> Mapping[tuple[int, str], int]:
    if rows.empty:
        return {}
    counts: dict[tuple[int, str], int] = {}
    for merchant_id, n_outlets in zip(rows.get("merchant_id", []), rows.get("n_outlets", []), strict=False):
        counts[(int(merchant_id), "__TOTAL__")] = int(n_outlets)
    return counts


def _check_outlet_sequences(
    outlet,
    *,
    expected_counts: Mapping[tuple[int, str], int],
    sequence_events: pd.DataFrame | None,
    metrics: S9ValidationMetrics,
) -> tuple[Mapping[tuple[int, str], int], Mapping[int, int]]:
    block_counts: dict[tuple[int, str], int] = {}
    merchant_totals: dict[int, int] = defaultdict(int)
    required_columns = {"merchant_id", "legal_country_iso", "site_order", "site_id", "final_country_outlet_count"}
    if not required_columns.issubset(outlet.columns):
        missing = required_columns - set(outlet.columns)
        raise err("E_S8_COLUMNS_MISSING", f"outlet_catalogue missing columns {sorted(missing)}")

    outlet_sorted = outlet.sort_values(["merchant_id", "legal_country_iso", "site_order"])
    for (merchant_id, iso), frame in outlet_sorted.groupby(["merchant_id", "legal_country_iso"]):
        site_orders = frame["site_order"].astype(int).to_numpy()
        expected_range = np.arange(1, len(frame) + 1, dtype=int)
        if len(site_orders) != len(frame) or not np.array_equal(site_orders, expected_range):
            raise err(
                "E_S8_SEQUENCE_GAP",
                f"site_order not contiguous for merchant={merchant_id}, country={iso}",
            )
        site_ids = frame["site_id"].astype(str).to_list()
        expected_ids = [f"{order:06d}" for order in expected_range]
        if site_ids != expected_ids:
            raise err(
                "E_SITE_ID_FORMAT",
                f"site_id mismatch for merchant={merchant_id}, country={iso}",
            )
        declared_count = int(frame["final_country_outlet_count"].iloc[0])
        if declared_count != len(frame):
            raise err(
                "E_SUM_MISMATCH",
                f"declared final_country_outlet_count does not match rows for merchant={merchant_id}, country={iso}",
            )
        block_counts[(int(merchant_id), str(iso))] = len(frame)
        merchant_totals[int(merchant_id)] += len(frame)

        expected = expected_counts.get((int(merchant_id), str(iso)))
        if expected is not None and expected != len(frame):
            raise err(
                "E_S7_PARITY",
                f"count mismatch for merchant={merchant_id}, country={iso}: expected {expected}, found {len(frame)}",
            )

    if sequence_events is not None and not sequence_events.empty:
        metrics.sequence_events = int(len(sequence_events))
        _check_sequence_events(sequence_events, block_counts)

    return block_counts, merchant_totals


def _check_sequence_events(sequence_events: pd.DataFrame, block_counts: Mapping[tuple[int, str], int]) -> None:
    for merchant_id, country_iso, site_count, start_seq, end_seq in zip(
        sequence_events.get("merchant_id", []),
        sequence_events.get("legal_country_iso", []),
        sequence_events.get("site_count", []),
        sequence_events.get("site_order_start", []),
        sequence_events.get("site_order_end", []),
        strict=False,
    ):
        key = (int(merchant_id), str(country_iso))
        expected_count = block_counts.get(key)
        if expected_count is None:
            raise err(
                "E_SEQUENCE_MISSING_BLOCK",
                f"sequence_finalize present for unexpected block merchant={merchant_id}, country={country_iso}",
            )
        if int(site_count) != expected_count:
            raise err(
                "E_SEQUENCE_COUNT_MISMATCH",
                f"sequence_finalize count mismatch for merchant={merchant_id}, country={country_iso}",
            )
        if int(start_seq) != 1 or int(end_seq) != expected_count:
            raise err(
                "E_SEQUENCE_RANGE_INVALID",
                f"sequence_finalize range invalid for merchant={merchant_id}, country={country_iso}",
            )


def _check_nb_sum_law(nb_final: pd.DataFrame, merchant_totals: Mapping[int, int]) -> None:
    if "merchant_id" not in nb_final or "n_outlets" not in nb_final:
        raise err("E_S2_COLUMNS_MISSING", "nb_final events missing required columns")
    for merchant_id, n_outlets in zip(nb_final["merchant_id"], nb_final["n_outlets"], strict=False):
        total = merchant_totals.get(int(merchant_id))
        if total is None:
            raise err(
                "E_S2_FINAL_MISSING",
                f"nb_final event exists for merchant={merchant_id}, but no egress rows found",
            )
        if int(n_outlets) != total:
            raise err(
                "E_S2_N_MISMATCH",
                f"merchant {merchant_id} outlet count mismatch (nb_final={n_outlets}, egress={total})",
            )


def _check_membership_alignment(outlet, membership) -> None:
    if "merchant_id" not in membership or "country_iso" not in membership:
        raise err("E_S6_MEMBERSHIP_COLUMNS", "s6_membership missing required columns")
    membership_lookup: dict[int, set[str]] = defaultdict(set)
    for merchant_id, country_iso in zip(membership["merchant_id"], membership["country_iso"], strict=False):
        membership_lookup[int(merchant_id)].add(str(country_iso).upper())

    for (merchant_id, country_iso), frame in outlet.groupby(["merchant_id", "legal_country_iso"]):
        if str(country_iso).upper() == str(frame["home_country_iso"].iloc[0]).upper():
            continue
        selected = membership_lookup.get(int(merchant_id), set())
        if str(country_iso).upper() not in selected:
            raise err(
                "E_S6_MEMBERSHIP_MISMATCH",
                f"country {country_iso} missing from membership for merchant={merchant_id}",
            )


def _check_writer_sort(outlet: pd.DataFrame) -> bool:
    """Return True when outlet rows obey the declared writer sort order."""

    if outlet.empty:
        return True
    ordered = outlet.sort_values(
        ["merchant_id", "legal_country_iso", "site_order"],
        kind="mergesort",
    ).reset_index(drop=True)
    return outlet.reset_index(drop=True).equals(ordered)
