"""Segment 5B S4 arrival events."""

from __future__ import annotations

import bisect
import concurrent.futures
import calendar
import datetime
import hashlib
import json
import math
import mmap
import os
import platform
import re
import struct
import subprocess
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

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
from engine.layers.l2.seg_5B.s4_arrival_events import numba_kernel as s4_numba
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


MODULE_NAME = "5B.s4_arrival_events"
SEGMENT = "5B"
STATE = "S4"
BATCH_SIZE = 200_000
UINT64_MASK = 0xFFFFFFFFFFFFFFFF
UINT64_MAX = UINT64_MASK
TWO_NEG_64 = float.fromhex("0x1.0000000000000p-64")
_MICROS_PER_SECOND = 1_000_000
_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
_TZ_CACHE_MAGIC = b"TZC1"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_S4_EVENT_UINT64_COLUMNS = {"seed", "merchant_id", "site_id", "edge_id"}
_S4_EVENT_INT64_COLUMNS = {"bucket_index", "arrival_seq"}
_S4_SUMMARY_UINT64_COLUMNS = {"seed", "merchant_id"}
_S4_SUMMARY_INT64_COLUMNS = {"bucket_index", "count_N", "count_physical", "count_virtual"}
_S4_EVENT_SCHEMA = [
    ("manifest_fingerprint", pl.Utf8),
    ("parameter_hash", pl.Utf8),
    ("seed", pl.UInt64),
    ("scenario_id", pl.Utf8),
    ("merchant_id", pl.UInt64),
    ("zone_representation", pl.Utf8),
    ("channel_group", pl.Utf8),
    ("bucket_index", pl.Int64),
    ("arrival_seq", pl.Int64),
    ("ts_utc", pl.Utf8),
    ("tzid_primary", pl.Utf8),
    ("ts_local_primary", pl.Utf8),
    ("tzid_settlement", pl.Utf8),
    ("ts_local_settlement", pl.Utf8),
    ("tzid_operational", pl.Utf8),
    ("ts_local_operational", pl.Utf8),
    ("tz_group_id", pl.Utf8),
    ("site_id", pl.UInt64),
    ("edge_id", pl.UInt64),
    ("routing_universe_hash", pl.Utf8),
    ("lambda_realised", pl.Float64),
    ("is_virtual", pl.Boolean),
    ("s4_spec_version", pl.Utf8),
]
_S4_SUMMARY_SCHEMA = [
    ("manifest_fingerprint", pl.Utf8),
    ("parameter_hash", pl.Utf8),
    ("seed", pl.UInt64),
    ("scenario_id", pl.Utf8),
    ("merchant_id", pl.UInt64),
    ("zone_representation", pl.Utf8),
    ("channel_group", pl.Utf8),
    ("bucket_index", pl.Int64),
    ("count_N", pl.Int64),
    ("count_physical", pl.Int64),
    ("count_virtual", pl.Int64),
    ("s4_spec_version", pl.Utf8),
]
_VIRTUAL_MODE_BY_CODE = ("NON_VIRTUAL", "HYBRID", "VIRTUAL_ONLY")
_VIRTUAL_MODE_CODE = {name: idx for idx, name in enumerate(_VIRTUAL_MODE_BY_CODE)}


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    event_paths: list[Path]
    summary_paths: list[Path]
    run_report_path: Path


_S4_WORKER_CONTEXT: dict[str, object] = {}


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


def _coerce_int_columns(df: pl.DataFrame, uint64_cols: set[str], int64_cols: set[str]) -> pl.DataFrame:
    casts: list[pl.Expr] = []
    columns = set(df.columns)
    for name in uint64_cols:
        if name in columns:
            casts.append(pl.col(name).cast(pl.UInt64))
    for name in int64_cols:
        if name in columns:
            casts.append(pl.col(name).cast(pl.Int64))
    if not casts:
        return df
    return df.with_columns(casts)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l2.seg_5B.s4_arrival_events.runner")
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
    item_schema = dict(items_schema)
    parent_defs = schema.get("$defs") or {}
    if parent_defs:
        merged_defs = dict(parent_defs)
        if isinstance(item_schema.get("$defs"), dict):
            merged_defs.update(item_schema.get("$defs", {}))
        item_schema["$defs"] = merged_defs
    return item_schema


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
            "S4: %s schema validated (mode=fast sample_rows=%s total_rows=%s)",
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


def _sum_parquet_column(paths: Iterable[Path], column: str) -> Optional[int]:
    total = 0
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            for rg in range(pf.num_row_groups):
                table = pf.read_row_group(rg, columns=[column])
                col = table.column(column)
                if pa and pa.types.is_integer(col.type):
                    if hasattr(pa, "compute"):
                        total += int(pa.compute.sum(col).as_py())
                    else:
                        total += int(np.nansum(col.to_numpy()))
                else:
                    total += int(np.nansum(col.to_numpy()))
        return total
    for path in paths:
        df = pl.read_parquet(path, columns=[column])
        total += int(df.get_column(column).sum())
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


def _event_file_from_root(root: Path, suffix: str = "part-00000.jsonl") -> Path:
    if root.is_file():
        return root
    return root / suffix


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
                        "5B.S4.RNG_ACCOUNTING_MISMATCH",
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
    event_root: Path, trace_handle, trace_acc: RngTraceAccumulator, logger, label: str
) -> int:
    event_paths = _iter_jsonl_paths(event_root)
    if not event_paths:
        raise EngineFailure(
            "F4",
            "5B.S4.RNG_ACCOUNTING_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": "no_event_jsonl_files", "path": str(event_root)},
        )
    rows_written = 0
    for event in _iter_jsonl_rows(event_paths, label):
        trace_row = trace_acc.append_event(event)
        trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
        trace_handle.write("\n")
        rows_written += 1
    logger.info("S4: appended trace rows from existing events label=%s rows=%d", label, rows_written)
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
                    logger.info("S4: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S4: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S4: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash = _hash_partition(tmp_root)
        final_hash = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "5B.S4.IO_WRITE_CONFLICT",
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
        logger.info("S4: %s partition already exists and is identical; skipping publish.", label)
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
                "5B.S4.IO_WRITE_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S4: %s file already exists and is identical; skipping publish.", label)
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


def _parse_rfc3339_micros(value: str) -> int:
    dt = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    return calendar.timegm(dt.timetuple()) * _MICROS_PER_SECOND + dt.microsecond


def _format_rfc3339_micros(micros: int) -> str:
    seconds, micro = divmod(int(micros), _MICROS_PER_SECOND)
    dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc).replace(microsecond=micro)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _utc_day_from_micros(micros: int) -> str:
    seconds, micro = divmod(int(micros), _MICROS_PER_SECOND)
    dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc).replace(microsecond=micro)
    return dt.date().isoformat()


def _decode_tz_cache(cache_root: Path, logger) -> dict[str, tuple[list[int], list[int]]]:
    cache_path = cache_root / "tz_cache_v1.bin"
    if not cache_path.exists():
        raise InputResolutionError(f"Missing tz cache binary: {cache_path}")
    data = cache_path.read_bytes()
    if len(data) < 10:
        raise InputResolutionError("tz cache binary too small")
    view = memoryview(data)
    offset = 0
    magic = view[offset : offset + 4].tobytes()
    if magic != _TZ_CACHE_MAGIC:
        raise InputResolutionError("tz cache magic mismatch")
    offset += 4
    version = struct.unpack_from("<H", view, offset)[0]
    offset += 2
    tz_count = struct.unpack_from("<I", view, offset)[0]
    offset += 4
    tz_map: dict[str, tuple[list[int], list[int]]] = {}
    for _ in range(tz_count):
        if offset + 2 > len(view):
            raise InputResolutionError("tz cache truncated (tzid length)")
        name_len = struct.unpack_from("<H", view, offset)[0]
        offset += 2
        if offset + name_len > len(view):
            raise InputResolutionError("tz cache truncated (tzid bytes)")
        tzid = view[offset : offset + name_len].tobytes().decode("ascii")
        offset += name_len
        if offset + 4 > len(view):
            raise InputResolutionError("tz cache truncated (transition count)")
        transition_count = struct.unpack_from("<I", view, offset)[0]
        offset += 4
        instants: list[int] = []
        offsets: list[int] = []
        for _ in range(int(transition_count)):
            if offset + 12 > len(view):
                raise InputResolutionError("tz cache truncated (transition)")
            instant = struct.unpack_from("<q", view, offset)[0]
            offset += 8
            offset_min = struct.unpack_from("<i", view, offset)[0]
            offset += 4
            instants.append(int(instant))
            offsets.append(int(offset_min))
        tz_map[tzid] = (instants, offsets)
    if offset != len(view):
        logger.info("S4: tz cache trailing bytes ignored (trailing=%d, version=%d)", len(view) - offset, version)
    logger.info("S4: tz cache decoded (tzids=%d, bytes=%d)", len(tz_map), len(view))
    return tz_map


def _save_shared_array(shared_root: Path, name: str, array: np.ndarray) -> str:
    filename = f"{name}.npy"
    np.save(shared_root / filename, array, allow_pickle=False)
    return filename


def _load_shared_array(shared_root: Path, filename: str) -> np.ndarray:
    return np.load(shared_root / filename, mmap_mode="r", allow_pickle=False)


def _lookup_sorted_key(keys: np.ndarray, value: int) -> int:
    if keys.size == 0:
        return -1
    idx = int(np.searchsorted(keys, value))
    if idx < int(keys.size) and int(keys[idx]) == int(value):
        return idx
    return -1


def _lookup_structured_key(keys: np.ndarray, merchant_id: int, second: int, second_field: str) -> int:
    if keys.size == 0:
        return -1
    key = np.array((int(merchant_id), int(second)), dtype=keys.dtype)
    idx = int(np.searchsorted(keys, key))
    if idx < int(keys.size):
        entry = keys[idx]
        if int(entry["merchant_id"]) == int(merchant_id) and int(entry[second_field]) == int(second):
            return idx
    return -1


def _build_shared_maps(
    run_paths: RunPaths,
    manifest_fingerprint: str,
    tz_cache: dict[str, tuple[list[int], list[int]]],
    classification_map: dict[int, dict[str, object]],
    settlement_map: dict[int, str],
    edge_map: dict[int, tuple[list[int], list[str]]],
    edge_alias_meta: dict[int, dict[str, object]],
    edge_alias_blob_path: Optional[Path],
    alias_endianness: str,
    site_alias_map: dict[tuple[int, str], tuple[np.ndarray, np.ndarray, list[int]]],
    fallback_alias_map: dict[int, tuple[np.ndarray, np.ndarray, list[int]]],
    site_tz_lookup: dict[tuple[int, int], str],
    logger,
) -> Path:
    shared_root = run_paths.tmp_root / f"s4_shared_maps_{uuid.uuid4().hex}"
    shared_root.mkdir(parents=True, exist_ok=True)

    tzid_list = sorted(tz_cache.keys())
    tzid_to_index = {tzid: idx for idx, tzid in enumerate(tzid_list)}

    def _tz_index(tzid: str) -> int:
        idx = tzid_to_index.get(tzid)
        if idx is None:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-06",
                "tzid_not_in_cache",
                {"tzid": tzid},
                manifest_fingerprint,
            )
        return int(idx)

    arrays: dict[str, str] = {}

    classification_items = sorted(classification_map.items(), key=lambda item: item[0])
    classification_keys = np.array([item[0] for item in classification_items], dtype=np.uint64)
    classification_modes = np.array(
        [_VIRTUAL_MODE_CODE.get(str(item[1].get("virtual_mode")), -1) for item in classification_items],
        dtype=np.int8,
    )
    if np.any(classification_modes < 0):
        _abort(
            "5B.S4.ROUTING_POLICY_INVALID",
            "V-06",
            "virtual_mode_invalid",
            {"detail": "classification contains unsupported virtual_mode"},
            manifest_fingerprint,
        )
    arrays["classification_keys"] = _save_shared_array(shared_root, "classification_keys", classification_keys)
    arrays["classification_modes"] = _save_shared_array(shared_root, "classification_modes", classification_modes)

    settlement_items = sorted(settlement_map.items(), key=lambda item: item[0])
    settlement_keys = np.array([item[0] for item in settlement_items], dtype=np.uint64)
    settlement_tz_index = np.array([_tz_index(item[1]) for item in settlement_items], dtype=np.int32)
    arrays["settlement_keys"] = _save_shared_array(shared_root, "settlement_keys", settlement_keys)
    arrays["settlement_tz_index"] = _save_shared_array(shared_root, "settlement_tz_index", settlement_tz_index)

    edge_items = sorted(edge_map.items(), key=lambda item: item[0])
    edge_keys = np.array([item[0] for item in edge_items], dtype=np.uint64)
    edge_offsets = np.zeros(len(edge_items), dtype=np.int64)
    edge_counts = np.zeros(len(edge_items), dtype=np.int32)
    edge_ids: list[int] = []
    edge_tz_idx: list[int] = []
    offset = 0
    for idx, (merchant_id, (edge_ids_list, tzids_list)) in enumerate(edge_items):
        count = len(edge_ids_list)
        edge_offsets[idx] = offset
        edge_counts[idx] = count
        for edge_id, tzid in zip(edge_ids_list, tzids_list):
            edge_ids.append(int(edge_id))
            edge_tz_idx.append(_tz_index(str(tzid)))
        offset += count
    arrays["edge_keys"] = _save_shared_array(shared_root, "edge_keys", edge_keys)
    arrays["edge_offsets"] = _save_shared_array(shared_root, "edge_offsets", edge_offsets)
    arrays["edge_counts"] = _save_shared_array(shared_root, "edge_counts", edge_counts)
    arrays["edge_ids"] = _save_shared_array(shared_root, "edge_ids", np.array(edge_ids, dtype=np.uint64))
    arrays["edge_tz_index"] = _save_shared_array(shared_root, "edge_tz_index", np.array(edge_tz_idx, dtype=np.int32))

    edge_alias_items = sorted(edge_alias_meta.items(), key=lambda item: item[0])
    edge_alias_keys = np.array([item[0] for item in edge_alias_items], dtype=np.uint64)
    edge_alias_offsets = np.array([int(item[1]["offset"]) for item in edge_alias_items], dtype=np.int64)
    edge_alias_lengths = np.array([int(item[1]["length"]) for item in edge_alias_items], dtype=np.int64)
    edge_alias_counts = np.array([int(item[1]["edge_count"]) for item in edge_alias_items], dtype=np.int32)
    edge_alias_table_lengths = np.array([int(item[1]["alias_length"]) for item in edge_alias_items], dtype=np.int32)
    arrays["edge_alias_keys"] = _save_shared_array(shared_root, "edge_alias_keys", edge_alias_keys)
    arrays["edge_alias_offsets"] = _save_shared_array(shared_root, "edge_alias_offsets", edge_alias_offsets)
    arrays["edge_alias_lengths"] = _save_shared_array(shared_root, "edge_alias_lengths", edge_alias_lengths)
    arrays["edge_alias_counts"] = _save_shared_array(shared_root, "edge_alias_counts", edge_alias_counts)
    arrays["edge_alias_table_lengths"] = _save_shared_array(
        shared_root, "edge_alias_table_lengths", edge_alias_table_lengths
    )
    if edge_alias_blob_path and s4_numba.numba_available():
        blob_view = _BlobView(edge_alias_blob_path)
        try:
            edge_alias_prob, edge_alias_alias, edge_alias_prob_offsets, edge_alias_prob_counts = (
                s4_numba.build_edge_alias_arrays(
                    edge_keys, edge_alias_meta, blob_view, alias_endianness
                )
            )
        finally:
            blob_view.close()
        arrays["edge_alias_prob"] = _save_shared_array(shared_root, "edge_alias_prob", edge_alias_prob)
        arrays["edge_alias_alias"] = _save_shared_array(shared_root, "edge_alias_alias", edge_alias_alias)
        arrays["edge_alias_prob_offsets"] = _save_shared_array(
            shared_root, "edge_alias_prob_offsets", edge_alias_prob_offsets
        )
        arrays["edge_alias_prob_counts"] = _save_shared_array(
            shared_root, "edge_alias_prob_counts", edge_alias_prob_counts
        )

    fallback_items = sorted(fallback_alias_map.items(), key=lambda item: item[0])
    fallback_keys = np.array([item[0] for item in fallback_items], dtype=np.uint64)
    fallback_offsets = np.zeros(len(fallback_items), dtype=np.int64)
    fallback_counts = np.zeros(len(fallback_items), dtype=np.int32)
    fallback_prob: list[float] = []
    fallback_alias: list[int] = []
    fallback_site_orders: list[int] = []
    offset = 0
    for idx, (merchant_id, (prob, alias, site_orders)) in enumerate(fallback_items):
        count = len(site_orders)
        fallback_offsets[idx] = offset
        fallback_counts[idx] = count
        fallback_prob.extend([float(val) for val in prob])
        fallback_alias.extend([int(val) for val in alias])
        fallback_site_orders.extend([int(val) for val in site_orders])
        offset += count
    arrays["fallback_keys"] = _save_shared_array(shared_root, "fallback_keys", fallback_keys)
    arrays["fallback_offsets"] = _save_shared_array(shared_root, "fallback_offsets", fallback_offsets)
    arrays["fallback_counts"] = _save_shared_array(shared_root, "fallback_counts", fallback_counts)
    arrays["fallback_prob"] = _save_shared_array(
        shared_root, "fallback_prob", np.array(fallback_prob, dtype=np.float64)
    )
    arrays["fallback_alias"] = _save_shared_array(
        shared_root, "fallback_alias", np.array(fallback_alias, dtype=np.int64)
    )
    arrays["fallback_site_orders"] = _save_shared_array(
        shared_root, "fallback_site_orders", np.array(fallback_site_orders, dtype=np.int64)
    )

    site_items: list[tuple[tuple[int, int], tuple[np.ndarray, np.ndarray, list[int]]]] = []
    for (merchant_id, tzid), value in site_alias_map.items():
        site_items.append(((int(merchant_id), _tz_index(str(tzid))), value))
    site_items.sort(key=lambda item: (item[0][0], item[0][1]))
    site_key_dtype = np.dtype([("merchant_id", "<u8"), ("tz_idx", "<i4")])
    site_keys = np.array([item[0] for item in site_items], dtype=site_key_dtype)
    site_offsets = np.zeros(len(site_items), dtype=np.int64)
    site_counts = np.zeros(len(site_items), dtype=np.int32)
    site_prob: list[float] = []
    site_alias: list[int] = []
    site_orders_flat: list[int] = []
    offset = 0
    for idx, (_, (prob, alias, site_orders)) in enumerate(site_items):
        count = len(site_orders)
        site_offsets[idx] = offset
        site_counts[idx] = count
        site_prob.extend([float(val) for val in prob])
        site_alias.extend([int(val) for val in alias])
        site_orders_flat.extend([int(val) for val in site_orders])
        offset += count
    arrays["site_keys"] = _save_shared_array(shared_root, "site_keys", site_keys)
    arrays["site_offsets"] = _save_shared_array(shared_root, "site_offsets", site_offsets)
    arrays["site_counts"] = _save_shared_array(shared_root, "site_counts", site_counts)
    arrays["site_prob"] = _save_shared_array(shared_root, "site_prob", np.array(site_prob, dtype=np.float64))
    arrays["site_alias"] = _save_shared_array(shared_root, "site_alias", np.array(site_alias, dtype=np.int64))
    arrays["site_site_orders"] = _save_shared_array(
        shared_root, "site_site_orders", np.array(site_orders_flat, dtype=np.int64)
    )

    site_tz_items = sorted(site_tz_lookup.items(), key=lambda item: (item[0][0], item[0][1]))
    site_tz_key_dtype = np.dtype([("merchant_id", "<u8"), ("site_id", "<i8")])
    site_tz_keys = np.array([item[0] for item in site_tz_items], dtype=site_tz_key_dtype)
    site_tz_values = np.array([_tz_index(str(item[1])) for item in site_tz_items], dtype=np.int32)
    arrays["site_tz_keys"] = _save_shared_array(shared_root, "site_tz_keys", site_tz_keys)
    arrays["site_tz_values"] = _save_shared_array(shared_root, "site_tz_values", site_tz_values)

    tzid_list_path = shared_root / "tzid_list.json"
    tzid_list_path.write_text(json.dumps(tzid_list, ensure_ascii=True), encoding="utf-8")
    manifest = {"arrays": arrays, "tzid_list": tzid_list_path.name}
    manifest_path = shared_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
    logger.info(
        "S4: shared_maps built root=%s merchants=%d site_alias=%d edge_alias=%d",
        shared_root,
        len(classification_keys),
        len(site_keys),
        len(edge_alias_keys),
    )
    return shared_root


