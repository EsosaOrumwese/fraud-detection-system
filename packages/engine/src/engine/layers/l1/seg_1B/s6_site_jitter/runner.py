"""S6 in-cell jitter runner for Segment 1B."""

from __future__ import annotations

import hashlib
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

import geopandas as gpd
import numpy as np
import polars as pl
import psutil
import shapely
import yaml
from jsonschema import Draft202012Validator
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.validation import explain_validity

try:  # Optional fast parquet scanning.
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pa = None
    ds = None
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


MODULE_NAME = "1B.S6.jitter"
SUBSTREAM_LABEL = "in_cell_jitter"
DATASET_ID = "rng_event_in_cell_jitter"
TRACE_DATASET_ID = "rng_trace_log"
AUDIT_DATASET_ID = "rng_audit_log"

DEFAULT_MAX_ATTEMPTS = 64
BATCH_SIZE = 200_000
CACHE_COUNTRIES_MAX = 6


@dataclass(frozen=True)
class S6Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    jitter_root: Path
    run_report_path: Path
    event_root: Path
    trace_path: Path
    audit_path: Path


@dataclass(frozen=True)
class _JitterComponentPolicy:
    lat_shape_exp: float
    lon_shape_exp: float
    max_abs_offset_fraction: float


@dataclass(frozen=True)
class _S6JitterPolicy:
    policy_version: str
    mode: str
    deterministic_seed_namespace: str
    max_attempts: int
    selection_blend: float
    weight_core: float
    weight_secondary: float
    weight_sparse: float
    core_component: _JitterComponentPolicy
    secondary_component: _JitterComponentPolicy
    sparse_component: _JitterComponentPolicy


@dataclass
class _TileIndexEntry:
    tile_ids_sorted: np.ndarray
    bytes_read: int

    def contains(self, tile_id: int) -> bool:
        idx = int(np.searchsorted(self.tile_ids_sorted, tile_id))
        if idx >= self.tile_ids_sorted.size:
            return False
        return int(self.tile_ids_sorted[idx]) == int(tile_id)


@dataclass
class _CountryGeometry:
    parts: list
    prepared: list


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


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InputResolutionError(f"YAML payload must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


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
                        "E614_JSONL_PARSE",
                        "S6",
                        MODULE_NAME,
                        {"detail": "jsonl_parse_failed", "label": label, "path": str(path), "line": line_no},
                    ) from exc


def _trace_has_substream(trace_path: Path, module: str, substream_label: str) -> bool:
    for row in _iter_jsonl_rows([trace_path], "rng_trace_log"):
        if row.get("module") == module and row.get("substream_label") == substream_label:
            return True
    return False


