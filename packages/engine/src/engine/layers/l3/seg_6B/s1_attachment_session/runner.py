
"""S1 arrival attachment + sessionisation for Segment 6B."""

from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import pyarrow.parquet as pq
import yaml
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro


MODULE_NAME = "6B.s1_attachment_session"
SEGMENT = "6B"
STATE = "S1"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class S1Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    scenario_ids: list[str]


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
    def __init__(self, total: int, logger, label: str, cadence_seconds: float = 5.0) -> None:
        self._total = max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0
        self._cadence = cadence_seconds

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < self._cadence and self._processed < self._total:
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


def _emit_validation(
    logger, manifest_fingerprint: Optional[str], validator_id: str, result: str, error_code: str, detail: dict
) -> None:
    severity = "INFO" if result == "pass" else "WARN" if result == "warn" else "ERROR"
    payload = {
        "event": "VALIDATION",
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint or "unknown",
        "validator_id": validator_id,
        "result": result,
        "error_code": error_code,
        "detail": detail,
        "timestamp_utc": utc_now_rfc3339_micro(),
    }
    message = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    if severity == "ERROR":
        logger.error("%s", message)
    elif severity == "WARN":
        logger.warning("%s", message)
    else:
        logger.info("%s", message)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l3.seg_6B.s1_attachment_session.runner")
    payload = {"message": message}
    payload.update(context)
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, payload)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _load_json(path: Path) -> object:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"Invalid JSON at {path}") from exc


def _load_yaml(path: Path) -> object:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SchemaValidationError(f"Invalid YAML at {path}") from exc


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
    else:
        receipt_path = _pick_latest_run_receipt(runs_root)
    receipt = _load_json(receipt_path)
    if not isinstance(receipt, dict):
        raise InputResolutionError(f"Invalid run_receipt.json payload at {receipt_path}")
    return receipt_path, receipt


def _render_path_template(path_template: str, tokens: dict[str, str], allow_wildcards: bool = False) -> str:
    rendered = str(path_template).strip()
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    if allow_wildcards:
        rendered = rendered.replace("{scenario_id}", "*")
    return rendered


def _resolve_dataset_path(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
    allow_wildcards: bool = False,
) -> Path:
    path_template = entry.get("path") or entry.get("path_template")
    if not path_template:
        raise InputResolutionError("Dataset entry missing path.")
    resolved = _render_path_template(path_template, tokens, allow_wildcards=allow_wildcards)
    if resolved.startswith(("data/", "logs/", "reports/")):
        return run_paths.run_root / resolved
    if resolved.startswith("artefacts/"):
        return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=False)
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _materialize_parquet_path(path: Path) -> Path:
    if "*" in path.name or "?" in path.name:
        return path.with_name("part-00000.parquet")
    if path.is_dir():
        return path / "part-00000.parquet"
    return path


def _list_parquet_files(root: Path, allow_empty: bool = False) -> list[Path]:
    if root.is_file():
        return [root]
    if "*" in str(root) or "?" in str(root):
        files = sorted(Path(path) for path in glob.glob(str(root)))
    else:
        files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not files and not allow_empty:
        raise InputResolutionError(f"No parquet files found under dataset path: {root}")
    return files


def _read_parquet(path: Path, columns: Optional[list[str]] = None, allow_empty: bool = False) -> pl.DataFrame:
    files = _list_parquet_files(path, allow_empty=allow_empty)
    if not files:
        return pl.DataFrame()
    return pl.read_parquet([str(file) for file in files], columns=columns)


def _count_parquet_rows(files: Iterable[Path]) -> int:
    total = 0
    for file in files:
        meta = pq.ParquetFile(file).metadata
        if meta:
            total += int(meta.num_rows)
    return total


def _iter_parquet_batches(
    files: Iterable[Path], columns: list[str], batch_rows: int
) -> Iterable[pl.DataFrame]:
    for file in files:
        parquet_file = pq.ParquetFile(file)
        for batch in parquet_file.iter_batches(batch_size=batch_rows, columns=columns):
            if batch.num_rows == 0:
                continue
            yield pl.from_arrow(batch)


def _schema_from_pack(schema_pack: dict, anchor: str) -> dict:
    if not anchor.startswith("#/"):
        raise ContractError(f"Invalid schema anchor: {anchor}")
    parts = [part for part in anchor[2:].split("/") if part]
    node = schema_pack
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, dict) and "properties" in node and part in node["properties"]:
            node = node["properties"][part]
        else:
            raise ContractError(f"Schema anchor not found: {anchor}")
    if not isinstance(node, dict):
        raise ContractError(f"Schema anchor {anchor} did not resolve to an object.")
    schema = normalize_nullable_schema(node)
    if "$defs" not in schema and "$defs" in schema_pack:
        schema = {**schema, "$defs": schema_pack["$defs"]}
    return schema


def _inline_external_refs(schema: dict, external_schema: dict, prefix: str) -> None:
    stack = [schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(prefix):
                target = external_schema
                path = ref[len(prefix) :]
                if path.startswith("/"):
                    path = path[1:]
                for part in path.split("/"):
                    if not part:
                        continue
                    target = target.get(part) if isinstance(target, dict) else None
                if not isinstance(target, dict):
                    raise ContractError(f"Unable to resolve external ref {ref}")
                node.clear()
                node.update(target)
                continue
            for value in node.values():
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)


def _validate_payload(
    payload: object,
    schema_pack: dict,
    schema_layer3: dict,
    schema_anchor: str,
    manifest_fingerprint: str,
    context: dict,
) -> None:
    schema = _schema_from_pack(schema_pack, schema_anchor)
    _inline_external_refs(schema, schema_layer3, "schemas.layer3.yaml#")
    if isinstance(payload, list) and schema.get("type") == "object":
        defs = schema.get("$defs")
        items_schema = {key: value for key, value in schema.items() if key != "$defs"}
        schema = {"type": "array", "items": items_schema}
        if defs:
            schema["$defs"] = defs
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "6B.S1.SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "context": context, "manifest_fingerprint": manifest_fingerprint},
        )


