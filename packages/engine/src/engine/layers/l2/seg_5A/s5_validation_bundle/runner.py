
"""S5 validation bundle & passed flag for Segment 5A."""

from __future__ import annotations

import hashlib
import heapq
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l2.seg_5A.s0_gate.runner import (
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _normalize_semver,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _sealed_inputs_digest,
)

try:  # pragma: no cover - optional dependency for streaming parquet scans
    import pyarrow.parquet as pq
except Exception:  # noqa: BLE001
    pq = None


MODULE_NAME = "5A.s5_validation_bundle"
SEGMENT = "5A"
STATE = "S5"
S5_SPEC_VERSION = "1.0.0"

DATASET_S0_GATE = "s0_gate_receipt_5A"
DATASET_SEALED_INPUTS = "sealed_inputs_5A"
DATASET_SCENARIO_MANIFEST = "scenario_manifest_5A"
DATASET_SCENARIO_HORIZON = "scenario_horizon_config_5A"
DATASET_VALIDATION_POLICY = "validation_policy_5A"
DATASET_SPEC_COMPAT = "spec_compatibility_config_5A"
DATASET_OVERLAY_POLICY = "scenario_overlay_policy_5A"

DATASET_MERCHANT_PROFILE = "merchant_zone_profile_5A"
DATASET_SHAPE_GRID = "shape_grid_definition_5A"
DATASET_CLASS_ZONE_SHAPE = "class_zone_shape_5A"
DATASET_BASELINE_LOCAL = "merchant_zone_baseline_local_5A"
DATASET_SCENARIO_LOCAL = "merchant_zone_scenario_local_5A"
DATASET_OVERLAY_FACTORS = "merchant_zone_overlay_factors_5A"
DATASET_SCENARIO_UTC = "merchant_zone_scenario_utc_5A"

DATASET_BUNDLE = "validation_bundle_5A"
DATASET_BUNDLE_INDEX = "validation_bundle_index_5A"
DATASET_REPORT = "validation_report_5A"
DATASET_ISSUES = "validation_issue_table_5A"
DATASET_FLAG = "validation_passed_flag_5A"
DATASET_RUN_REPORT = "s5_run_report_5A"

CHECK_S0_PRESENT = "S0_PRESENT"
CHECK_S0_DIGEST = "S0_DIGEST_MATCH"
CHECK_UPSTREAM = "UPSTREAM_ALL_PASS"
CHECK_S1_PRESENT = "S1_PRESENT"
CHECK_S1_PK = "S1_PK_VALID"
CHECK_S1_REQUIRED = "S1_REQUIRED_FIELDS"
CHECK_S1_SCALE = "S1_SCALE_NONNEG_FINITE"
CHECK_S2_PRESENT = "S2_PRESENT"
CHECK_S2_GRID = "S2_GRID_VALID"
CHECK_S2_SHAPE_NONNEG = "S2_SHAPES_NONNEG"
CHECK_S2_SHAPE_SUM = "S2_SHAPES_SUM_TO_ONE"
CHECK_S2_DOMAIN = "S2_DOMAIN_COVERS_S1"
CHECK_S3_PRESENT = "S3_PRESENT"
CHECK_S3_DOMAIN = "S3_DOMAIN_PARITY"
CHECK_S3_LAMBDA = "S3_LAMBDA_NONNEG_FINITE"
CHECK_S3_WEEKLY = "S3_WEEKLY_SUM_VS_SCALE"
CHECK_S4_PRESENT = "S4_PRESENT"
CHECK_S4_DOMAIN = "S4_DOMAIN_PARITY"
CHECK_S4_HORIZON = "S4_HORIZON_COVERAGE"
CHECK_S4_LAMBDA = "S4_LAMBDA_NONNEG_FINITE"
CHECK_S4_OVERLAY_HARD = "S4_OVERLAY_FACTOR_HARD_BOUNDS"
CHECK_S4_OVERLAY_WARN = "S4_OVERLAY_FACTOR_WARN_BOUNDS"
CHECK_S4_RECOMPOSE = "S4_RECOMPOSITION_SAMPLE"
CHECK_S4_GUARDRAIL = "S4_LAMBDA_SCENARIO_GUARDRAIL"
CHECK_S4_LOCAL_VS_UTC = "S4_LOCAL_VS_UTC_TOTAL"
CHECK_SPEC_COMPAT = "SPEC_COMPATIBILITY"

STATUS_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
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
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        if args:
            message = message % args
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(self, total: Optional[int], logger, label: str, min_interval_seconds: float = 5.0) -> None:
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


def _validate_array_rows(
    rows: Iterable[dict],
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    max_errors: int = 5,
) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    if schema.get("type") != "array":
        raise ContractError(f"Expected array schema at {anchor}, found {schema.get('type')}")
    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        raise ContractError(f"Array schema missing items object at {anchor}")
    item_schema = dict(items_schema)
    parent_defs = schema.get("$defs") or {}
    if parent_defs:
        merged_defs = dict(parent_defs)
        if isinstance(item_schema.get("$defs"), dict):
            merged_defs.update(item_schema.get("$defs", {}))
        item_schema["$defs"] = merged_defs
    validator = Draft202012Validator(item_schema)
    errors: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        for error in validator.iter_errors(row):
            field = ".".join(str(part) for part in error.path) if error.path else ""
            errors.append(
                {
                    "row_index": index,
                    "field": field,
                    "message": error.message,
                }
            )
            if len(errors) >= max_errors:
                break
        if errors and len(errors) >= max_errors:
            break
    if errors:
        lines = [
            f"row {item['row_index']}: {item['field']} {item['message']}".strip()
            for item in errors
        ]
        raise SchemaValidationError("Schema validation failed:\n" + "\n".join(lines), errors)


def _array_required_fields(
    schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str
) -> list[str]:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    if schema.get("type") != "array":
        raise ContractError(f"Expected array schema at {anchor}, found {schema.get('type')}")
    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        raise ContractError(f"Array schema missing items object at {anchor}")
    required = items_schema.get("required")
    if not isinstance(required, list):
        return []
    return [str(item) for item in required]


def _resolve_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _parse_rfc3339(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _status_worse(left: str, right: str) -> str:
    return right if STATUS_ORDER[right] > STATUS_ORDER[left] else left


def _status_from_error(max_abs: float, warn: float, fail: float) -> str:
    if max_abs <= warn:
        return "PASS"
    if max_abs <= fail:
        return "WARN"
    return "FAIL"


def _bundle_digest(bundle_root: Path, entries: list[dict]) -> str:
    hasher = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
        rel_path = entry.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            raise EngineFailure(
                "F4",
                "S5_INDEX_BUILD_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": "bundle entry missing path"},
            )
        file_path = bundle_root / rel_path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "S5_INDEX_BUILD_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"bundle file missing: {rel_path}", "bundle_root": str(bundle_root)},
            )
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def _hash64(prefix: bytes, merchant_bytes: bytes, zone_bytes: bytes, horizon_bytes: bytes) -> int:
    digest = hashlib.sha256(
        prefix
        + merchant_bytes
        + b"|"
        + zone_bytes
        + b"|"
        + horizon_bytes
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _sample_seed(prefix: bytes) -> int:
    digest = hashlib.sha256(prefix).digest()
    return int.from_bytes(digest[:8], "little", signed=False)


def _minhash_sample(
    paths: list[Path],
    sample_n: int,
    prefix: bytes,
    logger,
    include_channel_group: bool = False,
) -> list[dict]:
    if sample_n <= 0:
        return []

    # High-blast fast path: deterministic vectorized hashing + bottom-k in Polars.
    try:
        sample_columns = [
            "merchant_id",
            "legal_country_iso",
            "tzid",
            "local_horizon_bucket_index",
            "lambda_local_scenario",
            "overlay_factor_total",
        ]
        if include_channel_group:
            sample_columns.append("channel_group")

        hash_inputs: list[pl.Expr] = [
            pl.col("merchant_id"),
            pl.col("legal_country_iso"),
            pl.col("tzid"),
            pl.col("local_horizon_bucket_index"),
        ]
        order_by: list[str] = [
            "__sample_hash",
            "merchant_id",
            "legal_country_iso",
            "tzid",
            "local_horizon_bucket_index",
        ]
        if include_channel_group:
            hash_inputs.append(pl.col("channel_group"))
            order_by.append("channel_group")

        sample_df = (
            pl.scan_parquet([str(path) for path in paths])
            .select(sample_columns)
            .with_columns(
                pl.struct(hash_inputs).hash(seed=_sample_seed(prefix)).alias("__sample_hash")
            )
            .bottom_k(sample_n, by=order_by)
            .sort(order_by)
            .select(sample_columns)
            .collect()
        )
        logger.info(
            "S5: recomposition sample mode=fast_struct_hash_top_n_v2 selected=%s",
            sample_df.height,
        )
        return list(sample_df.iter_rows(named=True))
    except Exception as exc:  # noqa: BLE001
        logger.warning("S5: fast sample path failed; falling back to reference path: %s", exc)

    heap: list[tuple[int, tuple[str, str, int], tuple[object, object, object, int, object]]] = []
    base_columns = [
        "merchant_id",
        "legal_country_iso",
        "tzid",
        "local_horizon_bucket_index",
        "lambda_local_scenario",
        "overlay_factor_total",
    ]
    columns = list(base_columns)
    if include_channel_group:
        columns.append("channel_group")

    total_rows = None
    if pq is not None:
        total_rows = sum(int(pq.ParquetFile(path).metadata.num_rows) for path in paths)
    tracker = _ProgressTracker(total_rows, logger, "S5: recomposition sample scan")
    merchant_key_cache: dict[object, tuple[str, bytes]] = {}
    zone_key_cache: dict[tuple[object, object, object], tuple[str, bytes]] = {}
    horizon_key_cache: dict[int, bytes] = {}

    def _merchant_key_bytes(merchant_id: object) -> tuple[str, bytes]:
        cached = merchant_key_cache.get(merchant_id)
        if cached is not None:
            return cached
        key = str(merchant_id)
        value = (key, key.encode("ascii"))
        merchant_key_cache[merchant_id] = value
        return value

    def _zone_key_bytes(country: object, tzid: object, channel_group: object) -> tuple[str, bytes]:
        token = (country, tzid, channel_group if include_channel_group else None)
        cached = zone_key_cache.get(token)
        if cached is not None:
            return cached
        zone_key = f"{country}|{tzid}"
        if include_channel_group:
            zone_key = f"{zone_key}|{channel_group}"
        value = (zone_key, zone_key.encode("ascii"))
        zone_key_cache[token] = value
        return value

    def _horizon_bytes(horizon_key: int) -> bytes:
        cached = horizon_key_cache.get(horizon_key)
        if cached is not None:
            return cached
        value = str(horizon_key).encode("ascii")
        horizon_key_cache[horizon_key] = value
        return value

    for path in paths:
        if pq is None:
            df = pl.read_parquet(path, columns=columns)
            for row in df.iter_rows(named=True):
                merchant_id = row["merchant_id"]
                country = row["legal_country_iso"]
                tzid = row["tzid"]
                horizon_key = int(row["local_horizon_bucket_index"])
                channel_group = row.get("channel_group") if include_channel_group else None
                lambda_local_scenario = float(row["lambda_local_scenario"])
                overlay_factor_total = float(row["overlay_factor_total"])
                merchant_key, merchant_bytes = _merchant_key_bytes(merchant_id)
                zone_key, zone_bytes = _zone_key_bytes(country, tzid, channel_group)
                hash_val = _hash64(prefix, merchant_bytes, zone_bytes, _horizon_bytes(horizon_key))
                pk = (merchant_key, zone_key, horizon_key)
                payload = (
                    merchant_id,
                    country,
                    tzid,
                    horizon_key,
                    channel_group,
                    lambda_local_scenario,
                    overlay_factor_total,
                )
                if len(heap) < sample_n:
                    heapq.heappush(heap, (-hash_val, pk, payload))
                else:
                    worst_hash = -heap[0][0]
                    worst_pk = heap[0][1]
                    if hash_val < worst_hash or (hash_val == worst_hash and pk < worst_pk):
                        heapq.heapreplace(heap, (-hash_val, pk, payload))
            tracker.update(df.height)
            continue
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=65536, columns=columns):
            data = batch.to_pydict()
            channel_groups = data.get("channel_group") if include_channel_group else None
            merchant_ids = data["merchant_id"]
            countries = data["legal_country_iso"]
            tzids = data["tzid"]
            horizon_buckets = data["local_horizon_bucket_index"]
            lambda_values = data["lambda_local_scenario"]
            overlay_values = data["overlay_factor_total"]
            for idx in range(batch.num_rows):
                merchant_id = merchant_ids[idx]
                country = countries[idx]
                tzid = tzids[idx]
                horizon_key = int(horizon_buckets[idx])
                channel_group = channel_groups[idx] if channel_groups is not None else None
                lambda_local_scenario = float(lambda_values[idx])
                overlay_factor_total = float(overlay_values[idx])
                merchant_key, merchant_bytes = _merchant_key_bytes(merchant_id)
                zone_key, zone_bytes = _zone_key_bytes(country, tzid, channel_group)
                hash_val = _hash64(prefix, merchant_bytes, zone_bytes, _horizon_bytes(horizon_key))
                pk = (merchant_key, zone_key, horizon_key)
                payload = (
                    merchant_id,
                    country,
                    tzid,
                    horizon_key,
                    channel_group,
                    lambda_local_scenario,
                    overlay_factor_total,
                )
                if len(heap) < sample_n:
                    heapq.heappush(heap, (-hash_val, pk, payload))
                else:
                    worst_hash = -heap[0][0]
                    worst_pk = heap[0][1]
                    if hash_val < worst_hash or (hash_val == worst_hash and pk < worst_pk):
                        heapq.heapreplace(heap, (-hash_val, pk, payload))
            tracker.update(batch.num_rows)
    selected = sorted([(-item[0], item[1], item[2]) for item in heap], key=lambda item: (item[0], item[1]))
    rows: list[dict] = []
    for _, _, payload in selected:
        merchant_id, country, tzid, horizon_key, channel_group, lambda_local_scenario, overlay_factor_total = payload
        row = {
            "merchant_id": merchant_id,
            "legal_country_iso": country,
            "tzid": tzid,
            "local_horizon_bucket_index": int(horizon_key),
            "lambda_local_scenario": float(lambda_local_scenario),
            "overlay_factor_total": float(overlay_factor_total),
        }
        if include_channel_group:
            row["channel_group"] = channel_group
        rows.append(row)
    return rows


