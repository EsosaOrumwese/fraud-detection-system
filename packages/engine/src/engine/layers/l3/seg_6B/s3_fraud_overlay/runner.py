"""S3 fraud overlay for Segment 6B (lean deterministic overlays)."""

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


MODULE_NAME = "6B.s3_fraud_overlay"
SEGMENT = "6B"
STATE = "S3"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    scenario_ids: list[str]
    flow_count: int
    event_count: int
    campaign_count: int


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
    logger = get_logger("engine.layers.l3.seg_6B.s3_fraud_overlay.runner")
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


def _resolve_artifact_path(path_template: str, config: EngineConfig, run_paths: RunPaths) -> Path:
    relative = Path(str(path_template))
    repo_candidate = config.repo_root / relative
    if repo_candidate.exists():
        return repo_candidate
    return resolve_input_path(str(relative), run_paths, config.external_roots, allow_run_local=True)


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
            "6B.S3.SCHEMA_INVALID",
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
        logger.info("S3: rng_trace_log already contains rows for module=%s", module)
        return
    with rng_trace_path.open("a", encoding="utf-8") as handle:
        for row in pending_rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S3: appended rng_trace_log rows for module=%s", module)


def _hash_to_index(exprs: list[pl.Expr], seed: int, modulus: int) -> pl.Expr:
    if modulus <= 0:
        return pl.lit(0).cast(pl.Int64)
    named = [expr.alias(f"k{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    return (hashed % pl.lit(int(modulus))).cast(pl.Int64)


def _discover_scenario_ids(flow_entry: dict, tokens: dict[str, str], run_paths: RunPaths, external_roots) -> list[str]:
    wildcard_path = _resolve_dataset_path(
        flow_entry,
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
            "S3: sealed_inputs missing for %s (manifest_key=%s); using run-local output path",
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
        logger.info("S3: %s already exists at %s", label, final_path)
        tmp_path.unlink(missing_ok=True)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        logger.error("S3: unable to publish %s to %s (%s)", label, final_path, exc)
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_path), "error": str(exc)}, None)


def _publish_parquet_parts(
    tmp_dir: Path,
    final_dir: Path,
    logger,
    label: str,
    conflict_code: str,
    failure_code: str,
) -> None:
    if final_dir.exists():
        logger.info("S3: %s output already exists at %s", label, final_dir)
        return
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        final_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        logger.info("S3: %s output already exists at %s", label, final_dir)
        return
    parts = sorted(tmp_dir.glob("part-*.parquet"))
    if not parts:
        _abort(
            conflict_code,
            "V-01",
            "no_output_parts",
            {"label": label, "tmp_dir": str(tmp_dir)},
            None,
        )
    try:
        for part in parts:
            part.replace(final_dir / part.name)
    except OSError as exc:
        logger.error("S3: unable to publish %s to %s (%s)", label, final_dir, exc)
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_dir), "error": str(exc)}, None)


def _campaign_id_for(
    template_id: str,
    scenario_id: str,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    instance_index: int,
) -> str:
    raw = f"{manifest_fingerprint}:{parameter_hash}:{seed}:{scenario_id}:{template_id}:{instance_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _duration_days(schedule_model: dict, logger) -> float:
    if not isinstance(schedule_model, dict):
        return 1.0
    mode = str(schedule_model.get("mode") or "").upper()
    if mode == "FULL_SCENARIO":
        return 7.0
    duration_seconds = schedule_model.get("duration_seconds")
    if duration_seconds is None:
        return 1.0
    try:
        duration_seconds = float(duration_seconds)
    except (TypeError, ValueError):
        logger.warning("S3: invalid duration_seconds in schedule model; defaulting to 1 day")
        return 1.0
    return max(duration_seconds / 86400.0, 1.0)


def _quota_targets_per_day(quota_model: dict, logger) -> float:
    if not isinstance(quota_model, dict):
        return 0.0
    for key in ("targets_per_day", "targets_per_day_mean"):
        value = quota_model.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                logger.warning("S3: invalid %s in quota model", key)
    return 0.0