def _sealed_inputs_digest(rows: list[dict]) -> str:
    ordered_fields = (
        "manifest_fingerprint",
        "owner_layer",
        "owner_segment",
        "manifest_key",
        "path_template",
        "partition_keys",
        "schema_ref",
        "role",
        "status",
        "read_scope",
        "sha256_hex",
        "upstream_bundle_id",
        "notes",
    )
    hasher = hashlib.sha256()
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            row.get("owner_layer"),
            row.get("owner_segment"),
            row.get("manifest_key"),
            row.get("path_template"),
        ),
    )
    for row in sorted_rows:
        canonical = {field: row.get(field) for field in ordered_fields}
        hasher.update(
            json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
    return hasher.hexdigest()

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
    raise ValueError("Unexpected git hash length")


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
                    logger.info("S1: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S1: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S1: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _append_rng_trace(
    rng_trace_path: Path,
    trace_rows: list[dict],
    logger,
    module: str,
    run_id_value: str,
    seed: int,
) -> None:
    rng_trace_path.parent.mkdir(parents=True, exist_ok=True)
    existing_substreams = set()
    if rng_trace_path.exists():
        with rng_trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    payload.get("run_id") == run_id_value
                    and payload.get("seed") == int(seed)
                    and payload.get("module") == module
                ):
                    substream = payload.get("substream_label")
                    if substream:
                        existing_substreams.add(substream)
    pending_rows = [row for row in trace_rows if row.get("substream_label") not in existing_substreams]
    if not pending_rows:
        logger.info("S1: rng_trace_log already contains rows for module=%s", module)
        return
    with rng_trace_path.open("a", encoding="utf-8") as handle:
        for row in pending_rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S1: appended rng_trace_log rows for module=%s", module)


def _hash_to_open_unit(exprs: list[pl.Expr], seed: int) -> pl.Expr:
    if not exprs:
        return pl.lit(0.0)
    named = [expr.alias(f"h{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    return (hashed.cast(pl.Float64) + pl.lit(0.5)) / pl.lit(float(1 << 64))


def _hash_to_id64(exprs: list[pl.Expr], seed: int) -> pl.Expr:
    if not exprs:
        return pl.lit(1).cast(pl.Int64)
    named = [expr.alias(f"k{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    modulus = (1 << 63) - 1
    return (hashed % pl.lit(modulus) + pl.lit(1)).cast(pl.Int64)


def _discover_scenario_ids(arrivals_entry: dict, tokens: dict[str, str], run_paths: RunPaths, external_roots) -> list[str]:
    wildcard_path = _resolve_dataset_path(
        arrivals_entry,
        run_paths,
        external_roots,
        tokens,
        allow_wildcards=True,
    )
    paths = glob.glob(str(wildcard_path))
    scenario_ids = set()
    for path in paths:
        parts = Path(path).parts
        for part in parts:
            if part.startswith("scenario_id="):
                scenario_ids.add(part.split("=", 1)[1])
                break
    return sorted(scenario_ids)


def _select_sealed_row(sealed_inputs: list[dict], manifest_key: str) -> dict:
    matches = [row for row in sealed_inputs if row.get("manifest_key") == manifest_key]
    if not matches:
        raise InputResolutionError(f"sealed_inputs_6B missing manifest_key={manifest_key}")
    return matches[0]


def _resolve_sealed_path(row: dict, tokens: dict[str, str], run_paths: RunPaths, external_roots) -> Path:
    path_template = row.get("path_template") or row.get("path")
    if not path_template:
        raise InputResolutionError("sealed_inputs row missing path_template")
    resolved = _render_path_template(path_template, tokens, allow_wildcards=False)
    if resolved.startswith(("data/", "logs/", "reports/")):
        return run_paths.run_root / resolved
    if resolved.startswith("artefacts/"):
        return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=False)
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _normalize_channel_group(arrivals: pl.DataFrame, default_group: str, known_groups: list[str]) -> pl.DataFrame:
    known = [str(item) for item in known_groups]
    return arrivals.with_columns(
        pl.when(pl.col("channel_group").is_null())
        .then(pl.lit(default_group))
        .otherwise(pl.col("channel_group"))
        .cast(pl.Utf8)
        .str.to_uppercase()
        .alias("channel_group")
    ).with_columns(
        pl.when(pl.col("channel_group").is_in(known))
        .then(pl.col("channel_group"))
        .otherwise(pl.lit(default_group))
        .alias("channel_group")
    )


def _publish_parquet_idempotent(
    tmp_path: Path,
    final_path: Path,
    logger,
    label: str,
    conflict_code: str,
    failure_code: str,
) -> None:
    if final_path.exists():
        tmp_digest = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        existing_digest = hashlib.sha256(final_path.read_bytes()).hexdigest()
        if tmp_digest == existing_digest:
            tmp_path.unlink(missing_ok=True)
            logger.info("S1: %s already exists and is identical; skipping publish", label)
            return
        _abort(conflict_code, "V-01", f"{label} already exists", {"path": str(final_path)}, None)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
        logger.info("S1: published %s to %s", label, final_path)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_path), "error": str(exc)}, None)


def _publish_parquet_parts(
    tmp_dir: Path,
    final_dir: Path,
    logger,
    label: str,
    conflict_code: str,
    failure_code: str,
) -> None:
    try:
        final_dir.mkdir(parents=True, exist_ok=True)
        existing_parts = sorted(final_dir.glob("part-*.parquet"))
        if existing_parts:
            for existing in existing_parts:
                existing.unlink()
            logger.warning("S1: cleared %s existing parts at %s", label, final_dir)
        tmp_parts = sorted(tmp_dir.glob("part-*.parquet"))
        if not tmp_parts:
            _abort(conflict_code, "V-01", f"{label} parts missing", {"path": str(tmp_dir)}, None)
        for part in tmp_parts:
            part.replace(final_dir / part.name)
        logger.info("S1: published %s parts to %s", label, final_dir)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_dir), "error": str(exc)}, None)

