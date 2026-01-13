"""S0 gate-in runner for Segment 1B."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from jsonschema import Draft202012Validator

try:  # Optional fast row-group scanning.
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pc = None
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.jsonschema_adapter import validate_dataframe
from engine.contracts.loader import (
    find_dataset_entry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    HashingError,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro


MODULE_NAME = "1B.s0_gate"
_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")


@dataclass(frozen=True)
class InputAsset:
    asset_id: str
    path: Path
    schema_ref: str
    version_tag: str
    partition: dict[str, str]
    partition_keys: list[str]


@dataclass(frozen=True)
class S0GateResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    receipt_path: Path
    sealed_inputs_path: Path


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


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _table_pack(schema_pack: dict, path: str) -> tuple[dict, str]:
    node: dict = schema_pack
    parts = path.strip("#/").split("/")
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            raise ContractError(f"Schema section not found: {path}")
        node = node[part]
    table_name = parts[-1]
    table_def = node.get(table_name)
    if not isinstance(table_def, dict):
        raise ContractError(f"Schema section not found: {path}")
    pack = {"$id": schema_pack.get("$id", ""), "$defs": schema_pack.get("$defs", {})}
    pack[table_name] = table_def
    return pack, table_name


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    unevaluated = None
    if isinstance(schema.get("allOf"), list):
        for subschema in schema["allOf"]:
            if not isinstance(subschema, dict):
                continue
            if "unevaluatedProperties" in subschema:
                if unevaluated is None:
                    unevaluated = subschema["unevaluatedProperties"]
                subschema.pop("unevaluatedProperties", None)
    if unevaluated is not None and "unevaluatedProperties" not in schema:
        schema["unevaluatedProperties"] = unevaluated
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
    raise ContractError(f"Unsupported array item type '{item_type}' for receipt schema.")


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
            raise ContractError(f"Unsupported column type '{col_type}' for receipt schema.")
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
            raise ContractError(f"Column missing name in {path}.")
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


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    candidates = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return candidates[-1]


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


def _version_tag(entry: dict, tokens: dict[str, str]) -> str:
    version = entry.get("version")
    if not version or version in ("TBD", "null"):
        return "unknown"
    version = str(version)
    for key, value in tokens.items():
        version = version.replace(f"{{{key}}}", value)
    return version


def _partition_values(entry: dict, tokens: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    partition_keys = list(entry.get("partitioning") or [])
    partition = {key: tokens[key] for key in partition_keys if key in tokens}
    return partition, partition_keys


def _require_governance_fields(entry: dict, dataset_id: str) -> None:
    if not entry.get("licence"):
        raise EngineFailure(
            "F4",
            "E_DICTIONARY_RESOLUTION_FAILED",
            "S0",
            MODULE_NAME,
            {"detail": f"missing licence for {dataset_id}"},
            dataset_id=dataset_id,
        )
    if entry.get("retention_days") in (None, "", "TBD"):
        raise EngineFailure(
            "F4",
            "E_DICTIONARY_RESOLUTION_FAILED",
            "S0",
            MODULE_NAME,
            {"detail": f"missing retention_days for {dataset_id}"},
            dataset_id=dataset_id,
        )


def _schema_anchor_exists(schema_pack: dict, ref: str) -> None:
    anchor = ref.split("#", 1)[-1]
    node: dict = schema_pack
    for part in anchor.strip("/").split("/"):
        if part not in node:
            raise ContractError(f"Schema anchor missing: {ref}")
        node = node[part]


def _validate_schema_ref(
    schema_ref: str | None,
    schema_ingress: dict,
    schema_1a: dict,
    schema_1b: dict,
    schema_layer1: dict,
) -> str:
    if not schema_ref:
        raise ContractError("Missing schema_ref.")
    if schema_ref.startswith("schemas.ingress.layer1.yaml#"):
        _schema_anchor_exists(schema_ingress, schema_ref)
    elif schema_ref.startswith("schemas.1A.yaml#"):
        _schema_anchor_exists(schema_1a, schema_ref)
    elif schema_ref.startswith("schemas.1B.yaml#"):
        _schema_anchor_exists(schema_1b, schema_ref)
    elif schema_ref.startswith("schemas.layer1.yaml#"):
        _schema_anchor_exists(schema_layer1, schema_ref)
    else:
        raise ContractError(f"Unknown schema ref: {schema_ref}")
    return schema_ref


def _validate_index(
    bundle_root: Path, index_path: Path, schema_1a: dict, logger
) -> list[dict]:
    payload = _load_json(index_path)
    if not isinstance(payload, list):
        raise EngineFailure(
            "F4",
            "E_INDEX_INVALID",
            "S0",
            MODULE_NAME,
            {"detail": "index.json must be a list"},
        )
    pack, table_name = _table_pack(schema_1a, "validation/validation_bundle_index_1A")
    try:
        validate_dataframe(payload, pack, table_name)
    except SchemaValidationError as exc:
        detail = exc.errors[0] if exc.errors else {}
        raise EngineFailure(
            "F4",
            "E_INDEX_INVALID",
            "S0",
            MODULE_NAME,
            {"detail": detail},
        ) from exc
    paths = []
    artifact_ids = set()
    for entry in payload:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "E_INDEX_INVALID",
                "S0",
                MODULE_NAME,
                {"detail": "index entry missing path"},
            )
        try:
            path.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineFailure(
                "F4",
                "E_INDEX_INVALID",
                "S0",
                MODULE_NAME,
                {"detail": f"non-ascii path: {path}"},
            ) from exc
        if path.startswith(("/", "\\")) or ".." in Path(path).parts or ":" in path:
            raise EngineFailure(
                "F4",
                "E_INDEX_INVALID",
                "S0",
                MODULE_NAME,
                {"detail": f"non-relative path: {path}"},
            )
        if "\\" in path:
            raise EngineFailure(
                "F4",
                "E_INDEX_INVALID",
                "S0",
                MODULE_NAME,
                {"detail": f"backslash path not allowed: {path}"},
            )
        paths.append(path)
        artifact_id = entry.get("artifact_id")
        if artifact_id:
            if artifact_id in artifact_ids:
                raise EngineFailure(
                    "F4",
                    "E_INDEX_INVALID",
                    "S0",
                    MODULE_NAME,
                    {"detail": f"duplicate artifact_id: {artifact_id}"},
                )
            artifact_ids.add(artifact_id)
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "E_INDEX_INVALID",
            "S0",
            MODULE_NAME,
            {"detail": "duplicate path entries in index.json"},
        )
    bundle_files = [
        path
        for path in bundle_root.rglob("*")
        if path.is_file() and path.name != "_passed.flag"
    ]
    bundle_rel = {path.relative_to(bundle_root).as_posix() for path in bundle_files}
    index_paths = set(paths)
    missing = sorted(bundle_rel - index_paths)
    extra = sorted(index_paths - bundle_rel)
    if missing or extra:
        raise EngineFailure(
            "F4",
            "E_INDEX_INVALID",
            "S0",
            MODULE_NAME,
            {"detail": {"missing": missing, "extra": extra}},
        )
    logger.info(
        "S0: index.json validated (entries=%d, files=%d)", len(paths), len(bundle_rel)
    )
    return payload


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> str:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    for path in paths:
        file_path = bundle_root / path
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def _parse_pass_flag(path: Path) -> str:
    if not path.exists():
        raise EngineFailure(
            "F4",
            "E_PASS_MISSING",
            "S0",
            MODULE_NAME,
            {"detail": f"missing _passed.flag at {path}"},
        )
    content = path.read_text(encoding="ascii")
    match = _FLAG_PATTERN.match(content.strip())
    if not match:
        raise EngineFailure(
            "F4",
            "E_FLAG_FORMAT_INVALID",
            "S0",
            MODULE_NAME,
            {"detail": "invalid _passed.flag format"},
        )
    return match.group(1)


def _hash_files(paths: list[Path], logger, label: str) -> str:
    if not paths:
        raise HashingError(f"No files found for hash: {label}")
    hasher = hashlib.sha256()
    tracker = _ProgressTracker(len(paths), logger, f"{label} files")
    for path in sorted(paths, key=lambda item: item.as_posix()):
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        tracker.update(1)
    return hasher.hexdigest()


def _list_dataset_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    if root.is_dir():
        parquet_files = sorted(root.glob("*.parquet"))
        if parquet_files:
            return parquet_files
        files = sorted([path for path in root.iterdir() if path.is_file()])
        if files:
            return files
    raise InputResolutionError(f"No files found under dataset path: {root}")


def _scan_outlet_catalogue(
    outlet_root: Path, manifest_fingerprint: str, seed: int, logger
) -> None:
    files = _list_dataset_files(outlet_root)
    if not _HAVE_PYARROW:
        logger.info(
            "S0: pyarrow unavailable; scanning outlet_catalogue via Polars without per-row progress logs."
        )
        import polars as pl

        scan = pl.scan_parquet(files)
        columns = ["manifest_fingerprint"]
        if "global_seed" in scan.schema:
            columns.append("global_seed")
        df = scan.select(columns).collect(streaming=True)
        if df.filter(pl.col("manifest_fingerprint") != manifest_fingerprint).height > 0:
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S0",
                MODULE_NAME,
                {"detail": "manifest_fingerprint mismatch in outlet_catalogue"},
                dataset_id="outlet_catalogue",
            )
        if "global_seed" in df.columns:
            if df.filter(pl.col("global_seed") != seed).height > 0:
                raise EngineFailure(
                    "F4",
                    "E_PATH_EMBED_MISMATCH",
                    "S0",
                    MODULE_NAME,
                    {"detail": "global_seed mismatch in outlet_catalogue"},
                    dataset_id="outlet_catalogue",
                )
        logger.info("S0: outlet_catalogue path-embed parity verified (polars).")
        return

    total_rows = 0
    parquet_files: list[Path] = []
    for path in files:
        if path.suffix == ".parquet":
            pf = pq.ParquetFile(path)
            total_rows += pf.metadata.num_rows
            parquet_files.append(path)
    tracker = _ProgressTracker(total_rows, logger, "S0 outlet_catalogue rows")
    for path in parquet_files:
        pf = pq.ParquetFile(path)
        schema_names = pf.schema.names
        if "manifest_fingerprint" not in schema_names:
            raise EngineFailure(
                "F4",
                "E_PATH_EMBED_MISMATCH",
                "S0",
                MODULE_NAME,
                {"detail": "manifest_fingerprint column missing in outlet_catalogue"},
                dataset_id="outlet_catalogue",
            )
        has_global_seed = "global_seed" in schema_names
        columns = ["manifest_fingerprint"] + (["global_seed"] if has_global_seed else [])
        for rg in range(pf.num_row_groups):
            table = pf.read_row_group(rg, columns=columns)
            mf_col = table.column("manifest_fingerprint")
            bad_mf = pc.any(
                pc.or_(pc.is_null(mf_col), pc.not_equal(mf_col, manifest_fingerprint))
            ).as_py()
            if bad_mf:
                raise EngineFailure(
                    "F4",
                    "E_PATH_EMBED_MISMATCH",
                    "S0",
                    MODULE_NAME,
                    {"detail": "manifest_fingerprint mismatch in outlet_catalogue"},
                    dataset_id="outlet_catalogue",
                )
            if has_global_seed:
                gs_col = table.column("global_seed")
                bad_seed = pc.any(
                    pc.or_(pc.is_null(gs_col), pc.not_equal(gs_col, seed))
                ).as_py()
                if bad_seed:
                    raise EngineFailure(
                        "F4",
                        "E_PATH_EMBED_MISMATCH",
                        "S0",
                        MODULE_NAME,
                        {"detail": "global_seed mismatch in outlet_catalogue"},
                        dataset_id="outlet_catalogue",
                    )
            tracker.update(table.num_rows)
    logger.info("S0: outlet_catalogue path-embed parity verified.")


def _write_json_atomic(path: Path, payload: object, logger) -> None:
    payload_bytes = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing == payload_bytes:
            logger.info("S0: output already exists and is byte-identical: %s", path)
            return
        raise EngineFailure(
            "F4",
            "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
            "S0",
            MODULE_NAME,
            {"detail": f"non-identical output exists at {path}"},
        )
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_bytes(payload_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(path)
    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except OSError:
            pass


def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l1.seg_1B.s0_gate.l2.runner")
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
    timer.info(f"S0: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_ingress_path, schema_ingress = load_schema_pack(
        source, "1A", "ingress.layer1"
    )

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        schema_1b_path,
        schema_1a_path,
        schema_layer1_path,
        schema_ingress_path,
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": str(parameter_hash),
        "manifest_fingerprint": str(manifest_fingerprint),
        "run_id": str(run_id),
    }
    external_roots = config.external_roots or (config.repo_root,)

    required_ids = [
        "validation_bundle_1A",
        "validation_passed_flag_1A",
        "outlet_catalogue",
        "s3_candidate_set",
        "iso3166_canonical_2024",
        "world_countries",
        "population_raster_2025",
        "tz_world_2025a",
        "license_map",
        "s2_tile_weights_policy",
    ]

    entries = {}
    for dataset_id in required_ids:
        try:
            entry = find_dataset_entry(dictionary, dataset_id).entry
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "E_DICTIONARY_RESOLUTION_FAILED",
                "S0",
                MODULE_NAME,
                {"detail": str(exc)},
                dataset_id=dataset_id,
            ) from exc
        _require_governance_fields(entry, dataset_id)
        try:
            _validate_schema_ref(
                entry.get("schema_ref"),
                schema_ingress,
                schema_1a,
                schema_1b,
                schema_layer1,
            )
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "E_SCHEMA_RESOLUTION_FAILED",
                "S0",
                MODULE_NAME,
                {"detail": str(exc), "schema_ref": entry.get("schema_ref")},
                dataset_id=dataset_id,
            ) from exc
        entries[dataset_id] = entry

    bundle_entry = entries["validation_bundle_1A"]
    bundle_root = _resolve_dataset_path(bundle_entry, run_paths, external_roots, tokens)
    if not bundle_root.exists():
        raise EngineFailure(
            "F4",
            "E_BUNDLE_MISSING",
            "S0",
            MODULE_NAME,
            {"detail": f"bundle missing at {bundle_root}"},
            dataset_id="validation_bundle_1A",
        )
    index_path = bundle_root / "index.json"
    if not index_path.exists():
        raise EngineFailure(
            "F4",
            "E_INDEX_MISSING",
            "S0",
            MODULE_NAME,
            {"detail": f"index.json missing at {index_path}"},
            dataset_id="validation_bundle_1A",
        )

    index_entries = _validate_index(bundle_root, index_path, schema_1a, logger)
    timer.info("S0: validated index.json against schema + file listing")

    bundle_hash = _bundle_hash(bundle_root, index_entries)
    timer.info("S0: computed validation bundle hash")

    flag_entry = entries["validation_passed_flag_1A"]
    flag_path = _resolve_dataset_path(flag_entry, run_paths, external_roots, tokens)
    expected_hash = _parse_pass_flag(flag_path)
    if expected_hash != bundle_hash:
        raise EngineFailure(
            "F4",
            "E_FLAG_HASH_MISMATCH",
            "S0",
            MODULE_NAME,
            {"detail": "bundle hash does not match _passed.flag"},
            dataset_id="validation_passed_flag_1A",
        )
    timer.info("S0: PASS flag verified")

    param_payload = _load_json(bundle_root / "parameter_hash_resolved.json")
    if param_payload.get("parameter_hash") != parameter_hash:
        raise EngineFailure(
            "F4",
            "E_PATH_EMBED_MISMATCH",
            "S0",
            MODULE_NAME,
            {"detail": "parameter_hash mismatch vs bundle"},
        )
    mf_payload = _load_json(bundle_root / "manifest_fingerprint_resolved.json")
    if mf_payload.get("manifest_fingerprint") != manifest_fingerprint:
        raise EngineFailure(
            "F4",
            "E_PATH_EMBED_MISMATCH",
            "S0",
            MODULE_NAME,
            {"detail": "manifest_fingerprint mismatch vs bundle"},
        )

    outlet_entry = entries["outlet_catalogue"]
    outlet_root = _resolve_dataset_path(outlet_entry, run_paths, external_roots, tokens)
    if not outlet_root.exists():
        raise EngineFailure(
            "F4",
            "E_PARTITION_MISPLACED",
            "S0",
            MODULE_NAME,
            {"detail": f"outlet_catalogue missing at {outlet_root}"},
            dataset_id="outlet_catalogue",
        )
    _scan_outlet_catalogue(outlet_root, manifest_fingerprint, seed, logger)

    sealed_assets: list[InputAsset] = []
    digest_by_id: dict[str, str] = {}

    bundle_path_value = bundle_entry.get("path", "").replace(
        "{manifest_fingerprint}", manifest_fingerprint
    )
    if not bundle_path_value:
        raise EngineFailure(
            "F4",
            "E_DICTIONARY_RESOLUTION_FAILED",
            "S0",
            MODULE_NAME,
            {"detail": "validation_bundle_1A path missing"},
            dataset_id="validation_bundle_1A",
        )

    egress_checksums_path = bundle_root / "egress_checksums.json"
    outlet_digest = None
    if egress_checksums_path.exists():
        egress_payload = _load_json(egress_checksums_path)
        if (
            egress_payload.get("dataset_id") == "outlet_catalogue"
            and str(egress_payload.get("manifest_fingerprint")) == manifest_fingerprint
            and int(egress_payload.get("seed", seed)) == seed
        ):
            outlet_digest = str(egress_payload.get("composite_sha256_hex") or "")
            if outlet_digest:
                logger.info("S0: using outlet_catalogue composite hash from egress_checksums.json")
        else:
            logger.info("S0: egress_checksums identity mismatch; recomputing outlet_catalogue hash")
    if not outlet_digest:
        outlet_files = _list_dataset_files(outlet_root)
        outlet_digest = _hash_files(outlet_files, logger, "outlet_catalogue")

    candidate_entry = entries["s3_candidate_set"]
    candidate_root = _resolve_dataset_path(candidate_entry, run_paths, external_roots, tokens)
    if not candidate_root.exists():
        raise EngineFailure(
            "F4",
            "E_REFERENCE_SURFACE_MISSING",
            "S0",
            MODULE_NAME,
            {"detail": f"s3_candidate_set missing at {candidate_root}"},
            dataset_id="s3_candidate_set",
        )
    candidate_digest = _hash_files(
        _list_dataset_files(candidate_root), logger, "s3_candidate_set"
    )

    for dataset_id in required_ids:
        entry = entries[dataset_id]
        path = _resolve_dataset_path(entry, run_paths, external_roots, tokens)
        if not path.exists():
            raise EngineFailure(
                "F4",
                "E_REFERENCE_SURFACE_MISSING",
                "S0",
                MODULE_NAME,
                {"detail": f"missing path {path}"},
                dataset_id=dataset_id,
            )
        if dataset_id == "validation_bundle_1A":
            digest_by_id[dataset_id] = bundle_hash
        elif dataset_id == "validation_passed_flag_1A":
            digest_by_id[dataset_id] = sha256_file(path).sha256_hex
        elif dataset_id == "outlet_catalogue":
            digest_by_id[dataset_id] = outlet_digest
        elif dataset_id == "s3_candidate_set":
            digest_by_id[dataset_id] = candidate_digest
        else:
            digest_by_id[dataset_id] = sha256_file(path).sha256_hex
        partition, partition_keys = _partition_values(entry, tokens)
        sealed_assets.append(
            InputAsset(
                asset_id=dataset_id,
                path=path,
                schema_ref=entry.get("schema_ref"),
                version_tag=_version_tag(entry, tokens),
                partition=partition,
                partition_keys=partition_keys,
            )
        )

    sealed_payload = []
    for asset in sealed_assets:
        sealed_payload.append(
            {
                "asset_id": asset.asset_id,
                "version_tag": asset.version_tag,
                "sha256_hex": digest_by_id[asset.asset_id],
                "path": asset.path.as_posix(),
                "partition": dict(asset.partition),
                "schema_ref": asset.schema_ref,
            }
        )
    sealed_payload.sort(key=lambda item: (item["asset_id"], item["path"]))

    receipt_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "validation_bundle_path": bundle_path_value,
        "flag_sha256_hex": expected_hash,
        "verified_at_utc": utc_now_rfc3339_micro(),
        "sealed_inputs": [
            {
                "id": asset.asset_id,
                "partition": list(asset.partition_keys),
                "schema_ref": asset.schema_ref or "unknown",
            }
            for asset in sealed_assets
        ],
        "notes": None,
    }

    try:
        receipt_schema = _table_row_schema(schema_1b, "validation/s0_gate_receipt")
        receipt_validator = Draft202012Validator(receipt_schema)
        receipt_errors = list(receipt_validator.iter_errors(receipt_payload))
        if receipt_errors:
            raise SchemaValidationError(
                receipt_errors[0].message, [{"message": receipt_errors[0].message}]
            )
        _validate_payload(schema_1b, "validation/sealed_inputs_1B", sealed_payload)
    except (SchemaValidationError, ContractError) as exc:
        raise EngineFailure(
            "F4",
            "E_RECEIPT_SCHEMA_INVALID",
            "S0",
            MODULE_NAME,
            {"detail": str(exc)},
        ) from exc

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1B").entry
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, external_roots, tokens)
    sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_1B").entry
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, external_roots, tokens)

    _write_json_atomic(sealed_inputs_path, sealed_payload, logger)
    _write_json_atomic(receipt_path, receipt_payload, logger)
    timer.info("S0: published sealed_inputs_1B and s0_gate_receipt_1B")

    return S0GateResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        receipt_path=receipt_path,
        sealed_inputs_path=sealed_inputs_path,
    )
