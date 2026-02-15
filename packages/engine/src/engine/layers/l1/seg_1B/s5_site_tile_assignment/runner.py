"""S5 site-to-tile assignment runner for Segment 1B."""

from __future__ import annotations

import hashlib
import heapq
import json
import os
import shutil
import struct
import subprocess
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

import numpy as np
import polars as pl
import psutil
from jsonschema import Draft202012Validator

try:  # Optional fast row-group scanning.
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
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt
from engine.layers.l1.seg_1A.s0_foundations.rng import RngTraceAccumulator
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    add_u128,
    low64,
    merchant_u64,
    philox2x64_10,
    ser_u64,
    u01,
    uer_string,
)


MODULE_NAME = "1B.S5.assigner"
SUBSTREAM_LABEL = "site_tile_assign"
DATASET_ID = "rng_event_site_tile_assign"
TRACE_DATASET_ID = "rng_trace_log"
AUDIT_DATASET_ID = "rng_audit_log"

BATCH_SIZE = 200_000
CACHE_COUNTRIES_MAX = 8
EXTERNAL_SORT_THRESHOLD = 1_000_000
SORT_CHUNK_SIZE = 200_000
_RUN_RECORD = struct.Struct("<dQ")
_JSON_SEPARATORS = (",", ":")


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return int(default)
    try:
        value = int(str(raw).strip())
    except ValueError:
        return int(default)
    if value < minimum:
        return int(default)
    return int(value)


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return str(default)
    value = str(raw).strip()
    return value if value else str(default)


def _sha256_paths_and_sizes(root: Path, pattern: str = "*.parquet") -> str:
    files = sorted(
        [p for p in root.rglob(pattern) if p.is_file()],
        key=lambda p: p.relative_to(root).as_posix(),
    )
    h = hashlib.sha256()
    for p in files:
        rel = p.relative_to(root).as_posix().encode("utf-8")
        size = str(int(p.stat().st_size)).encode("ascii")
        h.update(rel)
        h.update(b"\n")
        h.update(size)
        h.update(b"\n")
    return h.hexdigest()


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    assignment_root: Path
    run_report_path: Path
    event_root: Path
    trace_path: Path
    audit_path: Path


