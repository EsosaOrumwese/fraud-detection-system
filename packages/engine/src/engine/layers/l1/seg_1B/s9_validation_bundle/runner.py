"""S9 validation bundle runner for Segment 1B."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import polars as pl
from jsonschema import Draft202012Validator

try:  # Optional fast parquet scanning.
    import pyarrow as pa
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pa = None
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import find_dataset_entry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt


MODULE_NAME = "1B.S9.validation_bundle"

DATASET_S7 = "s7_site_synthesis"
DATASET_S8 = "site_locations"
DATASET_EVENT_S5 = "rng_event_site_tile_assign"
DATASET_EVENT_S6 = "rng_event_in_cell_jitter"
DATASET_TRACE = "rng_trace_log"
DATASET_AUDIT = "rng_audit_log"
DATASET_BUNDLE = "validation_bundle_1B"
DATASET_INDEX = "validation_bundle_index_1B"
DATASET_FLAG = "validation_passed_flag_1B"

SITES_WITH_GE1_KEY = "sites_with_\u22651_event"


@dataclass(frozen=True)
class S9RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    decision: str
    bundle_root: Path


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


class _FailureTracker:
    def __init__(
        self,
        logger,
        seed: int,
        parameter_hash: str,
        manifest_fingerprint: str,
        run_id: str,
    ) -> None:
        self._logger = logger
        self._seed = seed
        self._parameter_hash = parameter_hash
        self._manifest_fingerprint = manifest_fingerprint
        self._run_id = run_id
        self.failures_by_code: dict[str, int] = defaultdict(int)
        self._log_counts: dict[str, int] = defaultdict(int)

    def record(self, code: str, detail: dict, sample_limit: int = 5) -> None:
        self.failures_by_code[code] += 1
        if self._log_counts[code] >= sample_limit:
            return
        self._log_counts[code] += 1
        payload = {
            "event": "S9_ERROR",
            "code": code,
            "at": utc_now_rfc3339_micro(),
            "seed": self._seed,
            "parameter_hash": self._parameter_hash,
            "manifest_fingerprint": self._manifest_fingerprint,
            "run_id": self._run_id,
        }
        payload.update(detail)
        self._logger.error("S9_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))

def _json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


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


def _resolve_run_glob(run_paths: RunPaths, path_template: str, tokens: dict[str, str]) -> list[Path]:
    resolved = path_template
    for key, value in tokens.items():
        resolved = resolved.replace(f"{{{key}}}", value)
    if "*" in resolved:
        return sorted(run_paths.run_root.glob(resolved))
    resolved_path = run_paths.run_root / resolved
    if resolved_path.is_dir():
        return sorted(resolved_path.glob("*.jsonl"))
    return [resolved_path]


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted([path for path in root.rglob("*.parquet") if path.is_file()])
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _close_parquet_reader(pfile) -> None:
    reader = getattr(pfile, "reader", None)
    if reader and hasattr(reader, "close"):
        reader.close()


def _iter_parquet_batches(paths: list[Path], columns: list[str]) -> Iterator[pl.DataFrame]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for batch in pf.iter_batches(columns=columns, batch_size=200_000):
                    yield pl.from_arrow(batch)
            finally:
                _close_parquet_reader(pf)
    else:
        for path in paths:
            df = pl.read_parquet(path, columns=columns)
            offset = 0
            while offset < df.height:
                chunk = df.slice(offset, 200_000)
                offset += chunk.height
                yield chunk


def _iter_parquet_rows(paths: list[Path], columns: list[str]) -> Iterator[dict]:
    for batch in _iter_parquet_batches(paths, columns):
        for row in batch.iter_rows(named=True):
            yield row


def _schema_node(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    return node


def _merge_defs(primary: dict, extra: dict) -> dict:
    merged = dict(extra or {})
    merged.update(primary or {})
    return merged


def _normalize_ref(ref: str) -> str:
    if ref.startswith("schemas.layer1.yaml#/$defs/"):
        return "#/$defs/" + ref.split("/$defs/")[1]
    if ref.startswith("schemas.1B.yaml#/$defs/"):
        return "#/$defs/" + ref.split("/$defs/")[1]
    if ref.startswith("schemas.1A.yaml#/$defs/"):
        return "#/$defs/" + ref.split("/$defs/")[1]
    return ref


def _normalize_refs(payload: object) -> object:
    if isinstance(payload, list):
        return [_normalize_refs(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    normalized: dict = {}
    for key, value in payload.items():
        if key == "$ref" and isinstance(value, str):
            normalized[key] = _normalize_ref(value)
        else:
            normalized[key] = _normalize_refs(value)
    return normalized


def _schema_from_pack(schema_pack: dict, path: str, defs_extra: Optional[dict] = None) -> dict:
    node = _schema_node(schema_pack, path)
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": _merge_defs(schema_pack.get("$defs", {}), defs_extra or {}),
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
    schema = _normalize_refs(schema)
    return normalize_nullable_schema(schema)


def _record_schema(schema_pack: dict, path: str, defs_extra: Optional[dict] = None) -> dict:
    node = _schema_node(schema_pack, path)
    record = node.get("record") if isinstance(node, dict) else None
    if record is None:
        record = node
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": _merge_defs(schema_pack.get("$defs", {}), defs_extra or {}),
    }
    if isinstance(record, dict):
        schema.update(record)
    schema = _normalize_refs(schema)
    return normalize_nullable_schema(schema)


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
            raise SchemaValidationError(f"Unsupported column type '{col_type}' for S9 schema.", [])
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

def _iter_jsonl_files(paths: Iterable[Path]):
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                yield path, line_no, json.loads(line)


def _u128(hi: int, lo: int) -> int:
    return (int(hi) << 64) + int(lo)


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> str:
    hasher = hashlib.sha256()
    for entry in sorted(index_entries, key=lambda item: item["path"]):
        path = bundle_root / entry["path"]
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


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


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E913_ATOMIC_PUBLISH_VIOLATION",
                "S9",
                MODULE_NAME,
                {"detail": "partition_exists_nonidentical", "dataset": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S9: %s partition already exists with identical bytes", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _resolve_git_hex(repo_root: Path) -> str:
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


def _assert_schema_ref(schema_ref: Optional[str], schema_packs: dict[str, dict]) -> None:
    if not schema_ref:
        raise ContractError("Schema reference missing from dictionary entry.")
    if schema_ref.startswith("schemas.1B.yaml#"):
        pack = schema_packs["1B"]
        path = schema_ref.split("#", 1)[1]
    elif schema_ref.startswith("schemas.layer1.yaml#"):
        pack = schema_packs["layer1"]
        path = schema_ref.split("#", 1)[1]
    elif schema_ref.startswith("schemas.1A.yaml#"):
        pack = schema_packs["1A"]
        path = schema_ref.split("#", 1)[1]
    else:
        raise ContractError(f"Unsupported schema_ref: {schema_ref}")
    try:
        _schema_node(pack, path)
    except Exception as exc:
        raise ContractError(f"Schema anchor not found: {schema_ref}") from exc

def _parse_draws(value: object) -> int:
    if value is None:
        return 0
    return int(str(value))


def _s8_row_key(row: dict) -> tuple[int, str, int]:
    return (
        int(row["merchant_id"]),
        str(row["legal_country_iso"]),
        int(row["site_order"]),
    )


def _rng_event_key(event: dict) -> tuple[int, str, int]:
    return (
        int(event.get("merchant_id")),
        str(event.get("legal_country_iso")),
        int(event.get("site_order")),
    )


def _required_bundle_files() -> list[str]:
    return [
        "MANIFEST.json",
        "parameter_hash_resolved.json",
        "manifest_fingerprint_resolved.json",
        "rng_accounting.json",
        "s9_summary.json",
        "egress_checksums.json",
        "index.json",
    ]


def run_s9(
    config: EngineConfig,
    run_id: Optional[str] = None,
    validate_only: bool = False,
) -> S9RunResult:
    logger = get_logger("engine.layers.l1.seg_1B.s9_validation_bundle.l2.runner")
    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = str(receipt.get("run_id") or run_id or "")
    if not run_id:
        raise InputResolutionError("run_id missing from run_receipt.json")
    seed = int(receipt.get("seed"))
    parameter_hash = str(receipt.get("parameter_hash"))
    manifest_fingerprint = str(receipt.get("manifest_fingerprint"))

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)

    logger.info(
        "S9: validation bundle start seed=%s manifest_fingerprint=%s parameter_hash=%s run_id=%s",
        seed,
        manifest_fingerprint,
        parameter_hash,
        run_id,
    )
    timer = _StepTimer(logger)
    tracker = _FailureTracker(logger, seed, parameter_hash, manifest_fingerprint, run_id)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    schema_packs = {"1B": schema_1b, "layer1": schema_layer1, "1A": schema_1a}
    logger.info(
        "S9: contracts loaded dictionary=%s schemas=%s,%s,%s",
        dict_path,
        schema_1b_path,
        schema_layer1_path,
        schema_1a_path,
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": str(parameter_hash),
        "manifest_fingerprint": str(manifest_fingerprint),
        "run_id": str(run_id),
    }
    external_roots = [Path(root) for root in config.external_roots]

    s7_entry = find_dataset_entry(dictionary, DATASET_S7).entry
    s8_entry = find_dataset_entry(dictionary, DATASET_S8).entry
    event_s5_entry = find_dataset_entry(dictionary, DATASET_EVENT_S5).entry
    event_s6_entry = find_dataset_entry(dictionary, DATASET_EVENT_S6).entry
    trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
    audit_entry = find_dataset_entry(dictionary, DATASET_AUDIT).entry
    bundle_entry = find_dataset_entry(dictionary, DATASET_BUNDLE).entry
    index_entry = find_dataset_entry(dictionary, DATASET_INDEX).entry
    flag_entry = find_dataset_entry(dictionary, DATASET_FLAG).entry

    for entry in (
        s7_entry,
        s8_entry,
        event_s5_entry,
        event_s6_entry,
        trace_entry,
        audit_entry,
        bundle_entry,
        index_entry,
        flag_entry,
    ):
        try:
            _assert_schema_ref(entry.get("schema_ref"), schema_packs)
        except ContractError as exc:
            tracker.record(
                "E900_SCHEMA_REF_INVALID",
                {"detail": "schema_ref_invalid", "schema_ref": entry.get("schema_ref", ""), "error": str(exc)},
            )

    if not s8_entry.get("lineage", {}).get("final_in_layer", False):
        tracker.record(
            "E911_FINALITY_OR_ORDER_LEAK",
            {"detail": "egress_not_final", "dataset_id": DATASET_S8},
        )
    if "parameter_hash" in (s8_entry.get("partitioning") or []):
        tracker.record(
            "E912_IDENTITY_COHERENCE",
            {"detail": "parameter_hash_in_egress_partition", "dataset_id": DATASET_S8},
        )
    if "parameter_hash=" in str(s8_entry.get("path", "")):
        tracker.record(
            "E912_IDENTITY_COHERENCE",
            {"detail": "parameter_hash_in_egress_path", "dataset_id": DATASET_S8},
        )

    s7_root = _resolve_dataset_path(s7_entry, run_paths, external_roots, tokens)
    s8_root = _resolve_dataset_path(s8_entry, run_paths, external_roots, tokens)
    bundle_root = _resolve_dataset_path(bundle_entry, run_paths, external_roots, tokens)
    index_path = _resolve_dataset_path(index_entry, run_paths, external_roots, tokens)
    flag_path = _resolve_dataset_path(flag_entry, run_paths, external_roots, tokens)

    s7_files = _list_parquet_files(s7_root)
    s8_files = _list_parquet_files(s8_root)
    s7_columns = ["merchant_id", "legal_country_iso", "site_order"]
    s8_columns = [
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "lon_deg",
        "lat_deg",
    ]
    s8_row_schema = _table_row_schema(
        schema_1b, "egress/site_locations", defs_extra=schema_layer1.get("$defs")
    )
    s8_validator = Draft202012Validator(s8_row_schema)

    by_country: dict[str, dict[str, object]] = {}
    counts = {
        "rows_s7": 0,
        "rows_s8": 0,
        "missing": 0,
        "extra": 0,
        "writer_sort_violations": 0,
        "path_embed_mismatches": 0,
        "schema_failures": 0,
        "dup_keys": 0,
    }
    s7_keys: set[tuple[int, str, int]] = set()

    progress_s7 = _ProgressTracker(None, logger, "S9 parity S7 rows")
    progress_s8 = _ProgressTracker(None, logger, "S9 parity S8 rows")

    def iter_s7_keys() -> Iterator[tuple[int, str, int]]:
        last_key: Optional[tuple[int, str, int]] = None
        for batch in _iter_parquet_batches(s7_files, s7_columns):
            progress_s7.update(batch.height)
            for row in batch.iter_rows(named=True):
                key = _s8_row_key(row)
                if last_key is not None and key <= last_key:
                    tracker.record(
                        "E906_WRITER_SORT_VIOLATION",
                        {"detail": "s7_writer_sort_violation", "key": key},
                    )
                last_key = key
                s7_keys.add(key)
                counts["rows_s7"] += 1
                stats = by_country.setdefault(
                    str(key[1]), {"rows_s7": 0, "rows_s8": 0, "parity_ok": True}
                )
                stats["rows_s7"] = int(stats["rows_s7"]) + 1
                yield key

    def iter_s8_keys() -> Iterator[tuple[int, str, int]]:
        last_key: Optional[tuple[int, str, int]] = None
        for batch in _iter_parquet_batches(s8_files, s8_columns):
            progress_s8.update(batch.height)
            for row in batch.iter_rows(named=True):
                schema_error = None
                for error in s8_validator.iter_errors(row):
                    schema_error = error
                    break
                if schema_error is not None:
                    counts["schema_failures"] += 1
                    tracker.record(
                        "E904_EGRESS_SCHEMA_VIOLATION",
                        {"detail": schema_error.message, "field": ".".join(str(p) for p in schema_error.path)},
                    )
                key = _s8_row_key(row)
                if last_key is not None:
                    if key < last_key:
                        counts["writer_sort_violations"] += 1
                        tracker.record(
                            "E906_WRITER_SORT_VIOLATION",
                            {"detail": "s8_writer_sort_violation", "key": key},
                        )
                    elif key == last_key:
                        counts["dup_keys"] += 1
                        tracker.record(
                            "E903_DUP_KEY",
                            {"detail": "s8_duplicate_key", "key": key},
                        )
                last_key = key
                counts["rows_s8"] += 1
                stats = by_country.setdefault(
                    str(key[1]), {"rows_s7": 0, "rows_s8": 0, "parity_ok": True}
                )
                stats["rows_s8"] = int(stats["rows_s8"]) + 1
                if "manifest_fingerprint" in row and str(row["manifest_fingerprint"]) != manifest_fingerprint:
                    counts["path_embed_mismatches"] += 1
                    tracker.record(
                        "E905_PARTITION_OR_IDENTITY",
                        {
                            "detail": "manifest_fingerprint_mismatch",
                            "observed": str(row.get("manifest_fingerprint")),
                            "expected": manifest_fingerprint,
                        },
                    )
                if "seed" in row and int(row["seed"]) != seed:
                    counts["path_embed_mismatches"] += 1
                    tracker.record(
                        "E905_PARTITION_OR_IDENTITY",
                        {
                            "detail": "seed_mismatch",
                            "observed": int(row.get("seed")),
                            "expected": seed,
                        },
                    )
                yield key

    timer.info("S9: parity validation start (S7 vs S8)")
    s7_iter = iter_s7_keys()
    s8_iter = iter_s8_keys()
    s7_key = next(s7_iter, None)
    s8_key = next(s8_iter, None)
    while s7_key is not None or s8_key is not None:
        if s7_key is not None and (s8_key is None or s7_key < s8_key):
            counts["missing"] += 1
            tracker.record(
                "E901_ROW_MISSING",
                {"detail": "s8_missing_key", "key": s7_key},
            )
            s7_key = next(s7_iter, None)
            continue
        if s8_key is not None and (s7_key is None or s8_key < s7_key):
            counts["extra"] += 1
            tracker.record(
                "E902_ROW_EXTRA",
                {"detail": "s8_extra_key", "key": s8_key},
            )
            s8_key = next(s8_iter, None)
            continue
        s7_key = next(s7_iter, None)
        s8_key = next(s8_iter, None)

    for stats in by_country.values():
        stats["parity_ok"] = int(stats["rows_s7"]) == int(stats["rows_s8"])

    parity_ok = counts["missing"] == 0 and counts["extra"] == 0
    timer.info(
        "S9: parity validation complete rows_s7=%d rows_s8=%d parity_ok=%s",
        counts["rows_s7"],
        counts["rows_s8"],
        parity_ok,
    )
    event_s5_paths = _resolve_run_glob(run_paths, event_s5_entry.get("path", ""), tokens)
    event_s6_paths = _resolve_run_glob(run_paths, event_s6_entry.get("path", ""), tokens)
    trace_paths = _resolve_run_glob(run_paths, trace_entry.get("path", ""), tokens)
    audit_paths = _resolve_run_glob(run_paths, audit_entry.get("path", ""), tokens)

    if not event_s5_paths:
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {"detail": "rng_event_site_tile_assign_missing", "path": event_s5_entry.get("path", "")},
        )
    if not event_s6_paths:
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {"detail": "rng_event_in_cell_jitter_missing", "path": event_s6_entry.get("path", "")},
        )
    if not trace_paths:
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {"detail": "rng_trace_log_missing", "path": trace_entry.get("path", "")},
        )
    if not audit_paths:
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {"detail": "rng_audit_log_missing", "path": audit_entry.get("path", "")},
        )

    event_s5_schema = _schema_from_pack(
        schema_layer1,
        "rng/events/site_tile_assign",
        defs_extra=schema_1b.get("$defs"),
    )
    event_s6_schema = _schema_from_pack(
        schema_layer1,
        "rng/events/in_cell_jitter",
        defs_extra=schema_1b.get("$defs"),
    )
    trace_schema = _record_schema(schema_layer1, "rng/core/rng_trace_log", defs_extra=schema_layer1.get("$defs"))
    audit_schema = _record_schema(schema_layer1, "rng/core/rng_audit_log", defs_extra=schema_layer1.get("$defs"))

    event_s5_validator = Draft202012Validator(event_s5_schema)
    event_s6_validator = Draft202012Validator(event_s6_schema)
    trace_validator = Draft202012Validator(trace_schema)
    audit_validator = Draft202012Validator(audit_schema)

    timer.info("S9: RNG trace/audit scan start")
    trace_final: dict[tuple[str, str, str], dict] = {}
    trace_rows_total: dict[tuple[str, str, str], int] = defaultdict(int)
    for _path, _line_no, payload in _iter_jsonl_files(trace_paths):
        if payload.get("run_id") != run_id:
            continue
        schema_error = None
        for error in trace_validator.iter_errors(payload):
            schema_error = error
            break
        if schema_error is not None:
            tracker.record(
                "E907_RNG_BUDGET_OR_COUNTERS",
                {"detail": "rng_trace_schema_invalid", "error": schema_error.message},
            )
        key = (str(payload.get("module")), str(payload.get("substream_label")), str(payload.get("run_id")))
        trace_rows_total[key] += 1
        trace_final[key] = payload

    audit_present = False
    for _path, _line_no, payload in _iter_jsonl_files(audit_paths):
        audit_present = True
        schema_error = None
        for error in audit_validator.iter_errors(payload):
            schema_error = error
            break
        if schema_error is not None:
            tracker.record(
                "E907_RNG_BUDGET_OR_COUNTERS",
                {"detail": "rng_audit_schema_invalid", "error": schema_error.message},
            )
        break
    if not audit_present:
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {"detail": "rng_audit_log_empty"},
        )

    def process_events(
        paths: list[Path],
        validator: Draft202012Validator,
        budget_blocks: Optional[int] = None,
        budget_draws: Optional[str] = None,
    ) -> dict:
        events_total = 0
        blocks_total = 0
        draws_total = 0
        envelope_failures = 0
        budget_failures = 0
        unknown_events = 0
        key_counts: dict[tuple[int, str, int], int] = defaultdict(int)
        for _path, _line_no, payload in _iter_jsonl_files(paths):
            if payload.get("run_id") != run_id:
                tracker.record(
                    "E907_RNG_BUDGET_OR_COUNTERS",
                    {"detail": "rng_event_run_id_mismatch", "observed": payload.get("run_id")},
                )
            schema_error = None
            for error in validator.iter_errors(payload):
                schema_error = error
                break
            if schema_error is not None:
                envelope_failures += 1
                tracker.record(
                    "E907_RNG_BUDGET_OR_COUNTERS",
                    {"detail": "rng_event_schema_invalid", "error": schema_error.message},
                )
            blocks = int(payload.get("blocks", 0))
            draws = _parse_draws(payload.get("draws"))
            before = _u128(payload.get("rng_counter_before_hi", 0), payload.get("rng_counter_before_lo", 0))
            after = _u128(payload.get("rng_counter_after_hi", 0), payload.get("rng_counter_after_lo", 0))
            if after - before != blocks:
                envelope_failures += 1
                tracker.record(
                    "E907_RNG_BUDGET_OR_COUNTERS",
                    {"detail": "rng_envelope_violation", "blocks": blocks},
                )
            if budget_blocks is not None:
                if blocks != budget_blocks or str(payload.get("draws")) != str(budget_draws):
                    budget_failures += 1
                    tracker.record(
                        "E907_RNG_BUDGET_OR_COUNTERS",
                        {
                            "detail": "rng_budget_violation",
                            "expected_blocks": budget_blocks,
                            "expected_draws": str(budget_draws),
                            "observed_blocks": blocks,
                            "observed_draws": str(payload.get("draws")),
                        },
                    )
            key = _rng_event_key(payload)
            if key in s7_keys:
                key_counts[key] += 1
            else:
                unknown_events += 1
            events_total += 1
            blocks_total += blocks
            draws_total += draws
        return {
            "events_total": events_total,
            "blocks_total": blocks_total,
            "draws_total": draws_total,
            "envelope_failures": envelope_failures,
            "budget_failures": budget_failures,
            "unknown_events": unknown_events,
            "key_counts": key_counts,
        }

    timer.info("S9: RNG events scan start")
    s5_stats = process_events(event_s5_paths, event_s5_validator)
    s6_stats = process_events(event_s6_paths, event_s6_validator, budget_blocks=1, budget_draws="2")

    sites_total = len(s7_keys)
    s5_key_counts = s5_stats["key_counts"]
    s6_key_counts = s6_stats["key_counts"]

    s5_missing = max(sites_total - len(s5_key_counts), 0)
    s5_duplicates = sum(max(count - 1, 0) for count in s5_key_counts.values())
    s5_extra = int(s5_stats["unknown_events"]) + int(s5_duplicates)

    s6_sites_with_event = len(s6_key_counts)
    s6_sites_with_0 = max(sites_total - s6_sites_with_event, 0)

    if s5_missing > 0 or s5_extra > 0 or s5_stats["envelope_failures"] > 0:
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {
                "detail": "s5_site_tile_assign_coverage",
                "events_missing": s5_missing,
                "events_extra": s5_extra,
                "envelope_failures": s5_stats["envelope_failures"],
            },
        )
    if (
        s6_sites_with_0 > 0
        or s6_stats["unknown_events"] > 0
        or s6_stats["envelope_failures"] > 0
        or s6_stats["budget_failures"] > 0
    ):
        tracker.record(
            "E907_RNG_BUDGET_OR_COUNTERS",
            {
                "detail": "s6_in_cell_jitter_coverage",
                "sites_with_0_event": s6_sites_with_0,
                "unknown_events": s6_stats["unknown_events"],
                "envelope_failures": s6_stats["envelope_failures"],
                "budget_failures": s6_stats["budget_failures"],
            },
        )

    def reconcile_trace(module: str, substream_label: str, events_total: int, blocks_total: int, draws_total: int) -> tuple[bool, dict, int]:
        key = (module, substream_label, run_id)
        trace_row = trace_final.get(key)
        trace_rows = trace_rows_total.get(key, 0)
        trace_totals = {
            "events_total": int(trace_row.get("events_total", 0)) if trace_row else 0,
            "blocks_total": int(trace_row.get("blocks_total", 0)) if trace_row else 0,
            "draws_total": str(trace_row.get("draws_total", 0)) if trace_row else "0",
        }
        reconciled = (
            trace_row is not None
            and trace_rows == events_total
            and trace_totals["events_total"] == events_total
            and trace_totals["blocks_total"] == blocks_total
            and int(trace_totals["draws_total"]) == int(draws_total)
        )
        if not reconciled:
            tracker.record(
                "E907_RNG_BUDGET_OR_COUNTERS",
                {
                    "detail": "rng_trace_mismatch",
                    "module": module,
                    "substream_label": substream_label,
                    "events_total": events_total,
                    "blocks_total": blocks_total,
                    "draws_total": str(draws_total),
                    "trace_rows": trace_rows,
                    "trace_totals": trace_totals,
                },
            )
        return reconciled, trace_totals, trace_rows

    s5_trace_ok, s5_trace_totals, _s5_trace_rows = reconcile_trace(
        "1B.S5.assigner",
        "site_tile_assign",
        int(s5_stats["events_total"]),
        int(s5_stats["blocks_total"]),
        int(s5_stats["draws_total"]),
    )
    s6_trace_ok, s6_trace_totals, _s6_trace_rows = reconcile_trace(
        "1B.S6.jitter",
        "in_cell_jitter",
        int(s6_stats["events_total"]),
        int(s6_stats["blocks_total"]),
        int(s6_stats["draws_total"]),
    )

    s5_coverage_ok = s5_missing == 0 and s5_extra == 0
    s6_coverage_ok = s6_sites_with_0 == 0

    egress_path_value = s8_entry.get("path", "")
    for key, value in tokens.items():
        egress_path_value = egress_path_value.replace(f"{{{key}}}", value)
    egress_path_value = egress_path_value.replace("\\", "/")
    if not egress_path_value.endswith("/"):
        egress_path_value += "/"

    timer.info("S9: computing egress checksums")
    egress_checksums = {
        "dataset_id": DATASET_S8,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "path": egress_path_value,
        "files": [],
        "composite_sha256_hex": "",
    }
    file_lookup: dict[str, Path] = {}
    for file_path in sorted(s8_files, key=lambda path: path.name):
        digest = sha256_file(file_path)
        rel_path = os.path.relpath(file_path, bundle_root)
        rel_path = Path(rel_path).as_posix()
        egress_checksums["files"].append(
            {
                "path": rel_path,
                "sha256_hex": digest.sha256_hex,
                "size_bytes": digest.size_bytes,
            }
        )
        file_lookup[rel_path] = file_path
    hasher = hashlib.sha256()
    for entry in sorted(egress_checksums["files"], key=lambda item: item["path"]):
        hasher.update(file_lookup[entry["path"]].read_bytes())
    egress_checksums["composite_sha256_hex"] = hasher.hexdigest()

    rng_summary = {
        "families": {
            "site_tile_assign": {
                "coverage_ok": s5_coverage_ok,
                "events_total": int(s5_stats["events_total"]),
                "blocks_total": int(s5_stats["blocks_total"]),
                "draws_total": str(s5_stats["draws_total"]),
                "envelope_failures": int(s5_stats["envelope_failures"]),
                "trace_reconciled": bool(s5_trace_ok),
            },
            "in_cell_jitter": {
                "coverage_ok": s6_coverage_ok,
                "events_total": int(s6_stats["events_total"]),
                "blocks_total": int(s6_stats["blocks_total"]),
                "draws_total": str(s6_stats["draws_total"]),
                "envelope_failures": int(s6_stats["envelope_failures"]),
                "trace_reconciled": bool(s6_trace_ok),
            },
        }
    }

    summary_payload = {
        "identity": {
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id,
        },
        "sizes": {
            "rows_s7": counts["rows_s7"],
            "rows_s8": counts["rows_s8"],
            "parity_ok": parity_ok,
        },
        "egress": {
            "path": egress_path_value,
            "writer_sort_violations": counts["writer_sort_violations"],
            "path_embed_mismatches": counts["path_embed_mismatches"],
        },
        "rng": rng_summary,
        "by_country": by_country,
    }

    rng_accounting = {
        "families": [
            {
                "id": "site_tile_assign",
                "module": "1B.S5.assigner",
                "coverage": {
                    "sites_total": sites_total,
                    "events_missing": s5_missing,
                    "events_extra": s5_extra,
                },
                "events_total": int(s5_stats["events_total"]),
                "blocks_total": int(s5_stats["blocks_total"]),
                "draws_total": str(s5_stats["draws_total"]),
                "trace_totals": s5_trace_totals,
                "trace_reconciled": bool(s5_trace_ok),
                "envelope_failures": int(s5_stats["envelope_failures"]),
            },
            {
                "id": "in_cell_jitter",
                "module": "1B.S6.jitter",
                "coverage": {
                    "sites_total": sites_total,
                    SITES_WITH_GE1_KEY: s6_sites_with_event,
                    "sites_with_0_event": s6_sites_with_0,
                },
                "events_total": int(s6_stats["events_total"]),
                "blocks_total": int(s6_stats["blocks_total"]),
                "draws_total": str(s6_stats["draws_total"]),
                "budget_per_event": {"blocks": 1, "draws": "2"},
                "trace_totals": s6_trace_totals,
                "trace_reconciled": bool(s6_trace_ok),
                "envelope_failures": int(s6_stats["envelope_failures"]),
            },
        ]
    }

    parameter_inputs = receipt.get("parameter_inputs") or []
    filenames_sorted = sorted(str(name) for name in parameter_inputs)
    if not filenames_sorted:
        logger.info("S9: parameter_inputs not found in run_receipt; artifact_count=0")
    parameter_hash_resolved = {
        "parameter_hash": parameter_hash,
        "artifact_count": len(filenames_sorted),
        "filenames_sorted": filenames_sorted,
    }

    manifest_artifacts = receipt.get("manifest_artifacts") or []
    git_commit_hex = receipt.get("git_commit_hex") or receipt.get("build_commit")
    if not git_commit_hex:
        git_commit_hex = _resolve_git_hex(config.repo_root)
    manifest_fingerprint_resolved = {
        "manifest_fingerprint": manifest_fingerprint,
        "artifact_count": len(manifest_artifacts),
        "git_commit_hex": str(git_commit_hex),
        "parameter_hash": parameter_hash,
    }

    manifest_payload = {
        "version": "1B.validation.v1",
        "seed": seed,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
        "inputs": {
            "s7_site_synthesis": s7_entry.get("path"),
            "site_locations": s8_entry.get("path"),
        },
        "outputs": {
            "validation_bundle": bundle_entry.get("path"),
        },
    }

    index_entries = [
        {
            "artifact_id": "MANIFEST",
            "kind": "summary",
            "path": "MANIFEST.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "parameter_hash_resolved",
            "kind": "table",
            "path": "parameter_hash_resolved.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "manifest_fingerprint_resolved",
            "kind": "table",
            "path": "manifest_fingerprint_resolved.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "rng_accounting",
            "kind": "table",
            "path": "rng_accounting.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "s9_summary",
            "kind": "summary",
            "path": "s9_summary.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "egress_checksums",
            "kind": "table",
            "path": "egress_checksums.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "index",
            "kind": "table",
            "path": "index.json",
            "mime": "application/json",
            "notes": None,
        },
    ]

    try:
        index_schema_pack, index_table = _table_pack(
            schema_1b, "validation/validation_bundle_index_1B"
        )
        validate_dataframe(index_entries, index_schema_pack, index_table)
    except SchemaValidationError as exc:
        tracker.record(
            "E909_INDEX_INVALID",
            {"detail": "index_schema_invalid", "error": str(exc)},
        )

    seen_artifacts: set[str] = set()
    for entry in index_entries:
        artifact_id = str(entry.get("artifact_id", ""))
        if artifact_id in seen_artifacts:
            tracker.record(
                "E909_INDEX_INVALID",
                {"detail": "duplicate_artifact_id", "artifact_id": artifact_id},
            )
        seen_artifacts.add(artifact_id)

    decision = "PASS" if not tracker.failures_by_code else "FAIL"
    if validate_only:
        return S9RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            decision=decision,
            bundle_root=Path(""),
        )

    tmp_root = bundle_root.parent / f"_tmp.{uuid.uuid4().hex}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    _write_json(tmp_root / "MANIFEST.json", manifest_payload)
    _write_json(tmp_root / "parameter_hash_resolved.json", parameter_hash_resolved)
    _write_json(tmp_root / "manifest_fingerprint_resolved.json", manifest_fingerprint_resolved)
    _write_json(tmp_root / "rng_accounting.json", rng_accounting)
    _write_json(tmp_root / "s9_summary.json", summary_payload)
    _write_json(tmp_root / "egress_checksums.json", egress_checksums)
    _write_json(tmp_root / "index.json", index_entries)

    for filename in _required_bundle_files():
        if not (tmp_root / filename).exists():
            tracker.record(
                "E908_BUNDLE_CONTENTS_MISSING",
                {"detail": "bundle_file_missing", "file": filename},
            )

    decision = "PASS" if not tracker.failures_by_code else "FAIL"
    if decision == "PASS":
        bundle_hash = _bundle_hash(tmp_root, index_entries)
        flag_payload = f"sha256_hex = {bundle_hash}"
        (tmp_root / "_passed.flag").write_text(flag_payload + "\n", encoding="ascii")
        if not (tmp_root / "_passed.flag").exists():
            tracker.record(
                "E910_FLAG_BAD_OR_MISSING",
                {"detail": "passed_flag_missing"},
            )

    _atomic_publish_dir(tmp_root, bundle_root, logger, DATASET_BUNDLE)
    timer.info("S9: bundle published decision=%s", decision)

    return S9RunResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        decision=decision,
        bundle_root=bundle_root,
    )


__all__ = ["S9RunResult", "run_s9"]
