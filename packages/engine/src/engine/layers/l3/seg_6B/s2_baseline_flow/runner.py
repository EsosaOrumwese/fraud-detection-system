"""S2 baseline flow synthesis for Segment 6B."""

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

import numpy as np
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


MODULE_NAME = "6B.s2_baseline_flow"
SEGMENT = "6B"
STATE = "S2"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    scenario_ids: list[str]
    flow_count: int
    event_count: int


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
    logger = get_logger("engine.layers.l3.seg_6B.s2_baseline_flow.runner")
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

def _materialize_parquet_path(path: Path) -> Path:
    if "*" in path.name or "?" in path.name:
        return path.with_name("part-00000.parquet")
    if path.is_dir():
        return path / "part-00000.parquet"
    return path


def _materialize_jsonl_path(path: Path) -> Path:
    if "*" in path.name or "?" in path.name:
        return path.with_name("part-00000.jsonl")
    if path.is_dir():
        return path / "part-00000.jsonl"
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
        items_schema = dict(schema)
        defs = items_schema.get("$defs")
        schema = {"type": "array", "items": items_schema}
        if defs:
            schema["$defs"] = defs
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "6B.S2.SCHEMA_INVALID",
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
        logger.info("S2: rng_trace_log already contains rows for module=%s", module)
        return
    with rng_trace_path.open("a", encoding="utf-8") as handle:
        for row in pending_rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S2: appended rng_trace_log rows for module=%s", module)