def _build_campaign_plans(
    catalogue_config: dict,
    overlay_policy: dict,
    scenario_id: str,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    total_flows: int,
    logger,
    modulus: int,
) -> list[dict]:
    templates = catalogue_config.get("templates") if isinstance(catalogue_config, dict) else None
    templates = templates if isinstance(templates, list) else []
    schedule_models = catalogue_config.get("schedule_models") if isinstance(catalogue_config, dict) else {}
    quota_models = catalogue_config.get("quota_models") if isinstance(catalogue_config, dict) else {}
    schedule_models = schedule_models if isinstance(schedule_models, dict) else {}
    quota_models = quota_models if isinstance(quota_models, dict) else {}

    guardrails = overlay_policy.get("guardrails") if isinstance(overlay_policy, dict) else {}
    guardrails = guardrails if isinstance(guardrails, dict) else {}
    max_targets_total = guardrails.get("max_targets_total_per_seed_scenario")
    try:
        max_targets_total = int(max_targets_total) if max_targets_total is not None else None
    except (TypeError, ValueError):
        max_targets_total = None

    plans: list[dict] = []
    for template in templates:
        if not isinstance(template, dict):
            continue
        template_id = str(template.get("template_id") or "").strip()
        if not template_id:
            logger.warning("S3: skipping template without template_id")
            continue
        campaign_type = str(template.get("campaign_type") or "").strip()
        max_instances = int(template.get("max_instances_per_seed") or 1)
        instances = max(1, min(max_instances, 1))
        schedule_id = str(template.get("schedule_model_id") or "").strip()
        quota_id = str(template.get("quota_model_id") or "").strip()
        schedule = schedule_models.get(schedule_id, {})
        quota = quota_models.get(quota_id, {})
        duration_days = _duration_days(schedule, logger)
        targets_per_day = _quota_targets_per_day(quota, logger)

        min_targets = int(template.get("min_targets_per_instance") or 0)
        max_targets = int(template.get("max_targets_per_instance") or 0)

        if targets_per_day <= 0:
            targets_per_day = float(min_targets) if min_targets else 0.0
        target_count = int(math.ceil(targets_per_day * duration_days)) if targets_per_day > 0 else 0

        if min_targets and target_count < min_targets:
            target_count = min_targets
        if max_targets and target_count > max_targets:
            target_count = max_targets
        if total_flows and target_count > total_flows:
            target_count = total_flows

        for instance_index in range(instances):
            campaign_id = _campaign_id_for(
                template_id,
                scenario_id,
                seed,
                parameter_hash,
                manifest_fingerprint,
                instance_index,
            )
            plans.append(
                {
                    "campaign_id": campaign_id,
                    "campaign_label": template_id,
                    "campaign_type": campaign_type,
                    "target_count": max(int(target_count), 0),
                }
            )

    total_requested = sum(plan["target_count"] for plan in plans)
    if max_targets_total is not None and total_requested > max_targets_total and max_targets_total > 0:
        scale = max_targets_total / float(total_requested)
        logger.warning(
            "S3: target_count sum %s exceeds guardrail %s; scaling by %.4f",
            total_requested,
            max_targets_total,
            scale,
        )
        for plan in plans:
            scaled = int(math.floor(plan["target_count"] * scale))
            plan["target_count"] = max(scaled, 0)

    for plan in plans:
        if total_flows <= 0:
            plan["target_rate"] = 0.0
        else:
            plan["target_rate"] = min(plan["target_count"] / float(total_flows), 1.0)
        plan["threshold"] = int(plan["target_rate"] * modulus)
    return plans


def _assign_campaign_expr(campaigns: list[dict], seed: int, modulus: int) -> pl.Expr:
    campaign_expr: pl.Expr = pl.lit(None, dtype=pl.Utf8)
    for idx, campaign in enumerate(campaigns):
        threshold = int(campaign.get("threshold") or 0)
        if threshold <= 0:
            continue
        hash_expr = _hash_to_index(
            [pl.col("flow_id"), pl.lit(campaign["campaign_id"])],
            seed=seed + 1700 + idx,
            modulus=modulus,
        )
        pick_expr = hash_expr < pl.lit(threshold)
        campaign_expr = pl.when(pick_expr & campaign_expr.is_null()).then(
            pl.lit(campaign["campaign_id"])
        ).otherwise(campaign_expr)
    return campaign_expr


