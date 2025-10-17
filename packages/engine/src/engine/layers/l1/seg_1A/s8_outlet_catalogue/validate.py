"""Validation utilities for S8 outlet catalogue outputs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Mapping, Tuple

import pandas as pd

from ..shared.dictionary import load_dictionary, resolve_dataset_path
from .constants import (
    EVENT_FAMILY_SEQUENCE_FINALIZE,
    EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW,
)

__all__ = [
    "S8ValidationError",
    "validate_outputs",
]

_COUNT_BUCKETS = ("b1", "b2_3", "b4_10", "b11_25", "b26_plus")
_DOMAIN_BUCKETS = ("b1", "b2", "b3_5", "b6_10", "b11_plus")


class S8ValidationError(RuntimeError):
    """Raised when S8 validation fails."""


def validate_outputs(
    *,
    base_path: Path,
    parameter_hash: str,
    manifest_fingerprint: str,
    seed: int,
    run_id: str,
    catalogue_path: Path,
    event_paths: Mapping[str, Path],
    dictionary: Mapping[str, object] | None = None,
) -> Tuple[Mapping[str, object], Mapping[str, object]]:
    """Run the S8 validation battery and return `(metrics, rng_accounting)` payloads."""

    dictionary = dictionary or load_dictionary()
    catalogue_path = catalogue_path.expanduser().resolve()
    if not catalogue_path.exists():
        raise S8ValidationError(f"outlet_catalogue missing at '{catalogue_path}'")

    _assert_partition_tokens(
        catalogue_path=catalogue_path,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
    )

    frame = pd.read_parquet(catalogue_path)
    _validate_columns(frame)
    _validate_lineage(frame=frame, seed=seed, manifest_fingerprint=manifest_fingerprint)
    _validate_pk(frame)

    metrics = _compute_metrics(
        frame=frame,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        base_path=base_path,
        dictionary=dictionary,
    )

    rng_accounting = _compute_rng_accounting(
        base_path=base_path,
        parameter_hash=parameter_hash,
        run_id=run_id,
        seed=seed,
        manifest_fingerprint=manifest_fingerprint,
        event_paths=event_paths,
        dictionary=dictionary,
    )

    metrics["pk_hash_hex"] = rng_accounting.get("pk_hash_hex", metrics.get("pk_hash_hex", ""))
    metrics.setdefault("rows_total", int(frame.shape[0]))

    return metrics, rng_accounting


def _assert_partition_tokens(
    *,
    catalogue_path: Path,
    seed: int,
    manifest_fingerprint: str,
) -> None:
    parents = {part.name for part in catalogue_path.parents}
    if f"seed={seed}" not in parents:
        raise S8ValidationError(
            f"catalogue partition missing expected seed token 'seed={seed}'"
        )
    if f"fingerprint={manifest_fingerprint}" not in parents:
        raise S8ValidationError(
            f"catalogue partition missing expected fingerprint token "
            f"'fingerprint={manifest_fingerprint}'"
        )


def _validate_columns(frame: pd.DataFrame) -> None:
    required = {
        "manifest_fingerprint",
        "merchant_id",
        "site_id",
        "home_country_iso",
        "legal_country_iso",
        "single_vs_multi_flag",
        "raw_nb_outlet_draw",
        "final_country_outlet_count",
        "site_order",
        "global_seed",
    }
    missing = required - set(frame.columns)
    if missing:
        raise S8ValidationError(f"outlet_catalogue missing columns {sorted(missing)}")


def _validate_lineage(
    *,
    frame: pd.DataFrame,
    seed: int,
    manifest_fingerprint: str,
) -> None:
    if not (frame["manifest_fingerprint"] == manifest_fingerprint).all():
        raise S8ValidationError("manifest_fingerprint column mismatch detected")
    if not (frame["global_seed"] == int(seed)).all():
        raise S8ValidationError("global_seed column mismatch detected")
    if not frame["legal_country_iso"].apply(lambda iso: _is_valid_iso(str(iso))).all():
        raise S8ValidationError("invalid ISO codes present in outlet_catalogue")


def _validate_pk(frame: pd.DataFrame) -> None:
    if frame.duplicated(["merchant_id", "legal_country_iso", "site_order"]).any():
        raise S8ValidationError("duplicate primary keys detected in outlet_catalogue")


def _compute_metrics(
    *,
    frame: pd.DataFrame,
    parameter_hash: str,
    seed: int,
    run_id: str,
    base_path: Path,
    dictionary: Mapping[str, object],
) -> Dict[str, object]:
    metrics: Dict[str, object] = {}
    metrics["rows_total"] = int(frame.shape[0])
    metrics["rows_total_by_country"] = (
        frame.groupby("legal_country_iso")
        .size()
        .sort_index()
        .astype(int)
        .to_dict()
    )
    metrics["merchants_in_egress"] = int(frame["merchant_id"].nunique())
    metrics["blocks_with_rows"] = int(frame[["merchant_id", "legal_country_iso"]].drop_duplicates().shape[0])

    hist_counts = {bucket: 0 for bucket in _COUNT_BUCKETS}
    domain_hist = {bucket: 0 for bucket in _DOMAIN_BUCKETS}
    sum_mismatch = 0
    membership_miss = 0
    iso_fk_violation = 0

    pk_digest = hashlib.sha256()

    candidate_lookup = _load_candidate_lookup(
        base_path=base_path,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )

    for (merchant_id, iso), block in frame.groupby(["merchant_id", "legal_country_iso"], sort=False):
        expected = int(block["final_country_outlet_count"].iloc[0])
        actual = block.shape[0]
        if expected != actual:
            sum_mismatch += 1
        _increment_bucket(hist_counts, _COUNT_BUCKETS, actual)

        for order, site_id in zip(block["site_order"], block["site_id"], strict=False):
            if int(order) < 1:
                raise S8ValidationError(
                    f"site_order must start at 1 (merchant={merchant_id}, iso={iso})"
                )
            expected_id = f"{int(order):06d}"
            if str(site_id) != expected_id:
                raise S8ValidationError(
                    f"site_id mismatch for merchant={merchant_id}, iso={iso}, site_order={order}"
                )
            pk_digest.update(f"{int(merchant_id)}|{iso}|{int(order)}".encode("utf-8"))

        if iso not in candidate_lookup.get(int(merchant_id), {iso}):
            membership_miss += 1
        if not _is_valid_iso(str(iso)):
            iso_fk_violation += 1

    metrics["hist_final_country_outlet_count"] = hist_counts

    domain_sizes = (
        frame.groupby("merchant_id")["legal_country_iso"].nunique().astype(int).to_dict()
    )
    for size in domain_sizes.values():
        _increment_bucket(domain_hist, _DOMAIN_BUCKETS, size)
    metrics["domain_size_distribution"] = domain_hist
    metrics["sum_law_mismatch_count"] = sum_mismatch
    metrics["s3_membership_miss_count"] = membership_miss
    metrics["iso_fk_violation_count"] = iso_fk_violation
    metrics["pk_hash_hex"] = pk_digest.hexdigest()

    try:
        overflow_path = resolve_dataset_path(
            EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW,
            base_path=base_path,
            template_args={
                "seed": seed,
                "parameter_hash": parameter_hash,
                "run_id": run_id,
            },
            dictionary=dictionary,
        )
    except Exception:  # pragma: no cover - dataset optional
        overflow_path = None
    overflow_ids = _collect_overflow_merchants(overflow_path)
    metrics["overflow_merchant_ids"] = overflow_ids
    metrics["overflow_merchant_count"] = len(overflow_ids)

    return metrics


def _load_candidate_lookup(
    *,
    base_path: Path,
    parameter_hash: str,
    dictionary: Mapping[str, object],
) -> Mapping[int, set[str]]:
    candidate_path = resolve_dataset_path(
        "s3_candidate_set",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    lookup: Dict[int, set[str]] = defaultdict(set)
    if not candidate_path.exists():
        return lookup
    candidate_frame = pd.read_parquet(candidate_path, columns=["merchant_id", "country_iso"])
    for row in candidate_frame.itertuples(index=False):
        lookup[int(row.merchant_id)].add(str(row.country_iso).upper())
    return lookup


def _increment_bucket(target: Dict[str, int], buckets: Tuple[str, ...], value: int) -> None:
    if buckets == _DOMAIN_BUCKETS:
        if value == 1:
            bucket = "b1"
        elif value == 2:
            bucket = "b2"
        elif 3 <= value <= 5:
            bucket = "b3_5"
        elif 6 <= value <= 10:
            bucket = "b6_10"
        else:
            bucket = "b11_plus"
    else:
        if value == 1:
            bucket = "b1"
        elif 2 <= value <= 3:
            bucket = "b2_3"
        elif 4 <= value <= 10:
            bucket = "b4_10"
        elif 11 <= value <= 25:
            bucket = "b11_25"
        else:
            bucket = "b26_plus"
    target[bucket] = target.get(bucket, 0) + 1


def _is_valid_iso(code: str) -> bool:
    return len(code) == 2 and code.isalpha() and code.isupper()


def _collect_overflow_merchants(path: Path | None) -> Tuple[int, ...]:
    if path is None or not path.exists():
        return tuple()
    ids: set[int] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            ids.add(int(record.get("merchant_id", 0)))
    return tuple(sorted(ids))


def _compute_rng_accounting(
    *,
    base_path: Path,
    parameter_hash: str,
    run_id: str,
    seed: int,
    manifest_fingerprint: str,
    event_paths: Mapping[str, Path],
    dictionary: Mapping[str, object],
) -> Dict[str, object]:
    sequence_path = event_paths.get(EVENT_FAMILY_SEQUENCE_FINALIZE)
    overflow_path = event_paths.get(EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW)
    trace_path = event_paths.get("rng_trace_log")

    sequence_events = _count_events(sequence_path)
    overflow_events = _count_events(overflow_path)

    trace_events_delta = sequence_events + overflow_events

    audit_path = resolve_dataset_path(
        "rng_audit_log",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )

    payload: Dict[str, object] = {
        "sequence_finalize_events": sequence_events,
        "site_sequence_overflow_events": overflow_events,
        "trace_events_total_delta": trace_events_delta,
        "trace_draws_total_delta": 0,
        "trace_blocks_total_delta": 0,
        "audit_present": audit_path.exists(),
        "manifest_fingerprint": manifest_fingerprint,
        "pk_hash_hex": "",
    }

    if trace_path is not None and trace_path.exists():
        payload["trace_path"] = trace_path.as_posix()
    return payload


def _count_events(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count