def _append_trace_from_events(
    event_root: Path, trace_handle, trace_acc: RngTraceAccumulator, logger
) -> int:
    event_paths = _iter_jsonl_paths(event_root)
    if not event_paths:
        raise EngineFailure(
            "F4",
            "E614_EVENT_LOG_EMPTY",
            "S6",
            MODULE_NAME,
            {"detail": "no_event_jsonl_files", "path": str(event_root)},
        )
    rows_written = 0
    for event in _iter_jsonl_rows(event_paths, "rng_event_in_cell_jitter"):
        trace_row = trace_acc.append_event(event)
        trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
        trace_handle.write("\n")
        rows_written += 1
    logger.info("S6: appended trace rows from existing events rows=%d", rows_written)
    return rows_written


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
        "event": "S6_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S6_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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
                "S6",
                MODULE_NAME,
                {"partition": str(final_root), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S6: %s partition already exists and is identical; skipping publish.", label)
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
                "S6",
                MODULE_NAME,
                {"path": str(final_path), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        tmp_path.unlink()
        logger.info("S6: %s already exists and is identical; skipping publish.", label)
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


def _count_parquet_rows(paths: Iterable[Path]) -> Optional[int]:
    if not _HAVE_PYARROW:
        return None
    total = 0
    for path in paths:
        pf = pq.ParquetFile(path)
        total += pf.metadata.num_rows
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


def _tile_index_files(tile_index_root: Path, country_iso: str) -> list[Path]:
    country_root = tile_index_root / f"country={country_iso}"
    if country_root.exists():
        return _list_parquet_files(country_root)
    return []


def _load_tile_index_country(tile_index_root: Path, country_iso: str) -> tuple[np.ndarray, int]:
    files = _tile_index_files(tile_index_root, country_iso)
    if not files:
        return np.array([], dtype=np.uint64), 0
    bytes_total = sum(path.stat().st_size for path in files)
    arrays = []
    if _HAVE_PYARROW:
        for path in files:
            pf = pq.ParquetFile(path)
            for rg in range(pf.num_row_groups):
                table = pf.read_row_group(rg, columns=["tile_id"])
                arrays.append(table.column("tile_id").to_numpy(zero_copy_only=False))
    else:
        for path in files:
            df = pl.read_parquet(path, columns=["tile_id"])
            arrays.append(df.get_column("tile_id").to_numpy())
    if not arrays:
        return np.array([], dtype=np.uint64), bytes_total
    return np.concatenate(arrays).astype(np.uint64, copy=False), bytes_total


def _tile_bounds_files(tile_bounds_root: Path, country_iso: str) -> list[Path]:
    country_root = tile_bounds_root / f"country={country_iso}"
    if country_root.exists():
        return _list_parquet_files(country_root)
    return []


def _load_tile_bounds_country(
    tile_bounds_root: Path,
    country_iso: str,
    tile_ids: np.ndarray,
) -> dict[int, tuple[float, float, float, float, float, float]]:
    files = _tile_bounds_files(tile_bounds_root, country_iso)
    if not files:
        return {}
    columns = [
        "tile_id",
        "min_lon_deg",
        "max_lon_deg",
        "min_lat_deg",
        "max_lat_deg",
        "centroid_lon_deg",
        "centroid_lat_deg",
    ]
    if _HAVE_PYARROW:
        table = None
        if ds is not None:
            dataset = ds.dataset(files, format="parquet")
            table = dataset.to_table(columns=columns, filter=ds.field("tile_id").isin(tile_ids.tolist()))
        else:
            dataset = pq.ParquetDataset(files)
            table = dataset.read(columns=columns)
            if table.num_rows:
                mask = np.isin(table.column("tile_id").to_numpy(zero_copy_only=False), tile_ids)
                table = table.filter(pa.array(mask))
        if table.num_rows == 0:
            return {}
        rows = table.to_pydict()
        tile_id_arr = rows["tile_id"]
        return {
            int(tile_id_arr[idx]): (
                float(rows["min_lon_deg"][idx]),
                float(rows["max_lon_deg"][idx]),
                float(rows["min_lat_deg"][idx]),
                float(rows["max_lat_deg"][idx]),
                float(rows["centroid_lon_deg"][idx]),
                float(rows["centroid_lat_deg"][idx]),
            )
            for idx in range(len(tile_id_arr))
        }
    df = pl.read_parquet(files, columns=columns)
    df = df.filter(pl.col("tile_id").is_in(tile_ids))
    if df.is_empty():
        return {}
    return {
        int(row[0]): (
            float(row[1]),
            float(row[2]),
            float(row[3]),
            float(row[4]),
            float(row[5]),
            float(row[6]),
        )
        for row in df.iter_rows()
    }


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


def _derive_site_substream(
    master_material: bytes,
    label: str,
    merchant_id: int,
    legal_country_iso: str,
    site_order: int,
) -> tuple[int, int, int]:
    msg = (
        uer_string("mlr:1B")
        + uer_string(label)
        + ser_u64(merchant_u64(merchant_id))
        + uer_string(legal_country_iso)
        + ser_u64(site_order)
    )
    digest = hashlib.sha256(master_material + msg).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


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
                        "S6: rng_audit_log already contains audit row for run_id=%s",
                        audit_entry["run_id"],
                    )
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S6: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S6: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _needs_antimeridian_shift(bounds: tuple[float, float, float, float]) -> bool:
    minx, _, maxx, _ = bounds
    return (maxx - minx) > 180.0


_ANTIMERIDIAN_EPS = 1e-9
_ANTIMERIDIAN_WEST = box(0.0, -90.0, 180.0 - _ANTIMERIDIAN_EPS, 90.0)
_ANTIMERIDIAN_EAST = box(180.0 - _ANTIMERIDIAN_EPS, -90.0, 360.0, 90.0)


def _shift_geometry_to_360(geom):
    def _shift(x, y, z=None):
        if isinstance(x, (list, tuple, np.ndarray)):
            x = np.asarray(x)
            return np.where(x < 0.0, x + 360.0, x), y
        return (x + 360.0 if x < 0.0 else x), y

    return shapely_transform(_shift, geom)


def _shift_geometry_from_360(geom):
    def _shift(x, y, z=None):
        if isinstance(x, (list, tuple, np.ndarray)):
            x = np.asarray(x)
            return x - 360.0, y
        return x - 360.0, y

    return shapely_transform(_shift, geom)


def _polygonal_only(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if getattr(geom, "geom_type", "") == "GeometryCollection":
        polys = [item for item in geom.geoms if isinstance(item, (Polygon, MultiPolygon)) and not item.is_empty]
        if not polys:
            return None
        return unary_union(polys)
    return None


def _split_antimeridian_geometries(geom) -> list:
    if not _needs_antimeridian_shift(geom.bounds):
        return [geom]
    geom_360 = _shift_geometry_to_360(geom)
    if not geom_360.is_valid:
        geom_360 = shapely.make_valid(geom_360)
        if geom_360 is None or geom_360.is_empty:
            return []
    west = _polygonal_only(geom_360.intersection(_ANTIMERIDIAN_WEST))
    east = _polygonal_only(geom_360.intersection(_ANTIMERIDIAN_EAST))
    parts: list = []
    if west is not None and not west.is_empty:
        parts.append(west)
    if east is not None and not east.is_empty:
        parts.append(_shift_geometry_from_360(east))
    return parts


def _normalize_lon(value: float) -> float:
    if value > 180.0:
        return value - 360.0
    if value < -180.0:
        return value + 360.0
    return value


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _shape_fraction(u: float, shape_exp: float, max_abs_offset_fraction: float) -> float:
    centered = (2.0 * _clip01(u)) - 1.0
    shaped = np.sign(centered) * (abs(centered) ** max(float(shape_exp), 1.0e-12))
    frac = 0.5 + 0.5 * shaped * _clip01(max_abs_offset_fraction)
    return _clip01(frac)


def _sample_lon_from_fraction(min_lon: float, max_lon: float, frac: float) -> float:
    span_lon = max_lon - min_lon
    if span_lon < 0.0:
        span_lon += 360.0
    lon = min_lon + _clip01(frac) * span_lon
    return _normalize_lon(lon)


def _sample_lat_from_fraction(min_lat: float, max_lat: float, frac: float) -> float:
    return float(min_lat + _clip01(frac) * (max_lat - min_lat))


def _select_component(u_lon: float, u_lat: float, policy: _S6JitterPolicy) -> tuple[str, _JitterComponentPolicy]:
    selector = ((1.0 - policy.selection_blend) * _clip01(u_lon)) + (
        policy.selection_blend * _clip01(u_lat)
    )
    if selector < policy.weight_core:
        return "core_cluster", policy.core_component
    if selector < policy.weight_core + policy.weight_secondary:
        return "secondary_cluster", policy.secondary_component
    return "sparse_tail", policy.sparse_component


def _sample_in_tile(
    policy: _S6JitterPolicy,
    u_lon: float,
    u_lat: float,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
) -> tuple[float, float, str, float, float]:
    if policy.mode == "uniform_v1":
        lon = _sample_lon_from_fraction(min_lon, max_lon, u_lon)
        lat = _sample_lat_from_fraction(min_lat, max_lat, u_lat)
        return lon, lat, "uniform_v1", 1.0, 1.0

    component_name, component = _select_component(u_lon, u_lat, policy)
    lon_frac = _shape_fraction(u_lon, component.lon_shape_exp, component.max_abs_offset_fraction)
    lat_frac = _shape_fraction(u_lat, component.lat_shape_exp, component.max_abs_offset_fraction)
    lon = _sample_lon_from_fraction(min_lon, max_lon, lon_frac)
    lat = _sample_lat_from_fraction(min_lat, max_lat, lat_frac)
    return (
        lon,
        lat,
        component_name,
        float(component.max_abs_offset_fraction),
        float(component.max_abs_offset_fraction),
    )


def _parse_component(payload: dict, key: str) -> _JitterComponentPolicy:
    node = payload.get(key) or {}
    return _JitterComponentPolicy(
        lat_shape_exp=float(node.get("lat_shape_exp", 1.0)),
        lon_shape_exp=float(node.get("lon_shape_exp", 1.0)),
        max_abs_offset_fraction=float(node.get("max_abs_offset_fraction", 1.0)),
    )


def _load_s6_jitter_policy(
    dictionary: dict,
    schema_1b: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    logger,
) -> tuple[_S6JitterPolicy, Path]:
    default = _S6JitterPolicy(
        policy_version="default-uniform-v1",
        mode="uniform_v1",
        deterministic_seed_namespace="1B.S6.JITTER_V1",
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        selection_blend=0.5,
        weight_core=0.0,
        weight_secondary=0.0,
        weight_sparse=1.0,
        core_component=_JitterComponentPolicy(1.0, 1.0, 1.0),
        secondary_component=_JitterComponentPolicy(1.0, 1.0, 1.0),
        sparse_component=_JitterComponentPolicy(1.0, 1.0, 1.0),
    )
    try:
        entry = find_dataset_entry(dictionary, "jitter_policy").entry
    except Exception:
        logger.info("S6: jitter_policy entry missing; using default uniform_v1 policy")
        return default, Path("<default>")

    policy_path = _resolve_dataset_path(entry, run_paths, external_roots, {})
    payload = _load_yaml(policy_path)
    _validate_payload(schema_1b, "#/policy/jitter_policy", payload)
    components = payload.get("components") or {}
    weights = payload.get("component_weights") or {}
    weight_core = float(weights.get("core_cluster", 0.0))
    weight_secondary = float(weights.get("secondary_cluster", 0.0))
    weight_sparse = float(weights.get("sparse_tail", 0.0))
    weight_sum = weight_core + weight_secondary + weight_sparse
    if weight_sum <= 0.0:
        raise InputResolutionError("jitter_policy component_weights must sum to > 0.")
    weight_core /= weight_sum
    weight_secondary /= weight_sum
    weight_sparse /= weight_sum

    policy = _S6JitterPolicy(
        policy_version=str(payload.get("policy_version") or "unknown"),
        mode=str(payload.get("mode") or "uniform_v1"),
        deterministic_seed_namespace=str(payload.get("deterministic_seed_namespace") or "1B.S6.JITTER_V1"),
        max_attempts=int(payload.get("max_attempts", DEFAULT_MAX_ATTEMPTS)),
        selection_blend=float(payload.get("selection_blend", 0.5)),
        weight_core=weight_core,
        weight_secondary=weight_secondary,
        weight_sparse=weight_sparse,
        core_component=_parse_component(components, "core_cluster"),
        secondary_component=_parse_component(components, "secondary_cluster"),
        sparse_component=_parse_component(components, "sparse_tail"),
    )
    if policy.max_attempts < 1:
        raise InputResolutionError("jitter_policy max_attempts must be >= 1.")
    if not (0.0 <= policy.selection_blend <= 1.0):
        raise InputResolutionError("jitter_policy selection_blend must be in [0,1].")
    return policy, policy_path


def _load_world_countries(world_path: Path) -> dict[str, _CountryGeometry]:
    world_gdf = gpd.read_parquet(world_path)
    if "country_iso" not in world_gdf.columns or "geom" not in world_gdf.columns:
        raise InputResolutionError("world_countries missing required columns (country_iso, geom).")
    world_gdf["country_iso"] = world_gdf["country_iso"].astype(str).str.upper()
    grouped = world_gdf.groupby("country_iso")["geom"].agg(lambda items: unary_union(list(items)))
    world_map = grouped.to_dict()
    output: dict[str, _CountryGeometry] = {}
    for iso, geom in world_map.items():
        if geom is None or geom.is_empty:
            raise EngineFailure(
                "F4",
                "E608_POINT_OUTSIDE_COUNTRY",
                "S6",
                MODULE_NAME,
                {"detail": "empty_geometry", "legal_country_iso": iso},
            )
        if not geom.is_valid:
            raise EngineFailure(
                "F4",
                "E608_POINT_OUTSIDE_COUNTRY",
                "S6",
                MODULE_NAME,
                {"detail": explain_validity(geom), "legal_country_iso": iso},
            )
        try:
            parts = _split_antimeridian_geometries(geom)
        except GEOSException as exc:
            raise EngineFailure(
                "F4",
                "E608_POINT_OUTSIDE_COUNTRY",
                "S6",
                MODULE_NAME,
                {"detail": str(exc), "legal_country_iso": iso},
            ) from exc
        if not parts:
            raise EngineFailure(
                "F4",
                "E608_POINT_OUTSIDE_COUNTRY",
                "S6",
                MODULE_NAME,
                {"detail": "no_polygon_parts", "legal_country_iso": iso},
            )
        output[iso] = _CountryGeometry(parts=parts, prepared=[prep(part) for part in parts])
    return output


def _point_in_country(country_geom: _CountryGeometry, lon: float, lat: float) -> bool:
    point = Point(lon, lat)
    for part, prepared in zip(country_geom.parts, country_geom.prepared):
        if prepared.contains(point) or part.touches(point):
            return True
    return False


def _write_batch(
    batch_rows: list[tuple[int, str, int, int, float, float, str]],
    batch_index: int,
    output_root: Path,
    logger,
) -> None:
    if not batch_rows:
        return
    part_path = output_root / f"part-{batch_index:05d}.parquet"
    merchant_ids, country_isos, site_orders, tile_ids, delta_lat, delta_lon, fingerprints = zip(*batch_rows)
    data = {
        "merchant_id": np.array(merchant_ids, dtype=np.uint64),
        "legal_country_iso": np.array(country_isos, dtype=object),
        "site_order": np.array(site_orders, dtype=np.int64),
        "tile_id": np.array(tile_ids, dtype=np.uint64),
        "delta_lat_deg": np.array(delta_lat, dtype=np.float64),
        "delta_lon_deg": np.array(delta_lon, dtype=np.float64),
        "manifest_fingerprint": np.array(fingerprints, dtype=object),
    }
    if _HAVE_PYARROW:
        table = pa.Table.from_pydict(data)
        pq.write_table(table, part_path, compression="zstd", row_group_size=200000)
    else:
        df = pl.DataFrame(data)
        df.write_parquet(part_path, compression="zstd", row_group_size=200000)
    logger.info("S6: wrote %d rows to %s", len(batch_rows), part_path)


def run_s6(config: EngineConfig, run_id: Optional[str] = None) -> S6Result:
    logger = get_logger("engine.layers.l1.seg_1B.s6_site_jitter.l2.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = receipt.get("seed")
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s",
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

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1B").entry
    receipt_path = _resolve_dataset_path(
        receipt_entry, run_paths, config.external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
    )
    if not receipt_path.exists():
        raise InputResolutionError(f"Missing s0_gate_receipt_1B: {receipt_path}")
    receipt_payload = _load_json(receipt_path)
    receipt_schema = _table_row_schema(schema_1b, "validation/s0_gate_receipt")
    receipt_validator = Draft202012Validator(receipt_schema)
    receipt_errors = list(receipt_validator.iter_errors(receipt_payload))
    if receipt_errors:
        raise SchemaValidationError(receipt_errors[0].message, [{"message": receipt_errors[0].message}])
    if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
        raise InputResolutionError("s0_gate_receipt_1B manifest_fingerprint mismatch.")
    timer.info("S6: gate receipt verified (authorizes S5 assignments + world_countries)")

    sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_1B").entry
    sealed_path = _resolve_dataset_path(
        sealed_entry, run_paths, config.external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
    )
    sealed_inputs = json.loads(sealed_path.read_text(encoding="utf-8"))
    sealed_index = {item["asset_id"]: item for item in sealed_inputs}
    if "world_countries" not in sealed_index:
        raise InputResolutionError("sealed_inputs_1B missing world_countries.")

    world_entry = find_dataset_entry(dictionary, "world_countries").entry
    world_path_expected = _resolve_dataset_path(world_entry, run_paths, config.external_roots, {})
    world_path = Path(sealed_index["world_countries"]["path"])
    if world_path.resolve() != world_path_expected.resolve():
        raise InputResolutionError(f"world_countries path mismatch: {world_path} vs {world_path_expected}")

    s5_entry = find_dataset_entry(dictionary, "s5_site_tile_assignment").entry
    tile_index_entry = find_dataset_entry(dictionary, "tile_index").entry
    tile_bounds_entry = find_dataset_entry(dictionary, "tile_bounds").entry
    jitter_entry = find_dataset_entry(dictionary, "s6_site_jitter").entry
    report_entry = find_dataset_entry(dictionary, "s6_run_report").entry
    jitter_policy, jitter_policy_path = _load_s6_jitter_policy(
        dictionary=dictionary,
        schema_1b=schema_1b,
        run_paths=run_paths,
        external_roots=config.external_roots,
        logger=logger,
    )
    event_entry = find_dataset_entry(dictionary, DATASET_ID).entry
    trace_entry = find_dataset_entry(dictionary, TRACE_DATASET_ID).entry
    audit_entry = find_dataset_entry(dictionary, AUDIT_DATASET_ID).entry

    s5_root = _resolve_dataset_path(s5_entry, run_paths, config.external_roots, tokens)
    tile_index_root = _resolve_dataset_path(
        tile_index_entry, run_paths, config.external_roots, {"parameter_hash": str(parameter_hash)}
    )
    tile_bounds_root = _resolve_dataset_path(
        tile_bounds_entry, run_paths, config.external_roots, {"parameter_hash": str(parameter_hash)}
    )
    jitter_root = _resolve_dataset_path(jitter_entry, run_paths, config.external_roots, tokens)
    run_report_path = _resolve_dataset_path(report_entry, run_paths, config.external_roots, tokens)
    event_root = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens)
    trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
    audit_path = _resolve_dataset_path(audit_entry, run_paths, config.external_roots, tokens)

    if not s5_root.exists():
        raise InputResolutionError(f"Missing s5_site_tile_assignment: {s5_root}")
    if not tile_bounds_root.exists():
        raise InputResolutionError(f"Missing tile_bounds: {tile_bounds_root}")
    if not tile_index_root.exists():
        raise InputResolutionError(f"Missing tile_index: {tile_index_root}")

    logger.info("S6: jitter inputs resolved (s5_site_tile_assignment + tile_bounds + world_countries)")
    logger.info("S6: loading world_countries geometry (path=%s)", world_path)
    world_geometry = _load_world_countries(world_path)
    logger.info("S6: world_countries loaded (countries=%d)", len(world_geometry))
    logger.info(
        "S6: loaded jitter policy mode=%s policy_version=%s max_attempts=%d selection_blend=%.3f path=%s",
        jitter_policy.mode,
        jitter_policy.policy_version,
        jitter_policy.max_attempts,
        jitter_policy.selection_blend,
        jitter_policy_path,
    )
    logger.info(
        "S6: jitter sampling uses %s with point-in-country check (max_attempts=%d)",
        jitter_policy.mode,
        jitter_policy.max_attempts,
    )

    s5_files = _list_parquet_files(s5_root)
    total_sites = _count_parquet_rows(s5_files)
    logger.info(
        "S6: s5_site_tile_assignment files=%d rows=%s",
        len(s5_files),
        total_sites if total_sites is not None else "unknown",
    )
    logger.info("S6: read mode=%s", "pyarrow" if _HAVE_PYARROW else "polars")

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

    tmp_root = run_paths.tmp_root / f"s6_site_jitter_{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    output_tmp = tmp_root / "data"
    output_tmp.mkdir(parents=True, exist_ok=True)
    event_tmp = tmp_root / "rng_events"
    event_tmp.mkdir(parents=True, exist_ok=True)
    event_tmp_file = _event_file_from_root(event_tmp)
    trace_tmp = tmp_root / "rng_trace.jsonl"

    event_enabled = not event_root.exists()
    event_handle = event_tmp_file.open("w", encoding="utf-8") if event_enabled else None
    if not event_enabled:
        logger.info("S6: rng_event_in_cell_jitter already exists; skipping event emission")

    if trace_path.exists():
        trace_mode = (
            "skip"
            if _trace_has_substream(trace_path, MODULE_NAME, SUBSTREAM_LABEL)
            else "append"
        )
    else:
        trace_mode = "create"
    if trace_mode == "create":
        trace_handle = trace_tmp.open("w", encoding="utf-8")
        trace_acc = RngTraceAccumulator()
    elif trace_mode == "append":
        trace_handle = trace_path.open("a", encoding="utf-8")
        trace_acc = RngTraceAccumulator()
    else:
        trace_handle = None
        trace_acc = None
    logger.info("S6: rng_trace_log mode=%s", trace_mode)
    trace_inline = event_enabled and trace_handle is not None and trace_acc is not None

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
    substream_material_label = f"{SUBSTREAM_LABEL}:{jitter_policy.deterministic_seed_namespace}"
    cache: OrderedDict[str, _TileIndexEntry] = OrderedDict()
    cache_hits = 0
    cache_misses = 0
    cache_evictions = 0
    bytes_read_index_total = 0

    batch_rows: list[tuple[int, str, int, int, float, float, str]] = []
    batch_index = 0
    rows_emitted = 0
    rng_events_emitted = 0
    resamples_total = 0
    attempts_hist: dict[int, int] = {}
    component_hist: dict[str, int] = {"uniform_v1": 0, "core_cluster": 0, "secondary_cluster": 0, "sparse_tail": 0}
    by_country: dict[str, dict[str, int]] = {}

    last_output_key: Optional[tuple[int, str, int]] = None
    progress_sites = _ProgressTracker(
        total_sites,
        logger,
        "S6 jitter progress sites_processed (location per site)",
    )

    def _flush_batch() -> None:
        nonlocal batch_index
        if not batch_rows:
            return
        _write_batch(batch_rows, batch_index, output_tmp, logger)
        batch_rows.clear()
        batch_index += 1

    def _get_tile_index_entry(country_iso: str) -> _TileIndexEntry:
        nonlocal cache_hits, cache_misses, cache_evictions, bytes_read_index_total
        if country_iso in cache:
            cache_hits += 1
            cache.move_to_end(country_iso)
            return cache[country_iso]
        cache_misses += 1
        tile_ids, bytes_read = _load_tile_index_country(tile_index_root, country_iso)
        entry = _TileIndexEntry(tile_ids_sorted=tile_ids, bytes_read=bytes_read)
        bytes_read_index_total += bytes_read
        cache[country_iso] = entry
        if len(cache) > CACHE_COUNTRIES_MAX:
            cache_evictions += 1
            cache.popitem(last=False)
        return entry

    def _update_country_stats(iso: str, attempts: int) -> None:
        stats = by_country.setdefault(iso, {"sites": 0, "attempts": 0, "resamples": 0})
        stats["sites"] += 1
        stats["attempts"] += attempts
        stats["resamples"] += max(attempts - 1, 0)

    start_wall = time.monotonic()
    start_cpu = time.process_time()

    try:
        for batch in _iter_parquet_batches(
            s5_files, ["merchant_id", "legal_country_iso", "site_order", "tile_id"]
        ):
            if _HAVE_PYARROW:
                merchant_ids = batch.column("merchant_id").to_numpy(zero_copy_only=False)
                country_isos = batch.column("legal_country_iso").to_numpy(zero_copy_only=False)
                site_orders = batch.column("site_order").to_numpy(zero_copy_only=False)
                tile_ids = batch.column("tile_id").to_numpy(zero_copy_only=False)
            else:
                merchant_ids = batch.get_column("merchant_id").to_numpy()
                country_isos = batch.get_column("legal_country_iso").to_numpy()
                site_orders = batch.get_column("site_order").to_numpy()
                tile_ids = batch.get_column("tile_id").to_numpy()

            unique_pairs: dict[str, set[int]] = {}
            for iso_val, tile_val in zip(country_isos, tile_ids):
                iso = str(iso_val)
                unique_pairs.setdefault(iso, set()).add(int(tile_val))

            bounds_cache: dict[str, dict[int, tuple[float, float, float, float, float, float]]] = {}
            for iso, tile_set in unique_pairs.items():
                if iso not in world_geometry:
                    _emit_failure_event(
                        logger,
                        "E608_POINT_OUTSIDE_COUNTRY",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "country_not_in_world", "legal_country_iso": iso},
                    )
                    raise EngineFailure(
                        "F4",
                        "E608_POINT_OUTSIDE_COUNTRY",
                        "S6",
                        MODULE_NAME,
                        {"legal_country_iso": iso},
                    )
                tile_ids_arr = np.array(sorted(tile_set), dtype=np.uint64)
                bounds_map = _load_tile_bounds_country(tile_bounds_root, iso, tile_ids_arr)
                if len(bounds_map) != tile_ids_arr.size:
                    missing = sorted(tile_set.difference(bounds_map.keys()))
                    _emit_failure_event(
                        logger,
                        "E606_FK_TILE_INDEX",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "tile_bounds_missing", "legal_country_iso": iso, "missing": missing},
                    )
                    raise EngineFailure(
                        "F4",
                        "E606_FK_TILE_INDEX",
                        "S6",
                        MODULE_NAME,
                        {"legal_country_iso": iso, "missing": missing},
                    )
                bounds_cache[iso] = bounds_map

                index_entry = _get_tile_index_entry(iso)
                for tile_id in tile_ids_arr:
                    if not index_entry.contains(int(tile_id)):
                        _emit_failure_event(
                            logger,
                            "E606_FK_TILE_INDEX",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "tile_id_not_in_index", "legal_country_iso": iso, "tile_id": int(tile_id)},
                        )
                        raise EngineFailure(
                            "F4",
                            "E606_FK_TILE_INDEX",
                            "S6",
                            MODULE_NAME,
                            {"legal_country_iso": iso, "tile_id": int(tile_id)},
                        )

            for idx in range(len(merchant_ids)):
                merchant_id = int(merchant_ids[idx])
                legal_country_iso = str(country_isos[idx])
                site_order = int(site_orders[idx])
                tile_id = int(tile_ids[idx])

                output_key = (merchant_id, legal_country_iso, site_order)
                if last_output_key is not None:
                    if output_key == last_output_key:
                        _emit_failure_event(
                            logger,
                            "E603_DUP_KEY",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "duplicate_output_key", "key": output_key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E603_DUP_KEY",
                            "S6",
                            MODULE_NAME,
                            {"key": output_key},
                        )
                    if output_key < last_output_key:
                        _emit_failure_event(
                            logger,
                            "E605_SORT_VIOLATION",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "output_unsorted", "key": output_key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E605_SORT_VIOLATION",
                            "S6",
                            MODULE_NAME,
                            {"detail": "output_unsorted", "key": output_key},
                        )
                last_output_key = output_key

                bounds = bounds_cache[legal_country_iso][tile_id]
                min_lon, max_lon, min_lat, max_lat, centroid_lon, centroid_lat = bounds
                key, counter_hi, counter_lo = _derive_site_substream(
                    master_material,
                    substream_material_label,
                    merchant_id,
                    legal_country_iso,
                    site_order,
                )

                attempts = 0
                accepted = False
                delta_lat = 0.0
                delta_lon = 0.0
                component_name = "uniform_v1"
                sigma_lat_deg = 1.0
                sigma_lon_deg = 1.0
                for _ in range(jitter_policy.max_attempts):
                    attempts += 1
                    before_hi = counter_hi
                    before_lo = counter_lo
                    out0, out1 = philox2x64_10(counter_hi, counter_lo, key)
                    counter_hi, counter_lo = add_u128(counter_hi, counter_lo, 1)
                    u_lon = u01(out0)
                    u_lat = u01(out1)

                    lon, lat, component_name, sigma_lat_deg, sigma_lon_deg = _sample_in_tile(
                        policy=jitter_policy,
                        u_lon=u_lon,
                        u_lat=u_lat,
                        min_lon=min_lon,
                        max_lon=max_lon,
                        min_lat=min_lat,
                        max_lat=max_lat,
                    )

                    span_lon = max_lon - min_lon
                    if span_lon < 0.0:
                        span_lon += 360.0

                    if not (min_lat - 1e-9 <= lat <= max_lat + 1e-9):
                        _emit_failure_event(
                            logger,
                            "E607_POINT_OUTSIDE_PIXEL",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "lat_outside_pixel", "lat": lat, "bounds": [min_lat, max_lat]},
                        )
                        raise EngineFailure(
                            "F4",
                            "E607_POINT_OUTSIDE_PIXEL",
                            "S6",
                            MODULE_NAME,
                            {"lat": lat, "bounds": [min_lat, max_lat]},
                        )
                    if span_lon <= 180.0 and not (
                        min_lon - 1e-9 <= lon <= max_lon + 1e-9
                    ):
                        _emit_failure_event(
                            logger,
                            "E607_POINT_OUTSIDE_PIXEL",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "lon_outside_pixel", "lon": lon, "bounds": [min_lon, max_lon]},
                        )
                        raise EngineFailure(
                            "F4",
                            "E607_POINT_OUTSIDE_PIXEL",
                            "S6",
                            MODULE_NAME,
                            {"lon": lon, "bounds": [min_lon, max_lon]},
                        )

                    delta_lat = lat - centroid_lat
                    delta_lon = lon - centroid_lon

                    event = {
                        "ts_utc": utc_now_rfc3339_micro(),
                        "run_id": str(run_id),
                        "seed": int(seed),
                        "parameter_hash": str(parameter_hash),
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "module": MODULE_NAME,
                        "substream_label": SUBSTREAM_LABEL,
                        "rng_counter_before_lo": int(before_lo),
                        "rng_counter_before_hi": int(before_hi),
                        "rng_counter_after_lo": int(counter_lo),
                        "rng_counter_after_hi": int(counter_hi),
                        "draws": "2",
                        "blocks": 1,
                        "merchant_id": merchant_id,
                        "legal_country_iso": legal_country_iso,
                        "site_order": site_order,
                        "sigma_lat_deg": float(sigma_lat_deg),
                        "sigma_lon_deg": float(sigma_lon_deg),
                        "delta_lat_deg": float(delta_lat),
                        "delta_lon_deg": float(delta_lon),
                    }
                    if trace_inline:
                        trace_row = trace_acc.append_event(event)
                    if event_enabled and event_handle is not None:
                        event_handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True))
                        event_handle.write("\n")
                    if trace_inline:
                        trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
                        trace_handle.write("\n")
                    rng_events_emitted += 1

                    if _point_in_country(world_geometry[legal_country_iso], lon, lat):
                        component_hist[component_name] = component_hist.get(component_name, 0) + 1
                        accepted = True
                        break

                if not accepted:
                    _emit_failure_event(
                        logger,
                        "E613_RESAMPLE_EXHAUSTED",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "resample_exhausted", "key": output_key, "attempts": attempts},
                    )
                    raise EngineFailure(
                        "F4",
                        "E613_RESAMPLE_EXHAUSTED",
                        "S6",
                        MODULE_NAME,
                        {"key": output_key, "attempts": attempts},
                    )

                if abs(delta_lat) > 1.0 or abs(delta_lon) > 1.0:
                    _emit_failure_event(
                        logger,
                        "E607_POINT_OUTSIDE_PIXEL",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "delta_out_of_bounds", "delta_lat": delta_lat, "delta_lon": delta_lon},
                    )
                    raise EngineFailure(
                        "F4",
                        "E607_POINT_OUTSIDE_PIXEL",
                        "S6",
                        MODULE_NAME,
                        {"delta_lat": delta_lat, "delta_lon": delta_lon},
                    )

                batch_rows.append(
                    (
                        merchant_id,
                        legal_country_iso,
                        site_order,
                        tile_id,
                        float(delta_lat),
                        float(delta_lon),
                        str(manifest_fingerprint),
                    )
                )
                rows_emitted += 1
                resamples_total += max(attempts - 1, 0)
                attempts_hist[attempts] = attempts_hist.get(attempts, 0) + 1
                _update_country_stats(legal_country_iso, attempts)
                progress_sites.update(1)

                if len(batch_rows) >= BATCH_SIZE:
                    _flush_batch()

            if hasattr(proc, "open_files"):
                try:
                    open_files_peak = max(open_files_peak, len(proc.open_files()))
                except Exception:
                    pass
            if open_files_metric == "handles" and hasattr(proc, "num_handles"):
                open_files_peak = max(open_files_peak, int(proc.num_handles()))
            if open_files_metric == "fds" and hasattr(proc, "num_fds"):
                open_files_peak = max(open_files_peak, int(proc.num_fds()))

        _flush_batch()
        if not event_enabled and trace_handle is not None and trace_acc is not None:
            rng_events_emitted = _append_trace_from_events(
                event_root, trace_handle, trace_acc, logger
            )
        if rows_emitted == 0:
            raise EngineFailure("F4", "E601_ROW_MISSING", "S6", MODULE_NAME, {"detail": "no_rows_emitted"})
        if total_sites is not None and rows_emitted != total_sites:
            _emit_failure_event(
                logger,
                "E601_ROW_MISSING",
                int(seed),
                str(manifest_fingerprint),
                str(parameter_hash),
                str(run_id),
                {"detail": "row_count_mismatch", "expected": total_sites, "actual": rows_emitted},
            )
            raise EngineFailure(
                "F4",
                "E601_ROW_MISSING",
                "S6",
                MODULE_NAME,
                {"expected": total_sites, "actual": rows_emitted},
            )
        if rng_events_emitted < rows_emitted:
            _emit_failure_event(
                logger,
                "E609_RNG_EVENT_COUNT",
                int(seed),
                str(manifest_fingerprint),
                str(parameter_hash),
                str(run_id),
                {"detail": "rng_events_lt_rows", "events": rng_events_emitted, "rows": rows_emitted},
            )
            raise EngineFailure(
                "F4",
                "E609_RNG_EVENT_COUNT",
                "S6",
                MODULE_NAME,
                {"events": rng_events_emitted, "rows": rows_emitted},
            )
    finally:
        if event_handle is not None and not event_handle.closed:
            event_handle.close()
        if trace_handle is not None and not trace_handle.closed:
            trace_handle.close()

    determinism_hash, determinism_bytes = _hash_partition(output_tmp)
    determinism_receipt = {
        "partition_path": str(jitter_root),
        "sha256_hex": determinism_hash,
        "bytes_hashed": determinism_bytes,
    }

    _atomic_publish_dir(output_tmp, jitter_root, logger, "s6_site_jitter")
    if event_enabled:
        _atomic_publish_dir(event_tmp, event_root, logger, DATASET_ID)
    if trace_mode == "create":
        _atomic_publish_file(trace_tmp, trace_path, logger, TRACE_DATASET_ID)
    elif trace_mode == "append":
        logger.info("S6: rng_trace_log appended (existing log retained)")
    _ensure_rng_audit(audit_path, audit_entry_payload, logger)

    wall_total = time.monotonic() - start_wall
    cpu_total = time.process_time() - start_cpu

    rng_draws_total = rng_events_emitted * 2
    component_total = int(sum(component_hist.values()))
    component_share = {
        key: (float(value) / float(component_total) if component_total > 0 else 0.0)
        for key, value in component_hist.items()
    }
    run_report = {
        "seed": int(seed),
        "manifest_fingerprint": str(manifest_fingerprint),
        "parameter_hash": str(parameter_hash),
        "run_id": str(run_id),
        "jitter_policy": {
            "policy_version": jitter_policy.policy_version,
            "mode": jitter_policy.mode,
            "deterministic_seed_namespace": jitter_policy.deterministic_seed_namespace,
            "max_attempts": jitter_policy.max_attempts,
            "selection_blend": jitter_policy.selection_blend,
            "component_weights": {
                "core_cluster": jitter_policy.weight_core,
                "secondary_cluster": jitter_policy.weight_secondary,
                "sparse_tail": jitter_policy.weight_sparse,
            },
            "components": {
                "core_cluster": {
                    "lat_shape_exp": jitter_policy.core_component.lat_shape_exp,
                    "lon_shape_exp": jitter_policy.core_component.lon_shape_exp,
                    "max_abs_offset_fraction": jitter_policy.core_component.max_abs_offset_fraction,
                },
                "secondary_cluster": {
                    "lat_shape_exp": jitter_policy.secondary_component.lat_shape_exp,
                    "lon_shape_exp": jitter_policy.secondary_component.lon_shape_exp,
                    "max_abs_offset_fraction": jitter_policy.secondary_component.max_abs_offset_fraction,
                },
                "sparse_tail": {
                    "lat_shape_exp": jitter_policy.sparse_component.lat_shape_exp,
                    "lon_shape_exp": jitter_policy.sparse_component.lon_shape_exp,
                    "max_abs_offset_fraction": jitter_policy.sparse_component.max_abs_offset_fraction,
                },
            },
        },
        "counts": {
            "sites_total": rows_emitted,
            "rng": {
                "events_total": rng_events_emitted,
                "draws_total": str(rng_draws_total),
                "blocks_total": rng_events_emitted,
            },
            "resamples_total": resamples_total,
        },
        "attempt_histogram": {str(k): int(v) for k, v in sorted(attempts_hist.items())},
        "component_histogram": {str(k): int(v) for k, v in sorted(component_hist.items())},
        "component_share": component_share,
        "by_country": by_country,
        "determinism_receipt": determinism_receipt,
        "pat": {
            "rows_emitted": rows_emitted,
            "rng_events_emitted": rng_events_emitted,
            "bytes_read_index_total": bytes_read_index_total,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_evictions": cache_evictions,
            "wall_clock_seconds_total": wall_total,
            "cpu_seconds_total": cpu_total,
            "open_files_peak": open_files_peak,
            "open_files_metric": open_files_metric,
        },
    }
    _validate_payload(schema_1b, "#/control/s6_run_report", run_report)
    run_report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(run_report_path, run_report)
    timer.info("S6: run report written (jitter summary + determinism receipt)")

    shutil.rmtree(tmp_root, ignore_errors=True)

    return S6Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        jitter_root=jitter_root,
        run_report_path=run_report_path,
        event_root=event_root,
        trace_path=trace_path,
        audit_path=audit_path,
    )