def _load_shared_maps(shared_root: Path) -> dict[str, object]:
    manifest_path = shared_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arrays = {
        name: _load_shared_array(shared_root, filename)
        for name, filename in (manifest.get("arrays") or {}).items()
    }
    tzid_list_path = shared_root / manifest.get("tzid_list", "tzid_list.json")
    tzid_list = json.loads(tzid_list_path.read_text(encoding="utf-8"))
    arrays["tzid_list"] = tzid_list
    return arrays


def _tz_offset_minutes(entry: tuple[list[int], list[int]], instant_seconds: int) -> int:
    instants, offsets = entry
    idx = bisect.bisect_right(instants, int(instant_seconds)) - 1
    if idx < 0:
        idx = 0
    return int(offsets[idx])


def _uer_string_be(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack(">I", len(encoded)) + encoded


def _rng_prefix_bytes(
    domain_sep: str,
    family_id: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
) -> bytes:
    return (
        _uer_string_be(domain_sep)
        + _uer_string_be(family_id)
        + _uer_string_be(manifest_fingerprint)
        + _uer_string_be(parameter_hash)
        + struct.pack("<Q", int(seed) & UINT64_MASK)
        + _uer_string_be(scenario_id)
    )


def _derive_rng_seed_from_prefix(prefix: bytes, domain_key: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(prefix + _uer_string_be(domain_key)).digest()
    key = int.from_bytes(digest[0:8], "big", signed=False)
    counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
    counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
    return key, counter_hi, counter_lo


def _derive_rng_seed(prefix_hasher: hashlib._Hash, domain_key: str) -> tuple[int, int, int]:
    hasher = prefix_hasher.copy()
    hasher.update(_uer_string_be(domain_key))
    digest = hasher.digest()
    key = int.from_bytes(digest[0:8], "big", signed=False)
    counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
    counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
    return key, counter_hi, counter_lo


def _rng_prefix_hasher(
    domain_sep: str,
    family_id: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
) -> hashlib._Hash:
    hasher = hashlib.sha256()
    hasher.update(_uer_string_be(domain_sep))
    hasher.update(_uer_string_be(family_id))
    hasher.update(_uer_string_be(manifest_fingerprint))
    hasher.update(_uer_string_be(parameter_hash))
    hasher.update(struct.pack("<Q", int(seed) & UINT64_MASK))
    hasher.update(_uer_string_be(scenario_id))
    return hasher


def _counter_wrapped(
    counter_hi: int, counter_lo: int, next_hi: int, next_lo: int
) -> bool:
    return next_hi < counter_hi or (next_hi == counter_hi and next_lo < counter_lo)


def _draw_philox_u64(
    key: int,
    counter_hi: int,
    counter_lo: int,
    draws: int,
    manifest_fingerprint: str,
) -> tuple[list[int], int, int, int]:
    blocks = int((draws + 1) // 2)
    values: list[int] = []
    cur_hi, cur_lo = int(counter_hi), int(counter_lo)
    for _ in range(blocks):
        out0, out1 = philox2x64_10(cur_hi, cur_lo, int(key))
        values.append(out0)
        if len(values) < draws:
            values.append(out1)
        next_hi, next_lo = add_u128(cur_hi, cur_lo, 1)
        if _counter_wrapped(cur_hi, cur_lo, next_hi, next_lo):
            _abort(
                "5B.S4.RNG_ACCOUNTING_MISMATCH",
                "V-12",
                "rng_counter_wrap",
                {"detail": "counter wrapped during draws"},
                manifest_fingerprint,
            )
        cur_hi, cur_lo = next_hi, next_lo
    return values, blocks, cur_hi, cur_lo


def _init_s4_worker(context: dict) -> None:
    global _S4_WORKER_CONTEXT
    ctx = dict(context)
    shared_root = ctx.get("shared_maps_root")
    if shared_root:
        ctx["shared_maps"] = _load_shared_maps(Path(shared_root))
    if ctx.get("shared_maps"):
        tzid_list = ctx["shared_maps"].get("tzid_list")
        if tzid_list is not None:
            ctx["tzid_to_index"] = {tzid: idx for idx, tzid in enumerate(tzid_list)}
    blob_path = ctx.get("edge_alias_blob_path")
    if blob_path:
        ctx["blob_view"] = _BlobView(Path(blob_path))
    ctx["edge_alias_cache"] = {}
    time_prefix = ctx.get("time_prefix")
    if time_prefix:
        time_hasher = hashlib.sha256()
        time_hasher.update(time_prefix)
        ctx["time_hasher"] = time_hasher
    site_prefix = ctx.get("site_prefix")
    if site_prefix:
        site_hasher = hashlib.sha256()
        site_hasher.update(site_prefix)
        ctx["site_hasher"] = site_hasher
    edge_prefix = ctx.get("edge_prefix")
    if edge_prefix:
        edge_hasher = hashlib.sha256()
        edge_hasher.update(edge_prefix)
        ctx["edge_hasher"] = edge_hasher
    event_schema = ctx.get("event_schema")
    summary_schema = ctx.get("summary_schema")
    if event_schema is not None:
        ctx["event_row_validator"] = Draft202012Validator(event_schema)
    if summary_schema is not None:
        ctx["summary_row_validator"] = Draft202012Validator(summary_schema)
    if ctx.get("compiled_kernel"):
        shared_maps = ctx.get("shared_maps")
        tzid_list = shared_maps.get("tzid_list") if shared_maps else None
        if tzid_list is not None:
            instants, offsets, offset_offsets, offset_counts = s4_numba.build_tz_cache_arrays(
                tzid_list, ctx.get("tz_cache") or {}
            )
            tz_bytes, tz_offsets, tz_lengths = s4_numba.build_tzid_bytes(tzid_list)
            ctx["tz_instants_flat"] = instants
            ctx["tz_offsets_flat"] = offsets
            ctx["tz_offset_offsets"] = offset_offsets
            ctx["tz_offset_counts"] = offset_counts
            ctx["tzid_bytes"] = tz_bytes
            ctx["tzid_offsets"] = tz_offsets
            ctx["tzid_lengths"] = tz_lengths
        time_prefix = ctx.get("time_prefix")
        if time_prefix:
            ctx["time_prefix_bytes"] = np.frombuffer(time_prefix, dtype=np.uint8)
        site_prefix = ctx.get("site_prefix")
        if site_prefix:
            ctx["site_prefix_bytes"] = np.frombuffer(site_prefix, dtype=np.uint8)
        edge_prefix = ctx.get("edge_prefix")
        if edge_prefix:
            ctx["edge_prefix_bytes"] = np.frombuffer(edge_prefix, dtype=np.uint8)
    _S4_WORKER_CONTEXT = ctx


def _process_s4_batch(payload: dict) -> dict:
    batch_id = int(payload.get("batch_id") or 0)
    try:
        return _process_s4_batch_impl(payload)
    except Exception as exc:
        error_payload = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if isinstance(exc, EngineFailure):
            error_payload.update(
                {
                    "failure_class": exc.failure_class,
                    "failure_code": exc.failure_code,
                    "detail": exc.detail,
                    "dataset_id": exc.dataset_id,
                    "merchant_id": exc.merchant_id,
                }
            )
        return {"batch_id": batch_id, "error": error_payload}


def _process_s4_batch_impl(payload: dict) -> dict:
    ctx = _S4_WORKER_CONTEXT
    if not ctx:
        raise EngineFailure(
            "F4",
            "5B.S4.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "worker context not initialised"},
        )

    batch_id = int(payload["batch_id"])
    scenario_id = str(payload["scenario_id"])
    merchants = payload["merchant_id"]
    zones = payload["zone_representation"]
    channels = payload["channel_group"]
    buckets = payload["bucket_index"]
    counts = payload["count_N"]
    lambdas = payload["lambda_realised"]
    arrival_seq_start = payload["arrival_seq_start"]

    output_validate_full = bool(ctx.get("output_validate_full"))
    output_sample_rows = int(ctx.get("output_sample_rows") or 0)
    output_buffer_rows = int(ctx.get("output_buffer_rows") or 50000)
    event_row_validator = ctx.get("event_row_validator")
    summary_row_validator = ctx.get("summary_row_validator")
    ordering_required = bool(ctx.get("ordering_required"))
    time_hasher = ctx.get("time_hasher")
    site_hasher = ctx.get("site_hasher")
    edge_hasher = ctx.get("edge_hasher")

    events_tmp_dir = Path(ctx["events_tmp_dir"])
    summary_tmp_dir = Path(ctx["summary_tmp_dir"])

    events_path = events_tmp_dir / f"part-{batch_id:06d}.parquet"
    summary_path = summary_tmp_dir / f"part-{batch_id:06d}.parquet"

    events_writer = None
    summary_writer = None
    events_chunks: list[pl.DataFrame] = []
    summary_chunks: list[pl.DataFrame] = []

    manifest_fingerprint = str(ctx["manifest_fingerprint"])
    parameter_hash = str(ctx["parameter_hash"])
    seed = int(ctx["seed"])
    spec_version = str(ctx["spec_version"])

    bucket_map = ctx["bucket_map"]
    tz_cache = ctx["tz_cache"]
    shared_maps = ctx.get("shared_maps")
    tzid_list = shared_maps.get("tzid_list") if shared_maps else None
    tzid_to_index = ctx.get("tzid_to_index")
    if tzid_to_index is None and tzid_list is not None:
        tzid_to_index = {tzid: idx for idx, tzid in enumerate(tzid_list)}
    site_alias_map = ctx.get("site_alias_map") if not shared_maps else None
    fallback_alias_map = ctx.get("fallback_alias_map") if not shared_maps else None
    site_tz_lookup = ctx.get("site_tz_lookup") if not shared_maps else None
    edge_alias_meta = ctx.get("edge_alias_meta") if not shared_maps else None
    edge_map = ctx.get("edge_map") if not shared_maps else None
    settlement_map = ctx.get("settlement_map") if not shared_maps else None
    classification_map = ctx.get("classification_map") if not shared_maps else None
    blob_view = ctx.get("blob_view")
    edge_alias_cache = ctx["edge_alias_cache"]
    alias_endianness = ctx["alias_endianness"]
    group_weights_map = ctx["group_weights_map"]
    skip_group_weight_check = bool(ctx["skip_group_weight_check"])
    classification_keys = classification_modes = None
    settlement_keys = settlement_tz_index = None
    edge_keys = edge_offsets = edge_counts = edge_ids_arr = edge_tz_index = None
    edge_alias_keys = edge_alias_offsets = edge_alias_lengths = edge_alias_counts = edge_alias_table_lengths = None
    site_keys = site_offsets = site_counts = site_prob = site_alias = site_site_orders = None
    fallback_keys = fallback_offsets = fallback_counts = fallback_prob = fallback_alias = fallback_site_orders = None
    site_tz_keys = site_tz_values = None
    if shared_maps:
        classification_keys = shared_maps["classification_keys"]
        classification_modes = shared_maps["classification_modes"]
        settlement_keys = shared_maps["settlement_keys"]
        settlement_tz_index = shared_maps["settlement_tz_index"]
        edge_keys = shared_maps["edge_keys"]
        edge_offsets = shared_maps["edge_offsets"]
        edge_counts = shared_maps["edge_counts"]
        edge_ids_arr = shared_maps["edge_ids"]
        edge_tz_index = shared_maps["edge_tz_index"]
        edge_alias_keys = shared_maps["edge_alias_keys"]
        edge_alias_offsets = shared_maps["edge_alias_offsets"]
        edge_alias_lengths = shared_maps["edge_alias_lengths"]
        edge_alias_counts = shared_maps["edge_alias_counts"]
        edge_alias_table_lengths = shared_maps["edge_alias_table_lengths"]
        site_keys = shared_maps["site_keys"]
        site_offsets = shared_maps["site_offsets"]
        site_counts = shared_maps["site_counts"]
        site_prob = shared_maps["site_prob"]
        site_alias = shared_maps["site_alias"]
        site_site_orders = shared_maps["site_site_orders"]
        fallback_keys = shared_maps["fallback_keys"]
        fallback_offsets = shared_maps["fallback_offsets"]
        fallback_counts = shared_maps["fallback_counts"]
        fallback_prob = shared_maps["fallback_prob"]
        fallback_alias = shared_maps["fallback_alias"]
        fallback_site_orders = shared_maps["fallback_site_orders"]
        site_tz_keys = shared_maps["site_tz_keys"]
        site_tz_values = shared_maps["site_tz_values"]
    zone_alloc_universe_hash = ctx["zone_alloc_universe_hash"]
    edge_universe_hash = ctx["edge_universe_hash"]
    max_arrivals_per_bucket = int(ctx["max_arrivals_per_bucket"])
    p_virtual_hybrid = float(ctx["p_virtual_hybrid"])

    time_prefix = ctx["time_prefix"]
    site_prefix = ctx["site_prefix"]
    edge_prefix = ctx["edge_prefix"]
    draws_per_arrival = int(ctx["draws_per_arrival"])

    def _derive_seed(prefix_hasher, prefix_bytes, domain_key: str) -> tuple[int, int, int]:
        if prefix_hasher is not None:
            return _derive_rng_seed(prefix_hasher, domain_key)
        return _derive_rng_seed_from_prefix(prefix_bytes, domain_key)

    rng_stats = {
        "arrival_time_jitter": {"events": 0, "draws": 0, "blocks": 0, "last": None},
        "arrival_site_pick": {"events": 0, "draws": 0, "blocks": 0, "last": None},
        "arrival_edge_pick": {"events": 0, "draws": 0, "blocks": 0, "last": None},
    }

    missing_group_keys: set[tuple[int, str, str]] = set()
    missing_alias_keys: set[tuple[int, str]] = set()
    compiled_kernel_enabled = bool(ctx.get("compiled_kernel")) and s4_numba.numba_available()

    def _validate_rows(rows: list[dict], validator, label: str) -> None:
        if validator is None:
            return
        if output_validate_full:
            sample = rows
        elif output_sample_rows > 0:
            sample = rows[: min(output_sample_rows, len(rows))]
        else:
            return
        errors: list[dict[str, object]] = []
        for index, row in enumerate(sample):
            for error in validator.iter_errors(row):
                field = ".".join(str(part) for part in error.path) if error.path else ""
                errors.append({"row_index": index, "field": field, "message": error.message})
                if len(errors) >= 5:
                    break
            if errors and len(errors) >= 5:
                break
        if errors:
            lines = [
                f"row {item['row_index']}: {item['field']} {item['message']}".strip()
                for item in errors
            ]
            raise SchemaValidationError(
                f"Schema validation failed ({label}):\n" + "\n".join(lines), errors
            )

    event_schema_names = [name for name, _ in _S4_EVENT_SCHEMA]

    def _sample_rows_from_tuples(rows: list[tuple], limit: int) -> list[dict]:
        sample: list[dict] = []
        for idx in range(limit):
            row = rows[idx]
            row_map: dict[str, object] = {}
            for col_idx, col_name in enumerate(event_schema_names):
                value = row[col_idx]
                if value is None:
                    continue
                row_map[col_name] = value
            sample.append(row_map)
        return sample

    def _write_events(rows: list) -> None:
        nonlocal events_writer
        if not rows:
            return
        if isinstance(rows[0], dict):
            _validate_rows(rows, event_row_validator, "arrival_events")
            df = pl.DataFrame(rows, schema=_S4_EVENT_SCHEMA)
        else:
            if event_row_validator is not None:
                if output_validate_full:
                    sample_limit = len(rows)
                elif output_sample_rows > 0:
                    sample_limit = min(output_sample_rows, len(rows))
                else:
                    sample_limit = 0
                if sample_limit:
                    sample_rows = _sample_rows_from_tuples(rows, sample_limit)
                    _validate_rows(sample_rows, event_row_validator, "arrival_events")
            df = pl.DataFrame(rows, schema=_S4_EVENT_SCHEMA, orient="row")
        df = _coerce_int_columns(df, _S4_EVENT_UINT64_COLUMNS, _S4_EVENT_INT64_COLUMNS)
        if _HAVE_PYARROW and pq is not None:
            table = df.to_arrow()
            if events_writer is None:
                events_writer = pq.ParquetWriter(events_path, table.schema, compression="zstd")
            events_writer.write_table(table)
        else:
            events_chunks.append(df)

    def _write_summary(rows: list[dict]) -> None:
        nonlocal summary_writer
        if not rows:
            return
        _validate_rows(rows, summary_row_validator, "arrival_summary")
        df = pl.DataFrame(rows, schema=_S4_SUMMARY_SCHEMA)
        df = _coerce_int_columns(df, _S4_SUMMARY_UINT64_COLUMNS, _S4_SUMMARY_INT64_COLUMNS)
        if _HAVE_PYARROW and pq is not None:
            table = df.to_arrow()
            if summary_writer is None:
                summary_writer = pq.ParquetWriter(summary_path, table.schema, compression="zstd")
            summary_writer.write_table(table)
        else:
            summary_chunks.append(df)

    total_rows_written = 0
    total_arrivals = 0
    total_physical = 0
    total_virtual = 0

    event_rows: list = []
    summary_rows: list[dict] = []

    compiled_kernel_ready = (
        compiled_kernel_enabled
        and shared_maps is not None
        and skip_group_weight_check
        and group_weights_map is None
    )
    if compiled_kernel_ready:
        tz_instants_flat = ctx.get("tz_instants_flat")
        tz_offsets_flat = ctx.get("tz_offsets_flat")
        tz_offset_offsets = ctx.get("tz_offset_offsets")
        tz_offset_counts = ctx.get("tz_offset_counts")
        tzid_bytes = ctx.get("tzid_bytes")
        tzid_offsets = ctx.get("tzid_offsets")
        tzid_lengths = ctx.get("tzid_lengths")
        time_prefix_bytes = ctx.get("time_prefix_bytes")
        site_prefix_bytes = ctx.get("site_prefix_bytes")
        edge_prefix_bytes = ctx.get("edge_prefix_bytes")
        bucket_start_micros = ctx.get("bucket_start_micros")
        bucket_duration_micros = ctx.get("bucket_duration_micros")
        bucket_duration_seconds = ctx.get("bucket_duration_seconds")
        edge_alias_prob = shared_maps.get("edge_alias_prob")
        edge_alias_alias = shared_maps.get("edge_alias_alias")
        edge_alias_prob_offsets = shared_maps.get("edge_alias_prob_offsets")
        edge_alias_prob_counts = shared_maps.get("edge_alias_prob_counts")
        required_arrays = [
            tz_instants_flat,
            tz_offsets_flat,
            tz_offset_offsets,
            tz_offset_counts,
            tzid_bytes,
            tzid_offsets,
            tzid_lengths,
            time_prefix_bytes,
            site_prefix_bytes,
            edge_prefix_bytes,
            bucket_start_micros,
            bucket_duration_micros,
            bucket_duration_seconds,
            edge_alias_prob,
            edge_alias_alias,
            edge_alias_prob_offsets,
            edge_alias_prob_counts,
        ]
        if any(item is None for item in required_arrays):
            compiled_kernel_ready = False

    if compiled_kernel_ready:
        merchants_arr = np.asarray(merchants, dtype=np.uint64)
        bucket_idx_arr = np.asarray(buckets, dtype=np.int64)
        counts_arr = np.asarray(counts, dtype=np.int64)
        arrival_seq_arr = np.asarray(arrival_seq_start, dtype=np.int64)
        zone_idx_arr = np.empty(len(zones), dtype=np.int32)
        for idx in range(len(zones)):
            tz_idx = tzid_to_index.get(zones[idx]) if tzid_to_index else None
            if tz_idx is None:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"tzid_primary": zones[idx]},
                )
            zone_idx_arr[idx] = int(tz_idx)

        total_events = int(np.sum(counts_arr[counts_arr > 0]))
        if total_events > 0:
            out_arrival_seq = np.zeros(total_events, dtype=np.int64)
            out_ts_utc_micros = np.zeros(total_events, dtype=np.int64)
            out_tzid_primary_idx = np.full(total_events, -1, dtype=np.int32)
            out_ts_local_primary_micros = np.zeros(total_events, dtype=np.int64)
            out_tzid_operational_idx = np.full(total_events, -1, dtype=np.int32)
            out_ts_local_operational_micros = np.zeros(total_events, dtype=np.int64)
            out_tzid_settlement_idx = np.full(total_events, -1, dtype=np.int32)
            out_ts_local_settlement_micros = np.zeros(total_events, dtype=np.int64)
            out_site_id = np.full(total_events, -1, dtype=np.int64)
            out_edge_id = np.full(total_events, -1, dtype=np.int64)
            out_is_virtual = np.zeros(total_events, dtype=np.uint8)
            summary_physical = np.zeros(len(merchants), dtype=np.int64)
            summary_virtual = np.zeros(len(merchants), dtype=np.int64)
            missing_alias_flags = np.zeros(len(merchants), dtype=np.uint8)
            rng_last = np.zeros((3, 2), dtype=np.int64)
            error_state = np.zeros(2, dtype=np.int64)

            out_size = s4_numba.expand_batch_kernel(
                merchants_arr,
                zone_idx_arr,
                bucket_idx_arr,
                counts_arr,
                arrival_seq_arr,
                bucket_start_micros,
                bucket_duration_micros,
                bucket_duration_seconds,
                classification_keys,
                classification_modes,
                settlement_keys,
                settlement_tz_index,
                edge_keys,
                edge_offsets,
                edge_counts,
                edge_ids_arr,
                edge_tz_index,
                edge_alias_prob,
                edge_alias_alias,
                edge_alias_prob_offsets,
                edge_alias_prob_counts,
                site_keys,
                site_offsets,
                site_counts,
                site_prob,
                site_alias,
                site_site_orders,
                fallback_keys,
                fallback_offsets,
                fallback_counts,
                fallback_prob,
                fallback_alias,
                fallback_site_orders,
                site_tz_keys,
                site_tz_values,
                tz_instants_flat,
                tz_offsets_flat,
                tz_offset_offsets,
                tz_offset_counts,
                tzid_bytes,
                tzid_offsets,
                tzid_lengths,
                time_prefix_bytes,
                site_prefix_bytes,
                edge_prefix_bytes,
                max_arrivals_per_bucket,
                p_virtual_hybrid,
                draws_per_arrival,
                out_arrival_seq,
                out_ts_utc_micros,
                out_tzid_primary_idx,
                out_ts_local_primary_micros,
                out_tzid_operational_idx,
                out_ts_local_operational_micros,
                out_tzid_settlement_idx,
                out_ts_local_settlement_micros,
                out_site_id,
                out_edge_id,
                out_is_virtual,
                summary_physical,
                summary_virtual,
                missing_alias_flags,
                rng_last,
                error_state,
            )
            if int(error_state[0]) != 0:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"error_code": int(error_state[0]), "row_index": int(error_state[1])},
                )
            if out_size != total_events:
                total_events = int(out_size)
                out_arrival_seq = out_arrival_seq[:total_events]
                out_ts_utc_micros = out_ts_utc_micros[:total_events]
                out_tzid_primary_idx = out_tzid_primary_idx[:total_events]
                out_ts_local_primary_micros = out_ts_local_primary_micros[:total_events]
                out_tzid_operational_idx = out_tzid_operational_idx[:total_events]
                out_ts_local_operational_micros = out_ts_local_operational_micros[:total_events]
                out_tzid_settlement_idx = out_tzid_settlement_idx[:total_events]
                out_ts_local_settlement_micros = out_ts_local_settlement_micros[:total_events]
                out_site_id = out_site_id[:total_events]
                out_edge_id = out_edge_id[:total_events]
                out_is_virtual = out_is_virtual[:total_events]

            repeat_counts = counts_arr.copy()
            repeat_counts[repeat_counts < 0] = 0
            merchants_rep = np.repeat(merchants_arr, repeat_counts)
            bucket_rep = np.repeat(bucket_idx_arr, repeat_counts)
            zone_rep = np.repeat(np.asarray(zones, dtype=object), repeat_counts)
            channel_rep = np.repeat(np.asarray(channels, dtype=object), repeat_counts)
            lambda_vals = np.array(
                [np.nan if value is None else float(value) for value in lambdas],
                dtype=np.float64,
            )
            lambda_rep = np.repeat(lambda_vals, repeat_counts)

            tzid_array = np.asarray(tzid_list, dtype=object)
            tzid_primary_vals = tzid_array[out_tzid_primary_idx]
            tzid_operational_vals = np.empty(total_events, dtype=object)
            tzid_settlement_vals = np.empty(total_events, dtype=object)
            mask_operational = out_tzid_operational_idx >= 0
            mask_settlement = out_tzid_settlement_idx >= 0
            tzid_operational_vals[mask_operational] = tzid_array[
                out_tzid_operational_idx[mask_operational]
            ]
            tzid_operational_vals[~mask_operational] = None
            tzid_settlement_vals[mask_settlement] = tzid_array[
                out_tzid_settlement_idx[mask_settlement]
            ]
            tzid_settlement_vals[~mask_settlement] = None

            routing_universe_vals = np.where(
                out_is_virtual.astype(bool),
                str(edge_universe_hash),
                str(zone_alloc_universe_hash),
            )

            events_df = pl.DataFrame(
                {
                    "manifest_fingerprint": np.full(total_events, manifest_fingerprint, dtype=object),
                    "parameter_hash": np.full(total_events, parameter_hash, dtype=object),
                    "seed": np.full(total_events, int(seed), dtype=np.uint64),
                    "scenario_id": np.full(total_events, scenario_id, dtype=object),
                    "merchant_id": merchants_rep.astype(np.uint64),
                    "zone_representation": zone_rep,
                    "channel_group": channel_rep,
                    "bucket_index": bucket_rep.astype(np.int64),
                    "arrival_seq": out_arrival_seq.astype(np.int64),
                    "tzid_primary": tzid_primary_vals,
                    "tzid_settlement": tzid_settlement_vals,
                    "tzid_operational": tzid_operational_vals,
                    "tz_group_id": tzid_primary_vals,
                    "site_id": out_site_id.astype(np.int64),
                    "edge_id": out_edge_id.astype(np.int64),
                    "routing_universe_hash": routing_universe_vals,
                    "lambda_realised": lambda_rep,
                    "is_virtual": out_is_virtual.astype(bool),
                    "s4_spec_version": np.full(total_events, spec_version, dtype=object),
                    "ts_utc_micros": out_ts_utc_micros,
                    "ts_local_primary_micros": out_ts_local_primary_micros,
                    "ts_local_operational_micros": out_ts_local_operational_micros,
                    "ts_local_settlement_micros": out_ts_local_settlement_micros,
                }
            )
            events_df = events_df.with_columns(
                pl.from_epoch("ts_utc_micros", time_unit="us")
                .dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                .alias("ts_utc"),
                pl.from_epoch("ts_local_primary_micros", time_unit="us")
                .dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                .alias("ts_local_primary"),
                pl.when(pl.col("tzid_operational").is_not_null())
                .then(
                    pl.from_epoch("ts_local_operational_micros", time_unit="us").dt.strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                )
                .otherwise(None)
                .alias("ts_local_operational"),
                pl.when(pl.col("tzid_settlement").is_not_null())
                .then(
                    pl.from_epoch("ts_local_settlement_micros", time_unit="us").dt.strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                )
                .otherwise(None)
                .alias("ts_local_settlement"),
            ).drop(
                [
                    "ts_utc_micros",
                    "ts_local_primary_micros",
                    "ts_local_operational_micros",
                    "ts_local_settlement_micros",
                ]
            )

            events_df = events_df.with_columns(
                pl.when(pl.col("site_id") < 0).then(None).otherwise(pl.col("site_id")).alias("site_id"),
                pl.when(pl.col("edge_id") < 0).then(None).otherwise(pl.col("edge_id")).alias("edge_id"),
                pl.when(pl.col("lambda_realised").is_nan())
                .then(None)
                .otherwise(pl.col("lambda_realised"))
                .alias("lambda_realised"),
            )
            events_df = _coerce_int_columns(events_df, _S4_EVENT_UINT64_COLUMNS, _S4_EVENT_INT64_COLUMNS)

            if event_row_validator is not None:
                sample_df = events_df if output_validate_full else events_df.head(output_sample_rows)
                sample_rows = sample_df.to_dicts()
                _validate_rows(sample_rows, event_row_validator, "arrival_events")

            if _HAVE_PYARROW and pq is not None:
                table = events_df.to_arrow()
                if events_writer is None:
                    events_writer = pq.ParquetWriter(events_path, table.schema, compression="zstd")
                events_writer.write_table(table)
            else:
                events_chunks.append(events_df)

            summary_df = pl.DataFrame(
                {
                    "manifest_fingerprint": np.full(len(merchants_arr), manifest_fingerprint, dtype=object),
                    "parameter_hash": np.full(len(merchants_arr), parameter_hash, dtype=object),
                    "seed": np.full(len(merchants_arr), int(seed), dtype=np.uint64),
                    "scenario_id": np.full(len(merchants_arr), scenario_id, dtype=object),
                    "merchant_id": merchants_arr.astype(np.uint64),
                    "zone_representation": np.asarray(zones, dtype=object),
                    "channel_group": np.asarray(channels, dtype=object),
                    "bucket_index": bucket_idx_arr.astype(np.int64),
                    "count_N": counts_arr.astype(np.int64),
                    "count_physical": summary_physical.astype(np.int64),
                    "count_virtual": summary_virtual.astype(np.int64),
                    "s4_spec_version": np.full(len(merchants_arr), spec_version, dtype=object),
                }
            )
            summary_df = _coerce_int_columns(summary_df, _S4_SUMMARY_UINT64_COLUMNS, _S4_SUMMARY_INT64_COLUMNS)
            if summary_row_validator is not None:
                sample_df = summary_df if output_validate_full else summary_df.head(output_sample_rows)
                sample_rows = sample_df.to_dicts()
                _validate_rows(sample_rows, summary_row_validator, "arrival_summary")

            if _HAVE_PYARROW and pq is not None:
                table = summary_df.to_arrow()
                if summary_writer is None:
                    summary_writer = pq.ParquetWriter(summary_path, table.schema, compression="zstd")
                summary_writer.write_table(table)
            else:
                summary_chunks.append(summary_df)

            for idx in range(len(missing_alias_flags)):
                if missing_alias_flags[idx] and (merchants[idx], zones[idx]) not in missing_alias_keys:
                    logger.warning(
                        "S4: site alias missing for merchant_id=%s tzid=%s; using fallback merchant alias",
                        merchants[idx],
                        zones[idx],
                    )
                    missing_alias_keys.add((merchants[idx], zones[idx]))

            total_rows_written = int(total_events)
            total_arrivals = int(total_events)
            total_physical = int(summary_physical.sum())
            total_virtual = int(summary_virtual.sum())

            rng_stats["arrival_time_jitter"]["events"] = int(total_events)
            rng_stats["arrival_time_jitter"]["draws"] = int(total_events * draws_per_arrival)
            rng_stats["arrival_time_jitter"]["blocks"] = int(
                math.ceil(float(draws_per_arrival) / 2.0) * total_events
            )
            rng_stats["arrival_site_pick"]["events"] = int(rng_last[1, 0])
            rng_stats["arrival_site_pick"]["draws"] = int(rng_last[1, 0] * 2)
            rng_stats["arrival_site_pick"]["blocks"] = int(rng_last[1, 0])
            rng_stats["arrival_edge_pick"]["events"] = int(rng_last[2, 0])
            rng_stats["arrival_edge_pick"]["draws"] = int(rng_last[2, 0])
            rng_stats["arrival_edge_pick"]["blocks"] = int(rng_last[2, 0])

            last_row_time = None
            for idx in range(len(counts_arr) - 1, -1, -1):
                if counts_arr[idx] > 0:
                    last_row_time = idx
                    break
            if last_row_time is not None:
                arrival_seq_last = int(arrival_seq_arr[last_row_time] + counts_arr[last_row_time] - 1)
                domain_key = (
                    f"merchant_id={merchants[last_row_time]}|zone={zones[last_row_time]}|"
                    f"bucket_index={bucket_idx_arr[last_row_time]}|arrival_seq={arrival_seq_last}"
                )
                time_key, time_hi, time_lo = _derive_seed(time_hasher, time_prefix, domain_key)
                _, time_blocks, time_next_hi, time_next_lo = _draw_philox_u64(
                    time_key,
                    time_hi,
                    time_lo,
                    draws_per_arrival,
                    manifest_fingerprint,
                )
                rng_stats["arrival_time_jitter"]["last"] = (
                    time_hi,
                    time_lo,
                    time_next_hi,
                    time_next_lo,
                )

            class_idx = np.searchsorted(classification_keys, merchants_arr)
            vmodes = classification_modes[class_idx]
            last_row_site = None
            for idx in range(len(counts_arr) - 1, -1, -1):
                if counts_arr[idx] > 0 and int(vmodes[idx]) != 2:
                    last_row_site = idx
                    break
            if last_row_site is not None:
                arrival_seq_last = int(arrival_seq_arr[last_row_site] + counts_arr[last_row_site] - 1)
                domain_key = (
                    f"merchant_id={merchants[last_row_site]}|zone={zones[last_row_site]}|"
                    f"bucket_index={bucket_idx_arr[last_row_site]}|arrival_seq={arrival_seq_last}"
                )
                site_key, site_hi, site_lo = _derive_seed(site_hasher, site_prefix, domain_key)
                _, site_blocks, site_next_hi, site_next_lo = _draw_philox_u64(
                    site_key,
                    site_hi,
                    site_lo,
                    2,
                    manifest_fingerprint,
                )
                rng_stats["arrival_site_pick"]["last"] = (
                    site_hi,
                    site_lo,
                    site_next_hi,
                    site_next_lo,
                )

            last_edge_idx = None
            for idx in range(total_events - 1, -1, -1):
                if out_is_virtual[idx]:
                    last_edge_idx = idx
                    break
            if last_edge_idx is not None:
                domain_key = (
                    f"merchant_id={merchants_rep[last_edge_idx]}|zone={zone_rep[last_edge_idx]}|"
                    f"bucket_index={bucket_rep[last_edge_idx]}|arrival_seq={int(out_arrival_seq[last_edge_idx])}"
                )
                edge_key, edge_hi, edge_lo = _derive_seed(edge_hasher, edge_prefix, domain_key)
                _, edge_blocks, edge_next_hi, edge_next_lo = _draw_philox_u64(
                    edge_key,
                    edge_hi,
                    edge_lo,
                    1,
                    manifest_fingerprint,
                )
                rng_stats["arrival_edge_pick"]["last"] = (
                    edge_hi,
                    edge_lo,
                    edge_next_hi,
                    edge_next_lo,
                )

            return {
                "batch_id": batch_id,
                "rows_written": total_rows_written,
                "arrivals": total_arrivals,
                "physical": total_physical,
                "virtual": total_virtual,
                "rng_stats": rng_stats,
                "missing_group_keys": list(missing_group_keys),
                "missing_alias_keys": list(missing_alias_keys),
            }

    for idx in range(len(merchants)):
        merchant_id = int(merchants[idx])
        zone_representation = str(zones[idx])
        channel_group = str(channels[idx]) if channels[idx] is not None else None
        bucket_index = int(buckets[idx])
        count_n = int(counts[idx] or 0)
        lambda_realised = lambdas[idx]
        if count_n <= 0:
            continue
        if count_n > max_arrivals_per_bucket:
            raise EngineFailure(
                "F4",
                "5B.S4.PLACEMENT_POLICY_INVALID",
                STATE,
                MODULE_NAME,
                {"bucket_index": bucket_index, "count_N": count_n, "max": max_arrivals_per_bucket},
            )

        bucket_info = bucket_map.get(bucket_index)
        if not bucket_info:
            raise EngineFailure(
                "F4",
                "5B.S4.DOMAIN_ALIGN_FAILED",
                STATE,
                MODULE_NAME,
                {"scenario_id": scenario_id, "bucket_index": bucket_index},
            )

        utc_day = str(bucket_info["utc_day"])
        group_key = (merchant_id, utc_day)
        if (
            not skip_group_weight_check
            and group_weights_map is not None
            and zone_representation not in group_weights_map.get(group_key, set())
        ):
            missing_group_keys.add((merchant_id, utc_day, zone_representation))

        if shared_maps:
            class_idx = _lookup_sorted_key(classification_keys, merchant_id)
            if class_idx < 0:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id},
                )
            virtual_mode_code = int(classification_modes[class_idx])
            if virtual_mode_code < 0 or virtual_mode_code >= len(_VIRTUAL_MODE_BY_CODE):
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id, "virtual_mode": virtual_mode_code},
                )
            virtual_mode = _VIRTUAL_MODE_BY_CODE[virtual_mode_code]
        else:
            classification = classification_map.get(merchant_id)
            if not classification:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id},
                )
            virtual_mode = str(classification.get("virtual_mode") or "")
            if virtual_mode not in {"NON_VIRTUAL", "HYBRID", "VIRTUAL_ONLY"}:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id, "virtual_mode": virtual_mode},
                )

        prefix = f"{merchant_id}|{zone_representation}|{bucket_index}|"
        start_seq = int(arrival_seq_start[idx])

        bucket_events = [] if ordering_required else None
        count_physical = 0
        count_virtual = 0

        for offset in range(count_n):
            arrival_seq = start_seq + offset
            domain_key = f"{prefix}{arrival_seq}"

            time_key, time_counter_hi, time_counter_lo = _derive_seed(
                time_hasher, time_prefix, domain_key
            )
            time_values, time_blocks, time_next_hi, time_next_lo = _draw_philox_u64(
                time_key,
                time_counter_hi,
                time_counter_lo,
                draws_per_arrival,
                manifest_fingerprint,
            )
            u_time = _u01_from_u64(time_values[0])
            offset_micros = int(math.floor(u_time * float(bucket_info["duration_seconds"]) * _MICROS_PER_SECOND))
            max_offset = int(bucket_info["duration_micros"]) - 1
            if offset_micros > max_offset:
                offset_micros = max_offset if max_offset > 0 else 0
            ts_utc_micros = int(bucket_info["start_micros"]) + offset_micros
            ts_utc = _format_rfc3339_micros(ts_utc_micros)

            rng_stats["arrival_time_jitter"]["events"] += 1
            rng_stats["arrival_time_jitter"]["draws"] += draws_per_arrival
            rng_stats["arrival_time_jitter"]["blocks"] += int(time_blocks)
            rng_stats["arrival_time_jitter"]["last"] = (
                time_counter_hi,
                time_counter_lo,
                time_next_hi,
                time_next_lo,
            )

            u_site_primary = None
            u_site_secondary = None
            use_site_pick = virtual_mode != "VIRTUAL_ONLY"
            if use_site_pick:
                site_key, site_counter_hi, site_counter_lo = _derive_seed(
                    site_hasher, site_prefix, domain_key
                )
                site_values, site_blocks, site_next_hi, site_next_lo = _draw_philox_u64(
                    site_key,
                    site_counter_hi,
                    site_counter_lo,
                    2,
                    manifest_fingerprint,
                )
                u_site_primary = _u01_from_u64(site_values[0])
                u_site_secondary = _u01_from_u64(site_values[1])

                rng_stats["arrival_site_pick"]["events"] += 1
                rng_stats["arrival_site_pick"]["draws"] += 2
                rng_stats["arrival_site_pick"]["blocks"] += int(site_blocks)
                rng_stats["arrival_site_pick"]["last"] = (
                    site_counter_hi,
                    site_counter_lo,
                    site_next_hi,
                    site_next_lo,
                )

            is_virtual = virtual_mode == "VIRTUAL_ONLY"
            if virtual_mode == "HYBRID":
                is_virtual = bool(u_site_primary is not None and u_site_primary < p_virtual_hybrid)

            tzid_primary = None
            ts_local_primary = None
            tzid_operational = None
            ts_local_operational = None
            tzid_settlement = None
            ts_local_settlement = None
            site_id = None
            edge_id = None
            routing_universe_hash = None

            if is_virtual:
                if shared_maps:
                    edge_idx = _lookup_sorted_key(edge_keys, merchant_id)
                    alias_idx = _lookup_sorted_key(edge_alias_keys, merchant_id)
                    if edge_idx < 0 or alias_idx < 0:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"merchant_id": merchant_id},
                        )
                    edge_offset = int(edge_offsets[edge_idx])
                    edge_count = int(edge_counts[edge_idx])
                    edge_ids = edge_ids_arr[edge_offset : edge_offset + edge_count]
                    edge_tzids = edge_tz_index[edge_offset : edge_offset + edge_count]
                    edge_meta = {
                        "offset": int(edge_alias_offsets[alias_idx]),
                        "length": int(edge_alias_lengths[alias_idx]),
                        "edge_count": int(edge_alias_counts[alias_idx]),
                        "alias_length": int(edge_alias_table_lengths[alias_idx]),
                    }
                else:
                    edge_meta = edge_alias_meta.get(merchant_id)
                    edge_list = edge_map.get(merchant_id)
                    if edge_meta is None or edge_list is None:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"merchant_id": merchant_id},
                        )
                    edge_ids, edge_tzids = edge_list
                if merchant_id not in edge_alias_cache:
                    if blob_view is None:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"detail": "edge alias blob not loaded"},
                        )
                    prob, alias, edge_count = _decode_alias_slice(
                        blob_view,
                        edge_meta["offset"],
                        edge_meta["length"],
                        alias_endianness,
                    )
                    if edge_count != edge_meta["edge_count"]:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {
                                "merchant_id": merchant_id,
                                "alias_count": edge_count,
                                "edge_count": edge_meta["edge_count"],
                            },
                        )
                    edge_alias_cache[merchant_id] = (prob, alias, edge_count)
                prob, alias, edge_count = edge_alias_cache[merchant_id]
                if edge_count != len(edge_ids):
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {
                            "merchant_id": merchant_id,
                            "alias_count": edge_count,
                            "edge_catalogue_count": len(edge_ids),
                        },
                    )
                edge_key, edge_counter_hi, edge_counter_lo = _derive_seed(
                    edge_hasher, edge_prefix, domain_key
                )
                edge_values, edge_blocks, edge_next_hi, edge_next_lo = _draw_philox_u64(
                    edge_key,
                    edge_counter_hi,
                    edge_counter_lo,
                    1,
                    manifest_fingerprint,
                )
                u_edge = _u01_from_u64(edge_values[0])
                edge_index = _alias_pick(prob, alias, u_edge)
                if edge_index >= len(edge_ids):
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"merchant_id": merchant_id, "edge_index": edge_index},
                    )
                edge_id = int(edge_ids[edge_index])
                if shared_maps:
                    tzid_operational = tzid_list[int(edge_tzids[edge_index])]
                else:
                    tzid_operational = edge_tzids[edge_index]
                if shared_maps:
                    settlement_idx = _lookup_sorted_key(settlement_keys, merchant_id)
                    tzid_settlement = (
                        tzid_list[int(settlement_tz_index[settlement_idx])]
                        if settlement_idx >= 0
                        else None
                    )
                else:
                    tzid_settlement = settlement_map.get(merchant_id)
                if tzid_operational not in tz_cache:
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"tzid_operational": tzid_operational},
                    )
                tzid_primary = tzid_operational
                offset_min = _tz_offset_minutes(tz_cache[tzid_primary], ts_utc_micros // _MICROS_PER_SECOND)
                ts_local_primary = _format_rfc3339_micros(
                    ts_utc_micros + offset_min * 60 * _MICROS_PER_SECOND
                )
                ts_local_operational = ts_local_primary
                if tzid_settlement:
                    if tzid_settlement not in tz_cache:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"tzid_settlement": tzid_settlement},
                        )
                    settlement_offset = _tz_offset_minutes(
                        tz_cache[tzid_settlement], ts_utc_micros // _MICROS_PER_SECOND
                    )
                    ts_local_settlement = _format_rfc3339_micros(
                        ts_utc_micros + settlement_offset * 60 * _MICROS_PER_SECOND
                    )
                routing_universe_hash = edge_universe_hash

                rng_stats["arrival_edge_pick"]["events"] += 1
                rng_stats["arrival_edge_pick"]["draws"] += 1
                rng_stats["arrival_edge_pick"]["blocks"] += int(edge_blocks)
                rng_stats["arrival_edge_pick"]["last"] = (
                    edge_counter_hi,
                    edge_counter_lo,
                    edge_next_hi,
                    edge_next_lo,
                )
                count_virtual += 1
            else:
                alias_key = (merchant_id, zone_representation)
                alias_entry = None
                if shared_maps:
                    tz_idx = tzid_to_index.get(zone_representation) if tzid_to_index else None
                    if tz_idx is None:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"tzid_primary": zone_representation},
                        )
                    site_idx = _lookup_structured_key(site_keys, merchant_id, tz_idx, "tz_idx")
                    if site_idx >= 0:
                        offset = int(site_offsets[site_idx])
                        count = int(site_counts[site_idx])
                        alias_entry = (
                            site_prob[offset : offset + count],
                            site_alias[offset : offset + count],
                            site_site_orders[offset : offset + count],
                        )
                    else:
                        missing_alias_keys.add(alias_key)
                        fallback_idx = _lookup_sorted_key(fallback_keys, merchant_id)
                        if fallback_idx >= 0:
                            offset = int(fallback_offsets[fallback_idx])
                            count = int(fallback_counts[fallback_idx])
                            alias_entry = (
                                fallback_prob[offset : offset + count],
                                fallback_alias[offset : offset + count],
                                fallback_site_orders[offset : offset + count],
                            )
                else:
                    alias_entry = site_alias_map.get(alias_key)
                    if alias_entry is None:
                        missing_alias_keys.add(alias_key)
                        alias_entry = fallback_alias_map.get(merchant_id)
                if alias_entry is None:
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"merchant_id": merchant_id, "tzid": zone_representation},
                    )
                prob, alias, site_orders = alias_entry
                u_site = u_site_secondary if virtual_mode == "HYBRID" else u_site_primary
                if u_site is None:
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"merchant_id": merchant_id, "detail": "site draw missing"},
                    )
                site_index = _alias_pick(prob, alias, u_site)
                if site_index >= len(site_orders):
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"merchant_id": merchant_id, "site_index": site_index},
                    )
                site_id = int(site_orders[site_index])
                if shared_maps:
                    tz_idx = _lookup_structured_key(site_tz_keys, merchant_id, site_id, "site_id")
                    if tz_idx < 0:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"merchant_id": merchant_id, "site_id": site_id},
                        )
                    tzid_primary = tzid_list[int(site_tz_values[tz_idx])]
                else:
                    tzid_primary = site_tz_lookup.get((merchant_id, site_id))
                    if tzid_primary is None:
                        raise EngineFailure(
                            "F4",
                            "5B.S4.ROUTING_POLICY_INVALID",
                            STATE,
                            MODULE_NAME,
                            {"merchant_id": merchant_id, "site_id": site_id},
                        )
                if tzid_primary not in tz_cache:
                    raise EngineFailure(
                        "F4",
                        "5B.S4.ROUTING_POLICY_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"tzid_primary": tzid_primary},
                    )
                offset_min = _tz_offset_minutes(tz_cache[tzid_primary], ts_utc_micros // _MICROS_PER_SECOND)
                ts_local_primary = _format_rfc3339_micros(
                    ts_utc_micros + offset_min * 60 * _MICROS_PER_SECOND
                )
                routing_universe_hash = zone_alloc_universe_hash
                count_physical += 1

            if tzid_primary is None or ts_local_primary is None or routing_universe_hash is None:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id, "bucket_index": bucket_index},
                )
            if is_virtual and edge_id is None:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id, "bucket_index": bucket_index},
                )
            if not is_virtual and site_id is None:
                raise EngineFailure(
                    "F4",
                    "5B.S4.ROUTING_POLICY_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"merchant_id": merchant_id, "bucket_index": bucket_index},
                )

            channel_group_value = str(channel_group) if channel_group is not None else None
            tzid_operational_value = str(tzid_operational) if tzid_operational else None
            ts_local_operational_value = (
                str(ts_local_operational) if ts_local_operational else None
            )
            tzid_settlement_value = str(tzid_settlement) if tzid_settlement else None
            ts_local_settlement_value = str(ts_local_settlement) if ts_local_settlement else None
            site_id_value = int(site_id) if site_id is not None else None
            edge_id_value = int(edge_id) if edge_id is not None else None
            lambda_realised_value = float(lambda_realised) if lambda_realised is not None else None

            if ordering_required:
                event_row = {
                    "manifest_fingerprint": manifest_fingerprint,
                    "parameter_hash": parameter_hash,
                    "seed": int(seed),
                    "scenario_id": str(scenario_id),
                    "merchant_id": int(merchant_id),
                    "zone_representation": str(zone_representation),
                    "bucket_index": int(bucket_index),
                    "arrival_seq": int(arrival_seq),
                    "ts_utc": ts_utc,
                    "tzid_primary": str(tzid_primary),
                    "ts_local_primary": str(ts_local_primary),
                    "is_virtual": bool(is_virtual),
                    "routing_universe_hash": str(routing_universe_hash),
                    "s4_spec_version": str(spec_version),
                    "_ts_utc_micros": ts_utc_micros,
                }
                if channel_group_value is not None:
                    event_row["channel_group"] = channel_group_value
                if tzid_operational_value:
                    event_row["tzid_operational"] = tzid_operational_value
                if ts_local_operational_value:
                    event_row["ts_local_operational"] = ts_local_operational_value
                if tzid_settlement_value:
                    event_row["tzid_settlement"] = tzid_settlement_value
                if ts_local_settlement_value:
                    event_row["ts_local_settlement"] = ts_local_settlement_value
                if site_id_value is not None:
                    event_row["site_id"] = site_id_value
                if edge_id_value is not None:
                    event_row["edge_id"] = edge_id_value
                if lambda_realised_value is not None:
                    event_row["lambda_realised"] = lambda_realised_value
                event_row["tz_group_id"] = str(tzid_primary)
                bucket_events.append(event_row)
            else:
                event_row = (
                    manifest_fingerprint,
                    parameter_hash,
                    int(seed),
                    str(scenario_id),
                    int(merchant_id),
                    str(zone_representation),
                    channel_group_value,
                    int(bucket_index),
                    int(arrival_seq),
                    ts_utc,
                    str(tzid_primary),
                    str(ts_local_primary),
                    tzid_settlement_value,
                    ts_local_settlement_value,
                    tzid_operational_value,
                    ts_local_operational_value,
                    str(tzid_primary),
                    site_id_value,
                    edge_id_value,
                    str(routing_universe_hash),
                    lambda_realised_value,
                    bool(is_virtual),
                    str(spec_version),
                )
                total_rows_written += 1
                total_arrivals += 1
                total_physical += 1 if not is_virtual else 0
                total_virtual += 1 if is_virtual else 0
                event_rows.append(event_row)
                if len(event_rows) >= output_buffer_rows:
                    _write_events(event_rows)
                    event_rows = []

        if ordering_required and bucket_events:
            bucket_events.sort(key=lambda item: (item["_ts_utc_micros"], item["arrival_seq"]))
            for event_row in bucket_events:
                event_row.pop("_ts_utc_micros", None)
                total_rows_written += 1
                total_arrivals += 1
                total_physical += 1 if not event_row["is_virtual"] else 0
                total_virtual += 1 if event_row["is_virtual"] else 0
                event_rows.append(event_row)
                if len(event_rows) >= output_buffer_rows:
                    _write_events(event_rows)
                    event_rows = []

        summary_row = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "seed": int(seed),
            "scenario_id": str(scenario_id),
            "merchant_id": int(merchant_id),
            "zone_representation": str(zone_representation),
            "bucket_index": int(bucket_index),
            "count_N": int(count_n),
            "count_physical": int(count_physical),
            "count_virtual": int(count_virtual),
            "s4_spec_version": str(spec_version),
        }
        if channel_group is not None:
            summary_row["channel_group"] = str(channel_group)
        summary_rows.append(summary_row)
        if len(summary_rows) >= output_buffer_rows:
            _write_summary(summary_rows)
            summary_rows = []

    if event_rows:
        _write_events(event_rows)
        event_rows = []
    if summary_rows:
        _write_summary(summary_rows)
        summary_rows = []

    if events_writer is not None:
        events_writer.close()
    elif events_chunks:
        events_all = pl.concat(events_chunks)
        events_all.write_parquet(events_path, compression="zstd")

    if summary_writer is not None:
        summary_writer.close()
    elif summary_chunks:
        summary_all = pl.concat(summary_chunks)
        summary_all.write_parquet(summary_path, compression="zstd")

    return {
        "batch_id": batch_id,
        "rows_written": total_rows_written,
        "arrivals": total_arrivals,
        "physical": total_physical,
        "virtual": total_virtual,
        "rng_stats": rng_stats,
        "missing_group_keys": list(missing_group_keys),
        "missing_alias_keys": list(missing_alias_keys),
    }

