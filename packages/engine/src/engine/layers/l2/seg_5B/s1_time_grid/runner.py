
"""Segment 5B S1 time grid + grouping."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
from jsonschema import Draft202012Validator

try:  # Optional fast parquet scanning.
    import pyarrow as pa
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pa = None
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import find_dataset_entry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l2.seg_5B.s0_gate.runner import (
    _append_jsonl,
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _sealed_inputs_digest,
    _segment_state_runs_path,
)


MODULE_NAME = "5B.s1_time_grid"
SEGMENT = "5B"
STATE = "S1"
MIN_MULTI_MEMBER_FRACTION = 0.70


@dataclass(frozen=True)
class S1Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    time_grid_paths: list[Path]
    grouping_paths: list[Path]
    run_report_path: Path


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str, *args) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        if args:
            message = message % args
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(
        self,
        total: Optional[int],
        logger,
        label: str,
        min_interval_seconds: float = 0.5,
    ) -> None:
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


def _emit_event(logger, event: str, manifest_fingerprint: Optional[str], severity: str, **fields: object) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint or "unknown",
        "severity": severity,
        "timestamp_utc": utc_now_rfc3339_micro(),
    }
    payload.update(fields)
    message = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    if severity == "ERROR":
        logger.error("%s %s", event, message)
    elif severity == "WARN":
        logger.warning("%s %s", event, message)
    elif severity == "DEBUG":
        logger.debug("%s %s", event, message)
    else:
        logger.info("%s %s", event, message)


def _emit_validation(
    logger,
    manifest_fingerprint: Optional[str],
    validator_id: str,
    result: str,
    error_code: Optional[str] = None,
    detail: Optional[object] = None,
) -> None:
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l2.seg_5B.s1_time_grid.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(schema, schema_layer2, "schemas.layer2.yaml#")
    return normalize_nullable_schema(schema)


def _validate_payload(
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    payload: object,
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
    logger=None,
    label: Optional[str] = None,
    total_rows: Optional[int] = None,
    progress_min_rows: int = 50000,
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
    tracker = None
    if logger and label and total_rows is not None and total_rows >= progress_min_rows:
        tracker = _ProgressTracker(total_rows, logger, label)
    for index, row in enumerate(rows):
        if tracker:
            tracker.update(1)
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


def _env_flag(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _schema_items(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    if schema.get("type") != "array":
        raise ContractError(f"Expected array schema at {anchor}, found {schema.get('type')}")
    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        raise ContractError(f"Array schema missing items object at {anchor}")
    return items_schema


def _property_allows_null(schema: dict) -> bool:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return "null" in schema_type
    if isinstance(schema_type, str):
        return schema_type == "null"
    for key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(key)
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict) and _property_allows_null(option):
                    return True
    return False


def _validate_dataframe_fast(
    df: pl.DataFrame,
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    *,
    logger,
    label: str,
    sample_rows: int,
) -> None:
    items_schema = _schema_items(schema_pack, schema_layer1, schema_layer2, anchor)
    properties = items_schema.get("properties")
    if not isinstance(properties, dict):
        raise ContractError(f"Schema items missing properties at {anchor}")
    required = items_schema.get("required") or []
    if not isinstance(required, list):
        raise ContractError(f"Schema items required is not a list at {anchor}")
    required_set = {str(name) for name in required}
    columns = set(df.columns)
    missing = sorted(required_set - columns)
    if missing:
        raise SchemaValidationError(f"Missing required columns at {anchor}: {missing}", [])
    additional_props = items_schema.get("additionalProperties", True)
    extra = sorted(columns - set(properties.keys()))
    if extra and additional_props is False:
        raise SchemaValidationError(f"Unexpected columns at {anchor}: {extra}", [])

    for name, prop_schema in properties.items():
        if name not in columns or not isinstance(prop_schema, dict):
            continue
        if _property_allows_null(prop_schema):
            continue
        nulls = int(df.select(pl.col(name).null_count()).item())
        if nulls:
            raise SchemaValidationError(
                f"Non-nullable column {name} has {nulls} nulls at {anchor}",
                [],
            )

    sample_rows = max(int(sample_rows), 0)
    sample_rows = min(sample_rows, df.height)
    if sample_rows:
        sample_df = df.head(sample_rows)
        _validate_array_rows(
            sample_df.iter_rows(named=True),
            schema_pack,
            schema_layer1,
            schema_layer2,
            anchor,
            logger=logger,
            label=f"{label} sample",
            total_rows=sample_df.height,
            progress_min_rows=sample_rows + 1,
        )
    logger.info(
        "S1: %s schema validated (mode=fast sample_rows=%s total_rows=%s)",
        label,
        sample_rows,
        df.height,
    )

def _resolve_sealed_row(
    sealed_by_id: dict[str, dict],
    artifact_id: str,
    manifest_fingerprint: str,
    read_scopes: set[str],
    required: bool,
    error_code: str,
) -> Optional[dict]:
    row = sealed_by_id.get(artifact_id)
    if not row or row.get("status") == "IGNORED":
        if required:
            _abort(
                error_code,
                "V-04",
                "required_input_missing",
                {"artifact_id": artifact_id},
                manifest_fingerprint,
            )
        return None
    if required and row.get("status") != "REQUIRED":
        _abort(
            error_code,
            "V-04",
            "required_input_unusable",
            {"artifact_id": artifact_id, "status": row.get("status")},
            manifest_fingerprint,
        )
    if row.get("read_scope") not in read_scopes:
        _abort(
            error_code,
            "V-04",
            "read_scope_invalid",
            {"artifact_id": artifact_id, "read_scope": row.get("read_scope")},
            manifest_fingerprint,
        )
    return row


def _publish_parquet_idempotent(path: Path, df: pl.DataFrame, logger, label: str) -> bool:
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    df.write_parquet(tmp_path, compression="zstd")
    if path.exists():
        existing_hash = sha256_file(path).sha256_hex
        tmp_hash = sha256_file(tmp_path).sha256_hex
        if existing_hash != tmp_hash:
            raise EngineFailure(
                "F4",
                "5B.S1.IO_WRITE_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(path), "label": label},
            )
        tmp_path.unlink()
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
        logger.info("S1: output already exists and is identical; skipping publish (%s).", label)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "5B.S1.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(path), "label": label, "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info("S1: published %s to %s", label, path)
    return True


def _parse_rfc3339_micros(value: str) -> datetime:
    if not isinstance(value, str):
        raise InputResolutionError(f"Invalid timestamp (expected string): {value}")
    text = value.strip()
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise InputResolutionError(f"Invalid rfc3339 timestamp: {value}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


def _format_rfc3339_micros(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _scan_domain_keys(
    paths: Iterable[Path],
    scenario_id: str,
    logger,
    manifest_fingerprint: str,
) -> tuple[set[tuple[int, str, str, str]], int]:
    source_paths = [str(path) for path in paths]
    if not source_paths:
        return set(), 0

    scan = pl.scan_parquet(source_paths).select(
        [
            pl.col("scenario_id"),
            pl.col("merchant_id"),
            pl.col("legal_country_iso"),
            pl.col("tzid"),
            pl.col("channel_group"),
        ]
    )
    scenario_match = pl.col("scenario_id") == pl.lit(scenario_id)
    invalid_row = (
        pl.col("merchant_id").is_null()
        | pl.col("legal_country_iso").is_null()
        | pl.col("tzid").is_null()
        | pl.col("channel_group").is_null()
        | pl.col("channel_group").cast(pl.Utf8).str.strip_chars().eq("")
    )

    summary = (
        scan.select(
            [
                scenario_match.sum().cast(pl.Int64).alias("rows_seen"),
                (~scenario_match).sum().cast(pl.Int64).alias("mismatch_count"),
                (
                    pl.when(scenario_match)
                    .then(invalid_row)
                    .otherwise(False)
                    .sum()
                    .cast(pl.Int64)
                    .alias("invalid_count")
                ),
                (
                    pl.when(~scenario_match)
                    .then(pl.col("scenario_id").cast(pl.Utf8))
                    .otherwise(None)
                    .drop_nulls()
                    .first()
                    .alias("first_mismatch_scenario_id")
                ),
                (
                    pl.when(scenario_match & invalid_row)
                    .then(pl.col("merchant_id").cast(pl.UInt64))
                    .otherwise(None)
                    .drop_nulls()
                    .first()
                    .alias("first_invalid_merchant_id")
                ),
            ]
        ).collect()
    )
    rows_seen = int(summary.get_column("rows_seen")[0] or 0)
    mismatch_count = int(summary.get_column("mismatch_count")[0] or 0)
    invalid_count = int(summary.get_column("invalid_count")[0] or 0)
    first_mismatch = summary.get_column("first_mismatch_scenario_id")[0]
    first_invalid_merchant = summary.get_column("first_invalid_merchant_id")[0]

    if mismatch_count > 0:
        _abort(
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
            "V-07",
            "scenario_id_mismatch",
            {
                "expected": scenario_id,
                "mismatch_count": mismatch_count,
                "first_actual": first_mismatch,
            },
            manifest_fingerprint,
        )

    if invalid_count > 0:
        _abort(
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
            "V-07",
            "scenario_local_row_missing",
            {
                "scenario_id": scenario_id,
                "invalid_count": invalid_count,
                "first_invalid_merchant_id": first_invalid_merchant,
            },
            manifest_fingerprint,
        )

    keys_df = (
        scan.filter(scenario_match)
        .select(
            [
                pl.col("merchant_id").cast(pl.UInt64).alias("merchant_id"),
                pl.col("legal_country_iso").cast(pl.Utf8).alias("legal_country_iso"),
                pl.col("tzid").cast(pl.Utf8).alias("tzid"),
                pl.col("channel_group").cast(pl.Utf8).str.strip_chars().alias("channel_group"),
            ]
        )
        .unique()
        .collect()
    )
    keys: set[tuple[int, str, str, str]] = set()
    for mid, iso, tzid, channel in keys_df.iter_rows():
        keys.add((int(mid), str(iso), str(tzid), str(channel)))

    logger.info(
        "S1: scan scenario_local keys (scenario_id=%s) rows_seen=%d unique_keys=%d mode=vectorized",
        scenario_id,
        rows_seen,
        len(keys),
    )
    return keys, rows_seen

def _load_profile_map(path: Path, logger, manifest_fingerprint: str) -> dict[tuple[int, str, str], str]:
    files = _list_parquet_files(path)
    df = pl.read_parquet(files, columns=["merchant_id", "legal_country_iso", "tzid", "demand_class"])
    if df.is_empty():
        _abort(
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
            "V-07",
            "profile_empty",
            {"path": str(path)},
            manifest_fingerprint,
        )
    profile_map: dict[tuple[int, str, str], str] = {}
    for row in df.iter_rows(named=True):
        merchant_id = row.get("merchant_id")
        legal_country_iso = row.get("legal_country_iso")
        tzid = row.get("tzid")
        demand_class = row.get("demand_class")
        if merchant_id is None or legal_country_iso is None or tzid is None or demand_class is None:
            _abort(
                "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
                "V-07",
                "profile_row_missing",
                {"detail": "merchant_id/legal_country_iso/tzid/demand_class missing"},
                manifest_fingerprint,
            )
        key = (int(merchant_id), str(legal_country_iso), str(tzid))
        demand_class_text = str(demand_class)
        existing = profile_map.get(key)
        if existing and existing != demand_class_text:
            _abort(
                "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
                "V-07",
                "profile_duplicate_key",
                {"merchant_id": int(merchant_id), "key": key},
                manifest_fingerprint,
            )
        profile_map[key] = demand_class_text
    logger.info("S1: merchant_zone_profile_5A loaded (rows=%d unique_keys=%d)", df.height, len(profile_map))
    return profile_map


def _load_virtual_map(path: Path, logger, manifest_fingerprint: str) -> dict[int, str]:
    files = _list_parquet_files(path)
    df = pl.read_parquet(files, columns=["merchant_id", "virtual_mode"])
    if df.is_empty():
        _abort(
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
            "V-07",
            "virtual_classification_empty",
            {"path": str(path)},
            manifest_fingerprint,
        )
    virtual_map: dict[int, str] = {}
    for row in df.iter_rows(named=True):
        merchant_id = row.get("merchant_id")
        virtual_mode = row.get("virtual_mode")
        if merchant_id is None or virtual_mode is None:
            _abort(
                "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
                "V-07",
                "virtual_row_missing",
                {"detail": "merchant_id/virtual_mode missing"},
                manifest_fingerprint,
            )
        key = int(merchant_id)
        virtual_mode_text = str(virtual_mode)
        existing = virtual_map.get(key)
        if existing and existing != virtual_mode_text:
            _abort(
                "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
                "V-07",
                "virtual_duplicate_key",
                {"merchant_id": key},
                manifest_fingerprint,
            )
        virtual_map[key] = virtual_mode_text
    logger.info("S1: virtual_classification_3B loaded (rows=%d unique_merchants=%d)", df.height, len(virtual_map))
    return virtual_map


def _zone_group_id(tzid: str, buckets: int) -> str:
    digest = hashlib.sha256(f"5B.zone_group|{tzid}".encode("utf-8")).digest()
    idx = digest[0] % buckets
    return f"zg{idx:02d}"


def _in_stratum_bucket(message: str, buckets: int) -> int:
    digest = hashlib.sha256(message.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big", signed=False)
    return value % buckets


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l2.seg_5B.s1_time_grid.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)
    output_validate_full = _env_flag("ENGINE_5B_S1_VALIDATE_FULL")
    output_sample_rows_env = os.environ.get("ENGINE_5B_S1_VALIDATE_SAMPLE_ROWS", "5000")
    try:
        output_sample_rows = max(int(output_sample_rows_env), 0)
    except ValueError:
        output_sample_rows = 5000
    output_validation_mode = "full" if output_validate_full else "fast_sampled"
    current_phase = "init"
    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    run_paths: Optional[RunPaths] = None
    run_report_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    scenario_set: list[str] = []
    seed: int = 0

    dictionary_5b: dict = {}
    tokens: dict[str, str] = {}

    scenario_details: dict[str, dict[str, object]] = {}
    total_bucket_count = 0
    total_grouping_rows = 0
    total_group_ids: set[str] = set()
    scenario_count_succeeded = 0

    try:
        current_phase = "run_receipt"
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id = receipt.get("run_id")
        if not run_id:
            raise InputResolutionError("run_receipt missing run_id.")
        if receipt_path.parent.name != run_id:
            raise InputResolutionError("run_receipt path does not match embedded run_id.")
        parameter_hash = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if manifest_fingerprint is None or parameter_hash is None:
            raise InputResolutionError("run_receipt missing manifest_fingerprint or parameter_hash.")
        seed = int(receipt.get("seed") or 0)

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S1: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5b_path, dictionary_5b = load_dataset_dictionary(source, "5B")
        schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s,%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_5b_path),
            str(schema_5b_path),
            str(schema_5a_path),
            str(schema_3b_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
        )

        logger.info(
            "S1: objective=build time grid + grouping plan (gate S0 receipt + sealed inputs + policies; output s1_time_grid_5B + s1_grouping_5B)"
        )

        tokens = {
            "seed": str(seed),
            "parameter_hash": str(parameter_hash),
            "manifest_fingerprint": str(manifest_fingerprint),
            "run_id": str(run_id),
        }

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_5b, "s0_gate_receipt_5B").entry
        sealed_entry = find_dataset_entry(dictionary_5b, "sealed_inputs_5B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        sealed_inputs = _load_json(sealed_inputs_path)

        _validate_payload(schema_5b, schema_layer1, schema_layer2, "validation/s0_gate_receipt_5B", receipt_payload)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "validation/sealed_inputs_5B", sealed_inputs)

        if receipt_payload.get("parameter_hash") != parameter_hash:
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_set_payload = receipt_payload.get("scenario_set")
        if not isinstance(scenario_set_payload, list) or not scenario_set_payload:
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "scenario_set_missing",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )
        scenario_set = sorted({str(item) for item in scenario_set_payload if item})
        if not scenario_set:
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "scenario_set_empty",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )

        upstream = receipt_payload.get("upstream_segments") or {}
        for segment_id in ("1A", "1B", "2A", "2B", "3A", "3B", "5A"):
            status_value = None
            if isinstance(upstream, dict):
                status_value = (upstream.get(segment_id) or {}).get("status")
            if status_value != "PASS":
                _abort(
                    "5B.S1.UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        if not isinstance(sealed_inputs, list):
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "sealed_inputs_invalid",
                {"detail": "sealed_inputs_5B payload is not a list"},
                manifest_fingerprint,
            )
        sealed_sorted = sorted(
            sealed_inputs,
            key=lambda row: (row.get("owner_segment"), row.get("artifact_id"), row.get("role")),
        )
        seen_keys: set[tuple[str, str]] = set()
        for row in sealed_sorted:
            key = (str(row.get("owner_segment") or ""), str(row.get("artifact_id") or ""))
            if key in seen_keys:
                _abort(
                    "5B.S1.S0_GATE_MISSING",
                    "V-03",
                    "sealed_inputs_duplicate_key",
                    {"owner_segment": key[0], "artifact_id": key[1]},
                    manifest_fingerprint,
                )
            seen_keys.add(key)
        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if sealed_digest != receipt_payload.get("sealed_inputs_digest"):
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {
                    "expected": receipt_payload.get("sealed_inputs_digest"),
                    "actual": sealed_digest,
                },
                manifest_fingerprint,
            )

        sealed_by_id = {row.get("artifact_id"): row for row in sealed_sorted if isinstance(row, dict)}

        current_phase = "input_resolution"
        _resolve_sealed_row(
            sealed_by_id,
            "scenario_manifest_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_profile_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_scenario_local_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "shape_grid_definition_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "class_zone_shape_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "time_grid_policy_5B",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "5B.S1.TIME_GRID_POLICY_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "grouping_policy_5B",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "5B.S1.GROUPING_POLICY_MISSING",
        )

        current_phase = "policy_load"
        time_grid_entry = find_dataset_entry(dictionary_5b, "time_grid_policy_5B").entry
        time_grid_path = _resolve_dataset_path(time_grid_entry, run_paths, config.external_roots, tokens)
        time_grid_policy = _load_yaml(time_grid_path)
        try:
            _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/time_grid_policy_5B", time_grid_policy)
        except SchemaValidationError as exc:
            _abort(
                "5B.S1.TIME_GRID_POLICY_SCHEMA_INVALID",
                "V-05",
                "time_grid_policy_schema_invalid",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        grouping_entry = find_dataset_entry(dictionary_5b, "grouping_policy_5B").entry
        grouping_path = _resolve_dataset_path(grouping_entry, run_paths, config.external_roots, tokens)
        grouping_policy = _load_yaml(grouping_path)
        try:
            _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/grouping_policy_5B", grouping_policy)
        except SchemaValidationError as exc:
            _abort(
                "5B.S1.GROUPING_POLICY_SCHEMA_INVALID",
                "V-05",
                "grouping_policy_schema_invalid",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        guardrails = time_grid_policy.get("guardrails") or {}
        min_horizon_days = int(guardrails.get("min_horizon_days") or 0)
        max_horizon_days = int(guardrails.get("max_horizon_days") or 0)
        max_buckets_per_scenario = int(guardrails.get("max_buckets_per_scenario") or 0)
        if min_horizon_days <= 0 or max_horizon_days <= 0 or max_buckets_per_scenario <= 0:
            _abort(
                "5B.S1.SCENARIO_HORIZON_INVALID",
                "V-05",
                "guardrails_invalid",
                {"guardrails": guardrails},
                manifest_fingerprint,
            )
        if max_horizon_days < min_horizon_days:
            _abort(
                "5B.S1.SCENARIO_HORIZON_INVALID",
                "V-05",
                "guardrails_inconsistent",
                {"min_horizon_days": min_horizon_days, "max_horizon_days": max_horizon_days},
                manifest_fingerprint,
            )
        if min_horizon_days < 14:
            logger.warning(
                "S1: time_grid_policy guardrail min_horizon_days below guide floor (value=%d)",
                min_horizon_days,
            )
        if max_buckets_per_scenario < 10000:
            logger.warning(
                "S1: time_grid_policy guardrail max_buckets_per_scenario below guide floor (value=%d)",
                max_buckets_per_scenario,
            )

        grouping_targets = grouping_policy.get("realism_targets") or {}
        min_groups_per_scenario = int(grouping_targets.get("min_groups_per_scenario") or 0)
        max_groups_per_scenario = int(grouping_targets.get("max_groups_per_scenario") or 0)
        min_group_members_median = float(grouping_targets.get("min_group_members_median") or 0)
        max_single_group_share = float(grouping_targets.get("max_single_group_share") or 0)
        if min_groups_per_scenario <= 0 or max_groups_per_scenario <= 0:
            _abort(
                "5B.S1.GROUPING_POLICY_SCHEMA_INVALID",
                "V-05",
                "realism_targets_invalid",
                {"targets": grouping_targets},
                manifest_fingerprint,
            )
        if min_groups_per_scenario < 200:
            logger.warning(
                "S1: grouping_policy min_groups_per_scenario below guide floor (value=%d)",
                min_groups_per_scenario,
            )

        logger.info(
            "S1: time_grid_policy validated (bucket_duration_seconds=%s guardrails=%s)",
            time_grid_policy.get("bucket_duration_seconds"),
            guardrails,
        )
        logger.info(
            "S1: grouping_policy validated (zone_group_buckets=%s in_stratum_buckets=%s)",
            grouping_policy.get("zone_group_buckets"),
            grouping_policy.get("in_stratum_buckets"),
        )

        current_phase = "scenario_manifest"
        manifest_entry = find_dataset_entry(dictionary_5b, "scenario_manifest_5A").entry
        manifest_path = _resolve_dataset_path(manifest_entry, run_paths, config.external_roots, tokens)
        manifest_df = pl.read_parquet(manifest_path)
        manifest_rows = manifest_df.to_dicts()
        _validate_array_rows(
            manifest_rows,
            schema_5a,
            schema_layer1,
            schema_layer2,
            "validation/scenario_manifest_5A",
        )
        scenario_map: dict[str, dict] = {}
        for row in manifest_rows:
            scenario_id = str(row.get("scenario_id") or "")
            if not scenario_id:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "scenario_id_missing",
                    {"row": row},
                    manifest_fingerprint,
                )
            if scenario_id in scenario_map:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "scenario_id_duplicate",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )
            scenario_map[scenario_id] = row

        if sorted(scenario_map.keys()) != sorted(scenario_set):
            _abort(
                "5B.S1.SCENARIO_HORIZON_INVALID",
                "V-05",
                "scenario_set_mismatch",
                {"scenario_set": scenario_set, "manifest_scenarios": sorted(scenario_map.keys())},
                manifest_fingerprint,
            )

        logger.info(
            "S1: scenario_manifest_5A loaded (scenarios=%d, scenario_set=%s)",
            len(scenario_map),
            ",".join(scenario_set),
        )

        current_phase = "domain_maps"
        profile_entry = find_dataset_entry(dictionary_5b, "merchant_zone_profile_5A").entry
        profile_path = _resolve_dataset_path(profile_entry, run_paths, config.external_roots, tokens)
        profile_map = _load_profile_map(profile_path, logger, manifest_fingerprint)

        virtual_entry = find_dataset_entry(dictionary_5b, "virtual_classification_3B").entry
        virtual_path = _resolve_dataset_path(virtual_entry, run_paths, config.external_roots, tokens)
        virtual_map = _load_virtual_map(virtual_path, logger, manifest_fingerprint)

        bucket_duration_seconds = int(time_grid_policy.get("bucket_duration_seconds") or 0)
        bucket_duration_minutes = int(bucket_duration_seconds / 60)
        carry_fields = time_grid_policy.get("carry_scenario_fields") or {}
        carry_required = carry_fields.get("required") or []
        carry_optional = carry_fields.get("optional") or []
        local_cfg = time_grid_policy.get("local_annotations") or {}
        emit_local = bool(local_cfg.get("emit"))
        weekend_days = set(local_cfg.get("weekend_days") or [])

        zone_group_buckets = int(grouping_policy.get("zone_group_buckets") or 0)
        in_stratum_buckets = int(grouping_policy.get("in_stratum_buckets") or 0)

        spec_version = str(receipt_payload.get("spec_version") or "")
        if not spec_version:
            _abort(
                "5B.S1.S0_GATE_MISSING",
                "V-03",
                "spec_version_missing",
                {"receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )

        for scenario_id in scenario_set:
            current_phase = f"scenario:{scenario_id}"
            scenario_row = scenario_map.get(scenario_id)
            if scenario_row is None:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "scenario_id_missing",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            horizon_start = _parse_rfc3339_micros(str(scenario_row.get("horizon_start_utc")))
            horizon_end = _parse_rfc3339_micros(str(scenario_row.get("horizon_end_utc")))
            if horizon_end <= horizon_start:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "horizon_end_before_start",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            if horizon_start.second != 0 or horizon_start.microsecond != 0:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "horizon_start_unaligned",
                    {"scenario_id": scenario_id, "horizon_start_utc": scenario_row.get("horizon_start_utc")},
                    manifest_fingerprint,
                )
            if horizon_end.second != 0 or horizon_end.microsecond != 0:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "horizon_end_unaligned",
                    {"scenario_id": scenario_id, "horizon_end_utc": scenario_row.get("horizon_end_utc")},
                    manifest_fingerprint,
                )
            if bucket_duration_minutes and (
                horizon_start.minute % bucket_duration_minutes != 0
                or horizon_end.minute % bucket_duration_minutes != 0
            ):
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "horizon_minutes_unaligned",
                    {"scenario_id": scenario_id, "bucket_duration_minutes": bucket_duration_minutes},
                    manifest_fingerprint,
                )

            total_seconds = int((horizon_end - horizon_start).total_seconds())
            if total_seconds % bucket_duration_seconds != 0:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "horizon_not_divisible",
                    {"scenario_id": scenario_id, "bucket_duration_seconds": bucket_duration_seconds},
                    manifest_fingerprint,
                )

            bucket_count = int(total_seconds / bucket_duration_seconds)
            horizon_days = total_seconds / 86400.0
            if horizon_days < min_horizon_days or horizon_days > max_horizon_days:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "horizon_days_out_of_bounds",
                    {
                        "scenario_id": scenario_id,
                        "horizon_days": horizon_days,
                        "min_horizon_days": min_horizon_days,
                        "max_horizon_days": max_horizon_days,
                    },
                    manifest_fingerprint,
                )
            if bucket_count > max_buckets_per_scenario:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "bucket_count_out_of_bounds",
                    {
                        "scenario_id": scenario_id,
                        "bucket_count": bucket_count,
                        "max_buckets_per_scenario": max_buckets_per_scenario,
                    },
                    manifest_fingerprint,
                )

            scenario_is_baseline = bool(scenario_row.get("is_baseline"))
            scenario_is_stress = bool(scenario_row.get("is_stress"))
            if scenario_is_baseline == scenario_is_stress:
                _abort(
                    "5B.S1.SCENARIO_HORIZON_INVALID",
                    "V-05",
                    "scenario_band_invalid",
                    {"scenario_id": scenario_id, "is_baseline": scenario_is_baseline, "is_stress": scenario_is_stress},
                    manifest_fingerprint,
                )
            scenario_band = "baseline" if scenario_is_baseline else "stress"

            logger.info(
                "S1: scenario horizon validated (scenario_id=%s bucket_count=%d bucket_duration_seconds=%d)",
                scenario_id,
                bucket_count,
                bucket_duration_seconds,
            )

            grid_rows: list[dict] = []
            grid_tracker = None
            if bucket_count >= 10000:
                grid_tracker = _ProgressTracker(bucket_count, logger, f"S1: build time grid (scenario_id={scenario_id})")
            for idx in range(bucket_count):
                if grid_tracker:
                    grid_tracker.update(1)
                bucket_start = horizon_start + timedelta(seconds=idx * bucket_duration_seconds)
                bucket_end = bucket_start + timedelta(seconds=bucket_duration_seconds)
                row = {
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "parameter_hash": str(parameter_hash),
                    "scenario_id": str(scenario_id),
                    "bucket_index": int(idx),
                    "bucket_start_utc": _format_rfc3339_micros(bucket_start),
                    "bucket_end_utc": _format_rfc3339_micros(bucket_end),
                    "bucket_duration_seconds": int(bucket_duration_seconds),
                    "s1_spec_version": spec_version,
                }
                if "scenario_is_baseline" in carry_required:
                    row["scenario_is_baseline"] = scenario_is_baseline
                if "scenario_is_stress" in carry_required:
                    row["scenario_is_stress"] = scenario_is_stress
                if "scenario_labels" in carry_optional:
                    labels = scenario_row.get("labels") or []
                    row["scenario_labels"] = list(labels) if labels else []
                if emit_local:
                    row["local_day_of_week"] = int(bucket_start.isoweekday())
                    row["local_minutes_since_midnight"] = int(bucket_start.hour * 60 + bucket_start.minute)
                    row["is_weekend"] = int(bucket_start.isoweekday()) in weekend_days
                grid_rows.append(row)

            if grid_rows:
                grid_df = pl.DataFrame(grid_rows)
            else:
                grid_schema = {
                    "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                    "parameter_hash": pl.Series([], dtype=pl.Utf8),
                    "scenario_id": pl.Series([], dtype=pl.Utf8),
                    "bucket_index": pl.Series([], dtype=pl.Int64),
                    "bucket_start_utc": pl.Series([], dtype=pl.Utf8),
                    "bucket_end_utc": pl.Series([], dtype=pl.Utf8),
                    "bucket_duration_seconds": pl.Series([], dtype=pl.Int64),
                    "s1_spec_version": pl.Series([], dtype=pl.Utf8),
                }
                if "scenario_is_baseline" in carry_required:
                    grid_schema["scenario_is_baseline"] = pl.Series([], dtype=pl.Boolean)
                if "scenario_is_stress" in carry_required:
                    grid_schema["scenario_is_stress"] = pl.Series([], dtype=pl.Boolean)
                if "scenario_labels" in carry_optional:
                    grid_schema["scenario_labels"] = pl.Series([], dtype=pl.List(pl.Utf8))
                if emit_local:
                    grid_schema["local_day_of_week"] = pl.Series([], dtype=pl.Int64)
                    grid_schema["local_minutes_since_midnight"] = pl.Series([], dtype=pl.Int64)
                    grid_schema["is_weekend"] = pl.Series([], dtype=pl.Boolean)
                grid_df = pl.DataFrame(grid_schema)

            grid_df = grid_df.sort(["scenario_id", "bucket_index"])
            if output_validate_full:
                _validate_array_rows(
                    grid_df.iter_rows(named=True),
                    schema_5b,
                    schema_layer1,
                    schema_layer2,
                    "model/s1_time_grid_5B",
                    logger=logger,
                    label=f"S1: validate time grid (scenario_id={scenario_id})",
                    total_rows=grid_df.height,
                )
            else:
                _validate_dataframe_fast(
                    grid_df,
                    schema_5b,
                    schema_layer1,
                    schema_layer2,
                    "model/s1_time_grid_5B",
                    logger=logger,
                    label=f"time_grid_5B scenario_id={scenario_id}",
                    sample_rows=output_sample_rows,
                )

            time_grid_entry = find_dataset_entry(dictionary_5b, "s1_time_grid_5B").entry
            time_grid_path = _resolve_dataset_path(
                time_grid_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            _publish_parquet_idempotent(time_grid_path, grid_df, logger, f"s1_time_grid_5B scenario_id={scenario_id}")

            scenario_local_entry = find_dataset_entry(dictionary_5b, "merchant_zone_scenario_local_5A").entry
            scenario_local_path = _resolve_dataset_path(
                scenario_local_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            scenario_local_files = _list_parquet_files(scenario_local_path)
            logger.info(
                "S1: scanning merchant_zone_scenario_local_5A for grouping domain (scenario_id=%s files=%d)",
                scenario_id,
                len(scenario_local_files),
            )
            domain_keys, rows_seen = _scan_domain_keys(
                scenario_local_files,
                str(scenario_id),
                logger,
                manifest_fingerprint,
            )
            if not domain_keys:
                _abort(
                    "5B.S1.GROUP_DOMAIN_DERIVATION_FAILED",
                    "V-07",
                    "group_domain_empty",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )
            logger.info(
                "S1: grouping domain derived (scenario_id=%s rows_seen=%d unique_keys=%d)",
                scenario_id,
                rows_seen,
                len(domain_keys),
            )

            grouping_rows: list[dict] = []
            group_sizes: dict[str, int] = {}
            tracker = _ProgressTracker(
                len(domain_keys),
                logger,
                f"S1: assign groups (scenario_id={scenario_id})",
            )
            for merchant_id, legal_country_iso, tzid, channel_group in sorted(
                domain_keys, key=lambda item: (item[0], item[2], item[3], item[1])
            ):
                tracker.update(1)
                demand_class = profile_map.get((merchant_id, legal_country_iso, tzid))
                if demand_class is None:
                    _abort(
                        "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                        "V-08",
                        "demand_class_missing",
                        {
                            "scenario_id": scenario_id,
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "tzid": tzid,
                        },
                        manifest_fingerprint,
                    )
                virtual_mode = virtual_map.get(merchant_id)
                if virtual_mode is None:
                    _abort(
                        "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                        "V-08",
                        "virtual_mode_missing",
                        {"scenario_id": scenario_id, "merchant_id": merchant_id},
                        manifest_fingerprint,
                    )
                virtual_band = "virtual" if virtual_mode != "NON_VIRTUAL" else "physical"
                zone_group_id = _zone_group_id(tzid, zone_group_buckets)
                message = (
                    "5B.group|"
                    f"{scenario_id}|{demand_class}|{channel_group}|{virtual_band}|{zone_group_id}|{merchant_id}"
                )
                bucket = _in_stratum_bucket(message, in_stratum_buckets)
                group_id = (
                    f"g|{scenario_band}|{demand_class}|{channel_group}|{virtual_band}|{zone_group_id}|b{bucket:02d}"
                )
                try:
                    group_id.encode("ascii")
                except UnicodeEncodeError as exc:
                    _abort(
                        "5B.S1.GROUP_ID_DOMAIN_INVALID",
                        "V-08",
                        "group_id_non_ascii",
                        {"scenario_id": scenario_id, "group_id": group_id},
                        manifest_fingerprint,
                    )
                grouping_rows.append(
                    {
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "parameter_hash": str(parameter_hash),
                        "scenario_id": str(scenario_id),
                        "merchant_id": int(merchant_id),
                        "zone_representation": str(tzid),
                        "channel_group": str(channel_group),
                        "group_id": group_id,
                        "scenario_band": scenario_band,
                        "demand_class": str(demand_class),
                        "virtual_band": virtual_band,
                        "zone_group_id": zone_group_id,
                        "s1_spec_version": spec_version,
                    }
                )
                group_sizes[group_id] = group_sizes.get(group_id, 0) + 1

            if not grouping_rows:
                _abort(
                    "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                    "V-08",
                    "grouping_rows_empty",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            group_count = len(group_sizes)
            group_sizes_list = list(group_sizes.values())
            median_members = float(statistics.median(group_sizes_list)) if group_sizes_list else 0.0
            max_members = max(group_sizes_list) if group_sizes_list else 0
            max_share = max_members / len(grouping_rows) if grouping_rows else 0.0
            multi_member_fraction = (
                sum(1 for count in group_sizes_list if count > 1) / group_count
                if group_count
                else 0.0
            )

            if group_count < min_groups_per_scenario or group_count > max_groups_per_scenario:
                _abort(
                    "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                    "V-08",
                    "group_count_out_of_bounds",
                    {
                        "scenario_id": scenario_id,
                        "group_count": group_count,
                        "min_groups_per_scenario": min_groups_per_scenario,
                        "max_groups_per_scenario": max_groups_per_scenario,
                    },
                    manifest_fingerprint,
                )
            if median_members < min_group_members_median:
                _abort(
                    "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                    "V-08",
                    "group_members_median_low",
                    {
                        "scenario_id": scenario_id,
                        "median_members": median_members,
                        "min_group_members_median": min_group_members_median,
                    },
                    manifest_fingerprint,
                )
            if max_share > max_single_group_share:
                _abort(
                    "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                    "V-08",
                    "group_share_too_high",
                    {
                        "scenario_id": scenario_id,
                        "max_share": max_share,
                        "max_single_group_share": max_single_group_share,
                    },
                    manifest_fingerprint,
                )
            if multi_member_fraction < MIN_MULTI_MEMBER_FRACTION:
                _abort(
                    "5B.S1.GROUP_ASSIGNMENT_INCOMPLETE",
                    "V-08",
                    "group_multi_member_fraction_low",
                    {
                        "scenario_id": scenario_id,
                        "multi_member_fraction": multi_member_fraction,
                        "min_fraction": MIN_MULTI_MEMBER_FRACTION,
                    },
                    manifest_fingerprint,
                )

            grouping_df = pl.DataFrame(
                grouping_rows, schema_overrides={"merchant_id": pl.UInt64}
            ).sort(
                ["scenario_id", "merchant_id", "zone_representation", "channel_group"]
            )
            if output_validate_full:
                _validate_array_rows(
                    grouping_df.iter_rows(named=True),
                    schema_5b,
                    schema_layer1,
                    schema_layer2,
                    "model/s1_grouping_5B",
                    logger=logger,
                    label=f"S1: validate grouping (scenario_id={scenario_id})",
                    total_rows=grouping_df.height,
                )
            else:
                _validate_dataframe_fast(
                    grouping_df,
                    schema_5b,
                    schema_layer1,
                    schema_layer2,
                    "model/s1_grouping_5B",
                    logger=logger,
                    label=f"s1_grouping_5B scenario_id={scenario_id}",
                    sample_rows=output_sample_rows,
                )

            grouping_entry = find_dataset_entry(dictionary_5b, "s1_grouping_5B").entry
            grouping_path = _resolve_dataset_path(
                grouping_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            _publish_parquet_idempotent(grouping_path, grouping_df, logger, f"s1_grouping_5B scenario_id={scenario_id}")

            scenario_details[scenario_id] = {
                "bucket_count": bucket_count,
                "grouping_row_count": len(grouping_rows),
                "group_id_count": group_count,
                "median_members_per_group": median_members,
                "max_group_share": max_share,
                "multi_member_fraction": multi_member_fraction,
            }
            total_bucket_count += bucket_count
            total_grouping_rows += len(grouping_rows)
            total_group_ids.update(group_sizes.keys())
            scenario_count_succeeded += 1

        status = "PASS"
        timer.info("S1: completed time grid + grouping plan")
    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        status = "FAIL"
        error_code = error_code or "5B.S1.IO_WRITE_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        status = "FAIL"
        error_code = error_code or "5B.S1.IO_WRITE_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint and dictionary_5b and run_paths is not None:
            try:
                utc_day = started_utc[:10]
                run_report_path = _segment_state_runs_path(run_paths, dictionary_5b, utc_day)
                bucket_counts = [
                    int(detail.get("bucket_count") or 0) for detail in scenario_details.values()
                ]
                group_counts = [
                    int(detail.get("group_id_count") or 0) for detail in scenario_details.values()
                ]
                members_per_group = [
                    float(detail.get("median_members_per_group") or 0.0) for detail in scenario_details.values()
                ]

                run_report_payload = {
                    "layer": "layer2",
                    "segment": SEGMENT,
                    "state": STATE,
                    "state_id": "5B.S1",
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "seed": int(seed),
                    "run_id": run_id,
                    "scenario_set": list(scenario_set),
                    "status": status,
                    "error_code": error_code,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "validation_mode": output_validation_mode,
                    "scenario_count_requested": len(scenario_set),
                    "scenario_count_succeeded": scenario_count_succeeded,
                    "scenario_count_failed": len(scenario_set) - scenario_count_succeeded,
                    "total_bucket_count": total_bucket_count,
                    "total_grouping_rows": total_grouping_rows,
                    "total_unique_group_ids": len(total_group_ids),
                    "bucket_count_min": min(bucket_counts) if bucket_counts else 0,
                    "bucket_count_max": max(bucket_counts) if bucket_counts else 0,
                    "bucket_count_mean": (sum(bucket_counts) / len(bucket_counts)) if bucket_counts else 0,
                    "group_ids_per_scenario_min": min(group_counts) if group_counts else 0,
                    "group_ids_per_scenario_max": max(group_counts) if group_counts else 0,
                    "median_members_per_group_min": min(members_per_group) if members_per_group else 0,
                    "median_members_per_group_max": max(members_per_group) if members_per_group else 0,
                    "details": scenario_details,
                }
                if error_context:
                    run_report_payload["error_context"] = error_context
                    run_report_payload["first_failure_phase"] = first_failure_phase

                _append_jsonl(run_report_path, run_report_payload)
                logger.info("S1: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S1: failed to write segment_state_runs: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "5B.S1.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if run_report_path is None or run_paths is None:
        raise EngineFailure(
            "F4",
            "5B.S1.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing run_report_path or run_paths"},
        )

    time_grid_entry = find_dataset_entry(dictionary_5b, "s1_time_grid_5B").entry
    grouping_entry = find_dataset_entry(dictionary_5b, "s1_grouping_5B").entry
    time_grid_paths = [
        _resolve_dataset_path(
            time_grid_entry,
            run_paths,
            config.external_roots,
            {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": scenario_id},
        )
        for scenario_id in scenario_set
    ]
    grouping_paths = [
        _resolve_dataset_path(
            grouping_entry,
            run_paths,
            config.external_roots,
            {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": scenario_id},
        )
        for scenario_id in scenario_set
    ]

    return S1Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        time_grid_paths=time_grid_paths,
        grouping_paths=grouping_paths,
        run_report_path=run_report_path,
    )
