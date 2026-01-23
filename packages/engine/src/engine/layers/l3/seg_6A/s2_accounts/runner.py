"""S2 account base runner for Segment 6A."""

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


MODULE_NAME = "6A.s2_accounts"
SEGMENT = "6A"
STATE = "S2"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_DEFAULT_BATCH_ROWS = 50_000


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    account_base_path: Path
    holdings_path: Path
    summary_path: Optional[Path]
    merchant_base_path: Optional[Path]


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
    logger = get_logger("engine.layers.l3.seg_6A.s2_accounts.runner")
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
            "6A.S2.SCHEMA_INVALID",
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
        logger.info("S2: published %s to %s", label, final_path)
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
        logger.info("S2: published %s to %s", label, final_path)
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
            "6A.S2.SCHEMA_INVALID",
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
    party_id: int,
    account_type: str,
    label: str,
) -> float:
    payload = (
        uer_string("mlr:6A")
        + uer_string("s2")
        + uer_string(label)
        + uer_string(manifest_fingerprint)
        + uer_string(parameter_hash)
        + ser_u64(int(party_id))
        + uer_string(account_type)
    )
    digest = hashlib.sha256(payload).digest()
    return u01(low64(digest))


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


def _largest_remainder(
    targets: dict[tuple[str, str, str, str], float],
    total: int,
    tie_stream: Optional[_RngStream] = None,
) -> tuple[dict[tuple[str, str, str, str], int], dict]:
    floors = {key: int(math.floor(value)) for key, value in targets.items()}
    residuals = {key: float(targets[key] - floors[key]) for key in targets}
    base_total = sum(floors.values())
    remaining = total - base_total
    draw_meta = {
        "draws": 0,
        "blocks": 0,
        "before_hi": None,
        "before_lo": None,
        "after_hi": None,
        "after_lo": None,
    }
    if remaining > 0:
        keys = sorted(residuals.keys())
        tie_values = [0.0] * len(keys)
        if tie_stream is not None:
            tie_values, before_hi, before_lo, after_hi, after_lo, draws, blocks = tie_stream.draw_uniforms(len(keys))
            draw_meta.update(
                {
                    "draws": draws,
                    "blocks": blocks,
                    "before_hi": before_hi,
                    "before_lo": before_lo,
                    "after_hi": after_hi,
                    "after_lo": after_lo,
                }
            )
        ranked = sorted(
            range(len(keys)),
            key=lambda idx: (residuals[keys[idx]], tie_values[idx]),
            reverse=True,
        )
        for idx in ranked[:remaining]:
            floors[keys[idx]] += 1
    elif remaining < 0:
        keys = sorted(residuals.keys())
        ranked = sorted(range(len(keys)), key=lambda idx: (residuals[keys[idx]], keys[idx]))
        for idx in ranked[: abs(remaining)]:
            floors[keys[idx]] = max(floors[keys[idx]] - 1, 0)
    return floors, draw_meta


