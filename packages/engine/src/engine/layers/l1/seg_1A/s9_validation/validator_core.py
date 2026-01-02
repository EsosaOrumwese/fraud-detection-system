"""Validation logic for the S9 replay gate."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml
from jsonschema import Draft202012Validator, ValidationError

from ..shared.dictionary import get_repo_root, load_dictionary
from ..s0_foundations.l0.artifacts import ArtifactDigest, hash_artifact
from ..s0_foundations.l1.hashing import compute_manifest_fingerprint, compute_parameter_hash
from ..s0_foundations.exceptions import ErrorContext, S0Error, err
from . import constants as c
from .contexts import (
    S9DeterministicContext,
    S9ValidationMetrics,
    S9ValidationResult,
)

__all__ = ["validate_outputs"]

_REQUIRED_COLUMNS: Dict[str, Sequence[str]] = {
    c.DATASET_OUTLET_CATALOGUE: (
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "site_id",
        "final_country_outlet_count",
        "manifest_fingerprint",
        "global_seed",
        "home_country_iso",
    ),
    c.DATASET_S3_CANDIDATE_SET: (
        "merchant_id",
        "candidate_rank",
        "country_iso",
        "is_home",
        "parameter_hash",
    ),
    c.DATASET_S3_INTEGERISED_COUNTS: (
        "merchant_id",
        "country_iso",
        "count",
        "parameter_hash",
    ),
    c.DATASET_S3_SITE_SEQUENCE: (
        "merchant_id",
        "country_iso",
        "site_order",
        "site_id",
        "parameter_hash",
    ),
    c.DATASET_S6_MEMBERSHIP: (
        "merchant_id",
        "country_iso",
        "parameter_hash",
    ),
}

_DATASET_DICTIONARY: Mapping[str, object] | None = None
_SCHEMA_DOCS: Dict[str, Dict[str, Any]] = {}
_SCHEMA_CACHE: Dict[tuple[str, str], Draft202012Validator] = {}
_SCHEMA_VERSION_CACHE: Dict[tuple[str, str], str] = {}
_ISO_CODES: set[str] | None = None

_HEX64_RE = re.compile(r"^[a-f0-9]{64}$")

_RNG_BUDGET_TABLE: Mapping[str, Mapping[str, object]] = {
    c.EVENT_FAMILY_ANCHOR: {"type": "non_consuming"},
    c.EVENT_FAMILY_NB_FINAL: {"type": "non_consuming"},
    c.EVENT_FAMILY_SEQUENCE_FINALIZE: {"type": "non_consuming"},
    c.EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW: {"type": "non_consuming"},
    c.EVENT_FAMILY_RESIDUAL_RANK: {"type": "non_consuming"},
    c.EVENT_FAMILY_ZTP_REJECTION: {"type": "non_consuming"},
    c.EVENT_FAMILY_ZTP_RETRY_EXHAUSTED: {"type": "non_consuming"},
    c.EVENT_FAMILY_ZTP_FINAL: {"type": "non_consuming"},
    c.EVENT_FAMILY_GUMBEL_KEY: {"type": "fixed_consumption", "blocks": 1, "draws": 1},
    c.EVENT_FAMILY_HURDLE_BERNOULLI: {
        "type": "conditional_consumption",
        "deterministic": {"blocks": 0, "draws": 0},
        "stochastic": {"blocks": 1, "draws": 1},
    },
    c.EVENT_FAMILY_GAMMA_COMPONENT: {"type": "positive_consumption", "min_blocks": 1, "min_draws": 1},
    c.EVENT_FAMILY_POISSON_COMPONENT: {
        "type": "positive_consumption",
        "min_blocks": 1,
        "min_draws": 1,
        "context": ["nb", "ztp"],
    },
    c.EVENT_FAMILY_DIRICHLET_GAMMA_VECTOR: {"type": "positive_consumption", "min_blocks": 1, "min_draws": 1},
}


def validate_outputs(context: S9DeterministicContext) -> S9ValidationResult:
    """Run the S9 validation battery and return the consolidated result."""

    failures: list[ErrorContext] = []
    failure_counts: dict[str, int] = defaultdict(int)
    metrics = S9ValidationMetrics()
    schema_versions: Dict[str, str] = {}

    surfaces = context.surfaces

    outlet = surfaces.outlet_catalogue.to_pandas()
    candidate_set = surfaces.s3_candidate_set.to_pandas()
    counts_df = (
        surfaces.s3_integerised_counts.to_pandas()
        if surfaces.s3_integerised_counts is not None
        else None
    )
    membership_df = (
        surfaces.s6_membership.to_pandas()
        if surfaces.s6_membership is not None
        else None
    )
    site_sequence_df = (
        surfaces.s3_site_sequence.to_pandas()
        if surfaces.s3_site_sequence is not None
        else None
    )

    nb_final_df = (
        surfaces.nb_final_events.copy()
        if isinstance(surfaces.nb_final_events, pd.DataFrame)
        else pd.DataFrame()
    )
    sequence_df = (
        surfaces.sequence_finalize_events.copy()
        if isinstance(surfaces.sequence_finalize_events, pd.DataFrame)
        else pd.DataFrame()
    )
    audit_df = (
        surfaces.rng_audit_log.copy()
        if isinstance(surfaces.rng_audit_log, pd.DataFrame)
        else pd.DataFrame()
    )
    trace_df = (
        surfaces.rng_trace_log.copy()
        if isinstance(surfaces.rng_trace_log, pd.DataFrame)
        else pd.DataFrame()
    )
    rng_events: Dict[str, pd.DataFrame] = {
        dataset_id: df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        for dataset_id, df in surfaces.rng_events.items()
    }

    metrics.rows_total = int(len(outlet))
    metrics.merchants_total = int(outlet["merchant_id"].nunique()) if "merchant_id" in outlet else 0
    metrics.nb_final_events = int(len(nb_final_df))
    metrics.membership_rows = int(len(membership_df)) if membership_df is not None else 0

    counts_source = "s3_integerised_counts" if counts_df is not None else "residual_rank"
    membership_source = "s6_membership" if membership_df is not None else "gumbel_key"

    def record_schema_version(dataset_id: str) -> None:
        try:
            entry = _dictionary_entry(dataset_id)
        except S0Error:
            return
        schema_ref = entry.get("schema_ref")
        if schema_ref:
            schema_versions[dataset_id] = _schema_version(schema_ref)

    def record_failure(exc: S0Error) -> None:
        failures.append(exc.context)
        failure_counts[exc.context.code] += 1

    def safe_call(callback: Callable[[], None]) -> None:
        try:
            callback()
        except S0Error as exc:
            record_failure(exc)

    safe_call(lambda: _require_non_empty(outlet, c.DATASET_OUTLET_CATALOGUE))
    safe_call(lambda: _require_non_empty(candidate_set, c.DATASET_S3_CANDIDATE_SET))

    safe_call(
        lambda: _validate_partition_tokens(
            context.source_paths.get(c.DATASET_OUTLET_CATALOGUE, ()),
            {"seed": str(context.seed), "fingerprint": context.manifest_fingerprint},
            dataset=c.DATASET_OUTLET_CATALOGUE,
        )
    )
    safe_call(
        lambda: _validate_partition_tokens(
            context.source_paths.get(c.DATASET_S3_CANDIDATE_SET, ()),
            {"parameter_hash": context.parameter_hash},
            dataset=c.DATASET_S3_CANDIDATE_SET,
        )
    )
    if counts_df is not None:
        safe_call(
            lambda: _validate_partition_tokens(
                context.source_paths.get(c.DATASET_S3_INTEGERISED_COUNTS, ()),
                {"parameter_hash": context.parameter_hash},
                dataset=c.DATASET_S3_INTEGERISED_COUNTS,
            )
        )
    if membership_df is not None:
        safe_call(
            lambda: _validate_partition_tokens(
                context.source_paths.get(c.DATASET_S6_MEMBERSHIP, ()),
                {"parameter_hash": context.parameter_hash, "seed": str(context.seed)},
                dataset=c.DATASET_S6_MEMBERSHIP,
            )
        )
    if site_sequence_df is not None:
        safe_call(
            lambda: _validate_partition_tokens(
                context.source_paths.get(c.DATASET_S3_SITE_SEQUENCE, ()),
                {"parameter_hash": context.parameter_hash},
                dataset=c.DATASET_S3_SITE_SEQUENCE,
            )
        )
    safe_call(
        lambda: _validate_partition_tokens(
            context.source_paths.get(c.AUDIT_LOG_ID, ()),
            {"seed": str(context.seed), "parameter_hash": context.parameter_hash, "run_id": context.run_id},
            dataset=c.AUDIT_LOG_ID,
        )
    )
    safe_call(
        lambda: _validate_partition_tokens(
            context.source_paths.get(c.TRACE_LOG_ID, ()),
            {"seed": str(context.seed), "parameter_hash": context.parameter_hash, "run_id": context.run_id},
            dataset=c.TRACE_LOG_ID,
        )
    )

    for dataset_id in c.RNG_EVENT_DATASETS:
        paths = context.source_paths.get(dataset_id, ())
        safe_call(
            lambda dataset_id=dataset_id, paths=paths: _validate_partition_tokens(
                paths,
                {"seed": str(context.seed), "parameter_hash": context.parameter_hash, "run_id": context.run_id},
                dataset=dataset_id,
                allow_empty=True,
            )
        )
        record_schema_version(dataset_id)

    safe_call(
        lambda: _assert_column_equals(
            outlet,
            "manifest_fingerprint",
            context.manifest_fingerprint,
            c.DATASET_OUTLET_CATALOGUE,
        )
    )
    safe_call(
        lambda: _assert_column_equals(
            outlet,
            "global_seed",
            context.seed,
            c.DATASET_OUTLET_CATALOGUE,
        )
    )
    safe_call(
        lambda: _assert_column_equals(
            candidate_set,
            "parameter_hash",
            context.parameter_hash,
            c.DATASET_S3_CANDIDATE_SET,
        )
    )
    if counts_df is not None:
        safe_call(
            lambda: _assert_column_equals(
                counts_df,
                "parameter_hash",
                context.parameter_hash,
                c.DATASET_S3_INTEGERISED_COUNTS,
            )
        )
    if membership_df is not None:
        safe_call(
            lambda: _assert_column_equals(
                membership_df,
                "parameter_hash",
                context.parameter_hash,
                c.DATASET_S6_MEMBERSHIP,
        )
    )

    safe_call(lambda: _require_columns(outlet, c.DATASET_OUTLET_CATALOGUE))
    safe_call(lambda: _require_columns(candidate_set, c.DATASET_S3_CANDIDATE_SET))
    if counts_df is not None:
        safe_call(lambda: _require_columns(counts_df, c.DATASET_S3_INTEGERISED_COUNTS))
    if membership_df is not None:
        safe_call(lambda: _require_columns(membership_df, c.DATASET_S6_MEMBERSHIP))
    if site_sequence_df is not None:
        safe_call(lambda: _require_columns(site_sequence_df, c.DATASET_S3_SITE_SEQUENCE))

    safe_call(lambda: _assert_iso_columns(outlet, ("legal_country_iso", "home_country_iso"), c.DATASET_OUTLET_CATALOGUE))
    safe_call(lambda: _assert_iso_columns(candidate_set, ("country_iso",), c.DATASET_S3_CANDIDATE_SET))
    if counts_df is not None:
        safe_call(lambda: _assert_iso_columns(counts_df, ("country_iso",), c.DATASET_S3_INTEGERISED_COUNTS))
    if membership_df is not None:
        safe_call(lambda: _assert_iso_columns(membership_df, ("country_iso",), c.DATASET_S6_MEMBERSHIP))
    if site_sequence_df is not None:
        safe_call(lambda: _assert_iso_columns(site_sequence_df, ("country_iso",), c.DATASET_S3_SITE_SEQUENCE))

    record_schema_version(c.DATASET_OUTLET_CATALOGUE)
    record_schema_version(c.DATASET_S3_CANDIDATE_SET)
    safe_call(lambda: _validate_dataset_schema(c.DATASET_OUTLET_CATALOGUE, outlet))
    safe_call(lambda: _validate_dataset_schema(c.DATASET_S3_CANDIDATE_SET, candidate_set))
    if counts_df is not None:
        record_schema_version(c.DATASET_S3_INTEGERISED_COUNTS)
        safe_call(lambda: _validate_dataset_schema(c.DATASET_S3_INTEGERISED_COUNTS, counts_df))
    if membership_df is not None:
        record_schema_version(c.DATASET_S6_MEMBERSHIP)
        safe_call(lambda: _validate_dataset_schema(c.DATASET_S6_MEMBERSHIP, membership_df))
    if site_sequence_df is not None:
        record_schema_version(c.DATASET_S3_SITE_SEQUENCE)
        safe_call(lambda: _validate_dataset_schema(c.DATASET_S3_SITE_SEQUENCE, site_sequence_df))

    safe_call(lambda: _check_candidate_ranks(candidate_set))
    safe_call(
        lambda: _assert_unique(
            candidate_set,
            ["merchant_id", "candidate_rank", "country_iso"],
            c.DATASET_S3_CANDIDATE_SET,
        )
    )
    if site_sequence_df is not None:
        safe_call(
            lambda: _assert_unique(
                site_sequence_df,
                ["merchant_id", "country_iso", "site_order"],
                c.DATASET_S3_SITE_SEQUENCE,
            )
        )
    if counts_df is not None:
        safe_call(
            lambda: _assert_unique(
                counts_df,
                ["merchant_id", "country_iso"],
                c.DATASET_S3_INTEGERISED_COUNTS,
            )
        )
    if membership_df is not None:
        safe_call(
            lambda: _assert_unique(
                membership_df,
                ["merchant_id", "country_iso"],
                c.DATASET_S6_MEMBERSHIP,
            )
        )

    expected_counts = (
        _build_counts_from_integerised(counts_df) if counts_df is not None else {}
    )
    if not expected_counts and not nb_final_df.empty:
        expected_counts = _build_counts_from_nb_final(nb_final_df)

    block_counts: Mapping[tuple[int, str], int] = {}
    merchant_totals: Mapping[int, int] = {}
    egress_writer_sort_ok = False
    outlet_valid = False

    def outlet_validation() -> None:
        nonlocal block_counts, merchant_totals, egress_writer_sort_ok, outlet_valid
        block_counts, merchant_totals = _check_outlet_sequences(
            outlet,
            expected_counts=expected_counts,
            sequence_events=sequence_df,
            metrics=metrics,
        )
        egress_writer_sort_ok = _check_writer_sort(outlet)
        outlet_valid = True

    safe_call(outlet_validation)
    safe_call(lambda: _assert_iso_columns(sequence_df, ("country_iso",), c.EVENT_FAMILY_SEQUENCE_FINALIZE))

    if outlet_valid and not nb_final_df.empty:
        safe_call(lambda: _check_nb_sum_law(nb_final_df, merchant_totals))

    if membership_df is not None and outlet_valid:
        safe_call(lambda: _check_membership_alignment(outlet, membership_df))

    overflow_merchants: set[int] = set()

    def overflow_validation() -> None:
        nonlocal overflow_merchants
        overflow_df = rng_events.get(c.EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW, pd.DataFrame())
        if overflow_df is None or overflow_df.empty:
            return
        if "merchant_id" not in overflow_df.columns:
            raise err(
                "E_OVERFLOW_POLICY_BREACH",
                "site_sequence_overflow missing merchant_id column",
            )
        required = {"merchant_id", "attempted_count", "max_seq", "overflow_by"}
        missing = required - set(overflow_df.columns)
        if missing:
            raise err(
                "E_SCHEMA_INVALID",
                f"site_sequence_overflow missing columns {sorted(missing)}",
            )
        overflow_merchants = {int(value) for value in overflow_df["merchant_id"].unique()}
        if outlet_valid:
            present = outlet[outlet["merchant_id"].isin(overflow_merchants)]
            if not present.empty:
                raise err(
                    "E_OVERFLOW_POLICY_BREACH",
                    "overflow merchants present in outlet_catalogue",
                )

    safe_call(overflow_validation)

    safe_call(lambda: _validate_trace_identity(context, trace_df))
    safe_call(lambda: _validate_audit_identity(context, audit_df))
    safe_call(lambda: _recompute_lineage(context))

    rng_accounting = _build_rng_accounting(
        context=context,
        rng_events=rng_events,
        trace_df=trace_df,
        audit_df=audit_df,
        record_failure=record_failure,
    )

    metrics.merchants_validated = metrics.merchants_total if not failures else 0
    metrics.merchants_failed = metrics.merchants_total - metrics.merchants_validated

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
        "overflow_merchants": sorted(overflow_merchants),
        "schema_versions": dict(sorted(schema_versions.items())),
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


def _require_non_empty(frame: pd.DataFrame, dataset: str) -> None:
    if frame.empty:
        raise err("E_DATASET_EMPTY", f"{dataset} is empty")


def _validate_partition_tokens(
    paths: Sequence[Path],
    expected: Mapping[str, Any],
    *,
    dataset: str,
    allow_empty: bool = False,
) -> None:
    if not paths:
        if allow_empty:
            return
        raise err("E_PARTITION_MISPLACED", f"{dataset} partition missing or empty")

    expected_tokens = {key: str(value) for key, value in expected.items()}
    for path in paths:
        tokens = _extract_partition_tokens(Path(path))
        for key, expected_value in expected_tokens.items():
            actual_value = tokens.get(key)
            if actual_value != expected_value:
                raise err(
                    "E_PARTITION_MISPLACED",
                    f"{dataset} path token '{key}' mismatch (expected '{expected_value}', found '{actual_value}')",
                )


def _extract_partition_tokens(path: Path) -> Dict[str, str]:
    tokens: Dict[str, str] = {}
    for part in path.parts:
        if "=" in part:
            key, value = part.split("=", 1)
            tokens[key] = value
    return tokens


def _assert_column_equals(frame: pd.DataFrame, column: str, expected: Any, dataset: str) -> None:
    if column not in frame.columns:
        raise err("E_SCHEMA_INVALID", f"{dataset} missing column '{column}'")

    series = frame[column]
    if pd.api.types.is_integer_dtype(series):
        expected_value = int(expected)
        comparison = series == expected_value
    elif pd.api.types.is_float_dtype(series):
        expected_value = float(expected)
        comparison = np.isclose(series.astype(float), expected_value, equal_nan=True)
    else:
        comparison = series.astype(str) == str(expected)
    if not bool(comparison.all()):
        raise err(
            "E_PATH_EMBED_MISMATCH",
            f"{dataset}.{column} mismatch for expected value '{expected}'",
        )


def _assert_unique(frame: pd.DataFrame, columns: Sequence[str], dataset: str) -> None:
    if frame.empty:
        return
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise err(
            "E_SCHEMA_INVALID",
            f"{dataset} missing columns {sorted(missing)}",
        )
    if frame.duplicated(subset=list(columns)).any():
        raise err(
            "E_DUP_PK",
            f"{dataset} contains duplicate keys for columns {list(columns)}",
        )


def _require_columns(frame: pd.DataFrame | None, dataset: str) -> None:
    if frame is None:
        return
    required = _REQUIRED_COLUMNS.get(dataset)
    if not required:
        return
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise err("E_SCHEMA_INVALID", f"{dataset} missing columns {sorted(missing)}")


def _assert_iso_columns(frame: pd.DataFrame | None, columns: Sequence[str], dataset: str) -> None:
    if frame is None or frame.empty:
        return
    iso_codes = _load_iso_codes()
    for column in columns:
        if column not in frame.columns:
            raise err("E_SCHEMA_INVALID", f"{dataset} missing column '{column}' for ISO validation")
        series = frame[column].dropna()
        if series.empty:
            continue
        values = series.astype(str).str.upper()
        if iso_codes:
            if not values.isin(iso_codes).all():
                raise err(
                    "E_FK_ISO_INVALID",
                    f"{dataset}.{column} contains invalid ISO codes",
                )
        else:
            if not values.str.fullmatch(r"[A-Z]{2}").all():
                raise err(
                    "E_FK_ISO_INVALID",
                    f"{dataset}.{column} contains non ISO-3166 alpha-2 values",
                )


def _digest_from_record(
    record: Mapping[str, Any],
    *,
    base_path: Path,
    error_prefix: str,
) -> ArtifactDigest:
    raw_path = str(record.get("path") or "")
    filename = record.get("filename")
    if not isinstance(filename, str):
        filename = ""
    sha_hex = record.get("sha256_hex") or record.get("sha256")
    basename = filename or (Path(raw_path).name if raw_path else "")

    if isinstance(sha_hex, str) and _HEX64_RE.fullmatch(sha_hex):
        path_value = Path(raw_path or basename)
        size_bytes = int(record.get("size_bytes") or 0)
        mtime_ns = int(record.get("mtime_ns") or 0)
        return ArtifactDigest(
            basename=basename or path_value.name,
            path=path_value,
            size_bytes=size_bytes,
            mtime_ns=mtime_ns,
            sha256_digest=bytes.fromhex(sha_hex),
        )

    if not raw_path:
        raise err(f"{error_prefix}_IO", "artefact path missing in lineage record")

    resolved = _resolve_artifact_path(raw_path, base_path)
    return hash_artifact(resolved, error_prefix=error_prefix)


def _recompute_lineage(context: S9DeterministicContext) -> None:
    mapping = context.lineage_paths
    required_keys = ("param_digest_log.jsonl", "fingerprint_artifacts.jsonl")
    for key in required_keys:
        if key not in mapping:
            raise err("E_LINEAGE_RECOMPUTE_MISSING", f"lineage file '{key}' missing for recomputation")

    param_records = _load_jsonl_records(mapping["param_digest_log.jsonl"])
    if not param_records:
        raise err("E_LINEAGE_RECOMPUTE_MISSING", "param_digest_log.jsonl is empty")

    parameter_digests = [
        _digest_from_record(
            record,
            base_path=context.base_path,
            error_prefix="E_LINEAGE_PARAM",
        )
        for record in param_records
    ]
    param_result = compute_parameter_hash(parameter_digests)
    if param_result.parameter_hash != context.parameter_hash:
        raise err(
            "E_LINEAGE_RECOMPUTE_MISMATCH",
            "parameter_hash mismatch during recomputation",
        )

    manifest_records = _load_jsonl_records(mapping["fingerprint_artifacts.jsonl"])
    if not manifest_records:
        raise err("E_LINEAGE_RECOMPUTE_MISSING", "fingerprint_artifacts.jsonl is empty")

    manifest_digests = [
        _digest_from_record(
            record,
            base_path=context.base_path,
            error_prefix="E_LINEAGE_MANIFEST",
        )
        for record in manifest_records
    ]

    git_hex = None
    manifest_path = mapping.get("MANIFEST.json")
    if manifest_path and manifest_path.exists():
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        git_hex = manifest_payload.get("git_commit_hex")
    if git_hex is None and context.upstream_manifest is not None:
        git_hex = context.upstream_manifest.get("git_commit_hex")
    if not git_hex:
        raise err("E_LINEAGE_RECOMPUTE_MISSING", "git_commit_hex unavailable for manifest recomputation")
    try:
        git_bytes = bytes.fromhex(git_hex)
    except ValueError as exc:
        raise err("E_LINEAGE_RECOMPUTE_MISSING", "git_commit_hex is not valid hex") from exc

    try:
        manifest_result = compute_manifest_fingerprint(
            manifest_digests,
            git_commit_raw=git_bytes,
            parameter_hash_bytes=bytes.fromhex(context.parameter_hash),
        )
    except ValueError as exc:
        raise err("E_LINEAGE_RECOMPUTE_MISSING", "parameter_hash is not valid hex") from exc

    if manifest_result.manifest_fingerprint != context.manifest_fingerprint:
        raise err(
            "E_LINEAGE_RECOMPUTE_MISMATCH",
            "manifest_fingerprint mismatch during recomputation",
        )


def _load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _resolve_artifact_path(raw_path: str, base_path: Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (base_path / raw_path).resolve()
        if not candidate.exists():
            repo_root = get_repo_root()
            candidate = (repo_root / raw_path).resolve()
    return candidate


def _validate_dataset_schema(dataset_id: str, frame: pd.DataFrame | None) -> None:
    if frame is None:
        return
    entry = _dictionary_entry(dataset_id)
    schema_ref = entry.get("schema_ref")
    if not schema_ref:
        return
    validator = _schema_validator(schema_ref)
    records = frame.to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if isinstance(value, np.ndarray):
                record[key] = value.tolist()
    try:
        validator.validate(records)
    except ValidationError as exc:
        raise err("E_SCHEMA_INVALID", f"{dataset_id} schema violation: {exc.message}") from exc


def _dictionary_entry(dataset_id: str) -> Mapping[str, Any]:
    dictionary = _load_dataset_dictionary()
    for section in dictionary.values():
        if not isinstance(section, Mapping):
            continue
        entry = section.get(dataset_id)
        if isinstance(entry, Mapping):
            return entry
    return {}


def _load_dataset_dictionary() -> Mapping[str, object]:
    global _DATASET_DICTIONARY
    if _DATASET_DICTIONARY is None:
        _DATASET_DICTIONARY = load_dictionary()
    return _DATASET_DICTIONARY


def _schema_validator(schema_ref: str) -> Draft202012Validator:
    file_name, pointer = _split_schema_ref(schema_ref)
    cache_key = (file_name, pointer)
    validator = _SCHEMA_CACHE.get(cache_key)
    if validator is not None:
        return validator
    document = _schema_document(file_name)
    schema_node = _resolve_pointer(document, pointer)
    normalized = _normalize_schema(schema_node, document)
    validator = Draft202012Validator(normalized)
    _SCHEMA_CACHE[cache_key] = validator
    return validator


def _schema_version(schema_ref: str) -> str:
    file_name, pointer = _split_schema_ref(schema_ref)
    cache_key = (file_name, pointer)
    cached = _SCHEMA_VERSION_CACHE.get(cache_key)
    if cached is not None:
        return cached
    document = _schema_document(file_name)
    node = _resolve_pointer(document, pointer)
    version: str | None = None
    if isinstance(node, Mapping):
        raw_id = node.get("$id") or node.get("version")
        if isinstance(raw_id, str) and raw_id:
            version = raw_id
    if version is None:
        version = schema_ref
    _SCHEMA_VERSION_CACHE[cache_key] = version
    return version


def _split_schema_ref(schema_ref: str) -> tuple[str, str]:
    if "#" in schema_ref:
        file_name, pointer = schema_ref.split("#", 1)
    else:
        file_name, pointer = schema_ref, ""
    pointer = pointer or ""
    if pointer and not pointer.startswith("/") and pointer != "#":
        pointer = f"/{pointer}"
    if pointer == "#":
        pointer = ""
    return file_name, pointer


def _schema_document(file_name: str) -> Dict[str, Any]:
    document = _SCHEMA_DOCS.get(file_name)
    if document is not None:
        return document
    path = _schema_file_path(file_name)
    if not path.exists():
        raise err("E_SCHEMA_INVALID", f"schema file '{file_name}' not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    _SCHEMA_DOCS[file_name] = payload
    return payload


def _schema_file_path(file_name: str) -> Path:
    repo_root = get_repo_root()
    if file_name == "schemas.1A.yaml":
        return (
            repo_root
            / "docs"
            / "model_spec"
            / "data-engine"
            / "layer-1"
            / "specs"
            / "contracts"
            / "1A"
            / "schemas.1A.yaml"
        )
    if file_name == "schemas.layer1.yaml":
        return repo_root / "contracts" / "schemas" / "layer1" / "schemas.layer1.yaml"
    if file_name.startswith("l1/"):
        alt = (repo_root / "contracts" / "schemas" / file_name).resolve()
        if alt.exists():
            return alt
    candidate = (repo_root / file_name).resolve()
    if candidate.exists():
        return candidate
    return (repo_root / "contracts" / "schemas" / file_name).resolve()


def _resolve_pointer(document: Mapping[str, Any], pointer: str) -> Any:
    if not pointer or pointer == "#":
        return document
    parts = pointer.lstrip("/").split("/")
    node: Any = document
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, Mapping):
            node = node.get(part)
        else:
            raise err("E_SCHEMA_INVALID", f"schema pointer '{pointer}' invalid at '{part}'")
        if node is None:
            raise err("E_SCHEMA_INVALID", f"schema pointer '{pointer}' missing segment '{part}'")
    return node


def _normalize_schema(schema_node: Any, document: Mapping[str, Any]) -> Any:
    if isinstance(schema_node, Mapping) and schema_node.get("type") == "table":
        return _table_to_json_schema(schema_node, document)
    return schema_node


def _table_to_json_schema(table_def: Mapping[str, Any], document: Mapping[str, Any]) -> Mapping[str, Any]:
    properties: Dict[str, Any] = {}
    required: list[str] = []
    for column_def in table_def.get("columns", []):
        name = column_def.get("name")
        if not name:
            continue
        column_schema = _column_to_schema(column_def)
        if column_def.get("nullable", False):
            column_schema = {"anyOf": [column_schema, {"type": "null"}]}
        else:
            required.append(name)
        properties[name] = column_schema

    return {
        "$schema": document.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "$defs": document.get("$defs", {}),
        "type": "array",
        "items": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


def _column_to_schema(column_def: Mapping[str, Any]) -> Mapping[str, Any]:
    if "$ref" in column_def:
        return {"$ref": column_def["$ref"]}

    column_type = column_def.get("type")
    if column_type in (None, "any"):
        schema: Dict[str, Any] = {}
    elif column_type in {"int32", "int64", "uint32", "uint64", "integer"}:
        schema = {"type": "integer"}
    elif column_type in {"float32", "float64", "number", "double"}:
        schema = {"type": "number"}
    elif column_type == "boolean":
        schema = {"type": "boolean"}
    else:
        schema = {"type": column_type}

    for key in ("pattern", "minimum", "maximum", "enum", "const"):
        if key in column_def:
            schema[key] = column_def[key]
    return schema


def _load_iso_codes() -> set[str] | None:
    global _ISO_CODES
    if _ISO_CODES is not None:
        return _ISO_CODES
    try:
        entry = _dictionary_entry("iso_canonical")
    except Exception:
        _ISO_CODES = None
        return _ISO_CODES
    path_str = entry.get("path")
    if not path_str:
        _ISO_CODES = None
        return _ISO_CODES
    path = Path(path_str)
    if not path.is_absolute():
        path = (get_repo_root() / path).resolve()
    if not path.exists():
        _ISO_CODES = None
        return _ISO_CODES
    try:
        data = pd.read_parquet(path)
    except Exception:
        _ISO_CODES = None
        return _ISO_CODES
    if "country_iso" not in data.columns:
        _ISO_CODES = None
        return _ISO_CODES
    _ISO_CODES = {str(code).upper() for code in data["country_iso"].dropna().unique()}
    return _ISO_CODES


def _validate_trace_identity(context: S9DeterministicContext, trace_df: pd.DataFrame) -> None:
    if trace_df.empty:
        return
    for column, value in (
        ("seed", context.seed),
        ("parameter_hash", context.parameter_hash),
        ("run_id", context.run_id),
        ("manifest_fingerprint", context.manifest_fingerprint),
    ):
        if column in trace_df.columns:
            series = trace_df[column]
            if series.notna().any():
                _assert_column_equals(trace_df[series.notna()], column, value, c.TRACE_LOG_ID)


def _validate_audit_identity(context: S9DeterministicContext, audit_df: pd.DataFrame) -> None:
    if audit_df.empty:
        return
    for column, value in (
        ("seed", context.seed),
        ("parameter_hash", context.parameter_hash),
        ("manifest_fingerprint", context.manifest_fingerprint),
        ("run_id", context.run_id),
    ):
        if column in audit_df.columns:
            _assert_column_equals(audit_df, column, value, c.AUDIT_LOG_ID)


def _build_rng_accounting(
    *,
    context: S9DeterministicContext,
    rng_events: Mapping[str, pd.DataFrame],
    trace_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    record_failure: Callable[[S0Error], None],
) -> Mapping[str, object]:
    families: Dict[str, Dict[str, object]] = {}
    audit_present = not audit_df.empty

    for dataset_id in c.RNG_EVENT_DATASETS:
        events_df = rng_events.get(dataset_id, pd.DataFrame())
        try:
            families[dataset_id] = _account_for_family(
                context=context,
                dataset_id=dataset_id,
                events_df=events_df,
                trace_df=trace_df,
                audit_present=audit_present,
            )
        except S0Error as exc:
            record_failure(exc)
            families[dataset_id] = {
                "events_total": int(len(events_df)),
                "draws_total_u128_dec": "0",
                "blocks_total_u64": 0,
                "nonconsuming_events": 0,
                "trace_rows_total": 0,
                "trace_totals": {},
                "audit_present": audit_present,
                "coverage_ok": False,
                "budget": _rng_budget_descriptor(dataset_id),
            }

    return {
        "runs": [
            {
                "seed": context.seed,
                "parameter_hash": context.parameter_hash,
                "run_id": context.run_id,
            }
        ],
        "families": families,
    }


def _rng_budget_descriptor(dataset_id: str) -> Mapping[str, object]:
    descriptor = _RNG_BUDGET_TABLE.get(dataset_id)
    if descriptor is None:
        return {"type": "unspecified"}
    return dict(descriptor)


def _account_for_family(
    *,
    context: S9DeterministicContext,
    dataset_id: str,
    events_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    audit_present: bool,
) -> Dict[str, object]:
    df = events_df.copy() if isinstance(events_df, pd.DataFrame) else pd.DataFrame()
    budget_descriptor = _rng_budget_descriptor(dataset_id)

    if df.empty:
        return {
            "events_total": 0,
            "draws_total_u128_dec": "0",
            "blocks_total_u64": 0,
            "nonconsuming_events": 0,
            "trace_rows_total": 0,
            "trace_totals": {},
            "audit_present": audit_present,
            "coverage_ok": trace_df.empty,
            "budget": budget_descriptor,
        }

    for column, expected in (
        ("seed", context.seed),
        ("parameter_hash", context.parameter_hash),
        ("run_id", context.run_id),
        ("manifest_fingerprint", context.manifest_fingerprint),
    ):
        if column in df.columns:
            _assert_column_equals(df, column, expected, dataset_id)

    required_columns = [
        "module",
        "substream_label",
        "blocks",
        "draws",
        "rng_counter_before_lo",
        "rng_counter_before_hi",
        "rng_counter_after_lo",
        "rng_counter_after_hi",
    ]
    for column in required_columns:
        if column not in df.columns:
            raise err("E_SCHEMA_INVALID", f"{dataset_id} missing column '{column}'")

    group_totals: Dict[tuple[str, str], Dict[str, int]] = {}

    events_total = int(len(df))
    blocks_total = 0
    draws_total = 0
    nonconsuming_events = 0

    for row in df.itertuples(index=False):
        module = str(getattr(row, "module"))
        substream_label = str(getattr(row, "substream_label"))
        group_key = (module, substream_label)
        if group_key not in group_totals:
            group_totals[group_key] = {
                "events_total": 0,
                "blocks_total": 0,
                "draws_total": 0,
            }

        try:
            blocks = int(getattr(row, "blocks"))
        except (TypeError, ValueError) as exc:
            raise err("E_RNG_BUDGET_VIOLATION", f"{dataset_id} invalid blocks value") from exc
        try:
            draws = _parse_u128(getattr(row, "draws"))
        except ValueError as exc:
            raise err("E_RNG_BUDGET_VIOLATION", f"{dataset_id} invalid draws value") from exc

        try:
            before = _combine_counter(
                getattr(row, "rng_counter_before_lo"),
                getattr(row, "rng_counter_before_hi"),
            )
            after = _combine_counter(
                getattr(row, "rng_counter_after_lo"),
                getattr(row, "rng_counter_after_hi"),
            )
        except (TypeError, ValueError) as exc:
            raise err("E_SCHEMA_INVALID", f"{dataset_id} invalid counter values") from exc

        if after - before != blocks:
            raise err(
                "E_RNG_COUNTER_MISMATCH",
                f"{dataset_id} counter delta mismatch (expected {after - before}, observed {blocks})",
            )

        _verify_rng_budgets(dataset_id, row, blocks, draws)

        blocks_total += blocks
        draws_total += draws
        if blocks == 0:
            nonconsuming_events += 1
        group_totals[group_key]["events_total"] += 1
        group_totals[group_key]["blocks_total"] += blocks
        group_totals[group_key]["draws_total"] += draws

    if "module" not in trace_df.columns or "substream_label" not in trace_df.columns:
        raise err("E_SCHEMA_INVALID", "rng_trace_log missing module or substream_label columns")

    trace_rows_total = 0
    trace_events_total = 0
    trace_blocks_total = 0
    trace_draws_total = 0

    for (module, substream_label), stats in group_totals.items():
        trace_subset = trace_df[
            (trace_df["module"].astype(str) == module)
            & (trace_df["substream_label"].astype(str) == substream_label)
        ]
        group_trace_rows = int(len(trace_subset))
        if stats["events_total"] > 0 and group_trace_rows != stats["events_total"]:
            raise err(
                "E_TRACE_COVERAGE_MISSING",
                f"{dataset_id} trace rows {group_trace_rows} do not match events {stats['events_total']} for module '{module}' ({substream_label})",
            )
        final_trace_row = _select_trace_row(trace_subset)
        if final_trace_row is None:
            if stats["events_total"] > 0:
                raise err(
                    "E_TRACE_COVERAGE_MISSING",
                    f"{dataset_id} events present but no trace coverage for module '{module}' ({substream_label})",
                )
            continue
        group_trace_events_total = int(final_trace_row["events_total"])
        group_trace_blocks_total = int(final_trace_row["blocks_total"])
        group_trace_draws_total = _parse_u128(final_trace_row["draws_total"])
        if (
            group_trace_events_total != stats["events_total"]
            or group_trace_blocks_total != stats["blocks_total"]
            or group_trace_draws_total != stats["draws_total"]
        ):
            raise err(
                "E_TRACE_TOTALS_MISMATCH",
                f"{dataset_id} trace totals mismatch for module '{module}' ({substream_label}) "
                f"(trace events={group_trace_events_total}, blocks={group_trace_blocks_total}, draws={group_trace_draws_total}; "
                f"observed events={stats['events_total']}, blocks={stats['blocks_total']}, draws={stats['draws_total']})",
            )
        trace_rows_total += group_trace_rows
        trace_events_total += group_trace_events_total
        trace_blocks_total += group_trace_blocks_total
        trace_draws_total += group_trace_draws_total

    if events_total > 0 and trace_rows_total != events_total:
        raise err(
            "E_TRACE_COVERAGE_MISSING",
            f"{dataset_id} trace rows {trace_rows_total} do not match events {events_total}",
        )
    coverage_ok = True if events_total > 0 else trace_df.empty
    trace_totals: Dict[str, object] = {
        "events_total": trace_events_total,
        "draws_total_u128_dec": str(trace_draws_total),
        "blocks_total_u64": trace_blocks_total,
    }

    return {
        "events_total": events_total,
        "draws_total_u128_dec": str(draws_total),
        "blocks_total_u64": blocks_total,
        "nonconsuming_events": nonconsuming_events,
        "trace_rows_total": trace_rows_total,
        "trace_totals": trace_totals,
        "audit_present": audit_present,
        "coverage_ok": coverage_ok,
        "budget": budget_descriptor,
    }


def _select_trace_row(trace_subset: pd.DataFrame) -> pd.Series | None:
    if trace_subset.empty:
        return None
    if not {
        "rng_counter_after_lo",
        "rng_counter_after_hi",
    }.issubset(trace_subset.columns):
        raise err("E_SCHEMA_INVALID", "rng_trace_log missing counter columns")
    working = trace_subset.copy()
    working["_after"] = [
        _combine_counter(lo, hi)
        for lo, hi in zip(
            working["rng_counter_after_lo"],
            working["rng_counter_after_hi"],
            strict=False,
        )
    ]
    sort_columns = ["_after"]
    if "events_total" in working.columns:
        try:
            working["_events_total"] = working["events_total"].astype(int)
        except Exception:
            working["_events_total"] = pd.to_numeric(
                working["events_total"], errors="coerce"
            ).fillna(0).astype(int)
        sort_columns = ["_events_total", "_after"]
    working = working.sort_values(sort_columns, ignore_index=False)
    idx = working.index[-1]
    return working.loc[idx]


def _parse_u128(value: Any) -> int:
    if isinstance(value, (int, np.integer)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    if not text.isdigit():
        raise ValueError(f"invalid u128 value '{value}'")
    return int(text)


def _combine_counter(lo: Any, hi: Any) -> int:
    return (int(hi) << 64) + int(lo)


def _verify_rng_budgets(dataset_id: str, row: Any, blocks: int, draws: int) -> None:
    if dataset_id in c.NON_CONSUMING_FAMILIES:
        if blocks != 0 or draws != 0:
            raise err(
                "E_NONCONSUMING_CHANGED_COUNTERS",
                f"{dataset_id} must not consume RNG counters",
            )
        return

    if dataset_id == c.EVENT_FAMILY_GUMBEL_KEY:
        if blocks != 1 or draws != 1:
            raise err(
                "E_RNG_BUDGET_VIOLATION",
                f"{dataset_id} must consume exactly one uniform",
            )
        return

    if dataset_id == c.EVENT_FAMILY_HURDLE_BERNOULLI:
        deterministic = getattr(row, "deterministic", None)
        u_value = getattr(row, "u", None)
        if deterministic is True:
            if blocks != 0 or draws != 0:
                raise err(
                    "E_NONCONSUMING_CHANGED_COUNTERS",
                    "deterministic hurdle draw must not consume RNG",
                )
            if u_value not in (None, "") and not pd.isna(u_value):
                raise err(
                    "E_RNG_BUDGET_VIOLATION",
                    "deterministic hurdle draw must have null uniform",
                )
        elif deterministic is False:
            if blocks != 1 or draws != 1:
                raise err(
                    "E_RNG_BUDGET_VIOLATION",
                    "stochastic hurdle draw must consume exactly one uniform",
                )
            if pd.isna(u_value) or u_value is None:
                raise err(
                    "E_RNG_BUDGET_VIOLATION",
                    "stochastic hurdle draw missing uniform sample",
                )
        else:
            raise err(
                "E_SCHEMA_INVALID",
                "hurdle_bernoulli event missing deterministic flag",
            )
        return

    if dataset_id in (
        c.EVENT_FAMILY_GAMMA_COMPONENT,
        c.EVENT_FAMILY_POISSON_COMPONENT,
        c.EVENT_FAMILY_DIRICHLET_GAMMA_VECTOR,
    ):
        if blocks <= 0 or draws <= 0:
            raise err(
                "E_RNG_BUDGET_VIOLATION",
                f"{dataset_id} must consume at least one block and one uniform",
            )
        return

    if blocks < 0 or draws < 0:
        raise err(
            "E_RNG_BUDGET_VIOLATION",
            f"{dataset_id} produced negative RNG consumption values",
        )