@dataclass
class _TileIndexEntry:
    tile_ids_sorted: np.ndarray
    bytes_read: int

    def contains(self, tile_id: int) -> bool:
        idx = int(np.searchsorted(self.tile_ids_sorted, tile_id))
        if idx >= self.tile_ids_sorted.size:
            return False
        return int(self.tile_ids_sorted[idx]) == int(tile_id)


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
    def __init__(self, total: Optional[int], logger, label: str) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < 0.5 and not (
            self._total is not None and self._processed >= self._total
        ):
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        if self._total and self._total > 0:
            remaining = max(self._total - self._processed, 0)
            if rate > 0:
                eta_seconds = remaining / rate
                eta_hms = _format_hms(eta_seconds)
                eta_complete_utc = (
                    datetime.now(timezone.utc) + timedelta(seconds=eta_seconds)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                eta_seconds = float("inf")
                eta_hms = "unknown"
                eta_complete_utc = "unknown"
            self._logger.info(
                "%s %s/%s (elapsed=%.2fs, rate=%.2f/s, eta_seconds=%.2f, eta_hms=%s, eta_complete_utc=%s)",
                self._label,
                self._processed,
                self._total,
                elapsed,
                rate,
                eta_seconds,
                eta_hms,
                eta_complete_utc,
            )
        else:
            self._logger.info(
                "%s processed=%s (elapsed=%.2fs, rate=%.2f/s)",
                self._label,
                self._processed,
                elapsed,
                rate,
            )


def _format_hms(seconds: float) -> str:
    if not np.isfinite(seconds):
        return "unknown"
    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _close_parquet_reader(pfile) -> None:
    reader = getattr(pfile, "reader", None)
    if reader and hasattr(reader, "close"):
        reader.close()


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    return pick_latest_run_receipt(runs_root)


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
        return receipt_path, _load_json(receipt_path)
    receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


def _resolve_dataset_path(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> Path:
    path_template = entry.get("path")
    if not path_template:
        raise InputResolutionError("Dataset entry missing path.")
    resolved = path_template
    for key, value in tokens.items():
        resolved = resolved.replace(f"{{{key}}}", value)
    if resolved.startswith(("data/", "logs/", "reports/", "artefacts/")):
        return run_paths.run_root / resolved
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    return normalize_nullable_schema(schema)


def _item_schema(item: dict) -> dict:
    if "$ref" in item:
        return {"$ref": item["$ref"]}
    item_type = item.get("type")
    if item_type == "object":
        schema = {
            "type": "object",
            "properties": item.get("properties", {}),
        }
        if item.get("required"):
            schema["required"] = item["required"]
        if "additionalProperties" in item:
            schema["additionalProperties"] = item["additionalProperties"]
        return schema
    if item_type in ("string", "integer", "number", "boolean"):
        schema: dict = {"type": item_type}
        for key in (
            "pattern",
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "enum",
            "minLength",
            "maxLength",
        ):
            if key in item:
                schema[key] = item[key]
        return schema
    raise InputResolutionError(f"Unsupported array item type '{item_type}' for receipt schema.")


def _column_schema(column: dict) -> dict:
    if "$ref" in column:
        schema: dict = {"$ref": column["$ref"]}
    else:
        col_type = column.get("type")
        if col_type == "array":
            items = column.get("items") or {}
            schema = {"type": "array", "items": _item_schema(items)}
        elif col_type in ("string", "integer", "number", "boolean"):
            schema = {"type": col_type}
        else:
            raise InputResolutionError(f"Unsupported column type '{col_type}' for receipt schema.")
    if column.get("nullable"):
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _table_row_schema(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    columns = node.get("columns") or []
    properties = {}
    required = []
    for column in columns:
        name = column.get("name")
        if not name:
            raise InputResolutionError(f"Column missing name in {path}.")
        properties[name] = _column_schema(column)
        required.append(name)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _validate_payload(schema_pack: dict, path: str, payload: object) -> None:
    schema = _schema_from_pack(schema_pack, path)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        detail = errors[0].message if errors else "schema validation failed"
        raise SchemaValidationError(detail, [{"message": detail}])


def _emit_failure_event(
    logger,
    code: str,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
    detail: dict,
) -> None:
    payload = {
        "event": "S5_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S5_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _hash_partition(root: Path) -> tuple[str, int]:
    files = sorted(
        [path for path in root.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    h = hashlib.sha256()
    total_bytes = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                h.update(chunk)
    return h.hexdigest(), total_bytes


def _atomic_publish_dir(
    tmp_root: Path,
    final_root: Path,
    logger,
    label: str,
) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                "S5",
                MODULE_NAME,
                {"detail": "partition_exists_nonidentical", "dataset": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S5: %s partition already exists with identical bytes", label)
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
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                "S5",
                MODULE_NAME,
                {"path": str(final_path), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        tmp_path.unlink()
        logger.info("S5: %s already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted([path for path in root.rglob("*.parquet") if path.is_file()])
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _tile_index_files(tile_index_root: Path, country_iso: str) -> list[Path]:
    country_root = tile_index_root / f"country={country_iso}"
    if country_root.exists():
        return _list_parquet_files(country_root)
    return []


def _load_tile_index_country(
    tile_index_root: Path,
    country_iso: str,
) -> tuple[np.ndarray, int]:
    files = _tile_index_files(tile_index_root, country_iso)
    if not files:
        return np.array([], dtype=np.uint64), 0
    bytes_total = sum(path.stat().st_size for path in files)
    arrays = []
    if _HAVE_PYARROW:
        for path in files:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    table = pf.read_row_group(rg, columns=["tile_id"])
                    arrays.append(table.column("tile_id").to_numpy(zero_copy_only=False))
            finally:
                _close_parquet_reader(pf)
    else:
        for path in files:
            df = pl.read_parquet(path, columns=["tile_id"])
            arrays.append(df.get_column("tile_id").to_numpy())
    if not arrays:
        return np.array([], dtype=np.uint64), bytes_total
    return np.concatenate(arrays).astype(np.uint64, copy=False), bytes_total


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


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


def _derive_master_material(manifest_fingerprint: str, seed: int) -> bytes:
    payload = (
        uer_string("mlr:1B.master")
        + bytes.fromhex(manifest_fingerprint)
        + struct.pack("<Q", seed)
    )
    return hashlib.sha256(payload).digest()


def _derive_pair_substream(
    master_material: bytes,
    label: str,
    merchant_id: int,
    legal_country_iso: str,
) -> tuple[int, int, int]:
    msg = (
        uer_string("mlr:1B")
        + uer_string(label)
        + ser_u64(merchant_u64(merchant_id))
        + uer_string(legal_country_iso)
    )
    digest = hashlib.sha256(master_material + msg).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def _write_batch(
    batch_rows: list[tuple[int, str, int, int]],
    batch_index: int,
    output_root: Path,
    logger,
) -> None:
    if not batch_rows:
        return
    part_path = output_root / f"part-{batch_index:05d}.parquet"
    merchant_ids, country_isos, site_orders, tile_ids = zip(*batch_rows)
    data = {
        "merchant_id": np.array(merchant_ids, dtype=np.uint64),
        "legal_country_iso": np.array(country_isos, dtype=object),
        "site_order": np.array(site_orders, dtype=np.int64),
        "tile_id": np.array(tile_ids, dtype=np.uint64),
    }
    if _HAVE_PYARROW:
        table = pa.Table.from_pydict(data)
        pq.write_table(table, part_path, compression="zstd", row_group_size=200000)
    else:
        df = pl.DataFrame(data)
        df.write_parquet(part_path, compression="zstd", row_group_size=200000)
    logger.info("S5: wrote %d rows to %s", len(batch_rows), part_path)


def _iter_s4_batches(paths: Iterable[Path]) -> Iterator[object]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    yield pf.read_row_group(
                        rg,
                        columns=[
                            "merchant_id",
                            "legal_country_iso",
                            "tile_id",
                            "n_sites_tile",
                        ],
                    )
            finally:
                _close_parquet_reader(pf)
    else:
        for path in paths:
            yield pl.read_parquet(
                path,
                columns=["merchant_id", "legal_country_iso", "tile_id", "n_sites_tile"],
            )


def _event_file_from_root(root: Path) -> Path:
    if root.is_file():
        return root
    return root / "part-00000.jsonl"


def _ensure_rng_audit(
    audit_path: Path,
    audit_entry: dict,
    logger,
) -> None:
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
                    logger.info(
                        "S5: rng_audit_log already contains audit row for run_id=%s",
                        audit_entry["run_id"],
                    )
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S5: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S5: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _generate_rng_arrays(
    n_sites: int,
    key: int,
    counter_hi: int,
    counter_lo: int,
    tmp_dir: Optional[Path],
    logger,
    label: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if tmp_dir:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        u_values = np.memmap(tmp_dir / "u.bin", dtype="float64", mode="w+", shape=(n_sites,))
        before_hi = np.memmap(tmp_dir / "before_hi.bin", dtype="uint64", mode="w+", shape=(n_sites,))
        before_lo = np.memmap(tmp_dir / "before_lo.bin", dtype="uint64", mode="w+", shape=(n_sites,))
        after_hi = np.memmap(tmp_dir / "after_hi.bin", dtype="uint64", mode="w+", shape=(n_sites,))
        after_lo = np.memmap(tmp_dir / "after_lo.bin", dtype="uint64", mode="w+", shape=(n_sites,))
    else:
        u_values = np.empty(n_sites, dtype=np.float64)
        before_hi = np.empty(n_sites, dtype=np.uint64)
        before_lo = np.empty(n_sites, dtype=np.uint64)
        after_hi = np.empty(n_sites, dtype=np.uint64)
        after_lo = np.empty(n_sites, dtype=np.uint64)

    tracker = None
    progress_step = 1
    if n_sites >= 100000:
        tracker = _ProgressTracker(n_sites, logger, label)
        progress_step = max(1000, min(50_000, n_sites // 200))

    hi = int(counter_hi)
    lo = int(counter_lo)
    for idx in range(n_sites):
        before_hi[idx] = hi
        before_lo[idx] = lo
        x0, _x1 = philox2x64_10(hi, lo, key)
        u = u01(x0)
        if not (0.0 < u < 1.0):
            raise EngineFailure(
                "F4",
                "E507_RNG_EVENT_MISMATCH",
                "S5",
                MODULE_NAME,
                {"detail": "u_out_of_range", "u": u},
            )
        u_values[idx] = u
        hi, lo = add_u128(hi, lo, 1)
        after_hi[idx] = hi
        after_lo[idx] = lo
        if tracker:
            count = idx + 1
            if count % progress_step == 0:
                tracker.update(progress_step)
            elif count == n_sites:
                tracker.update(count % progress_step)
    return u_values, before_hi, before_lo, after_hi, after_lo


def _external_sort_runs(
    u_values: np.ndarray,
    tmp_dir: Path,
    logger,
) -> list[Path]:
    run_paths: list[Path] = []
    total = int(u_values.shape[0])
    for start in range(0, total, SORT_CHUNK_SIZE):
        end = min(start + SORT_CHUNK_SIZE, total)
        chunk_u = np.asarray(u_values[start:end])
        chunk_sites = np.arange(start + 1, end + 1, dtype=np.uint64)
        order = np.lexsort((chunk_sites, chunk_u))
        run_path = tmp_dir / f"run_{len(run_paths):05d}.bin"
        with run_path.open("wb") as handle:
            for idx in order:
                handle.write(_RUN_RECORD.pack(float(chunk_u[idx]), int(chunk_sites[idx])))
        run_paths.append(run_path)
    logger.info(
        "S5: external sort runs=%d chunk_size=%d",
        len(run_paths),
        SORT_CHUNK_SIZE,
    )
    return run_paths


def _merge_sorted_runs(run_paths: Iterable[Path]) -> Iterator[tuple[float, int]]:
    heap: list[tuple[float, int, object]] = []
    for path in run_paths:
        handle = path.open("rb")
        data = handle.read(_RUN_RECORD.size)
        if not data:
            handle.close()
            continue
        u, site_order = _RUN_RECORD.unpack(data)
        heapq.heappush(heap, (u, int(site_order), handle))

    while heap:
        u, site_order, handle = heapq.heappop(heap)
        yield u, site_order
        data = handle.read(_RUN_RECORD.size)
        if data:
            next_u, next_site = _RUN_RECORD.unpack(data)
            heapq.heappush(heap, (float(next_u), int(next_site), handle))
        else:
            handle.close()


def _tile_multiset_iter(tile_ids: np.ndarray, counts: np.ndarray) -> Iterator[int]:
    for tile_id, count in zip(tile_ids, counts, strict=True):
        for _ in range(int(count)):
            yield int(tile_id)


def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l1.seg_1B.s5_site_tile_assignment.l2.runner")
    timer = _StepTimer(logger)
    runs_root_norm = str(config.runs_root).replace("\\", "/")
    validate_index_mode_default = (
        "signature" if "runs/fix-data-engine" in runs_root_norm else "strict"
    )
    validate_index_mode = _env_str(
        "ENGINE_1B_S5_VALIDATE_TILE_INDEX_MODE",
        validate_index_mode_default,
    ).lower()
    if validate_index_mode not in ("strict", "signature", "off"):
        validate_index_mode = validate_index_mode_default
    cache_countries_max = _env_int(
        "ENGINE_1B_S5_CACHE_COUNTRIES_MAX",
        CACHE_COUNTRIES_MAX,
        minimum=0,
    )
    log_assign_every_pairs = _env_int(
        "ENGINE_1B_S5_LOG_ASSIGNMENT_EVERY_PAIRS",
        0 if "runs/fix-data-engine" in runs_root_norm else 1,
        minimum=0,
    )
    do_tile_index_membership_check = validate_index_mode == "strict"
    logger.info(
        "S5: validate_tile_index_mode=%s cache_countries_max=%d log_assignment_every_pairs=%d",
        validate_index_mode,
        cache_countries_max,
        log_assign_every_pairs,
    )

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = int(receipt.get("seed"))
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing parameter_hash or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s schemas=%s layer1=%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        schema_1b_path,
        schema_layer1_path,
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": str(parameter_hash),
        "manifest_fingerprint": str(manifest_fingerprint),
        "run_id": str(run_id),
    }
    external_roots = config.external_roots or (config.repo_root,)

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1B").entry
    s4_entry = find_dataset_entry(dictionary, "s4_alloc_plan").entry
    s4_report_entry = find_dataset_entry(dictionary, "s4_run_report").entry
    tile_index_entry = find_dataset_entry(dictionary, "tile_index").entry
    iso_entry = find_dataset_entry(dictionary, "iso3166_canonical_2024").entry
    assignment_entry = find_dataset_entry(dictionary, "s5_site_tile_assignment").entry
    run_report_entry = find_dataset_entry(dictionary, "s5_run_report").entry
    event_entry = find_dataset_entry(dictionary, DATASET_ID).entry
    trace_entry = find_dataset_entry(dictionary, TRACE_DATASET_ID).entry
    audit_entry = find_dataset_entry(dictionary, AUDIT_DATASET_ID).entry

    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, external_roots, tokens)
    if not receipt_path.exists():
        _emit_failure_event(
            logger,
            "E301_NO_PASS_FLAG",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            str(run_id),
            {"detail": "s0_gate_receipt_missing", "path": str(receipt_path)},
        )
        raise EngineFailure(
            "F4",
            "E301_NO_PASS_FLAG",
            "S5",
            MODULE_NAME,
            {"path": str(receipt_path)},
        )

    receipt_payload = _load_json(receipt_path)
    try:
        receipt_schema = _table_row_schema(schema_1b, "validation/s0_gate_receipt")
        validator = Draft202012Validator(receipt_schema)
        errors = list(validator.iter_errors(receipt_payload))
        if errors:
            raise SchemaValidationError(errors[0].message, [{"message": errors[0].message}])
    except SchemaValidationError as exc:
        _emit_failure_event(
            logger,
            "E_RECEIPT_SCHEMA_INVALID",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            str(run_id),
            {"detail": str(exc)},
        )
        raise EngineFailure(
            "F4",
            "E_RECEIPT_SCHEMA_INVALID",
            "S5",
            MODULE_NAME,
            {"detail": str(exc)},
        ) from exc

    if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
        _emit_failure_event(
            logger,
            "E508_TOKEN_MISMATCH",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            str(run_id),
            {"detail": "receipt_manifest_fingerprint_mismatch"},
        )
        raise EngineFailure(
            "F4",
            "E508_TOKEN_MISMATCH",
            "S5",
            MODULE_NAME,
            {"detail": "receipt_manifest_fingerprint_mismatch"},
        )

    sealed_inputs = receipt_payload.get("sealed_inputs") or []
    sealed_ids = {entry.get("id") for entry in sealed_inputs if isinstance(entry, dict)}
    required_sealed = {"tile_index", "iso3166_canonical_2024"}
    missing_sealed = sorted(required_sealed - sealed_ids)
    if missing_sealed:
        _emit_failure_event(
            logger,
            "E510_DISALLOWED_READ",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            str(run_id),
            {"detail": "sealed_inputs_missing", "missing": missing_sealed},
        )
        raise EngineFailure(
            "F4",
            "E510_DISALLOWED_READ",
            "S5",
            MODULE_NAME,
            {"detail": "sealed_inputs_missing", "missing": missing_sealed},
        )
    logger.info(
        "S5: gate receipt verified; sealed_inputs=%d (authorizes S4 allocation + tile assets)",
        len(sealed_inputs),
    )

    s4_root = _resolve_dataset_path(s4_entry, run_paths, external_roots, tokens)
    s4_run_report_path = _resolve_dataset_path(
        s4_report_entry,
        run_paths,
        external_roots,
        tokens,
    )
    tile_index_root = _resolve_dataset_path(
        tile_index_entry,
        run_paths,
        external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    iso_path = _resolve_dataset_path(iso_entry, run_paths, external_roots, {})
    assignment_root = _resolve_dataset_path(assignment_entry, run_paths, external_roots, tokens)
    run_report_path = _resolve_dataset_path(run_report_entry, run_paths, external_roots, tokens)
    event_root = _resolve_dataset_path(event_entry, run_paths, external_roots, tokens)
    trace_path = _resolve_dataset_path(trace_entry, run_paths, external_roots, tokens)
    audit_path = _resolve_dataset_path(audit_entry, run_paths, external_roots, tokens)

    if not s4_root.exists():
        _emit_failure_event(
            logger,
            "E501_NO_S4_ALLOC_PLAN",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            str(run_id),
            {"detail": "s4_alloc_plan_missing", "path": str(s4_root)},
        )
        raise EngineFailure(
            "F4",
            "E501_NO_S4_ALLOC_PLAN",
            "S5",
            MODULE_NAME,
            {"path": str(s4_root)},
        )

    logger.info("S5: assignment inputs resolved (s4_alloc_plan + tile_index)")

    tile_index_surface_sig = ""
    s4_tile_index_surface_sig = ""
    s4_tile_weights_surface_sig = ""
    tile_index_surface_verified = False
    if validate_index_mode == "signature":
        try:
            tile_index_surface_sig = _sha256_paths_and_sizes(tile_index_root)
        except Exception as exc:
            logger.info("S5: tile_index surface signature unavailable: %s", exc)
            tile_index_surface_sig = ""

        try:
            s4_payload = _load_json(s4_run_report_path)
            pat = s4_payload.get("pat") or {}
            s4_tile_index_surface_sig = str(pat.get("tile_index_surface_sig") or "")
            s4_tile_weights_surface_sig = str(pat.get("tile_weights_surface_sig") or "")
        except Exception as exc:
            logger.info(
                "S5: unable to load S4 run report for signature verification (path=%s): %s",
                s4_run_report_path,
                exc,
            )

        if s4_tile_index_surface_sig and tile_index_surface_sig:
            tile_index_surface_verified = s4_tile_index_surface_sig == tile_index_surface_sig

        # Fail-closed posture: only skip membership validation when the upstream
        # surface signatures match.
        do_tile_index_membership_check = not tile_index_surface_verified

        logger.info(
            "S5: tile_index signature verification verified=%s membership_check=%s tile_index_sig=%s s4_tile_index_sig=%s",
            tile_index_surface_verified,
            do_tile_index_membership_check,
            tile_index_surface_sig[:12],
            s4_tile_index_surface_sig[:12],
        )
    elif validate_index_mode == "off":
        do_tile_index_membership_check = False
        logger.info("S5: tile_index membership validation disabled (mode=off)")
    else:
        logger.info("S5: tile_index membership validation enabled (mode=strict)")

    iso_df = pl.read_parquet(iso_path, columns=["country_iso"])
    iso_set = set(iso_df.get_column("country_iso").to_list())
    logger.info("S5: ISO domain loaded (count=%d) for country validation", len(iso_set))

    s4_files = _list_parquet_files(s4_root)
    bytes_read_s4_total = sum(path.stat().st_size for path in s4_files)
    logger.info(
        "S5: s4_alloc_plan files=%d bytes=%d (tile requirements per merchant-country)",
        len(s4_files),
        bytes_read_s4_total,
    )
    logger.info("S5: read mode=%s", "pyarrow" if _HAVE_PYARROW else "polars")

    proc = psutil.Process()
    open_files_metric = "open_files"
    try:
        open_files_metric = "open_files"
        _ = len(proc.open_files())
    except Exception:
        if hasattr(proc, "num_handles"):
            open_files_metric = "handles"
        elif hasattr(proc, "num_fds"):
            open_files_metric = "fds"
    open_files_peak = 0

    tmp_root = run_paths.tmp_root / f"s5_site_tile_assignment_{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    output_tmp = tmp_root / "data"
    output_tmp.mkdir(parents=True, exist_ok=True)

    event_tmp = tmp_root / "rng_events"
    event_tmp.mkdir(parents=True, exist_ok=True)
    event_tmp_file = _event_file_from_root(event_tmp)
    trace_tmp = tmp_root / "rng_trace.jsonl"

    # Large buffered writes to reduce per-line syscall overhead.
    event_handle = event_tmp_file.open("w", encoding="utf-8", buffering=1024 * 1024)
    trace_handle = trace_tmp.open("w", encoding="utf-8", buffering=1024 * 1024)
    trace_acc = RngTraceAccumulator()

    audit_entry_payload = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": str(run_id),
        "seed": int(seed),
        "manifest_fingerprint": str(manifest_fingerprint),
        "parameter_hash": str(parameter_hash),
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "code_digest": None,
        "hostname": None,
        "platform": None,
        "notes": None,
    }
    audit_entry_payload = {key: value for key, value in audit_entry_payload.items() if value is not None}
    _validate_payload(schema_layer1, "#/rng/core/rng_audit_log/record", audit_entry_payload)

    master_material = _derive_master_material(str(manifest_fingerprint), int(seed))

    cache: OrderedDict[str, _TileIndexEntry] = OrderedDict()
    cache_hits = 0
    cache_misses = 0
    cache_evictions = 0
    bytes_read_index_total = 0

    batch_rows: list[tuple[int, str, int, int]] = []
    batch_index = 0
    rows_emitted = 0
    rng_events_emitted = 0
    pairs_total = 0
    merchants_total = 0
    last_merchant: Optional[int] = None
    last_key: Optional[tuple[int, str, int]] = None
    last_output_key: Optional[tuple[int, str, int]] = None

    wall_start = time.monotonic()
    cpu_start = time.process_time()

    progress_sites = _ProgressTracker(
        None,
        logger,
        "S5 assignment progress sites_processed (tile assignment per site)",
    )
    timer.info("S5: starting tile assignment loop (per site -> tile_id)")

    def _load_tile_index(country_iso: str) -> _TileIndexEntry:
        nonlocal cache_hits, cache_misses, cache_evictions, bytes_read_index_total
        if cache_countries_max <= 0:
            tile_ids, bytes_read = _load_tile_index_country(tile_index_root, country_iso)
            bytes_read_index_total += bytes_read
            return _TileIndexEntry(tile_ids_sorted=np.sort(tile_ids), bytes_read=bytes_read)
        if country_iso in cache:
            cache_hits += 1
            cache.move_to_end(country_iso)
            return cache[country_iso]
        cache_misses += 1
        tile_ids, bytes_read = _load_tile_index_country(tile_index_root, country_iso)
        bytes_read_index_total += bytes_read
        tile_ids_sorted = np.sort(tile_ids)
        entry = _TileIndexEntry(tile_ids_sorted=tile_ids_sorted, bytes_read=bytes_read)
        cache[country_iso] = entry
        if len(cache) > int(cache_countries_max):
            cache.popitem(last=False)
            cache_evictions += 1
        return entry

    def _flush_batch() -> None:
        nonlocal batch_index
        if not batch_rows:
            return
        _write_batch(batch_rows, batch_index, output_tmp, logger)
        batch_rows.clear()
        batch_index += 1

    def _process_pair(
        merchant_id: int,
        legal_country_iso: str,
        tile_ids: list[int],
        tile_counts: list[int],
    ) -> None:
        nonlocal rows_emitted, rng_events_emitted, pairs_total, merchants_total, last_merchant, last_output_key

        pairs_total += 1
        if last_merchant != merchant_id:
            merchants_total += 1
            last_merchant = merchant_id

        if not tile_ids:
            _emit_failure_event(
                logger,
                "E504_SUM_TO_N_MISMATCH",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                str(run_id),
                {"detail": "empty_tile_list", "merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )
            raise EngineFailure(
                "F4",
                "E504_SUM_TO_N_MISMATCH",
                "S5",
                MODULE_NAME,
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )

        tile_ids_arr = np.array(tile_ids, dtype=np.uint64)
        counts_arr = np.array(tile_counts, dtype=np.int64)
        n_sites_total = int(counts_arr.sum())
        if n_sites_total <= 0:
            _emit_failure_event(
                logger,
                "E504_SUM_TO_N_MISMATCH",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                str(run_id),
                {"detail": "nonpositive_sites", "merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )
            raise EngineFailure(
                "F4",
                "E504_SUM_TO_N_MISMATCH",
                "S5",
                MODULE_NAME,
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )

        tile_order = np.argsort(tile_ids_arr)
        tile_ids_arr = tile_ids_arr[tile_order]
        counts_arr = counts_arr[tile_order]

        if log_assign_every_pairs > 0 and (pairs_total % int(log_assign_every_pairs) == 0):
            logger.info(
                "S5: assigning merchant_id=%s country=%s sites_total=%d tiles_distinct=%d pairs_total=%d",
                merchant_id,
                legal_country_iso,
                n_sites_total,
                tile_ids_arr.size,
                pairs_total,
            )

        key, ctr_hi, ctr_lo = _derive_pair_substream(
            master_material, SUBSTREAM_LABEL, int(merchant_id), str(legal_country_iso)
        )

        use_external = n_sites_total > EXTERNAL_SORT_THRESHOLD
        pair_tmp: Optional[Path] = None
        if use_external:
            pair_tmp = tmp_root / f"pair_{merchant_id}_{legal_country_iso}_{uuid.uuid4().hex}"
        u_values: Optional[np.ndarray] = None
        before_hi: Optional[np.ndarray] = None
        before_lo: Optional[np.ndarray] = None
        after_hi: Optional[np.ndarray] = None
        after_lo: Optional[np.ndarray] = None
        assigned_tile_ids: Optional[np.ndarray] = None

        progress_step = 32
        if n_sites_total >= 100000:
            progress_step = max(1000, min(50_000, n_sites_total // 200))

        try:
            u_values, before_hi, before_lo, after_hi, after_lo = _generate_rng_arrays(
                n_sites_total,
                key,
                int(ctr_hi),
                int(ctr_lo),
                pair_tmp if use_external else None,
                logger,
                f"S5 RNG merchant={merchant_id} country={legal_country_iso}",
            )

            if use_external:
                assert pair_tmp is not None
                run_dir = pair_tmp / "runs"
                run_dir.mkdir(parents=True, exist_ok=True)
                run_paths = _external_sort_runs(u_values, run_dir, logger)
                assigned_tile_ids = np.memmap(
                    pair_tmp / "assigned_tile_id.bin",
                    dtype="uint64",
                    mode="w+",
                    shape=(n_sites_total,),
                )
                tile_iter = _tile_multiset_iter(tile_ids_arr, counts_arr)
                assigned_count = 0
                for _u, site_order in _merge_sorted_runs(run_paths):
                    try:
                        tile_id = next(tile_iter)
                    except StopIteration as exc:
                        raise EngineFailure(
                            "F4",
                            "E503_TILE_QUOTA_MISMATCH",
                            "S5",
                            MODULE_NAME,
                            {"detail": "tile_multiset_exhausted"},
                        ) from exc
                    assigned_tile_ids[int(site_order) - 1] = int(tile_id)
                    assigned_count += 1
                if assigned_count != n_sites_total:
                    raise EngineFailure(
                        "F4",
                        "E503_TILE_QUOTA_MISMATCH",
                        "S5",
                        MODULE_NAME,
                        {"detail": "assigned_count_mismatch", "expected": n_sites_total, "got": assigned_count},
                    )
                for path in run_paths:
                    path.unlink(missing_ok=True)
            else:
                site_orders = np.arange(1, n_sites_total + 1, dtype=np.int64)
                order = np.lexsort((site_orders, u_values))
                tile_multiset = np.repeat(tile_ids_arr, counts_arr)
                if tile_multiset.size != n_sites_total:
                    raise EngineFailure(
                        "F4",
                        "E503_TILE_QUOTA_MISMATCH",
                        "S5",
                        MODULE_NAME,
                        {"detail": "tile_multiset_size_mismatch", "expected": n_sites_total, "got": tile_multiset.size},
                    )
                assigned_tile_ids = np.empty(n_sites_total, dtype=np.uint64)
                assigned_tile_ids[site_orders[order] - 1] = tile_multiset

            dumps = json.dumps
            event_write = event_handle.write
            trace_write = trace_handle.write
            progress_accum = 0

            event_base = {
                "run_id": str(run_id),
                "seed": int(seed),
                "parameter_hash": str(parameter_hash),
                "manifest_fingerprint": str(manifest_fingerprint),
                "module": MODULE_NAME,
                "substream_label": SUBSTREAM_LABEL,
                "draws": "1",
                "blocks": 1,
                "merchant_id": int(merchant_id),
                "legal_country_iso": str(legal_country_iso),
            }

            for idx in range(n_sites_total):
                site_order = idx + 1
                tile_id = int(assigned_tile_ids[idx])
                output_key = (int(merchant_id), str(legal_country_iso), int(site_order))
                if last_output_key is not None:
                    if output_key == last_output_key:
                        _emit_failure_event(
                            logger,
                            "E502_PK_DUPLICATE_SITE",
                            seed,
                            manifest_fingerprint,
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "duplicate_output_key", "key": output_key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E502_PK_DUPLICATE_SITE",
                            "S5",
                            MODULE_NAME,
                            {"key": output_key},
                        )
                    if output_key < last_output_key:
                        _emit_failure_event(
                            logger,
                            "E509_UNSORTED",
                            seed,
                            manifest_fingerprint,
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "output_unsorted", "key": output_key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E509_UNSORTED",
                            "S5",
                            MODULE_NAME,
                            {"detail": "output_unsorted", "key": output_key},
                        )
                last_output_key = output_key
                event = dict(event_base)
                event["ts_utc"] = utc_now_rfc3339_micro()
                event["rng_counter_before_lo"] = int(before_lo[idx])
                event["rng_counter_before_hi"] = int(before_hi[idx])
                event["rng_counter_after_lo"] = int(after_lo[idx])
                event["rng_counter_after_hi"] = int(after_hi[idx])
                event["site_order"] = int(site_order)
                event["tile_id"] = int(tile_id)
                event["u"] = float(u_values[idx])
                trace_row = trace_acc.append_event(event)
                event_write(dumps(event, ensure_ascii=True, separators=_JSON_SEPARATORS))
                event_write("\n")
                trace_write(dumps(trace_row, ensure_ascii=True, separators=_JSON_SEPARATORS))
                trace_write("\n")
                rng_events_emitted += 1
                batch_rows.append((int(merchant_id), str(legal_country_iso), int(site_order), int(tile_id)))
                rows_emitted += 1
                progress_accum += 1
                if progress_accum >= progress_step:
                    progress_sites.update(progress_accum)
                    progress_accum = 0
                if len(batch_rows) >= BATCH_SIZE:
                    _flush_batch()
            if progress_accum:
                progress_sites.update(progress_accum)
        finally:
            if use_external and pair_tmp is not None:
                for array in (u_values, before_hi, before_lo, after_hi, after_lo, assigned_tile_ids):
                    if isinstance(array, np.memmap):
                        array.flush()
                shutil.rmtree(pair_tmp, ignore_errors=True)

    current_key: Optional[tuple[int, str]] = None
    current_tiles: list[int] = []
    current_counts: list[int] = []

    try:
        for batch in _iter_s4_batches(s4_files):
            if _HAVE_PYARROW:
                merchant_ids = batch.column("merchant_id").to_numpy(zero_copy_only=False)
                country_isos = batch.column("legal_country_iso").to_numpy(zero_copy_only=False)
                tile_ids = batch.column("tile_id").to_numpy(zero_copy_only=False)
                n_sites_tile = batch.column("n_sites_tile").to_numpy(zero_copy_only=False)
            else:
                merchant_ids = batch.get_column("merchant_id").to_numpy()
                country_isos = batch.get_column("legal_country_iso").to_numpy()
                tile_ids = batch.get_column("tile_id").to_numpy()
                n_sites_tile = batch.get_column("n_sites_tile").to_numpy()

            for idx in range(len(merchant_ids)):
                merchant_id = int(merchant_ids[idx])
                legal_country_iso = str(country_isos[idx])
                tile_id = int(tile_ids[idx])
                n_sites = int(n_sites_tile[idx])

                key_tuple = (merchant_id, legal_country_iso, tile_id)
                if last_key and key_tuple < last_key:
                    _emit_failure_event(
                        logger,
                        "E509_UNSORTED",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "s4_alloc_plan_unsorted", "key": key_tuple},
                    )
                    raise EngineFailure(
                        "F4",
                        "E509_UNSORTED",
                        "S5",
                        MODULE_NAME,
                        {"detail": "s4_alloc_plan_unsorted", "key": key_tuple},
                    )
                last_key = key_tuple

                if legal_country_iso not in iso_set:
                    _emit_failure_event(
                        logger,
                        "E302_FK_COUNTRY",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "country_not_in_iso", "legal_country_iso": legal_country_iso},
                    )
                    raise EngineFailure(
                        "F4",
                        "E302_FK_COUNTRY",
                        "S5",
                        MODULE_NAME,
                        {"legal_country_iso": legal_country_iso},
                    )

                if do_tile_index_membership_check:
                    tile_index_entry = _load_tile_index(legal_country_iso)
                    if tile_index_entry.tile_ids_sorted.size == 0:
                        _emit_failure_event(
                            logger,
                            "E505_TILE_NOT_IN_INDEX",
                            seed,
                            manifest_fingerprint,
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "tile_index_missing", "legal_country_iso": legal_country_iso},
                        )
                        raise EngineFailure(
                            "F4",
                            "E505_TILE_NOT_IN_INDEX",
                            "S5",
                            MODULE_NAME,
                            {"legal_country_iso": legal_country_iso},
                        )
                    if not tile_index_entry.contains(tile_id):
                        _emit_failure_event(
                            logger,
                            "E505_TILE_NOT_IN_INDEX",
                            seed,
                            manifest_fingerprint,
                            str(parameter_hash),
                            str(run_id),
                            {
                                "detail": "tile_id_not_in_index",
                                "legal_country_iso": legal_country_iso,
                                "tile_id": tile_id,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "E505_TILE_NOT_IN_INDEX",
                            "S5",
                            MODULE_NAME,
                            {"legal_country_iso": legal_country_iso, "tile_id": tile_id},
                        )

                if n_sites <= 0:
                    _emit_failure_event(
                        logger,
                        "E503_TILE_QUOTA_MISMATCH",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        str(run_id),
                        {
                            "detail": "nonpositive_tile_quota",
                            "legal_country_iso": legal_country_iso,
                            "tile_id": tile_id,
                            "n_sites_tile": n_sites,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "E503_TILE_QUOTA_MISMATCH",
                        "S5",
                        MODULE_NAME,
                        {"legal_country_iso": legal_country_iso, "tile_id": tile_id},
                    )

                if current_key is None:
                    current_key = (merchant_id, legal_country_iso)
                if (merchant_id, legal_country_iso) != current_key:
                    _process_pair(current_key[0], current_key[1], current_tiles, current_counts)
                    current_tiles = []
                    current_counts = []
                    current_key = (merchant_id, legal_country_iso)

                current_tiles.append(tile_id)
                current_counts.append(n_sites)

            if hasattr(proc, "open_files"):
                try:
                    open_files_peak = max(open_files_peak, len(proc.open_files()))
                except Exception:
                    pass
            if open_files_metric == "handles" and hasattr(proc, "num_handles"):
                open_files_peak = max(open_files_peak, int(proc.num_handles()))
            if open_files_metric == "fds" and hasattr(proc, "num_fds"):
                open_files_peak = max(open_files_peak, int(proc.num_fds()))

        if current_key is not None:
            _process_pair(current_key[0], current_key[1], current_tiles, current_counts)

        _flush_batch()
        if rng_events_emitted != rows_emitted:
            _emit_failure_event(
                logger,
                "E507_RNG_EVENT_MISMATCH",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                str(run_id),
                {"detail": "rng_event_budget_mismatch", "expected": rows_emitted, "actual": rng_events_emitted},
            )
            raise EngineFailure(
                "F4",
                "E507_RNG_EVENT_MISMATCH",
                "S5",
                MODULE_NAME,
                {"expected": rows_emitted, "actual": rng_events_emitted},
            )
    finally:
        if not event_handle.closed:
            event_handle.close()
        if not trace_handle.closed:
            trace_handle.close()

    timer.info(
        "S5: assignment loop completed (pairs_total=%d rows_emitted=%d rng_events=%d)",
        pairs_total,
        rows_emitted,
        rng_events_emitted,
    )
    logger.info(
        "S5: cache summary hits=%d misses=%d evictions=%d",
        cache_hits,
        cache_misses,
        cache_evictions,
    )

    determinism_hash, determinism_bytes = _hash_partition(output_tmp)
    determinism_receipt = {
        "partition_path": str(assignment_root),
        "sha256_hex": determinism_hash,
        "bytes_hashed": determinism_bytes,
    }

    _atomic_publish_dir(output_tmp, assignment_root, logger, "s5_site_tile_assignment")

    event_final_root = event_root
    event_tmp_dir = event_tmp
    _atomic_publish_dir(event_tmp_dir, event_final_root, logger, DATASET_ID)

    _atomic_publish_file(trace_tmp, trace_path, logger, TRACE_DATASET_ID)
    _ensure_rng_audit(audit_path, audit_entry_payload, logger)

    wall_total = time.monotonic() - wall_start
    cpu_total = time.process_time() - cpu_start

    run_report = {
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "rows_emitted": rows_emitted,
        "pairs_total": pairs_total,
        "rng_events_emitted": rng_events_emitted,
        "determinism_receipt": determinism_receipt,
        "pat": {
            "bytes_read_s4_total": bytes_read_s4_total,
            "bytes_read_index_total": bytes_read_index_total,
            "rows_emitted": rows_emitted,
            "pairs_total": pairs_total,
            "merchants_total": merchants_total,
            "wall_clock_seconds_total": wall_total,
            "cpu_seconds_total": cpu_total,
            "open_files_peak": open_files_peak,
            "open_files_metric": open_files_metric,
        },
    }
    _validate_payload(schema_1b, "#/control/s5_run_report", run_report)
    run_report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(run_report_path, run_report)
    timer.info("S5: run report written (assignment summary + determinism receipt)")

    shutil.rmtree(tmp_root, ignore_errors=True)

    return S5Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        assignment_root=assignment_root,
        run_report_path=run_report_path,
        event_root=event_final_root,
        trace_path=trace_path,
        audit_path=audit_path,
    )
