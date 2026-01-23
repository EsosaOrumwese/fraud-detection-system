"""S4 device/IP graph runner for Segment 6A."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
import uuid
from bisect import bisect_left
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

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
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - optional dependency
    pa = None
    pq = None
    _HAVE_PYARROW = False


MODULE_NAME = "6A.s4_device_graph"
SEGMENT = "6A"
STATE = "S4"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_DEFAULT_BATCH_ROWS = 50_000
_BUFFER_MAX_ROWS = 50_000
_HASH_MASK_64 = 0xFFFFFFFFFFFFFFFF
_HASH_CONST_A = 0x9E3779B97F4A7C15
_HASH_CONST_B = 0xBF58476D1CE4E5B9
_HASH_CONST_C = 0x94D049BB133111EB


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    device_base_path: Path
    ip_base_path: Path
    device_links_path: Path
    ip_links_path: Path
    neighbourhoods_path: Optional[Path]
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
    logger = get_logger("engine.layers.l3.seg_6A.s4_device_graph.runner")
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
            "6A.S4.SCHEMA_INVALID",
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
                    logger.info("S4: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S4: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S4: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


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
        logger.info("S4: published %s to %s", label, final_path)
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
        logger.info("S4: published %s to %s", label, final_path)
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
            "6A.S4.SCHEMA_INVALID",
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


def _deterministic_uniform(
    manifest_fingerprint: str,
    parameter_hash: str,
    account_id: int,
    instrument_type: str,
    label: str,
) -> float:
    payload = (
        uer_string("mlr:6A")
        + uer_string("s4")
        + uer_string(label)
        + uer_string(manifest_fingerprint)
        + uer_string(parameter_hash)
        + ser_u64(int(account_id))
        + uer_string(str(instrument_type))
    )
    digest = hashlib.sha256(payload).digest()
    return u01(low64(digest))


def _mix64(value: int) -> int:
    value = (value ^ (value >> 30)) * _HASH_CONST_B & _HASH_MASK_64
    value = (value ^ (value >> 27)) * _HASH_CONST_C & _HASH_MASK_64
    value ^= value >> 31
    return value & _HASH_MASK_64


def _seed_for_label(manifest_fingerprint: str, parameter_hash: str, label: str) -> int:
    payload = (
        uer_string("mlr:6A")
        + uer_string("s4")
        + uer_string(label)
        + uer_string(manifest_fingerprint)
        + uer_string(parameter_hash)
    )
    digest = hashlib.sha256(payload).digest()
    return low64(digest)


def _stable_u64_from_str(value: str) -> int:
    digest = hashlib.sha256(uer_string(str(value))).digest()
    return low64(digest)


def _u01_from_u64(value: int) -> float:
    return (value & _HASH_MASK_64) / float(1 << 64)


def _fast_u01(seed: int, key: int, extra: int = 0) -> float:
    mixed = seed ^ ((key * _HASH_CONST_A) & _HASH_MASK_64)
    if extra:
        mixed ^= ((extra * _HASH_CONST_B) & _HASH_MASK_64)
    return _u01_from_u64(_mix64(mixed))


def _build_cumulative(items: list[tuple[str, float]]) -> tuple[list[str], list[float], float]:
    total = sum(weight for _, weight in items)
    if total <= 0:
        return [items[0][0]] if items else [], [1.0] if items else [], 1.0
    cells: list[str] = []
    cumulative: list[float] = []
    running = 0.0
    for value, weight in items:
        running += weight
        cells.append(value)
        cumulative.append(running)
    return cells, cumulative, total


def _pick_from_cumulative(cells: list[str], cumulative: list[float], total: float, u: float) -> str:
    if not cells:
        return ""
    u = min(max(u, 0.0), 1.0 - 1.0e-12)
    target = u * total
    idx = bisect_left(cumulative, target)
    if idx >= len(cells):
        idx = len(cells) - 1
    return cells[idx]


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


def _largest_remainder_list(
    targets: list[float],
    total: int,
    tie_stream: Optional[_RngStream] = None,
) -> list[int]:
    floors = [int(math.floor(value)) for value in targets]
    residuals = [float(target - floor) for target, floor in zip(targets, floors)]
    base_total = sum(floors)
    remaining = total - base_total
    if remaining > 0:
        tie_values = [0.0] * len(targets)
        if tie_stream is not None:
            tie_values, _, _, _, _, _, _ = tie_stream.draw_uniforms(len(targets))
        ranked = sorted(
            range(len(targets)),
            key=lambda idx: (residuals[idx], tie_values[idx]),
            reverse=True,
        )
        for idx in ranked[:remaining]:
            floors[idx] += 1
    elif remaining < 0:
        ranked = sorted(range(len(targets)), key=lambda idx: (residuals[idx], idx))
        for idx in ranked[: abs(remaining)]:
            floors[idx] = max(floors[idx] - 1, 0)
    return floors


def _normalize_shares(items: list[tuple[str, float]], logger, label: str) -> list[tuple[str, float]]:
    total = sum(share for _, share in items)
    if total <= 0:
        raise ValueError(f"{label} shares sum to zero")
    if abs(total - 1.0) > 1.0e-6:
        logger.warning("%s shares normalized (sum=%.6f)", label, total)
    return [(key, share / total) for key, share in items]


def _categorical_pick(items: list[tuple[str, float]], u: float) -> str:
    if not items:
        return ""
    total = sum(weight for _, weight in items)
    if total <= 0:
        return items[0][0]
    u = min(max(u, 0.0), 1.0 - 1.0e-12)
    target = u * total
    running = 0.0
    for value, weight in items:
        running += weight
        if target <= running:
            return value
    return items[-1][0]


def _apply_caps(
    counts: list[int],
    weights: list[float],
    hard_max: int,
    total_target: int,
    rng_stream: _RngStream,
) -> list[int]:
    capped = counts[:]
    overflow = 0
    for idx, count in enumerate(capped):
        if count > hard_max:
            overflow += count - hard_max
            capped[idx] = hard_max
    if overflow <= 0:
        return capped
    iterations = 0
    remaining = overflow
    while remaining > 0 and iterations < 6:
        indices = [idx for idx, count in enumerate(capped) if count < hard_max and weights[idx] > 0.0]
        if not indices:
            break
        capacity = [hard_max - capped[idx] for idx in indices]
        total_capacity = sum(capacity)
        if total_capacity < remaining:
            raise ValueError("insufficient capacity to reallocate overflow")
        target_weights = [weights[idx] for idx in indices]
        total_weight = sum(target_weights)
        if total_weight <= 0:
            raise ValueError("insufficient weight to reallocate overflow")
        targets = [(remaining * weight) / total_weight for weight in target_weights]
        alloc = _largest_remainder_list(targets, remaining, rng_stream)
        new_remaining = 0
        for idx, add in zip(indices, alloc):
            cap = hard_max - capped[idx]
            if add > cap:
                capped[idx] += cap
                new_remaining += add - cap
            else:
                capped[idx] += add
        remaining = new_remaining
        iterations += 1
    if remaining > 0:
        raise ValueError("cap redistribution failed to place all overflow")
    return capped


def _allocate_with_caps(
    total: int,
    weights: list[float],
    caps: list[int],
    rng_stream: _RngStream,
) -> list[int]:
    if total <= 0:
        return [0] * len(weights)
    if len(weights) != len(caps):
        raise ValueError("weights/caps length mismatch")
    capacity = sum(caps)
    if capacity < total:
        raise ValueError("insufficient capacity to allocate total")
    weights_clean = [max(float(weight), 0.0) for weight in weights]
    if sum(weights_clean) <= 0.0:
        raise ValueError("allocation weights sum to zero")

    alloc = [0] * len(weights_clean)
    remaining = int(total)
    active = [idx for idx, cap in enumerate(caps) if cap > 0]
    iterations = 0
    while remaining > 0 and active:
        iterations += 1
        active_weights = [weights_clean[idx] for idx in active]
        weight_sum = sum(active_weights)
        if weight_sum <= 0.0:
            raise ValueError("allocation weights sum to zero")
        targets = [(remaining * weight) / weight_sum for weight in active_weights]
        alloc_active = _largest_remainder_list(targets, remaining, rng_stream)
        overflow = 0
        next_active: list[int] = []
        for idx, add in zip(active, alloc_active):
            cap_remaining = caps[idx] - alloc[idx]
            if add >= cap_remaining:
                alloc[idx] += cap_remaining
                overflow += add - cap_remaining
            else:
                alloc[idx] += add
                if cap_remaining - add > 0:
                    next_active.append(idx)
        remaining = overflow
        active = next_active
        if iterations > len(weights_clean) + 6:
            break
    if remaining > 0:
        raise ValueError("allocation_with_caps failed to place all counts")
    return alloc


def _merge_parquet_parts(part_paths: list[Path], output_path: Path, logger, label: str) -> None:
    if not part_paths:
        logger.warning("S4: no parquet parts found for %s (output=%s)", label, output_path)
        return
    if not _HAVE_PYARROW:
        if len(part_paths) == 1:
            part_paths[0].replace(output_path)
        else:
            frames = [pl.read_parquet(path) for path in part_paths]
            pl.concat(frames, how="vertical").write_parquet(output_path, compression="zstd")
        logger.info("S4: merged %s parts=%s -> %s (polars fallback)", label, len(part_paths), output_path)
        return
    schema = pq.read_schema(part_paths[0])
    writer = pq.ParquetWriter(output_path, schema, compression="zstd")
    try:
        for part_path in part_paths:
            parquet_file = pq.ParquetFile(part_path)
            for batch in parquet_file.iter_batches(batch_size=_DEFAULT_BATCH_ROWS):
                writer.write_table(pa.Table.from_batches([batch], schema=schema))
    finally:
        writer.close()
    logger.info("S4: merged %s parts=%s -> %s", label, len(part_paths), output_path)


def _emit_region_parts(
    region_id: str,
    party_base_path: Path,
    device_counts_by_party_type: dict[str, dict[str, int]],
    device_type_to_group: dict[str, str],
    group_to_types: dict[str, list[str]],
    os_mix_by_type: dict[str, list[tuple[str, float]]],
    p_zero_by_group: dict[str, float],
    sigma_by_group: dict[str, float],
    weight_floor_eps: float,
    max_devices_per_party: int,
    device_id_stride: int,
    ip_cell_weights: list[tuple[str, str, float]],
    ip_cell_ranges: dict[tuple[str, str], tuple[int, int]],
    lambda_ip_by_group: dict[str, float],
    max_ips_per_device: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    run_log_path: Path,
    tmp_dir: Path,
    buffer_max_rows: int,
    device_schema: dict,
    device_links_schema: dict,
    ip_links_schema: dict,
) -> dict:
    add_file_handler(run_log_path)
    logger = get_logger("engine.layers.l3.seg_6A.s4_device_graph.runner")
    region_label = f"region={region_id}"
    timer = _StepTimer(logger)

    frame = (
        pl.scan_parquet(party_base_path)
        .select(["party_id", "party_type", "region_id", "country_iso"])
        .filter(pl.col("region_id") == region_id)
        .collect()
    )
    if frame.is_empty():
        logger.warning("S4: %s has no parties; emitting empty outputs", region_label)

    party_ids = frame["party_id"].to_list()
    party_types = frame["party_type"].to_list()
    country_isos = frame["country_iso"].to_list()
    party_ids_by_type: dict[str, list[int]] = {}
    party_country_by_id: dict[int, str] = {}
    for party_id, party_type, country_iso in zip(party_ids, party_types, country_isos):
        pid = int(party_id)
        party_ids_by_type.setdefault(str(party_type), []).append(pid)
        party_country_by_id[pid] = str(country_iso)

    device_validator = Draft202012Validator(device_schema)
    device_links_validator = Draft202012Validator(device_links_schema)
    ip_links_validator = Draft202012Validator(ip_links_schema)

    device_part = tmp_dir / f"s4_device_base_6A.region={region_id}.parquet"
    device_links_part = tmp_dir / f"s4_device_links_6A.region={region_id}.parquet"
    ip_links_part = tmp_dir / f"s4_ip_links_6A.region={region_id}.parquet"

    device_frames: list[pl.DataFrame] = []
    device_links_frames: list[pl.DataFrame] = []
    ip_links_frames: list[pl.DataFrame] = []

    device_writer = None
    device_links_writer = None
    ip_links_writer = None
    if _HAVE_PYARROW:
        device_writer = pq.ParquetWriter(
            device_part,
            pa.schema(
                [
                    ("device_id", pa.int64()),
                    ("device_type", pa.string()),
                    ("os_family", pa.string()),
                    ("primary_party_id", pa.int64()),
                    ("home_region_id", pa.string()),
                    ("home_country_iso", pa.string()),
                    ("manifest_fingerprint", pa.string()),
                    ("parameter_hash", pa.string()),
                    ("seed", pa.int64()),
                ]
            ),
            compression="zstd",
        )
        device_links_writer = pq.ParquetWriter(
            device_links_part,
            pa.schema(
                [
                    ("device_id", pa.int64()),
                    ("party_id", pa.int64()),
                    ("account_id", pa.int64()),
                    ("instrument_id", pa.int64()),
                    ("link_role", pa.string()),
                    ("manifest_fingerprint", pa.string()),
                    ("parameter_hash", pa.string()),
                    ("seed", pa.int64()),
                ]
            ),
            compression="zstd",
        )
        ip_links_writer = pq.ParquetWriter(
            ip_links_part,
            pa.schema(
                [
                    ("ip_id", pa.int64()),
                    ("device_id", pa.int64()),
                    ("party_id", pa.int64()),
                    ("link_role", pa.string()),
                    ("manifest_fingerprint", pa.string()),
                    ("parameter_hash", pa.string()),
                    ("seed", pa.int64()),
                ]
            ),
            compression="zstd",
        )

    device_buffer: list[tuple] = []
    device_links_buffer: list[tuple] = []
    ip_links_buffer: list[tuple] = []
    validated_device = False
    validated_device_links = False
    validated_ip_links = False

    def _flush_device_buffers() -> None:
        nonlocal validated_device, validated_device_links
        if not device_buffer:
            return
        device_frame = pl.DataFrame(
            device_buffer,
            schema=[
                "device_id",
                "device_type",
                "os_family",
                "primary_party_id",
                "home_region_id",
                "home_country_iso",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
            orient="row",
        )
        links_frame = pl.DataFrame(
            device_links_buffer,
            schema=[
                "device_id",
                "party_id",
                "account_id",
                "instrument_id",
                "link_role",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
            orient="row",
        )
        if not validated_device:
            _validate_sample_rows(device_frame, device_validator, manifest_fingerprint, "s4_device_base_6A")
            validated_device = True
        if not validated_device_links:
            _validate_sample_rows(links_frame, device_links_validator, manifest_fingerprint, "s4_device_links_6A")
            validated_device_links = True
        if _HAVE_PYARROW:
            device_table = device_frame.to_arrow()
            link_table = links_frame.to_arrow()
            if device_table.schema != device_writer.schema:
                device_table = device_table.cast(device_writer.schema)
            if link_table.schema != device_links_writer.schema:
                link_table = link_table.cast(device_links_writer.schema)
            device_writer.write_table(device_table)
            device_links_writer.write_table(link_table)
        else:
            device_frames.append(device_frame)
            device_links_frames.append(links_frame)
        device_buffer.clear()
        device_links_buffer.clear()

    def _flush_ip_links() -> None:
        nonlocal validated_ip_links
        if not ip_links_buffer:
            return
        links_frame = pl.DataFrame(
            ip_links_buffer,
            schema=[
                "ip_id",
                "device_id",
                "party_id",
                "link_role",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
            orient="row",
        )
        if not validated_ip_links:
            _validate_sample_rows(links_frame, ip_links_validator, manifest_fingerprint, "s4_ip_links_6A")
            validated_ip_links = True
        if _HAVE_PYARROW:
            link_table = links_frame.to_arrow()
            if link_table.schema != ip_links_writer.schema:
                link_table = link_table.cast(ip_links_writer.schema)
            ip_links_writer.write_table(link_table)
        else:
            ip_links_frames.append(links_frame)
        ip_links_buffer.clear()

    total_devices_region = sum(
        sum(type_counts.values()) for type_counts in device_counts_by_party_type.values()
    )
    estimated_ip_links = 0
    for party_type, type_counts in device_counts_by_party_type.items():
        for device_type, count in type_counts.items():
            group_id = device_type_to_group.get(device_type, "")
            estimated_ip_links += int(round(count * float(lambda_ip_by_group.get(group_id) or 0.0)))

    alloc_total = max(
        sum(len(types) for types in group_to_types.values()) * max(len(party_ids_by_type), 1),
        1,
    )
    alloc_tracker = _ProgressTracker(
        alloc_total,
        logger,
        f"S4: allocate devices to parties ({region_label})",
    )
    emit_tracker = _ProgressTracker(
        max(total_devices_region, 1),
        logger,
        f"S4: emit s4_device_base_6A ({region_label})",
    )
    ip_link_tracker = _ProgressTracker(
        max(estimated_ip_links, 1),
        logger,
        f"S4: emit s4_ip_links_6A ({region_label})",
    )

    seed_zero = _seed_for_label(manifest_fingerprint, parameter_hash, f"zero_gate|{region_id}")
    seed_weight = _seed_for_label(manifest_fingerprint, parameter_hash, f"weight|{region_id}")
    seed_os = _seed_for_label(manifest_fingerprint, parameter_hash, f"os_family|{region_id}")
    seed_ip_count = _seed_for_label(manifest_fingerprint, parameter_hash, f"ip_edge_count|{region_id}")
    seed_ip_cell = _seed_for_label(manifest_fingerprint, parameter_hash, f"ip_cell|{region_id}")
    seed_ip_id = _seed_for_label(manifest_fingerprint, parameter_hash, f"ip_id|{region_id}")

    os_cumulative: dict[str, tuple[list[str], list[float], float]] = {}
    for device_type, mix in os_mix_by_type.items():
        os_cumulative[device_type] = _build_cumulative(mix)

    ip_cells = [(f"{ip_type}|{asn}", weight) for ip_type, asn, weight in ip_cell_weights]
    ip_cell_values, ip_cell_cumulative, ip_cell_total = _build_cumulative(ip_cells)

    party_device_totals: dict[int, int] = {}

    for party_type in sorted(party_ids_by_type.keys()):
        parties = sorted(party_ids_by_type[party_type])
        if not parties:
            continue
        for group_id, device_types_in_group in sorted(group_to_types.items()):
            eligible_parties: list[int] = []
            weights: list[float] = []
            p_zero = float(p_zero_by_group.get(group_id) or 0.0)
            sigma = float(sigma_by_group.get(group_id) or 0.0)
            group_hash = _stable_u64_from_str(group_id)
            for party_id in parties:
                current = party_device_totals.get(party_id, 0)
                if current >= max_devices_per_party:
                    continue
                u0 = _fast_u01(seed_zero, party_id, group_hash)
                if u0 < p_zero:
                    continue
                u1 = _fast_u01(seed_weight, party_id, group_hash)
                u1 = min(max(u1, 1.0e-12), 1.0 - 1.0e-12)
                if sigma > 0:
                    z = _normal_icdf(u1)
                    weight = math.exp(sigma * z - 0.5 * sigma * sigma)
                else:
                    weight = 1.0
                weight = max(weight_floor_eps, weight)
                eligible_parties.append(party_id)
                weights.append(weight)

            for device_type in device_types_in_group:
                n_devices = int(device_counts_by_party_type.get(party_type, {}).get(device_type, 0))
                if n_devices <= 0:
                    alloc_tracker.update(1)
                    continue
                if not eligible_parties:
                    raise ValueError(f"No eligible parties for {region_id}/{party_type}/{device_type}")
                caps = [max_devices_per_party - party_device_totals.get(pid, 0) for pid in eligible_parties]
                alloc_counts = _allocate_with_caps(n_devices, weights, caps, _RngStream(
                    f"device_alloc|{region_id}|{party_type}|{group_id}|{device_type}",
                    manifest_fingerprint,
                    parameter_hash,
                    int(seed),
                ))

                for party_id, count in zip(eligible_parties, alloc_counts):
                    if count <= 0:
                        continue
                    start_idx = party_device_totals.get(party_id, 0)
                    end_idx = start_idx + count
                    party_device_totals[party_id] = end_idx
                    device_ids = [
                        party_id * device_id_stride + idx for idx in range(start_idx + 1, end_idx + 1)
                    ]

                    os_values, os_cum, os_total = os_cumulative.get(device_type, ([], [], 1.0))
                    if not os_values:
                        os_values = ["EMBEDDED"]
                        os_cum = [1.0]
                        os_total = 1.0

                    os_families = [
                        _pick_from_cumulative(
                            os_values,
                            os_cum,
                            os_total,
                            _fast_u01(seed_os, device_id),
                        )
                        for device_id in device_ids
                    ]

                    region_str = str(region_id)
                    country_iso = party_country_by_id.get(party_id, "")
                    total_ip_links_added = 0
                    for device_id, os_family in zip(device_ids, os_families):
                        device_buffer.append(
                            (
                                device_id,
                                device_type,
                                os_family,
                                party_id,
                                region_str,
                                country_iso,
                                manifest_fingerprint,
                                parameter_hash,
                                int(seed),
                            )
                        )
                        device_links_buffer.append(
                            (
                                device_id,
                                party_id,
                                None,
                                None,
                                "PRIMARY_OWNER",
                                manifest_fingerprint,
                                parameter_hash,
                                int(seed),
                            )
                        )

                        group_lambda = float(lambda_ip_by_group.get(group_id) or 0.0)
                        base_ip = int(math.floor(group_lambda))
                        frac = max(group_lambda - base_ip, 0.0)
                        k_ip = base_ip
                        if frac > 0:
                            u_ip = _fast_u01(seed_ip_count, device_id)
                            if u_ip < frac:
                                k_ip += 1
                        if max_ips_per_device > 0:
                            k_ip = min(k_ip, max_ips_per_device)

                        for edge_idx in range(k_ip):
                            if not ip_cell_values:
                                break
                            cell_key = _pick_from_cumulative(
                                ip_cell_values,
                                ip_cell_cumulative,
                                ip_cell_total,
                                _fast_u01(seed_ip_cell, device_id, edge_idx),
                            )
                            ip_type, asn_class = cell_key.split("|", 1)
                            cell_range = ip_cell_ranges.get((ip_type, asn_class))
                            if not cell_range:
                                continue
                            start_id, end_id = cell_range
                            span = max(end_id - start_id, 1)
                            ip_id = start_id + int(_fast_u01(seed_ip_id, device_id, edge_idx) * span)
                            ip_links_buffer.append(
                                (
                                    ip_id,
                                    device_id,
                                    party_id,
                                    "TYPICAL_DEVICE_IP",
                                    manifest_fingerprint,
                                    parameter_hash,
                                    int(seed),
                                )
                            )
                        total_ip_links_added += k_ip
                        if len(device_buffer) >= buffer_max_rows or len(device_links_buffer) >= buffer_max_rows:
                            _flush_device_buffers()
                        if len(ip_links_buffer) >= buffer_max_rows:
                            _flush_ip_links()
                    emit_tracker.update(len(device_ids))
                    ip_link_tracker.update(total_ip_links_added)
                alloc_tracker.update(1)

    _flush_device_buffers()
    _flush_ip_links()

    if _HAVE_PYARROW:
        device_writer.close()
        device_links_writer.close()
        ip_links_writer.close()
    else:
        if device_frames:
            pl.concat(device_frames, how="vertical").write_parquet(device_part, compression="zstd")
            pl.concat(device_links_frames, how="vertical").write_parquet(device_links_part, compression="zstd")
        else:
            pl.DataFrame(
                [],
                schema=[
                    "device_id",
                    "device_type",
                    "os_family",
                    "primary_party_id",
                    "home_region_id",
                    "home_country_iso",
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                ],
            ).write_parquet(device_part, compression="zstd")
            pl.DataFrame(
                [],
                schema=[
                    "device_id",
                    "party_id",
                    "account_id",
                    "instrument_id",
                    "link_role",
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                ],
            ).write_parquet(device_links_part, compression="zstd")
        if ip_links_frames:
            pl.concat(ip_links_frames, how="vertical").write_parquet(ip_links_part, compression="zstd")
        else:
            pl.DataFrame(
                [],
                schema=[
                    "ip_id",
                    "device_id",
                    "party_id",
                    "link_role",
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                ],
            ).write_parquet(ip_links_part, compression="zstd")
    timer.info("S4: region emit complete (%s)", region_label)
    return {
        "region_id": region_id,
        "device_part": str(device_part),
        "device_links_part": str(device_links_part),
        "ip_links_part": str(ip_links_part),
        "total_devices": total_devices_region,
    }


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    return run_s4(config, run_id=run_id)


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l3.seg_6A.s4_device_graph.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        _abort("6A.S4.IO_READ_FAILED", "V-01", "run_id_missing", {"path": str(receipt_path)}, None)

    seed = receipt.get("seed")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        _abort(
            "6A.S4.IO_READ_FAILED",
            "V-01",
            "run_receipt_missing_fields",
            {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )
    if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
        _abort(
            "6A.S4.IO_READ_FAILED",
            "V-01",
            "run_receipt_invalid_hashes",
            {"parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info("S4: run log initialized at %s", run_log_path)
    logger.info(
        "S4: objective=build device/IP graph; gated inputs (S0 receipt + sealed inputs + S1/S2/S3 bases + priors/taxonomies) -> outputs s4_device_base_6A + s4_ip_base_6A + s4_device_links_6A + s4_ip_links_6A + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6a_path, dictionary_6a = load_dataset_dictionary(source, "6A")
    reg_6a_path, registry_6a = load_artefact_registry(source, "6A")
    schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6A", "layer3")
    timer.info(
        "S4: loaded contracts (dictionary=%s registry=%s schema_6a=%s schema_layer3=%s)",
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
            "6A.S4.S0_GATE_MISSING",
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
            "6A.S4.SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "6A.S4.SEALED_INPUTS_INVALID",
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
            "6A.S4.SEALED_INPUTS_DIGEST_MISMATCH",
            "V-02",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S4: sealed_inputs digest verified")

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
                "6A.S4.S0_S1_S2_S3_GATE_FAILED",
                "V-03",
                "upstream_gate_not_pass",
                {"segment": required, "status": status},
                manifest_fingerprint,
            )
    if missing_status:
        logger.warning(
            "S4: upstream gate status missing for segments=%s; proceeding in lean mode",
            ",".join(missing_status),
        )
    else:
        logger.info("S4: upstream gate PASS checks complete (segments=1A,1B,2A,2B,3A,3B,5A,5B)")

    logger.warning(
        "S4: run-report check skipped (no layer-3 run-report contract); using gate receipt + sealed inputs only"
    )

    def _find_sealed_input(
        manifest_key: str,
        required: bool = True,
        role: Optional[str] = None,
        fallback_path: Optional[str] = None,
        fallback_schema_ref: Optional[str] = None,
    ) -> dict:
        matches = [row for row in sealed_inputs if row.get("manifest_key") == manifest_key]
        if role:
            matches = [row for row in matches if row.get("role") == role]
        if not matches:
            if fallback_path:
                _emit_validation(
                    logger,
                    manifest_fingerprint,
                    "V-04",
                    "warn",
                    "6A.S4.SEALED_INPUTS_MISSING",
                    {"manifest_key": manifest_key, "fallback_path": fallback_path, "role": role},
                )
                logger.warning(
                    "S4: sealed input missing for %s; using fallback path %s",
                    manifest_key,
                    fallback_path,
                )
                return {
                    "manifest_key": manifest_key,
                    "path_template": fallback_path,
                    "schema_ref": fallback_schema_ref,
                    "role": role,
                    "read_scope": "ROW_LEVEL",
                }
            if required:
                _abort(
                    "6A.S4.SEALED_INPUTS_MISSING",
                    "V-04",
                    "sealed_input_missing",
                    {"manifest_key": manifest_key},
                    manifest_fingerprint,
                )
            return {}
        return matches[0]

    device_counts_entry = _find_sealed_input(
        "mlr.6A.prior.device_counts",
        role="DEVICE_PRIOR",
        fallback_path="config/layer3/6A/priors/device_count_priors_6A.v1.yaml",
        fallback_schema_ref="#/prior/device_count_priors_6A",
    )
    ip_counts_entry = _find_sealed_input(
        "mlr.6A.prior.ip_counts",
        role="IP_PRIOR",
        fallback_path="config/layer3/6A/priors/ip_count_priors_6A.v1.yaml",
        fallback_schema_ref="#/prior/ip_count_priors_6A",
    )
    device_taxonomy_entry = _find_sealed_input(
        "mlr.6A.taxonomy.devices",
        role="TAXONOMY",
        fallback_path="config/layer3/6A/taxonomy/device_taxonomy_6A.v1.yaml",
        fallback_schema_ref="#/taxonomy/device_taxonomy_6A",
    )
    ip_taxonomy_entry = _find_sealed_input(
        "mlr.6A.taxonomy.ips",
        role="TAXONOMY",
        fallback_path="config/layer3/6A/taxonomy/ip_taxonomy_6A.v1.yaml",
        fallback_schema_ref="#/taxonomy/ip_taxonomy_6A",
    )
    device_linkage_entry = _find_sealed_input(
        "mlr.6A.policy.device_linkage_rules",
        role="DEVICE_LINKAGE_RULES",
        fallback_path="config/layer3/6A/policy/device_linkage_rules_6A.v1.yaml",
        fallback_schema_ref="#/policy/device_linkage_rules_6A",
    )
    graph_linkage_entry = _find_sealed_input(
        "mlr.6A.policy.graph_linkage_rules",
        role="GRAPH_LINKAGE_RULES",
        fallback_path="config/layer3/6A/policy/graph_linkage_rules_6A.v1.yaml",
        fallback_schema_ref="#/policy/graph_linkage_rules_6A",
    )

    for entry in (
        device_counts_entry,
        ip_counts_entry,
        device_taxonomy_entry,
        ip_taxonomy_entry,
        device_linkage_entry,
        graph_linkage_entry,
    ):
        if entry.get("read_scope") != "ROW_LEVEL":
            _abort(
                "6A.S4.SEALED_INPUTS_INVALID",
                "V-05",
                "sealed_input_read_scope_invalid",
                {"manifest_key": entry.get("manifest_key"), "read_scope": entry.get("read_scope")},
                manifest_fingerprint,
            )

    device_counts_path = _resolve_dataset_path(device_counts_entry, run_paths, config.external_roots, tokens)
    ip_counts_path = _resolve_dataset_path(ip_counts_entry, run_paths, config.external_roots, tokens)
    device_taxonomy_path = _resolve_dataset_path(device_taxonomy_entry, run_paths, config.external_roots, tokens)
    ip_taxonomy_path = _resolve_dataset_path(ip_taxonomy_entry, run_paths, config.external_roots, tokens)
    device_linkage_path = _resolve_dataset_path(device_linkage_entry, run_paths, config.external_roots, tokens)
    graph_linkage_path = _resolve_dataset_path(graph_linkage_entry, run_paths, config.external_roots, tokens)

    device_counts = _load_yaml(device_counts_path)
    ip_counts = _load_yaml(ip_counts_path)
    device_taxonomy = _load_yaml(device_taxonomy_path)
    ip_taxonomy = _load_yaml(ip_taxonomy_path)
    device_linkage = _load_yaml(device_linkage_path)
    graph_linkage = _load_yaml(graph_linkage_path)

    _validate_payload(
        device_counts,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(device_counts_entry.get("schema_ref") or "#/prior/device_count_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": device_counts_entry.get("manifest_key")},
    )
    _validate_payload(
        ip_counts,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(ip_counts_entry.get("schema_ref") or "#/prior/ip_count_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": ip_counts_entry.get("manifest_key")},
    )
    _validate_payload(
        device_taxonomy,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(device_taxonomy_entry.get("schema_ref") or "#/taxonomy/device_taxonomy_6A"),
        manifest_fingerprint,
        {"manifest_key": device_taxonomy_entry.get("manifest_key")},
    )
    _validate_payload(
        ip_taxonomy,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(ip_taxonomy_entry.get("schema_ref") or "#/taxonomy/ip_taxonomy_6A"),
        manifest_fingerprint,
        {"manifest_key": ip_taxonomy_entry.get("manifest_key")},
    )
    _validate_payload(
        device_linkage,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(device_linkage_entry.get("schema_ref") or "#/policy/device_linkage_rules_6A"),
        manifest_fingerprint,
        {"manifest_key": device_linkage_entry.get("manifest_key")},
    )
    _validate_payload(
        graph_linkage,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(graph_linkage_entry.get("schema_ref") or "#/policy/graph_linkage_rules_6A"),
        manifest_fingerprint,
        {"manifest_key": graph_linkage_entry.get("manifest_key")},
    )

    logger.warning("S4: device/account/instrument access edges ignored in lean mode")
    logger.warning("S4: device sharing rules ignored in lean mode (only primary owners emitted)")

    device_roles = {row.get("role_id") for row in device_linkage.get("link_role_vocabulary", [])}
    if "PRIMARY_OWNER" not in device_roles:
        _abort(
            "6A.S4.PRIOR_PACK_INVALID",
            "V-06",
            "missing_primary_owner_role",
            {"roles": sorted(device_roles)},
            manifest_fingerprint,
        )
    ip_roles = {row.get("role_id") for row in graph_linkage.get("ip_link_roles", [])}
    if "TYPICAL_DEVICE_IP" not in ip_roles:
        _abort(
            "6A.S4.PRIOR_PACK_INVALID",
            "V-06",
            "missing_typical_device_ip_role",
            {"roles": sorted(ip_roles)},
            manifest_fingerprint,
        )
    logger.warning(
        "S4: ip link rules forbid party_id for TYPICAL_DEVICE_IP, but schema requires it; proceeding with party_id populated"
    )

    device_types = device_taxonomy.get("device_types") or []
    device_type_ids = {str(item.get("id")) for item in device_types}
    os_families = device_taxonomy.get("os_families") or []
    os_family_ids = {str(item.get("id")) for item in os_families}
    allowed_os_by_type = {
        str(item.get("id")): [str(x) for x in (item.get("allowed_os_families") or [])] for item in device_types
    }

    ip_types = ip_taxonomy.get("ip_types") or []
    ip_type_ids = {str(item.get("id")) for item in ip_types}
    asn_classes = ip_taxonomy.get("asn_classes") or []
    asn_class_ids = {str(item.get("id")) for item in asn_classes}

    density_model = device_counts.get("density_model") or {}
    lambda_base = density_model.get("party_lambda", {}).get("base_lambda_by_party_type") or {}
    global_multiplier = float(density_model.get("global_density_multiplier") or 1.0)
    type_mix_model = device_counts.get("type_mix_model", {})
    base_mix = type_mix_model.get("base_pi_by_party_type") or {}
    if type_mix_model.get("segment_tilts"):
        logger.warning("S4: segment feature tilts ignored in lean mode")

    sharing_model = device_counts.get("sharing_model") or {}
    device_type_groups = sharing_model.get("device_type_groups") or []
    device_type_to_group: dict[str, str] = {}
    for group in device_type_groups:
        group_id = str(group.get("group_id"))
        for device_type in group.get("device_types") or []:
            device_type_to_group[str(device_type)] = group_id

    weight_model = device_counts.get("allocation_weight_model") or {}
    p_zero_by_group = weight_model.get("p_zero_weight_by_group") or {}
    sigma_by_group = weight_model.get("sigma_by_group") or {}
    weight_floor_eps = float(weight_model.get("weight_floor_eps") or 1.0e-12)
    constraints = device_counts.get("constraints") or {}
    max_devices_per_party = int(constraints.get("max_devices_per_party") or 0)
    if max_devices_per_party <= 0:
        _abort(
            "6A.S4.PRIOR_PACK_INVALID",
            "V-06",
            "invalid_max_devices_per_party",
            {"max_devices_per_party": max_devices_per_party},
            manifest_fingerprint,
        )

    attribute_models = device_counts.get("attribute_models") or {}
    os_model = attribute_models.get("os_family_model") or {}
    os_defaults = os_model.get("defaults") or {}
    os_mix_by_type: dict[str, list[tuple[str, float]]] = {}
    for device_type in device_type_ids:
        rows = os_defaults.get(device_type)
        if rows:
            mix_rows = [(str(row.get("os_family")), float(row.get("share") or 0.0)) for row in rows]
            mix_rows = _normalize_shares(mix_rows, logger, f"S4: os_family mix {device_type}")
            os_mix_by_type[device_type] = mix_rows
        else:
            allowed = allowed_os_by_type.get(device_type) or []
            if allowed:
                os_mix_by_type[device_type] = [(allowed[0], 1.0)]
                logger.warning("S4: os_family mix missing for %s; using %s", device_type, allowed[0])

    ip_edge_model = ip_counts.get("ip_edge_demand_model") or {}
    lambda_ip_by_group = ip_edge_model.get("lambda_ip_per_device_by_group") or {}

    ip_type_mix_model = ip_counts.get("ip_type_mix_model") or {}
    pi_ip_type_by_region = ip_type_mix_model.get("pi_ip_type_by_region") or []
    ip_type_mix_map: dict[str, list[tuple[str, float]]] = {}
    for entry in pi_ip_type_by_region:
        region_id = str(entry.get("region_id"))
        pi_ip = [(str(row.get("ip_type")), float(row.get("share") or 0.0)) for row in (entry.get("pi_ip_type") or [])]
        ip_type_mix_map[region_id] = _normalize_shares(pi_ip, logger, f"S4: ip_type mix {region_id}")

    if not ip_type_mix_map:
        _abort(
            "6A.S4.PRIOR_PACK_INVALID",
            "V-06",
            "ip_type_mix_missing",
            {},
            manifest_fingerprint,
        )

    asn_mix_model = ip_counts.get("asn_mix_model") or {}
    pi_asn_by_ip_type = asn_mix_model.get("pi_asn_class_by_ip_type") or []
    asn_mix_map: dict[str, list[tuple[str, float]]] = {}
    for entry in pi_asn_by_ip_type:
        ip_type = str(entry.get("ip_type"))
        pi_asn = [(str(row.get("asn_class")), float(row.get("share") or 0.0)) for row in (entry.get("pi_asn") or [])]
        asn_mix_map[ip_type] = _normalize_shares(pi_asn, logger, f"S4: asn_class mix {ip_type}")

    sharing_model_ip = ip_counts.get("sharing_model") or {}
    mu_entries = sharing_model_ip.get("mu_dev_per_ip") or []
    mu_dev_per_ip: dict[tuple[str, str], float] = {}
    for entry in mu_entries:
        ip_type = str(entry.get("ip_type"))
        asn_class = str(entry.get("asn_class"))
        mu_dev_per_ip[(ip_type, asn_class)] = float(entry.get("mean") or 0.0)

    ip_constraints = ip_counts.get("constraints") or {}
    max_ips_per_device = int(ip_constraints.get("max_ips_per_device") or 0)
    if max_ips_per_device <= 0:
        max_ips_per_device = 40

    party_entry = find_dataset_entry(dictionary_6a, "s1_party_base_6A").entry
    party_base_path = _resolve_dataset_path(party_entry, run_paths, config.external_roots, tokens)
    if not party_base_path.exists():
        _abort(
            "6A.S4.INPUT_MISSING",
            "V-01",
            "party_base_missing",
            {"path": str(party_base_path)},
            manifest_fingerprint,
        )

    account_entry = find_dataset_entry(dictionary_6a, "s2_account_base_6A").entry
    account_base_path = _resolve_dataset_path(account_entry, run_paths, config.external_roots, tokens)
    if not account_base_path.exists():
        _abort(
            "6A.S4.INPUT_MISSING",
            "V-01",
            "account_base_missing",
            {"path": str(account_base_path)},
            manifest_fingerprint,
        )

    instrument_entry = find_dataset_entry(dictionary_6a, "s3_instrument_base_6A").entry
    instrument_path = _resolve_dataset_path(instrument_entry, run_paths, config.external_roots, tokens)
    if not instrument_path.exists():
        _abort(
            "6A.S4.INPUT_MISSING",
            "V-01",
            "instrument_base_missing",
            {"path": str(instrument_path)},
            manifest_fingerprint,
        )

    instrument_links_entry = find_dataset_entry(dictionary_6a, "s3_account_instrument_links_6A").entry
    instrument_links_path = _resolve_dataset_path(instrument_links_entry, run_paths, config.external_roots, tokens)
    if not instrument_links_path.exists():
        _abort(
            "6A.S4.INPUT_MISSING",
            "V-01",
            "instrument_links_missing",
            {"path": str(instrument_links_path)},
            manifest_fingerprint,
        )

    party_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(party_entry.get("schema_ref") or "#/s1/party_base")
    )
    _inline_external_refs(party_schema, schema_layer3, "schemas.layer3.yaml#")
    party_validator = Draft202012Validator(party_schema)

    party_files = _list_parquet_files(party_base_path)
    party_cells: dict[tuple[str, str], list[int]] = {}
    party_meta: dict[int, tuple[str, str, str]] = {}
    region_country_counts: dict[tuple[str, str], int] = {}
    total_parties = 0

    timer.info("S4: loading party base for device planning (files=%s)", len(party_files))
    for file_path in party_files:
        if _HAVE_PYARROW:
            parquet_file = pq.ParquetFile(file_path)
            for batch in parquet_file.iter_batches(
                batch_size=_DEFAULT_BATCH_ROWS,
                columns=["party_id", "party_type", "region_id", "country_iso"],
            ):
                batch_dict = batch.to_pydict()
                party_ids = batch_dict.get("party_id") or []
                party_types = batch_dict.get("party_type") or []
                region_ids = batch_dict.get("region_id") or []
                country_isos = batch_dict.get("country_iso") or []
                for idx in range(len(party_ids)):
                    party_id = int(party_ids[idx])
                    party_type = str(party_types[idx])
                    region_id = str(region_ids[idx])
                    country_iso = str(country_isos[idx])
                    if party_id in party_meta:
                        _abort(
                            "6A.S4.INPUT_INVALID",
                            "V-06",
                            "duplicate_party_id",
                            {"party_id": party_id},
                            manifest_fingerprint,
                        )
                    party_meta[party_id] = (region_id, country_iso, party_type)
                    party_cells.setdefault((region_id, party_type), []).append(party_id)
                    region_country_counts[(region_id, country_iso)] = (
                        region_country_counts.get((region_id, country_iso), 0) + 1
                    )
                    total_parties += 1
        else:
            frame = pl.read_parquet(file_path, columns=["party_id", "party_type", "region_id", "country_iso"])
            _validate_sample_rows(frame, party_validator, manifest_fingerprint, "s1_party_base_6A")
            for row in frame.iter_rows(named=True):
                party_id = int(row["party_id"])
                party_type = str(row["party_type"])
                region_id = str(row["region_id"])
                country_iso = str(row["country_iso"])
                if party_id in party_meta:
                    _abort(
                        "6A.S4.INPUT_INVALID",
                        "V-06",
                        "duplicate_party_id",
                        {"party_id": party_id},
                        manifest_fingerprint,
                    )
                party_meta[party_id] = (region_id, country_iso, party_type)
                party_cells.setdefault((region_id, party_type), []).append(party_id)
                region_country_counts[(region_id, country_iso)] = (
                    region_country_counts.get((region_id, country_iso), 0) + 1
                )
                total_parties += 1

    region_country_map: dict[str, str] = {}
    for (region_id, country_iso), count in region_country_counts.items():
        if region_id not in region_country_map:
            region_country_map[region_id] = country_iso
            continue
        current = region_country_map[region_id]
        if region_country_counts[(region_id, country_iso)] > region_country_counts[(region_id, current)]:
            region_country_map[region_id] = country_iso

    logger.info(
        "S4: loaded party base for device planning (parties=%s, cells=%s, regions=%s)",
        total_parties,
        len(party_cells),
        len({key[0] for key in party_cells}),
    )

    rng_device_count = _RngStream("device_count_realisation", manifest_fingerprint, parameter_hash, int(seed))
    rng_device_alloc = _RngStream("device_allocation_sampling", manifest_fingerprint, parameter_hash, int(seed))
    rng_device_attr = _RngStream("device_attribute_sampling", manifest_fingerprint, parameter_hash, int(seed))
    rng_ip_count = _RngStream("ip_count_realisation", manifest_fingerprint, parameter_hash, int(seed))
    rng_ip_alloc = _RngStream("ip_allocation_sampling", manifest_fingerprint, parameter_hash, int(seed))
    rng_ip_attr = _RngStream("ip_attribute_sampling", manifest_fingerprint, parameter_hash, int(seed))

    rng_event_rows_device_count: list[dict] = []
    rng_event_rows_device_alloc: list[dict] = []
    rng_event_rows_device_attr: list[dict] = []
    rng_event_rows_ip_count: list[dict] = []
    rng_event_rows_ip_alloc: list[dict] = []
    rng_event_rows_ip_attr: list[dict] = []

    device_counts_by_cell: dict[tuple[str, str, str], int] = {}
    device_counts_by_group_region: dict[tuple[str, str], int] = {}

    count_tracker = _ProgressTracker(len(party_cells), logger, "S4: plan device counts")
    for key, parties in sorted(party_cells.items()):
        region_id, party_type = key
        n_parties = len(parties)
        if n_parties == 0:
            count_tracker.update(1)
            continue
        base_lambda = lambda_base.get(party_type)
        if base_lambda is None:
            _abort(
                "6A.S4.PRIOR_PACK_INVALID",
                "V-06",
                "lambda_missing",
                {"party_type": party_type},
                manifest_fingerprint,
            )
        total_target = float(n_parties) * float(base_lambda) * float(global_multiplier)
        total_int = int(round(total_target))
        mix_rows = base_mix.get(party_type)
        if not mix_rows:
            _abort(
                "6A.S4.PRIOR_PACK_INVALID",
                "V-06",
                "device_mix_missing",
                {"party_type": party_type},
                manifest_fingerprint,
            )
        mix_list = [(str(row.get("device_type")), float(row.get("share") or 0.0)) for row in mix_rows]
        normalized_mix = _normalize_shares(mix_list, logger, f"S4: device mix {party_type}")
        targets = [total_target * share for _, share in normalized_mix]
        before_hi = rng_device_count.counter_hi
        before_lo = rng_device_count.counter_lo
        draws_before = rng_device_count.draws_total
        blocks_before = rng_device_count.blocks_total
        counts = _largest_remainder_list(targets, total_int, rng_device_count)
        draws = rng_device_count.draws_total - draws_before
        blocks = rng_device_count.blocks_total - blocks_before
        after_hi = rng_device_count.counter_hi
        after_lo = rng_device_count.counter_lo
        rng_device_count.record_event()
        rng_event_rows_device_count.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S4",
                "substream_label": "device_count_realisation",
                "rng_counter_before_lo": int(before_lo),
                "rng_counter_before_hi": int(before_hi),
                "rng_counter_after_lo": int(after_lo),
                "rng_counter_after_hi": int(after_hi),
                "draws": str(draws),
                "blocks": int(blocks),
                "context": {
                    "region_id": region_id,
                    "party_type": party_type,
                    "n_parties": n_parties,
                    "total_target": total_target,
                    "total_int": total_int,
                    "device_types": len(normalized_mix),
                },
            }
        )
        for (device_type, _), count in zip(normalized_mix, counts):
            if device_type not in device_type_ids:
                _abort(
                    "6A.S4.PRIOR_PACK_INVALID",
                    "V-06",
                    "device_type_unknown",
                    {"device_type": device_type},
                    manifest_fingerprint,
                )
            device_counts_by_cell[(region_id, party_type, device_type)] = int(count)
            group_id = device_type_to_group.get(device_type, "")
            if group_id:
                device_counts_by_group_region[(region_id, group_id)] = (
                    device_counts_by_group_region.get((region_id, group_id), 0) + int(count)
                )
        count_tracker.update(1)

    total_devices = sum(device_counts_by_cell.values())
    logger.info("S4: planned device counts (total_devices=%s)", total_devices)

    ip_counts_by_cell: dict[tuple[str, str, str], int] = {}
    ip_cell_weights_by_region: dict[str, list[tuple[str, str, float]]] = {}

    ip_count_tracker = _ProgressTracker(len(region_country_map), logger, "S4: plan IP counts")
    for region_id in sorted(region_country_map.keys()):
        total_edge_target = 0.0
        for group_id, lambda_ip in lambda_ip_by_group.items():
            device_count = device_counts_by_group_region.get((region_id, str(group_id)), 0)
            total_edge_target += float(device_count) * float(lambda_ip)
        if total_edge_target <= 0:
            ip_count_tracker.update(1)
            continue
        ip_type_mix = ip_type_mix_map.get(region_id)
        if not ip_type_mix:
            ip_type_mix = next(iter(ip_type_mix_map.values()))
            logger.warning("S4: ip_type mix missing for %s; using fallback", region_id)
        cell_targets: list[tuple[tuple[str, str], float]] = []
        for ip_type, share_type in ip_type_mix:
            if ip_type not in ip_type_ids:
                _abort(
                    "6A.S4.PRIOR_PACK_INVALID",
                    "V-06",
                    "ip_type_unknown",
                    {"ip_type": ip_type},
                    manifest_fingerprint,
                )
            asn_mix = asn_mix_map.get(ip_type)
            if not asn_mix:
                logger.warning("S4: asn mix missing for ip_type=%s; using uniform", ip_type)
                asn_mix = [(asn, 1.0 / len(asn_class_ids)) for asn in sorted(asn_class_ids)]
            for asn_class, share_asn in asn_mix:
                if asn_class not in asn_class_ids:
                    _abort(
                        "6A.S4.PRIOR_PACK_INVALID",
                        "V-06",
                        "asn_class_unknown",
                        {"asn_class": asn_class},
                        manifest_fingerprint,
                    )
                mu = float(mu_dev_per_ip.get((ip_type, asn_class)) or 1.0)
                mu = max(mu, 1.0e-9)
                cell_target = total_edge_target * float(share_type) * float(share_asn) / mu
                cell_targets.append(((ip_type, asn_class), cell_target))

        if not cell_targets:
            ip_count_tracker.update(1)
            continue
        total_target = sum(value for _, value in cell_targets)
        total_int = int(round(total_target))
        targets = [value for _, value in cell_targets]
        before_hi = rng_ip_count.counter_hi
        before_lo = rng_ip_count.counter_lo
        draws_before = rng_ip_count.draws_total
        blocks_before = rng_ip_count.blocks_total
        counts = _largest_remainder_list(targets, total_int, rng_ip_count)
        draws = rng_ip_count.draws_total - draws_before
        blocks = rng_ip_count.blocks_total - blocks_before
        after_hi = rng_ip_count.counter_hi
        after_lo = rng_ip_count.counter_lo
        rng_ip_count.record_event()
        rng_event_rows_ip_count.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S4",
                "substream_label": "ip_count_realisation",
                "rng_counter_before_lo": int(before_lo),
                "rng_counter_before_hi": int(before_hi),
                "rng_counter_after_lo": int(after_lo),
                "rng_counter_after_hi": int(after_hi),
                "draws": str(draws),
                "blocks": int(blocks),
                "context": {
                    "region_id": region_id,
                    "total_edge_target": total_edge_target,
                    "total_target": total_target,
                    "total_int": total_int,
                    "cells": len(cell_targets),
                },
            }
        )
        for (ip_type, asn_class), count in zip((key for key, _ in cell_targets), counts):
            if count <= 0:
                continue
            ip_counts_by_cell[(region_id, ip_type, asn_class)] = int(count)
        weights: list[tuple[str, str, float]] = []
        for (region_cell, cell_target), count in zip(cell_targets, counts):
            if count <= 0:
                continue
            ip_type, asn_class = region_cell
            mu = float(mu_dev_per_ip.get((ip_type, asn_class)) or 1.0)
            weight = float(count) * mu
            weights.append((ip_type, asn_class, weight))
        if weights:
            total_weight = sum(value for _, _, value in weights)
            ip_cell_weights_by_region[region_id] = [
                (ip_type, asn_class, value / total_weight) for ip_type, asn_class, value in weights
            ]
        ip_count_tracker.update(1)

    total_ips = sum(ip_counts_by_cell.values())
    logger.info("S4: planned IP counts (total_ips=%s)", total_ips)

    device_base_entry = find_dataset_entry(dictionary_6a, "s4_device_base_6A").entry
    ip_base_entry = find_dataset_entry(dictionary_6a, "s4_ip_base_6A").entry
    device_links_entry = find_dataset_entry(dictionary_6a, "s4_device_links_6A").entry
    ip_links_entry = find_dataset_entry(dictionary_6a, "s4_ip_links_6A").entry
    neighbourhood_entry = find_dataset_entry(dictionary_6a, "s4_entity_neighbourhoods_6A").entry
    summary_entry = find_dataset_entry(dictionary_6a, "s4_network_summary_6A").entry

    device_base_path = _resolve_dataset_path(device_base_entry, run_paths, config.external_roots, tokens)
    ip_base_path = _resolve_dataset_path(ip_base_entry, run_paths, config.external_roots, tokens)
    device_links_path = _resolve_dataset_path(device_links_entry, run_paths, config.external_roots, tokens)
    ip_links_path = _resolve_dataset_path(ip_links_entry, run_paths, config.external_roots, tokens)

    tmp_dir = run_paths.tmp_root / f"s4_device_graph_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    device_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(device_base_entry.get("schema_ref") or "#/s4/device_base")
    )
    _inline_external_refs(device_schema, schema_layer3, "schemas.layer3.yaml#")

    ip_schema = _schema_from_pack(schema_6a, _anchor_from_ref(ip_base_entry.get("schema_ref") or "#/s4/ip_base"))
    _inline_external_refs(ip_schema, schema_layer3, "schemas.layer3.yaml#")
    ip_validator = Draft202012Validator(ip_schema)

    device_links_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(device_links_entry.get("schema_ref") or "#/s4/device_links")
    )
    _inline_external_refs(device_links_schema, schema_layer3, "schemas.layer3.yaml#")

    ip_links_schema = _schema_from_pack(
        schema_6a, _anchor_from_ref(ip_links_entry.get("schema_ref") or "#/s4/ip_links")
    )
    _inline_external_refs(ip_links_schema, schema_layer3, "schemas.layer3.yaml#")

    tmp_device = tmp_dir / device_base_path.name
    tmp_device_links = tmp_dir / device_links_path.name
    tmp_ip = tmp_dir / ip_base_path.name
    tmp_ip_links = tmp_dir / ip_links_path.name

    ip_writer = None
    ip_frames: list[pl.DataFrame] = []
    ip_buffer: list[tuple] = []

    def _flush_ip_buffers() -> None:
        nonlocal ip_writer
        if not ip_buffer:
            return
        ip_frame = pl.DataFrame(
            ip_buffer,
            schema=[
                "ip_id",
                "ip_type",
                "asn_class",
                "country_iso",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
            orient="row",
        )
        _validate_sample_rows(ip_frame, ip_validator, manifest_fingerprint, "s4_ip_base_6A")
        if _HAVE_PYARROW:
            ip_table = ip_frame.to_arrow()
            if ip_writer is None:
                ip_writer = pq.ParquetWriter(tmp_ip, ip_table.schema, compression="zstd")
            ip_writer.write_table(ip_table)
        else:
            ip_frames.append(ip_frame)
        ip_buffer.clear()

    ip_id_counter = 1
    ip_cell_ranges: dict[tuple[str, str, str], tuple[int, int]] = {}
    ip_emit_tracker = _ProgressTracker(total_ips, logger, "S4: emit s4_ip_base_6A")
    for (region_id, ip_type, asn_class) in sorted(ip_counts_by_cell.keys()):
        count = int(ip_counts_by_cell[(region_id, ip_type, asn_class)])
        if count <= 0:
            continue
        start_id = ip_id_counter
        end_id = ip_id_counter + count
        ip_cell_ranges[(region_id, ip_type, asn_class)] = (start_id, end_id)
        country_iso = region_country_map.get(region_id, "")
        for ip_id in range(start_id, end_id):
            ip_buffer.append(
                (
                    ip_id,
                    ip_type,
                    asn_class,
                    country_iso,
                    manifest_fingerprint,
                    parameter_hash,
                    int(seed),
                )
            )
            if len(ip_buffer) >= _BUFFER_MAX_ROWS:
                _flush_ip_buffers()
            ip_emit_tracker.update(1)
        ip_id_counter = end_id
    _flush_ip_buffers()

    device_id_stride = max_devices_per_party + 1

    if ip_writer is None:
        if ip_frames:
            pl.concat(ip_frames, how="vertical").write_parquet(tmp_ip, compression="zstd")
        else:
            pl.DataFrame(
                [],
                schema=[
                    "ip_id",
                    "ip_type",
                    "asn_class",
                    "country_iso",
                    "manifest_fingerprint",
                    "parameter_hash",
                    "seed",
                ],
            ).write_parquet(tmp_ip, compression="zstd")
    else:
        ip_writer.close()

    group_to_types: dict[str, list[str]] = {}
    for device_type, group_id in device_type_to_group.items():
        group_to_types.setdefault(group_id, []).append(device_type)
    for types in group_to_types.values():
        types.sort()

    region_ids = sorted({region_id for (region_id, _, _) in device_counts_by_cell.keys()})
    device_counts_by_region: dict[str, dict[str, dict[str, int]]] = {}
    for (region_id, party_type, device_type), count in device_counts_by_cell.items():
        device_counts_by_region.setdefault(region_id, {}).setdefault(party_type, {})[device_type] = int(count)

    ip_cell_ranges_by_region: dict[str, dict[tuple[str, str], tuple[int, int]]] = {}
    for (region_id, ip_type, asn_class), range_tuple in ip_cell_ranges.items():
        ip_cell_ranges_by_region.setdefault(region_id, {})[(ip_type, asn_class)] = range_tuple

    part_dir = tmp_dir / "region_parts"
    part_dir.mkdir(parents=True, exist_ok=True)

    workers_env = os.getenv("ENGINE_6A_S4_WORKERS")
    if workers_env:
        try:
            worker_count = max(int(workers_env), 1)
        except ValueError:
            worker_count = max(os.cpu_count() or 1, 1)
    else:
        worker_count = max(os.cpu_count() or 1, 1)
    worker_count = min(worker_count, max(len(region_ids), 1))
    use_parallel = _HAVE_PYARROW and worker_count > 1 and len(region_ids) > 1
    if not _HAVE_PYARROW:
        logger.warning("S4: pyarrow not available; parallel merge disabled (falling back to single worker)")
        use_parallel = False
        worker_count = 1

    logger.info(
        "S4: emission strategy (regions=%s workers=%s parallel=%s buffer_rows=%s)",
        len(region_ids),
        worker_count,
        use_parallel,
        _BUFFER_MAX_ROWS,
    )

    results: list[dict] = []
    if use_parallel:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = {}
            for region_id in region_ids:
                futures[
                    executor.submit(
                        _emit_region_parts,
                        region_id,
                        party_base_path,
                        device_counts_by_region.get(region_id, {}),
                        device_type_to_group,
                        group_to_types,
                        os_mix_by_type,
                        p_zero_by_group,
                        sigma_by_group,
                        weight_floor_eps,
                        max_devices_per_party,
                        device_id_stride,
                        ip_cell_weights_by_region.get(region_id, []),
                        ip_cell_ranges_by_region.get(region_id, {}),
                        lambda_ip_by_group,
                        max_ips_per_device,
                        manifest_fingerprint,
                        parameter_hash,
                        int(seed),
                        run_log_path,
                        part_dir,
                        _BUFFER_MAX_ROWS,
                        device_schema,
                        device_links_schema,
                        ip_links_schema,
                    )
                ] = region_id
            for future in as_completed(futures):
                results.append(future.result())
    else:
        for region_id in region_ids:
            results.append(
                _emit_region_parts(
                    region_id,
                    party_base_path,
                    device_counts_by_region.get(region_id, {}),
                    device_type_to_group,
                    group_to_types,
                    os_mix_by_type,
                    p_zero_by_group,
                    sigma_by_group,
                    weight_floor_eps,
                    max_devices_per_party,
                    device_id_stride,
                    ip_cell_weights_by_region.get(region_id, []),
                    ip_cell_ranges_by_region.get(region_id, {}),
                    lambda_ip_by_group,
                    max_ips_per_device,
                    manifest_fingerprint,
                    parameter_hash,
                    int(seed),
                    run_log_path,
                    part_dir,
                    _BUFFER_MAX_ROWS,
                    device_schema,
                    device_links_schema,
                    ip_links_schema,
                )
            )

    if not results:
        pl.DataFrame(
            [],
            schema=[
                "device_id",
                "device_type",
                "os_family",
                "primary_party_id",
                "home_region_id",
                "home_country_iso",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
        ).write_parquet(tmp_device, compression="zstd")
        pl.DataFrame(
            [],
            schema=[
                "device_id",
                "party_id",
                "account_id",
                "instrument_id",
                "link_role",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
        ).write_parquet(tmp_device_links, compression="zstd")
        pl.DataFrame(
            [],
            schema=[
                "ip_id",
                "device_id",
                "party_id",
                "link_role",
                "manifest_fingerprint",
                "parameter_hash",
                "seed",
            ],
        ).write_parquet(tmp_ip_links, compression="zstd")
    else:
        device_part_paths = sorted(Path(result["device_part"]) for result in results)
        device_links_part_paths = sorted(Path(result["device_links_part"]) for result in results)
        ip_links_part_paths = sorted(Path(result["ip_links_part"]) for result in results)
        _merge_parquet_parts(device_part_paths, tmp_device, logger, "s4_device_base_6A")
        _merge_parquet_parts(device_links_part_paths, tmp_device_links, logger, "s4_device_links_6A")
        _merge_parquet_parts(ip_links_part_paths, tmp_ip_links, logger, "s4_ip_links_6A")

    if not rng_event_rows_device_alloc:
        rng_device_alloc.record_event()
        rng_event_rows_device_alloc.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S4",
                "substream_label": "device_allocation_sampling",
                "rng_counter_before_lo": int(rng_device_alloc.counter_lo),
                "rng_counter_before_hi": int(rng_device_alloc.counter_hi),
                "rng_counter_after_lo": int(rng_device_alloc.counter_lo),
                "rng_counter_after_hi": int(rng_device_alloc.counter_hi),
                "draws": "0",
                "blocks": 0,
                "context": {"method": "region_parallel", "regions": len(region_ids)},
            }
        )

    if not rng_event_rows_device_attr:
        rng_device_attr.record_event()
        rng_event_rows_device_attr.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S4",
                "substream_label": "device_attribute_sampling",
                "rng_counter_before_lo": int(rng_device_attr.counter_lo),
                "rng_counter_before_hi": int(rng_device_attr.counter_hi),
                "rng_counter_after_lo": int(rng_device_attr.counter_lo),
                "rng_counter_after_hi": int(rng_device_attr.counter_hi),
                "draws": "0",
                "blocks": 0,
                "context": {"method": "deterministic_hash", "regions": len(region_ids)},
            }
        )

    _publish_parquet_file_idempotent(
        tmp_device,
        device_base_path,
        logger,
        "s4_device_base_6A",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_parquet_file_idempotent(
        tmp_ip,
        ip_base_path,
        logger,
        "s4_ip_base_6A",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_parquet_file_idempotent(
        tmp_device_links,
        device_links_path,
        logger,
        "s4_device_links_6A",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_parquet_file_idempotent(
        tmp_ip_links,
        ip_links_path,
        logger,
        "s4_ip_links_6A",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )

    neighbourhoods_path = None
    summary_path = None
    logger.info("S4: optional outputs skipped (neighbourhoods_path=%s summary_path=%s)", neighbourhoods_path, summary_path)

    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6A.S4 device/IP graph RNG audit",
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
        for stream in (
            rng_device_count,
            rng_device_alloc,
            rng_device_attr,
            rng_ip_count,
            rng_ip_alloc,
            rng_ip_attr,
        ):
            trace_row = stream.trace_row(run_id_value, int(seed), "6A.S4")
            handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S4: appended rng_trace_log rows for device + ip streams")

    if not rng_event_rows_ip_alloc:
        rng_ip_alloc.record_event()
        rng_event_rows_ip_alloc.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S4",
                "substream_label": "ip_allocation_sampling",
                "rng_counter_before_lo": int(rng_ip_alloc.counter_lo),
                "rng_counter_before_hi": int(rng_ip_alloc.counter_hi),
                "rng_counter_after_lo": int(rng_ip_alloc.counter_lo),
                "rng_counter_after_hi": int(rng_ip_alloc.counter_hi),
                "draws": "0",
                "blocks": 0,
                "context": {
                    "method": "deterministic_hash",
                    "total_devices": total_devices,
                    "total_ips": total_ips,
                },
            }
        )

    if not rng_event_rows_ip_attr:
        rng_ip_attr.record_event()
        rng_event_rows_ip_attr.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S4",
                "substream_label": "ip_attribute_sampling",
                "rng_counter_before_lo": int(rng_ip_attr.counter_lo),
                "rng_counter_before_hi": int(rng_ip_attr.counter_hi),
                "rng_counter_after_lo": int(rng_ip_attr.counter_lo),
                "rng_counter_after_hi": int(rng_ip_attr.counter_hi),
                "draws": "0",
                "blocks": 0,
                "context": {
                    "ip_cells": len(ip_counts_by_cell),
                    "asn_classes": len({asn for (_, _, asn) in ip_counts_by_cell}),
                },
            }
        )

    rng_device_count_entry = find_dataset_entry(dictionary_6a, "rng_event_device_count_realisation").entry
    rng_device_alloc_entry = find_dataset_entry(dictionary_6a, "rng_event_device_allocation_sampling").entry
    rng_device_attr_entry = find_dataset_entry(dictionary_6a, "rng_event_device_attribute_sampling").entry
    rng_ip_count_entry = find_dataset_entry(dictionary_6a, "rng_event_ip_count_realisation").entry
    rng_ip_alloc_entry = find_dataset_entry(dictionary_6a, "rng_event_ip_allocation_sampling").entry
    rng_ip_attr_entry = find_dataset_entry(dictionary_6a, "rng_event_ip_attribute_sampling").entry

    rng_device_count_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_device_count_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_device_alloc_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_device_alloc_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_device_attr_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_device_attr_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_ip_count_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_ip_count_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_ip_alloc_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_ip_alloc_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_ip_attr_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_ip_attr_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )

    tmp_device_count_path = tmp_dir / rng_device_count_path.name
    tmp_device_alloc_path = tmp_dir / rng_device_alloc_path.name
    tmp_device_attr_path = tmp_dir / rng_device_attr_path.name
    tmp_ip_count_path = tmp_dir / rng_ip_count_path.name
    tmp_ip_alloc_path = tmp_dir / rng_ip_alloc_path.name
    tmp_ip_attr_path = tmp_dir / rng_ip_attr_path.name

    tmp_paths = {
        tmp_device_count_path,
        tmp_device_alloc_path,
        tmp_device_attr_path,
        tmp_ip_count_path,
        tmp_ip_alloc_path,
        tmp_ip_attr_path,
    }
    if len(tmp_paths) < 6:
        tmp_device_count_path = tmp_dir / "device_count_realisation.jsonl"
        tmp_device_alloc_path = tmp_dir / "device_allocation_sampling.jsonl"
        tmp_device_attr_path = tmp_dir / "device_attribute_sampling.jsonl"
        tmp_ip_count_path = tmp_dir / "ip_count_realisation.jsonl"
        tmp_ip_alloc_path = tmp_dir / "ip_allocation_sampling.jsonl"
        tmp_ip_attr_path = tmp_dir / "ip_attribute_sampling.jsonl"

    tmp_device_count_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_device_count) + "\n",
        encoding="utf-8",
    )
    tmp_device_alloc_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_device_alloc) + "\n",
        encoding="utf-8",
    )
    tmp_device_attr_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_device_attr) + "\n",
        encoding="utf-8",
    )
    tmp_ip_count_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_ip_count) + "\n",
        encoding="utf-8",
    )
    tmp_ip_alloc_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_ip_alloc) + "\n",
        encoding="utf-8",
    )
    tmp_ip_attr_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_ip_attr) + "\n",
        encoding="utf-8",
    )

    _publish_jsonl_file_idempotent(
        tmp_device_count_path,
        rng_device_count_path,
        logger,
        "rng_event_device_count_realisation",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_device_alloc_path,
        rng_device_alloc_path,
        logger,
        "rng_event_device_allocation_sampling",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_device_attr_path,
        rng_device_attr_path,
        logger,
        "rng_event_device_attribute_sampling",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_ip_count_path,
        rng_ip_count_path,
        logger,
        "rng_event_ip_count_realisation",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_ip_alloc_path,
        rng_ip_alloc_path,
        logger,
        "rng_event_ip_allocation_sampling",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_ip_attr_path,
        rng_ip_attr_path,
        logger,
        "rng_event_ip_attribute_sampling",
        "6A.S4.IO_WRITE_CONFLICT",
        "6A.S4.IO_WRITE_FAILED",
    )

    timer.info("S4: device/IP graph generation complete")
    return S4Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        device_base_path=device_base_path,
        ip_base_path=ip_base_path,
        device_links_path=device_links_path,
        ip_links_path=ip_links_path,
        neighbourhoods_path=None,
        summary_path=None,
    )
