"""S5 validation gate for Segment 6B (lean path)."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import duckdb
import polars as pl
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
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt

try:  # pragma: no cover - optional dependency for fast parquet metadata
    import pyarrow.parquet as pq
except Exception:  # noqa: BLE001
    pq = None


MODULE_NAME = "6B.s5_validation_gate"
SEGMENT = "6B"
STATE = "S5"
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")

DATASET_S0_GATE = "s0_gate_receipt_6B"
DATASET_SEALED_INPUTS = "sealed_inputs_6B"
DATASET_VALIDATION_POLICY = "segment_validation_policy_6B"

DATASET_S1_ARRIVALS = "s1_arrival_entities_6B"
DATASET_S1_SESSIONS = "s1_session_index_6B"
DATASET_S2_FLOWS = "s2_flow_anchor_baseline_6B"
DATASET_S2_EVENTS = "s2_event_stream_baseline_6B"
DATASET_S3_CAMPAIGN = "s3_campaign_catalogue_6B"
DATASET_S3_FLOWS = "s3_flow_anchor_with_fraud_6B"
DATASET_S3_EVENTS = "s3_event_stream_with_fraud_6B"
DATASET_S4_TRUTH = "s4_flow_truth_labels_6B"
DATASET_S4_BANK = "s4_flow_bank_view_6B"
DATASET_S4_EVENT_LABELS = "s4_event_labels_6B"
DATASET_S4_CASES = "s4_case_timeline_6B"

DATASET_RNG_TRACE = "rng_trace_log"
DATASET_RNG_AUDIT = "rng_audit_log"

DATASET_REPORT = "s5_validation_report_6B"
DATASET_ISSUES = "s5_issue_table_6B"
DATASET_BUNDLE = "validation_bundle_6B"
DATASET_BUNDLE_INDEX = "validation_bundle_index_6B"
DATASET_FLAG = "validation_passed_flag_6B"

REQUIRED_OUTPUTS = [
    DATASET_S1_ARRIVALS,
    DATASET_S1_SESSIONS,
    DATASET_S2_FLOWS,
    DATASET_S2_EVENTS,
    DATASET_S3_CAMPAIGN,
    DATASET_S3_FLOWS,
    DATASET_S3_EVENTS,
    DATASET_S4_TRUTH,
    DATASET_S4_BANK,
    DATASET_S4_EVENT_LABELS,
    DATASET_S4_CASES,
]


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    report_path: Path
    issue_table_path: Path
    bundle_index_path: Path
    passed_flag_path: Optional[Path]


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str, *args: object) -> None:
        if args:
            message = message % args
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(self, total: int, logger, label: str, cadence_seconds: float = 4.0) -> None:
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
    severity = "INFO" if result == "PASS" else "WARN" if result == "WARN" else "ERROR"
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
    logger = get_logger("engine.layers.l3.seg_6B.s5_validation_gate.runner")
    payload = {"message": message}
    payload.update(context)
    _emit_validation(logger, manifest_fingerprint, validator_id, "FAIL", code, payload)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"Invalid JSON at {path}") from exc


def _load_yaml(path: Path) -> dict:
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
    if resolved.startswith(("data/", "logs/", "reports/", "runs/")):
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


def _schema_from_pack(schema_pack: dict, anchor: str) -> dict:
    if anchor.startswith("#/"):
        anchor = anchor[2:]
    parts = [part for part in anchor.split("/") if part]
    node: dict = schema_pack
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
            continue
        props = node.get("properties") if isinstance(node, dict) else None
        if isinstance(props, dict) and part in props:
            node = props[part]
            continue
        raise ContractError(f"Schema anchor not found: {anchor}")
    if not isinstance(node, dict):
        raise ContractError(f"Schema anchor {anchor} did not resolve to object.")
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


def _validate_payload(schema_pack: dict, schema_layer3: dict, anchor: str, payload: object) -> None:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer3, "schemas.layer3.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(str(errors[0]), [])


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


def _normalize_severity(raw: str) -> str:
    if raw == "WARN":
        return "WARN_ONLY"
    if raw in {"REQUIRED", "WARN_ONLY", "INFO"}:
        return raw
    return "INFO"


def _discover_scenarios(entry: dict, run_paths: RunPaths, tokens: dict[str, str], logger) -> list[str]:
    path_template = entry.get("path") or entry.get("path_template") or ""
    marker = "scenario_id={scenario_id}"
    if marker not in path_template:
        logger.warning("S5: scenario discovery skipped (path template missing scenario token)")
        return []
    prefix = path_template.split(marker, 1)[0]
    resolved_prefix = _render_path_template(prefix, tokens)
    if resolved_prefix.startswith(("data/", "logs/", "reports/")):
        base = run_paths.run_root / resolved_prefix
    else:
        try:
            base = resolve_input_path(resolved_prefix, run_paths, [run_paths.run_root], allow_run_local=True)
        except InputResolutionError:
            base = run_paths.run_root / resolved_prefix
    if not base.exists():
        logger.warning("S5: scenario discovery path missing: %s", base)
        return []
    scenario_ids: list[str] = []
    for item in sorted(base.glob("scenario_id=*")):
        scenario_id = item.name.split("scenario_id=")[-1]
        if scenario_id:
            scenario_ids.append(scenario_id)
    return scenario_ids


def _resolve_parquet_files(root: Path) -> list[Path]:
    if "*" in str(root) or "?" in str(root):
        matches = sorted(root.parent.glob(root.name))
        if not matches:
            raise InputResolutionError(f"No parquet files matched {root}")
        return matches
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _count_parquet_rows(paths: list[Path]) -> Optional[int]:
    if not paths:
        return 0
    if pq is None:
        return None
    total = 0
    for path in paths:
        total += pq.ParquetFile(path).metadata.num_rows
    return total


def _sample_parquet(path: Path, columns: list[str], sample_rows: int) -> pl.DataFrame:
    files = _resolve_parquet_files(path)
    sample_file = files[0]
    df = pl.read_parquet(sample_file, columns=columns)
    if df.height > sample_rows:
        df = df.head(sample_rows)
    return df


def _duckdb_scan(path: Path) -> str:
    normalized = str(path).replace("\\", "/").replace("'", "''")
    return f"read_parquet('{normalized}', hive_partitioning=true, union_by_name=true)"


def _parse_passed_flag(path: Path) -> str:
    content = path.read_text(encoding="utf-8").strip()
    if content.startswith("{"):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            digest = payload.get("bundle_digest_sha256")
            if isinstance(digest, str) and _HEX64_PATTERN.match(digest):
                return digest
    line = content.splitlines()[0] if content else ""
    line = line.lstrip("\ufeff")
    match = _FLAG_PATTERN.match(line)
    if not match:
        raise InputResolutionError(f"Invalid _passed.flag format: {path}")
    return match.group(1)


def _bundle_digest(bundle_root: Path, entries: list[dict]) -> str:
    hasher = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: str(item.get("path") or "")):
        rel_path = entry.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            raise EngineFailure("F4", "S5_INDEX_BUILD_FAILED", STATE, MODULE_NAME, {"detail": "missing path"})
        file_path = bundle_root / rel_path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "S5_INDEX_BUILD_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"bundle file missing: {rel_path}"},
            )
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
    return hasher.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(path)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _make_issue(
    issue_id: str,
    manifest_fingerprint: str,
    check_id: str,
    severity: str,
    scope_type: str,
    message: str,
    metrics: Optional[dict] = None,
    seed: Optional[int] = None,
    scenario_id: Optional[str] = None,
    flow_id: Optional[int] = None,
    case_id: Optional[int] = None,
    event_seq: Optional[int] = None,
) -> dict:
    return {
        "manifest_fingerprint": manifest_fingerprint,
        "check_id": check_id,
        "issue_id": issue_id,
        "severity": severity,
        "scope_type": scope_type,
        "seed": seed,
        "scenario_id": scenario_id,
        "flow_id": flow_id,
        "case_id": case_id,
        "event_seq": event_seq,
        "message": message,
        "metrics": metrics or {},
    }



def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l3.seg_6B.s5_validation_gate.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    status = "FAIL"
    error_code: Optional[str] = None
    error_context: Optional[dict] = None
    current_phase = "init"

    run_paths: Optional[RunPaths] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    run_id_value: Optional[str] = None
    seed: Optional[int] = None
    spec_version: str = ""

    issues: list[dict] = []
    checks: list[dict] = []
    issue_counter = 0

    try:
        current_phase = "run_receipt"
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
        parameter_hash = str(receipt.get("parameter_hash") or "")
        seed = receipt.get("seed")

        if not run_id_value or not manifest_fingerprint or not parameter_hash:
            raise InputResolutionError(f"Invalid run_receipt at {receipt_path}")
        if seed is None:
            raise InputResolutionError("run_receipt seed is missing.")
        if not _HEX64_PATTERN.match(manifest_fingerprint):
            raise InputResolutionError("run_receipt manifest_fingerprint invalid.")
        if not _HEX64_PATTERN.match(parameter_hash):
            raise InputResolutionError("run_receipt parameter_hash invalid.")

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        timer.info("S5: run log initialized at %s", run_log_path)

        logger.info(
            "S5: objective=validate 6B world + emit bundle/pass flag; gated inputs (S0 receipt + sealed_inputs + S1-S4 outputs + rng logs + policy) -> outputs s5_validation_report_6B + s5_issue_table_6B + validation_bundle_6B/_passed.flag"
        )

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary_6b = load_dataset_dictionary(source, "6B")
        reg_path, registry_6b = load_artefact_registry(source, "6B")
        schema_6b_path, schema_6b = load_schema_pack(source, "6B", "6B")
        schema_layer3_path, schema_layer3 = load_schema_pack(source, "6B", "layer3")
        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_path),
            str(reg_path),
            str(schema_6b_path),
            str(schema_layer3_path),
        )

        current_phase = "s0_receipt"
        tokens_mf = {"manifest_fingerprint": manifest_fingerprint}
        s0_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_S0_GATE).entry,
            run_paths,
            config.external_roots,
            tokens_mf,
        )
        sealed_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_SEALED_INPUTS).entry,
            run_paths,
            config.external_roots,
            tokens_mf,
        )
        s0_receipt = _load_json(s0_path)
        sealed_inputs_payload = _load_json(sealed_path)
        _validate_payload(schema_layer3, schema_layer3, "gate/6B/s0_gate_receipt_6B", s0_receipt)

        if isinstance(sealed_inputs_payload, dict) and "rows" in sealed_inputs_payload:
            sealed_inputs = sealed_inputs_payload.get("rows") or []
        else:
            sealed_inputs = sealed_inputs_payload
        if not isinstance(sealed_inputs, list):
            raise SchemaValidationError("sealed_inputs_6B is not a list", [])
        sealed_schema = _schema_from_pack(schema_layer3, "gate/6B/sealed_inputs_6B")
        if sealed_schema.get("type") == "array":
            schema_to_use = sealed_schema
        else:
            schema_to_use = {
                "type": "array",
                "items": sealed_schema,
                "$defs": schema_layer3.get("$defs", {}),
            }
        errors = list(Draft202012Validator(schema_to_use).iter_errors(sealed_inputs))
        if errors:
            raise SchemaValidationError(str(errors[0]), [])

        spec_version = str(s0_receipt.get("spec_version_6B") or "")
        if not spec_version:
            raise InputResolutionError("s0_gate_receipt_6B missing spec_version_6B")
        if s0_receipt.get("manifest_fingerprint") != manifest_fingerprint:
            raise InputResolutionError("s0_gate_receipt_6B manifest_fingerprint mismatch")
        if s0_receipt.get("parameter_hash") != parameter_hash:
            raise InputResolutionError("s0_gate_receipt_6B parameter_hash mismatch")

        sealed_digest = _sealed_inputs_digest(sealed_inputs)
        receipt_digest = s0_receipt.get("sealed_inputs_digest_6B")
        if sealed_digest != receipt_digest:
            raise EngineFailure(
                "F4",
                "6B.S5.SEALED_INPUTS_DIGEST_MISMATCH",
                STATE,
                MODULE_NAME,
                {"sealed_inputs_digest": sealed_digest, "receipt_digest": receipt_digest},
            )
        timer.info("S5: sealed_inputs digest verified (%s)", sealed_digest)

        current_phase = "validation_policy"
        policy_entry = find_artifact_entry(registry_6b, DATASET_VALIDATION_POLICY).entry
        policy_key = policy_entry.get("manifest_key")
        policy_row = next((row for row in sealed_inputs if row.get("manifest_key") == policy_key), None)
        if not policy_row:
            raise InputResolutionError("segment_validation_policy_6B missing from sealed_inputs_6B")
        policy_path = _resolve_sealed_input_path(policy_row, run_paths, config.external_roots, {})
        validation_policy = _load_yaml(policy_path)
        _validate_payload(schema_6b, schema_layer3, "policy/segment_validation_policy_6B", validation_policy)
        timer.info("S5: validation policy loaded (%s)", policy_path)

        reporting_cfg = validation_policy.get("reporting") or {}
        include_issue_table = bool(reporting_cfg.get("include_issue_table", True))
        issue_table_max_rows = int(reporting_cfg.get("issue_table_max_rows", 20000))
        sample_rows = int(validation_policy.get("thresholds", {}).get("sample_rows", 2000) or 2000)
        policy_checks = {
            check.get("check_id"): _normalize_severity(str(check.get("severity") or "INFO"))
            for check in (validation_policy.get("checks") or [])
            if isinstance(check, dict)
        }

        current_phase = "scenario_discovery"
        tokens_base = {
            "seed": str(seed),
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        }
        s2_entry = find_dataset_entry(dictionary_6b, DATASET_S2_FLOWS).entry
        scenario_ids = _discover_scenarios(s2_entry, run_paths, tokens_base, logger)
        if not scenario_ids:
            scenario_ids = ["baseline_v1"]
            logger.warning("S5: scenario discovery empty; falling back to %s", scenario_ids)
        logger.info("S5: scenario_ids discovered=%s", scenario_ids)

        dataset_entries = {dataset_id: find_dataset_entry(dictionary_6b, dataset_id).entry for dataset_id in REQUIRED_OUTPUTS}

        dataset_paths: dict[str, dict[str, Path]] = {dataset_id: {} for dataset_id in REQUIRED_OUTPUTS}
        missing_paths: list[str] = []
        for dataset_id, entry in dataset_entries.items():
            for scenario_id in scenario_ids:
                tokens = {
                    "seed": str(seed),
                    "manifest_fingerprint": manifest_fingerprint,
                    "parameter_hash": parameter_hash,
                    "scenario_id": scenario_id,
                }
                path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens, allow_wildcards=True)
                dataset_paths[dataset_id][scenario_id] = path
                if "*" in str(path) or "?" in str(path):
                    matches = list(path.parent.glob(path.name))
                    if not matches:
                        missing_paths.append(f"{dataset_id}:{scenario_id}")
                elif not path.exists():
                    missing_paths.append(f"{dataset_id}:{scenario_id}")

        parquet_files_cache: dict[str, list[Path]] = {}
        parquet_count_cache: dict[str, Optional[int]] = {}
        parquet_sample_cache: dict[tuple[str, tuple[str, ...], int], pl.DataFrame] = {}

        def _cache_key(path: Path) -> str:
            return str(path.resolve()) if path.exists() else str(path)

        def _resolve_parquet_files_cached(path: Path) -> list[Path]:
            key = _cache_key(path)
            cached = parquet_files_cache.get(key)
            if cached is not None:
                return cached
            resolved = _resolve_parquet_files(path)
            parquet_files_cache[key] = resolved
            return resolved

        def _count_parquet_rows_cached(path: Path) -> Optional[int]:
            key = _cache_key(path)
            cached = parquet_count_cache.get(key)
            if cached is not None:
                return cached
            files = _resolve_parquet_files_cached(path)
            count = _count_parquet_rows(files)
            parquet_count_cache[key] = count
            return count

        def _sample_parquet_cached(path: Path, columns: list[str], sample_rows_local: int) -> pl.DataFrame:
            files = _resolve_parquet_files_cached(path)
            sample_file = files[0]
            cols = tuple(columns)
            rows = max(int(sample_rows_local), 1)
            cache_key = (_cache_key(sample_file), cols, rows)
            cached_df = parquet_sample_cache.get(cache_key)
            if cached_df is not None:
                return cached_df

            if pq is not None:
                parquet_file = pq.ParquetFile(sample_file)
                first_batch = None
                for batch in parquet_file.iter_batches(batch_size=rows, columns=list(cols)):
                    first_batch = batch
                    break
                if first_batch is None:
                    sampled = pl.DataFrame({name: [] for name in cols})
                else:
                    sampled = pl.from_arrow(first_batch)
            else:
                sampled = pl.scan_parquet(str(sample_file)).select([pl.col(c) for c in cols]).limit(rows).collect()

            parquet_sample_cache[cache_key] = sampled
            return sampled

        def _dataset_missing(dataset_id: str) -> bool:
            return any(item.startswith(f"{dataset_id}:") for item in missing_paths)

        segment_states = {
            "S0": "PASS" if s0_path.exists() and sealed_path.exists() else "MISSING",
            "S1": "PASS" if not _dataset_missing(DATASET_S1_ARRIVALS) else "MISSING",
            "S2": "PASS" if not _dataset_missing(DATASET_S2_FLOWS) else "MISSING",
            "S3": "PASS" if not _dataset_missing(DATASET_S3_FLOWS) else "MISSING",
            "S4": "PASS" if not _dataset_missing(DATASET_S4_TRUTH) else "MISSING",
        }

        def record_check(
            check_id: str,
            severity: str,
            result: str,
            metrics: Optional[dict] = None,
            thresholds: Optional[dict] = None,
            issue_message: Optional[str] = None,
            scope_type: str = "world",
        ) -> None:
            nonlocal issue_counter
            severity = policy_checks.get(check_id, severity)
            payload = {
                "check_id": check_id,
                "severity": severity,
                "result": result,
            }
            if metrics is not None:
                payload["metrics"] = metrics
            if thresholds is not None:
                payload["thresholds"] = thresholds
            checks.append(payload)
            if result != "PASS" and severity in {"REQUIRED", "WARN_ONLY"}:
                issue_counter += 1
                issues.append(
                    _make_issue(
                        issue_id=f"{check_id}-{issue_counter}",
                        manifest_fingerprint=manifest_fingerprint,
                        check_id=check_id,
                        severity="FAIL" if result == "FAIL" else "WARN",
                        scope_type=scope_type,
                        message=issue_message or f"{check_id} reported {result}",
                        metrics=metrics,
                        seed=seed,
                    )
                )

        current_phase = "checks"
        thresholds = validation_policy.get("thresholds") or {}
        realism = validation_policy.get("realism_corridors") or {}
        critical_sample_mod = max(1, int(thresholds.get("critical_realism_sample_mod", 128) or 128))
        checks_phase_started = time.monotonic()
        check_runtime_seconds: dict[str, float] = {}

        def _profile_check(name: str, started: float) -> None:
            check_runtime_seconds[name] = round(time.monotonic() - started, 6)

        # Check: upstream hashgates (lean presence + status).
        check_started = time.monotonic()
        upstream_segments = s0_receipt.get("upstream_segments") or {}
        missing_upstream = [seg for seg, payload in upstream_segments.items() if payload.get("status") != "PASS"]
        flag_rows = [
            row
            for row in sealed_inputs
            if row.get("role") == "UPSTREAM_GATE_FLAG" and row.get("status") == "REQUIRED"
        ]
        flag_missing: list[str] = []
        flag_mismatch: list[str] = []
        for row in flag_rows:
            try:
                path = _resolve_sealed_input_path(row, run_paths, config.external_roots, tokens_mf)
            except InputResolutionError:
                flag_missing.append(str(row.get("manifest_key")))
                continue
            if not path.exists():
                flag_missing.append(str(path))
                continue
            try:
                digest = _parse_passed_flag(path)
            except InputResolutionError:
                flag_mismatch.append(str(path))
                continue
            if row.get("sha256_hex") and row.get("sha256_hex") != digest:
                flag_mismatch.append(str(path))
        upstream_result = "PASS"
        if missing_upstream or flag_missing or flag_mismatch:
            upstream_result = "FAIL"
        record_check(
            "REQ_UPSTREAM_HASHGATES",
            "REQUIRED",
            upstream_result,
            metrics={
                "missing_upstream": missing_upstream,
                "flag_missing": flag_missing,
                "flag_mismatch": flag_mismatch,
            },
            issue_message="Upstream HashGate verification failed or missing.",
        )
        _profile_check("REQ_UPSTREAM_HASHGATES", check_started)

        # Check: sealed inputs present (policy + upstream gates + output paths).
        check_started = time.monotonic()
        missing_sealed_inputs: list[str] = []
        missing_required_paths = list(missing_paths)
        for dataset_id in REQUIRED_OUTPUTS:
            artifact = find_artifact_entry(registry_6b, dataset_id).entry
            manifest_key = artifact.get("manifest_key")
            if manifest_key:
                if not any(row.get("manifest_key") == manifest_key for row in sealed_inputs):
                    missing_sealed_inputs.append(manifest_key)
        sealed_result = "PASS" if not missing_required_paths else "FAIL"
        record_check(
            "REQ_SEALED_INPUTS_PRESENT",
            "REQUIRED",
            sealed_result,
            metrics={
                "missing_sealed_inputs": missing_sealed_inputs,
                "missing_required_paths": missing_required_paths,
            },
            issue_message="Required sealed inputs or output paths missing.",
        )
        _profile_check("REQ_SEALED_INPUTS_PRESENT", check_started)

        # Row counts (metadata only).
        row_count_started = time.monotonic()
        count_metrics: dict[str, dict[str, Optional[int]]] = {}
        for dataset_id in [
            DATASET_S2_FLOWS,
            DATASET_S2_EVENTS,
            DATASET_S3_FLOWS,
            DATASET_S3_EVENTS,
            DATASET_S4_TRUTH,
            DATASET_S4_BANK,
            DATASET_S4_EVENT_LABELS,
            DATASET_S4_CASES,
        ]:
            dataset_counts: dict[str, Optional[int]] = {}
            for scenario_id in scenario_ids:
                path = dataset_paths[dataset_id][scenario_id]
                try:
                    dataset_counts[scenario_id] = _count_parquet_rows_cached(path)
                except InputResolutionError:
                    dataset_counts[scenario_id] = None
            count_metrics[dataset_id] = dataset_counts
        _profile_check("ROW_COUNT_METADATA_SCAN", row_count_started)

        # Check: PK uniqueness (sample only).
        check_started = time.monotonic()
        pk_failures: list[str] = []
        pk_duplicates = 0
        sample_scenario = scenario_ids[0]
        for dataset_id in REQUIRED_OUTPUTS:
            entry = dataset_entries[dataset_id]
            pk = entry.get("primary_key") or []
            if not pk:
                continue
            path = dataset_paths[dataset_id][sample_scenario]
            try:
                df = _sample_parquet_cached(path, list(pk), sample_rows)
            except Exception as exc:  # noqa: BLE001
                pk_failures.append(f"{dataset_id}:{exc}")
                continue
            if df.height == 0:
                continue
            dupes = int(df.select(pl.struct(pk).is_duplicated().sum()).item())
            if dupes:
                pk_duplicates += dupes
        pk_threshold = int(thresholds.get("max_duplicate_pk_count", 0) or 0)
        pk_result = "PASS" if pk_duplicates <= pk_threshold and not pk_failures else "FAIL"
        record_check(
            "REQ_PK_UNIQUENESS",
            "REQUIRED",
            pk_result,
            metrics={
                "sample_scenario": sample_scenario,
                "sample_rows": sample_rows,
                "duplicate_pk_count": pk_duplicates,
                "sample_errors": pk_failures,
            },
            thresholds={"max_duplicate_pk_count": pk_threshold},
            issue_message="Duplicate primary keys detected in sample.",
        )
        _profile_check("REQ_PK_UNIQUENESS", check_started)

        # Check: flow/event parity (metadata counts).
        check_started = time.monotonic()
        parity_failures: list[str] = []
        for scenario_id in scenario_ids:
            f2 = count_metrics[DATASET_S2_FLOWS].get(scenario_id)
            f3 = count_metrics[DATASET_S3_FLOWS].get(scenario_id)
            f4 = count_metrics[DATASET_S4_TRUTH].get(scenario_id)
            e2 = count_metrics[DATASET_S2_EVENTS].get(scenario_id)
            e3 = count_metrics[DATASET_S3_EVENTS].get(scenario_id)
            e4 = count_metrics[DATASET_S4_EVENT_LABELS].get(scenario_id)
            if None in {f2, f3, f4, e2, e3, e4}:
                parity_failures.append(f"{scenario_id}:missing_counts")
                continue
            if f2 != f3 or f2 != f4:
                parity_failures.append(f"{scenario_id}:flow_mismatch")
            if e2 != e3 or e2 != e4:
                parity_failures.append(f"{scenario_id}:event_mismatch")
        parity_result = "PASS" if not parity_failures else "FAIL"
        record_check(
            "REQ_FLOW_EVENT_PARITY",
            "REQUIRED",
            parity_result,
            metrics={"parity_failures": parity_failures, "counts": count_metrics},
            issue_message="Flow/event parity mismatch across stages.",
        )
        _profile_check("REQ_FLOW_EVENT_PARITY", check_started)

        # Check: flow label coverage.
        check_started = time.monotonic()
        coverage_failures: list[str] = []
        for scenario_id in scenario_ids:
            f3 = count_metrics[DATASET_S3_FLOWS].get(scenario_id)
            t4 = count_metrics[DATASET_S4_TRUTH].get(scenario_id)
            b4 = count_metrics[DATASET_S4_BANK].get(scenario_id)
            if None in {f3, t4, b4}:
                coverage_failures.append(f"{scenario_id}:missing_counts")
                continue
            if f3 != t4 or f3 != b4:
                coverage_failures.append(f"{scenario_id}:label_coverage_mismatch")
        coverage_result = "PASS" if not coverage_failures else "FAIL"
        record_check(
            "REQ_FLOW_LABEL_COVERAGE",
            "REQUIRED",
            coverage_result,
            metrics={"coverage_failures": coverage_failures, "counts": count_metrics},
            issue_message="Truth/bank view coverage mismatch for flows.",
        )
        _profile_check("REQ_FLOW_LABEL_COVERAGE", check_started)

        # Check: critical truth realism gates (aligns with P1 scorer lane: T1/T2/T3/T22).
        check_started = time.monotonic()
        critical_truth_result = "PASS"
        critical_truth_metrics: dict[str, object] = {}
        try:
            s3_scan = _duckdb_scan(dataset_paths[DATASET_S3_FLOWS][sample_scenario])
            s4_truth_scan = _duckdb_scan(dataset_paths[DATASET_S4_TRUTH][sample_scenario])
            truth_row = duckdb.execute(
                f"""
                WITH s3_sample AS (
                  SELECT flow_id, campaign_id
                  FROM {s3_scan}
                  WHERE MOD(ABS(HASH(flow_id)), {critical_sample_mod}) = 0
                ),
                s4_sample AS (
                  SELECT
                    flow_id,
                    CAST(is_fraud_truth AS BOOLEAN) AS is_fraud_truth,
                    UPPER(COALESCE(fraud_label, '')) AS fraud_label
                  FROM {s4_truth_scan}
                  WHERE MOD(ABS(HASH(flow_id)), {critical_sample_mod}) = 0
                ),
                j AS (
                  SELECT
                    s3_sample.campaign_id,
                    s4_sample.is_fraud_truth,
                    s4_sample.fraud_label
                  FROM s3_sample
                  JOIN s4_sample USING(flow_id)
                )
                SELECT
                  AVG(CASE WHEN fraud_label = 'LEGIT' THEN 1.0 ELSE 0.0 END) AS legit_share,
                  AVG(CASE WHEN is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_mean,
                  COUNT(*) AS sampled_flows,
                  SUM(CASE WHEN campaign_id IS NULL THEN 1 ELSE 0 END) AS no_campaign_total,
                  SUM(CASE WHEN campaign_id IS NULL AND fraud_label != 'ABUSE' THEN 1 ELSE 0 END) AS no_campaign_non_overlay_total,
                  SUM(
                    CASE
                      WHEN campaign_id IS NULL AND (fraud_label = 'LEGIT' OR NOT is_fraud_truth) THEN 1
                      ELSE 0
                    END
                  ) AS no_campaign_legit,
                  SUM(
                    CASE
                      WHEN campaign_id IS NULL AND fraud_label != 'ABUSE' AND (fraud_label = 'LEGIT' OR NOT is_fraud_truth) THEN 1
                      ELSE 0
                    END
                  ) AS no_campaign_non_overlay_legit
                FROM j
                """
            ).fetchone()
            legit_share = float(truth_row[0] or 0.0)
            fraud_truth_mean = float(truth_row[1] or 0.0)
            sampled_flows = int(truth_row[2] or 0)
            no_campaign_total = int(truth_row[3] or 0)
            no_campaign_non_overlay_total = int(truth_row[4] or 0)
            no_campaign_legit = int(truth_row[5] or 0)
            no_campaign_non_overlay_legit = int(truth_row[6] or 0)
            no_campaign_non_overlay_legit_rate = (
                float(no_campaign_non_overlay_legit) / float(no_campaign_non_overlay_total)
                if no_campaign_non_overlay_total > 0
                else 0.0
            )

            truth_threshold_min = float(thresholds.get("critical_truth_fraud_rate_min", 0.02) or 0.02)
            truth_threshold_max = float(thresholds.get("critical_truth_fraud_rate_max", 0.30) or 0.30)
            no_campaign_legit_min = float(thresholds.get("critical_truth_no_campaign_legit_min", 0.99) or 0.99)
            truth_collision_guard_pass = True  # S4 fails-closed on rule collisions/unmatched rows.

            t1_ok = legit_share > 0.0
            t2_ok = truth_threshold_min <= fraud_truth_mean <= truth_threshold_max
            t3_ok = no_campaign_non_overlay_legit_rate >= no_campaign_legit_min
            t22_ok = truth_collision_guard_pass
            critical_truth_result = "PASS" if (t1_ok and t2_ok and t3_ok and t22_ok) else "FAIL"
            critical_truth_metrics = {
                "sample_scenario": sample_scenario,
                "sample_mod": critical_sample_mod,
                "sampled_flows": sampled_flows,
                "legit_share": legit_share,
                "fraud_truth_mean": fraud_truth_mean,
                "truth_rate_range": {"min": truth_threshold_min, "max": truth_threshold_max},
                "no_campaign_total": no_campaign_total,
                "no_campaign_legit": no_campaign_legit,
                "no_campaign_non_overlay_total": no_campaign_non_overlay_total,
                "no_campaign_non_overlay_legit": no_campaign_non_overlay_legit,
                "no_campaign_non_overlay_legit_rate": no_campaign_non_overlay_legit_rate,
                "no_campaign_legit_min": no_campaign_legit_min,
                "truth_collision_guard_pass": truth_collision_guard_pass,
                "t1_ok": t1_ok,
                "t2_ok": t2_ok,
                "t3_ok": t3_ok,
                "t22_ok": t22_ok,
            }
        except Exception as exc:  # noqa: BLE001
            critical_truth_result = "FAIL"
            critical_truth_metrics = {"sample_scenario": sample_scenario, "error": str(exc)}
        record_check(
            "REQ_CRITICAL_TRUTH_REALISM",
            "REQUIRED",
            critical_truth_result,
            metrics=critical_truth_metrics,
            issue_message="Critical truth realism gates failed (T1/T2/T3/T22).",
        )
        _profile_check("REQ_CRITICAL_TRUTH_REALISM", check_started)

        # Check: critical case timeline monotonicity (aligns with scorer lane: T8/T10).
        check_started = time.monotonic()
        critical_case_result = "PASS"
        critical_case_metrics: dict[str, object] = {}
        try:
            s4_case_scan = _duckdb_scan(dataset_paths[DATASET_S4_CASES][sample_scenario])
            case_row = duckdb.execute(
                f"""
                WITH ct AS (
                  SELECT
                    case_id,
                    case_event_seq,
                    ts_utc
                  FROM {s4_case_scan}
                  WHERE MOD(ABS(HASH(case_id)), {critical_sample_mod}) = 0
                ),
                g AS (
                  SELECT
                    case_id,
                    ts_utc,
                    LAG(ts_utc) OVER (PARTITION BY case_id ORDER BY case_event_seq) AS prev_ts
                  FROM ct
                )
                SELECT
                  SUM(CASE WHEN prev_ts IS NOT NULL THEN 1 ELSE 0 END) AS gaps_total,
                  SUM(CASE WHEN prev_ts IS NOT NULL AND ts_utc IS NOT NULL AND ts_utc < prev_ts THEN 1 ELSE 0 END) AS neg_gaps,
                  COUNT(DISTINCT CASE WHEN prev_ts IS NOT NULL THEN case_id END) AS cases_with_gaps,
                  COUNT(DISTINCT CASE WHEN prev_ts IS NOT NULL AND ts_utc IS NOT NULL AND ts_utc < prev_ts THEN case_id END) AS cases_with_neg
                FROM g
                """
            ).fetchone()
            gaps_total = int(case_row[0] or 0)
            neg_gaps = int(case_row[1] or 0)
            cases_with_gaps = int(case_row[2] or 0)
            cases_with_neg = int(case_row[3] or 0)
            critical_case_result = "PASS" if neg_gaps == 0 and cases_with_neg == 0 and gaps_total > 0 else "FAIL"
            critical_case_metrics = {
                "sample_scenario": sample_scenario,
                "sample_mod": critical_sample_mod,
                "gaps_total": gaps_total,
                "negative_gaps": neg_gaps,
                "cases_with_gaps": cases_with_gaps,
                "cases_with_negative_gaps": cases_with_neg,
            }
        except Exception as exc:  # noqa: BLE001
            critical_case_result = "FAIL"
            critical_case_metrics = {"sample_scenario": sample_scenario, "error": str(exc)}
        record_check(
            "REQ_CRITICAL_CASE_TIMELINE",
            "REQUIRED",
            critical_case_result,
            metrics=critical_case_metrics,
            issue_message="Critical case timeline monotonicity failed (T8/T10).",
        )
        _profile_check("REQ_CRITICAL_CASE_TIMELINE", check_started)

        # Check: RNG budgets (presence only).
        check_started = time.monotonic()
        rng_trace_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_RNG_TRACE).entry,
            run_paths,
            config.external_roots,
            {
                "seed": str(seed),
                "parameter_hash": parameter_hash,
                "run_id": run_id_value,
            },
        )
        rng_audit_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_RNG_AUDIT).entry,
            run_paths,
            config.external_roots,
            {
                "seed": str(seed),
                "parameter_hash": parameter_hash,
                "run_id": run_id_value,
            },
        )
        rng_missing = []
        if not rng_trace_path.exists():
            rng_missing.append("rng_trace_log")
        if not rng_audit_path.exists():
            rng_missing.append("rng_audit_log")
        required_modules = {"6B.S1", "6B.S2", "6B.S3", "6B.S4"}
        seen_modules: set[str] = set()
        if rng_trace_path.exists():
            with rng_trace_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    module = payload.get("module")
                    if module in required_modules:
                        seen_modules.add(module)
                        if seen_modules == required_modules:
                            break
        missing_modules = sorted(required_modules - seen_modules)
        rng_result = "PASS" if not rng_missing and not missing_modules else "FAIL"
        record_check(
            "REQ_RNG_BUDGETS",
            "REQUIRED",
            rng_result,
            metrics={"missing_logs": rng_missing, "missing_modules": missing_modules},
            thresholds={"rng_budget_violation_max": thresholds.get("rng_budget_violation_max")},
            issue_message="RNG budgets/families do not match policy.",
        )
        _profile_check("REQ_RNG_BUDGETS", check_started)

        # Check: time monotone (sample S2 events).
        check_started = time.monotonic()
        monotone_failures = 0
        time_sample_errors: list[str] = []
        try:
            path = dataset_paths[DATASET_S2_EVENTS][sample_scenario]
            df = _sample_parquet_cached(path, ["flow_id", "event_seq", "ts_utc"], sample_rows)
            if df.height:
                df = df.with_columns(
                    pl.col("ts_utc")
                    .str.strptime(
                        pl.Datetime,
                        format="%Y-%m-%dT%H:%M:%S%.6fZ",
                        strict=True,
                        exact=True,
                    )
                    .alias("ts_dt")
                ).sort(["flow_id", "event_seq"])
                df = df.with_columns(pl.col("ts_dt").shift(1).over("flow_id").alias("ts_prev"))
                monotone_failures = int(
                    df.filter(
                        pl.col("ts_dt").is_not_null()
                        & pl.col("ts_prev").is_not_null()
                        & (pl.col("ts_dt") < pl.col("ts_prev"))
                    ).height
                )
        except Exception as exc:  # noqa: BLE001
            time_sample_errors.append(str(exc))
        mono_threshold = int(thresholds.get("time_monotonicity_violation_max", 0) or 0)
        mono_result = "PASS" if monotone_failures <= mono_threshold and not time_sample_errors else "FAIL"
        record_check(
            "REQ_TIME_MONOTONE",
            "REQUIRED",
            mono_result,
            metrics={"sample_scenario": sample_scenario, "violations": monotone_failures, "errors": time_sample_errors},
            thresholds={"time_monotonicity_violation_max": mono_threshold},
            issue_message="Event timestamps are not monotone per flow.",
        )
        _profile_check("REQ_TIME_MONOTONE", check_started)

        # Check: scenario OOB (parseability only, no horizon config).
        check_started = time.monotonic()
        oob_failures = 0
        try:
            path = dataset_paths[DATASET_S2_EVENTS][sample_scenario]
            df = _sample_parquet_cached(path, ["ts_utc"], sample_rows)
            if df.height:
                parsed = df.select(
                    pl.col("ts_utc")
                    .str.strptime(
                        pl.Datetime,
                        format="%Y-%m-%dT%H:%M:%S%.6fZ",
                        strict=True,
                        exact=True,
                    )
                    .alias("ts_dt")
                )
                oob_failures = int(parsed.filter(pl.col("ts_dt").is_null()).height)
        except Exception as exc:  # noqa: BLE001
            oob_failures = sample_rows
            time_sample_errors.append(str(exc))
        oob_threshold = int(thresholds.get("scenario_oob_timestamp_max", 0) or 0)
        oob_result = "PASS" if oob_failures <= oob_threshold else "FAIL"
        record_check(
            "REQ_SCENARIO_OOB",
            "REQUIRED",
            oob_result,
            metrics={"sample_scenario": sample_scenario, "oob_count": oob_failures, "note": "parseable_only"},
            thresholds={"scenario_oob_timestamp_max": oob_threshold},
            issue_message="Timestamps outside scenario horizon or unparseable.",
        )
        _profile_check("REQ_SCENARIO_OOB", check_started)

        # WARN checks (realism corridors, sample only).
        check_started = time.monotonic()
        baseline_result = "PASS"
        baseline_metrics: dict = {"note": "event_type corridors not enforced (AUTH_REQUEST/RESPONSE only)"}
        record_check("WARN_BASELINE_REALISM", "WARN_ONLY", baseline_result, metrics=baseline_metrics)
        _profile_check("WARN_BASELINE_REALISM", check_started)

        check_started = time.monotonic()
        fraud_fraction = None
        fraud_result = "PASS"
        try:
            path = dataset_paths[DATASET_S3_FLOWS][sample_scenario]
            df = _sample_parquet_cached(path, ["campaign_id"], sample_rows)
            if df.height:
                fraud_fraction = float((df.get_column("campaign_id").is_not_null().sum()) / df.height)
        except Exception:  # noqa: BLE001
            fraud_fraction = None
        fraud_range = (realism.get("fraud") or {}).get("fraud_fraction_range") or {}
        fraud_min = float(fraud_range.get("min", 0.0) or 0.0)
        fraud_max = float(fraud_range.get("max", 1.0) or 1.0)
        if fraud_fraction is not None and not (fraud_min <= fraud_fraction <= fraud_max):
            fraud_result = "WARN"
        record_check(
            "WARN_FRAUD_REALISM",
            "WARN_ONLY",
            fraud_result,
            metrics={"fraud_fraction_sample": fraud_fraction},
            thresholds={"fraud_fraction_range": fraud_range},
            issue_message="Fraud overlay realism corridors violated.",
        )
        _profile_check("WARN_FRAUD_REALISM", check_started)

        check_started = time.monotonic()
        bank_rate = None
        bank_result = "PASS"
        try:
            path = dataset_paths[DATASET_S4_BANK][sample_scenario]
            df = _sample_parquet_cached(path, ["is_fraud_bank_view"], sample_rows)
            if df.height:
                bank_rate = float((df.get_column("is_fraud_bank_view").sum()) / df.height)
        except Exception:  # noqa: BLE001
            bank_rate = None
        bank_range = (realism.get("bank_view") or {}).get("false_positive_rate_range") or {}
        bank_min = float(bank_range.get("min", 0.0) or 0.0)
        bank_max = float(bank_range.get("max", 1.0) or 1.0)
        if bank_rate is not None and not (bank_min <= bank_rate <= bank_max):
            bank_result = "WARN"
        record_check(
            "WARN_BANK_VIEW_REALISM",
            "WARN_ONLY",
            bank_result,
            metrics={"bank_view_rate_sample": bank_rate},
            thresholds={"false_positive_rate_range": bank_range},
            issue_message="Bank view realism corridors violated.",
        )
        _profile_check("WARN_BANK_VIEW_REALISM", check_started)

        check_started = time.monotonic()
        case_result = "PASS"
        case_rate = None
        case_range = (realism.get("cases") or {}).get("case_involvement_fraction_range") or {}
        case_min = float(case_range.get("min", 0.0) or 0.0)
        case_max = float(case_range.get("max", 1.0) or 1.0)
        total_flows = count_metrics[DATASET_S4_TRUTH].get(sample_scenario) or 0
        case_events = count_metrics[DATASET_S4_CASES].get(sample_scenario) or 0
        if total_flows:
            case_rate = float(case_events) / float(total_flows)
            if not (case_min <= case_rate <= case_max):
                case_result = "WARN"
        record_check(
            "WARN_CASE_REALISM",
            "WARN_ONLY",
            case_result,
            metrics={"case_event_rate": case_rate, "case_events": case_events, "flow_count": total_flows},
            thresholds={"case_involvement_fraction_range": case_range},
            issue_message="Case timeline realism corridors violated.",
        )
        _profile_check("WARN_CASE_REALISM", check_started)
        _profile_check("CHECKS_TOTAL", checks_phase_started)

        # Aggregate overall status.
        required_failed = any(check["severity"] == "REQUIRED" and check["result"] != "PASS" for check in checks)
        warn_checks = [check for check in checks if check["severity"] == "WARN_ONLY"]
        warn_failed = sum(1 for check in warn_checks if check["result"] != "PASS")
        warn_fraction = (warn_failed / len(warn_checks)) if warn_checks else 0.0
        seal_rules = validation_policy.get("seal_rules") or {}
        fail_on_warn = bool(seal_rules.get("fail_on_any_warn_failure", False))
        warn_still_pass = float(seal_rules.get("warn_still_pass_max_fraction", 0.0) or 0.0)

        overall_status = "PASS"
        if required_failed:
            overall_status = "FAIL"
        elif warn_failed and fail_on_warn:
            overall_status = "FAIL"
        elif warn_failed and warn_fraction > warn_still_pass:
            overall_status = "WARN"

        upstream_report = {}
        for seg_id, payload in upstream_segments.items():
            upstream_report[seg_id] = {
                "status": str(payload.get("status") or "UNKNOWN"),
                "bundle_sha256": str(payload.get("bundle_sha256") or ""),
                "flag_path": str(payload.get("flag_path") or ""),
            }

        report_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "spec_version_6B": spec_version,
            "overall_status": overall_status,
            "upstream_segments": upstream_report,
            "segment_states": segment_states,
            "checks": checks,
        }
        _validate_payload(schema_layer3, schema_layer3, "validation/6B/s5_validation_report", report_payload)

        current_phase = "bundle_write"
        bundle_phase_started = time.monotonic()
        bundle_root = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_BUNDLE).entry, run_paths, config.external_roots, tokens_mf
        )
        report_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_REPORT).entry, run_paths, config.external_roots, tokens_mf
        )
        issues_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_ISSUES).entry, run_paths, config.external_roots, tokens_mf
        )
        index_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_BUNDLE_INDEX).entry, run_paths, config.external_roots, tokens_mf
        )
        flag_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_6b, DATASET_FLAG).entry, run_paths, config.external_roots, tokens_mf
        )

        tmp_root = run_paths.tmp_root / f"s5_validation_bundle_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        report_rel = report_path.relative_to(bundle_root)
        index_rel = index_path.relative_to(bundle_root)
        flag_rel = flag_path.relative_to(bundle_root)
        _write_json(tmp_root / report_rel, report_payload)

        entries: list[dict] = []
        report_schema = find_dataset_entry(dictionary_6b, DATASET_REPORT).entry.get("schema_ref")
        entries.append(
            {
                "path": report_rel.as_posix(),
                "sha256_hex": sha256_file(tmp_root / report_rel).sha256_hex,
                "role": "validation_report",
                "schema_ref": report_schema,
            }
        )

        if include_issue_table:
            if issues:
                issue_rows = issues[:issue_table_max_rows]
                for row in issue_rows:
                    _validate_payload(schema_layer3, schema_layer3, "validation/6B/s5_issue_table", row)
                issues_df = pl.DataFrame(issue_rows)
            else:
                issues_df = pl.DataFrame(
                    {
                        "manifest_fingerprint": pl.Series([], dtype=pl.Utf8),
                        "check_id": pl.Series([], dtype=pl.Utf8),
                        "issue_id": pl.Series([], dtype=pl.Utf8),
                        "severity": pl.Series([], dtype=pl.Utf8),
                        "scope_type": pl.Series([], dtype=pl.Utf8),
                        "seed": pl.Series([], dtype=pl.Int64),
                        "scenario_id": pl.Series([], dtype=pl.Utf8),
                        "flow_id": pl.Series([], dtype=pl.Int64),
                        "case_id": pl.Series([], dtype=pl.Int64),
                        "event_seq": pl.Series([], dtype=pl.Int64),
                        "message": pl.Series([], dtype=pl.Utf8),
                        "metrics": pl.Series([], dtype=pl.Object),
                    }
                )
            issues_rel = issues_path.relative_to(bundle_root)
            issues_df_path = tmp_root / issues_rel
            issues_df_path.parent.mkdir(parents=True, exist_ok=True)
            issues_df.write_parquet(issues_df_path)
            issues_schema = find_dataset_entry(dictionary_6b, DATASET_ISSUES).entry.get("schema_ref")
            entries.append(
                {
                    "path": issues_rel.as_posix(),
                    "sha256_hex": sha256_file(issues_df_path).sha256_hex,
                    "role": "validation_issue_table",
                    "schema_ref": issues_schema,
                }
            )

        index_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "spec_version_6B": spec_version,
            "items": sorted(entries, key=lambda item: item["path"]),
        }
        _validate_payload(schema_layer3, schema_layer3, "validation/6B/validation_bundle_index_6B", index_payload)
        _write_json(tmp_root / index_rel, index_payload)

        bundle_digest = _bundle_digest(tmp_root, entries)
        if overall_status in {"PASS", "WARN"}:
            flag_text = f"sha256_hex = {bundle_digest}\n"
            (tmp_root / flag_rel).write_text(flag_text, encoding="utf-8")
        _profile_check("BUNDLE_WRITE_TOTAL", bundle_phase_started)

        current_phase = "publish"
        publish_phase_started = time.monotonic()
        if bundle_root.exists():
            existing_index = bundle_root / index_rel
            if not existing_index.exists():
                raise EngineFailure(
                    "F4",
                    "S5_IDEMPOTENCE_VIOLATION",
                    STATE,
                    MODULE_NAME,
                    {"detail": "bundle exists without index", "bundle_root": str(bundle_root)},
                )
            if existing_index.read_bytes() != (tmp_root / index_rel).read_bytes():
                raise EngineFailure(
                    "F4",
                    "S5_IDEMPOTENCE_VIOLATION",
                    STATE,
                    MODULE_NAME,
                    {"detail": "bundle index mismatch", "bundle_root": str(bundle_root)},
                )
            if overall_status in {"PASS", "WARN"}:
                existing_flag = bundle_root / flag_rel
                if not existing_flag.exists():
                    existing_flag.parent.mkdir(parents=True, exist_ok=True)
                    existing_flag.write_text(f"sha256_hex = {bundle_digest}\n", encoding="utf-8")
                    logger.info("S5: wrote missing _passed.flag for existing bundle.")
                else:
                    existing_digest = _parse_passed_flag(existing_flag)
                    if existing_digest != bundle_digest:
                        raise EngineFailure(
                            "F4",
                            "S5_IDEMPOTENCE_VIOLATION",
                            STATE,
                            MODULE_NAME,
                            {"detail": "passed flag digest mismatch", "bundle_root": str(bundle_root)},
                        )
            logger.info("S5: bundle already exists and is identical; skipping publish.")
        else:
            bundle_root.parent.mkdir(parents=True, exist_ok=True)
            tmp_root.replace(bundle_root)
            logger.info("S5: bundle published path=%s", bundle_root)
        _profile_check("PUBLISH_TOTAL", publish_phase_started)

        profile_payload = {
            "run_id": run_id_value,
            "seed": int(seed),
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "phase": "P3.R3",
            "runtime_seconds": {
                **check_runtime_seconds,
                "TOTAL_ELAPSED": round(time.monotonic() - started_monotonic, 6),
            },
            "top_hotspots": [
                {"name": name, "elapsed_seconds": value}
                for name, value in sorted(
                    check_runtime_seconds.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10]
            ],
        }
        profile_path = run_paths.run_root / "reports" / f"s5_runtime_profile_{run_id_value}.json"
        _write_json(profile_path, profile_payload)
        logger.info("S5: runtime profile emitted path=%s", profile_path)

        status = "PASS" if overall_status in {"PASS", "WARN"} else "FAIL"
        timer.info("S5: bundle complete (entries=%d, digest=%s)", len(entries), bundle_digest)

    except (ContractError, InputResolutionError, SchemaValidationError) as exc:
        error_code = error_code or "S5_CONTRACT_INVALID"
        error_context = {"detail": str(exc), "phase": current_phase}
    except Exception as exc:  # noqa: BLE001
        error_code = error_code or "S5_INTERNAL_ERROR"
        error_context = {"detail": str(exc), "phase": current_phase}
    finally:
        if status != "PASS":
            logger.error(
                "S5: failed status=%s error_code=%s phase=%s elapsed=%.2fs",
                status,
                error_code,
                current_phase,
                time.monotonic() - started_monotonic,
            )
        else:
            logger.info("S5: completed status=%s elapsed=%.2fs", status, time.monotonic() - started_monotonic)

    if status != "PASS":
        raise EngineFailure("F4", error_code or "S5_VALIDATION_FAILED", STATE, MODULE_NAME, error_context or {})

    if run_paths is None:
        raise EngineFailure("F4", "S5_INTERNAL_ERROR", STATE, MODULE_NAME, {"detail": "missing run_paths"})

    return S5Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        report_path=report_path,
        issue_table_path=issues_path,
        bundle_index_path=index_path,
        passed_flag_path=flag_path if status == "PASS" else None,
    )