def _largest_remainder_list(
    targets: list[float],
    total: int,
    tie_stream: Optional[_RngStream] = None,
) -> tuple[list[int], dict]:
    floors = [int(math.floor(value)) for value in targets]
    residuals = [float(target - floor) for target, floor in zip(targets, floors)]
    base_total = sum(floors)
    remaining = total - base_total
    draw_meta = {
        "draws": 0,
        "blocks": 0,
        "before_hi": None,
        "before_lo": None,
        "after_hi": None,
        "after_lo": None,
    }
    if remaining > 0:
        tie_values = [0.0] * len(targets)
        if tie_stream is not None:
            tie_values, before_hi, before_lo, after_hi, after_lo, draws, blocks = tie_stream.draw_uniforms(len(targets))
            draw_meta.update(
                {
                    "draws": draws,
                    "blocks": blocks,
                    "before_hi": before_hi,
                    "before_lo": before_lo,
                    "after_hi": after_hi,
                    "after_lo": after_lo,
                }
            )
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
    return floors, draw_meta


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l3.seg_6A.s2_accounts.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        _abort("6A.S2.IO_READ_FAILED", "V-01", "run_id_missing", {"path": str(receipt_path)}, None)

    seed = receipt.get("seed")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        _abort(
            "6A.S2.IO_READ_FAILED",
            "V-01",
            "run_receipt_missing_fields",
            {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )
    if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
        _abort(
            "6A.S2.IO_READ_FAILED",
            "V-01",
            "run_receipt_invalid_hashes",
            {"parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info("S2: run log initialized at %s", run_log_path)
    logger.info(
        "S2: objective=build account base; gated inputs (S0 receipt + sealed inputs + S1 party base + priors/taxonomy) -> outputs s2_account_base_6A + s2_party_product_holdings_6A + optional summary + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6a_path, dictionary_6a = load_dataset_dictionary(source, "6A")
    reg_6a_path, registry_6a = load_artefact_registry(source, "6A")
    schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6A", "layer3")
    timer.info(
        "S2: loaded contracts (dictionary=%s registry=%s schema_6a=%s schema_layer3=%s)",
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

    receipt_entry = find_dataset_entry(dictionary_6a, "s0_gate_receipt_6A").entry
    sealed_entry = find_dataset_entry(dictionary_6a, "sealed_inputs_6A").entry
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

    if not receipt_path.exists():
        _abort(
            "6A.S2.S0_GATE_FAILED",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if not sealed_inputs_path.exists():
        _abort(
            "6A.S2.SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    s0_receipt = _load_json(receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "6A.S2.SEALED_INPUTS_INVALID",
            "V-01",
            "sealed_inputs_not_list",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    _validate_payload(
        s0_receipt,
        schema_layer3,
        schema_layer3,
        "#/gate/6A/s0_gate_receipt_6A",
        manifest_fingerprint,
        {"path": str(receipt_path)},
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
    if digest_actual != digest_expected:
        _abort(
            "6A.S2.SEALED_INPUTS_DIGEST_MISMATCH",
            "V-02",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S2: sealed_inputs digest verified")

    upstream_segments = s0_receipt.get("upstream_segments") or {}
    for required in ("1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B"):
        status = str((upstream_segments.get(required) or {}).get("status") or "")
        if status != "PASS":
            _abort(
                "6A.S2.S0_GATE_FAILED",
                "V-03",
                "upstream_gate_not_pass",
                {"segment": required, "status": status},
                manifest_fingerprint,
            )
    logger.info("S2: upstream gate PASS checks complete (segments=1A,1B,2A,2B,3A,3B,5A,5B)")

    logger.warning(
        "S2: run-report check skipped (no layer-3 run-report contract); using gate receipt + sealed inputs only"
    )

    def _find_sealed_input(manifest_key: str, required: bool = True, role: Optional[str] = None) -> dict:
        matches = [row for row in sealed_inputs if row.get("manifest_key") == manifest_key]
        if role:
            matches = [row for row in matches if row.get("role") == role]
        if not matches:
            if required:
                _abort(
                    "6A.S2.SEALED_INPUTS_MISSING",
                    "V-04",
                    "sealed_input_missing",
                    {"manifest_key": manifest_key},
                    manifest_fingerprint,
                )
            return {}
        return matches[0]

    product_mix_entry = _find_sealed_input("mlr.6A.prior.product_mix", role="PRODUCT_PRIOR")
    account_per_party_entry = _find_sealed_input("mlr.6A.prior.account_per_party", role="PRODUCT_PRIOR")
    account_taxonomy_entry = _find_sealed_input("mlr.6A.taxonomy.account_types", role="TAXONOMY")
    party_taxonomy_entry = _find_sealed_input("mlr.6A.taxonomy.party", role="TAXONOMY")
    segmentation_entry = _find_sealed_input("mlr.6A.prior.segmentation", role="SEGMENT_PRIOR")
    linkage_entry = _find_sealed_input("mlr.6A.policy.product_linkage_rules", required=False, role="POLICY")
    eligibility_entry = _find_sealed_input("mlr.6A.policy.product_eligibility_config", required=False, role="POLICY")

    required_entries = (
        product_mix_entry,
        account_per_party_entry,
        account_taxonomy_entry,
        party_taxonomy_entry,
        segmentation_entry,
    )
    for entry in required_entries:
        if entry.get("read_scope") != "ROW_LEVEL":
            _abort(
                "6A.S2.SEALED_INPUTS_INVALID",
                "V-05",
                "sealed_input_read_scope_invalid",
                {"manifest_key": entry.get("manifest_key"), "read_scope": entry.get("read_scope")},
                manifest_fingerprint,
            )
    for entry in (linkage_entry, eligibility_entry):
        if entry and entry.get("read_scope") != "ROW_LEVEL":
            _abort(
                "6A.S2.SEALED_INPUTS_INVALID",
                "V-05",
                "sealed_input_read_scope_invalid",
                {"manifest_key": entry.get("manifest_key"), "read_scope": entry.get("read_scope")},
                manifest_fingerprint,
            )

    product_mix_path = _resolve_dataset_path(product_mix_entry, run_paths, config.external_roots, tokens)
    account_per_party_path = _resolve_dataset_path(account_per_party_entry, run_paths, config.external_roots, tokens)
    account_taxonomy_path = _resolve_dataset_path(account_taxonomy_entry, run_paths, config.external_roots, tokens)
    party_taxonomy_path = _resolve_dataset_path(party_taxonomy_entry, run_paths, config.external_roots, tokens)
    segmentation_path = _resolve_dataset_path(segmentation_entry, run_paths, config.external_roots, tokens)

    product_mix = _load_yaml(product_mix_path)
    account_per_party = _load_yaml(account_per_party_path)
    account_taxonomy = _load_yaml(account_taxonomy_path)
    party_taxonomy = _load_yaml(party_taxonomy_path)
    segmentation_priors = _load_yaml(segmentation_path)

    _validate_payload(
        product_mix,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(product_mix_entry.get("schema_ref") or "#/prior/product_mix_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": product_mix_entry.get("manifest_key")},
    )
    _validate_payload(
        account_per_party,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(account_per_party_entry.get("schema_ref") or "#/prior/account_per_party_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": account_per_party_entry.get("manifest_key")},
    )
    _validate_payload(
        account_taxonomy,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(account_taxonomy_entry.get("schema_ref") or "#/taxonomy/account_taxonomy_6A"),
        manifest_fingerprint,
        {"manifest_key": account_taxonomy_entry.get("manifest_key")},
    )
    _validate_payload(
        party_taxonomy,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(party_taxonomy_entry.get("schema_ref") or "#/taxonomy/party_taxonomy_6A"),
        manifest_fingerprint,
        {"manifest_key": party_taxonomy_entry.get("manifest_key")},
    )
    _validate_payload(
        segmentation_priors,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(segmentation_entry.get("schema_ref") or "#/prior/segmentation_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": segmentation_entry.get("manifest_key")},
    )

    linkage_rules = None
    if linkage_entry:
        linkage_path = _resolve_dataset_path(linkage_entry, run_paths, config.external_roots, tokens)
        if linkage_path.exists():
            linkage_rules = _load_yaml(linkage_path)
            _validate_payload(
                linkage_rules,
                schema_6a,
                schema_layer3,
                _anchor_from_ref(linkage_entry.get("schema_ref") or "#/policy/product_linkage_rules_6A"),
                manifest_fingerprint,
                {"manifest_key": linkage_entry.get("manifest_key")},
            )
        else:
            logger.warning(
                "S2: optional product_linkage_rules_6A missing at %s; using permissive defaults",
                linkage_path,
            )

    eligibility_rules = None
    if eligibility_entry:
        eligibility_path = _resolve_dataset_path(eligibility_entry, run_paths, config.external_roots, tokens)
        if eligibility_path.exists():
            eligibility_rules = _load_yaml(eligibility_path)
            _validate_payload(
                eligibility_rules,
                schema_6a,
                schema_layer3,
                _anchor_from_ref(eligibility_entry.get("schema_ref") or "#/policy/product_eligibility_config_6A"),
                manifest_fingerprint,
                {"manifest_key": eligibility_entry.get("manifest_key")},
            )
        else:
            logger.warning(
                "S2: optional product_eligibility_config_6A missing at %s; using permissive defaults",
                eligibility_path,
            )

    if linkage_rules is not None:
        logger.info("S2: product_linkage_rules_6A loaded (lean mode: no additional constraints applied)")
    if eligibility_rules is not None:
        logger.info("S2: product_eligibility_config_6A loaded (lean mode: no additional constraints applied)")

    timer.info("S2: priors and taxonomy loaded + schema-validated")

    merchant_mode = product_mix.get("merchant_mode") or {}
    if bool(merchant_mode.get("enabled")):
        _abort(
            "6A.S2.MERCHANT_MODE_UNSUPPORTED",
            "V-06",
            "merchant_mode_enabled",
            {"merchant_mode": merchant_mode},
            manifest_fingerprint,
        )

    party_entry = find_dataset_entry(dictionary_6a, "s1_party_base_6A").entry
    party_path = _resolve_dataset_path(party_entry, run_paths, config.external_roots, tokens)
    party_files = _list_parquet_files(party_path)
    party_df = pl.read_parquet(party_files).select(
        [
            "party_id",
            "party_type",
            "segment_id",
            "region_id",
            "country_iso",
            "seed",
            "manifest_fingerprint",
            "parameter_hash",
        ]
    )
    if party_df.height == 0:
        _abort(
            "6A.S2.S1_GATE_FAILED",
            "V-06",
            "party_base_empty",
            {"path": str(party_path)},
            manifest_fingerprint,
        )

    party_schema = _schema_from_pack(schema_6a, _anchor_from_ref(party_entry.get("schema_ref") or "#/s1/party_base"))
    _inline_external_refs(party_schema, schema_layer3, "schemas.layer3.yaml#")
    party_validator = Draft202012Validator(party_schema)
    _validate_sample_rows(party_df, party_validator, manifest_fingerprint, "s1_party_base_6A")

    seed_values = party_df.select(pl.col("seed").unique()).get_column("seed").to_list()
    mf_values = party_df.select(pl.col("manifest_fingerprint").unique()).get_column("manifest_fingerprint").to_list()
    ph_values = party_df.select(pl.col("parameter_hash").unique()).get_column("parameter_hash").to_list()
    if seed_values != [seed] or mf_values != [manifest_fingerprint] or ph_values != [parameter_hash]:
        _abort(
            "6A.S2.S1_GATE_FAILED",
            "V-06",
            "party_base_scope_mismatch",
            {
                "seed_values": seed_values,
                "manifest_values": mf_values,
                "parameter_values": ph_values,
            },
            manifest_fingerprint,
        )

    party_df = party_df.sort("party_id")
    party_ids = party_df.get_column("party_id").to_list()
    total_parties = len(party_ids)
    if total_parties == 0:
        _abort(
            "6A.S2.S1_GATE_FAILED",
            "V-06",
            "party_base_empty",
            {"path": str(party_path)},
            manifest_fingerprint,
        )

    max_party_id = max(party_ids)
    contiguous = max_party_id == total_parties and party_ids[0] == 1
    if not contiguous:
        logger.warning(
            "S2: party_id not contiguous; using sparse mapping (max_party_id=%d total_rows=%d)",
            max_party_id,
            total_parties,
        )
        party_country = [""] * (max_party_id + 1)
        party_region = [""] * (max_party_id + 1)
        party_type = [""] * (max_party_id + 1)
        party_segment = [""] * (max_party_id + 1)
        for row in party_df.iter_rows(named=True):
            pid = int(row.get("party_id"))
            party_country[pid] = str(row.get("country_iso"))
            party_region[pid] = str(row.get("region_id"))
            party_type[pid] = str(row.get("party_type"))
            party_segment[pid] = str(row.get("segment_id"))
    else:
        party_country = [""] + party_df.get_column("country_iso").to_list()
        party_region = [""] + party_df.get_column("region_id").to_list()
        party_type = [""] + party_df.get_column("party_type").to_list()
        party_segment = [""] + party_df.get_column("segment_id").to_list()

    country_to_party_ids: dict[str, list[int]] = {}
    cell_parties: dict[tuple[str, str, str], list[int]] = {}
    for pid in range(1, max_party_id + 1):
        country = party_country[pid]
        if not country:
            continue
        country_to_party_ids.setdefault(country, []).append(pid)
        cell_key = (party_region[pid], party_type[pid], party_segment[pid])
        cell_parties.setdefault(cell_key, []).append(pid)

    base_cells = sorted(cell_parties.keys())
    logger.info("S2: loaded party base (total_parties=%d, base_cells=%d)", total_parties, len(base_cells))

    segment_profiles = {
        profile.get("segment_id"): profile
        for profile in segmentation_priors.get("segment_profiles", [])
        if profile.get("segment_id")
    }
    segment_tags = {
        segment.get("id"): list(segment.get("tags") or [])
        for segment in party_taxonomy.get("segments", [])
        if segment.get("id")
    }

    account_owner_kind: dict[str, str] = {}
    account_allowed_party_types: dict[str, set[str]] = {}
    for account in account_taxonomy.get("account_types", []):
        account_id = account.get("id")
        if not account_id:
            continue
        owner_kind = str(account.get("owner_kind") or "")
        account_owner_kind[account_id] = owner_kind
        allowed_types = set(account.get("allowed_party_types") or [])
        account_allowed_party_types[account_id] = allowed_types

    party_account_domain = product_mix.get("party_account_domain") or {}
    domain_mode = str(party_account_domain.get("mode") or "")
    required_by_party_type = party_account_domain.get("required_account_types_by_party_type") or {}
    allowed_by_party_type = party_account_domain.get("allowed_account_types_by_party_type") or {}
    allowed_by_segment: dict[tuple[str, str], list[str]] = {}
    if domain_mode == "explicit_by_party_type_and_segment":
        for entry in party_account_domain.get("allowed_account_types_by_segment", []) or []:
            party_type_id = entry.get("party_type")
            segment_id = entry.get("segment_id")
            if not party_type_id or not segment_id:
                continue
            allowed_by_segment[(party_type_id, segment_id)] = list(entry.get("allowed_account_types") or [])
    elif domain_mode != "explicit_by_party_type":
        _abort(
            "6A.S2.PRIOR_PACK_INVALID",
            "V-07",
            "unsupported_domain_mode",
            {"mode": domain_mode},
            manifest_fingerprint,
        )

    lambda_model = product_mix.get("party_lambda_model") or {}
    base_lambda_by_party_type = lambda_model.get("base_lambda_by_party_type") or {}
    segment_tilt = lambda_model.get("segment_tilt") or {}
    segment_features = list(segment_tilt.get("features") or [])
    weights_by_feature = segment_tilt.get("weights_by_feature") or {}
    feature_center = float(segment_tilt.get("feature_center") or 0.5)
    clip_log_multiplier = float(segment_tilt.get("clip_log_multiplier") or 0.0)
    segment_profile_source = str(segment_tilt.get("segment_profile_source") or "")
    segment_tilt_enabled = bool(segment_features) and bool(weights_by_feature) and segment_profile_source == "prior_segmentation_6A"
    if not segment_tilt_enabled:
        logger.warning(
            "S2: segment tilt disabled (missing weights or unsupported segment_profile_source=%s); using base lambdas only",
            segment_profile_source or "unknown",
        )

    context_scaling = lambda_model.get("context_scaling") or {}
    if bool(context_scaling.get("enabled")):
        logger.warning("S2: context_scaling enabled but not implemented; using scale=1.0")

    constraints = product_mix.get("constraints") or {}
    disallow_zero_domain_cells = bool(constraints.get("disallow_zero_domain_cells", False))
    enforce_required_types = bool(constraints.get("enforce_required_types", False))
    max_total_lambda_by_type = constraints.get("max_total_lambda_per_party_by_party_type") or {}
    min_nonzero_types_by_party = constraints.get("min_nonzero_account_types_in_domain") or {}

    supported_models = {item.get("count_model_id") for item in account_per_party.get("supported_count_models", [])}
    rules_map: dict[tuple[str, str], dict] = {}
    for rule in account_per_party.get("rules", []) or []:
        party_type_id = rule.get("party_type")
        account_type_id = rule.get("account_type")
        if not party_type_id or not account_type_id:
            continue
        key = (party_type_id, account_type_id)
        if key in rules_map:
            _abort(
                "6A.S2.PRIOR_PACK_INVALID",
                "V-07",
                "duplicate_account_rule",
                {"party_type": party_type_id, "account_type": account_type_id},
                manifest_fingerprint,
            )
        count_model_id = rule.get("count_model_id")
        if count_model_id not in supported_models:
            _abort(
                "6A.S2.PRIOR_PACK_INVALID",
                "V-07",
                "unsupported_count_model",
                {"party_type": party_type_id, "account_type": account_type_id, "count_model": count_model_id},
                manifest_fingerprint,
            )
        rules_map[key] = rule

    coverage_mode = (account_per_party.get("constraints") or {}).get("coverage_mode")
    enforce_rule_coverage = coverage_mode == "fail_on_missing_rule"

    tag_adjustments_map: dict[tuple[str, str], dict] = {}
    for adjustment in account_per_party.get("tag_adjustments", []) or []:
        tag = adjustment.get("tag")
        account_type_id = adjustment.get("account_type")
        if not tag or not account_type_id:
            continue
        tag_adjustments_map[(tag, account_type_id)] = adjustment

    cell_targets: dict[tuple[str, str, str, str], float] = {}
    total_target = 0.0
    missing_profiles: set[str] = set()

    for region_id, party_type_id, segment_id in base_cells:
        parties = cell_parties.get((region_id, party_type_id, segment_id)) or []
        n_party = len(parties)
        if n_party <= 0:
            continue
        allowed = list(allowed_by_party_type.get(party_type_id) or [])
        if domain_mode == "explicit_by_party_type_and_segment":
            allowed = list(allowed_by_segment.get((party_type_id, segment_id)) or allowed)
        if disallow_zero_domain_cells and not allowed:
            _abort(
                "6A.S2.DOMAIN_INVALID",
                "V-07",
                "zero_domain_cell",
                {"region_id": region_id, "party_type": party_type_id, "segment_id": segment_id},
                manifest_fingerprint,
            )
        required_types = list(required_by_party_type.get(party_type_id) or [])
        if enforce_required_types and required_types:
            missing_required = [acct for acct in required_types if acct not in allowed]
            if missing_required:
                _abort(
                    "6A.S2.DOMAIN_INVALID",
                    "V-07",
                    "required_account_type_missing",
                    {
                        "region_id": region_id,
                        "party_type": party_type_id,
                        "segment_id": segment_id,
                        "missing": missing_required,
                    },
                    manifest_fingerprint,
                )

        total_lambda = 0.0
        nonzero_types = 0
        for account_type_id in allowed:
            owner_kind = account_owner_kind.get(account_type_id)
            if owner_kind != "PARTY":
                _abort(
                    "6A.S2.DOMAIN_INVALID",
                    "V-07",
                    "account_type_not_party_owned",
                    {"account_type": account_type_id, "owner_kind": owner_kind},
                    manifest_fingerprint,
                )
            allowed_types = account_allowed_party_types.get(account_type_id, set())
            if party_type_id not in allowed_types:
                _abort(
                    "6A.S2.DOMAIN_INVALID",
                    "V-07",
                    "account_type_not_allowed_for_party",
                    {"account_type": account_type_id, "party_type": party_type_id},
                    manifest_fingerprint,
                )
            base_lambda = base_lambda_by_party_type.get(party_type_id, {}).get(account_type_id)
            if base_lambda is None:
                _abort(
                    "6A.S2.PRIOR_PACK_INVALID",
                    "V-07",
                    "missing_base_lambda",
                    {"party_type": party_type_id, "account_type": account_type_id},
                    manifest_fingerprint,
                )
            base_lambda = float(base_lambda)
            lambda_value = base_lambda
            if segment_tilt_enabled and base_lambda > 0:
                profile = segment_profiles.get(segment_id)
                if not profile:
                    missing_profiles.add(segment_id)
                x = 0.0
                if profile:
                    for feature in segment_features:
                        weights = weights_by_feature.get(feature) or {}
                        weight = float(weights.get(account_type_id) or 0.0)
                        score = profile.get(feature)
                        if score is None:
                            score = feature_center
                        x += weight * (float(score) - feature_center)
                if clip_log_multiplier > 0:
                    x = max(-clip_log_multiplier, min(clip_log_multiplier, x))
                lambda_value = base_lambda * math.exp(x)
            if lambda_value < 0:
                lambda_value = 0.0
            if enforce_required_types and account_type_id in required_types and lambda_value <= 0:
                _abort(
                    "6A.S2.DOMAIN_INVALID",
                    "V-07",
                    "required_account_type_zero_lambda",
                    {"party_type": party_type_id, "segment_id": segment_id, "account_type": account_type_id},
                    manifest_fingerprint,
                )
            total_lambda += lambda_value
            if lambda_value > 0:
                nonzero_types += 1
                target = float(n_party) * lambda_value
                cell_targets[(region_id, party_type_id, segment_id, account_type_id)] = target
                total_target += target
            if enforce_rule_coverage and (party_type_id, account_type_id) not in rules_map:
                _abort(
                    "6A.S2.PRIOR_PACK_INVALID",
                    "V-07",
                    "account_rule_missing",
                    {"party_type": party_type_id, "account_type": account_type_id},
                    manifest_fingerprint,
                )

        max_lambda = float(max_total_lambda_by_type.get(party_type_id) or 0.0)
        if max_lambda and total_lambda > max_lambda:
            logger.warning(
                "S2: total lambda exceeds cap (party_type=%s segment_id=%s total_lambda=%.4f cap=%.4f)",
                party_type_id,
                segment_id,
                total_lambda,
                max_lambda,
            )
        min_nonzero = int(min_nonzero_types_by_party.get(party_type_id) or 0)
        if min_nonzero and nonzero_types < min_nonzero:
            logger.warning(
                "S2: nonzero account types below minimum (party_type=%s segment_id=%s nonzero=%d min=%d)",
                party_type_id,
                segment_id,
                nonzero_types,
                min_nonzero,
            )

    if missing_profiles:
        logger.warning(
            "S2: missing segment profiles for segments=%s; used base lambdas only",
            ",".join(sorted(missing_profiles)),
        )

    if total_target <= 0:
        _abort(
            "6A.S2.ACCOUNT_TARGETS_INCONSISTENT",
            "V-08",
            "account_targets_zero",
            {"total_target": total_target, "total_parties": total_parties},
            manifest_fingerprint,
        )

    total_accounts_int = int(round(total_target))
    if total_accounts_int <= 0:
        _abort(
            "6A.S2.ACCOUNT_INTEGERISATION_FAILED",
            "V-08",
            "account_integerisation_failed",
            {"total_target": total_target},
            manifest_fingerprint,
        )

    rng_count_stream = _RngStream("account_count_realisation", manifest_fingerprint, parameter_hash, int(seed))
    cell_counts, count_meta = _largest_remainder(cell_targets, total_accounts_int, rng_count_stream)
    rng_count_stream.record_event()

    total_accounts = sum(cell_counts.values())
    if total_accounts != total_accounts_int:
        logger.warning(
            "S2: total account count mismatch after integerisation (expected=%d actual=%d)",
            total_accounts_int,
            total_accounts,
        )

    rng_event_rows_count = [
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "module": "6A.S2",
            "substream_label": "account_count_realisation",
            "rng_counter_before_lo": int(count_meta.get("before_lo") or rng_count_stream.counter_lo),
            "rng_counter_before_hi": int(count_meta.get("before_hi") or rng_count_stream.counter_hi),
            "rng_counter_after_lo": int(count_meta.get("after_lo") or rng_count_stream.counter_lo),
            "rng_counter_after_hi": int(count_meta.get("after_hi") or rng_count_stream.counter_hi),
            "draws": str(count_meta.get("draws") or 0),
            "blocks": int(count_meta.get("blocks") or 0),
            "context": {
                "cells": len(cell_targets),
                "total_target": total_target,
                "total_int": total_accounts_int,
            },
        }
    ]

    account_types_in_use = sorted({key[3] for key, value in cell_counts.items() if value > 0})
    if not account_types_in_use:
        _abort(
            "6A.S2.ACCOUNT_TARGETS_INCONSISTENT",
            "V-08",
            "no_accounts_realised",
            {"total_accounts": total_accounts},
            manifest_fingerprint,
        )

    rng_alloc_stream = _RngStream("account_allocation_sampling", manifest_fingerprint, parameter_hash, int(seed))
    rng_attr_stream = _RngStream("account_attribute_sampling", manifest_fingerprint, parameter_hash, int(seed))

    allocation_cells = sorted([key for key, value in cell_counts.items() if value > 0])
    alloc_tracker = _ProgressTracker(len(allocation_cells), logger, "S2: allocate accounts to parties")

    holdings_counts: dict[str, list[int]] = {}
    holdings_rows_total = 0
    rng_event_rows_alloc: list[dict] = []

    for region_id, party_type_id, segment_id, account_type_id in allocation_cells:
        n_acc = int(cell_counts.get((region_id, party_type_id, segment_id, account_type_id), 0))
        if n_acc <= 0:
            alloc_tracker.update(1)
            continue
        parties = cell_parties.get((region_id, party_type_id, segment_id)) or []
        if not parties:
            _abort(
                "6A.S2.ALLOCATION_FAILED",
                "V-09",
                "cell_parties_missing",
                {
                    "region_id": region_id,
                    "party_type": party_type_id,
                    "segment_id": segment_id,
                    "account_type": account_type_id,
                },
                manifest_fingerprint,
            )
        rule = rules_map.get((party_type_id, account_type_id))
        if not rule:
            _abort(
                "6A.S2.PRIOR_PACK_INVALID",
                "V-09",
                "account_rule_missing",
                {"party_type": party_type_id, "account_type": account_type_id},
                manifest_fingerprint,
            )
        params = rule.get("params") or {}
        p_zero_weight = float(params.get("p_zero_weight") or 0.0)
        sigma = float(params.get("sigma") or 0.0)
        weight_floor = float(params.get("weight_floor_eps") or 1.0e-12)
        if weight_floor <= 0:
            _abort(
                "6A.S2.PRIOR_PACK_INVALID",
                "V-09",
                "invalid_weight_floor",
                {"party_type": party_type_id, "account_type": account_type_id, "weight_floor": weight_floor},
                manifest_fingerprint,
            )

        tags = segment_tags.get(segment_id) or []
        if tags:
            for tag in tags:
                adjustment = tag_adjustments_map.get((tag, account_type_id))
                if not adjustment:
                    continue
                clip = adjustment.get("multipliers_clip") or {}
                p_mult = float(adjustment.get("p_zero_weight_multiplier") or 1.0)
                s_mult = float(adjustment.get("sigma_multiplier") or 1.0)
                clip_min = float(clip.get("min") or 0.0)
                clip_max = float(clip.get("max") or 0.0)
                if clip_max:
                    p_mult = min(p_mult, clip_max)
                    s_mult = min(s_mult, clip_max)
                if clip_min:
                    p_mult = max(p_mult, clip_min)
                    s_mult = max(s_mult, clip_min)
                p_zero_weight *= p_mult
                sigma *= s_mult
        if p_zero_weight < 0.0:
            p_zero_weight = 0.0
        if p_zero_weight > 1.0:
            p_zero_weight = 1.0
        if sigma < 0.0:
            sigma = 0.0

        eligible_party_ids: list[int] = []
        weights: list[float] = []
        for pid in parties:
            u0 = _deterministic_uniform(manifest_fingerprint, parameter_hash, pid, account_type_id, "zero_gate")
            if u0 < p_zero_weight:
                continue
            u1 = _deterministic_uniform(manifest_fingerprint, parameter_hash, pid, account_type_id, "weight")
            u1 = min(max(u1, 1.0e-12), 1.0 - 1.0e-12)
            if sigma > 0:
                z = _normal_icdf(u1)
                weight = math.exp(sigma * z - 0.5 * sigma * sigma)
            else:
                weight = 1.0
            weight = max(weight_floor, weight)
            eligible_party_ids.append(pid)
            weights.append(weight)

        if not eligible_party_ids:
            _abort(
                "6A.S2.ALLOCATION_FAILED",
                "V-09",
                "allocation_weights_zero",
                {
                    "region_id": region_id,
                    "party_type": party_type_id,
                    "segment_id": segment_id,
                    "account_type": account_type_id,
                },
                manifest_fingerprint,
            )

        total_weight = sum(weights)
        if total_weight <= 0:
            _abort(
                "6A.S2.ALLOCATION_FAILED",
                "V-09",
                "allocation_weights_total_zero",
                {"account_type": account_type_id, "n_acc": n_acc},
                manifest_fingerprint,
            )

        targets = [(n_acc * weight) / total_weight for weight in weights]
        alloc_counts, alloc_meta = _largest_remainder_list(targets, n_acc, rng_alloc_stream)
        rng_alloc_stream.record_event()

        counts_array = holdings_counts.get(account_type_id)
        if counts_array is None:
            counts_array = [0] * (max_party_id + 1)
            holdings_counts[account_type_id] = counts_array

        for pid, count in zip(eligible_party_ids, alloc_counts):
            if count <= 0:
                continue
            counts_array[pid] = count
            holdings_rows_total += 1

        rng_event_rows_alloc.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S2",
                "substream_label": "account_allocation_sampling",
                "rng_counter_before_lo": int(alloc_meta.get("before_lo") or rng_alloc_stream.counter_lo),
                "rng_counter_before_hi": int(alloc_meta.get("before_hi") or rng_alloc_stream.counter_hi),
                "rng_counter_after_lo": int(alloc_meta.get("after_lo") or rng_alloc_stream.counter_lo),
                "rng_counter_after_hi": int(alloc_meta.get("after_hi") or rng_alloc_stream.counter_hi),
                "draws": str(alloc_meta.get("draws") or 0),
                "blocks": int(alloc_meta.get("blocks") or 0),
                "context": {
                    "region_id": region_id,
                    "party_type": party_type_id,
                    "segment_id": segment_id,
                    "account_type": account_type_id,
                    "party_count": len(parties),
                    "eligible_party_count": len(eligible_party_ids),
                    "n_acc": n_acc,
                },
            }
        )
        alloc_tracker.update(1)

    rng_attr_stream.record_event()
    rng_event_rows_attr = [
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "module": "6A.S2",
            "substream_label": "account_attribute_sampling",
            "rng_counter_before_lo": int(rng_attr_stream.counter_lo),
            "rng_counter_before_hi": int(rng_attr_stream.counter_hi),
            "rng_counter_after_lo": int(rng_attr_stream.counter_lo),
            "rng_counter_after_hi": int(rng_attr_stream.counter_hi),
            "draws": "0",
            "blocks": 0,
            "context": {
                "note": "account attributes not materialized in v1 schema",
                "total_accounts": total_accounts,
            },
        }
    ]

    account_entry = find_dataset_entry(dictionary_6a, "s2_account_base_6A").entry
    holdings_entry = find_dataset_entry(dictionary_6a, "s2_party_product_holdings_6A").entry
    summary_entry = find_dataset_entry(dictionary_6a, "s2_account_summary_6A").entry
    merchant_entry = find_dataset_entry(dictionary_6a, "s2_merchant_account_base_6A").entry

    account_base_path = _resolve_dataset_path(account_entry, run_paths, config.external_roots, tokens)
    holdings_path = _resolve_dataset_path(holdings_entry, run_paths, config.external_roots, tokens)
    summary_path = _resolve_dataset_path(summary_entry, run_paths, config.external_roots, tokens)

    tmp_dir = run_paths.tmp_root / f"s2_accounts_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_account = tmp_dir / account_base_path.name
    account_schema = _schema_from_pack(schema_6a, _anchor_from_ref(account_entry.get("schema_ref") or "#/s2/account_base"))
    _inline_external_refs(account_schema, schema_layer3, "schemas.layer3.yaml#")
    account_validator = Draft202012Validator(account_schema)

    account_buffer: list[tuple] = []
    account_buffer_rows = 0
    account_writer = None
    buffered_frames: list[pl.DataFrame] = []

    account_id = 1
    account_tracker = _ProgressTracker(total_accounts, logger, "S2: emit s2_account_base_6A")

    def _flush_account_buffer() -> None:
        nonlocal account_buffer_rows, account_writer
        if not account_buffer:
            return
        frame = pl.DataFrame(
            account_buffer,
            schema=[
                "account_id",
                "owner_party_id",
                "account_type",
                "party_type",
                "segment_id",
                "region_id",
                "country_iso",
                "seed",
                "manifest_fingerprint",
                "parameter_hash",
            ],
            orient="row",
        )
        _validate_sample_rows(frame, account_validator, manifest_fingerprint, "s2_account_base_6A")
        if _HAVE_PYARROW:
            table = frame.to_arrow()
            if account_writer is None:
                account_writer = pq.ParquetWriter(tmp_account, table.schema, compression="zstd")
            account_writer.write_table(table)
        else:
            buffered_frames.append(frame)
        account_buffer_rows = 0
        account_buffer.clear()

    for country in sorted(country_to_party_ids.keys()):
        party_ids = country_to_party_ids[country]
        for account_type_id in account_types_in_use:
            counts_array = holdings_counts.get(account_type_id)
            if counts_array is None:
                continue
            for pid in party_ids:
                count = counts_array[pid]
                if count <= 0:
                    continue
                ptype = party_type[pid]
                segment_id = party_segment[pid]
                region_id = party_region[pid]
                for _ in range(count):
                    account_buffer.append(
                        (
                            account_id,
                            pid,
                            account_type_id,
                            ptype,
                            segment_id,
                            region_id,
                            country,
                            int(seed),
                            manifest_fingerprint,
                            parameter_hash,
                        )
                    )
                    account_id += 1
                    account_buffer_rows += 1
                    if account_buffer_rows >= _DEFAULT_BATCH_ROWS:
                        _flush_account_buffer()
                account_tracker.update(count)

    _flush_account_buffer()
    if account_writer is not None:
        account_writer.close()
    elif buffered_frames:
        pl.concat(buffered_frames).write_parquet(tmp_account, compression="zstd")

    _publish_parquet_file_idempotent(
        tmp_account,
        account_base_path,
        logger,
        "s2_account_base_6A",
        "6A.S2.IO_WRITE_CONFLICT",
        "6A.S2.IO_WRITE_FAILED",
    )

    holdings_schema = _schema_from_pack(
        schema_6a,
        _anchor_from_ref(holdings_entry.get("schema_ref") or "#/s2/party_product_holdings"),
    )
    _inline_external_refs(holdings_schema, schema_layer3, "schemas.layer3.yaml#")
    holdings_validator = Draft202012Validator(holdings_schema)
    tmp_holdings = tmp_dir / holdings_path.name
    holdings_buffer: list[tuple] = []
    holdings_buffer_rows = 0
    holdings_writer = None
    holdings_frames: list[pl.DataFrame] = []

    holdings_tracker = _ProgressTracker(holdings_rows_total, logger, "S2: emit s2_party_product_holdings_6A")

    def _flush_holdings_buffer() -> None:
        nonlocal holdings_buffer_rows, holdings_writer
        if not holdings_buffer:
            return
        frame = pl.DataFrame(
            holdings_buffer,
            schema=["owner_party_id", "account_type", "account_count"],
            orient="row",
        )
        _validate_sample_rows(frame, holdings_validator, manifest_fingerprint, "s2_party_product_holdings_6A")
        if _HAVE_PYARROW:
            table = frame.to_arrow()
            if holdings_writer is None:
                holdings_writer = pq.ParquetWriter(tmp_holdings, table.schema, compression="zstd")
            holdings_writer.write_table(table)
        else:
            holdings_frames.append(frame)
        holdings_buffer_rows = 0
        holdings_buffer.clear()

    for pid in range(1, max_party_id + 1):
        for account_type_id in account_types_in_use:
            counts_array = holdings_counts.get(account_type_id)
            if counts_array is None:
                continue
            count = counts_array[pid]
            if count <= 0:
                continue
            holdings_buffer.append((pid, account_type_id, int(count)))
            holdings_buffer_rows += 1
            if holdings_buffer_rows >= _DEFAULT_BATCH_ROWS:
                _flush_holdings_buffer()
            holdings_tracker.update(1)

    _flush_holdings_buffer()
    if holdings_writer is not None:
        holdings_writer.close()
    elif holdings_frames:
        pl.concat(holdings_frames).write_parquet(tmp_holdings, compression="zstd")

    _publish_parquet_file_idempotent(
        tmp_holdings,
        holdings_path,
        logger,
        "s2_party_product_holdings_6A",
        "6A.S2.IO_WRITE_CONFLICT",
        "6A.S2.IO_WRITE_FAILED",
    )

    summary_counts: dict[tuple[str, str, str, str], int] = {}
    for pid in range(1, max_party_id + 1):
        country = party_country[pid]
        if not country:
            continue
        region_id = party_region[pid]
        party_type_id = party_type[pid]
        for account_type_id in account_types_in_use:
            counts_array = holdings_counts.get(account_type_id)
            if counts_array is None:
                continue
            count = counts_array[pid]
            if count <= 0:
                continue
            key = (country, region_id, party_type_id, account_type_id)
            summary_counts[key] = summary_counts.get(key, 0) + int(count)

    summary_final_path: Optional[Path] = None
    if summary_counts:
        summary_rows = [
            {
                "country_iso": key[0],
                "region_id": key[1],
                "party_type": key[2],
                "account_type": key[3],
                "account_count": int(count),
            }
            for key, count in summary_counts.items()
        ]
        summary_rows.sort(
            key=lambda row: (row["country_iso"], row["region_id"], row["party_type"], row["account_type"])
        )
        summary_frame = pl.DataFrame(summary_rows)
        tmp_summary = tmp_dir / summary_path.name
        summary_frame.write_parquet(tmp_summary, compression="zstd")
        _publish_parquet_file_idempotent(
            tmp_summary,
            summary_path,
            logger,
            "s2_account_summary_6A",
            "6A.S2.IO_WRITE_CONFLICT",
            "6A.S2.IO_WRITE_FAILED",
        )
        summary_final_path = summary_path
    else:
        logger.warning("S2: summary rows empty; skipping s2_account_summary_6A output")

    merchant_base_path = None
    if bool(merchant_entry.get("status") == "optional"):
        logger.info("S2: merchant account base not produced (merchant_mode disabled)")

    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6A.S2 account base RNG audit",
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
            trace_row = stream.trace_row(run_id_value, int(seed), "6A.S2")
            handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S2: appended rng_trace_log rows for count + allocation + attribute streams")

    rng_count_entry = find_dataset_entry(dictionary_6a, "rng_event_account_count_realisation").entry
    rng_alloc_entry = find_dataset_entry(dictionary_6a, "rng_event_account_allocation_sampling").entry
    rng_attr_entry = find_dataset_entry(dictionary_6a, "rng_event_account_attribute_sampling").entry
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
        tmp_count_path = tmp_dir / "account_count_realisation.jsonl"
        tmp_alloc_path = tmp_dir / "account_allocation_sampling.jsonl"
        tmp_attr_path = tmp_dir / "account_attribute_sampling.jsonl"

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
        "rng_event_account_count_realisation",
        "6A.S2.IO_WRITE_CONFLICT",
        "6A.S2.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_alloc_path,
        rng_alloc_path,
        logger,
        "rng_event_account_allocation_sampling",
        "6A.S2.IO_WRITE_CONFLICT",
        "6A.S2.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_attr_path,
        rng_attr_path,
        logger,
        "rng_event_account_attribute_sampling",
        "6A.S2.IO_WRITE_CONFLICT",
        "6A.S2.IO_WRITE_FAILED",
    )

    timer.info("S2: account base generation complete")
    return S2Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        account_base_path=account_base_path,
        holdings_path=holdings_path,
        summary_path=summary_final_path,
        merchant_base_path=merchant_base_path,
    )
