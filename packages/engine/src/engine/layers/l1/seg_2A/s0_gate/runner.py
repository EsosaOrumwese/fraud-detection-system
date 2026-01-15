"""S0 gate-in runner for Segment 2A."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import yaml
from jsonschema import Draft202012Validator

try:  # Optional GeoParquet metadata access.
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
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


MODULE_NAME = "2A.s0_gate"
SEGMENT = "2A"
STATE = "S0"
_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_RELEASE_TAG_PATTERN = re.compile(r"^20[0-9]{2}[a-z]?$")


@dataclass(frozen=True)
class SealedAsset:
    asset_id: str
    asset_kind: str
    path: Path
    schema_ref: str
    version_tag: str
    partition: dict[str, str]
    partition_keys: list[str]
    catalog_path: str
    license_class: str
    sha256_hex: str
    size_bytes: int
    basename: str


@dataclass(frozen=True)
class S0GateResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    receipt_path: Path
    sealed_inputs_path: Path
    run_report_path: Path
    determinism_receipt: dict[str, object]


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


def _emit_event(
    logger,
    event: str,
    manifest_fingerprint: Optional[str],
    severity: str,
    **fields: object,
) -> None:
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


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> object:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

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


def _rewrite_external_refs(schema: object, ref_map: dict[str, str]) -> None:
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str):
            for prefix, replacement in ref_map.items():
                if ref.startswith(prefix):
                    schema["$ref"] = ref.replace(prefix, replacement, 1)
                    break
        for value in schema.values():
            _rewrite_external_refs(value, ref_map)
    elif isinstance(schema, list):
        for item in schema:
            _rewrite_external_refs(item, ref_map)


def _collect_external_defs(schema: object, prefix: str) -> set[str]:
    needed: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(prefix):
                tail = ref.split("#/$defs/", 1)
                if len(tail) == 2:
                    name = tail[1].split("/", 1)[0]
                    if name:
                        needed.add(name)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
    return needed


def _collect_local_defs(schema: object) -> set[str]:
    needed: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref.split("#/$defs/", 1)[1].split("/", 1)[0]
                if name:
                    needed.add(name)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
    return needed


def _resolve_defs(
    schema_pack: dict,
    external_pack: dict,
    names: Iterable[str],
) -> dict:
    defs: dict[str, object] = {}
    external_defs = external_pack.get("$defs") or {}
    local_defs = schema_pack.get("$defs") or {}
    for name in names:
        if name in external_defs:
            defs[name] = external_defs[name]
            continue
        local_def = local_defs.get(name)
        if isinstance(local_def, dict) and "$ref" not in local_def:
            defs[name] = local_def
            continue
        raise ContractError(f"External $defs missing: {name}")
    return defs


def _inline_external_refs(schema: object, external_pack: dict, prefix: str) -> None:
    external_defs = external_pack.get("$defs") or {}

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(prefix):
                tail = ref.split("#/$defs/", 1)
                if len(tail) == 2:
                    name = tail[1].split("/", 1)[0]
                    if name in external_defs:
                        replacement = copy.deepcopy(external_defs[name])
                        for key, value in list(node.items()):
                            if key != "$ref":
                                replacement[key] = value
                        node.clear()
                        node.update(replacement)
                        return
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)


def _prepare_table_pack_with_layer1_defs(
    schema_pack: dict,
    table_path: str,
    schema_layer1: dict,
    prefix: str,
) -> tuple[dict, str]:
    pack, table_name = _table_pack(schema_pack, table_path)
    pack = copy.deepcopy(pack)
    table_def = pack[table_name]
    needed = set()
    needed.update(_collect_external_defs(table_def, f"{prefix}#"))
    needed.update(_collect_local_defs(table_def))
    pack["$defs"] = _resolve_defs(schema_pack, schema_layer1, needed)
    _rewrite_external_refs(table_def, {f"{prefix}#": "#"})
    return pack, table_name


def _prepare_row_schema_with_layer1_defs(
    schema_pack: dict,
    schema_path: str,
    schema_layer1: dict,
    prefix: str,
) -> dict:
    row_schema = _table_row_schema(schema_pack, schema_path)
    needed = set()
    needed.update(_collect_external_defs(row_schema, f"{prefix}#"))
    needed.update(_collect_local_defs(row_schema))
    row_schema["$defs"] = _resolve_defs(schema_pack, schema_layer1, needed)
    _rewrite_external_refs(row_schema, {f"{prefix}#": "#"})
    return row_schema


def _validate_payload(
    schema_pack: dict,
    path: str,
    payload: object,
    ref_packs: Optional[dict[str, dict]] = None,
) -> None:
    base_schema = _schema_from_pack(schema_pack, path)
    schema: dict
    if base_schema.get("type") == "table":
        schema = None
        if ref_packs and "schemas.layer1.yaml" in ref_packs:
            schema = _prepare_row_schema_with_layer1_defs(
                schema_pack, path, ref_packs["schemas.layer1.yaml"], "schemas.layer1.yaml"
            )
        if schema is None:
            schema = _table_row_schema(schema_pack, path)
    else:
        schema = copy.deepcopy(base_schema)
        if ref_packs:
            for prefix, pack in ref_packs.items():
                _inline_external_refs(schema, pack, f"{prefix}#")
    schema = normalize_nullable_schema(schema)
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
    if resolved.startswith(("data/", "logs/", "reports/")):
        return run_paths.run_root / resolved
    if resolved.startswith("artefacts/"):
        return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=False)
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _render_catalog_path(entry: dict, tokens: dict[str, str]) -> str:
    path_template = entry.get("path") or ""
    rendered = path_template
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _resolve_version_tag(
    entry: dict,
    tokens: dict[str, str],
    dataset_id: str,
    fallback: Optional[str] = None,
) -> str:
    version = entry.get("version")
    if not version or version in ("TBD", "null"):
        if fallback is not None:
            return fallback
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {"detail": f"missing version tag for {dataset_id}"},
            dataset_id=dataset_id,
        )
    rendered = str(version)
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    if "{" in rendered or "}" in rendered:
        if fallback is not None:
            return fallback
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {"detail": f"unresolved version tag for {dataset_id}: {rendered}"},
            dataset_id=dataset_id,
        )
    if rendered.lower() in ("latest", "current"):
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {"detail": f"unpinned version tag for {dataset_id}: {rendered}"},
            dataset_id=dataset_id,
        )
    return rendered


def _partition_values(entry: dict, tokens: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    partition_keys = list(entry.get("partitioning") or [])
    partition = {key: tokens[key] for key in partition_keys if key in tokens}
    return partition, partition_keys


def _schema_anchor_exists(schema_pack: dict, ref: str) -> None:
    anchor = ref.split("#", 1)[-1]
    node: dict = schema_pack
    for part in anchor.strip("/").split("/"):
        if part not in node:
            raise ContractError(f"Schema anchor missing: {ref}")
        node = node[part]


def _validate_schema_ref(
    schema_ref: str | None,
    schema_2a: dict,
    schema_1a: dict,
    schema_1b: dict,
    schema_layer1: dict,
    schema_ingress: dict,
) -> str:
    if not schema_ref:
        raise ContractError("Missing schema_ref.")
    if schema_ref.startswith("schemas.2A.yaml#"):
        _schema_anchor_exists(schema_2a, schema_ref)
    elif schema_ref.startswith("schemas.1B.yaml#"):
        _schema_anchor_exists(schema_1b, schema_ref)
    elif schema_ref.startswith("schemas.1A.yaml#"):
        _schema_anchor_exists(schema_1a, schema_ref)
    elif schema_ref.startswith("schemas.layer1.yaml#"):
        _schema_anchor_exists(schema_layer1, schema_ref)
    elif schema_ref.startswith("schemas.ingress.layer1.yaml#"):
        _schema_anchor_exists(schema_ingress, schema_ref)
    else:
        raise ContractError(f"Unknown schema ref: {schema_ref}")
    return schema_ref


def _validate_index(
    bundle_root: Path,
    index_path: Path,
    schema_1a: dict,
    logger,
    manifest_fingerprint: str,
) -> list[dict]:
    payload = _load_json(index_path)
    if not isinstance(payload, list):
        raise EngineFailure(
            "F4",
            "2A-S0-003",
            STATE,
            MODULE_NAME,
            {"detail": "index.json must be a list", "path": str(index_path)},
        )
    pack, table_name = _table_pack(schema_1a, "validation/validation_bundle_index_1A")
    try:
        validate_dataframe(payload, pack, table_name)
    except SchemaValidationError as exc:
        detail = exc.errors[0] if exc.errors else {}
        raise EngineFailure(
            "F4",
            "2A-S0-003",
            STATE,
            MODULE_NAME,
            {"detail": detail, "path": str(index_path)},
        ) from exc
    paths = []
    artifact_ids = set()
    for entry in payload:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "2A-S0-003",
                STATE,
                MODULE_NAME,
                {"detail": "index entry missing path", "path": str(index_path)},
            )
        try:
            path.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineFailure(
                "F4",
                "2A-S0-003",
                STATE,
                MODULE_NAME,
                {"detail": f"non-ascii path: {path}", "path": str(index_path)},
            ) from exc
        if path.startswith(("/", "\\")) or ".." in Path(path).parts or ":" in path:
            raise EngineFailure(
                "F4",
                "2A-S0-003",
                STATE,
                MODULE_NAME,
                {"detail": f"non-relative path: {path}", "path": str(index_path)},
            )
        if "\\" in path:
            raise EngineFailure(
                "F4",
                "2A-S0-003",
                STATE,
                MODULE_NAME,
                {"detail": f"backslash path not allowed: {path}", "path": str(index_path)},
            )
        paths.append(path)
        artifact_id = entry.get("artifact_id")
        if artifact_id:
            if artifact_id in artifact_ids:
                raise EngineFailure(
                    "F4",
                    "2A-S0-003",
                    STATE,
                    MODULE_NAME,
                    {"detail": f"duplicate artifact_id: {artifact_id}", "path": str(index_path)},
                )
            artifact_ids.add(artifact_id)
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "2A-S0-003",
            STATE,
            MODULE_NAME,
            {"detail": "duplicate path entries in index.json", "path": str(index_path)},
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
            "2A-S0-003",
            STATE,
            MODULE_NAME,
            {"detail": {"missing": missing, "extra": extra}, "path": str(index_path)},
        )
    logger.info(
        "S0: index.json validated (entries=%d, files=%d) for manifest_fingerprint=%s",
        len(paths),
        len(bundle_rel),
        manifest_fingerprint,
    )
    return payload

def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> tuple[str, int]:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        file_path = bundle_root / path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "2A-S0-003",
                STATE,
                MODULE_NAME,
                {"detail": f"bundle file missing: {path}", "bundle_root": str(bundle_root)},
            )
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
    return hasher.hexdigest(), total_bytes


def _parse_pass_flag(path: Path) -> str:
    if not path.exists():
        raise EngineFailure(
            "F4",
            "2A-S0-001",
            STATE,
            MODULE_NAME,
            {"detail": f"missing _passed.flag at {path}"},
        )
    content = path.read_text(encoding="ascii")
    match = _FLAG_PATTERN.match(content.strip())
    if not match:
        raise EngineFailure(
            "F4",
            "2A-S0-001",
            STATE,
            MODULE_NAME,
            {"detail": "invalid _passed.flag format", "path": str(path)},
        )
    return match.group(1)


def _hash_paths(paths: list[Path], logger, label: str) -> tuple[str, int]:
    if not paths:
        raise HashingError(f"No files found for hash: {label}")
    hasher = hashlib.sha256()
    total_bytes = 0
    tracker = _ProgressTracker(len(paths), logger, f"{label} files")
    for path in sorted(paths, key=lambda item: item.as_posix()):
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
        tracker.update(1)
    return hasher.hexdigest(), total_bytes


def _list_files_recursive(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = [path for path in root.rglob("*") if path.is_file()]
    if not files:
        raise InputResolutionError(f"No files found under dataset path: {root}")
    return sorted(files, key=lambda path: path.as_posix())


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
                "2A-S0-062",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S0: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _atomic_publish_file(
    final_path: Path,
    payload_bytes: bytes,
    logger,
    label: str,
) -> None:
    if final_path.exists():
        if final_path.read_bytes() != payload_bytes:
            raise EngineFailure(
                "F4",
                "2A-S0-062",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        logger.info("S0: %s already exists and is identical; skipping publish.", label)
        return
    tmp_dir = final_path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / final_path.name
    tmp_path.write_bytes(payload_bytes)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)
    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

def _extract_geo_crs(path: Path) -> Optional[str]:
    if _HAVE_PYARROW:
        try:
            parquet_file = pq.ParquetFile(path)
            metadata = parquet_file.schema_arrow.metadata or {}
            crs_bytes = metadata.get(b"geo:crs")
            if crs_bytes:
                return crs_bytes.decode("utf-8")
        except Exception:
            pass
    try:
        import geopandas as gpd

        gdf = gpd.read_parquet(path)
        if gdf.crs is not None:
            return gdf.crs.to_string()
    except Exception:
        return None
    return None


def _is_wgs84(crs_text: Optional[str]) -> bool:
    if not crs_text:
        return False
    crs_norm = crs_text.upper().replace(" ", "")
    return crs_norm in {
        "EPSG:4326",
        "WGS84",
        "CRS84",
        "OGC:CRS84",
        "EPSG::4326",
    }


def _load_tz_world_metadata(path: Path) -> int:
    if _HAVE_PYARROW:
        try:
            parquet_file = pq.ParquetFile(path)
            return int(parquet_file.metadata.num_rows)
        except Exception:
            pass
    try:
        import geopandas as gpd

        gdf = gpd.read_parquet(path)
        return int(len(gdf))
    except Exception as exc:
        raise EngineFailure(
            "F4",
            "2A-S0-021",
            STATE,
            MODULE_NAME,
            {"detail": "unable to read tz_world metadata", "path": str(path)},
        ) from exc


def _load_tz_world_tzids(path: Path) -> set[str]:
    if _HAVE_PYARROW:
        try:
            table = pq.read_table(path, columns=["tzid"])
            tzids = table.column("tzid").to_pylist()
            return {
                tzid for tzid in tzids if isinstance(tzid, str) and tzid.strip()
            }
        except Exception:
            pass
    try:
        import geopandas as gpd

        gdf = gpd.read_parquet(path)
        tzids = gdf.get("tzid")
        if tzids is None:
            return set()
        return {tzid for tzid in tzids.tolist() if isinstance(tzid, str) and tzid.strip()}
    except Exception:
        return set()


def _resolve_release_dir(path: Path) -> tuple[Path, Path]:
    if path.is_file():
        return path.parent, path
    if not path.exists():
        raise InputResolutionError(f"tzdb_release path not found: {path}")
    if path.is_dir():
        candidates = [
            path / "tzdb_release.json",
            path / "tzdb_release.yaml",
            path / "tzdb_release.yml",
        ]
        matches = [candidate for candidate in candidates if candidate.exists()]
        if len(matches) == 1:
            return path, matches[0]
        if len(matches) > 1:
            raise EngineFailure(
                "F4",
                "2A-S0-014",
                STATE,
                MODULE_NAME,
                {"detail": "multiple tzdb_release metadata files", "path": str(path)},
            )
    raise EngineFailure(
        "F4",
        "2A-S0-014",
        STATE,
        MODULE_NAME,
        {"detail": "tzdb_release metadata file missing", "path": str(path)},
    )


def _resolve_release_tag_from_root(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
) -> str:
    path_template = entry.get("path") or ""
    if "{release_tag}" not in path_template:
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb_release path missing {release_tag} token", "path": path_template},
            dataset_id="tzdb_release",
        )
    base_template = path_template.split("{release_tag}", 1)[0]
    try:
        base_root = resolve_input_path(
            base_template, run_paths, external_roots, allow_run_local=False
        )
    except InputResolutionError as exc:
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb_release root not found", "path": base_template},
            dataset_id="tzdb_release",
        ) from exc
    candidates: list[Path] = []
    for child in base_root.iterdir():
        if not child.is_dir():
            continue
        if (
            (child / "tzdb_release.json").exists()
            or (child / "tzdb_release.yaml").exists()
            or (child / "tzdb_release.yml").exists()
        ):
            candidates.append(child)
    if not candidates:
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb_release metadata missing under root", "path": str(base_root)},
            dataset_id="tzdb_release",
        )
    if len(candidates) > 1:
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {
                "detail": "multiple tzdb_release candidates under root",
                "path": str(base_root),
                "candidates": [candidate.name for candidate in candidates],
            },
            dataset_id="tzdb_release",
        )
    return candidates[0].name


def _write_json(path: Path, payload: object) -> bytes:
    payload_bytes = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload_bytes)
    return payload_bytes


def _write_run_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _asset_kind_for(dataset_id: str, entry: dict) -> str:
    if dataset_id.endswith("_passed_flag_1B"):
        return "manifest"
    if dataset_id.startswith("validation_bundle"):
        return "bundle"
    path = (entry.get("path") or "").lower()
    if path.startswith("config/"):
        return "config"
    category = (entry.get("category") or "").lower()
    if category in ("policy", "config"):
        return "config"
    return "dataset"

def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l1.seg_2A.s0_gate.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = receipt.get("seed")
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if seed is None or parameter_hash is None or manifest_fingerprint is None:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")
    created_utc = receipt.get("created_utc") or utc_now_rfc3339_micro()
    warnings: list[str] = []

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)
    timer.info(f"S0: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    registry_path, registry = load_artefact_registry(source, SEGMENT)
    schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        registry_path,
        schema_2a_path,
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

    def _load_entry(dataset_id: str) -> tuple[dict, dict, str, str]:
        try:
            dataset_entry = find_dataset_entry(dictionary, dataset_id).entry
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "2A-S0-012",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "dataset_id": dataset_id},
                dataset_id=dataset_id,
            ) from exc
        try:
            artifact_entry = find_artifact_entry(registry, dataset_id).entry
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "2A-S0-013",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "dataset_id": dataset_id},
                dataset_id=dataset_id,
            ) from exc
        license_class = artifact_entry.get("license") or dataset_entry.get("licence")
        if not license_class:
            raise EngineFailure(
                "F4",
                "2A-S0-013",
                STATE,
                MODULE_NAME,
                {"detail": "license missing", "dataset_id": dataset_id},
                dataset_id=dataset_id,
            )
        if dataset_entry.get("licence") and dataset_entry.get("licence") != license_class:
            raise EngineFailure(
                "F4",
                "2A-S0-052",
                STATE,
                MODULE_NAME,
                {"detail": "license mismatch", "dataset_id": dataset_id},
                dataset_id=dataset_id,
            )
        schema_ref = dataset_entry.get("schema_ref")
        try:
            _validate_schema_ref(
                schema_ref,
                schema_2a,
                schema_1a,
                schema_1b,
                schema_layer1,
                schema_ingress,
            )
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "2A-S0-011",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "schema_ref": schema_ref, "dataset_id": dataset_id},
                dataset_id=dataset_id,
            ) from exc
        return dataset_entry, artifact_entry, schema_ref, license_class

    required_ids = [
        "validation_bundle_1B",
        "validation_passed_flag_1B",
        "site_locations",
        "tz_world_2025a",
        "tzdb_release",
        "tz_overrides",
        "tz_nudge",
    ]

    entries: dict[str, dict] = {}
    registry_entries: dict[str, dict] = {}
    schema_refs: dict[str, str] = {}
    license_classes: dict[str, str] = {}

    for dataset_id in required_ids:
        dataset_entry, registry_entry, schema_ref, license_class = _load_entry(dataset_id)
        entries[dataset_id] = dataset_entry
        registry_entries[dataset_id] = registry_entry
        schema_refs[dataset_id] = schema_ref
        license_classes[dataset_id] = license_class

    bundle_root = _resolve_dataset_path(
        entries["validation_bundle_1B"], run_paths, external_roots, tokens
    )
    if not bundle_root.exists():
        raise EngineFailure(
            "F4",
            "2A-S0-003",
            STATE,
            MODULE_NAME,
            {"detail": "validation_bundle_1B missing", "path": str(bundle_root)},
            dataset_id="validation_bundle_1B",
        )

    index_path = bundle_root / "index.json"
    index_entries = _validate_index(bundle_root, index_path, schema_1a, logger, str(manifest_fingerprint))
    bundle_hash, bundle_bytes = _bundle_hash(bundle_root, index_entries)

    flag_path = _resolve_dataset_path(
        entries["validation_passed_flag_1B"], run_paths, external_roots, tokens
    )
    flag_sha256 = _parse_pass_flag(flag_path)
    if flag_sha256 != bundle_hash:
        raise EngineFailure(
            "F4",
            "2A-S0-002",
            STATE,
            MODULE_NAME,
            {
                "detail": "flag digest mismatch",
                "expected": bundle_hash,
                "flag_sha256_hex": flag_sha256,
            },
            dataset_id="validation_passed_flag_1B",
        )

    if not _HEX64_PATTERN.match(flag_sha256):
        raise EngineFailure(
            "F4",
            "2A-S0-042",
            STATE,
            MODULE_NAME,
            {"detail": "flag_sha256_hex invalid", "value": flag_sha256},
            dataset_id="validation_passed_flag_1B",
        )
    bundle_catalog_path = _render_catalog_path(entries["validation_bundle_1B"], tokens)
    if f"manifest_fingerprint={manifest_fingerprint}" not in bundle_catalog_path:
        raise EngineFailure(
            "F4",
            "2A-S0-041",
            STATE,
            MODULE_NAME,
            {
                "detail": "validation_bundle_path does not embed manifest_fingerprint",
                "validation_bundle_path": bundle_catalog_path,
            },
            dataset_id="validation_bundle_1B",
        )
    _emit_validation(logger, manifest_fingerprint, "V-11", "pass")

    _emit_validation(logger, manifest_fingerprint, "V-01", "pass")
    _emit_validation(logger, manifest_fingerprint, "V-02", "pass")
    _emit_event(
        logger,
        "GATE",
        manifest_fingerprint,
        "INFO",
        result="verified",
        bundle_path=str(bundle_root),
        flag_sha256_hex=flag_sha256,
    )
    timer.info("S0: verified 1B PASS artefacts")

    sealed_assets: list[SealedAsset] = []
    sealed_inputs_for_receipt: list[dict] = []

    def _add_sealed_asset(dataset_id: str, path: Path, sha256_hex: str, size_bytes: int, version_tag: str) -> None:
        if not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "2A-S0-015",
                STATE,
                MODULE_NAME,
                {"detail": "invalid sha256 hex", "dataset_id": dataset_id, "sha256_hex": sha256_hex},
                dataset_id=dataset_id,
            )
        entry = entries[dataset_id]
        partition, partition_keys = _partition_values(entry, tokens)
        catalog_path = _render_catalog_path(entry, tokens)
        asset_kind = _asset_kind_for(dataset_id, entry)
        sealed_assets.append(
            SealedAsset(
                asset_id=dataset_id,
                asset_kind=asset_kind,
                path=path,
                schema_ref=schema_refs[dataset_id],
                version_tag=version_tag,
                partition=partition,
                partition_keys=partition_keys,
                catalog_path=catalog_path,
                license_class=license_classes[dataset_id],
                sha256_hex=sha256_hex,
                size_bytes=size_bytes,
                basename=dataset_id,
            )
        )
        sealed_inputs_for_receipt.append(
            {"id": dataset_id, "partition": partition_keys, "schema_ref": schema_refs[dataset_id]}
        )

    _emit_event(
        logger,
        "SEAL",
        manifest_fingerprint,
        "INFO",
        step="start",
        assets_total=len(required_ids),
    )

    _add_sealed_asset(
        "validation_bundle_1B",
        bundle_root,
        bundle_hash,
        bundle_bytes,
        _resolve_version_tag(entries["validation_bundle_1B"], tokens, "validation_bundle_1B"),
    )

    flag_digest = sha256_file(flag_path)
    _add_sealed_asset(
        "validation_passed_flag_1B",
        flag_path,
        flag_digest.sha256_hex,
        flag_digest.size_bytes,
        _resolve_version_tag(entries["validation_passed_flag_1B"], tokens, "validation_passed_flag_1B"),
    )

    site_locations_path = _resolve_dataset_path(
        entries["site_locations"], run_paths, external_roots, tokens
    )
    if f"manifest_fingerprint={manifest_fingerprint}" not in site_locations_path.as_posix():
        raise EngineFailure(
            "F4",
            "2A-S0-004",
            STATE,
            MODULE_NAME,
            {
                "detail": "site_locations manifest_fingerprint mismatch",
                "path": str(site_locations_path),
            },
            dataset_id="site_locations",
        )
    _emit_validation(logger, manifest_fingerprint, "V-03", "pass")
    site_files = _list_files_recursive(site_locations_path)
    site_digest, site_bytes = _hash_paths(site_files, logger, "site_locations")
    site_version = _resolve_version_tag(entries["site_locations"], tokens, "site_locations")
    _add_sealed_asset("site_locations", site_locations_path, site_digest, site_bytes, site_version)

    tz_world_path = _resolve_dataset_path(
        entries["tz_world_2025a"], run_paths, external_roots, tokens
    )
    tz_world_crs = _extract_geo_crs(tz_world_path)
    if not _is_wgs84(tz_world_crs):
        raise EngineFailure(
            "F4",
            "2A-S0-020",
            STATE,
            MODULE_NAME,
            {"detail": "tz_world CRS invalid", "crs": tz_world_crs, "path": str(tz_world_path)},
            dataset_id="tz_world_2025a",
        )
    tz_world_count = _load_tz_world_metadata(tz_world_path)
    if tz_world_count <= 0:
        raise EngineFailure(
            "F4",
            "2A-S0-021",
            STATE,
            MODULE_NAME,
            {"detail": "tz_world empty", "path": str(tz_world_path)},
            dataset_id="tz_world_2025a",
        )
    _emit_validation(logger, manifest_fingerprint, "V-07", "pass")
    tz_world_digest = sha256_file(tz_world_path)
    tz_world_version = _resolve_version_tag(entries["tz_world_2025a"], tokens, "tz_world_2025a")
    _add_sealed_asset(
        "tz_world_2025a",
        tz_world_path,
        tz_world_digest.sha256_hex,
        tz_world_digest.size_bytes,
        tz_world_version,
    )
    tzid_index = _load_tz_world_tzids(tz_world_path)
    tzid_index_present = bool(tzid_index)
    tzid_index_list = sorted(tzid_index) if tzid_index_present else []
    if tzid_index_present:
        logger.info(
            "S0: derived tzid index from tz_world (tzids=%s)",
            len(tzid_index_list),
        )
    else:
        logger.info("S0: tzid index unavailable; override membership not enforced")

    tzdb_entry = entries["tzdb_release"]
    tzdb_path_template = tzdb_entry.get("path") or ""
    if "{release_tag}" in tzdb_path_template and "release_tag" not in tokens:
        resolved_tag = _resolve_release_tag_from_root(
            tzdb_entry, run_paths, external_roots
        )
        tokens["release_tag"] = resolved_tag
        logger.info("S0: resolved tzdb_release tag=%s from artefacts root", resolved_tag)
    tzdb_root = _resolve_dataset_path(tzdb_entry, run_paths, external_roots, tokens)
    release_dir, release_meta_path = _resolve_release_dir(tzdb_root)
    tzdb_payload = _load_json(release_meta_path) if release_meta_path.suffix == ".json" else _load_yaml(release_meta_path)
    try:
        _validate_payload(
            schema_2a,
            "ingress/tzdb_release_v1",
            tzdb_payload,
            ref_packs={"schemas.layer1.yaml": schema_layer1},
        )
    except SchemaValidationError as exc:
        raise EngineFailure(
            "F4",
            "2A-S0-022",
            STATE,
            MODULE_NAME,
            {"detail": exc.errors, "path": str(release_meta_path)},
            dataset_id="tzdb_release",
        ) from exc

    release_tag = tzdb_payload.get("release_tag")
    archive_sha256 = tzdb_payload.get("archive_sha256")
    if not isinstance(release_tag, str) or not _RELEASE_TAG_PATTERN.match(release_tag):
        raise EngineFailure(
            "F4",
            "2A-S0-022",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb release tag invalid", "release_tag": release_tag},
            dataset_id="tzdb_release",
        )
    if "release_tag" in tokens and tokens["release_tag"] != release_tag:
        raise EngineFailure(
            "F4",
            "2A-S0-014",
            STATE,
            MODULE_NAME,
            {
                "detail": "tzdb release tag mismatch",
                "path_tag": tokens["release_tag"],
                "metadata_tag": release_tag,
            },
            dataset_id="tzdb_release",
        )
    tokens["release_tag"] = release_tag
    if not isinstance(archive_sha256, str) or not _HEX64_PATTERN.match(archive_sha256):
        raise EngineFailure(
            "F4",
            "2A-S0-023",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb archive sha256 invalid", "archive_sha256": archive_sha256},
            dataset_id="tzdb_release",
        )

    archive_candidates = sorted(
        [path for path in release_dir.iterdir() if path.is_file() and path.suffix in (".tar", ".gz", ".tgz")],
        key=lambda path: path.name,
    )
    archive_candidates = [path for path in archive_candidates if path.name.endswith((".tar.gz", ".tgz", ".tar"))]
    if len(archive_candidates) != 1:
        raise EngineFailure(
            "F4",
            "2A-S0-023",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb archive not uniquely identified", "path": str(release_dir)},
            dataset_id="tzdb_release",
        )
    archive_path = archive_candidates[0]
    archive_digest = sha256_file(archive_path)
    if archive_digest.sha256_hex != archive_sha256:
        raise EngineFailure(
            "F4",
            "2A-S0-023",
            STATE,
            MODULE_NAME,
            {
                "detail": "tzdb archive digest mismatch",
                "expected": archive_sha256,
                "actual": archive_digest.sha256_hex,
            },
            dataset_id="tzdb_release",
        )
    _emit_validation(logger, manifest_fingerprint, "V-08", "pass")

    tzdb_files = _list_files_recursive(release_dir)
    tzdb_digest, tzdb_bytes = _hash_paths(tzdb_files, logger, "tzdb_release")
    tzdb_version = release_tag
    _add_sealed_asset(
        "tzdb_release",
        release_dir,
        tzdb_digest,
        tzdb_bytes,
        tzdb_version,
    )

    overrides_path = _resolve_dataset_path(entries["tz_overrides"], run_paths, external_roots, tokens)
    overrides_payload = _load_yaml(overrides_path)
    try:
        _validate_payload(
            schema_2a,
            "policy/tz_overrides_v1",
            overrides_payload,
            ref_packs={"schemas.layer1.yaml": schema_layer1},
        )
    except SchemaValidationError as exc:
        raise EngineFailure(
            "F4",
            "2A-S0-030",
            STATE,
            MODULE_NAME,
            {"detail": exc.errors, "path": str(overrides_path)},
            dataset_id="tz_overrides",
        ) from exc

    seen_pairs = set()
    mcc_override = False
    for entry in overrides_payload:
        scope = entry.get("scope")
        target = entry.get("target")
        key = (scope, target)
        if key in seen_pairs:
            raise EngineFailure(
                "F4",
                "2A-S0-031",
                STATE,
                MODULE_NAME,
                {"detail": "duplicate override scope/target", "scope": scope, "target": target},
                dataset_id="tz_overrides",
            )
        seen_pairs.add(key)
        if scope == "mcc":
            mcc_override = True

    if not overrides_payload:
        logger.info("S0: tz_overrides is empty; no overrides will be applied")
        _emit_validation(logger, manifest_fingerprint, "V-09", "pass")
    else:
        if tzid_index_present:
            override_tzids = {
                entry.get("tzid")
                for entry in overrides_payload
                if isinstance(entry.get("tzid"), str)
            }
            missing_tzids = sorted(
                tzid for tzid in override_tzids if tzid and tzid not in tzid_index
            )
            if missing_tzids:
                raise EngineFailure(
                    "F4",
                    "2A-S0-032",
                    STATE,
                    MODULE_NAME,
                    {"detail": "override tzid not in tz_world", "missing": missing_tzids},
                    dataset_id="tz_overrides",
                )
            logger.info(
                "S0: validated tz_overrides against tz_world tzid index (overrides=%s)",
                len(overrides_payload),
            )
            _emit_validation(logger, manifest_fingerprint, "V-09", "pass")
        else:
            warnings.append("2A-S0-032")
            _emit_validation(
                logger,
                manifest_fingerprint,
                "V-09",
                "warn",
                "2A-S0-032",
                "tzid index not sealed; membership not enforced",
            )

    overrides_digest = sha256_file(overrides_path)
    overrides_version = _resolve_version_tag(
        entries["tz_overrides"],
        tokens,
        "tz_overrides",
        fallback=f"sha256:{overrides_digest.sha256_hex}",
    )
    _add_sealed_asset(
        "tz_overrides",
        overrides_path,
        overrides_digest.sha256_hex,
        overrides_digest.size_bytes,
        overrides_version,
    )

    nudge_path = _resolve_dataset_path(entries["tz_nudge"], run_paths, external_roots, tokens)
    nudge_payload = _load_yaml(nudge_path)
    try:
        _validate_payload(
            schema_2a,
            "policy/tz_nudge_v1",
            nudge_payload,
            ref_packs={"schemas.layer1.yaml": schema_layer1},
        )
    except SchemaValidationError as exc:
        raise EngineFailure(
            "F4",
            "2A-S0-030",
            STATE,
            MODULE_NAME,
            {"detail": exc.errors, "path": str(nudge_path)},
            dataset_id="tz_nudge",
        ) from exc
    nudge_digest = sha256_file(nudge_path)
    nudge_version = _resolve_version_tag(
        entries["tz_nudge"],
        tokens,
        "tz_nudge",
        fallback=f"sha256:{nudge_digest.sha256_hex}",
    )
    _add_sealed_asset(
        "tz_nudge",
        nudge_path,
        nudge_digest.sha256_hex,
        nudge_digest.size_bytes,
        nudge_version,
    )

    if mcc_override:
        dataset_id = "merchant_mcc_map"
        dataset_entry, registry_entry, schema_ref, license_class = _load_entry(dataset_id)
        entries[dataset_id] = dataset_entry
        registry_entries[dataset_id] = registry_entry
        schema_refs[dataset_id] = schema_ref
        license_classes[dataset_id] = license_class
        mcc_path = _resolve_dataset_path(dataset_entry, run_paths, external_roots, tokens)
        mcc_files = _list_files_recursive(mcc_path)
        mcc_digest, mcc_bytes = _hash_paths(mcc_files, logger, "merchant_mcc_map")
        mcc_version = _resolve_version_tag(dataset_entry, tokens, dataset_id)
        _add_sealed_asset(dataset_id, mcc_path, mcc_digest, mcc_bytes, mcc_version)

    required_set = {
        "validation_bundle_1B",
        "validation_passed_flag_1B",
        "site_locations",
        "tz_world_2025a",
        "tzdb_release",
        "tz_overrides",
        "tz_nudge",
    }
    sealed_ids = {asset.asset_id for asset in sealed_assets}
    missing_required = sorted(required_set - sealed_ids)
    if missing_required:
        raise EngineFailure(
            "F4",
            "2A-S0-010",
            STATE,
            MODULE_NAME,
            {"detail": "minimum sealed set missing", "missing": missing_required},
        )
    _emit_validation(logger, manifest_fingerprint, "V-04", "pass")
    _emit_validation(logger, manifest_fingerprint, "V-05", "pass")

    seen_assets = set()
    seen_basenames = set()
    seen_digests = set()
    for asset in sealed_assets:
        if asset.asset_id in seen_assets:
            raise EngineFailure(
                "F4",
                "2A-S0-016",
                STATE,
                MODULE_NAME,
                {"detail": "duplicate asset_id", "asset_id": asset.asset_id},
                dataset_id=asset.asset_id,
            )
        if asset.basename in seen_basenames:
            raise EngineFailure(
                "F4",
                "2A-S0-018",
                STATE,
                MODULE_NAME,
                {"detail": "duplicate basename", "basename": asset.basename},
                dataset_id=asset.asset_id,
            )
        if asset.sha256_hex in seen_digests:
            raise EngineFailure(
                "F4",
                "2A-S0-017",
                STATE,
                MODULE_NAME,
                {"detail": "aliasing bytes", "sha256_hex": asset.sha256_hex},
                dataset_id=asset.asset_id,
            )
        seen_assets.add(asset.asset_id)
        seen_basenames.add(asset.basename)
        seen_digests.add(asset.sha256_hex)
    _emit_validation(logger, manifest_fingerprint, "V-06", "pass")

    sealed_assets_sorted = sorted(
        sealed_assets, key=lambda asset: (asset.asset_kind, asset.basename)
    )
    _emit_event(
        logger,
        "SEAL",
        manifest_fingerprint,
        "INFO",
        step="complete",
        assets_total=len(sealed_assets_sorted),
        bytes_total=sum(asset.size_bytes for asset in sealed_assets_sorted),
    )

    sealed_inputs_payload = []
    for asset in sealed_assets_sorted:
        sealed_inputs_payload.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "asset_id": asset.asset_id,
                "asset_kind": asset.asset_kind,
                "basename": asset.basename,
                "version_tag": asset.version_tag,
                "schema_ref": asset.schema_ref,
                "catalog_path": asset.catalog_path,
                "sha256_hex": asset.sha256_hex,
                "size_bytes": asset.size_bytes,
                "license_class": asset.license_class,
                "created_utc": created_utc,
            }
        )

    try:
        pack, table_name = _prepare_table_pack_with_layer1_defs(
            schema_2a, "manifests/sealed_inputs_2A", schema_layer1, "schemas.layer1.yaml"
        )
        validate_dataframe(sealed_inputs_payload, pack, table_name)
    except SchemaValidationError as exc:
        raise EngineFailure(
            "F4",
            "2A-S0-052",
            STATE,
            MODULE_NAME,
            {"detail": exc.errors},
        ) from exc
    _emit_validation(logger, manifest_fingerprint, "V-16", "pass")

    sealed_inputs_bytes = json.dumps(
        sealed_inputs_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    manifest_digest = hashlib.sha256(sealed_inputs_bytes).hexdigest()
    _emit_event(
        logger,
        "HASH",
        manifest_fingerprint,
        "INFO",
        manifest_digest=manifest_digest,
        canonical_order="asset_kind,basename",
    )

    receipt_payload = {
        "manifest_fingerprint": str(manifest_fingerprint),
        "parameter_hash": str(parameter_hash),
        "validation_bundle_path": _render_catalog_path(
            entries["validation_bundle_1B"], tokens
        ),
        "flag_sha256_hex": flag_sha256,
        "verified_at_utc": created_utc,
        "sealed_inputs": sealed_inputs_for_receipt,
        "notes": None,
    }

    receipt_schema = _prepare_row_schema_with_layer1_defs(
        schema_2a, "validation/s0_gate_receipt_v1", schema_layer1, "schemas.layer1.yaml"
    )
    validator = Draft202012Validator(receipt_schema)
    errors = list(validator.iter_errors(receipt_payload))
    if errors:
        detail = errors[0].message if errors else "schema validation failed"
        raise EngineFailure(
            "F4",
            "2A-S0-052",
            STATE,
            MODULE_NAME,
            {"detail": detail},
        )

    if receipt_payload["manifest_fingerprint"] != manifest_fingerprint:
        raise EngineFailure(
            "F4",
            "2A-S0-040",
            STATE,
            MODULE_NAME,
            {"detail": "manifest_fingerprint mismatch in receipt"},
        )

    if not _HEX64_PATTERN.match(flag_sha256):
        raise EngineFailure(
            "F4",
            "2A-S0-042",
            STATE,
            MODULE_NAME,
            {"detail": "flag_sha256_hex invalid", "value": flag_sha256},
        )

    receipt_ids = {item["id"] for item in sealed_inputs_for_receipt}
    if receipt_ids != sealed_ids:
        raise EngineFailure(
            "F4",
            "2A-S0-043",
            STATE,
            MODULE_NAME,
            {"detail": "receipt sealed_inputs mismatch", "missing": sorted(sealed_ids - receipt_ids)},
        )
    _emit_validation(logger, manifest_fingerprint, "V-12", "pass")
    _emit_validation(logger, manifest_fingerprint, "V-15", "pass")

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_2A").entry
    sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_2A").entry

    receipt_partition = receipt_entry.get("partitioning") or []
    sealed_partition = sealed_entry.get("partitioning") or []
    if "seed" in receipt_partition or "parameter_hash" in receipt_partition:
        raise EngineFailure(
            "F4",
            "2A-S0-061",
            STATE,
            MODULE_NAME,
            {"detail": "receipt has disallowed partitions", "partitioning": receipt_partition},
        )
    if "seed" in sealed_partition or "parameter_hash" in sealed_partition:
        raise EngineFailure(
            "F4",
            "2A-S0-061",
            STATE,
            MODULE_NAME,
            {"detail": "sealed_inputs has disallowed partitions", "partitioning": sealed_partition},
        )
    _emit_validation(logger, manifest_fingerprint, "V-19", "pass")

    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, external_roots, tokens)
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, external_roots, tokens)

    if f"manifest_fingerprint={manifest_fingerprint}" not in receipt_path.as_posix():
        raise EngineFailure(
            "F4",
            "2A-S0-040",
            STATE,
            MODULE_NAME,
            {"detail": "receipt path does not embed manifest_fingerprint", "path": str(receipt_path)},
        )
    _emit_validation(logger, manifest_fingerprint, "V-10", "pass")
    if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
        raise EngineFailure(
            "F4",
            "2A-S0-050",
            STATE,
            MODULE_NAME,
            {"detail": "sealed_inputs path does not embed manifest_fingerprint", "path": str(sealed_inputs_path)},
        )
    _emit_validation(logger, manifest_fingerprint, "V-14", "pass")

    receipt_bytes = json.dumps(
        receipt_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    sealed_tmp = run_paths.tmp_root / f"s0_sealed_inputs_{uuid.uuid4().hex}"
    sealed_tmp.mkdir(parents=True, exist_ok=True)
    sealed_inputs_file = sealed_tmp / sealed_inputs_path.name
    sealed_inputs_file.write_bytes(sealed_inputs_bytes)

    determinism_hash, determinism_bytes = _hash_partition(sealed_tmp)
    determinism_receipt = {
        "partition_path": str(sealed_inputs_path.parent),
        "sha256_hex": determinism_hash,
        "bytes_hashed": determinism_bytes,
    }
    determinism_path = sealed_tmp / "determinism_receipt.json"
    _write_json(determinism_path, determinism_receipt)

    _atomic_publish_file(receipt_path, receipt_bytes, logger, "s0_gate_receipt_2A")
    _emit_validation(logger, manifest_fingerprint, "V-17", "pass")
    _atomic_publish_dir(
        sealed_tmp, sealed_inputs_path.parent, logger, "sealed_inputs_2A"
    )
    _emit_validation(logger, manifest_fingerprint, "V-18", "pass")

    _emit_event(
        logger,
        "EMIT",
        manifest_fingerprint,
        "INFO",
        receipt_path=str(receipt_path),
        sealed_inputs_path=str(sealed_inputs_path),
    )

    _emit_event(
        logger,
        "DETERMINISM",
        manifest_fingerprint,
        "INFO",
        partition_hash=determinism_hash,
        partition_path=str(sealed_inputs_path.parent),
    )
    _emit_validation(logger, manifest_fingerprint, "V-13", "pass")

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2A"
        / "state=S0"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s0_run_report.json"
    )
    tzid_index_path = run_report_path.parent / "tzid_index.json"
    tzid_index_digest = None
    if tzid_index_present:
        if not tzid_index_path.exists():
            _write_json(tzid_index_path, tzid_index_list)
            logger.info(
                "S0: tzid_index written %s (tzids=%s)",
                tzid_index_path,
                len(tzid_index_list),
            )
        tzid_index_digest = sha256_file(tzid_index_path)

    required_fields_missing = []

    run_report = {
        "segment": SEGMENT,
        "state": STATE,
        "status": "pass",
        "manifest_fingerprint": str(manifest_fingerprint),
        "parameter_hash": str(parameter_hash),
        "started_utc": created_utc,
        "finished_utc": created_utc,
        "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
        "upstream": {
            "bundle_path": _render_catalog_path(entries["validation_bundle_1B"], tokens),
            "flag_sha256_hex": flag_sha256,
            "verified_at_utc": created_utc,
            "result": "verified",
            "errors": [],
        },
        "sealed_inputs": {
            "count": len(sealed_inputs_payload),
            "bytes_total": sum(asset.size_bytes for asset in sealed_assets_sorted),
            "inventory_path": _render_catalog_path(sealed_entry, tokens),
            "manifest_digest": manifest_digest,
        },
        "tz_assets": {
            "tzdb_release_tag": release_tag,
            "tzdb_archive_sha256": archive_sha256,
            "tz_world_id": "tz_world_2025a",
            "tz_world_crs": "WGS84" if _is_wgs84(tz_world_crs) else str(tz_world_crs),
            "tz_world_feature_count": tz_world_count,
        },
        "outputs": {
            "receipt_path": _render_catalog_path(receipt_entry, tokens),
            "inventory_path": _render_catalog_path(sealed_entry, tokens),
        },
        "determinism": {
            "partition_hash": determinism_hash,
            "computed_at_utc": created_utc,
        },
        "warnings": warnings,
        "errors": [],
    }
    if tzid_index_present and tzid_index_digest is not None:
        run_report["tz_assets"].update(
            {
                "tzid_index_path": str(tzid_index_path),
                "tzid_index_sha256": tzid_index_digest.sha256_hex,
                "tzid_index_count": len(tzid_index_list),
            }
        )

    for key in (
        "segment",
        "state",
        "status",
        "manifest_fingerprint",
        "parameter_hash",
        "started_utc",
        "finished_utc",
    ):
        if run_report.get(key) in (None, ""):
            required_fields_missing.append(key)
    if not run_report.get("upstream"):
        required_fields_missing.append("upstream")
    if not run_report.get("sealed_inputs"):
        required_fields_missing.append("sealed_inputs")
    if not run_report.get("tz_assets"):
        required_fields_missing.append("tz_assets")
    if not run_report.get("outputs"):
        required_fields_missing.append("outputs")
    if not run_report.get("determinism"):
        required_fields_missing.append("determinism")

    if required_fields_missing:
        warnings.append("2A-S0-070")
        _emit_validation(
            logger,
            manifest_fingerprint,
            "V-20",
            "warn",
            "2A-S0-070",
            {"missing": required_fields_missing},
        )
    run_report["warnings"] = warnings

    if not run_report_path.exists():
        _write_run_report(run_report_path, run_report)
        logger.info("S0: run-report written %s", run_report_path)
    else:
        logger.info("S0: run-report already exists; leaving unchanged: %s", run_report_path)

    timer.info("S0: completed gate and sealed inputs")

    return S0GateResult(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        receipt_path=receipt_path,
        sealed_inputs_path=sealed_inputs_path,
        run_report_path=run_report_path,
        determinism_receipt=determinism_receipt,
    )
