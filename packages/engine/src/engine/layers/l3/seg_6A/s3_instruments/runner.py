"""S3 instrument base runner for Segment 6A."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import polars as pl
import yaml
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import (
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
from engine.core.run_receipt import pick_latest_run_receipt
from engine.layers.l3.seg_6A.perf import Segment6APerfRecorder
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    add_u128,
    low64,
    philox2x64_10,
    ser_u64,
    u01,
    uer_string,
)

try:  # pragma: no cover - optional dependency
    import pyarrow as pa
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - optional dependency
    pa = None
    pq = None
    _HAVE_PYARROW = False


MODULE_NAME = "6A.s3_instruments"
SEGMENT = "6A"
STATE = "S3"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_DEFAULT_BATCH_ROWS = 50_000
_DETERMINISTIC_PRF_VERSION = "6A_S3_PRF_V2_SPLITMIX64"
_U64_MASK = (1 << 64) - 1
_INV_2_POW_53 = 1.0 / 9007199254740992.0


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    instrument_base_path: Path
    account_links_path: Path
    holdings_path: Optional[Path]
    summary_path: Optional[Path]


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
    logger = get_logger("engine.layers.l3.seg_6A.s3_instruments.runner")
    payload = {"message": message}
    payload.update(context)
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, payload)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"Invalid JSON at {path}") from exc


def _load_yaml(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SchemaValidationError(f"Invalid YAML at {path}") from exc


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    return pick_latest_run_receipt(runs_root)


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
    else:
        receipt_path = _pick_latest_run_receipt(runs_root)
    receipt = _load_json(receipt_path)
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


def _materialize_jsonl_path(path: Path) -> Path:
    if "*" in path.name or "?" in path.name:
        return path.with_name("part-00000.jsonl")
    if path.is_dir():
        return path / "part-00000.jsonl"
    return path


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not files:
        raise InputResolutionError(f"No parquet files found under dataset path: {root}")
    return files


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


def _anchor_from_ref(schema_ref: str) -> str:
    if "#" in schema_ref:
        return schema_ref[schema_ref.index("#") :]
    return schema_ref


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
            "6A.S3.SCHEMA_INVALID",
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
                    logger.info("S3: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S3: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S3: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _publish_parquet_file_idempotent(
    tmp_path: Path,
    final_path: Path,
    logger,
    label: str,
    conflict_code: str,
    failure_code: str,
) -> None:
    if final_path.exists():
        _abort(conflict_code, "V-01", f"{label} already exists", {"path": str(final_path)}, None)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
        logger.info("S3: published %s to %s", label, final_path)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_path), "error": str(exc)}, None)


def _publish_jsonl_file_idempotent(
    tmp_path: Path,
    final_path: Path,
    logger,
    label: str,
    conflict_code: str,
    failure_code: str,
) -> None:
    if final_path.exists():
        _abort(conflict_code, "V-01", f"{label} already exists", {"path": str(final_path)}, None)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
        logger.info("S3: published %s to %s", label, final_path)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_path), "error": str(exc)}, None)


def _validate_sample_rows(
    frame: pl.DataFrame,
    validator: Draft202012Validator,
    manifest_fingerprint: str,
    label: str,
) -> None:
    sample_errors = []
    for row in frame.head(500).iter_rows(named=True):
        for error in validator.iter_errors(row):
            sample_errors.append(error)
            break
        if sample_errors:
            break
    if sample_errors:
        _abort(
            "6A.S3.SCHEMA_INVALID",
            "V-09",
            "output_schema_invalid",
            {"detail": str(sample_errors[0]), "dataset": label},
            manifest_fingerprint,
        )


class _RngStream:
    def __init__(self, label: str, manifest_fingerprint: str, parameter_hash: str, seed: int) -> None:
        prefix = (
            uer_string("mlr:6A")
            + uer_string(label)
            + uer_string(manifest_fingerprint)
            + uer_string(parameter_hash)
            + ser_u64(seed)
        )
        digest = hashlib.sha256(prefix).digest()
        self.label = label
        self.key = low64(digest)
        self.counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
        self.counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
        self.start_hi = self.counter_hi
        self.start_lo = self.counter_lo
        self.draws_total = 0
        self.blocks_total = 0
        self.events_total = 0

    def draw_uniforms(self, n: int) -> tuple[list[float], int, int, int, int, int, int]:
        if n <= 0:
            return [], self.counter_hi, self.counter_lo, self.counter_hi, self.counter_lo, 0, 0
        before_hi, before_lo = self.counter_hi, self.counter_lo
        values: list[float] = []
        blocks = 0
        remaining = n
        while remaining > 0:
            out0, out1 = philox2x64_10(self.counter_hi, self.counter_lo, self.key)
            values.append(u01(out0))
            if remaining > 1:
                values.append(u01(out1))
            self.counter_hi, self.counter_lo = add_u128(self.counter_hi, self.counter_lo, 1)
            blocks += 1
            remaining -= 2
        draws = n
        self.draws_total += draws
        self.blocks_total += blocks
        return values[:n], before_hi, before_lo, self.counter_hi, self.counter_lo, draws, blocks

    def record_event(self) -> None:
        self.events_total += 1

    def trace_row(self, run_id: str, seed: int, module: str) -> dict:
        return {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id,
            "seed": seed,
            "module": module,
            "substream_label": self.label,
            "rng_counter_before_lo": int(self.start_lo),
            "rng_counter_before_hi": int(self.start_hi),
            "rng_counter_after_lo": int(self.counter_lo),
            "rng_counter_after_hi": int(self.counter_hi),
            "draws_total": int(self.draws_total),
            "blocks_total": int(self.blocks_total),
            "events_total": int(self.events_total),
        }


def _mix_splitmix64_array(values: np.ndarray) -> np.ndarray:
    mixed = values.astype(np.uint64, copy=True)
    with np.errstate(over="ignore"):
        mixed += np.uint64(0x9E3779B97F4A7C15)
        mixed = (mixed ^ (mixed >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        mixed = (mixed ^ (mixed >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        mixed = mixed ^ (mixed >> np.uint64(31))
    return mixed


class _DeterministicUniformGenerator:
    def __init__(self, manifest_fingerprint: str, parameter_hash: str) -> None:
        base_digest = hashlib.blake2b(
            bytes.fromhex(manifest_fingerprint) + bytes.fromhex(parameter_hash),
            digest_size=16,
            person=b"6A.S3.PRF",
        ).digest()
        self._seed_lo = int.from_bytes(base_digest[:8], "little", signed=False)
        self._seed_hi = int.from_bytes(base_digest[8:], "little", signed=False)
        self._stream_cache: dict[tuple[str, str], np.uint64] = {}

    def _stream_seed(self, instrument_type: str, label: str) -> np.uint64:
        cache_key = (instrument_type, label)
        cached = self._stream_cache.get(cache_key)
        if cached is not None:
            return cached
        stream_digest = hashlib.blake2b(
            f"{instrument_type}|{label}".encode("utf-8"),
            digest_size=8,
            person=b"6A.S3.STM",
        ).digest()
        stream_seed = int.from_bytes(stream_digest, "little", signed=False)
        rotated_hi = ((self._seed_hi << 1) & _U64_MASK) | (self._seed_hi >> 63)
        mixed_seed = (stream_seed ^ self._seed_lo ^ rotated_hi ^ 0xD2B74407B1CE6E93) & _U64_MASK
        seed_value = np.uint64(mixed_seed)
        self._stream_cache[cache_key] = seed_value
        return seed_value

    def uniforms(self, account_ids: np.ndarray, instrument_type: str, label: str) -> np.ndarray:
        if account_ids.size == 0:
            return np.empty(0, dtype=np.float64)
        account_u64 = account_ids.astype(np.uint64, copy=False)
        mixed = _mix_splitmix64_array(account_u64 ^ self._stream_seed(instrument_type, label))
        return ((mixed >> np.uint64(11)).astype(np.float64)) * _INV_2_POW_53


def _normal_icdf(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r) + 1.0
    )


def _normal_icdf_array(probabilities: np.ndarray) -> np.ndarray:
    if probabilities.size == 0:
        return np.empty(0, dtype=np.float64)
    if np.any(probabilities <= 0.0) or np.any(probabilities >= 1.0):
        raise ValueError("p must be in (0,1)")
    p = probabilities.astype(np.float64, copy=False)
    out = np.empty_like(p)

    a = np.array(
        (
            -3.969683028665376e01,
            2.209460984245205e02,
            -2.759285104469687e02,
            1.383577518672690e02,
            -3.066479806614716e01,
            2.506628277459239e00,
        ),
        dtype=np.float64,
    )
    b = np.array(
        (
            -5.447609879822406e01,
            1.615858368580409e02,
            -1.556989798598866e02,
            6.680131188771972e01,
            -1.328068155288572e01,
        ),
        dtype=np.float64,
    )
    c = np.array(
        (
            -7.784894002430293e-03,
            -3.223964580411365e-01,
            -2.400758277161838e00,
            -2.549732539343734e00,
            4.374664141464968e00,
            2.938163982698783e00,
        ),
        dtype=np.float64,
    )
    d = np.array(
        (
            7.784695709041462e-03,
            3.224671290700398e-01,
            2.445134137142996e00,
            3.754408661907416e00,
        ),
        dtype=np.float64,
    )

    plow = 0.02425
    phigh = 1.0 - plow
    low = p < plow
    high = p > phigh
    mid = ~(low | high)

    if np.any(low):
        q = np.sqrt(-2.0 * np.log(p[low]))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q) + c[5]
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        out[low] = num / den
    if np.any(high):
        q = np.sqrt(-2.0 * np.log(1.0 - p[high]))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q) + c[5]
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        out[high] = -(num / den)
    if np.any(mid):
        q = p[mid] - 0.5
        r = q * q
        num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        den = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r) + 1.0
        out[mid] = num / den
    return out


def _select_top_indices(
    residuals: np.ndarray,
    tie_values: np.ndarray,
    count: int,
) -> np.ndarray:
    if count <= 0:
        return np.empty(0, dtype=np.int64)
    n = residuals.size
    if count >= n:
        return np.arange(n, dtype=np.int64)
    if n >= 50_000 and count <= n // 4:
        cutoff = np.partition(residuals, n - count)[n - count]
        above = np.flatnonzero(residuals > cutoff)
        needed = count - above.size
        if needed <= 0:
            return above[:count]
        equal = np.flatnonzero(residuals == cutoff)
        if equal.size <= needed:
            return np.concatenate((above, equal))
        order = np.lexsort((equal, -tie_values[equal]))
        return np.concatenate((above, equal[order[:needed]]))
    order = np.lexsort((np.arange(n, dtype=np.int64), -tie_values, -residuals))
    return order[:count]


def _select_bottom_indices(residuals: np.ndarray, count: int) -> np.ndarray:
    if count <= 0:
        return np.empty(0, dtype=np.int64)
    n = residuals.size
    if count >= n:
        return np.arange(n, dtype=np.int64)
    if n >= 50_000 and count <= n // 4:
        cutoff = np.partition(residuals, count - 1)[count - 1]
        below = np.flatnonzero(residuals < cutoff)
        needed = count - below.size
        if needed <= 0:
            return below[:count]
        equal = np.flatnonzero(residuals == cutoff)
        return np.concatenate((below, np.sort(equal)[:needed]))
    order = np.lexsort((np.arange(n, dtype=np.int64), residuals))
    return order[:count]


def _largest_remainder_fullsort_reference(
    targets: np.ndarray,
    total: int,
    tie_values: np.ndarray,
) -> np.ndarray:
    floors = np.floor(targets).astype(np.int64)
    residuals = targets - floors
    remaining = int(total) - int(floors.sum())
    if remaining > 0:
        ranked = sorted(
            range(targets.size),
            key=lambda idx: (float(residuals[idx]), float(tie_values[idx])),
            reverse=True,
        )
        for idx in ranked[:remaining]:
            floors[idx] += 1
    elif remaining < 0:
        ranked = sorted(range(targets.size), key=lambda idx: (float(residuals[idx]), int(idx)))
        need = abs(remaining)
        for idx in ranked:
            if need <= 0:
                break
            if floors[idx] > 0:
                floors[idx] -= 1
                need -= 1
    return floors


def _largest_remainder_list(
    targets: list[float] | np.ndarray,
    total: int,
    tie_stream: Optional[_RngStream] = None,
) -> np.ndarray:
    targets_arr = np.asarray(targets, dtype=np.float64)
    if targets_arr.size == 0:
        return np.empty(0, dtype=np.int64)
    floors = np.floor(targets_arr).astype(np.int64)
    residuals = targets_arr - floors
    base_total = int(floors.sum())
    remaining = int(total) - base_total
    tie_values = np.zeros(targets_arr.size, dtype=np.float64)
    tie_values_drawn = False
    if remaining > 0:
        if tie_stream is not None:
            tie_draws, _, _, _, _, _, _ = tie_stream.draw_uniforms(targets_arr.size)
            tie_values = np.asarray(tie_draws, dtype=np.float64)
            tie_values_drawn = True
        selected = _select_top_indices(residuals, tie_values, remaining)
        floors[selected] += 1
    elif remaining < 0:
        selected = _select_bottom_indices(residuals, abs(remaining))
        floors[selected] = np.maximum(floors[selected] - 1, 0)
    delta = int(total) - int(floors.sum())
    if delta > 0:
        if tie_stream is not None and not tie_values_drawn:
            tie_draws, _, _, _, _, _, _ = tie_stream.draw_uniforms(targets_arr.size)
            tie_values = np.asarray(tie_draws, dtype=np.float64)
            tie_values_drawn = True
        selected = _select_top_indices(residuals, tie_values, delta)
        floors[selected] += 1
    elif delta < 0:
        remaining = abs(delta)
        while remaining > 0:
            positive_idx = np.flatnonzero(floors > 0)
            if positive_idx.size == 0:
                break
            if positive_idx.size <= remaining:
                floors[positive_idx] -= 1
                remaining -= positive_idx.size
                continue
            order = np.lexsort((positive_idx, residuals[positive_idx]))
            selected = positive_idx[order[:remaining]]
            floors[selected] -= 1
            remaining = 0
    if os.getenv("ENGINE_6A_S3_ALLOC_SELFTEST", "0") == "1" and targets_arr.size <= 200_000:
        reference = _largest_remainder_fullsort_reference(targets_arr, int(total), tie_values)
        if int(reference.sum()) != int(floors.sum()):
            raise ValueError("largest_remainder_selfcheck_failed")
    return floors


def _normalize_shares(items: list[tuple[str, float]], logger, label: str) -> list[tuple[str, float]]:
    total = sum(share for _, share in items)
    if total <= 0:
        raise ValueError(f"{label} shares sum to zero")
    if abs(total - 1.0) > 1.0e-6:
        logger.warning("%s shares normalized (sum=%.6f)", label, total)
    return [(key, share / total) for key, share in items]


def _apply_caps(
    counts: list[int] | np.ndarray,
    weights: list[float] | np.ndarray,
    hard_max: int,
    total_target: int,
    rng_stream: _RngStream,
) -> np.ndarray:
    capped = np.asarray(counts, dtype=np.int64).copy()
    weights_arr = np.asarray(weights, dtype=np.float64)
    if capped.size != weights_arr.size:
        raise ValueError("counts/weights size mismatch")
    overflow_mask = capped > hard_max
    overflow = int((capped[overflow_mask] - hard_max).sum())
    capped[overflow_mask] = hard_max
    if overflow <= 0:
        return capped
    iterations = 0
    remaining = overflow
    while remaining > 0 and iterations < 6:
        indices = np.flatnonzero((capped < hard_max) & (weights_arr > 0.0))
        if indices.size == 0:
            break
        capacity = hard_max - capped[indices]
        total_capacity = int(capacity.sum())
        if total_capacity < remaining:
            raise ValueError("insufficient capacity to reallocate overflow")
        target_weights = weights_arr[indices]
        total_weight = float(target_weights.sum())
        if total_weight <= 0:
            raise ValueError("insufficient weight to reallocate overflow")
        targets = (float(remaining) * target_weights) / total_weight
        alloc = _largest_remainder_list(targets, remaining, rng_stream)
        if alloc.size != indices.size:
            raise ValueError("allocation result size mismatch")
        add = np.minimum(alloc, capacity)
        capped[indices] += add
        remaining = int((alloc - add).sum())
        iterations += 1
    if remaining > 0:
        raise ValueError("cap redistribution failed to place all overflow")
    if int(capped.sum()) != int(total_target):
        raise ValueError("cap redistribution target mismatch")
    return capped


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l3.seg_6A.s3_instruments.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        _abort("6A.S3.IO_READ_FAILED", "V-01", "run_id_missing", {"path": str(receipt_path)}, None)

    seed = receipt.get("seed")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        _abort(
            "6A.S3.IO_READ_FAILED",
            "V-01",
            "run_receipt_missing_fields",
            {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )
    if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
        _abort(
            "6A.S3.IO_READ_FAILED",
            "V-01",
            "run_receipt_invalid_hashes",
            {"parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info("S3: run log initialized at %s", run_log_path)
    logger.info(
        "S3: objective=build instrument base; gated inputs (S0 receipt + sealed inputs + S1 party base + S2 account base + instrument priors/taxonomy) -> outputs s3_instrument_base_6A + s3_account_instrument_links_6A + rng logs"
    )
    perf = Segment6APerfRecorder(
        run_paths=run_paths,
        run_id=run_id_value,
        seed=int(seed),
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        state=STATE,
        logger=logger,
    )

    step_started = time.monotonic()
    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6a_path, dictionary_6a = load_dataset_dictionary(source, "6A")
    reg_6a_path, registry_6a = load_artefact_registry(source, "6A")
    schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6A", "layer3")
    timer.info(
        "S3: loaded contracts (dictionary=%s registry=%s schema_6a=%s schema_layer3=%s)",
        dict_6a_path,
        reg_6a_path,
        schema_6a_path,
        schema_layer3_path,
    )

    tokens = {
        "seed": str(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id_value,
    }

    s0_receipt_entry = find_dataset_entry(dictionary_6a, "s0_gate_receipt_6A").entry
    s0_receipt_path = _resolve_dataset_path(s0_receipt_entry, run_paths, config.external_roots, tokens)
    if not s0_receipt_path.exists():
        _abort(
            "6A.S3.S0_GATE_MISSING",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(s0_receipt_path)},
            manifest_fingerprint,
        )
    s0_receipt = _load_json(s0_receipt_path)
    _validate_payload(
        s0_receipt,
        schema_layer3,
        schema_layer3,
        "#/gate/6A/s0_gate_receipt_6A",
        manifest_fingerprint,
        {"path": str(s0_receipt_path)},
    )

    sealed_entry = find_dataset_entry(dictionary_6a, "sealed_inputs_6A").entry
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
    if not sealed_inputs_path.exists():
        _abort(
            "6A.S3.SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "6A.S3.SEALED_INPUTS_INVALID",
            "V-01",
            "sealed_inputs_not_list",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )
    _validate_payload(
        sealed_inputs,
        schema_layer3,
        schema_layer3,
        "#/gate/6A/sealed_inputs_6A",
        manifest_fingerprint,
        {"path": str(sealed_inputs_path)},
    )
    digest_expected = str(s0_receipt.get("sealed_inputs_digest_6A") or "")
    digest_actual = _sealed_inputs_digest(sealed_inputs)
    if digest_expected != digest_actual:
        _abort(
            "6A.S3.SEALED_INPUTS_DIGEST_MISMATCH",
            "V-02",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S3: sealed_inputs digest verified")

    upstream_gates = s0_receipt.get("upstream_gates") or {}
    upstream_segments = s0_receipt.get("upstream_segments") or {}
    required_segments = ("1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B")
    missing_status = []
    for required in required_segments:
        status = (upstream_gates.get(required) or {}).get("gate_status")
        if not status:
            status = (upstream_segments.get(required) or {}).get("status")
        if not status:
            missing_status.append(required)
            continue
        if status != "PASS":
            _abort(
                "6A.S3.S0_S1_S2_GATE_FAILED",
                "V-03",
                "upstream_gate_not_pass",
                {"segment": required, "status": status},
                manifest_fingerprint,
            )
    if missing_status:
        logger.warning(
            "S3: upstream gate status missing for segments=%s; proceeding in lean mode",
            ",".join(missing_status),
        )
    else:
        logger.info("S3: upstream gate PASS checks complete (segments=1A,1B,2A,2B,3A,3B,5A,5B)")

    logger.warning(
        "S3: run-report check skipped (no layer-3 run-report contract); using gate receipt + sealed inputs only"
    )

    def _find_sealed_input(manifest_key: str, required: bool = True, role: Optional[str] = None) -> dict:
        matches = [row for row in sealed_inputs if row.get("manifest_key") == manifest_key]
        if role:
            matches = [row for row in matches if row.get("role") == role]
        if not matches:
            if required:
                _abort(
                    "6A.S3.SEALED_INPUTS_MISSING",
                    "V-04",
                    "sealed_input_missing",
                    {"manifest_key": manifest_key},
                    manifest_fingerprint,
                )
            return {}
        return matches[0]

    instrument_mix_entry = _find_sealed_input("mlr.6A.prior.instrument_mix", role="PRODUCT_PRIOR")
    instrument_per_entry = _find_sealed_input("mlr.6A.prior.instrument_per_account", role="PRODUCT_PRIOR")
    instrument_taxonomy_entry = _find_sealed_input("mlr.6A.taxonomy.instrument_types", role="TAXONOMY")
    linkage_entry = _find_sealed_input(
        "mlr.6A.policy.instrument_linkage_rules",
        required=False,
        role="POLICY",
    )

    for entry in (instrument_mix_entry, instrument_per_entry, instrument_taxonomy_entry):
        if entry.get("read_scope") != "ROW_LEVEL":
            _abort(
                "6A.S3.SEALED_INPUTS_INVALID",
                "V-05",
                "sealed_input_read_scope_invalid",
                {"manifest_key": entry.get("manifest_key"), "read_scope": entry.get("read_scope")},
                manifest_fingerprint,
            )
    if linkage_entry and linkage_entry.get("read_scope") != "ROW_LEVEL":
        _abort(
            "6A.S3.SEALED_INPUTS_INVALID",
            "V-05",
            "sealed_input_read_scope_invalid",
            {"manifest_key": linkage_entry.get("manifest_key"), "read_scope": linkage_entry.get("read_scope")},
            manifest_fingerprint,
        )

    mix_path = _resolve_dataset_path(instrument_mix_entry, run_paths, config.external_roots, tokens)
    per_account_path = _resolve_dataset_path(instrument_per_entry, run_paths, config.external_roots, tokens)
    taxonomy_path = _resolve_dataset_path(instrument_taxonomy_entry, run_paths, config.external_roots, tokens)
    instrument_mix = _load_yaml(mix_path)
    instrument_per = _load_yaml(per_account_path)
    instrument_taxonomy = _load_yaml(taxonomy_path)

    _validate_payload(
        instrument_mix,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(instrument_mix_entry.get("schema_ref") or "#/prior/instrument_mix_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": instrument_mix_entry.get("manifest_key")},
    )
    _validate_payload(
        instrument_per,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(instrument_per_entry.get("schema_ref") or "#/prior/instrument_per_account_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": instrument_per_entry.get("manifest_key")},
    )
    _validate_payload(
        instrument_taxonomy,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(instrument_taxonomy_entry.get("schema_ref") or "#/taxonomy/instrument_taxonomy_6A"),
        manifest_fingerprint,
        {"manifest_key": instrument_taxonomy_entry.get("manifest_key")},
    )

    if linkage_entry:
        linkage_path = _resolve_dataset_path(linkage_entry, run_paths, config.external_roots, tokens)
        logger.warning(
            "S3: instrument linkage rules sealed but ignored in lean mode (path=%s)", linkage_path
        )
    else:
        logger.warning("S3: instrument linkage rules missing (optional); using permissive defaults")

    scheme_mode = str(instrument_mix.get("scheme_mode") or "")
    if scheme_mode and scheme_mode.upper() != "ATTRIBUTE_ONLY":
        logger.warning(
            "S3: scheme_mode overridden to ATTRIBUTE_ONLY for lean path (prior_mode=%s)", scheme_mode
        )

    if instrument_per.get("scheme_scope_mode") not in (None, "NONE"):
        logger.warning(
            "S3: per-account scheme scope ignored in lean mode (scheme_scope_mode=%s)",
            instrument_per.get("scheme_scope_mode"),
        )

    if instrument_mix.get("segment_tilt") or instrument_mix.get("region_tilt"):
        logger.warning("S3: segment/region tilts ignored in lean mode")
    if instrument_per.get("segment_feature_tilts"):
        logger.warning("S3: per-account segment feature tilts ignored in lean mode")
    perf.record_elapsed("load_contracts_inputs", step_started)

    step_started = time.monotonic()
    account_base_entry = find_dataset_entry(dictionary_6a, "s2_account_base_6A").entry
    account_base_path = _resolve_dataset_path(account_base_entry, run_paths, config.external_roots, tokens)
    if not account_base_path.exists():
        _abort(
            "6A.S3.INPUT_MISSING",
            "V-01",
            "account_base_missing",
            {"path": str(account_base_path)},
            manifest_fingerprint,
        )

    account_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(account_base_entry.get("schema_ref") or "#/s2/account_base")
    )
    _inline_external_refs(account_schema, schema_layer3, "schemas.layer3.yaml#")
    account_validator = Draft202012Validator(account_schema)

    account_files = _list_parquet_files(account_base_path)
    account_cells_raw: dict[tuple[str, str], list[int]] = {}
    account_owner_cells_raw: dict[tuple[str, str], list[int]] = {}
    account_owner: dict[int, int] = {}
    total_accounts = 0

    timer.info("S3: loading account base for planning (files=%s)", len(account_files))
    for file_path in account_files:
        if _HAVE_PYARROW:
            parquet_file = pq.ParquetFile(file_path)
            for batch in parquet_file.iter_batches(
                batch_size=_DEFAULT_BATCH_ROWS,
                columns=["account_id", "owner_party_id", "account_type", "party_type"],
            ):
                batch_dict = batch.to_pydict()
                account_ids = batch_dict.get("account_id") or []
                owner_ids = batch_dict.get("owner_party_id") or []
                account_types = batch_dict.get("account_type") or []
                party_types = batch_dict.get("party_type") or []
                for idx in range(len(account_ids)):
                    account_id = int(account_ids[idx])
                    owner_id = int(owner_ids[idx])
                    account_type = str(account_types[idx])
                    party_type = str(party_types[idx])
                    if account_id in account_owner:
                        _abort(
                            "6A.S3.INPUT_INVALID",
                            "V-06",
                            "duplicate_account_id",
                            {"account_id": account_id},
                            manifest_fingerprint,
                        )
                    account_owner[account_id] = owner_id
                    cell_key = (party_type, account_type)
                    account_cells_raw.setdefault(cell_key, []).append(account_id)
                    account_owner_cells_raw.setdefault(cell_key, []).append(owner_id)
                    total_accounts += 1
        else:
            frame = pl.read_parquet(file_path, columns=["account_id", "owner_party_id", "account_type", "party_type"])
            _validate_sample_rows(frame, account_validator, manifest_fingerprint, "s2_account_base_6A")
            for row in frame.iter_rows(named=True):
                account_id = int(row["account_id"])
                owner_id = int(row["owner_party_id"])
                account_type = str(row["account_type"])
                party_type = str(row["party_type"])
                if account_id in account_owner:
                    _abort(
                        "6A.S3.INPUT_INVALID",
                        "V-06",
                        "duplicate_account_id",
                        {"account_id": account_id},
                        manifest_fingerprint,
                    )
                account_owner[account_id] = owner_id
                cell_key = (party_type, account_type)
                account_cells_raw.setdefault(cell_key, []).append(account_id)
                account_owner_cells_raw.setdefault(cell_key, []).append(owner_id)
                total_accounts += 1

    account_cells: dict[tuple[str, str], np.ndarray] = {}
    account_owner_cells: dict[tuple[str, str], np.ndarray] = {}
    for cell_key, account_ids in account_cells_raw.items():
        owner_ids = account_owner_cells_raw.get(cell_key) or []
        if len(account_ids) != len(owner_ids):
            _abort(
                "6A.S3.INPUT_INVALID",
                "V-06",
                "cell_owner_alignment_invalid",
                {"cell": f"{cell_key[0]}::{cell_key[1]}", "accounts": len(account_ids), "owners": len(owner_ids)},
                manifest_fingerprint,
            )
        account_arr = np.asarray(account_ids, dtype=np.int64)
        owner_arr = np.asarray(owner_ids, dtype=np.int64)
        if account_arr.size > 1:
            order = np.argsort(account_arr, kind="mergesort")
            account_arr = account_arr[order]
            owner_arr = owner_arr[order]
        account_cells[cell_key] = account_arr
        account_owner_cells[cell_key] = owner_arr

    logger.info(
        "S3: loaded account base for instrument planning (accounts=%s, cells=%s)",
        total_accounts,
        len(account_cells),
    )
    perf.record_elapsed("load_account_base", step_started)

    step_started = time.monotonic()
    domain_entries = instrument_mix.get("instrument_domain_model", {}).get("allowed_instrument_types") or []
    domain_map: dict[tuple[str, str], list[str]] = {}
    for entry in domain_entries:
        key = (str(entry.get("party_type")), str(entry.get("account_type")))
        instruments = entry.get("instrument_types") or []
        domain_map[key] = [str(item) for item in instruments]

    lambda_entries = instrument_mix.get("lambda_model", {}).get("lambda_total_by_party_type_account_type") or []
    lambda_map: dict[tuple[str, str], float] = {}
    for entry in lambda_entries:
        key = (str(entry.get("party_type")), str(entry.get("account_type")))
        lambda_map[key] = float(entry.get("lambda_total") or 0.0)

    mix_entries = instrument_mix.get("lambda_model", {}).get("mix_by_party_type_account_type") or []
    mix_map: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for entry in mix_entries:
        key = (str(entry.get("party_type")), str(entry.get("account_type")))
        pi_instr = entry.get("pi_instr") or []
        mix_list = [(str(row.get("instrument_type")), float(row.get("share") or 0.0)) for row in pi_instr]
        mix_map[key] = mix_list

    instrument_rules = instrument_per.get("rules") or []
    rule_map: dict[tuple[str, str, str], dict] = {}
    for rule in instrument_rules:
        key = (str(rule.get("party_type")), str(rule.get("account_type")), str(rule.get("instrument_type")))
        rule_map[key] = rule

    instrument_types = instrument_taxonomy.get("instrument_types") or []
    scheme_defs = instrument_taxonomy.get("schemes") or []
    scheme_kind_map: dict[str, str] = {}
    scheme_by_kind: dict[str, list[str]] = {}
    for scheme in scheme_defs:
        scheme_id = str(scheme.get("id"))
        scheme_kind = str(scheme.get("kind"))
        scheme_kind_map[scheme_id] = scheme_kind
        scheme_by_kind.setdefault(scheme_kind, []).append(scheme_id)
    for values in scheme_by_kind.values():
        values.sort()

    instrument_type_defaults: dict[str, str] = {}
    for item in instrument_types:
        instrument_id = str(item.get("id"))
        default_kind = str(item.get("default_scheme_kind") or "")
        if default_kind:
            instrument_type_defaults[instrument_id] = default_kind

    scheme_defaults = (
        instrument_mix.get("attribute_models", {}).get("scheme_model", {}).get("defaults") or {}
    )
    scheme_share_map: dict[str, list[tuple[str, float]]] = {}
    for kind, rows in scheme_defaults.items():
        scheme_rows = [(str(row.get("scheme")), float(row.get("share") or 0.0)) for row in (rows or [])]
        if scheme_rows:
            scheme_share_map[str(kind)] = scheme_rows

    rng_event_rows_count: list[dict] = []
    rng_event_rows_alloc: list[dict] = []
    rng_event_rows_attr: list[dict] = []

    instrument_counts: dict[tuple[str, str, str], int] = {}
    rng_count_stream = _RngStream("instrument_count_realisation", manifest_fingerprint, parameter_hash, int(seed))
    count_tracker = _ProgressTracker(len(account_cells), logger, "S3: plan instrument counts")
    for key, accounts in sorted(account_cells.items()):
        party_type, account_type = key
        n_accounts = len(accounts)
        if n_accounts == 0:
            count_tracker.update(1)
            continue
        if key not in domain_map:
            _abort(
                "6A.S3.PRIOR_PACK_INVALID",
                "V-07",
                "instrument_domain_missing",
                {"party_type": party_type, "account_type": account_type},
                manifest_fingerprint,
            )
        mix_list = mix_map.get(key)
        if not mix_list:
            _abort(
                "6A.S3.PRIOR_PACK_INVALID",
                "V-07",
                "instrument_mix_missing",
                {"party_type": party_type, "account_type": account_type},
                manifest_fingerprint,
            )
        lambda_total = lambda_map.get(key)
        if lambda_total is None:
            _abort(
                "6A.S3.PRIOR_PACK_INVALID",
                "V-07",
                "lambda_total_missing",
                {"party_type": party_type, "account_type": account_type},
                manifest_fingerprint,
            )
        normalized_mix = _normalize_shares(mix_list, logger, f"S3: mix shares {party_type}/{account_type}")
        total_target = float(n_accounts) * float(lambda_total)
        total_int = int(round(total_target))
        if total_int < 0:
            total_int = 0
        targets = [total_target * share for _, share in normalized_mix]
        before_hi = rng_count_stream.counter_hi
        before_lo = rng_count_stream.counter_lo
        draws_before = rng_count_stream.draws_total
        blocks_before = rng_count_stream.blocks_total
        counts = _largest_remainder_list(targets, total_int, rng_count_stream)
        draws = rng_count_stream.draws_total - draws_before
        blocks = rng_count_stream.blocks_total - blocks_before
        after_hi = rng_count_stream.counter_hi
        after_lo = rng_count_stream.counter_lo
        rng_count_stream.record_event()
        rng_event_rows_count.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S3",
                "substream_label": "instrument_count_realisation",
                "rng_counter_before_lo": int(before_lo),
                "rng_counter_before_hi": int(before_hi),
                "rng_counter_after_lo": int(after_lo),
                "rng_counter_after_hi": int(after_hi),
                "draws": str(draws),
                "blocks": int(blocks),
                "context": {
                    "party_type": party_type,
                    "account_type": account_type,
                    "n_accounts": n_accounts,
                    "total_target": total_target,
                    "total_int": total_int,
                    "instrument_types": len(normalized_mix),
                },
            }
        )
        for (instrument_type, _), count in zip(normalized_mix, counts):
            instrument_counts[(party_type, account_type, instrument_type)] = int(count)
        count_tracker.update(1)

    total_instruments = sum(instrument_counts.values())
    logger.info("S3: planned instrument counts (total_instruments=%s)", total_instruments)
    perf.record_elapsed("plan_counts", step_started)

    step_started = time.monotonic()
    logger.info("S3: deterministic uniform PRF active (version=%s)", _DETERMINISTIC_PRF_VERSION)
    rng_alloc_stream = _RngStream("instrument_allocation_sampling", manifest_fingerprint, parameter_hash, int(seed))
    rng_attr_stream = _RngStream("instrument_attribute_sampling", manifest_fingerprint, parameter_hash, int(seed))
    deterministic_uniforms = _DeterministicUniformGenerator(manifest_fingerprint, parameter_hash)

    instrument_entry = find_dataset_entry(dictionary_6a, "s3_instrument_base_6A").entry
    link_entry = find_dataset_entry(dictionary_6a, "s3_account_instrument_links_6A").entry
    holdings_entry = find_dataset_entry(dictionary_6a, "s3_party_instrument_holdings_6A").entry
    summary_entry = find_dataset_entry(dictionary_6a, "s3_instrument_summary_6A").entry

    instrument_base_path = _resolve_dataset_path(instrument_entry, run_paths, config.external_roots, tokens)
    link_path = _resolve_dataset_path(link_entry, run_paths, config.external_roots, tokens)
    holdings_path = _resolve_dataset_path(holdings_entry, run_paths, config.external_roots, tokens)
    summary_path = _resolve_dataset_path(summary_entry, run_paths, config.external_roots, tokens)

    tmp_dir = run_paths.tmp_root / f"s3_instruments_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    instrument_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(instrument_entry.get("schema_ref") or "#/s3/instrument_base")
    )
    _inline_external_refs(instrument_schema, schema_layer3, "schemas.layer3.yaml#")
    instrument_validator = Draft202012Validator(instrument_schema)

    link_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(link_entry.get("schema_ref") or "#/s3/account_instrument_links")
    )
    _inline_external_refs(link_schema, schema_layer3, "schemas.layer3.yaml#")
    link_validator = Draft202012Validator(link_schema)

    tmp_instrument = tmp_dir / instrument_base_path.name
    tmp_link = tmp_dir / link_path.name
    instrument_writer = None
    link_writer = None

    emit_tracker = _ProgressTracker(total_instruments, logger, "S3: emit s3_instrument_base_6A")
    alloc_tracker = _ProgressTracker(len(instrument_counts), logger, "S3: allocate instruments to accounts")
    allocation_account_evals = 0
    allocation_zero_skips = 0
    allocation_weight_evals = 0
    emit_chunks = 0
    emit_rows_written = 0

    def _write_chunk(
        instrument_ids: np.ndarray,
        account_ids: np.ndarray,
        owner_ids: np.ndarray,
        instrument_type: str,
        scheme_ids: np.ndarray,
    ) -> None:
        nonlocal instrument_writer, link_writer, emit_chunks, emit_rows_written
        row_count = int(instrument_ids.size)
        if row_count <= 0:
            return
        instrument_frame = pl.DataFrame(
            {
                "instrument_id": instrument_ids,
                "account_id": account_ids,
                "owner_party_id": owner_ids,
                "scheme": scheme_ids,
            }
        ).with_columns(
            [
                pl.lit(instrument_type).alias("instrument_type"),
                pl.lit(int(seed)).alias("seed"),
                pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                pl.lit(parameter_hash).alias("parameter_hash"),
            ]
        ).select(
            [
                "instrument_id",
                "account_id",
                "owner_party_id",
                "instrument_type",
                "scheme",
                "seed",
                "manifest_fingerprint",
                "parameter_hash",
            ]
        )
        link_frame = pl.DataFrame(
            {
                "account_id": account_ids,
                "instrument_id": instrument_ids,
                "scheme": scheme_ids,
            }
        ).with_columns(pl.lit(instrument_type).alias("instrument_type")).select(
            ["account_id", "instrument_id", "instrument_type", "scheme"]
        )
        _validate_sample_rows(instrument_frame, instrument_validator, manifest_fingerprint, "s3_instrument_base_6A")
        _validate_sample_rows(link_frame, link_validator, manifest_fingerprint, "s3_account_instrument_links_6A")
        if _HAVE_PYARROW:
            inst_table = instrument_frame.to_arrow()
            link_table = link_frame.to_arrow()
            if instrument_writer is None:
                instrument_writer = pq.ParquetWriter(tmp_instrument, inst_table.schema, compression="zstd")
            if link_writer is None:
                link_writer = pq.ParquetWriter(tmp_link, link_table.schema, compression="zstd")
            instrument_writer.write_table(inst_table)
            link_writer.write_table(link_table)
        else:
            _abort(
                "6A.S3.IO_WRITE_FAILED",
                "V-10",
                "pyarrow_required_for_streaming_writer",
                {"detail": "pyarrow is required to emit S3 instrument/link outputs without in-memory concat fallback"},
                manifest_fingerprint,
            )
        emit_chunks += 1
        emit_rows_written += row_count

    instrument_id = 1
    for key in sorted(instrument_counts.keys()):
        party_type, account_type, instrument_type = key
        n_instr = int(instrument_counts[key])
        if n_instr <= 0:
            alloc_tracker.update(1)
            continue
        accounts = account_cells.get((party_type, account_type))
        owner_ids_for_accounts = account_owner_cells.get((party_type, account_type))
        if (
            accounts is None
            or owner_ids_for_accounts is None
            or accounts.size == 0
            or owner_ids_for_accounts.size == 0
        ):
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "account_cell_missing",
                {"party_type": party_type, "account_type": account_type},
                manifest_fingerprint,
            )
        if accounts.size != owner_ids_for_accounts.size:
            _abort(
                "6A.S3.INPUT_INVALID",
                "V-06",
                "cell_owner_alignment_invalid",
                {
                    "party_type": party_type,
                    "account_type": account_type,
                    "accounts": int(accounts.size),
                    "owners": int(owner_ids_for_accounts.size),
                },
                manifest_fingerprint,
            )
        rule = rule_map.get((party_type, account_type, instrument_type))
        if not rule:
            _abort(
                "6A.S3.PRIOR_PACK_INVALID",
                "V-07",
                "instrument_rule_missing",
                {"party_type": party_type, "account_type": account_type, "instrument_type": instrument_type},
                manifest_fingerprint,
            )
        params = rule.get("params") or {}
        p_zero_weight = float(params.get("p_zero_weight") or 0.0)
        sigma = float(params.get("sigma") or 0.0)
        weight_floor = float(params.get("weight_floor_eps") or 1.0e-12)
        hard_max = int(rule.get("hard_max_per_account") or 1)
        if hard_max < 1:
            _abort(
                "6A.S3.PRIOR_PACK_INVALID",
                "V-07",
                "invalid_hard_max",
                {"instrument_type": instrument_type, "hard_max": hard_max},
                manifest_fingerprint,
            )
        if weight_floor <= 0:
            _abort(
                "6A.S3.PRIOR_PACK_INVALID",
                "V-07",
                "invalid_weight_floor",
                {"instrument_type": instrument_type, "weight_floor": weight_floor},
                manifest_fingerprint,
            )

        allocation_account_evals += int(accounts.size)
        zero_uniforms = deterministic_uniforms.uniforms(accounts, instrument_type, "zero_gate")
        if p_zero_weight > 0.0:
            eligible_mask = zero_uniforms >= p_zero_weight
        else:
            eligible_mask = np.ones(accounts.size, dtype=bool)
        allocation_zero_skips += int(accounts.size - int(eligible_mask.sum()))

        eligible_accounts = accounts[eligible_mask]
        eligible_owner_ids = owner_ids_for_accounts[eligible_mask]
        allocation_weight_evals += int(eligible_accounts.size)

        if eligible_accounts.size == 0:
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "allocation_weights_zero",
                {"party_type": party_type, "account_type": account_type, "instrument_type": instrument_type},
                manifest_fingerprint,
            )

        total_capacity = hard_max * int(eligible_accounts.size)
        if n_instr > total_capacity:
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "allocation_exceeds_capacity",
                {
                    "instrument_type": instrument_type,
                    "hard_max": hard_max,
                    "eligible_accounts": int(eligible_accounts.size),
                    "n_instr": n_instr,
                },
                manifest_fingerprint,
            )

        weight_uniforms = deterministic_uniforms.uniforms(eligible_accounts, instrument_type, "weight")
        weight_uniforms = np.clip(weight_uniforms, 1.0e-12, 1.0 - 1.0e-12)
        if sigma > 0:
            z = _normal_icdf_array(weight_uniforms)
            weights = np.exp(sigma * z - 0.5 * sigma * sigma)
        else:
            weights = np.ones(eligible_accounts.size, dtype=np.float64)
        weights = np.maximum(weights, weight_floor)

        total_weight = float(weights.sum())
        if total_weight <= 0:
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "allocation_weights_total_zero",
                {"instrument_type": instrument_type, "n_instr": n_instr},
                manifest_fingerprint,
            )

        targets = (float(n_instr) * weights) / total_weight
        alloc_before_hi = rng_alloc_stream.counter_hi
        alloc_before_lo = rng_alloc_stream.counter_lo
        draws_before = rng_alloc_stream.draws_total
        blocks_before = rng_alloc_stream.blocks_total
        alloc_counts = _largest_remainder_list(targets, n_instr, rng_alloc_stream)
        try:
            alloc_counts = _apply_caps(alloc_counts, weights, hard_max, n_instr, rng_alloc_stream)
        except ValueError as exc:
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "allocation_caps_failed",
                {"instrument_type": instrument_type, "error": str(exc)},
                manifest_fingerprint,
            )
        draws = rng_alloc_stream.draws_total - draws_before
        blocks = rng_alloc_stream.blocks_total - blocks_before
        alloc_after_hi = rng_alloc_stream.counter_hi
        alloc_after_lo = rng_alloc_stream.counter_lo
        rng_alloc_stream.record_event()
        rng_event_rows_alloc.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S3",
                "substream_label": "instrument_allocation_sampling",
                "rng_counter_before_lo": int(alloc_before_lo),
                "rng_counter_before_hi": int(alloc_before_hi),
                "rng_counter_after_lo": int(alloc_after_lo),
                "rng_counter_after_hi": int(alloc_after_hi),
                "draws": str(draws),
                "blocks": int(blocks),
                "context": {
                    "party_type": party_type,
                    "account_type": account_type,
                    "instrument_type": instrument_type,
                    "eligible_accounts": int(eligible_accounts.size),
                    "n_instr": n_instr,
                },
            }
        )

        default_kind = instrument_type_defaults.get(instrument_type) or "CARD_NETWORK"
        scheme_options = scheme_share_map.get(default_kind)
        if not scheme_options:
            fallback = scheme_by_kind.get(default_kind) or []
            if not fallback:
                _abort(
                    "6A.S3.PRIOR_PACK_INVALID",
                    "V-07",
                    "scheme_defaults_missing",
                    {"instrument_type": instrument_type, "scheme_kind": default_kind},
                    manifest_fingerprint,
                )
            logger.warning(
                "S3: scheme defaults missing for kind=%s; using equal shares", default_kind
            )
            scheme_options = [(scheme_id, 1.0 / len(fallback)) for scheme_id in fallback]
        scheme_options = _normalize_shares(scheme_options, logger, f"S3: scheme shares {default_kind}")

        attr_before_hi = rng_attr_stream.counter_hi
        attr_before_lo = rng_attr_stream.counter_lo
        draws_before = rng_attr_stream.draws_total
        blocks_before = rng_attr_stream.blocks_total
        scheme_targets = np.asarray([n_instr * share for _, share in scheme_options], dtype=np.float64)
        scheme_counts = _largest_remainder_list(scheme_targets, n_instr, rng_attr_stream)
        draws = rng_attr_stream.draws_total - draws_before
        blocks = rng_attr_stream.blocks_total - blocks_before
        attr_after_hi = rng_attr_stream.counter_hi
        attr_after_lo = rng_attr_stream.counter_lo
        rng_attr_stream.record_event()
        rng_event_rows_attr.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S3",
                "substream_label": "instrument_attribute_sampling",
                "rng_counter_before_lo": int(attr_before_lo),
                "rng_counter_before_hi": int(attr_before_hi),
                "rng_counter_after_lo": int(attr_after_lo),
                "rng_counter_after_hi": int(attr_after_hi),
                "draws": str(draws),
                "blocks": int(blocks),
                "context": {
                    "instrument_type": instrument_type,
                    "scheme_kind": default_kind,
                    "n_instr": n_instr,
                },
            }
        )

        positive_alloc = alloc_counts > 0
        alloc_counts_positive = alloc_counts[positive_alloc]
        eligible_accounts_positive = eligible_accounts[positive_alloc]
        eligible_owner_positive = eligible_owner_ids[positive_alloc]

        emitted_account_ids = np.repeat(eligible_accounts_positive, alloc_counts_positive)
        emitted_owner_ids = np.repeat(eligible_owner_positive, alloc_counts_positive)
        if int(emitted_account_ids.size) != n_instr:
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "allocation_emit_size_mismatch",
                {
                    "instrument_type": instrument_type,
                    "n_instr": n_instr,
                    "emitted_rows": int(emitted_account_ids.size),
                },
                manifest_fingerprint,
            )

        scheme_labels = np.asarray([scheme_id for scheme_id, _ in scheme_options], dtype=object)
        positive_schemes = scheme_counts > 0
        emitted_scheme_ids = np.repeat(scheme_labels[positive_schemes], scheme_counts[positive_schemes])
        if int(emitted_scheme_ids.size) != n_instr:
            _abort(
                "6A.S3.ALLOCATION_FAILED",
                "V-08",
                "scheme_queue_exhausted",
                {
                    "instrument_type": instrument_type,
                    "n_instr": n_instr,
                    "scheme_rows": int(emitted_scheme_ids.size),
                },
                manifest_fingerprint,
            )

        emitted_instrument_ids = np.arange(instrument_id, instrument_id + n_instr, dtype=np.int64)
        instrument_id += n_instr
        offset = 0
        while offset < n_instr:
            end = min(offset + _DEFAULT_BATCH_ROWS, n_instr)
            _write_chunk(
                emitted_instrument_ids[offset:end],
                emitted_account_ids[offset:end],
                emitted_owner_ids[offset:end],
                instrument_type,
                emitted_scheme_ids[offset:end],
            )
            offset = end
        emit_tracker.update(n_instr)

        alloc_tracker.update(1)

    perf.record_elapsed("allocate_instruments", step_started)
    logger.info(
        "S3: allocation-path counters (account_evals=%s zero_skips=%s weight_evals=%s emit_chunks=%s emitted_rows=%s)",
        allocation_account_evals,
        allocation_zero_skips,
        allocation_weight_evals,
        emit_chunks,
        emit_rows_written,
    )
    step_started = time.monotonic()

    if instrument_writer is not None:
        instrument_writer.close()
    elif total_instruments == 0:
        empty_frame = pl.DataFrame(
            [],
            schema=[
                "instrument_id",
                "account_id",
                "owner_party_id",
                "instrument_type",
                "scheme",
                "seed",
                "manifest_fingerprint",
                "parameter_hash",
            ],
        )
        empty_frame.write_parquet(tmp_instrument, compression="zstd")

    if link_writer is not None:
        link_writer.close()
    elif total_instruments == 0:
        empty_link = pl.DataFrame([], schema=["account_id", "instrument_id", "instrument_type", "scheme"])
        empty_link.write_parquet(tmp_link, compression="zstd")

    _publish_parquet_file_idempotent(
        tmp_instrument,
        instrument_base_path,
        logger,
        "s3_instrument_base_6A",
        "6A.S3.IO_WRITE_CONFLICT",
        "6A.S3.IO_WRITE_FAILED",
    )
    _publish_parquet_file_idempotent(
        tmp_link,
        link_path,
        logger,
        "s3_account_instrument_links_6A",
        "6A.S3.IO_WRITE_CONFLICT",
        "6A.S3.IO_WRITE_FAILED",
    )

    logger.info("S3: optional outputs skipped (holdings_path=%s summary_path=%s)", holdings_path, summary_path)
    perf.record_elapsed("emit_instrument_base_links", step_started)

    step_started = time.monotonic()
    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6A.S3 instrument base RNG audit",
    }
    rng_audit_entry = {key: value if value is not None else None for key, value in rng_audit_entry.items()}
    rng_audit_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6a, "rng_audit_log").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    _ensure_rng_audit(rng_audit_path, rng_audit_entry, logger)

    rng_trace_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6a, "rng_trace_log").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    rng_trace_path.parent.mkdir(parents=True, exist_ok=True)
    with rng_trace_path.open("a", encoding="utf-8") as handle:
        for stream in (rng_count_stream, rng_alloc_stream, rng_attr_stream):
            trace_row = stream.trace_row(run_id_value, int(seed), "6A.S3")
            handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S3: appended rng_trace_log rows for count + allocation + attribute streams")

    rng_count_entry = find_dataset_entry(dictionary_6a, "rng_event_instrument_count_realisation").entry
    rng_alloc_entry = find_dataset_entry(dictionary_6a, "rng_event_instrument_allocation_sampling").entry
    rng_attr_entry = find_dataset_entry(dictionary_6a, "rng_event_instrument_attribute_sampling").entry
    rng_count_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_count_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_alloc_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_alloc_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_attr_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_attr_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )

    tmp_count_path = tmp_dir / rng_count_path.name
    tmp_alloc_path = tmp_dir / rng_alloc_path.name
    tmp_attr_path = tmp_dir / rng_attr_path.name
    if tmp_count_path == tmp_alloc_path or tmp_count_path == tmp_attr_path or tmp_alloc_path == tmp_attr_path:
        tmp_count_path = tmp_dir / "instrument_count_realisation.jsonl"
        tmp_alloc_path = tmp_dir / "instrument_allocation_sampling.jsonl"
        tmp_attr_path = tmp_dir / "instrument_attribute_sampling.jsonl"

    tmp_count_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_count) + "\n",
        encoding="utf-8",
    )
    tmp_alloc_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_alloc) + "\n",
        encoding="utf-8",
    )
    tmp_attr_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_attr) + "\n",
        encoding="utf-8",
    )

    _publish_jsonl_file_idempotent(
        tmp_count_path,
        rng_count_path,
        logger,
        "rng_event_instrument_count_realisation",
        "6A.S3.IO_WRITE_CONFLICT",
        "6A.S3.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_alloc_path,
        rng_alloc_path,
        logger,
        "rng_event_instrument_allocation_sampling",
        "6A.S3.IO_WRITE_CONFLICT",
        "6A.S3.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_attr_path,
        rng_attr_path,
        logger,
        "rng_event_instrument_attribute_sampling",
        "6A.S3.IO_WRITE_CONFLICT",
        "6A.S3.IO_WRITE_FAILED",
    )
    perf.record_elapsed("rng_publish", step_started)
    perf.write_events(raise_on_error=True)

    timer.info("S3: instrument base generation complete")
    return S3Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        instrument_base_path=instrument_base_path,
        account_links_path=link_path,
        holdings_path=None,
        summary_path=None,
    )
