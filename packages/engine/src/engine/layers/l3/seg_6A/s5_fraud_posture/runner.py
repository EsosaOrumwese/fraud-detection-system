"""S5 fraud posture + validation bundle runner for Segment 6A (lean path)."""

from __future__ import annotations

import hashlib
import json
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
from engine.contracts.loader import find_dataset_entry, load_artefact_registry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, HashingError, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt
from engine.layers.l3.seg_6A.perf import (
    Segment6APerfRecorder,
    write_segment6a_perf_summary_and_budget,
)


MODULE_NAME = "6A.s5_fraud_posture"
SEGMENT = "6A"
STATE = "S5"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_HASH_SEED = 0x6A5F001
_DEFAULT_PARTY_RISKY_ROLES = {"SYNTHETIC_ID", "MULE", "ASSOCIATE", "ORGANISER"}


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    party_roles_path: Path
    account_roles_path: Path
    merchant_roles_path: Path
    device_roles_path: Path
    ip_roles_path: Path
    validation_report_path: Path
    issue_table_path: Path
    bundle_index_path: Path
    passed_flag_path: Optional[Path]


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
    logger = get_logger("engine.layers.l3.seg_6A.s5_fraud_posture.runner")
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


def _resolve_sealed_input_path(
    row: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> Path:
    entry = {"path_template": row.get("path_template")}
    return _resolve_dataset_path(entry, run_paths, external_roots, tokens)


def _materialize_jsonl_path(path: Path) -> Path:
    if "*" in path.name or "?" in path.name:
        return path.with_name("part-00000.jsonl")
    if path.is_dir():
        return path / "part-00000.jsonl"
    return path


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
    schema = _schema_from_pack(schema_pack, f"#/{schema_anchor}")
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
            "6A.S5.SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "context": context, "manifest_fingerprint": manifest_fingerprint},
        )


def _sanitize_upstream_segments(upstream_segments: dict, manifest_fingerprint: str) -> dict:
    sanitized = {}
    for segment_id, payload in (upstream_segments or {}).items():
        if not isinstance(payload, dict):
            _abort(
                "6A.S5.UPSTREAM_RECEIPT_INVALID",
                "V-04",
                "upstream_segment_payload_invalid",
                {"segment_id": segment_id, "payload_type": type(payload).__name__},
                manifest_fingerprint,
            )
        status = payload.get("status")
        bundle_sha256 = payload.get("bundle_sha256")
        flag_path = payload.get("flag_path")
        if not isinstance(status, str) or not isinstance(bundle_sha256, str) or not isinstance(flag_path, str):
            _abort(
                "6A.S5.UPSTREAM_RECEIPT_INVALID",
                "V-04",
                "upstream_segment_fields_missing",
                {
                    "segment_id": segment_id,
                    "status": status,
                    "bundle_sha256": bundle_sha256,
                    "flag_path": flag_path,
                },
                manifest_fingerprint,
            )
        sanitized[str(segment_id)] = {
            "status": status,
            "bundle_sha256": bundle_sha256,
            "flag_path": flag_path,
        }
    return sanitized

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
                    logger.info("S5: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S5: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S5: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


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
        logger.info("S5: published %s to %s", label, final_path)
    except Exception as exc:
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_path), "error": str(exc)}, None)


def _publish_json_file_idempotent(
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
        logger.info("S5: published %s to %s", label, final_path)
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
        logger.info("S5: published %s to %s", label, final_path)
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
            "6A.S5.SCHEMA_INVALID",
            "V-09",
            "output_schema_invalid",
            {"detail": str(sample_errors[0]), "dataset": label},
            manifest_fingerprint,
        )


def _reuse_existing_parquet(
    path: Path,
    validator: Draft202012Validator,
    logger,
    manifest_fingerprint: str,
    label: str,
) -> bool:
    if not path.exists():
        return False
    logger.info("S5: reusing existing %s at %s", label, path)
    _validate_sample_rows(pl.read_parquet(path, n_rows=500), validator, manifest_fingerprint, label)
    return True


def _bundle_digest_for_members(bundle_root: Path, members: list[dict]) -> str:
    hasher = hashlib.sha256()
    for member in members:
        rel_path = str(member.get("path") or "")
        if not rel_path:
            raise HashingError("Bundle member missing path.")
        file_path = bundle_root / rel_path
        if not file_path.exists():
            raise HashingError(f"Bundle member missing file: {file_path}")
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def _existing_bundle_identical(
    validation_root: Path,
    report_path: Path,
    issues_path: Path,
    index_path: Path,
    flag_path: Path,
    tmp_bundle_root: Path,
    report_rel: Path,
    issues_rel: Path,
    index_rel: Path,
    flag_payload: str | None,
    expected_digest: str,
    logger,
    manifest_fingerprint: str,
) -> bool:
    if not index_path.exists():
        return False
    try:
        existing_index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _abort(
            "6A.S5.IO_WRITE_CONFLICT",
            "V-01",
            "validation_bundle_index_read_failed",
            {"path": str(index_path), "error": str(exc)},
            manifest_fingerprint,
        )
    existing_entries = existing_index.get("items") or []
    existing_digest = _bundle_digest_for_members(validation_root, existing_entries)
    if existing_digest != expected_digest:
        _abort(
            "6A.S5.IO_WRITE_CONFLICT",
            "V-01",
            "validation_bundle_digest_mismatch",
            {"expected": expected_digest, "actual": existing_digest},
            manifest_fingerprint,
        )
    if report_path.read_bytes() != (tmp_bundle_root / report_rel).read_bytes():
        _abort(
            "6A.S5.IO_WRITE_CONFLICT",
            "V-01",
            "validation_report_mismatch",
            {"path": str(report_path)},
            manifest_fingerprint,
        )
    if issues_path.read_bytes() != (tmp_bundle_root / issues_rel).read_bytes():
        _abort(
            "6A.S5.IO_WRITE_CONFLICT",
            "V-01",
            "validation_issue_table_mismatch",
            {"path": str(issues_path)},
            manifest_fingerprint,
        )
    if index_path.read_bytes() != (tmp_bundle_root / index_rel).read_bytes():
        _abort(
            "6A.S5.IO_WRITE_CONFLICT",
            "V-01",
            "validation_index_mismatch",
            {"path": str(index_path)},
            manifest_fingerprint,
        )
    if flag_payload is None:
        if flag_path.exists():
            _abort(
                "6A.S5.IO_WRITE_CONFLICT",
                "V-01",
                "validation_flag_unexpected",
                {"path": str(flag_path)},
                manifest_fingerprint,
            )
    else:
        if not flag_path.exists():
            _abort(
                "6A.S5.IO_WRITE_CONFLICT",
                "V-01",
                "validation_flag_missing",
                {"path": str(flag_path)},
                manifest_fingerprint,
            )
        existing_flag = flag_path.read_text(encoding="ascii").strip()
        if existing_flag != flag_payload:
            _abort(
                "6A.S5.IO_WRITE_CONFLICT",
                "V-01",
                "validation_flag_mismatch",
                {"expected": flag_payload, "actual": existing_flag},
                manifest_fingerprint,
            )
    logger.info("S5: validation bundle already exists and is identical; skipping publish.")
    return True


def _hash_to_unit(exprs: list[pl.Expr], seed: int) -> pl.Expr:
    if not exprs:
        return pl.lit(0.0)
    named = [expr.alias(f"h{idx}") for idx, expr in enumerate(exprs)]
    return pl.struct(named).hash(seed=seed).cast(pl.UInt64) / pl.lit(float(1 << 64))


def _derive_stream_seed(
    base_seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    label: str,
    salt: int,
) -> int:
    material = f"{int(base_seed)}|{manifest_fingerprint}|{parameter_hash}|{label}|{int(salt)}".encode("ascii")
    digest = hashlib.blake2b(material, digest_size=8).digest()
    return int.from_bytes(digest, "little", signed=False)


def _hash_id_to_unit(id_expr: pl.Expr, seed: int) -> pl.Expr:
    return id_expr.cast(pl.UInt64, strict=False).fill_null(0).hash(seed=seed).cast(pl.UInt64) / pl.lit(float(1 << 64))