def run_s1(config: EngineConfig, run_id: Optional[str] = None, batch_rows: int = 250000) -> S1Result:
    logger = get_logger("engine.layers.l3.seg_6B.s1_attachment_session.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    seed = int(receipt.get("seed") or 0)
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    if not run_id_value:
        raise InputResolutionError(f"Missing run_id in run_receipt {receipt_path}")
    if not _HEX64_PATTERN.match(manifest_fingerprint):
        raise InputResolutionError(f"Invalid manifest_fingerprint in run_receipt {receipt_path}")
    if not _HEX64_PATTERN.match(parameter_hash):
        raise InputResolutionError(f"Invalid parameter_hash in run_receipt {receipt_path}")

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S1: run log initialized at {run_log_path}")
    logger.info(
        "S1: objective=attach arrivals to entities + sessionise; gated inputs (S0 receipt + sealed_inputs + 5B arrivals + 6A entity graph) -> outputs s1_arrival_entities_6B + s1_session_index_6B + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6b_path, dictionary_6b = load_dataset_dictionary(source, "6B")
    reg_6b_path, registry_6b = load_artefact_registry(source, "6B")
    reg_6a_path, registry_6a = load_artefact_registry(source, "6A")
    reg_5b_path, registry_5b = load_artefact_registry(source, "5B")
    schema_6b_path, schema_6b = load_schema_pack(source, "6B", "6B")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6B", "layer3")
    schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
    schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
    timer.info(
        "S1: loaded contracts (dictionary=%s registry_6b=%s registry_6a=%s registry_5b=%s schema_6b=%s schema_layer3=%s schema_6a=%s schema_5b=%s)",
        dict_6b_path,
        reg_6b_path,
        reg_6a_path,
        reg_5b_path,
        schema_6b_path,
        schema_layer3_path,
        schema_6a_path,
        schema_5b_path,
    )

    tokens = {
        "seed": str(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id_value,
    }

    receipt_entry = find_dataset_entry(dictionary_6b, "s0_gate_receipt_6B").entry
    sealed_entry = find_dataset_entry(dictionary_6b, "sealed_inputs_6B").entry
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

    if not receipt_path.exists():
        _abort(
            "S1_PRECONDITION_S0_FAILED",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if not sealed_inputs_path.exists():
        _abort(
            "S1_PRECONDITION_SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    s0_receipt = _load_json(receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "S1_PRECONDITION_SEALED_INPUTS_INVALID",
            "V-01",
            "sealed_inputs_not_list",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    _validate_payload(
        s0_receipt,
        schema_layer3,
        schema_layer3,
        "#/gate/6B/s0_gate_receipt_6B",
        manifest_fingerprint,
        {"path": str(receipt_path)},
    )
    _validate_payload(
        sealed_inputs,
        schema_layer3,
        schema_layer3,
        "#/gate/6B/sealed_inputs_6B",
        manifest_fingerprint,
        {"path": str(sealed_inputs_path)},
    )

    receipt_param_hash = str(s0_receipt.get("parameter_hash") or "")
    if receipt_param_hash and receipt_param_hash != parameter_hash:
        _abort(
            "S1_PRECONDITION_PARAMETER_HASH_MISMATCH",
            "V-01",
            "parameter_hash_mismatch",
            {"run_receipt": parameter_hash, "s0_receipt": receipt_param_hash},
            manifest_fingerprint,
        )

    upstream_segments = s0_receipt.get("upstream_segments") or {}
    required_segments = ["1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B", "6A"]
    for segment in required_segments:
        status = (upstream_segments.get(segment) or {}).get("status")
        if status != "PASS":
            _abort(
                "S1_PRECONDITION_UPSTREAM_GATE_NOT_PASS",
                "V-01",
                "upstream_gate_not_pass",
                {"segment": segment, "status": status},
                manifest_fingerprint,
            )

    digest_expected = str(s0_receipt.get("sealed_inputs_digest_6B") or "")
    digest_actual = _sealed_inputs_digest(sealed_inputs)
    if digest_expected and digest_expected != digest_actual:
        _abort(
            "S1_PRECONDITION_SEALED_INPUTS_DIGEST_MISMATCH",
            "V-01",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S1: sealed_inputs digest verified")

    required_dataset_ids = [
        "arrival_events_5B",
        "s1_party_base_6A",
        "s2_account_base_6A",
        "s3_instrument_base_6A",
        "s3_account_instrument_links_6A",
        "s4_device_base_6A",
        "s4_ip_base_6A",
        "s4_device_links_6A",
        "s4_ip_links_6A",
        "s5_party_fraud_roles_6A",
        "s5_account_fraud_roles_6A",
        "s5_device_fraud_roles_6A",
        "s5_ip_fraud_roles_6A",
    ]
    manifest_keys = {}
    for dataset_id in required_dataset_ids:
        if dataset_id.endswith("_6A"):
            registry = registry_6a
        elif dataset_id.endswith("_5B"):
            registry = registry_5b
        else:
            registry = registry_6b
        artifact_entry = find_artifact_entry(registry, dataset_id).entry
        manifest_keys[dataset_id] = str(artifact_entry.get("manifest_key") or "")
    missing_keys = [
        dataset_id for dataset_id, manifest_key in manifest_keys.items() if not manifest_key
    ]
    if missing_keys:
        _abort(
            "S1_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
            "V-01",
            "manifest_key_missing",
            {"dataset_ids": missing_keys},
            manifest_fingerprint,
        )

    for dataset_id, manifest_key in manifest_keys.items():
        row = _select_sealed_row(sealed_inputs, manifest_key)
        status = row.get("status")
        read_scope = row.get("read_scope")
        if status != "REQUIRED" or read_scope != "ROW_LEVEL":
            _abort(
                "S1_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
                "V-01",
                "sealed_inputs_status_invalid",
                {"dataset_id": dataset_id, "status": status, "read_scope": read_scope},
                manifest_fingerprint,
            )

    policy_ids = [
        "attachment_policy_6B",
        "sessionisation_policy_6B",
        "behaviour_config_6B",
        "behaviour_prior_pack_6B",
        "rng_policy_6B",
        "rng_profile_layer3",
    ]
    policy_manifest_keys = {}
    for policy_id in policy_ids:
        policy_entry = find_artifact_entry(registry_6b, policy_id).entry
        policy_manifest_keys[policy_id] = str(policy_entry.get("manifest_key") or "")

    policy_rows = {policy_id: _select_sealed_row(sealed_inputs, key) for policy_id, key in policy_manifest_keys.items()}

    attachment_policy = _load_yaml(
        _resolve_sealed_path(policy_rows["attachment_policy_6B"], tokens, run_paths, config.external_roots)
    )
    sessionisation_policy = _load_yaml(
        _resolve_sealed_path(policy_rows["sessionisation_policy_6B"], tokens, run_paths, config.external_roots)
    )
    behaviour_config = _load_yaml(
        _resolve_sealed_path(policy_rows["behaviour_config_6B"], tokens, run_paths, config.external_roots)
    )
    behaviour_prior_pack = _load_yaml(
        _resolve_sealed_path(policy_rows["behaviour_prior_pack_6B"], tokens, run_paths, config.external_roots)
    )
    rng_policy = _load_yaml(
        _resolve_sealed_path(policy_rows["rng_policy_6B"], tokens, run_paths, config.external_roots)
    )
    rng_profile = _load_yaml(
        _resolve_sealed_path(policy_rows["rng_profile_layer3"], tokens, run_paths, config.external_roots)
    )
    _ = behaviour_prior_pack
    _ = rng_profile
    _ = rng_policy

    channel_model = attachment_policy.get("channel_model") or {}
    default_channel_group = str(channel_model.get("default_channel_group") or "ECOM")
    known_channel_groups = channel_model.get("known_channel_groups") or [default_channel_group]

    scope_filters = behaviour_config.get("scope_filters") or {}
    scenario_allowlist = set(scope_filters.get("scenario_id_allowlist") or [])
    scenario_blocklist = set(scope_filters.get("scenario_id_blocklist") or [])
    seed_allowlist = set(scope_filters.get("seed_allowlist") or [])
    seed_blocklist = set(scope_filters.get("seed_blocklist") or [])
    degrade_posture = behaviour_config.get("degrade_posture") or {}
    on_scope_miss = str(degrade_posture.get("on_scope_filter_miss") or "SKIP_PARTITION")

    if seed_allowlist and seed not in seed_allowlist:
        logger.warning(
            "S1: seed=%s not in scope allowlist; posture=%s", seed, on_scope_miss
        )
        if on_scope_miss.upper() == "SKIP_PARTITION":
            return S1Result(run_id=run_id_value, parameter_hash=parameter_hash, manifest_fingerprint=manifest_fingerprint, scenario_ids=[])
        _abort(
            "S1_PRECONDITION_SCOPE_FILTER",
            "V-01",
            "seed_not_in_allowlist",
            {"seed": seed},
            manifest_fingerprint,
        )
    if seed_blocklist and seed in seed_blocklist:
        logger.warning(
            "S1: seed=%s in scope blocklist; posture=%s", seed, on_scope_miss
        )
        if on_scope_miss.upper() == "SKIP_PARTITION":
            return S1Result(run_id=run_id_value, parameter_hash=parameter_hash, manifest_fingerprint=manifest_fingerprint, scenario_ids=[])
        _abort(
            "S1_PRECONDITION_SCOPE_FILTER",
            "V-01",
            "seed_in_blocklist",
            {"seed": seed},
            manifest_fingerprint,
        )

    arrival_manifest_key = manifest_keys["arrival_events_5B"]
    arrival_row = _select_sealed_row(sealed_inputs, arrival_manifest_key)
    arrivals_entry = find_dataset_entry(dictionary_6b, "arrival_events_5B").entry
    _ = arrival_row

    scenario_ids = _discover_scenario_ids(arrivals_entry, tokens, run_paths, config.external_roots)
    if not scenario_ids:
        _abort(
            "S1_PRECONDITION_ARRIVALS_MISSING",
            "V-01",
            "no_arrival_partitions_found",
            {"path": arrival_row.get("path_template")},
            manifest_fingerprint,
        )

    logger.info("S1: discovered scenario_ids=%s", scenario_ids)

    def _scenario_in_scope(scenario_id: str) -> bool:
        if scenario_allowlist and scenario_id not in scenario_allowlist:
            return False
        if scenario_blocklist and scenario_id in scenario_blocklist:
            return False
        return True

    # Load 6A entity surfaces once per seed.
    party_entry = find_dataset_entry(dictionary_6b, "s1_party_base_6A").entry
    account_entry = find_dataset_entry(dictionary_6b, "s2_account_base_6A").entry
    instrument_entry = find_dataset_entry(dictionary_6b, "s3_instrument_base_6A").entry
    account_instrument_entry = find_dataset_entry(dictionary_6b, "s3_account_instrument_links_6A").entry
    device_entry = find_dataset_entry(dictionary_6b, "s4_device_base_6A").entry
    ip_entry = find_dataset_entry(dictionary_6b, "s4_ip_base_6A").entry
    device_links_entry = find_dataset_entry(dictionary_6b, "s4_device_links_6A").entry
    ip_links_entry = find_dataset_entry(dictionary_6b, "s4_ip_links_6A").entry

    party_path = _resolve_dataset_path(party_entry, run_paths, config.external_roots, tokens)
    account_path = _resolve_dataset_path(account_entry, run_paths, config.external_roots, tokens)
    instrument_path = _resolve_dataset_path(instrument_entry, run_paths, config.external_roots, tokens)
    account_instrument_path = _resolve_dataset_path(account_instrument_entry, run_paths, config.external_roots, tokens)
    device_path = _resolve_dataset_path(device_entry, run_paths, config.external_roots, tokens)
    ip_path = _resolve_dataset_path(ip_entry, run_paths, config.external_roots, tokens)
    device_links_path = _resolve_dataset_path(device_links_entry, run_paths, config.external_roots, tokens)
    ip_links_path = _resolve_dataset_path(ip_links_entry, run_paths, config.external_roots, tokens)

    party_base = _read_parquet(party_path, columns=["party_id", "country_iso", "segment_id"])
    account_base = _read_parquet(account_path, columns=["account_id", "owner_party_id", "account_type"])
    _ = _read_parquet(instrument_path, columns=["instrument_id", "account_id"])  # ensures presence
    account_instruments = _read_parquet(account_instrument_path, columns=["account_id", "instrument_id"])
    device_base = _read_parquet(device_path, columns=["device_id", "primary_party_id"])
    _ = _read_parquet(ip_path, columns=["ip_id"])  # ensures presence
    device_links = _read_parquet(device_links_path, columns=["device_id", "party_id"])
    ip_links = _read_parquet(ip_links_path, columns=["device_id", "ip_id", "party_id"])
    _ = device_base

    if party_base.is_empty():
        _abort(
            "S1_PRECONDITION_ENTITY_EMPTY",
            "V-01",
            "party_base_empty",
            {"path": str(party_path)},
            manifest_fingerprint,
        )

    account_base = account_base.drop_nulls(["account_id", "owner_party_id"])
    account_instruments = account_instruments.drop_nulls(["account_id", "instrument_id"])
    device_links = device_links.drop_nulls(["device_id", "party_id"])
    ip_links = ip_links.drop_nulls(["device_id", "ip_id", "party_id"])

    device_links = device_links.join(ip_links.select("device_id").unique(), on="device_id", how="inner")
    device_links = device_links.sort(["party_id", "device_id"]).with_columns(
        (pl.col("device_id").cum_count().over("party_id") - 1).alias("device_index"),
        pl.len().over("party_id").alias("device_count"),
    )

    account_instruments = account_instruments.sort(["account_id", "instrument_id"]).with_columns(
        (pl.col("instrument_id").cum_count().over("account_id") - 1).alias("instrument_index"),
        pl.len().over("account_id").alias("instrument_count"),
    )

    instrument_counts = account_instruments.select(["account_id", "instrument_count"]).unique()
    account_base = account_base.join(instrument_counts, on="account_id", how="inner")
    account_base = account_base.sort(["owner_party_id", "account_id"]).with_columns(
        (pl.col("account_id").cum_count().over("owner_party_id") - 1).alias("account_index"),
        pl.len().over("owner_party_id").alias("account_count"),
    )

    ip_links = ip_links.sort(["device_id", "ip_id"]).with_columns(
        (pl.col("ip_id").cum_count().over("device_id") - 1).alias("ip_index"),
        pl.len().over("device_id").alias("ip_count"),
    )

    party_accounts = account_base.select(["owner_party_id", "account_count"]).unique().rename(
        {"owner_party_id": "party_id"}
    )
    party_devices = device_links.select(["party_id", "device_count"]).unique()
    party_candidates = party_accounts.join(party_devices, on="party_id", how="inner")
    party_candidates = party_candidates.join(party_base.select(["party_id"]).unique(), on="party_id", how="inner")
    party_candidates = party_candidates.sort("party_id").with_row_count("party_index")

    account_counts = account_base.select(["owner_party_id", "account_count"]).unique().rename(
        {"owner_party_id": "party_id"}
    )
    account_index_df = account_base.select(["owner_party_id", "account_index", "account_id"]).rename(
        {"owner_party_id": "party_id"}
    )
    instrument_counts = account_instruments.select(["account_id", "instrument_count"]).unique()
    instrument_index_df = account_instruments.select(["account_id", "instrument_index", "instrument_id"])
    device_counts = device_links.select(["party_id", "device_count"]).unique()
    device_index_df = device_links.select(["party_id", "device_index", "device_id"])
    ip_counts = ip_links.select(["device_id", "ip_count"]).unique()
    ip_index_df = ip_links.select(["device_id", "ip_index", "ip_id"])

    party_count = party_candidates.height
    if party_count == 0:
        _abort(
            "S1_PRECONDITION_ENTITY_EMPTY",
            "V-01",
            "no_eligible_parties",
            {},
            manifest_fingerprint,
        )

    logger.info(
        "S1: candidate pools ready (eligible_parties=%s, accounts_with_instruments=%s, devices_with_ips=%s, ip_links=%s)",
        party_count,
        account_base.height,
        device_links.height,
        ip_links.height,
    )
    logger.warning(
        "S1: attachment_policy uses arrival.legal_country_iso but 5B arrivals do not include it; using global party pool only"
    )
    logger.warning(
        "S1: merchant-linked device/IP candidates not available in 6A links; using party-linked devices and device-linked IPs"
    )

    feature_flags = (behaviour_config.get("feature_flags") or {}).get("s1") or {}
    enable_steps = feature_flags.get("enable_attachment_steps") or {}
    enable_sessionisation = bool(feature_flags.get("enable_sessionisation", True))
    if not enable_sessionisation:
        _abort(
            "S1_PRECONDITION_SESSION_DISABLED",
            "V-01",
            "sessionisation_disabled",
            {},
            manifest_fingerprint,
        )

    step_order = attachment_policy.get("attachment_steps_order") or [
        "PARTY",
        "ACCOUNT",
        "INSTRUMENT",
        "DEVICE",
        "IP",
    ]
    enabled_steps = [step for step in step_order if enable_steps.get(f"ATTACH_{step}", True)]
    if len(enabled_steps) != len(step_order):
        logger.warning(
            "S1: enable_attachment_steps disables some steps (%s); proceeding with full attachment to satisfy required outputs",
            enable_steps,
        )
        enabled_steps = step_order

    rng_draws_entity_attach = 0
    rng_events_entity_attach = 0
    rng_draws_session_boundary = 0
    rng_events_session_boundary = 0

    tracker = _ProgressTracker(len(scenario_ids), logger, "S1: scenarios processed")
    processed_scenarios: list[str] = []

    batch_rows = max(int(batch_rows or 0), 1000)
    logger.info("S1: batch_rows=%s for arrival processing", batch_rows)

    for scenario_id in scenario_ids:
        if not _scenario_in_scope(scenario_id):
            logger.warning(
                "S1: scenario_id=%s outside scope filters; posture=%s", scenario_id, on_scope_miss
            )
            if on_scope_miss.upper() == "SKIP_PARTITION":
                tracker.update(1)
                continue
            _abort(
                "S1_PRECONDITION_SCOPE_FILTER",
                "V-01",
                "scenario_not_in_scope",
                {"scenario_id": scenario_id},
                manifest_fingerprint,
            )

        tokens_local = {**tokens, "scenario_id": str(scenario_id)}
        arrivals_path = _resolve_dataset_path(arrivals_entry, run_paths, config.external_roots, tokens_local)
        arrivals_files = _list_parquet_files(arrivals_path, allow_empty=True)

        arrival_out_entry = find_dataset_entry(dictionary_6b, "s1_arrival_entities_6B").entry
        session_out_entry = find_dataset_entry(dictionary_6b, "s1_session_index_6B").entry
        arrival_out_path = _resolve_dataset_path(arrival_out_entry, run_paths, config.external_roots, tokens_local)
        session_out_path = _resolve_dataset_path(session_out_entry, run_paths, config.external_roots, tokens_local)

        tmp_root = run_paths.tmp_root
        tmp_root.mkdir(parents=True, exist_ok=True)
        arrival_tmp_dir = tmp_root / f"s1_arrival_entities_6B_{scenario_id}"
        session_tmp_dir = tmp_root / f"s1_session_index_6B_{scenario_id}_summaries"
        arrival_tmp_dir.mkdir(parents=True, exist_ok=True)
        session_tmp_dir.mkdir(parents=True, exist_ok=True)
        for existing in arrival_tmp_dir.glob("part-*.parquet"):
            existing.unlink()
        for existing in session_tmp_dir.glob("part-*.parquet"):
            existing.unlink()

        empty_arrival_entities = pl.DataFrame(
            schema={
                "scenario_id": pl.Utf8,
                "arrival_seq": pl.Int64,
                "merchant_id": pl.UInt64,
                "ts_utc": pl.Utf8,
                "party_id": pl.Int64,
                "account_id": pl.Int64,
                "instrument_id": pl.Int64,
                "device_id": pl.Int64,
                "ip_id": pl.Int64,
                "session_id": pl.Int64,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
            }
        )
        empty_session_index = pl.DataFrame(
            schema={
                "session_id": pl.Int64,
                "arrival_count": pl.Int64,
                "session_start_utc": pl.Utf8,
                "session_end_utc": pl.Utf8,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "scenario_id": pl.Utf8,
                "party_id": pl.Int64,
                "device_id": pl.Int64,
                "account_id": pl.Int64,
                "instrument_id": pl.Int64,
                "merchant_id": pl.UInt64,
            }
        )

        if not arrivals_files:
            logger.info(
                "S1: scenario_id=%s has no arrival parquet files; emitting empty outputs", scenario_id
            )
            arrival_part = arrival_tmp_dir / "part-00000.parquet"
            empty_arrival_entities.write_parquet(arrival_part, compression="zstd")
            session_index = empty_session_index
        else:
            total_rows = _count_parquet_rows(arrivals_files)
            logger.info(
                "S1: scenario_id=%s arrivals_in_scope=%s (seed=%s, manifest_fingerprint=%s)",
                scenario_id,
                total_rows,
                seed,
                manifest_fingerprint,
            )
            progress = _ProgressTracker(
                total_rows,
                logger,
                f"S1: scenario_id={scenario_id} arrivals_processed",
            )
            session_fields = (sessionisation_policy.get("session_key") or {}).get("fields") or []
            if not session_fields:
                session_fields = ["scenario_id", "merchant_id", "channel_group"]
                logger.warning(
                    "S1: session_key fields missing; defaulting to %s",
                    session_fields,
                )
            allowed_fields = {
                "scenario_id",
                "merchant_id",
                "channel_group",
                "party_id",
                "device_id",
                "account_id",
                "instrument_id",
                "arrival_seq",
                "ts_utc",
                "ip_id",
            }
            missing_fields = [field for field in session_fields if field not in allowed_fields]
            if missing_fields:
                _abort(
                    "S1_SESSION_KEY_INVALID",
                    "V-01",
                    "session_key_fields_missing",
                    {"missing": missing_fields},
                    manifest_fingerprint,
                )
            boundary_rules = sessionisation_policy.get("boundary_rules") or {}
            hard_timeout = float(boundary_rules.get("hard_timeout_seconds") or 1200)
            if hard_timeout <= 0:
                hard_timeout = 1200.0
            logger.warning(
                "S1: sessionisation uses fixed %ss buckets (hard_break/day-boundary ignored) to avoid global sort",
                int(hard_timeout),
            )
            domain_tag = str(
                (sessionisation_policy.get("session_id") or {}).get("domain_tag") or "mlr:6B.session_id.v1"
            )
            session_seed = int.from_bytes(hashlib.sha256(domain_tag.encode("utf-8")).digest()[:8], "little")

            part_index = 0
            sample_arrival = None

            for arrivals in _iter_parquet_batches(
                arrivals_files,
                ["scenario_id", "arrival_seq", "merchant_id", "ts_utc", "channel_group"],
                batch_rows,
            ):
                arrivals = arrivals.with_columns(
                    pl.col("arrival_seq").cast(pl.Int64),
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("scenario_id").cast(pl.Utf8),
                    pl.col("ts_utc").cast(pl.Utf8),
                )
                arrivals = _normalize_channel_group(arrivals, default_channel_group, known_channel_groups)

                u_party = _hash_to_open_unit(
                    [
                        pl.lit(manifest_fingerprint),
                        pl.lit(parameter_hash),
                        pl.lit(seed),
                        pl.col("scenario_id"),
                        pl.col("merchant_id"),
                        pl.col("arrival_seq"),
                        pl.lit("ATTACH_PARTY"),
                    ],
                    seed=seed,
                )
                arrivals = arrivals.with_columns(
                    (u_party * pl.lit(float(party_count))).floor().cast(pl.Int64).alias("party_index")
                )
                arrivals = arrivals.join(
                    party_candidates.select(["party_index", "party_id"]),
                    on="party_index",
                    how="left",
                ).drop("party_index")
                if arrivals.get_column("party_id").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "party_attach_failed",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                arrivals = arrivals.join(account_counts, on="party_id", how="left")
                if arrivals.get_column("account_count").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "account_candidates_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
                u_account = _hash_to_open_unit(
                    [
                        pl.lit(manifest_fingerprint),
                        pl.lit(parameter_hash),
                        pl.lit(seed),
                        pl.col("scenario_id"),
                        pl.col("merchant_id"),
                        pl.col("arrival_seq"),
                        pl.lit("ATTACH_ACCOUNT"),
                    ],
                    seed=seed,
                )
                arrivals = arrivals.with_columns(
                    (u_account * pl.col("account_count").cast(pl.Float64))
                    .floor()
                    .cast(pl.Int64)
                    .alias("account_index")
                )
                arrivals = arrivals.join(account_index_df, on=["party_id", "account_index"], how="left")
                if arrivals.get_column("account_id").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "account_attach_failed",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                arrivals = arrivals.join(instrument_counts, on="account_id", how="left")
                if arrivals.get_column("instrument_count").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "instrument_candidates_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
                u_instrument = _hash_to_open_unit(
                    [
                        pl.lit(manifest_fingerprint),
                        pl.lit(parameter_hash),
                        pl.lit(seed),
                        pl.col("scenario_id"),
                        pl.col("merchant_id"),
                        pl.col("arrival_seq"),
                        pl.lit("ATTACH_INSTRUMENT"),
                    ],
                    seed=seed,
                )
                arrivals = arrivals.with_columns(
                    (u_instrument * pl.col("instrument_count").cast(pl.Float64))
                    .floor()
                    .cast(pl.Int64)
                    .alias("instrument_index")
                )
                arrivals = arrivals.join(instrument_index_df, on=["account_id", "instrument_index"], how="left")
                if arrivals.get_column("instrument_id").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "instrument_attach_failed",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                arrivals = arrivals.join(device_counts, on="party_id", how="left")
                if arrivals.get_column("device_count").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "device_candidates_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
                u_device = _hash_to_open_unit(
                    [
                        pl.lit(manifest_fingerprint),
                        pl.lit(parameter_hash),
                        pl.lit(seed),
                        pl.col("scenario_id"),
                        pl.col("merchant_id"),
                        pl.col("arrival_seq"),
                        pl.lit("ATTACH_DEVICE"),
                    ],
                    seed=seed,
                )
                arrivals = arrivals.with_columns(
                    (u_device * pl.col("device_count").cast(pl.Float64))
                    .floor()
                    .cast(pl.Int64)
                    .alias("device_index")
                )
                arrivals = arrivals.join(device_index_df, on=["party_id", "device_index"], how="left")
                if arrivals.get_column("device_id").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "device_attach_failed",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                arrivals = arrivals.join(ip_counts, on="device_id", how="left")
                if arrivals.get_column("ip_count").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "ip_candidates_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )
                u_ip = _hash_to_open_unit(
                    [
                        pl.lit(manifest_fingerprint),
                        pl.lit(parameter_hash),
                        pl.lit(seed),
                        pl.col("scenario_id"),
                        pl.col("merchant_id"),
                        pl.col("arrival_seq"),
                        pl.lit("ATTACH_IP"),
                    ],
                    seed=seed,
                )
                arrivals = arrivals.with_columns(
                    (u_ip * pl.col("ip_count").cast(pl.Float64))
                    .floor()
                    .cast(pl.Int64)
                    .alias("ip_index")
                )
                arrivals = arrivals.join(ip_index_df, on=["device_id", "ip_index"], how="left")
                if arrivals.get_column("ip_id").null_count() > 0:
                    _abort(
                        "S1_ENTITY_REFERENCE_INVALID",
                        "V-01",
                        "ip_attach_failed",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                batch_count = arrivals.height
                party_draws = batch_count if party_count > 1 else 0
                account_draws = arrivals.select((pl.col("account_count") > 1).sum()).item()
                instrument_draws = arrivals.select((pl.col("instrument_count") > 1).sum()).item()
                device_draws = arrivals.select((pl.col("device_count") > 1).sum()).item()
                ip_draws = arrivals.select((pl.col("ip_count") > 1).sum()).item()
                rng_draws_entity_attach += int(
                    party_draws + account_draws + instrument_draws + device_draws + ip_draws
                )
                rng_events_entity_attach += int(batch_count * len(enabled_steps))

                session_key_base = pl.concat_str(
                    [pl.col(field).cast(pl.Utf8) for field in session_fields], separator="|"
                )
                arrivals = arrivals.with_columns(
                    session_key_base.alias("session_key_base"),
                    pl.col("ts_utc")
                    .str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S%.fZ", strict=False)
                    .alias("ts_dt"),
                )
                arrivals = arrivals.with_columns(
                    (pl.col("ts_dt").dt.epoch("s") / pl.lit(float(hard_timeout)))
                    .floor()
                    .cast(pl.Int64)
                    .alias("session_bucket")
                )
                arrivals = arrivals.with_columns(
                    _hash_to_id64(
                        [
                            pl.lit(domain_tag),
                            pl.col("session_key_base"),
                            pl.col("session_bucket"),
                        ],
                        seed=session_seed,
                    ).alias("session_id")
                )

                arrival_entities = arrivals.select(
                    [
                        "scenario_id",
                        "arrival_seq",
                        "merchant_id",
                        "ts_utc",
                        "party_id",
                        "account_id",
                        "instrument_id",
                        "device_id",
                        "ip_id",
                        "session_id",
                    ]
                ).with_columns(
                    pl.lit(int(seed)).alias("seed"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                )

                if sample_arrival is None and arrival_entities.height > 0:
                    sample_arrival = arrival_entities.head(1).to_dicts()[0]

                arrival_part = arrival_tmp_dir / f"part-{part_index:05d}.parquet"
                arrival_entities.write_parquet(arrival_part, compression="zstd")

                session_summary = arrival_entities.group_by("session_id").agg(
                    pl.len().alias("arrival_count"),
                    pl.min("ts_utc").alias("session_start_utc"),
                    pl.max("ts_utc").alias("session_end_utc"),
                    pl.first("seed").alias("seed"),
                    pl.first("manifest_fingerprint").alias("manifest_fingerprint"),
                    pl.first("scenario_id").alias("scenario_id"),
                    pl.first("party_id").alias("party_id"),
                    pl.first("device_id").alias("device_id"),
                    pl.first("account_id").alias("account_id"),
                    pl.first("instrument_id").alias("instrument_id"),
                    pl.first("merchant_id").alias("merchant_id"),
                )
                session_part = session_tmp_dir / f"part-{part_index:05d}.parquet"
                session_summary.write_parquet(session_part, compression="zstd")

                part_index += 1
                progress.update(batch_count)

            if part_index == 0:
                arrival_part = arrival_tmp_dir / "part-00000.parquet"
                empty_arrival_entities.write_parquet(arrival_part, compression="zstd")
                session_index = empty_session_index
            else:
                if sample_arrival is not None:
                    _validate_payload(
                        sample_arrival,
                        schema_6b,
                        schema_layer3,
                        "#/s1/arrival_entities_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )

                session_index = (
                    pl.scan_parquet(str(session_tmp_dir / "part-*.parquet"))
                    .group_by("session_id")
                    .agg(
                        pl.sum("arrival_count").alias("arrival_count"),
                        pl.min("session_start_utc").alias("session_start_utc"),
                        pl.max("session_end_utc").alias("session_end_utc"),
                        pl.first("seed").alias("seed"),
                        pl.first("manifest_fingerprint").alias("manifest_fingerprint"),
                        pl.first("scenario_id").alias("scenario_id"),
                        pl.first("party_id").alias("party_id"),
                        pl.first("device_id").alias("device_id"),
                        pl.first("account_id").alias("account_id"),
                        pl.first("instrument_id").alias("instrument_id"),
                        pl.first("merchant_id").alias("merchant_id"),
                    )
                    .collect(streaming=True)
                )

                if session_index.height > 0:
                    _validate_payload(
                        session_index.head(1).to_dicts()[0],
                        schema_6b,
                        schema_layer3,
                        "#/s1/session_index_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )

                logger.info(
                    "S1: scenario_id=%s attachments_complete arrivals=%s sessions=%s",
                    scenario_id,
                    total_rows,
                    session_index.height,
                )

        session_tmp = tmp_root / f"s1_session_index_6B_{scenario_id}.parquet"
        session_index.write_parquet(session_tmp, compression="zstd")

        arrival_out_dir = _materialize_parquet_path(arrival_out_path).parent
        session_out_file = _materialize_parquet_path(session_out_path)

        _publish_parquet_parts(
            arrival_tmp_dir,
            arrival_out_dir,
            logger,
            f"s1_arrival_entities_6B (scenario_id={scenario_id})",
            "6B.S1.IO_WRITE_CONFLICT",
            "6B.S1.IO_WRITE_FAILED",
        )
        _publish_parquet_idempotent(
            session_tmp,
            session_out_file,
            logger,
            f"s1_session_index_6B (scenario_id={scenario_id})",
            "6B.S1.IO_WRITE_CONFLICT",
            "6B.S1.IO_WRITE_FAILED",
        )

        processed_scenarios.append(str(scenario_id))
        tracker.update(1)

    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6B.S1 deterministic hash attachment/sessionisation audit",
    }
    rng_audit_entry = {key: value if value is not None else None for key, value in rng_audit_entry.items()}
    rng_audit_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_audit_log").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    _ensure_rng_audit(rng_audit_path, rng_audit_entry, logger)

    rng_trace_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_trace_log").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    entity_blocks = int(math.ceil(rng_draws_entity_attach / 2.0))
    session_blocks = int(math.ceil(rng_draws_session_boundary / 2.0))
    trace_rows = [
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6B.S1",
            "substream_label": "rng_event_entity_attach",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": entity_blocks,
            "rng_counter_after_hi": 0,
            "draws_total": int(rng_draws_entity_attach),
            "blocks_total": int(entity_blocks),
            "events_total": int(rng_events_entity_attach),
        },
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6B.S1",
            "substream_label": "rng_event_session_boundary",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": session_blocks,
            "rng_counter_after_hi": 0,
            "draws_total": int(rng_draws_session_boundary),
            "blocks_total": int(session_blocks),
            "events_total": int(rng_events_session_boundary),
        },
    ]
    _append_rng_trace(rng_trace_path, trace_rows, logger, "6B.S1", run_id_value, seed)

    timer.info("S1: completed attachment/sessionisation")
    return S1Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        scenario_ids=processed_scenarios,
    )