def _scenario_horizon_map(policy: dict) -> dict[str, dict]:
    scenarios = policy.get("scenarios")
    if not isinstance(scenarios, list):
        raise ContractError("scenario_horizon_config_5A missing scenarios list")
    output: dict[str, dict] = {}
    for row in scenarios:
        if not isinstance(row, dict):
            continue
        scenario_id = row.get("scenario_id")
        if not scenario_id:
            continue
        horizon_start = _parse_rfc3339(str(row["horizon_start_utc"]))
        horizon_end = _parse_rfc3339(str(row["horizon_end_utc"]))
        bucket_minutes = int(row["bucket_duration_minutes"])
        horizon_minutes = int((horizon_end - horizon_start).total_seconds() // 60)
        if horizon_minutes <= 0 or horizon_minutes % bucket_minutes != 0:
            raise ContractError(
                f"Scenario horizon invalid for {scenario_id}: minutes={horizon_minutes} bucket={bucket_minutes}"
            )
        output[str(scenario_id)] = {
            "scenario_id": str(scenario_id),
            "scenario_version": row.get("scenario_version"),
            "horizon_start": horizon_start,
            "horizon_end": horizon_end,
            "bucket_minutes": bucket_minutes,
            "bucket_count": horizon_minutes // bucket_minutes,
            "emit_utc_intensities": bool(row.get("emit_utc_intensities", False)),
        }
    return output


def _grid_lookup(grid_df: pl.DataFrame) -> dict[tuple[int, int], int]:
    grid_map: dict[tuple[int, int], int] = {}
    for row in grid_df.iter_rows(named=True):
        key = (int(row["local_day_of_week"]), int(row["local_minutes_since_midnight"]))
        grid_map[key] = int(row["bucket_index"])
    return grid_map


def _bucket_index_for_row(
    tzid: str,
    horizon_start: datetime,
    bucket_minutes: int,
    local_horizon_bucket_index: int,
    grid_map: dict[tuple[int, int], int],
) -> Optional[int]:
    try:
        zone = ZoneInfo(tzid)
    except Exception:  # noqa: BLE001
        return None
    utc_dt = horizon_start + timedelta(minutes=int(local_horizon_bucket_index) * bucket_minutes)
    local_dt = utc_dt.astimezone(zone)
    local_minutes = local_dt.hour * 60 + local_dt.minute
    local_minutes = (local_minutes // bucket_minutes) * bucket_minutes
    key = (local_dt.isoweekday(), local_minutes)
    return grid_map.get(key)


def _ensure_required_columns(columns: list[str], required: list[str]) -> list[str]:
    missing = [col for col in required if col not in columns]
    return missing


def _count_invalid(scan: pl.LazyFrame, expr: pl.Expr) -> int:
    value = scan.select(expr.cast(pl.UInt64).sum()).collect().item()
    return int(value or 0)


def _scan_columns(scan: pl.LazyFrame) -> list[str]:
    try:
        return list(scan.collect_schema().names())
    except Exception:  # noqa: BLE001
        return list(scan.columns)


def _load_policy(
    path: Optional[Path],
    schema_5a: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    logger,
) -> Optional[dict]:
    if path is None or not path.exists():
        logger.warning("S5: policy missing (%s); using defaults if available", anchor)
        return None
    payload = _load_yaml(path) if path.suffix.lower() in {".yaml", ".yml"} else _load_json(path)
    _validate_payload(schema_5a, schema_layer1, schema_layer2, anchor, payload)
    if not isinstance(payload, dict):
        raise ContractError(f"Policy payload is not a dict: {path}")
    return payload


def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l2.seg_5A.s5_validation_bundle.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    if hasattr(pl.Config, "set_streaming"):
        pl.Config.set_streaming(False)
        logger.info("S5: polars streaming engine disabled to keep parquet scans on the standard engine")

    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    seed: Optional[int] = None
    run_id_value: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash_receipt: Optional[str] = None
    parameter_hash_gate: Optional[str] = None

    run_paths: Optional[RunPaths] = None
    dictionary_5a: Optional[dict] = None
    registry_5a: Optional[dict] = None
    schema_5a: Optional[dict] = None
    schema_layer1: Optional[dict] = None
    schema_layer2: Optional[dict] = None

    bundle_root: Optional[Path] = None
    index_path: Optional[Path] = None
    report_path: Optional[Path] = None
    issues_path: Optional[Path] = None
    flag_path: Optional[Path] = None
    run_report_path: Optional[Path] = None

    current_phase = "run_receipt"
    checks: dict[str, dict] = {}
    issues: list[dict] = []
    scenario_results: list[dict] = []
    counts: dict[str, object] = {}
    metrics: dict[str, object] = {}
    policy_versions: dict[str, object] = {}
    tokens: dict[str, str] = {}

    def _merge_metrics(existing: dict, updates: dict) -> dict:
        for key, value in updates.items():
            if value is None:
                continue
            if key not in existing:
                existing[key] = value
                continue
            old = existing[key]
            if isinstance(old, (int, float)) and isinstance(value, (int, float)):
                if key.startswith("max_") or key.endswith("_max") or "max" in key:
                    existing[key] = max(old, value)
                elif key.startswith("min_") or key.endswith("_min") or "min" in key:
                    existing[key] = min(old, value)
                elif key.endswith("_count") or key.endswith("_total") or key.startswith("count_") or key.startswith("n_"):
                    existing[key] = old + value
                else:
                    existing[key] = value
            else:
                existing[key] = value
        return existing

    def record_check(check_id: str, status_value: str, metrics_value: Optional[dict] = None) -> None:
        payload = checks.get(check_id)
        if payload is None:
            checks[check_id] = {
                "check_id": check_id,
                "status": status_value,
                "metrics": dict(metrics_value or {}),
            }
        else:
            payload["status"] = _status_worse(payload["status"], status_value)
            if metrics_value:
                payload["metrics"] = _merge_metrics(payload.get("metrics", {}), metrics_value)

    def record_issue(
        check_id: str,
        issue_code: str,
        severity: str,
        message: str,
        context: Optional[dict] = None,
        parameter_hash: Optional[str] = None,
        scenario_id: Optional[str] = None,
        segment: str = STATE,
    ) -> None:
        param_value = parameter_hash or parameter_hash_gate or parameter_hash_receipt or manifest_fingerprint or ""
        if not param_value and manifest_fingerprint:
            param_value = manifest_fingerprint
        issues.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint or ""),
                "parameter_hash": str(param_value),
                "scenario_id": scenario_id,
                "segment": segment,
                "check_id": check_id,
                "issue_code": issue_code,
                "severity": severity,
                "context": context or {},
                "message": message,
            }
        )

    def update_run_check(run_checks: dict, check_id: str, status_value: str) -> None:
        existing = run_checks.get(check_id, "PASS")
        run_checks[check_id] = _status_worse(existing, status_value)

    def _parse_major(value: Optional[str]) -> Optional[int]:
        text = _normalize_semver(value)
        if not text:
            return None
        parts = text.split(".")
        if not parts:
            return None
        try:
            return int(parts[0])
        except ValueError:
            return None

    try:
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = receipt.get("run_id")
        if not run_id_value:
            raise InputResolutionError("run_receipt missing run_id.")
        parameter_hash_receipt = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if not manifest_fingerprint:
            raise InputResolutionError("run_receipt missing manifest_fingerprint.")
        seed = int(receipt.get("seed")) if receipt.get("seed") is not None else None

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        logger.info("S5: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5a_path, dictionary_5a = load_dataset_dictionary(source, "5A")
        reg_5a_path, registry_5a = load_artefact_registry(source, "5A")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s",
            config.contracts_layout,
            config.contracts_root,
            dict_5a_path,
            reg_5a_path,
            ",".join([str(schema_5a_path), str(schema_layer1_path), str(schema_layer2_path)]),
        )

        tokens = {
            "run_id": str(run_id_value),
            "manifest_fingerprint": str(manifest_fingerprint),
        }
        if parameter_hash_receipt:
            tokens["parameter_hash"] = str(parameter_hash_receipt)

        logger.info(
            "S5: objective=validate S1-S4 outputs for manifest_fingerprint=%s; gated inputs "
            "(s0_gate_receipt_5A, sealed_inputs_5A, scenario configs, S1-S4 outputs) -> "
            "outputs (validation_bundle_5A, validation_bundle_index_5A, validation_report_5A, "
            "validation_issue_table_5A, validation_passed_flag_5A)",
            manifest_fingerprint,
        )
        timer.info("S5: phase begin")

        current_phase = "s0_gate"
        s0_payload: Optional[dict] = None
        sealed_inputs: list[dict] = []
        sealed_inputs_path: Optional[Path] = None
        sealed_inputs_digest: Optional[str] = None

        try:
            gate_entry = find_dataset_entry(dictionary_5a, DATASET_S0_GATE).entry
            gate_path = _resolve_dataset_path(gate_entry, run_paths, config.external_roots, tokens)
            s0_payload = _load_json(gate_path)
            _validate_payload(schema_5a, schema_layer1, schema_layer2, "validation/s0_gate_receipt_5A", s0_payload)
            if str(s0_payload.get("manifest_fingerprint")) != str(manifest_fingerprint):
                raise ContractError("s0_gate_receipt_5A manifest_fingerprint mismatch.")
            parameter_hash_gate = str(s0_payload.get("parameter_hash") or "")
            record_check(CHECK_S0_PRESENT, "PASS", {"gate_path": str(gate_path)})
        except Exception as exc:  # noqa: BLE001
            record_check(CHECK_S0_PRESENT, "FAIL", {"detail": str(exc)})
            record_issue(
                CHECK_S0_PRESENT,
                "S0_MISSING_OR_INVALID",
                "ERROR",
                "s0_gate_receipt_5A missing or invalid",
                {"error": str(exc)},
                segment="S0",
            )
            s0_payload = None

        current_phase = "sealed_inputs"
        try:
            sealed_entry = find_dataset_entry(dictionary_5a, DATASET_SEALED_INPUTS).entry
            sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
            sealed_payload = _load_json(sealed_inputs_path)
            _validate_payload(schema_5a, schema_layer1, schema_layer2, "validation/sealed_inputs_5A", sealed_payload)
            if not isinstance(sealed_payload, list):
                raise ContractError("sealed_inputs_5A payload is not a list.")
            sealed_inputs = [row for row in sealed_payload if isinstance(row, dict)]
            record_check(CHECK_S0_PRESENT, "PASS", {"sealed_inputs_path": str(sealed_inputs_path)})
        except Exception as exc:  # noqa: BLE001
            record_check(CHECK_S0_PRESENT, "FAIL", {"detail": str(exc)})
            record_issue(
                CHECK_S0_PRESENT,
                "S0_MISSING_OR_INVALID",
                "ERROR",
                "sealed_inputs_5A missing or invalid",
                {"error": str(exc)},
                segment="S0",
            )
            sealed_inputs = []

        if s0_payload and sealed_inputs:
            sealed_inputs_digest = _sealed_inputs_digest(sealed_inputs)
            expected_digest = s0_payload.get("sealed_inputs_digest")
            if sealed_inputs_digest != expected_digest:
                record_check(
                    CHECK_S0_DIGEST,
                    "FAIL",
                    {"expected": expected_digest, "actual": sealed_inputs_digest},
                )
                record_issue(
                    CHECK_S0_DIGEST,
                    "S0_SEALED_DIGEST_MISMATCH",
                    "ERROR",
                    "sealed_inputs_5A digest mismatch",
                    {"expected": expected_digest, "actual": sealed_inputs_digest},
                    segment="S0",
                )
            else:
                record_check(CHECK_S0_DIGEST, "PASS", {"digest": sealed_inputs_digest})
        else:
            record_check(CHECK_S0_DIGEST, "FAIL", {"detail": "missing s0_gate_receipt_5A or sealed_inputs_5A"})

        if s0_payload:
            upstream = s0_payload.get("verified_upstream_segments") or {}
            missing_segments: list[dict] = []
            for segment_id in ("1A", "1B", "2A", "2B", "3A", "3B"):
                entry = upstream.get(segment_id) or upstream.get(f"segment_{segment_id}") or {}
                status_value = entry.get("status")
                if status_value != "PASS":
                    missing_segments.append({"segment": segment_id, "status": status_value})
            if missing_segments:
                record_check(CHECK_UPSTREAM, "FAIL", {"missing_segments": missing_segments})
                record_issue(
                    CHECK_UPSTREAM,
                    "S0_UPSTREAM_NOT_PASS",
                    "ERROR",
                    "upstream segments not PASS per s0_gate_receipt_5A",
                    {"missing_segments": missing_segments},
                    segment="S0",
                )
            else:
                record_check(CHECK_UPSTREAM, "PASS", {"segments": list(upstream.keys())})
        else:
            record_check(CHECK_UPSTREAM, "FAIL", {"detail": "s0_gate_receipt_5A missing"})

        parameter_hashes = {value for value in [parameter_hash_gate, parameter_hash_receipt] if value}
        mismatched_params: list[str] = []
        for row in sealed_inputs:
            row_hash = row.get("parameter_hash")
            if row_hash:
                if parameter_hash_gate and row_hash != parameter_hash_gate:
                    mismatched_params.append(str(row_hash))
                parameter_hashes.add(str(row_hash))
            if row.get("manifest_fingerprint") and row.get("manifest_fingerprint") != manifest_fingerprint:
                record_check(CHECK_S0_PRESENT, "FAIL", {"detail": "manifest_fingerprint mismatch in sealed_inputs_5A"})
                record_issue(
                    CHECK_S0_PRESENT,
                    "S0_SEALED_IDENTITY_MISMATCH",
                    "ERROR",
                    "sealed_inputs_5A row manifest_fingerprint mismatch",
                    {"row_manifest": row.get("manifest_fingerprint")},
                    segment="S0",
                )
        if mismatched_params:
            record_check(CHECK_S0_PRESENT, "FAIL", {"parameter_hash_mismatch": mismatched_params})
            record_issue(
                CHECK_S0_PRESENT,
                "S0_PARAMETER_HASH_MISMATCH",
                "ERROR",
                "sealed_inputs_5A parameter_hash mismatch vs s0_gate_receipt_5A",
                {"mismatched_parameter_hashes": sorted(set(mismatched_params))},
                segment="S0",
            )

        sealed_by_id = {row.get("artifact_id"): row for row in sealed_inputs if isinstance(row, dict)}

        def _is_sealed(artifact_id: str) -> bool:
            row = sealed_by_id.get(artifact_id)
            if not row:
                return False
            return row.get("status") not in ("IGNORED",)

        def _resolve_sealed_path(artifact_id: str, local_tokens: dict[str, str]) -> Optional[Path]:
            if not _is_sealed(artifact_id):
                return None
            entry = find_dataset_entry(dictionary_5a, artifact_id).entry
            return _resolve_dataset_path(entry, run_paths, config.external_roots, local_tokens)

        def _resolve_output_path(artifact_id: str, local_tokens: dict[str, str]) -> Optional[Path]:
            entry = find_dataset_entry(dictionary_5a, artifact_id).entry
            path = _resolve_dataset_path(entry, run_paths, config.external_roots, local_tokens)
            if not path.exists():
                return None
            if not _is_sealed(artifact_id):
                logger.info("S5: %s not sealed; validating run output path=%s", artifact_id, path)
            return path

        current_phase = "policy_load"
        default_validation_policy = {
            "policy_id": "validation_policy_5A",
            "version": "v1.0.0",
            "tolerances": {
                "s2_shape_sum_abs_warn": 0.000001,
                "s2_shape_sum_abs_fail": 0.000010,
                "s3_weekly_sum_rel_fail": 0.000001,
                "s3_weekly_sum_abs_fail": 0.000001,
                "s3_rel_denominator_floor": 1.0,
                "s4_recompose_rel_fail": 0.000001,
                "s4_recompose_abs_fail": 0.000001,
                "s4_recompose_rel_denominator_floor": 1.0,
                "s4_local_vs_utc_total_rel_fail": 0.0,
                "s4_local_vs_utc_total_abs_fail": 0.0,
            },
            "bounds": {
                "overlay_factor_min_warn": 0.20,
                "overlay_factor_max_warn": 3.50,
                "overlay_low_warn_exempt_types": ["OUTAGE"],
                "lambda_scenario_max_per_bucket_warn": 10000000.0,
                "lambda_scenario_max_per_bucket_fail": 25000000.0,
            },
            "sampling": {
                "recompose_sample_mode": "minhash_top_n_v1",
                "recompose_sample_n": 2048,
                "recompose_hash_law": (
                    "hash64 = uint64_be(SHA256(\"5A.S5.recompose|\" + manifest_fingerprint + \"|\" + "
                    "parameter_hash + \"|\" + scenario_id + \"|\" + merchant_id + \"|\" + zone_key + \"|\" + "
                    "horizon_bucket_key)[0:8])"
                ),
            },
            "blocking": {
                "blocking_check_ids": [
                    CHECK_S0_PRESENT,
                    CHECK_S0_DIGEST,
                    CHECK_UPSTREAM,
                    CHECK_S1_PRESENT,
                    CHECK_S1_PK,
                    CHECK_S1_REQUIRED,
                    CHECK_S1_SCALE,
                    CHECK_S2_PRESENT,
                    CHECK_S2_GRID,
                    CHECK_S2_SHAPE_NONNEG,
                    CHECK_S2_SHAPE_SUM,
                    CHECK_S2_DOMAIN,
                    CHECK_S3_PRESENT,
                    CHECK_S3_DOMAIN,
                    CHECK_S3_LAMBDA,
                    CHECK_S3_WEEKLY,
                    CHECK_S4_PRESENT,
                    CHECK_S4_DOMAIN,
                    CHECK_S4_HORIZON,
                    CHECK_S4_LAMBDA,
                    CHECK_S4_OVERLAY_HARD,
                ],
                "nonblocking_check_ids": [
                    CHECK_S4_OVERLAY_WARN,
                    CHECK_S4_RECOMPOSE,
                    CHECK_S4_GUARDRAIL,
                    CHECK_S4_LOCAL_VS_UTC,
                ],
                "warn_is_blocking_check_ids": [],
                "unknown_check_id_posture": "fail_closed",
            },
        }

        validation_policy_path = _resolve_sealed_path(DATASET_VALIDATION_POLICY, tokens) if run_paths else None
        validation_policy = _load_policy(
            validation_policy_path,
            schema_5a,
            schema_layer1,
            schema_layer2,
            "validation/validation_policy_5A",
            logger,
        )
        if validation_policy is None:
            validation_policy = default_validation_policy
            policy_versions["validation_policy_5A"] = "default_v1"
        else:
            policy_versions["validation_policy_5A"] = validation_policy.get("version")

        blocking = validation_policy.get("blocking") or {}
        blocking_ids = set(blocking.get("blocking_check_ids") or [])
        nonblocking_ids = set(blocking.get("nonblocking_check_ids") or [])
        warn_blocking_ids = set(blocking.get("warn_is_blocking_check_ids") or [])
        unknown_posture = str(blocking.get("unknown_check_id_posture") or "fail_closed")

        def is_blocking(check_id: str) -> bool:
            if check_id in blocking_ids:
                return True
            if check_id in nonblocking_ids:
                return False
            return unknown_posture == "fail_closed"

        scenario_overlay_policy_path = _resolve_sealed_path(DATASET_OVERLAY_POLICY, tokens) if run_paths else None
        scenario_overlay_policy = _load_policy(
            scenario_overlay_policy_path,
            schema_5a,
            schema_layer1,
            schema_layer2,
            "scenario/scenario_overlay_policy_5A",
            logger,
        )
        if scenario_overlay_policy is not None:
            policy_versions["scenario_overlay_policy_5A"] = scenario_overlay_policy.get("version")

        scenario_horizon_path = _resolve_sealed_path(DATASET_SCENARIO_HORIZON, tokens) if run_paths else None
        scenario_horizon_config = _load_policy(
            scenario_horizon_path,
            schema_5a,
            schema_layer1,
            schema_layer2,
            "scenario/scenario_horizon_config_5A",
            logger,
        )
        if scenario_horizon_config is not None:
            policy_versions["scenario_horizon_config_5A"] = scenario_horizon_config.get("version")

        spec_compat_path = _resolve_sealed_path(DATASET_SPEC_COMPAT, tokens) if run_paths else None
        spec_compat_config = _load_policy(
            spec_compat_path,
            schema_5a,
            schema_layer1,
            schema_layer2,
            "validation/spec_compatibility_config_5A",
            logger,
        )
        if spec_compat_config is not None:
            policy_versions["spec_compatibility_config_5A"] = spec_compat_config.get("version")

        scenario_ids: list[str] = []
        scenario_manifest_path = _resolve_sealed_path(DATASET_SCENARIO_MANIFEST, tokens) if run_paths else None
        if scenario_manifest_path and scenario_manifest_path.exists():
            try:
                manifest_df = pl.read_parquet(scenario_manifest_path)
                _validate_array_rows(
                    manifest_df.iter_rows(named=True),
                    schema_5a,
                    schema_layer1,
                    schema_layer2,
                    "validation/scenario_manifest_5A",
                )
                scenario_ids = sorted(
                    [str(value) for value in manifest_df.get_column("scenario_id").unique()]
                )
                policy_versions["scenario_manifest_5A"] = "present"
            except Exception as exc:  # noqa: BLE001
                record_issue(
                    CHECK_S0_PRESENT,
                    "S5_SCENARIO_MANIFEST_INVALID",
                    "ERROR",
                    "scenario_manifest_5A invalid",
                    {"error": str(exc)},
                    segment="S0",
                )
                scenario_ids = []

        if not scenario_ids and scenario_horizon_config:
            scenario_ids = [str(row.get("scenario_id")) for row in scenario_horizon_config.get("scenarios", []) if row]

        if not scenario_ids and s0_payload:
            scenario_value = s0_payload.get("scenario_id")
            if isinstance(scenario_value, list):
                scenario_ids = [str(value) for value in scenario_value if value]
            elif scenario_value:
                scenario_ids = [str(scenario_value)]

        if not scenario_ids:
            record_check(CHECK_S0_PRESENT, "FAIL", {"detail": "no scenarios discovered"})
            record_issue(
                CHECK_S0_PRESENT,
                "S5_SCENARIO_DISCOVERY_FAILED",
                "ERROR",
                "no scenario_id values discovered for validation",
                segment="S0",
            )

        scenario_horizon_map = _scenario_horizon_map(scenario_horizon_config) if scenario_horizon_config else {}

        logger.info(
            "S5: discovered scenarios=%s parameter_hashes=%s",
            scenario_ids,
            sorted(parameter_hashes),
        )

        current_phase = "s1_check"
        s1_checks: dict[str, str] = {
            CHECK_S1_PRESENT: "FAIL",
            CHECK_S1_PK: "FAIL",
            CHECK_S1_REQUIRED: "FAIL",
            CHECK_S1_SCALE: "FAIL",
        }
        s1_domain_class: Optional[pl.LazyFrame] = None
        s1_domain_zone: Optional[pl.LazyFrame] = None
        s1_profile_scan: Optional[pl.LazyFrame] = None
        s1_profile_columns: list[str] = []
        profile_path = _resolve_output_path(DATASET_MERCHANT_PROFILE, tokens)
        if profile_path:
            profile_paths = _resolve_parquet_files(profile_path)
            s1_profile_scan = pl.scan_parquet([str(path) for path in profile_paths])
            s1_profile_columns = _scan_columns(s1_profile_scan)
            required_fields = _array_required_fields(
                schema_5a, schema_layer1, schema_layer2, "model/merchant_zone_profile_5A"
            )
            missing_cols = _ensure_required_columns(s1_profile_columns, required_fields)
            row_summary = s1_profile_scan.select(
                [
                    pl.count().alias("row_count"),
                    pl.struct(["merchant_id", "legal_country_iso", "tzid"]).n_unique().alias("pk_unique"),
                    pl.col("merchant_id").n_unique().alias("merchant_count"),
                    pl.col("legal_country_iso").n_unique().alias("country_count"),
                    pl.col("tzid").n_unique().alias("tz_count"),
                    pl.col("demand_class").is_null().sum().alias("demand_nulls"),
                    pl.col("weekly_volume_expected").is_null().sum().alias("weekly_nulls"),
                    (~pl.col("weekly_volume_expected").is_finite()).sum().alias("weekly_nonfinite"),
                    (pl.col("weekly_volume_expected") < 0).sum().alias("weekly_negative"),
                    pl.col("scale_factor").is_null().sum().alias("scale_nulls"),
                    (~pl.col("scale_factor").is_finite()).sum().alias("scale_nonfinite"),
                    (pl.col("scale_factor") < 0).sum().alias("scale_negative"),
                ]
            ).collect()
            row_count = int(row_summary["row_count"][0])
            pk_unique = int(row_summary["pk_unique"][0])
            demand_nulls = int(row_summary["demand_nulls"][0])
            weekly_nulls = int(row_summary["weekly_nulls"][0])
            weekly_nonfinite = int(row_summary["weekly_nonfinite"][0])
            weekly_negative = int(row_summary["weekly_negative"][0])
            scale_nulls = int(row_summary["scale_nulls"][0])
            scale_nonfinite = int(row_summary["scale_nonfinite"][0])
            scale_negative = int(row_summary["scale_negative"][0])

            counts["s1_rows"] = row_count
            counts["s1_merchants"] = int(row_summary["merchant_count"][0])
            counts["s1_countries"] = int(row_summary["country_count"][0])
            counts["s1_tzids"] = int(row_summary["tz_count"][0])

            if missing_cols:
                record_check(CHECK_S1_REQUIRED, "FAIL", {"missing_columns": missing_cols})
                record_issue(
                    CHECK_S1_REQUIRED,
                    "S1_SCHEMA_MISSING_FIELDS",
                    "ERROR",
                    "merchant_zone_profile_5A missing required columns",
                    {"missing_columns": missing_cols},
                    segment="S1",
                )
            else:
                s1_checks[CHECK_S1_REQUIRED] = "PASS" if demand_nulls == 0 else "FAIL"
                record_check(
                    CHECK_S1_REQUIRED,
                    s1_checks[CHECK_S1_REQUIRED],
                    {"demand_nulls": demand_nulls},
                )
                if demand_nulls:
                    record_issue(
                        CHECK_S1_REQUIRED,
                        "S1_REQUIRED_FIELD_NULL",
                        "ERROR",
                        "merchant_zone_profile_5A demand_class null",
                        {"null_count": demand_nulls},
                        segment="S1",
                    )

            pk_duplicates = max(row_count - pk_unique, 0)
            s1_checks[CHECK_S1_PK] = "PASS" if pk_duplicates == 0 else "FAIL"
            record_check(CHECK_S1_PK, s1_checks[CHECK_S1_PK], {"duplicate_pk": pk_duplicates})
            if pk_duplicates:
                record_issue(
                    CHECK_S1_PK,
                    "S1_PK_DUPLICATE",
                    "ERROR",
                    "merchant_zone_profile_5A PK duplicates",
                    {"duplicate_pk": pk_duplicates},
                    segment="S1",
                )

            both_missing = _count_invalid(
                s1_profile_scan,
                pl.col("weekly_volume_expected").is_null() & pl.col("scale_factor").is_null(),
            )
            scale_invalid = weekly_nonfinite + weekly_negative + scale_nonfinite + scale_negative + both_missing
            s1_checks[CHECK_S1_SCALE] = "PASS" if scale_invalid == 0 else "FAIL"
            record_check(
                CHECK_S1_SCALE,
                s1_checks[CHECK_S1_SCALE],
                {
                    "weekly_nulls": weekly_nulls,
                    "weekly_nonfinite": weekly_nonfinite,
                    "weekly_negative": weekly_negative,
                    "scale_nulls": scale_nulls,
                    "scale_nonfinite": scale_nonfinite,
                    "scale_negative": scale_negative,
                    "scale_missing_both": both_missing,
                },
            )
            if scale_invalid:
                record_issue(
                    CHECK_S1_SCALE,
                    "S1_SCALE_INVALID",
                    "ERROR",
                    "merchant_zone_profile_5A scale fields invalid",
                    {
                        "weekly_negative": weekly_negative,
                        "scale_negative": scale_negative,
                        "weekly_nonfinite": weekly_nonfinite,
                        "scale_nonfinite": scale_nonfinite,
                        "missing_both": both_missing,
                    },
                    segment="S1",
                )

            s1_checks[CHECK_S1_PRESENT] = "PASS"
            record_check(CHECK_S1_PRESENT, "PASS", {"path": str(profile_path)})

            s1_domain_class = s1_profile_scan.select(
                ["demand_class", "legal_country_iso", "tzid"]
            ).unique()
            s1_domain_zone_keys = ["merchant_id", "legal_country_iso", "tzid"]
            if "channel_group" in s1_profile_columns:
                s1_domain_zone_keys.append("channel_group")
            s1_domain_zone = s1_profile_scan.select(s1_domain_zone_keys).unique()
        else:
            record_check(CHECK_S1_PRESENT, "FAIL", {"detail": "merchant_zone_profile_5A missing"})
            record_issue(
                CHECK_S1_PRESENT,
                "S1_MISSING",
                "ERROR",
                "merchant_zone_profile_5A missing",
                segment="S1",
            )

        s1_spec_version: Optional[str] = None
        if s1_profile_scan is not None and "s1_spec_version" in s1_profile_columns:
            versions = (
                s1_profile_scan.select(pl.col("s1_spec_version").drop_nulls().unique())
                .collect()
                .get_column("s1_spec_version")
            )
            s1_spec_version = str(versions[0]) if len(versions) else None

        timer.info(
            "S5: phase input_load_schema_validation complete (scenarios=%s, s1_rows=%s)",
            len(scenario_ids),
            counts.get("s1_rows"),
        )

        current_phase = "per_scenario_checks"
        tolerances = validation_policy.get("tolerances") or {}
        bounds = validation_policy.get("bounds") or {}
        sampling = validation_policy.get("sampling") or {}

        s2_version_by_path: dict[str, Optional[str]] = {}
        s3_version_by_path: dict[str, Optional[str]] = {}

        for scenario_id in scenario_ids:
            run_checks: dict[str, str] = {}
            for check_id, check_status in s1_checks.items():
                update_run_check(run_checks, check_id, check_status)

            run_tokens = dict(tokens)
            if parameter_hash_gate:
                run_tokens["parameter_hash"] = parameter_hash_gate
            if scenario_id:
                run_tokens["scenario_id"] = str(scenario_id)

            grid_df: Optional[pl.DataFrame] = None
            grid_map: Optional[dict[tuple[int, int], int]] = None
            t_week: Optional[int] = None

            current_phase = "s2_check"
            grid_path = _resolve_output_path(DATASET_SHAPE_GRID, run_tokens)
            shape_path = _resolve_output_path(DATASET_CLASS_ZONE_SHAPE, run_tokens)
            if grid_path and shape_path:
                try:
                    grid_df = pl.read_parquet(grid_path).sort("bucket_index")
                    t_week = int(grid_df.height)
                    unique_bucket = grid_df.get_column("bucket_index").unique().len()
                    bucket_min = int(grid_df.get_column("bucket_index").min()) if t_week else 0
                    bucket_max = int(grid_df.get_column("bucket_index").max()) if t_week else -1
                    grid_valid = t_week > 0 and unique_bucket == t_week and bucket_min == 0 and bucket_max == t_week - 1
                    grid_status = "PASS" if grid_valid else "FAIL"
                    record_check(
                        CHECK_S2_GRID,
                        grid_status,
                        {
                            "bucket_count": t_week,
                            "bucket_min": bucket_min,
                            "bucket_max": bucket_max,
                            "unique_bucket": unique_bucket,
                        },
                    )
                    update_run_check(run_checks, CHECK_S2_GRID, grid_status)
                    if not grid_valid:
                        record_issue(
                            CHECK_S2_GRID,
                            "S2_GRID_INVALID",
                            "ERROR",
                            "shape_grid_definition_5A bucket_index invalid",
                            {
                                "bucket_min": bucket_min,
                                "bucket_max": bucket_max,
                                "unique_bucket": unique_bucket,
                            },
                            scenario_id=str(scenario_id),
                            segment="S2",
                        )
                    grid_map = _grid_lookup(grid_df) if grid_valid else None

                    shape_paths = _resolve_parquet_files(shape_path)
                    shape_scan = pl.scan_parquet([str(path) for path in shape_paths])
                    shape_columns = _scan_columns(shape_scan)
                    shape_required = _array_required_fields(
                        schema_5a, schema_layer1, schema_layer2, "model/class_zone_shape_5A"
                    )
                    shape_missing = _ensure_required_columns(shape_columns, shape_required)
                    if shape_missing:
                        record_check(CHECK_S2_PRESENT, "FAIL", {"missing_columns": shape_missing})
                        update_run_check(run_checks, CHECK_S2_PRESENT, "FAIL")
                        record_issue(
                            CHECK_S2_PRESENT,
                            "S2_SCHEMA_MISSING_FIELDS",
                            "ERROR",
                            "class_zone_shape_5A missing required columns",
                            {"missing_columns": shape_missing},
                            scenario_id=str(scenario_id),
                            segment="S2",
                        )
                    else:
                        record_check(CHECK_S2_PRESENT, "PASS", {"path": str(shape_path)})
                        update_run_check(run_checks, CHECK_S2_PRESENT, "PASS")

                    neg_shapes = _count_invalid(shape_scan, pl.col("shape_value") < 0)
                    nonfinite_shapes = _count_invalid(shape_scan, ~pl.col("shape_value").is_finite())
                    shape_nonneg_status = "PASS" if (neg_shapes + nonfinite_shapes) == 0 else "FAIL"
                    record_check(
                        CHECK_S2_SHAPE_NONNEG,
                        shape_nonneg_status,
                        {"negative": neg_shapes, "nonfinite": nonfinite_shapes},
                    )
                    update_run_check(run_checks, CHECK_S2_SHAPE_NONNEG, shape_nonneg_status)

                    shape_group_keys = ["demand_class", "legal_country_iso", "tzid"]
                    if "channel_group" in shape_columns:
                        shape_group_keys.append("channel_group")
                    shape_group = shape_scan.group_by(shape_group_keys).agg(
                        pl.col("shape_value").sum().alias("shape_sum")
                    )
                    warn_tol = float(tolerances.get("s2_shape_sum_abs_warn") or 0.0)
                    fail_tol = float(tolerances.get("s2_shape_sum_abs_fail") or 0.0)
                    shape_stats = shape_group.select(
                        [
                            (pl.col("shape_sum") - 1.0).abs().max().alias("max_abs_err"),
                            ((pl.col("shape_sum") - 1.0).abs() > warn_tol).sum().alias("warn_count"),
                            ((pl.col("shape_sum") - 1.0).abs() > fail_tol).sum().alias("fail_count"),
                        ]
                    ).collect()
                    max_abs_err = float(shape_stats["max_abs_err"][0] or 0.0)
                    warn_count = int(shape_stats["warn_count"][0] or 0)
                    fail_count = int(shape_stats["fail_count"][0] or 0)
                    sum_status = _status_from_error(max_abs_err, warn_tol, fail_tol)
                    record_check(
                        CHECK_S2_SHAPE_SUM,
                        sum_status,
                        {"max_abs_err": max_abs_err, "warn_count": warn_count, "fail_count": fail_count},
                    )
                    update_run_check(run_checks, CHECK_S2_SHAPE_SUM, sum_status)
                    if fail_count:
                        record_issue(
                            CHECK_S2_SHAPE_SUM,
                            "S2_SHAPE_SUM_INVALID",
                            "ERROR",
                            "shape_value sums deviate from 1",
                            {"fail_count": fail_count, "max_abs_err": max_abs_err},
                            scenario_id=str(scenario_id),
                            segment="S2",
                        )

                    if s1_domain_class is not None:
                        s2_domain = shape_scan.select(shape_group_keys).unique()
                        if "channel_group" in shape_group_keys:
                            s2_domain = s2_domain.select(["demand_class", "legal_country_iso", "tzid"]).unique()
                        missing_domain = s1_domain_class.join(
                            s2_domain,
                            on=["demand_class", "legal_country_iso", "tzid"],
                            how="anti",
                        ).collect()
                        missing_count = int(missing_domain.height)
                        domain_status = "PASS" if missing_count == 0 else "FAIL"
                        record_check(
                            CHECK_S2_DOMAIN,
                            domain_status,
                            {"missing_class_zone": missing_count},
                        )
                        update_run_check(run_checks, CHECK_S2_DOMAIN, domain_status)
                        if missing_count:
                            record_issue(
                                CHECK_S2_DOMAIN,
                                "S2_DOMAIN_MISSING",
                                "ERROR",
                                "class_zone_shape_5A missing S1 domain entries",
                                {"missing_count": missing_count},
                                scenario_id=str(scenario_id),
                                segment="S2",
                            )
                except Exception as exc:  # noqa: BLE001
                    record_check(CHECK_S2_PRESENT, "FAIL", {"detail": str(exc)})
                    update_run_check(run_checks, CHECK_S2_PRESENT, "FAIL")
                    record_issue(
                        CHECK_S2_PRESENT,
                        "S2_IO_READ_FAILED",
                        "ERROR",
                        "S2 inputs could not be read",
                        {"error": str(exc)},
                        scenario_id=str(scenario_id),
                        segment="S2",
                    )
            else:
                record_check(CHECK_S2_PRESENT, "FAIL", {"detail": "S2 outputs missing"})
                update_run_check(run_checks, CHECK_S2_PRESENT, "FAIL")
                record_issue(
                    CHECK_S2_PRESENT,
                    "S2_MISSING",
                    "ERROR",
                    "shape_grid_definition_5A or class_zone_shape_5A missing",
                    {"grid_path": str(grid_path), "shape_path": str(shape_path)},
                    scenario_id=str(scenario_id),
                    segment="S2",
                )
            current_phase = "s3_check"
            baseline_scan: Optional[pl.LazyFrame] = None
            baseline_columns: list[str] = []
            baseline_keys: list[str] = ["merchant_id", "legal_country_iso", "tzid"]
            baseline_path = _resolve_output_path(DATASET_BASELINE_LOCAL, run_tokens)
            if baseline_path:
                try:
                    baseline_paths = _resolve_parquet_files(baseline_path)
                    baseline_scan = pl.scan_parquet([str(path) for path in baseline_paths])
                    baseline_columns = _scan_columns(baseline_scan)
                    if "channel_group" in baseline_columns:
                        baseline_keys.append("channel_group")
                    baseline_required = _array_required_fields(
                        schema_5a, schema_layer1, schema_layer2, "model/merchant_zone_baseline_local_5A"
                    )
                    baseline_missing = _ensure_required_columns(baseline_columns, baseline_required)
                    if baseline_missing:
                        record_check(CHECK_S3_PRESENT, "FAIL", {"missing_columns": baseline_missing})
                        update_run_check(run_checks, CHECK_S3_PRESENT, "FAIL")
                        record_issue(
                            CHECK_S3_PRESENT,
                            "S3_SCHEMA_MISSING_FIELDS",
                            "ERROR",
                            "merchant_zone_baseline_local_5A missing required columns",
                            {"missing_columns": baseline_missing},
                            scenario_id=str(scenario_id),
                            segment="S3",
                        )
                    else:
                        record_check(CHECK_S3_PRESENT, "PASS", {"path": str(baseline_path)})
                        update_run_check(run_checks, CHECK_S3_PRESENT, "PASS")

                        invalid_lambda = _count_invalid(baseline_scan, pl.col("lambda_local_base") < 0)
                        invalid_lambda += _count_invalid(baseline_scan, ~pl.col("lambda_local_base").is_finite())
                        lambda_status = "PASS" if invalid_lambda == 0 else "FAIL"
                        record_check(CHECK_S3_LAMBDA, lambda_status, {"invalid_lambda": invalid_lambda})
                        update_run_check(run_checks, CHECK_S3_LAMBDA, lambda_status)
                        if invalid_lambda:
                            record_issue(
                                CHECK_S3_LAMBDA,
                                "S3_LAMBDA_INVALID",
                                "ERROR",
                                "lambda_local_base negative or non-finite",
                                {"invalid_lambda": invalid_lambda},
                                scenario_id=str(scenario_id),
                                segment="S3",
                            )

                        if t_week is not None and t_week > 0:
                            bucket_counts = baseline_scan.group_by(baseline_keys).agg(
                                pl.col("bucket_index").n_unique().alias("bucket_count")
                            )
                            invalid_buckets = bucket_counts.filter(pl.col("bucket_count") != t_week).collect()
                            invalid_bucket_count = int(invalid_buckets.height)
                            domain_status = "PASS" if invalid_bucket_count == 0 else "FAIL"
                            record_check(
                                CHECK_S3_DOMAIN,
                                domain_status,
                                {"invalid_bucket_groups": invalid_bucket_count, "expected": t_week},
                            )
                            update_run_check(run_checks, CHECK_S3_DOMAIN, domain_status)
                            if invalid_bucket_count:
                                record_issue(
                                    CHECK_S3_DOMAIN,
                                    "S3_DOMAIN_BUCKET_MISMATCH",
                                    "ERROR",
                                    "baseline bucket coverage mismatch",
                                    {"invalid_bucket_groups": invalid_bucket_count, "expected": t_week},
                                    scenario_id=str(scenario_id),
                                    segment="S3",
                                )
                        else:
                            record_check(CHECK_S3_DOMAIN, "FAIL", {"detail": "missing shape grid"})
                            update_run_check(run_checks, CHECK_S3_DOMAIN, "FAIL")

                        if s1_domain_zone is not None:
                            s1_zone = s1_domain_zone
                            if "channel_group" in baseline_keys and "channel_group" not in s1_profile_columns:
                                s1_zone = s1_zone.with_columns(pl.lit("mixed").alias("channel_group"))
                            baseline_domain = baseline_scan.select(baseline_keys).unique()
                            missing_domain = s1_zone.join(baseline_domain, on=baseline_keys, how="anti").collect()
                            missing_count = int(missing_domain.height)
                            if missing_count:
                                record_check(
                                    CHECK_S3_DOMAIN,
                                    "FAIL",
                                    {"missing_domain_rows": missing_count},
                                )
                                update_run_check(run_checks, CHECK_S3_DOMAIN, "FAIL")
                                record_issue(
                                    CHECK_S3_DOMAIN,
                                    "S3_DOMAIN_MISSING",
                                    "ERROR",
                                    "baseline missing S1 domain rows",
                                    {"missing_count": missing_count},
                                    scenario_id=str(scenario_id),
                                    segment="S3",
                                )

                        weekly_rel_fail = float(tolerances.get("s3_weekly_sum_rel_fail") or 0.0)
                        weekly_abs_fail = float(tolerances.get("s3_weekly_sum_abs_fail") or 0.0)
                        rel_floor = float(tolerances.get("s3_rel_denominator_floor") or 0.0)
                        weekly_group = baseline_scan.group_by(baseline_keys).agg(
                            [
                                pl.col("lambda_local_base").sum().alias("sum_lambda"),
                                pl.col("weekly_volume_expected").first().alias("weekly_volume_expected"),
                            ]
                        )
                        weekly_calc = weekly_group.with_columns(
                            [
                                (pl.col("sum_lambda") - pl.col("weekly_volume_expected")).abs().alias("abs_err"),
                                (
                                    (pl.col("sum_lambda") - pl.col("weekly_volume_expected")).abs()
                                    / pl.max_horizontal(
                                        pl.col("weekly_volume_expected").abs(),
                                        pl.lit(rel_floor),
                                    )
                                ).alias("rel_err"),
                            ]
                        )
                        weekly_stats = weekly_calc.select(
                            [
                                pl.col("abs_err").max().alias("max_abs_err"),
                                pl.col("rel_err").max().alias("max_rel_err"),
                                (
                                    (pl.col("abs_err") > weekly_abs_fail)
                                    & (pl.col("rel_err") > weekly_rel_fail)
                                )
                                .sum()
                                .alias("fail_count"),
                            ]
                        ).collect()
                        weekly_fail_count = int(weekly_stats["fail_count"][0] or 0)
                        weekly_status = "PASS" if weekly_fail_count == 0 else "FAIL"
                        record_check(
                            CHECK_S3_WEEKLY,
                            weekly_status,
                            {
                                "max_abs_err": float(weekly_stats["max_abs_err"][0] or 0.0),
                                "max_rel_err": float(weekly_stats["max_rel_err"][0] or 0.0),
                                "fail_count": weekly_fail_count,
                            },
                        )
                        update_run_check(run_checks, CHECK_S3_WEEKLY, weekly_status)
                        if weekly_fail_count:
                            record_issue(
                                CHECK_S3_WEEKLY,
                                "S3_WEEKLY_SUM_MISMATCH",
                                "ERROR",
                                "weekly sum vs scale mismatch",
                                {"fail_count": weekly_fail_count},
                                scenario_id=str(scenario_id),
                                segment="S3",
                            )
                except Exception as exc:  # noqa: BLE001
                    record_check(CHECK_S3_PRESENT, "FAIL", {"detail": str(exc)})
                    update_run_check(run_checks, CHECK_S3_PRESENT, "FAIL")
                    record_issue(
                        CHECK_S3_PRESENT,
                        "S3_IO_READ_FAILED",
                        "ERROR",
                        "S3 inputs could not be read",
                        {"error": str(exc)},
                        scenario_id=str(scenario_id),
                        segment="S3",
                    )
            else:
                record_check(CHECK_S3_PRESENT, "FAIL", {"detail": "S3 output missing"})
                update_run_check(run_checks, CHECK_S3_PRESENT, "FAIL")
                record_issue(
                    CHECK_S3_PRESENT,
                    "S3_MISSING",
                    "ERROR",
                    "merchant_zone_baseline_local_5A missing",
                    scenario_id=str(scenario_id),
                    segment="S3",
                )

            current_phase = "s4_check"
            scenario_scan: Optional[pl.LazyFrame] = None
            scenario_paths: list[Path] = []
            scenario_columns: list[str] = []
            scenario_keys: list[str] = ["merchant_id", "legal_country_iso", "tzid"]
            overlay_scan: Optional[pl.LazyFrame] = None
            include_channel_group = False
            overlay_min = None
            overlay_max = None
            horizon_info = scenario_horizon_map.get(str(scenario_id))
            scenario_path = _resolve_output_path(DATASET_SCENARIO_LOCAL, run_tokens)
            if scenario_path:
                try:
                    scenario_paths = _resolve_parquet_files(scenario_path)
                    scenario_scan = pl.scan_parquet([str(path) for path in scenario_paths])
                    scenario_columns = _scan_columns(scenario_scan)
                    if "channel_group" in scenario_columns:
                        scenario_keys.append("channel_group")
                        include_channel_group = True

                    scenario_required = _array_required_fields(
                        schema_5a, schema_layer1, schema_layer2, "model/merchant_zone_scenario_local_5A"
                    )
                    scenario_missing = _ensure_required_columns(scenario_columns, scenario_required)
                    if scenario_missing:
                        record_check(CHECK_S4_PRESENT, "FAIL", {"missing_columns": scenario_missing})
                        update_run_check(run_checks, CHECK_S4_PRESENT, "FAIL")
                        record_issue(
                            CHECK_S4_PRESENT,
                            "S4_SCHEMA_MISSING_FIELDS",
                            "ERROR",
                            "merchant_zone_scenario_local_5A missing required columns",
                            {"missing_columns": scenario_missing},
                            scenario_id=str(scenario_id),
                            segment="S4",
                        )
                    else:
                        record_check(CHECK_S4_PRESENT, "PASS", {"path": str(scenario_path)})
                        update_run_check(run_checks, CHECK_S4_PRESENT, "PASS")

                        scenario_stats = scenario_scan.select(
                            [
                                (pl.col("lambda_local_scenario") < 0).cast(pl.UInt64).sum().alias("lambda_negative"),
                                (~pl.col("lambda_local_scenario").is_finite())
                                .cast(pl.UInt64)
                                .sum()
                                .alias("lambda_nonfinite"),
                                pl.col("lambda_local_scenario").max().alias("max_lambda"),
                                pl.col("lambda_local_scenario").sum().alias("sum_local_lambda"),
                            ]
                        ).collect()
                        lambda_negative = int(scenario_stats["lambda_negative"][0] or 0)
                        lambda_nonfinite = int(scenario_stats["lambda_nonfinite"][0] or 0)
                        max_lambda = float(scenario_stats["max_lambda"][0] or 0.0)
                        total_local_scenario = float(scenario_stats["sum_local_lambda"][0] or 0.0)
                        invalid_lambda = lambda_negative + lambda_nonfinite
                        lambda_status = "PASS" if invalid_lambda == 0 else "FAIL"
                        record_check(CHECK_S4_LAMBDA, lambda_status, {"invalid_lambda": invalid_lambda})
                        update_run_check(run_checks, CHECK_S4_LAMBDA, lambda_status)
                        if invalid_lambda:
                            record_issue(
                                CHECK_S4_LAMBDA,
                                "S4_LAMBDA_INVALID",
                                "ERROR",
                                "lambda_local_scenario negative or non-finite",
                                {"invalid_lambda": invalid_lambda},
                                scenario_id=str(scenario_id),
                                segment="S4",
                            )

                        if horizon_info:
                            horizon_count = int(horizon_info["bucket_count"])
                            bucket_counts = scenario_scan.group_by(scenario_keys).agg(
                                pl.col("local_horizon_bucket_index").n_unique().alias("bucket_count")
                            )
                            invalid_buckets = bucket_counts.filter(pl.col("bucket_count") != horizon_count).collect()
                            invalid_bucket_count = int(invalid_buckets.height)
                            horizon_status = "PASS" if invalid_bucket_count == 0 else "FAIL"
                            record_check(
                                CHECK_S4_HORIZON,
                                horizon_status,
                                {"invalid_bucket_groups": invalid_bucket_count, "expected": horizon_count},
                            )
                            update_run_check(run_checks, CHECK_S4_HORIZON, horizon_status)
                            if invalid_bucket_count:
                                record_issue(
                                    CHECK_S4_HORIZON,
                                    "S4_HORIZON_BUCKET_MISMATCH",
                                    "ERROR",
                                    "scenario horizon bucket coverage mismatch",
                                    {"invalid_bucket_groups": invalid_bucket_count, "expected": horizon_count},
                                    scenario_id=str(scenario_id),
                                    segment="S4",
                                )
                        else:
                            record_check(CHECK_S4_HORIZON, "FAIL", {"detail": "missing horizon config"})
                            update_run_check(run_checks, CHECK_S4_HORIZON, "FAIL")

                        if baseline_scan is not None:
                            baseline_domain = baseline_scan.select(baseline_keys).unique()
                            scenario_domain = scenario_scan.select(scenario_keys).unique()
                            missing_domain = baseline_domain.join(scenario_domain, on=scenario_keys, how="anti").collect()
                            missing_count = int(missing_domain.height)
                            domain_status = "PASS" if missing_count == 0 else "FAIL"
                            record_check(
                                CHECK_S4_DOMAIN,
                                domain_status,
                                {"missing_domain_rows": missing_count},
                            )
                            update_run_check(run_checks, CHECK_S4_DOMAIN, domain_status)
                            if missing_count:
                                record_issue(
                                    CHECK_S4_DOMAIN,
                                    "S4_DOMAIN_MISSING",
                                    "ERROR",
                                    "scenario_local missing baseline domain rows",
                                    {"missing_count": missing_count},
                                    scenario_id=str(scenario_id),
                                    segment="S4",
                                )

                        if scenario_overlay_policy:
                            overlay_min = float(scenario_overlay_policy.get("combination", {}).get("min_factor"))
                            overlay_max = float(scenario_overlay_policy.get("combination", {}).get("max_factor"))
                        if "overlay_factor_total" in scenario_columns:
                            overlay_scan = scenario_scan.select(
                                scenario_keys + ["local_horizon_bucket_index", "overlay_factor_total"]
                            )
                        else:
                            overlay_path = _resolve_output_path(DATASET_OVERLAY_FACTORS, run_tokens)
                            if overlay_path:
                                overlay_paths = _resolve_parquet_files(overlay_path)
                                overlay_scan = pl.scan_parquet([str(path) for path in overlay_paths])
                            else:
                                overlay_scan = None

                        warn_min = bounds.get("overlay_factor_min_warn")
                        warn_max = bounds.get("overlay_factor_max_warn")
                        warn_min = float(warn_min) if warn_min is not None else None
                        warn_max = float(warn_max) if warn_max is not None else None

                        overlay_hard_violations: Optional[int] = None
                        overlay_warn_violations: Optional[int] = None
                        if overlay_scan is not None:
                            hard_expr = (
                                (pl.col("overlay_factor_total") < overlay_min)
                                | (pl.col("overlay_factor_total") > overlay_max)
                            ) if (overlay_min is not None and overlay_max is not None) else None
                            warn_expr = (
                                (pl.col("overlay_factor_total") < (warn_min if warn_min is not None else -1.0))
                                | (pl.col("overlay_factor_total") > (warn_max if warn_max is not None else 1.0e18))
                            )
                            overlay_stats = overlay_scan.select(
                                [
                                    (
                                        hard_expr.cast(pl.UInt64).sum().alias("hard_violations")
                                        if hard_expr is not None
                                        else pl.lit(None, dtype=pl.UInt64).alias("hard_violations")
                                    ),
                                    warn_expr.cast(pl.UInt64).sum().alias("warn_violations"),
                                ]
                            ).collect()
                            hard_val = overlay_stats["hard_violations"][0]
                            warn_val = overlay_stats["warn_violations"][0]
                            overlay_hard_violations = int(hard_val) if hard_val is not None else None
                            overlay_warn_violations = int(warn_val) if warn_val is not None else 0

                        if overlay_scan is not None and overlay_min is not None and overlay_max is not None:
                            hard_violations = int(overlay_hard_violations or 0)
                            hard_status = "PASS" if hard_violations == 0 else "FAIL"
                            record_check(
                                CHECK_S4_OVERLAY_HARD,
                                hard_status,
                                {"violations": hard_violations, "min_factor": overlay_min, "max_factor": overlay_max},
                            )
                            update_run_check(run_checks, CHECK_S4_OVERLAY_HARD, hard_status)
                            if hard_violations:
                                record_issue(
                                    CHECK_S4_OVERLAY_HARD,
                                    "S4_OVERLAY_HARD_BOUNDS",
                                    "ERROR",
                                    "overlay_factor_total outside hard bounds",
                                    {"violations": hard_violations, "min_factor": overlay_min, "max_factor": overlay_max},
                                    scenario_id=str(scenario_id),
                                    segment="S4",
                                )
                        elif overlay_scan is not None:
                            record_check(CHECK_S4_OVERLAY_HARD, "FAIL", {"detail": "missing overlay hard bounds"})
                            update_run_check(run_checks, CHECK_S4_OVERLAY_HARD, "FAIL")

                        if overlay_scan is not None:
                            warn_violations = int(overlay_warn_violations or 0)
                            warn_status = "PASS" if warn_violations == 0 else "WARN"
                            record_check(
                                CHECK_S4_OVERLAY_WARN,
                                warn_status,
                                {"warn_violations": warn_violations},
                            )
                            update_run_check(run_checks, CHECK_S4_OVERLAY_WARN, warn_status)
                            if warn_violations:
                                record_issue(
                                    CHECK_S4_OVERLAY_WARN,
                                    "S4_OVERLAY_WARN_BOUNDS",
                                    "WARN",
                                    "overlay_factor_total outside warn corridor (exemptions not applied)",
                                    {"warn_violations": warn_violations},
                                    scenario_id=str(scenario_id),
                                    segment="S4",
                                )

                        guardrail_warn = float(bounds.get("lambda_scenario_max_per_bucket_warn") or 0.0)
                        guardrail_fail = float(bounds.get("lambda_scenario_max_per_bucket_fail") or 0.0)
                        if guardrail_fail and max_lambda > guardrail_fail:
                            guard_status = "FAIL"
                        elif guardrail_warn and max_lambda > guardrail_warn:
                            guard_status = "WARN"
                        else:
                            guard_status = "PASS"
                        record_check(
                            CHECK_S4_GUARDRAIL,
                            guard_status,
                            {"max_lambda": max_lambda},
                        )
                        update_run_check(run_checks, CHECK_S4_GUARDRAIL, guard_status)

                        if horizon_info and grid_map is not None:
                            tzids = scenario_scan.select(pl.col("tzid").unique()).collect()
                            missing_map = 0
                            for tzid in tzids.get_column("tzid"):
                                for bucket_idx in range(int(horizon_info["bucket_count"])):
                                    if _bucket_index_for_row(
                                        str(tzid),
                                        horizon_info["horizon_start"],
                                        int(horizon_info["bucket_minutes"]),
                                        bucket_idx,
                                        grid_map,
                                    ) is None:
                                        missing_map += 1
                                        break
                            if missing_map:
                                record_check(
                                    CHECK_S4_HORIZON,
                                    "FAIL",
                                    {"missing_time_mappings": missing_map},
                                )
                                update_run_check(run_checks, CHECK_S4_HORIZON, "FAIL")
                                record_issue(
                                    CHECK_S4_HORIZON,
                                    "S4_HORIZON_MAPPING_MISSING",
                                    "ERROR",
                                    "horizon buckets could not map to shape grid",
                                    {"missing_time_mappings": missing_map},
                                    scenario_id=str(scenario_id),
                                    segment="S4",
                                )

                        if overlay_scan is not None and baseline_scan is not None and horizon_info and grid_map:
                            sample_n = int(sampling.get("recompose_sample_n") or 0)
                            prefix = (
                                f"5A.S5.recompose|{manifest_fingerprint}|{parameter_hash_gate}|{scenario_id}|".encode(
                                    "ascii"
                                )
                            )
                            sample_rows = _minhash_sample(
                                scenario_paths,
                                sample_n,
                                prefix,
                                logger,
                                include_channel_group=include_channel_group,
                            )
                            sample_key_cols = [
                                "merchant_id",
                                "legal_country_iso",
                                "tzid",
                                "local_horizon_bucket_index",
                            ]
                            if include_channel_group:
                                sample_key_cols.append("channel_group")

                            sample_with_bucket: list[dict] = []
                            missing_bucket = 0
                            for row in sample_rows:
                                bucket_index = _bucket_index_for_row(
                                    str(row["tzid"]),
                                    horizon_info["horizon_start"],
                                    int(horizon_info["bucket_minutes"]),
                                    int(row["local_horizon_bucket_index"]),
                                    grid_map,
                                )
                                if bucket_index is None:
                                    missing_bucket += 1
                                    continue
                                row_copy = dict(row)
                                row_copy["bucket_index"] = int(bucket_index)
                                sample_with_bucket.append(row_copy)
                            if missing_bucket:
                                record_check(CHECK_S4_RECOMPOSE, "FAIL", {"missing_bucket": missing_bucket})
                                update_run_check(run_checks, CHECK_S4_RECOMPOSE, "FAIL")
                            elif sample_with_bucket:
                                sample_schema_overrides = {
                                    "merchant_id": pl.UInt64,
                                    "legal_country_iso": pl.Utf8,
                                    "tzid": pl.Utf8,
                                    "local_horizon_bucket_index": pl.Int64,
                                    "bucket_index": pl.Int64,
                                    "lambda_local_scenario": pl.Float64,
                                    "overlay_factor_total": pl.Float64,
                                }
                                if include_channel_group:
                                    sample_schema_overrides["channel_group"] = pl.Utf8
                                sample_df = pl.DataFrame(
                                    sample_with_bucket,
                                    schema_overrides=sample_schema_overrides,
                                )
                                join_keys = ["merchant_id", "legal_country_iso", "tzid"]
                                if include_channel_group:
                                    join_keys.append("channel_group")
                                join_keys.append("bucket_index")
                                abs_fail = float(tolerances.get("s4_recompose_abs_fail") or 0.0)
                                rel_fail = float(tolerances.get("s4_recompose_rel_fail") or 0.0)
                                rel_floor = float(tolerances.get("s4_recompose_rel_denominator_floor") or 0.0)
                                sample_eval = (
                                    sample_df.lazy()
                                    .join(
                                        baseline_scan.select(join_keys + ["lambda_local_base"]),
                                        on=join_keys,
                                        how="left",
                                    )
                                    .with_columns(
                                        [
                                            (pl.col("lambda_local_base") * pl.col("overlay_factor_total"))
                                            .alias("expected_lambda"),
                                            (pl.col("lambda_local_scenario") - pl.col("lambda_local_base") * pl.col("overlay_factor_total"))
                                            .abs()
                                            .alias("abs_err"),
                                        ]
                                    )
                                    .with_columns(
                                        (
                                            pl.col("abs_err")
                                            / pl.max_horizontal(
                                                pl.col("lambda_local_scenario").abs(),
                                                pl.lit(rel_floor),
                                            )
                                        ).alias("rel_err")
                                    )
                                    .collect()
                                )
                                missing_baseline = int(sample_eval.filter(pl.col("lambda_local_base").is_null()).height)
                                if missing_baseline:
                                    record_check(
                                        CHECK_S4_RECOMPOSE,
                                        "FAIL",
                                        {"missing_baseline": missing_baseline},
                                    )
                                    update_run_check(run_checks, CHECK_S4_RECOMPOSE, "FAIL")
                                else:
                                    recomposition_stats = sample_eval.select(
                                        [
                                            pl.col("abs_err").max().alias("max_abs_err"),
                                            pl.col("rel_err").max().alias("max_rel_err"),
                                            ((pl.col("abs_err") > abs_fail) & (pl.col("rel_err") > rel_fail))
                                            .cast(pl.UInt64)
                                            .sum()
                                            .alias("fail_count"),
                                        ]
                                    )
                                    max_abs_err = float(recomposition_stats["max_abs_err"][0] or 0.0)
                                    max_rel_err = float(recomposition_stats["max_rel_err"][0] or 0.0)
                                    fail_count = int(recomposition_stats["fail_count"][0] or 0)
                                    recomposition_status = "PASS" if fail_count == 0 else "FAIL"
                                    record_check(
                                        CHECK_S4_RECOMPOSE,
                                        recomposition_status,
                                        {
                                            "sample_n": len(sample_with_bucket),
                                            "fail_count": fail_count,
                                            "max_abs_err": max_abs_err,
                                            "max_rel_err": max_rel_err,
                                        },
                                    )
                                    update_run_check(run_checks, CHECK_S4_RECOMPOSE, recomposition_status)

                        utc_path = _resolve_output_path(DATASET_SCENARIO_UTC, run_tokens)
                        if utc_path:
                            utc_paths = _resolve_parquet_files(utc_path)
                            utc_scan = pl.scan_parquet([str(path) for path in utc_paths])
                            total_utc = utc_scan.select(
                                pl.col("lambda_utc_scenario").sum().alias("total_utc")
                            ).collect()["total_utc"][0]
                            total_local = total_local_scenario
                            total_utc = float(total_utc or 0.0)
                            abs_err = abs(total_local - total_utc)
                            rel_floor = float(tolerances.get("s4_local_vs_utc_total_rel_fail") or 0.0)
                            abs_fail = float(tolerances.get("s4_local_vs_utc_total_abs_fail") or 0.0)
                            rel_err = abs_err / max(abs(total_local), rel_floor) if rel_floor > 0 else 0.0
                            if abs_fail and rel_floor and abs_err > abs_fail and rel_err > rel_floor:
                                status_val = "FAIL"
                            else:
                                status_val = "PASS"
                            record_check(
                                CHECK_S4_LOCAL_VS_UTC,
                                status_val,
                                {
                                    "total_local": total_local,
                                    "total_utc": total_utc,
                                    "abs_err": abs_err,
                                    "rel_err": rel_err,
                                },
                            )
                            update_run_check(run_checks, CHECK_S4_LOCAL_VS_UTC, status_val)
                except Exception as exc:  # noqa: BLE001
                    record_check(CHECK_S4_PRESENT, "FAIL", {"detail": str(exc)})
                    update_run_check(run_checks, CHECK_S4_PRESENT, "FAIL")
                    record_issue(
                        CHECK_S4_PRESENT,
                        "S4_IO_READ_FAILED",
                        "ERROR",
                        "S4 inputs could not be read",
                        {"error": str(exc)},
                        scenario_id=str(scenario_id),
                        segment="S4",
                    )
            else:
                record_check(CHECK_S4_PRESENT, "FAIL", {"detail": "S4 output missing"})
                update_run_check(run_checks, CHECK_S4_PRESENT, "FAIL")
                record_issue(
                    CHECK_S4_PRESENT,
                    "S4_MISSING",
                    "ERROR",
                    "merchant_zone_scenario_local_5A missing",
                    scenario_id=str(scenario_id),
                    segment="S4",
                )

            if spec_compat_config:
                check_id = str(
                    (spec_compat_config.get("enforcement") or {}).get("failure_check_id") or CHECK_SPEC_COMPAT
                )
                s1_version = s1_spec_version
                if scenario_scan is not None and "s4_spec_version" in scenario_columns:
                    s4_versions = (
                        scenario_scan.select(pl.col("s4_spec_version").drop_nulls().unique())
                        .collect()
                        .get_column("s4_spec_version")
                    )
                    s4_version = str(s4_versions[0]) if len(s4_versions) else None
                else:
                    s4_version = None
                s2_version = None
                shape_path = _resolve_output_path(DATASET_CLASS_ZONE_SHAPE, run_tokens)
                if shape_path:
                    shape_key = str(shape_path)
                    if shape_key not in s2_version_by_path:
                        shape_paths = _resolve_parquet_files(shape_path)
                        shape_scan_for_spec = pl.scan_parquet([str(path) for path in shape_paths])
                        shape_cols = _scan_columns(shape_scan_for_spec)
                        if "s2_spec_version" in shape_cols:
                            values = (
                                shape_scan_for_spec.select(pl.col("s2_spec_version").drop_nulls().unique())
                                .collect()
                                .get_column("s2_spec_version")
                            )
                            s2_version_by_path[shape_key] = str(values[0]) if len(values) else None
                        else:
                            s2_version_by_path[shape_key] = None
                    s2_version = s2_version_by_path[shape_key]

                s3_version = None
                if baseline_scan is not None and baseline_path is not None:
                    baseline_key = str(baseline_path)
                    if baseline_key not in s3_version_by_path:
                        if "s3_spec_version" in baseline_columns:
                            values = (
                                baseline_scan.select(pl.col("s3_spec_version").drop_nulls().unique())
                                .collect()
                                .get_column("s3_spec_version")
                            )
                            s3_version_by_path[baseline_key] = str(values[0]) if len(values) else None
                        else:
                            s3_version_by_path[baseline_key] = None
                    s3_version = s3_version_by_path[baseline_key]
                versions = {"s1": s1_version, "s2": s2_version, "s3": s3_version, "s4": s4_version}
                enforcement = spec_compat_config.get("enforcement") or {}
                missing_fields = [key for key, value in versions.items() if not value]
                if missing_fields:
                    record_check(check_id, "FAIL", {"missing_versions": missing_fields})
                    update_run_check(run_checks, check_id, "FAIL")
                    record_issue(
                        check_id,
                        "SPEC_COMPAT_MISSING_VERSION",
                        "ERROR",
                        "spec_version missing for compatibility check",
                        {"missing_versions": missing_fields},
                        scenario_id=str(scenario_id),
                        segment="S5",
                    )
                else:
                    majors = {key: _parse_major(value) for key, value in versions.items()}
                    if any(val is None for val in majors.values()):
                        record_check(check_id, "FAIL", {"unparseable_versions": majors})
                        update_run_check(run_checks, check_id, "FAIL")
                    else:
                        supported = spec_compat_config.get("supported_majors") or {}
                        unsupported = [
                            key for key, val in majors.items() if val not in (supported.get(key) or [])
                        ]
                        allowed = spec_compat_config.get("allowed_major_tuples") or []
                        tuple_match = False
                        for entry in allowed:
                            if (
                                int(entry.get("s1_major", -1)) == majors["s1"]
                                and int(entry.get("s2_major", -1)) == majors["s2"]
                                and int(entry.get("s3_major", -1)) == majors["s3"]
                                and int(entry.get("s4_major", -1)) == majors["s4"]
                            ):
                                tuple_match = True
                                break
                        status_val = "PASS"
                        if unsupported:
                            status_val = (
                                "WARN"
                                if enforcement.get("on_unsupported_major") == "WARN_AND_CONTINUE"
                                else "FAIL"
                            )
                        elif not tuple_match:
                            status_val = (
                                "WARN"
                                if enforcement.get("on_unsupported_tuple") == "WARN_AND_CONTINUE"
                                else "FAIL"
                            )
                        record_check(
                            check_id,
                            status_val,
                            {"majors": majors, "unsupported": unsupported, "tuple_match": tuple_match},
                        )
                        update_run_check(run_checks, check_id, status_val)

            run_status = "PASS"
            has_warn = False
            for check_id, check_status in run_checks.items():
                if check_status == "FAIL" and is_blocking(check_id):
                    run_status = "FAIL"
                    break
                if check_status == "WARN":
                    if check_id in warn_blocking_ids and is_blocking(check_id):
                        run_status = "FAIL"
                        break
                    has_warn = True
            if run_status == "PASS" and has_warn:
                run_status = "WARN"

            scenario_results.append(
                {
                    "parameter_hash": str(parameter_hash_gate or parameter_hash_receipt or ""),
                    "scenario_id": str(scenario_id),
                    "status": run_status,
                }
            )

        timer.info(
            "S5: phase recomposition_checks complete (scenarios=%s, checks=%s, issues=%s)",
            len(scenario_results),
            len(checks),
            len(issues),
        )

        overall_status = "PASS"
        has_warn = False
        for check_id, check_payload in checks.items():
            check_status = check_payload.get("status")
            if check_status == "FAIL" and is_blocking(check_id):
                overall_status = "FAIL"
                break
            if check_status == "WARN":
                if check_id in warn_blocking_ids and is_blocking(check_id):
                    overall_status = "FAIL"
                    break
                has_warn = True
        if overall_status == "PASS" and has_warn:
            overall_status = "PASS"

        current_phase = "bundle_write"
        bundle_root = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, DATASET_BUNDLE).entry, run_paths, config.external_roots, tokens
        )
        index_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, DATASET_BUNDLE_INDEX).entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        report_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, DATASET_REPORT).entry, run_paths, config.external_roots, tokens
        )
        issues_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, DATASET_ISSUES).entry, run_paths, config.external_roots, tokens
        )
        flag_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, DATASET_FLAG).entry, run_paths, config.external_roots, tokens
        )

        tmp_root = run_paths.tmp_root / f"s5_validation_bundle_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        report_rel = report_path.relative_to(bundle_root)
        issues_rel = issues_path.relative_to(bundle_root)
        index_rel = index_path.relative_to(bundle_root)
        flag_rel = flag_path.relative_to(bundle_root)

        report_payload = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "s5_spec_version": S5_SPEC_VERSION,
            "overall_status": overall_status,
            "parameter_hashes": sorted(parameter_hashes),
            "scenarios": scenario_results,
            "checks": list(checks.values()),
            "issues_path": str(issues_rel.as_posix()),
            "notes": "overlay warn exemptions not applied; overlay types not present in overlay_factor_total output",
        }
        _validate_payload(schema_layer2, schema_layer1, schema_layer2, "validation/validation_report_5A", report_payload)
        _write_json(tmp_root / report_rel, report_payload)

        issue_rows = issues
        if issue_rows:
            issues_df = pl.DataFrame(issue_rows)
        else:
            issues_df = pl.DataFrame(
                {
                    "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                    "parameter_hash": pl.Series([], dtype=pl.Utf8),
                    "scenario_id": pl.Series([], dtype=pl.Utf8),
                    "segment": pl.Series([], dtype=pl.Utf8),
                    "check_id": pl.Series([], dtype=pl.Utf8),
                    "issue_code": pl.Series([], dtype=pl.Utf8),
                    "severity": pl.Series([], dtype=pl.Utf8),
                    "context": pl.Series([], dtype=pl.Object),
                    "message": pl.Series([], dtype=pl.Utf8),
                }
            )
        issues_df_path = tmp_root / issues_rel
        issues_df_path.parent.mkdir(parents=True, exist_ok=True)
        issues_df.write_parquet(issues_df_path)
        timer.info("S5: phase issue_table_assembly complete (issue_rows=%s)", len(issue_rows))

        report_digest = sha256_file(tmp_root / report_rel)
        issues_digest = sha256_file(tmp_root / issues_rel)
        entries = [
            {"path": report_rel.as_posix(), "sha256_hex": report_digest.sha256_hex},
            {"path": issues_rel.as_posix(), "sha256_hex": issues_digest.sha256_hex},
        ]

        index_payload = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "segment_id": SEGMENT,
            "s5_spec_version": S5_SPEC_VERSION,
            "generated_utc": utc_now_rfc3339_micro(),
            "overall_status": overall_status,
            "summary": {
                "scenario_count": len(scenario_results),
                "parameter_hashes": sorted(parameter_hashes),
                "issue_count": len(issue_rows),
            },
            "entries": sorted(entries, key=lambda item: item["path"]),
        }
        _validate_payload(schema_layer2, schema_layer1, schema_layer2, "validation/validation_bundle_index_5A", index_payload)
        _write_json(tmp_root / index_rel, index_payload)

        bundle_digest = _bundle_digest(tmp_root, entries)
        if overall_status == "PASS":
            flag_payload = {
                "manifest_fingerprint": str(manifest_fingerprint),
                "bundle_digest_sha256": bundle_digest,
            }
            _validate_payload(schema_layer2, schema_layer1, schema_layer2, "validation/passed_flag_5A", flag_payload)
            _write_json(tmp_root / flag_rel, flag_payload)

        timer.info(
            "S5: phase bundle_index_report_write complete (overall_status=%s, entries=%s)",
            overall_status,
            len(entries),
        )

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
            existing_index_bytes = existing_index.read_bytes()
            new_index_bytes = (tmp_root / index_rel).read_bytes()
            if existing_index_bytes != new_index_bytes:
                raise EngineFailure(
                    "F4",
                    "S5_OUTPUT_CONFLICT",
                    STATE,
                    MODULE_NAME,
                    {"detail": "index mismatch", "bundle_root": str(bundle_root)},
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

        status = "PASS" if overall_status == "PASS" else "FAIL"
        if status != "PASS" and not error_code:
            error_code = "S5_VALIDATION_FAILED"
        timer.info(f"S5: bundle complete (entries={len(entries)}, digest={bundle_digest})")

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
        if run_id_value and manifest_fingerprint and run_paths and dictionary_5a:
            try:
                run_report_entry = find_dataset_entry(dictionary_5a, DATASET_RUN_REPORT).entry
                run_report_path = _resolve_dataset_path(
                    run_report_entry, run_paths, config.external_roots, tokens
                )
                run_report = {
                    "layer": "layer2",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash_gate or parameter_hash_receipt or ""),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": run_id_value,
                    "status": status,
                    "seed": seed,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": dict(policy_versions),
                    "counts": counts,
                    "metrics": metrics,
                    "overall_status": "PASS" if status == "PASS" else "FAIL",
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "validation_bundle_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, DATASET_BUNDLE).entry, tokens
                        ),
                        "validation_bundle_index_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, DATASET_BUNDLE_INDEX).entry, tokens
                        ),
                        "validation_report_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, DATASET_REPORT).entry, tokens
                        ),
                        "validation_issue_table_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, DATASET_ISSUES).entry, tokens
                        ),
                        "validation_passed_flag_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, DATASET_FLAG).entry, tokens
                        ),
                    },
                }
                run_report_path.parent.mkdir(parents=True, exist_ok=True)
                run_report_path.write_text(
                    json.dumps(run_report, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
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

    if bundle_root is None or index_path is None or report_path is None or issues_path is None:
        raise EngineFailure(
            "F4",
            "S5_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S5Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash_gate or parameter_hash_receipt or ""),
        manifest_fingerprint=str(manifest_fingerprint),
        bundle_root=bundle_root,
        index_path=index_path,
        report_path=report_path,
        issues_path=issues_path,
        flag_path=flag_path if status == "PASS" else None,
        run_report_path=run_report_path or (run_paths.run_root / "reports" / "missing"),
    )
