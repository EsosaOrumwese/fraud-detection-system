from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
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
from engine.core.errors import (
    ContractError,
    EngineFailure,
    HashingError,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_3A.s0_gate.runner import (
    _append_jsonl,
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _segment_state_runs_path,
)


MODULE_NAME = "3A.s6_validation"
SEGMENT = "3A"
STATE = "S6"
HEX64_ZERO = "0" * 64
TOLERANCE = 1e-12

MODULE_RNG = "3A.S3"
SUBSTREAM_LABEL = "zone_dirichlet"


@dataclass(frozen=True)
class S6Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    report_path: Path
    issue_table_path: Path
    receipt_path: Path


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(self, total: int | None, logger, label: str) -> None:
        self._total = None if total is None else max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if (
            now - self._last_log < 0.5
            and self._total is not None
            and self._processed < self._total
        ):
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        if self._total is None:
            self._logger.info(
                "%s %s (elapsed=%.2fs, rate=%.2f/s)",
                self._label,
                self._processed,
                elapsed,
                rate,
            )
            return
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


def _emit_event(logger, event: str, manifest_fingerprint: Optional[str], severity: str, **fields: object) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint or "unknown",
        "severity": severity,
        "timestamp_utc": utc_now_rfc3339_micro(),
    }
    payload.update(fields)
    message = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    if severity == "ERROR":
        logger.error("%s %s", event, message)
    elif severity == "WARN":
        logger.warning("%s %s", event, message)
    elif severity == "DEBUG":
        logger.debug("%s %s", event, message)
    else:
        logger.info("%s %s", event, message)


def _emit_validation(
    logger,
    manifest_fingerprint: Optional[str],
    validator_id: str,
    result: str,
    error_code: Optional[str] = None,
    detail: Optional[object] = None,
) -> None:
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l1.seg_3A.s6_validation.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _load_sealed_inputs(path: Path) -> list[dict]:
    try:
        payload = _load_json(path)
    except (InputResolutionError, json.JSONDecodeError):
        if path.suffix.lower() == ".parquet":
            return pl.read_parquet(path).to_dicts()
        raise
    if not isinstance(payload, list):
        raise InputResolutionError("sealed_inputs_3A payload is not a list")
    return payload


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"), key=lambda path: path.relative_to(root).as_posix())
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _hash_parquet_partition(root: Path) -> tuple[str, int, int]:
    if root.is_file():
        files = [root]
    else:
        if not root.exists():
            raise InputResolutionError(f"Missing parquet directory: {root}")
        files = sorted(root.rglob("*.parquet"), key=lambda path: path.relative_to(root).as_posix())
    if not files:
        raise InputResolutionError(f"No parquet files found under {root}")
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
    return hasher.hexdigest(), total_bytes, len(files)


def _resolve_event_paths(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> list[Path]:
    path = _resolve_dataset_path(entry, run_paths, external_roots, tokens)
    if any(ch in path.name for ch in ("*", "?", "[")):
        parent = path.parent
        if not parent.exists():
            raise InputResolutionError(f"Missing log directory: {parent}")
        paths = sorted(parent.glob(path.name), key=lambda p: p.name)
        if not paths:
            raise InputResolutionError(f"No log files matched pattern: {path}")
        return paths
    if path.is_dir():
        paths = sorted(path.glob("*.jsonl"), key=lambda p: p.name)
        if not paths:
            raise InputResolutionError(f"No log files found under {path}")
        return paths
    if not path.exists():
        raise InputResolutionError(f"Missing log file: {path}")
    return [path]


def _iter_jsonl(path: Path) -> Iterable[tuple[int, dict]]:
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            payload = line.strip()
            if not payload:
                continue
            yield idx, json.loads(payload)


def _require_columns(
    df: pl.DataFrame,
    dataset_label: str,
    required: list[str],
    manifest_fingerprint: str,
) -> None:
    missing = [col for col in required if col not in df.columns]
    if not missing:
        return
    _abort(
        "E3A_S6_001_PRECONDITION_FAILED",
        "V-04",
        "dataset_columns_missing",
        {
            "component": dataset_label,
            "reason": "columns_missing",
            "missing_columns": missing,
        },
        manifest_fingerprint,
    )


def _compute_masked_alloc_digest(
    df: pl.DataFrame,
    tmp_root: Path,
    logger,
) -> tuple[str, int, int]:
    tmp_dir = tmp_root / f"s6_zone_alloc_digest_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / "part-00000.parquet"
    df.write_parquet(tmp_path, compression="zstd")
    digest, total_bytes, file_count = _hash_parquet_partition(tmp_dir)
    for path in tmp_dir.rglob("*"):
        if path.is_file():
            path.unlink()
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info(
        "S6: computed masked zone_alloc_parquet_digest (files=%d, bytes=%d)",
        file_count,
        total_bytes,
    )
    return digest, total_bytes, file_count


def _publish_json(path: Path, payload: dict, logger, label: str) -> None:
    payload_bytes = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing == payload_bytes:
            logger.info("S6: %s already exists and is identical; skipping publish.", label)
            return
        existing_obj = json.loads(existing.decode("utf-8"))
        difference_count = len(set(existing_obj.keys()) ^ set(payload.keys()))
        for key in payload:
            if key in existing_obj and existing_obj[key] != payload[key]:
                difference_count += 1
        raise EngineFailure(
            "F4",
            "E3A_S6_006_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {
                "artefact": label,
                "difference_kind": "field_value",
                "difference_count": int(difference_count),
                "path": str(path),
            },
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload_bytes)


def _publish_parquet_file(path: Path, df: pl.DataFrame, logger, label: str, sort_cols: list[str]) -> None:
    if path.exists():
        existing_df = pl.read_parquet(path)
        existing_sorted = existing_df.sort(sort_cols) if existing_df.height else existing_df
        incoming_sorted = df.sort(sort_cols) if df.height else df
        if incoming_sorted.equals(existing_sorted):
            logger.info("S6: %s already exists and is identical; skipping publish.", label)
            return
        difference_kind = "row_set"
        difference_count = abs(incoming_sorted.height - existing_sorted.height)
        if incoming_sorted.height == existing_sorted.height and incoming_sorted.columns == existing_sorted.columns:
            diff_left = incoming_sorted.join(existing_sorted, on=incoming_sorted.columns, how="anti")
            diff_right = existing_sorted.join(incoming_sorted, on=existing_sorted.columns, how="anti")
            difference_kind = "field_value"
            difference_count = diff_left.height + diff_right.height
        raise EngineFailure(
            "F4",
            "E3A_S6_006_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {
                "artefact": label,
                "difference_kind": difference_kind,
                "difference_count": int(difference_count),
                "path": str(path),
            },
        )
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    df.write_parquet(tmp_path, compression="zstd")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(path)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _error_class_label(error_code: Optional[str]) -> Optional[str]:
    mapping = {
        "E3A_S6_001_PRECONDITION_FAILED": "PRECONDITION",
        "E3A_S6_002_CATALOGUE_MALFORMED": "CATALOGUE",
        "E3A_S6_003_CHECK_EXECUTION_FAILED": "CHECK_EXECUTION",
        "E3A_S6_004_REPORT_SCHEMA_INVALID": "REPORT_SCHEMA",
        "E3A_S6_005_RECEIPT_INCONSISTENT": "RECEIPT_INCONSISTENT",
        "E3A_S6_006_IMMUTABILITY_VIOLATION": "IMMUTABILITY",
        "E3A_S6_007_INFRASTRUCTURE_IO_ERROR": "INFRASTRUCTURE",
    }
    if not error_code:
        return None
    return mapping.get(error_code)


def _sha256_concat_hex(parts: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("ascii"))
    return hasher.hexdigest()


def _json_digest(payload: dict) -> str:
    payload_bytes = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload_bytes).hexdigest()


def _select_trace_row(rows: Iterable[tuple[dict, str]]) -> tuple[Optional[dict], Optional[str]]:
    best_row: Optional[dict] = None
    best_source: Optional[str] = None
    best_key: Optional[tuple] = None
    for row, source in rows:
        key = (
            int(row.get("events_total") or 0),
            int(row.get("blocks_total") or 0),
            int(row.get("draws_total") or 0),
            int(row.get("rng_counter_after_hi") or 0),
            int(row.get("rng_counter_after_lo") or 0),
            str(row.get("ts_utc") or ""),
            source,
        )
        if best_key is None or key > best_key:
            best_key = key
            best_row = row
            best_source = source
    return best_row, best_source


