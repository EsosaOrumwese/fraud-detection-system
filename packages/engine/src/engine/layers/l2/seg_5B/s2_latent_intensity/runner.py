"""Segment 5B S2 latent intensity fields."""

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


MODULE_NAME = "5B.s2_latent_intensity"
SEGMENT = "5B"
STATE = "S2"
BATCH_SIZE = 200_000
UINT64_MASK = 0xFFFFFFFFFFFFFFFF
UINT64_MAX = UINT64_MASK
TWO_NEG_64 = float.fromhex("0x1.0000000000000p-64")
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
DEFAULT_PROGRESS_INTERVAL_SECONDS = 10.0


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    realised_paths: list[Path]
    latent_paths: list[Path]
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
    logger = get_logger("engine.layers.l2.seg_5B.s2_latent_intensity.runner")
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
        "S2: %s schema validated (mode=fast sample_rows=%s total_rows=%s)",
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
                        "5B.S2.RNG_ACCOUNTING_MISMATCH",
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
            "5B.S2.RNG_ACCOUNTING_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": "no_event_jsonl_files", "path": str(event_root)},
        )
    rows_written = 0
    for event in _iter_jsonl_rows(event_paths, "rng_event_arrival_lgcp_gaussian"):
        trace_row = trace_acc.append_event(event)
        trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
        trace_handle.write("\n")
        rows_written += 1
    logger.info("S2: appended trace rows from existing events rows=%d", rows_written)
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
                    logger.info("S2: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S2: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S2: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash = _hash_partition(tmp_root)
        final_hash = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "5B.S2.IO_WRITE_CONFLICT",
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
        logger.info("S2: %s partition already exists and is identical; skipping publish.", label)
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
                "5B.S2.IO_WRITE_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S2: %s file already exists and is identical; skipping publish.", label)
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
        logger.info("S2: output already exists and is identical; skipping publish (%s).", label)
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
    logger.info("S2: published %s (%s).", label, final_path)
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