def _u01_from_u64(value: int) -> float:
    return (float(value) + 0.5) * TWO_NEG_64


def _build_alias_table(weights: Iterable[float]) -> tuple[np.ndarray, np.ndarray, bool]:
    values = np.asarray(list(weights), dtype=np.float64)
    if values.size == 0:
        raise ValueError("empty weight vector")
    fallback_used = False
    if not np.isfinite(values).all():
        values = np.ones(values.size, dtype=np.float64)
        fallback_used = True
    values = np.where(values < 0.0, 0.0, values)
    total = float(values.sum())
    if total <= 0.0:
        values = np.ones(values.size, dtype=np.float64)
        total = float(values.sum())
        fallback_used = True
    values = values / total
    count = values.size
    prob = np.zeros(count, dtype=np.float64)
    alias = np.zeros(count, dtype=np.int64)
    if count == 1:
        prob[0] = 1.0
        alias[0] = 0
        return prob, alias, fallback_used
    scaled = values * count
    small = [idx for idx, val in enumerate(scaled) if val < 1.0]
    large = [idx for idx, val in enumerate(scaled) if val >= 1.0]
    while small and large:
        s_idx = small.pop()
        l_idx = large.pop()
        prob[s_idx] = scaled[s_idx]
        alias[s_idx] = l_idx
        scaled[l_idx] = scaled[l_idx] - (1.0 - prob[s_idx])
        if scaled[l_idx] < 1.0:
            small.append(l_idx)
        else:
            large.append(l_idx)
    for idx in small + large:
        prob[idx] = 1.0
        alias[idx] = idx
    return prob, alias, fallback_used


