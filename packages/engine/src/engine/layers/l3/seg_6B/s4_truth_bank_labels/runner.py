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

import duckdb
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
from engine.core.run_receipt import pick_latest_run_receipt


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


@dataclass(frozen=True)
class _TruthRule:
    rule_id: str
    fraud_pattern_type: str
    overlay_anomaly_any: Optional[bool]
    requires_campaign_id: bool
    truth_label: str
    truth_subtype: str


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
    def __init__(self, total: int, logger, label: str, cadence_seconds: float = 10.0) -> None:
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
    return pick_latest_run_receipt(runs_root)


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


def _parse_optional_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def _load_truth_rules(truth_policy: dict, logger) -> list[_TruthRule]:
    parsed: list[_TruthRule] = []
    rules = truth_policy.get("direct_pattern_map") if isinstance(truth_policy, dict) else None
    rules = rules if isinstance(rules, list) else []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") if isinstance(rule, dict) else None
        if not isinstance(match, dict):
            continue
        pattern = str(match.get("fraud_pattern_type") or "").strip()
        if not pattern:
            continue
        truth_label = str(rule.get("truth_label") or "").strip()
        if not truth_label:
            continue
        truth_subtype = str(rule.get("truth_subtype") or pattern).strip()
        rule_id = str(rule.get("rule_id") or f"rule_{index}").strip()
        overlay_anomaly_any = _parse_optional_bool(match.get("overlay_anomaly_any"))
        requires_campaign_id = bool(rule.get("requires_campaign_id"))
        parsed.append(
            _TruthRule(
                rule_id=rule_id,
                fraud_pattern_type=pattern,
                overlay_anomaly_any=overlay_anomaly_any,
                requires_campaign_id=requires_campaign_id,
                truth_label=truth_label,
                truth_subtype=truth_subtype,
            )
        )
    if not parsed:
        logger.warning("S4: direct_pattern_map missing usable rules; defaulting to LEGIT/NONE")
    return parsed


def _truth_rule_condition_expr(rule: _TruthRule) -> pl.Expr:
    condition = pl.col("campaign_type") == pl.lit(rule.fraud_pattern_type)
    if rule.overlay_anomaly_any is not None:
        condition = condition & (pl.col("overlay_anomaly_any") == pl.lit(bool(rule.overlay_anomaly_any)))
    if rule.requires_campaign_id:
        condition = condition & pl.col("campaign_id").is_not_null()
    return condition


def _build_truth_rule_exprs(truth_rules: list[_TruthRule]) -> tuple[pl.Expr, pl.Expr, pl.Expr]:
    if not truth_rules:
        return (
            pl.lit("LEGIT"),
            pl.lit("NONE"),
            pl.lit(0, dtype=pl.Int64),
        )

    label_expr = None
    subtype_expr = None
    match_count_expr = pl.lit(0, dtype=pl.Int64)
    for rule in truth_rules:
        condition = _truth_rule_condition_expr(rule)
        if label_expr is None:
            label_expr = pl.when(condition).then(pl.lit(rule.truth_label))
        else:
            label_expr = label_expr.when(condition).then(pl.lit(rule.truth_label))
        if subtype_expr is None:
            subtype_expr = pl.when(condition).then(pl.lit(rule.truth_subtype))
        else:
            subtype_expr = subtype_expr.when(condition).then(pl.lit(rule.truth_subtype))
        match_count_expr = match_count_expr + pl.when(condition).then(pl.lit(1, dtype=pl.Int64)).otherwise(
            pl.lit(0, dtype=pl.Int64)
        )
    return (
        label_expr.otherwise(pl.lit("LEGIT")),
        subtype_expr.otherwise(pl.lit("NONE")),
        match_count_expr,
    )


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


def _load_max_delay_seconds(delay_models: dict, logger) -> dict[str, float]:
    models = delay_models.get("delay_models") if isinstance(delay_models, dict) else None
    models = models if isinstance(models, list) else []
    result: dict[str, float] = {}
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("delay_model_id") or "").strip()
        if not model_id:
            continue
        value = model.get("max_seconds")
        try:
            result[model_id] = float(value)
        except (TypeError, ValueError):
            logger.warning("S4: invalid max_seconds for delay_model_id=%s", model_id)
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


