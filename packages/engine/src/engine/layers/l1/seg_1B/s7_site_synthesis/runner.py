from __future__ import annotations

import hashlib
import json
import shutil
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
import yaml
from jsonschema import Draft202012Validator

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


MODULE_NAME = "1B.S7.synthesis"
CACHE_COUNTRIES_MAX = 6
BATCH_SIZE = 200_000


@dataclass(frozen=True)
class S7Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    synthesis_root: Path
    run_summary_path: Path


@dataclass(frozen=True)
class S3RequirementsPolicy:
    policy_version: str
    enabled: bool
    denylist_country_iso: tuple[str, ...]


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


def _column_schema(column: dict) -> dict:
    if "$ref" in column:
        schema: dict = {"$ref": column["$ref"]}
    else:
        col_type = column.get("type")
        if col_type == "array":
            items = column.get("items") or {}
            schema = {"type": "array", "items": items}
        elif col_type in ("string", "integer", "number", "boolean"):
            schema = {"type": col_type}
        else:
            raise SchemaValidationError(f"Unsupported column type '{col_type}' for receipt schema.", [])
    if column.get("nullable"):
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _table_row_schema(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    columns = node.get("columns") or []
    if not columns:
        raise SchemaValidationError(f"Table '{path}' has no columns.", [])
    properties: dict[str, dict] = {}
    required: list[str] = []
    for column in columns:
        name = column.get("name")
        if not name:
            raise SchemaValidationError(f"Column missing name in {path}.", [])
        properties[name] = _column_schema(column)
        required.append(name)
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    return normalize_nullable_schema(schema)


def _validate_payload(schema_pack: dict, path: str, payload: object) -> None:
    schema = _schema_from_pack(schema_pack, path)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        detail = errors[0].message if errors else "schema validation failed"
        raise SchemaValidationError(detail, [{"message": detail}])


def _assert_schema_ref(
    schema_ref: Optional[str],
    schema_1a: dict,
    schema_1b: dict,
    dataset_id: str,
    logger,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> None:
    if not schema_ref:
        _emit_failure_event(
            logger,
            "E711_DICT_SCHEMA_MISMATCH",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
        raise EngineFailure(
            "F4",
            "E711_DICT_SCHEMA_MISMATCH",
            "S7",
            MODULE_NAME,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
    try:
        if schema_ref.startswith("schemas.1B.yaml#"):
            _schema_from_pack(schema_1b, schema_ref.split("#", 1)[1])
        elif schema_ref.startswith("schemas.1A.yaml#"):
            _schema_from_pack(schema_1a, schema_ref.split("#", 1)[1])
        else:
            raise SchemaValidationError(f"Unknown schema_ref prefix: {schema_ref}", [])
    except Exception as exc:
        _emit_failure_event(
            logger,
            "E711_DICT_SCHEMA_MISMATCH",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref, "error": str(exc)},
        )
        raise EngineFailure(
            "F4",
            "E711_DICT_SCHEMA_MISMATCH",
            "S7",
            MODULE_NAME,
            {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
        )


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
        "event": "S7_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S7_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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
                "E712_ATOMIC_PUBLISH_VIOLATION",
                "S7",
                MODULE_NAME,
                {"partition": str(final_root), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S7: %s partition already exists and is identical; skipping publish.", label)
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
                "E712_ATOMIC_PUBLISH_VIOLATION",
                "S7",
                MODULE_NAME,
                {"path": str(final_path), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        tmp_path.unlink()
        logger.info("S7: %s already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)


def _close_parquet_reader(reader: object) -> None:
    if hasattr(reader, "close"):
        try:
            reader.close()
        except Exception:
            pass


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
        try:
            total += pf.metadata.num_rows
        finally:
            _close_parquet_reader(pf)
    return total


def _parse_s3_policy(policy_payload: dict) -> S3RequirementsPolicy:
    denylist_raw = policy_payload.get("denylist_country_iso") or []
    if not isinstance(denylist_raw, list):
        raise InputResolutionError("s3_requirements_policy.denylist_country_iso must be a list.")
    normalized: list[str] = []
    for iso in denylist_raw:
        if not isinstance(iso, str):
            raise InputResolutionError("s3_requirements_policy.denylist_country_iso must contain strings.")
        value = iso.strip().upper()
        if not value:
            raise InputResolutionError("s3_requirements_policy.denylist_country_iso cannot contain blank values.")
        normalized.append(value)
    return S3RequirementsPolicy(
        policy_version=str(policy_payload.get("policy_version") or "unknown"),
        enabled=bool(policy_payload.get("enabled", False)),
        denylist_country_iso=tuple(sorted(set(normalized))),
    )


def _count_outlet_rows_excluding(paths: Iterable[Path], excluded_country_iso: set[str]) -> int:
    if not excluded_country_iso:
        rows = _count_parquet_rows(paths)
        return int(rows or 0)
    excluded = sorted(excluded_country_iso)
    frame = pl.scan_parquet([str(path) for path in paths]).select(["legal_country_iso"])
    kept = frame.filter(~pl.col("legal_country_iso").is_in(excluded)).collect()
    return int(kept.height)


def _iter_parquet_batches(paths: Iterable[Path], columns: list[str]) -> Iterator[object]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    yield pf.read_row_group(rg, columns=columns)
            finally:
                _close_parquet_reader(pf)
    else:
        for path in paths:
            df = pl.read_parquet(path, columns=columns)
            offset = 0
            while offset < df.height:
                chunk = df.slice(offset, BATCH_SIZE)
                offset += chunk.height
                yield chunk


def _normalize_lon(value: float) -> float:
    if value > 180.0:
        return value - 360.0
    if value < -180.0:
        return value + 360.0
    return value


def _lon_in_bounds(lon: float, min_lon: float, max_lon: float) -> bool:
    if min_lon <= max_lon:
        return min_lon - 1e-9 <= lon <= max_lon + 1e-9
    return lon >= min_lon - 1e-9 or lon <= max_lon + 1e-9


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


def _detect_column(paths: list[Path], column: str) -> bool:
    if not paths:
        return False
    if _HAVE_PYARROW:
        pf = pq.ParquetFile(paths[0])
        try:
            return column in pf.schema.names
        finally:
            _close_parquet_reader(pf)
    df = pl.read_parquet(paths[0], n_rows=0)
    return column in df.columns


def _iter_s6_rows(paths: list[Path]) -> Iterator[tuple[tuple[int, str, int], int, float, float, str]]:
    columns = [
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "tile_id",
        "delta_lat_deg",
        "delta_lon_deg",
        "manifest_fingerprint",
    ]
    last_key: Optional[tuple[int, str, int]] = None
    for batch in _iter_parquet_batches(paths, columns):
        if _HAVE_PYARROW:
            merchant_ids = batch.column("merchant_id").to_numpy(zero_copy_only=False)
            country_isos = batch.column("legal_country_iso").to_numpy(zero_copy_only=False)
            site_orders = batch.column("site_order").to_numpy(zero_copy_only=False)
            tile_ids = batch.column("tile_id").to_numpy(zero_copy_only=False)
            delta_lat = batch.column("delta_lat_deg").to_numpy(zero_copy_only=False)
            delta_lon = batch.column("delta_lon_deg").to_numpy(zero_copy_only=False)
            manifest_fp = batch.column("manifest_fingerprint").to_numpy(zero_copy_only=False)
            rows_total = batch.num_rows
        else:
            merchant_ids = batch.get_column("merchant_id").to_numpy()
            country_isos = batch.get_column("legal_country_iso").to_numpy()
            site_orders = batch.get_column("site_order").to_numpy()
            tile_ids = batch.get_column("tile_id").to_numpy()
            delta_lat = batch.get_column("delta_lat_deg").to_numpy()
            delta_lon = batch.get_column("delta_lon_deg").to_numpy()
            manifest_fp = batch.get_column("manifest_fingerprint").to_numpy()
            rows_total = batch.height
        for idx in range(rows_total):
            key = (int(merchant_ids[idx]), str(country_isos[idx]), int(site_orders[idx]))
            if last_key is not None and key < last_key:
                raise EngineFailure(
                    "F4",
                    "E706_WRITER_SORT_VIOLATION",
                    "S7",
                    MODULE_NAME,
                    {"detail": "s6_unsorted", "key": key},
                )
            if last_key is not None and key == last_key:
                raise EngineFailure(
                    "F4",
                    "E703_DUP_KEY",
                    "S7",
                    MODULE_NAME,
                    {"detail": "s6_duplicate_key", "key": key},
                )
            last_key = key
            yield key, int(tile_ids[idx]), float(delta_lat[idx]), float(delta_lon[idx]), str(manifest_fp[idx])


def _iter_outlet_rows(
    paths: list[Path],
    include_global_seed: bool,
    excluded_country_iso: set[str],
) -> Iterator[tuple[tuple[int, str, int], str, Optional[int]]]:
    columns = ["merchant_id", "legal_country_iso", "site_order", "manifest_fingerprint"]
    if include_global_seed:
        columns.append("global_seed")
    last_key: Optional[tuple[int, str, int]] = None
    for batch in _iter_parquet_batches(paths, columns):
        if _HAVE_PYARROW:
            merchant_ids = batch.column("merchant_id").to_numpy(zero_copy_only=False)
            country_isos = batch.column("legal_country_iso").to_numpy(zero_copy_only=False)
            site_orders = batch.column("site_order").to_numpy(zero_copy_only=False)
            manifest_fp = batch.column("manifest_fingerprint").to_numpy(zero_copy_only=False)
            global_seed = (
                batch.column("global_seed").to_numpy(zero_copy_only=False)
                if include_global_seed
                else None
            )
            rows_total = batch.num_rows
        else:
            merchant_ids = batch.get_column("merchant_id").to_numpy()
            country_isos = batch.get_column("legal_country_iso").to_numpy()
            site_orders = batch.get_column("site_order").to_numpy()
            manifest_fp = batch.get_column("manifest_fingerprint").to_numpy()
            global_seed = batch.get_column("global_seed").to_numpy() if include_global_seed else None
            rows_total = batch.height
        for idx in range(rows_total):
            country_iso = str(country_isos[idx])
            if excluded_country_iso and country_iso in excluded_country_iso:
                continue
            key = (int(merchant_ids[idx]), country_iso, int(site_orders[idx]))
            if last_key is not None and key < last_key:
                raise EngineFailure(
                    "F4",
                    "E706_WRITER_SORT_VIOLATION",
                    "S7",
                    MODULE_NAME,
                    {"detail": "outlet_unsorted", "key": key},
                )
            if last_key is not None and key == last_key:
                raise EngineFailure(
                    "F4",
                    "E703_DUP_KEY",
                    "S7",
                    MODULE_NAME,
                    {"detail": "outlet_duplicate_key", "key": key},
                )
            last_key = key
            seed_val = int(global_seed[idx]) if include_global_seed else None
            yield key, str(manifest_fp[idx]), seed_val


class _RowStream:
    def __init__(self, iterator, label: str) -> None:
        self._iter = iterator
        self.label = label
        self.current = None
        self.advance()

    def advance(self) -> None:
        try:
            self.current = next(self._iter)
        except StopIteration:
            self.current = None


def _write_batch(rows: list[tuple], batch_index: int, output_tmp: Path, logger) -> None:
    if not rows:
        return
    df = pl.DataFrame(
        rows,
        schema=[
            ("merchant_id", pl.UInt64),
            ("legal_country_iso", pl.Utf8),
            ("site_order", pl.Int32),
            ("tile_id", pl.UInt64),
            ("lon_deg", pl.Float64),
            ("lat_deg", pl.Float64),
        ],
        orient="row",
    )
    path = output_tmp / f"part-{batch_index:05d}.parquet"
    df.write_parquet(path, compression="zstd", row_group_size=100000)
    logger.info("S7: wrote %d rows to %s", df.height, path)


def run_s7(config: EngineConfig, run_id: Optional[str] = None) -> S7Result:
    logger = get_logger("engine.layers.l1.seg_1B.s7_site_synthesis.l2.runner")
    timer = _StepTimer(logger)

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
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        schema_1b_path,
        schema_1a_path,
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": str(parameter_hash),
        "manifest_fingerprint": str(manifest_fingerprint),
        "run_id": str(run_id),
    }
    external_roots = config.external_roots or (config.repo_root,)

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1B").entry
    sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_1B").entry
    s5_entry = find_dataset_entry(dictionary, "s5_site_tile_assignment").entry
    s6_entry = find_dataset_entry(dictionary, "s6_site_jitter").entry
    tile_bounds_entry = find_dataset_entry(dictionary, "tile_bounds").entry
    outlet_entry = find_dataset_entry(dictionary, "outlet_catalogue").entry
    s3_policy_entry = find_dataset_entry(dictionary, "s3_requirements_policy").entry
    synthesis_entry = find_dataset_entry(dictionary, "s7_site_synthesis").entry
    summary_entry = find_dataset_entry(dictionary, "s7_run_summary").entry

    for dataset_id, entry in (
        ("s0_gate_receipt_1B", receipt_entry),
        ("sealed_inputs_1B", sealed_entry),
        ("s5_site_tile_assignment", s5_entry),
        ("s6_site_jitter", s6_entry),
        ("tile_bounds", tile_bounds_entry),
        ("outlet_catalogue", outlet_entry),
        ("s3_requirements_policy", s3_policy_entry),
        ("s7_site_synthesis", synthesis_entry),
        ("s7_run_summary", summary_entry),
    ):
        _assert_schema_ref(
            entry.get("schema_ref"),
            schema_1a,
            schema_1b,
            dataset_id,
            logger,
            int(seed),
            str(manifest_fingerprint),
            str(parameter_hash),
            str(run_id),
        )

    receipt_path = _resolve_dataset_path(
        receipt_entry, run_paths, external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
    )
    if not receipt_path.exists():
        raise InputResolutionError(f"Missing s0_gate_receipt_1B: {receipt_path}")
    receipt_payload = _load_json(receipt_path)
    receipt_schema = _table_row_schema(schema_1b, "validation/s0_gate_receipt")
    receipt_validator = Draft202012Validator(receipt_schema)
    receipt_errors = list(receipt_validator.iter_errors(receipt_payload))
    if receipt_errors:
        raise EngineFailure(
            "F4",
            "E705_PARTITION_OR_IDENTITY",
            "S7",
            MODULE_NAME,
            {"detail": receipt_errors[0].message},
        )
    if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
        raise EngineFailure(
            "F4",
            "E705_PARTITION_OR_IDENTITY",
            "S7",
            MODULE_NAME,
            {"detail": "s0_gate_receipt manifest_fingerprint mismatch"},
        )
    sealed_inputs = receipt_payload.get("sealed_inputs", [])
    sealed_ids = {item.get("id") for item in sealed_inputs}
    if "outlet_catalogue" not in sealed_ids:
        raise EngineFailure(
            "F4",
            "E705_PARTITION_OR_IDENTITY",
            "S7",
            MODULE_NAME,
            {"detail": "outlet_catalogue missing from sealed_inputs"},
        )
    timer.info("S7: gate receipt verified (sealed_inputs=%d; outlet_catalogue authorized)", len(sealed_inputs))

    sealed_path = _resolve_dataset_path(
        sealed_entry, run_paths, external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
    )
    if sealed_path.exists():
        try:
            _validate_payload(schema_1b, "validation/sealed_inputs_1B", _load_json(sealed_path))
        except SchemaValidationError:
            raise EngineFailure(
                "F4",
                "E705_PARTITION_OR_IDENTITY",
                "S7",
                MODULE_NAME,
                {"detail": "sealed_inputs_1B schema invalid"},
            )

    s5_root = _resolve_dataset_path(s5_entry, run_paths, external_roots, tokens)
    s6_root = _resolve_dataset_path(s6_entry, run_paths, external_roots, tokens)
    tile_bounds_root = _resolve_dataset_path(
        tile_bounds_entry, run_paths, external_roots, {"parameter_hash": str(parameter_hash)}
    )
    outlet_root = _resolve_dataset_path(outlet_entry, run_paths, external_roots, tokens)
    s3_policy_path = _resolve_dataset_path(s3_policy_entry, run_paths, external_roots, {})
    synthesis_root = _resolve_dataset_path(synthesis_entry, run_paths, external_roots, tokens)
    summary_path = _resolve_dataset_path(summary_entry, run_paths, external_roots, tokens)

    if not tile_bounds_root.exists():
        raise InputResolutionError(f"Missing tile_bounds: {tile_bounds_root}")

    s5_files = _list_parquet_files(s5_root)
    s6_files = _list_parquet_files(s6_root)
    outlet_files = _list_parquet_files(outlet_root)
    s3_policy_payload = _load_yaml(s3_policy_path)
    _validate_payload(schema_1b, "#/policy/s3_requirements_policy", s3_policy_payload)
    s3_policy = _parse_s3_policy(s3_policy_payload)
    country_denylist_set = set(s3_policy.denylist_country_iso) if s3_policy.enabled else set()
    logger.info(
        "S7: loaded requirements policy enabled=%s denylist_count=%d version=%s path=%s",
        s3_policy.enabled,
        len(country_denylist_set),
        s3_policy.policy_version,
        s3_policy_path,
    )

    logger.info("S7: synthesis inputs resolved (S5 assignments + S6 jitter + 1A outlet_catalogue)")

    s5_rows_total = _count_parquet_rows(s5_files)
    s6_rows_total = _count_parquet_rows(s6_files)
    outlet_rows_total = _count_outlet_rows_excluding(outlet_files, country_denylist_set)
    logger.info(
        "S7: input row counts s5=%s s6=%s outlet_catalogue_effective=%s (site-level parity check)",
        s5_rows_total if s5_rows_total is not None else "unknown",
        s6_rows_total if s6_rows_total is not None else "unknown",
        outlet_rows_total if outlet_rows_total is not None else "unknown",
    )

    if s5_rows_total is not None and s6_rows_total is not None and s5_rows_total != s6_rows_total:
        raise EngineFailure(
            "F4",
            "E701_ROW_MISSING",
            "S7",
            MODULE_NAME,
            {"detail": "s5_s6_row_count_mismatch", "s5_rows": s5_rows_total, "s6_rows": s6_rows_total},
        )
    if (
        s5_rows_total is not None
        and outlet_rows_total is not None
        and s5_rows_total != outlet_rows_total
    ):
        raise EngineFailure(
            "F4",
            "E708_1A_COVERAGE_FAIL",
            "S7",
            MODULE_NAME,
            {"detail": "s5_outlet_row_count_mismatch", "s5_rows": s5_rows_total, "outlet_rows": outlet_rows_total},
        )

    include_global_seed = _detect_column(outlet_files, "global_seed")
    progress = _ProgressTracker(
        s5_rows_total,
        logger,
        "S7 synthesis progress sites_processed (site records built)",
    )

    output_tmp = run_paths.tmp_root / f"s7_site_synthesis_{uuid.uuid4().hex}"
    output_tmp.mkdir(parents=True, exist_ok=True)

    last_key: Optional[tuple[int, str, int]] = None
    batch_rows: list[tuple] = []
    batch_index = 0

    s6_stream = _RowStream(_iter_s6_rows(s6_files), "s6_site_jitter")
    outlet_stream = _RowStream(
        _iter_outlet_rows(outlet_files, include_global_seed, country_denylist_set),
        "outlet_catalogue",
    )

    counts = {
        "sites_total_s5": 0,
        "sites_total_s6": 0,
        "sites_total_s7": 0,
    }
    validation_counters = {
        "fk_tile_ok_count": 0,
        "fk_tile_fail_count": 0,
        "inside_pixel_ok_count": 0,
        "inside_pixel_fail_count": 0,
        "coverage_1a_ok_count": 0,
        "coverage_1a_miss_count": 0,
        "path_embed_mismatches": 0,
    }
    by_country: dict[str, dict[str, int]] = {}

    bounds_cache: OrderedDict[str, dict[int, tuple[float, float, float, float, float, float]]] = OrderedDict()
    cache_hits = 0
    cache_misses = 0
    cache_evictions = 0

    def _get_bounds(iso: str, tile_set: set[int]) -> dict[int, tuple[float, float, float, float, float, float]]:
        nonlocal cache_hits, cache_misses, cache_evictions
        if iso in bounds_cache:
            bounds_cache.move_to_end(iso)
            cache_hits += 1
            return bounds_cache[iso]
        cache_misses += 1
        tile_ids_arr = np.array(sorted(tile_set), dtype=np.uint64)
        bounds_map = _load_tile_bounds_country(tile_bounds_root, iso, tile_ids_arr)
        if len(bounds_map) != tile_ids_arr.size:
            missing = sorted(tile_set.difference(bounds_map.keys()))
            _emit_failure_event(
                logger,
                "E709_TILE_FK_VIOLATION",
                int(seed),
                str(manifest_fingerprint),
                str(parameter_hash),
                str(run_id),
                {"detail": "tile_bounds_missing", "legal_country_iso": iso, "missing": missing},
            )
            raise EngineFailure(
                "F4",
                "E709_TILE_FK_VIOLATION",
                "S7",
                MODULE_NAME,
                {"legal_country_iso": iso, "missing": missing},
            )
        bounds_cache[iso] = bounds_map
        bounds_cache.move_to_end(iso)
        if len(bounds_cache) > CACHE_COUNTRIES_MAX:
            cache_evictions += 1
            bounds_cache.popitem(last=False)
        return bounds_map

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
                rows_total = batch.num_rows
            else:
                merchant_ids = batch.get_column("merchant_id").to_numpy()
                country_isos = batch.get_column("legal_country_iso").to_numpy()
                site_orders = batch.get_column("site_order").to_numpy()
                tile_ids = batch.get_column("tile_id").to_numpy()
                rows_total = batch.height

            unique_pairs: dict[str, set[int]] = {}
            for iso_val, tile_val in zip(country_isos, tile_ids):
                iso = str(iso_val)
                unique_pairs.setdefault(iso, set()).add(int(tile_val))

            bounds_map_by_iso: dict[str, dict[int, tuple[float, float, float, float, float, float]]] = {}
            for iso, tile_set in unique_pairs.items():
                bounds_map_by_iso[iso] = _get_bounds(iso, tile_set)

            for idx in range(rows_total):
                key = (int(merchant_ids[idx]), str(country_isos[idx]), int(site_orders[idx]))
                tile_id = int(tile_ids[idx])
                counts["sites_total_s5"] += 1

                if last_key is not None:
                    if key == last_key:
                        _emit_failure_event(
                            logger,
                            "E703_DUP_KEY",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "s5_duplicate_key", "key": key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E703_DUP_KEY",
                            "S7",
                            MODULE_NAME,
                            {"detail": "s5_duplicate_key", "key": key},
                        )
                    if key < last_key:
                        _emit_failure_event(
                            logger,
                            "E706_WRITER_SORT_VIOLATION",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "s5_unsorted", "key": key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E706_WRITER_SORT_VIOLATION",
                            "S7",
                            MODULE_NAME,
                            {"detail": "s5_unsorted", "key": key},
                        )
                last_key = key

                if s6_stream.current is None:
                    _emit_failure_event(
                        logger,
                        "E701_ROW_MISSING",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "s6_missing_row", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E701_ROW_MISSING",
                        "S7",
                        MODULE_NAME,
                        {"detail": "s6_missing_row", "key": key},
                    )
                s6_key, s6_tile, delta_lat, delta_lon, s6_mf = s6_stream.current
                if s6_key < key:
                    _emit_failure_event(
                        logger,
                        "E702_ROW_EXTRA",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "s6_extra_row", "key": s6_key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E702_ROW_EXTRA",
                        "S7",
                        MODULE_NAME,
                        {"detail": "s6_extra_row", "key": s6_key},
                    )
                if s6_key > key:
                    _emit_failure_event(
                        logger,
                        "E701_ROW_MISSING",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "s6_missing_row", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E701_ROW_MISSING",
                        "S7",
                        MODULE_NAME,
                        {"detail": "s6_missing_row", "key": key},
                    )
                counts["sites_total_s6"] += 1
                if s6_mf != manifest_fingerprint:
                    validation_counters["path_embed_mismatches"] += 1
                    _emit_failure_event(
                        logger,
                        "E705_PARTITION_OR_IDENTITY",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "s6_manifest_fingerprint_mismatch", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E705_PARTITION_OR_IDENTITY",
                        "S7",
                        MODULE_NAME,
                        {"detail": "s6_manifest_fingerprint_mismatch", "key": key},
                    )
                if s6_tile != tile_id:
                    _emit_failure_event(
                        logger,
                        "E709_TILE_FK_VIOLATION",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "s5_s6_tile_mismatch", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E709_TILE_FK_VIOLATION",
                        "S7",
                        MODULE_NAME,
                        {"detail": "s5_s6_tile_mismatch", "key": key},
                    )

                if outlet_stream.current is None:
                    validation_counters["coverage_1a_miss_count"] += 1
                    _emit_failure_event(
                        logger,
                        "E708_1A_COVERAGE_FAIL",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "outlet_catalogue_missing_row", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E708_1A_COVERAGE_FAIL",
                        "S7",
                        MODULE_NAME,
                        {"detail": "outlet_catalogue_missing_row", "key": key},
                    )
                outlet_key, outlet_mf, outlet_seed = outlet_stream.current
                if outlet_key < key:
                    validation_counters["coverage_1a_miss_count"] += 1
                    _emit_failure_event(
                        logger,
                        "E708_1A_COVERAGE_FAIL",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "outlet_extra_row", "key": outlet_key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E708_1A_COVERAGE_FAIL",
                        "S7",
                        MODULE_NAME,
                        {"detail": "outlet_extra_row", "key": outlet_key},
                    )
                if outlet_key > key:
                    validation_counters["coverage_1a_miss_count"] += 1
                    _emit_failure_event(
                        logger,
                        "E708_1A_COVERAGE_FAIL",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "outlet_missing_row", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E708_1A_COVERAGE_FAIL",
                        "S7",
                        MODULE_NAME,
                        {"detail": "outlet_missing_row", "key": key},
                    )
                if outlet_mf != manifest_fingerprint:
                    validation_counters["path_embed_mismatches"] += 1
                    _emit_failure_event(
                        logger,
                        "E705_PARTITION_OR_IDENTITY",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "outlet_manifest_fingerprint_mismatch", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E705_PARTITION_OR_IDENTITY",
                        "S7",
                        MODULE_NAME,
                        {"detail": "outlet_manifest_fingerprint_mismatch", "key": key},
                    )
                if outlet_seed is not None and outlet_seed != seed:
                    validation_counters["path_embed_mismatches"] += 1
                    _emit_failure_event(
                        logger,
                        "E705_PARTITION_OR_IDENTITY",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "outlet_global_seed_mismatch", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E705_PARTITION_OR_IDENTITY",
                        "S7",
                        MODULE_NAME,
                        {"detail": "outlet_global_seed_mismatch", "key": key},
                    )
                validation_counters["coverage_1a_ok_count"] += 1

                iso = str(country_isos[idx])
                bounds_map = bounds_map_by_iso[iso]
                if tile_id not in bounds_map:
                    validation_counters["fk_tile_fail_count"] += 1
                    _emit_failure_event(
                        logger,
                        "E709_TILE_FK_VIOLATION",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "tile_bounds_missing", "legal_country_iso": iso, "tile_id": tile_id},
                    )
                    raise EngineFailure(
                        "F4",
                        "E709_TILE_FK_VIOLATION",
                        "S7",
                        MODULE_NAME,
                        {"legal_country_iso": iso, "tile_id": tile_id},
                    )
                validation_counters["fk_tile_ok_count"] += 1
                min_lon, max_lon, min_lat, max_lat, centroid_lon, centroid_lat = bounds_map[tile_id]
                lon = _normalize_lon(centroid_lon + delta_lon)
                lat = centroid_lat + delta_lat

                if not (min_lat - 1e-9 <= lat <= max_lat + 1e-9) or not _lon_in_bounds(
                    lon, min_lon, max_lon
                ):
                    validation_counters["inside_pixel_fail_count"] += 1
                    _emit_failure_event(
                        logger,
                        "E707_POINT_OUTSIDE_PIXEL",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": "point_outside_pixel", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E707_POINT_OUTSIDE_PIXEL",
                        "S7",
                        MODULE_NAME,
                        {"detail": "point_outside_pixel", "key": key},
                    )
                validation_counters["inside_pixel_ok_count"] += 1

                country_stats = by_country.setdefault(
                    iso, {"sites_s7": 0, "fk_tile_fail": 0, "outside_pixel": 0, "coverage_1a_miss": 0}
                )
                country_stats["sites_s7"] += 1

                batch_rows.append((key[0], key[1], key[2], tile_id, lon, lat))
                counts["sites_total_s7"] += 1

                if len(batch_rows) >= BATCH_SIZE:
                    _write_batch(batch_rows, batch_index, output_tmp, logger)
                    batch_index += 1
                    batch_rows = []

                progress.update(1)
                s6_stream.advance()
                outlet_stream.advance()

        if s6_stream.current is not None:
            _emit_failure_event(
                logger,
                "E702_ROW_EXTRA",
                int(seed),
                str(manifest_fingerprint),
                str(parameter_hash),
                str(run_id),
                {"detail": "s6_extra_row", "key": s6_stream.current[0]},
            )
            raise EngineFailure(
                "F4",
                "E702_ROW_EXTRA",
                "S7",
                MODULE_NAME,
                {"detail": "s6_extra_row", "key": s6_stream.current[0]},
            )
        if outlet_stream.current is not None:
            _emit_failure_event(
                logger,
                "E708_1A_COVERAGE_FAIL",
                int(seed),
                str(manifest_fingerprint),
                str(parameter_hash),
                str(run_id),
                {"detail": "outlet_extra_row", "key": outlet_stream.current[0]},
            )
            raise EngineFailure(
                "F4",
                "E708_1A_COVERAGE_FAIL",
                "S7",
                MODULE_NAME,
                {"detail": "outlet_extra_row", "key": outlet_stream.current[0]},
            )

        _write_batch(batch_rows, batch_index, output_tmp, logger)
    except Exception:
        if output_tmp.exists():
            shutil.rmtree(output_tmp, ignore_errors=True)
        raise

    _atomic_publish_dir(output_tmp, synthesis_root, logger, "s7_site_synthesis")
    timer.info("S7: site synthesis published rows=%d", counts["sites_total_s7"])

    run_summary = {
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "identity": {
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        "sizes": {
            "sites_total_s5": counts["sites_total_s5"],
            "sites_total_s6": counts["sites_total_s6"],
            "sites_total_s7": counts["sites_total_s7"],
            "parity_s5_s7_ok": counts["sites_total_s5"] == counts["sites_total_s7"],
            "parity_s5_s6_ok": counts["sites_total_s5"] == counts["sites_total_s6"],
        },
        "validation_counters": validation_counters,
        "by_country": by_country,
        "gates": {"outlet_catalogue_pass_flag_sha256": receipt_payload.get("flag_sha256_hex", "")},
        "pat": {
            "wall_seconds": time.monotonic() - start_wall,
            "cpu_seconds": time.process_time() - start_cpu,
            "rss_bytes": int(psutil.Process().memory_info().rss),
            "open_files_peak": len(psutil.Process().open_files()),
        },
        "cache": {
            "tile_bounds_cache_hits": cache_hits,
            "tile_bounds_cache_misses": cache_misses,
            "tile_bounds_cache_evictions": cache_evictions,
        },
        "ingress_versions": {
            "s5_site_tile_assignment": s5_entry.get("version"),
            "s6_site_jitter": s6_entry.get("version"),
            "tile_bounds": tile_bounds_entry.get("version"),
            "outlet_catalogue": outlet_entry.get("version"),
            "s3_requirements_policy": s3_policy.policy_version,
        },
        "country_filter_policy": {
            "policy_path": str(s3_policy_path),
            "policy_version": s3_policy.policy_version,
            "enabled": s3_policy.enabled,
            "denylist_country_iso": sorted(s3_policy.denylist_country_iso),
        },
    }
    _validate_payload(schema_1b, "#/control/s7_run_summary", run_summary)
    summary_tmp = summary_path.parent / f"{summary_path.stem}.{uuid.uuid4().hex}.tmp"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(summary_tmp, run_summary)
    _atomic_publish_file(summary_tmp, summary_path, logger, "s7_run_summary")
    timer.info("S7: run summary written (parity + validation counters)")

    return S7Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        synthesis_root=synthesis_root,
        run_summary_path=summary_path,
    )
