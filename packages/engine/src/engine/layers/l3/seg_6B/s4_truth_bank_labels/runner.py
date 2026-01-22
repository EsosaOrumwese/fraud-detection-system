"""S4 truth + bank-view labelling for Segment 6B (lean deterministic)."""

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


MODULE_NAME = "6B.s4_truth_bank_labels"
SEGMENT = "6B"
STATE = "S4"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    scenario_ids: list[str]
    flow_count: int
    event_count: int
    case_count: int


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
    logger = get_logger("engine.layers.l3.seg_6B.s4_truth_bank_labels.runner")
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
        defs = schema.get("$defs")
        items_schema = {key: value for key, value in schema.items() if key != "$defs"}
        schema = {"type": "array", "items": items_schema}
        if defs:
            schema["$defs"] = defs
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "6B.S4.SCHEMA_INVALID",
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
        logger.info("S4: rng_trace_log already contains rows for module=%s", module)
        return
    with rng_trace_path.open("a", encoding="utf-8") as handle:
        for row in pending_rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
    logger.info("S4: appended rng_trace_log rows for module=%s", module)


def _hash_to_index(exprs: list[pl.Expr], seed: int, modulus: int) -> pl.Expr:
    if modulus <= 0:
        return pl.lit(0).cast(pl.Int64)
    named = [expr.alias(f"k{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    return (hashed % pl.lit(int(modulus))).cast(pl.Int64)


def _hash_to_id64(exprs: list[pl.Expr], seed: int) -> pl.Expr:
    if not exprs:
        return pl.lit(1).cast(pl.Int64)
    named = [expr.alias(f"k{idx}") for idx, expr in enumerate(exprs)]
    hashed = pl.struct(named).hash(seed=seed).cast(pl.UInt64)
    modulus = (1 << 63) - 1
    return (hashed % pl.lit(modulus) + pl.lit(1)).cast(pl.Int64)


def _uniform_expr(seed: int, salt: int, modulus: int, *exprs: pl.Expr) -> pl.Expr:
    return _hash_to_index(list(exprs), seed=seed + salt, modulus=modulus).cast(pl.Float64) / float(modulus)


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
            "S4: sealed_inputs missing for %s (manifest_key=%s); using run-local output path",
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
        logger.info("S4: %s already exists at %s", label, final_path)
        tmp_path.unlink(missing_ok=True)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        logger.error("S4: unable to publish %s to %s (%s)", label, final_path, exc)
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
        logger.info("S4: %s output already exists at %s", label, final_dir)
        return
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        final_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        logger.info("S4: %s output already exists at %s", label, final_dir)
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
        logger.error("S4: unable to publish %s to %s (%s)", label, final_dir, exc)
        _abort(failure_code, "V-01", "io_write_failed", {"path": str(final_dir), "error": str(exc)}, None)


def _map_enum_expr(column: str, mapping: dict[str, object], default: object) -> pl.Expr:
    expr = None
    for key, value in mapping.items():
        if expr is None:
            expr = pl.when(pl.col(column) == key).then(pl.lit(value))
        else:
            expr = expr.when(pl.col(column) == key).then(pl.lit(value))
    if expr is None:
        return pl.lit(default)
    return expr.otherwise(pl.lit(default))


def _load_templates_map(catalogue_config: dict, logger) -> dict[str, str]:
    templates = catalogue_config.get("templates") if isinstance(catalogue_config, dict) else None
    templates = templates if isinstance(templates, list) else []
    mapping: dict[str, str] = {}
    for template in templates:
        if not isinstance(template, dict):
            continue
        template_id = str(template.get("template_id") or "").strip()
        campaign_type = str(template.get("campaign_type") or "").strip()
        if not template_id or not campaign_type:
            continue
        mapping[template_id] = campaign_type
    if not mapping:
        logger.warning("S4: no template->campaign_type mapping found in catalogue config")
    return mapping


def _load_truth_maps(truth_policy: dict, logger) -> tuple[dict[str, str], dict[str, str]]:
    mapping_label: dict[str, str] = {}
    mapping_subtype: dict[str, str] = {}
    rules = truth_policy.get("direct_pattern_map") if isinstance(truth_policy, dict) else None
    rules = rules if isinstance(rules, list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") if isinstance(rule, dict) else None
        if not isinstance(match, dict):
            continue
        pattern = match.get("fraud_pattern_type")
        if not pattern:
            continue
        truth_label = rule.get("truth_label")
        truth_subtype = rule.get("truth_subtype") or pattern
        if truth_label:
            mapping_label[str(pattern)] = str(truth_label)
            mapping_subtype[str(pattern)] = str(truth_subtype)
    if not mapping_label:
        logger.warning("S4: direct_pattern_map missing fraud_pattern_type rules; defaulting to LEGIT")
    return mapping_label, mapping_subtype


def _load_min_delay_seconds(delay_models: dict, logger) -> dict[str, float]:
    models = delay_models.get("delay_models") if isinstance(delay_models, dict) else None
    models = models if isinstance(models, list) else []
    result: dict[str, float] = {}
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("delay_model_id") or "").strip()
        if not model_id:
            continue
        value = model.get("min_seconds")
        try:
            result[model_id] = float(value)
        except (TypeError, ValueError):
            logger.warning("S4: invalid min_seconds for delay_model_id=%s", model_id)
    return result


def _extract_auth_mixture(bank_view_policy: dict) -> list[tuple[str, float]]:
    model = bank_view_policy.get("auth_decision_model") if isinstance(bank_view_policy, dict) else None
    rules = model.get("rules") if isinstance(model, dict) else None
    rules = rules if isinstance(rules, list) else []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        pi = rule.get("pi_decision")
        if isinstance(pi, list) and pi:
            result = []
            for entry in pi:
                if not isinstance(entry, dict):
                    continue
                decision = str(entry.get("auth_decision") or "").strip()
                prob = entry.get("prob")
                if not decision:
                    continue
                try:
                    prob_value = float(prob)
                except (TypeError, ValueError):
                    prob_value = 0.0
                result.append((decision, prob_value))
            if result:
                return result
    return [("APPROVE", 1.0)]


def _prob_map_from_policy(policy: dict, key: str) -> dict[str, float]:
    mapping: dict[str, float] = {}
    values = policy.get(key) if isinstance(policy, dict) else None
    if isinstance(values, dict):
        for subtype, prob in values.items():
            try:
                mapping[str(subtype)] = float(prob)
            except (TypeError, ValueError):
                continue
    return mapping


def _choice_expr(choices: list[tuple[str, float]], uniform_expr: pl.Expr) -> pl.Expr:
    cumulative = 0.0
    expr = None
    for decision, prob in choices:
        cumulative += float(prob)
        if expr is None:
            expr = pl.when(uniform_expr < cumulative).then(pl.lit(decision))
        else:
            expr = expr.when(uniform_expr < cumulative).then(pl.lit(decision))
    if expr is None:
        return pl.lit(choices[-1][0] if choices else "APPROVE")
    return expr.otherwise(pl.lit(choices[-1][0]))


def _normalize_outcome_choices(outcome_map: dict) -> dict[str, list[tuple[str, float]]]:
    normalized: dict[str, list[tuple[str, float]]] = {}
    if not isinstance(outcome_map, dict):
        return normalized
    for key, entries in outcome_map.items():
        if not isinstance(entries, list):
            continue
        choices: list[tuple[str, float]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            outcome = entry.get("chargeback_outcome") or entry.get("outcome")
            prob = entry.get("prob")
            if not outcome:
                continue
            try:
                prob_value = float(prob)
            except (TypeError, ValueError):
                prob_value = 0.0
            choices.append((str(outcome), prob_value))
        if choices:
            normalized[str(key)] = choices
    return normalized


def run_s4(
    config: EngineConfig,
    run_id: Optional[str] = None,
    batch_rows: int = 250000,
    parquet_compression: str = "zstd",
) -> S4Result:
    logger = get_logger("engine.layers.l3.seg_6B.s4_truth_bank_labels.runner")
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
            "S4_CONFIG_INVALID",
            "V-01",
            "batch_rows_invalid",
            {"batch_rows": batch_rows},
            manifest_fingerprint,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S4: run log initialized at {run_log_path}")
    logger.info(
        "S4: objective=truth+bank-view labels + case timeline; gated inputs (S0 receipt + sealed_inputs + S3 outputs + S4 policies) -> outputs s4_flow_truth_labels_6B + s4_flow_bank_view_6B + s4_event_labels_6B + s4_case_timeline_6B + rng logs"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_6b_path, dictionary_6b = load_dataset_dictionary(source, "6B")
    reg_6b_path, registry_6b = load_artefact_registry(source, "6B")
    schema_6b_path, schema_6b = load_schema_pack(source, "6B", "6B")
    schema_layer3_path, schema_layer3 = load_schema_pack(source, "6B", "layer3")
    timer.info(
        "S4: loaded contracts (dictionary=%s registry=%s schema_6b=%s schema_layer3=%s)",
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
            "S4_PRECONDITION_S0_FAILED",
            "V-01",
            "s0_gate_receipt_missing",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if not sealed_inputs_path.exists():
        _abort(
            "S4_PRECONDITION_SEALED_INPUTS_MISSING",
            "V-01",
            "sealed_inputs_missing",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    s0_receipt = _load_json(receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    if not isinstance(sealed_inputs, list):
        _abort(
            "S4_PRECONDITION_SEALED_INPUTS_INVALID",
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
            "S4_PRECONDITION_PARAMETER_HASH_MISMATCH",
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
                "S4_PRECONDITION_UPSTREAM_GATE_NOT_PASS",
                "V-01",
                "upstream_gate_not_pass",
                {"segment": segment, "status": status},
                manifest_fingerprint,
            )

    digest_expected = str(s0_receipt.get("sealed_inputs_digest_6B") or "")
    digest_actual = _sealed_inputs_digest(sealed_inputs)
    if digest_expected and digest_expected != digest_actual:
        _abort(
            "S4_PRECONDITION_SEALED_INPUTS_DIGEST_MISMATCH",
            "V-01",
            "sealed_inputs_digest_mismatch",
            {"expected": digest_expected, "actual": digest_actual},
            manifest_fingerprint,
        )
    timer.info("S4: sealed_inputs digest verified")

    required_dataset_ids = [
        "s3_flow_anchor_with_fraud_6B",
        "s3_event_stream_with_fraud_6B",
        "s3_campaign_catalogue_6B",
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
            "S4_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
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
                "S4_PRECONDITION_SEALED_INPUTS_INCOMPLETE",
                "V-01",
                "sealed_inputs_status_invalid",
                {"dataset_id": dataset_id, "status": status, "read_scope": read_scope},
                manifest_fingerprint,
            )

    policy_ids = [
        "fraud_campaign_catalogue_config_6B",
        "truth_labelling_policy_6B",
        "bank_view_policy_6B",
        "delay_models_6B",
        "case_policy_6B",
        "label_rng_policy_6B",
    ]
    policy_payloads = {}
    for policy_id in policy_ids:
        artifact_entry = find_artifact_entry(registry_6b, policy_id).entry
        path_template = artifact_entry.get("path")
        if not path_template:
            _abort(
                "S4_PRECONDITION_POLICY_MISSING",
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
                "S4_PRECONDITION_SCHEMA_REF_INVALID",
                "V-01",
                "schema_ref_missing",
                {"policy_id": policy_id, "schema_ref": schema_ref},
                manifest_fingerprint,
            )
        anchor = "#" + schema_ref.split("#", 1)[1]
        pack = schema_layer3 if schema_ref.startswith("schemas.layer3.yaml") else schema_6b
        _validate_payload(payload, pack, schema_layer3, anchor, manifest_fingerprint, {"policy_id": policy_id})

    catalogue_config = policy_payloads["fraud_campaign_catalogue_config_6B"]
    truth_policy = policy_payloads["truth_labelling_policy_6B"]
    bank_view_policy = policy_payloads["bank_view_policy_6B"]
    delay_models = policy_payloads["delay_models_6B"]
    label_rng_policy = policy_payloads["label_rng_policy_6B"]
    case_policy = policy_payloads["case_policy_6B"]
    _ = label_rng_policy
    _ = case_policy

    template_map = _load_templates_map(catalogue_config, logger)
    truth_label_map, truth_subtype_map = _load_truth_maps(truth_policy, logger)
    fail_on_unknown = bool((truth_policy.get("constraints") or {}).get("fail_on_unknown_fraud_pattern_type"))

    auth_choices = _extract_auth_mixture(bank_view_policy)
    detection_model = bank_view_policy.get("detection_model") if isinstance(bank_view_policy, dict) else {}
    dispute_model = bank_view_policy.get("dispute_model") if isinstance(bank_view_policy, dict) else {}
    chargeback_model = bank_view_policy.get("chargeback_model") if isinstance(bank_view_policy, dict) else {}
    case_lifecycle_model = bank_view_policy.get("case_lifecycle_model") if isinstance(bank_view_policy, dict) else {}

    p_detect_map = _prob_map_from_policy(detection_model, "p_detect_by_truth_subtype")
    p_detect_at_auth_map = _prob_map_from_policy(detection_model, "p_detect_at_auth_given_detect")
    p_dispute_map = _prob_map_from_policy(dispute_model, "p_dispute_by_truth_subtype")
    p_chargeback_map = _prob_map_from_policy(chargeback_model, "p_chargeback_given_dispute")

    chargeback_outcome_map = chargeback_model.get("pi_chargeback_outcome") if isinstance(chargeback_model, dict) else {}
    chargeback_outcome_map = chargeback_outcome_map if isinstance(chargeback_outcome_map, dict) else {}
    chargeback_outcome_map = _normalize_outcome_choices(chargeback_outcome_map)

    delay_min = _load_min_delay_seconds(delay_models, logger)
    detect_delay_id = detection_model.get("delay_model_id_for_post_auth_detection")
    dispute_delay_id = dispute_model.get("delay_model_id_for_dispute")
    chargeback_delay_id = chargeback_model.get("delay_model_id_for_chargeback")
    case_close_delay_id = case_lifecycle_model.get("case_close_delay_model_id")

    detect_delay_seconds = float(delay_min.get(str(detect_delay_id), 1.0))
    dispute_delay_seconds = float(delay_min.get(str(dispute_delay_id), 3600.0))
    chargeback_delay_seconds = float(delay_min.get(str(chargeback_delay_id), 86400.0))
    case_close_delay_seconds = float(delay_min.get(str(case_close_delay_id), 3600.0))

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
            "S4_CONFIG_INVALID",
            "V-01",
            "parquet_compression_invalid",
            {"value": parquet_compression},
            manifest_fingerprint,
        )
    parquet_compression = compression_map[compression]
    logger.info(
        "S4: batch_rows=%s parquet_compression=%s detect_delay=%.2fs dispute_delay=%.2fs chargeback_delay=%.2fs case_close_delay=%.2fs",
        batch_rows,
        parquet_compression,
        detect_delay_seconds,
        dispute_delay_seconds,
        chargeback_delay_seconds,
        case_close_delay_seconds,
    )

    flow_entry = find_dataset_entry(dictionary_6b, "s3_flow_anchor_with_fraud_6B").entry
    scenario_ids = _discover_scenario_ids(flow_entry, tokens, run_paths, config.external_roots)
    if not scenario_ids:
        _abort(
            "S4_PRECONDITION_S3_MISSING",
            "V-01",
            "no_flow_partitions_found",
            {"path": flow_entry.get("path") or flow_entry.get("path_template")},
            manifest_fingerprint,
        )

    logger.info("S4: discovered scenario_ids=%s", scenario_ids)

    total_flows = 0
    total_events = 0
    total_cases = 0
    processed_scenarios: list[str] = []
    modulus = 1_000_000

    for scenario_id in scenario_ids:
        tokens_local = {**tokens, "scenario_id": str(scenario_id)}
        flow_path = _resolve_dataset_path(flow_entry, run_paths, config.external_roots, tokens_local)
        event_entry = find_dataset_entry(dictionary_6b, "s3_event_stream_with_fraud_6B").entry
        event_path = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens_local)
        campaign_entry = find_dataset_entry(dictionary_6b, "s3_campaign_catalogue_6B").entry
        campaign_path = _resolve_dataset_path(campaign_entry, run_paths, config.external_roots, tokens_local)

        flow_files = _list_parquet_files(flow_path, allow_empty=True)
        event_files = _list_parquet_files(event_path, allow_empty=True)
        flow_rows = _count_parquet_rows(flow_files) if flow_files else 0
        event_rows = _count_parquet_rows(event_files) if event_files else 0

        campaign_type_by_id: dict[str, str] = {}
        if campaign_path.exists():
            campaign_df = pl.read_parquet(campaign_path)
            if campaign_df.height > 0:
                for row in campaign_df.select(["campaign_id", "campaign_label"]).to_dicts():
                    campaign_id = row.get("campaign_id")
                    label = row.get("campaign_label")
                    if campaign_id is None:
                        continue
                    campaign_type = template_map.get(str(label)) if label is not None else None
                    if campaign_type is None:
                        message = f"S4: campaign_label {label} missing template mapping"
                        if fail_on_unknown:
                            _abort(
                                "S4_PRECONDITION_UNKNOWN_CAMPAIGN",
                                "V-01",
                                "campaign_label_unknown",
                                {"campaign_label": label},
                                manifest_fingerprint,
                            )
                        logger.warning("%s; defaulting to NONE", message)
                        campaign_type = "NONE"
                    campaign_type_by_id[str(campaign_id)] = str(campaign_type)
        else:
            logger.warning("S4: campaign catalogue missing at %s; defaulting all campaigns to NONE", campaign_path)

        if campaign_type_by_id:
            campaign_map_df = pl.DataFrame(
                {
                    "campaign_id": list(campaign_type_by_id.keys()),
                    "campaign_type": list(campaign_type_by_id.values()),
                }
            )
        else:
            campaign_map_df = pl.DataFrame(schema={"campaign_id": pl.Utf8, "campaign_type": pl.Utf8})

        logger.info(
            "S4: scenario_id=%s flows_in_scope=%s events_in_scope=%s campaigns=%s",
            scenario_id,
            flow_rows,
            event_rows,
            len(campaign_type_by_id),
        )

        flow_truth_entry = find_dataset_entry(dictionary_6b, "s4_flow_truth_labels_6B").entry
        flow_bank_entry = find_dataset_entry(dictionary_6b, "s4_flow_bank_view_6B").entry
        event_label_entry = find_dataset_entry(dictionary_6b, "s4_event_labels_6B").entry
        case_entry = find_dataset_entry(dictionary_6b, "s4_case_timeline_6B").entry

        flow_truth_path = _resolve_dataset_path(flow_truth_entry, run_paths, config.external_roots, tokens_local)
        flow_bank_path = _resolve_dataset_path(flow_bank_entry, run_paths, config.external_roots, tokens_local)
        event_label_path = _resolve_dataset_path(event_label_entry, run_paths, config.external_roots, tokens_local)
        case_path = _resolve_dataset_path(case_entry, run_paths, config.external_roots, tokens_local)

        tmp_root = run_paths.tmp_root
        tmp_root.mkdir(parents=True, exist_ok=True)
        flow_truth_tmp = tmp_root / f"s4_flow_truth_labels_6B_{scenario_id}"
        flow_bank_tmp = tmp_root / f"s4_flow_bank_view_6B_{scenario_id}"
        event_label_tmp = tmp_root / f"s4_event_labels_6B_{scenario_id}"
        case_tmp = tmp_root / f"s4_case_timeline_6B_{scenario_id}"
        flow_truth_tmp.mkdir(parents=True, exist_ok=True)
        flow_bank_tmp.mkdir(parents=True, exist_ok=True)
        event_label_tmp.mkdir(parents=True, exist_ok=True)
        case_tmp.mkdir(parents=True, exist_ok=True)
        for existing in flow_truth_tmp.glob("part-*.parquet"):
            existing.unlink()
        for existing in flow_bank_tmp.glob("part-*.parquet"):
            existing.unlink()
        for existing in event_label_tmp.glob("part-*.parquet"):
            existing.unlink()
        for existing in case_tmp.glob("part-*.parquet"):
            existing.unlink()

        empty_flow_truth = pl.DataFrame(
            schema={
                "flow_id": pl.Int64,
                "is_fraud_truth": pl.Boolean,
                "fraud_label": pl.Utf8,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "scenario_id": pl.Utf8,
            }
        )
        empty_flow_bank = pl.DataFrame(
            schema={
                "flow_id": pl.Int64,
                "is_fraud_bank_view": pl.Boolean,
                "bank_label": pl.Utf8,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "scenario_id": pl.Utf8,
            }
        )
        empty_event_labels = pl.DataFrame(
            schema={
                "flow_id": pl.Int64,
                "event_seq": pl.Int64,
                "is_fraud_truth": pl.Boolean,
                "is_fraud_bank_view": pl.Boolean,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "scenario_id": pl.Utf8,
            }
        )
        empty_case = pl.DataFrame(
            schema={
                "case_id": pl.Int64,
                "case_event_seq": pl.Int64,
                "flow_id": pl.Int64,
                "case_event_type": pl.Utf8,
                "ts_utc": pl.Utf8,
                "seed": pl.Int64,
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "scenario_id": pl.Utf8,
            }
        )

        if not flow_files or flow_rows == 0:
            flow_part = flow_truth_tmp / "part-00000.parquet"
            bank_part = flow_bank_tmp / "part-00000.parquet"
            case_part = case_tmp / "part-00000.parquet"
            empty_flow_truth.write_parquet(flow_part, compression=parquet_compression)
            empty_flow_bank.write_parquet(bank_part, compression=parquet_compression)
            empty_case.write_parquet(case_part, compression=parquet_compression)
        else:
            flow_progress = _ProgressTracker(
                flow_rows,
                logger,
                f"S4: scenario_id={scenario_id} flows_processed",
            )
            flow_part_index = 0
            case_part_index = 0
            wrote_case_parts = False
            validated_flow_truth = False
            validated_flow_bank = False
            validated_case = False

            auth_choices_expr = _choice_expr(auth_choices, _uniform_expr(seed, 101, modulus, pl.col("flow_id"), pl.lit("auth_decision")))

            for flows in _iter_parquet_batches(
                flow_files,
                [
                    "flow_id",
                    "campaign_id",
                    "ts_utc",
                    "seed",
                    "manifest_fingerprint",
                    "parameter_hash",
                    "scenario_id",
                ],
                batch_rows,
            ):
                flows = flows.with_columns(
                    pl.col("flow_id").cast(pl.Int64),
                    pl.col("campaign_id").cast(pl.Utf8),
                    pl.col("ts_utc").cast(pl.Utf8),
                    pl.col("seed").cast(pl.Int64),
                    pl.col("manifest_fingerprint").cast(pl.Utf8),
                    pl.col("parameter_hash").cast(pl.Utf8),
                    pl.col("scenario_id").cast(pl.Utf8),
                )

                flows = flows.join(campaign_map_df, on="campaign_id", how="left").with_columns(
                    pl.col("campaign_type").fill_null("NONE")
                )

                flows = flows.with_columns(
                    _map_enum_expr("campaign_type", truth_label_map, "LEGIT").alias("truth_label"),
                    _map_enum_expr("campaign_type", truth_subtype_map, "NONE").alias("truth_subtype"),
                )

                flows = flows.with_columns(
                    (pl.col("truth_label") != "LEGIT").alias("is_fraud_truth")
                )

                auth_decision = pl.when(pl.col("truth_subtype") == "CARD_TESTING").then(pl.lit("DECLINE")).otherwise(auth_choices_expr)

                detect_prob = _map_enum_expr("truth_subtype", p_detect_map, 0.0)
                detect_at_auth_prob = _map_enum_expr("truth_subtype", p_detect_at_auth_map, 0.0)
                dispute_prob = _map_enum_expr("truth_subtype", p_dispute_map, 0.0)
                chargeback_prob = _map_enum_expr("truth_subtype", p_chargeback_map, 0.0)

                detect_flag = _uniform_expr(seed, 111, modulus, pl.col("flow_id"), pl.lit("detect_flag")) < detect_prob
                detect_at_auth_flag = detect_flag & (
                    _uniform_expr(seed, 112, modulus, pl.col("flow_id"), pl.lit("detect_at_auth")) < detect_at_auth_prob
                )
                dispute_flag = _uniform_expr(seed, 121, modulus, pl.col("flow_id"), pl.lit("dispute_flag")) < dispute_prob
                chargeback_flag = dispute_flag & (
                    _uniform_expr(seed, 131, modulus, pl.col("flow_id"), pl.lit("chargeback_flag")) < chargeback_prob
                )

                cb_uniform = _uniform_expr(seed, 141, modulus, pl.col("flow_id"), pl.lit("chargeback_outcome"))
                cb_fraud = _choice_expr(chargeback_outcome_map.get("FRAUD", [("BANK_LOSS", 1.0)]), cb_uniform)
                cb_abuse = _choice_expr(chargeback_outcome_map.get("ABUSE", [("BANK_WIN", 1.0)]), cb_uniform)
                cb_legit = _choice_expr(chargeback_outcome_map.get("LEGIT", [("BANK_WIN", 1.0)]), cb_uniform)

                chargeback_outcome = (
                    pl.when(chargeback_flag & (pl.col("truth_label") == "FRAUD")).then(cb_fraud)
                    .when(chargeback_flag & (pl.col("truth_label") == "ABUSE")).then(cb_abuse)
                    .when(chargeback_flag & (pl.col("truth_label") == "LEGIT")).then(cb_legit)
                    .otherwise(pl.lit("NONE"))
                )

                bank_label = (
                    pl.when(chargeback_outcome == "BANK_LOSS").then(pl.lit("CHARGEBACK_WRITTEN_OFF"))
                    .when(dispute_flag & chargeback_outcome.is_in(["BANK_WIN", "PARTIAL"]))
                    .then(pl.lit("CUSTOMER_DISPUTE_REJECTED"))
                    .when((pl.col("truth_label").is_in(["FRAUD", "ABUSE"])) & detect_flag)
                    .then(pl.lit("BANK_CONFIRMED_FRAUD"))
                    .when(pl.col("truth_label") == "LEGIT")
                    .then(pl.lit("BANK_CONFIRMED_LEGIT"))
                    .otherwise(pl.lit("NO_CASE_OPENED"))
                )

                is_fraud_bank_view = bank_label.is_in(["BANK_CONFIRMED_FRAUD", "CHARGEBACK_WRITTEN_OFF"])
                case_opened = detect_flag | dispute_flag | auth_decision.is_in(["REVIEW", "CHALLENGE"])

                flows = flows.with_columns(
                    auth_decision.alias("auth_decision"),
                    detect_flag.alias("detect_flag"),
                    detect_at_auth_flag.alias("detect_at_auth_flag"),
                    dispute_flag.alias("dispute_flag"),
                    chargeback_flag.alias("chargeback_flag"),
                    chargeback_outcome.alias("chargeback_outcome"),
                    bank_label.alias("bank_label"),
                    is_fraud_bank_view.alias("is_fraud_bank_view"),
                    case_opened.alias("case_opened"),
                )

                flow_truth = flows.select(
                    [
                        "flow_id",
                        "is_fraud_truth",
                        pl.col("truth_label").alias("fraud_label"),
                        "seed",
                        "manifest_fingerprint",
                        "parameter_hash",
                        "scenario_id",
                    ]
                )

                flow_bank = flows.select(
                    [
                        "flow_id",
                        "is_fraud_bank_view",
                        "bank_label",
                        "seed",
                        "manifest_fingerprint",
                        "parameter_hash",
                        "scenario_id",
                    ]
                )

                if not validated_flow_truth and flow_truth.height > 0:
                    sample = flow_truth.head(1).to_dicts()[0]
                    _validate_payload(
                        sample,
                        schema_6b,
                        schema_layer3,
                        "#/s4/flow_truth_labels_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )
                    validated_flow_truth = True

                if not validated_flow_bank and flow_bank.height > 0:
                    sample = flow_bank.head(1).to_dicts()[0]
                    _validate_payload(
                        sample,
                        schema_6b,
                        schema_layer3,
                        "#/s4/flow_bank_view_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )
                    validated_flow_bank = True

                flow_truth_part = flow_truth_tmp / f"part-{flow_part_index:05d}.parquet"
                flow_bank_part = flow_bank_tmp / f"part-{flow_part_index:05d}.parquet"
                flow_truth.write_parquet(flow_truth_part, compression=parquet_compression)
                flow_bank.write_parquet(flow_bank_part, compression=parquet_compression)

                cases = flows.filter(pl.col("case_opened"))
                if cases.height > 0:
                    total_cases += int(cases.height)
                    base_ts = pl.col("ts_utc").str.strptime(pl.Datetime, strict=False).alias("base_ts")
                    case_id_expr = _hash_to_id64(
                        [
                            pl.lit("mlr:6B.case_id.v1"),
                            pl.lit(manifest_fingerprint),
                            pl.lit(seed),
                            pl.col("flow_id"),
                        ],
                        seed=seed + 191,
                    )
                    cases = cases.with_columns(case_id_expr.alias("case_id"), base_ts)

                    open_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        pl.col("base_ts").dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))
                    detect_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        (pl.col("base_ts") + pl.duration(seconds=detect_delay_seconds)).dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))
                    dispute_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        (pl.col("base_ts") + pl.duration(seconds=dispute_delay_seconds)).dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))
                    chargeback_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        (pl.col("base_ts") + pl.duration(seconds=chargeback_delay_seconds)).dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))
                    chargeback_decision_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        (pl.col("base_ts") + pl.duration(seconds=chargeback_delay_seconds + 1.0)).dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))
                    close_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        (pl.col("base_ts") + pl.duration(seconds=case_close_delay_seconds)).dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))

                    case_base = cases.select(
                        [
                            "case_id",
                            "flow_id",
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                            "detect_flag",
                            "dispute_flag",
                            "chargeback_flag",
                            "ts_utc",
                            "base_ts",
                        ]
                    ).with_columns(
                        open_ts.alias("open_ts"),
                        detect_ts.alias("detect_ts"),
                        dispute_ts.alias("dispute_ts"),
                        chargeback_ts.alias("chargeback_ts"),
                        chargeback_decision_ts.alias("chargeback_decision_ts"),
                        close_ts.alias("close_ts"),
                    )

                    case_events = [
                        case_base.select(
                            [
                                "case_id",
                                pl.lit(0).cast(pl.Int64).alias("case_event_seq"),
                                "flow_id",
                                pl.lit("CASE_OPENED").alias("case_event_type"),
                                pl.col("open_ts").alias("ts_utc"),
                                "seed",
                                "manifest_fingerprint",
                                "parameter_hash",
                                "scenario_id",
                            ]
                        )
                    ]

                    detect_events = case_base.filter(pl.col("detect_flag")).select(
                        [
                            "case_id",
                            pl.lit(1).cast(pl.Int64).alias("case_event_seq"),
                            "flow_id",
                            pl.lit("DETECTION_EVENT_ATTACHED").alias("case_event_type"),
                            pl.col("detect_ts").alias("ts_utc"),
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )
                    if detect_events.height > 0:
                        case_events.append(detect_events)

                    dispute_events = case_base.filter(pl.col("dispute_flag")).select(
                        [
                            "case_id",
                            pl.lit(2).cast(pl.Int64).alias("case_event_seq"),
                            "flow_id",
                            pl.lit("CUSTOMER_DISPUTE_FILED").alias("case_event_type"),
                            pl.col("dispute_ts").alias("ts_utc"),
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )
                    if dispute_events.height > 0:
                        case_events.append(dispute_events)

                    chargeback_events = case_base.filter(pl.col("chargeback_flag")).select(
                        [
                            "case_id",
                            pl.lit(3).cast(pl.Int64).alias("case_event_seq"),
                            "flow_id",
                            pl.lit("CHARGEBACK_INITIATED").alias("case_event_type"),
                            pl.col("chargeback_ts").alias("ts_utc"),
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )
                    if chargeback_events.height > 0:
                        case_events.append(chargeback_events)

                    chargeback_decision_events = case_base.filter(pl.col("chargeback_flag")).select(
                        [
                            "case_id",
                            pl.lit(4).cast(pl.Int64).alias("case_event_seq"),
                            "flow_id",
                            pl.lit("CHARGEBACK_DECISION").alias("case_event_type"),
                            pl.col("chargeback_decision_ts").alias("ts_utc"),
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )
                    if chargeback_decision_events.height > 0:
                        case_events.append(chargeback_decision_events)

                    case_close_events = case_base.select(
                        [
                            "case_id",
                            pl.lit(5).cast(pl.Int64).alias("case_event_seq"),
                            "flow_id",
                            pl.lit("CASE_CLOSED").alias("case_event_type"),
                            pl.col("close_ts").alias("ts_utc"),
                            "seed",
                            "manifest_fingerprint",
                            "parameter_hash",
                            "scenario_id",
                        ]
                    )
                    case_events.append(case_close_events)

                    case_df = pl.concat(case_events, how="vertical")
                    if not validated_case and case_df.height > 0:
                        sample = case_df.head(1).to_dicts()[0]
                        _validate_payload(
                            sample,
                            schema_6b,
                            schema_layer3,
                            "#/s4/case_timeline_6B",
                            manifest_fingerprint,
                            {"scenario_id": scenario_id},
                        )
                        validated_case = True

                    case_part = case_tmp / f"part-{case_part_index:05d}.parquet"
                    case_df.write_parquet(case_part, compression=parquet_compression)
                    wrote_case_parts = True
                    case_part_index += 1

                batch_rows_processed = int(flow_truth.height)
                total_flows += batch_rows_processed
                flow_part_index += 1
                flow_progress.update(batch_rows_processed)

            if not wrote_case_parts:
                case_part = case_tmp / "part-00000.parquet"
                empty_case.write_parquet(case_part, compression=parquet_compression)

        flow_truth_out_dir = _materialize_parquet_path(flow_truth_path).parent
        flow_bank_out_dir = _materialize_parquet_path(flow_bank_path).parent
        case_out_dir = _materialize_parquet_path(case_path).parent
        _publish_parquet_parts(
            flow_truth_tmp,
            flow_truth_out_dir,
            logger,
            f"s4_flow_truth_labels_6B (scenario_id={scenario_id})",
            "6B.S4.IO_WRITE_CONFLICT",
            "6B.S4.IO_WRITE_FAILED",
        )
        _publish_parquet_parts(
            flow_bank_tmp,
            flow_bank_out_dir,
            logger,
            f"s4_flow_bank_view_6B (scenario_id={scenario_id})",
            "6B.S4.IO_WRITE_CONFLICT",
            "6B.S4.IO_WRITE_FAILED",
        )
        _publish_parquet_parts(
            case_tmp,
            case_out_dir,
            logger,
            f"s4_case_timeline_6B (scenario_id={scenario_id})",
            "6B.S4.IO_WRITE_CONFLICT",
            "6B.S4.IO_WRITE_FAILED",
        )

        if not event_files or event_rows == 0:
            event_part = event_label_tmp / "part-00000.parquet"
            empty_event_labels.write_parquet(event_part, compression=parquet_compression)
        else:
            event_progress = _ProgressTracker(
                event_rows,
                logger,
                f"S4: scenario_id={scenario_id} events_processed",
            )
            event_part_index = 0
            validated_event = False

            auth_choices_expr = _choice_expr(auth_choices, _uniform_expr(seed, 101, modulus, pl.col("flow_id"), pl.lit("auth_decision")))

            for events in _iter_parquet_batches(
                event_files,
                [
                    "flow_id",
                    "event_seq",
                    "campaign_id",
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
                    pl.col("campaign_id").cast(pl.Utf8),
                    pl.col("seed").cast(pl.Int64),
                    pl.col("manifest_fingerprint").cast(pl.Utf8),
                    pl.col("parameter_hash").cast(pl.Utf8),
                    pl.col("scenario_id").cast(pl.Utf8),
                )

                events = events.join(campaign_map_df, on="campaign_id", how="left").with_columns(
                    pl.col("campaign_type").fill_null("NONE")
                )
                events = events.with_columns(
                    _map_enum_expr("campaign_type", truth_label_map, "LEGIT").alias("truth_label"),
                    _map_enum_expr("campaign_type", truth_subtype_map, "NONE").alias("truth_subtype"),
                )

                events = events.with_columns(
                    (pl.col("truth_label") != "LEGIT").alias("is_fraud_truth")
                )

                auth_decision = pl.when(pl.col("truth_subtype") == "CARD_TESTING").then(pl.lit("DECLINE")).otherwise(auth_choices_expr)

                detect_prob = _map_enum_expr("truth_subtype", p_detect_map, 0.0)
                detect_at_auth_prob = _map_enum_expr("truth_subtype", p_detect_at_auth_map, 0.0)
                dispute_prob = _map_enum_expr("truth_subtype", p_dispute_map, 0.0)
                chargeback_prob = _map_enum_expr("truth_subtype", p_chargeback_map, 0.0)

                detect_flag = _uniform_expr(seed, 111, modulus, pl.col("flow_id"), pl.lit("detect_flag")) < detect_prob
                detect_at_auth_flag = detect_flag & (
                    _uniform_expr(seed, 112, modulus, pl.col("flow_id"), pl.lit("detect_at_auth")) < detect_at_auth_prob
                )
                dispute_flag = _uniform_expr(seed, 121, modulus, pl.col("flow_id"), pl.lit("dispute_flag")) < dispute_prob
                chargeback_flag = dispute_flag & (
                    _uniform_expr(seed, 131, modulus, pl.col("flow_id"), pl.lit("chargeback_flag")) < chargeback_prob
                )

                cb_uniform = _uniform_expr(seed, 141, modulus, pl.col("flow_id"), pl.lit("chargeback_outcome"))
                cb_fraud = _choice_expr(chargeback_outcome_map.get("FRAUD", [("BANK_LOSS", 1.0)]), cb_uniform)
                cb_abuse = _choice_expr(chargeback_outcome_map.get("ABUSE", [("BANK_WIN", 1.0)]), cb_uniform)
                cb_legit = _choice_expr(chargeback_outcome_map.get("LEGIT", [("BANK_WIN", 1.0)]), cb_uniform)

                chargeback_outcome = (
                    pl.when(chargeback_flag & (pl.col("truth_label") == "FRAUD")).then(cb_fraud)
                    .when(chargeback_flag & (pl.col("truth_label") == "ABUSE")).then(cb_abuse)
                    .when(chargeback_flag & (pl.col("truth_label") == "LEGIT")).then(cb_legit)
                    .otherwise(pl.lit("NONE"))
                )

                bank_label = (
                    pl.when(chargeback_outcome == "BANK_LOSS").then(pl.lit("CHARGEBACK_WRITTEN_OFF"))
                    .when(dispute_flag & chargeback_outcome.is_in(["BANK_WIN", "PARTIAL"]))
                    .then(pl.lit("CUSTOMER_DISPUTE_REJECTED"))
                    .when((pl.col("truth_label").is_in(["FRAUD", "ABUSE"])) & detect_flag)
                    .then(pl.lit("BANK_CONFIRMED_FRAUD"))
                    .when(pl.col("truth_label") == "LEGIT")
                    .then(pl.lit("BANK_CONFIRMED_LEGIT"))
                    .otherwise(pl.lit("NO_CASE_OPENED"))
                )

                is_fraud_bank_view = bank_label.is_in(["BANK_CONFIRMED_FRAUD", "CHARGEBACK_WRITTEN_OFF"])

                event_labels = events.select(
                    [
                        "flow_id",
                        "event_seq",
                        "is_fraud_truth",
                        is_fraud_bank_view.alias("is_fraud_bank_view"),
                        "seed",
                        "manifest_fingerprint",
                        "parameter_hash",
                        "scenario_id",
                    ]
                )

                if not validated_event and event_labels.height > 0:
                    sample = event_labels.head(1).to_dicts()[0]
                    _validate_payload(
                        sample,
                        schema_6b,
                        schema_layer3,
                        "#/s4/event_labels_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )
                    validated_event = True

                event_part = event_label_tmp / f"part-{event_part_index:05d}.parquet"
                event_labels.write_parquet(event_part, compression=parquet_compression)

                batch_rows_processed = int(event_labels.height)
                total_events += batch_rows_processed
                event_part_index += 1
                event_progress.update(batch_rows_processed)

        event_out_dir = _materialize_parquet_path(event_label_path).parent
        _publish_parquet_parts(
            event_label_tmp,
            event_out_dir,
            logger,
            f"s4_event_labels_6B (scenario_id={scenario_id})",
            "6B.S4.IO_WRITE_CONFLICT",
            "6B.S4.IO_WRITE_FAILED",
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
        "notes": "6B.S4 deterministic label audit",
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
            "module": "6B.S4",
            "substream_label": "truth_label",
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
            "module": "6B.S4",
            "substream_label": "bank_view_label",
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 0,
            "rng_counter_after_hi": 0,
            "draws_total": 0,
            "blocks_total": 0,
            "events_total": int(total_events),
        },
    ]
    _append_rng_trace(rng_trace_path, trace_rows, logger, "6B.S4", run_id_value, seed)

    rng_truth_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_event_truth_label").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    rng_bank_path = _resolve_dataset_path(
        find_dataset_entry(dictionary_6b, "rng_event_bank_view_label").entry,
        run_paths,
        config.external_roots,
        tokens,
    )
    rng_truth_file = _materialize_jsonl_path(rng_truth_path)
    rng_bank_file = _materialize_jsonl_path(rng_bank_path)

    tmp_root = run_paths.tmp_root
    tmp_root.mkdir(parents=True, exist_ok=True)
    rng_truth_tmp = tmp_root / f"rng_event_truth_label_{run_id_value}.jsonl"
    rng_bank_tmp = tmp_root / f"rng_event_bank_view_label_{run_id_value}.jsonl"

    rng_truth_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "6B.S4",
        "substream_label": "truth_label",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 0,
        "rng_counter_after_hi": 0,
        "draws": 0,
        "blocks": 0,
        "context": {
            "flows_total": int(total_flows),
            "notes": "deterministic hash truth labels",
        },
    }
    rng_bank_entry = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": int(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "module": "6B.S4",
        "substream_label": "bank_view_label",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 0,
        "rng_counter_after_hi": 0,
        "draws": 0,
        "blocks": 0,
        "context": {
            "flows_total": int(total_flows),
            "notes": "deterministic hash bank-view labels",
        },
    }

    rng_truth_tmp.write_text(json.dumps(rng_truth_entry, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    rng_bank_tmp.write_text(json.dumps(rng_bank_entry, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

    _publish_file_idempotent(
        rng_truth_tmp,
        rng_truth_file,
        logger,
        "rng_event_truth_label",
        "6B.S4.IO_WRITE_CONFLICT",
        "6B.S4.IO_WRITE_FAILED",
    )
    _publish_file_idempotent(
        rng_bank_tmp,
        rng_bank_file,
        logger,
        "rng_event_bank_view_label",
        "6B.S4.IO_WRITE_CONFLICT",
        "6B.S4.IO_WRITE_FAILED",
    )

    timer.info("S4: completed truth + bank-view labelling")
    return S4Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        scenario_ids=processed_scenarios,
        flow_count=int(total_flows),
        event_count=int(total_events),
        case_count=int(total_cases),
    )
