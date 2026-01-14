"""S8 runner for Segment 1B site_locations egress."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import polars as pl
import psutil
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
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro


MODULE_NAME = "1B.S8.site_locations"
BATCH_SIZE = 200_000


@dataclass(frozen=True)
class S8Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    site_locations_root: Path
    run_summary_path: Path


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


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    receipts = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not receipts:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1]


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


def _schema_node(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    return node


def _schema_from_pack(schema_pack: dict, path: str, defs_extra: Optional[dict] = None) -> dict:
    node = _schema_node(schema_pack, path)
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": _merge_defs(schema_pack.get("$defs", {}), defs_extra or {}),
    }
    schema.update(node)
    return normalize_nullable_schema(schema)


def _merge_defs(primary: dict, extra: dict) -> dict:
    merged = dict(extra or {})
    merged.update(primary or {})
    return merged


def _normalize_ref(ref: str) -> str:
    if ref.startswith("schemas.layer1.yaml#/$defs/"):
        return "#/$defs/" + ref.split("/$defs/")[1]
    if ref.startswith("schemas.1B.yaml#/$defs/"):
        return "#/$defs/" + ref.split("/$defs/")[1]
    return ref


def _column_schema(column: dict) -> dict:
    if "$ref" in column:
        schema: dict = {"$ref": _normalize_ref(column["$ref"])}
    else:
        col_type = column.get("type")
        if col_type == "array":
            items = column.get("items") or {}
            schema = {"type": "array", "items": items}
        elif col_type in ("string", "integer", "number", "boolean"):
            schema = {"type": col_type}
        else:
            raise SchemaValidationError(f"Unsupported column type '{col_type}' for S8 schema.", [])
    for key in (
        "pattern",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "enum",
        "minLength",
        "maxLength",
        "const",
    ):
        if key in column:
            schema[key] = column[key]
    if column.get("nullable"):
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _table_row_schema(schema_pack: dict, path: str, defs_extra: Optional[dict] = None) -> dict:
    node = _schema_node(schema_pack, path)
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
        "$defs": _merge_defs(schema_pack.get("$defs", {}), defs_extra or {}),
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    return normalize_nullable_schema(schema)


def _assert_schema_ref(
    schema_ref: Optional[str],
    schema_1b: dict,
    schema_layer1: dict,
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
            "E808_DICT_SCHEMA_MISMATCH",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
        raise EngineFailure(
            "F4",
            "E808_DICT_SCHEMA_MISMATCH",
            "S8",
            MODULE_NAME,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
    try:
        if schema_ref.startswith("schemas.1B.yaml#"):
            _schema_node(schema_1b, schema_ref.split("#", 1)[1])
        elif schema_ref.startswith("schemas.layer1.yaml#"):
            _schema_node(schema_layer1, schema_ref.split("#", 1)[1])
        else:
            raise SchemaValidationError(f"Unknown schema_ref prefix: {schema_ref}", [])
    except Exception as exc:
        _emit_failure_event(
            logger,
            "E808_DICT_SCHEMA_MISMATCH",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref, "error": str(exc)},
        )
        raise EngineFailure(
            "F4",
            "E808_DICT_SCHEMA_MISMATCH",
            "S8",
            MODULE_NAME,
            {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
        )


def _assert_alignment(
    entry: dict,
    schema_pack: dict,
    schema_path: str,
    dataset_id: str,
    logger,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> None:
    node = _schema_node(schema_pack, schema_path)
    partitioning = entry.get("partitioning") or []
    ordering = entry.get("ordering") or []
    if node.get("partition_keys") and list(node["partition_keys"]) != list(partitioning):
        _emit_failure_event(
            logger,
            "E808_DICT_SCHEMA_MISMATCH",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {
                "detail": "partitioning_mismatch",
                "dataset_id": dataset_id,
                "dict_partitioning": partitioning,
                "schema_partition_keys": node.get("partition_keys"),
            },
        )
        raise EngineFailure(
            "F4",
            "E808_DICT_SCHEMA_MISMATCH",
            "S8",
            MODULE_NAME,
            {"detail": "partitioning_mismatch", "dataset_id": dataset_id},
        )
    if node.get("sort_keys") and list(node["sort_keys"]) != list(ordering):
        _emit_failure_event(
            logger,
            "E808_DICT_SCHEMA_MISMATCH",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {
                "detail": "ordering_mismatch",
                "dataset_id": dataset_id,
                "dict_ordering": ordering,
                "schema_sort_keys": node.get("sort_keys"),
            },
        )
        raise EngineFailure(
            "F4",
            "E808_DICT_SCHEMA_MISMATCH",
            "S8",
            MODULE_NAME,
            {"detail": "ordering_mismatch", "dataset_id": dataset_id},
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
        "event": "S8_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S8_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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


def _iter_parquet_batches(paths: list[Path], columns: list[str]) -> Iterator[pl.DataFrame]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for batch in pf.iter_batches(columns=columns, batch_size=BATCH_SIZE):
                    yield pl.from_arrow(batch)
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


def _write_batch(rows: list[tuple], batch_index: int, output_tmp: Path, logger) -> None:
    if not rows:
        return
    df = pl.DataFrame(
        rows,
        schema=[
            ("merchant_id", pl.UInt64),
            ("legal_country_iso", pl.Utf8),
            ("site_order", pl.Int32),
            ("lon_deg", pl.Float64),
            ("lat_deg", pl.Float64),
        ],
        orient="row",
    )
    path = output_tmp / f"part-{batch_index:05d}.parquet"
    df.write_parquet(path, compression="zstd", row_group_size=100000)
    logger.info("S8: wrote %d rows to %s", df.height, path)


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    final_root.parent.mkdir(parents=True, exist_ok=True)
    if final_root.exists():
        existing_files = sorted(path.relative_to(final_root) for path in final_root.rglob("*"))
        new_files = sorted(path.relative_to(tmp_root) for path in tmp_root.rglob("*"))
        if existing_files != new_files:
            raise EngineFailure(
                "F4",
                "E810_PUBLISH_POSTURE",
                "S8",
                MODULE_NAME,
                {"detail": f"{label} partition exists with different file list"},
            )
        for rel in existing_files:
            existing_path = final_root / rel
            new_path = tmp_root / rel
            if existing_path.is_file() and existing_path.read_bytes() != new_path.read_bytes():
                raise EngineFailure(
                    "F4",
                    "E810_PUBLISH_POSTURE",
                    "S8",
                    MODULE_NAME,
                    {"detail": f"{label} partition exists with different content"},
                )
        logger.info("S8: %s already exists; identical content; skipping publish.", label)
        shutil.rmtree(tmp_root, ignore_errors=True)
        return
    tmp_root.replace(final_root)
    logger.info("S8: published %s to %s", label, final_root)


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        if final_path.read_bytes() != tmp_path.read_bytes():
            raise EngineFailure(
                "F4",
                "E810_PUBLISH_POSTURE",
                "S8",
                MODULE_NAME,
                {"detail": f"{label} exists with different content"},
            )
        logger.info("S8: %s already exists; identical content; skipping publish.", label)
        tmp_path.unlink(missing_ok=True)
        return
    tmp_path.replace(final_path)
    logger.info("S8: published %s to %s", label, final_path)


def run_s8(config: EngineConfig, run_id: Optional[str] = None) -> S8Result:
    logger = get_logger("engine.layers.l1.seg_1B.s8_site_locations.l2.runner")
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
    external_roots = config.external_roots or (config.repo_root,)

    s7_entry = find_dataset_entry(dictionary, "s7_site_synthesis").entry
    site_locations_entry = find_dataset_entry(dictionary, "site_locations").entry
    summary_entry = find_dataset_entry(dictionary, "s8_run_summary").entry

    for dataset_id, entry in (
        ("s7_site_synthesis", s7_entry),
        ("site_locations", site_locations_entry),
        ("s8_run_summary", summary_entry),
    ):
        _assert_schema_ref(
            entry.get("schema_ref"),
            schema_1b,
            schema_layer1,
            dataset_id,
            logger,
            int(seed),
            str(manifest_fingerprint),
            str(parameter_hash),
            str(run_id),
        )

    _assert_alignment(
        site_locations_entry,
        schema_1b,
        "egress/site_locations",
        "site_locations",
        logger,
        int(seed),
        str(manifest_fingerprint),
        str(parameter_hash),
        str(run_id),
    )
    _assert_alignment(
        s7_entry,
        schema_1b,
        "plan/s7_site_synthesis",
        "s7_site_synthesis",
        logger,
        int(seed),
        str(manifest_fingerprint),
        str(parameter_hash),
        str(run_id),
    )

    final_in_layer = site_locations_entry.get("lineage", {}).get("final_in_layer")
    if not final_in_layer:
        _emit_failure_event(
            logger,
            "E811_FINAL_FLAG_MISMATCH",
            int(seed),
            str(manifest_fingerprint),
            str(parameter_hash),
            str(run_id),
            {"detail": "site_locations not marked final_in_layer"},
        )
        raise EngineFailure(
            "F4",
            "E811_FINAL_FLAG_MISMATCH",
            "S8",
            MODULE_NAME,
            {"detail": "site_locations not marked final_in_layer"},
        )

    s7_root = _resolve_dataset_path(s7_entry, run_paths, external_roots, tokens)
    s8_root = _resolve_dataset_path(
        site_locations_entry,
        run_paths,
        external_roots,
        {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint)},
    )
    summary_path = _resolve_dataset_path(
        summary_entry,
        run_paths,
        external_roots,
        {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint)},
    )
    if "parameter_hash=" in str(s8_root):
        _emit_failure_event(
            logger,
            "E809_PARTITION_SHIFT_VIOLATION",
            int(seed),
            str(manifest_fingerprint),
            str(parameter_hash),
            str(run_id),
            {"detail": "parameter_hash_in_egress_path", "path": str(s8_root)},
        )
        raise EngineFailure(
            "F4",
            "E809_PARTITION_SHIFT_VIOLATION",
            "S8",
            MODULE_NAME,
            {"detail": "parameter_hash_in_egress_path", "path": str(s8_root)},
        )

    logger.info("S8: egress inputs resolved (S7 site synthesis -> site_locations)")
    logger.info("S8: egress is order-free and fingerprint-scoped (no inter-country ordering)")

    s7_files = _list_parquet_files(s7_root)
    s7_rows_total = _count_parquet_rows(s7_files)
    logger.info(
        "S8: S7 rows=%s (each row becomes one site_locations row)",
        s7_rows_total if s7_rows_total is not None else "unknown",
    )

    output_tmp = run_paths.tmp_root / f"s8_site_locations_{uuid.uuid4().hex}"
    output_tmp.mkdir(parents=True, exist_ok=True)

    row_schema = _table_row_schema(schema_1b, "egress/site_locations", schema_layer1.get("$defs", {}))
    row_validator = Draft202012Validator(row_schema)

    last_key: Optional[tuple[int, str, int]] = None
    batch_rows: list[tuple] = []
    batch_index = 0

    counts = {"rows_s7": 0, "rows_s8": 0}
    validation_counters = {
        "schema_fail_count": 0,
        "path_embed_mismatches": 0,
        "writer_sort_violations": 0,
        "order_leak_indicators": 0,
    }
    by_country: dict[str, dict[str, int | bool]] = {}

    progress = _ProgressTracker(
        s7_rows_total,
        logger,
        "S8 egress progress sites_processed (site_locations rows)",
    )
    start_wall = time.monotonic()
    start_cpu = time.process_time()

    try:
        for batch in _iter_parquet_batches(
            s7_files, ["merchant_id", "legal_country_iso", "site_order", "lon_deg", "lat_deg"]
        ):
            merchant_ids = batch.get_column("merchant_id").to_numpy()
            country_isos = batch.get_column("legal_country_iso").to_numpy()
            site_orders = batch.get_column("site_order").to_numpy()
            lons = batch.get_column("lon_deg").to_numpy()
            lats = batch.get_column("lat_deg").to_numpy()

            for idx in range(batch.height):
                key = (int(merchant_ids[idx]), str(country_isos[idx]), int(site_orders[idx]))
                if last_key is not None:
                    if key == last_key:
                        _emit_failure_event(
                            logger,
                            "E803_DUP_KEY",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "duplicate_key", "key": key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E803_DUP_KEY",
                            "S8",
                            MODULE_NAME,
                            {"detail": "duplicate_key", "key": key},
                        )
                    if key < last_key:
                        validation_counters["writer_sort_violations"] += 1
                        _emit_failure_event(
                            logger,
                            "E806_WRITER_SORT_VIOLATION",
                            int(seed),
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            str(run_id),
                            {"detail": "writer_sort_violation", "key": key},
                        )
                        raise EngineFailure(
                            "F4",
                            "E806_WRITER_SORT_VIOLATION",
                            "S8",
                            MODULE_NAME,
                            {"detail": "writer_sort_violation", "key": key},
                        )
                last_key = key

                row = {
                    "merchant_id": int(merchant_ids[idx]),
                    "legal_country_iso": str(country_isos[idx]),
                    "site_order": int(site_orders[idx]),
                    "lon_deg": float(lons[idx]),
                    "lat_deg": float(lats[idx]),
                }
                errors = list(row_validator.iter_errors(row))
                if errors:
                    validation_counters["schema_fail_count"] += 1
                    _emit_failure_event(
                        logger,
                        "E804_SCHEMA_VIOLATION",
                        int(seed),
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        str(run_id),
                        {"detail": errors[0].message, "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "E804_SCHEMA_VIOLATION",
                        "S8",
                        MODULE_NAME,
                        {"detail": errors[0].message, "key": key},
                    )

                counts["rows_s7"] += 1
                counts["rows_s8"] += 1
                country_stats = by_country.setdefault(
                    str(country_isos[idx]), {"rows_s7": 0, "rows_s8": 0, "parity_ok": True}
                )
                country_stats["rows_s7"] += 1
                country_stats["rows_s8"] += 1

                batch_rows.append(
                    (row["merchant_id"], row["legal_country_iso"], row["site_order"], row["lon_deg"], row["lat_deg"])
                )
                if len(batch_rows) >= BATCH_SIZE:
                    _write_batch(batch_rows, batch_index, output_tmp, logger)
                    batch_index += 1
                    batch_rows = []
                progress.update(1)

        _write_batch(batch_rows, batch_index, output_tmp, logger)
    except Exception:
        if output_tmp.exists():
            shutil.rmtree(output_tmp, ignore_errors=True)
        raise

    _atomic_publish_dir(output_tmp, s8_root, logger, "site_locations")
    timer.info("S8: published site_locations rows=%d (order-free egress)", counts["rows_s8"])

    for stats in by_country.values():
        stats["parity_ok"] = stats["rows_s7"] == stats["rows_s8"]

    run_summary = {
        "identity": {
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash_consumed": parameter_hash,
        },
        "sizes": {
            "rows_s7": counts["rows_s7"],
            "rows_s8": counts["rows_s8"],
            "parity_ok": counts["rows_s7"] == counts["rows_s8"],
        },
        "validation_counters": validation_counters,
        "by_country": by_country,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash_consumed": parameter_hash,
        "pat": {
            "wall_seconds": time.monotonic() - start_wall,
            "cpu_seconds": time.process_time() - start_cpu,
            "rss_bytes": int(psutil.Process().memory_info().rss),
            "open_files_peak": len(psutil.Process().open_files()),
        },
    }

    summary_schema = _schema_from_pack(schema_1b, "control/s8_run_summary")
    summary_validator = Draft202012Validator(summary_schema)
    summary_errors = list(summary_validator.iter_errors(run_summary))
    if summary_errors:
        raise EngineFailure(
            "F4",
            "E804_SCHEMA_VIOLATION",
            "S8",
            MODULE_NAME,
            {"detail": summary_errors[0].message},
        )

    summary_tmp = summary_path.parent / f"{summary_path.stem}.{uuid.uuid4().hex}.tmp"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(summary_tmp, run_summary)
    _atomic_publish_file(summary_tmp, summary_path, logger, "s8_run_summary")
    timer.info("S8: run summary written (parity + validation counters)")

    return S8Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        site_locations_root=s8_root,
        run_summary_path=summary_path,
    )


__all__ = ["S8Result", "run_s8"]