def _normalize_prob_rows(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    total = 0.0
    for row in rows:
        try:
            prob = float(row.get("prob", 0.0))
        except (TypeError, ValueError):
            prob = 0.0
        normalized.append({"role_id": row.get("role_id"), "prob": prob})
        total += prob
    if total <= 0.0:
        return []
    if abs(total - 1.0) > 1e-6:
        for row in normalized:
            row["prob"] = row["prob"] / total
    return normalized


def _role_choice_expr(prob_rows: list[dict], u_expr: pl.Expr, default_role: str) -> pl.Expr:
    rows = _normalize_prob_rows(prob_rows)
    if not rows:
        return pl.lit(default_role)
    expr = None
    cumulative = 0.0
    for row in rows:
        prob = float(row.get("prob", 0.0))
        role = str(row.get("role_id") or default_role)
        cumulative += prob
        condition = u_expr <= pl.lit(cumulative)
        if expr is None:
            expr = pl.when(condition).then(pl.lit(role))
        else:
            expr = expr.when(condition).then(pl.lit(role))
    if expr is None:
        return pl.lit(default_role)
    return expr.otherwise(pl.lit(default_role))


def _risk_tier_expr(thresholds: dict, u_expr: pl.Expr) -> pl.Expr:
    low_max = float(thresholds.get("LOW_max", 0.25))
    standard_max = float(thresholds.get("STANDARD_max", 0.65))
    elevated_max = float(thresholds.get("ELEVATED_max", 0.85))
    return (
        pl.when(u_expr <= pl.lit(low_max))
        .then(pl.lit("LOW"))
        .when(u_expr <= pl.lit(standard_max))
        .then(pl.lit("STANDARD"))
        .when(u_expr <= pl.lit(elevated_max))
        .then(pl.lit("ELEVATED"))
        .otherwise(pl.lit("HIGH"))
    )


def _clamp01(value: object, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _tier_probability_expr(promotion_by_tier: dict[str, object], tier_expr: pl.Expr, default_prob: float) -> pl.Expr:
    expr = None
    for tier_id in ("LOW", "STANDARD", "ELEVATED", "HIGH"):
        prob = _clamp01(promotion_by_tier.get(tier_id), default_prob)
        condition = tier_expr == pl.lit(tier_id)
        if expr is None:
            expr = pl.when(condition).then(pl.lit(prob))
        else:
            expr = expr.when(condition).then(pl.lit(prob))
    if expr is None:
        return pl.lit(_clamp01(default_prob))
    return expr.otherwise(pl.lit(_clamp01(default_prob)))


def _promote_tier_one_step_expr(tier_expr: pl.Expr) -> pl.Expr:
    return (
        pl.when(tier_expr == pl.lit("LOW"))
        .then(pl.lit("STANDARD"))
        .when(tier_expr == pl.lit("STANDARD"))
        .then(pl.lit("ELEVATED"))
        .when(tier_expr == pl.lit("ELEVATED"))
        .then(pl.lit("HIGH"))
        .otherwise(pl.lit("HIGH"))
    )


def _conditional_tier_promotion_expr(
    base_tier_expr: pl.Expr,
    trigger_expr: pl.Expr,
    u_expr: pl.Expr,
    promotion_by_tier: dict[str, object],
    default_prob: float = 0.0,
) -> pl.Expr:
    promote_prob = _tier_probability_expr(promotion_by_tier, base_tier_expr, default_prob)
    promoted_tier = _promote_tier_one_step_expr(base_tier_expr)
    trigger = trigger_expr.cast(pl.Int8, strict=False).fill_null(0) > pl.lit(0)
    promote = trigger & (u_expr <= promote_prob)
    return pl.when(promote).then(promoted_tier).otherwise(base_tier_expr)


def _build_role_expr(
    mapping: dict,
    group_expr: pl.Expr,
    tier_expr: pl.Expr,
    u_expr: pl.Expr,
    default_role: str,
) -> pl.Expr:
    expr = None
    for group_id, tier_map in mapping.items():
        if not isinstance(tier_map, dict):
            continue
        for tier_id, rows in tier_map.items():
            role_expr = _role_choice_expr(rows or [], u_expr, default_role)
            condition = (group_expr == pl.lit(group_id)) & (tier_expr == pl.lit(tier_id))
            if expr is None:
                expr = pl.when(condition).then(role_expr)
            else:
                expr = expr.when(condition).then(role_expr)
    if expr is None:
        return pl.lit(default_role)
    return expr.otherwise(pl.lit(default_role))


def _map_group_expr(column: str, mapping: dict[str, str], default_group: str) -> pl.Expr:
    if not mapping:
        return pl.lit(default_group)
    return pl.col(column).replace_strict(mapping, default=default_group)


def _map_role_to_taxonomy_expr(role_expr: pl.Expr, mapping: dict[str, str], default_role: str) -> pl.Expr:
    if not mapping:
        return pl.lit(default_role)
    return role_expr.replace_strict(mapping, default=default_role)


def _collect_role_model_roles(mapping: dict) -> set[str]:
    out: set[str] = set()
    for _, tier_map in (mapping or {}).items():
        if not isinstance(tier_map, dict):
            continue
        for _, rows in tier_map.items():
            for row in rows or []:
                role_id = str(row.get("role_id") or "").strip()
                if role_id:
                    out.add(role_id)
    return out


def _write_json(path: Path, payload: dict) -> None:
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(path)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _select_dataset_path(
    dictionary: dict,
    dataset_id: str,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> Path:
    entry = find_dataset_entry(dictionary, dataset_id).entry
    return _resolve_dataset_path(entry, run_paths, external_roots, tokens)

def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l3.seg_6A.s5_fraud_posture.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = receipt.get("run_id")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    parameter_hash = receipt.get("parameter_hash")
    seed = receipt.get("seed")

    if not run_id_value or not manifest_fingerprint or not parameter_hash:
        raise InputResolutionError(f"Invalid run_receipt at {receipt_path}")
    if not _HEX64_PATTERN.match(str(manifest_fingerprint)):
        raise InputResolutionError("run_receipt manifest_fingerprint is invalid.")
    if not _HEX64_PATTERN.match(str(parameter_hash)):
        raise InputResolutionError("run_receipt parameter_hash is invalid.")
    if seed is None:
        raise InputResolutionError("run_receipt seed is missing.")

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info("S5: run log initialized at %s", run_log_path)
    logger.info(
        "S5: objective=assign fraud roles + emit validation bundle; gated inputs (S0 receipt + sealed inputs + S1-S4 bases + priors/taxonomy/policy) -> outputs s5_*_fraud_roles_6A + validation_bundle_6A/_passed.flag"
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
        "S5: loaded contracts (dictionary=%s registry=%s schema_6a=%s schema_layer3=%s)",
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

    s0_receipt_path = _select_dataset_path(dictionary_6a, "s0_gate_receipt_6A", run_paths, config.external_roots, tokens)
    if not s0_receipt_path.exists():
        _abort(
            "6A.S5.S0_GATE_MISSING",
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
        "gate/6A/s0_gate_receipt_6A",
        manifest_fingerprint,
        {"path": str(s0_receipt_path)},
    )

    sealed_inputs_path = _select_dataset_path(dictionary_6a, "sealed_inputs_6A", run_paths, config.external_roots, tokens)
    if not sealed_inputs_path.exists():
        _abort(
            "6A.S5.SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "6A.S5.SEALED_INPUTS_INVALID",
            "V-01",
            "sealed_inputs_not_list",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )
    _validate_payload(
        sealed_inputs,
        schema_layer3,
        schema_layer3,
        "gate/6A/sealed_inputs_6A",
        manifest_fingerprint,
        {"path": str(sealed_inputs_path)},
    )
    sealed_digest = _sealed_inputs_digest(sealed_inputs)
    receipt_digest = s0_receipt.get("sealed_inputs_digest_6A")
    if sealed_digest != receipt_digest:
        _abort(
            "6A.S5.SEALED_INPUTS_DIGEST_MISMATCH",
            "V-01",
            "sealed_inputs_digest_mismatch",
            {"sealed_inputs_digest": sealed_digest, "receipt_digest": receipt_digest},
            manifest_fingerprint,
        )
    timer.info("S5: sealed_inputs digest verified (%s)", sealed_digest)

    def _find_manifest_row(key: str) -> dict:
        for row in sealed_inputs:
            if row.get("manifest_key") == key:
                return row
        _abort(
            "6A.S5.REQUIRED_INPUT_MISSING",
            "V-01",
            "sealed_input_missing",
            {"manifest_key": key},
            manifest_fingerprint,
        )
        return {}

    party_prior_row = _find_manifest_row("mlr.6A.s5.prior.party_roles")
    account_prior_row = _find_manifest_row("mlr.6A.s5.prior.account_roles")
    merchant_prior_row = _find_manifest_row("mlr.6A.s5.prior.merchant_roles")
    device_prior_row = _find_manifest_row("mlr.6A.s5.prior.device_roles")
    ip_prior_row = _find_manifest_row("mlr.6A.s5.prior.ip_roles")
    taxonomy_row = _find_manifest_row("mlr.6A.taxonomy.fraud_roles")
    policy_row = _find_manifest_row("mlr.6A.policy.validation_policy")
    linkage_row = _find_manifest_row("mlr.6A.policy.graph_linkage_rules")

    party_prior_path = _resolve_sealed_input_path(party_prior_row, run_paths, config.external_roots, tokens)
    account_prior_path = _resolve_sealed_input_path(account_prior_row, run_paths, config.external_roots, tokens)
    merchant_prior_path = _resolve_sealed_input_path(merchant_prior_row, run_paths, config.external_roots, tokens)
    device_prior_path = _resolve_sealed_input_path(device_prior_row, run_paths, config.external_roots, tokens)
    ip_prior_path = _resolve_sealed_input_path(ip_prior_row, run_paths, config.external_roots, tokens)
    taxonomy_path = _resolve_sealed_input_path(taxonomy_row, run_paths, config.external_roots, tokens)
    policy_path = _resolve_sealed_input_path(policy_row, run_paths, config.external_roots, tokens)
    linkage_path = _resolve_sealed_input_path(linkage_row, run_paths, config.external_roots, tokens)

    party_prior = _load_yaml(party_prior_path)
    account_prior = _load_yaml(account_prior_path)
    merchant_prior = _load_yaml(merchant_prior_path)
    device_prior = _load_yaml(device_prior_path)
    ip_prior = _load_yaml(ip_prior_path)
    taxonomy = _load_yaml(taxonomy_path)
    validation_policy = _load_yaml(policy_path)
    linkage_rules = _load_yaml(linkage_path)

    _validate_payload(
        party_prior,
        schema_6a,
        schema_layer3,
        "prior/party_role_priors_6A",
        manifest_fingerprint,
        {"path": str(party_prior_path)},
    )
    _validate_payload(
        account_prior,
        schema_6a,
        schema_layer3,
        "prior/account_role_priors_6A",
        manifest_fingerprint,
        {"path": str(account_prior_path)},
    )
    _validate_payload(
        merchant_prior,
        schema_6a,
        schema_layer3,
        "prior/merchant_role_priors_6A",
        manifest_fingerprint,
        {"path": str(merchant_prior_path)},
    )
    _validate_payload(
        device_prior,
        schema_6a,
        schema_layer3,
        "prior/device_role_priors_6A",
        manifest_fingerprint,
        {"path": str(device_prior_path)},
    )
    _validate_payload(
        ip_prior,
        schema_6a,
        schema_layer3,
        "prior/ip_role_priors_6A",
        manifest_fingerprint,
        {"path": str(ip_prior_path)},
    )
    _validate_payload(
        taxonomy,
        schema_6a,
        schema_layer3,
        "taxonomy/fraud_role_taxonomy_6A",
        manifest_fingerprint,
        {"path": str(taxonomy_path)},
    )
    _validate_payload(
        validation_policy,
        schema_6a,
        schema_layer3,
        "policy/validation_policy_6A",
        manifest_fingerprint,
        {"path": str(policy_path)},
    )
    _validate_payload(
        linkage_rules,
        schema_6a,
        schema_layer3,
        "policy/graph_linkage_rules_6A",
        manifest_fingerprint,
        {"path": str(linkage_path)},
    )
    timer.info("S5: priors/taxonomy/policy loaded and schema-validated")
    party_schema = _schema_from_pack(schema_6a, "#/s5/party_fraud_roles")
    account_schema = _schema_from_pack(schema_6a, "#/s5/account_fraud_roles")
    merchant_schema = _schema_from_pack(schema_6a, "#/s5/merchant_fraud_roles")
    device_schema = _schema_from_pack(schema_6a, "#/s5/device_fraud_roles")
    ip_schema = _schema_from_pack(schema_6a, "#/s5/ip_fraud_roles")
    party_validator = Draft202012Validator(party_schema)
    account_validator = Draft202012Validator(account_schema)
    merchant_validator = Draft202012Validator(merchant_schema)
    device_validator = Draft202012Validator(device_schema)
    ip_validator = Draft202012Validator(ip_schema)

    required_layers = validation_policy.get("require_upstream_pass", {})
    required_segments = []
    required_segments.extend(required_layers.get("layer1_required", []) or [])
    required_segments.extend(required_layers.get("layer2_required", []) or [])
    required_segments.extend(required_layers.get("layer3_required", []) or [])
    upstream_segments = s0_receipt.get("upstream_segments", {})
    missing_upstream = []
    for segment in required_segments:
        status = (upstream_segments.get(segment) or {}).get("status")
        if status != "PASS":
            missing_upstream.append(segment)
    if missing_upstream:
        _abort(
            "6A.S5.UPSTREAM_GATE_FAILED",
            "V-02",
            "upstream_segment_not_pass",
            {"missing": missing_upstream},
            manifest_fingerprint,
        )
    logger.info(
        "S5: upstream PASS verified for segments=%s (policy require_upstream_pass)",
        required_segments,
    )
    upstream_segments_report = _sanitize_upstream_segments(upstream_segments, manifest_fingerprint)

    party_base_path = _select_dataset_path(dictionary_6a, "s1_party_base_6A", run_paths, config.external_roots, tokens)
    account_base_path = _select_dataset_path(dictionary_6a, "s2_account_base_6A", run_paths, config.external_roots, tokens)
    merchant_account_base_path = _select_dataset_path(
        dictionary_6a, "s2_merchant_account_base_6A", run_paths, config.external_roots, tokens
    )
    instrument_base_path = _select_dataset_path(
        dictionary_6a, "s3_instrument_base_6A", run_paths, config.external_roots, tokens
    )
    instrument_links_path = _select_dataset_path(
        dictionary_6a, "s3_account_instrument_links_6A", run_paths, config.external_roots, tokens
    )
    device_base_path = _select_dataset_path(dictionary_6a, "s4_device_base_6A", run_paths, config.external_roots, tokens)
    ip_base_path = _select_dataset_path(dictionary_6a, "s4_ip_base_6A", run_paths, config.external_roots, tokens)
    device_links_path = _select_dataset_path(
        dictionary_6a, "s4_device_links_6A", run_paths, config.external_roots, tokens
    )
    ip_links_path = _select_dataset_path(dictionary_6a, "s4_ip_links_6A", run_paths, config.external_roots, tokens)
    outlet_catalogue_path = _select_dataset_path(
        dictionary_6a, "outlet_catalogue", run_paths, config.external_roots, tokens
    )

    required_paths = [
        party_base_path,
        account_base_path,
        instrument_base_path,
        instrument_links_path,
        device_base_path,
        ip_base_path,
        device_links_path,
        ip_links_path,
    ]
    for req_path in required_paths:
        if not req_path.exists():
            _abort(
                "6A.S5.REQUIRED_INPUT_MISSING",
                "V-03",
                "required_input_missing",
                {"path": str(req_path)},
                manifest_fingerprint,
            )
    timer.info("S5: required S1-S4 inputs confirmed on disk")
    perf.record_elapsed("load_contracts_inputs", step_started)

    role_mapping_contract = validation_policy.get("role_mapping_contract", {}) or {}
    require_full_role_mapping = bool(role_mapping_contract.get("require_full_mapping", True))
    device_taxonomy_map_cfg = (role_mapping_contract.get("device_raw_to_taxonomy") or {}) if role_mapping_contract else {}
    ip_taxonomy_map_cfg = (role_mapping_contract.get("ip_raw_to_taxonomy") or {}) if role_mapping_contract else {}
    default_device_taxonomy_map = {
        "NORMAL_DEVICE": "CLEAN_DEVICE",
        "RISKY_DEVICE": "HIGH_RISK_DEVICE",
        "BOT_LIKE_DEVICE": "HIGH_RISK_DEVICE",
        "SHARED_SUSPICIOUS_DEVICE": "REUSED_DEVICE",
    }
    default_ip_taxonomy_map = {
        "NORMAL_IP": "CLEAN_IP",
        "CORPORATE_NAT_IP": "SHARED_IP",
        "MOBILE_CARRIER_IP": "SHARED_IP",
        "PUBLIC_SHARED_IP": "SHARED_IP",
        "DATACENTRE_IP": "HIGH_RISK_IP",
        "PROXY_IP": "HIGH_RISK_IP",
        "HIGH_RISK_IP": "HIGH_RISK_IP",
    }
    device_taxonomy_map = {
        str(k): str(v)
        for k, v in (device_taxonomy_map_cfg.items() if device_taxonomy_map_cfg else default_device_taxonomy_map.items())
    }
    ip_taxonomy_map = {
        str(k): str(v)
        for k, v in (ip_taxonomy_map_cfg.items() if ip_taxonomy_map_cfg else default_ip_taxonomy_map.items())
    }
    device_role_model_full = (device_prior.get("role_probability_model") or {}).get("pi_role_by_group_and_tier", {})
    ip_role_model_full = (ip_prior.get("role_probability_model") or {}).get("pi_role_by_group_and_tier", {})
    if require_full_role_mapping:
        missing_device = sorted(_collect_role_model_roles(device_role_model_full) - set(device_taxonomy_map.keys()))
        if missing_device:
            _abort(
                "6A.S5.ROLE_MAPPING_INCOMPLETE",
                "V-33",
                "device_role_mapping_incomplete",
                {"missing_raw_roles": missing_device},
                manifest_fingerprint,
            )
        missing_ip = sorted(_collect_role_model_roles(ip_role_model_full) - set(ip_taxonomy_map.keys()))
        if missing_ip:
            _abort(
                "6A.S5.ROLE_MAPPING_INCOMPLETE",
                "V-33",
                "ip_role_mapping_incomplete",
                {"missing_raw_roles": missing_ip},
                manifest_fingerprint,
            )
    timer.info(
        "S5: role mapping contract loaded (device_map=%d, ip_map=%d, require_full=%s)",
        len(device_taxonomy_map),
        len(ip_taxonomy_map),
        require_full_role_mapping,
    )

    risk_propagation = validation_policy.get("risk_propagation", {}) or {}
    party_risky_roles = {
        str(role).upper()
        for role in (risk_propagation.get("party_risky_roles") or sorted(_DEFAULT_PARTY_RISKY_ROLES))
        if str(role).strip()
    }
    if not party_risky_roles:
        party_risky_roles = set(_DEFAULT_PARTY_RISKY_ROLES)
    account_prop_cfg = risk_propagation.get("account_owner_propagation", {}) or {}
    device_prop_cfg = risk_propagation.get("device_owner_propagation", {}) or {}
    ip_prop_cfg = risk_propagation.get("ip_sharing_propagation", {}) or {}
    account_prop_enabled = bool(account_prop_cfg.get("enabled", True))
    device_prop_enabled = bool(device_prop_cfg.get("enabled", True))
    ip_prop_enabled = bool(ip_prop_cfg.get("enabled", False))
    timer.info(
        "S5: risk propagation config loaded (party_risky_roles=%d, account_enabled=%s, device_enabled=%s, ip_enabled=%s)",
        len(party_risky_roles),
        account_prop_enabled,
        device_prop_enabled,
        ip_prop_enabled,
    )

    run_seed = int(seed)
    stream_seeds = {
        "party_risk_tier": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "party_risk_tier", _HASH_SEED),
        "party_role": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "party_role", _HASH_SEED + 1),
        "account_risk_tier": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "account_risk_tier", _HASH_SEED + 2),
        "account_role": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "account_role", _HASH_SEED + 3),
        "merchant_risk_tier": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "merchant_risk_tier", _HASH_SEED + 4),
        "merchant_role": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "merchant_role", _HASH_SEED + 5),
        "device_risk_tier": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "device_risk_tier", _HASH_SEED + 6),
        "device_role": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "device_role", _HASH_SEED + 7),
        "ip_risk_tier": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "ip_risk_tier", _HASH_SEED + 8),
        "ip_role": _derive_stream_seed(run_seed, manifest_fingerprint, parameter_hash, "ip_role", _HASH_SEED + 9),
        "account_owner_promo": _derive_stream_seed(
            run_seed, manifest_fingerprint, parameter_hash, "account_owner_promo", _HASH_SEED + 10
        ),
        "device_owner_promo": _derive_stream_seed(
            run_seed, manifest_fingerprint, parameter_hash, "device_owner_promo", _HASH_SEED + 11
        ),
        "ip_sharing_promo": _derive_stream_seed(
            run_seed, manifest_fingerprint, parameter_hash, "ip_sharing_promo", _HASH_SEED + 12
        ),
    }

    taxonomy_roles = {}
    for role_set in taxonomy.get("role_sets", []) or []:
        entity_type = role_set.get("entity_type")
        roles = {role.get("id") for role in role_set.get("roles", []) if role.get("id")}
        if entity_type:
            taxonomy_roles[str(entity_type)] = roles

    tmp_root = run_paths.tmp_root / f"s5_fraud_posture_{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)

    party_roles_path = _select_dataset_path(
        dictionary_6a, "s5_party_fraud_roles_6A", run_paths, config.external_roots, tokens
    )
    account_roles_path = _select_dataset_path(
        dictionary_6a, "s5_account_fraud_roles_6A", run_paths, config.external_roots, tokens
    )
    merchant_roles_path = _select_dataset_path(
        dictionary_6a, "s5_merchant_fraud_roles_6A", run_paths, config.external_roots, tokens
    )
    device_roles_path = _select_dataset_path(
        dictionary_6a, "s5_device_fraud_roles_6A", run_paths, config.external_roots, tokens
    )
    ip_roles_path = _select_dataset_path(dictionary_6a, "s5_ip_fraud_roles_6A", run_paths, config.external_roots, tokens)

    step_started = time.monotonic()
    if _reuse_existing_parquet(
        party_roles_path,
        party_validator,
        logger,
        manifest_fingerprint,
        "s5_party_fraud_roles_6A",
    ):
        logger.info("S5: using existing party fraud roles (path=%s)", party_roles_path)
    else:
        logger.info("S5: assigning party fraud roles (inputs=%s)", party_base_path)
        party_lf = pl.scan_parquet(str(party_base_path))
        party_u_risk = _hash_id_to_unit(pl.col("party_id"), stream_seeds["party_risk_tier"])
        party_u_role = _hash_id_to_unit(pl.col("party_id"), stream_seeds["party_role"])
        party_thresholds = (party_prior.get("risk_tier_thresholds") or {}).get("thresholds", {})
        party_tier_expr = _risk_tier_expr(party_thresholds, party_u_risk)
        party_role_model = (party_prior.get("role_probability_model") or {}).get(
            "pi_role_by_party_type_and_tier", {}
        )
        party_role_expr = _build_role_expr(
            party_role_model,
            pl.col("party_type"),
            party_tier_expr,
            party_u_role,
            "CLEAN",
        )
        party_out = (
            party_lf.with_columns(
                [
                    party_tier_expr.alias("risk_tier"),
                    party_role_expr.alias("fraud_role_party"),
                    pl.lit(run_seed).cast(pl.Int64).alias("seed"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                ]
            )
            .select(
                [
                    "party_id",
                    "fraud_role_party",
                    "risk_tier",
                    "seed",
                    "manifest_fingerprint",
                    "parameter_hash",
                ]
            )
        )
        tmp_party = tmp_root / party_roles_path.name
        party_out.sink_parquet(tmp_party, compression="zstd")
        _validate_sample_rows(
            pl.read_parquet(tmp_party, n_rows=500),
            party_validator,
            manifest_fingerprint,
            "s5_party_fraud_roles_6A",
        )
        _publish_parquet_file_idempotent(
            tmp_party,
            party_roles_path,
            logger,
            "s5_party_fraud_roles_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
    perf.record_elapsed("assign_party_roles", step_started)
    party_risk_lf = pl.scan_parquet(str(party_roles_path)).select(
        [
            pl.col("party_id"),
            pl.col("fraud_role_party")
            .str.to_uppercase()
            .is_in(sorted(party_risky_roles))
            .cast(pl.Int8)
            .alias("party_risk_flag"),
        ]
    )

    step_started = time.monotonic()
    if _reuse_existing_parquet(
        account_roles_path,
        account_validator,
        logger,
        manifest_fingerprint,
        "s5_account_fraud_roles_6A",
    ):
        logger.info("S5: using existing account fraud roles (path=%s)", account_roles_path)
    else:
        logger.info("S5: assigning account fraud roles (inputs=%s)", account_base_path)
        account_lf = pl.scan_parquet(str(account_base_path))
        if account_prop_enabled:
            account_lf = (
                account_lf.join(party_risk_lf, left_on="owner_party_id", right_on="party_id", how="left")
                .with_columns(pl.col("party_risk_flag").fill_null(0).cast(pl.Int8))
            )
        else:
            account_lf = account_lf.with_columns(pl.lit(0).cast(pl.Int8).alias("party_risk_flag"))
        account_groups = (account_prior.get("cell_definition") or {}).get("account_groups", {})
        default_account_group = account_groups.get("OTHER_CURRENT_BASIC") or next(iter(account_groups.values()), "OTHER")
        account_group_expr = _map_group_expr("account_type", account_groups, default_account_group)
        account_u_risk = _hash_id_to_unit(pl.col("account_id"), stream_seeds["account_risk_tier"])
        account_u_role = _hash_id_to_unit(pl.col("account_id"), stream_seeds["account_role"])
        account_u_owner_promo = _hash_id_to_unit(pl.col("account_id"), stream_seeds["account_owner_promo"])
        account_thresholds = (account_prior.get("risk_tier_thresholds") or {}).get("thresholds", {})
        account_tier_base_expr = _risk_tier_expr(account_thresholds, account_u_risk)
        account_tier_expr = account_tier_base_expr
        if account_prop_enabled:
            account_tier_expr = _conditional_tier_promotion_expr(
                account_tier_base_expr,
                pl.col("party_risk_flag"),
                account_u_owner_promo,
                account_prop_cfg.get("promote_probability_by_tier", {}) or {},
                _clamp01(account_prop_cfg.get("default_promote_probability", 0.0)),
            )
        account_role_model = (account_prior.get("role_probability_model") or {}).get(
            "pi_role_by_group_and_tier", {}
        )
        account_role_expr = _build_role_expr(
            account_role_model, account_group_expr, account_tier_expr, account_u_role, "CLEAN_ACCOUNT"
        )
        account_out = (
            account_lf.with_columns(
                [
                    account_tier_expr.alias("risk_tier"),
                    account_role_expr.alias("fraud_role_account"),
                    pl.lit(run_seed).cast(pl.Int64).alias("seed"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                ]
            )
            .select(
                [
                    "account_id",
                    "fraud_role_account",
                    "risk_tier",
                    "seed",
                    "manifest_fingerprint",
                    "parameter_hash",
                ]
            )
        )
        tmp_account = tmp_root / account_roles_path.name
        account_out.sink_parquet(tmp_account, compression="zstd")
        _validate_sample_rows(
            pl.read_parquet(tmp_account, n_rows=500),
            account_validator,
            manifest_fingerprint,
            "s5_account_fraud_roles_6A",
        )
        _publish_parquet_file_idempotent(
            tmp_account,
            account_roles_path,
            logger,
            "s5_account_fraud_roles_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
    perf.record_elapsed("assign_account_roles", step_started)

    step_started = time.monotonic()
    if _reuse_existing_parquet(
        merchant_roles_path,
        merchant_validator,
        logger,
        manifest_fingerprint,
        "s5_merchant_fraud_roles_6A",
    ):
        logger.info("S5: using existing merchant fraud roles (path=%s)", merchant_roles_path)
    else:
        logger.info("S5: assigning merchant fraud roles")
        merchant_source_path = merchant_account_base_path if merchant_account_base_path.exists() else outlet_catalogue_path
        if not merchant_source_path.exists():
            _abort(
                "6A.S5.REQUIRED_INPUT_MISSING",
                "V-03",
                "merchant_source_missing",
                {
                    "merchant_account_base_path": str(merchant_account_base_path),
                    "outlet_catalogue_path": str(outlet_catalogue_path),
                },
                manifest_fingerprint,
            )
        merchant_lf = (
            pl.scan_parquet(str(merchant_source_path))
            .select([pl.col("merchant_id")])
            .drop_nulls()
            .unique()
        )
        merchant_u_risk = _hash_id_to_unit(pl.col("merchant_id"), stream_seeds["merchant_risk_tier"])
        merchant_u_role = _hash_id_to_unit(pl.col("merchant_id"), stream_seeds["merchant_role"])
        merchant_thresholds = (merchant_prior.get("risk_tier_thresholds") or {}).get("thresholds", {})
        merchant_tier_expr = _risk_tier_expr(merchant_thresholds, merchant_u_risk)
        merchant_role_model = (merchant_prior.get("role_probability_model") or {}).get(
            "pi_role_by_class_and_tier", {}
        )
        merchant_group_expr = pl.lit("GENERAL_RETAIL")
        merchant_role_expr = _build_role_expr(
            merchant_role_model, merchant_group_expr, merchant_tier_expr, merchant_u_role, "NORMAL"
        )
        merchant_out = (
            merchant_lf.with_columns(
                [
                    merchant_tier_expr.alias("risk_tier"),
                    merchant_role_expr.alias("fraud_role_merchant"),
                    pl.lit(run_seed).cast(pl.Int64).alias("seed"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                ]
            )
            .select(
                [
                    "merchant_id",
                    "fraud_role_merchant",
                    "risk_tier",
                    "seed",
                    "manifest_fingerprint",
                    "parameter_hash",
                ]
            )
        )
        tmp_merchant = tmp_root / merchant_roles_path.name
        merchant_out.sink_parquet(tmp_merchant, compression="zstd")
        _validate_sample_rows(
            pl.read_parquet(tmp_merchant, n_rows=500),
            merchant_validator,
            manifest_fingerprint,
            "s5_merchant_fraud_roles_6A",
        )
        _publish_parquet_file_idempotent(
            tmp_merchant,
            merchant_roles_path,
            logger,
            "s5_merchant_fraud_roles_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
    perf.record_elapsed("assign_merchant_roles", step_started)

    step_started = time.monotonic()
    if _reuse_existing_parquet(
        device_roles_path,
        device_validator,
        logger,
        manifest_fingerprint,
        "s5_device_fraud_roles_6A",
    ):
        logger.info("S5: using existing device fraud roles (path=%s)", device_roles_path)
    else:
        logger.info("S5: assigning device fraud roles (inputs=%s)", device_base_path)
        device_lf = pl.scan_parquet(str(device_base_path))
        if device_prop_enabled:
            device_lf = (
                device_lf.join(party_risk_lf, left_on="primary_party_id", right_on="party_id", how="left")
                .with_columns(pl.col("party_risk_flag").fill_null(0).cast(pl.Int8))
            )
        else:
            device_lf = device_lf.with_columns(pl.lit(0).cast(pl.Int8).alias("party_risk_flag"))
        device_group_map = (device_prior.get("device_groups") or {}).get("device_type_to_group", {})
        default_device_group = next(iter(device_group_map.values()), "CONSUMER_PERSONAL")
        device_group_expr = _map_group_expr("device_type", device_group_map, default_device_group)
        device_u_risk = _hash_id_to_unit(pl.col("device_id"), stream_seeds["device_risk_tier"])
        device_u_role = _hash_id_to_unit(pl.col("device_id"), stream_seeds["device_role"])
        device_u_owner_promo = _hash_id_to_unit(pl.col("device_id"), stream_seeds["device_owner_promo"])
        device_thresholds = (device_prior.get("risk_tier_thresholds") or {}).get("thresholds", {})
        device_tier_base_expr = _risk_tier_expr(device_thresholds, device_u_risk)
        device_tier_expr = device_tier_base_expr
        if device_prop_enabled:
            device_tier_expr = _conditional_tier_promotion_expr(
                device_tier_base_expr,
                pl.col("party_risk_flag"),
                device_u_owner_promo,
                device_prop_cfg.get("promote_probability_by_tier", {}) or {},
                _clamp01(device_prop_cfg.get("default_promote_probability", 0.0)),
            )
        device_role_model = device_role_model_full
        device_raw_role_expr = _build_role_expr(
            device_role_model, device_group_expr, device_tier_expr, device_u_role, "NORMAL_DEVICE"
        )
        device_role_expr = _map_role_to_taxonomy_expr(device_raw_role_expr, device_taxonomy_map, "CLEAN_DEVICE")
        device_out = (
            device_lf.with_columns(
                [
                    device_tier_expr.alias("risk_tier"),
                    device_role_expr.alias("fraud_role_device"),
                    pl.lit(run_seed).cast(pl.Int64).alias("seed"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                ]
            )
            .select(
                [
                    "device_id",
                    "fraud_role_device",
                    "risk_tier",
                    "seed",
                    "manifest_fingerprint",
                    "parameter_hash",
                ]
            )
        )
        tmp_device = tmp_root / device_roles_path.name
        device_out.sink_parquet(tmp_device, compression="zstd")
        _validate_sample_rows(
            pl.read_parquet(tmp_device, n_rows=500),
            device_validator,
            manifest_fingerprint,
            "s5_device_fraud_roles_6A",
        )
        _publish_parquet_file_idempotent(
            tmp_device,
            device_roles_path,
            logger,
            "s5_device_fraud_roles_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
    perf.record_elapsed("assign_device_roles", step_started)

    step_started = time.monotonic()
    if _reuse_existing_parquet(
        ip_roles_path,
        ip_validator,
        logger,
        manifest_fingerprint,
        "s5_ip_fraud_roles_6A",
    ):
        logger.info("S5: using existing IP fraud roles (path=%s)", ip_roles_path)
    else:
        logger.info("S5: assigning IP fraud roles (inputs=%s)", ip_base_path)
        ip_lf = pl.scan_parquet(str(ip_base_path))
        if ip_prop_enabled:
            shared_degree_threshold = max(int(ip_prop_cfg.get("shared_degree_threshold", 0) or 0), 0)
            if shared_degree_threshold > 0:
                ip_shared_lf = (
                    pl.scan_parquet(str(ip_links_path))
                    .group_by("ip_id")
                    .agg(pl.n_unique("device_id").alias("devices_per_ip"))
                    .select(
                        [
                            pl.col("ip_id"),
                            (pl.col("devices_per_ip") >= pl.lit(shared_degree_threshold))
                            .cast(pl.Int8)
                            .alias("ip_sharing_risk_flag"),
                        ]
                    )
                )
                ip_lf = (
                    ip_lf.join(ip_shared_lf, on="ip_id", how="left")
                    .with_columns(pl.col("ip_sharing_risk_flag").fill_null(0).cast(pl.Int8))
                )
            else:
                ip_lf = ip_lf.with_columns(pl.lit(0).cast(pl.Int8).alias("ip_sharing_risk_flag"))
        else:
            ip_lf = ip_lf.with_columns(pl.lit(0).cast(pl.Int8).alias("ip_sharing_risk_flag"))
        ip_groups = (ip_prior.get("ip_groups") or {}).get("groups", [])
        ip_groups_sorted = sorted(
            ip_groups,
            key=lambda group: int(group.get("group_priority", 0)),
        )
        ip_group_expr = None
        for group in ip_groups_sorted:
            group_id = group.get("group_id")
            ip_types = set(group.get("ip_types", []) or [])
            asn_classes = set(group.get("asn_classes", []) or [])
            condition = pl.lit(False)
            if ip_types:
                condition = condition | pl.col("ip_type").is_in(sorted(ip_types))
            if asn_classes:
                condition = condition | pl.col("asn_class").is_in(sorted(asn_classes))
            if ip_group_expr is None:
                ip_group_expr = pl.when(condition).then(pl.lit(group_id))
            else:
                ip_group_expr = ip_group_expr.when(condition).then(pl.lit(group_id))
        if ip_group_expr is None:
            ip_group_expr = pl.lit("RESIDENTIAL")
        else:
            ip_group_expr = ip_group_expr.otherwise(pl.lit("RESIDENTIAL"))
        ip_u_risk = _hash_id_to_unit(pl.col("ip_id"), stream_seeds["ip_risk_tier"])
        ip_u_role = _hash_id_to_unit(pl.col("ip_id"), stream_seeds["ip_role"])
        ip_u_sharing_promo = _hash_id_to_unit(pl.col("ip_id"), stream_seeds["ip_sharing_promo"])
        ip_thresholds = (ip_prior.get("risk_tier_thresholds") or {}).get("thresholds", {})
        ip_tier_base_expr = _risk_tier_expr(ip_thresholds, ip_u_risk)
        ip_tier_expr = ip_tier_base_expr
        if ip_prop_enabled:
            ip_tier_expr = _conditional_tier_promotion_expr(
                ip_tier_base_expr,
                pl.col("ip_sharing_risk_flag"),
                ip_u_sharing_promo,
                ip_prop_cfg.get("promote_probability_by_tier", {}) or {},
                _clamp01(ip_prop_cfg.get("default_promote_probability", 0.0)),
            )
        ip_role_model = ip_role_model_full
        ip_raw_role_expr = _build_role_expr(ip_role_model, ip_group_expr, ip_tier_expr, ip_u_role, "NORMAL_IP")
        ip_role_expr = _map_role_to_taxonomy_expr(ip_raw_role_expr, ip_taxonomy_map, "CLEAN_IP")
        ip_out = (
            ip_lf.with_columns(
                [
                    ip_tier_expr.alias("risk_tier"),
                    ip_role_expr.alias("fraud_role_ip"),
                    pl.lit(run_seed).cast(pl.Int64).alias("seed"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                ]
            )
            .select(
                [
                    "ip_id",
                    "fraud_role_ip",
                    "risk_tier",
                    "seed",
                    "manifest_fingerprint",
                    "parameter_hash",
                ]
            )
        )
        tmp_ip = tmp_root / ip_roles_path.name
        ip_out.sink_parquet(tmp_ip, compression="zstd")
        _validate_sample_rows(
            pl.read_parquet(tmp_ip, n_rows=500),
            ip_validator,
            manifest_fingerprint,
            "s5_ip_fraud_roles_6A",
        )
        _publish_parquet_file_idempotent(
            tmp_ip,
            ip_roles_path,
            logger,
            "s5_ip_fraud_roles_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
    perf.record_elapsed("assign_ip_roles", step_started)

    timer.info("S5: fraud-role tables published")

    step_started = time.monotonic()
    checks: list[dict] = []
    issues: list[dict] = []
    issue_counter = 0

    def _record_check(check_id: str, severity: str, result: str, metrics: dict, thresholds: dict, message: str) -> None:
        nonlocal issue_counter
        checks.append(
            {
                "check_id": check_id,
                "severity": severity,
                "result": result,
                "metrics": metrics,
                "thresholds": thresholds,
            }
        )
        if result in ("WARN", "FAIL"):
            issue_counter += 1
            issues.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "check_id": check_id,
                    "issue_id": issue_counter,
                    "severity": "FAIL" if result == "FAIL" else "WARN",
                    "scope_type": "GLOBAL",
                    "seed": seed,
                    "message": message,
                    "metrics": metrics,
                }
            )

    policy_structural = validation_policy.get("structural_checks", {}) or {}

    def _structural_check(path: Path, required_cols: list[str]) -> tuple[bool, dict]:
        lf = pl.scan_parquet(str(path))
        schema_names = list(lf.collect_schema().names())
        missing = [col for col in required_cols if col not in schema_names]
        if missing:
            return False, {"missing_columns": missing}
        null_checks = {}
        if required_cols:
            null_row = lf.select([pl.col(col).is_null().any().alias(col) for col in required_cols]).collect().row(
                0, named=True
            )
            null_checks = {col: bool(null_row.get(col, False)) for col in required_cols}
        return not any(null_checks.values()), {"nulls": null_checks}

    party_required = ["party_id"]
    if policy_structural.get("party_base", {}).get("require_country_iso_present"):
        party_required.append("country_iso")
    if policy_structural.get("party_base", {}).get("require_segment_id_present"):
        party_required.append("segment_id")
    party_ok, party_metrics = _structural_check(party_base_path, party_required)
    if policy_structural.get("party_base", {}).get("require_unique_party_id"):
        party_lf = pl.scan_parquet(str(party_base_path))
        party_counts = party_lf.select(
            [
                pl.len().alias("party_count"),
                pl.col("party_id").n_unique().alias("party_unique"),
            ]
        ).collect().row(0, named=True)
        total_parties = int(party_counts.get("party_count", 0) or 0)
        unique_parties = int(party_counts.get("party_unique", 0) or 0)
        party_ok = party_ok and (total_parties == unique_parties)
        party_metrics["party_count"] = total_parties
        party_metrics["party_unique"] = unique_parties
    _record_check(
        "STRUCTURAL_PARTY_BASE",
        "REQUIRED",
        "PASS" if party_ok else "FAIL",
        party_metrics,
        {},
        "Party base structural checks failed." if not party_ok else "Party base structural checks passed.",
    )

    account_required = ["account_id"]
    if policy_structural.get("account_base", {}).get("require_owner_party_id_present"):
        account_required.append("owner_party_id")
    if policy_structural.get("account_base", {}).get("require_account_type_present"):
        account_required.append("account_type")
    account_ok, account_metrics = _structural_check(account_base_path, account_required)
    _record_check(
        "STRUCTURAL_ACCOUNT_BASE",
        "REQUIRED",
        "PASS" if account_ok else "FAIL",
        account_metrics,
        {},
        "Account base structural checks failed." if not account_ok else "Account base structural checks passed.",
    )

    instrument_required = ["account_id", "instrument_type"]
    instrument_ok, instrument_metrics = _structural_check(instrument_base_path, instrument_required)
    _record_check(
        "STRUCTURAL_INSTRUMENT_BASE",
        "REQUIRED",
        "PASS" if instrument_ok else "FAIL",
        instrument_metrics,
        {},
        "Instrument base structural checks failed." if not instrument_ok else "Instrument base structural checks passed.",
    )

    device_required = ["device_id", "device_type"]
    if policy_structural.get("device_base", {}).get("require_primary_party_present"):
        device_required.append("primary_party_id")
    device_ok, device_metrics = _structural_check(device_base_path, device_required)
    _record_check(
        "STRUCTURAL_DEVICE_BASE",
        "REQUIRED",
        "PASS" if device_ok else "FAIL",
        device_metrics,
        {},
        "Device base structural checks failed." if not device_ok else "Device base structural checks passed.",
    )

    ip_required = ["ip_id"]
    if policy_structural.get("ip_base", {}).get("require_ip_type_present"):
        ip_required.append("ip_type")
    if policy_structural.get("ip_base", {}).get("require_country_iso_present"):
        ip_required.append("country_iso")
    ip_ok, ip_metrics = _structural_check(ip_base_path, ip_required)
    _record_check(
        "STRUCTURAL_IP_BASE",
        "REQUIRED",
        "PASS" if ip_ok else "FAIL",
        ip_metrics,
        {},
        "IP base structural checks failed." if not ip_ok else "IP base structural checks passed.",
    )

    linkage_policy = validation_policy.get("linkage_checks", {}) or {}

    device_links_lf = pl.scan_parquet(str(device_links_path))
    device_party_counts = (
        device_links_lf.filter(pl.col("party_id").is_not_null())
        .group_by("party_id")
        .agg(pl.n_unique("device_id").alias("device_count"))
        .select(pl.max("device_count").alias("max_devices_per_party"))
        .collect()
        .item()
    )
    device_party_counts = int(device_party_counts or 0)
    parties_per_device = (
        device_links_lf.filter(pl.col("party_id").is_not_null())
        .group_by("device_id")
        .agg(pl.n_unique("party_id").alias("party_count"))
        .select(pl.max("party_count").alias("max_parties_per_device"))
        .collect()
        .item()
    )
    parties_per_device = int(parties_per_device or 0)
    max_devices_per_party = int(linkage_policy.get("device_links", {}).get("max_devices_per_party", 0))
    max_parties_per_device = int(linkage_policy.get("device_links", {}).get("max_parties_per_device", 0))
    device_links_ok = device_party_counts <= max_devices_per_party and parties_per_device <= max_parties_per_device
    if linkage_policy.get("device_links", {}).get("require_owner_link_present"):
        device_ids = pl.scan_parquet(str(device_base_path)).select(pl.col("device_id").unique()).collect()
        total_devices = len(device_ids)
        devices_with_owner = (
            device_links_lf.filter(pl.col("link_role") == pl.lit("PRIMARY_OWNER"))
            .select(pl.col("device_id").unique())
            .collect()
        )
        device_links_ok = device_links_ok and (len(devices_with_owner) == total_devices)
    _record_check(
        "LINKAGE_DEVICE_LINKS",
        "REQUIRED",
        "PASS" if device_links_ok else "FAIL",
        {
            "max_devices_per_party": device_party_counts,
            "max_parties_per_device": parties_per_device,
        },
        {
            "max_devices_per_party": max_devices_per_party,
            "max_parties_per_device": max_parties_per_device,
        },
        "Device linkage caps failed." if not device_links_ok else "Device linkage caps passed.",
    )

    ip_links_lf = pl.scan_parquet(str(ip_links_path))
    ips_per_device = (
        ip_links_lf.group_by("device_id")
        .agg(pl.n_unique("ip_id").alias("ip_count"))
        .select(pl.max("ip_count").alias("max_ips_per_device"))
        .collect()
        .item()
    )
    ips_per_device = int(ips_per_device or 0)
    devices_per_ip = (
        ip_links_lf.group_by("ip_id")
        .agg(pl.n_unique("device_id").alias("device_count"))
        .select(pl.max("device_count").alias("max_devices_per_ip"))
        .collect()
        .item()
    )
    devices_per_ip = int(devices_per_ip or 0)
    max_ips_per_device = int(linkage_policy.get("ip_links", {}).get("max_ips_per_device", 0))
    max_devices_per_ip = int(linkage_policy.get("ip_links", {}).get("max_devices_per_ip", 0))
    ip_links_ok = ips_per_device <= max_ips_per_device and devices_per_ip <= max_devices_per_ip
    _record_check(
        "LINKAGE_IP_LINKS",
        "REQUIRED",
        "PASS" if ip_links_ok else "FAIL",
        {
            "max_ips_per_device": ips_per_device,
            "max_devices_per_ip": devices_per_ip,
        },
        {
            "max_ips_per_device": max_ips_per_device,
            "max_devices_per_ip": max_devices_per_ip,
        },
        "IP linkage caps failed." if not ip_links_ok else "IP linkage caps passed.",
    )

    account_links_lf = pl.scan_parquet(str(instrument_links_path))
    instruments_per_account = (
        account_links_lf.group_by("account_id")
        .agg(pl.n_unique("instrument_id").alias("instrument_count"))
        .select(pl.max("instrument_count").alias("max_instruments_per_account"))
        .collect()
        .item()
    )
    instruments_per_account = int(instruments_per_account or 0)
    max_instruments_per_account = int(
        linkage_policy.get("account_instrument_links", {}).get("max_instruments_per_account", 0)
    )
    account_links_ok = instruments_per_account <= max_instruments_per_account
    _record_check(
        "LINKAGE_ACCOUNT_INSTRUMENT",
        "REQUIRED",
        "PASS" if account_links_ok else "FAIL",
        {"max_instruments_per_account": instruments_per_account},
        {"max_instruments_per_account": max_instruments_per_account},
        "Account-instrument linkage caps failed." if not account_links_ok else "Account-instrument linkage caps passed.",
    )

    def _role_fraction(path: Path, role_column: str, clean_role: str) -> tuple[int, int, float, set[str]]:
        lf = pl.scan_parquet(str(path))
        row = lf.select(
            [
                pl.len().alias("total"),
                (pl.col(role_column) != pl.lit(clean_role)).sum().cast(pl.Int64).alias("non_clean"),
                pl.col(role_column).drop_nulls().unique().sort().implode().alias("vocab"),
            ]
        ).collect().row(0, named=True)
        total = int(row.get("total", 0) or 0)
        non_clean = int(row.get("non_clean", 0) or 0)
        frac = float(non_clean) / float(total) if total > 0 else 0.0
        vocab_raw = row.get("vocab")
        if isinstance(vocab_raw, list):
            if len(vocab_raw) == 1 and isinstance(vocab_raw[0], list):
                vocab_values = vocab_raw[0]
            else:
                vocab_values = vocab_raw
        elif vocab_raw is None:
            vocab_values = []
        else:
            vocab_values = [vocab_raw]
        vocab = {str(value) for value in vocab_values if value is not None}
        return total, non_clean, frac, vocab

    role_policy = validation_policy.get("role_distribution_checks", {}) or {}

    party_total, party_nonclean, party_frac, party_roles = _role_fraction(
        party_roles_path, "fraud_role_party", "CLEAN"
    )
    party_min = float(role_policy.get("party_roles", {}).get("min_fraud_fraction", 0.0))
    party_max = float(role_policy.get("party_roles", {}).get("max_fraud_fraction", 1.0))
    party_roles_ok = party_min <= party_frac <= party_max
    _record_check(
        "ROLE_DISTRIBUTION_PARTY",
        "REQUIRED",
        "PASS" if party_roles_ok else "FAIL",
        {"nonclean_count": party_nonclean, "total": party_total, "fraction": party_frac},
        {"min_fraud_fraction": party_min, "max_fraud_fraction": party_max},
        "Party fraud-role distribution out of bounds." if not party_roles_ok else "Party roles within bounds.",
    )

    account_total, account_nonclean, account_frac, account_roles = _role_fraction(
        account_roles_path, "fraud_role_account", "CLEAN_ACCOUNT"
    )
    account_min = float(role_policy.get("account_roles", {}).get("min_fraud_fraction", 0.0))
    account_max = float(role_policy.get("account_roles", {}).get("max_fraud_fraction", 1.0))
    account_roles_ok = account_min <= account_frac <= account_max
    _record_check(
        "ROLE_DISTRIBUTION_ACCOUNT",
        "REQUIRED",
        "PASS" if account_roles_ok else "FAIL",
        {"nonclean_count": account_nonclean, "total": account_total, "fraction": account_frac},
        {"min_fraud_fraction": account_min, "max_fraud_fraction": account_max},
        "Account fraud-role distribution out of bounds." if not account_roles_ok else "Account roles within bounds.",
    )

    merchant_total, merchant_nonclean, merchant_frac, merchant_roles = _role_fraction(
        merchant_roles_path, "fraud_role_merchant", "NORMAL"
    )
    merchant_min = float(role_policy.get("merchant_roles", {}).get("min_fraud_fraction", 0.0))
    merchant_max = float(role_policy.get("merchant_roles", {}).get("max_fraud_fraction", 1.0))
    merchant_roles_ok = merchant_min <= merchant_frac <= merchant_max
    _record_check(
        "ROLE_DISTRIBUTION_MERCHANT",
        "REQUIRED",
        "PASS" if merchant_roles_ok else "FAIL",
        {"nonclean_count": merchant_nonclean, "total": merchant_total, "fraction": merchant_frac},
        {"min_fraud_fraction": merchant_min, "max_fraud_fraction": merchant_max},
        "Merchant fraud-role distribution out of bounds." if not merchant_roles_ok else "Merchant roles within bounds.",
    )

    device_total, device_nonclean, device_frac, device_roles = _role_fraction(
        device_roles_path, "fraud_role_device", "CLEAN_DEVICE"
    )
    device_min = float(role_policy.get("device_roles", {}).get("min_risky_fraction", 0.0))
    device_max = float(role_policy.get("device_roles", {}).get("max_risky_fraction", 1.0))
    device_roles_ok = device_min <= device_frac <= device_max
    _record_check(
        "ROLE_DISTRIBUTION_DEVICE",
        "REQUIRED",
        "PASS" if device_roles_ok else "FAIL",
        {"risky_count": device_nonclean, "total": device_total, "fraction": device_frac},
        {"min_risky_fraction": device_min, "max_risky_fraction": device_max},
        "Device fraud-role distribution out of bounds." if not device_roles_ok else "Device roles within bounds.",
    )

    ip_total, ip_nonclean, ip_frac, ip_roles = _role_fraction(ip_roles_path, "fraud_role_ip", "CLEAN_IP")
    ip_min = float(role_policy.get("ip_roles", {}).get("min_risky_fraction", 0.0))
    ip_max = float(role_policy.get("ip_roles", {}).get("max_risky_fraction", 1.0))
    ip_roles_ok = ip_min <= ip_frac <= ip_max
    _record_check(
        "ROLE_DISTRIBUTION_IP",
        "REQUIRED",
        "PASS" if ip_roles_ok else "FAIL",
        {"risky_count": ip_nonclean, "total": ip_total, "fraction": ip_frac},
        {"min_risky_fraction": ip_min, "max_risky_fraction": ip_max},
        "IP fraud-role distribution out of bounds." if not ip_roles_ok else "IP roles within bounds.",
    )

    require_vocab = validation_policy.get("consistency_checks", {}).get("require_role_vocab_match_taxonomy", False)
    if require_vocab:
        vocab_ok = (
            party_roles.issubset(taxonomy_roles.get("PARTY", set()))
            and account_roles.issubset(taxonomy_roles.get("ACCOUNT", set()))
            and merchant_roles.issubset(taxonomy_roles.get("MERCHANT", set()))
            and device_roles.issubset(taxonomy_roles.get("DEVICE", set()))
            and ip_roles.issubset(taxonomy_roles.get("IP", set()))
        )
        _record_check(
            "ROLE_VOCAB_TAXONOMY",
            "REQUIRED",
            "PASS" if vocab_ok else "FAIL",
            {
                "party_roles_extra": sorted(party_roles - taxonomy_roles.get("PARTY", set())),
                "account_roles_extra": sorted(account_roles - taxonomy_roles.get("ACCOUNT", set())),
                "merchant_roles_extra": sorted(merchant_roles - taxonomy_roles.get("MERCHANT", set())),
                "device_roles_extra": sorted(device_roles - taxonomy_roles.get("DEVICE", set())),
                "ip_roles_extra": sorted(ip_roles - taxonomy_roles.get("IP", set())),
            },
            {},
            "Role vocabulary not in taxonomy." if not vocab_ok else "Role vocabulary matches taxonomy.",
        )

    require_link_roles = validation_policy.get("consistency_checks", {}).get(
        "require_linkage_roles_match_policy", False
    )
    if require_link_roles:
        allowed_device_roles = {role.get("role_id") for role in linkage_rules.get("device_link_roles", []) if role.get("role_id")}
        allowed_ip_roles = {role.get("role_id") for role in linkage_rules.get("ip_link_roles", []) if role.get("role_id")}
        device_link_roles = set(
            pl.scan_parquet(str(device_links_path)).select(pl.col("link_role").unique()).collect()["link_role"]
        )
        ip_link_roles = set(
            pl.scan_parquet(str(ip_links_path)).select(pl.col("link_role").unique()).collect()["link_role"]
        )
        link_vocab_ok = device_link_roles.issubset(allowed_device_roles) and ip_link_roles.issubset(allowed_ip_roles)
        _record_check(
            "LINK_ROLE_VOCAB_POLICY",
            "REQUIRED",
            "PASS" if link_vocab_ok else "FAIL",
            {
                "device_link_roles_extra": sorted(device_link_roles - allowed_device_roles),
                "ip_link_roles_extra": sorted(ip_link_roles - allowed_ip_roles),
            },
            {},
            "Link roles outside policy." if not link_vocab_ok else "Link roles match policy.",
        )

    warnings = sum(1 for check in checks if check.get("result") == "WARN")
    failures = any(check.get("result") == "FAIL" and check.get("severity") == "REQUIRED" for check in checks)
    overall_status = "PASS"
    failure_policy = validation_policy.get("failure_policy", {}) or {}
    max_warnings = int(failure_policy.get("max_warnings", 0))
    if failures:
        overall_status = "FAIL"
    elif failure_policy.get("mode") == "fail_closed" and warnings > max_warnings:
        overall_status = "FAIL"
    elif warnings:
        overall_status = "WARN"

    checks_sorted = sorted(checks, key=lambda item: item.get("check_id", ""))
    report_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "spec_version_6A": s0_receipt.get("spec_version_6A", "1.0.0"),
        "overall_status": overall_status,
        "upstream_segments": upstream_segments_report,
        "segment_states": {
            "S0": "PASS",
            "S1": "PASS",
            "S2": "PASS",
            "S3": "PASS",
            "S4": "PASS",
            "S5": overall_status,
        },
        "checks": checks_sorted,
    }
    _validate_payload(
        report_payload,
        schema_layer3,
        schema_layer3,
        "validation/6A/validation_report_6A",
        manifest_fingerprint,
        {"stage": "report_payload"},
    )
    perf.record_elapsed("validation_checks", step_started)

    step_started = time.monotonic()
    validation_root = _select_dataset_path(dictionary_6a, "validation_bundle_6A", run_paths, config.external_roots, tokens)
    index_path = _select_dataset_path(dictionary_6a, "validation_bundle_index_6A", run_paths, config.external_roots, tokens)
    report_path = _select_dataset_path(dictionary_6a, "s5_validation_report_6A", run_paths, config.external_roots, tokens)
    issues_path = _select_dataset_path(dictionary_6a, "s5_issue_table_6A", run_paths, config.external_roots, tokens)
    flag_path = _select_dataset_path(dictionary_6a, "validation_passed_flag_6A", run_paths, config.external_roots, tokens)

    report_rel = report_path.relative_to(validation_root)
    issues_rel = issues_path.relative_to(validation_root)
    index_rel = index_path.relative_to(validation_root)
    flag_rel = flag_path.relative_to(validation_root)

    tmp_bundle_root = tmp_root / "bundle"
    tmp_bundle_root.mkdir(parents=True, exist_ok=True)
    _write_json(tmp_bundle_root / report_rel, report_payload)

    if issues:
        issues_df = pl.DataFrame(issues)
    else:
        issues_df = pl.DataFrame(
            {
                "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                "check_id": pl.Series([], dtype=pl.Utf8),
                "issue_id": pl.Series([], dtype=pl.Int64),
                "severity": pl.Series([], dtype=pl.Utf8),
                "scope_type": pl.Series([], dtype=pl.Utf8),
                "seed": pl.Series([], dtype=pl.Int64),
                "message": pl.Series([], dtype=pl.Utf8),
                "metrics": pl.Series([], dtype=pl.Struct([pl.Field("placeholder", pl.Utf8)])),
            }
        )
    issues_df_path = tmp_bundle_root / issues_rel
    issues_df_path.parent.mkdir(parents=True, exist_ok=True)
    issues_df.write_parquet(issues_df_path, compression="zstd")

    entries = [
        {
            "path": report_rel.as_posix(),
            "sha256_hex": sha256_file(tmp_bundle_root / report_rel).sha256_hex,
            "role": "VALIDATION_REPORT",
            "schema_ref": "schemas.layer3.yaml#/validation/6A/validation_report_6A",
        },
        {
            "path": issues_rel.as_posix(),
            "sha256_hex": sha256_file(tmp_bundle_root / issues_rel).sha256_hex,
            "role": "ISSUE_TABLE",
            "schema_ref": "schemas.layer3.yaml#/validation/6A/validation_issue_table_6A",
        },
    ]
    bundle_digest = _bundle_digest_for_members(tmp_bundle_root, entries)
    index_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "spec_version_6A": report_payload["spec_version_6A"],
        "items": entries,
    }
    _validate_payload(
        index_payload,
        schema_layer3,
        schema_layer3,
        "validation/6A/validation_bundle_index_6A",
        manifest_fingerprint,
        {"stage": "index_payload"},
    )
    _write_json(tmp_bundle_root / index_rel, index_payload)

    emit_flag = overall_status == "PASS"
    flag_file_path = None
    flag_payload = None
    if emit_flag:
        passed_flag_payload = f"sha256_hex = {bundle_digest}"
        flag_payload = passed_flag_payload
        flag_file_path = tmp_bundle_root / flag_rel
        flag_file_path.parent.mkdir(parents=True, exist_ok=True)
        flag_file_path.write_text(passed_flag_payload + "\n", encoding="utf-8")

    if report_path.exists() or issues_path.exists() or flag_path.exists():
        if not index_path.exists():
            _abort(
                "6A.S5.IO_WRITE_CONFLICT",
                "V-01",
                "validation_bundle_partial_exists",
                {"report_path": str(report_path), "issues_path": str(issues_path), "flag_path": str(flag_path)},
                manifest_fingerprint,
            )
    if not _existing_bundle_identical(
        validation_root,
        report_path,
        issues_path,
        index_path,
        flag_path,
        tmp_bundle_root,
        report_rel,
        issues_rel,
        index_rel,
        flag_payload,
        bundle_digest,
        logger,
        manifest_fingerprint,
    ):
        _publish_json_file_idempotent(
            tmp_bundle_root / report_rel,
            report_path,
            logger,
            "s5_validation_report_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
        _publish_parquet_file_idempotent(
            tmp_bundle_root / issues_rel,
            issues_path,
            logger,
            "s5_issue_table_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
        _publish_json_file_idempotent(
            tmp_bundle_root / index_rel,
            index_path,
            logger,
            "validation_bundle_index_6A",
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
        if emit_flag and flag_file_path is not None:
            _publish_json_file_idempotent(
                flag_file_path,
                flag_path,
                logger,
                "validation_passed_flag_6A",
                "6A.S5.IO_WRITE_CONFLICT",
                "6A.S5.IO_WRITE_FAILED",
            )
        else:
            logger.info("S5: overall_status=%s; passed flag not emitted", overall_status)
        timer.info("S5: validation bundle published (digest=%s)", bundle_digest)
    perf.record_elapsed("bundle_publish", step_started)

    step_started = time.monotonic()
    rng_audit_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_git_hash(config.repo_root),
        "notes": "6A.S5 fraud-role sampling audit (hash-based roles)",
    }
    rng_audit_entry = {key: value if value is not None else None for key, value in rng_audit_entry.items()}
    rng_audit_path = _select_dataset_path(dictionary_6a, "rng_audit_log", run_paths, config.external_roots, tokens)
    _ensure_rng_audit(rng_audit_path, rng_audit_entry, logger)

    rng_trace_path = _select_dataset_path(dictionary_6a, "rng_trace_log", run_paths, config.external_roots, tokens)
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
                    and payload.get("module") == "6A.S5"
                ):
                    substream = payload.get("substream_label")
                    if substream:
                        existing_substreams.add(substream)
    trace_rows = [
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6A.S5",
            "substream_label": label,
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 0,
            "rng_counter_after_hi": 0,
            "draws_total": int(draws),
            "blocks_total": 0,
            "events_total": 1,
        }
        for label, draws in (
            ("fraud_role_sampling_party", party_total),
            ("fraud_role_sampling_account", account_total),
            ("fraud_role_sampling_merchant", merchant_total),
            ("fraud_role_sampling_device", device_total),
            ("fraud_role_sampling_ip", ip_total),
        )
    ]
    trace_rows = [row for row in trace_rows if row.get("substream_label") not in existing_substreams]
    if trace_rows:
        with rng_trace_path.open("a", encoding="utf-8") as handle:
            for row in trace_rows:
                handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
                handle.write("\n")
        logger.info("S5: appended rng_trace_log rows for fraud-role sampling")
    else:
        logger.info("S5: rng_trace_log already contains fraud-role sampling rows; skipping append")

    rng_event_map = {
        "rng_event_fraud_role_sampling_party": party_total,
        "rng_event_fraud_role_sampling_account": account_total,
        "rng_event_fraud_role_sampling_merchant": merchant_total,
        "rng_event_fraud_role_sampling_device": device_total,
        "rng_event_fraud_role_sampling_ip": ip_total,
    }
    for dataset_id, draws in rng_event_map.items():
        entry = find_dataset_entry(dictionary_6a, dataset_id).entry
        event_path = _materialize_jsonl_path(_resolve_dataset_path(entry, run_paths, config.external_roots, tokens, True))
        tmp_event_path = tmp_root / event_path.name
        payload = {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "module": "6A.S5",
            "substream_label": dataset_id.replace("rng_event_", ""),
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 0,
            "rng_counter_after_hi": 0,
            "draws": str(int(draws)),
            "blocks": 0,
            "context": {"method": "deterministic_hash", "rows": int(draws)},
        }
        payload_text = json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n"
        if event_path.exists():
            try:
                existing_payload = json.loads(event_path.read_text(encoding="utf-8").strip())
            except Exception as exc:
                _abort(
                    "6A.S5.IO_WRITE_CONFLICT",
                    "V-01",
                    "rng_event_read_failed",
                    {"path": str(event_path), "error": str(exc)},
                    manifest_fingerprint,
                )
            existing_payload.pop("ts_utc", None)
            compare_payload = dict(payload)
            compare_payload.pop("ts_utc", None)
            if existing_payload == compare_payload:
                logger.info("S5: %s already exists and is identical; skipping publish.", dataset_id)
                continue
            _abort(
                "6A.S5.IO_WRITE_CONFLICT",
                "V-01",
                f"{dataset_id} already exists",
                {"path": str(event_path)},
                manifest_fingerprint,
            )
        tmp_event_path.write_text(payload_text, encoding="utf-8")
        _publish_jsonl_file_idempotent(
            tmp_event_path,
            event_path,
            logger,
            dataset_id,
            "6A.S5.IO_WRITE_CONFLICT",
            "6A.S5.IO_WRITE_FAILED",
        )
    perf.record_elapsed("rng_publish", step_started)
    perf.write_events(raise_on_error=True)
    write_segment6a_perf_summary_and_budget(
        run_paths=run_paths,
        run_id=run_id_value,
        seed=int(seed),
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        logger=logger,
    )

    timer.info("S5: fraud posture + validation bundle complete")
    return S5Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        party_roles_path=party_roles_path,
        account_roles_path=account_roles_path,
        merchant_roles_path=merchant_roles_path,
        device_roles_path=device_roles_path,
        ip_roles_path=ip_roles_path,
        validation_report_path=report_path,
        issue_table_path=issues_path,
        bundle_index_path=index_path,
        passed_flag_path=flag_path if emit_flag else None,
    )


__all__ = ["S5Result", "run_s5"]
