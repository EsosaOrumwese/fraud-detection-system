"""S3 requirements runner for Segment 1B."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np
import polars as pl
import psutil
import yaml
from jsonschema import Draft202012Validator

try:  # Optional fast row-group scanning.
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pc = None
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.loader import find_dataset_entry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt


MODULE_NAME = "1B.s3_requirements"
BATCH_SIZE = 1_000_000


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    requirements_path: Path
    run_report_path: Path


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

    def info(self, message: str) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(self, total: int, logger, label: str) -> None:
        self._total = max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < 0.5 and self._processed < self._total:
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
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


def _close_parquet_reader(pfile) -> None:
    reader = getattr(pfile, "reader", None)
    if reader and hasattr(reader, "close"):
        reader.close()


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
    return schema


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


def _validate_payload(schema_pack: dict, path: str, payload: dict) -> None:
    schema = _schema_from_pack(schema_pack, path)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        detail = errors[0].message if errors else "schema validation failed"
        raise SchemaValidationError(detail, [{"message": detail}])


def _emit_failure_event(logger, code: str, seed: int, manifest_fingerprint: str, parameter_hash: str, detail: dict) -> None:
    payload = {
        "event": "S3_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
    }
    payload.update(detail)
    logger.error("S3_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _hash_partition(root: Path) -> tuple[str, int]:
    files = sorted(
        [path for path in root.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
    return hasher.hexdigest(), total_bytes


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                "S3",
                MODULE_NAME,
                {"detail": "partition_exists_nonidentical", "dataset": label},
            )
        logger.info("S3: %s partition already exists with identical bytes", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _select_open_files_counter(proc: psutil.Process) -> tuple[Callable[[], int], str]:
    def _open_files() -> int:
        return len(proc.open_files())

    try:
        _open_files()
        return _open_files, "open_files"
    except Exception:
        if hasattr(proc, "num_handles"):
            return proc.num_handles, "handles"
        if hasattr(proc, "num_fds"):
            return proc.num_fds, "fds"
        return lambda: 0, "unknown"


def _entry_version(entry: dict) -> Optional[str]:
    version = entry.get("version")
    if not version or not isinstance(version, str):
        return None
    if "{" in version:
        return None
    return version


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


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted([path for path in root.rglob("*.parquet") if path.is_file()])
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _load_tile_weight_countries(paths: list[Path]) -> set[str]:
    if _HAVE_PYARROW:
        countries: set[str] = set()
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    table = pf.read_row_group(rg, columns=["country_iso"])
                    values = table.column("country_iso").to_numpy(zero_copy_only=False)
                    countries.update(str(value) for value in values)
            finally:
                _close_parquet_reader(pf)
        return countries
    df = pl.read_parquet(paths, columns=["country_iso"])
    return set(df.get_column("country_iso").to_list())


def _write_batch(
    batch_rows: list[tuple[int, str, int]],
    batch_index: int,
    output_root: Path,
    logger,
) -> None:
    if not batch_rows:
        return
    part_path = output_root / f"part-{batch_index:05d}.parquet"
    merchant_ids, country_isos, n_sites = zip(*batch_rows)
    data = {
        "merchant_id": np.array(merchant_ids, dtype=np.uint64),
        "legal_country_iso": np.array(country_isos, dtype=object),
        "n_sites": np.array(n_sites, dtype=np.int64),
    }
    if _HAVE_PYARROW:
        import pyarrow as pa

        table = pa.Table.from_pydict(data)
        pq.write_table(table, part_path, compression="zstd", row_group_size=200000)
    else:
        df = pl.DataFrame(data)
        df.write_parquet(part_path, compression="zstd", row_group_size=200000)
    logger.info("S3: wrote %d rows to %s", len(batch_rows), part_path)


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l1.seg_1B.s3_requirements.l2.runner")
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
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s schemas=%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        schema_1b_path,
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": str(parameter_hash),
        "manifest_fingerprint": str(manifest_fingerprint),
        "run_id": str(run_id),
    }
    external_roots = config.external_roots or (config.repo_root,)

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1B").entry
    outlet_entry = find_dataset_entry(dictionary, "outlet_catalogue").entry
    tile_weights_entry = find_dataset_entry(dictionary, "tile_weights").entry
    s3_policy_entry = find_dataset_entry(dictionary, "s3_requirements_policy").entry
    iso_entry = find_dataset_entry(dictionary, "iso3166_canonical_2024").entry
    requirements_entry = find_dataset_entry(dictionary, "s3_requirements").entry
    run_report_entry = find_dataset_entry(dictionary, "s3_run_report").entry

    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, external_roots, tokens)
    if not receipt_path.exists():
        _emit_failure_event(
            logger,
            "E301_NO_PASS_FLAG",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "s0_gate_receipt_missing", "path": str(receipt_path)},
        )
        raise EngineFailure(
            "F4",
            "E301_NO_PASS_FLAG",
            "S3",
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
            {"detail": str(exc)},
        )
        raise EngineFailure(
            "F4",
            "E_RECEIPT_SCHEMA_INVALID",
            "S3",
            MODULE_NAME,
            {"detail": str(exc)},
        ) from exc
    if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
        _emit_failure_event(
            logger,
            "E306_TOKEN_MISMATCH",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "receipt_manifest_fingerprint_mismatch"},
        )
        raise EngineFailure(
            "F4",
            "E306_TOKEN_MISMATCH",
            "S3",
            MODULE_NAME,
            {"detail": "receipt_manifest_fingerprint_mismatch"},
        )
    sealed_inputs = receipt_payload.get("sealed_inputs") or []
    sealed_ids = {entry.get("id") for entry in sealed_inputs if isinstance(entry, dict)}
    required_sealed = {"outlet_catalogue", "iso3166_canonical_2024"}
    missing_sealed = sorted(required_sealed - sealed_ids)
    if missing_sealed:
        _emit_failure_event(
            logger,
            "E311_DISALLOWED_READ",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "sealed_inputs_missing", "missing": missing_sealed},
        )
        raise EngineFailure(
            "F4",
            "E311_DISALLOWED_READ",
            "S3",
            MODULE_NAME,
            {"detail": "sealed_inputs_missing", "missing": missing_sealed},
        )
    logger.info("S3: s0_gate_receipt validated (sealed_inputs=%d)", len(sealed_inputs))

    outlet_root = _resolve_dataset_path(outlet_entry, run_paths, external_roots, tokens)
    tile_weights_root = _resolve_dataset_path(
        tile_weights_entry,
        run_paths,
        external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    s3_policy_path = _resolve_dataset_path(s3_policy_entry, run_paths, external_roots, {})
    iso_path = _resolve_dataset_path(iso_entry, run_paths, external_roots, {})
    requirements_root = _resolve_dataset_path(requirements_entry, run_paths, external_roots, tokens)
    run_report_path = _resolve_dataset_path(run_report_entry, run_paths, external_roots, tokens)

    s3_policy_payload = _load_yaml(s3_policy_path)
    _validate_payload(schema_1b, "#/policy/s3_requirements_policy", s3_policy_payload)
    s3_policy = _parse_s3_policy(s3_policy_payload)
    country_denylist_set = set(s3_policy.denylist_country_iso) if s3_policy.enabled else set()
    logger.info(
        "S3: loaded requirements policy enabled=%s denylist_count=%d version=%s path=%s",
        s3_policy.enabled,
        len(country_denylist_set),
        s3_policy.policy_version,
        s3_policy_path,
    )

    if not outlet_root.exists():
        _emit_failure_event(
            logger,
            "E311_DISALLOWED_READ",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "outlet_catalogue_missing", "path": str(outlet_root)},
        )
        raise EngineFailure(
            "F4",
            "E311_DISALLOWED_READ",
            "S3",
            MODULE_NAME,
            {"path": str(outlet_root)},
        )

    iso_df = pl.read_parquet(iso_path, columns=["country_iso"])
    iso_set = set(iso_df.get_column("country_iso").to_list())
    unknown_policy_isos = sorted(country_denylist_set - iso_set)
    if unknown_policy_isos:
        _emit_failure_event(
            logger,
            "E315_POLICY_ISO_UNKNOWN",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "denylist_iso_not_in_iso3166", "policy_unknown_iso": unknown_policy_isos},
        )
        raise EngineFailure(
            "F4",
            "E315_POLICY_ISO_UNKNOWN",
            "S3",
            MODULE_NAME,
            {"detail": "denylist_iso_not_in_iso3166", "policy_unknown_iso": unknown_policy_isos},
        )
    ingress_versions = {
        "iso3166": _entry_version(iso_entry) or "",
        "s3_requirements_policy": s3_policy.policy_version,
    }

    tile_weight_files = _list_parquet_files(tile_weights_root)
    bytes_read_tile_weights_total = sum(path.stat().st_size for path in tile_weight_files)
    tw_start = time.monotonic()
    tile_weight_countries = _load_tile_weight_countries(tile_weight_files)
    tw_elapsed = time.monotonic() - tw_start
    logger.info(
        "S3: tile_weights coverage loaded countries=%d bytes=%d elapsed=%.2fs",
        len(tile_weight_countries),
        bytes_read_tile_weights_total,
        tw_elapsed,
    )
    if not tile_weight_countries:
        _emit_failure_event(
            logger,
            "E303_TILE_WEIGHT_COVERAGE",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "tile_weights_empty", "path": str(tile_weights_root)},
        )
        raise EngineFailure(
            "F4",
            "E303_TILE_WEIGHT_COVERAGE",
            "S3",
            MODULE_NAME,
            {"detail": "tile_weights_empty"},
        )

    outlet_files = _list_parquet_files(outlet_root)
    bytes_read_outlet_catalogue_total = sum(path.stat().st_size for path in outlet_files)

    total_rows = 0
    if _HAVE_PYARROW:
        for path in outlet_files:
            pf = pq.ParquetFile(path)
            try:
                total_rows += pf.metadata.num_rows
            finally:
                _close_parquet_reader(pf)
    tracker = _ProgressTracker(total_rows, logger, "S3 outlet_catalogue rows") if total_rows else None

    run_paths.tmp_root.mkdir(parents=True, exist_ok=True)
    requirements_tmp = run_paths.tmp_root / f"s3_requirements_{uuid.uuid4().hex}"
    requirements_tmp.mkdir(parents=True, exist_ok=True)

    wall_start = time.monotonic()
    cpu_start = time.process_time()
    proc = psutil.Process()
    open_files_counter, open_files_metric = _select_open_files_counter(proc)
    max_rss = proc.memory_info().rss
    open_files_peak = open_files_counter()
    logger.info("S3: PAT open_files metric=%s", open_files_metric)

    batch_rows: list[tuple[int, str, int]] = []
    batch_index = 0

    last_key: Optional[tuple[int, str]] = None
    last_merchant_id: Optional[int] = None
    merchants_total = 0
    countries_set: set[str] = set()
    dropped_countries_set: set[str] = set()
    rows_emitted = 0
    rows_dropped_policy = 0
    sites_dropped_policy = 0
    source_rows_total = 0

    open_mid: Optional[int] = None
    open_iso: Optional[str] = None
    open_count = 0
    open_expected = 1

    def _finalize_group(mid: int, iso: str, count: int) -> None:
        nonlocal last_key, last_merchant_id, merchants_total, rows_emitted, rows_dropped_policy, sites_dropped_policy
        key = (mid, iso)
        if last_key is not None and key < last_key:
            _emit_failure_event(
                logger,
                "E310_UNSORTED",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "writer_sort_violation", "merchant_id": mid, "legal_country_iso": iso},
            )
            raise EngineFailure(
                "F4",
                "E310_UNSORTED",
                "S3",
                MODULE_NAME,
                {"merchant_id": mid, "legal_country_iso": iso},
            )
        last_key = key
        if count <= 0:
            _emit_failure_event(
                logger,
                "E304_ZERO_SITES_ROW",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"merchant_id": mid, "legal_country_iso": iso},
            )
            raise EngineFailure(
                "F4",
                "E304_ZERO_SITES_ROW",
                "S3",
                MODULE_NAME,
                {"merchant_id": mid, "legal_country_iso": iso},
            )
        if country_denylist_set and iso in country_denylist_set:
            dropped_countries_set.add(iso)
            rows_dropped_policy += 1
            sites_dropped_policy += int(count)
            return
        if iso not in iso_set:
            _emit_failure_event(
                logger,
                "E302_ISO_FK",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"legal_country_iso": iso},
            )
            raise EngineFailure(
                "F4",
                "E302_ISO_FK",
                "S3",
                MODULE_NAME,
                {"legal_country_iso": iso},
            )
        if iso not in tile_weight_countries:
            _emit_failure_event(
                logger,
                "E303_TILE_WEIGHT_COVERAGE",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"legal_country_iso": iso},
            )
            raise EngineFailure(
                "F4",
                "E303_TILE_WEIGHT_COVERAGE",
                "S3",
                MODULE_NAME,
                {"legal_country_iso": iso},
            )
        if last_merchant_id is None or mid != last_merchant_id:
            merchants_total += 1
            last_merchant_id = mid
        countries_set.add(iso)
        batch_rows.append((mid, iso, count))
        rows_emitted += 1

    def _flush_batch() -> None:
        nonlocal batch_index, batch_rows
        if not batch_rows:
            return
        _write_batch(batch_rows, batch_index, requirements_tmp, logger)
        batch_index += 1
        batch_rows = []

    if not _HAVE_PYARROW:
        logger.info("S3: pyarrow unavailable; loading outlet_catalogue via Polars streaming fallback.")
        outlet_scan = pl.scan_parquet(outlet_files)
        columns = ["merchant_id", "legal_country_iso", "site_order", "manifest_fingerprint"]
        if "global_seed" in outlet_scan.schema:
            columns.append("global_seed")
        scan = outlet_scan.select(columns)
        df = scan.collect(streaming=True)
        source_rows_total = df.height
        mf_mismatch = df.filter(pl.col("manifest_fingerprint") != manifest_fingerprint)
        if mf_mismatch.height > 0:
            _emit_failure_event(
                logger,
                "E306_TOKEN_MISMATCH",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "manifest_fingerprint mismatch in outlet_catalogue"},
            )
            raise EngineFailure(
                "F4",
                "E306_TOKEN_MISMATCH",
                "S3",
                MODULE_NAME,
                {"detail": "manifest_fingerprint mismatch in outlet_catalogue"},
            )
        if "global_seed" in df.columns:
            gs_mismatch = df.filter(pl.col("global_seed") != seed)
            if gs_mismatch.height > 0:
                _emit_failure_event(
                    logger,
                    "E306_TOKEN_MISMATCH",
                    seed,
                    manifest_fingerprint,
                    str(parameter_hash),
                    {"detail": "global_seed mismatch in outlet_catalogue"},
                )
                raise EngineFailure(
                    "F4",
                    "E306_TOKEN_MISMATCH",
                    "S3",
                    MODULE_NAME,
                    {"detail": "global_seed mismatch in outlet_catalogue"},
                )
        logger.info("S3: outlet_catalogue path-embed parity verified (polars)")
        merchant_ids = df.get_column("merchant_id").to_numpy()
        countries = df.get_column("legal_country_iso").to_numpy()
        site_orders = df.get_column("site_order").to_numpy()
        changes = (merchant_ids[1:] != merchant_ids[:-1]) | (countries[1:] != countries[:-1])
        boundaries = np.nonzero(changes)[0] + 1
        starts = np.concatenate(([0], boundaries))
        ends = np.concatenate((boundaries, [merchant_ids.size]))
        for idx, (start, end) in enumerate(zip(starts, ends)):
            seg_mid = int(merchant_ids[start])
            seg_iso = str(countries[start])
            seg_orders = site_orders[start:end]
            if idx == 0 and open_mid is not None and seg_mid == open_mid and seg_iso == open_iso:
                if int(seg_orders[0]) != open_expected or not np.all(np.diff(seg_orders) == 1):
                    _emit_failure_event(
                        logger,
                        "E314_SITE_ORDER_INTEGRITY",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        {"merchant_id": open_mid, "legal_country_iso": open_iso},
                    )
                    raise EngineFailure(
                        "F4",
                        "E314_SITE_ORDER_INTEGRITY",
                        "S3",
                        MODULE_NAME,
                        {"merchant_id": open_mid, "legal_country_iso": open_iso},
                    )
                open_count += int(seg_orders.size)
                open_expected = int(seg_orders[-1]) + 1
            else:
                if open_mid is not None:
                    _finalize_group(open_mid, open_iso, open_count)
                if int(seg_orders[0]) != 1 or not np.all(np.diff(seg_orders) == 1):
                    _emit_failure_event(
                        logger,
                        "E314_SITE_ORDER_INTEGRITY",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        {"merchant_id": seg_mid, "legal_country_iso": seg_iso},
                    )
                    raise EngineFailure(
                        "F4",
                        "E314_SITE_ORDER_INTEGRITY",
                        "S3",
                        MODULE_NAME,
                        {"merchant_id": seg_mid, "legal_country_iso": seg_iso},
                    )
                open_mid = seg_mid
                open_iso = seg_iso
                open_count = int(seg_orders.size)
                open_expected = int(seg_orders[-1]) + 1
            if idx < len(starts) - 1:
                _finalize_group(open_mid, open_iso, open_count)
                open_mid = None
                open_iso = None
                open_count = 0
                open_expected = 1
            if len(batch_rows) >= BATCH_SIZE:
                _flush_batch()
        if open_mid is not None:
            _finalize_group(open_mid, open_iso, open_count)
        _flush_batch()
        rss_now = proc.memory_info().rss
        max_rss = max(max_rss, rss_now)
        open_files_peak = max(open_files_peak, open_files_counter())
    else:
        for path in outlet_files:
            pf = pq.ParquetFile(path)
            schema_names = pf.schema.names
            has_global_seed = "global_seed" in schema_names
            columns = ["merchant_id", "legal_country_iso", "site_order", "manifest_fingerprint"]
            if has_global_seed:
                columns.append("global_seed")
            for rg in range(pf.num_row_groups):
                table = pf.read_row_group(rg, columns=columns)
                source_rows_total += table.num_rows
                if tracker:
                    tracker.update(table.num_rows)

                mf_col = table.column("manifest_fingerprint")
                bad_mf = pc.any(
                    pc.or_(pc.is_null(mf_col), pc.not_equal(mf_col, manifest_fingerprint))
                ).as_py()
                if bad_mf:
                    _emit_failure_event(
                        logger,
                        "E306_TOKEN_MISMATCH",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        {"detail": "manifest_fingerprint mismatch in outlet_catalogue"},
                    )
                    raise EngineFailure(
                        "F4",
                        "E306_TOKEN_MISMATCH",
                        "S3",
                        MODULE_NAME,
                        {"detail": "manifest_fingerprint mismatch in outlet_catalogue"},
                    )
                if has_global_seed:
                    gs_col = table.column("global_seed")
                    bad_seed = pc.any(
                        pc.or_(pc.is_null(gs_col), pc.not_equal(gs_col, seed))
                    ).as_py()
                    if bad_seed:
                        _emit_failure_event(
                            logger,
                            "E306_TOKEN_MISMATCH",
                            seed,
                            manifest_fingerprint,
                            str(parameter_hash),
                            {"detail": "global_seed mismatch in outlet_catalogue"},
                        )
                        raise EngineFailure(
                            "F4",
                            "E306_TOKEN_MISMATCH",
                            "S3",
                            MODULE_NAME,
                            {"detail": "global_seed mismatch in outlet_catalogue"},
                        )

                merchant_ids = table.column("merchant_id").to_numpy(zero_copy_only=False)
                countries = table.column("legal_country_iso").to_numpy(zero_copy_only=False)
                site_orders = table.column("site_order").to_numpy(zero_copy_only=False)
                if merchant_ids.size == 0:
                    continue
                changes = (merchant_ids[1:] != merchant_ids[:-1]) | (countries[1:] != countries[:-1])
                boundaries = np.nonzero(changes)[0] + 1
                starts = np.concatenate(([0], boundaries))
                ends = np.concatenate((boundaries, [merchant_ids.size]))

                for idx, (start, end) in enumerate(zip(starts, ends)):
                    seg_mid = int(merchant_ids[start])
                    seg_iso = str(countries[start])
                    seg_orders = site_orders[start:end]

                    if idx == 0 and open_mid is not None and seg_mid == open_mid and seg_iso == open_iso:
                        if int(seg_orders[0]) != open_expected or not np.all(np.diff(seg_orders) == 1):
                            _emit_failure_event(
                                logger,
                                "E314_SITE_ORDER_INTEGRITY",
                                seed,
                                manifest_fingerprint,
                                str(parameter_hash),
                                {"merchant_id": open_mid, "legal_country_iso": open_iso},
                            )
                            raise EngineFailure(
                                "F4",
                                "E314_SITE_ORDER_INTEGRITY",
                                "S3",
                                MODULE_NAME,
                                {"merchant_id": open_mid, "legal_country_iso": open_iso},
                            )
                        open_count += int(seg_orders.size)
                        open_expected = int(seg_orders[-1]) + 1
                    else:
                        if open_mid is not None:
                            _finalize_group(open_mid, open_iso, open_count)
                        if int(seg_orders[0]) != 1 or not np.all(np.diff(seg_orders) == 1):
                            _emit_failure_event(
                                logger,
                                "E314_SITE_ORDER_INTEGRITY",
                                seed,
                                manifest_fingerprint,
                                str(parameter_hash),
                                {"merchant_id": seg_mid, "legal_country_iso": seg_iso},
                            )
                            raise EngineFailure(
                                "F4",
                                "E314_SITE_ORDER_INTEGRITY",
                                "S3",
                                MODULE_NAME,
                                {"merchant_id": seg_mid, "legal_country_iso": seg_iso},
                            )
                        open_mid = seg_mid
                        open_iso = seg_iso
                        open_count = int(seg_orders.size)
                        open_expected = int(seg_orders[-1]) + 1

                    if idx < len(starts) - 1:
                        _finalize_group(open_mid, open_iso, open_count)
                        open_mid = None
                        open_iso = None
                        open_count = 0
                        open_expected = 1

                    if len(batch_rows) >= BATCH_SIZE:
                        _flush_batch()

                rss_now = proc.memory_info().rss
                max_rss = max(max_rss, rss_now)
                open_files_peak = max(open_files_peak, open_files_counter())
            _close_parquet_reader(pf)

        if open_mid is not None:
            _finalize_group(open_mid, open_iso, open_count)
        _flush_batch()
        logger.info("S3: outlet_catalogue path-embed parity verified (pyarrow)")

    determinism_hash, determinism_bytes = _hash_partition(requirements_tmp)
    determinism_receipt = {
        "partition_path": str(requirements_root),
        "sha256_hex": determinism_hash,
        "bytes_hashed": determinism_bytes,
    }

    _atomic_publish_dir(requirements_tmp, requirements_root, logger, "s3_requirements")

    wall_total = time.monotonic() - wall_start
    cpu_total = time.process_time() - cpu_start

    run_report = {
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "country_filter_policy": {
            "policy_path": str(s3_policy_path),
            "policy_version": s3_policy.policy_version,
            "enabled": s3_policy.enabled,
            "denylist_country_iso": sorted(s3_policy.denylist_country_iso),
        },
        "rows_emitted": rows_emitted,
        "rows_dropped_by_policy": rows_dropped_policy,
        "sites_dropped_by_policy": sites_dropped_policy,
        "countries_dropped_by_policy_total": len(dropped_countries_set),
        "countries_dropped_by_policy": sorted(dropped_countries_set),
        "merchants_total": merchants_total,
        "countries_total": len(countries_set),
        "source_rows_total": source_rows_total,
        "ingress_versions": ingress_versions,
        "determinism_receipt": determinism_receipt,
        "pat": {
            "wall_clock_seconds_total": wall_total,
            "cpu_seconds_total": cpu_total,
            "bytes_read_outlet_catalogue_total": bytes_read_outlet_catalogue_total,
            "bytes_read_tile_weights_total": bytes_read_tile_weights_total,
            "max_worker_rss_bytes": max_rss,
            "open_files_peak": open_files_peak,
            "open_files_metric": open_files_metric,
            "workers_used": 1,
        },
    }
    _validate_payload(schema_1b, "#/control/s3_run_report", run_report)
    run_report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(run_report_path, run_report)
    timer.info("S3: run report written")

    return S3Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        requirements_path=requirements_root,
        run_report_path=run_report_path,
    )
