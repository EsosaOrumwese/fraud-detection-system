
"""Segment 5B S3 bucket-level arrival counts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import statistics
import struct
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import concurrent.futures
from collections import deque
try:  # Faster JSON when available.
    import orjson

    def _json_dumps(payload: object) -> str:
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS).decode("utf-8")

    _HAVE_ORJSON = True
except Exception:  # pragma: no cover - fallback when orjson missing.

    def _json_dumps(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

    _HAVE_ORJSON = False

import numpy as np
import polars as pl
from jsonschema import Draft202012Validator

try:  # Optional fast parquet scanning / streaming.
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
from engine.layers.l1.seg_1A.s0_foundations.rng import RngTraceAccumulator
from engine.layers.l1.seg_1A.s1_hurdle.rng import add_u128, philox2x64_10
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


MODULE_NAME = "5B.s3_bucket_counts"
SEGMENT = "5B"
STATE = "S3"
BATCH_SIZE = 200_000
UINT64_MASK = 0xFFFFFFFFFFFFFFFF
UINT64_MAX = UINT64_MASK
TWO_NEG_64 = float.fromhex("0x1.0000000000000p-64")
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_KAPPA_MEDIAN_BOUNDS = (10.0, 80.0)
DEFAULT_PROGRESS_INTERVAL_SECONDS = 5.0

@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    counts_paths: list[Path]
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
        min_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
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
    logger = get_logger("engine.layers.l2.seg_5B.s3_bucket_counts.runner")
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


def _env_progress_interval_seconds(name: str, default: float = DEFAULT_PROGRESS_INTERVAL_SECONDS) -> float:
    raw = os.environ.get(name, f"{default}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} invalid: {raw}") from exc
    if not math.isfinite(value) or value < 0.1:
        raise ValueError(f"{name} invalid: {raw}")
    return value


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
    logger=None,
    label: Optional[str] = None,
    sample_rows: int = 5000,
) -> None:
    items_schema = _schema_items(schema_pack, schema_layer1, schema_layer2, anchor)
    properties = items_schema.get("properties") or {}
    required = items_schema.get("required") or []
    if not isinstance(properties, dict):
        raise ContractError(f"Schema {anchor} has no properties object.")
    if not isinstance(required, list):
        raise ContractError(f"Schema {anchor} required list invalid.")
    missing_required = [key for key in required if key not in df.columns]
    if missing_required:
        raise SchemaValidationError(
            f"Schema validation failed: missing required columns {missing_required}",
            missing_required,
        )
    for name, spec in properties.items():
        if name not in df.columns:
            continue
        if not _property_allows_null(spec):
            if df.get_column(name).is_null().any():
                raise SchemaValidationError(
                    f"Schema validation failed: column {name} has null values", []
                )
    if sample_rows <= 0:
        return
    sample_rows = min(sample_rows, df.height)
    sample_df = df.head(sample_rows)
    if sample_df.height > 0:
        _validate_array_rows(
            sample_df.iter_rows(named=True),
            schema_pack,
            schema_layer1,
            schema_layer2,
            anchor,
            logger=logger,
            label=f"{label} sample" if label else None,
            total_rows=sample_df.height,
            progress_min_rows=sample_rows + 1,
        )
    if logger and label:
        logger.info(
            "S3: %s schema validated (mode=fast sample_rows=%s total_rows=%s)",
            label,
            sample_rows,
            df.height,
        )

def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _count_parquet_rows(paths: Iterable[Path]) -> Optional[int]:
    total = 0
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            total += pf.metadata.num_rows
        return total
    for path in paths:
        count_df = pl.scan_parquet(path).select(pl.len()).collect()
        total += int(count_df.item())
    return total


def _iter_parquet_batches(paths: Iterable[Path], columns: list[str]) -> Iterator[object]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            for rg in range(pf.num_row_groups):
                yield pf.read_row_group(rg, columns=columns)
    else:
        for path in paths:
            df = pl.read_parquet(path, columns=columns)
            offset = 0
            while offset < df.height:
                chunk = df.slice(offset, BATCH_SIZE)
                offset += chunk.height
                yield chunk


def _event_root_from_path(path: Path) -> Path:
    if "*" in path.name or path.suffix:
        return path.parent
    return path


def _event_file_from_root(root: Path) -> Path:
    if root.is_file():
        return root
    return root / "part-00000.jsonl"


def _iter_jsonl_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.jsonl") if path.is_file())


def _iter_jsonl_rows(paths: Iterable[Path], label: str) -> Iterator[dict]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                payload = line.strip()
                if not payload:
                    continue
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise EngineFailure(
                        "F4",
                        "5B.S3.RNG_ACCOUNTING_MISMATCH",
                        STATE,
                        MODULE_NAME,
                        {"detail": str(exc), "path": str(path), "line": line_no, "label": label},
                    ) from exc


def _trace_has_substream(trace_path: Path, module: str, substream_label: str) -> bool:
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            try:
                record = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if record.get("module") == module and record.get("substream_label") == substream_label:
                return True
    return False


def _append_trace_from_events(
    event_root: Path, trace_handle, trace_acc: RngTraceAccumulator, logger
) -> int:
    event_paths = _iter_jsonl_paths(event_root)
    if not event_paths:
        raise EngineFailure(
            "F4",
            "5B.S3.RNG_ACCOUNTING_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": "no_event_jsonl_files", "path": str(event_root)},
        )
    rows_written = 0
    for event in _iter_jsonl_rows(event_paths, "rng_event_arrival_bucket_count"):
        trace_row = trace_acc.append_event(event)
        trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
        trace_handle.write("\n")
        rows_written += 1
    logger.info("S3: appended trace rows from existing events rows=%d", rows_written)
    return rows_written


def _ensure_rng_audit(audit_path: Path, audit_entry: dict, logger) -> None:
    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if (
                    payload.get("run_id") == audit_entry.get("run_id")
                    and payload.get("seed") == audit_entry.get("seed")
                    and payload.get("parameter_hash") == audit_entry.get("parameter_hash")
                    and payload.get("manifest_fingerprint") == audit_entry.get("manifest_fingerprint")
                ):
                    logger.info("S3: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S3: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S3: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash = _hash_partition(tmp_root)
        final_hash = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "5B.S3.IO_WRITE_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        for path in tmp_root.rglob("*"):
            if path.is_file():
                path.unlink()
        try:
            tmp_root.rmdir()
        except OSError:
            pass
        logger.info("S3: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "5B.S3.IO_WRITE_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S3: %s file already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)


def _hash_partition(root: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        hasher.update(path.name.encode("utf-8"))
        hasher.update(sha256_file(path).sha256_hex.encode("utf-8"))
    return hasher.hexdigest()


def _publish_parquet_file_idempotent(
    tmp_path: Path,
    final_path: Path,
    logger,
    label: str,
    error_code_conflict: str,
    error_code_failed: str,
) -> bool:
    if final_path.exists():
        existing_hash = sha256_file(final_path).sha256_hex
        tmp_hash = sha256_file(tmp_path).sha256_hex
        if existing_hash != tmp_hash:
            raise EngineFailure(
                "F4",
                error_code_conflict,
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        try:
            tmp_path.parent.rmdir()
        except OSError:
            pass
        logger.info("S3: output already exists and is identical; skipping publish (%s).", label)
        return False
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            error_code_failed,
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(final_path), "label": label, "error": str(exc)},
        ) from exc
    logger.info("S3: published %s (%s).", label, final_path)
    return True

def _uer_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _ser_u64_le(value: int) -> bytes:
    if value < 0 or value > UINT64_MAX:
        raise ValueError("seed out of range")
    return struct.pack("<Q", value)


def _open_interval_u01(value: int) -> float:
    if value < 0 or value > UINT64_MAX:
        raise ValueError("u64 out of range")
    return (float(value) + 0.5) * TWO_NEG_64


def _counter_wrapped(before_hi: int, before_lo: int, after_hi: int, after_lo: int) -> bool:
    if after_hi < before_hi:
        return True
    if after_hi == before_hi and after_lo < before_lo:
        return True
    return False


def _derive_rng_seed(
    domain_sep: str,
    family_id: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
    domain_key: str,
) -> tuple[int, int, int]:
    msg = (
        _uer_string(domain_sep)
        + _uer_string(family_id)
        + _uer_string(manifest_fingerprint)
        + _uer_string(parameter_hash)
        + _ser_u64_le(seed)
        + _uer_string(scenario_id)
        + _uer_string(domain_key)
    )
    digest = hashlib.sha256(msg).digest()
    key = int.from_bytes(digest[0:8], "big", signed=False)
    counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
    counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
    return key, counter_hi, counter_lo


def _rng_prefix(
    domain_sep: str,
    family_id: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
) -> bytes:
    return (
        _uer_string(domain_sep)
        + _uer_string(family_id)
        + _uer_string(manifest_fingerprint)
        + _uer_string(parameter_hash)
        + _ser_u64_le(seed)
        + _uer_string(scenario_id)
    )


def _derive_rng_seed_from_prefix(prefix: bytes, domain_key: str) -> tuple[int, int, int]:
    msg = prefix + _uer_string(domain_key)
    digest = hashlib.sha256(msg).digest()
    key = int.from_bytes(digest[0:8], "big", signed=False)
    counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
    counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
    return key, counter_hi, counter_lo


def _derive_rng_seed_from_hasher(base_hasher: "hashlib._Hash", domain_key: str) -> tuple[int, int, int]:
    hasher = base_hasher.copy()
    hasher.update(_uer_string(domain_key))
    digest = hasher.digest()
    key = int.from_bytes(digest[0:8], "big", signed=False)
    counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
    counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
    return key, counter_hi, counter_lo


def _process_counts_batch(
    batch_index: int,
    scenario_id: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    run_id: str,
    count_law_id: str,
    lambda_zero_eps: float,
    max_count_per_bucket: int,
    poisson_exact_lambda_max: float,
    poisson_n_cap_exact: int,
    domain_sep: str,
    family_id: str,
    mu_array: np.ndarray,
    merchant_ids: np.ndarray,
    zone_values: list[str],
    bucket_indices: np.ndarray,
    group_ids: list[str],
    kappa_values: Optional[np.ndarray],
    event_dir: Optional[str],
    draws_per_row: int,
    blocks_per_row: int,
    event_buffer_size: int,
    validate_events_full: bool,
    validate_events_limit: int,
    event_schema: Optional[dict],
) -> dict:
    mu_array = np.asarray(mu_array, dtype=np.float64)
    zero_mask = mu_array <= lambda_zero_eps
    nonzero_indices = np.flatnonzero(~zero_mask)
    count_array = np.zeros(mu_array.size, dtype=np.int64)
    capped_array = np.zeros(mu_array.size, dtype=bool)

    rng_prefix = _rng_prefix(
        domain_sep,
        family_id,
        str(manifest_fingerprint),
        str(parameter_hash),
        int(seed),
        str(scenario_id),
    )
    base_hasher = hashlib.sha256(rng_prefix)
    domain_prefix_cache: dict[tuple[int, str], str] = {}

    event_validator = Draft202012Validator(event_schema) if event_schema is not None else None
    validate_remaining = None if validate_events_full else max(int(validate_events_limit), 0)

    event_handle = None
    if event_dir:
        event_path = Path(event_dir) / f"part-{batch_index:06d}.jsonl"
        event_handle = event_path.open("w", encoding="utf-8")
    event_buffer: list[str] = []

    rng_events = 0
    rng_draws = 0
    rng_blocks = 0
    last_counters: Optional[tuple[int, int, int, int]] = None

    derive_seed = _derive_rng_seed_from_hasher
    draw_philox = _draw_philox_u64
    open_u01 = _open_interval_u01
    poisson_one_u = _poisson_one_u
    gamma_one_u = _gamma_one_u_approx
    add_u128_local = add_u128
    counter_wrapped = _counter_wrapped

    for idx in nonzero_indices:
        merchant_id = int(merchant_ids[idx])
        zone_rep = str(zone_values[idx])
        bucket_index = int(bucket_indices[idx])
        mu = float(mu_array[idx])

        cache_key = (merchant_id, zone_rep)
        domain_prefix = domain_prefix_cache.get(cache_key)
        if domain_prefix is None:
            domain_prefix = f"merchant_id={merchant_id}|zone={zone_rep}|bucket_index="
            domain_prefix_cache[cache_key] = domain_prefix
        domain_key = f"{domain_prefix}{bucket_index}"

        key, counter_hi, counter_lo = derive_seed(base_hasher, domain_key)
        values, blocks, after_hi, after_lo = draw_philox(
            key, counter_hi, counter_lo, draws_per_row, manifest_fingerprint
        )
        if blocks != blocks_per_row:
            raise EngineFailure(
                "F4",
                "5B.S3.RNG_ACCOUNTING_MISMATCH",
                STATE,
                MODULE_NAME,
                {"scenario_id": scenario_id, "blocks": blocks},
            )
        expected_hi, expected_lo = add_u128_local(counter_hi, counter_lo, blocks)
        if counter_wrapped(counter_hi, counter_lo, expected_hi, expected_lo):
            raise EngineFailure(
                "F4",
                "5B.S3.RNG_ACCOUNTING_MISMATCH",
                STATE,
                MODULE_NAME,
                {"scenario_id": scenario_id, "detail": "counter_wrap"},
            )

        u1 = open_u01(values[0])
        if count_law_id == "poisson":
            count, capped = poisson_one_u(
                mu,
                u1,
                poisson_exact_lambda_max,
                poisson_n_cap_exact,
                max_count_per_bucket,
            )
        else:
            kappa = float(kappa_values[idx]) if kappa_values is not None else None
            if kappa is None or not math.isfinite(kappa) or kappa <= 0.0:
                raise EngineFailure(
                    "F4",
                    "5B.S3.COUNT_CONFIG_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"scenario_id": scenario_id, "group_id": group_ids[idx]},
                )
            u2 = open_u01(values[1])
            gamma_lambda = gamma_one_u(mu, kappa, u1)
            if not math.isfinite(gamma_lambda) or gamma_lambda < 0.0:
                raise EngineFailure(
                    "F4",
                    "5B.S3.COUNTS_NUMERIC_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"scenario_id": scenario_id, "value": gamma_lambda},
                )
            count, capped = poisson_one_u(
                gamma_lambda,
                u2,
                poisson_exact_lambda_max,
                poisson_n_cap_exact,
                max_count_per_bucket,
            )

        if count < 0 or count > max_count_per_bucket:
            raise EngineFailure(
                "F4",
                "5B.S3.COUNTS_NUMERIC_INVALID",
                STATE,
                MODULE_NAME,
                {"scenario_id": scenario_id, "count": int(count), "max": max_count_per_bucket},
            )

        count_array[idx] = int(count)
        capped_array[idx] = bool(capped)

        rng_events += 1
        rng_draws += draws_per_row
        rng_blocks += blocks
        last_counters = (counter_hi, counter_lo, expected_hi, expected_lo)

        if event_handle is not None:
            event_payload = {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": str(run_id),
                "seed": int(seed),
                "parameter_hash": str(parameter_hash),
                "manifest_fingerprint": str(manifest_fingerprint),
                "module": "5B.S3",
                "substream_label": "bucket_count",
                "scenario_id": str(scenario_id),
                "bucket_index": int(bucket_index),
                "merchant_id": int(merchant_id),
                "rng_counter_before_lo": int(counter_lo),
                "rng_counter_before_hi": int(counter_hi),
                "rng_counter_after_lo": int(expected_lo),
                "rng_counter_after_hi": int(expected_hi),
                "draws": str(draws_per_row),
                "blocks": int(blocks),
            }
            if event_validator is not None and (validate_remaining is None or validate_remaining > 0):
                errors = list(event_validator.iter_errors(event_payload))
                if errors:
                    raise EngineFailure(
                        "F4",
                        "5B.S3.RNG_ACCOUNTING_MISMATCH",
                        STATE,
                        MODULE_NAME,
                        {"scenario_id": scenario_id, "error": str(errors[0])},
                    )
                if validate_remaining is not None:
                    validate_remaining -= 1
            event_buffer.append(_json_dumps(event_payload))
            if len(event_buffer) >= event_buffer_size:
                event_handle.write("\n".join(event_buffer))
                event_handle.write("\n")
                event_buffer.clear()

    if event_handle is not None and event_buffer:
        event_handle.write("\n".join(event_buffer))
        event_handle.write("\n")
        event_buffer.clear()
    if event_handle is not None:
        event_handle.close()

    return {
        "batch_index": batch_index,
        "count_array": count_array,
        "capped_array": capped_array,
        "rng_events": rng_events,
        "rng_draws": rng_draws,
        "rng_blocks": rng_blocks,
        "last_counters": last_counters,
    }


def _process_counts_batch_star(args: tuple) -> dict:
    return _process_counts_batch(*args)


def _draw_philox_u64(
    key: int,
    counter_hi: int,
    counter_lo: int,
    draws: int,
    manifest_fingerprint: str,
) -> tuple[list[int], int, int, int]:
    blocks = int((draws + 1) // 2)
    values: list[int] = []
    cur_hi, cur_lo = counter_hi, counter_lo
    for _ in range(blocks):
        out0, out1 = philox2x64_10(cur_hi, cur_lo, key)
        values.append(out0)
        if len(values) < draws:
            values.append(out1)
        next_hi, next_lo = add_u128(cur_hi, cur_lo, 1)
        if _counter_wrapped(cur_hi, cur_lo, next_hi, next_lo):
            _abort(
                "5B.S3.RNG_ACCOUNTING_MISMATCH",
                "V-12",
                "rng_counter_wrap",
                {"detail": "counter wrapped during draws"},
                manifest_fingerprint,
            )
        cur_hi, cur_lo = next_hi, next_lo
    return values, blocks, cur_hi, cur_lo


def _normal_icdf(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r) + 1.0
    )


def _poisson_one_u(
    lambda_value: float,
    u: float,
    poisson_exact_lambda_max: float,
    poisson_n_cap_exact: int,
    max_count_per_bucket: int,
) -> tuple[int, bool]:
    if lambda_value <= 0.0:
        return 0, False
    if lambda_value <= poisson_exact_lambda_max:
        p = math.exp(-lambda_value)
        cdf = p
        n = 0
        while cdf < u and n < poisson_n_cap_exact:
            n += 1
            p = p * lambda_value / n
            cdf += p
        capped = False
        if cdf < u:
            n = max_count_per_bucket
            capped = True
        if n > max_count_per_bucket:
            n = max_count_per_bucket
            capped = True
        return int(n), capped
    z = _normal_icdf(u)
    n = math.floor(lambda_value + math.sqrt(lambda_value) * z + 0.5)
    capped = False
    if n < 0:
        n = 0
        capped = True
    if n > max_count_per_bucket:
        n = max_count_per_bucket
        capped = True
    return int(n), capped


def _gamma_one_u_approx(mu: float, kappa: float, u: float) -> float:
    if mu <= 0.0 or kappa <= 0.0:
        raise ValueError("mu and kappa must be positive")
    sigma2 = math.log(1.0 + 1.0 / kappa)
    m = math.log(mu) - 0.5 * sigma2
    z = _normal_icdf(u)
    return math.exp(m + math.sqrt(sigma2) * z)


def _resolve_git_hash(repo_root: Path) -> str:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash).hex()
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip()).hex()
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip()).hex()
    except Exception as exc:  # pragma: no cover - fallback when git unavailable
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


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

def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l2.seg_5B.s3_bucket_counts.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)
    output_validate_full = _env_flag("ENGINE_5B_S3_VALIDATE_FULL")
    output_sample_rows_env = os.environ.get("ENGINE_5B_S3_VALIDATE_SAMPLE_ROWS", "5000")
    try:
        output_sample_rows = max(int(output_sample_rows_env), 0)
    except ValueError:
        output_sample_rows = 5000
    output_validation_mode = "full" if output_validate_full else "fast_sampled"
    progress_interval_seconds = _env_progress_interval_seconds("ENGINE_5B_S3_PROGRESS_INTERVAL_SEC")
    strict_ordering = _env_flag("ENGINE_5B_S3_STRICT_ORDERING")
    ordering_stats_enabled = strict_ordering or _env_flag("ENGINE_5B_S3_ORDERING_STATS")
    validate_events_full = _env_flag("ENGINE_5B_S3_VALIDATE_EVENTS_FULL")
    validate_events_limit_env = os.environ.get("ENGINE_5B_S3_VALIDATE_EVENTS_LIMIT", "1000")
    try:
        validate_events_limit = max(int(validate_events_limit_env), 0)
    except ValueError:
        validate_events_limit = 1000
    enable_rng_events = _env_flag("ENGINE_5B_S3_RNG_EVENTS")
    event_buffer_env = os.environ.get("ENGINE_5B_S3_EVENT_BUFFER", "5000")
    try:
        event_buffer_size = max(int(event_buffer_env), 1)
    except ValueError:
        event_buffer_size = 5000
    workers_env = os.environ.get("ENGINE_5B_S3_WORKERS", "").strip()
    if workers_env:
        try:
            worker_count = max(int(workers_env), 1)
        except ValueError:
            worker_count = 1
    else:
        worker_count = max(1, min(os.cpu_count() or 1, 4))
    max_inflight_env = os.environ.get("ENGINE_5B_S3_INFLIGHT_BATCHES", "").strip()
    if max_inflight_env:
        try:
            max_inflight = max(int(max_inflight_env), 1)
        except ValueError:
            max_inflight = max(2, worker_count * 2)
    else:
        max_inflight = max(2, worker_count * 2)
    use_parallel = worker_count > 1
    if use_parallel:
        ordering_stats_enabled = strict_ordering
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
    scenario_details: dict[str, dict[str, object]] = {}
    scenario_count_succeeded = 0
    total_rows_written = 0
    total_counts = 0
    total_buckets = 0
    total_groups = 0
    rng_events_total = 0
    rng_draws_total = 0
    rng_blocks_total = 0
    count_capped_total = 0

    count_min: Optional[int] = None
    count_max: Optional[int] = None
    mu_min: Optional[float] = None
    mu_max: Optional[float] = None

    counts_paths: list[Path] = []

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
        logger.info("S3: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5b_path, dictionary_5b = load_dataset_dictionary(source, "5B")
        schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_5b_path),
            str(schema_5b_path),
            str(schema_5a_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
        )

        logger.info(
            "S3: objective=realise bucket-level arrival counts (gate S0+S1+S2+configs; output s3_bucket_counts_5B + rng logs)"
        )
        logger.info(
            "S3: rng_event logging=%s (set ENGINE_5B_S3_RNG_EVENTS=1 to enable)",
            "on" if enable_rng_events else "off",
        )
        logger.info("S3: progress cadence interval=%.2fs", progress_interval_seconds)
        if not strict_ordering:
            logger.warning(
                "S3: strict ordering disabled; output order follows input stream (set ENGINE_5B_S3_STRICT_ORDERING=1 to enforce)"
            )
        if not ordering_stats_enabled:
            logger.info("S3: ordering stats disabled (set ENGINE_5B_S3_ORDERING_STATS=1 to collect)")
        logger.info(
            "S3: rng_event validation mode=%s limit=%s json_encoder=%s",
            "full" if validate_events_full else "sampled",
            "all" if validate_events_full else validate_events_limit,
            "orjson" if _HAVE_ORJSON else "json",
        )
        logger.info(
            "S3: parallel_mode=%s workers=%d inflight_batches=%d",
            "on" if use_parallel else "off",
            worker_count,
            max_inflight,
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
                "5B.S3.S0_GATE_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "5B.S3.S0_GATE_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_set_payload = receipt_payload.get("scenario_set")
        if not isinstance(scenario_set_payload, list) or not scenario_set_payload:
            _abort(
                "5B.S3.S0_GATE_INVALID",
                "V-03",
                "scenario_set_missing",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )
        scenario_set = sorted({str(item) for item in scenario_set_payload if item})
        if not scenario_set:
            _abort(
                "5B.S3.S0_GATE_INVALID",
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
                    "5B.S3.UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        spec_version = str(receipt_payload.get("spec_version") or "")
        if not spec_version:
            _abort(
                "5B.S3.S0_GATE_INVALID",
                "V-03",
                "spec_version_missing",
                {"receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )

        if not isinstance(sealed_inputs, list):
            _abort(
                "5B.S3.S0_GATE_INVALID",
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
        sealed_by_id: dict[str, dict] = {}
        for row in sealed_sorted:
            key = (str(row.get("owner_segment") or ""), str(row.get("artifact_id") or ""))
            if key in seen_keys:
                _abort(
                    "5B.S3.S0_GATE_INVALID",
                    "V-03",
                    "sealed_inputs_duplicate_key",
                    {"owner_segment": key[0], "artifact_id": key[1]},
                    manifest_fingerprint,
                )
            seen_keys.add(key)
            if key[1]:
                sealed_by_id[key[1]] = row

        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if receipt_payload.get("sealed_inputs_digest") != sealed_digest:
            _abort(
                "5B.S3.S0_GATE_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {"expected": receipt_payload.get("sealed_inputs_digest"), "actual": sealed_digest},
                manifest_fingerprint,
            )

        _resolve_sealed_row(
            sealed_by_id,
            "arrival_count_config_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S3.COUNT_CONFIG_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_rng_policy_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S3.RNG_POLICY_INVALID",
        )

        current_phase = "config_load"
        count_entry = find_dataset_entry(dictionary_5b, "arrival_count_config_5B").entry
        rng_entry = find_dataset_entry(dictionary_5b, "arrival_rng_policy_5B").entry
        count_path = _resolve_dataset_path(count_entry, run_paths, config.external_roots, tokens)
        rng_path = _resolve_dataset_path(rng_entry, run_paths, config.external_roots, tokens)
        count_config = _load_yaml(count_path)
        rng_policy = _load_yaml(rng_path)

        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_count_config_5B", count_config)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_rng_policy_5B", rng_policy)

        if count_config.get("policy_id") != "arrival_count_config_5B":
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_count_config_5B", "actual": count_config.get("policy_id")},
                manifest_fingerprint,
            )
        if rng_policy.get("policy_id") != "arrival_rng_policy_5B":
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_rng_policy_5B", "actual": rng_policy.get("policy_id")},
                manifest_fingerprint,
            )

        count_law_id = str(count_config.get("count_law_id") or "")
        if count_law_id not in {"poisson", "nb2"}:
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "count_law_invalid",
                {"count_law_id": count_law_id},
                manifest_fingerprint,
            )

        lambda_zero_eps = float(count_config.get("lambda_zero_eps") or 0.0)
        max_count_per_bucket = int(count_config.get("max_count_per_bucket") or 0)
        if lambda_zero_eps < 0.0 or max_count_per_bucket < 1:
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "lambda_zero_eps_invalid",
                {"lambda_zero_eps": lambda_zero_eps, "max_count_per_bucket": max_count_per_bucket},
                manifest_fingerprint,
            )

        poisson_cfg = count_config.get("poisson_sampler") or {}
        if str(poisson_cfg.get("kind") or "") != "cdf_inversion_one_u_bounded_v1":
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "poisson_sampler_invalid",
                {"poisson_sampler": poisson_cfg.get("kind")},
                manifest_fingerprint,
            )
        if str(poisson_cfg.get("p0_law") or "") != "exp_minus_lambda":
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "poisson_p0_law_invalid",
                {"p0_law": poisson_cfg.get("p0_law")},
                manifest_fingerprint,
            )
        if str(poisson_cfg.get("recurrence") or "") != "p_next = p * lambda / (n+1)":
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "poisson_recurrence_invalid",
                {"recurrence": poisson_cfg.get("recurrence")},
                manifest_fingerprint,
            )
        if str(poisson_cfg.get("normal_icdf") or "") != "erfinv_v1":
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "poisson_icdf_invalid",
                {"normal_icdf": poisson_cfg.get("normal_icdf")},
                manifest_fingerprint,
            )

        poisson_exact_lambda_max = float(poisson_cfg.get("poisson_exact_lambda_max") or 0.0)
        poisson_n_cap_exact = int(poisson_cfg.get("poisson_n_cap_exact") or 0)
        if poisson_exact_lambda_max <= 0.0 or poisson_n_cap_exact < max_count_per_bucket:
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "poisson_limits_invalid",
                {
                    "poisson_exact_lambda_max": poisson_exact_lambda_max,
                    "poisson_n_cap_exact": poisson_n_cap_exact,
                    "max_count_per_bucket": max_count_per_bucket,
                },
                manifest_fingerprint,
            )

        nb2_cfg = count_config.get("nb2") or {}
        kappa_law = nb2_cfg.get("kappa_law") or {}
        kappa_bounds = tuple(kappa_law.get("kappa_bounds") or [])
        if count_law_id == "nb2":
            if not nb2_cfg:
                _abort(
                    "5B.S3.COUNT_CONFIG_INVALID",
                    "V-04",
                    "nb2_config_missing",
                    {},
                    manifest_fingerprint,
                )
            gamma_cfg = nb2_cfg.get("gamma_sampler") or {}
            if str(gamma_cfg.get("kind") or "") != "gamma_one_u_approx_v1":
                _abort(
                    "5B.S3.COUNT_CONFIG_INVALID",
                    "V-04",
                    "gamma_sampler_invalid",
                    {"kind": gamma_cfg.get("kind")},
                    manifest_fingerprint,
                )
            poisson_on_gamma = nb2_cfg.get("poisson_on_gamma") or {}
            if str(poisson_on_gamma.get("kind") or "") != "cdf_inversion_reuse_u2_v1":
                _abort(
                    "5B.S3.COUNT_CONFIG_INVALID",
                    "V-04",
                    "poisson_on_gamma_invalid",
                    {"kind": poisson_on_gamma.get("kind")},
                    manifest_fingerprint,
                )
            if len(kappa_bounds) != 2:
                _abort(
                    "5B.S3.COUNT_CONFIG_INVALID",
                    "V-04",
                    "kappa_bounds_invalid",
                    {"kappa_bounds": kappa_bounds},
                    manifest_fingerprint,
                )

        realism = count_config.get("realism_floors") or {}
        max_count_floor = int(realism.get("max_count_per_bucket_min") or 0)
        lambda_zero_eps_max = float(realism.get("lambda_zero_eps_max") or 0.0)
        require_kappa_distinct = int(realism.get("require_kappa_distinct_values_min") or 0)
        if max_count_floor <= 0 or max_count_per_bucket < max_count_floor:
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "max_count_floor_failed",
                {"max_count_per_bucket": max_count_per_bucket, "min_required": max_count_floor},
                manifest_fingerprint,
            )
        if lambda_zero_eps_max > 0.0 and lambda_zero_eps > lambda_zero_eps_max:
            _abort(
                "5B.S3.COUNT_CONFIG_INVALID",
                "V-04",
                "lambda_zero_eps_too_large",
                {"lambda_zero_eps": lambda_zero_eps, "max": lambda_zero_eps_max},
                manifest_fingerprint,
            )

        if str(rng_policy.get("rng_engine") or "") != "philox2x64-10":
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "rng_engine_invalid",
                {"rng_engine": rng_policy.get("rng_engine")},
                manifest_fingerprint,
            )
        if str(rng_policy.get("uniform_law") or "") != "open_interval_u64":
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "uniform_law_invalid",
                {"uniform_law": rng_policy.get("uniform_law")},
                manifest_fingerprint,
            )

        families = rng_policy.get("families") or []
        s3_family = None
        for family in families:
            if family.get("module") == "5B.S3" and family.get("substream_label") == "bucket_count":
                s3_family = family
                break
        if not s3_family:
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "rng_family_missing",
                {"module": "5B.S3", "substream_label": "bucket_count"},
                manifest_fingerprint,
            )
        family_id = str(s3_family.get("family_id") or "")
        if not family_id:
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "family_id_missing",
                {"family": s3_family},
                manifest_fingerprint,
            )
        if str(s3_family.get("domain_key_law") or "") != "merchant_zone_bucket":
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "domain_key_law_invalid",
                {"domain_key_law": s3_family.get("domain_key_law")},
                manifest_fingerprint,
            )
        draws_law = s3_family.get("draws_u64_law") or {}
        if str(draws_law.get("kind") or "") != "by_count_law":
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "draws_law_invalid",
                {"draws_law": draws_law},
                manifest_fingerprint,
            )
        when_lambda_zero = draws_law.get("when_lambda_zero")
        try:
            when_lambda_zero_int = int(when_lambda_zero)
        except (TypeError, ValueError):
            when_lambda_zero_int = None
        if when_lambda_zero_int != 0:
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "draws_law_zero_invalid",
                {"when_lambda_zero": when_lambda_zero},
                manifest_fingerprint,
            )
        laws = draws_law.get("laws") or {}
        if int(laws.get("poisson") or -1) != 1 or int(laws.get("nb2") or -1) != 2:
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "draws_law_budget_invalid",
                {"laws": laws},
                manifest_fingerprint,
            )

        domain_sep = str((rng_policy.get("derivation") or {}).get("domain_sep") or "")
        if not domain_sep:
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "domain_sep_missing",
                {"derivation": rng_policy.get("derivation")},
                manifest_fingerprint,
            )

        if not _HEX64_PATTERN.match(str(manifest_fingerprint)):
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "manifest_fingerprint_invalid",
                {"manifest_fingerprint": manifest_fingerprint},
                manifest_fingerprint,
            )
        if not _HEX64_PATTERN.match(str(parameter_hash)):
            _abort(
                "5B.S3.RNG_POLICY_INVALID",
                "V-04",
                "parameter_hash_invalid",
                {"parameter_hash": parameter_hash},
                manifest_fingerprint,
            )

        event_entry = find_dataset_entry(dictionary_5b, "rng_event_arrival_bucket_count").entry
        trace_entry = find_dataset_entry(dictionary_5b, "rng_trace_log").entry
        audit_entry = find_dataset_entry(dictionary_5b, "rng_audit_log").entry

        event_path = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens)
        event_root = _event_root_from_path(event_path)
        event_paths = _iter_jsonl_paths(event_root) if event_root.exists() else []
        event_enabled = enable_rng_events and not event_paths
        if not enable_rng_events:
            logger.info("S3: rng_event logging disabled; emitting rng_trace_log only")
        elif event_paths:
            logger.info("S3: rng_event logs already exist; skipping new emission")

        trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
        trace_mode = "create"
        if trace_path.exists():
            trace_mode = (
                "skip"
                if _trace_has_substream(trace_path, "5B.S3", "bucket_count")
                else "append"
            )

        if event_enabled and trace_mode == "skip":
            _abort(
                "5B.S3.RNG_ACCOUNTING_MISMATCH",
                "V-05",
                "rng_trace_without_events",
                {"detail": "trace already has substream but events are missing"},
                manifest_fingerprint,
            )

        trace_handle = None
        trace_acc = None
        trace_tmp_path = None
        if trace_mode == "create":
            trace_tmp_path = run_paths.tmp_root / f"s3_trace_{uuid.uuid4().hex}.jsonl"
            trace_handle = trace_tmp_path.open("w", encoding="utf-8")
            if not use_parallel:
                trace_acc = RngTraceAccumulator()
        elif trace_mode == "append":
            trace_handle = trace_path.open("a", encoding="utf-8")
            if not use_parallel:
                trace_acc = RngTraceAccumulator()
        logger.info("S3: rng_trace_log mode=%s", trace_mode)

        if event_paths and trace_mode == "append" and trace_acc is not None:
            _append_trace_from_events(event_root, trace_handle, trace_acc, logger)

        audit_payload = {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": str(run_id),
            "seed": int(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "algorithm": "philox2x64-10",
            "build_commit": _resolve_git_hash(config.repo_root),
            "code_digest": None,
            "hostname": platform.node(),
            "platform": platform.platform(),
            "notes": None,
        }
        audit_payload = {key: value for key, value in audit_payload.items() if value is not None}
        _validate_payload(schema_layer1, schema_layer1, schema_layer1, "rng/core/rng_audit_log/record", audit_payload)
        _ensure_rng_audit(_resolve_dataset_path(audit_entry, run_paths, config.external_roots, tokens), audit_payload, logger)

        event_schema = None
        event_validator = None
        if event_enabled:
            event_schema = _schema_from_pack(schema_layer1, "rng/events/arrival_bucket_count")
            event_schema = normalize_nullable_schema(event_schema)
            event_validator = Draft202012Validator(event_schema)

        event_tmp_dir = None
        event_handle = None
        if event_enabled:
            event_tmp_dir = run_paths.tmp_root / f"s3_rng_events_{uuid.uuid4().hex}"
            event_tmp_dir.mkdir(parents=True, exist_ok=True)
            if not use_parallel:
                event_tmp_path = _event_file_from_root(event_tmp_dir)
                event_handle = event_tmp_path.open("w", encoding="utf-8")

        event_buffer: list[str] = []
        trace_buffer: list[str] = []

        def _flush_rng_buffers() -> None:
            if event_handle is not None and event_buffer:
                event_handle.write("\n".join(event_buffer))
                event_handle.write("\n")
                event_buffer.clear()
            if trace_handle is not None and trace_buffer:
                trace_handle.write("\n".join(trace_buffer))
                trace_handle.write("\n")
                trace_buffer.clear()

        for scenario_id in scenario_set:
            current_phase = f"scenario:{scenario_id}"
            logger.info(
                "S3: scenario=%s preparing time grid, grouping, and realised intensities for count draws",
                scenario_id,
            )

            time_grid_entry = find_dataset_entry(dictionary_5b, "s1_time_grid_5B").entry
            grouping_entry = find_dataset_entry(dictionary_5b, "s1_grouping_5B").entry
            realised_entry = find_dataset_entry(dictionary_5b, "s2_realised_intensity_5B").entry

            time_grid_path = _resolve_dataset_path(
                time_grid_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            grouping_path = _resolve_dataset_path(
                grouping_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            realised_path = _resolve_dataset_path(
                realised_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )

            if not time_grid_path.exists():
                _abort(
                    "5B.S3.S1_OUTPUT_MISSING",
                    "V-06",
                    "time_grid_missing",
                    {"scenario_id": scenario_id, "path": str(time_grid_path)},
                    manifest_fingerprint,
                )
            if not grouping_path.exists():
                _abort(
                    "5B.S3.S1_OUTPUT_MISSING",
                    "V-06",
                    "grouping_missing",
                    {"scenario_id": scenario_id, "path": str(grouping_path)},
                    manifest_fingerprint,
                )
            if not realised_path.exists():
                _abort(
                    "5B.S3.S2_OUTPUT_MISSING",
                    "V-06",
                    "realised_missing",
                    {"scenario_id": scenario_id, "path": str(realised_path)},
                    manifest_fingerprint,
                )

            time_grid_df = pl.read_parquet(time_grid_path)
            if time_grid_df.is_empty():
                _abort(
                    "5B.S3.S1_OUTPUT_MISSING",
                    "V-06",
                    "time_grid_empty",
                    {"scenario_id": scenario_id, "path": str(time_grid_path)},
                    manifest_fingerprint,
                )
            bucket_indices = sorted({int(value) for value in time_grid_df.get_column("bucket_index").to_list()})
            bucket_count = len(bucket_indices)
            if not bucket_indices or bucket_indices[0] != 0 or bucket_indices[-1] != bucket_count - 1:
                _abort(
                    "5B.S3.BUCKET_SET_INCONSISTENT",
                    "V-06",
                    "bucket_index_non_contiguous",
                    {"scenario_id": scenario_id, "bucket_count": bucket_count},
                    manifest_fingerprint,
                )
            expected_indices = list(range(bucket_count))
            if bucket_indices != expected_indices:
                _abort(
                    "5B.S3.BUCKET_SET_INCONSISTENT",
                    "V-06",
                    "bucket_index_gap",
                    {"scenario_id": scenario_id, "expected_tail": expected_indices[-1]},
                    manifest_fingerprint,
                )
            scenario_is_baseline = bool(time_grid_df.get_column("scenario_is_baseline")[0])
            scenario_is_stress = bool(time_grid_df.get_column("scenario_is_stress")[0])
            if scenario_is_baseline == scenario_is_stress:
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "scenario_band_invalid",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )
            scenario_band = "baseline" if scenario_is_baseline else "stress"
            total_buckets += bucket_count

            grouping_df = pl.read_parquet(grouping_path)
            if grouping_df.is_empty():
                _abort(
                    "5B.S3.S1_OUTPUT_MISSING",
                    "V-06",
                    "grouping_empty",
                    {"scenario_id": scenario_id, "path": str(grouping_path)},
                    manifest_fingerprint,
                )
            grouping_df = grouping_df.with_columns(
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("zone_representation").cast(pl.Utf8),
                pl.col("channel_group").cast(pl.Utf8),
                pl.col("demand_class").cast(pl.Utf8),
                pl.col("scenario_band").cast(pl.Utf8),
            )
            if grouping_df.filter(pl.col("channel_group").is_null()).height:
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "channel_group_missing",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            duplicate_check = (
                grouping_df.group_by(
                    ["scenario_id", "merchant_id", "zone_representation", "channel_group"]
                )
                .agg(
                    pl.len().alias("rows"),
                    pl.col("group_id").n_unique().alias("group_id_n"),
                )
            )
            conflicting = duplicate_check.filter((pl.col("rows") > 1) & (pl.col("group_id_n") > 1))
            if conflicting.height:
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "grouping_keys_not_unique",
                    {"scenario_id": scenario_id, "conflicts": conflicting.height},
                    manifest_fingerprint,
                )
            unique_rows = grouping_df.unique()
            if unique_rows.height != grouping_df.height:
                logger.warning(
                    "S3: grouping rows contain duplicates; deduplicating (scenario_id=%s rows=%d unique=%d)",
                    scenario_id,
                    grouping_df.height,
                    unique_rows.height,
                )
                grouping_df = unique_rows

            channel_counts = (
                grouping_df.group_by(["merchant_id", "zone_representation"])
                .agg(pl.col("channel_group").n_unique().alias("channel_group_n"))
            )
            if channel_counts.filter(pl.col("channel_group_n") > 1).height:
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "channel_group_multi",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            group_features = (
                grouping_df.group_by("group_id")
                .agg(
                    pl.col("scenario_band").n_unique().alias("scenario_band_n"),
                    pl.col("scenario_band").first().alias("scenario_band"),
                    pl.col("demand_class").n_unique().alias("demand_class_n"),
                    pl.col("demand_class").first().alias("demand_class"),
                )
                .sort("group_id")
            )
            invalid_groups = group_features.filter(
                (pl.col("scenario_band_n") != 1) | (pl.col("demand_class_n") != 1)
            )
            if invalid_groups.height:
                sample = invalid_groups.head(1).to_dicts()[0]
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "group_feature_inconsistent",
                    {"scenario_id": scenario_id, "group_id": sample.get("group_id")},
                    manifest_fingerprint,
                )
            scenario_band_values = group_features.get_column("scenario_band").unique().to_list()
            if len(scenario_band_values) != 1 or scenario_band_values[0] != scenario_band:
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "scenario_band_mismatch",
                    {"scenario_id": scenario_id, "expected": scenario_band, "observed": scenario_band_values},
                    manifest_fingerprint,
                )

            group_ids = group_features.get_column("group_id").to_list()
            group_count = len(group_ids)
            if group_count == 0:
                _abort(
                    "5B.S3.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "group_count_empty",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )
            total_groups += group_count

            group_kappa: dict[str, float] = {}
            kappa_values: list[float] = []
            if count_law_id == "nb2":
                base_by_band = kappa_law.get("base_by_scenario_band") or {}
                class_mult = kappa_law.get("class_multipliers") or {}
                if scenario_band not in base_by_band:
                    _abort(
                        "5B.S3.COUNT_CONFIG_INVALID",
                        "V-06",
                        "kappa_base_missing",
                        {"scenario_band": scenario_band},
                        manifest_fingerprint,
                    )
                base_kappa = float(base_by_band.get(scenario_band))
                kappa_low = float(kappa_bounds[0])
                kappa_high = float(kappa_bounds[1])
                for row in group_features.iter_rows(named=True):
                    group_id = str(row.get("group_id"))
                    demand_class = str(row.get("demand_class"))
                    if demand_class not in class_mult:
                        _abort(
                            "5B.S3.COUNT_CONFIG_INVALID",
                            "V-06",
                            "kappa_multiplier_missing",
                            {"scenario_id": scenario_id, "group_id": group_id, "demand_class": demand_class},
                            manifest_fingerprint,
                        )
                    raw_kappa = base_kappa * float(class_mult[demand_class])
                    kappa = max(min(raw_kappa, kappa_high), kappa_low)
                    if not math.isfinite(kappa) or kappa <= 0.0:
                        _abort(
                            "5B.S3.COUNT_CONFIG_INVALID",
                            "V-06",
                            "kappa_invalid",
                            {"scenario_id": scenario_id, "group_id": group_id, "kappa": kappa},
                            manifest_fingerprint,
                        )
                    group_kappa[group_id] = float(kappa)
                    kappa_values.append(float(kappa))
                if scenario_band == "baseline" and require_kappa_distinct > 0:
                    distinct_kappa = {round(value, 6) for value in kappa_values}
                    if len(distinct_kappa) < require_kappa_distinct:
                        _abort(
                            "5B.S3.COUNT_CONFIG_INVALID",
                            "V-07",
                            "kappa_distinct_floor_failed",
                            {"scenario_id": scenario_id, "distinct_kappa": len(distinct_kappa)},
                            manifest_fingerprint,
                        )
                    median_kappa = float(statistics.median(kappa_values)) if kappa_values else 0.0
                    if not (_KAPPA_MEDIAN_BOUNDS[0] <= median_kappa <= _KAPPA_MEDIAN_BOUNDS[1]):
                        _abort(
                            "5B.S3.COUNT_CONFIG_INVALID",
                            "V-07",
                            "kappa_median_floor_failed",
                            {"scenario_id": scenario_id, "median_kappa": median_kappa, "bounds": _KAPPA_MEDIAN_BOUNDS},
                            manifest_fingerprint,
                        )

            grouping_lookup = grouping_df.select(
                [
                    "scenario_id",
                    "merchant_id",
                    "zone_representation",
                    "channel_group",
                    "group_id",
                    "demand_class",
                    "scenario_band",
                ]
            )
            if count_law_id == "nb2":
                kappa_df = pl.DataFrame(
                    {"group_id": list(group_kappa.keys()), "kappa": list(group_kappa.values())}
                )
                grouping_lookup = grouping_lookup.join(kappa_df, on="group_id", how="left")
                if grouping_lookup.filter(pl.col("kappa").is_null()).height:
                    _abort(
                        "5B.S3.COUNT_CONFIG_INVALID",
                        "V-06",
                        "kappa_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

            time_grid_lookup = (
                time_grid_df.select(["bucket_index", "bucket_duration_seconds"])
                .unique(subset=["bucket_index"])
                .sort("bucket_index")
            )

            draws_per_row = 1 if count_law_id == "poisson" else 2
            blocks_per_row = int((draws_per_row + 1) // 2)

            realised_files = _list_parquet_files(realised_path)
            rows_total = _count_parquet_rows(realised_files)
            logger.info(
                "S3: processing realised intensities for counts (scenario_id=%s files=%d rows=%s)",
                scenario_id,
                len(realised_files),
                rows_total,
            )
            tracker = _ProgressTracker(
                rows_total,
                logger,
                f"S3: bucket counts (scenario_id={scenario_id})",
                min_interval_seconds=progress_interval_seconds,
            )

            counts_entry = find_dataset_entry(dictionary_5b, "s3_bucket_counts_5B").entry
            counts_path = _resolve_dataset_path(
                counts_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            counts_tmp_dir = run_paths.tmp_root / f"s3_counts_{uuid.uuid4().hex}"
            counts_tmp_dir.mkdir(parents=True, exist_ok=True)
            counts_tmp_path = counts_tmp_dir / counts_path.name

            writer = None
            counts_chunks: list[pl.DataFrame] = []
            counts_rows = 0
            counts_sum = 0
            counts_capped = 0
            scenario_count_min: Optional[int] = None
            scenario_count_max: Optional[int] = None
            scenario_mu_min: Optional[float] = None
            scenario_mu_max: Optional[float] = None

            sample_remaining = output_sample_rows

            last_key: Optional[tuple] = None
            ordering_violations = 0
            ordering_violation_sample: Optional[tuple[tuple, tuple]] = None

            batch_index = 0
            event_schema_payload = event_schema if (validate_events_full or validate_events_limit > 0) else None
            event_dir = str(event_tmp_dir) if event_tmp_dir is not None else None

            def _batch_payloads() -> Iterator[tuple[int, tuple, pl.DataFrame, np.ndarray]]:
                nonlocal batch_index
                for batch in _iter_parquet_batches(
                    realised_files,
                    [
                        "scenario_id",
                        "merchant_id",
                        "zone_representation",
                        "channel_group",
                        "bucket_index",
                        "lambda_realised",
                    ],
                ):
                    if _HAVE_PYARROW and hasattr(batch, "column"):
                        batch_df = pl.from_arrow(batch)
                    else:
                        batch_df = batch
                    if batch_df.is_empty():
                        continue
                    tracker.update(batch_df.height)

                    if batch_df.filter(pl.col("scenario_id") != scenario_id).height:
                        _abort(
                            "5B.S3.DOMAIN_ALIGN_FAILED",
                            "V-08",
                            "scenario_id_mismatch",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )
                    if batch_df.filter(pl.col("channel_group").is_null()).height:
                        _abort(
                            "5B.S3.DOMAIN_ALIGN_FAILED",
                            "V-08",
                            "channel_group_missing",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )

                    batch_df = batch_df.with_columns(
                        pl.col("merchant_id").cast(pl.UInt64),
                        pl.col("zone_representation").cast(pl.Utf8),
                        pl.col("channel_group").cast(pl.Utf8),
                        pl.col("bucket_index").cast(pl.Int64),
                        pl.col("lambda_realised").cast(pl.Float64),
                    )
                    joined = batch_df.join(
                        grouping_lookup,
                        on=["scenario_id", "merchant_id", "zone_representation", "channel_group"],
                        how="left",
                    )
                    if joined.height != batch_df.height:
                        _abort(
                            "5B.S3.DOMAIN_ALIGN_FAILED",
                            "V-08",
                            "grouping_join_mismatch",
                            {"scenario_id": scenario_id, "rows": batch_df.height, "joined": joined.height},
                            manifest_fingerprint,
                        )
                    if joined.filter(pl.col("group_id").is_null()).height:
                        _abort(
                            "5B.S3.COUNTS_DOMAIN_INCOMPLETE",
                            "V-08",
                            "group_id_missing",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )
                    joined = joined.join(time_grid_lookup, on="bucket_index", how="left")
                    if joined.filter(pl.col("bucket_duration_seconds").is_null()).height:
                        _abort(
                            "5B.S3.BUCKET_SET_INCONSISTENT",
                            "V-08",
                            "bucket_index_missing",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )

                    mu_array = np.asarray(joined.get_column("lambda_realised").to_numpy(), dtype=np.float64)
                    if not np.isfinite(mu_array).all():
                        _abort(
                            "5B.S3.COUNTS_NUMERIC_INVALID",
                            "V-08",
                            "lambda_realised_invalid",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )
                    if (mu_array < 0.0).any():
                        _abort(
                            "5B.S3.COUNTS_NUMERIC_INVALID",
                            "V-08",
                            "lambda_realised_negative",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )

                    merchant_ids = joined.get_column("merchant_id").to_numpy()
                    zone_values = joined.get_column("zone_representation").to_list()
                    bucket_indices_batch = joined.get_column("bucket_index").to_numpy()
                    group_ids_batch = joined.get_column("group_id").to_list()
                    if count_law_id == "nb2":
                        kappa_values = joined.get_column("kappa").to_numpy()
                    else:
                        kappa_values = None

                    payload = (
                        batch_index,
                        str(scenario_id),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        int(seed),
                        str(run_id),
                        str(count_law_id),
                        float(lambda_zero_eps),
                        int(max_count_per_bucket),
                        float(poisson_exact_lambda_max),
                        int(poisson_n_cap_exact),
                        str(domain_sep),
                        str(family_id),
                        np.asarray(mu_array, dtype=np.float64),
                        merchant_ids,
                        zone_values,
                        bucket_indices_batch,
                        group_ids_batch,
                        kappa_values,
                        event_dir,
                        int(draws_per_row),
                        int(blocks_per_row),
                        int(event_buffer_size),
                        bool(validate_events_full),
                        int(validate_events_limit),
                        event_schema_payload,
                    )
                    current_index = batch_index
                    batch_index += 1
                    yield current_index, payload, joined, mu_array

            def _handle_result(result: dict, joined: pl.DataFrame, mu_array: np.ndarray) -> None:
                nonlocal counts_rows
                nonlocal total_rows_written
                nonlocal counts_sum
                nonlocal counts_capped
                nonlocal scenario_count_min
                nonlocal scenario_count_max
                nonlocal scenario_mu_min
                nonlocal scenario_mu_max
                nonlocal writer
                nonlocal counts_chunks
                nonlocal rng_events_total
                nonlocal rng_draws_total
                nonlocal rng_blocks_total
                nonlocal sample_remaining
                nonlocal last_key
                nonlocal ordering_violations
                nonlocal ordering_violation_sample

                count_array = np.asarray(result.get("count_array"), dtype=np.int64)
                capped_array = np.asarray(result.get("capped_array"), dtype=bool)

                output_df = joined.select(
                    pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
                    pl.lit(str(parameter_hash)).alias("parameter_hash"),
                    pl.lit(int(seed)).cast(pl.UInt64).alias("seed"),
                    pl.col("scenario_id").cast(pl.Utf8),
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("zone_representation").cast(pl.Utf8),
                    pl.col("channel_group").cast(pl.Utf8),
                    pl.col("bucket_index").cast(pl.Int64),
                    pl.Series("lambda_realised", mu_array).cast(pl.Float64),
                    pl.Series("mu", mu_array).cast(pl.Float64),
                    pl.Series("count_N", count_array).cast(pl.Int64),
                    pl.Series("count_capped", capped_array).cast(pl.Boolean),
                    pl.col("bucket_duration_seconds").cast(pl.Int64),
                    pl.lit(count_law_id).alias("count_law_id"),
                    pl.lit(spec_version).cast(pl.Utf8).alias("s3_spec_version"),
                )

                if output_validate_full:
                    _validate_array_rows(
                        output_df.iter_rows(named=True),
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        "model/s3_bucket_counts_5B",
                        logger=logger,
                        label=f"S3: validate counts (scenario_id={scenario_id})",
                        total_rows=output_df.height,
                    )
                elif sample_remaining > 0:
                    sample_chunk = output_df.head(min(sample_remaining, output_df.height))
                    _validate_dataframe_fast(
                        sample_chunk,
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        "model/s3_bucket_counts_5B",
                        logger=logger,
                        label=f"s3_bucket_counts_5B scenario_id={scenario_id}",
                        sample_rows=sample_chunk.height,
                    )
                    sample_remaining -= sample_chunk.height

                if output_df.height:
                    counts_rows += output_df.height
                    total_rows_written += output_df.height
                    counts_sum += int(count_array.sum())
                    counts_capped += int(capped_array.sum())
                    batch_count_min = int(count_array.min()) if count_array.size else 0
                    batch_count_max = int(count_array.max()) if count_array.size else 0
                    batch_mu_min = float(mu_array.min()) if mu_array.size else 0.0
                    batch_mu_max = float(mu_array.max()) if mu_array.size else 0.0
                    scenario_count_min = (
                        batch_count_min if scenario_count_min is None else min(scenario_count_min, batch_count_min)
                    )
                    scenario_count_max = (
                        batch_count_max if scenario_count_max is None else max(scenario_count_max, batch_count_max)
                    )
                    scenario_mu_min = (
                        batch_mu_min if scenario_mu_min is None else min(scenario_mu_min, batch_mu_min)
                    )
                    scenario_mu_max = (
                        batch_mu_max if scenario_mu_max is None else max(scenario_mu_max, batch_mu_max)
                    )

                if _HAVE_PYARROW:
                    table = output_df.to_arrow()
                    if writer is None:
                        writer = pq.ParquetWriter(counts_tmp_path, table.schema, compression="zstd")
                    writer.write_table(table)
                else:
                    counts_chunks.append(output_df)

                rng_events_total += int(result.get("rng_events") or 0)
                rng_draws_total += int(result.get("rng_draws") or 0)
                rng_blocks_total += int(result.get("rng_blocks") or 0)
                last_counters = result.get("last_counters")
                if trace_handle is not None and last_counters:
                    counter_hi, counter_lo, expected_hi, expected_lo = last_counters
                    trace_row = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "run_id": str(run_id),
                        "seed": int(seed),
                        "module": "5B.S3",
                        "substream_label": "bucket_count",
                        "rng_counter_before_lo": int(counter_lo),
                        "rng_counter_before_hi": int(counter_hi),
                        "rng_counter_after_lo": int(expected_lo),
                        "rng_counter_after_hi": int(expected_hi),
                        "draws_total": int(rng_draws_total),
                        "blocks_total": int(rng_blocks_total),
                        "events_total": int(rng_events_total),
                    }
                    trace_handle.write(_json_dumps(trace_row))
                    trace_handle.write("\n")

                if ordering_stats_enabled:
                    merchants = output_df.get_column("merchant_id").to_numpy()
                    zones = output_df.get_column("zone_representation").to_list()
                    buckets = output_df.get_column("bucket_index").to_numpy()
                    for idx in range(output_df.height):
                        key_tuple = (
                            scenario_id,
                            int(merchants[idx]),
                            str(zones[idx]),
                            int(buckets[idx]),
                        )
                        if last_key is not None and key_tuple < last_key:
                            ordering_violations += 1
                            if ordering_violation_sample is None:
                                ordering_violation_sample = (last_key, key_tuple)
                            if strict_ordering:
                                _abort(
                                    "5B.S3.DOMAIN_ALIGN_FAILED",
                                    "V-08",
                                    "ordering_violation",
                                    {"scenario_id": scenario_id},
                                    manifest_fingerprint,
                                )
                        last_key = key_tuple

            executor = None
            pending: deque[tuple[int, pl.DataFrame, np.ndarray, concurrent.futures.Future]] = deque()
            try:
                if use_parallel:
                    executor = concurrent.futures.ProcessPoolExecutor(max_workers=worker_count)
                    for batch_id, payload, joined, mu_array in _batch_payloads():
                        future = executor.submit(_process_counts_batch_star, payload)
                        pending.append((batch_id, joined, mu_array, future))
                        if len(pending) >= max_inflight:
                            queued_id, queued_joined, queued_mu, queued_future = pending.popleft()
                            result = queued_future.result()
                            if result.get("batch_index") != queued_id:
                                _abort(
                                    "5B.S3.DOMAIN_ALIGN_FAILED",
                                    "V-08",
                                    "batch_index_mismatch",
                                    {"scenario_id": scenario_id, "expected": queued_id, "actual": result.get("batch_index")},
                                    manifest_fingerprint,
                                )
                            _handle_result(result, queued_joined, queued_mu)
                    while pending:
                        queued_id, queued_joined, queued_mu, queued_future = pending.popleft()
                        result = queued_future.result()
                        if result.get("batch_index") != queued_id:
                            _abort(
                                "5B.S3.DOMAIN_ALIGN_FAILED",
                                "V-08",
                                "batch_index_mismatch",
                                {"scenario_id": scenario_id, "expected": queued_id, "actual": result.get("batch_index")},
                                manifest_fingerprint,
                            )
                        _handle_result(result, queued_joined, queued_mu)
                else:
                    for batch_id, payload, joined, mu_array in _batch_payloads():
                        result = _process_counts_batch_star(payload)
                        if result.get("batch_index") != batch_id:
                            _abort(
                                "5B.S3.DOMAIN_ALIGN_FAILED",
                                "V-08",
                                "batch_index_mismatch",
                                {"scenario_id": scenario_id, "expected": batch_id, "actual": result.get("batch_index")},
                                manifest_fingerprint,
                            )
                        _handle_result(result, joined, mu_array)
            finally:
                if executor is not None:
                    executor.shutdown(wait=True, cancel_futures=False)
            if writer is not None:
                writer.close()
            elif counts_chunks:
                counts_all = pl.concat(counts_chunks)
                counts_all.write_parquet(counts_tmp_path, compression="zstd")

            if counts_rows == 0:
                _abort(
                    "5B.S3.COUNTS_DOMAIN_INCOMPLETE",
                    "V-08",
                    "counts_empty",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            _publish_parquet_file_idempotent(
                counts_tmp_path,
                counts_path,
                logger,
                f"s3_bucket_counts_5B scenario_id={scenario_id}",
                "5B.S3.IO_WRITE_CONFLICT",
                "5B.S3.IO_WRITE_FAILED",
            )
            counts_paths.append(counts_path)

            if ordering_stats_enabled and ordering_violations:
                logger.warning(
                    "S3: input ordering not sorted; preserving stream order (scenario_id=%s violations=%d first_violation=%s)",
                    scenario_id,
                    ordering_violations,
                    ordering_violation_sample,
                )
            elif ordering_stats_enabled:
                logger.info("S3: input ordering check passed (scenario_id=%s)", scenario_id)

            total_counts += counts_sum
            count_capped_total += counts_capped
            if scenario_count_min is not None:
                if count_min is None or scenario_count_min < count_min:
                    count_min = scenario_count_min
                if count_max is None or scenario_count_max > count_max:
                    count_max = scenario_count_max
            if scenario_mu_min is not None:
                if mu_min is None or scenario_mu_min < mu_min:
                    mu_min = scenario_mu_min
                if mu_max is None or scenario_mu_max > mu_max:
                    mu_max = scenario_mu_max

            scenario_details[scenario_id] = {
                "bucket_count": bucket_count,
                "group_count": group_count,
                "count_rows": counts_rows,
                "sum_count_N": counts_sum,
                "count_min": scenario_count_min,
                "count_max": scenario_count_max,
                "mu_min": scenario_mu_min,
                "mu_max": scenario_mu_max,
                "count_capped": counts_capped,
                "ordering_violations": ordering_violations if ordering_stats_enabled else None,
            }
            scenario_count_succeeded += 1
            timer.info("S3: scenario %s completed (rows=%d)", scenario_id, counts_rows)

            _flush_rng_buffers()

        if event_handle is not None:
            _flush_rng_buffers()
            event_handle.close()
        if trace_handle is not None:
            _flush_rng_buffers()
            trace_handle.close()

        if event_enabled and event_tmp_dir is not None:
            _atomic_publish_dir(event_tmp_dir, event_root, logger, "rng_event_arrival_bucket_count")
        if trace_mode == "create" and trace_tmp_path is not None:
            _atomic_publish_file(trace_tmp_path, trace_path, logger, "rng_trace_log")

        status = "PASS"
        timer.info("S3: completed bucket-level arrival counts")
    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        status = "FAIL"
        error_code = error_code or "5B.S3.IO_WRITE_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # pragma: no cover - unexpected error
        status = "FAIL"
        error_code = error_code or "5B.S3.IO_WRITE_FAILED"
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
                run_report_payload = {
                    "layer": "layer2",
                    "segment": SEGMENT,
                    "state": STATE,
                    "state_id": "5B.S3",
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
                    "total_rows_written": total_rows_written,
                    "total_bucket_count": total_buckets,
                    "total_group_count": total_groups,
                    "sum_count_N": total_counts,
                    "count_min": count_min,
                    "count_max": count_max,
                    "mu_min": mu_min,
                    "mu_max": mu_max,
                    "count_capped": count_capped_total,
                    "count_rng_event_count": rng_events_total,
                    "count_rng_total_draws": rng_draws_total,
                    "count_rng_total_blocks": rng_blocks_total,
                    "details": scenario_details,
                }
                if error_context:
                    run_report_payload["error_context"] = error_context
                    run_report_payload["first_failure_phase"] = first_failure_phase

                _append_jsonl(run_report_path, run_report_payload)
                logger.info("S3: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S3: failed to write segment_state_runs: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "5B.S3.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if run_report_path is None or run_paths is None:
        raise EngineFailure(
            "F4",
            "5B.S3.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing run_report_path or run_paths"},
        )

    return S3Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        counts_paths=counts_paths,
        run_report_path=run_report_path,
    )
