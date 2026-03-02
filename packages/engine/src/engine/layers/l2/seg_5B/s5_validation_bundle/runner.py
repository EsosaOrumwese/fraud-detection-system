"""S5 validation bundle & HashGate for Segment 5B (lean path)."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import (
    find_dataset_entry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l2.seg_5B.s0_gate.runner import (
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _sealed_inputs_digest,
)

try:  # pragma: no cover - optional dependency for fast parquet metadata
    import pyarrow.parquet as pq
except Exception:  # noqa: BLE001
    pq = None


MODULE_NAME = "5B.s5_validation_bundle"
SEGMENT = "5B"
STATE = "S5"

DATASET_S0_GATE = "s0_gate_receipt_5B"
DATASET_SEALED_INPUTS = "sealed_inputs_5B"
DATASET_TIME_GRID = "s1_time_grid_5B"
DATASET_S3_COUNTS = "s3_bucket_counts_5B"
DATASET_S4_EVENTS = "arrival_events_5B"
DATASET_S4_SUMMARY = "s4_arrival_summary_5B"
DATASET_VALIDATION_POLICY = "validation_policy_5B"
DATASET_BUNDLE_POLICY = "bundle_layout_policy_5B"
DATASET_SITE_LOCATIONS = "site_locations"
DATASET_EDGE_CATALOGUE = "edge_catalogue_3B"
DATASET_RNG_TRACE = "rng_trace_log"
DATASET_BUNDLE = "validation_bundle_5B"
DATASET_BUNDLE_INDEX = "validation_bundle_index_5B"
DATASET_REPORT = "validation_report_5B"
DATASET_ISSUES = "validation_issue_table_5B"
DATASET_FLAG = "validation_passed_flag_5B"
DATASET_RUN_REPORT = "segment_state_runs"

REQUIRED_RNG_FAMILIES = [
    ("5B.S2", "latent_vector"),
    ("5B.S3", "bucket_count"),
    ("5B.S4", "arrival_time_jitter"),
    ("5B.S4", "arrival_site_pick"),
    ("5B.S4", "arrival_edge_pick"),
]


@dataclass(frozen=True)
class S5Result:
    run_id: str
    manifest_fingerprint: str
    bundle_root: Path
    index_path: Path
    report_path: Path
    issues_path: Path
    flag_path: Optional[Path]
    run_report_path: Path


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str, *args: object) -> None:
        if args:
            message = message % args
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(self, total: Optional[int], logger, label: str, min_interval_seconds: float = 2.0) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0
        self._min_interval = float(min_interval_seconds)

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < self._min_interval and not (
            self._total is not None and self._processed >= self._total
        ):
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        if self._total and self._total > 0:
            remaining = max(self._total - self._processed, 0)
            eta = remaining / rate if rate > 0 else 0.0
            self._logger.info(
                "%s %s/%s (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                self._label,
                self._processed,
                self._total,
                elapsed,
                rate,
                eta,
            )
        else:
            self._logger.info(
                "%s processed=%s (elapsed=%.2fs, rate=%.2f/s)",
                self._label,
                self._processed,
                elapsed,
                rate,
            )


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _canonical_index_payload(payload: dict) -> dict:
    """Normalize volatile fields so replay comparisons are semantic, not bytewise."""
    normalized = dict(payload)
    normalized.pop("generated_utc", None)
    entries = normalized.get("entries")
    if isinstance(entries, list):
        normalized["entries"] = sorted(entries, key=lambda item: str(item.get("path", "")))
    return normalized


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(schema, schema_layer2, "schemas.layer2.yaml#")
    return normalize_nullable_schema(schema)


def _validate_payload(
    schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str, payload: object
) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(str(errors[0]), [])


def _resolve_parquet_files(root: Path) -> list[Path]:
    if "*" in str(root) or "?" in str(root):
        matches = sorted(root.parent.glob(root.name))
        if not matches:
            raise InputResolutionError(f"No parquet files matched {root}")
        return matches
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _resolve_jsonl_files(root: Path) -> list[Path]:
    if "*" in str(root) or "?" in str(root):
        matches = sorted(root.parent.glob(root.name))
        if not matches:
            raise InputResolutionError(f"No jsonl files matched {root}")
        return matches
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing jsonl directory: {root}")
    paths = sorted(root.rglob("*.jsonl"))
    if not paths:
        raise InputResolutionError(f"No jsonl files found under {root}")
    return paths


def _discover_seeds(entry: dict, run_paths: RunPaths, logger) -> list[int]:
    path_template = str(entry.get("path") or "")
    marker = "seed={seed}"
    if marker not in path_template:
        logger.info("S5: seed discovery skipped (path template has no seed token)")
        return []
    prefix = path_template.split(marker, 1)[0]
    prefix_path = run_paths.run_root / prefix
    if not prefix_path.exists():
        logger.warning("S5: seed discovery path missing: %s", prefix_path)
        return []
    seeds: list[int] = []
    for item in sorted(prefix_path.glob("seed=*")):
        seed_text = item.name.split("seed=")[-1]
        if seed_text.isdigit():
            seeds.append(int(seed_text))
    seeds = sorted(set(seeds))
    if seeds:
        logger.info("S5: discovered seeds=%s under %s", seeds, prefix_path)
    return seeds


def _parse_rfc3339(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _parse_local_time(value: str, zone: ZoneInfo) -> datetime:
    text = value.strip()
    # Local-wall contract: local fields are wall-clock values; trailing UTC markers
    # are treated as legacy lexical markers, not UTC semantics.
    if text.endswith("Z"):
        text = text[:-1]
    if text.endswith("+00:00"):
        text = text[:-6]
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone)
    return dt.astimezone(zone)


def _build_transition_windows(tzid: str, utc_min: datetime, utc_max: datetime) -> list[tuple[datetime, datetime]]:
    try:
        tz = ZoneInfo(tzid)
    except Exception:  # noqa: BLE001
        return []
    probe_start = utc_min - timedelta(days=2)
    probe_end = utc_max + timedelta(days=2)
    cur = probe_start
    prev_offset: Optional[int] = None
    transitions: list[datetime] = []
    while cur <= probe_end:
        off = int(cur.astimezone(tz).utcoffset().total_seconds())
        if prev_offset is not None and off != prev_offset:
            transitions.append(cur)
        prev_offset = off
        cur += timedelta(hours=1)
    return [(t - timedelta(hours=24), t + timedelta(hours=24)) for t in transitions]


def _dst_window_support(
    rows: list[dict],
    *,
    material_window_floor: int,
    min_material_windows: int,
    min_material_total_support: int,
) -> dict:
    if not rows:
        return {
            "dst_window_count": 0,
            "dst_windows_with_exposure": 0,
            "dst_windows_material_count": 0,
            "dst_window_support_min": 0,
            "dst_window_support_material_min": 0,
            "dst_window_support_material_total": 0,
            "dst_window_material_floor": int(material_window_floor),
            "dst_window_material_windows_threshold": int(min_material_windows),
            "dst_window_material_total_support_threshold": int(min_material_total_support),
            "dst_window_insufficient_power": False,
        }

    utc_values: list[datetime] = []
    tzids: set[str] = set()
    for row in rows:
        tzid = row.get("tzid_primary")
        ts_utc = row.get("ts_utc")
        if tzid and ts_utc:
            tzids.add(str(tzid))
            utc_values.append(_parse_rfc3339(str(ts_utc)))
    if not utc_values or not tzids:
        return {
            "dst_window_count": 0,
            "dst_windows_with_exposure": 0,
            "dst_windows_material_count": 0,
            "dst_window_support_min": 0,
            "dst_window_support_material_min": 0,
            "dst_window_support_material_total": 0,
            "dst_window_material_floor": int(material_window_floor),
            "dst_window_material_windows_threshold": int(min_material_windows),
            "dst_window_material_total_support_threshold": int(min_material_total_support),
            "dst_window_insufficient_power": False,
        }

    utc_min = min(utc_values)
    utc_max = max(utc_values)
    windows_by_tz = {tzid: _build_transition_windows(tzid, utc_min, utc_max) for tzid in sorted(tzids)}
    support: dict[str, int] = {}
    for row in rows:
        tzid = row.get("tzid_primary")
        ts_utc = row.get("ts_utc")
        if not tzid or not ts_utc:
            continue
        parsed = _parse_rfc3339(str(ts_utc))
        windows = windows_by_tz.get(str(tzid), [])
        for idx, (ws, we) in enumerate(windows):
            if ws <= parsed <= we:
                key = f"{tzid}#w{idx+1}"
                support[key] = support.get(key, 0) + 1

    supports = list(support.values())
    material_supports = [v for v in supports if v >= int(material_window_floor)]
    material_total = int(sum(material_supports)) if material_supports else 0
    insufficient = (
        len(material_supports) < int(min_material_windows)
        or material_total < int(min_material_total_support)
    )
    return {
        "dst_window_count": int(sum(len(w) for w in windows_by_tz.values())),
        "dst_windows_with_exposure": int(len(support)),
        "dst_windows_material_count": int(len(material_supports)),
        "dst_window_support_min": int(min(supports)) if supports else 0,
        "dst_window_support_material_min": int(min(material_supports)) if material_supports else 0,
        "dst_window_support_material_total": material_total,
        "dst_window_material_floor": int(material_window_floor),
        "dst_window_material_windows_threshold": int(min_material_windows),
        "dst_window_material_total_support_threshold": int(min_material_total_support),
        "dst_window_insufficient_power": bool(insufficient),
    }


def _dst_window_hour_bin_mae_pp(rows: list[dict], *, material_window_floor: int) -> dict:
    if not rows:
        return {"dst_window_hour_bin_mae_pp": None, "dst_windows_material_count": 0}

    utc_values: list[datetime] = []
    tzids: set[str] = set()
    for row in rows:
        tzid = row.get("tzid_primary")
        ts_utc = row.get("ts_utc")
        if tzid and ts_utc:
            tzids.add(str(tzid))
            utc_values.append(_parse_rfc3339(str(ts_utc)))
    if not utc_values or not tzids:
        return {"dst_window_hour_bin_mae_pp": None, "dst_windows_material_count": 0}

    utc_min = min(utc_values)
    utc_max = max(utc_values)
    windows_by_tz = {tzid: _build_transition_windows(tzid, utc_min, utc_max) for tzid in sorted(tzids)}
    per_window: dict[str, dict[str, list[int] | int]] = {}
    for row in rows:
        tzid = row.get("tzid_primary")
        ts_utc = row.get("ts_utc")
        ts_local = row.get("ts_local_primary")
        if not tzid or not ts_utc or not ts_local:
            continue
        try:
            zone = ZoneInfo(str(tzid))
            utc_dt = _parse_rfc3339(str(ts_utc))
            expected_local = utc_dt.astimezone(zone)
            actual_local = _parse_local_time(str(ts_local), zone)
        except Exception:  # noqa: BLE001
            continue
        for idx, (ws, we) in enumerate(windows_by_tz.get(str(tzid), [])):
            if ws <= utc_dt <= we:
                key = f"{tzid}#w{idx+1}"
                slot = per_window.get(key)
                if slot is None:
                    slot = {"support": 0, "expected": [0] * 24, "actual": [0] * 24}
                    per_window[key] = slot
                slot["support"] = int(slot["support"]) + 1
                slot["expected"][int(expected_local.hour)] += 1
                slot["actual"][int(actual_local.hour)] += 1

    maes: list[float] = []
    for slot in per_window.values():
        support = int(slot["support"])
        if support < int(material_window_floor):
            continue
        diffs = [
            abs((slot["actual"][h] / support) - (slot["expected"][h] / support))
            for h in range(24)
        ]
        maes.append((sum(diffs) / 24.0) * 100.0)

    return {
        "dst_window_hour_bin_mae_pp": float(sum(maes) / len(maes)) if maes else None,
        "dst_windows_material_count": int(len(maes)),
    }


def _observed_weekend_share(rows: list[dict]) -> Optional[float]:
    if not rows:
        return None
    weekend = 0
    valid = 0
    for row in rows:
        ts_utc = row.get("ts_utc")
        if not ts_utc:
            continue
        try:
            ts = _parse_rfc3339(str(ts_utc))
        except Exception:  # noqa: BLE001
            continue
        valid += 1
        if ts.weekday() >= 5:
            weekend += 1
    if valid <= 0:
        return None
    return float(weekend) / float(valid)


def _expected_weekend_share_from_s3_sample(
    rows: list[dict], bucket_maps: dict[str, dict[int, tuple[datetime, datetime]]]
) -> Optional[float]:
    if not rows:
        return None
    weekend_weight = 0.0
    total_weight = 0.0
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "")
        bucket_index_raw = row.get("bucket_index")
        count_raw = row.get("count_N")
        if scenario_id not in bucket_maps or bucket_index_raw is None or count_raw is None:
            continue
        try:
            bucket_index = int(bucket_index_raw)
            count_n = float(count_raw)
        except Exception:  # noqa: BLE001
            continue
        if count_n <= 0:
            continue
        start_end = bucket_maps[scenario_id].get(bucket_index)
        if start_end is None:
            continue
        start_utc, _ = start_end
        total_weight += count_n
        if start_utc.weekday() >= 5:
            weekend_weight += count_n
    if total_weight <= 0.0:
        return None
    return float(weekend_weight) / float(total_weight)


def _residual_std_from_s3_sample(rows: list[dict]) -> Optional[float]:
    if not rows:
        return None
    residuals: list[float] = []
    for row in rows:
        n_raw = row.get("count_N")
        lam_raw = row.get("lambda_realised")
        if n_raw is None or lam_raw is None:
            continue
        try:
            n = float(n_raw)
            lam = float(lam_raw)
        except Exception:  # noqa: BLE001
            continue
        if not (lam > 0.0):
            continue
        residuals.append((n - lam) / ((lam + 1.0e-9) ** 0.5))
    if len(residuals) < 2:
        return None
    mean = sum(residuals) / float(len(residuals))
    var = sum((val - mean) ** 2 for val in residuals) / float(len(residuals))
    return float(var**0.5)


def _parquet_total_rows(paths: list[Path], logger, label: str) -> int:
    tracker = _ProgressTracker(len(paths), logger, f"S5: count {label} files")
    total = 0
    for path in paths:
        if pq is not None:
            total += int(pq.ParquetFile(path).metadata.num_rows)
        else:
            total += int(pl.read_parquet(path, columns=[]).height)
        tracker.update(1)
    return total


def _sum_arrival_summary(paths: list[Path], logger) -> tuple[int, int, int]:
    tracker = _ProgressTracker(len(paths), logger, "S5: count arrival_summary files")
    total = 0
    total_physical = 0
    total_virtual = 0
    for path in paths:
        df = pl.read_parquet(path, columns=["count_N", "count_physical", "count_virtual"])
        metrics = df.select(
            pl.sum("count_N").alias("total"),
            pl.sum("count_physical").alias("physical"),
            pl.sum("count_virtual").alias("virtual"),
        )
        total += int(metrics["total"][0] or 0)
        total_physical += int(metrics["physical"][0] or 0)
        total_virtual += int(metrics["virtual"][0] or 0)
        tracker.update(1)
    return total, total_physical, total_virtual


def _sample_paths(paths: list[Path], max_files: int) -> list[Path]:
    if max_files <= 0 or not paths:
        return []
    if len(paths) <= max_files:
        return sorted(paths)
    pairs = []
    for path in paths:
        digest = hashlib.sha256(str(path).encode("utf-8")).digest()
        pairs.append((int.from_bytes(digest[:8], "big"), path))
    pairs.sort(key=lambda item: item[0])
    return [pair[1] for pair in pairs[:max_files]]


def _sample_rows(
    paths: list[Path],
    columns: list[str],
    sample_target: int,
    rows_per_file: int,
    logger,
    label: str,
) -> list[dict]:
    if sample_target <= 0 or not paths:
        return []
    # Keep sample volume bounded but spread across a broad deterministic file set.
    # This improves DST-window support robustness without inflating memory/runtime.
    min_rows_per_file = 128
    max_files = max(1, min(len(paths), max(1, sample_target // min_rows_per_file)))
    sample_paths = _sample_paths(paths, max_files)
    effective_rows_per_file = max(
        1,
        min(
            max(1, int(rows_per_file)),
            (int(sample_target) + len(sample_paths) - 1) // len(sample_paths),
        ),
    )
    logger.info(
        "S5: sample %s plan target=%d files=%d rows_per_file=%d",
        label,
        int(sample_target),
        len(sample_paths),
        int(effective_rows_per_file),
    )
    tracker = _ProgressTracker(len(sample_paths), logger, f"S5: sample {label} files")
    rows: list[dict] = []
    for path in sample_paths:
        if pq is not None:
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(batch_size=effective_rows_per_file, columns=columns):
                rows.extend(pl.from_arrow(batch).iter_rows(named=True))
                break
        else:
            rows.extend(pl.read_parquet(path, columns=columns).head(effective_rows_per_file).iter_rows(named=True))
        tracker.update(1)
        if len(rows) >= sample_target:
            break
    if len(rows) > sample_target:
        rows = rows[:sample_target]
    logger.info("S5: sampled %d rows for %s", len(rows), label)
    return rows


def _bucket_map(grid_df: pl.DataFrame) -> dict[int, tuple[datetime, datetime]]:
    mapping: dict[int, tuple[datetime, datetime]] = {}
    for row in grid_df.iter_rows(named=True):
        bucket_index = int(row["bucket_index"])
        start = _parse_rfc3339(str(row["bucket_start_utc"]))
        end = _parse_rfc3339(str(row["bucket_end_utc"]))
        mapping[bucket_index] = (start, end)
    return mapping


def _load_policy(
    path: Optional[Path],
    schema_5b: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    logger,
) -> Optional[dict]:
    if path is None or not path.exists():
        logger.warning("S5: policy missing (%s); using defaults if available", anchor)
        return None
    payload = _load_yaml(path) if path.suffix.lower() in {".yaml", ".yml"} else _load_json(path)
    _validate_payload(schema_5b, schema_layer1, schema_layer2, anchor, payload)
    if not isinstance(payload, dict):
        raise ContractError(f"Policy payload is not a dict: {path}")
    return payload


def _coerce_float(value: object, default: float, *, min_value: Optional[float] = None) -> float:
    try:
        resolved = float(value)
    except Exception:  # noqa: BLE001
        resolved = float(default)
    if min_value is not None and resolved < float(min_value):
        return float(min_value)
    return float(resolved)


def _coerce_int(value: object, default: int, *, min_value: Optional[int] = None) -> int:
    try:
        resolved = int(value)
    except Exception:  # noqa: BLE001
        resolved = int(default)
    if min_value is not None and resolved < int(min_value):
        return int(min_value)
    return int(resolved)


def _topk_tz_share(rows: list[dict], *, k: int) -> Optional[float]:
    if not rows:
        return None
    counts: dict[str, int] = {}
    total = 0
    for row in rows:
        tzid = row.get("tzid_primary")
        if tzid is None:
            continue
        key = str(tzid)
        counts[key] = counts.get(key, 0) + 1
        total += 1
    if total <= 0:
        return None
    ranked = sorted(counts.values(), reverse=True)
    return float(sum(ranked[: max(1, int(k))])) / float(total)


def _check_time_windows(rows: list[dict], bucket_maps: dict[str, dict[int, tuple[datetime, datetime]]]) -> tuple[bool, dict]:
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "")
        bucket_index = row.get("bucket_index")
        ts_utc = row.get("ts_utc")
        if scenario_id not in bucket_maps or bucket_index is None or ts_utc is None:
            return False, {"detail": "missing bucket mapping", "scenario_id": scenario_id}
        start_end = bucket_maps[scenario_id].get(int(bucket_index))
        if start_end is None:
            return False, {"detail": "bucket_index missing from grid", "bucket_index": int(bucket_index)}
        start, end = start_end
        ts = _parse_rfc3339(str(ts_utc))
        if ts < start or ts >= end:
            return False, {"detail": "ts_utc outside bucket", "bucket_index": int(bucket_index), "ts_utc": str(ts_utc)}
    return True, {}


def _check_civil_time(rows: list[dict], max_mismatch_rate: float) -> tuple[bool, dict]:
    checked_rows = 0
    mismatch_rows = 0
    parse_error_rows = 0
    one_hour_shift_rows = 0
    first_issue: Optional[dict] = None

    for row in rows:
        checked_rows += 1
        tzid = row.get("tzid_primary")
        ts_utc = row.get("ts_utc")
        ts_local = row.get("ts_local_primary")
        if not tzid or not ts_utc or not ts_local:
            parse_error_rows += 1
            if first_issue is None:
                first_issue = {"detail": "missing tzid_primary/ts_local_primary/ts_utc"}
            continue
        try:
            zone = ZoneInfo(str(tzid))
            utc_dt = _parse_rfc3339(str(ts_utc))
            expected_local = utc_dt.astimezone(zone)
            actual_local = _parse_local_time(str(ts_local), zone)
            delta = abs((expected_local - actual_local).total_seconds())
        except Exception as exc:  # noqa: BLE001
            parse_error_rows += 1
            if first_issue is None:
                first_issue = {"detail": "local parse failed", "tzid": str(tzid), "error": str(exc)}
            continue
        if abs(abs(delta) - 3600.0) <= 1.0:
            one_hour_shift_rows += 1
        if delta > 1.0:
            mismatch_rows += 1
            if first_issue is None:
                first_issue = {"detail": "local time mismatch", "tzid": str(tzid), "delta_seconds": float(delta)}

    mismatch_rate = (float(mismatch_rows + parse_error_rows) / float(checked_rows)) if checked_rows > 0 else 0.0
    one_hour_shift_rate = (float(one_hour_shift_rows) / float(checked_rows)) if checked_rows > 0 else 0.0
    gate_ok = mismatch_rate <= float(max_mismatch_rate)
    detail = {
        "checked_rows": int(checked_rows),
        "mismatch_rows": int(mismatch_rows),
        "parse_error_rows": int(parse_error_rows),
        "one_hour_shift_rows": int(one_hour_shift_rows),
        "mismatch_rate": float(mismatch_rate),
        "one_hour_shift_rate": float(one_hour_shift_rate),
        "max_mismatch_rate": float(max_mismatch_rate),
    }
    if first_issue is not None:
        detail["first_issue"] = first_issue
    return gate_ok, detail


def _check_routing_membership(
    rows: list[dict],
    site_paths: list[Path],
    edge_paths: list[Path],
    logger,
) -> tuple[bool, dict]:
    physical_rows = [row for row in rows if not bool(row.get("is_virtual"))]
    site_ids = {str(row["site_id"]) for row in physical_rows if row.get("site_id") is not None}
    edge_ids = {str(row["edge_id"]) for row in physical_rows if row.get("edge_id") is not None}
    if not site_ids and not edge_ids:
        return True, {}

    if site_ids:
        scan = pl.scan_parquet([str(path) for path in site_paths])
        if "site_id" not in scan.collect_schema().names():
            logger.info("S5: site_locations missing site_id column; skipping site_id membership check")
        else:
            site_expr = pl.col("site_id").cast(pl.Utf8)
            found = set(
                scan.select(site_expr.alias("site_id"))
                .filter(site_expr.is_in(list(site_ids)))
                .collect()
                .get_column("site_id")
                .to_list()
            )
            missing = sorted(site_ids - found)
            if missing:
                logger.warning("S5: missing site_ids sample=%s", missing[:5])
                return False, {"detail": "missing site_id membership", "missing_count": len(missing)}

    if edge_ids:
        scan = pl.scan_parquet([str(path) for path in edge_paths])
        if "edge_id" not in scan.collect_schema().names():
            logger.warning("S5: edge_catalogue missing edge_id column; skipping edge_id check")
        else:
            edge_expr = pl.col("edge_id").cast(pl.Utf8)
            found = set(
                scan.select(edge_expr.alias("edge_id"))
                .filter(edge_expr.is_in(list(edge_ids)))
                .collect()
                .get_column("edge_id")
                .to_list()
            )
            missing = sorted(edge_ids - found)
            if missing:
                logger.warning("S5: missing edge_ids sample=%s", missing[:5])
                return False, {"detail": "missing edge_id membership", "missing_count": len(missing)}

    return True, {}


def _bundle_digest(bundle_root: Path, entries: list[dict]) -> str:
    hasher = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
        rel_path = entry.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            raise EngineFailure("F4", "S5_INDEX_BUILD_FAILED", STATE, MODULE_NAME, {"detail": "missing path"})
        file_path = bundle_root / rel_path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "S5_INDEX_BUILD_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"bundle file missing: {rel_path}"},
            )
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l2.seg_5B.s5_validation_bundle.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    run_paths: Optional[RunPaths] = None
    manifest_fingerprint: Optional[str] = None
    run_id_value: Optional[str] = None
    spec_version: str = ""
    run_report_output_path: Optional[Path] = None

    dictionary_5b: dict = {}
    schema_5b: dict = {}
    schema_layer2: dict = {}
    schema_layer1: dict = {}

    issues: list[dict] = []
    counts_match_s3 = False
    time_windows_ok = False
    civil_time_ok = False
    civil_time_gate_ok = False
    calibration_gate_ok = True
    routing_ok = False
    schema_ok = False
    schema_detail: dict = {}
    rng_accounting_ok = False
    bundle_integrity_ok = False
    calibration_eval_mode = "warn_only"

    n_parameter_hashes = 0
    n_scenarios = 0
    n_seeds = 0
    n_buckets_total = 0
    n_buckets_nonzero = 0
    n_arrivals_total = 0
    n_arrivals_physical = 0
    n_arrivals_virtual = 0
    have_summary_counts = False
    calibration_detail: dict = {}
    civil_gate_detail: dict = {}

    current_phase = "init"

    try:
        current_phase = "run_receipt"
        _, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        if not run_id_value:
            raise InputResolutionError("run_receipt missing run_id.")
        manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
        if not manifest_fingerprint:
            raise InputResolutionError("run_receipt missing manifest_fingerprint.")

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        logger.info("S5: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary_5b = load_dataset_dictionary(source, "5B")
        schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        logger.info(
            "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_path),
            str(schema_5b_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
        )

        logger.info(
            "S5: objective=validate 5B world + emit bundle/pass flag; gated inputs (S0-S4, rng_trace) -> outputs validation_bundle_5B/_passed.flag"
        )

        current_phase = "s0_receipts"
        tokens_mf = {"manifest_fingerprint": manifest_fingerprint}
        s0_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_S0_GATE).entry,
            run_paths,
            config.external_roots,
            tokens_mf,
        )
        sealed_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_SEALED_INPUTS).entry,
            run_paths,
            config.external_roots,
            tokens_mf,
        )
        s0_receipt = _load_json(s0_path)
        sealed_inputs = _load_json(sealed_path)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "validation/s0_gate_receipt_5B", s0_receipt)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "validation/sealed_inputs_5B", sealed_inputs)
        spec_version = str(s0_receipt.get("spec_version") or "")

        if isinstance(sealed_inputs, dict):
            sealed_rows = sealed_inputs.get("rows") or []
        else:
            sealed_rows = sealed_inputs
        computed_digest = _sealed_inputs_digest(sealed_rows)
        if computed_digest != s0_receipt.get("sealed_inputs_digest"):
            raise EngineFailure(
                "F4",
                "5B.S5.SEALED_INPUTS_DIGEST_MISMATCH",
                STATE,
                MODULE_NAME,
                {"computed": computed_digest, "sealed": s0_receipt.get("sealed_inputs_digest")},
            )

        scenario_set = s0_receipt.get("scenario_set") or []
        scenario_ids = [str(item) for item in scenario_set]
        n_scenarios = len(scenario_ids)
        if not scenario_ids:
            raise InputResolutionError("S5: scenario_set empty in s0_gate_receipt_5B.")

        policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_VALIDATION_POLICY).entry,
            run_paths,
            config.external_roots,
            {},
        )
        bundle_policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_BUNDLE_POLICY).entry,
            run_paths,
            config.external_roots,
            {},
        )
        validation_policy = _load_policy(
            policy_path, schema_5b, schema_layer1, schema_layer2, "config/validation_policy_5B", logger
        )
        bundle_policy = _load_policy(
            bundle_policy_path, schema_5b, schema_layer1, schema_layer2, "config/bundle_layout_policy_5B", logger
        )
        if bundle_policy:
            logger.info(
                "S5: bundle policy loaded policy_id=%s version=%s",
                bundle_policy.get("policy_id"),
                bundle_policy.get("version"),
            )
        failure_policy = (validation_policy or {}).get("failure_policy") or {}
        failure_mode = str(failure_policy.get("mode") or "fail_closed").strip().lower()
        max_warnings = int(failure_policy.get("max_warnings") or 0)
        civil_cfg = (validation_policy or {}).get("civil_time_gates") or {}
        calibration_cfg = (validation_policy or {}).get("calibration_sentinels") or {}
        env_override_enabled = str(os.environ.get("ENGINE_5B_S5_ENABLE_POLICY_ENV_OVERRIDE") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        civil_mismatch_limit = _coerce_float(civil_cfg.get("max_civil_mismatch_rate"), 0.005, min_value=0.0)
        one_hour_shift_limit = _coerce_float(civil_cfg.get("max_one_hour_shift_rate"), 0.001, min_value=0.0)
        dst_window_hour_bin_mae_pp_max = _coerce_float(
            civil_cfg.get("dst_window_hour_bin_mae_pp_max"), 1.5, min_value=0.0
        )
        dst_window_material_floor = _coerce_int(civil_cfg.get("dst_window_min_support"), 50, min_value=1)
        dst_window_min_material_windows = _coerce_int(
            civil_cfg.get("dst_window_min_exposed_windows"), 3, min_value=1
        )
        dst_window_min_total_support = _coerce_int(civil_cfg.get("dst_window_min_total_support"), 2000, min_value=1)

        if env_override_enabled:
            civil_mismatch_limit = _coerce_float(
                os.environ.get("ENGINE_5B_S5_MAX_CIVIL_MISMATCH_RATE", civil_mismatch_limit),
                civil_mismatch_limit,
                min_value=0.0,
            )
            one_hour_shift_limit = _coerce_float(
                os.environ.get("ENGINE_5B_S5_MAX_ONE_HOUR_SHIFT_RATE", one_hour_shift_limit),
                one_hour_shift_limit,
                min_value=0.0,
            )
            dst_window_hour_bin_mae_pp_max = _coerce_float(
                os.environ.get("ENGINE_5B_S5_DST_WINDOW_HOUR_BIN_MAE_PP_MAX", dst_window_hour_bin_mae_pp_max),
                dst_window_hour_bin_mae_pp_max,
                min_value=0.0,
            )
            dst_window_material_floor = _coerce_int(
                os.environ.get("ENGINE_5B_S5_DST_WINDOW_MIN_SUPPORT", dst_window_material_floor),
                dst_window_material_floor,
                min_value=1,
            )
            dst_window_min_material_windows = _coerce_int(
                os.environ.get("ENGINE_5B_S5_DST_WINDOW_MIN_EXPOSED_WINDOWS", dst_window_min_material_windows),
                dst_window_min_material_windows,
                min_value=1,
            )
            dst_window_min_total_support = _coerce_int(
                os.environ.get("ENGINE_5B_S5_DST_WINDOW_MIN_TOTAL_SUPPORT", dst_window_min_total_support),
                dst_window_min_total_support,
                min_value=1,
            )

        calibration_eval_mode = str(calibration_cfg.get("evaluation_mode") or "warn_only").strip().lower()
        if calibration_eval_mode not in {"warn_only", "enforce_b", "enforce_bplus"}:
            logger.warning("S5: unknown calibration evaluation_mode=%s; falling back to warn_only", calibration_eval_mode)
            calibration_eval_mode = "warn_only"
        calibration_min_sample_rows = _coerce_int(calibration_cfg.get("min_sample_rows"), 25000, min_value=1)
        top10_tz_share_max_b = _coerce_float(calibration_cfg.get("top10_tz_share_max_b"), 0.72, min_value=0.0)
        top10_tz_share_max_bplus = _coerce_float(
            calibration_cfg.get("top10_tz_share_max_bplus"), 0.62, min_value=0.0
        )
        virtual_share_min_b = _coerce_float(calibration_cfg.get("virtual_share_min_b"), 0.03, min_value=0.0)
        virtual_share_max_b = _coerce_float(calibration_cfg.get("virtual_share_max_b"), 0.08, min_value=0.0)
        virtual_share_min_bplus = _coerce_float(calibration_cfg.get("virtual_share_min_bplus"), 0.05, min_value=0.0)
        virtual_share_max_bplus = _coerce_float(calibration_cfg.get("virtual_share_max_bplus"), 0.12, min_value=0.0)
        weekend_delta_max_b = _coerce_float(
            calibration_cfg.get("weekend_share_delta_pp_max_b"), 0.20, min_value=0.0
        )
        weekend_delta_max_bplus = _coerce_float(
            calibration_cfg.get("weekend_share_delta_pp_max_bplus"), 0.10, min_value=0.0
        )
        residual_std_min_b = _coerce_float(calibration_cfg.get("residual_std_min_b"), 1.20, min_value=0.0)
        residual_std_max_b = _coerce_float(calibration_cfg.get("residual_std_max_b"), 1.60, min_value=0.0)
        residual_std_min_bplus = _coerce_float(calibration_cfg.get("residual_std_min_bplus"), 1.25, min_value=0.0)
        residual_std_max_bplus = _coerce_float(calibration_cfg.get("residual_std_max_bplus"), 1.50, min_value=0.0)
        logger.info(
            "S5: failure policy mode=%s max_warnings=%d env_override_enabled=%s civil_mismatch_limit=%.6f one_hour_shift_limit=%.6f dst_window_hour_bin_mae_pp_max=%.6f dst_window_material_floor=%d dst_window_min_exposed_windows=%d dst_window_min_total_support=%d calibration_eval_mode=%s calibration_min_sample_rows=%d",
            failure_mode,
            max_warnings,
            str(env_override_enabled).lower(),
            civil_mismatch_limit,
            one_hour_shift_limit,
            dst_window_hour_bin_mae_pp_max,
            dst_window_material_floor,
            dst_window_min_material_windows,
            dst_window_min_total_support,
            calibration_eval_mode,
            calibration_min_sample_rows,
        )

        current_phase = "upstream_pass"
        require_pass = (validation_policy or {}).get("require_upstream_pass") or {}
        required_segments = list(require_pass.get("layer1_required") or []) + list(
            require_pass.get("layer2_required") or []
        )
        upstream_segments = s0_receipt.get("upstream_segments") or {}
        missing_upstream = [
            seg for seg in required_segments if str(upstream_segments.get(seg, {}).get("status")) != "PASS"
        ]
        if missing_upstream:
            raise EngineFailure(
                "F4",
                "5B.S5.UPSTREAM_NOT_PASS",
                STATE,
                MODULE_NAME,
                {"missing": missing_upstream},
            )

        current_phase = "domain_discovery"
        s3_entry = find_dataset_entry(dictionary_5b, DATASET_S3_COUNTS).entry
        seed_list = _discover_seeds(s3_entry, run_paths, logger)
        if not seed_list:
            seed_fallback = int(receipt.get("seed") or 0)
            seed_list = [seed_fallback]
        n_seeds = len(seed_list)

        parameter_hashes: set[str] = set()
        total_expected = 0
        total_buckets = 0
        total_nonzero = 0
        s3_paths_for_sampling: list[Path] = []

        for seed in seed_list:
            for scenario_id in scenario_ids:
                tokens = {
                    "seed": str(seed),
                    "manifest_fingerprint": manifest_fingerprint,
                    "scenario_id": scenario_id,
                }
                s3_path = _resolve_dataset_path(s3_entry, run_paths, config.external_roots, tokens)
                if not s3_path.exists():
                    issues.append(
                        {
                            "manifest_fingerprint": manifest_fingerprint,
                            "seed": seed,
                            "scenario_id": scenario_id,
                            "issue_code": "S3_MISSING",
                            "severity": "ERROR",
                            "context": {"path": str(s3_path)},
                            "message": "s3_bucket_counts_5B missing",
                        }
                    )
                    raise InputResolutionError(f"Missing s3_bucket_counts_5B at {s3_path}")
                s3_paths = _resolve_parquet_files(s3_path)
                s3_paths_for_sampling.extend(s3_paths)
                scan = pl.scan_parquet([str(path) for path in s3_paths])
                if "count_N" not in scan.collect_schema().names():
                    raise ContractError("s3_bucket_counts_5B missing count_N column")
                metrics = scan.select(
                    pl.len().alias("rows_total"),
                    pl.sum("count_N").alias("rows_expected"),
                    (pl.col("count_N") > 0).sum().alias("rows_nonzero"),
                    pl.col("parameter_hash").unique().alias("parameter_hashes"),
                ).collect()
                total_buckets += int(metrics["rows_total"][0] or 0)
                total_expected += int(metrics["rows_expected"][0] or 0)
                total_nonzero += int(metrics["rows_nonzero"][0] or 0)
                for val in metrics["parameter_hashes"][0]:
                    parameter_hashes.add(str(val))
        s3_paths_for_sampling = list(dict.fromkeys(s3_paths_for_sampling))

        n_parameter_hashes = len(parameter_hashes)
        n_buckets_total = total_buckets
        n_buckets_nonzero = total_nonzero

        current_phase = "arrival_totals"
        s4_entry = find_dataset_entry(dictionary_5b, DATASET_S4_EVENTS).entry
        arrival_paths: list[Path] = []
        for seed in seed_list:
            for scenario_id in scenario_ids:
                tokens = {
                    "seed": str(seed),
                    "manifest_fingerprint": manifest_fingerprint,
                    "scenario_id": scenario_id,
                }
                arrival_root = _resolve_dataset_path(s4_entry, run_paths, config.external_roots, tokens)
                try:
                    arrival_paths.extend(_resolve_parquet_files(arrival_root))
                except InputResolutionError as exc:
                    issues.append(
                        {
                            "manifest_fingerprint": manifest_fingerprint,
                            "seed": seed,
                            "scenario_id": scenario_id,
                            "issue_code": "S4_MISSING",
                            "severity": "ERROR",
                            "context": {"path": str(arrival_root)},
                            "message": "arrival_events_5B missing",
                        }
                    )
                    raise exc

        n_arrivals_total = _parquet_total_rows(arrival_paths, logger, "arrival_events")
        counts_match_s3 = int(total_expected) == int(n_arrivals_total)
        logger.info(
            "S5: arrival totals (expected_from_s3=%d, observed_events=%d)",
            int(total_expected),
            int(n_arrivals_total),
        )
        if not counts_match_s3:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "ARRIVAL_COUNT_MISMATCH",
                    "severity": "ERROR",
                    "context": {
                        "expected_from_s3": int(total_expected),
                        "observed_events": int(n_arrivals_total),
                    },
                    "message": "Arrival counts do not match S3 bucket totals",
                }
            )

        summary_entry = find_dataset_entry(dictionary_5b, DATASET_S4_SUMMARY).entry
        summary_paths: list[Path] = []
        for seed in seed_list:
            for scenario_id in scenario_ids:
                tokens = {
                    "seed": str(seed),
                    "manifest_fingerprint": manifest_fingerprint,
                    "scenario_id": scenario_id,
                }
                summary_root = _resolve_dataset_path(summary_entry, run_paths, config.external_roots, tokens)
                if summary_root.exists():
                    summary_paths.extend(_resolve_parquet_files(summary_root))
        if summary_paths:
            summary_total, summary_physical, summary_virtual = _sum_arrival_summary(summary_paths, logger)
            have_summary_counts = True
            n_arrivals_physical = summary_physical
            n_arrivals_virtual = summary_virtual
            logger.info(
                "S5: arrival summary totals (total=%d, physical=%d, virtual=%d)",
                summary_total,
                summary_physical,
                summary_virtual,
            )
            if summary_total != n_arrivals_total:
                logger.warning(
                    "S5: arrival summary total differs from arrival events (summary=%d, events=%d)",
                    summary_total,
                    n_arrivals_total,
                )
        else:
            logger.info("S5: arrival summary missing; physical/virtual counts omitted")

        sample_target = (
            min(200000, max(calibration_min_sample_rows, int(n_arrivals_total * 0.005))) if n_arrivals_total > 0 else 0
        )
        rows_per_file = max(1, sample_target // max(1, min(20, len(arrival_paths))))
        sample_columns = [
            "manifest_fingerprint",
            "parameter_hash",
            "seed",
            "scenario_id",
            "merchant_id",
            "zone_representation",
            "bucket_index",
            "arrival_seq",
            "ts_utc",
            "tzid_primary",
            "ts_local_primary",
            "site_id",
            "edge_id",
            "is_virtual",
        ]
        sample_rows = _sample_rows(
            arrival_paths, sample_columns, sample_target, rows_per_file, logger, "arrival_events"
        )
        s3_sample_rows: list[dict] = []
        s3_sample_target = (
            min(200000, max(calibration_min_sample_rows, int(max(1, n_buckets_total) * 0.02)))
            if n_buckets_total > 0
            else 0
        )
        s3_rows_per_file = max(1, s3_sample_target // max(1, min(20, len(s3_paths_for_sampling))))
        s3_sample_columns = ["scenario_id", "bucket_index", "count_N"]
        if s3_sample_target > 0 and s3_paths_for_sampling:
            s3_has_lambda = False
            try:
                s3_schema = pl.scan_parquet([str(path) for path in s3_paths_for_sampling]).collect_schema()
                s3_has_lambda = "lambda_realised" in s3_schema.names()
            except Exception as exc:  # noqa: BLE001
                logger.warning("S5: unable to inspect s3 schema for calibration sentinels: %s", exc)
            if s3_has_lambda:
                s3_sample_columns.append("lambda_realised")
            try:
                s3_sample_rows = _sample_rows(
                    s3_paths_for_sampling,
                    s3_sample_columns,
                    s3_sample_target,
                    s3_rows_per_file,
                    logger,
                    "s3_bucket_counts",
                )
            except Exception as exc:  # noqa: BLE001
                if "lambda_realised" in s3_sample_columns:
                    logger.warning(
                        "S5: s3 sample with lambda_realised failed (%s); retrying without lambda_realised", exc
                    )
                    s3_sample_columns = ["scenario_id", "bucket_index", "count_N"]
                    s3_sample_rows = _sample_rows(
                        s3_paths_for_sampling,
                        s3_sample_columns,
                        s3_sample_target,
                        s3_rows_per_file,
                        logger,
                        "s3_bucket_counts",
                    )
                else:
                    raise
        schema_ok = True
        schema_detail = {}
        if n_arrivals_total > 0:
            if not sample_rows:
                schema_ok = False
                schema_detail = {"detail": "sample empty for nonzero arrivals"}
            else:
                required_fields = [
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                    "scenario_id",
                    "merchant_id",
                    "zone_representation",
                    "bucket_index",
                    "arrival_seq",
                    "ts_utc",
                    "tzid_primary",
                    "ts_local_primary",
                    "is_virtual",
                ]
                for row in sample_rows:
                    missing = [field for field in required_fields if row.get(field) is None]
                    if missing:
                        schema_ok = False
                        schema_detail = {"detail": "missing required fields", "fields": missing}
                        break
        if not schema_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "SCHEMA_SAMPLE_MISSING_FIELDS",
                    "severity": "ERROR",
                    "context": schema_detail,
                    "message": "Sampled arrivals missing required fields",
                }
            )

        current_phase = "time_grid"
        bucket_maps: dict[str, dict[int, tuple[datetime, datetime]]] = {}
        grid_entry = find_dataset_entry(dictionary_5b, DATASET_TIME_GRID).entry
        for scenario_id in scenario_ids:
            tokens = {
                "manifest_fingerprint": manifest_fingerprint,
                "scenario_id": scenario_id,
            }
            grid_path = _resolve_dataset_path(grid_entry, run_paths, config.external_roots, tokens)
            grid_df = pl.read_parquet(_resolve_parquet_files(grid_path))
            bucket_maps[str(scenario_id)] = _bucket_map(grid_df)

        time_windows_ok, time_detail = _check_time_windows(sample_rows, bucket_maps)
        if not time_windows_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "TIME_WINDOW_MISMATCH",
                    "severity": "ERROR",
                    "context": time_detail,
                    "message": "Sampled arrivals outside bucket window",
                }
            )

        civil_time_ok, civil_detail = _check_civil_time(sample_rows, civil_mismatch_limit)
        one_hour_shift_rate = float(civil_detail.get("one_hour_shift_rate") or 0.0)
        one_hour_shift_gate_ok = one_hour_shift_rate <= float(one_hour_shift_limit)
        civil_time_gate_ok = civil_time_ok and one_hour_shift_gate_ok
        if not one_hour_shift_gate_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CIVIL_TIME_ONE_HOUR_SHIFT_EXCEEDS_LIMIT",
                    "severity": "ERROR",
                    "context": {
                        "one_hour_shift_rate": float(one_hour_shift_rate),
                        "max_one_hour_shift_rate": float(one_hour_shift_limit),
                        "checked_rows": int(civil_detail.get("checked_rows") or 0),
                    },
                    "message": "Sampled one-hour civil-time shift rate exceeds configured threshold",
                }
            )
        dst_support = _dst_window_support(
            sample_rows,
            material_window_floor=dst_window_material_floor,
            min_material_windows=dst_window_min_material_windows,
            min_material_total_support=dst_window_min_total_support,
        )
        dst_hour_mae = _dst_window_hour_bin_mae_pp(
            sample_rows, material_window_floor=dst_window_material_floor
        )
        dst_hour_bin_mae_pp = dst_hour_mae.get("dst_window_hour_bin_mae_pp")
        dst_hour_bin_gate_ok = True
        if dst_hour_bin_mae_pp is not None:
            dst_hour_bin_gate_ok = float(dst_hour_bin_mae_pp) <= float(dst_window_hour_bin_mae_pp_max)
            if not dst_hour_bin_gate_ok:
                issues.append(
                    {
                        "manifest_fingerprint": manifest_fingerprint,
                        "issue_code": "DST_WINDOW_HOUR_BIN_MAE_EXCEEDS_LIMIT",
                        "severity": "ERROR",
                        "context": {
                            "dst_window_hour_bin_mae_pp": float(dst_hour_bin_mae_pp),
                            "dst_window_hour_bin_mae_pp_max": float(dst_window_hour_bin_mae_pp_max),
                            "dst_windows_material_count": int(dst_hour_mae.get("dst_windows_material_count") or 0),
                        },
                        "message": "DST-window hour-bin MAE exceeds configured threshold",
                    }
                )
                civil_time_gate_ok = False
        if bool(dst_support.get("dst_window_insufficient_power")):
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "DST_WINDOW_INSUFFICIENT_POWER",
                    "severity": "ERROR",
                    "context": dst_support,
                    "message": "DST-window sampled support below configured minimum",
                }
            )
            civil_time_gate_ok = False
        if not civil_time_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CIVIL_TIME_MISMATCH",
                    "severity": "ERROR",
                    "context": civil_detail,
                    "message": "Sampled civil-time mismatch exceeds configured threshold",
                }
            )
        civil_gate_detail = {
            "threshold_source": "policy+opt_in_env_override" if env_override_enabled else "policy",
            "policy_path": str(policy_path),
            "max_civil_mismatch_rate": float(civil_mismatch_limit),
            "max_one_hour_shift_rate": float(one_hour_shift_limit),
            "dst_window_hour_bin_mae_pp_max": float(dst_window_hour_bin_mae_pp_max),
            "dst_window_min_support": int(dst_window_material_floor),
            "dst_window_min_exposed_windows": int(dst_window_min_material_windows),
            "dst_window_min_total_support": int(dst_window_min_total_support),
            "civil_mismatch_rate": float(civil_detail.get("mismatch_rate") or 0.0),
            "one_hour_shift_rate": float(one_hour_shift_rate),
            "dst_window_hour_bin_mae_pp": float(dst_hour_bin_mae_pp) if dst_hour_bin_mae_pp is not None else None,
            "civil_time_ok": bool(civil_time_ok),
            "one_hour_shift_gate_ok": bool(one_hour_shift_gate_ok),
            "dst_window_hour_bin_gate_ok": bool(dst_hour_bin_gate_ok),
            "dst_window_support": dst_support,
            "civil_time_gate_ok": bool(civil_time_gate_ok),
        }

        current_phase = "routing_membership"
        site_entry = find_dataset_entry(dictionary_5b, DATASET_SITE_LOCATIONS).entry
        edge_entry = find_dataset_entry(dictionary_5b, DATASET_EDGE_CATALOGUE).entry
        site_paths = _resolve_parquet_files(
            _resolve_dataset_path(
                site_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed_list[0]), "manifest_fingerprint": manifest_fingerprint},
            )
        )
        edge_paths = _resolve_parquet_files(
            _resolve_dataset_path(
                edge_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed_list[0]), "manifest_fingerprint": manifest_fingerprint},
            )
        )
        routing_ok, routing_detail = _check_routing_membership(sample_rows, site_paths, edge_paths, logger)
        if not routing_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "ROUTING_ID_MISMATCH",
                    "severity": "ERROR",
                    "context": routing_detail,
                    "message": "Sampled routing ids missing from universe",
                }
            )

        calibration_gate_ok = True
        calibration_target = "bplus" if calibration_eval_mode == "enforce_bplus" else "b"
        calibration_severity = "ERROR" if calibration_eval_mode in {"enforce_b", "enforce_bplus"} else "WARN"
        top10_tz_share = _topk_tz_share(sample_rows, k=10)
        if have_summary_counts and n_arrivals_total > 0:
            virtual_share_observed = float(n_arrivals_virtual) / float(n_arrivals_total)
        else:
            sampled_virtual = [row for row in sample_rows if row.get("is_virtual") is not None]
            if sampled_virtual:
                virtual_share_observed = float(sum(1 for row in sampled_virtual if bool(row.get("is_virtual")))) / float(
                    len(sampled_virtual)
                )
            else:
                virtual_share_observed = None
        weekend_share_observed = _observed_weekend_share(sample_rows)
        weekend_share_expected = _expected_weekend_share_from_s3_sample(s3_sample_rows, bucket_maps)
        weekend_share_delta_pp = (
            abs(float(weekend_share_observed) - float(weekend_share_expected)) * 100.0
            if weekend_share_observed is not None and weekend_share_expected is not None
            else None
        )
        residual_std = (
            _residual_std_from_s3_sample(s3_sample_rows)
            if s3_sample_rows and "lambda_realised" in s3_sample_rows[0]
            else None
        )
        if calibration_target == "bplus":
            top10_limit = float(top10_tz_share_max_bplus)
            virtual_min = float(virtual_share_min_bplus)
            virtual_max = float(virtual_share_max_bplus)
            weekend_delta_limit = float(weekend_delta_max_bplus)
            residual_min = float(residual_std_min_bplus)
            residual_max = float(residual_std_max_bplus)
        else:
            top10_limit = float(top10_tz_share_max_b)
            virtual_min = float(virtual_share_min_b)
            virtual_max = float(virtual_share_max_b)
            weekend_delta_limit = float(weekend_delta_max_b)
            residual_min = float(residual_std_min_b)
            residual_max = float(residual_std_max_b)
        calibration_sample_power_ok = (
            len(sample_rows) >= int(calibration_min_sample_rows)
            and len(s3_sample_rows) >= int(calibration_min_sample_rows)
        )
        if not calibration_sample_power_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CALIBRATION_SAMPLE_POWER_INSUFFICIENT",
                    "severity": calibration_severity,
                    "context": {
                        "arrival_sample_rows": int(len(sample_rows)),
                        "s3_sample_rows": int(len(s3_sample_rows)),
                        "min_sample_rows": int(calibration_min_sample_rows),
                    },
                    "message": "Calibration sentinel sample support below configured threshold",
                }
            )
            if calibration_severity == "ERROR":
                calibration_gate_ok = False

        top10_ok = top10_tz_share is not None and float(top10_tz_share) <= float(top10_limit)
        if not top10_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CALIBRATION_TOP10_TZ_SHARE_EXCEEDS_LIMIT",
                    "severity": calibration_severity,
                    "context": {
                        "top10_tz_share": float(top10_tz_share) if top10_tz_share is not None else None,
                        "top10_tz_share_max": float(top10_limit),
                        "target": calibration_target,
                    },
                    "message": "Top-10 timezone concentration exceeds calibration target",
                }
            )
            if calibration_severity == "ERROR":
                calibration_gate_ok = False

        virtual_ok = (
            virtual_share_observed is not None
            and float(virtual_share_observed) >= float(virtual_min)
            and float(virtual_share_observed) <= float(virtual_max)
        )
        if not virtual_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CALIBRATION_VIRTUAL_SHARE_OUT_OF_BOUNDS",
                    "severity": calibration_severity,
                    "context": {
                        "virtual_share_observed": float(virtual_share_observed)
                        if virtual_share_observed is not None
                        else None,
                        "virtual_share_min": float(virtual_min),
                        "virtual_share_max": float(virtual_max),
                        "target": calibration_target,
                    },
                    "message": "Observed virtual share is outside calibration target band",
                }
            )
            if calibration_severity == "ERROR":
                calibration_gate_ok = False

        weekend_ok = weekend_share_delta_pp is not None and float(weekend_share_delta_pp) <= float(weekend_delta_limit)
        if not weekend_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CALIBRATION_WEEKEND_DELTA_EXCEEDS_LIMIT",
                    "severity": calibration_severity,
                    "context": {
                        "weekend_share_observed": float(weekend_share_observed)
                        if weekend_share_observed is not None
                        else None,
                        "weekend_share_expected": float(weekend_share_expected)
                        if weekend_share_expected is not None
                        else None,
                        "weekend_share_delta_pp": float(weekend_share_delta_pp)
                        if weekend_share_delta_pp is not None
                        else None,
                        "weekend_share_delta_pp_max": float(weekend_delta_limit),
                        "target": calibration_target,
                    },
                    "message": "Weekend share delta exceeds calibration target",
                }
            )
            if calibration_severity == "ERROR":
                calibration_gate_ok = False

        residual_ok = (
            residual_std is not None
            and float(residual_std) >= float(residual_min)
            and float(residual_std) <= float(residual_max)
        )
        if not residual_ok:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "CALIBRATION_RESIDUAL_STD_OUT_OF_BOUNDS",
                    "severity": calibration_severity,
                    "context": {
                        "residual_std": float(residual_std) if residual_std is not None else None,
                        "residual_std_min": float(residual_min),
                        "residual_std_max": float(residual_max),
                        "target": calibration_target,
                    },
                    "message": "Residual-std sentinel is outside calibration target range",
                }
            )
            if calibration_severity == "ERROR":
                calibration_gate_ok = False

        calibration_detail = {
            "evaluation_mode": calibration_eval_mode,
            "target": calibration_target,
            "severity_on_fail": calibration_severity,
            "policy_path": str(policy_path),
            "min_sample_rows": int(calibration_min_sample_rows),
            "arrival_sample_rows": int(len(sample_rows)),
            "s3_sample_rows": int(len(s3_sample_rows)),
            "sample_power_ok": bool(calibration_sample_power_ok),
            "metrics": {
                "top10_tz_share": float(top10_tz_share) if top10_tz_share is not None else None,
                "virtual_share_observed": float(virtual_share_observed)
                if virtual_share_observed is not None
                else None,
                "weekend_share_observed": float(weekend_share_observed)
                if weekend_share_observed is not None
                else None,
                "weekend_share_expected": float(weekend_share_expected)
                if weekend_share_expected is not None
                else None,
                "weekend_share_delta_pp": float(weekend_share_delta_pp) if weekend_share_delta_pp is not None else None,
                "residual_std": float(residual_std) if residual_std is not None else None,
            },
            "thresholds": {
                "top10_tz_share_max_b": float(top10_tz_share_max_b),
                "top10_tz_share_max_bplus": float(top10_tz_share_max_bplus),
                "virtual_share_min_b": float(virtual_share_min_b),
                "virtual_share_max_b": float(virtual_share_max_b),
                "virtual_share_min_bplus": float(virtual_share_min_bplus),
                "virtual_share_max_bplus": float(virtual_share_max_bplus),
                "weekend_share_delta_pp_max_b": float(weekend_delta_max_b),
                "weekend_share_delta_pp_max_bplus": float(weekend_delta_max_bplus),
                "residual_std_min_b": float(residual_std_min_b),
                "residual_std_max_b": float(residual_std_max_b),
                "residual_std_min_bplus": float(residual_std_min_bplus),
                "residual_std_max_bplus": float(residual_std_max_bplus),
            },
            "gates": {
                "top10_tz_share_ok": bool(top10_ok),
                "virtual_share_ok": bool(virtual_ok),
                "weekend_delta_ok": bool(weekend_ok),
                "residual_std_ok": bool(residual_ok),
                "calibration_gate_ok": bool(calibration_gate_ok),
            },
        }

        current_phase = "rng_trace"
        rng_entry = find_dataset_entry(dictionary_5b, DATASET_RNG_TRACE).entry
        rng_paths: list[Path] = []
        for seed in seed_list:
            for parameter_hash in sorted(parameter_hashes):
                tokens = {"seed": str(seed), "parameter_hash": parameter_hash, "run_id": run_id_value}
                rng_root = _resolve_dataset_path(rng_entry, run_paths, config.external_roots, tokens)
                if rng_root.exists():
                    rng_paths.extend(_resolve_jsonl_files(rng_root))
        rng_families_found = set()
        for path in rng_paths:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    payload = line.strip()
                    if not payload:
                        continue
                    record = json.loads(payload)
                    rng_families_found.add(
                        (str(record.get("module") or ""), str(record.get("substream_label") or ""))
                    )
        if not rng_paths:
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "issue_code": "RNG_TRACE_MISSING",
                    "severity": "WARN",
                    "context": {"detail": "no rng_trace_log files resolved"},
                    "message": "rng_trace_log missing for this run (lean mode)",
                }
            )
            rng_accounting_ok = True
        else:
            missing_rng = [item for item in REQUIRED_RNG_FAMILIES if item not in rng_families_found]
            if missing_rng:
                issues.append(
                    {
                        "manifest_fingerprint": manifest_fingerprint,
                        "issue_code": "RNG_TRACE_FAMILY_MISSING",
                        "severity": "WARN",
                        "context": {"missing": missing_rng},
                        "message": "rng_trace_log missing some RNG families (lean mode)",
                    }
                )
            rng_accounting_ok = True

        current_phase = "bundle_write"
        bundle_root = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_BUNDLE).entry, run_paths, config.external_roots, tokens_mf
        )
        index_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_BUNDLE_INDEX).entry, run_paths, config.external_roots, tokens_mf
        )
        report_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_REPORT).entry, run_paths, config.external_roots, tokens_mf
        )
        issues_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_ISSUES).entry, run_paths, config.external_roots, tokens_mf
        )
        flag_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5b, DATASET_FLAG).entry, run_paths, config.external_roots, tokens_mf
        )

        overall_status = "PASS"
        if not all(
            [
                counts_match_s3,
                time_windows_ok,
                civil_time_gate_ok,
                calibration_gate_ok,
                routing_ok,
                schema_ok,
                rng_accounting_ok,
            ]
        ):
            overall_status = "FAIL"

        report_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "spec_version": spec_version,
            "status": overall_status,
            "n_parameter_hashes": n_parameter_hashes,
            "n_scenarios": n_scenarios,
            "n_seeds": n_seeds,
            "n_buckets_total": n_buckets_total,
            "n_buckets_nonzero": n_buckets_nonzero,
            "n_arrivals_total": n_arrivals_total,
            "counts_match_s3": counts_match_s3,
            "time_windows_ok": time_windows_ok,
            "civil_time_ok": civil_time_ok,
            "civil_time_gate_ok": civil_time_gate_ok,
            "calibration_gate_ok": calibration_gate_ok,
            "routing_ok": routing_ok,
            "schema_partition_pk_ok": schema_ok,
            "rng_accounting_ok": rng_accounting_ok,
            "bundle_integrity_ok": True,
            "sampling": {
                "arrival_sample_target": sample_target,
                "arrival_sample_rows": len(sample_rows),
                "s3_sample_target": s3_sample_target,
                "s3_sample_rows": len(s3_sample_rows),
                "civil_mismatch_rate": float(civil_detail.get("mismatch_rate") or 0.0),
                "civil_mismatch_limit": float(civil_mismatch_limit),
                "civil_time_gates": civil_gate_detail,
                "calibration_sentinels": calibration_detail,
            },
        }
        if have_summary_counts:
            report_payload["n_arrivals_physical"] = n_arrivals_physical
            report_payload["n_arrivals_virtual"] = n_arrivals_virtual
        if overall_status != "PASS":
            report_payload["error_code"] = "S5_VALIDATION_FAILED"
        _validate_payload(schema_layer2, schema_layer1, schema_layer2, "validation/validation_report_5B", report_payload)

        tmp_root = run_paths.tmp_root / f"s5_validation_bundle_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        report_rel = report_path.relative_to(bundle_root)
        issues_rel = issues_path.relative_to(bundle_root)
        index_rel = index_path.relative_to(bundle_root)
        flag_rel = flag_path.relative_to(bundle_root)

        _write_json(tmp_root / report_rel, report_payload)

        if issues:
            issues_df = pl.DataFrame(issues)
        else:
            issues_df = pl.DataFrame(
                {
                    "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                    "issue_code": pl.Series([], dtype=pl.Utf8),
                    "severity": pl.Series([], dtype=pl.Utf8),
                    "context": pl.Series([], dtype=pl.Object),
                    "message": pl.Series([], dtype=pl.Utf8),
                }
            )
        issues_df_path = tmp_root / issues_rel
        issues_df_path.parent.mkdir(parents=True, exist_ok=True)
        issues_df.write_parquet(issues_df_path)

        entries = [
            {"path": report_rel.as_posix(), "sha256_hex": sha256_file(tmp_root / report_rel).sha256_hex},
            {"path": issues_rel.as_posix(), "sha256_hex": sha256_file(tmp_root / issues_rel).sha256_hex},
        ]

        index_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "segment_id": SEGMENT,
            "s5_spec_version": spec_version,
            "generated_utc": utc_now_rfc3339_micro(),
            "status": overall_status,
            "summary": {
                "scenario_count": n_scenarios,
                "issue_count": len(issues),
            },
            "entries": sorted(entries, key=lambda item: item["path"]),
        }
        _validate_payload(schema_layer2, schema_layer1, schema_layer2, "validation/validation_bundle_index_5B", index_payload)
        _write_json(tmp_root / index_rel, index_payload)

        bundle_digest = _bundle_digest(tmp_root, entries)
        if overall_status == "PASS":
            flag_payload = {"manifest_fingerprint": manifest_fingerprint, "bundle_digest_sha256": bundle_digest}
            _validate_payload(schema_layer2, schema_layer1, schema_layer2, "validation/passed_flag_5B", flag_payload)
            _write_json(tmp_root / flag_rel, flag_payload)

        current_phase = "publish"
        if bundle_root.exists():
            existing_index = bundle_root / index_rel
            if not existing_index.exists():
                raise EngineFailure(
                    "F4",
                    "S5_OUTPUT_CONFLICT",
                    STATE,
                    MODULE_NAME,
                    {"detail": "bundle exists without index", "bundle_root": str(bundle_root)},
                )
            existing_index_payload = _load_json(existing_index)
            candidate_index_payload = _load_json(tmp_root / index_rel)
            if _canonical_index_payload(existing_index_payload) != _canonical_index_payload(candidate_index_payload):
                raise EngineFailure(
                    "F4",
                    "S5_OUTPUT_CONFLICT",
                    STATE,
                    MODULE_NAME,
                    {"detail": "index mismatch (non-volatile fields)", "bundle_root": str(bundle_root)},
                )
            if overall_status == "PASS":
                existing_flag = bundle_root / flag_rel
                if not existing_flag.exists():
                    raise EngineFailure(
                        "F4",
                        "S5_OUTPUT_CONFLICT",
                        STATE,
                        MODULE_NAME,
                        {"detail": "missing _passed.flag", "bundle_root": str(bundle_root)},
                    )
                existing_flag_payload = _load_json(existing_flag)
                if existing_flag_payload.get("bundle_digest_sha256") != bundle_digest:
                    raise EngineFailure(
                        "F4",
                        "S5_OUTPUT_CONFLICT",
                        STATE,
                        MODULE_NAME,
                        {"detail": "passed flag digest mismatch", "bundle_root": str(bundle_root)},
                    )
            logger.info("S5: bundle already exists and is identical; skipping publish.")
        else:
            bundle_root.parent.mkdir(parents=True, exist_ok=True)
            tmp_root.replace(bundle_root)
            logger.info("S5: bundle published path=%s", bundle_root)

        bundle_integrity_ok = True
        status = "PASS" if overall_status == "PASS" else "FAIL"
        if status != "PASS" and not error_code:
            error_code = "S5_VALIDATION_FAILED"
        timer.info("S5: bundle complete (entries=%d, digest=%s)", len(entries), bundle_digest)

    except (ContractError, InputResolutionError) as exc:
        error_code = error_code or "S5_CONTRACT_INVALID"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        error_code = error_code or "S5_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id_value and manifest_fingerprint and run_paths and dictionary_5b:
            try:
                utc_day = started_utc[:10]
                run_report_path = _resolve_dataset_path(
                    find_dataset_entry(dictionary_5b, DATASET_RUN_REPORT).entry,
                    run_paths,
                    config.external_roots,
                    {"utc_day": utc_day},
                )
                run_report_output_path = run_report_path
                run_report_payload = {
                    "layer": "layer2",
                    "segment": SEGMENT,
                    "state": STATE,
                    "state_id": "5B.S5",
                    "manifest_fingerprint": manifest_fingerprint,
                    "run_id": run_id_value,
                    "status": status,
                    "error_code": error_code,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "metrics": {
                        "n_parameter_hashes": n_parameter_hashes,
                        "n_scenarios": n_scenarios,
                        "n_seeds": n_seeds,
                        "n_buckets_total": n_buckets_total,
                        "n_buckets_nonzero": n_buckets_nonzero,
                        "n_arrivals_total": n_arrivals_total,
                        "n_arrivals_physical": n_arrivals_physical,
                        "n_arrivals_virtual": n_arrivals_virtual,
                        "counts_match_s3": counts_match_s3,
                        "time_windows_ok": time_windows_ok,
                        "civil_time_ok": civil_time_ok,
                        "civil_time_gate_ok": civil_time_gate_ok,
                        "calibration_gate_ok": calibration_gate_ok,
                        "calibration_evaluation_mode": calibration_eval_mode,
                        "routing_ok": routing_ok,
                        "schema_partition_pk_ok": schema_ok,
                        "rng_accounting_ok": rng_accounting_ok,
                        "bundle_integrity_ok": bundle_integrity_ok,
                    },
                }
                if error_context:
                    run_report_payload["error_context"] = error_context
                    run_report_payload["first_failure_phase"] = first_failure_phase
                _append_jsonl(run_report_path, run_report_payload)
                logger.info("S5: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S5: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "S5_VALIDATION_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if run_paths is None:
        raise EngineFailure("F4", "S5_INFRASTRUCTURE_IO_ERROR", STATE, MODULE_NAME, {"detail": "missing run_paths"})

    return S5Result(
        run_id=str(run_id_value),
        manifest_fingerprint=str(manifest_fingerprint),
        bundle_root=bundle_root,
        index_path=index_path,
        report_path=report_path,
        issues_path=issues_path,
        flag_path=flag_path if status == "PASS" else None,
        run_report_path=run_report_output_path
        if run_report_output_path is not None
        else run_paths.run_root / "reports" / "missing",
    )