def _float_map_from_policy(raw: object) -> dict[str, float]:
    result: dict[str, float] = {}
    if not isinstance(raw, dict):
        return result
    for key, value in raw.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _class_multiplier_expr(class_col: str, mapping: dict[str, float], default: float = 1.0) -> pl.Expr:
    if not mapping:
        return pl.lit(float(default))
    expr = None
    for class_name, multiplier in mapping.items():
        if expr is None:
            expr = pl.when(pl.col(class_col) == pl.lit(str(class_name))).then(pl.lit(float(multiplier)))
        else:
            expr = expr.when(pl.col(class_col) == pl.lit(str(class_name))).then(pl.lit(float(multiplier)))
    if expr is None:
        return pl.lit(float(default))
    return expr.otherwise(pl.lit(float(default)))


def _resolve_merchant_class_profile_files(
    run_root: Path,
    external_roots: Iterable[Path],
    repo_root: Path,
    manifest_fingerprint: str,
    parameter_hash: str,
    preferred_globs: list[str],
    logger,
) -> list[Path]:
    resolved_patterns: list[str] = []
    tokenized_globs = preferred_globs or []
    roots = [run_root, *list(external_roots), repo_root]

    for raw_pattern in tokenized_globs:
        rendered = (
            str(raw_pattern)
            .replace("{manifest_fingerprint}", str(manifest_fingerprint))
            .replace("{parameter_hash}", str(parameter_hash))
        )
        pattern_path = Path(rendered)
        if pattern_path.is_absolute():
            resolved_patterns.append(str(pattern_path))
        else:
            for root in roots:
                resolved_patterns.append(str((root / rendered)))

    default_rel_patterns = [
        f"data/layer2/5A/merchant_class_profile/**/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/**/*.parquet",
        f"data/layer2/5A/merchant_class_profile/**/manifest_fingerprint={manifest_fingerprint}/**/*.parquet",
        (
            f"runs/local_full_run-*/**/data/layer2/5A/merchant_class_profile/**/"
            f"parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/**/*.parquet"
        ),
        (
            f"runs/local_full_run-*/**/data/layer2/5A/merchant_class_profile/**/"
            f"manifest_fingerprint={manifest_fingerprint}/**/*.parquet"
        ),
    ]
    for rel in default_rel_patterns:
        for root in roots:
            resolved_patterns.append(str((root / rel)))

    files: list[Path] = []
    for pattern in resolved_patterns:
        for matched in glob.glob(pattern, recursive=True):
            path = Path(matched)
            if path.is_file() and path.suffix.lower() == ".parquet":
                files.append(path.resolve())

    seen: set[str] = set()
    deduped: list[Path] = []
    for path in sorted(files):
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)

    logger.info("S4: merchant-class profile candidate files=%s", len(deduped))
    return deduped


def _load_merchant_class_profile_df(
    run_root: Path,
    external_roots: Iterable[Path],
    repo_root: Path,
    manifest_fingerprint: str,
    parameter_hash: str,
    preferred_globs: list[str],
    logger,
) -> pl.DataFrame:
    files = _resolve_merchant_class_profile_files(
        run_root=run_root,
        external_roots=external_roots,
        repo_root=repo_root,
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        preferred_globs=preferred_globs,
        logger=logger,
    )
    if not files:
        return pl.DataFrame(schema={"merchant_id": pl.UInt64, "primary_demand_class": pl.Utf8})

    try:
        class_df = (
            pl.scan_parquet([path.as_posix() for path in files], hive_partitioning=True)
            .select(
                [
                    pl.col("merchant_id").cast(pl.UInt64, strict=False).alias("merchant_id"),
                    pl.col("primary_demand_class").cast(pl.Utf8, strict=False).alias("primary_demand_class"),
                ]
            )
            .filter(pl.col("merchant_id").is_not_null())
            .group_by("merchant_id")
            .agg(pl.col("primary_demand_class").drop_nulls().first().alias("primary_demand_class"))
            .with_columns(pl.col("primary_demand_class").fill_null("__UNK__"))
            .collect()
        )
    except Exception as exc:
        logger.warning("S4: failed loading merchant_class_profile (%s)", exc)
        return pl.DataFrame(schema={"merchant_id": pl.UInt64, "primary_demand_class": pl.Utf8})

    class_count = (
        class_df.select(pl.col("primary_demand_class").n_unique().cast(pl.Int64).alias("class_count"))
        .to_dicts()[0]
        .get("class_count", 0)
    )
    logger.info(
        "S4: loaded merchant-class profile rows=%s classes=%s",
        class_df.height,
        int(class_count),
    )
    return class_df


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


def _merchant_legit_fp_prob_expr(merchant_id_col: str = "merchant_id") -> pl.Expr:
    merchant_bucket = (pl.col(merchant_id_col).cast(pl.UInt64) % pl.lit(128, dtype=pl.UInt64)).cast(pl.Int64)
    return (
        pl.when(merchant_bucket < 16)
        .then(pl.lit(0.0002))
        .when(merchant_bucket < 48)
        .then(pl.lit(0.002))
        .when(merchant_bucket < 96)
        .then(pl.lit(0.030))
        .when(merchant_bucket < 120)
        .then(pl.lit(0.150))
        .otherwise(pl.lit(0.450))
    )


