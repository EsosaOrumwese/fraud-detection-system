"""S1 party base runner for Segment 6A."""

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


MODULE_NAME = "6A.s1_party_base"
SEGMENT = "6A"
STATE = "S1"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_DEFAULT_BATCH_ROWS = 50_000


@dataclass(frozen=True)
class S1Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    party_base_path: Path
    party_summary_path: Optional[Path]


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
    logger = get_logger("engine.layers.l3.seg_6A.s1_party_base.runner")
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
        defs = schema.get("$defs")
        items_schema = {key: value for key, value in schema.items() if key != "$defs"}
        schema = {"type": "array", "items": items_schema}
        if defs:
            schema["$defs"] = defs
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "6A.S1.SCHEMA_INVALID",
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
        return b"\\x00" * 12 + raw
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
        logger.info("S1: published %s to %s", label, final_path)
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
        logger.info("S1: published %s to %s", label, final_path)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_path), "error": str(exc)}, None)


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


def _lognormal_multiplier(stream: _RngStream, sigma: float) -> tuple[float, dict]:
    if sigma <= 0:
        return 1.0, {
            "draws": 0,
            "blocks": 0,
            "before_hi": stream.counter_hi,
            "before_lo": stream.counter_lo,
            "after_hi": stream.counter_hi,
            "after_lo": stream.counter_lo,
        }
    values, before_hi, before_lo, after_hi, after_lo, draws, blocks = stream.draw_uniforms(2)
    u1 = max(values[0], 1e-12)
    u2 = max(values[1], 1e-12)
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    multiplier = math.exp(sigma * z - 0.5 * sigma * sigma)
    return multiplier, {
        "draws": draws,
        "blocks": blocks,
        "before_hi": before_hi,
        "before_lo": before_lo,
        "after_hi": after_hi,
        "after_lo": after_lo,
    }


def _largest_remainder(
    targets: dict[str, float],
    total: int,
    tie_stream: Optional[_RngStream] = None,
) -> tuple[dict[str, int], dict]:
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


def _region_for_country(country_iso: str, region_ids: list[str]) -> str:
    digest = hashlib.sha256(country_iso.encode("utf-8")).digest()
    idx = int.from_bytes(digest[-4:], "big", signed=False) % max(len(region_ids), 1)
    return region_ids[idx]


def _sum_by_country(paths: list[Path], column: str, logger, label: str) -> dict[str, float]:
    if not paths:
        return {}
    tracker = _ProgressTracker(len(paths), logger, label)
    totals: dict[str, float] = {}
    for path in paths:
        tracker.update(1)
        df = pl.scan_parquet(path).group_by("legal_country_iso").agg(pl.col(column).sum().alias("value"))
        values = df.collect()
        for row in values.iter_rows(named=True):
            key = str(row.get("legal_country_iso"))
            totals[key] = totals.get(key, 0.0) + float(row.get("value") or 0.0)
    return totals