def _draw_philox_u64(
    key: int,
    counter_hi: int,
    counter_lo: int,
    draws: int,
    manifest_fingerprint: str,
) -> tuple[list[int], int, int, int]:
    blocks = int((draws + 1) // 2)
    values: list[int] = [0] * draws
    cur_hi, cur_lo = counter_hi, counter_lo
    out_idx = 0
    for _ in range(blocks):
        out0, out1 = philox2x64_10(cur_hi, cur_lo, key)
        values[out_idx] = out0
        out_idx += 1
        if out_idx < draws:
            values[out_idx] = out1
            out_idx += 1
        next_lo = (cur_lo + 1) & UINT64_MASK
        next_hi = cur_hi + (1 if next_lo == 0 else 0)
        if _counter_wrapped(cur_hi, cur_lo, next_hi, next_lo):
            _abort(
                "5B.S2.RNG_ACCOUNTING_MISMATCH",
                "V-12",
                "rng_counter_wrap",
                {"detail": "counter wrapped during draws"},
                manifest_fingerprint,
            )
        cur_hi, cur_lo = next_hi, next_lo
    return values, blocks, cur_hi, cur_lo


def _box_muller(u1: float, u2: float) -> float:
    r = math.sqrt(-2.0 * math.log(u1))
    theta = 2.0 * math.pi * u2
    return r * math.cos(theta)


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    lower, upper = bounds
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


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


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l2.seg_5B.s2_latent_intensity.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)
    output_validate_full = _env_flag("ENGINE_5B_S2_VALIDATE_FULL")
    output_sample_rows_env = os.environ.get("ENGINE_5B_S2_VALIDATE_SAMPLE_ROWS", "5000")
    try:
        output_sample_rows = max(int(output_sample_rows_env), 0)
    except ValueError:
        output_sample_rows = 5000
    output_validation_mode = "full" if output_validate_full else "fast_sampled"
    enable_rng_events = _env_flag("ENGINE_5B_S2_RNG_EVENTS")
    progress_interval_seconds = _env_progress_interval_seconds("ENGINE_5B_S2_PROGRESS_INTERVAL_SEC")
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
    total_latent_values = 0
    total_groups = 0
    total_buckets = 0
    rng_events_total = 0
    rng_draws_total = 0
    rng_blocks_total = 0

    lambda_min: Optional[float] = None
    lambda_max: Optional[float] = None
    factor_clip_min = 0
    factor_clip_max = 0
    lambda_max_clipped = 0

    realised_paths: list[Path] = []
    latent_paths: list[Path] = []

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
        logger.info("S2: run log initialized at %s", run_log_path)

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
            "S2: objective=sample latent intensity fields and realise lambda (gate S0+S1+5A+configs; output s2_realised_intensity_5B + rng logs)"
        )
        logger.info(
            "S2: rng_event logging=%s (set ENGINE_5B_S2_RNG_EVENTS=1 to enable)",
            "on" if enable_rng_events else "off",
        )
        logger.info("S2: progress cadence interval=%.2fs", progress_interval_seconds)

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
                "5B.S2.S0_GATE_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "5B.S2.S0_GATE_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_set_payload = receipt_payload.get("scenario_set")
        if not isinstance(scenario_set_payload, list) or not scenario_set_payload:
            _abort(
                "5B.S2.S0_GATE_INVALID",
                "V-03",
                "scenario_set_missing",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )
        scenario_set = sorted({str(item) for item in scenario_set_payload if item})
        if not scenario_set:
            _abort(
                "5B.S2.S0_GATE_INVALID",
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
                    "5B.S2.UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        spec_version = str(receipt_payload.get("spec_version") or "")
        if not spec_version:
            _abort(
                "5B.S2.S0_GATE_INVALID",
                "V-03",
                "spec_version_missing",
                {"receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )

        if not isinstance(sealed_inputs, list):
            _abort(
                "5B.S2.S0_GATE_INVALID",
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
                    "5B.S2.S0_GATE_INVALID",
                    "V-03",
                    "sealed_inputs_duplicate_key",
                    {"owner_segment": key[0], "artifact_id": key[1]},
                    manifest_fingerprint,
                )
            seen_keys.add(key)
            sealed_by_id[str(row.get("artifact_id") or "")] = row
        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if sealed_digest != receipt_payload.get("sealed_inputs_digest"):
            _abort(
                "5B.S2.S0_GATE_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {
                    "expected": receipt_payload.get("sealed_inputs_digest"),
                    "actual": sealed_digest,
                },
                manifest_fingerprint,
            )

        _resolve_sealed_row(
            sealed_by_id,
            "arrival_lgcp_config_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S2.LGCP_CONFIG_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_rng_policy_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S2.RNG_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_scenario_local_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S2.LAMBDA_SOURCE_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_scenario_utc_5A",
            manifest_fingerprint,
            {"ROW_LEVEL", "METADATA_ONLY"},
            False,
            "5B.S2.LAMBDA_SOURCE_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_overlay_factors_5A",
            manifest_fingerprint,
            {"ROW_LEVEL", "METADATA_ONLY"},
            False,
            "5B.S2.LAMBDA_SOURCE_MISSING",
        )

        current_phase = "config_load"
        lgcp_entry = find_dataset_entry(dictionary_5b, "arrival_lgcp_config_5B").entry
        rng_entry = find_dataset_entry(dictionary_5b, "arrival_rng_policy_5B").entry
        lgcp_path = _resolve_dataset_path(lgcp_entry, run_paths, config.external_roots, tokens)
        rng_path = _resolve_dataset_path(rng_entry, run_paths, config.external_roots, tokens)
        lgcp_config = _load_yaml(lgcp_path)
        rng_policy = _load_yaml(rng_path)

        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_lgcp_config_5B", lgcp_config)
        _validate_payload(schema_5b, schema_layer1, schema_layer2, "config/arrival_rng_policy_5B", rng_policy)

        if lgcp_config.get("policy_id") != "arrival_lgcp_config_5B":
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_lgcp_config_5B", "actual": lgcp_config.get("policy_id")},
                manifest_fingerprint,
            )
        if rng_policy.get("policy_id") != "arrival_rng_policy_5B":
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "policy_id_mismatch",
                {"expected": "arrival_rng_policy_5B", "actual": rng_policy.get("policy_id")},
                manifest_fingerprint,
            )

        latent_model_id = str(lgcp_config.get("latent_model_id") or "")
        if latent_model_id not in {"none", "log_gaussian_ou_v1", "log_gaussian_iid_v1"}:
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "latent_model_id_invalid",
                {"latent_model_id": latent_model_id},
                manifest_fingerprint,
            )

        if str(lgcp_config.get("normal_method") or "") != "box_muller_u2":
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "normal_method_invalid",
                {"normal_method": lgcp_config.get("normal_method")},
                manifest_fingerprint,
            )
        if str(lgcp_config.get("latent_dims_mode") or "") != "horizon_buckets_H":
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "latent_dims_mode_invalid",
                {"latent_dims_mode": lgcp_config.get("latent_dims_mode")},
                manifest_fingerprint,
            )

        kernel = lgcp_config.get("kernel") or {}
        kernel_kind = str(kernel.get("kind") or "")
        if latent_model_id == "log_gaussian_ou_v1" and kernel_kind != "ou_ar1_buckets_v1":
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "kernel_kind_invalid",
                {"latent_model_id": latent_model_id, "kernel_kind": kernel_kind},
                manifest_fingerprint,
            )
        if latent_model_id == "log_gaussian_iid_v1" and kernel_kind != "iid_v1":
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "kernel_kind_invalid",
                {"latent_model_id": latent_model_id, "kernel_kind": kernel_kind},
                manifest_fingerprint,
            )

        hyperparam_law = lgcp_config.get("hyperparam_law") or {}
        sigma_law = hyperparam_law.get("sigma") or {}
        length_law = hyperparam_law.get("length_scale_buckets") or {}
        sigma_bounds = tuple(sigma_law.get("sigma_bounds") or [])
        length_bounds = tuple(length_law.get("length_scale_bounds") or [])
        kernel_bounds = tuple(kernel.get("length_scale_buckets_bounds") or [])
        if len(sigma_bounds) != 2 or len(length_bounds) != 2 or len(kernel_bounds) != 2:
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "bounds_invalid",
                {"sigma_bounds": sigma_bounds, "length_bounds": length_bounds, "kernel_bounds": kernel_bounds},
                manifest_fingerprint,
            )

        clip_cfg = lgcp_config.get("clipping") or {}
        min_factor = float(clip_cfg.get("min_factor") or 0.0)
        max_factor = float(clip_cfg.get("max_factor") or 0.0)
        lambda_max_enabled = bool(clip_cfg.get("lambda_max_enabled"))
        lambda_max_value = float(clip_cfg.get("lambda_max") or 0.0)
        if min_factor <= 0.0 or max_factor <= 0.0 or max_factor < min_factor:
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "clipping_invalid",
                {"min_factor": min_factor, "max_factor": max_factor},
                manifest_fingerprint,
            )

        transform_cfg = lgcp_config.get("latent_transform") or {}
        if str(transform_cfg.get("kind") or "") != "exp_mean_one_v1":
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "latent_transform_invalid",
                {"latent_transform": transform_cfg},
                manifest_fingerprint,
            )

        realism = lgcp_config.get("realism_floors") or {}
        require_sigma_distinct = int(realism.get("require_sigma_distinct_values_min") or 0)
        require_stress_fraction = float(realism.get("require_stress_sigma_ge_fraction") or 0.0)
        baseline_L_bounds = tuple(realism.get("require_baseline_median_L_bounds") or [])
        if len(baseline_L_bounds) != 2:
            baseline_L_bounds = (0.0, float("inf"))

        if max_factor / min_factor < 10.0 or max_factor < 3.0 or min_factor > 0.5:
            _abort(
                "5B.S2.LGCP_CONFIG_INVALID",
                "V-04",
                "clipping_realism_floor_failed",
                {"min_factor": min_factor, "max_factor": max_factor},
                manifest_fingerprint,
            )

        rng_engine = str(rng_policy.get("rng_engine") or "")
        uniform_law = str(rng_policy.get("uniform_law") or "")
        block_outputs = int(rng_policy.get("block_outputs_u64") or 0)
        wrap_policy = str(rng_policy.get("wrap_policy") or "")
        if rng_engine != "philox2x64-10" or uniform_law != "open_interval_u64" or block_outputs != 2:
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "rng_engine_invalid",
                {"rng_engine": rng_engine, "uniform_law": uniform_law, "block_outputs_u64": block_outputs},
                manifest_fingerprint,
            )
        if wrap_policy != "abort_on_wrap":
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "wrap_policy_invalid",
                {"wrap_policy": wrap_policy},
                manifest_fingerprint,
            )

        encoding = rng_policy.get("encoding") or {}
        if str(encoding.get("uer") or "") != "u32be_len_prefix":
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "uer_encoding_invalid",
                {"uer": encoding.get("uer")},
                manifest_fingerprint,
            )
        if str(encoding.get("seed_encoding") or "") != "LE64":
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "seed_encoding_invalid",
                {"seed_encoding": encoding.get("seed_encoding")},
                manifest_fingerprint,
            )
        key_bytes = encoding.get("key_bytes") or []
        counter_hi_bytes = encoding.get("counter_hi_bytes") or []
        counter_lo_bytes = encoding.get("counter_lo_bytes") or []
        if key_bytes != [0, 8] or counter_hi_bytes != [8, 16] or counter_lo_bytes != [16, 24]:
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "byte_ranges_invalid",
                {
                    "key_bytes": key_bytes,
                    "counter_hi_bytes": counter_hi_bytes,
                    "counter_lo_bytes": counter_lo_bytes,
                },
                manifest_fingerprint,
            )

        derivation = rng_policy.get("derivation") or {}
        domain_sep = str(derivation.get("domain_sep") or "")
        required_inputs = set(derivation.get("required_inputs") or [])
        forbid_inputs = set(derivation.get("forbid_inputs") or [])
        if "run_id" in required_inputs or "run_id" not in forbid_inputs:
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "derivation_inputs_invalid",
                {"required_inputs": list(required_inputs), "forbid_inputs": list(forbid_inputs)},
                manifest_fingerprint,
            )
        if not domain_sep:
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "domain_sep_missing",
                {"derivation": derivation},
                manifest_fingerprint,
            )
        required_core = {"manifest_fingerprint", "parameter_hash", "seed", "scenario_id", "family_id", "domain_key"}
        if not required_core.issubset(required_inputs):
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "required_inputs_missing",
                {"required_inputs": list(required_inputs)},
                manifest_fingerprint,
            )

        family_id = None
        substream_label = None
        draws_law = None
        for family in rng_policy.get("families") or []:
            if family.get("module") == "5B.S2" and family.get("substream_label") == "latent_vector":
                family_id = str(family.get("family_id") or "")
                substream_label = str(family.get("substream_label") or "")
                draws_law = family.get("draws_u64_law") or {}
                break
        if not family_id or not substream_label:
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "family_missing",
                {"family_id": family_id, "substream_label": substream_label},
                manifest_fingerprint,
            )
        if draws_law.get("kind") != "box_muller_u2_vector":
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "draws_law_invalid",
                {"draws_u64_law": draws_law},
                manifest_fingerprint,
            )
        uniforms_per_normal = int(draws_law.get("uniforms_per_standard_normal") or 0)
        if uniforms_per_normal != 2:
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "uniforms_per_standard_normal_invalid",
                {"uniforms_per_standard_normal": uniforms_per_normal},
                manifest_fingerprint,
            )
        if draws_law.get("latent_dims") != "horizon_buckets_H":
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "latent_dims_invalid",
                {"latent_dims": draws_law.get("latent_dims")},
                manifest_fingerprint,
            )

        if not _HEX64_PATTERN.match(str(manifest_fingerprint)):
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "manifest_fingerprint_invalid",
                {"manifest_fingerprint": manifest_fingerprint},
                manifest_fingerprint,
            )
        if not _HEX64_PATTERN.match(str(parameter_hash)):
            _abort(
                "5B.S2.RNG_POLICY_INVALID",
                "V-04",
                "parameter_hash_invalid",
                {"parameter_hash": parameter_hash},
                manifest_fingerprint,
            )

        event_entry = find_dataset_entry(dictionary_5b, "rng_event_arrival_lgcp_gaussian").entry
        trace_entry = find_dataset_entry(dictionary_5b, "rng_trace_log").entry
        audit_entry = find_dataset_entry(dictionary_5b, "rng_audit_log").entry

        event_path = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens)
        event_root = _event_root_from_path(event_path)
        event_paths = _iter_jsonl_paths(event_root) if event_root.exists() else []
        event_enabled = enable_rng_events and not event_paths
        if not enable_rng_events:
            logger.info("S2: rng_event logging disabled; emitting rng_trace_log only")
        elif event_paths:
            logger.info("S2: rng_event logs already exist; skipping new emission")

        trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
        trace_mode = "create"
        if trace_path.exists():
            trace_mode = (
                "skip"
                if _trace_has_substream(trace_path, "5B.S2", "latent_vector")
                else "append"
            )

        if latent_model_id == "none":
            if event_paths or trace_mode == "skip":
                _abort(
                    "5B.S2.RNG_ACCOUNTING_MISMATCH",
                    "V-05",
                    "rng_logs_present_for_none",
                    {"detail": "latent_model_id=none but rng logs exist"},
                    manifest_fingerprint,
                )
            event_enabled = False
            trace_mode = "skip"

        if event_enabled and trace_mode == "skip":
            _abort(
                "5B.S2.RNG_ACCOUNTING_MISMATCH",
                "V-05",
                "rng_trace_without_events",
                {"detail": "trace already has substream but events are missing"},
                manifest_fingerprint,
            )

        trace_handle = None
        trace_acc = None
        trace_tmp_path = None
        if trace_mode == "create":
            trace_tmp_path = run_paths.tmp_root / f"s2_trace_{uuid.uuid4().hex}.jsonl"
            trace_handle = trace_tmp_path.open("w", encoding="utf-8")
            trace_acc = RngTraceAccumulator()
        elif trace_mode == "append":
            trace_handle = trace_path.open("a", encoding="utf-8")
            trace_acc = RngTraceAccumulator()
        logger.info("S2: rng_trace_log mode=%s", trace_mode)

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

        event_validator = None
        if event_enabled:
            event_schema = _schema_from_pack(schema_layer1, "rng/events/arrival_lgcp_gaussian")
            event_schema = normalize_nullable_schema(event_schema)
            event_validator = Draft202012Validator(event_schema)

        event_tmp_dir = None
        event_handle = None
        if event_enabled and latent_model_id != "none":
            event_tmp_dir = run_paths.tmp_root / f"s2_rng_events_{uuid.uuid4().hex}"
            event_tmp_dir.mkdir(parents=True, exist_ok=True)
            event_tmp_path = _event_file_from_root(event_tmp_dir)
            event_handle = event_tmp_path.open("w", encoding="utf-8")

        realism_sigma_threshold = 0.35
        baseline_L_low, baseline_L_high = baseline_L_bounds

        for scenario_id in scenario_set:
            current_phase = f"scenario:{scenario_id}"
            logger.info(
                "S2: scenario=%s preparing S1 grid + grouping + lambda target inputs for latent draw",
                scenario_id,
            )

            time_grid_entry = find_dataset_entry(dictionary_5b, "s1_time_grid_5B").entry
            grouping_entry = find_dataset_entry(dictionary_5b, "s1_grouping_5B").entry
            scenario_local_entry = find_dataset_entry(dictionary_5b, "merchant_zone_scenario_local_5A").entry

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
            scenario_local_path = _resolve_dataset_path(
                scenario_local_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )

            if not time_grid_path.exists():
                _abort(
                    "5B.S2.S1_OUTPUT_MISSING",
                    "V-06",
                    "time_grid_missing",
                    {"scenario_id": scenario_id, "path": str(time_grid_path)},
                    manifest_fingerprint,
                )
            if not grouping_path.exists():
                _abort(
                    "5B.S2.S1_OUTPUT_MISSING",
                    "V-06",
                    "grouping_missing",
                    {"scenario_id": scenario_id, "path": str(grouping_path)},
                    manifest_fingerprint,
                )

            time_grid_df = pl.read_parquet(time_grid_path)
            if time_grid_df.is_empty():
                _abort(
                    "5B.S2.S1_OUTPUT_MISSING",
                    "V-06",
                    "time_grid_empty",
                    {"scenario_id": scenario_id, "path": str(time_grid_path)},
                    manifest_fingerprint,
                )
            bucket_indices = sorted({int(value) for value in time_grid_df.get_column("bucket_index").to_list()})
            bucket_count = len(bucket_indices)
            if not bucket_indices or bucket_indices[0] != 0 or bucket_indices[-1] != bucket_count - 1:
                _abort(
                    "5B.S2.BUCKET_SET_INCONSISTENT",
                    "V-06",
                    "bucket_index_non_contiguous",
                    {"scenario_id": scenario_id, "bucket_count": bucket_count},
                    manifest_fingerprint,
                )
            expected_indices = list(range(bucket_count))
            if bucket_indices != expected_indices:
                _abort(
                    "5B.S2.BUCKET_SET_INCONSISTENT",
                    "V-06",
                    "bucket_index_gap",
                    {"scenario_id": scenario_id, "expected_tail": expected_indices[-1]},
                    manifest_fingerprint,
                )
            scenario_is_baseline = bool(time_grid_df.get_column("scenario_is_baseline")[0])
            scenario_is_stress = bool(time_grid_df.get_column("scenario_is_stress")[0])
            if scenario_is_baseline == scenario_is_stress:
                _abort(
                    "5B.S2.DOMAIN_ALIGN_FAILED",
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
                    "5B.S2.S1_OUTPUT_MISSING",
                    "V-06",
                    "grouping_empty",
                    {"scenario_id": scenario_id, "path": str(grouping_path)},
                    manifest_fingerprint,
                )
            grouping_df = grouping_df.with_columns(
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("zone_representation").cast(pl.Utf8),
                pl.col("channel_group").cast(pl.Utf8),
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
                    "5B.S2.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "grouping_keys_not_unique",
                    {"scenario_id": scenario_id, "conflicts": conflicting.height},
                    manifest_fingerprint,
                )
            unique_rows = grouping_df.unique()
            if unique_rows.height != grouping_df.height:
                logger.warning(
                    "S2: grouping rows contain duplicates; deduplicating (scenario_id=%s rows=%d unique=%d)",
                    scenario_id,
                    grouping_df.height,
                    unique_rows.height,
                )
                grouping_df = unique_rows

            group_features = (
                grouping_df.group_by("group_id")
                .agg(
                    pl.col("scenario_band").n_unique().alias("scenario_band_n"),
                    pl.col("scenario_band").first().alias("scenario_band"),
                    pl.col("demand_class").n_unique().alias("demand_class_n"),
                    pl.col("demand_class").first().alias("demand_class"),
                    pl.col("channel_group").n_unique().alias("channel_group_n"),
                    pl.col("channel_group").first().alias("channel_group"),
                    pl.col("virtual_band").n_unique().alias("virtual_band_n"),
                    pl.col("virtual_band").first().alias("virtual_band"),
                    pl.col("zone_group_id").n_unique().alias("zone_group_id_n"),
                    pl.col("zone_group_id").first().alias("zone_group_id"),
                )
                .sort("group_id")
            )
            invalid_groups = group_features.filter(
                (pl.col("scenario_band_n") != 1)
                | (pl.col("demand_class_n") != 1)
                | (pl.col("channel_group_n") != 1)
                | (pl.col("virtual_band_n") != 1)
                | (pl.col("zone_group_id_n") != 1)
            )
            if invalid_groups.height:
                sample = invalid_groups.head(1).to_dicts()[0]
                _abort(
                    "5B.S2.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "group_feature_inconsistent",
                    {"scenario_id": scenario_id, "group_id": sample.get("group_id")},
                    manifest_fingerprint,
                )
            scenario_band_values = group_features.get_column("scenario_band").unique().to_list()
            if len(scenario_band_values) != 1 or scenario_band_values[0] != scenario_band:
                _abort(
                    "5B.S2.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "scenario_band_mismatch",
                    {"scenario_id": scenario_id, "expected": scenario_band, "observed": scenario_band_values},
                    manifest_fingerprint,
                )

            group_ids = group_features.get_column("group_id").to_list()
            group_count = len(group_ids)
            if group_count == 0:
                _abort(
                    "5B.S2.DOMAIN_ALIGN_FAILED",
                    "V-06",
                    "group_count_empty",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )
            total_groups += group_count

            sigma_by_band = sigma_law.get("base_by_scenario_band") or {}
            length_by_band = length_law.get("base_by_scenario_band") or {}
            sigma_class_mult = sigma_law.get("class_multipliers") or {}
            length_class_mult = length_law.get("class_multipliers") or {}
            sigma_channel_mult = sigma_law.get("channel_multipliers") or {}
            sigma_virtual_mult = sigma_law.get("virtual_multipliers") or {}

            if scenario_band not in sigma_by_band or scenario_band not in length_by_band:
                _abort(
                    "5B.S2.LGCP_CONFIG_INVALID",
                    "V-06",
                    "scenario_band_missing",
                    {"scenario_band": scenario_band},
                    manifest_fingerprint,
                )

            scenario_base_sigma = float(sigma_by_band.get(scenario_band))
            scenario_base_length = float(length_by_band.get(scenario_band))
            sigma_values: list[float] = []
            length_values: list[float] = []
            group_sigma: list[float] = []
            group_length: list[float] = []
            group_factor_lists: list[list[float]] = []
            group_latent_lists: list[list[float]] = []

            logger.info(
                "S2: computing group hyperparams (scenario_id=%s groups=%d buckets=%d) for latent model",
                scenario_id,
                group_count,
                bucket_count,
            )
            tracker = _ProgressTracker(
                group_count,
                logger,
                f"S2: group hyperparams (scenario_id={scenario_id})",
                min_interval_seconds=progress_interval_seconds,
            )
            for row in group_features.iter_rows(named=True):
                tracker.update(1)
                group_id = str(row.get("group_id"))
                demand_class = str(row.get("demand_class"))
                channel_group = str(row.get("channel_group"))
                virtual_band = str(row.get("virtual_band"))

                if demand_class not in sigma_class_mult or demand_class not in length_class_mult:
                    _abort(
                        "5B.S2.LGCP_CONFIG_INVALID",
                        "V-06",
                        "class_multiplier_missing",
                        {"scenario_id": scenario_id, "group_id": group_id, "demand_class": demand_class},
                        manifest_fingerprint,
                    )
                if channel_group not in sigma_channel_mult:
                    _abort(
                        "5B.S2.LGCP_CONFIG_INVALID",
                        "V-06",
                        "channel_multiplier_missing",
                        {"scenario_id": scenario_id, "group_id": group_id, "channel_group": channel_group},
                        manifest_fingerprint,
                    )
                if virtual_band not in sigma_virtual_mult:
                    _abort(
                        "5B.S2.LGCP_CONFIG_INVALID",
                        "V-06",
                        "virtual_multiplier_missing",
                        {"scenario_id": scenario_id, "group_id": group_id, "virtual_band": virtual_band},
                        manifest_fingerprint,
                    )

                sigma_raw = (
                    scenario_base_sigma
                    * float(sigma_class_mult[demand_class])
                    * float(sigma_channel_mult[channel_group])
                    * float(sigma_virtual_mult[virtual_band])
                )
                length_raw = scenario_base_length * float(length_class_mult[demand_class])
                sigma = _clamp(float(sigma_raw), (float(sigma_bounds[0]), float(sigma_bounds[1])))
                length_bound_low = max(float(length_bounds[0]), float(kernel_bounds[0]))
                length_bound_high = min(float(length_bounds[1]), float(kernel_bounds[1]))
                length_scale = _clamp(float(length_raw), (length_bound_low, length_bound_high))
                if not math.isfinite(sigma) or sigma <= 0.0:
                    _abort(
                        "5B.S2.KERNEL_CONSTRUCTION_FAILED",
                        "V-06",
                        "sigma_invalid",
                        {"scenario_id": scenario_id, "group_id": group_id, "sigma": sigma},
                        manifest_fingerprint,
                    )
                if latent_model_id == "log_gaussian_ou_v1" and (not math.isfinite(length_scale) or length_scale <= 0.0):
                    _abort(
                        "5B.S2.KERNEL_CONSTRUCTION_FAILED",
                        "V-06",
                        "length_scale_invalid",
                        {"scenario_id": scenario_id, "group_id": group_id, "length_scale": length_scale},
                        manifest_fingerprint,
                    )
                sigma_values.append(float(sigma))
                length_values.append(float(length_scale))
                group_sigma.append(float(sigma))
                group_length.append(float(length_scale))

            if scenario_band == "baseline":
                distinct_sigma = {round(value, 6) for value in sigma_values}
                if len(distinct_sigma) < require_sigma_distinct:
                    _abort(
                        "5B.S2.LGCP_CONFIG_INVALID",
                        "V-07",
                        "sigma_distinct_floor_failed",
                        {"scenario_id": scenario_id, "distinct_sigma": len(distinct_sigma)},
                        manifest_fingerprint,
                    )
                median_L = float(statistics.median(length_values)) if length_values else 0.0
                if not (baseline_L_low <= median_L <= baseline_L_high):
                    _abort(
                        "5B.S2.LGCP_CONFIG_INVALID",
                        "V-07",
                        "baseline_length_scale_floor_failed",
                        {"scenario_id": scenario_id, "median_L": median_L, "bounds": baseline_L_bounds},
                        manifest_fingerprint,
                    )
            if scenario_band == "stress":
                if sigma_values:
                    fraction = sum(1 for value in sigma_values if value >= realism_sigma_threshold) / len(
                        sigma_values
                    )
                else:
                    fraction = 0.0
                if fraction < require_stress_fraction:
                    _abort(
                        "5B.S2.LGCP_CONFIG_INVALID",
                        "V-07",
                        "stress_sigma_floor_failed",
                        {"scenario_id": scenario_id, "fraction": fraction, "threshold": require_stress_fraction},
                        manifest_fingerprint,
                    )

            if latent_model_id != "none":
                logger.info(
                    "S2: sampling latent vectors (scenario_id=%s groups=%d buckets=%d) using Philox",
                    scenario_id,
                    group_count,
                    bucket_count,
                )
                tracker = _ProgressTracker(
                    group_count,
                    logger,
                    f"S2: latent draw (scenario_id={scenario_id})",
                    min_interval_seconds=progress_interval_seconds,
                )
                for idx, group_id in enumerate(group_ids):
                    tracker.update(1)
                    sigma = group_sigma[idx]
                    length_scale = group_length[idx]
                    draws = uniforms_per_normal * bucket_count
                    domain_key = f"group_id={group_id}"
                    key, counter_hi, counter_lo = _derive_rng_seed(
                        domain_sep,
                        family_id,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        int(seed),
                        str(scenario_id),
                        domain_key,
                    )
                    values, blocks, after_hi, after_lo = _draw_philox_u64(
                        key, counter_hi, counter_lo, draws, manifest_fingerprint
                    )
                    if blocks != int((draws + 1) // 2):
                        _abort(
                            "5B.S2.RNG_ACCOUNTING_MISMATCH",
                            "V-12",
                            "blocks_mismatch",
                            {"scenario_id": scenario_id, "group_id": group_id, "blocks": blocks},
                            manifest_fingerprint,
                        )
                    expected_hi, expected_lo = add_u128(counter_hi, counter_lo, blocks)
                    if _counter_wrapped(counter_hi, counter_lo, expected_hi, expected_lo):
                        _abort(
                            "5B.S2.RNG_ACCOUNTING_MISMATCH",
                            "V-12",
                            "counter_wrap",
                            {"scenario_id": scenario_id, "group_id": group_id},
                            manifest_fingerprint,
                        )
                    if expected_hi != after_hi or expected_lo != after_lo:
                        _abort(
                            "5B.S2.RNG_ACCOUNTING_MISMATCH",
                            "V-12",
                            "counter_after_mismatch",
                            {"scenario_id": scenario_id, "group_id": group_id},
                            manifest_fingerprint,
                        )

                    u64_values = np.asarray(values, dtype=np.uint64)
                    uniforms = (u64_values.astype(np.float64) + 0.5) * TWO_NEG_64
                    u1 = uniforms[0::2]
                    u2 = uniforms[1::2]
                    normals = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * math.pi * u2)

                    if latent_model_id == "log_gaussian_iid_v1":
                        latent_arr = sigma * normals
                    else:
                        phi = math.exp(-1.0 / float(length_scale))
                        sigma_eps = sigma * math.sqrt(max(1.0 - phi * phi, 0.0))
                        latent_arr = np.empty(bucket_count, dtype=np.float64)
                        if normals.size:
                            latent_arr[0] = sigma * float(normals[0])
                        for t in range(1, bucket_count):
                            latent_arr[t] = phi * latent_arr[t - 1] + sigma_eps * float(normals[t])

                    if latent_arr.size != bucket_count:
                        _abort(
                            "5B.S2.LATENT_DOMAIN_INCOMPLETE",
                            "V-09",
                            "latent_length_mismatch",
                            {"scenario_id": scenario_id, "group_id": group_id},
                            manifest_fingerprint,
                        )
                    sigma2 = sigma * sigma
                    factor_arr = np.exp(latent_arr - 0.5 * sigma2)
                    clip_min_mask = factor_arr < min_factor
                    clip_max_mask = factor_arr > max_factor
                    clip_min = int(np.count_nonzero(clip_min_mask))
                    clip_max = int(np.count_nonzero(clip_max_mask))
                    if clip_min:
                        factor_arr[clip_min_mask] = min_factor
                    if clip_max:
                        factor_arr[clip_max_mask] = max_factor

                    factor_clip_min += clip_min
                    factor_clip_max += clip_max

                    group_factor_lists.append(factor_arr.tolist())
                    if bool(lgcp_config.get("diagnostics", {}).get("emit_latent_field_diagnostic")):
                        group_latent_lists.append(latent_arr.tolist())

                    rng_events_total += 1
                    rng_draws_total += draws
                    rng_blocks_total += blocks

                    if event_handle is not None or (trace_handle is not None and trace_acc is not None):
                        event_payload = {
                            "ts_utc": utc_now_rfc3339_micro(),
                            "run_id": str(run_id),
                            "seed": int(seed),
                            "parameter_hash": str(parameter_hash),
                            "manifest_fingerprint": str(manifest_fingerprint),
                            "module": "5B.S2",
                            "substream_label": "latent_vector",
                            "scenario_id": str(scenario_id),
                            "group_id": str(group_id),
                            "rng_counter_before_lo": int(counter_lo),
                            "rng_counter_before_hi": int(counter_hi),
                            "rng_counter_after_lo": int(expected_lo),
                            "rng_counter_after_hi": int(expected_hi),
                            "draws": str(draws),
                            "blocks": int(blocks),
                        }
                        if event_handle is not None:
                            if event_validator is not None:
                                errors = list(event_validator.iter_errors(event_payload))
                                if errors:
                                    _abort(
                                        "5B.S2.RNG_ACCOUNTING_MISMATCH",
                                        "V-12",
                                        "rng_event_schema_invalid",
                                        {"scenario_id": scenario_id, "group_id": group_id, "error": str(errors[0])},
                                        manifest_fingerprint,
                                    )
                            event_handle.write(json.dumps(event_payload, ensure_ascii=True, sort_keys=True))
                            event_handle.write("\n")
                        if trace_handle is not None and trace_acc is not None:
                            trace_row = trace_acc.append_event(event_payload)
                            trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
                            trace_handle.write("\n")
            else:
                group_factor_lists = [[1.0] * bucket_count for _ in group_ids]
                if bool(lgcp_config.get("diagnostics", {}).get("emit_latent_field_diagnostic")):
                    group_latent_lists = [[0.0] * bucket_count for _ in group_ids]

            factor_matrix: np.ndarray | None = None
            if latent_model_id != "none":
                factor_matrix = np.asarray(group_factor_lists, dtype=np.float64)
                if factor_matrix.shape != (group_count, bucket_count):
                    _abort(
                        "5B.S2.RNG_OUTPUT_INCOMPLETE",
                        "V-12",
                        "factor_matrix_shape_mismatch",
                        {
                            "scenario_id": scenario_id,
                            "expected": [group_count, bucket_count],
                            "actual": list(factor_matrix.shape),
                        },
                        manifest_fingerprint,
                    )
                group_factor_lists = []

            scenario_local_files = _list_parquet_files(scenario_local_path)
            rows_total = _count_parquet_rows(scenario_local_files)
            logger.info(
                "S2: processing lambda target rows from merchant_zone_scenario_local_5A (scenario_id=%s files=%d rows=%s)",
                scenario_id,
                len(scenario_local_files),
                rows_total,
            )
            tracker = _ProgressTracker(
                rows_total,
                logger,
                f"S2: realised intensity rows (scenario_id={scenario_id})",
                min_interval_seconds=progress_interval_seconds,
            )

            realised_entry = find_dataset_entry(dictionary_5b, "s2_realised_intensity_5B").entry
            realised_path = _resolve_dataset_path(
                realised_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            realised_tmp_dir = run_paths.tmp_root / f"s2_realised_{uuid.uuid4().hex}"
            realised_tmp_dir.mkdir(parents=True, exist_ok=True)
            realised_tmp_path = realised_tmp_dir / realised_path.name

            writer = None
            realised_chunks: list[pl.DataFrame] = []
            realised_rows = 0

            grouping_lookup = grouping_df.select(
                ["scenario_id", "merchant_id", "zone_representation", "channel_group", "group_id"]
            )
            if latent_model_id != "none":
                group_index_df = pl.DataFrame(
                    {
                        "group_id": group_ids,
                        "group_idx": list(range(group_count)),
                    }
                )
                grouping_lookup = grouping_lookup.join(group_index_df, on="group_id", how="left")
                if grouping_lookup.filter(pl.col("group_idx").is_null()).height:
                    _abort(
                        "5B.S2.REALISED_DOMAIN_INCOMPLETE",
                        "V-08",
                        "group_idx_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
            sample_remaining = output_sample_rows
            for batch in _iter_parquet_batches(
                scenario_local_files,
                ["scenario_id", "merchant_id", "tzid", "channel_group", "local_horizon_bucket_index", "lambda_local_scenario"],
            ):
                if _HAVE_PYARROW and hasattr(batch, "column"):
                    batch_df = pl.from_arrow(batch)
                else:
                    batch_df = batch
                if batch_df.is_empty():
                    continue
                tracker.update(batch_df.height)
                scenario_mismatch = bool(batch_df.select((pl.col("scenario_id") != scenario_id).any()).item())
                if scenario_mismatch:
                    _abort(
                        "5B.S2.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "scenario_id_mismatch",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
                if batch_df.get_column("channel_group").null_count() > 0:
                    _abort(
                        "5B.S2.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "channel_group_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                batch_df = batch_df.with_columns(
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("tzid").cast(pl.Utf8).alias("zone_representation"),
                    pl.col("channel_group").cast(pl.Utf8),
                    pl.col("local_horizon_bucket_index").cast(pl.Int64).alias("bucket_index"),
                    pl.col("lambda_local_scenario").cast(pl.Float64).alias("lambda_baseline"),
                )
                joined = batch_df.join(
                    grouping_lookup,
                    on=["scenario_id", "merchant_id", "zone_representation", "channel_group"],
                    how="left",
                )
                if joined.height != batch_df.height:
                    _abort(
                        "5B.S2.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "grouping_join_mismatch",
                        {"scenario_id": scenario_id, "rows": batch_df.height, "joined": joined.height},
                        manifest_fingerprint,
                    )
                if joined.filter(pl.col("group_id").is_null()).height:
                    _abort(
                        "5B.S2.REALISED_DOMAIN_INCOMPLETE",
                        "V-08",
                        "group_id_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                bucket_idx = np.asarray(joined.get_column("bucket_index").to_numpy(), dtype=np.int64)
                if bucket_idx.size and (
                    int(bucket_idx.min()) < 0 or int(bucket_idx.max()) >= bucket_count
                ):
                    _abort(
                        "5B.S2.BUCKET_SET_INCONSISTENT",
                        "V-08",
                        "bucket_index_out_of_range",
                        {"scenario_id": scenario_id, "bucket_count": bucket_count},
                        manifest_fingerprint,
                    )

                if latent_model_id != "none":
                    if joined.get_column("group_idx").null_count() > 0:
                        _abort(
                            "5B.S2.REALISED_DOMAIN_INCOMPLETE",
                            "V-08",
                            "group_idx_missing",
                            {"scenario_id": scenario_id},
                            manifest_fingerprint,
                        )
                    group_idx = np.asarray(joined.get_column("group_idx").to_numpy(), dtype=np.int64)
                    try:
                        lambda_values = factor_matrix[group_idx, bucket_idx]
                    except IndexError as exc:
                        _abort(
                            "5B.S2.REALISED_DOMAIN_INCOMPLETE",
                            "V-08",
                            "latent_factor_missing",
                            {"scenario_id": scenario_id, "error": str(exc)},
                            manifest_fingerprint,
                        )
                else:
                    lambda_values = np.ones(batch_df.height, dtype=np.float64)

                lambda_baseline = np.asarray(joined.get_column("lambda_baseline").to_numpy(), dtype=np.float64)
                if np.any(lambda_baseline < 0.0):
                    _abort(
                        "5B.S2.REALISED_NUMERIC_INVALID",
                        "V-08",
                        "lambda_baseline_negative",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                lambda_realised = lambda_baseline * np.asarray(lambda_values, dtype=np.float64)
                if lambda_max_enabled:
                    clip_mask = lambda_realised > lambda_max_value
                    lambda_max_clipped += int(np.count_nonzero(clip_mask))
                    if np.any(clip_mask):
                        lambda_realised = np.minimum(lambda_realised, lambda_max_value)

                if not np.isfinite(lambda_realised).all():
                    _abort(
                        "5B.S2.REALISED_NUMERIC_INVALID",
                        "V-08",
                        "lambda_realised_not_finite",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
                if np.any(lambda_realised < 0.0):
                    _abort(
                        "5B.S2.REALISED_NUMERIC_INVALID",
                        "V-08",
                        "lambda_realised_negative",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                output_df = joined.select(
                    pl.col("scenario_id").cast(pl.Utf8),
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("zone_representation").cast(pl.Utf8),
                    pl.col("channel_group").cast(pl.Utf8),
                    pl.col("bucket_index").cast(pl.Int64),
                ).with_columns(
                    pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
                    pl.lit(str(parameter_hash)).alias("parameter_hash"),
                    pl.lit(int(seed)).cast(pl.UInt64).alias("seed"),
                    pl.Series("lambda_baseline", lambda_baseline).cast(pl.Float64),
                    pl.Series("lambda_random_component", lambda_values).cast(pl.Float64),
                    pl.Series("lambda_realised", lambda_realised).cast(pl.Float64),
                    pl.lit(spec_version).cast(pl.Utf8).alias("s2_spec_version"),
                ).select(
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                    "scenario_id",
                    "merchant_id",
                    "zone_representation",
                    "channel_group",
                    "bucket_index",
                    "lambda_baseline",
                    "lambda_random_component",
                    "lambda_realised",
                    "s2_spec_version",
                )

                if output_validate_full:
                    _validate_array_rows(
                        output_df.iter_rows(named=True),
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        "model/s2_realised_intensity_5B",
                        logger=logger,
                        label=f"S2: validate realised (scenario_id={scenario_id})",
                        total_rows=output_df.height,
                    )
                elif sample_remaining > 0:
                    sample_chunk = output_df.head(min(sample_remaining, output_df.height))
                    _validate_dataframe_fast(
                        sample_chunk,
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        "model/s2_realised_intensity_5B",
                        logger=logger,
                        label=f"s2_realised_intensity_5B scenario_id={scenario_id}",
                        sample_rows=sample_chunk.height,
                    )
                    sample_remaining -= sample_chunk.height

                if output_df.height:
                    realised_rows += output_df.height
                    total_rows_written += output_df.height
                    batch_min = float(output_df.get_column("lambda_realised").min())
                    batch_max = float(output_df.get_column("lambda_realised").max())
                    if lambda_min is None or batch_min < lambda_min:
                        lambda_min = batch_min
                    if lambda_max is None or batch_max > lambda_max:
                        lambda_max = batch_max

                if _HAVE_PYARROW:
                    table = output_df.to_arrow()
                    if writer is None:
                        writer = pq.ParquetWriter(realised_tmp_path, table.schema, compression="zstd")
                    writer.write_table(table)
                else:
                    realised_chunks.append(output_df)

            if writer is not None:
                writer.close()
            elif realised_chunks:
                realised_all = pl.concat(realised_chunks)
                realised_all.write_parquet(realised_tmp_path, compression="zstd")

            if realised_rows == 0:
                _abort(
                    "5B.S2.REALISED_DOMAIN_INCOMPLETE",
                    "V-08",
                    "realised_empty",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )

            _publish_parquet_file_idempotent(
                realised_tmp_path,
                realised_path,
                logger,
                f"s2_realised_intensity_5B scenario_id={scenario_id}",
                "5B.S2.IO_WRITE_CONFLICT",
                "5B.S2.IO_WRITE_FAILED",
            )
            realised_paths.append(realised_path)

            latent_path = None
            if group_latent_lists:
                latent_entry = find_dataset_entry(dictionary_5b, "s2_latent_field_5B").entry
                latent_path = _resolve_dataset_path(
                    latent_entry,
                    run_paths,
                    config.external_roots,
                    {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
                )
                latent_tmp_dir = run_paths.tmp_root / f"s2_latent_{uuid.uuid4().hex}"
                latent_tmp_dir.mkdir(parents=True, exist_ok=True)
                latent_tmp_path = latent_tmp_dir / latent_path.name

                latent_df = pl.DataFrame(
                    {
                        "group_id": group_ids,
                        "latent_value": group_latent_lists,
                    }
                ).with_columns(pl.lit(bucket_indices).alias("bucket_index"))
                latent_df = latent_df.explode(["latent_value", "bucket_index"]).with_columns(
                    pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
                    pl.lit(str(parameter_hash)).alias("parameter_hash"),
                    pl.lit(int(seed)).cast(pl.UInt64).alias("seed"),
                    pl.lit(str(scenario_id)).alias("scenario_id"),
                    pl.lit(0.0).alias("latent_mean"),
                    pl.lit(0.0).alias("latent_std"),
                    pl.lit(spec_version).alias("s2_spec_version"),
                ).select(
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                    "scenario_id",
                    "group_id",
                    "bucket_index",
                    "latent_value",
                    "latent_mean",
                    "latent_std",
                    "s2_spec_version",
                )

                if output_validate_full:
                    _validate_array_rows(
                        latent_df.iter_rows(named=True),
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        "model/s2_latent_field_5B",
                        logger=logger,
                        label=f"S2: validate latent (scenario_id={scenario_id})",
                        total_rows=latent_df.height,
                    )
                else:
                    _validate_dataframe_fast(
                        latent_df,
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        "model/s2_latent_field_5B",
                        logger=logger,
                        label=f"s2_latent_field_5B scenario_id={scenario_id}",
                        sample_rows=min(output_sample_rows, latent_df.height),
                    )

                latent_df.write_parquet(latent_tmp_path, compression="zstd")
                _publish_parquet_file_idempotent(
                    latent_tmp_path,
                    latent_path,
                    logger,
                    f"s2_latent_field_5B scenario_id={scenario_id}",
                    "5B.S2.IO_WRITE_CONFLICT",
                    "5B.S2.IO_WRITE_FAILED",
                )
                latent_paths.append(latent_path)

            total_latent_values += group_count * bucket_count
            scenario_details[scenario_id] = {
                "bucket_count": bucket_count,
                "group_count": group_count,
                "rows_written": realised_rows,
                "latent_values_total": group_count * bucket_count,
            }
            scenario_count_succeeded += 1
            timer.info("S2: scenario %s completed (rows=%d)", scenario_id, realised_rows)

        if event_handle is not None:
            event_handle.close()
        if trace_handle is not None:
            trace_handle.close()

        if event_enabled and event_tmp_dir is not None:
            _atomic_publish_dir(event_tmp_dir, event_root, logger, "rng_event_arrival_lgcp_gaussian")
        if trace_mode == "create" and trace_tmp_path is not None:
            _atomic_publish_file(trace_tmp_path, trace_path, logger, "rng_trace_log")

        status = "PASS"
        timer.info("S2: completed latent intensity fields")
    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        status = "FAIL"
        error_code = error_code or "5B.S2.IO_WRITE_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        status = "FAIL"
        error_code = error_code or "5B.S2.IO_WRITE_FAILED"
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
                    "state_id": "5B.S2",
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
                    "total_group_count": total_groups,
                    "total_bucket_count": total_buckets,
                    "total_latent_values": total_latent_values,
                    "latent_rng_event_count": rng_events_total,
                    "latent_rng_total_draws": rng_draws_total,
                    "latent_rng_total_blocks": rng_blocks_total,
                    "lambda_realised_min": lambda_min,
                    "lambda_realised_max": lambda_max,
                    "factor_clip_min": factor_clip_min,
                    "factor_clip_max": factor_clip_max,
                    "lambda_max_clipped": lambda_max_clipped,
                    "details": scenario_details,
                }
                if error_context:
                    run_report_payload["error_context"] = error_context
                    run_report_payload["first_failure_phase"] = first_failure_phase

                _append_jsonl(run_report_path, run_report_payload)
                logger.info("S2: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S2: failed to write segment_state_runs: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "5B.S2.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if run_report_path is None or run_paths is None:
        raise EngineFailure(
            "F4",
            "5B.S2.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing run_report_path or run_paths"},
        )

    return S2Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        realised_paths=realised_paths,
        latent_paths=latent_paths,
        run_report_path=run_report_path,
    )