def _overlay_anomaly_prob_expr(merchant_id_col: str = "merchant_id", amount_col: str = "amount") -> pl.Expr:
    merchant_bucket = (pl.col(merchant_id_col).cast(pl.UInt64) % pl.lit(128, dtype=pl.UInt64)).cast(pl.Int64)
    base_prob = (
        pl.when(merchant_bucket < 16)
        .then(pl.lit(0.007))
        .when(merchant_bucket < 48)
        .then(pl.lit(0.016))
        .when(merchant_bucket < 96)
        .then(pl.lit(0.030))
        .when(merchant_bucket < 120)
        .then(pl.lit(0.050))
        .otherwise(pl.lit(0.090))
    )
    amount_factor = ((pl.col(amount_col).clip(pl.lit(5.0), pl.lit(5000.0)) / pl.lit(160.0)).sqrt()).clip(
        pl.lit(0.8), pl.lit(3.0)
    )
    return (base_prob * amount_factor).clip(pl.lit(0.003), pl.lit(0.20))


def _merchant_risk_factor_expr(merchant_id_col: str = "merchant_id") -> pl.Expr:
    merchant_bucket = (pl.col(merchant_id_col).cast(pl.UInt64) % pl.lit(128, dtype=pl.UInt64)).cast(pl.Int64)
    return (
        pl.when(merchant_bucket < 16)
        .then(pl.lit(0.30))
        .when(merchant_bucket < 48)
        .then(pl.lit(0.60))
        .when(merchant_bucket < 96)
        .then(pl.lit(1.20))
        .when(merchant_bucket < 120)
        .then(pl.lit(2.00))
        .otherwise(pl.lit(3.50))
    )


def _ts_plus_seconds_expr(ts_expr: pl.Expr, seconds_expr: pl.Expr) -> pl.Expr:
    milliseconds_expr = (seconds_expr * pl.lit(1000.0)).round(0).cast(pl.Int64)
    return (ts_expr + pl.duration(milliseconds=milliseconds_expr)).dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")


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


def _sql_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _duckdb_parquet_relation(paths: list[Path]) -> str:
    literals = ", ".join(_sql_quote(path.resolve().as_posix()) for path in paths)
    return f"read_parquet([{literals}], union_by_name=true)"