def _count_by_country(paths: list[Path], logger, label: str) -> dict[str, int]:
    if not paths:
        return {}
    tracker = _ProgressTracker(len(paths), logger, label)
    totals: dict[str, int] = {}
    for path in paths:
        tracker.update(1)
        df = pl.scan_parquet(path).group_by("legal_country_iso").len()
        values = df.collect()
        for row in values.iter_rows(named=True):
            key = str(row.get("legal_country_iso"))
            totals[key] = totals.get(key, 0) + int(row.get("len") or 0)
    return totals


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l3.seg_6A.s1_party_base.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        _abort("6A.S1.IO_READ_FAILED", "V-01", "run_id_missing", {"path": str(receipt_path)}, None)

    seed = receipt.get("seed")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        _abort(
            "6A.S1.IO_READ_FAILED",
            "V-01",
            "run_receipt_missing_fields",
            {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )
    if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
        _abort(
            "6A.S1.IO_READ_FAILED",
            "V-01",
            "run_receipt_invalid_hashes",
            {"parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S1: run log initialized at {run_log_path}")
    logger.info(
        "S1: objective=build party base; gated inputs (S0 receipt + sealed inputs + priors/taxonomy) -> outputs s1_party_base_6A (+ optional summary) + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6a_path, dictionary_6a = load_dataset_dictionary(source, "6A")
    reg_6a_path, registry_6a = load_artefact_registry(source, "6A")
    schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6A", "layer3")
    timer.info(
        "S1: loaded contracts (dictionary=%s registry=%s schema_6a=%s schema_layer3=%s)",
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
            "6A.S1.S0_GATE_FAILED",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if not sealed_inputs_path.exists():
        _abort(
            "6A.S1.SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    s0_receipt = _load_json(receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "6A.S1.SEALED_INPUTS_INVALID",
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
            "6A.S1.SEALED_INPUTS_DIGEST_MISMATCH",
            "V-02",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S1: sealed_inputs digest verified")

    upstream_segments = s0_receipt.get("upstream_segments") or {}
    for required in ("1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B"):
        status = str((upstream_segments.get(required) or {}).get("status") or "")
        if status != "PASS":
            _abort(
                "6A.S1.S0_GATE_FAILED",
                "V-03",
                "upstream_gate_not_pass",
                {"segment": required, "status": status},
                manifest_fingerprint,
            )
    logger.info("S1: upstream gate PASS checks complete (segments=1A,1B,2A,2B,3A,3B,5A,5B)")

    logger.warning(
        "S1: S0 run-report check skipped (no layer-3 run-report contract); using gate receipt + sealed inputs only"
    )

    def _find_sealed_input(manifest_key: str, required: bool = True, role: Optional[str] = None) -> dict:
        matches = [row for row in sealed_inputs if row.get("manifest_key") == manifest_key]
        if role:
            matches = [row for row in matches if row.get("role") == role]
        if not matches:
            if required:
                _abort(
                    "6A.S1.SEALED_INPUTS_MISSING",
                    "V-04",
                    "sealed_input_missing",
                    {"manifest_key": manifest_key},
                    manifest_fingerprint,
                )
            return {}
        return matches[0]

    population_entry = _find_sealed_input("mlr.6A.prior.population", role="POPULATION_PRIOR")
    segmentation_entry = _find_sealed_input("mlr.6A.prior.segmentation", role="SEGMENT_PRIOR")
    taxonomy_entry = _find_sealed_input("mlr.6A.taxonomy.party", role="TAXONOMY")
    outlet_entry = _find_sealed_input("mlr.1A.output.outlet_catalogue", role="UPSTREAM_EGRESS")
    arrival_entry = _find_sealed_input("mlr.5A.model.merchant_zone_profile", role="UPSTREAM_EGRESS")

    for entry in (population_entry, segmentation_entry, taxonomy_entry, outlet_entry, arrival_entry):
        if entry.get("read_scope") != "ROW_LEVEL":
            _abort(
                "6A.S1.SEALED_INPUTS_INVALID",
                "V-05",
                "sealed_input_read_scope_invalid",
                {"manifest_key": entry.get("manifest_key"), "read_scope": entry.get("read_scope")},
                manifest_fingerprint,
            )

    population_path = _resolve_dataset_path(population_entry, run_paths, config.external_roots, tokens)
    segmentation_path = _resolve_dataset_path(segmentation_entry, run_paths, config.external_roots, tokens)
    taxonomy_path = _resolve_dataset_path(taxonomy_entry, run_paths, config.external_roots, tokens)
    outlet_path = _resolve_dataset_path(outlet_entry, run_paths, config.external_roots, tokens)
    arrivals_path = _resolve_dataset_path(arrival_entry, run_paths, config.external_roots, tokens)

    population_priors = _load_yaml(population_path)
    segmentation_priors = _load_yaml(segmentation_path)
    party_taxonomy = _load_yaml(taxonomy_path)

    _validate_payload(
        population_priors,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(population_entry.get("schema_ref") or "#/prior/population_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": population_entry.get("manifest_key")},
    )
    _validate_payload(
        segmentation_priors,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(segmentation_entry.get("schema_ref") or "#/prior/segmentation_priors_6A"),
        manifest_fingerprint,
        {"manifest_key": segmentation_entry.get("manifest_key")},
    )
    _validate_payload(
        party_taxonomy,
        schema_6a,
        schema_layer3,
        _anchor_from_ref(taxonomy_entry.get("schema_ref") or "#/taxonomy/party_taxonomy_6A"),
        manifest_fingerprint,
        {"manifest_key": taxonomy_entry.get("manifest_key")},
    )
    timer.info("S1: priors and taxonomy loaded + schema-validated")

    required_hints = set((population_priors.get("inputs_allowed") or {}).get("required_hints") or [])
    if "OUTLET_COUNTS_BY_COUNTRY" in required_hints:
        logger.info("S1: required hint OUTLET_COUNTS_BY_COUNTRY satisfied via outlet_catalogue")
    if "EXPECTED_ARRIVALS_BY_COUNTRY" in required_hints:
        logger.info("S1: required hint EXPECTED_ARRIVALS_BY_COUNTRY satisfied via merchant_zone_profile_5A")

    outlet_files = _list_parquet_files(outlet_path)
    outlet_counts = _count_by_country(outlet_files, logger, "S1: count outlets by country")
    if not outlet_counts:
        _abort(
            "6A.S1.PRIOR_PACK_INVALID",
            "V-06",
            "outlet_catalogue_empty",
            {"path": str(outlet_path)},
            manifest_fingerprint,
        )

    arrival_files = _list_parquet_files(arrivals_path)
    arrival_counts = _sum_by_country(arrival_files, "weekly_volume_expected", logger, "S1: sum arrivals by country")
    total_arrivals = sum(arrival_counts.values())
    total_outlets = sum(outlet_counts.values())

    world_size_model = population_priors.get("world_size_model") or {}
    size_mode = str(world_size_model.get("mode") or "")
    active_fraction = float(world_size_model.get("active_fraction") or 0.0)
    arrivals_per_active = float(world_size_model.get("arrivals_per_active_party_per_week") or 0.0)
    parties_per_outlet = float(world_size_model.get("parties_per_outlet") or 0.0)
    n_world_min = int(world_size_model.get("N_world_min") or 0)
    n_world_max = int(world_size_model.get("N_world_max") or 0)
    sigma = float(world_size_model.get("seed_scale_lognormal_sigma") or 0.0)
    clip = world_size_model.get("seed_scale_clip") or {}

    rng_count_stream = _RngStream("party_count_realisation", manifest_fingerprint, parameter_hash, int(seed))
    rng_attr_stream = _RngStream("party_attribute_sampling", manifest_fingerprint, parameter_hash, int(seed))

    if size_mode == "arrivals_based_v1" and total_arrivals > 0 and active_fraction > 0 and arrivals_per_active > 0:
        n_world_target = total_arrivals / (arrivals_per_active * active_fraction)
    elif size_mode == "outlets_based_v1" and parties_per_outlet > 0:
        n_world_target = total_outlets * parties_per_outlet
    else:
        logger.warning(
            "S1: world_size_model fallback (mode=%s arrivals=%s outlets=%s); using outlets-based estimate",
            size_mode,
            total_arrivals,
            total_outlets,
        )
        fallback_per_outlet = float(
            (population_priors.get("realism_targets") or {}).get("parties_per_outlet_range", {}).get("min") or 50.0
        )
        n_world_target = total_outlets * fallback_per_outlet

    scale_multiplier, _scale_meta = _lognormal_multiplier(rng_count_stream, sigma)
    if scale_multiplier != 1.0:
        clip_min = float(clip.get("min") or 0.0) if clip else 0.0
        clip_max = float(clip.get("max") or 0.0) if clip else 0.0
        if clip_min and scale_multiplier < clip_min:
            scale_multiplier = clip_min
        if clip_max and scale_multiplier > clip_max:
            scale_multiplier = clip_max
        n_world_target *= scale_multiplier
    n_world_target = max(float(n_world_min), min(float(n_world_target), float(n_world_max)))

    n_world_int = int(round(n_world_target))
    if n_world_int <= 0:
        _abort(
            "6A.S1.POPULATION_INTEGERISATION_FAILED",
            "V-07",
            "world_population_zero",
            {"n_world_target": n_world_target},
            manifest_fingerprint,
        )
    if n_world_int > n_world_max:
        _abort(
            "6A.S1.POPULATION_INTEGERISATION_FAILED",
            "V-07",
            "world_population_over_max",
            {"n_world_int": n_world_int, "n_world_max": n_world_max},
            manifest_fingerprint,
        )
    logger.info(
        "S1: world population target=%s int=%s (mode=%s total_arrivals=%s total_outlets=%s)",
        n_world_target,
        n_world_int,
        size_mode,
        int(total_arrivals),
        int(total_outlets),
    )

    weight_model = population_priors.get("country_weight_model") or {}
    use_outlets = bool(weight_model.get("use_outlets", True))
    use_arrivals = bool(weight_model.get("use_arrivals", True))
    outlet_offset = float(weight_model.get("outlet_offset") or 0.0)
    outlet_exponent = float(weight_model.get("outlet_exponent") or 1.0)
    arrival_offset = float(weight_model.get("arrival_offset") or 0.0)
    arrival_exponent = float(weight_model.get("arrival_exponent") or 1.0)
    weight_floor = float(weight_model.get("country_weight_floor") or 1.0)

    countries = sorted(set(outlet_counts) | set(arrival_counts))
    weights: dict[str, float] = {}
    for country in countries:
        outlet_count = float(outlet_counts.get(country, 0))
        arrival_count = float(arrival_counts.get(country, 0))
        outlet_component = (outlet_count + outlet_offset) ** outlet_exponent if use_outlets else 1.0
        arrival_component = (arrival_count + arrival_offset) ** arrival_exponent if use_arrivals else 1.0
        weight = max(outlet_component * arrival_component, weight_floor)
        weights[country] = weight
    total_weight = sum(weights.values())
    if total_weight <= 0:
        weights = {country: 1.0 for country in countries}
        total_weight = float(len(countries))
        logger.warning("S1: country weights collapsed; using uniform weights")

    shares = {country: weights[country] / total_weight for country in countries}
    targets = {country: shares[country] * n_world_int for country in countries}
    country_counts, _ = _largest_remainder(targets, n_world_int)

    region_ids = sorted(
        {row.get("region_id") for row in segmentation_priors.get("region_party_type_mix", []) if row.get("region_id")}
    )
    if not region_ids:
        _abort(
            "6A.S1.PRIOR_PACK_INVALID",
            "V-08",
            "segmentation_regions_missing",
            {},
            manifest_fingerprint,
        )
    region_map = {country: _region_for_country(country, region_ids) for country in countries}
    region_counts: dict[str, int] = {}
    for country, region_id in region_map.items():
        region_counts[region_id] = region_counts.get(region_id, 0) + int(country_counts.get(country, 0))
    logger.info(
        "S1: region assignment via deterministic hash (regions=%s, countries=%d)",
        ",".join(region_ids),
        len(countries),
    )

    mix_by_region = {
        row.get("region_id"): row.get("pi_type")
        for row in segmentation_priors.get("region_party_type_mix", [])
    }
    segment_mix = {}
    for row in segmentation_priors.get("region_type_segment_mix", []):
        key = (row.get("region_id"), row.get("party_type"))
        segment_mix[key] = row.get("pi_segment") or []

    party_types = [row.get("id") for row in party_taxonomy.get("party_types", []) if row.get("id")]
    segments_by_type: dict[str, list[str]] = {}
    segment_to_type: dict[str, str] = {}
    for segment in party_taxonomy.get("segments", []):
        seg_id = segment.get("id")
        party_type = segment.get("party_type")
        if seg_id and party_type:
            segments_by_type.setdefault(party_type, []).append(seg_id)
            segment_to_type[seg_id] = party_type
    for party_type in segments_by_type:
        segments_by_type[party_type].sort()

    party_counts: dict[tuple[str, str, str], int] = {}
    total_parties = 0
    rng_event_rows_count: list[dict] = []
    rng_event_rows_attr: list[dict] = []

    for country in countries:
        country_total = int(country_counts.get(country, 0))
        region_id = region_map[country]
        mix = mix_by_region.get(region_id) or {}
        if not mix:
            logger.warning("S1: missing region mix for %s; using global base shares", region_id)
            mix = (population_priors.get("party_type_model") or {}).get("base_shares") or {}
        targets_type = {ptype: float(mix.get(ptype, 0.0)) * country_total for ptype in party_types}
        type_counts, type_meta = _largest_remainder(targets_type, country_total, rng_count_stream)
        rng_count_stream.record_event()
        rng_event_rows_count.append(
            {
                "ts_utc": utc_now_rfc3339_micro(),
                "run_id": run_id_value,
                "seed": int(seed),
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "module": "6A.S1",
                "substream_label": "party_count_realisation",
                "rng_counter_before_lo": int(type_meta.get("before_lo") or rng_count_stream.counter_lo),
                "rng_counter_before_hi": int(type_meta.get("before_hi") or rng_count_stream.counter_hi),
                "rng_counter_after_lo": int(type_meta.get("after_lo") or rng_count_stream.counter_lo),
                "rng_counter_after_hi": int(type_meta.get("after_hi") or rng_count_stream.counter_hi),
                "draws": str(type_meta.get("draws") or 0),
                "blocks": int(type_meta.get("blocks") or 0),
                "context": {
                    "country_iso": country,
                    "region_id": region_id,
                    "country_total": country_total,
                },
            }
        )

        for party_type, type_total in type_counts.items():
            mix_key = (region_id, party_type)
            seg_mix = segment_mix.get(mix_key) or []
            if not seg_mix:
                logger.warning(
                    "S1: missing segment mix for region=%s party_type=%s; using uniform",
                    region_id,
                    party_type,
                )
                seg_ids = segments_by_type.get(party_type, [])
                seg_mix = [{"segment_id": seg_id, "share": 1.0 / max(len(seg_ids), 1)} for seg_id in seg_ids]
            targets_seg = {item["segment_id"]: float(item.get("share") or 0.0) * type_total for item in seg_mix}
            seg_counts, seg_meta = _largest_remainder(targets_seg, type_total, rng_attr_stream)
            rng_attr_stream.record_event()
            rng_event_rows_attr.append(
                {
                    "ts_utc": utc_now_rfc3339_micro(),
                    "run_id": run_id_value,
                    "seed": int(seed),
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "module": "6A.S1",
                    "substream_label": "party_attribute_sampling",
                    "rng_counter_before_lo": int(seg_meta.get("before_lo") or rng_attr_stream.counter_lo),
                    "rng_counter_before_hi": int(seg_meta.get("before_hi") or rng_attr_stream.counter_hi),
                    "rng_counter_after_lo": int(seg_meta.get("after_lo") or rng_attr_stream.counter_lo),
                    "rng_counter_after_hi": int(seg_meta.get("after_hi") or rng_attr_stream.counter_hi),
                    "draws": str(seg_meta.get("draws") or 0),
                    "blocks": int(seg_meta.get("blocks") or 0),
                    "context": {
                        "country_iso": country,
                        "region_id": region_id,
                        "party_type": party_type,
                        "party_type_total": type_total,
                    },
                }
            )
            for seg_id, seg_total in seg_counts.items():
                party_counts[(country, party_type, seg_id)] = int(seg_total)
                total_parties += int(seg_total)

    if total_parties != n_world_int:
        logger.warning(
            "S1: total party count mismatch after integerisation (expected=%d actual=%d)",
            n_world_int,
            total_parties,
        )

    constraints = population_priors.get("constraints") or {}
    min_per_country = int(constraints.get("min_parties_per_country") or 0)
    if min_per_country:
        for country, count in country_counts.items():
            if int(count) < min_per_country:
                logger.warning(
                    "S1: min_parties_per_country unmet (country=%s count=%d min=%d)",
                    country,
                    int(count),
                    min_per_country,
                )

    base_entry = find_dataset_entry(dictionary_6a, "s1_party_base_6A").entry
    summary_entry = find_dataset_entry(dictionary_6a, "s1_party_summary_6A").entry
    base_path = _resolve_dataset_path(base_entry, run_paths, config.external_roots, tokens)
    summary_path = _resolve_dataset_path(summary_entry, run_paths, config.external_roots, tokens)

    tmp_dir = run_paths.tmp_root / f"s1_party_base_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_base = tmp_dir / base_path.name

    buffer: list[tuple[int, str, str, str, str, int, str, str]] = []
    buffer_rows = 0
    party_id = 1
    summary_counts: dict[tuple[str, str, str, str], int] = {}
    schema_anchor = _anchor_from_ref(base_entry.get("schema_ref") or "#/s1/party_base")
    row_schema = _schema_from_pack(schema_6a, schema_anchor)
    _inline_external_refs(row_schema, schema_layer3, "schemas.layer3.yaml#")
    validator = Draft202012Validator(row_schema)

    tracker = _ProgressTracker(total_parties, logger, "S1: generate parties")
    writer = None
    buffered_frames: list[pl.DataFrame] = []

    def _flush_buffer() -> None:
        nonlocal buffer_rows, writer
        if not buffer:
            return
        frame = pl.DataFrame(
            buffer,
            schema=[
                "party_id",
                "party_type",
                "segment_id",
                "region_id",
                "country_iso",
                "seed",
                "manifest_fingerprint",
                "parameter_hash",
            ],
        )
        sample_errors = []
        for row in frame.head(500).iter_rows(named=True):
            for error in validator.iter_errors(row):
                sample_errors.append(error)
                break
            if sample_errors:
                break
        if sample_errors:
            _abort(
                "6A.S1.SCHEMA_INVALID",
                "V-09",
                "output_schema_invalid",
                {"detail": str(sample_errors[0])},
                manifest_fingerprint,
            )
        if _HAVE_PYARROW:
            table = frame.to_arrow()
            if writer is None:
                writer = pq.ParquetWriter(tmp_base, table.schema, compression="zstd")
            writer.write_table(table)
        else:
            buffered_frames.append(frame)
        buffer_rows = 0
        buffer.clear()

    segment_order = sorted(segment_to_type.items())

    for country in sorted(countries):
        region_id = region_map[country]
        for seg_id, party_type in segment_order:
            count = party_counts.get((country, party_type, seg_id), 0)
            if count <= 0:
                continue
            for _ in range(count):
                buffer.append(
                    (
                        party_id,
                        party_type,
                        seg_id,
                        region_id,
                        country,
                        int(seed),
                        manifest_fingerprint,
                        parameter_hash,
                    )
                )
                party_id += 1
                buffer_rows += 1
                summary_key = (country, region_id, party_type, seg_id)
                summary_counts[summary_key] = summary_counts.get(summary_key, 0) + 1
                if buffer_rows >= _DEFAULT_BATCH_ROWS:
                    _flush_buffer()
                tracker.update(1)

    _flush_buffer()
    if writer is not None:
        writer.close()
    elif buffered_frames:
        pl.concat(buffered_frames).write_parquet(tmp_base, compression="zstd")

    _publish_parquet_file_idempotent(
        tmp_base,
        base_path,
        logger,
        "s1_party_base_6A",
        "6A.S1.IO_WRITE_CONFLICT",
        "6A.S1.IO_WRITE_FAILED",
    )

    summary_tmp = tmp_dir / summary_path.name
    summary_rows = [
        {
            "country_iso": key[0],
            "region_id": key[1],
            "party_type": key[2],
            "segment_id": key[3],
            "party_count": int(count),
        }
        for key, count in summary_counts.items()
    ]
    if summary_rows:
        summary_rows.sort(key=lambda row: (row["country_iso"], row["segment_id"], row["party_type"]))
        summary_frame = pl.DataFrame(summary_rows)
        summary_frame.write_parquet(summary_tmp, compression="zstd")
        _publish_parquet_file_idempotent(
            summary_tmp,
            summary_path,
            logger,
            "s1_party_summary_6A",
            "6A.S1.IO_WRITE_CONFLICT",
            "6A.S1.IO_WRITE_FAILED",
        )
    else:
        summary_path = None
        logger.warning("S1: summary rows empty; skipping s1_party_summary_6A output")

    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6A.S1 party base RNG audit",
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
        for stream in (rng_count_stream, rng_attr_stream):
            trace_row = stream.trace_row(run_id_value, int(seed), "6A.S1")
            handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S1: appended rng_trace_log rows for count + attribute streams")

    rng_event_count_entry = find_dataset_entry(dictionary_6a, "rng_event_party_count_realisation").entry
    rng_event_attr_entry = find_dataset_entry(dictionary_6a, "rng_event_party_attribute_sampling").entry
    rng_count_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_event_count_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )
    rng_attr_path = _materialize_jsonl_path(
        _resolve_dataset_path(rng_event_attr_entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
    )

    tmp_count_path = tmp_dir / rng_count_path.name
    tmp_attr_path = tmp_dir / rng_attr_path.name
    if tmp_count_path == tmp_attr_path:
        tmp_count_path = tmp_dir / "party_count_realisation.jsonl"
        tmp_attr_path = tmp_dir / "party_attribute_sampling.jsonl"
    tmp_count_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rng_event_rows_count) + "\n",
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
        "rng_event_party_count_realisation",
        "6A.S1.IO_WRITE_CONFLICT",
        "6A.S1.IO_WRITE_FAILED",
    )
    _publish_jsonl_file_idempotent(
        tmp_attr_path,
        rng_attr_path,
        logger,
        "rng_event_party_attribute_sampling",
        "6A.S1.IO_WRITE_CONFLICT",
        "6A.S1.IO_WRITE_FAILED",
    )

    timer.info("S1: party base generation complete")
    return S1Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        party_base_path=base_path,
        party_summary_path=summary_path,
    )