def _amount_shift_expr(
    min_factor: float,
    max_factor: float,
    max_multiplier: float,
    seed: int,
    modulus: int,
) -> pl.Expr:
    hash_expr = _hash_to_index(
        [pl.col("flow_id"), pl.col("campaign_id").fill_null("")],
        seed=seed + 2900,
        modulus=modulus,
    ).cast(pl.Float64)
    fraction = hash_expr / float(modulus) if modulus else pl.lit(0.0)
    factor = pl.lit(min_factor) + fraction * float(max_factor - min_factor)
    factor = pl.when(factor > max_multiplier).then(pl.lit(max_multiplier)).otherwise(factor)
    return pl.when(pl.col("campaign_id").is_not_null()).then(pl.col("amount") * factor).otherwise(pl.col("amount"))


def run_s3(
    config: EngineConfig,
    run_id: Optional[str] = None,
    batch_rows: int = 250000,
    parquet_compression: str = "zstd",
) -> S3Result:
    logger = get_logger("engine.layers.l3.seg_6B.s3_fraud_overlay.runner")
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
            "S3_CONFIG_INVALID",
            "V-01",
            "batch_rows_invalid",
            {"batch_rows": batch_rows},
            manifest_fingerprint,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S3: run log initialized at {run_log_path}")
    logger.info(
        "S3: objective=overlay lean fraud signals; gated inputs (S0 receipt + sealed_inputs + S2 outputs + S3 policies) -> outputs s3_flow_anchor_with_fraud_6B + s3_event_stream_with_fraud_6B + s3_campaign_catalogue_6B + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6b_path, dictionary_6b = load_dataset_dictionary(source, "6B")
    reg_6b_path, registry_6b = load_artefact_registry(source, "6B")
    schema_6b_path, schema_6b = load_schema_pack(source, "6B", "6B")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6B", "layer3")
    timer.info(
        "S3: loaded contracts (dictionary=%s registry=%s schema_6b=%s schema_layer3=%s)",
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
            "S3_PRECONDITION_S0_FAILED",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if not sealed_inputs_path.exists():
        _abort(
            "S3_PRECONDITION_SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    s0_receipt = _load_json(receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "S3_PRECONDITION_SEALED_INPUTS_INVALID",
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
            "S3_PRECONDITION_PARAMETER_HASH_MISMATCH",
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
                "S3_PRECONDITION_UPSTREAM_GATE_NOT_PASS",
                "V-01",
                "upstream_gate_not_pass",
                {"segment": segment, "status": status},
                manifest_fingerprint,
            )

    digest_expected = str(s0_receipt.get("sealed_inputs_digest_6B") or "")
    digest_actual = _sealed_inputs_digest(sealed_inputs)
    if digest_expected and digest_expected != digest_actual:
        _abort(
            "S3_PRECONDITION_SEALED_INPUTS_DIGEST_MISMATCH",
            "V-01",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S3: sealed_inputs digest verified")

    required_dataset_ids = [
        "s2_flow_anchor_baseline_6B",
        "s2_event_stream_baseline_6B",
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
            "S3_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
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
                "S3_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
                "V-01",
                "sealed_inputs_status_invalid",
                {"dataset_id": dataset_id, "status": status, "read_scope": read_scope},
                manifest_fingerprint,
            )

    policy_ids = [
        "fraud_campaign_catalogue_config_6B",
        "fraud_overlay_policy_6B",
        "fraud_rng_policy_6B",
    ]
    policy_payloads = {}
    for policy_id in policy_ids:
        artifact_entry = find_artifact_entry(registry_6b, policy_id).entry
        path_template = artifact_entry.get("path")
        if not path_template:
            _abort(
                "S3_PRECONDITION_POLICY_MISSING",
                "V-01",
                "policy_path_missing",
                {"policy_id": policy_id},
                manifest_fingerprint,
            )
        policy_path = _resolve_artifact_path(path_template, config, run_paths)
        policy_payloads[policy_id] = _load_yaml(policy_path)

    for policy_id, payload in policy_payloads.items():
        entry = find_dataset_entry(dictionary_6b, policy_id).entry
        schema_ref = str(entry.get("schema_ref") or "")
        if not schema_ref:
            continue
        if "#" not in schema_ref:
            _abort(
                "S3_PRECONDITION_SCHEMA_REF_INVALID",
                "V-01",
                "schema_ref_missing",
                {"policy_id": policy_id, "schema_ref": schema_ref},
                manifest_fingerprint,
            )
        anchor = "#" + schema_ref.split("#", 1)[1]
        pack = schema_layer3 if schema_ref.startswith("schemas.layer3.yaml") else schema_6b
        _validate_payload(payload, pack, schema_layer3, anchor, manifest_fingerprint, {"policy_id": policy_id})

    catalogue_config = policy_payloads["fraud_campaign_catalogue_config_6B"]
    overlay_policy = policy_payloads["fraud_overlay_policy_6B"]
    rng_policy = policy_payloads["fraud_rng_policy_6B"]
    _ = rng_policy

    realism = overlay_policy.get("realism_targets") if isinstance(overlay_policy, dict) else {}
    realism = realism if isinstance(realism, dict) else {}
    amount_range = realism.get("amount_shift_factor_range") if isinstance(realism, dict) else {}
    amount_range = amount_range if isinstance(amount_range, dict) else {}
    try:
        min_factor = float(amount_range.get("min"))
    except (TypeError, ValueError):
        min_factor = 1.10
    try:
        max_factor = float(amount_range.get("max"))
    except (TypeError, ValueError):
        max_factor = 1.50
    guardrails = overlay_policy.get("guardrails") if isinstance(overlay_policy, dict) else {}
    guardrails = guardrails if isinstance(guardrails, dict) else {}
    try:
        max_amount_multiplier = float(guardrails.get("max_amount_multiplier"))
    except (TypeError, ValueError):
        max_amount_multiplier = max_factor
    max_factor = min(max_factor, max_amount_multiplier)
    if min_factor <= 0:
        min_factor = 1.10
    if max_factor < min_factor:
        max_factor = min_factor

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
            "S3_CONFIG_INVALID",
            "V-01",
            "parquet_compression_invalid",
            {"value": parquet_compression},
            manifest_fingerprint,
        )
    parquet_compression = compression_map[compression]
    logger.info(
        "S3: batch_rows=%s parquet_compression=%s amount_shift_range=[%.2f, %.2f] max_multiplier=%.2f",
        batch_rows,
        parquet_compression,
        min_factor,
        max_factor,
        max_amount_multiplier,
    )

    flow_entry = find_dataset_entry(dictionary_6b, "s2_flow_anchor_baseline_6B").entry
    scenario_ids = _discover_scenario_ids(flow_entry, tokens, run_paths, config.external_roots)
    if not scenario_ids:
        _abort(
            "S3_PRECONDITION_S2_MISSING",
            "V-01",
            "no_flow_partitions_found",
            {"path": flow_entry.get("path") or flow_entry.get("path_template")},
            manifest_fingerprint,
        )

    logger.info("S3: discovered scenario_ids=%s", scenario_ids)

    total_flows = 0
    total_events = 0
    processed_scenarios: list[str] = []
    modulus = 1_000_000
    campaign_count_total = 0

    for scenario_id in scenario_ids:
        tokens_local = {**tokens, "scenario_id": str(scenario_id)}
        flow_path = _resolve_dataset_path(flow_entry, run_paths, config.external_roots, tokens_local)
        event_entry = find_dataset_entry(dictionary_6b, "s2_event_stream_baseline_6B").entry
        event_path = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens_local)
        flow_files = _list_parquet_files(flow_path, allow_empty=True)
        event_files = _list_parquet_files(event_path, allow_empty=True)

        flow_rows = _count_parquet_rows(flow_files) if flow_files else 0
        event_rows = _count_parquet_rows(event_files) if event_files else 0

        campaigns = _build_campaign_plans(
            catalogue_config,
            overlay_policy,
            scenario_id,
            seed,
            parameter_hash,
            manifest_fingerprint,
            flow_rows,
            logger,
            modulus,
        )
        campaign_count_total += len(campaigns)
        logger.info(
            "S3: scenario_id=%s flow_rows=%s event_rows=%s campaigns=%s",
            scenario_id,
            flow_rows,
            event_rows,
            len(campaigns),
        )

        flow_out_entry = find_dataset_entry(dictionary_6b, "s3_flow_anchor_with_fraud_6B").entry
        event_out_entry = find_dataset_entry(dictionary_6b, "s3_event_stream_with_fraud_6B").entry
        campaign_entry = find_dataset_entry(dictionary_6b, "s3_campaign_catalogue_6B").entry
        flow_out_path = _resolve_dataset_path(flow_out_entry, run_paths, config.external_roots, tokens_local)
        event_out_path = _resolve_dataset_path(event_out_entry, run_paths, config.external_roots, tokens_local)
        campaign_out_path = _resolve_dataset_path(campaign_entry, run_paths, config.external_roots, tokens_local)

        tmp_root = run_paths.tmp_root
        tmp_root.mkdir(parents=True, exist_ok=True)
        flow_tmp_dir = tmp_root / f"s3_flow_anchor_with_fraud_6B_{scenario_id}"
        event_tmp_dir = tmp_root / f"s3_event_stream_with_fraud_6B_{scenario_id}"
        flow_tmp_dir.mkdir(parents=True, exist_ok=True)
        event_tmp_dir.mkdir(parents=True, exist_ok=True)
        for existing in flow_tmp_dir.glob("part-*.parquet"):
            existing.unlink()
        for existing in event_tmp_dir.glob("part-*.parquet"):
            existing.unlink()

        campaign_counts: dict[str, int] = {plan["campaign_id"]: 0 for plan in campaigns}

        if not flow_files or flow_rows == 0:
            logger.info("S3: scenario_id=%s has no flows; emitting empty outputs", scenario_id)
            empty_flow = pl.DataFrame(
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
                    "fraud_flag": pl.Boolean,
                    "campaign_id": pl.Utf8,
                }
            )
            empty_event = pl.DataFrame(
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
                    "fraud_flag": pl.Boolean,
                    "campaign_id": pl.Utf8,
                }
            )
            flow_part = flow_tmp_dir / "part-00000.parquet"
            event_part = event_tmp_dir / "part-00000.parquet"
            empty_flow.write_parquet(flow_part, compression=parquet_compression)
            empty_event.write_parquet(event_part, compression=parquet_compression)
        else:
            progress = _ProgressTracker(
                flow_rows,
                logger,
                f"S3: scenario_id={scenario_id} flows_processed",
            )
            part_index = 0
            validated_flow_schema = False
            campaign_expr = _assign_campaign_expr(campaigns, seed, modulus)
            amount_expr = _amount_shift_expr(min_factor, max_factor, max_amount_multiplier, seed, modulus)

            for flows in _iter_parquet_batches(
                flow_files,
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
                ],
                batch_rows,
            ):
                flows = flows.with_columns(
                    pl.col("flow_id").cast(pl.Int64),
                    pl.col("arrival_seq").cast(pl.Int64),
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("party_id").cast(pl.Int64),
                    pl.col("account_id").cast(pl.Int64),
                    pl.col("instrument_id").cast(pl.Int64),
                    pl.col("device_id").cast(pl.Int64),
                    pl.col("ip_id").cast(pl.Int64),
                    pl.col("ts_utc").cast(pl.Utf8),
                    pl.col("amount").cast(pl.Float64),
                )
                flows = flows.with_columns(campaign_expr.alias("campaign_id"))
                flows = flows.with_columns(
                    amount_expr.alias("amount"),
                    pl.col("campaign_id").is_not_null().alias("fraud_flag"),
                )

                if flows.height > 0:
                    fraud_counts = (
                        flows.filter(pl.col("campaign_id").is_not_null())
                        .group_by("campaign_id")
                        .len()
                        .to_dicts()
                    )
                    for row in fraud_counts:
                        campaign_id = row.get("campaign_id")
                        count = int(row.get("len") or 0)
                        if campaign_id in campaign_counts:
                            campaign_counts[campaign_id] += count

                if not validated_flow_schema and flows.height > 0:
                    sample = flows.head(1).to_dicts()[0]
                    _validate_payload(
                        sample,
                        schema_6b,
                        schema_layer3,
                        "#/s3/flow_anchor_with_fraud_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )
                    validated_flow_schema = True

                flow_part = flow_tmp_dir / f"part-{part_index:05d}.parquet"
                flows.select(
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
                        "fraud_flag",
                        "campaign_id",
                    ]
                ).write_parquet(flow_part, compression=parquet_compression)

                batch_rows_processed = int(flows.height)
                total_flows += batch_rows_processed
                part_index += 1
                progress.update(batch_rows_processed)

        flow_out_dir = _materialize_parquet_path(flow_out_path).parent
        _publish_parquet_parts(
            flow_tmp_dir,
            flow_out_dir,
            logger,
            f"s3_flow_anchor_with_fraud_6B (scenario_id={scenario_id})",
            "6B.S3.IO_WRITE_CONFLICT",
            "6B.S3.IO_WRITE_FAILED",
        )

        if not event_files or event_rows == 0:
            logger.info("S3: scenario_id=%s has no events; emitting empty outputs", scenario_id)
            empty_event = pl.DataFrame(
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
                    "fraud_flag": pl.Boolean,
                    "campaign_id": pl.Utf8,
                }
            )
            event_part = event_tmp_dir / "part-00000.parquet"
            empty_event.write_parquet(event_part, compression=parquet_compression)
        else:
            event_progress = _ProgressTracker(
                event_rows,
                logger,
                f"S3: scenario_id={scenario_id} events_processed",
            )
            part_index = 0
            validated_event_schema = False
            campaign_expr = _assign_campaign_expr(campaigns, seed, modulus)
            amount_expr = _amount_shift_expr(min_factor, max_factor, max_amount_multiplier, seed, modulus)

            for events in _iter_parquet_batches(
                event_files,
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
                ],
                batch_rows,
            ):
                events = events.with_columns(
                    pl.col("flow_id").cast(pl.Int64),
                    pl.col("event_seq").cast(pl.Int64),
                    pl.col("event_type").cast(pl.Utf8),
                    pl.col("ts_utc").cast(pl.Utf8),
                    pl.col("amount").cast(pl.Float64),
                )
                events = events.with_columns(campaign_expr.alias("campaign_id"))
                events = events.with_columns(
                    amount_expr.alias("amount"),
                    pl.col("campaign_id").is_not_null().alias("fraud_flag"),
                )

                if not validated_event_schema and events.height > 0:
                    sample = events.head(1).to_dicts()[0]
                    _validate_payload(
                        sample,
                        schema_6b,
                        schema_layer3,
                        "#/s3/event_stream_with_fraud_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )
                    validated_event_schema = True

                event_part = event_tmp_dir / f"part-{part_index:05d}.parquet"
                events.select(
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
                        "fraud_flag",
                        "campaign_id",
                    ]
                ).write_parquet(event_part, compression=parquet_compression)

                batch_rows_processed = int(events.height)
                total_events += batch_rows_processed
                part_index += 1
                event_progress.update(batch_rows_processed)

        event_out_dir = _materialize_parquet_path(event_out_path).parent
        _publish_parquet_parts(
            event_tmp_dir,
            event_out_dir,
            logger,
            f"s3_event_stream_with_fraud_6B (scenario_id={scenario_id})",
            "6B.S3.IO_WRITE_CONFLICT",
            "6B.S3.IO_WRITE_FAILED",
        )

        campaign_rows = []
        for plan in campaigns:
            count = int(campaign_counts.get(plan["campaign_id"], 0))
            fraud_rate = count / float(flow_rows) if flow_rows > 0 else 0.0
            campaign_rows.append(
                {
                    "campaign_id": plan["campaign_id"],
                    "campaign_label": plan["campaign_label"],
                    "fraud_rate": fraud_rate,
                    "scenario_id": str(scenario_id),
                    "seed": int(seed),
                    "manifest_fingerprint": manifest_fingerprint,
                    "parameter_hash": parameter_hash,
                }
            )

        if campaign_rows:
            campaign_df = pl.DataFrame(campaign_rows)
        else:
            campaign_df = pl.DataFrame(
                schema={
                    "campaign_id": pl.Utf8,
                    "campaign_label": pl.Utf8,
                    "fraud_rate": pl.Float64,
                    "scenario_id": pl.Utf8,
                    "seed": pl.Int64,
                    "manifest_fingerprint": pl.Utf8,
                    "parameter_hash": pl.Utf8,
                }
            )
        if campaign_df.height > 0:
            sample = campaign_df.head(1).to_dicts()[0]
            _validate_payload(
                sample,
                schema_6b,
                schema_layer3,
                "#/s3/campaign_catalogue_6B",
                manifest_fingerprint,
                {"scenario_id": scenario_id},
            )
        campaign_tmp = run_paths.tmp_root / f"s3_campaign_catalogue_6B_{scenario_id}.parquet"
        campaign_df.write_parquet(campaign_tmp, compression=parquet_compression)
        _publish_file_idempotent(
            campaign_tmp,
            _materialize_parquet_path(campaign_out_path),
            logger,
            f"s3_campaign_catalogue_6B (scenario_id={scenario_id})",
            "6B.S3.IO_WRITE_CONFLICT",
            "6B.S3.IO_WRITE_FAILED",
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
        "notes": "6B.S3 deterministic fraud overlay audit",
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
    trace_rows = [
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6B.S3",
            "substream_label": "fraud_campaign_pick",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 0,
            "rng_counter_after_hi": 0,
            "draws_total": 0,
            "blocks_total": 0,
            "events_total": int(total_flows),
        },
        {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": run_id_value,
            "seed": int(seed),
            "module": "6B.S3",
            "substream_label": "fraud_overlay_apply",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 0,
            "rng_counter_after_hi": 0,
            "draws_total": 0,
            "blocks_total": 0,
            "events_total": int(total_events),
        },
    ]
    _append_rng_trace(rng_trace_path, trace_rows, logger, "6B.S3", run_id_value, seed)

    rng_campaign_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_event_fraud_campaign_pick").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    rng_overlay_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_event_fraud_overlay_apply").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    rng_campaign_file = _materialize_jsonl_path(rng_campaign_path)
    rng_overlay_file = _materialize_jsonl_path(rng_overlay_path)

    tmp_root = run_paths.tmp_root
    tmp_root.mkdir(parents=True, exist_ok=True)
    rng_campaign_tmp = tmp_root / f"rng_event_fraud_campaign_pick_{run_id_value}.jsonl"
    rng_overlay_tmp = tmp_root / f"rng_event_fraud_overlay_apply_{run_id_value}.jsonl"

    rng_campaign_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "6B.S3",
        "substream_label": "fraud_campaign_pick",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 0,
        "rng_counter_after_hi": 0,
        "draws": 0,
        "blocks": 0,
        "context": {
            "campaigns_total": int(campaign_count_total),
            "notes": "deterministic hash selection for fraud campaign picks",
        },
    }
    rng_overlay_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "6B.S3",
        "substream_label": "fraud_overlay_apply",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 0,
        "rng_counter_after_hi": 0,
        "draws": 0,
        "blocks": 0,
        "context": {
            "events_total": int(total_events),
            "notes": "deterministic hash selection for overlay application",
        },
    }

    rng_campaign_tmp.write_text(
        json.dumps(rng_campaign_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rng_overlay_tmp.write_text(
        json.dumps(rng_overlay_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _publish_file_idempotent(
        rng_campaign_tmp,
        rng_campaign_file,
        logger,
        "rng_event_fraud_campaign_pick",
        "6B.S3.IO_WRITE_CONFLICT",
        "6B.S3.IO_WRITE_FAILED",
    )
    _publish_file_idempotent(
        rng_overlay_tmp,
        rng_overlay_file,
        logger,
        "rng_event_fraud_overlay_apply",
        "6B.S3.IO_WRITE_CONFLICT",
        "6B.S3.IO_WRITE_FAILED",
    )

    timer.info("S3: completed fraud overlay")
    return S3Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        scenario_ids=processed_scenarios,
        flow_count=int(total_flows),
        event_count=int(total_events),
        campaign_count=int(campaign_count_total),
    )
