"""Validation battery for Segment 1B S9."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from . import constants as c
from .contexts import S9DeterministicContext, S9ValidationResult
from .exceptions import ErrorContext, err

KEY_COLUMNS = ("merchant_id", "legal_country_iso", "site_order")

_RNG_FAMILY_CONFIG: Mapping[str, Mapping[str, Any]] = {
    c.RNG_EVENT_SITE_TILE_ASSIGN: {
        "id": "site_tile_assign",
        "module": "1B.S5.assigner",
        "substream": "site_tile_assign",
        "expected_blocks": 1,
        "expected_draws": 1,
        "coverage": "exactly_one",
    },
    c.RNG_EVENT_IN_CELL_JITTER: {
        "id": "in_cell_jitter",
        "module": "1B.S6.jitter",
        "substream": "in_cell_jitter",
        "expected_blocks": 1,
        "expected_draws": 2,
        "coverage": "at_least_one",
    },
}


def validate_outputs(context: S9DeterministicContext) -> S9ValidationResult:
    """Execute the governed acceptance tests."""

    s7_df = context.surfaces.s7_site_synthesis.to_pandas()
    s8_df = context.surfaces.site_locations.to_pandas()

    failures: list[ErrorContext] = []

    parity_ok, parity_failures = _validate_row_parity(s7_df, s8_df)
    failures.extend(parity_failures)

    schema_failures = _validate_schema(s8_df)
    failures.extend(schema_failures)

    identity_failures = _validate_identity(context, parity_ok)
    failures.extend(identity_failures)

    writer_failures, writer_stats = _validate_writer_sort(s8_df)
    failures.extend(writer_failures)

    rng_results, rng_failures, audit_status = _validate_rng(context, s7_df)
    failures.extend(rng_failures)

    summary = _build_summary(
        context=context,
        s7_df=s7_df,
        s8_df=s8_df,
        parity_ok=parity_ok,
        writer_stats=writer_stats,
        rng_results=rng_results,
        audit_status=audit_status,
    )

    rng_accounting = {
        "families": list(rng_results.values()),
        "audit": audit_status,
    }

    passed = not failures

    return S9ValidationResult(
        passed=passed,
        failures=tuple(failures),
        summary=summary,
        rng_accounting=rng_accounting,
    )


def _build_summary(
    *,
    context: S9DeterministicContext,
    s7_df: pd.DataFrame,
    s8_df: pd.DataFrame,
    parity_ok: bool,
    writer_stats: Mapping[str, int],
    rng_results: Mapping[str, Mapping[str, Any]],
    audit_status: Mapping[str, Any],
) -> Mapping[str, Any]:
    rows_s7 = int(len(s7_df))
    rows_s8 = int(len(s8_df))

    by_country = {}
    s7_counts = Counter(s7_df.get("legal_country_iso", []))
    s8_counts = Counter(s8_df.get("legal_country_iso", []))
    for iso in sorted(set(s7_counts) | set(s8_counts)):
        s7_val = int(s7_counts.get(iso, 0))
        s8_val = int(s8_counts.get(iso, 0))
        by_country[iso] = {
            "rows_s7": s7_val,
            "rows_s8": s8_val,
            "parity_ok": s7_val == s8_val,
        }

    egress_path = ""
    egress_files = context.source_paths.get(c.DATASET_SITE_LOCATIONS)
    if egress_files:
        egress_path = str(egress_files[0].parent.as_posix())

    rng_summary = {
        "families": {
            family["id"]: {
                key: value
                for key, value in family.items()
                if key
                not in {
                    "id",
                    "module",
                    "substream",
                }
            }
            for family in rng_results.values()
        }
    }
    rng_summary["audit"] = dict(audit_status)

    return {
        "identity": {
            "seed": context.seed,
            "parameter_hash": context.parameter_hash,
            "manifest_fingerprint": context.manifest_fingerprint,
            "run_id": context.run_id,
        },
        "sizes": {
            "rows_s7": rows_s7,
            "rows_s8": rows_s8,
            "parity_ok": parity_ok and rows_s7 == rows_s8,
        },
        "egress": {
            "path": egress_path,
            "writer_sort_violations": int(writer_stats.get("writer_sort_violations", 0)),
            "path_embed_mismatches": int(writer_stats.get("path_embed_mismatches", 0)),
        },
        "rng": rng_summary,
        "by_country": by_country,
    }


def _validate_row_parity(
    s7_df: pd.DataFrame,
    s8_df: pd.DataFrame,
) -> tuple[bool, Sequence[ErrorContext]]:
    failures: list[ErrorContext] = []

    keys7 = _key_series(s7_df)
    keys8 = _key_series(s8_df)

    missing = keys7.difference(keys8)
    extra = keys8.difference(keys7)

    if missing:
        failures.append(err("E901_ROW_MISSING", f"{len(missing)} S7 keys missing in S8").context)
    if extra:
        failures.append(err("E902_ROW_EXTRA", f"{len(extra)} unexpected S8 keys").context)

    duplicate_s8 = _duplicate_count(s8_df)
    if duplicate_s8:
        failures.append(err("E903_DUP_KEY", f"{duplicate_s8} duplicate primary keys in S8").context)

    parity_ok = not missing and not extra and duplicate_s8 == 0
    return parity_ok, failures


def _validate_schema(s8_df: pd.DataFrame) -> Sequence[ErrorContext]:
    failures: list[ErrorContext] = []

    expected_columns = {"merchant_id", "legal_country_iso", "site_order", "lon_deg", "lat_deg"}
    actual_columns = set(s8_df.columns)
    if actual_columns != expected_columns:
        failures.append(
            err(
                "E904_EGRESS_SCHEMA_VIOLATION",
                f"site_locations columns {sorted(actual_columns)} do not match expected {sorted(expected_columns)}",
            ).context
        )

    if not s8_df.empty:
        if not np.issubdtype(s8_df["merchant_id"].dtype, np.integer):
            if not s8_df["merchant_id"].apply(lambda v: isinstance(v, (int, np.integer))).all():
                failures.append(err("E904_EGRESS_SCHEMA_VIOLATION", "merchant_id must be integers").context)

        if not np.issubdtype(s8_df["site_order"].dtype, np.integer):
            if not s8_df["site_order"].apply(lambda v: isinstance(v, (int, np.integer))).all():
                failures.append(err("E904_EGRESS_SCHEMA_VIOLATION", "site_order must be integers").context)

        if (s8_df["site_order"] < 1).any():
            failures.append(err("E904_EGRESS_SCHEMA_VIOLATION", "site_order must be >= 1").context)

        if not s8_df["legal_country_iso"].apply(lambda v: isinstance(v, str) and v.isupper() and len(v) == 2).all():
            failures.append(err("E904_EGRESS_SCHEMA_VIOLATION", "legal_country_iso must be uppercase ISO2 codes").context)

        lon_valid = s8_df["lon_deg"].apply(lambda v: isinstance(v, (int, float, np.floating, np.integer)) and -180 <= float(v) <= 180)
        lat_valid = s8_df["lat_deg"].apply(lambda v: isinstance(v, (int, float, np.floating, np.integer)) and -90 <= float(v) <= 90)
        if not lon_valid.all():
            failures.append(err("E904_EGRESS_SCHEMA_VIOLATION", "lon_deg outside [-180, 180]").context)
        if not lat_valid.all():
            failures.append(err("E904_EGRESS_SCHEMA_VIOLATION", "lat_deg outside [-90, 90]").context)

    return failures


def _validate_identity(context: S9DeterministicContext, parity_ok: bool) -> Sequence[ErrorContext]:
    failures: list[ErrorContext] = []

    def _check_tokens(dataset_id: str, expected: Mapping[str, str], allow_extra: bool) -> None:
        files = context.source_paths.get(dataset_id, ())
        for file_path in files:
            parts = {segment.split("=", 1)[0]: segment.split("=", 1)[1] for segment in file_path.parts if "=" in segment}
            for key, value in expected.items():
                observed = parts.get(key)
                if observed != value:
                    failures.append(
                        err(
                            "E905_PARTITION_OR_IDENTITY",
                            f"{dataset_id} path '{file_path}' missing partition {key}={value}",
                        ).context
                    )
            if not allow_extra and "parameter_hash" in parts and "parameter_hash" not in expected:
                failures.append(
                    err(
                        "E912_IDENTITY_COHERENCE",
                        f"{dataset_id} path '{file_path}' unexpectedly includes parameter_hash",
                    ).context
                )

    expected_s7 = {
        "seed": str(context.seed),
        "fingerprint": context.manifest_fingerprint,
        "parameter_hash": context.parameter_hash,
    }
    expected_s8 = {
        "seed": str(context.seed),
        "fingerprint": context.manifest_fingerprint,
    }

    _check_tokens(c.DATASET_S7_SITE_SYNTHESIS, expected_s7, allow_extra=True)
    _check_tokens(c.DATASET_SITE_LOCATIONS, expected_s8, allow_extra=False)

    if parity_ok:
        s8_paths = context.source_paths.get(c.DATASET_SITE_LOCATIONS, ())
        s7_paths = context.source_paths.get(c.DATASET_S7_SITE_SYNTHESIS, ())
        if s8_paths and s7_paths:
            s8_parent = s8_paths[0].parent
            s7_parent = s7_paths[0].parent
            if s8_parent.parts[-1] != s7_parent.parts[-2]:
                failures.append(
                    err(
                        "E912_IDENTITY_COHERENCE",
                        "S7 and S8 partitions do not share the same fingerprint identity",
                    ).context
                )

    return failures


def _validate_writer_sort(s8_df: pd.DataFrame) -> tuple[Sequence[ErrorContext], Mapping[str, int]]:
    if s8_df.empty:
        return (), {"writer_sort_violations": 0, "path_embed_mismatches": 0}

    ordered = s8_df.sort_values(list(KEY_COLUMNS), kind="mergesort")
    matches = ordered[list(KEY_COLUMNS)].to_numpy()
    actual = s8_df[list(KEY_COLUMNS)].to_numpy()
    is_sorted = np.array_equal(matches, actual)

    failures: list[ErrorContext] = []
    writer_sort_violations = 0
    if not is_sorted:
        writer_sort_violations = int(
            (matches != actual).any(axis=1).sum()
        )
        failures.append(err("E906_WRITER_SORT_VIOLATION", "site_locations not sorted by primary key").context)

    return failures, {"writer_sort_violations": writer_sort_violations, "path_embed_mismatches": 0}


def _validate_rng(
    context: S9DeterministicContext,
    s7_df: pd.DataFrame,
) -> tuple[Mapping[str, Mapping[str, Any]], Sequence[ErrorContext], Mapping[str, Any]]:
    failures: list[ErrorContext] = []
    results: dict[str, Mapping[str, Any]] = {}

    s7_keys = set(_key_series(s7_df))

    trace_df = context.surfaces.rng_trace_log if context.surfaces.rng_trace_log is not None else pd.DataFrame()
    if not trace_df.empty:
        trace_df = trace_df.copy()
        trace_df["module"] = trace_df["module"].astype(str)
        trace_df["substream_label"] = trace_df["substream_label"].astype(str)

    audit_df = context.surfaces.rng_audit_log if context.surfaces.rng_audit_log is not None else pd.DataFrame()
    audit_status, audit_failures = _validate_audit_log(context, audit_df)
    failures.extend(audit_failures)

    for dataset_id, config in _RNG_FAMILY_CONFIG.items():
        frame = context.surfaces.rng_events.get(dataset_id, pd.DataFrame())
        frame = frame.copy()
        if not frame.empty:
            # Avoid narrowing uint64 merchant identifiers into signed int64 values
            # (large IDs overflow and break coverage reconciliation).
            frame["merchant_id"] = frame["merchant_id"].map(int)
            frame["legal_country_iso"] = frame["legal_country_iso"].astype(str)
            frame["site_order"] = frame["site_order"].astype(int)

        try:
            result = _evaluate_rng_family(
                dataset_id=dataset_id,
                frame=frame,
                config=config,
                s7_keys=s7_keys,
                trace_df=trace_df,
            )
            results[config["id"]] = result
        except Exception as exc:  # pragma: no cover - defensive
            failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", str(exc)).context)
        else:
            if not result.get("coverage_ok", False) or not result.get("trace_reconciled", False):
                failures.append(
                    err(
                        "E907_RNG_BUDGET_OR_COUNTERS",
                        f"{config['id']} coverage_ok={result.get('coverage_ok')} trace_reconciled={result.get('trace_reconciled')}",
                    ).context
                )

    return results, failures, audit_status


def _evaluate_rng_family(
    *,
    dataset_id: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    s7_keys: set[tuple[int, str, int]],
    trace_df: pd.DataFrame,
) -> Mapping[str, Any]:
    expected_blocks = int(config["expected_blocks"])
    expected_draws = int(config["expected_draws"])

    coverage_type = config["coverage"]
    key_counts = Counter(_key_series(frame))

    coverage_ok = True
    envelope_failures = 0

    if coverage_type == "exactly_one":
        for key in s7_keys:
            count = key_counts.get(key, 0)
            if count != 1:
                coverage_ok = False
        events_missing = sum(1 for key in s7_keys if key_counts.get(key, 0) == 0)
        events_extra = sum(max(0, count - 1) for count in key_counts.values())
        stray_events = sum(count for key, count in key_counts.items() if key not in s7_keys)
        if stray_events:
            events_extra += stray_events
            coverage_ok = False
        coverage_descriptor = {
            "sites_total": len(s7_keys),
            "events_missing": events_missing,
            "events_extra": events_extra,
        }
    else:
        sites_with_event = sum(1 for key in s7_keys if key_counts.get(key, 0) >= 1)
        coverage_ok = sites_with_event == len(s7_keys)
        stray_events = sum(count for key, count in key_counts.items() if key not in s7_keys)
        if stray_events:
            coverage_ok = False
        coverage_descriptor = {
            "sites_total": len(s7_keys),
            "sites_with_≥1_event": sites_with_event,
            "sites_with_0_event": len(s7_keys) - sites_with_event,
            "events_extra": stray_events,
        }

    blocks_total = 0
    draws_total = 0

    for _, row in frame.iterrows():
        try:
            blocks = int(row.get("blocks", 0))
            draws = int(str(row.get("draws", "0")))
        except (TypeError, ValueError):
            blocks = 0
            draws = 0
            envelope_failures += 1

        try:
            before = _combine_counter(row.get("rng_counter_before_lo"), row.get("rng_counter_before_hi"))
            after = _combine_counter(row.get("rng_counter_after_lo"), row.get("rng_counter_after_hi"))
        except (TypeError, ValueError):
            before = 0
            after = blocks
            envelope_failures += 1
        else:
            if after - before != blocks:
                envelope_failures += 1

        if blocks != expected_blocks or draws != expected_draws:
            envelope_failures += 1

        blocks_total += blocks
        draws_total += draws

    events_total = int(len(frame))

    trace_reconciled = False
    trace_totals: Mapping[str, Any] = {}

    if events_total == 0:
        trace_reconciled = coverage_ok
    else:
        mask = (trace_df["module"] == config["module"]) & (
            trace_df["substream_label"] == config["substream"]
        )
        subset = trace_df.loc[mask]
        if subset.empty:
            trace_reconciled = False
        else:
            required_cols = {
                "rng_counter_after_lo",
                "events_total",
                "blocks_total",
                "draws_total",
            }
            if not required_cols.issubset(set(subset.columns)):
                trace_reconciled = False
            else:
                final_row = subset.iloc[-1]
                trace_events = int(final_row.get("events_total", 0))
                trace_blocks = int(final_row.get("blocks_total", 0))
                trace_draws = _parse_u128(final_row.get("draws_total", 0))
                trace_reconciled = (
                    trace_events == events_total
                    and trace_blocks == blocks_total
                    and trace_draws == draws_total
                )
                trace_totals = {
                    "events_total": trace_events,
                    "blocks_total": trace_blocks,
                    "draws_total": str(trace_draws),
                }

    if events_total > 0 and envelope_failures == 0 and coverage_ok and not trace_totals:
        trace_reconciled = False

    result = {
        "id": config["id"],
        "module": config["module"],
        "substream_label": config["substream"],
        "coverage": coverage_descriptor,
        "events_total": events_total,
        "blocks_total": blocks_total,
        "draws_total": str(draws_total),
        "trace_totals": trace_totals,
        "trace_reconciled": trace_reconciled,
        "coverage_ok": coverage_ok,
        "envelope_failures": envelope_failures,
        "budget_per_event": {"blocks": expected_blocks, "draws": str(expected_draws)},
    }
    return result


def _key_series(df: pd.DataFrame) -> set[tuple[int, str, int]]:
    if df.empty:
        return set()
    return {
        (int(row[KEY_COLUMNS[0]]), str(row[KEY_COLUMNS[1]]), int(row[KEY_COLUMNS[2]]))
        for _, row in df[list(KEY_COLUMNS)].iterrows()
    }


def _duplicate_count(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    duplicates = df.duplicated(subset=list(KEY_COLUMNS), keep=False)
    return int(duplicates.sum())


def _combine_counter(lo: Any, hi: Any) -> int:
    return (int(hi) << 64) + int(lo)


def _parse_u128(value: Any) -> int:
    if isinstance(value, (int, np.integer)):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    if not text.isdigit():
        raise ValueError(f"invalid u128 value '{value}'")
    return int(text)


def _validate_audit_log(
    context: S9DeterministicContext,
    audit_df: pd.DataFrame,
) -> tuple[Mapping[str, Any], Sequence[ErrorContext]]:
    status: dict[str, Any] = {
        "records_total": int(len(audit_df)) if audit_df is not None else 0,
        "identity_ok": False,
    }
    failures: list[ErrorContext] = []

    if audit_df is None or audit_df.empty:
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log missing for run").context)
        return status, failures

    if len(audit_df) != 1:
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log must contain exactly one record").context)
        return status, failures

    record = audit_df.iloc[0]

    try:
        seed_value = int(record.get("seed"))
    except (TypeError, ValueError):
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log seed is invalid").context)
        return status, failures

    expected_seed = int(context.seed)
    if seed_value != expected_seed:
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log seed mismatch").context)

    run_id = str(record.get("run_id", ""))
    if run_id != context.run_id:
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log run_id mismatch").context)

    parameter_hash = str(record.get("parameter_hash", "")).lower()
    if parameter_hash != context.parameter_hash.lower():
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log parameter_hash mismatch").context)

    fingerprint = str(record.get("manifest_fingerprint", "")).lower()
    if fingerprint != context.manifest_fingerprint.lower():
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log manifest_fingerprint mismatch").context)

    algorithm = str(record.get("algorithm", ""))
    if algorithm and algorithm != "philox2x64-10":
        failures.append(err("E907_RNG_BUDGET_OR_COUNTERS", "rng_audit_log algorithm mismatch").context)

    status.update(
        {
            "identity_ok": not failures,
            "run_id": run_id,
            "algorithm": algorithm or None,
        }
    )

    return status, failures


__all__ = ["validate_outputs"]