def _alias_pick(prob: np.ndarray, alias: np.ndarray, u: float) -> int:
    count = prob.size
    if count == 1:
        return 0
    scaled = u * count
    idx = int(scaled)
    if idx >= count:
        idx = count - 1
    frac = scaled - idx
    if frac < prob[idx]:
        return idx
    return int(alias[idx])


class _BlobView:
    def __init__(self, path: Path) -> None:
        self._file = path.open("rb")
        self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)

    def slice(self, offset: int, length: int) -> memoryview:
        return memoryview(self._mmap)[offset : offset + length]

    def close(self) -> None:
        try:
            self._mmap.close()
        finally:
            self._file.close()


def _decode_alias_slice(
    blob_view: _BlobView,
    offset: int,
    length: int,
    endianness: str,
) -> tuple[np.ndarray, np.ndarray, int]:
    if length <= 0:
        raise ValueError("alias slice length invalid")
    view = blob_view.slice(offset, length)
    fmt = "<" if endianness == "little" else ">"
    if len(view) < 16:
        raise ValueError("alias slice header incomplete")
    n_items = struct.unpack_from(f"{fmt}I", view, 0)[0]
    prob_qbits = struct.unpack_from(f"{fmt}I", view, 4)[0]
    payload_offset = 16
    expected_len = payload_offset + (int(n_items) * 8)
    if len(view) < expected_len:
        raise ValueError("alias slice payload incomplete")
    prob_q = np.zeros(int(n_items), dtype=np.float64)
    alias = np.zeros(int(n_items), dtype=np.int64)
    scale = float(1 << int(prob_qbits))
    for idx in range(int(n_items)):
        base = payload_offset + idx * 8
        prob_raw = struct.unpack_from(f"{fmt}I", view, base)[0]
        alias_idx = struct.unpack_from(f"{fmt}I", view, base + 4)[0]
        prob_q[idx] = float(prob_raw) / scale
        alias[idx] = int(alias_idx)
    return prob_q, alias, int(n_items)


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



def _schema_for_event(schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_layer1, anchor)
    return normalize_nullable_schema(schema)