def _build_event_labels_via_duckdb(
    event_files: list[Path],
    flow_truth_files: list[Path],
    flow_bank_files: list[Path],
    output_file: Path,
    parquet_compression: str,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    scenario_id: str,
    expected_rows: int,
    logger,
) -> int:
    if output_file.exists():
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    compression_sql = {
        "zstd": "zstd",
        "snappy": "snappy",
        "lz4": "lz4",
        "uncompressed": "uncompressed",
    }.get(str(parquet_compression).lower().strip(), "zstd")

    events_rel = _duckdb_parquet_relation(event_files)
    flow_truth_rel = _duckdb_parquet_relation(flow_truth_files)
    flow_bank_rel = _duckdb_parquet_relation(flow_bank_files)

    output_sql = _sql_quote(output_file.resolve().as_posix())
    manifest_sql = _sql_quote(manifest_fingerprint)
    parameter_sql = _sql_quote(parameter_hash)
    scenario_sql = _sql_quote(str(scenario_id))

    query = f"""
COPY (
    WITH events AS (
        SELECT
            CAST(flow_id AS BIGINT) AS flow_id,
            CAST(event_seq AS BIGINT) AS event_seq
        FROM {events_rel}
    ),
    flow_truth AS (
        SELECT
            CAST(flow_id AS BIGINT) AS flow_id,
            CAST(is_fraud_truth AS BOOLEAN) AS is_fraud_truth
        FROM {flow_truth_rel}
    ),
    flow_bank AS (
        SELECT
            CAST(flow_id AS BIGINT) AS flow_id,
            CAST(is_fraud_bank_view AS BOOLEAN) AS is_fraud_bank_view
        FROM {flow_bank_rel}
    )
    SELECT
        e.flow_id,
        e.event_seq,
        t.is_fraud_truth,
        b.is_fraud_bank_view,
        CAST({int(seed)} AS BIGINT) AS seed,
        {manifest_sql} AS manifest_fingerprint,
        {parameter_sql} AS parameter_hash,
        {scenario_sql} AS scenario_id
    FROM events e
    JOIN flow_truth t USING (flow_id)
    JOIN flow_bank b USING (flow_id)
) TO {output_sql} (FORMAT PARQUET, COMPRESSION {compression_sql})
"""

    start = time.monotonic()
    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute("PRAGMA preserve_insertion_order=false")
        conn.execute(query)
    finally:
        conn.close()
    elapsed = time.monotonic() - start
    logger.info(
        "S4: event-label join lane completed scenario_id=%s expected_rows=%s elapsed=%.2fs",
        scenario_id,
        expected_rows,
        elapsed,
    )

    output_rows = _count_parquet_rows([output_file])
    return int(output_rows)


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
    truth_rules = _load_truth_rules(truth_policy, logger)
    fail_on_unknown = bool((truth_policy.get("constraints") or {}).get("fail_on_unknown_fraud_pattern_type"))
    logger.info("S4: loaded %s direct truth rules (fail_on_unknown=%s)", len(truth_rules), fail_on_unknown)

    auth_choices = _extract_auth_mixture(bank_view_policy)
    detection_model = bank_view_policy.get("detection_model") if isinstance(bank_view_policy, dict) else {}
    dispute_model = bank_view_policy.get("dispute_model") if isinstance(bank_view_policy, dict) else {}
    chargeback_model = bank_view_policy.get("chargeback_model") if isinstance(bank_view_policy, dict) else {}
    case_lifecycle_model = bank_view_policy.get("case_lifecycle_model") if isinstance(bank_view_policy, dict) else {}

    p_detect_map = _prob_map_from_policy(detection_model, "p_detect_by_truth_subtype")
    p_detect_at_auth_map = _prob_map_from_policy(detection_model, "p_detect_at_auth_given_detect")
    p_dispute_map = _prob_map_from_policy(dispute_model, "p_dispute_by_truth_subtype")
    p_chargeback_map = _prob_map_from_policy(chargeback_model, "p_chargeback_given_dispute")
    class_conditioning = detection_model.get("class_conditioning") if isinstance(detection_model, dict) else {}
    class_conditioning = class_conditioning if isinstance(class_conditioning, dict) else {}
    class_conditioning_enabled = bool(class_conditioning.get("enabled", False))
    class_profile_required = bool(class_conditioning.get("fail_on_missing_profile", False))
    class_profile_globs_raw = class_conditioning.get("merchant_class_globs")
    class_profile_globs = (
        [str(item) for item in class_profile_globs_raw if str(item).strip()]
        if isinstance(class_profile_globs_raw, list)
        else []
    )
    p_detect_class_multiplier_map = _float_map_from_policy(detection_model.get("p_detect_class_multiplier"))
    p_dispute_class_multiplier_map = _float_map_from_policy(dispute_model.get("p_dispute_class_multiplier"))
    p_chargeback_class_multiplier_map = _float_map_from_policy(chargeback_model.get("p_chargeback_class_multiplier"))
    p_legit_fp_class_multiplier_map = _float_map_from_policy(detection_model.get("p_legit_fp_class_multiplier"))
    merchant_class_df = pl.DataFrame(schema={"merchant_id": pl.UInt64, "primary_demand_class": pl.Utf8})
    if class_conditioning_enabled:
        merchant_class_df = _load_merchant_class_profile_df(
            run_root=run_paths.run_root,
            external_roots=config.external_roots,
            repo_root=config.repo_root,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            preferred_globs=class_profile_globs,
            logger=logger,
        )
        if merchant_class_df.height == 0 and class_profile_required:
            _abort(
                "S4_PRECONDITION_MERCHANT_CLASS_PROFILE_MISSING",
                "V-01",
                "merchant_class_profile_missing",
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "parameter_hash": parameter_hash,
                    "globs": class_profile_globs,
                },
                manifest_fingerprint,
            )
    logger.info(
        "S4: class conditioning enabled=%s profile_rows=%s detect_multipliers=%s dispute_multipliers=%s chargeback_multipliers=%s legit_fp_multipliers=%s",
        class_conditioning_enabled,
        merchant_class_df.height,
        len(p_detect_class_multiplier_map),
        len(p_dispute_class_multiplier_map),
        len(p_chargeback_class_multiplier_map),
        len(p_legit_fp_class_multiplier_map),
    )

    chargeback_outcome_map = chargeback_model.get("pi_chargeback_outcome") if isinstance(chargeback_model, dict) else {}
    chargeback_outcome_map = chargeback_outcome_map if isinstance(chargeback_outcome_map, dict) else {}
    chargeback_outcome_map = _normalize_outcome_choices(chargeback_outcome_map)

    delay_min = _load_min_delay_seconds(delay_models, logger)
    delay_max = _load_max_delay_seconds(delay_models, logger)
    detect_delay_id = detection_model.get("delay_model_id_for_post_auth_detection")
    dispute_delay_id = dispute_model.get("delay_model_id_for_dispute")
    chargeback_delay_id = chargeback_model.get("delay_model_id_for_chargeback")
    case_close_delay_id = case_lifecycle_model.get("case_close_delay_model_id")

    detect_delay_seconds = float(delay_min.get(str(detect_delay_id), 1.0))
    dispute_delay_seconds = float(delay_min.get(str(dispute_delay_id), 3600.0))
    chargeback_delay_seconds = float(delay_min.get(str(chargeback_delay_id), 86400.0))
    case_close_delay_seconds = float(delay_min.get(str(case_close_delay_id), 3600.0))
    detect_delay_max_seconds = float(delay_max.get(str(detect_delay_id), detect_delay_seconds))
    dispute_delay_max_seconds = float(delay_max.get(str(dispute_delay_id), dispute_delay_seconds))
    chargeback_delay_max_seconds = float(delay_max.get(str(chargeback_delay_id), chargeback_delay_seconds))
    case_close_delay_max_seconds = float(delay_max.get(str(case_close_delay_id), case_close_delay_seconds))

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
            seed_literal = pl.lit(int(seed)).cast(pl.Int64)
            manifest_literal = pl.lit(manifest_fingerprint).cast(pl.Utf8)
            parameter_literal = pl.lit(parameter_hash).cast(pl.Utf8)
            scenario_literal = pl.lit(str(scenario_id)).cast(pl.Utf8)
            truth_label_expr, truth_subtype_expr, truth_rule_match_expr = _build_truth_rule_exprs(truth_rules)

            for flows in _iter_parquet_batches(
                flow_files,
                [
                    "flow_id",
                    "merchant_id",
                    "campaign_id",
                    "fraud_flag",
                    "amount",
                    "ts_utc",
                ],
                batch_rows,
            ):
                flows = flows.with_columns(
                    pl.col("flow_id").cast(pl.Int64),
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("campaign_id").cast(pl.Utf8),
                    pl.col("fraud_flag").cast(pl.Boolean),
                    pl.col("amount").cast(pl.Float64),
                    pl.col("ts_utc").cast(pl.Utf8),
                )

                flows = flows.join(campaign_map_df, on="campaign_id", how="left").with_columns(
                    pl.col("campaign_type").fill_null("NONE")
                )
                if class_conditioning_enabled and merchant_class_df.height > 0:
                    flows = flows.join(merchant_class_df, on="merchant_id", how="left")
                else:
                    flows = flows.with_columns(pl.lit(None, dtype=pl.Utf8).alias("primary_demand_class"))
                flows = flows.with_columns(pl.col("primary_demand_class").fill_null("__UNK__"))

                base_overlay_flag = pl.col("fraud_flag") & pl.col("campaign_id").is_null()
                heuristic_overlay_flag = (
                    pl.col("campaign_id").is_null()
                    & (
                        _uniform_expr(seed, 109, modulus, pl.col("flow_id"), pl.lit("overlay_anomaly"))
                        < _overlay_anomaly_prob_expr("merchant_id", "amount")
                    )
                )
                flows = flows.with_columns((base_overlay_flag | heuristic_overlay_flag).alias("overlay_anomaly_any"))

                flows = flows.with_columns(
                    truth_label_expr.alias("truth_label"),
                    truth_subtype_expr.alias("truth_subtype"),
                    truth_rule_match_expr.alias("truth_rule_match_count"),
                )

                flows = flows.with_columns(
                    (pl.col("truth_label") != "LEGIT").alias("is_fraud_truth")
                )

                rule_guard = flows.select(
                    pl.len().cast(pl.Int64).alias("flow_rows"),
                    (pl.col("truth_rule_match_count") == 0).sum().cast(pl.Int64).alias("unmatched_rows"),
                    (pl.col("truth_rule_match_count") > 1).sum().cast(pl.Int64).alias("collision_rows"),
                ).to_dicts()[0]
                unmatched_rows = int(rule_guard["unmatched_rows"])
                collision_rows = int(rule_guard["collision_rows"])
                if collision_rows > 0:
                    collision_examples = (
                        flows.filter(pl.col("truth_rule_match_count") > 1)
                        .select(
                            [
                                "flow_id",
                                "campaign_id",
                                "campaign_type",
                                "fraud_flag",
                                "overlay_anomaly_any",
                                "truth_rule_match_count",
                            ]
                        )
                        .head(5)
                        .to_dicts()
                    )
                    _abort(
                        "S4_TRUTH_RULE_COLLISION",
                        "V-01",
                        "truth_rule_collision_detected",
                        {
                            "scenario_id": str(scenario_id),
                            "collision_rows": collision_rows,
                            "sample_rows": collision_examples,
                        },
                        manifest_fingerprint,
                    )
                if unmatched_rows > 0 and fail_on_unknown:
                    unmatched_examples = (
                        flows.filter(pl.col("truth_rule_match_count") == 0)
                        .select(
                            [
                                "flow_id",
                                "campaign_id",
                                "campaign_type",
                                "fraud_flag",
                                "overlay_anomaly_any",
                            ]
                        )
                        .head(5)
                        .to_dicts()
                    )
                    _abort(
                        "S4_TRUTH_RULE_UNMATCHED",
                        "V-01",
                        "truth_rule_unmatched_rows_detected",
                        {
                            "scenario_id": str(scenario_id),
                            "unmatched_rows": unmatched_rows,
                            "sample_rows": unmatched_examples,
                        },
                        manifest_fingerprint,
                    )
                if unmatched_rows > 0 and not fail_on_unknown:
                    logger.warning(
                        "S4: scenario_id=%s truth-rule unmatched rows=%s; LEGIT/NONE fallback applied",
                        scenario_id,
                        unmatched_rows,
                    )

                auth_decision = pl.when(pl.col("truth_subtype") == "CARD_TESTING").then(pl.lit("DECLINE")).otherwise(auth_choices_expr)

                detect_prob = _map_enum_expr("truth_subtype", p_detect_map, 0.0)
                detect_at_auth_prob = _map_enum_expr("truth_subtype", p_detect_at_auth_map, 0.0)
                dispute_prob = _map_enum_expr("truth_subtype", p_dispute_map, 0.0)
                chargeback_prob = _map_enum_expr("truth_subtype", p_chargeback_map, 0.0)
                merchant_risk_factor = _merchant_risk_factor_expr("merchant_id")
                detect_class_multiplier = _class_multiplier_expr(
                    "primary_demand_class",
                    p_detect_class_multiplier_map,
                    1.0,
                )
                dispute_class_multiplier = _class_multiplier_expr(
                    "primary_demand_class",
                    p_dispute_class_multiplier_map,
                    1.0,
                )
                chargeback_class_multiplier = _class_multiplier_expr(
                    "primary_demand_class",
                    p_chargeback_class_multiplier_map,
                    1.0,
                )
                legit_fp_class_multiplier = _class_multiplier_expr(
                    "primary_demand_class",
                    p_legit_fp_class_multiplier_map,
                    1.0,
                )
                detect_prob = (detect_prob * merchant_risk_factor * detect_class_multiplier).clip(pl.lit(0.0), pl.lit(0.98))
                dispute_prob = (dispute_prob * merchant_risk_factor * dispute_class_multiplier).clip(pl.lit(0.0), pl.lit(0.98))
                chargeback_prob = (chargeback_prob * merchant_risk_factor * chargeback_class_multiplier).clip(pl.lit(0.0), pl.lit(0.98))

                detect_flag = _uniform_expr(seed, 111, modulus, pl.col("flow_id"), pl.lit("detect_flag")) < detect_prob
                detect_at_auth_flag = detect_flag & (
                    _uniform_expr(seed, 112, modulus, pl.col("flow_id"), pl.lit("detect_at_auth")) < detect_at_auth_prob
                )
                dispute_flag = _uniform_expr(seed, 121, modulus, pl.col("flow_id"), pl.lit("dispute_flag")) < dispute_prob
                chargeback_flag = dispute_flag & (
                    _uniform_expr(seed, 131, modulus, pl.col("flow_id"), pl.lit("chargeback_flag")) < chargeback_prob
                )
                amount_risk_factor = (
                    (pl.col("amount").clip(pl.lit(1.0), pl.lit(5000.0)) / pl.lit(180.0)).sqrt()
                ).clip(pl.lit(0.5), pl.lit(5.0))
                legit_fp_prob = (_merchant_legit_fp_prob_expr("merchant_id") * amount_risk_factor * legit_fp_class_multiplier).clip(
                    pl.lit(0.0002), pl.lit(0.60)
                )
                legit_fp_confirm_flag = (
                    (pl.col("truth_label") == "LEGIT")
                    & (
                        _uniform_expr(seed, 151, modulus, pl.col("flow_id"), pl.lit("legit_fp_confirm"))
                        < legit_fp_prob
                    )
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
                    .when(legit_fp_confirm_flag)
                    .then(pl.lit("BANK_CONFIRMED_FRAUD"))
                    .when(pl.col("truth_label") == "LEGIT")
                    .then(pl.lit("BANK_CONFIRMED_LEGIT"))
                    .otherwise(pl.lit("NO_CASE_OPENED"))
                )

                is_fraud_bank_view = bank_label.is_in(["BANK_CONFIRMED_FRAUD", "CHARGEBACK_WRITTEN_OFF"])
                case_opened = detect_flag | dispute_flag | auth_decision.is_in(["REVIEW", "CHALLENGE"]) | legit_fp_confirm_flag

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
                        seed_literal.alias("seed"),
                        manifest_literal.alias("manifest_fingerprint"),
                        parameter_literal.alias("parameter_hash"),
                        scenario_literal.alias("scenario_id"),
                    ]
                )

                flow_bank = flows.select(
                    [
                        "flow_id",
                        "is_fraud_bank_view",
                        "bank_label",
                        seed_literal.alias("seed"),
                        manifest_literal.alias("manifest_fingerprint"),
                        parameter_literal.alias("parameter_hash"),
                        scenario_literal.alias("scenario_id"),
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
                    base_ts = (
                        pl.col("ts_utc")
                        .str.strptime(
                            pl.Datetime,
                            format="%Y-%m-%dT%H:%M:%S%.6fZ",
                            strict=True,
                            exact=True,
                        )
                        .alias("base_ts")
                    )
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

                    detect_delay_draw = _uniform_expr(seed, 211, modulus, pl.col("flow_id"), pl.lit("detect_delay"))
                    dispute_delay_draw = _uniform_expr(seed, 221, modulus, pl.col("flow_id"), pl.lit("dispute_delay"))
                    chargeback_delay_draw = _uniform_expr(
                        seed, 231, modulus, pl.col("flow_id"), pl.lit("chargeback_delay")
                    )
                    close_delay_draw = _uniform_expr(seed, 241, modulus, pl.col("flow_id"), pl.lit("case_close_delay"))
                    chargeback_decision_gap_draw = _uniform_expr(
                        seed, 251, modulus, pl.col("flow_id"), pl.lit("chargeback_decision_gap")
                    )

                    detect_delay_sample = pl.lit(detect_delay_seconds) + (
                        detect_delay_draw.pow(1.6) * pl.lit(max(detect_delay_max_seconds - detect_delay_seconds, 0.0))
                    )
                    dispute_delay_sample = pl.lit(dispute_delay_seconds) + (
                        dispute_delay_draw.pow(1.35) * pl.lit(max(dispute_delay_max_seconds - dispute_delay_seconds, 0.0))
                    )
                    chargeback_delay_sample = pl.lit(chargeback_delay_seconds) + (
                        chargeback_delay_draw.pow(1.25)
                        * pl.lit(max(chargeback_delay_max_seconds - chargeback_delay_seconds, 0.0))
                    )
                    close_delay_sample = pl.lit(case_close_delay_seconds) + (
                        close_delay_draw.pow(1.4) * pl.lit(max(case_close_delay_max_seconds - case_close_delay_seconds, 0.0))
                    )
                    chargeback_decision_gap_seconds = pl.lit(1.0) + (chargeback_decision_gap_draw * pl.lit(300.0))

                    detect_offset_seconds = (
                        pl.when(pl.col("detect_flag"))
                        .then(
                            pl.when(pl.col("detect_at_auth_flag"))
                            .then(pl.lit(0.0))
                            .otherwise(detect_delay_sample)
                        )
                        .otherwise(pl.lit(0.0))
                    )
                    dispute_offset_raw = (
                        pl.when(pl.col("dispute_flag"))
                        .then(dispute_delay_sample)
                        .otherwise(pl.lit(0.0))
                    )
                    dispute_offset_seconds = (
                        pl.when(pl.col("dispute_flag"))
                        .then(
                            pl.max_horizontal(
                                [
                                    dispute_offset_raw,
                                    pl.when(pl.col("detect_flag"))
                                    .then(detect_offset_seconds + pl.lit(1.0))
                                    .otherwise(pl.lit(0.0)),
                                ]
                            )
                        )
                        .otherwise(pl.lit(0.0))
                    )
                    chargeback_offset_raw = (
                        pl.when(pl.col("chargeback_flag"))
                        .then(chargeback_delay_sample)
                        .otherwise(pl.lit(0.0))
                    )
                    chargeback_offset_seconds = (
                        pl.when(pl.col("chargeback_flag"))
                        .then(
                            pl.max_horizontal(
                                [
                                    chargeback_offset_raw,
                                    pl.when(pl.col("dispute_flag"))
                                    .then(dispute_offset_seconds + pl.lit(1.0))
                                    .otherwise(pl.lit(0.0)),
                                    pl.when(pl.col("detect_flag"))
                                    .then(detect_offset_seconds + pl.lit(1.0))
                                    .otherwise(pl.lit(0.0)),
                                ]
                            )
                        )
                        .otherwise(pl.lit(0.0))
                    )
                    chargeback_decision_offset_seconds = (
                        pl.when(pl.col("chargeback_flag"))
                        .then(chargeback_offset_seconds + chargeback_decision_gap_seconds)
                        .otherwise(pl.lit(0.0))
                    )
                    max_case_event_offset = pl.max_horizontal(
                        [
                            detect_offset_seconds,
                            dispute_offset_seconds,
                            chargeback_offset_seconds,
                            chargeback_decision_offset_seconds,
                        ]
                    )
                    close_offset_seconds = max_case_event_offset + close_delay_sample

                    open_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        pl.col("base_ts").dt.strftime("%Y-%m-%dT%H:%M:%S%.6fZ")
                    ).otherwise(pl.col("ts_utc"))
                    detect_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        _ts_plus_seconds_expr(pl.col("base_ts"), detect_offset_seconds)
                    ).otherwise(pl.col("ts_utc"))
                    dispute_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        _ts_plus_seconds_expr(pl.col("base_ts"), dispute_offset_seconds)
                    ).otherwise(pl.col("ts_utc"))
                    chargeback_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        _ts_plus_seconds_expr(pl.col("base_ts"), chargeback_offset_seconds)
                    ).otherwise(pl.col("ts_utc"))
                    chargeback_decision_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        _ts_plus_seconds_expr(pl.col("base_ts"), chargeback_decision_offset_seconds)
                    ).otherwise(pl.col("ts_utc"))
                    close_ts = pl.when(pl.col("base_ts").is_not_null()).then(
                        _ts_plus_seconds_expr(pl.col("base_ts"), close_offset_seconds)
                    ).otherwise(pl.col("ts_utc"))

                    case_base = cases.select(
                        [
                            "case_id",
                            "flow_id",
                            "detect_flag",
                            "detect_at_auth_flag",
                            "dispute_flag",
                            "chargeback_flag",
                            "ts_utc",
                            "base_ts",
                        ]
                    ).with_columns(
                        seed_literal.alias("seed"),
                        manifest_literal.alias("manifest_fingerprint"),
                        parameter_literal.alias("parameter_hash"),
                        scenario_literal.alias("scenario_id"),
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
            logger.info(
                "S4: scenario_id=%s starting event-label join lane rows=%s",
                scenario_id,
                event_rows,
            )
            validated_event = False
            flow_truth_files = sorted(path for path in flow_truth_out_dir.rglob("*.parquet") if path.is_file())
            flow_bank_files = sorted(path for path in flow_bank_out_dir.rglob("*.parquet") if path.is_file())
            if not flow_truth_files or not flow_bank_files:
                _abort(
                    "S4_EVENT_LABEL_JOIN_INPUT_MISSING",
                    "V-01",
                    "event_label_join_inputs_missing",
                    {
                        "scenario_id": str(scenario_id),
                        "flow_truth_parts": len(flow_truth_files),
                        "flow_bank_parts": len(flow_bank_files),
                    },
                    manifest_fingerprint,
                )
            event_part = event_label_tmp / "part-00000.parquet"
            joined_rows = _build_event_labels_via_duckdb(
                event_files=event_files,
                flow_truth_files=flow_truth_files,
                flow_bank_files=flow_bank_files,
                output_file=event_part,
                parquet_compression=parquet_compression,
                seed=seed,
                manifest_fingerprint=manifest_fingerprint,
                parameter_hash=parameter_hash,
                scenario_id=str(scenario_id),
                expected_rows=int(event_rows),
                logger=logger,
            )
            if int(joined_rows) != int(event_rows):
                _abort(
                    "S4_EVENT_LABEL_JOIN_COVERAGE_MISS",
                    "V-01",
                    "event_flow_join_rowcount_mismatch",
                    {
                        "scenario_id": str(scenario_id),
                        "event_rows": int(event_rows),
                        "joined_rows": int(joined_rows),
                    },
                    manifest_fingerprint,
                )

            if not validated_event and joined_rows > 0:
                sample_rows = pl.read_parquet(event_part, n_rows=1).to_dicts()
                if sample_rows:
                    _validate_payload(
                        sample_rows[0],
                        schema_6b,
                        schema_layer3,
                        "#/s4/event_labels_6B",
                        manifest_fingerprint,
                        {"scenario_id": scenario_id},
                    )
                    validated_event = True

            total_events += int(joined_rows)

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
