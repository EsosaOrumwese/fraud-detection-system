"""S7 validation bundle runner for Segment 3A."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import (
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
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_3A.s0_gate.runner import (
    _append_jsonl,
    _inline_external_refs,
    _load_json,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _segment_state_runs_path,
    _table_pack,
)


MODULE_NAME = "3A.s7_validation_bundle"
SEGMENT = "3A"
STATE = "S7"

DATASET_S0_GATE = "s0_gate_receipt_3A"
DATASET_SEALED_INPUTS = "sealed_inputs_3A"
DATASET_S1 = "s1_escalation_queue"
DATASET_S2 = "s2_country_zone_priors"
DATASET_S3 = "s3_zone_shares"
DATASET_S4 = "s4_zone_counts"
DATASET_S5 = "zone_alloc"
DATASET_S5_UNIVERSE = "zone_alloc_universe_hash"
DATASET_S6_REPORT = "s6_validation_report_3A"
DATASET_S6_ISSUES = "s6_issue_table_3A"
DATASET_S6_RECEIPT = "s6_receipt_3A"
DATASET_S6_RUN_REPORT = "s6_run_report_3A"
DATASET_BUNDLE = "validation_bundle_3A"
DATASET_FLAG = "validation_passed_flag_3A"

DATASET_RNG_EVENT = "rng_event_zone_dirichlet"
DATASET_RNG_TRACE = "rng_trace_log"
DATASET_RNG_AUDIT = "rng_audit_log"

MEMBER_SPECS = [
    (DATASET_S0_GATE, "gate", "json"),
    (DATASET_SEALED_INPUTS, "sealed_inputs", "json"),
    (DATASET_S1, "escalation", "parquet"),
    (DATASET_S2, "priors", "parquet"),
    (DATASET_S3, "shares", "parquet"),
    (DATASET_RNG_EVENT, "rng_event", "log"),
    (DATASET_RNG_TRACE, "rng_trace", "log"),
    (DATASET_RNG_AUDIT, "rng_audit", "log"),
    (DATASET_S4, "counts", "parquet"),
    (DATASET_S5, "egress", "parquet"),
    (DATASET_S5_UNIVERSE, "universe_hash", "json"),
    (DATASET_S6_REPORT, "validation_report", "json"),
    (DATASET_S6_ISSUES, "validation_issues", "parquet"),
    (DATASET_S6_RECEIPT, "validation_receipt", "json"),
]

# S6 already validates these heavy parquet members in the same run and gates S7 on S6 PASS.
# Keep fail-closed required-column guards here and avoid repeating row-wise JSON-schema loops.
TRUSTED_PARQUET_MEMBERS = {
    DATASET_S1,
    DATASET_S2,
    DATASET_S3,
    DATASET_S4,
    DATASET_S5,
}
REQUIRED_PARQUET_COLUMNS: dict[str, list[str]] = {
    DATASET_S1: ["merchant_id", "legal_country_iso", "is_escalated", "site_count"],
    DATASET_S2: ["country_iso", "tzid", "alpha_effective"],
    DATASET_S3: ["merchant_id", "legal_country_iso", "tzid", "share_drawn"],
    DATASET_S4: ["merchant_id", "legal_country_iso", "tzid", "zone_site_count", "zone_site_count_sum"],
    DATASET_S5: [
        "merchant_id",
        "legal_country_iso",
        "tzid",
        "zone_site_count",
        "zone_site_count_sum",
        "site_count",
        "routing_universe_hash",
    ],
}


@dataclass(frozen=True)
class S7Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    bundle_root: Path
    index_path: Path
    flag_path: Path


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
    logger = get_logger("engine.layers.l1.seg_3A.s7_validation_bundle.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_digest(payload: object) -> str:
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _record_schema_for_stream(schema: dict) -> dict:
    if schema.get("type") != "stream" or not isinstance(schema.get("record"), dict):
        return schema
    record_schema = dict(schema["record"])
    record_schema.setdefault("$schema", schema.get("$schema", "https://json-schema.org/draft/2020-12/schema"))
    if "$defs" in schema and "$defs" not in record_schema:
        record_schema["$defs"] = schema["$defs"]
    if "$id" in schema and "$id" not in record_schema:
        record_schema["$id"] = schema["$id"]
    return record_schema


def _schema_pack_for_ref(schema_ref: str, schema_3a: dict, schema_layer1: dict) -> tuple[dict, str]:
    if schema_ref.startswith("schemas.3A.yaml#"):
        return schema_3a, schema_ref.split("#", 1)[1].lstrip("/")
    if schema_ref.startswith("schemas.layer1.yaml#"):
        return schema_layer1, schema_ref.split("#", 1)[1].lstrip("/")
    raise ContractError(f"Unsupported schema_ref for S7: {schema_ref}")


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"), key=lambda path: path.relative_to(root).as_posix())
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


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

def _hash_paths(paths: list[Path], logger, label: str) -> tuple[str, int]:
    tracker = _ProgressTracker(len(paths), logger, label)
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
        tracker.update(1)
    return hasher.hexdigest(), total_bytes


def _hash_jsonl_with_validation(
    paths: list[Path],
    schema: dict,
    logger,
    label: str,
) -> tuple[str, int]:
    validator_schema = _record_schema_for_stream(schema)
    validator = Draft202012Validator(validator_schema)
    tracker = _ProgressTracker(None, logger, label)
    hasher = hashlib.sha256()
    total_bytes = 0
    rows_seen = 0
    for path in paths:
        with path.open("rb") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line:
                    continue
                hasher.update(line)
                total_bytes += len(line)
                payload = line.decode("utf-8").strip()
                if payload:
                    errors = list(validator.iter_errors(json.loads(payload)))
                    if errors:
                        raise SchemaValidationError(
                            f"JSONL schema validation failed at {path}:{line_no}: {errors[0].message}"
                        )
                rows_seen += 1
                tracker.update(1)
    if rows_seen == 0:
        raise SchemaValidationError(f"JSONL stream is empty for label={label}")
    return hasher.hexdigest(), total_bytes


def _sha256_concat_hex(parts: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("ascii"))
    return hasher.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _write_flag(path: Path, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"sha256_hex = {digest}\n", encoding="ascii")

def run_s7(config: EngineConfig, run_id: Optional[str] = None) -> S7Result:
    logger = get_logger("engine.layers.l1.seg_3A.s7_validation_bundle.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    seed: Optional[int] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    run_id_value: Optional[str] = None

    bundle_root: Optional[Path] = None
    index_path: Optional[Path] = None
    flag_path: Optional[Path] = None
    bundle_catalog_path: Optional[str] = None
    flag_catalog_path: Optional[str] = None

    bundle_digest = ""
    s6_receipt_digest = ""
    member_count = 0
    member_bytes = 0

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
        timer.info(f"S7: run log initialized at {run_log_path}")

        logger.info(
            "S7: objective=seal 3A validation bundle from S0-S6 evidence; outputs=index.json,_passed.flag"
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
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        timer.info("S7: contracts loaded")

        current_phase = "s6_run_report"
        s6_run_entry = find_dataset_entry(dictionary, DATASET_S6_RUN_REPORT).entry
        try:
            s6_run_path = _resolve_dataset_path(s6_run_entry, run_paths, config.external_roots, tokens)
            s6_run_report = _load_json(s6_run_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S7_001_S6_NOT_PASS",
                "V-02",
                "s6_run_report_missing",
                {"component": "S6_RUN_REPORT", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        run_schema = _schema_for_payload(schema_layer1, schema_layer1, "run_report/segment_state_run")
        run_errors = list(Draft202012Validator(run_schema).iter_errors(s6_run_report))
        if run_errors:
            _abort(
                "E3A_S7_001_S6_NOT_PASS",
                "V-02",
                "s6_run_report_schema_invalid",
                {"component": "S6_RUN_REPORT", "error": str(run_errors[0])},
                manifest_fingerprint,
            )
        if s6_run_report.get("status") != "PASS" or s6_run_report.get("error_code") not in (None, "", "null"):
            _abort(
                "E3A_S7_001_S6_NOT_PASS",
                "V-02",
                "s6_run_report_not_pass",
                {
                    "component": "S6_RUN_REPORT",
                    "status": s6_run_report.get("status"),
                    "error_code": s6_run_report.get("error_code"),
                },
                manifest_fingerprint,
            )

        current_phase = "s6_receipt"
        s6_receipt_entry = find_dataset_entry(dictionary, DATASET_S6_RECEIPT).entry
        try:
            s6_receipt_path = _resolve_dataset_path(s6_receipt_entry, run_paths, config.external_roots, tokens)
            s6_receipt = _load_json(s6_receipt_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S7_001_S6_NOT_PASS",
                "V-03",
                "s6_receipt_missing",
                {"component": "S6_RECEIPT", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        receipt_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s6_receipt_3A")
        receipt_errors = list(Draft202012Validator(receipt_schema).iter_errors(s6_receipt))
        if receipt_errors:
            _abort(
                "E3A_S7_001_S6_NOT_PASS",
                "V-03",
                "s6_receipt_schema_invalid",
                {"component": "S6_RECEIPT", "error": str(receipt_errors[0])},
                manifest_fingerprint,
            )
        if str(s6_receipt.get("overall_status")) != "PASS":
            _abort(
                "E3A_S7_001_S6_NOT_PASS",
                "V-03",
                "s6_receipt_not_pass",
                {"component": "S6_RECEIPT", "overall_status": s6_receipt.get("overall_status")},
                manifest_fingerprint,
            )
        s6_receipt_digest = _json_digest(s6_receipt)

        current_phase = "s0_gate"
        s0_entry = find_dataset_entry(dictionary, DATASET_S0_GATE).entry
        try:
            s0_path = _resolve_dataset_path(s0_entry, run_paths, config.external_roots, tokens)
            s0_gate = _load_json(s0_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                "V-04",
                "s0_gate_missing",
                {"component": "S0_GATE", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s0_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A")
        s0_errors = list(Draft202012Validator(s0_schema).iter_errors(s0_gate))
        if s0_errors:
            _abort(
                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                "V-04",
                "s0_gate_schema_invalid",
                {"component": "S0_GATE", "error": str(s0_errors[0])},
                manifest_fingerprint,
            )
        upstream_gates = s0_gate.get("upstream_gates") or {}
        gate_failures = [
            seg
            for seg in ("1A", "1B", "2A")
            if (upstream_gates.get(f"segment_{seg}") or {}).get("status") != "PASS"
        ]
        if gate_failures:
            _abort(
                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                "V-04",
                "upstream_gate_not_pass",
                {"component": "S0_GATE", "segments": gate_failures},
                manifest_fingerprint,
            )

        sealed_entry = find_dataset_entry(dictionary, DATASET_SEALED_INPUTS).entry
        try:
            sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
            sealed_inputs = _load_json(sealed_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                "V-04",
                "sealed_inputs_missing",
                {"component": "SEALED_INPUTS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        if not isinstance(sealed_inputs, list):
            _abort(
                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                "V-04",
                "sealed_inputs_not_list",
                {"component": "SEALED_INPUTS", "path": str(sealed_path)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/sealed_inputs_3A")
        sealed_validator = Draft202012Validator(sealed_schema)
        for idx, row in enumerate(sealed_inputs, start=1):
            if not isinstance(row, dict):
                _abort(
                    "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                    "V-04",
                    "sealed_inputs_not_object",
                    {"component": "SEALED_INPUTS", "path": str(sealed_path), "row_index": idx},
                    manifest_fingerprint,
                )
            sealed_errors = list(sealed_validator.iter_errors(row))
            if sealed_errors:
                _abort(
                    "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                    "V-04",
                    "sealed_inputs_schema_invalid",
                    {
                        "component": "SEALED_INPUTS",
                        "row_index": idx,
                        "error": sealed_errors[0].message,
                    },
                    manifest_fingerprint,
                )

        logger.info("S7: gating checks passed (S6 PASS + S0 upstream PASS).")

        current_phase = "members"
        logger.info(
            "S7: building bundle members (index_only=true, rng_logs_included=true) for manifest=%s",
            manifest_fingerprint,
        )

        members: list[dict] = []
        member_ids_seen: set[str] = set()
        s6_report_digest_expected = str(s6_receipt.get("validation_report_digest") or "")
        s6_issue_digest_expected = str(s6_receipt.get("issue_table_digest") or "")
        s6_report_digest_actual = ""
        s6_issue_digest_actual = ""

        for dataset_id, role, kind in MEMBER_SPECS:
            entry = find_dataset_entry(dictionary, dataset_id).entry
            schema_ref = str(entry.get("schema_ref") or "")
            if not schema_ref:
                _abort(
                    "E3A_S7_003_INDEX_BUILD_FAILED",
                    "V-05",
                    "member_schema_ref_missing",
                    {"dataset_id": dataset_id},
                    manifest_fingerprint,
                )
            schema_pack, anchor = _schema_pack_for_ref(schema_ref, schema_3a, schema_layer1)
            path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            path_str = _render_catalog_path(entry, tokens)
            if kind != "log" and not path.exists():
                _abort(
                    "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                    "V-05",
                    "member_missing",
                    {"dataset_id": dataset_id, "path": str(path)},
                    manifest_fingerprint,
                )

            digest = ""
            size_bytes = 0
            if kind == "json":
                payload = _load_json(path)
                schema = _schema_for_payload(schema_pack, schema_layer1, anchor)
                if dataset_id == DATASET_SEALED_INPUTS:
                    if not isinstance(payload, list):
                        _abort(
                            "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                            "V-05",
                            "member_schema_invalid",
                            {"dataset_id": dataset_id, "error": "sealed_inputs payload is not a list"},
                            manifest_fingerprint,
                        )
                    validator = Draft202012Validator(schema)
                    for idx, row in enumerate(payload, start=1):
                        if not isinstance(row, dict):
                            _abort(
                                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                                "V-05",
                                "member_schema_invalid",
                                {"dataset_id": dataset_id, "row_index": idx, "error": "row is not an object"},
                                manifest_fingerprint,
                            )
                        errors = list(validator.iter_errors(row))
                        if errors:
                            _abort(
                                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                                "V-05",
                                "member_schema_invalid",
                                {
                                    "dataset_id": dataset_id,
                                    "row_index": idx,
                                    "error": errors[0].message,
                                },
                                manifest_fingerprint,
                            )
                else:
                    errors = list(Draft202012Validator(schema).iter_errors(payload))
                    if errors:
                        _abort(
                            "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                            "V-05",
                            "member_schema_invalid",
                            {"dataset_id": dataset_id, "error": str(errors[0])},
                            manifest_fingerprint,
                        )
                digest = _json_digest(payload)
                size_bytes = path.stat().st_size
            elif kind == "parquet":
                parquet_paths = _list_parquet_paths(path)
                if dataset_id in TRUSTED_PARQUET_MEMBERS:
                    required = REQUIRED_PARQUET_COLUMNS.get(dataset_id) or []
                    schema_names = (
                        pl.scan_parquet([str(member_path) for member_path in parquet_paths])
                        .collect_schema()
                        .names()
                    )
                    missing = [column for column in required if column not in schema_names]
                    if missing:
                        _abort(
                            "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                            "V-05",
                            "member_schema_invalid",
                            {
                                "dataset_id": dataset_id,
                                "error": "required parquet columns missing",
                                "missing_columns": missing,
                            },
                            manifest_fingerprint,
                        )
                else:
                    df = pl.read_parquet(parquet_paths)
                    schema_def = _schema_from_pack(schema_pack, anchor)
                    if schema_def.get("type") == "object":
                        schema = _schema_for_payload(schema_pack, schema_layer1, anchor)
                        validator = Draft202012Validator(schema)
                        for row in df.iter_rows(named=True):
                            payload = {key: value for key, value in row.items() if value is not None}
                            errors = list(validator.iter_errors(payload))
                            if errors:
                                _abort(
                                    "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                                    "V-05",
                                    "member_schema_invalid",
                                    {"dataset_id": dataset_id, "error": errors[0].message},
                                    manifest_fingerprint,
                                )
                    else:
                        table_pack, table_name = _table_pack(schema_pack, anchor)
                        _inline_external_refs(table_pack, schema_layer1, "schemas.layer1.yaml#")
                        try:
                            validate_dataframe(df.iter_rows(named=True), table_pack, table_name)
                        except SchemaValidationError as exc:
                            _abort(
                                "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                                "V-05",
                                "member_schema_invalid",
                                {"dataset_id": dataset_id, "error": str(exc)},
                                manifest_fingerprint,
                            )
                digest, size_bytes = _hash_paths(parquet_paths, logger, f"S7: hash {dataset_id}")
            elif kind == "log":
                try:
                    log_paths = _resolve_event_paths(entry, run_paths, config.external_roots, tokens)
                except InputResolutionError as exc:
                    _abort(
                        "E3A_S7_002_PRECONDITION_MISSING_ARTEFACT",
                        "V-05",
                        "member_missing",
                        {"dataset_id": dataset_id, "path": str(path), "detail": str(exc)},
                        manifest_fingerprint,
                    )
                log_schema = _schema_for_payload(schema_pack, schema_layer1, anchor)
                digest, size_bytes = _hash_jsonl_with_validation(
                    log_paths, log_schema, logger, f"S7: hash {dataset_id}"
                )
            else:
                _abort(
                    "E3A_S7_003_INDEX_BUILD_FAILED",
                    "V-05",
                    "member_kind_unknown",
                    {"dataset_id": dataset_id, "kind": kind},
                    manifest_fingerprint,
                )

            member = {
                "logical_id": dataset_id,
                "path": path_str,
                "schema_ref": schema_ref,
                "sha256_hex": digest,
                "role": role,
                "size_bytes": int(size_bytes),
            }
            members.append(member)
            member_bytes += int(size_bytes)
            if dataset_id in member_ids_seen:
                _abort(
                    "E3A_S7_003_INDEX_BUILD_FAILED",
                    "V-05",
                    "member_duplicate",
                    {"dataset_id": dataset_id},
                    manifest_fingerprint,
                )
            member_ids_seen.add(dataset_id)
            if dataset_id == DATASET_S6_REPORT:
                s6_report_digest_actual = digest
            if dataset_id == DATASET_S6_ISSUES:
                s6_issue_digest_actual = digest
            logger.info(
                "S7: member_digest dataset=%s role=%s files_bytes=%d sha256=%s",
                dataset_id,
                role,
                size_bytes,
                digest,
            )

        if s6_report_digest_actual != s6_report_digest_expected:
            _abort(
                "E3A_S7_004_DIGEST_MISMATCH",
                "V-06",
                "s6_report_digest_mismatch",
                {
                    "expected": s6_report_digest_expected,
                    "computed": s6_report_digest_actual,
                },
                manifest_fingerprint,
            )
        if s6_issue_digest_actual != s6_issue_digest_expected:
            _abort(
                "E3A_S7_004_DIGEST_MISMATCH",
                "V-06",
                "s6_issue_digest_mismatch",
                {
                    "expected": s6_issue_digest_expected,
                    "computed": s6_issue_digest_actual,
                },
                manifest_fingerprint,
            )

        members = sorted(members, key=lambda item: str(item.get("logical_id", "")))
        member_count = len(members)
        if member_count == 0:
            _abort(
                "E3A_S7_003_INDEX_BUILD_FAILED",
                "V-05",
                "members_empty",
                {"detail": "no bundle members constructed"},
                manifest_fingerprint,
            )

        index_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "s6_receipt_digest": s6_receipt_digest,
            "members": members,
        }
        index_schema = _schema_for_payload(schema_layer1, schema_layer1, "validation/validation_bundle_index_3A")
        index_errors = list(Draft202012Validator(index_schema).iter_errors(index_payload))
        if index_errors:
            _abort(
                "E3A_S7_003_INDEX_BUILD_FAILED",
                "V-05",
                "index_schema_invalid",
                {"error": str(index_errors[0])},
                manifest_fingerprint,
            )

        bundle_digest = _sha256_concat_hex([str(member["sha256_hex"]) for member in members])
        flag_schema = _schema_for_payload(schema_layer1, schema_layer1, "validation/passed_flag_3A")
        flag_payload = f"sha256_hex = {bundle_digest}"
        flag_errors = list(Draft202012Validator(flag_schema).iter_errors(flag_payload))
        if flag_errors:
            _abort(
                "E3A_S7_005_HASHGATE_MISMATCH",
                "V-06",
                "flag_schema_invalid",
                {"error": str(flag_errors[0])},
                manifest_fingerprint,
            )

        bundle_entry = find_dataset_entry(dictionary, DATASET_BUNDLE).entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        bundle_catalog_path = _render_catalog_path(bundle_entry, tokens)
        if f"manifest_fingerprint={manifest_fingerprint}" not in bundle_catalog_path:
            _abort(
                "E3A_S7_003_INDEX_BUILD_FAILED",
                "V-06",
                "bundle_partition_mismatch",
                {"path": bundle_catalog_path},
                manifest_fingerprint,
            )
        index_path = bundle_root / "index.json"

        flag_entry = find_dataset_entry(dictionary, DATASET_FLAG).entry
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        flag_catalog_path = _render_catalog_path(flag_entry, tokens)
        if f"manifest_fingerprint={manifest_fingerprint}" not in flag_catalog_path:
            _abort(
                "E3A_S7_003_INDEX_BUILD_FAILED",
                "V-06",
                "flag_partition_mismatch",
                {"path": flag_catalog_path},
                manifest_fingerprint,
            )
        if flag_path.parent != bundle_root:
            _abort(
                "E3A_S7_003_INDEX_BUILD_FAILED",
                "V-06",
                "flag_bundle_mismatch",
                {"flag_path": str(flag_path), "bundle_root": str(bundle_root)},
                manifest_fingerprint,
            )

        current_phase = "publish"
        index_bytes = _json_bytes(index_payload)
        if bundle_root.exists():
            existing_index = index_path.read_bytes() if index_path.exists() else None
            existing_flag = flag_path.read_text(encoding="ascii").strip() if flag_path.exists() else None
            if existing_index != index_bytes or existing_flag != flag_payload:
                _abort(
                    "E3A_S7_006_IMMUTABILITY_VIOLATION",
                    "V-07",
                    "bundle_immutability_violation",
                    {"bundle_root": str(bundle_root)},
                    manifest_fingerprint,
                )
            logger.info("S7: bundle already exists and is identical; skipping publish.")
        else:
            tmp_root = run_paths.tmp_root / f"s7_validation_bundle_{uuid.uuid4().hex}"
            tmp_root.mkdir(parents=True, exist_ok=True)
            _write_json(tmp_root / "index.json", index_payload)
            _write_flag(tmp_root / "_passed.flag", bundle_digest)
            bundle_root.parent.mkdir(parents=True, exist_ok=True)
            tmp_root.replace(bundle_root)
            logger.info("S7: bundle published path=%s", bundle_root)

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
            error_code = "E3A_S7_003_INDEX_BUILD_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S7_007_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S7_007_INFRASTRUCTURE_IO_ERROR"
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
                logger.warning("S7: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s7_run_report_3A").entry
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
                    "counts": {"member_count": member_count, "member_bytes": member_bytes},
                    "digests": {
                        "bundle_digest": bundle_digest,
                        "s6_receipt_digest": s6_receipt_digest,
                    },
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "bundle_path": bundle_catalog_path if bundle_root else None,
                        "index_path": (bundle_catalog_path + "index.json") if bundle_catalog_path else None,
                        "flag_path": flag_catalog_path if flag_path else None,
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S7: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S7: failed to write run-report: %s", exc)

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
                    error_details=error_context,
                )

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3A_S7_007_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if bundle_root is None or index_path is None or flag_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S7_007_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S7Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        bundle_root=bundle_root,
        index_path=index_path,
        flag_path=flag_path,
    )


__all__ = ["S7Result", "run_s7"]