def _family_by_id(families: list[dict], module: str, substream_label: str) -> Optional[dict]:
    for family in families:
        if family.get("module") == module and family.get("substream_label") == substream_label:
            return family
    return None


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l2.seg_5B.s4_arrival_events.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)
    output_validate_full = _env_flag("ENGINE_5B_S4_VALIDATE_FULL")
    output_sample_rows_env = os.environ.get("ENGINE_5B_S4_VALIDATE_SAMPLE_ROWS", "5000")
    try:
        output_sample_rows = max(int(output_sample_rows_env), 0)
    except ValueError:
        output_sample_rows = 5000
    output_validation_mode = "full" if output_validate_full else "fast_sampled"
    strict_ordering = _env_flag("ENGINE_5B_S4_STRICT_ORDERING")
    ordering_stats_enabled = strict_ordering or _env_flag("ENGINE_5B_S4_ORDERING_STATS")
    validate_events_full = _env_flag("ENGINE_5B_S4_VALIDATE_EVENTS_FULL")
    validate_events_limit_env = os.environ.get("ENGINE_5B_S4_VALIDATE_EVENTS_LIMIT", "1000")
    try:
        validate_events_limit = max(int(validate_events_limit_env), 0)
    except ValueError:
        validate_events_limit = 1000
    enable_rng_events = _env_flag("ENGINE_5B_S4_RNG_EVENTS")
    event_buffer_env = os.environ.get("ENGINE_5B_S4_EVENT_BUFFER", "5000")
    try:
        event_buffer_size = max(int(event_buffer_env), 1)
    except ValueError:
        event_buffer_size = 5000
    workers_env = os.environ.get("ENGINE_5B_S4_WORKERS", "").strip()
    if workers_env:
        try:
            worker_count = max(int(workers_env), 1)
        except ValueError:
            worker_count = 1
    else:
        worker_count = max(1, min(os.cpu_count() or 1, 4))
    max_inflight_env = os.environ.get("ENGINE_5B_S4_INFLIGHT_BATCHES", "").strip()
    if max_inflight_env:
        try:
            max_inflight = max(int(max_inflight_env), 1)
        except ValueError:
            max_inflight = max(2, worker_count * 2)
    else:
        max_inflight = max(2, worker_count * 2)
    use_parallel = worker_count > 1
    if use_parallel and enable_rng_events:
        use_parallel = False
    if use_parallel and not _HAVE_PYARROW:
        use_parallel = False
    if use_parallel:
        ordering_stats_enabled = strict_ordering
    ordering_required = ordering_stats_enabled
    output_buffer_env = os.environ.get("ENGINE_5B_S4_OUTPUT_BUFFER_ROWS", "50000")
    try:
        output_buffer_rows = max(int(output_buffer_env), 1000)
    except ValueError:
        output_buffer_rows = 50000
    shared_maps_env = os.environ.get("ENGINE_5B_S4_SHARED_MAPS")
    if shared_maps_env is None:
        shared_maps_enabled = True
    else:
        shared_maps_enabled = shared_maps_env.strip().lower() in {"1", "true", "yes", "y"}
    compiled_kernel_env = os.environ.get("ENGINE_5B_S4_COMPILED_KERNEL", "").strip()
    if compiled_kernel_env:
        compiled_kernel_enabled = compiled_kernel_env.lower() in {"1", "true", "yes", "y"}
    else:
        compiled_kernel_enabled = True
    compiled_kernel_enabled = compiled_kernel_enabled and s4_numba.numba_available()

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
    schema_5b: dict = {}
    schema_5a: dict = {}
    schema_layer2: dict = {}
    schema_layer1: dict = {}
    schema_2b: dict = {}
    schema_3a: dict = {}
    schema_3b: dict = {}

    scenario_details: dict[str, dict[str, object]] = {}
    scenario_count_succeeded = 0
    total_rows_written = 0
    total_arrivals = 0
    total_physical = 0
    total_virtual = 0
    ordering_violations_total = 0

    event_paths: list[Path] = []
    summary_paths: list[Path] = []

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
        logger.info("S4: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5b_path, dictionary_5b = load_dataset_dictionary(source, "5B")
        schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s,%s,%s,%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_5b_path),
            str(schema_5b_path),
            str(schema_5a_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
            str(schema_2b_path),
            str(schema_3a_path),
            str(schema_3b_path),
        )

        logger.info(
            "S4: objective=expand bucket counts into arrival events (gate S0-S3 + routing inputs; output arrival_events_5B + rng logs)"
        )
        logger.info(
            "S4: rng_event logging=%s (set ENGINE_5B_S4_RNG_EVENTS=1 to enable)",
            "on" if enable_rng_events else "off",
        )
        if not strict_ordering:
            logger.warning(
                "S4: strict ordering disabled; output order follows input stream (set ENGINE_5B_S4_STRICT_ORDERING=1 to enforce)"
            )
        if not ordering_stats_enabled:
            logger.info("S4: ordering stats disabled (set ENGINE_5B_S4_ORDERING_STATS=1 to collect)")
        logger.info(
            "S4: rng_event validation mode=%s limit=%s json_encoder=%s",
            "full" if validate_events_full else "sampled",
            "all" if validate_events_full else validate_events_limit,
            "orjson" if _HAVE_ORJSON else "json",
        )
        if use_parallel:
            logger.info(
                "S4: parallel_mode=on workers=%d inflight_batches=%d",
                worker_count,
                max_inflight,
            )
        else:
            if worker_count > 1 and enable_rng_events:
                logger.info("S4: parallel_mode=off (rng_event logging enabled)")
            elif worker_count > 1 and not _HAVE_PYARROW:
                logger.info("S4: parallel_mode=off (pyarrow unavailable)")
            else:
                logger.info("S4: parallel_mode=off")
        logger.info(
            "S4: compiled_kernel=%s (set ENGINE_5B_S4_COMPILED_KERNEL=0 to disable)",
            "on" if compiled_kernel_enabled else "off",
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
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_set_payload = receipt_payload.get("scenario_set")
        if not isinstance(scenario_set_payload, list) or not scenario_set_payload:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "scenario_set_missing",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )
        scenario_set = sorted({str(item) for item in scenario_set_payload if item})
        if not scenario_set:
            _abort(
                "5B.S4.S0_GATE_INVALID",
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
                    "5B.S4.UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        spec_version = str(receipt_payload.get("spec_version") or "")
        if not spec_version:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "spec_version_missing",
                {"receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )

        if not isinstance(sealed_inputs, list):
            _abort(
                "5B.S4.S0_GATE_INVALID",
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
                    "5B.S4.S0_GATE_INVALID",
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
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {"expected": receipt_payload.get("sealed_inputs_digest"), "actual": sealed_digest},
                manifest_fingerprint,
            )

        policy_scopes = {"ROW_LEVEL"}
        data_scopes = {"ROW_LEVEL", "METADATA_ONLY"}

        _resolve_sealed_row(
            sealed_by_id,
            "arrival_time_placement_policy_5B",
            manifest_fingerprint,
            policy_scopes,
            True,
            "5B.S4.PLACEMENT_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_routing_policy_5B",
            manifest_fingerprint,
            policy_scopes,
            True,
            "5B.S4.ROUTING_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_rng_policy_5B",
            manifest_fingerprint,
            policy_scopes,
            True,
            "5B.S4.RNG_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "route_rng_policy_v1",
            manifest_fingerprint,
            policy_scopes,
            True,
            "5B.S4.ROUTING_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "alias_layout_policy_v1",
            manifest_fingerprint,
            policy_scopes,
            True,
            "5B.S4.ROUTING_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "site_locations",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "site_timezones",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        tz_cache_row = _resolve_sealed_row(
            sealed_by_id,
            "tz_timetable_cache",
            manifest_fingerprint,
            data_scopes,
            False,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "s1_site_weights",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "s2_alias_index",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "s2_alias_blob",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "s4_group_weights",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "virtual_classification_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        virtual_settlement_row = _resolve_sealed_row(
            sealed_by_id,
            "virtual_settlement_3B",
            manifest_fingerprint,
            data_scopes,
            False,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "edge_catalogue_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "edge_catalogue_index_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "edge_alias_blob_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "edge_alias_index_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "edge_universe_hash_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.S1_OUTPUT_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "virtual_routing_policy_3B",
            manifest_fingerprint,
            data_scopes,
            True,
            "5B.S4.ROUTING_POLICY_INVALID",
        )

        current_phase = "config_load"
        placement_entry = find_dataset_entry(dictionary_5b, "arrival_time_placement_policy_5B").entry
        routing_entry = find_dataset_entry(dictionary_5b, "arrival_routing_policy_5B").entry
        rng_entry = find_dataset_entry(dictionary_5b, "arrival_rng_policy_5B").entry
        route_rng_entry = find_dataset_entry(dictionary_5b, "route_rng_policy_v1").entry
        alias_layout_entry = find_dataset_entry(dictionary_5b, "alias_layout_policy_v1").entry
        virtual_routing_entry = find_dataset_entry(dictionary_5b, "virtual_routing_policy_3B").entry

        placement_path = _resolve_dataset_path(placement_entry, run_paths, config.external_roots, tokens)
        routing_path = _resolve_dataset_path(routing_entry, run_paths, config.external_roots, tokens)
        rng_path = _resolve_dataset_path(rng_entry, run_paths, config.external_roots, tokens)
        route_rng_path = _resolve_dataset_path(route_rng_entry, run_paths, config.external_roots, tokens)
        alias_layout_path = _resolve_dataset_path(alias_layout_entry, run_paths, config.external_roots, tokens)
        virtual_routing_path = _resolve_dataset_path(virtual_routing_entry, run_paths, config.external_roots, tokens)

        placement_policy = _load_yaml(placement_path)
        routing_policy = _load_yaml(routing_path)
        rng_policy = _load_yaml(rng_path)
        route_rng_policy = _load_json(route_rng_path)
        alias_layout_policy = _load_json(alias_layout_path)
        virtual_routing_policy = _load_json(virtual_routing_path)

        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_time_placement_policy_5B", placement_policy)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_routing_policy_5B", routing_policy)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_rng_policy_5B", rng_policy)
        _validate_payload(schema_2b, schema_layer1, schema_layer2, "policy/route_rng_policy_v1", route_rng_policy)
        _validate_payload(schema_2b, schema_layer1, schema_layer2, "policy/alias_layout_policy_v1", alias_layout_policy)
        _validate_payload(schema_3b, schema_layer1, schema_layer2, "egress/virtual_routing_policy_3B", virtual_routing_policy)

        if placement_policy.get("policy_id") != "arrival_time_placement_policy_5B":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_time_placement_policy_5B", "actual": placement_policy.get("policy_id")},
                manifest_fingerprint,
            )
        if routing_policy.get("policy_id") != "arrival_routing_policy_5B":
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_routing_policy_5B", "actual": routing_policy.get("policy_id")},
                manifest_fingerprint,
            )
        if rng_policy.get("policy_id") != "arrival_rng_policy_5B":
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_rng_policy_5B", "actual": rng_policy.get("policy_id")},
                manifest_fingerprint,
            )
        if route_rng_policy.get("policy_id") != "route_rng_policy_v1":
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "route_rng_policy_invalid",
                {"policy_id": route_rng_policy.get("policy_id")},
                manifest_fingerprint,
            )
        if alias_layout_policy.get("policy_id") != "alias_layout_policy_v1":
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "alias_layout_policy_invalid",
                {"policy_id": alias_layout_policy.get("policy_id")},
                manifest_fingerprint,
            )

        placement_kind = str(placement_policy.get("placement_kind") or "")
        if placement_kind != "uniform_within_bucket_v1":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "placement_kind_invalid",
                {"placement_kind": placement_kind},
                manifest_fingerprint,
            )
        if str(placement_policy.get("interval_semantics") or "") != "[start,end)":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "interval_semantics_invalid",
                {"interval_semantics": placement_policy.get("interval_semantics")},
                manifest_fingerprint,
            )
        if str(placement_policy.get("timestamp_precision") or "") != "microsecond":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "timestamp_precision_invalid",
                {"timestamp_precision": placement_policy.get("timestamp_precision")},
                manifest_fingerprint,
            )
        try:
            draws_per_arrival = int(placement_policy.get("draws_per_arrival") or 0)
        except (TypeError, ValueError):
            draws_per_arrival = 0
        if draws_per_arrival != 1:
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "draws_per_arrival_invalid",
                {"draws_per_arrival": placement_policy.get("draws_per_arrival")},
                manifest_fingerprint,
            )
        u_mapping = placement_policy.get("u_mapping") or {}
        if str(u_mapping.get("uniform_law") or "") != "open_interval_u64":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "uniform_law_invalid",
                {"uniform_law": u_mapping.get("uniform_law")},
                manifest_fingerprint,
            )

        offset_quantisation = placement_policy.get("offset_quantisation") or {}
        if str(offset_quantisation.get("unit") or "") != "microsecond":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "offset_unit_invalid",
                {"unit": offset_quantisation.get("unit")},
                manifest_fingerprint,
            )
        if str(offset_quantisation.get("law") or "") != "floor(u * D_seconds * 1_000_000)":
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "offset_law_invalid",
                {"law": offset_quantisation.get("law")},
                manifest_fingerprint,
            )
        if not bool(offset_quantisation.get("clamp_end_exclusive")):
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "clamp_end_exclusive_invalid",
                {"clamp_end_exclusive": offset_quantisation.get("clamp_end_exclusive")},
                manifest_fingerprint,
            )

        guardrails = placement_policy.get("guardrails") or {}
        try:
            max_arrivals_per_bucket = int(guardrails.get("max_arrivals_per_bucket") or 0)
        except (TypeError, ValueError):
            max_arrivals_per_bucket = 0
        try:
            max_bucket_duration_seconds = int(guardrails.get("max_bucket_duration_seconds") or 0)
        except (TypeError, ValueError):
            max_bucket_duration_seconds = 0
        if max_arrivals_per_bucket <= 0:
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "guardrail_invalid",
                {"max_arrivals_per_bucket": max_arrivals_per_bucket},
                manifest_fingerprint,
            )
        if max_bucket_duration_seconds <= 0:
            _abort(
                "5B.S4.PLACEMENT_POLICY_INVALID",
                "V-04",
                "guardrail_invalid",
                {"max_bucket_duration_seconds": max_bucket_duration_seconds},
                manifest_fingerprint,
            )

        virtual_mode_source = str(routing_policy.get("virtual_mode_source") or "")
        if virtual_mode_source != "virtual_classification_3B":
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "virtual_mode_source_invalid",
                {"virtual_mode_source": virtual_mode_source},
                manifest_fingerprint,
            )
        hybrid_policy = routing_policy.get("hybrid_policy") or {}
        try:
            p_virtual_hybrid = float(hybrid_policy.get("p_virtual_hybrid"))
        except (TypeError, ValueError):
            p_virtual_hybrid = -1.0
        if not (0.0 <= p_virtual_hybrid <= 1.0):
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "p_virtual_hybrid_invalid",
                {"p_virtual_hybrid": hybrid_policy.get("p_virtual_hybrid")},
                manifest_fingerprint,
            )
        realism_bounds = (routing_policy.get("realism_floors") or {}).get("hybrid_p_virtual_bounds") or []
        if isinstance(realism_bounds, list) and len(realism_bounds) == 2:
            try:
                min_bound = float(realism_bounds[0])
                max_bound = float(realism_bounds[1])
            except (TypeError, ValueError):
                min_bound = None
                max_bound = None
            if min_bound is not None and max_bound is not None:
                if p_virtual_hybrid < min_bound or p_virtual_hybrid > max_bound:
                    _abort(
                        "5B.S4.ROUTING_POLICY_INVALID",
                        "V-04",
                        "p_virtual_hybrid_out_of_bounds",
                        {"p_virtual_hybrid": p_virtual_hybrid, "bounds": realism_bounds},
                        manifest_fingerprint,
                    )

        physical_router = routing_policy.get("physical_router") or {}
        if str(physical_router.get("zone_representation") or "") != "tzid":
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "zone_representation_invalid",
                {"zone_representation": physical_router.get("zone_representation")},
                manifest_fingerprint,
            )
        if int(physical_router.get("draws_required_u64") or 0) != 2:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "physical_draws_invalid",
                {"draws_required_u64": physical_router.get("draws_required_u64")},
                manifest_fingerprint,
            )

        virtual_router = routing_policy.get("virtual_router") or {}
        if int(virtual_router.get("draws_required_u64") or 0) != 1:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "virtual_draws_invalid",
                {"draws_required_u64": virtual_router.get("draws_required_u64")},
                manifest_fingerprint,
            )

        if str(rng_policy.get("rng_engine") or "") != "philox2x64-10":
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "rng_engine_invalid",
                {"rng_engine": rng_policy.get("rng_engine")},
                manifest_fingerprint,
            )
        if str(rng_policy.get("uniform_law") or "") != "open_interval_u64":
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "uniform_law_invalid",
                {"uniform_law": rng_policy.get("uniform_law")},
                manifest_fingerprint,
            )

        families = rng_policy.get("families") or []
        time_family = _family_by_id(families, "5B.S4", "arrival_time_jitter")
        site_family = _family_by_id(families, "5B.S4", "arrival_site_pick")
        edge_family = _family_by_id(families, "5B.S4", "arrival_edge_pick")
        if not time_family or not site_family or not edge_family:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "rng_family_missing",
                {"missing": [name for name, fam in {
                    "arrival_time_jitter": time_family,
                    "arrival_site_pick": site_family,
                    "arrival_edge_pick": edge_family,
                }.items() if fam is None]},
                manifest_fingerprint,
            )
        time_family_id = str(time_family.get("family_id") or "")
        site_family_id = str(site_family.get("family_id") or "")
        edge_family_id = str(edge_family.get("family_id") or "")
        if not time_family_id or not site_family_id or not edge_family_id:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "family_id_missing",
                {"time_family_id": time_family_id, "site_family_id": site_family_id, "edge_family_id": edge_family_id},
                manifest_fingerprint,
            )

        def _validate_fixed_draws(family: dict, expected: int, label: str) -> None:
            draws_law = family.get("draws_u64_law") or {}
            if str(draws_law.get("kind") or "") != "fixed":
                _abort(
                    "5B.S4.RNG_POLICY_INVALID",
                    "V-04",
                    "draws_law_invalid",
                    {"label": label, "draws_law": draws_law},
                    manifest_fingerprint,
                )
            if int(draws_law.get("draws_u64") or 0) != expected:
                _abort(
                    "5B.S4.RNG_POLICY_INVALID",
                    "V-04",
                    "draws_count_invalid",
                    {"label": label, "draws_u64": draws_law.get("draws_u64"), "expected": expected},
                    manifest_fingerprint,
                )

        _validate_fixed_draws(time_family, 1, "arrival_time_jitter")
        _validate_fixed_draws(site_family, 2, "arrival_site_pick")
        _validate_fixed_draws(edge_family, 1, "arrival_edge_pick")

        domain_sep = str((rng_policy.get("derivation") or {}).get("domain_sep") or "")
        if not domain_sep:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "domain_sep_missing",
                {"derivation": rng_policy.get("derivation")},
                manifest_fingerprint,
            )

        forbid_inputs = (rng_policy.get("derivation") or {}).get("forbid_inputs") or []
        if isinstance(forbid_inputs, list) and "run_id" in forbid_inputs:
            logger.info("S4: rng derivation forbids run_id as expected.")
        elif forbid_inputs:
            logger.info("S4: rng derivation forbid_inputs=%s", forbid_inputs)
        else:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "forbid_inputs_missing",
                {"derivation": rng_policy.get("derivation")},
                manifest_fingerprint,
            )

        if not _HEX64_PATTERN.match(str(manifest_fingerprint)):
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "manifest_fingerprint_invalid",
                {"manifest_fingerprint": manifest_fingerprint},
                manifest_fingerprint,
            )
        if not _HEX64_PATTERN.match(str(parameter_hash)):
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-04",
                "parameter_hash_invalid",
                {"parameter_hash": parameter_hash},
                manifest_fingerprint,
            )

        if virtual_routing_policy.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "virtual_policy_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": virtual_routing_policy.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        if virtual_routing_policy.get("parameter_hash") != parameter_hash:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "virtual_policy_parameter_mismatch",
                {"expected": parameter_hash, "actual": virtual_routing_policy.get("parameter_hash")},
                manifest_fingerprint,
            )

        alias_layout_version = str(alias_layout_policy.get("layout_version") or "")
        if alias_layout_version and virtual_routing_policy.get("alias_layout_version") != alias_layout_version:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "alias_layout_version_mismatch",
                {
                    "policy": virtual_routing_policy.get("alias_layout_version"),
                    "layout_version": alias_layout_version,
                },
                manifest_fingerprint,
            )

        current_phase = "rng_logs"
        event_specs = {
            "arrival_time_jitter": "rng_event_arrival_time_jitter",
            "arrival_site_pick": "rng_event_arrival_site_pick",
            "arrival_edge_pick": "rng_event_arrival_edge_pick",
        }
        event_entries = {
            label: find_dataset_entry(dictionary_5b, dataset_id).entry
            for label, dataset_id in event_specs.items()
        }
        event_handles: dict[str, object] = {}
        event_buffers: dict[str, list[str]] = {}
        event_roots: dict[str, Path] = {}
        event_tmp_dirs: dict[str, Path] = {}
        event_enabled: dict[str, bool] = {}
        event_has_data: dict[str, bool] = {}
        for label, entry in event_entries.items():
            path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            root = _event_root_from_path(path)
            event_roots[label] = root
            event_paths_existing = _iter_jsonl_paths(root) if root.exists() else []
            event_has_data[label] = bool(event_paths_existing)
            if not enable_rng_events or event_paths_existing:
                event_enabled[label] = False
            else:
                event_enabled[label] = True
                tmp_dir = run_paths.tmp_root / f"s4_rng_{label}_{uuid.uuid4().hex}"
                tmp_dir.mkdir(parents=True, exist_ok=True)
                event_tmp_dirs[label] = tmp_dir
                event_path = _event_file_from_root(tmp_dir)
                event_handles[label] = event_path.open("w", encoding="utf-8")
                event_buffers[label] = []
        if not enable_rng_events:
            logger.info("S4: rng_event logging disabled; emitting rng_trace_log only")
        else:
            existing_labels = sorted([label for label, present in event_has_data.items() if present])
            if existing_labels:
                logger.info("S4: rng_event logs already exist for labels=%s; skipping new emission", existing_labels)

        trace_entry = find_dataset_entry(dictionary_5b, "rng_trace_log").entry
        trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
        trace_mode = "create"
        trace_missing: set[str] = set(event_specs.keys())
        if trace_path.exists():
            trace_missing = {
                label for label in event_specs.keys() if not _trace_has_substream(trace_path, "5B.S4", label)
            }
            trace_mode = "skip" if not trace_missing else "append"

        if trace_mode == "skip" and enable_rng_events:
            for label, enabled in event_enabled.items():
                if enabled:
                    _abort(
                        "5B.S4.RNG_ACCOUNTING_MISMATCH",
                        "V-05",
                        "rng_trace_without_events",
                        {"detail": "trace already has substream but events are missing", "label": label},
                        manifest_fingerprint,
                    )

        trace_handle = None
        trace_acc = None
        trace_tmp_path = None
        if trace_mode == "create":
            trace_tmp_path = run_paths.tmp_root / f"s4_trace_{uuid.uuid4().hex}.jsonl"
            trace_handle = trace_tmp_path.open("w", encoding="utf-8")
            trace_acc = RngTraceAccumulator()
        elif trace_mode == "append":
            trace_handle = trace_path.open("a", encoding="utf-8")
            trace_acc = RngTraceAccumulator()
        logger.info("S4: rng_trace_log mode=%s", trace_mode)

        if trace_mode == "append" and trace_acc is not None:
            for label in event_specs.keys():
                if event_has_data.get(label) and label in trace_missing:
                    _append_trace_from_events(event_roots[label], trace_handle, trace_acc, logger, label)

        audit_entry = find_dataset_entry(dictionary_5b, "rng_audit_log").entry
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
        _ensure_rng_audit(
            _resolve_dataset_path(audit_entry, run_paths, config.external_roots, tokens), audit_payload, logger
        )

        event_validators: dict[str, Draft202012Validator] = {}
        validate_remaining: dict[str, Optional[int]] = {}
        if enable_rng_events:
            event_validators = {
                label: Draft202012Validator(_schema_for_event(schema_layer1, f"rng/events/{label}"))
                for label in event_specs.keys()
            }
            for label in event_specs.keys():
                validate_remaining[label] = None if validate_events_full else validate_events_limit

        event_schema = _schema_items(schema_5b, schema_layer1, schema_layer2, "egress/s4_arrival_events_5B")
        event_row_validator = Draft202012Validator(event_schema)
        summary_schema = _schema_items(schema_5b, schema_layer1, schema_layer2, "diagnostics/s4_arrival_summary_5B")
        summary_row_validator = Draft202012Validator(summary_schema)

        current_phase = "routing_inputs"
        tz_cache_entry = find_dataset_entry(dictionary_5b, "tz_timetable_cache").entry
        tz_cache_path = _resolve_dataset_path(tz_cache_entry, run_paths, config.external_roots, tokens)
        if tz_cache_row is None or not tz_cache_path.exists():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "tz_cache_missing",
                {"path": str(tz_cache_path)},
                manifest_fingerprint,
            )
        tz_cache = _decode_tz_cache(tz_cache_path, logger)

        zone_hash_entry = find_dataset_entry(dictionary_5b, "zone_alloc_universe_hash").entry
        zone_hash_path = _resolve_dataset_path(zone_hash_entry, run_paths, config.external_roots, tokens)
        zone_hash_payload = _load_json(zone_hash_path)
        _validate_payload(schema_3a, schema_layer1, schema_layer2, "validation/zone_alloc_universe_hash", zone_hash_payload)
        zone_alloc_universe_hash = zone_hash_payload.get("routing_universe_hash")
        if not zone_alloc_universe_hash:
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "zone_alloc_universe_hash_missing",
                {"path": str(zone_hash_path)},
                manifest_fingerprint,
            )

        edge_hash_entry = find_dataset_entry(dictionary_5b, "edge_universe_hash_3B").entry
        edge_hash_path = _resolve_dataset_path(edge_hash_entry, run_paths, config.external_roots, tokens)
        edge_hash_payload = _load_json(edge_hash_path)
        _validate_payload(schema_3b, schema_layer1, schema_layer2, "validation/edge_universe_hash_3B", edge_hash_payload)
        edge_universe_hash = edge_hash_payload.get("universe_hash")
        if not edge_universe_hash:
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "edge_universe_hash_missing",
                {"path": str(edge_hash_path)},
                manifest_fingerprint,
            )

        if virtual_routing_policy.get("edge_universe_hash") and virtual_routing_policy.get("edge_universe_hash") != edge_universe_hash:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-04",
                "edge_universe_hash_mismatch",
                {"policy": virtual_routing_policy.get("edge_universe_hash"), "actual": edge_universe_hash},
                manifest_fingerprint,
            )

        site_weights_entry = find_dataset_entry(dictionary_5b, "s1_site_weights").entry
        site_tz_entry = find_dataset_entry(dictionary_5b, "site_timezones").entry
        group_weights_entry = find_dataset_entry(dictionary_5b, "s4_group_weights").entry
        site_weights_path = _resolve_dataset_path(site_weights_entry, run_paths, config.external_roots, tokens)
        site_tz_path = _resolve_dataset_path(site_tz_entry, run_paths, config.external_roots, tokens)
        group_weights_path = _resolve_dataset_path(group_weights_entry, run_paths, config.external_roots, tokens)

        site_weights_df = pl.read_parquet(site_weights_path)
        site_tz_df = pl.read_parquet(site_tz_path)
        if site_weights_df.is_empty() or site_tz_df.is_empty():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "site_weights_or_tz_empty",
                {"site_weights_path": str(site_weights_path), "site_timezones_path": str(site_tz_path)},
                manifest_fingerprint,
            )
        site_join = site_weights_df.join(
            site_tz_df,
            on=["merchant_id", "legal_country_iso", "site_order"],
            how="inner",
        )
        if site_join.is_empty():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "site_weights_join_empty",
                {"site_weights_path": str(site_weights_path), "site_timezones_path": str(site_tz_path)},
                manifest_fingerprint,
            )
        site_join = site_join.with_columns(
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("site_order").cast(pl.Int64),
            pl.col("tzid").cast(pl.Utf8),
            pl.col("p_weight").cast(pl.Float64),
        )

        site_tz_lookup: dict[tuple[int, int], str] = {}
        for merchant_id, site_order, tzid in site_tz_df.select(
            ["merchant_id", "site_order", "tzid"]
        ).iter_rows():
            site_tz_lookup[(int(merchant_id), int(site_order))] = str(tzid)

        site_alias_map: dict[tuple[int, str], tuple[np.ndarray, np.ndarray, list[int]]] = {}
        fallback_alias_map: dict[int, tuple[np.ndarray, np.ndarray, list[int]]] = {}
        missing_alias_keys: set[tuple[int, str]] = set()
        fallback_sites = 0
        for row in (
            site_join.group_by(["merchant_id", "tzid"])
            .agg(
                pl.col("site_order").alias("site_orders"),
                pl.col("p_weight").alias("weights"),
            )
            .iter_rows(named=True)
        ):
            merchant_id = int(row["merchant_id"])
            tzid = str(row["tzid"])
            pairs = sorted(
                zip(row["site_orders"], row["weights"]),
                key=lambda item: int(item[0]),
            )
            site_orders = [int(val) for val, _ in pairs]
            weights = [float(val) for _, val in pairs]
            prob, alias, fallback_used = _build_alias_table(weights)
            if fallback_used:
                fallback_sites += 1
            site_alias_map[(merchant_id, tzid)] = (prob, alias, site_orders)
        for row in (
            site_join.group_by(["merchant_id"])
            .agg(
                pl.col("site_order").alias("site_orders"),
                pl.col("p_weight").alias("weights"),
            )
            .iter_rows(named=True)
        ):
            merchant_id = int(row["merchant_id"])
            pairs = sorted(
                zip(row["site_orders"], row["weights"]),
                key=lambda item: int(item[0]),
            )
            site_orders = [int(val) for val, _ in pairs]
            weights = [float(val) for _, val in pairs]
            prob, alias, fallback_used = _build_alias_table(weights)
            if fallback_used:
                fallback_sites += 1
            fallback_alias_map[merchant_id] = (prob, alias, site_orders)
        if fallback_sites:
            logger.warning("S4: %d site alias tables used fallback weights due to invalid inputs", fallback_sites)

        if not group_weights_path.exists():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "group_weights_missing",
                {"path": str(group_weights_path)},
                manifest_fingerprint,
            )
        group_weight_years: set[str] = set(
            pl.scan_parquet(group_weights_path)
            .select(pl.col("utc_day").cast(pl.Utf8).str.slice(0, 4).unique())
            .collect()
            .get_column("utc_day")
            .to_list()
        )
        if not group_weight_years:
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "group_weights_empty",
                {"path": str(group_weights_path)},
                manifest_fingerprint,
            )
        group_weights_cache_years: set[str] = set()
        group_weights_map: Optional[dict[tuple[int, str], set[str]]] = None

        classification_entry = find_dataset_entry(dictionary_5b, "virtual_classification_3B").entry
        classification_path = _resolve_dataset_path(classification_entry, run_paths, config.external_roots, tokens)
        classification_df = pl.read_parquet(classification_path)
        if classification_df.is_empty():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "virtual_classification_empty",
                {"path": str(classification_path)},
                manifest_fingerprint,
            )
        classification_map: dict[int, dict[str, object]] = {}
        for row in classification_df.select(["merchant_id", "is_virtual", "virtual_mode"]).iter_rows(named=True):
            classification_map[int(row["merchant_id"])] = {
                "is_virtual": bool(row["is_virtual"]),
                "virtual_mode": str(row["virtual_mode"]),
            }

        settlement_map: dict[int, str] = {}
        if virtual_settlement_row is not None:
            settlement_entry = find_dataset_entry(dictionary_5b, "virtual_settlement_3B").entry
            settlement_path = _resolve_dataset_path(settlement_entry, run_paths, config.external_roots, tokens)
            if settlement_path.exists():
                settlement_df = pl.read_parquet(settlement_path)
                if not settlement_df.is_empty():
                    for row in settlement_df.select(["merchant_id", "tzid_settlement"]).iter_rows(named=True):
                        settlement_map[int(row["merchant_id"])] = str(row["tzid_settlement"])

        edge_catalogue_entry = find_dataset_entry(dictionary_5b, "edge_catalogue_3B").entry
        edge_catalogue_path = _resolve_dataset_path(edge_catalogue_entry, run_paths, config.external_roots, tokens)
        edge_catalogue_files = _list_parquet_files(edge_catalogue_path)
        edge_catalogue_df = pl.concat([pl.read_parquet(path) for path in edge_catalogue_files])
        if edge_catalogue_df.is_empty():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "edge_catalogue_empty",
                {"path": str(edge_catalogue_path)},
                manifest_fingerprint,
            )
        edge_catalogue_df = edge_catalogue_df.sort(["merchant_id", "edge_seq_index"])
        edge_map: dict[int, tuple[list[int], list[str]]] = {}
        for row in (
            edge_catalogue_df.group_by("merchant_id", maintain_order=True)
            .agg(
                pl.col("edge_id").alias("edge_ids"),
                pl.col("tzid_operational").alias("tzid_operational"),
            )
            .iter_rows(named=True)
        ):
            merchant_id = int(row["merchant_id"])
            edge_ids_raw = row["edge_ids"]
            tzids_raw = row["tzid_operational"]
            edge_ids: list[int] = []
            tzids: list[str] = []
            for edge_id, tzid in zip(edge_ids_raw, tzids_raw):
                try:
                    parsed = int(str(edge_id), 16)
                except ValueError:
                    _abort(
                        "5B.S4.ROUTING_POLICY_INVALID",
                        "V-06",
                        "edge_id_parse_failed",
                        {"edge_id": edge_id, "merchant_id": merchant_id},
                        manifest_fingerprint,
                    )
                if parsed <= 0 or parsed > UINT64_MAX:
                    _abort(
                        "5B.S4.ROUTING_POLICY_INVALID",
                        "V-06",
                        "edge_id_out_of_range",
                        {"edge_id": edge_id, "merchant_id": merchant_id},
                        manifest_fingerprint,
                    )
                edge_ids.append(parsed)
                tzids.append(str(tzid))
            edge_map[merchant_id] = (edge_ids, tzids)

        edge_alias_index_entry = find_dataset_entry(dictionary_5b, "edge_alias_index_3B").entry
        edge_alias_blob_entry = find_dataset_entry(dictionary_5b, "edge_alias_blob_3B").entry
        edge_alias_index_path = _resolve_dataset_path(edge_alias_index_entry, run_paths, config.external_roots, tokens)
        edge_alias_blob_path = _resolve_dataset_path(edge_alias_blob_entry, run_paths, config.external_roots, tokens)
        edge_alias_index_df = pl.read_parquet(edge_alias_index_path)
        if edge_alias_index_df.is_empty():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "edge_alias_index_empty",
                {"path": str(edge_alias_index_path)},
                manifest_fingerprint,
            )
        edge_alias_index_df = edge_alias_index_df.with_columns(
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("blob_offset_bytes").cast(pl.Int64),
            pl.col("blob_length_bytes").cast(pl.Int64),
            pl.col("edge_count_total").cast(pl.Int64),
            pl.col("alias_table_length").cast(pl.Int64),
            pl.col("alias_layout_version").cast(pl.Utf8),
        )
        edge_alias_meta: dict[int, dict[str, object]] = {}
        alias_layout_versions = set()
        for row in edge_alias_index_df.filter(pl.col("scope") == "MERCHANT").iter_rows(named=True):
            merchant_id = int(row["merchant_id"])
            edge_alias_meta[merchant_id] = {
                "offset": int(row["blob_offset_bytes"]),
                "length": int(row["blob_length_bytes"]),
                "edge_count": int(row["edge_count_total"]),
                "alias_length": int(row["alias_table_length"]),
            }
            if row.get("alias_layout_version"):
                alias_layout_versions.add(str(row["alias_layout_version"]))
        if alias_layout_versions and alias_layout_version not in alias_layout_versions:
            _abort(
                "5B.S4.ROUTING_POLICY_INVALID",
                "V-06",
                "alias_layout_version_inconsistent",
                {"alias_layout_version": alias_layout_version, "index_versions": sorted(alias_layout_versions)},
                manifest_fingerprint,
            )

        if not edge_alias_blob_path.exists():
            _abort(
                "5B.S4.S1_OUTPUT_MISSING",
                "V-06",
                "edge_alias_blob_missing",
                {"path": str(edge_alias_blob_path)},
                manifest_fingerprint,
            )

        blob_view = _BlobView(edge_alias_blob_path)
        edge_alias_cache: dict[int, tuple[np.ndarray, np.ndarray, int]] = {}
        alias_endianness = str(alias_layout_policy.get("endianness") or "little")

        if use_parallel and shared_maps_enabled:
            shared_maps_root = _build_shared_maps(
                run_paths,
                str(manifest_fingerprint),
                tz_cache,
                classification_map,
                settlement_map,
                edge_map,
                edge_alias_meta,
                edge_alias_blob_path,
                alias_endianness,
                site_alias_map,
                fallback_alias_map,
                site_tz_lookup,
                logger,
            )
            logger.info("S4: shared_maps=on root=%s", shared_maps_root)
            classification_map = {}
            settlement_map = {}
            edge_map = {}
            edge_alias_meta = {}
            site_alias_map = {}
            fallback_alias_map = {}
            site_tz_lookup = {}
        elif use_parallel:
            logger.info("S4: shared_maps=off (set ENGINE_5B_S4_SHARED_MAPS=1 to enable)")

        try:
            for scenario_id in scenario_set:
                scenario_start = time.monotonic()
                current_phase = f"scenario:{scenario_id}"
                logger.info(
                    "S4: scenario=%s start (inputs: time_grid, grouping, bucket_counts; output arrival_events_5B)",
                    scenario_id,
                )
                scenario_tokens = dict(tokens)
                scenario_tokens["scenario_id"] = str(scenario_id)
                time_grid_entry = find_dataset_entry(dictionary_5b, "s1_time_grid_5B").entry
                grouping_entry = find_dataset_entry(dictionary_5b, "s1_grouping_5B").entry
                counts_entry = find_dataset_entry(dictionary_5b, "s3_bucket_counts_5B").entry
                realised_entry = find_dataset_entry(dictionary_5b, "s2_realised_intensity_5B").entry

                time_grid_path = _resolve_dataset_path(time_grid_entry, run_paths, config.external_roots, scenario_tokens)
                grouping_path = _resolve_dataset_path(grouping_entry, run_paths, config.external_roots, scenario_tokens)
                counts_path = _resolve_dataset_path(counts_entry, run_paths, config.external_roots, scenario_tokens)
                realised_path = _resolve_dataset_path(realised_entry, run_paths, config.external_roots, scenario_tokens)

                if not time_grid_path.exists():
                    _abort(
                        "5B.S4.S1_OUTPUT_MISSING",
                        "V-06",
                        "time_grid_missing",
                        {"scenario_id": scenario_id, "path": str(time_grid_path)},
                        manifest_fingerprint,
                    )
                if not grouping_path.exists():
                    _abort(
                        "5B.S4.S1_OUTPUT_MISSING",
                        "V-06",
                        "grouping_missing",
                        {"scenario_id": scenario_id, "path": str(grouping_path)},
                        manifest_fingerprint,
                    )
                if not counts_path.exists():
                    _abort(
                        "5B.S4.S3_OUTPUT_MISSING",
                        "V-06",
                        "bucket_counts_missing",
                        {"scenario_id": scenario_id, "path": str(counts_path)},
                        manifest_fingerprint,
                    )
                if not realised_path.exists():
                    _abort(
                        "5B.S4.S2_OUTPUT_MISSING",
                        "V-06",
                        "realised_intensity_missing",
                        {"scenario_id": scenario_id, "path": str(realised_path)},
                        manifest_fingerprint,
                    )

                time_grid_df = pl.read_parquet(time_grid_path)
                if time_grid_df.is_empty():
                    _abort(
                        "5B.S4.S1_OUTPUT_MISSING",
                        "V-06",
                        "time_grid_empty",
                        {"scenario_id": scenario_id, "path": str(time_grid_path)},
                        manifest_fingerprint,
                    )
                grouping_sample = pl.read_parquet(grouping_path, n_rows=1)
                if grouping_sample.is_empty():
                    _abort(
                        "5B.S4.S1_OUTPUT_MISSING",
                        "V-06",
                        "grouping_empty",
                        {"scenario_id": scenario_id, "path": str(grouping_path)},
                        manifest_fingerprint,
                    )
                realised_sample = pl.read_parquet(realised_path, n_rows=1)
                if realised_sample.is_empty():
                    _abort(
                        "5B.S4.S2_OUTPUT_MISSING",
                        "V-06",
                        "realised_intensity_empty",
                        {"scenario_id": scenario_id, "path": str(realised_path)},
                        manifest_fingerprint,
                    )

                bucket_indices = sorted({int(value) for value in time_grid_df.get_column("bucket_index").to_list()})
                bucket_count = len(bucket_indices)
                if not bucket_indices or bucket_indices[0] != 0 or bucket_indices[-1] != bucket_count - 1:
                    _abort(
                        "5B.S4.DOMAIN_ALIGN_FAILED",
                        "V-06",
                        "bucket_index_non_contiguous",
                        {"scenario_id": scenario_id, "bucket_count": bucket_count},
                        manifest_fingerprint,
                    )

                bucket_map: dict[int, dict[str, object]] = {}
                for row in time_grid_df.select(
                    ["bucket_index", "bucket_start_utc", "bucket_end_utc", "bucket_duration_seconds"]
                ).iter_rows(named=True):
                    bucket_index = int(row["bucket_index"])
                    start_micros = _parse_rfc3339_micros(str(row["bucket_start_utc"]))
                    end_micros = _parse_rfc3339_micros(str(row["bucket_end_utc"]))
                    duration_seconds = int(row["bucket_duration_seconds"])
                    if duration_seconds <= 0 or duration_seconds > max_bucket_duration_seconds:
                        _abort(
                            "5B.S4.PLACEMENT_POLICY_INVALID",
                            "V-06",
                            "bucket_duration_invalid",
                            {"bucket_index": bucket_index, "duration_seconds": duration_seconds},
                            manifest_fingerprint,
                        )
                    if end_micros <= start_micros:
                        _abort(
                            "5B.S4.DOMAIN_ALIGN_FAILED",
                            "V-06",
                            "bucket_time_invalid",
                            {"bucket_index": bucket_index},
                            manifest_fingerprint,
                        )
                    bucket_map[bucket_index] = {
                        "start_micros": start_micros,
                        "end_micros": end_micros,
                        "duration_micros": end_micros - start_micros,
                        "duration_seconds": duration_seconds,
                        "utc_day": _utc_day_from_micros(start_micros),
                    }
                bucket_start_micros = np.zeros(bucket_count, dtype=np.int64)
                bucket_duration_micros = np.zeros(bucket_count, dtype=np.int64)
                bucket_duration_seconds = np.zeros(bucket_count, dtype=np.float64)
                for idx in range(bucket_count):
                    info = bucket_map[idx]
                    bucket_start_micros[idx] = int(info["start_micros"])
                    bucket_duration_micros[idx] = int(info["duration_micros"])
                    bucket_duration_seconds[idx] = float(info["duration_seconds"])

                bucket_years = {info["utc_day"][:4] for info in bucket_map.values()}
                skip_group_weight_check = not bool(bucket_years & group_weight_years)
                if skip_group_weight_check:
                    group_weights_map = None
                    group_weights_cache_years.clear()
                    logger.warning(
                        "S4: group_weights years=%s do not cover time_grid years=%s; skipping group-weight validation.",
                        sorted(group_weight_years),
                        sorted(bucket_years),
                    )
                else:
                    if group_weights_map is None:
                        group_weights_map = {}
                    missing_years = bucket_years - group_weights_cache_years
                    if missing_years:
                        group_weights_scan = pl.scan_parquet(group_weights_path).filter(
                            pl.col("utc_day")
                            .cast(pl.Utf8)
                            .str.slice(0, 4)
                            .is_in(sorted(missing_years))
                        )
                        group_weights_df = group_weights_scan.select(
                            ["merchant_id", "utc_day", "tz_group_id"]
                        ).collect()
                        if group_weights_df.is_empty():
                            logger.warning(
                                "S4: group_weights missing for years=%s (path=%s); skipping group-weight validation.",
                                sorted(missing_years),
                                str(group_weights_path),
                            )
                            skip_group_weight_check = True
                            group_weights_map = None
                            group_weights_cache_years.clear()
                        else:
                            for row in (
                                group_weights_df.group_by(["merchant_id", "utc_day"])
                                .agg(pl.col("tz_group_id").alias("tz_group_ids"))
                                .iter_rows(named=True)
                            ):
                                group_key = (int(row["merchant_id"]), str(row["utc_day"]))
                                tz_ids = {str(val) for val in row["tz_group_ids"]}
                                existing = group_weights_map.get(group_key)
                                if existing is None:
                                    group_weights_map[group_key] = tz_ids
                                else:
                                    existing.update(tz_ids)
                            group_weights_cache_years.update(missing_years)
                            logger.info(
                                "S4: group_weights loaded years=%s rows=%d keys=%d",
                                sorted(missing_years),
                                int(group_weights_df.height),
                                len(group_weights_map),
                            )

                counts_files = _list_parquet_files(counts_path)
                total_rows = _count_parquet_rows(counts_files) or 0
                total_count_n = _sum_parquet_column(counts_files, "count_N") or 0
                row_tracker = _ProgressTracker(total_rows, logger, f"S4: bucket rows scenario={scenario_id}")
                arrival_tracker = _ProgressTracker(
                    total_count_n, logger, f"S4: arrivals scenario={scenario_id}"
                )

                events_entry = find_dataset_entry(dictionary_5b, "arrival_events_5B").entry
                summary_entry = find_dataset_entry(dictionary_5b, "s4_arrival_summary_5B").entry
                events_path = _resolve_dataset_path(events_entry, run_paths, config.external_roots, scenario_tokens)
                summary_path = _resolve_dataset_path(summary_entry, run_paths, config.external_roots, scenario_tokens)
                events_root = _event_root_from_path(events_path)

                events_tmp_dir = run_paths.tmp_root / f"s4_events_{uuid.uuid4().hex}"
                events_tmp_dir.mkdir(parents=True, exist_ok=True)
                summary_tmp_path = run_paths.tmp_root / f"s4_summary_{uuid.uuid4().hex}.parquet"
                summary_tmp_dir = None
                events_writer = None
                summary_writer = None
                events_chunks: list[pl.DataFrame] = []
                summary_chunks: list[pl.DataFrame] = []
                if use_parallel:
                    summary_tmp_dir = run_paths.tmp_root / f"s4_summary_parts_{uuid.uuid4().hex}"
                    summary_tmp_dir.mkdir(parents=True, exist_ok=True)
                else:
                    events_tmp_path = events_tmp_dir / "part-00000.parquet"

                last_key: Optional[tuple] = None
                ordering_violations = 0
                ordering_violation_sample = None
                scenario_rows_written = 0
                scenario_arrivals = 0
                scenario_physical = 0
                scenario_virtual = 0
                missing_group_keys: set[tuple[int, str, str]] = set()

                rng_stats = {
                    "arrival_time_jitter": {"events": 0, "draws": 0, "blocks": 0, "last": None},
                    "arrival_site_pick": {"events": 0, "draws": 0, "blocks": 0, "last": None},
                    "arrival_edge_pick": {"events": 0, "draws": 0, "blocks": 0, "last": None},
                }

                if use_parallel:
                    if summary_tmp_dir is None:
                        _abort(
                            "5B.S4.IO_WRITE_FAILED",
                            "V-06",
                            "summary_tmp_dir_missing",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )
                    missing_group_keys = set()
                    arrival_seq_by_merchant: dict[int, int] = {}

                    time_prefix = _rng_prefix_bytes(
                        domain_sep,
                        time_family_id,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        seed,
                        str(scenario_id),
                    )
                    site_prefix = _rng_prefix_bytes(
                        domain_sep,
                        site_family_id,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        seed,
                        str(scenario_id),
                    )
                    edge_prefix = _rng_prefix_bytes(
                        domain_sep,
                        edge_family_id,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        seed,
                        str(scenario_id),
                    )

                    worker_context = {
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "parameter_hash": str(parameter_hash),
                        "seed": int(seed),
                        "spec_version": str(spec_version),
                        "bucket_map": bucket_map,
                        "bucket_start_micros": bucket_start_micros,
                        "bucket_duration_micros": bucket_duration_micros,
                        "bucket_duration_seconds": bucket_duration_seconds,
                        "tz_cache": tz_cache,
                        "edge_alias_blob_path": str(edge_alias_blob_path),
                        "alias_endianness": alias_endianness,
                        "group_weights_map": group_weights_map,
                        "skip_group_weight_check": skip_group_weight_check,
                        "zone_alloc_universe_hash": zone_alloc_universe_hash,
                        "edge_universe_hash": edge_universe_hash,
                        "max_arrivals_per_bucket": max_arrivals_per_bucket,
                        "p_virtual_hybrid": p_virtual_hybrid,
                        "time_prefix": time_prefix,
                        "site_prefix": site_prefix,
                        "edge_prefix": edge_prefix,
                        "draws_per_arrival": draws_per_arrival,
                        "output_validate_full": output_validate_full,
                        "output_sample_rows": output_sample_rows,
                        "output_buffer_rows": output_buffer_rows,
                        "ordering_required": ordering_required,
                        "event_schema": event_schema,
                        "summary_schema": summary_schema,
                        "events_tmp_dir": str(events_tmp_dir),
                        "summary_tmp_dir": str(summary_tmp_dir),
                        "compiled_kernel": bool(compiled_kernel_enabled),
                    }
                    if shared_maps_root is not None:
                        worker_context["shared_maps_root"] = str(shared_maps_root)
                    else:
                        worker_context.update(
                            {
                                "site_alias_map": site_alias_map,
                                "fallback_alias_map": fallback_alias_map,
                                "site_tz_lookup": site_tz_lookup,
                                "edge_alias_meta": edge_alias_meta,
                                "edge_map": edge_map,
                                "settlement_map": settlement_map,
                                "classification_map": classification_map,
                            }
                        )

                    def _handle_result(result: dict, expected_batch_id: int) -> None:
                        nonlocal scenario_rows_written
                        nonlocal scenario_arrivals
                        nonlocal scenario_physical
                        nonlocal scenario_virtual
                        nonlocal total_rows_written
                        nonlocal total_arrivals
                        nonlocal total_physical
                        nonlocal total_virtual
                        if result.get("error"):
                            _abort(
                                result["error"].get("failure_code") or "5B.S4.IO_WRITE_FAILED",
                                "V-06",
                                "worker_exception",
                                {
                                    "scenario_id": scenario_id,
                                    "batch_id": expected_batch_id,
                                    "error": result["error"],
                                },
                                manifest_fingerprint,
                            )
                        if result.get("batch_id") != expected_batch_id:
                            _abort(
                                "5B.S4.DOMAIN_ALIGN_FAILED",
                                "V-08",
                                "batch_index_mismatch",
                                {"scenario_id": scenario_id, "expected": expected_batch_id, "actual": result.get("batch_id")},
                                manifest_fingerprint,
                            )
                        batch_rows = int(result.get("rows_written") or 0)
                        batch_arrivals = int(result.get("arrivals") or 0)
                        batch_physical = int(result.get("physical") or 0)
                        batch_virtual = int(result.get("virtual") or 0)
                        scenario_rows_written += batch_rows
                        scenario_arrivals += batch_arrivals
                        scenario_physical += batch_physical
                        scenario_virtual += batch_virtual
                        total_rows_written += batch_rows
                        total_arrivals += batch_arrivals
                        total_physical += batch_physical
                        total_virtual += batch_virtual

                        for label, stats in (result.get("rng_stats") or {}).items():
                            if label not in rng_stats:
                                continue
                            rng_stats[label]["events"] += int(stats.get("events") or 0)
                            rng_stats[label]["draws"] += int(stats.get("draws") or 0)
                            rng_stats[label]["blocks"] += int(stats.get("blocks") or 0)
                            if stats.get("last") is not None:
                                rng_stats[label]["last"] = stats.get("last")

                        for key in result.get("missing_group_keys") or []:
                            if key not in missing_group_keys:
                                logger.warning(
                                    "S4: group_weights missing (merchant_id=%s utc_day=%s tz_group_id=%s); "
                                    "continuing with zone_representation routing.",
                                    key[0],
                                    key[1],
                                    key[2],
                                )
                                missing_group_keys.add(key)

                        for key in result.get("missing_alias_keys") or []:
                            if key not in missing_alias_keys:
                                logger.warning(
                                    "S4: site alias missing for merchant_id=%s tzid=%s; using fallback merchant alias",
                                    key[0],
                                    key[1],
                                )
                                missing_alias_keys.add(key)

                    executor = None
                    pending: deque[tuple[int, concurrent.futures.Future]] = deque()
                    batch_id = 0
                    try:
                        executor = concurrent.futures.ProcessPoolExecutor(
                            max_workers=worker_count,
                            initializer=_init_s4_worker,
                            initargs=(worker_context,),
                        )
                        for batch in _iter_parquet_batches(
                            counts_files,
                            ["merchant_id", "zone_representation", "channel_group", "bucket_index", "count_N", "lambda_realised"],
                        ):
                            if _HAVE_PYARROW and pa and isinstance(batch, pa.Table):
                                df = pl.from_arrow(batch)
                            else:
                                df = batch
                            merchants = df.get_column("merchant_id").to_list()
                            zones = df.get_column("zone_representation").to_list()
                            channels = df.get_column("channel_group").to_list()
                            buckets = df.get_column("bucket_index").to_list()
                            counts = df.get_column("count_N").to_list()
                            lambdas = (
                                df.get_column("lambda_realised").to_list()
                                if "lambda_realised" in df.columns
                                else [None] * df.height
                            )
                            arrival_seq_start = [0] * df.height
                            for idx in range(df.height):
                                row_tracker.update(1)
                                count_n = int(counts[idx] or 0)
                                if count_n <= 0:
                                    continue
                                merchant_id = int(merchants[idx])
                                start_seq = arrival_seq_by_merchant.get(merchant_id, 0) + 1
                                arrival_seq_start[idx] = start_seq
                                arrival_seq_by_merchant[merchant_id] = start_seq + count_n - 1
                                arrival_tracker.update(count_n)

                            payload = {
                                "batch_id": batch_id,
                                "scenario_id": scenario_id,
                                "merchant_id": merchants,
                                "zone_representation": zones,
                                "channel_group": channels,
                                "bucket_index": buckets,
                                "count_N": counts,
                                "lambda_realised": lambdas,
                                "arrival_seq_start": arrival_seq_start,
                            }
                            future = executor.submit(_process_s4_batch, payload)
                            pending.append((batch_id, future))
                            if len(pending) >= max_inflight:
                                queued_id, queued_future = pending.popleft()
                                result = queued_future.result()
                                _handle_result(result, queued_id)
                            batch_id += 1
                        while pending:
                            queued_id, queued_future = pending.popleft()
                            result = queued_future.result()
                            _handle_result(result, queued_id)
                    finally:
                        if executor is not None:
                            executor.shutdown(wait=True, cancel_futures=False)

                    summary_parts = sorted(summary_tmp_dir.glob("part-*.parquet"))
                    if summary_parts:
                        summary_writer = None
                        for part_path in summary_parts:
                            parquet = pq.ParquetFile(part_path)
                            for rg in range(parquet.num_row_groups):
                                table = parquet.read_row_group(rg)
                                if summary_writer is None:
                                    summary_writer = pq.ParquetWriter(
                                        summary_tmp_path, table.schema, compression="zstd"
                                    )
                                summary_writer.write_table(table)
                        if summary_writer is not None:
                            summary_writer.close()

                    if scenario_rows_written == 0:
                        _abort(
                            "5B.S4.DOMAIN_ALIGN_FAILED",
                            "V-08",
                            "arrival_events_empty",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )

                    _atomic_publish_dir(events_tmp_dir, events_root, logger, f"arrival_events_5B scenario_id={scenario_id}")
                    if summary_parts:
                        _atomic_publish_file(
                            summary_tmp_path,
                            summary_path,
                            logger,
                            f"s4_arrival_summary_5B scenario_id={scenario_id}",
                        )
                        summary_paths.append(summary_path)
                    event_paths.append(events_root)

                    if trace_handle is not None:
                        for label, stats in rng_stats.items():
                            last_counters = stats.get("last")
                            if not last_counters:
                                continue
                            counter_hi, counter_lo, next_hi, next_lo = last_counters
                            trace_row = {
                                "ts_utc": utc_now_rfc3339_micro(),
                                "run_id": str(run_id),
                                "seed": int(seed),
                                "module": "5B.S4",
                                "substream_label": label,
                                "rng_counter_before_lo": int(counter_lo),
                                "rng_counter_before_hi": int(counter_hi),
                                "rng_counter_after_lo": int(next_lo),
                                "rng_counter_after_hi": int(next_hi),
                                "draws_total": int(stats.get("draws") or 0),
                                "blocks_total": int(stats.get("blocks") or 0),
                                "events_total": int(stats.get("events") or 0),
                            }
                            trace_handle.write(_json_dumps(trace_row))
                            trace_handle.write("\n")

                    scenario_details[str(scenario_id)] = {
                        "arrival_rows": int(scenario_rows_written),
                        "arrival_total": int(scenario_arrivals),
                        "arrival_physical": int(scenario_physical),
                        "arrival_virtual": int(scenario_virtual),
                        "ordering_violations": int(ordering_violations),
                        "duration_s": int(time.monotonic() - scenario_start),
                    }
                    ordering_violations_total += ordering_violations
                    scenario_count_succeeded += 1

                    logger.info(
                        "S4: scenario=%s completed arrivals=%d physical=%d virtual=%d ordering_violations=%d",
                        scenario_id,
                        scenario_arrivals,
                        scenario_physical,
                        scenario_virtual,
                        ordering_violations,
                    )
                    continue

                def _flush_event_buffers() -> None:
                    for label, handle in event_handles.items():
                        buffer = event_buffers.get(label)
                        if handle is None or buffer is None or not buffer:
                            continue
                        handle.write("\n".join(buffer))
                        handle.write("\n")
                        buffer.clear()

                def _write_events(rows: list[dict]) -> None:
                    nonlocal events_writer
                    if not rows:
                        return
                    df = pl.DataFrame(rows, schema=_S4_EVENT_SCHEMA)
                    df = _coerce_int_columns(df, _S4_EVENT_UINT64_COLUMNS, _S4_EVENT_INT64_COLUMNS)
                    if output_validate_full:
                        _validate_array_rows(
                            df.iter_rows(named=True),
                            schema_5b,
                            schema_layer1,
                            schema_layer2,
                            "egress/s4_arrival_events_5B",
                            logger=logger,
                            label=f"S4: validate arrivals scenario_id={scenario_id}",
                            total_rows=df.height,
                        )
                    elif output_sample_rows > 0:
                        sample_df = df.head(min(output_sample_rows, df.height))
                        for row in sample_df.iter_rows(named=True):
                            errors = list(event_row_validator.iter_errors(row))
                            if errors:
                                raise SchemaValidationError(str(errors[0]), [])
                    if _HAVE_PYARROW:
                        table = df.to_arrow()
                        if events_writer is None:
                            events_writer = pq.ParquetWriter(events_tmp_path, table.schema, compression="zstd")
                        events_writer.write_table(table)
                    else:
                        events_chunks.append(df)

                def _write_summary(rows: list[dict]) -> None:
                    nonlocal summary_writer
                    if not rows:
                        return
                    df = pl.DataFrame(rows, schema=_S4_SUMMARY_SCHEMA)
                    df = _coerce_int_columns(df, _S4_SUMMARY_UINT64_COLUMNS, _S4_SUMMARY_INT64_COLUMNS)
                    if output_validate_full:
                        _validate_array_rows(
                            df.iter_rows(named=True),
                            schema_5b,
                            schema_layer1,
                            schema_layer2,
                            "diagnostics/s4_arrival_summary_5B",
                            logger=logger,
                            label=f"S4: validate summary scenario_id={scenario_id}",
                            total_rows=df.height,
                        )
                    elif output_sample_rows > 0:
                        sample_df = df.head(min(output_sample_rows, df.height))
                        for row in sample_df.iter_rows(named=True):
                            errors = list(summary_row_validator.iter_errors(row))
                            if errors:
                                raise SchemaValidationError(str(errors[0]), [])
                    if _HAVE_PYARROW:
                        table = df.to_arrow()
                        if summary_writer is None:
                            summary_writer = pq.ParquetWriter(summary_tmp_path, table.schema, compression="zstd")
                        summary_writer.write_table(table)
                    else:
                        summary_chunks.append(df)

                arrival_seq_by_merchant: dict[int, int] = {}
                event_rows: list[dict] = []
                summary_rows: list[dict] = []

                time_prefix = _rng_prefix_hasher(
                    domain_sep,
                    time_family_id,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    seed,
                    str(scenario_id),
                )
                site_prefix = _rng_prefix_hasher(
                    domain_sep,
                    site_family_id,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    seed,
                    str(scenario_id),
                )
                edge_prefix = _rng_prefix_hasher(
                    domain_sep,
                    edge_family_id,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    seed,
                    str(scenario_id),
                )

                for batch in _iter_parquet_batches(
                    counts_files,
                    ["merchant_id", "zone_representation", "channel_group", "bucket_index", "count_N", "lambda_realised"],
                ):
                    if _HAVE_PYARROW and pa and isinstance(batch, pa.Table):
                        df = pl.from_arrow(batch)
                    else:
                        df = batch
                    merchants = df.get_column("merchant_id").to_list()
                    zones = df.get_column("zone_representation").to_list()
                    channels = df.get_column("channel_group").to_list()
                    buckets = df.get_column("bucket_index").to_list()
                    counts = df.get_column("count_N").to_list()
                    lambdas = df.get_column("lambda_realised").to_list() if "lambda_realised" in df.columns else [None] * df.height

                    for idx in range(df.height):
                        row_tracker.update(1)
                        merchant_id = int(merchants[idx])
                        zone_representation = str(zones[idx])
                        channel_group = str(channels[idx]) if channels[idx] is not None else None
                        bucket_index = int(buckets[idx])
                        count_n = int(counts[idx] or 0)
                        lambda_realised = lambdas[idx]
                        if count_n <= 0:
                            continue

                        bucket_info = bucket_map.get(bucket_index)
                        if not bucket_info:
                            _abort(
                                "5B.S4.DOMAIN_ALIGN_FAILED",
                                "V-06",
                                "bucket_missing",
                                {"scenario_id": scenario_id, "bucket_index": bucket_index},
                                manifest_fingerprint,
                            )
                        if count_n > max_arrivals_per_bucket:
                            _abort(
                                "5B.S4.PLACEMENT_POLICY_INVALID",
                                "V-06",
                                "bucket_count_exceeds_guardrail",
                                {"bucket_index": bucket_index, "count_N": count_n, "max": max_arrivals_per_bucket},
                                manifest_fingerprint,
                            )

                        utc_day = str(bucket_info["utc_day"])
                        group_key = (merchant_id, utc_day)
                        if (
                            not skip_group_weight_check
                            and group_weights_map is not None
                            and zone_representation not in group_weights_map.get(group_key, set())
                        ):
                            missing_key = (merchant_id, utc_day, zone_representation)
                            if missing_key not in missing_group_keys:
                                logger.warning(
                                    "S4: group_weights missing (merchant_id=%s utc_day=%s tz_group_id=%s); "
                                    "continuing with zone_representation routing.",
                                    merchant_id,
                                    utc_day,
                                    zone_representation,
                                )
                                missing_group_keys.add(missing_key)

                        classification = classification_map.get(merchant_id)
                        if not classification:
                            _abort(
                                "5B.S4.ROUTING_POLICY_INVALID",
                                "V-06",
                                "classification_missing",
                                {"merchant_id": merchant_id},
                                manifest_fingerprint,
                            )
                        virtual_mode = str(classification.get("virtual_mode") or "")
                        if virtual_mode not in {"NON_VIRTUAL", "HYBRID", "VIRTUAL_ONLY"}:
                            _abort(
                                "5B.S4.ROUTING_POLICY_INVALID",
                                "V-06",
                                "virtual_mode_invalid",
                                {"merchant_id": merchant_id, "virtual_mode": virtual_mode},
                                manifest_fingerprint,
                            )

                        bucket_events = [] if ordering_stats_enabled else None
                        count_physical = 0
                        count_virtual = 0

                        for _ in range(count_n):
                            arrival_seq = arrival_seq_by_merchant.get(merchant_id, 0) + 1
                            arrival_seq_by_merchant[merchant_id] = arrival_seq
                            domain_key = f"{merchant_id}|{zone_representation}|{bucket_index}|{arrival_seq}"

                            time_key, time_counter_hi, time_counter_lo = _derive_rng_seed(time_prefix, domain_key)
                            time_values, time_blocks, time_next_hi, time_next_lo = _draw_philox_u64(
                                time_key,
                                time_counter_hi,
                                time_counter_lo,
                                draws_per_arrival,
                                str(manifest_fingerprint),
                            )
                            u_time = _u01_from_u64(time_values[0])
                            offset_micros = int(
                                math.floor(u_time * float(bucket_info["duration_seconds"]) * _MICROS_PER_SECOND)
                            )
                            max_offset = int(bucket_info["duration_micros"]) - 1
                            if offset_micros > max_offset:
                                offset_micros = max_offset if max_offset > 0 else 0
                            ts_utc_micros = int(bucket_info["start_micros"]) + offset_micros
                            ts_utc = _format_rfc3339_micros(ts_utc_micros)

                            if event_enabled.get("arrival_time_jitter"):
                                event_payload = {
                                    "ts_utc": utc_now_rfc3339_micro(),
                                    "run_id": str(run_id),
                                    "seed": int(seed),
                                    "parameter_hash": str(parameter_hash),
                                    "manifest_fingerprint": str(manifest_fingerprint),
                                    "module": "5B.S4",
                                    "substream_label": "arrival_time_jitter",
                                    "scenario_id": str(scenario_id),
                                    "bucket_index": int(bucket_index),
                                    "merchant_id": int(merchant_id),
                                    "arrival_seq": int(arrival_seq),
                                    "rng_counter_before_lo": int(time_counter_lo),
                                    "rng_counter_before_hi": int(time_counter_hi),
                                    "rng_counter_after_lo": int(time_next_lo),
                                    "rng_counter_after_hi": int(time_next_hi),
                                    "draws": str(draws_per_arrival),
                                    "blocks": int(time_blocks),
                                }
                                validator = event_validators["arrival_time_jitter"]
                                remaining = validate_remaining.get("arrival_time_jitter")
                                if remaining is None or remaining > 0:
                                    errors = list(validator.iter_errors(event_payload))
                                    if errors:
                                        raise EngineFailure(
                                            "F4",
                                            "5B.S4.RNG_ACCOUNTING_MISMATCH",
                                            STATE,
                                            MODULE_NAME,
                                            {"scenario_id": scenario_id, "error": str(errors[0])},
                                        )
                                    if remaining is not None:
                                        validate_remaining["arrival_time_jitter"] = remaining - 1
                                event_buffers["arrival_time_jitter"].append(_json_dumps(event_payload))
                                if len(event_buffers["arrival_time_jitter"]) >= event_buffer_size:
                                    _flush_event_buffers()
                            rng_stats["arrival_time_jitter"]["events"] += 1
                            rng_stats["arrival_time_jitter"]["draws"] += draws_per_arrival
                            rng_stats["arrival_time_jitter"]["blocks"] += int(time_blocks)
                            rng_stats["arrival_time_jitter"]["last"] = (
                                time_counter_hi,
                                time_counter_lo,
                                time_next_hi,
                                time_next_lo,
                            )

                            u_site_primary = None
                            u_site_secondary = None
                            use_site_pick = virtual_mode != "VIRTUAL_ONLY"
                            if use_site_pick:
                                site_key, site_counter_hi, site_counter_lo = _derive_rng_seed(site_prefix, domain_key)
                                site_values, site_blocks, site_next_hi, site_next_lo = _draw_philox_u64(
                                    site_key,
                                    site_counter_hi,
                                    site_counter_lo,
                                    2,
                                    str(manifest_fingerprint),
                                )
                                u_site_primary = _u01_from_u64(site_values[0])
                                u_site_secondary = _u01_from_u64(site_values[1])

                                if event_enabled.get("arrival_site_pick"):
                                    event_payload = {
                                        "ts_utc": utc_now_rfc3339_micro(),
                                        "run_id": str(run_id),
                                        "seed": int(seed),
                                        "parameter_hash": str(parameter_hash),
                                        "manifest_fingerprint": str(manifest_fingerprint),
                                        "module": "5B.S4",
                                        "substream_label": "arrival_site_pick",
                                        "scenario_id": str(scenario_id),
                                        "bucket_index": int(bucket_index),
                                        "merchant_id": int(merchant_id),
                                        "arrival_seq": int(arrival_seq),
                                        "rng_counter_before_lo": int(site_counter_lo),
                                        "rng_counter_before_hi": int(site_counter_hi),
                                        "rng_counter_after_lo": int(site_next_lo),
                                        "rng_counter_after_hi": int(site_next_hi),
                                        "draws": "2",
                                        "blocks": int(site_blocks),
                                    }
                                    validator = event_validators["arrival_site_pick"]
                                    remaining = validate_remaining.get("arrival_site_pick")
                                    if remaining is None or remaining > 0:
                                        errors = list(validator.iter_errors(event_payload))
                                        if errors:
                                            raise EngineFailure(
                                                "F4",
                                                "5B.S4.RNG_ACCOUNTING_MISMATCH",
                                                STATE,
                                                MODULE_NAME,
                                                {"scenario_id": scenario_id, "error": str(errors[0])},
                                            )
                                        if remaining is not None:
                                            validate_remaining["arrival_site_pick"] = remaining - 1
                                    event_buffers["arrival_site_pick"].append(_json_dumps(event_payload))
                                    if len(event_buffers["arrival_site_pick"]) >= event_buffer_size:
                                        _flush_event_buffers()
                                rng_stats["arrival_site_pick"]["events"] += 1
                                rng_stats["arrival_site_pick"]["draws"] += 2
                                rng_stats["arrival_site_pick"]["blocks"] += int(site_blocks)
                                rng_stats["arrival_site_pick"]["last"] = (
                                    site_counter_hi,
                                    site_counter_lo,
                                    site_next_hi,
                                    site_next_lo,
                                )

                            is_virtual = virtual_mode == "VIRTUAL_ONLY"
                            if virtual_mode == "HYBRID":
                                is_virtual = bool(u_site_primary is not None and u_site_primary < p_virtual_hybrid)

                            tzid_primary = None
                            ts_local_primary = None
                            tzid_operational = None
                            ts_local_operational = None
                            tzid_settlement = None
                            ts_local_settlement = None
                            site_id = None
                            edge_id = None
                            routing_universe_hash = None

                            if is_virtual:
                                edge_meta = edge_alias_meta.get(merchant_id)
                                edge_list = edge_map.get(merchant_id)
                                if edge_meta is None or edge_list is None:
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "edge_alias_missing",
                                        {"merchant_id": merchant_id},
                                        manifest_fingerprint,
                                    )
                                if merchant_id not in edge_alias_cache:
                                    prob, alias, edge_count = _decode_alias_slice(
                                        blob_view,
                                        edge_meta["offset"],
                                        edge_meta["length"],
                                        alias_endianness,
                                    )
                                    if edge_count != edge_meta["edge_count"]:
                                        _abort(
                                            "5B.S4.ROUTING_POLICY_INVALID",
                                            "V-06",
                                            "edge_alias_count_mismatch",
                                            {
                                                "merchant_id": merchant_id,
                                                "alias_count": edge_count,
                                                "edge_count": edge_meta["edge_count"],
                                            },
                                            manifest_fingerprint,
                                        )
                                    edge_alias_cache[merchant_id] = (prob, alias, edge_count)
                                prob, alias, edge_count = edge_alias_cache[merchant_id]
                                edge_ids, edge_tzids = edge_list
                                if edge_count != len(edge_ids):
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "edge_catalogue_count_mismatch",
                                        {
                                            "merchant_id": merchant_id,
                                            "alias_count": edge_count,
                                            "edge_catalogue_count": len(edge_ids),
                                        },
                                        manifest_fingerprint,
                                    )
                                edge_key, edge_counter_hi, edge_counter_lo = _derive_rng_seed(
                                    edge_prefix, domain_key
                                )
                                edge_values, edge_blocks, edge_next_hi, edge_next_lo = _draw_philox_u64(
                                    edge_key,
                                    edge_counter_hi,
                                    edge_counter_lo,
                                    1,
                                    str(manifest_fingerprint),
                                )
                                u_edge = _u01_from_u64(edge_values[0])
                                edge_index = _alias_pick(prob, alias, u_edge)
                                if edge_index >= len(edge_ids):
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "edge_index_out_of_range",
                                        {"merchant_id": merchant_id, "edge_index": edge_index},
                                        manifest_fingerprint,
                                    )
                                edge_id = int(edge_ids[edge_index])
                                tzid_operational = edge_tzids[edge_index]
                                tzid_settlement = settlement_map.get(merchant_id)
                                if tzid_operational not in tz_cache:
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "tzid_operational_unknown",
                                        {"tzid_operational": tzid_operational},
                                        manifest_fingerprint,
                                    )
                                tzid_primary = tzid_operational
                                offset_min = _tz_offset_minutes(tz_cache[tzid_primary], ts_utc_micros // _MICROS_PER_SECOND)
                                ts_local_primary = _format_rfc3339_micros(
                                    ts_utc_micros + offset_min * 60 * _MICROS_PER_SECOND
                                )
                                ts_local_operational = ts_local_primary
                                if tzid_settlement:
                                    if tzid_settlement not in tz_cache:
                                        _abort(
                                            "5B.S4.ROUTING_POLICY_INVALID",
                                            "V-06",
                                            "tzid_settlement_unknown",
                                            {"tzid_settlement": tzid_settlement},
                                            manifest_fingerprint,
                                        )
                                    settlement_offset = _tz_offset_minutes(
                                        tz_cache[tzid_settlement], ts_utc_micros // _MICROS_PER_SECOND
                                    )
                                    ts_local_settlement = _format_rfc3339_micros(
                                        ts_utc_micros + settlement_offset * 60 * _MICROS_PER_SECOND
                                    )
                                routing_universe_hash = edge_universe_hash

                                if event_enabled.get("arrival_edge_pick"):
                                    event_payload = {
                                        "ts_utc": utc_now_rfc3339_micro(),
                                        "run_id": str(run_id),
                                        "seed": int(seed),
                                        "parameter_hash": str(parameter_hash),
                                        "manifest_fingerprint": str(manifest_fingerprint),
                                        "module": "5B.S4",
                                        "substream_label": "arrival_edge_pick",
                                        "scenario_id": str(scenario_id),
                                        "bucket_index": int(bucket_index),
                                        "merchant_id": int(merchant_id),
                                        "arrival_seq": int(arrival_seq),
                                        "rng_counter_before_lo": int(edge_counter_lo),
                                        "rng_counter_before_hi": int(edge_counter_hi),
                                        "rng_counter_after_lo": int(edge_next_lo),
                                        "rng_counter_after_hi": int(edge_next_hi),
                                        "draws": "1",
                                        "blocks": int(edge_blocks),
                                    }
                                    validator = event_validators["arrival_edge_pick"]
                                    remaining = validate_remaining.get("arrival_edge_pick")
                                    if remaining is None or remaining > 0:
                                        errors = list(validator.iter_errors(event_payload))
                                        if errors:
                                            raise EngineFailure(
                                                "F4",
                                                "5B.S4.RNG_ACCOUNTING_MISMATCH",
                                                STATE,
                                                MODULE_NAME,
                                                {"scenario_id": scenario_id, "error": str(errors[0])},
                                            )
                                        if remaining is not None:
                                            validate_remaining["arrival_edge_pick"] = remaining - 1
                                    event_buffers["arrival_edge_pick"].append(_json_dumps(event_payload))
                                    if len(event_buffers["arrival_edge_pick"]) >= event_buffer_size:
                                        _flush_event_buffers()
                                rng_stats["arrival_edge_pick"]["events"] += 1
                                rng_stats["arrival_edge_pick"]["draws"] += 1
                                rng_stats["arrival_edge_pick"]["blocks"] += int(edge_blocks)
                                rng_stats["arrival_edge_pick"]["last"] = (
                                    edge_counter_hi,
                                    edge_counter_lo,
                                    edge_next_hi,
                                    edge_next_lo,
                                )
                                count_virtual += 1
                            else:
                                alias_key = (merchant_id, zone_representation)
                                alias_entry = site_alias_map.get(alias_key)
                                if alias_entry is None:
                                    if alias_key not in missing_alias_keys:
                                        logger.warning(
                                            "S4: site alias missing for merchant_id=%s tzid=%s; using fallback merchant alias",
                                            merchant_id,
                                            zone_representation,
                                        )
                                        missing_alias_keys.add(alias_key)
                                    alias_entry = fallback_alias_map.get(merchant_id)
                                if alias_entry is None:
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "site_alias_missing",
                                        {"merchant_id": merchant_id, "tzid": zone_representation},
                                        manifest_fingerprint,
                                    )
                                prob, alias, site_orders = alias_entry
                                u_site = u_site_secondary if virtual_mode == "HYBRID" else u_site_primary
                                site_index = _alias_pick(prob, alias, u_site)
                                if site_index >= len(site_orders):
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "site_index_out_of_range",
                                        {"merchant_id": merchant_id, "site_index": site_index},
                                        manifest_fingerprint,
                                    )
                                site_id = int(site_orders[site_index])
                                tzid_primary = site_tz_lookup.get((merchant_id, site_id))
                                if tzid_primary is None:
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "site_timezone_missing",
                                        {"merchant_id": merchant_id, "site_id": site_id},
                                        manifest_fingerprint,
                                    )
                                if tzid_primary not in tz_cache:
                                    _abort(
                                        "5B.S4.ROUTING_POLICY_INVALID",
                                        "V-06",
                                        "tzid_primary_unknown",
                                        {"tzid_primary": tzid_primary},
                                        manifest_fingerprint,
                                    )
                                offset_min = _tz_offset_minutes(tz_cache[tzid_primary], ts_utc_micros // _MICROS_PER_SECOND)
                                ts_local_primary = _format_rfc3339_micros(
                                    ts_utc_micros + offset_min * 60 * _MICROS_PER_SECOND
                                )
                                routing_universe_hash = zone_alloc_universe_hash
                                count_physical += 1

                            if tzid_primary is None or ts_local_primary is None or routing_universe_hash is None:
                                _abort(
                                    "5B.S4.ROUTING_POLICY_INVALID",
                                    "V-06",
                                    "routing_fields_missing",
                                    {"merchant_id": merchant_id, "bucket_index": bucket_index},
                                    manifest_fingerprint,
                                )
                            if is_virtual and edge_id is None:
                                _abort(
                                    "5B.S4.ROUTING_POLICY_INVALID",
                                    "V-06",
                                    "edge_id_missing",
                                    {"merchant_id": merchant_id, "bucket_index": bucket_index},
                                    manifest_fingerprint,
                                )
                            if not is_virtual and site_id is None:
                                _abort(
                                    "5B.S4.ROUTING_POLICY_INVALID",
                                    "V-06",
                                    "site_id_missing",
                                    {"merchant_id": merchant_id, "bucket_index": bucket_index},
                                    manifest_fingerprint,
                                )

                            event_row = {
                                "manifest_fingerprint": str(manifest_fingerprint),
                                "parameter_hash": str(parameter_hash),
                                "seed": int(seed),
                                "scenario_id": str(scenario_id),
                                "merchant_id": int(merchant_id),
                                "zone_representation": str(zone_representation),
                                "bucket_index": int(bucket_index),
                                "arrival_seq": int(arrival_seq),
                                "ts_utc": ts_utc,
                                "tzid_primary": str(tzid_primary),
                                "ts_local_primary": str(ts_local_primary),
                                "is_virtual": bool(is_virtual),
                                "routing_universe_hash": str(routing_universe_hash),
                                "s4_spec_version": str(spec_version),
                            }
                            if ordering_stats_enabled:
                                event_row["_ts_utc_micros"] = ts_utc_micros
                            if channel_group is not None:
                                event_row["channel_group"] = str(channel_group)
                            if tzid_operational:
                                event_row["tzid_operational"] = str(tzid_operational)
                            if ts_local_operational:
                                event_row["ts_local_operational"] = str(ts_local_operational)
                            if tzid_settlement:
                                event_row["tzid_settlement"] = str(tzid_settlement)
                            if ts_local_settlement:
                                event_row["ts_local_settlement"] = str(ts_local_settlement)
                            if site_id is not None:
                                event_row["site_id"] = int(site_id)
                            if edge_id is not None:
                                event_row["edge_id"] = int(edge_id)
                            if lambda_realised is not None:
                                event_row["lambda_realised"] = float(lambda_realised)
                            event_row["tz_group_id"] = str(tzid_primary)

                            if ordering_stats_enabled:
                                bucket_events.append(event_row)
                            else:
                                total_rows_written += 1
                                scenario_rows_written += 1
                                total_arrivals += 1
                                scenario_arrivals += 1
                                total_physical += 1 if not event_row["is_virtual"] else 0
                                scenario_physical += 1 if not event_row["is_virtual"] else 0
                                total_virtual += 1 if event_row["is_virtual"] else 0
                                scenario_virtual += 1 if event_row["is_virtual"] else 0

                                event_rows.append(event_row)
                                if len(event_rows) >= output_buffer_rows:
                                    _write_events(event_rows)
                                    event_rows = []
                        if ordering_stats_enabled and bucket_events:
                            bucket_events.sort(key=lambda item: (item["_ts_utc_micros"], item["arrival_seq"]))
                            for event_row in bucket_events:
                                event_row.pop("_ts_utc_micros", None)
                                total_rows_written += 1
                                scenario_rows_written += 1
                                total_arrivals += 1
                                scenario_arrivals += 1
                                total_physical += 1 if not event_row["is_virtual"] else 0
                                scenario_physical += 1 if not event_row["is_virtual"] else 0
                                total_virtual += 1 if event_row["is_virtual"] else 0
                                scenario_virtual += 1 if event_row["is_virtual"] else 0

                                key_tuple = (
                                    scenario_id,
                                    int(event_row["merchant_id"]),
                                    str(event_row["zone_representation"]),
                                    int(event_row["bucket_index"]),
                                    str(event_row["ts_utc"]),
                                    int(event_row["arrival_seq"]),
                                )
                                if last_key is not None and key_tuple < last_key:
                                    ordering_violations += 1
                                    if ordering_violation_sample is None:
                                        ordering_violation_sample = (last_key, key_tuple)
                                    if strict_ordering:
                                        _abort(
                                            "5B.S4.DOMAIN_ALIGN_FAILED",
                                            "V-08",
                                            "ordering_violation",
                                            {"scenario_id": scenario_id},
                                            manifest_fingerprint,
                                        )
                                last_key = key_tuple

                                event_rows.append(event_row)
                                if len(event_rows) >= output_buffer_rows:
                                    _write_events(event_rows)
                                    event_rows = []

                        summary_row = {
                            "manifest_fingerprint": str(manifest_fingerprint),
                            "parameter_hash": str(parameter_hash),
                            "seed": int(seed),
                            "scenario_id": str(scenario_id),
                            "merchant_id": int(merchant_id),
                            "zone_representation": str(zone_representation),
                            "bucket_index": int(bucket_index),
                            "count_N": int(count_n),
                            "count_physical": int(count_physical),
                            "count_virtual": int(count_virtual),
                            "s4_spec_version": str(spec_version),
                        }
                        if channel_group is not None:
                            summary_row["channel_group"] = str(channel_group)
                        summary_rows.append(summary_row)
                        if len(summary_rows) >= output_buffer_rows:
                            _write_summary(summary_rows)
                            summary_rows = []

                        arrival_tracker.update(count_n)

                if event_rows:
                    _write_events(event_rows)
                    event_rows = []
                if summary_rows:
                    _write_summary(summary_rows)
                    summary_rows = []

                if events_writer is not None:
                    events_writer.close()
                elif events_chunks:
                    events_all = pl.concat(events_chunks)
                    events_all.write_parquet(events_tmp_path, compression="zstd")

                if summary_writer is not None:
                    summary_writer.close()
                elif summary_chunks:
                    summary_all = pl.concat(summary_chunks)
                    summary_all.write_parquet(summary_tmp_path, compression="zstd")

                if scenario_rows_written == 0:
                    _abort(
                        "5B.S4.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "arrival_events_empty",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                _atomic_publish_dir(events_tmp_dir, events_root, logger, f"arrival_events_5B scenario_id={scenario_id}")
                _atomic_publish_file(
                    summary_tmp_path, summary_path, logger, f"s4_arrival_summary_5B scenario_id={scenario_id}"
                )
                event_paths.append(events_root)
                summary_paths.append(summary_path)

                if trace_handle is not None:
                    for label, stats in rng_stats.items():
                        last_counters = stats.get("last")
                        if not last_counters:
                            continue
                        counter_hi, counter_lo, next_hi, next_lo = last_counters
                        trace_row = {
                            "ts_utc": utc_now_rfc3339_micro(),
                            "run_id": str(run_id),
                            "seed": int(seed),
                            "module": "5B.S4",
                            "substream_label": label,
                            "rng_counter_before_lo": int(counter_lo),
                            "rng_counter_before_hi": int(counter_hi),
                            "rng_counter_after_lo": int(next_lo),
                            "rng_counter_after_hi": int(next_hi),
                            "draws_total": int(stats.get("draws") or 0),
                            "blocks_total": int(stats.get("blocks") or 0),
                            "events_total": int(stats.get("events") or 0),
                        }
                        trace_handle.write(_json_dumps(trace_row))
                        trace_handle.write("\n")

                _flush_event_buffers()

                scenario_details[str(scenario_id)] = {
                    "arrival_rows": int(scenario_rows_written),
                    "arrival_total": int(scenario_arrivals),
                    "arrival_physical": int(scenario_physical),
                    "arrival_virtual": int(scenario_virtual),
                    "ordering_violations": int(ordering_violations),
                    "duration_s": int(time.monotonic() - scenario_start),
                }
                ordering_violations_total += ordering_violations
                scenario_count_succeeded += 1

                logger.info(
                    "S4: scenario=%s completed arrivals=%d physical=%d virtual=%d ordering_violations=%d",
                    scenario_id,
                    scenario_arrivals,
                    scenario_physical,
                    scenario_virtual,
                    ordering_violations,
                )
        finally:
            blob_view.close()
            for handle in event_handles.values():
                if handle is not None:
                    handle.close()
            if trace_handle is not None:
                trace_handle.close()

        if trace_tmp_path is not None:
            _atomic_publish_file(trace_tmp_path, trace_path, logger, "rng_trace_log")

        for label, tmp_dir in event_tmp_dirs.items():
            _atomic_publish_dir(tmp_dir, event_roots[label], logger, f"rng_event_{label}")

        status = "PASS"
    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        status = "FAIL"
        error_code = error_code or "5B.S4.IO_WRITE_FAILED"
        error_class = "F4"
        detail = str(exc) or type(exc).__name__
        error_context = {"detail": detail, "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # pragma: no cover
        status = "FAIL"
        error_code = error_code or "5B.S4.IO_WRITE_FAILED"
        error_class = "F4"
        detail = str(exc) or type(exc).__name__
        error_context = {"detail": detail, "phase": current_phase}
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
                    "state_id": "5B.S4",
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
                    "total_arrivals": total_arrivals,
                    "total_physical": total_physical,
                    "total_virtual": total_virtual,
                    "ordering_violations": ordering_violations_total,
                    "details": scenario_details,
                }
                if error_context:
                    run_report_payload["error_context"] = error_context
                    run_report_payload["first_failure_phase"] = first_failure_phase

                _append_jsonl(run_report_path, run_report_payload)
                logger.info("S4: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S4: failed to write segment_state_runs: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            error_class or "F4",
            error_code or "5B.S4.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if run_report_path is None or run_paths is None:
        raise EngineFailure(
            "F4",
            "5B.S4.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing run_report_path or run_paths"},
        )

    return S4Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        event_paths=event_paths,
        summary_paths=summary_paths,
        run_report_path=run_report_path,
    )