def _select_trace_row_by_counter(rows: Iterable[tuple[dict, str]]) -> tuple[Optional[dict], Optional[str]]:
    best_row: Optional[dict] = None
    best_source: Optional[str] = None
    best_key: Optional[tuple] = None
    for row, source in rows:
        key = (
            int(row.get("rng_counter_after_hi") or 0),
            int(row.get("rng_counter_after_lo") or 0),
            str(row.get("ts_utc") or ""),
            int(row.get("events_total") or 0),
            int(row.get("blocks_total") or 0),
            int(row.get("draws_total") or 0),
            source,
        )
        if best_key is None or key > best_key:
            best_key = key
            best_row = row
            best_source = source
    return best_row, best_source


def _add_issue(
    issue_rows: list[dict],
    manifest_fingerprint: str,
    check_id: str,
    issue_code: str,
    severity: str,
    message: str,
    merchant_id: Optional[int] = None,
    legal_country_iso: Optional[str] = None,
    tzid: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    issue_rows.append(
        {
            "manifest_fingerprint": manifest_fingerprint,
            "issue_code": issue_code,
            "check_id": check_id,
            "severity": severity,
            "message": message,
            "merchant_id": merchant_id,
            "legal_country_iso": legal_country_iso,
            "tzid": tzid,
            "details": details,
        }
    )


def run_s6(config: EngineConfig, run_id: Optional[str] = None) -> S6Result:
    logger = get_logger("engine.layers.l1.seg_3A.s6_validation.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    overall_status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    seed: Optional[int] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    run_id_value: Optional[str] = None

    report_path: Optional[Path] = None
    issue_table_path: Optional[Path] = None
    receipt_path: Optional[Path] = None
    report_catalog_path: Optional[str] = None
    issue_catalog_path: Optional[str] = None
    receipt_catalog_path: Optional[str] = None

    s6_version: Optional[str] = None
    report_digest = ""
    issue_digest = ""
    routing_universe_hash = ""

    counts = {
        "pairs_total": 0,
        "pairs_escalated": 0,
        "s3_pairs": 0,
        "s4_pairs": 0,
        "s3_rows": 0,
        "s4_rows": 0,
        "zone_alloc_rows": 0,
        "issues_total": 0,
        "issues_error": 0,
        "issues_warn": 0,
    }

    start_logged = False
    current_phase = "run_receipt"

    try:
        _receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        seed = int(receipt.get("seed") or 0)
        parameter_hash = str(receipt.get("parameter_hash") or "")
        manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
        if not run_id_value or not parameter_hash or not manifest_fingerprint:
            raise InputResolutionError("run_receipt missing run_id, parameter_hash, or manifest_fingerprint.")

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        timer.info(f"S6: run log initialized at {run_log_path}")

        logger.info(
            "S6: objective=validate S0-S5 invariants and RNG accounting; outputs=report, issue_table, receipt"
        )

        tokens = {
            "seed": str(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id_value,
        }

        _emit_event(
            logger,
            "STATE_START",
            manifest_fingerprint,
            "INFO",
            layer="layer1",
            segment=SEGMENT,
            state=STATE,
            parameter_hash=parameter_hash,
            seed=seed,
            run_id=run_id_value,
            attempt=1,
        )
        start_logged = True

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
        reg_path, registry = load_artefact_registry(source, SEGMENT)
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        timer.info("S6: contracts loaded")

        current_phase = "s0_gate"
        s0_entry = find_dataset_entry(dictionary, "s0_gate_receipt_3A").entry
        try:
            s0_path = _resolve_dataset_path(s0_entry, run_paths, config.external_roots, tokens)
            s0_gate = _load_json(s0_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-01",
                "s0_gate_missing",
                {"component": "S0_GATE", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s0_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A")
        s0_errors = list(Draft202012Validator(s0_schema).iter_errors(s0_gate))
        if s0_errors:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-01",
                "s0_gate_schema_invalid",
                {"component": "S0_GATE", "reason": "schema_invalid", "error": str(s0_errors[0])},
                manifest_fingerprint,
            )

        current_phase = "sealed_inputs"
        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_3A").entry
        try:
            sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
            sealed_inputs = _load_sealed_inputs(sealed_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_inputs_missing",
                {"component": "S0_SEALED_INPUTS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_from_pack(schema_3a, "validation/sealed_inputs_3A")
        _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
        sealed_validator = Draft202012Validator(normalize_nullable_schema(sealed_schema))
        sealed_rows: list[dict] = []
        for row in sealed_inputs:
            errors = list(sealed_validator.iter_errors(row))
            if errors:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_schema_invalid",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )
            if str(row.get("manifest_fingerprint")) != str(manifest_fingerprint):
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_identity_mismatch",
                    {
                        "component": "S0_SEALED_INPUTS",
                        "reason": "schema_invalid",
                        "row_manifest_fingerprint": row.get("manifest_fingerprint"),
                    },
                    manifest_fingerprint,
                )
            sealed_rows.append(row)

        sealed_by_id: dict[str, dict] = {}
        for row in sealed_rows:
            logical_id = str(row.get("logical_id") or "")
            if not logical_id:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_missing_logical_id",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid"},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_logical_id_duplicate",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid", "logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        sealed_policy_set = s0_gate.get("sealed_policy_set") or []
        sealed_policy_ids = {str(item.get("logical_id") or "") for item in sealed_policy_set}
        required_policies = ["zone_mixture_policy", "country_zone_alphas", "zone_floor_policy", "day_effect_policy_v1"]
        missing_policies = sorted(policy_id for policy_id in required_policies if policy_id not in sealed_policy_ids)
        if missing_policies:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_policy_set_incomplete",
                {"component": "S0_SEALED_INPUTS", "reason": "missing_policy", "missing_policies": missing_policies},
                manifest_fingerprint,
            )

        s6_entry = find_artifact_entry(registry, "s6_receipt_3A").entry
        s6_version = str(s6_entry.get("semver") or "")
        if not s6_version:
            _abort(
                "E3A_S6_002_CATALOGUE_MALFORMED",
                "V-01",
                "s6_version_missing",
                {"component": "ARTEFACT_REGISTRY", "reason": "missing_s6_version"},
                manifest_fingerprint,
            )

        current_phase = "sealed_inputs_verify"
        policy_specs = {
            "zone_mixture_policy": ("policy/zone_mixture_policy_v1", schema_3a),
            "country_zone_alphas": ("policy/country_zone_alphas_v1", schema_3a),
            "zone_floor_policy": ("policy/zone_floor_policy_v1", schema_3a),
            "day_effect_policy_v1": ("policy/day_effect_policy_v1", schema_2b),
        }
        policy_digests: dict[str, str] = {}
        for policy_id, (anchor, pack) in policy_specs.items():
            if policy_id not in sealed_by_id:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-02",
                    "sealed_policy_missing",
                    {"component": "S0_SEALED_INPUTS", "reason": "missing_policy", "logical_id": policy_id},
                    manifest_fingerprint,
                )
            sealed_row = sealed_by_id[policy_id]
            entry = find_dataset_entry(dictionary, policy_id).entry
            expected_path = _render_catalog_path(entry, tokens)
            if str(sealed_row.get("path")) != expected_path:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-02",
                    "sealed_policy_path_mismatch",
                    {"component": "S0_SEALED_INPUTS", "logical_id": policy_id, "expected": expected_path},
                    manifest_fingerprint,
                )
            policy_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            digest = sha256_file(Path(policy_path)).sha256_hex
            if str(sealed_row.get("sha256_hex")) != digest:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-02",
                    "sealed_policy_digest_mismatch",
                    {"component": "S0_SEALED_INPUTS", "logical_id": policy_id},
                    manifest_fingerprint,
                )
            policy_schema = _schema_for_payload(pack, schema_layer1, anchor)
            try:
                if policy_path.suffix.lower() in {".yaml", ".yml"}:
                    payload = _load_yaml(policy_path)
                else:
                    payload = _load_json(policy_path)
            except InputResolutionError as exc:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-02",
                    "sealed_policy_missing",
                    {"component": "S0_SEALED_INPUTS", "logical_id": policy_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
                raise
            policy_errors = list(Draft202012Validator(policy_schema).iter_errors(payload))
            if policy_errors:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-02",
                    "sealed_policy_schema_invalid",
                    {"component": "S0_SEALED_INPUTS", "logical_id": policy_id, "error": str(policy_errors[0])},
                    manifest_fingerprint,
                )
            policy_digests[policy_id] = digest

        outlet_entry = find_dataset_entry(dictionary, "outlet_catalogue").entry
        if "outlet_catalogue" not in sealed_by_id:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-02",
                "sealed_outlet_catalogue_missing",
                {"component": "S0_SEALED_INPUTS", "logical_id": "outlet_catalogue"},
                manifest_fingerprint,
            )
        outlet_sealed = sealed_by_id["outlet_catalogue"]
        outlet_catalog_path = _render_catalog_path(outlet_entry, tokens)
        if str(outlet_sealed.get("path")) != outlet_catalog_path:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-02",
                "sealed_outlet_catalogue_path_mismatch",
                {"component": "S0_SEALED_INPUTS", "expected": outlet_catalog_path},
                manifest_fingerprint,
            )
        outlet_root = _resolve_dataset_path(outlet_entry, run_paths, config.external_roots, tokens)
        outlet_digest, _, _ = _hash_parquet_partition(outlet_root)
        if str(outlet_sealed.get("sha256_hex")) != outlet_digest:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-02",
                "sealed_outlet_catalogue_digest_mismatch",
                {"component": "S0_SEALED_INPUTS", "logical_id": "outlet_catalogue"},
                manifest_fingerprint,
            )

        current_phase = "run_reports"
        run_report_schema = normalize_nullable_schema(_schema_from_pack(schema_layer1, "run_report/segment_state_run"))
        run_report_validator = Draft202012Validator(run_report_schema)
        run_reports: dict[str, dict] = {}
        for entry_id, state_label in (
            ("s1_run_report_3A", "S1"),
            ("s2_run_report_3A", "S2"),
            ("s3_run_report_3A", "S3"),
            ("s4_run_report_3A", "S4"),
            ("s5_run_report_3A", "S5"),
        ):
            report_entry = find_dataset_entry(dictionary, entry_id).entry
            report_path = _resolve_dataset_path(report_entry, run_paths, config.external_roots, tokens)
            try:
                report_payload = _load_json(report_path)
            except InputResolutionError as exc:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-03",
                    "run_report_missing",
                    {"component": entry_id, "reason": "missing", "detail": str(exc)},
                    manifest_fingerprint,
                )
            errors = list(run_report_validator.iter_errors(report_payload))
            if errors:
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-03",
                    "run_report_schema_invalid",
                    {"component": entry_id, "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )
            if str(report_payload.get("manifest_fingerprint")) != str(manifest_fingerprint):
                _abort(
                    "E3A_S6_001_PRECONDITION_FAILED",
                    "V-03",
                    "run_report_identity_mismatch",
                    {"component": entry_id, "reason": "manifest_fingerprint_mismatch"},
                    manifest_fingerprint,
                )
            run_reports[state_label] = report_payload

        current_phase = "datasets"
        s1_entry = find_dataset_entry(dictionary, "s1_escalation_queue").entry
        try:
            s1_path = _resolve_dataset_path(s1_entry, run_paths, config.external_roots, tokens)
            s1_paths = _list_parquet_paths(s1_path)
            s1_df = pl.read_parquet(s1_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "s1_escalation_missing",
                {"component": "S1_ESCALATION_QUEUE", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        # Upstream S1 already performs full schema validation. S6 keeps a strict
        # fail-closed column guard to avoid repeating expensive row-wise JSON-schema work.
        _require_columns(
            s1_df,
            "S1_ESCALATION_QUEUE",
            ["merchant_id", "legal_country_iso", "is_escalated", "site_count"],
            manifest_fingerprint,
        )

        s2_entry = find_dataset_entry(dictionary, "s2_country_zone_priors").entry
        try:
            s2_path = _resolve_dataset_path(s2_entry, run_paths, config.external_roots, tokens)
            s2_paths = _list_parquet_paths(s2_path)
            s2_df = pl.read_parquet(s2_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "s2_priors_missing",
                {"component": "S2_PRIORS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        _require_columns(
            s2_df,
            "S2_PRIORS",
            ["country_iso", "tzid", "alpha_effective"],
            manifest_fingerprint,
        )

        s3_entry = find_dataset_entry(dictionary, "s3_zone_shares").entry
        try:
            s3_path = _resolve_dataset_path(s3_entry, run_paths, config.external_roots, tokens)
            s3_paths = _list_parquet_paths(s3_path)
            s3_df = pl.read_parquet(s3_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "s3_zone_shares_missing",
                {"component": "S3_ZONE_SHARES", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        _require_columns(
            s3_df,
            "S3_ZONE_SHARES",
            ["merchant_id", "legal_country_iso", "tzid", "share_drawn"],
            manifest_fingerprint,
        )

        s4_entry = find_dataset_entry(dictionary, "s4_zone_counts").entry
        try:
            s4_path = _resolve_dataset_path(s4_entry, run_paths, config.external_roots, tokens)
            s4_paths = _list_parquet_paths(s4_path)
            s4_df = pl.read_parquet(s4_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "s4_zone_counts_missing",
                {"component": "S4_ZONE_COUNTS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        _require_columns(
            s4_df,
            "S4_ZONE_COUNTS",
            ["merchant_id", "legal_country_iso", "tzid", "zone_site_count", "zone_site_count_sum"],
            manifest_fingerprint,
        )

        zone_alloc_entry = find_dataset_entry(dictionary, "zone_alloc").entry
        try:
            zone_alloc_path = _resolve_dataset_path(zone_alloc_entry, run_paths, config.external_roots, tokens)
            zone_alloc_paths = _list_parquet_paths(zone_alloc_path)
            zone_alloc_df = pl.read_parquet(zone_alloc_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "zone_alloc_missing",
                {"component": "ZONE_ALLOC", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        _require_columns(
            zone_alloc_df,
            "ZONE_ALLOC",
            [
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "zone_site_count",
                "zone_site_count_sum",
                "site_count",
                "routing_universe_hash",
            ],
            manifest_fingerprint,
        )

        zone_universe_entry = find_dataset_entry(dictionary, "zone_alloc_universe_hash").entry
        try:
            zone_universe_path = _resolve_dataset_path(zone_universe_entry, run_paths, config.external_roots, tokens)
            zone_alloc_universe = _load_json(zone_universe_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "zone_alloc_universe_hash_missing",
                {"component": "ZONE_ALLOC_UNIVERSE_HASH", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        universe_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/zone_alloc_universe_hash")
        universe_errors = list(Draft202012Validator(universe_schema).iter_errors(zone_alloc_universe))
        if universe_errors:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-04",
                "zone_alloc_universe_hash_schema_invalid",
                {"component": "ZONE_ALLOC_UNIVERSE_HASH", "reason": "schema_invalid", "error": str(universe_errors[0])},
                manifest_fingerprint,
            )

        outlet_paths = _list_parquet_paths(outlet_root)
        outlet_df = pl.read_parquet(outlet_paths)
        _require_columns(
            outlet_df,
            "OUTLET_CATALOGUE",
            ["merchant_id", "legal_country_iso"],
            manifest_fingerprint,
        )

        current_phase = "rng_logs"
        event_entry = find_dataset_entry(dictionary, "rng_event_zone_dirichlet").entry
        trace_entry = find_dataset_entry(dictionary, "rng_trace_log").entry
        audit_entry = find_dataset_entry(dictionary, "rng_audit_log").entry
        try:
            event_paths = _resolve_event_paths(event_entry, run_paths, config.external_roots, tokens)
            trace_paths = _resolve_event_paths(trace_entry, run_paths, config.external_roots, tokens)
            audit_paths = _resolve_event_paths(audit_entry, run_paths, config.external_roots, tokens)
        except InputResolutionError as exc:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-05",
                "rng_logs_missing",
                {"component": "RNG_LOGS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )

        event_schema = normalize_nullable_schema(_schema_from_pack(schema_layer1, "rng/events/zone_dirichlet"))
        event_validator = Draft202012Validator(event_schema)
        trace_schema = normalize_nullable_schema(_schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record"))
        trace_validator = Draft202012Validator(trace_schema)
        audit_schema = normalize_nullable_schema(_schema_from_pack(schema_layer1, "rng/core/rng_audit_log/record"))
        audit_validator = Draft202012Validator(audit_schema)

        event_tracker = _ProgressTracker(None, logger, "S6: rng_event_zone_dirichlet")
        event_pairs: list[tuple[int, str]] = []
        event_rows_total = 0
        event_blocks_total = 0
        event_draws_total = 0
        event_identity_mismatch = 0
        for path in event_paths:
            for line_no, payload in _iter_jsonl(path):
                errors = list(event_validator.iter_errors(payload))
                if errors:
                    _abort(
                        "E3A_S6_001_PRECONDITION_FAILED",
                        "V-05",
                        "rng_event_schema_invalid",
                        {"component": "RNG_EVENTS", "error": str(errors[0]), "path": str(path), "line": line_no},
                        manifest_fingerprint,
                    )
                event_rows_total += 1
                if str(payload.get("run_id")) != run_id_value:
                    event_identity_mismatch += 1
                if str(payload.get("parameter_hash")) != str(parameter_hash):
                    event_identity_mismatch += 1
                if str(payload.get("manifest_fingerprint")) != str(manifest_fingerprint):
                    event_identity_mismatch += 1
                if int(payload.get("seed") or -1) != int(seed):
                    event_identity_mismatch += 1
                event_pairs.append((int(payload.get("merchant_id")), str(payload.get("country_iso"))))
                event_blocks_total += int(payload.get("blocks") or 0)
                event_draws_total += int(payload.get("draws") or 0)
                event_tracker.update(1)
        if event_rows_total == 0:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-05",
                "rng_events_missing",
                {"component": "RNG_EVENTS", "reason": "empty"},
                manifest_fingerprint,
            )

        trace_tracker = _ProgressTracker(None, logger, "S6: rng_trace_log")
        trace_rows: list[tuple[dict, str]] = []
        trace_rows_total = 0
        trace_identity_mismatch = 0
        for path in trace_paths:
            for line_no, payload in _iter_jsonl(path):
                trace_rows_total += 1
                errors = list(trace_validator.iter_errors(payload))
                if errors:
                    _abort(
                        "E3A_S6_001_PRECONDITION_FAILED",
                        "V-05",
                        "rng_trace_schema_invalid",
                        {"component": "RNG_TRACE", "error": str(errors[0]), "path": str(path), "line": line_no},
                        manifest_fingerprint,
                    )
                if str(payload.get("run_id")) != run_id_value or int(payload.get("seed") or -1) != int(seed):
                    trace_identity_mismatch += 1
                    trace_tracker.update(1)
                    continue
                if (
                    str(payload.get("module")) == MODULE_RNG
                    and str(payload.get("substream_label")) == SUBSTREAM_LABEL
                ):
                    trace_rows.append((payload, path.name))
                trace_tracker.update(1)
        if trace_rows_total == 0:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-05",
                "rng_trace_missing",
                {"component": "RNG_TRACE", "reason": "empty"},
                manifest_fingerprint,
            )

        audit_tracker = _ProgressTracker(None, logger, "S6: rng_audit_log")
        audit_rows_total = 0
        audit_found = False
        for path in audit_paths:
            for line_no, payload in _iter_jsonl(path):
                audit_rows_total += 1
                errors = list(audit_validator.iter_errors(payload))
                if errors:
                    _abort(
                        "E3A_S6_001_PRECONDITION_FAILED",
                        "V-05",
                        "rng_audit_schema_invalid",
                        {"component": "RNG_AUDIT", "error": str(errors[0]), "path": str(path), "line": line_no},
                        manifest_fingerprint,
                    )
                if (
                    str(payload.get("run_id")) == run_id_value
                    and str(payload.get("parameter_hash")) == str(parameter_hash)
                    and str(payload.get("manifest_fingerprint")) == str(manifest_fingerprint)
                    and int(payload.get("seed") or -1) == int(seed)
                ):
                    audit_found = True
                audit_tracker.update(1)
        if audit_rows_total == 0:
            _abort(
                "E3A_S6_001_PRECONDITION_FAILED",
                "V-05",
                "rng_audit_missing",
                {"component": "RNG_AUDIT", "reason": "empty"},
                manifest_fingerprint,
            )

        timer.info("S6: precondition inputs loaded")

        issue_rows: list[dict] = []
        check_severities = {
            "CHK_S0_GATE_SEALED_INPUTS": "ERROR",
            "CHK_S1_DOMAIN_COUNTS": "ERROR",
            "CHK_S2_PRIORS_ZONE_UNIVERSE": "ERROR",
            "CHK_S3_DOMAIN_ALIGNMENT": "ERROR",
            "CHK_S3_SHARE_SUM": "ERROR",
            "CHK_S3_RNG_ACCOUNTING": "ERROR",
            "CHK_S4_COUNT_CONSERVATION": "ERROR",
            "CHK_S4_DOMAIN_ALIGNMENT": "ERROR",
            "CHK_S5_ZONE_ALLOC_COUNTS": "ERROR",
            "CHK_S5_UNIVERSE_HASH_DIGESTS": "ERROR",
            "CHK_S5_UNIVERSE_HASH_COMBINED": "ERROR",
            "CHK_STATE_STATUS_CONSISTENCY": "WARN",
        }
        checks: dict[str, dict] = {
            check_id: {
                "check_id": check_id,
                "status": "PASS",
                "severity": severity,
                "affected_count": 0,
            }
            for check_id, severity in check_severities.items()
        }

        def _record_check(check_id: str, affected: int, notes: Optional[str] = None) -> None:
            entry = checks[check_id]
            entry["affected_count"] = int(affected)
            if affected > 0:
                if entry["severity"] == "ERROR":
                    entry["status"] = "FAIL"
                elif entry["severity"] == "WARN":
                    entry["status"] = "WARN"
            if notes:
                entry["notes"] = notes

        current_phase = "checks"
        logger.info("S6: running structural checks (checks=%d)", len(checks))

        upstream_gates = s0_gate.get("upstream_gates") or {}
        gate_failures: list[str] = []
        for segment in ("1A", "1B", "2A"):
            status_value = (upstream_gates.get(f"segment_{segment}") or {}).get("status")
            if status_value != "PASS":
                gate_failures.append(segment)
                _add_issue(
                    issue_rows,
                    manifest_fingerprint,
                    "CHK_S0_GATE_SEALED_INPUTS",
                    "S0_GATE_STATUS",
                    "ERROR",
                    "upstream_gate_not_pass",
                    details=f"segment={segment},status={status_value}",
                )
        gate_manifest_mismatch = str(s0_gate.get("manifest_fingerprint")) != str(manifest_fingerprint)
        gate_param_mismatch = str(s0_gate.get("parameter_hash")) != str(parameter_hash)
        if gate_manifest_mismatch:
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S0_GATE_SEALED_INPUTS",
                "S0_GATE_MANIFEST_MISMATCH",
                "ERROR",
                "s0_gate_manifest_mismatch",
                details="s0_gate manifest_fingerprint does not match run_receipt",
            )
        if gate_param_mismatch:
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S0_GATE_SEALED_INPUTS",
                "S0_GATE_PARAMETER_MISMATCH",
                "ERROR",
                "s0_gate_parameter_mismatch",
                details="s0_gate parameter_hash does not match run_receipt",
            )
        missing_policy_ids = sorted(policy_id for policy_id in required_policies if policy_id not in sealed_policy_ids)
        for policy_id in missing_policy_ids:
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S0_GATE_SEALED_INPUTS",
                "S0_SEALED_POLICY_MISSING",
                "ERROR",
                "sealed_policy_missing",
                details=f"logical_id={policy_id}",
            )
        affected = len(gate_failures) + len(missing_policy_ids) + int(gate_manifest_mismatch) + int(gate_param_mismatch)
        _record_check(
            "CHK_S0_GATE_SEALED_INPUTS",
            affected,
            notes=f"gate_failures={len(gate_failures)},missing_policies={len(missing_policy_ids)}",
        )

        s1_keys = ["merchant_id", "legal_country_iso"]
        s1_pairs = s1_df.select(s1_keys).unique()
        counts["pairs_total"] = s1_pairs.height
        esc_df = s1_df.filter(pl.col("is_escalated") == True).select(
            ["merchant_id", "legal_country_iso", "site_count"]
        )
        esc_pairs = esc_df.select(s1_keys).unique()
        counts["pairs_escalated"] = esc_pairs.height

        s1_dupes = s1_df.group_by(s1_keys).len().filter(pl.col("len") > 1)
        for row in s1_dupes.select(s1_keys).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S1_DOMAIN_COUNTS",
                "S1_DUPLICATE_PAIR",
                "ERROR",
                "duplicate_s1_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )

        s1_invalid = s1_df.filter((pl.col("site_count") < 1) | (pl.col("site_count").is_null()))
        for row in s1_invalid.select(s1_keys + ["site_count"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S1_DOMAIN_COUNTS",
                "S1_SITE_COUNT_INVALID",
                "ERROR",
                "invalid_site_count",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=f"site_count={row['site_count']}",
            )

        outlet_counts = outlet_df.group_by(s1_keys).agg(pl.count().alias("outlet_count"))
        s1_counts = s1_df.select(s1_keys + ["site_count"])
        s1_missing = outlet_counts.join(s1_counts, on=s1_keys, how="anti")
        for row in s1_missing.select(s1_keys).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S1_DOMAIN_COUNTS",
                "S1_MISSING_PAIR",
                "ERROR",
                "missing_s1_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        s1_extra = s1_counts.join(outlet_counts, on=s1_keys, how="anti")
        for row in s1_extra.select(s1_keys).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S1_DOMAIN_COUNTS",
                "S1_EXTRA_PAIR",
                "ERROR",
                "extra_s1_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        s1_mismatch = outlet_counts.join(s1_counts, on=s1_keys, how="inner").filter(
            pl.col("outlet_count") != pl.col("site_count")
        )
        for row in s1_mismatch.select(s1_keys + ["outlet_count", "site_count"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S1_DOMAIN_COUNTS",
                "S1_SITE_COUNT_MISMATCH",
                "ERROR",
                "site_count_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=f"outlet_count={row['outlet_count']},site_count={row['site_count']}",
            )

        affected = s1_dupes.height + s1_invalid.height + s1_missing.height + s1_extra.height + s1_mismatch.height
        _record_check(
            "CHK_S1_DOMAIN_COUNTS",
            int(affected),
            notes=(
                "duplicates=%d,missing=%d,extra=%d,mismatch=%d"
                % (s1_dupes.height, s1_missing.height, s1_extra.height, s1_mismatch.height)
            ),
        )

        s2_dupes = s2_df.group_by(["country_iso", "tzid"]).len().filter(pl.col("len") > 1)
        for row in s2_dupes.select(["country_iso", "tzid"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S2_PRIORS_ZONE_UNIVERSE",
                "S2_DUPLICATE_ZONE",
                "ERROR",
                "duplicate_zone_entry",
                legal_country_iso=row["country_iso"],
                tzid=row["tzid"],
            )

        s2_alpha_invalid = s2_df.filter(
            (~pl.col("alpha_effective").is_finite()) | (pl.col("alpha_effective") <= 0)
        )
        for row in s2_alpha_invalid.select(["country_iso", "tzid", "alpha_effective"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S2_PRIORS_ZONE_UNIVERSE",
                "S2_ALPHA_INVALID",
                "ERROR",
                "alpha_effective_invalid",
                legal_country_iso=row["country_iso"],
                tzid=row["tzid"],
                details=f"alpha_effective={row['alpha_effective']}",
            )

        s2_alpha_sum_invalid = s2_df.filter(
            (~pl.col("alpha_sum_country").is_finite()) | (pl.col("alpha_sum_country") <= 0)
        )
        for row in s2_alpha_sum_invalid.select(["country_iso", "alpha_sum_country"]).unique().to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S2_PRIORS_ZONE_UNIVERSE",
                "S2_ALPHA_SUM_INVALID",
                "ERROR",
                "alpha_sum_country_invalid",
                legal_country_iso=row["country_iso"],
                details=f"alpha_sum_country={row['alpha_sum_country']}",
            )

        alpha_sum = s2_df.group_by("country_iso").agg(
            pl.sum("alpha_effective").alias("alpha_sum_calc"),
            pl.first("alpha_sum_country").alias("alpha_sum_reported"),
        )
        alpha_sum_mismatch = alpha_sum.filter(
            (~pl.col("alpha_sum_calc").is_finite())
            | (~pl.col("alpha_sum_reported").is_finite())
            | ((pl.col("alpha_sum_calc") - pl.col("alpha_sum_reported")).abs() > TOLERANCE)
        )
        for row in alpha_sum_mismatch.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S2_PRIORS_ZONE_UNIVERSE",
                "S2_ALPHA_SUM_MISMATCH",
                "ERROR",
                "alpha_sum_country_mismatch",
                legal_country_iso=row["country_iso"],
                details=f"alpha_sum_calc={row['alpha_sum_calc']},alpha_sum_reported={row['alpha_sum_reported']}",
            )

        affected = (
            s2_dupes.height + s2_alpha_invalid.height + s2_alpha_sum_invalid.height + alpha_sum_mismatch.height
        )
        _record_check(
            "CHK_S2_PRIORS_ZONE_UNIVERSE",
            int(affected),
            notes=(
                "duplicates=%d,alpha_invalid=%d,alpha_sum_invalid=%d,alpha_sum_mismatch=%d"
                % (s2_dupes.height, s2_alpha_invalid.height, s2_alpha_sum_invalid.height, alpha_sum_mismatch.height)
            ),
        )

        s2_zones = s2_df.select(["country_iso", "tzid"]).unique()
        expected_zone_counts = s2_zones.group_by("country_iso").agg(
            pl.count().alias("expected_zone_count")
        )

        s3_pairs = s3_df.select(s1_keys).unique()
        counts["s3_pairs"] = s3_pairs.height
        counts["s3_rows"] = s3_df.height
        s3_missing = esc_pairs.join(s3_pairs, on=s1_keys, how="anti")
        s3_extra = s3_pairs.join(esc_pairs, on=s1_keys, how="anti")
        s3_dupes = s3_df.group_by(s1_keys + ["tzid"]).len().filter(pl.col("len") > 1)
        s3_bad_tz = s3_df.join(
            s2_zones, left_on=["legal_country_iso", "tzid"], right_on=["country_iso", "tzid"], how="anti"
        )
        s3_zone_counts = s3_df.group_by(s1_keys).agg(pl.count().alias("observed_zone_count"))
        s3_zone_counts = s3_zone_counts.join(
            expected_zone_counts,
            left_on="legal_country_iso",
            right_on="country_iso",
            how="left",
        )
        s3_zone_mismatch = s3_zone_counts.filter(
            pl.col("expected_zone_count").is_null()
            | (pl.col("observed_zone_count") != pl.col("expected_zone_count"))
        )

        for row in s3_missing.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_DOMAIN_ALIGNMENT",
                "S3_MISSING_PAIR",
                "ERROR",
                "missing_s3_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        for row in s3_extra.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_DOMAIN_ALIGNMENT",
                "S3_EXTRA_PAIR",
                "ERROR",
                "extra_s3_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        for row in s3_dupes.select(s1_keys + ["tzid"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_DOMAIN_ALIGNMENT",
                "S3_DUPLICATE_TRIPLET",
                "ERROR",
                "duplicate_s3_triplet",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
            )
        for row in s3_bad_tz.select(s1_keys + ["tzid"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_DOMAIN_ALIGNMENT",
                "S3_TZID_OUT_OF_UNIVERSE",
                "ERROR",
                "tzid_not_in_s2",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
            )
        for row in s3_zone_mismatch.select(s1_keys + ["observed_zone_count", "expected_zone_count"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_DOMAIN_ALIGNMENT",
                "S3_ZONE_COUNT_MISMATCH",
                "ERROR",
                "zone_count_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=(
                    f"observed={row['observed_zone_count']},expected={row['expected_zone_count']}"
                ),
            )
        affected = (
            s3_missing.height + s3_extra.height + s3_dupes.height + s3_bad_tz.height + s3_zone_mismatch.height
        )
        _record_check(
            "CHK_S3_DOMAIN_ALIGNMENT",
            int(affected),
            notes=(
                "missing=%d,extra=%d,dup_triplets=%d,bad_tz=%d,zone_count_mismatch=%d"
                % (
                    s3_missing.height,
                    s3_extra.height,
                    s3_dupes.height,
                    s3_bad_tz.height,
                    s3_zone_mismatch.height,
                )
            ),
        )

        s3_share_sum = s3_df.group_by(s1_keys).agg(pl.sum("share_drawn").alias("share_sum"))
        s3_share_bad = s3_share_sum.filter(
            (~pl.col("share_sum").is_finite()) | ((pl.col("share_sum") - 1.0).abs() > TOLERANCE)
        )
        for row in s3_share_bad.select(s1_keys + ["share_sum"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_SHARE_SUM",
                "S3_SHARE_SUM_MISMATCH",
                "ERROR",
                "share_sum_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=f"share_sum={row['share_sum']}",
            )
        _record_check(
            "CHK_S3_SHARE_SUM",
            int(s3_share_bad.height),
            notes=f"pairs_out_of_tolerance={s3_share_bad.height}",
        )

        event_pair_schema = {"merchant_id": pl.UInt64, "legal_country_iso": pl.Utf8}
        if event_pairs:
            event_pair_df = pl.DataFrame(event_pairs, schema=event_pair_schema, orient="row")
        else:
            event_pair_df = pl.DataFrame([], schema=event_pair_schema)
        event_pair_df = event_pair_df.unique() if event_pair_df.height else event_pair_df
        event_pair_dupes = 0
        if event_pairs:
            counter = Counter(event_pairs)
            event_pair_dupes = sum(1 for count in counter.values() if count > 1)
            for (merchant_id, country_iso), count in counter.items():
                if count > 1:
                    _add_issue(
                        issue_rows,
                        manifest_fingerprint,
                        "CHK_S3_RNG_ACCOUNTING",
                        "S3_RNG_DUPLICATE_EVENT",
                        "ERROR",
                        "duplicate_rng_event",
                        merchant_id=merchant_id,
                        legal_country_iso=country_iso,
                        details=f"event_count={count}",
                    )

        rng_missing = esc_pairs.join(event_pair_df, on=s1_keys, how="anti") if event_pair_df.height else esc_pairs
        rng_extra = event_pair_df.join(esc_pairs, on=s1_keys, how="anti") if event_pair_df.height else pl.DataFrame()
        for row in rng_missing.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_RNG_ACCOUNTING",
                "S3_RNG_EVENT_MISSING",
                "ERROR",
                "missing_rng_event",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        for row in rng_extra.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_RNG_ACCOUNTING",
                "S3_RNG_EVENT_EXTRA",
                "ERROR",
                "extra_rng_event",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )

        trace_row, trace_source = _select_trace_row(trace_rows)
        trace_counter_row, trace_counter_source = _select_trace_row_by_counter(trace_rows)
        if trace_row and trace_counter_row and trace_row != trace_counter_row:
            logger.info(
                "S6: rng_trace aggregate selection uses max totals; max-counter differs (totals_events=%s,totals_blocks=%s,totals_draws=%s,totals_source=%s,counter_events=%s,counter_blocks=%s,counter_draws=%s,counter_source=%s)",
                trace_row.get("events_total"),
                trace_row.get("blocks_total"),
                trace_row.get("draws_total"),
                trace_source,
                trace_counter_row.get("events_total"),
                trace_counter_row.get("blocks_total"),
                trace_counter_row.get("draws_total"),
                trace_counter_source,
            )
        trace_mismatch = 0
        if trace_row is None:
            trace_mismatch += 1
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_RNG_ACCOUNTING",
                "S3_RNG_TRACE_MISSING",
                "ERROR",
                "missing_rng_trace",
                details="no trace rows for module/substream",
            )
        else:
            trace_events_total = int(trace_row.get("events_total") or 0)
            trace_blocks_total = int(trace_row.get("blocks_total") or 0)
            trace_draws_total = int(trace_row.get("draws_total") or 0)
            if trace_events_total != event_rows_total:
                trace_mismatch += 1
            if trace_blocks_total != event_blocks_total:
                trace_mismatch += 1
            if trace_draws_total != event_draws_total:
                trace_mismatch += 1
            if trace_mismatch:
                _add_issue(
                    issue_rows,
                    manifest_fingerprint,
                    "CHK_S3_RNG_ACCOUNTING",
                    "S3_RNG_TRACE_MISMATCH",
                    "ERROR",
                    "rng_trace_mismatch",
                    details=(
                        f"events_total={trace_events_total},blocks_total={trace_blocks_total},"
                        f"draws_total={trace_draws_total},event_rows={event_rows_total},"
                        f"blocks_sum={event_blocks_total},draws_sum={event_draws_total},"
                        f"source={trace_source}"
                    ),
                )

        if not audit_found:
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_RNG_ACCOUNTING",
                "S3_RNG_AUDIT_MISSING",
                "ERROR",
                "missing_rng_audit_entry",
                details="audit log missing run entry",
            )

        rng_affected = (
            rng_missing.height
            + rng_extra.height
            + int(event_pair_dupes)
            + int(event_identity_mismatch > 0)
            + int(trace_mismatch > 0)
            + int(trace_identity_mismatch > 0)
            + int(not audit_found)
        )
        if event_identity_mismatch:
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_RNG_ACCOUNTING",
                "S3_RNG_IDENTITY_MISMATCH",
                "ERROR",
                "rng_event_identity_mismatch",
                details=f"mismatch_rows={event_identity_mismatch}",
            )
        if trace_identity_mismatch:
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S3_RNG_ACCOUNTING",
                "S3_RNG_TRACE_IDENTITY_MISMATCH",
                "ERROR",
                "rng_trace_identity_mismatch",
                details=f"mismatch_rows={trace_identity_mismatch}",
            )
        _record_check(
            "CHK_S3_RNG_ACCOUNTING",
            int(rng_affected),
            notes=(
                "missing=%d,extra=%d,dupes=%d,identity_mismatch=%d,trace_mismatch=%d,audit_found=%s"
                % (
                    rng_missing.height,
                    rng_extra.height,
                    event_pair_dupes,
                    event_identity_mismatch,
                    trace_mismatch,
                    audit_found,
                )
            ),
        )

        s4_pairs = s4_df.select(s1_keys).unique()
        counts["s4_pairs"] = s4_pairs.height
        counts["s4_rows"] = s4_df.height
        s4_dupes = s4_df.group_by(s1_keys + ["tzid"]).len().filter(pl.col("len") > 1)
        s4_missing = esc_pairs.join(s4_pairs, on=s1_keys, how="anti")
        s4_extra = s4_pairs.join(esc_pairs, on=s1_keys, how="anti")
        s4_bad_tz = s4_df.join(
            s2_zones, left_on=["legal_country_iso", "tzid"], right_on=["country_iso", "tzid"], how="anti"
        )
        s4_zone_counts = s4_df.group_by(s1_keys).agg(pl.count().alias("observed_zone_count"))
        s4_zone_counts = s4_zone_counts.join(
            expected_zone_counts,
            left_on="legal_country_iso",
            right_on="country_iso",
            how="left",
        )
        s4_zone_mismatch = s4_zone_counts.filter(
            pl.col("expected_zone_count").is_null()
            | (pl.col("observed_zone_count") != pl.col("expected_zone_count"))
        )

        for row in s4_missing.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S4_DOMAIN_ALIGNMENT",
                "S4_MISSING_PAIR",
                "ERROR",
                "missing_s4_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        for row in s4_extra.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S4_DOMAIN_ALIGNMENT",
                "S4_EXTRA_PAIR",
                "ERROR",
                "extra_s4_pair",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
            )
        for row in s4_dupes.select(s1_keys + ["tzid"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S4_DOMAIN_ALIGNMENT",
                "S4_DUPLICATE_TRIPLET",
                "ERROR",
                "duplicate_s4_triplet",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
            )
        for row in s4_bad_tz.select(s1_keys + ["tzid"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S4_DOMAIN_ALIGNMENT",
                "S4_TZID_OUT_OF_UNIVERSE",
                "ERROR",
                "tzid_not_in_s2",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
            )
        for row in s4_zone_mismatch.select(s1_keys + ["observed_zone_count", "expected_zone_count"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S4_DOMAIN_ALIGNMENT",
                "S4_ZONE_COUNT_MISMATCH",
                "ERROR",
                "zone_count_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=(
                    f"observed={row['observed_zone_count']},expected={row['expected_zone_count']}"
                ),
            )

        affected = (
            s4_missing.height + s4_extra.height + s4_dupes.height + s4_bad_tz.height + s4_zone_mismatch.height
        )
        _record_check(
            "CHK_S4_DOMAIN_ALIGNMENT",
            int(affected),
            notes=(
                "missing=%d,extra=%d,dup_triplets=%d,bad_tz=%d,zone_count_mismatch=%d"
                % (
                    s4_missing.height,
                    s4_extra.height,
                    s4_dupes.height,
                    s4_bad_tz.height,
                    s4_zone_mismatch.height,
                )
            ),
        )

        s4_sum = s4_df.group_by(s1_keys).agg(
            pl.sum("zone_site_count").alias("zone_site_count_sum_calc"),
            pl.first("zone_site_count_sum").alias("zone_site_count_sum_reported"),
        )
        s4_sum = s4_sum.join(esc_df.select(s1_keys + ["site_count"]), on=s1_keys, how="left")
        s4_sum_bad = s4_sum.filter(
            pl.col("site_count").is_null()
            | (pl.col("zone_site_count_sum_calc") != pl.col("zone_site_count_sum_reported"))
            | (pl.col("zone_site_count_sum_reported") != pl.col("site_count"))
        )
        for row in s4_sum_bad.select(s1_keys + ["zone_site_count_sum_calc", "zone_site_count_sum_reported", "site_count"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S4_COUNT_CONSERVATION",
                "S4_COUNT_CONSERVATION",
                "ERROR",
                "count_conservation_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=(
                    f"calc={row['zone_site_count_sum_calc']},"
                    f"reported={row['zone_site_count_sum_reported']},"
                    f"site_count={row['site_count']}"
                ),
            )
        _record_check(
            "CHK_S4_COUNT_CONSERVATION",
            int(s4_sum_bad.height),
            notes=f"pairs_mismatched={s4_sum_bad.height}",
        )

        counts["zone_alloc_rows"] = zone_alloc_df.height
        zone_alloc_triplets = zone_alloc_df.select(s1_keys + ["tzid"])
        s4_triplets = s4_df.select(s1_keys + ["tzid"])
        alloc_missing = s4_triplets.join(zone_alloc_triplets, on=s1_keys + ["tzid"], how="anti")
        alloc_extra = zone_alloc_triplets.join(s4_triplets, on=s1_keys + ["tzid"], how="anti")

        alloc_compare = zone_alloc_df.join(
            s4_df.select(s1_keys + ["tzid", "zone_site_count", "zone_site_count_sum"]),
            on=s1_keys + ["tzid"],
            how="left",
            suffix="_s4",
        )
        alloc_mismatch = alloc_compare.filter(
            pl.col("zone_site_count_s4").is_null()
            | (pl.col("zone_site_count") != pl.col("zone_site_count_s4"))
        )

        alloc_sum = zone_alloc_df.group_by(s1_keys).agg(
            pl.sum("zone_site_count").alias("zone_site_count_sum_calc"),
            pl.first("zone_site_count_sum").alias("zone_site_count_sum_reported"),
            pl.first("site_count").alias("site_count"),
        )
        alloc_sum = alloc_sum.join(esc_df.select(s1_keys + ["site_count"]), on=s1_keys, how="left", suffix="_s1")
        alloc_sum_bad = alloc_sum.filter(
            pl.col("site_count_s1").is_null()
            | (pl.col("zone_site_count_sum_calc") != pl.col("zone_site_count_sum_reported"))
            | (pl.col("zone_site_count_sum_reported") != pl.col("site_count"))
            | (pl.col("site_count") != pl.col("site_count_s1"))
        )

        for row in alloc_missing.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S5_ZONE_ALLOC_COUNTS",
                "S5_ALLOC_MISSING_TRIPLET",
                "ERROR",
                "missing_zone_alloc_triplet",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
            )
        for row in alloc_extra.to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S5_ZONE_ALLOC_COUNTS",
                "S5_ALLOC_EXTRA_TRIPLET",
                "ERROR",
                "extra_zone_alloc_triplet",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
            )
        for row in alloc_mismatch.select(s1_keys + ["tzid", "zone_site_count", "zone_site_count_s4"]).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S5_ZONE_ALLOC_COUNTS",
                "S5_ALLOC_COUNT_MISMATCH",
                "ERROR",
                "zone_site_count_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                tzid=row["tzid"],
                details=f"alloc={row['zone_site_count']},s4={row['zone_site_count_s4']}",
            )
        for row in alloc_sum_bad.select(
            s1_keys
            + ["zone_site_count_sum_calc", "zone_site_count_sum_reported", "site_count", "site_count_s1"]
        ).to_dicts():
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S5_ZONE_ALLOC_COUNTS",
                "S5_ALLOC_SUM_MISMATCH",
                "ERROR",
                "zone_alloc_sum_mismatch",
                merchant_id=row["merchant_id"],
                legal_country_iso=row["legal_country_iso"],
                details=(
                    f"calc={row['zone_site_count_sum_calc']},"
                    f"reported={row['zone_site_count_sum_reported']},"
                    f"alloc_site_count={row['site_count']},s1_site_count={row['site_count_s1']}"
                ),
            )

        affected = alloc_missing.height + alloc_extra.height + alloc_mismatch.height + alloc_sum_bad.height
        _record_check(
            "CHK_S5_ZONE_ALLOC_COUNTS",
            int(affected),
            notes=(
                "missing_triplets=%d,extra_triplets=%d,count_mismatch=%d,sum_mismatch=%d"
                % (alloc_missing.height, alloc_extra.height, alloc_mismatch.height, alloc_sum_bad.height)
            ),
        )

        zone_alpha_digest, _, _ = _hash_parquet_partition(s2_path)
        theta_digest = policy_digests["zone_mixture_policy"]
        zone_floor_digest = policy_digests["zone_floor_policy"]
        day_effect_digest = policy_digests["day_effect_policy_v1"]
        masked_df = zone_alloc_df.with_columns(pl.lit(HEX64_ZERO).alias("routing_universe_hash"))
        zone_alloc_parquet_digest, _, _ = _compute_masked_alloc_digest(masked_df, run_paths.tmp_root, logger)

        digest_mismatch = 0
        digest_fields = {
            "zone_alpha_digest": zone_alpha_digest,
            "theta_digest": theta_digest,
            "zone_floor_digest": zone_floor_digest,
            "day_effect_digest": day_effect_digest,
            "zone_alloc_parquet_digest": zone_alloc_parquet_digest,
        }
        for key, value in digest_fields.items():
            if str(zone_alloc_universe.get(key)) != str(value):
                digest_mismatch += 1
                _add_issue(
                    issue_rows,
                    manifest_fingerprint,
                    "CHK_S5_UNIVERSE_HASH_DIGESTS",
                    "S5_DIGEST_MISMATCH",
                    "ERROR",
                    "universe_digest_mismatch",
                    details=f"{key} expected={value} observed={zone_alloc_universe.get(key)}",
                )
        _record_check(
            "CHK_S5_UNIVERSE_HASH_DIGESTS",
            int(digest_mismatch),
            notes=f"mismatched_digests={digest_mismatch}",
        )

        routing_universe_hash = _sha256_concat_hex(
            [
                zone_alpha_digest,
                theta_digest,
                zone_floor_digest,
                day_effect_digest,
                zone_alloc_parquet_digest,
            ]
        )
        combined_mismatch = 0
        recorded_routing = str(zone_alloc_universe.get("routing_universe_hash") or "")
        if recorded_routing != routing_universe_hash:
            combined_mismatch += 1
            _add_issue(
                issue_rows,
                manifest_fingerprint,
                "CHK_S5_UNIVERSE_HASH_COMBINED",
                "S5_ROUTING_HASH_MISMATCH",
                "ERROR",
                "routing_universe_hash_mismatch",
                details=f"expected={routing_universe_hash},observed={recorded_routing}",
            )
        alloc_hash_bad = zone_alloc_df.filter(pl.col("routing_universe_hash") != routing_universe_hash)
        if alloc_hash_bad.height:
            combined_mismatch += alloc_hash_bad.height
            for row in alloc_hash_bad.select(s1_keys + ["tzid", "routing_universe_hash"]).to_dicts():
                _add_issue(
                    issue_rows,
                    manifest_fingerprint,
                    "CHK_S5_UNIVERSE_HASH_COMBINED",
                    "S5_ALLOC_ROUTING_HASH_MISMATCH",
                    "ERROR",
                    "zone_alloc_hash_mismatch",
                    merchant_id=row["merchant_id"],
                    legal_country_iso=row["legal_country_iso"],
                    tzid=row["tzid"],
                    details=f"observed={row['routing_universe_hash']}",
                )
        _record_check(
            "CHK_S5_UNIVERSE_HASH_COMBINED",
            int(combined_mismatch),
            notes=f"routing_hash_mismatch={combined_mismatch}",
        )

        state_status_inconsistencies = 0
        state_checks = {
            "S1": ["CHK_S1_DOMAIN_COUNTS"],
            "S2": ["CHK_S2_PRIORS_ZONE_UNIVERSE"],
            "S3": ["CHK_S3_DOMAIN_ALIGNMENT", "CHK_S3_SHARE_SUM", "CHK_S3_RNG_ACCOUNTING"],
            "S4": ["CHK_S4_DOMAIN_ALIGNMENT", "CHK_S4_COUNT_CONSERVATION"],
            "S5": ["CHK_S5_ZONE_ALLOC_COUNTS", "CHK_S5_UNIVERSE_HASH_DIGESTS", "CHK_S5_UNIVERSE_HASH_COMBINED"],
        }
        for state_label, check_ids in state_checks.items():
            reported_status = str(run_reports.get(state_label, {}).get("status") or "")
            has_fail = any(checks[check_id]["status"] == "FAIL" for check_id in check_ids)
            if reported_status == "PASS" and has_fail:
                state_status_inconsistencies += 1
                _add_issue(
                    issue_rows,
                    manifest_fingerprint,
                    "CHK_STATE_STATUS_CONSISTENCY",
                    "STATE_STATUS_MISMATCH",
                    "WARN",
                    "run_report_pass_but_checks_fail",
                    details=f"state={state_label}",
                )
            if reported_status == "FAIL" and not has_fail:
                state_status_inconsistencies += 1
                _add_issue(
                    issue_rows,
                    manifest_fingerprint,
                    "CHK_STATE_STATUS_CONSISTENCY",
                    "STATE_STATUS_MISMATCH",
                    "WARN",
                    "run_report_fail_but_checks_pass",
                    details=f"state={state_label}",
                )
        _record_check(
            "CHK_STATE_STATUS_CONSISTENCY",
            int(state_status_inconsistencies),
            notes=f"inconsistent_states={state_status_inconsistencies}",
        )

        check_list = [checks[key] for key in sorted(checks.keys())]
        checks_failed_count = sum(1 for entry in check_list if entry["status"] == "FAIL")
        checks_warn_count = sum(1 for entry in check_list if entry["status"] == "WARN")
        checks_passed_count = sum(1 for entry in check_list if entry["status"] == "PASS")

        overall_status = "PASS"
        for entry in check_list:
            if entry["severity"] == "ERROR" and entry["status"] == "FAIL":
                overall_status = "FAIL"
                break

        counts["issues_total"] = len(issue_rows)
        counts["issues_error"] = sum(1 for row in issue_rows if row["severity"] == "ERROR")
        counts["issues_warn"] = sum(1 for row in issue_rows if row["severity"] == "WARN")

        report = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "overall_status": overall_status,
            "checks_passed_count": checks_passed_count,
            "checks_failed_count": checks_failed_count,
            "checks_warn_count": checks_warn_count,
            "checks": check_list,
            "metrics": {
                "pairs_total": counts["pairs_total"],
                "pairs_escalated": counts["pairs_escalated"],
                "s3_pairs": counts["s3_pairs"],
                "s4_pairs": counts["s4_pairs"],
                "s3_rows": counts["s3_rows"],
                "s4_rows": counts["s4_rows"],
                "zone_alloc_rows": counts["zone_alloc_rows"],
                "rng_event_rows": event_rows_total,
                "rng_trace_rows": len(trace_rows),
                "issues_total": counts["issues_total"],
            },
        }
        report_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s6_validation_report_3A")
        report_errors = list(Draft202012Validator(report_schema).iter_errors(report))
        if report_errors:
            _abort(
                "E3A_S6_004_REPORT_SCHEMA_INVALID",
                "V-06",
                "s6_report_schema_invalid",
                {"component": "S6_REPORT", "error": str(report_errors[0])},
                manifest_fingerprint,
            )
        report_digest = _json_digest(report)

        issue_schema = {
            "manifest_fingerprint": pl.Utf8,
            "issue_code": pl.Utf8,
            "check_id": pl.Utf8,
            "severity": pl.Utf8,
            "message": pl.Utf8,
            "merchant_id": pl.UInt64,
            "legal_country_iso": pl.Utf8,
            "tzid": pl.Utf8,
            "details": pl.Utf8,
        }
        issue_df = pl.DataFrame(issue_rows, schema=issue_schema) if issue_rows else pl.DataFrame([], schema=issue_schema)
        issue_sort_cols = ["severity", "issue_code", "merchant_id", "legal_country_iso", "tzid"]
        if issue_df.height:
            issue_df = issue_df.sort(issue_sort_cols)
        issue_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s6_issue_table_3A")
        issue_validator = Draft202012Validator(issue_schema)
        for row in issue_df.iter_rows(named=True):
            payload = {key: value for key, value in row.items() if value is not None}
            errors = list(issue_validator.iter_errors(payload))
            if errors:
                _abort(
                    "E3A_S6_004_REPORT_SCHEMA_INVALID",
                    "V-06",
                    "s6_issue_table_schema_invalid",
                    {"component": "S6_ISSUE_TABLE", "error": str(errors[0])},
                    manifest_fingerprint,
                )

        receipt = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "s6_version": s6_version,
            "overall_status": overall_status,
            "checks_passed_count": checks_passed_count,
            "checks_failed_count": checks_failed_count,
            "checks_warn_count": checks_warn_count,
            "check_status_map": {
                entry["check_id"]: {"status": entry["status"], "severity": entry["severity"]} for entry in check_list
            },
            "validation_report_digest": report_digest,
            "issue_table_digest": "",
            "created_at_utc": utc_now_rfc3339_micro(),
            "notes": "issue_table_digest is sha256 over parquet bytes",
        }

        report_entry = find_dataset_entry(dictionary, "s6_validation_report_3A").entry
        report_path = _resolve_dataset_path(report_entry, run_paths, config.external_roots, tokens)
        report_catalog_path = _render_catalog_path(report_entry, tokens)
        if f"manifest_fingerprint={manifest_fingerprint}" not in report_catalog_path:
            _abort(
                "E3A_S6_002_CATALOGUE_MALFORMED",
                "V-06",
                "report_partition_mismatch",
                {"catalogue_id": "s6_validation_report_3A", "path": report_catalog_path},
                manifest_fingerprint,
            )
        _publish_json(report_path, report, logger, "s6_validation_report_3A")
        timer.info("S6: published s6_validation_report_3A")

        issue_entry = find_dataset_entry(dictionary, "s6_issue_table_3A").entry
        issue_table_path = _resolve_dataset_path(issue_entry, run_paths, config.external_roots, tokens)
        issue_catalog_path = _render_catalog_path(issue_entry, tokens)
        if f"manifest_fingerprint={manifest_fingerprint}" not in issue_catalog_path:
            _abort(
                "E3A_S6_002_CATALOGUE_MALFORMED",
                "V-06",
                "issue_partition_mismatch",
                {"catalogue_id": "s6_issue_table_3A", "path": issue_catalog_path},
                manifest_fingerprint,
            )
        _publish_parquet_file(issue_table_path, issue_df, logger, "s6_issue_table_3A", issue_sort_cols)
        issue_digest = sha256_file(issue_table_path).sha256_hex
        timer.info("S6: published s6_issue_table_3A")

        receipt["issue_table_digest"] = issue_digest
        receipt_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s6_receipt_3A")
        receipt_errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt))
        if receipt_errors:
            _abort(
                "E3A_S6_005_RECEIPT_INCONSISTENT",
                "V-06",
                "s6_receipt_schema_invalid",
                {"component": "S6_RECEIPT", "error": str(receipt_errors[0])},
                manifest_fingerprint,
            )

        receipt_entry = find_dataset_entry(dictionary, "s6_receipt_3A").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_catalog_path = _render_catalog_path(receipt_entry, tokens)
        if f"manifest_fingerprint={manifest_fingerprint}" not in receipt_catalog_path:
            _abort(
                "E3A_S6_002_CATALOGUE_MALFORMED",
                "V-06",
                "receipt_partition_mismatch",
                {"catalogue_id": "s6_receipt_3A", "path": receipt_catalog_path},
                manifest_fingerprint,
            )
        _publish_json(receipt_path, receipt, logger, "s6_receipt_3A")
        timer.info("S6: published s6_receipt_3A")

        status = "PASS"
    except EngineFailure as exc:
        if not error_code:
            error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except ContractError as exc:
        if not error_code:
            error_code = "E3A_S6_002_CATALOGUE_MALFORMED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S6_007_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S6_007_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id_value and parameter_hash and manifest_fingerprint:
            utc_day = finished_utc[:10]
            try:
                segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)
                _append_jsonl(
                    segment_state_runs_path,
                    {
                        "layer": "layer1",
                        "segment": SEGMENT,
                        "state": STATE,
                        "parameter_hash": str(parameter_hash),
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "run_id": run_id_value,
                        "status": status,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("S6: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s6_run_report_3A").entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": run_id_value,
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "overall_status": overall_status,
                    "counts": counts,
                    "digests": {
                        "validation_report_digest": report_digest,
                        "issue_table_digest": issue_digest,
                        "routing_universe_hash": routing_universe_hash,
                    },
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "error_class_detail": _error_class_label(error_code),
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "report_path": report_catalog_path if report_path else None,
                        "issue_table_path": issue_catalog_path if issue_table_path else None,
                        "receipt_path": receipt_catalog_path if receipt_path else None,
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S6: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S6: failed to write run-report: %s", exc)

            if start_logged and status == "PASS":
                _emit_event(
                    logger,
                    "STATE_SUCCESS",
                    manifest_fingerprint,
                    "INFO",
                    layer="layer1",
                    segment=SEGMENT,
                    state=STATE,
                    parameter_hash=parameter_hash,
                    seed=seed,
                    run_id=run_id_value,
                    attempt=1,
                    status=status,
                    overall_status=overall_status,
                    checks_failed=counts.get("issues_error", 0),
                    issues_total=counts.get("issues_total", 0),
                )
            if start_logged and status != "PASS":
                _emit_event(
                    logger,
                    "STATE_FAILURE",
                    manifest_fingerprint,
                    "ERROR",
                    layer="layer1",
                    segment=SEGMENT,
                    state=STATE,
                    parameter_hash=parameter_hash,
                    seed=seed,
                    run_id=run_id_value,
                    attempt=1,
                    status=status,
                    error_code=error_code,
                    error_class=_error_class_label(error_code),
                    error_details=error_context,
                )

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3A_S6_007_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if report_path is None or issue_table_path is None or receipt_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S6_007_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S6Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        report_path=report_path,
        issue_table_path=issue_table_path,
        receipt_path=receipt_path,
    )