def _hash_to_id64(exprs: list[pl.Expr], seed: int) -> pl.Expr:
    if not exprs:
        return pl.lit(1).cast(pl.Int64)
    named = [expr.alias(f"k{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    modulus = (1 << 63) - 1
    return (hashed % pl.lit(modulus) + pl.lit(1)).cast(pl.Int64)


def _hash_to_index(exprs: list[pl.Expr], seed: int, modulus: int) -> pl.Expr:
    if modulus <= 0:
        return pl.lit(0).cast(pl.Int64)
    named = [expr.alias(f"k{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    return (hashed % pl.lit(int(modulus))).cast(pl.Int64)


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


def _select_sealed_row_optional(
    sealed_inputs: list[dict],
    manifest_key: str,
    logger,
    dataset_id: str,
) -> Optional[dict]:
    try:
        return _select_sealed_row(sealed_inputs, manifest_key)
    except InputResolutionError:
        logger.warning(
            "S2: sealed_inputs missing for %s (manifest_key=%s); using run-local output path",
            dataset_id,
            manifest_key,
        )
        return None


def _publish_file_idempotent(
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
            logger.info("S2: %s already exists and is identical; skipping publish", label)
            return
        _abort(conflict_code, "V-01", f"{label} already exists", {"path": str(final_path)}, None)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
        logger.info("S2: published %s to %s", label, final_path)
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
            logger.warning("S2: cleared %s existing parts at %s", label, final_dir)
        tmp_parts = sorted(tmp_dir.glob("part-*.parquet"))
        if not tmp_parts:
            _abort(conflict_code, "V-01", f"{label} parts missing", {"path": str(tmp_dir)}, None)
        for part in tmp_parts:
            part.replace(final_dir / part.name)
        logger.info("S2: published %s parts to %s", label, final_dir)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_dir), "error": str(exc)}, None)


def _extract_price_points(amount_model: dict, logger) -> list[int]:
    families = amount_model.get("amount_families") if isinstance(amount_model, dict) else None
    if isinstance(families, dict):
        purchase = families.get("PURCHASE") or {}
        base = purchase.get("base_distribution") or {}
        price_points = base.get("price_points_minor")
        if isinstance(price_points, list) and price_points:
            return [int(value) for value in price_points]
        for family in families.values():
            if not isinstance(family, dict):
                continue
            base = family.get("base_distribution") or {}
            price_points = base.get("price_points_minor")
            if isinstance(price_points, list) and price_points:
                logger.warning("S2: using fallback price_points_minor from non-PURCHASE family")
                return [int(value) for value in price_points]
    logger.warning("S2: amount_model_6B missing price_points_minor; using default price points")
    return [199, 499, 999, 1499, 1999, 2999, 4999, 9999]

def run_s2(
    config: EngineConfig,
    run_id: Optional[str] = None,
    batch_rows: int = 250000,
    parquet_compression: str = "zstd",
) -> S2Result:
    logger = get_logger("engine.layers.l3.seg_6B.s2_baseline_flow.runner")
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

    if batch_rows <= 0:
        _abort(
            "S2_CONFIG_INVALID",
            "V-01",
            "batch_rows_invalid",
            {"batch_rows": batch_rows},
            manifest_fingerprint,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S2: run log initialized at {run_log_path}")
    logger.info(
        "S2: objective=baseline flows/events (all-legit); gated inputs (S0 receipt + sealed_inputs + S1 outputs + S2 policies) -> outputs s2_flow_anchor_baseline_6B + s2_event_stream_baseline_6B + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6b_path, dictionary_6b = load_dataset_dictionary(source, "6B")
    reg_6b_path, registry_6b = load_artefact_registry(source, "6B")
    schema_6b_path, schema_6b = load_schema_pack(source, "6B", "6B")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6B", "layer3")
    timer.info(
        "S2: loaded contracts (dictionary=%s registry=%s schema_6b=%s schema_layer3=%s)",
        dict_6b_path,
        reg_6b_path,
        schema_6b_path,
        schema_layer3_path,
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
            "S2_PRECONDITION_S0_FAILED",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if not sealed_inputs_path.exists():
        _abort(
            "S2_PRECONDITION_SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    s0_receipt = _load_json(receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "S2_PRECONDITION_SEALED_INPUTS_INVALID",
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
            "S2_PRECONDITION_PARAMETER_HASH_MISMATCH",
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
                "S2_PRECONDITION_UPSTREAM_GATE_NOT_PASS",
                "V-01",
                "upstream_gate_not_pass",
                {"segment": segment, "status": status},
                manifest_fingerprint,
            )

    digest_expected = str(s0_receipt.get("sealed_inputs_digest_6B") or "")
    digest_actual = _sealed_inputs_digest(sealed_inputs)
    if digest_expected and digest_expected != digest_actual:
        _abort(
            "S2_PRECONDITION_SEALED_INPUTS_DIGEST_MISMATCH",
            "V-01",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S2: sealed_inputs digest verified")
    required_dataset_ids = [
        "s1_arrival_entities_6B",
        "s1_session_index_6B",
    ]
    manifest_keys = {}
    for dataset_id in required_dataset_ids:
        artifact_entry = find_artifact_entry(registry_6b, dataset_id).entry
        manifest_keys[dataset_id] = str(artifact_entry.get("manifest_key") or "")
    missing_keys = [
        dataset_id for dataset_id, manifest_key in manifest_keys.items() if not manifest_key
    ]
    if missing_keys:
        _abort(
            "S2_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
            "V-01",
            "manifest_key_missing",
            {"dataset_ids": missing_keys},
            manifest_fingerprint,
        )

    for dataset_id, manifest_key in manifest_keys.items():
        row = _select_sealed_row_optional(sealed_inputs, manifest_key, logger, dataset_id)
        if row is None:
            continue
        status = row.get("status")
        read_scope = row.get("read_scope")
        if status != "REQUIRED" or read_scope != "ROW_LEVEL":
            _abort(
                "S2_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
                "V-01",
                "sealed_inputs_status_invalid",
                {"dataset_id": dataset_id, "status": status, "read_scope": read_scope},
                manifest_fingerprint,
            )

    policy_ids = [
        "behaviour_config_6B",
        "behaviour_prior_pack_6B",
        "flow_shape_policy_6B",
        "amount_model_6B",
        "timing_policy_6B",
        "flow_rng_policy_6B",
        "rng_profile_layer3",
    ]
    policy_manifest_keys = {}
    for policy_id in policy_ids:
        policy_entry = find_artifact_entry(registry_6b, policy_id).entry
        policy_manifest_keys[policy_id] = str(policy_entry.get("manifest_key") or "")

    policy_rows = {policy_id: _select_sealed_row(sealed_inputs, key) for policy_id, key in policy_manifest_keys.items()}

    def _load_policy(policy_id: str) -> object:
        row = policy_rows[policy_id]
        status = row.get("status")
        if status not in {"REQUIRED", "OPTIONAL"}:
            _abort(
                "S2_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
                "V-01",
                "policy_status_invalid",
                {"policy_id": policy_id, "status": status},
                manifest_fingerprint,
            )
        if status == "OPTIONAL":
            logger.warning(
                "S2: policy %s marked OPTIONAL in sealed_inputs; proceeding with provided config",
                policy_id,
            )
        path = _resolve_sealed_path(row, tokens, run_paths, config.external_roots)
        return _load_yaml(path)

    behaviour_config = _load_policy("behaviour_config_6B")
    behaviour_prior_pack = _load_policy("behaviour_prior_pack_6B")
    flow_shape_policy = _load_policy("flow_shape_policy_6B")
    amount_model = _load_policy("amount_model_6B")
    timing_policy = _load_policy("timing_policy_6B")
    flow_rng_policy = _load_policy("flow_rng_policy_6B")
    rng_profile = _load_policy("rng_profile_layer3")
    _ = behaviour_prior_pack
    _ = flow_shape_policy
    _ = timing_policy
    _ = flow_rng_policy
    _ = rng_profile

    for policy_id, payload in {
        "behaviour_config_6B": behaviour_config,
        "behaviour_prior_pack_6B": behaviour_prior_pack,
        "flow_shape_policy_6B": flow_shape_policy,
        "amount_model_6B": amount_model,
        "timing_policy_6B": timing_policy,
        "flow_rng_policy_6B": flow_rng_policy,
        "rng_profile_layer3": rng_profile,
    }.items():
        entry = find_dataset_entry(dictionary_6b, policy_id).entry
        schema_ref = str(entry.get("schema_ref") or "")
        if not schema_ref:
            continue
        if "#" not in schema_ref:
            _abort(
                "S2_PRECONDITION_SCHEMA_REF_INVALID",
                "V-01",
                "schema_ref_missing",
                {"policy_id": policy_id, "schema_ref": schema_ref},
                manifest_fingerprint,
            )
        anchor = "#" + schema_ref.split("#", 1)[1]
        pack = schema_layer3 if schema_ref.startswith("schemas.layer3.yaml") else schema_6b
        _validate_payload(payload, pack, schema_layer3, anchor, manifest_fingerprint, {"policy_id": policy_id})

    scope_filters = behaviour_config.get("scope_filters") if isinstance(behaviour_config, dict) else {}
    scope_filters = scope_filters if isinstance(scope_filters, dict) else {}
    seed_allowlist = set(scope_filters.get("seed_allowlist") or [])
    seed_blocklist = set(scope_filters.get("seed_blocklist") or [])
    scenario_allowlist = set(scope_filters.get("scenario_id_allowlist") or [])
    scenario_blocklist = set(scope_filters.get("scenario_id_blocklist") or [])
    degrade_posture = behaviour_config.get("degrade_posture") if isinstance(behaviour_config, dict) else {}
    degrade_posture = degrade_posture if isinstance(degrade_posture, dict) else {}
    on_scope_miss = str(degrade_posture.get("on_scope_filter_miss") or "SKIP_PARTITION")

    if seed_allowlist and seed not in seed_allowlist:
        _abort(
            "S2_PRECONDITION_SCOPE_FILTER",
            "V-01",
            "seed_not_in_allowlist",
            {"seed": seed},
            manifest_fingerprint,
        )
    if seed_blocklist and seed in seed_blocklist:
        _abort(
            "S2_PRECONDITION_SCOPE_FILTER",
            "V-01",
            "seed_in_blocklist",
            {"seed": seed},
            manifest_fingerprint,
        )

    arrivals_entry = find_dataset_entry(dictionary_6b, "s1_arrival_entities_6B").entry
    scenario_ids = _discover_scenario_ids(arrivals_entry, tokens, run_paths, config.external_roots)
    if not scenario_ids:
        _abort(
            "S2_PRECONDITION_S1_MISSING",
            "V-01",
            "no_arrival_partitions_found",
            {"path": arrivals_entry.get("path") or arrivals_entry.get("path_template")},
            manifest_fingerprint,
        )

    logger.info("S2: discovered scenario_ids=%s", scenario_ids)

    def _scenario_in_scope(scenario_id: str) -> bool:
        if scenario_allowlist and scenario_id not in scenario_allowlist:
            return False
        if scenario_blocklist and scenario_id in scenario_blocklist:
            return False
        return True

    compression_map = {
        "zstd": "zstd",
        "lz4": "lz4",
        "snappy": "snappy",
        "uncompressed": "uncompressed",
        "none": "uncompressed",
    }
    compression = str(parquet_compression).lower().strip()
    if compression not in compression_map:
        _abort(
            "S2_CONFIG_INVALID",
            "V-01",
            "parquet_compression_invalid",
            {"value": parquet_compression},
            manifest_fingerprint,
        )
    parquet_compression = compression_map[compression]
    logger.info("S2: batch_rows=%s parquet_compression=%s", batch_rows, parquet_compression)

    price_points = _extract_price_points(amount_model, logger)
    if not price_points:
        _abort(
            "S2_PRECONDITION_AMOUNT_MODEL_INVALID",
            "V-01",
            "price_points_empty",
            {"policy_id": "amount_model_6B"},
            manifest_fingerprint,
        )
    price_points_array = np.asarray(price_points, dtype="int64")

    processed_scenarios: list[str] = []
    total_flows = 0
    total_events = 0
    for scenario_id in scenario_ids:
        if not _scenario_in_scope(scenario_id):
            logger.warning(
                "S2: scenario_id=%s outside scope filters; posture=%s",
                scenario_id,
                on_scope_miss,
            )
            if on_scope_miss.upper() == "SKIP_PARTITION":
                continue
            _abort(
                "S2_PRECONDITION_SCOPE_FILTER",
                "V-01",
                "scenario_not_in_scope",
                {"scenario_id": scenario_id},
                manifest_fingerprint,
            )

        tokens_local = {**tokens, "scenario_id": str(scenario_id)}
        arrivals_path = _resolve_dataset_path(arrivals_entry, run_paths, config.external_roots, tokens_local)
        arrivals_files = _list_parquet_files(arrivals_path, allow_empty=True)

        session_entry = find_dataset_entry(dictionary_6b, "s1_session_index_6B").entry
        session_path = _resolve_dataset_path(session_entry, run_paths, config.external_roots, tokens_local)
        session_files = _list_parquet_files(session_path, allow_empty=True)
        if arrivals_files and not session_files:
            _abort(
                "S2_PRECONDITION_S1_MISSING",
                "V-01",
                "session_index_missing",
                {"scenario_id": scenario_id, "path": str(session_path)},
                manifest_fingerprint,
            )

        flow_out_entry = find_dataset_entry(dictionary_6b, "s2_flow_anchor_baseline_6B").entry
        event_out_entry = find_dataset_entry(dictionary_6b, "s2_event_stream_baseline_6B").entry
        flow_out_path = _resolve_dataset_path(flow_out_entry, run_paths, config.external_roots, tokens_local)
        event_out_path = _resolve_dataset_path(event_out_entry, run_paths, config.external_roots, tokens_local)

        tmp_root = run_paths.tmp_root
        tmp_root.mkdir(parents=True, exist_ok=True)
        flow_tmp_dir = tmp_root / f"s2_flow_anchor_baseline_6B_{scenario_id}"
        event_tmp_dir = tmp_root / f"s2_event_stream_baseline_6B_{scenario_id}"
        flow_tmp_dir.mkdir(parents=True, exist_ok=True)
        event_tmp_dir.mkdir(parents=True, exist_ok=True)
        for existing in flow_tmp_dir.glob("part-*.parquet"):
            existing.unlink()
        for existing in event_tmp_dir.glob("part-*.parquet"):
            existing.unlink()

        empty_flow_anchor = pl.DataFrame(
            schema={
                "flow_id": pl.Int64,
                "arrival_seq": pl.Int64,
                "merchant_id": pl.UInt64,
                "party_id": pl.Int64,
                "account_id": pl.Int64,
                "instrument_id": pl.Int64,
                "device_id": pl.Int64,
                "ip_id": pl.Int64,
                "ts_utc": pl.Utf8,
                "amount": pl.Float64,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "scenario_id": pl.Utf8,
            }
        )
        empty_event_stream = pl.DataFrame(
            schema={
                "flow_id": pl.Int64,
                "event_seq": pl.Int64,
                "event_type": pl.Utf8,
                "ts_utc": pl.Utf8,
                "amount": pl.Float64,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "scenario_id": pl.Utf8,
            }
        )

        if not arrivals_files:
            logger.info("S2: scenario_id=%s has no arrivals; emitting empty outputs", scenario_id)
            flow_part = flow_tmp_dir / "part-00000.parquet"
            event_part = event_tmp_dir / "part-00000.parquet"
            empty_flow_anchor.write_parquet(flow_part, compression=parquet_compression)
            empty_event_stream.write_parquet(event_part, compression=parquet_compression)
        else:
            total_rows = _count_parquet_rows(arrivals_files)
            logger.info(
                "S2: scenario_id=%s arrivals_in_scope=%s (seed=%s, manifest_fingerprint=%s)",
                scenario_id,
                total_rows,
                seed,
                manifest_fingerprint,
            )
            if total_rows == 0:
                logger.info("S2: scenario_id=%s has zero arrivals; emitting empty outputs", scenario_id)
                flow_part = flow_tmp_dir / "part-00000.parquet"
                event_part = event_tmp_dir / "part-00000.parquet"
                empty_flow_anchor.write_parquet(flow_part, compression=parquet_compression)
                empty_event_stream.write_parquet(event_part, compression=parquet_compression)
            else:
                progress = _ProgressTracker(
                    total_rows,
                    logger,
                    f"S2: scenario_id={scenario_id} arrivals_processed",
                )
                part_index = 0
                validated_flow_schema = False
                validated_event_schema = False

                for arrivals in _iter_parquet_batches(
                    arrivals_files,
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
                    ],
                    batch_rows,
                ):
                    arrivals = arrivals.with_columns(
                        pl.col("arrival_seq").cast(pl.Int64),
                        pl.col("merchant_id").cast(pl.UInt64),
                        pl.col("party_id").cast(pl.Int64),
                        pl.col("account_id").cast(pl.Int64),
                        pl.col("instrument_id").cast(pl.Int64),
                        pl.col("device_id").cast(pl.Int64),
                        pl.col("ip_id").cast(pl.Int64),
                        pl.col("ts_utc").cast(pl.Utf8),
                    )

                    arrivals = arrivals.with_columns(
                        _hash_to_id64(
                            [
                                pl.lit(manifest_fingerprint),
                                pl.lit(parameter_hash),
                                pl.lit(seed),
                                pl.lit(scenario_id),
                                pl.col("merchant_id"),
                                pl.col("arrival_seq"),
                            ],
                            seed=seed,
                        ).alias("flow_id"),
                        _hash_to_index(
                            [
                                pl.lit(manifest_fingerprint),
                                pl.lit(parameter_hash),
                                pl.lit(seed),
                                pl.lit(scenario_id),
                                pl.col("merchant_id"),
                                pl.col("arrival_seq"),
                                pl.lit("AMOUNT"),
                            ],
                            seed=seed + 991,
                            modulus=len(price_points_array),
                        ).alias("amount_index"),
                    )

                    amount_index = arrivals.get_column("amount_index").to_numpy()
                    amount_minor = price_points_array[amount_index]
                    amount_major = amount_minor / 100.0
                    arrivals = arrivals.with_columns(
                        pl.Series("amount_minor", amount_minor),
                        pl.Series("amount", amount_major),
                        pl.lit(seed).cast(pl.Int64).alias("seed"),
                        pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                        pl.lit(parameter_hash).alias("parameter_hash"),
                        pl.lit(scenario_id).alias("scenario_id"),
                    )

                    flow_anchor = arrivals.select(
                        [
                            "flow_id",
                            "arrival_seq",
                            "merchant_id",
                            "party_id",
                            "account_id",
                            "instrument_id",
                            "device_id",
                            "ip_id",
                            "ts_utc",
                            "amount",
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )

                    event_base = flow_anchor.select(
                        [
                            "flow_id",
                            "ts_utc",
                            "amount",
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )
                    event_request = event_base.with_columns(
                        pl.lit(0).cast(pl.Int64).alias("event_seq"),
                        pl.lit("AUTH_REQUEST").alias("event_type"),
                    )
                    event_response = event_base.with_columns(
                        pl.lit(1).cast(pl.Int64).alias("event_seq"),
                        pl.lit("AUTH_RESPONSE").alias("event_type"),
                    )
                    event_stream = pl.concat([event_request, event_response], how="vertical").select(
                        [
                            "flow_id",
                            "event_seq",
                            "event_type",
                            "ts_utc",
                            "amount",
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )

                    if not validated_flow_schema and flow_anchor.height > 0:
                        sample = flow_anchor.head(1).to_dicts()[0]
                        _validate_payload(
                            sample,
                            schema_6b,
                            schema_layer3,
                            "#/s2/flow_anchor_baseline_6B",
                            manifest_fingerprint,
                            {"scenario_id": scenario_id},
                        )
                        validated_flow_schema = True

                    if not validated_event_schema and event_stream.height > 0:
                        sample = event_stream.head(1).to_dicts()[0]
                        _validate_payload(
                            sample,
                            schema_6b,
                            schema_layer3,
                            "#/s2/event_stream_baseline_6B",
                            manifest_fingerprint,
                            {"scenario_id": scenario_id},
                        )
                        validated_event_schema = True

                    flow_part = flow_tmp_dir / f"part-{part_index:05d}.parquet"
                    event_part = event_tmp_dir / f"part-{part_index:05d}.parquet"
                    flow_anchor.write_parquet(flow_part, compression=parquet_compression)
                    event_stream.write_parquet(event_part, compression=parquet_compression)

                    batch_rows_processed = int(flow_anchor.height)
                    total_flows += batch_rows_processed
                    total_events += int(event_stream.height)
                    part_index += 1
                    progress.update(batch_rows_processed)

        flow_out_dir = _materialize_parquet_path(flow_out_path).parent
        event_out_dir = _materialize_parquet_path(event_out_path).parent

        _publish_parquet_parts(
            flow_tmp_dir,
            flow_out_dir,
            logger,
            f"s2_flow_anchor_baseline_6B (scenario_id={scenario_id})",
            "6B.S2.IO_WRITE_CONFLICT",
            "6B.S2.IO_WRITE_FAILED",
        )
        _publish_parquet_parts(
            event_tmp_dir,
            event_out_dir,
            logger,
            f"s2_event_stream_baseline_6B (scenario_id={scenario_id})",
            "6B.S2.IO_WRITE_CONFLICT",
            "6B.S2.IO_WRITE_FAILED",
        )

        processed_scenarios.append(str(scenario_id))
    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6B.S2 deterministic baseline flow synthesis audit",
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
    flow_blocks = int(math.ceil(total_flows / 2.0))
    event_blocks = int(math.ceil(total_events / 2.0))
    trace_rows = [
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6B.S2",
            "substream_label": "flow_anchor_baseline",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": flow_blocks,
            "rng_counter_after_hi": 0,
            "draws_total": int(total_flows),
            "blocks_total": int(flow_blocks),
            "events_total": int(total_flows),
        },
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6B.S2",
            "substream_label": "event_stream_baseline",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": event_blocks,
            "rng_counter_after_hi": 0,
            "draws_total": int(total_events),
            "blocks_total": int(event_blocks),
            "events_total": int(total_events),
        },
    ]
    _append_rng_trace(rng_trace_path, trace_rows, logger, "6B.S2", run_id_value, seed)

    rng_flow_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_event_flow_anchor_baseline").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    rng_event_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_event_event_stream_baseline").entry,
        run_paths,
        config.external_roots,
        tokens,
    )

    rng_flow_file = _materialize_jsonl_path(rng_flow_path)
    rng_event_file = _materialize_jsonl_path(rng_event_path)

    tmp_root = run_paths.tmp_root
    tmp_root.mkdir(parents=True, exist_ok=True)
    rng_flow_tmp = tmp_root / f"rng_event_flow_anchor_baseline_{run_id_value}.jsonl"
    rng_event_tmp = tmp_root / f"rng_event_event_stream_baseline_{run_id_value}.jsonl"

    flow_event_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "6B.S2",
        "substream_label": "flow_anchor_baseline",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": int(flow_blocks),
        "rng_counter_after_hi": 0,
        "draws": int(total_flows),
        "blocks": int(flow_blocks),
        "context": {
            "events_total": int(total_flows),
            "notes": "deterministic hash selection for baseline flows",
        },
    }
    event_stream_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "6B.S2",
        "substream_label": "event_stream_baseline",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": int(event_blocks),
        "rng_counter_after_hi": 0,
        "draws": int(total_events),
        "blocks": int(event_blocks),
        "context": {
            "events_total": int(total_events),
            "notes": "deterministic hash selection for baseline events",
        },
    }

    rng_flow_tmp.write_text(json.dumps(flow_event_entry, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    rng_event_tmp.write_text(
        json.dumps(event_stream_entry, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8"
    )

    _publish_file_idempotent(
        rng_flow_tmp,
        rng_flow_file,
        logger,
        "rng_event_flow_anchor_baseline",
        "6B.S2.IO_WRITE_CONFLICT",
        "6B.S2.IO_WRITE_FAILED",
    )
    _publish_file_idempotent(
        rng_event_tmp,
        rng_event_file,
        logger,
        "rng_event_event_stream_baseline",
        "6B.S2.IO_WRITE_CONFLICT",
        "6B.S2.IO_WRITE_FAILED",
    )

    timer.info("S2: completed baseline flow synthesis")
    return S2Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        scenario_ids=processed_scenarios,
        flow_count=int(total_flows),
        event_count=int(total_events),
    )
