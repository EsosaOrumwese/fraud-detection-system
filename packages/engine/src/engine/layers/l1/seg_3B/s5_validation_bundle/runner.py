
"""S5 validation bundle & passed flag for Segment 3B."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import orjson
import polars as pl
from jsonschema import Draft202012Validator

try:
    import fastjsonschema
    from fastjsonschema import JsonSchemaException as FastJsonSchemaException
except Exception:  # pragma: no cover - optional backend fallback
    fastjsonschema = None
    FastJsonSchemaException = Exception  # type: ignore[assignment]

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
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_3B.s0_gate.runner import (
    _hash_partition,
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _table_pack,
)


MODULE_NAME = "3B.S5.validation_bundle"
SEGMENT = "3B"
STATE = "S5"

DATASET_S0_GATE = "s0_gate_receipt_3B"
DATASET_SEALED_INPUTS = "sealed_inputs_3B"
DATASET_S1_CLASS = "virtual_classification_3B"
DATASET_S1_SETTLE = "virtual_settlement_3B"
DATASET_S2_EDGE = "edge_catalogue_3B"
DATASET_S2_EDGE_INDEX = "edge_catalogue_index_3B"
DATASET_S3_ALIAS_BLOB = "edge_alias_blob_3B"
DATASET_S3_ALIAS_INDEX = "edge_alias_index_3B"
DATASET_S3_UNIVERSE = "edge_universe_hash_3B"
DATASET_S4_POLICY = "virtual_routing_policy_3B"
DATASET_S4_CONTRACT = "virtual_validation_contract_3B"
DATASET_S4_SUMMARY = "s4_run_summary_3B"
DATASET_RNG_AUDIT = "rng_audit_log"
DATASET_RNG_TRACE = "rng_trace_log"
DATASET_RNG_EDGE_JITTER = "rng_event_edge_jitter"
DATASET_RNG_EDGE_TILE = "rng_event_edge_tile_assign"

DATASET_BUNDLE = "validation_bundle_3B"
DATASET_BUNDLE_INDEX = "validation_bundle_index_3B"
DATASET_FLAG = "validation_passed_flag_3B"
DATASET_S5_MANIFEST = "s5_manifest_3B"
DATASET_S5_STRUCT = "s5_structural_summary_3B"
DATASET_S5_RNG = "s5_rng_summary_3B"
DATASET_S5_DIGEST = "s5_digest_summary_3B"
DATASET_S5_REPORT = "s5_run_report_3B"

# POPT.2R.1: lower hash-lane log cadence to reduce avoidable log drag.
S5_HASH_PROGRESS_LOG_INTERVAL_S = 5.0

# POPT.2R.2: compiled-validator cache for hot JSONL schema lanes.
_FASTJSONSCHEMA_VALIDATOR_CACHE: dict[str, Callable[[object], None]] = {}


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    bundle_root: Path
    index_path: Path
    flag_path: Path
    run_report_path: Path


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
    def __init__(
        self,
        total: Optional[int],
        logger,
        label: str,
        min_log_interval_s: float = 0.5,
    ) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._min_log_interval_s = float(min_log_interval_s)
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < self._min_log_interval_s and not (
            self._total is not None and self._processed >= self._total
        ):
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        if self._total and self._total > 0:
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
        else:
            self._logger.info(
                "%s processed=%s (elapsed=%.2fs, rate=%.2f/s)",
                self._label,
                self._processed,
                elapsed,
                rate,
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
    logger = get_logger("engine.layers.l1.seg_3B.s5_validation_bundle.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_digest(payload: object) -> str:
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _schema_digest(schema: dict) -> str:
    return hashlib.sha256(
        json.dumps(schema, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parse_json_payload(payload: bytes, path: Path, line_no: int) -> object:
    try:
        return orjson.loads(payload)
    except orjson.JSONDecodeError as exc:
        raise SchemaValidationError(
            f"JSONL parse failed at {path}:{line_no}: {exc}"
        ) from exc


def _build_record_validator(schema: dict, logger, label: str) -> Callable[[object, Path, int], None]:
    if fastjsonschema is not None:
        try:
            cache_key = _schema_digest(schema)
            compiled = _FASTJSONSCHEMA_VALIDATOR_CACHE.get(cache_key)
            if compiled is None:
                compiled = fastjsonschema.compile(schema)
                _FASTJSONSCHEMA_VALIDATOR_CACHE[cache_key] = compiled
            logger.info("%s: validator_backend=fastjsonschema_compiled", label)

            def _validate_fast(record: object, path: Path, line_no: int) -> None:
                try:
                    compiled(record)
                except FastJsonSchemaException as exc:
                    raise SchemaValidationError(
                        f"JSONL schema validation failed at {path}:{line_no}: {exc.message}"
                    ) from exc

            return _validate_fast
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "%s: validator_backend=fastjsonschema_compile_failed fallback=draft202012 detail=%s",
                label,
                exc,
            )
    draft_validator = Draft202012Validator(schema)
    logger.info("%s: validator_backend=draft202012", label)

    def _validate_draft(record: object, path: Path, line_no: int) -> None:
        error = next(draft_validator.iter_errors(record), None)
        if error is not None:
            raise SchemaValidationError(
                f"JSONL schema validation failed at {path}:{line_no}: {error.message}"
            )

    return _validate_draft


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _write_flag(path: Path, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"sha256_hex = {digest}\n", encoding="ascii")


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _validate_payload(schema_pack: dict, schema_layer1: dict, anchor: str, payload: object) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, anchor)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(str(errors[0]), [])


def _resolve_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _hash_dataset(path: Path) -> str:
    if path.is_dir():
        digest, _ = _hash_partition(path)
        return digest
    return sha256_file(path).sha256_hex


def _resolve_event_paths(entry: dict, run_paths: RunPaths, external_roots: list[Path], tokens: dict[str, str]) -> list[Path]:
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


def _hash_jsonl_with_validation(
    paths: list[Path],
    schema: dict,
    logger,
    label: str,
    on_record: Optional[Callable[[dict], None]] = None,
) -> tuple[str, int, int]:
    validate_record = _build_record_validator(schema, logger, label)
    tracker = _ProgressTracker(
        None,
        logger,
        label,
        min_log_interval_s=S5_HASH_PROGRESS_LOG_INTERVAL_S,
    )
    hasher = hashlib.sha256()
    total_bytes = 0
    total_events = 0
    for path in paths:
        with path.open("rb") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line:
                    continue
                hasher.update(line)
                total_bytes += len(line)
                payload = line.rstrip(b"\r\n")
                if payload:
                    total_events += 1
                    record = _parse_json_payload(payload, path, line_no)
                    validate_record(record, path, line_no)
                    if on_record is not None:
                        on_record(record)
                tracker.update(1)
    return hasher.hexdigest(), total_bytes, total_events


def _pick_trace_row(best: Optional[dict], row: dict) -> dict:
    if best is None:
        return row
    key = (int(row.get("rng_counter_after_hi") or 0), int(row.get("rng_counter_after_lo") or 0))
    best_key = (
        int(best.get("rng_counter_after_hi") or 0),
        int(best.get("rng_counter_after_lo") or 0),
    )
    if key > best_key:
        return row
    return best


def _validate_parquet_rows(
    files: list[Path],
    schema_pack: dict,
    schema_layer1: dict,
    anchor: str,
    label: str,
    manifest_fingerprint: Optional[str],
) -> None:
    logger = get_logger("engine.layers.l1.seg_3B.s5_validation_bundle.l2.runner")
    pack, table_name = _table_pack(schema_pack, anchor)
    _inline_external_refs(pack, schema_layer1, "schemas.layer1.yaml#")
    progress = _ProgressTracker(len(files), logger, f"S5: validate {label} files")
    for file_path in files:
        df = pl.read_parquet(file_path)
        try:
            validate_dataframe(df.iter_rows(named=True), pack, table_name)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S5_INPUT_SCHEMA_INVALID",
                "V-10",
                f"{label}_schema_invalid",
                {"error": str(exc), "path": str(file_path)},
                manifest_fingerprint,
            )
        progress.update(1)


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


def _drop_none(value: object) -> object:
    if isinstance(value, dict):
        return {key: _drop_none(val) for key, val in value.items() if val is not None}
    if isinstance(value, list):
        return [_drop_none(item) for item in value if item is not None]
    return value

def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l1.seg_3B.s5_validation_bundle.l2.runner")
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
    run_report_path: Optional[Path] = None

    current_phase = "run_receipt"
    checks: list[dict] = []
    tokens: dict[str, str] = {}
    run_paths: Optional[RunPaths] = None
    dictionary_3b: Optional[dict] = None

    try:
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = receipt.get("run_id")
        if not run_id_value:
            raise InputResolutionError("run_receipt missing run_id.")
        if receipt_path.parent.name != run_id_value:
            raise InputResolutionError("run_receipt path does not match embedded run_id.")
        parameter_hash = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if manifest_fingerprint is None or parameter_hash is None:
            raise InputResolutionError("run_receipt missing manifest_fingerprint or parameter_hash.")
        seed = int(receipt.get("seed"))

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        logger.info("S5: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        reg_3b_path, registry_3b = load_artefact_registry(source, "3B")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s",
            config.contracts_layout,
            config.contracts_root,
            dict_3b_path,
            reg_3b_path,
            ",".join([str(schema_3b_path), str(schema_2b_path), str(schema_layer1_path)]),
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "run_id": str(run_id_value),
        }

        logger.info(
            "S5: objective=validate 3B artefacts + RNG logs -> bundle index + passed flag; "
            "gated inputs (s0_gate_receipt_3B, sealed_inputs_3B, S1-S4 outputs, RNG logs) -> "
            "outputs (validation_bundle_3B, validation_bundle_index_3B, validation_passed_flag_3B, s5_manifest_3B)"
        )

        current_phase = "s0_gate"
        gate_entry = find_dataset_entry(dictionary_3b, DATASET_S0_GATE).entry
        gate_path = _resolve_dataset_path(gate_entry, run_paths, config.external_roots, tokens)
        gate_payload = _load_json(gate_path)
        _validate_payload(schema_3b, schema_layer1, "validation/s0_gate_receipt_3B", gate_payload)
        if gate_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _abort(
                "E3B_S5_IDENTITY_MISMATCH",
                "V-01",
                "gate_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": gate_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        if gate_payload.get("seed") not in (None, seed) or gate_payload.get("parameter_hash") not in (
            None,
            parameter_hash,
        ):
            _abort(
                "E3B_S5_IDENTITY_MISMATCH",
                "V-01",
                "gate_identity_mismatch",
                {
                    "seed": gate_payload.get("seed"),
                    "parameter_hash": gate_payload.get("parameter_hash"),
                },
                manifest_fingerprint,
            )
        for segment_id in ("segment_1A", "segment_1B", "segment_2A", "segment_3A"):
            status_value = gate_payload.get("upstream_gates", {}).get(segment_id, {}).get("status")
            if status_value != "PASS":
                _abort(
                    "E3B_S5_UPSTREAM_GATE_NOT_PASS",
                    "V-02",
                    "upstream_gate_not_pass",
                    {"segment": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        current_phase = "sealed_inputs"
        sealed_entry = find_dataset_entry(dictionary_3b, DATASET_SEALED_INPUTS).entry
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        sealed_payload = _load_json(sealed_path)
        if not isinstance(sealed_payload, list):
            _abort(
                "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                "V-03",
                "sealed_inputs_not_list",
                {"path": str(sealed_path)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_for_payload(schema_3b, schema_layer1, "validation/sealed_inputs_3B")
        validator = Draft202012Validator(sealed_schema)
        sealed_by_id: dict[str, dict] = {}
        for idx, row in enumerate(sealed_payload, start=1):
            if not isinstance(row, dict):
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-03",
                    "sealed_input_not_object",
                    {"row_index": idx},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-03",
                    "sealed_input_schema_invalid",
                    {"row_index": idx, "error": errors[0].message},
                    manifest_fingerprint,
                )
            if row.get("manifest_fingerprint") != str(manifest_fingerprint):
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-03",
                    "sealed_manifest_mismatch",
                    {"expected": manifest_fingerprint, "actual": row.get("manifest_fingerprint")},
                    manifest_fingerprint,
                )
            logical_id = str(row.get("logical_id") or "")
            if not logical_id:
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-03",
                    "sealed_logical_id_missing",
                    {"row_index": idx},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        required_sealed = [
            "cdn_country_weights",
            "mcc_channel_rules",
            "alias_layout_policy_v1",
            "route_rng_policy_v1",
            "virtual_validation_policy",
            "virtual_routing_fields_v1",
        ]

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "sealed_input_missing",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_row = sealed_by_id[logical_id]
            entry = find_dataset_entry(dictionary_3b, logical_id).entry
            expected_path = _render_catalog_path(entry, tokens).rstrip("/")
            sealed_path_value = str(sealed_row.get("path") or "").rstrip("/")
            if expected_path != sealed_path_value:
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "sealed_path_mismatch",
                    {"logical_id": logical_id, "expected": expected_path, "actual": sealed_path_value},
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "input_missing",
                    {"logical_id": logical_id, "path": str(asset_path)},
                    manifest_fingerprint,
                )
            computed_digest = _hash_dataset(asset_path)
            sealed_digest = str(sealed_row.get("sha256_hex") or "")
            if computed_digest != sealed_digest:
                _abort(
                    "E3B_S5_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "sealed_digest_mismatch",
                    {
                        "logical_id": logical_id,
                        "path": str(asset_path),
                        "sealed_sha256_hex": sealed_digest,
                        "computed_sha256_hex": computed_digest,
                    },
                    manifest_fingerprint,
                )
            return sealed_row, asset_path, computed_digest

        sealed_assets: dict[str, tuple[dict, Path, str]] = {}
        for logical_id in required_sealed:
            sealed_assets[logical_id] = _verify_sealed_asset(logical_id)

        timer.info("S5: sealed inputs validated and required policy digests verified")

        current_phase = "s1_inputs"
        class_entry = find_dataset_entry(dictionary_3b, DATASET_S1_CLASS).entry
        settle_entry = find_dataset_entry(dictionary_3b, DATASET_S1_SETTLE).entry
        class_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        settle_path = _resolve_dataset_path(settle_entry, run_paths, config.external_roots, tokens)
        class_files = _resolve_parquet_files(class_path)
        settle_files = _resolve_parquet_files(settle_path)
        _validate_parquet_rows(class_files, schema_3b, schema_layer1, "plan/virtual_classification_3B", "S1", manifest_fingerprint)
        _validate_parquet_rows(settle_files, schema_3b, schema_layer1, "plan/virtual_settlement_3B", "S1", manifest_fingerprint)
        class_df = pl.read_parquet(class_files)
        settle_df = pl.read_parquet(settle_files)
        virtual_ids = {
            int(row["merchant_id"])
            for row in class_df.iter_rows(named=True)
            if row.get("is_virtual")
        }
        settlement_ids = {int(row["merchant_id"]) for row in settle_df.iter_rows(named=True)}
        missing_settlement = sorted(virtual_ids - settlement_ids)
        extra_settlement = sorted(settlement_ids - virtual_ids)
        if missing_settlement or extra_settlement:
            _abort(
                "E3B_S5_S1_CONTRACT_VIOLATION",
                "V-05",
                "s1_settlement_mismatch",
                {
                    "missing_count": len(missing_settlement),
                    "extra_count": len(extra_settlement),
                    "missing_sample": missing_settlement[:10],
                    "extra_sample": extra_settlement[:10],
                },
                manifest_fingerprint,
            )
        checks.append(
            {
                "check_id": "S1_VIRTUAL_SETTLEMENT_MATCH",
                "status": "PASS",
                "affected_count": len(virtual_ids),
                "detail": "virtual merchants match settlement rows",
            }
        )

        current_phase = "s2_inputs"
        edge_index_entry = find_dataset_entry(dictionary_3b, DATASET_S2_EDGE_INDEX).entry
        edge_entry = find_dataset_entry(dictionary_3b, DATASET_S2_EDGE).entry
        edge_index_path = _resolve_dataset_path(edge_index_entry, run_paths, config.external_roots, tokens)
        edge_path = _resolve_dataset_path(edge_entry, run_paths, config.external_roots, tokens)
        edge_index_files = _resolve_parquet_files(edge_index_path)
        edge_files = _resolve_parquet_files(edge_path)
        _validate_parquet_rows(edge_index_files, schema_3b, schema_layer1, "plan/edge_catalogue_index_3B", "S2 index", manifest_fingerprint)
        _validate_parquet_rows(edge_files, schema_3b, schema_layer1, "plan/edge_catalogue_3B", "S2 edges", manifest_fingerprint)
        edge_index_df = pl.read_parquet(edge_index_files)
        edge_index_df = edge_index_df.with_columns(pl.col("scope").cast(pl.Utf8))
        merchant_rows = edge_index_df.filter(pl.col("scope") == "MERCHANT")
        expected_counts = {
            int(row["merchant_id"]): int(row["edge_count_total"])
            for row in merchant_rows.iter_rows(named=True)
            if row.get("merchant_id") is not None
        }
        global_row = edge_index_df.filter(pl.col("scope") == "GLOBAL")
        edge_count_total_all = None
        edge_catalogue_digest_global = None
        if global_row.height > 0:
            row = global_row.to_dicts()[0]
            edge_count_total_all = row.get("edge_count_total_all_merchants")
            edge_catalogue_digest_global = row.get("edge_catalogue_digest_global")
        edge_scan = pl.scan_parquet(edge_files).select(["merchant_id", "edge_id", "lat_deg", "lon_deg", "tzid_operational"])
        edge_counts_df = edge_scan.group_by("merchant_id").len().collect()
        edge_counts = {
            int(row["merchant_id"]): int(row["len"]) for row in edge_counts_df.iter_rows(named=True)
        }
        if edge_count_total_all is not None and sum(edge_counts.values()) != int(edge_count_total_all):
            _abort(
                "E3B_S5_S2_CONTRACT_VIOLATION",
                "V-06",
                "edge_total_mismatch",
                {"expected": int(edge_count_total_all), "actual": sum(edge_counts.values())},
                manifest_fingerprint,
            )
        count_mismatch = []
        for merchant_id, expected in expected_counts.items():
            actual = edge_counts.get(merchant_id)
            if actual is None or actual != expected:
                count_mismatch.append((merchant_id, expected, actual))
            if len(count_mismatch) >= 10:
                break
        if count_mismatch:
            _abort(
                "E3B_S5_S2_CONTRACT_VIOLATION",
                "V-06",
                "edge_count_mismatch",
                {"examples": count_mismatch, "mismatch_count": len(count_mismatch)},
                manifest_fingerprint,
            )
        checks.append(
            {
                "check_id": "S2_EDGE_COUNTS_MATCH",
                "status": "PASS",
                "affected_count": len(edge_counts),
                "detail": "edge catalogue counts match index",
            }
        )

        current_phase = "s3_inputs"
        alias_index_entry = find_dataset_entry(dictionary_3b, DATASET_S3_ALIAS_INDEX).entry
        alias_blob_entry = find_dataset_entry(dictionary_3b, DATASET_S3_ALIAS_BLOB).entry
        universe_entry = find_dataset_entry(dictionary_3b, DATASET_S3_UNIVERSE).entry
        alias_index_path = _resolve_dataset_path(alias_index_entry, run_paths, config.external_roots, tokens)
        alias_blob_path = _resolve_dataset_path(alias_blob_entry, run_paths, config.external_roots, tokens)
        universe_path = _resolve_dataset_path(universe_entry, run_paths, config.external_roots, tokens)
        alias_index_files = _resolve_parquet_files(alias_index_path)
        _validate_parquet_rows(alias_index_files, schema_3b, schema_layer1, "plan/edge_alias_index_3B", "S3 alias index", manifest_fingerprint)
        alias_index_df = pl.read_parquet(alias_index_files)
        alias_index_df = alias_index_df.with_columns(pl.col("scope").cast(pl.Utf8))
        alias_merchant_rows = alias_index_df.filter(pl.col("scope") == "MERCHANT")
        alias_counts = {
            int(row["merchant_id"]): int(row["edge_count_total"])
            for row in alias_merchant_rows.iter_rows(named=True)
            if row.get("merchant_id") is not None
        }
        missing_alias = sorted(set(expected_counts.keys()) - set(alias_counts.keys()))
        if missing_alias:
            _abort(
                "E3B_S5_S3_CONTRACT_VIOLATION",
                "V-07",
                "alias_index_missing_merchants",
                {"missing_merchants": missing_alias[:10], "missing_count": len(missing_alias)},
                manifest_fingerprint,
            )
        alias_count_mismatch = []
        for merchant_id, expected in expected_counts.items():
            actual = alias_counts.get(merchant_id)
            if actual is None or actual != expected:
                alias_count_mismatch.append((merchant_id, expected, actual))
            if len(alias_count_mismatch) >= 10:
                break
        if alias_count_mismatch:
            _abort(
                "E3B_S5_S3_CONTRACT_VIOLATION",
                "V-07",
                "alias_count_mismatch",
                {"examples": alias_count_mismatch, "mismatch_count": len(alias_count_mismatch)},
                manifest_fingerprint,
            )

        universe_payload = _load_json(universe_path)
        _validate_payload(schema_3b, schema_layer1, "validation/edge_universe_hash_3B", universe_payload)
        if universe_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _abort(
                "E3B_S5_S3_CONTRACT_VIOLATION",
                "V-07",
                "universe_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": universe_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        edge_catalogue_index_digest = _hash_dataset(edge_index_path)
        edge_alias_index_digest = _hash_dataset(alias_index_path)
        if universe_payload.get("edge_catalogue_index_digest") != edge_catalogue_index_digest:
            _abort(
                "E3B_S5_DIGEST_COMPONENT_MISMATCH",
                "V-07",
                "edge_catalogue_index_digest_mismatch",
                {
                    "expected": universe_payload.get("edge_catalogue_index_digest"),
                    "actual": edge_catalogue_index_digest,
                },
                manifest_fingerprint,
            )
        if universe_payload.get("edge_alias_index_digest") != edge_alias_index_digest:
            _abort(
                "E3B_S5_DIGEST_COMPONENT_MISMATCH",
                "V-07",
                "edge_alias_index_digest_mismatch",
                {
                    "expected": universe_payload.get("edge_alias_index_digest"),
                    "actual": edge_alias_index_digest,
                },
                manifest_fingerprint,
            )

        cdn_weights_digest = sealed_assets["cdn_country_weights"][2]
        virtual_rules_digest = sealed_assets["mcc_channel_rules"][2]
        components = [
            ("cdn_weights", cdn_weights_digest),
            ("edge_alias_index", edge_alias_index_digest),
            ("edge_catalogue_index", edge_catalogue_index_digest),
            ("virtual_rules", virtual_rules_digest),
        ]
        components.sort(key=lambda item: item[0])
        digest_bytes = b"".join(bytes.fromhex(str(item[1])) for item in components)
        recomputed_universe_hash = hashlib.sha256(digest_bytes).hexdigest()
        if recomputed_universe_hash != universe_payload.get("universe_hash"):
            _abort(
                "E3B_S5_UNIVERSE_HASH_MISMATCH",
                "V-07",
                "universe_hash_mismatch",
                {"expected": universe_payload.get("universe_hash"), "actual": recomputed_universe_hash},
                manifest_fingerprint,
            )

        alias_blob_digest = sha256_file(alias_blob_path).sha256_hex
        alias_blob_global = alias_index_df.filter(pl.col("scope") == "GLOBAL")
        if alias_blob_global.height > 0:
            blob_sha = alias_blob_global.to_dicts()[0].get("blob_sha256_hex")
            if blob_sha and blob_sha != alias_blob_digest:
                _abort(
                    "E3B_S5_S3_CONTRACT_VIOLATION",
                    "V-07",
                    "alias_blob_digest_mismatch",
                    {"expected": blob_sha, "actual": alias_blob_digest},
                    manifest_fingerprint,
                )

        checks.append(
            {
                "check_id": "S3_ALIAS_INDEX_COUNTS",
                "status": "PASS",
                "affected_count": len(alias_counts),
                "detail": "alias index counts match edge catalogue",
            }
        )

        current_phase = "s4_inputs"
        routing_entry = find_dataset_entry(dictionary_3b, DATASET_S4_POLICY).entry
        validation_entry = find_dataset_entry(dictionary_3b, DATASET_S4_CONTRACT).entry
        routing_path = _resolve_dataset_path(routing_entry, run_paths, config.external_roots, tokens)
        validation_path = _resolve_dataset_path(validation_entry, run_paths, config.external_roots, tokens)
        routing_policy = _load_json(routing_path)
        _validate_payload(schema_3b, schema_layer1, "egress/virtual_routing_policy_3B", routing_policy)
        if routing_policy.get("manifest_fingerprint") != str(manifest_fingerprint):
            _abort(
                "E3B_S5_S4_CONTRACT_VIOLATION",
                "V-08",
                "routing_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": routing_policy.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        if routing_policy.get("edge_universe_hash") != str(universe_payload.get("universe_hash")):
            _abort(
                "E3B_S5_S4_CONTRACT_VIOLATION",
                "V-08",
                "routing_universe_hash_mismatch",
                {
                    "expected": universe_payload.get("universe_hash"),
                    "actual": routing_policy.get("edge_universe_hash"),
                },
                manifest_fingerprint,
            )

        validation_files = _resolve_parquet_files(validation_path)
        validation_df = pl.read_parquet(validation_files)
        validation_pack, validation_table = _table_pack(schema_3b, "egress/virtual_validation_contract_3B")
        _inline_external_refs(validation_pack, schema_layer1, "schemas.layer1.yaml#")
        cleaned_rows = (
            {
                **row,
                "thresholds": _drop_none(row.get("thresholds")),
                "inputs": _drop_none(row.get("inputs")),
                "target_population": _drop_none(row.get("target_population")),
            }
            for row in validation_df.iter_rows(named=True)
        )
        try:
            validate_dataframe(cleaned_rows, validation_pack, validation_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S5_INPUT_SCHEMA_INVALID",
                "V-10",
                "virtual_validation_contract_schema_invalid",
                {"error": str(exc), "path": str(validation_path)},
                manifest_fingerprint,
            )
        if validation_df.get_column("test_id").n_unique() != validation_df.height:
            _abort(
                "E3B_S5_S4_CONTRACT_VIOLATION",
                "V-08",
                "validation_test_id_duplicate",
                {"rows": int(validation_df.height)},
                manifest_fingerprint,
            )

        checks.append(
            {
                "check_id": "S4_ROUTING_VALIDATION",
                "status": "PASS",
                "affected_count": int(validation_df.height),
                "detail": "routing policy + validation contract coherence",
            }
        )

        current_phase = "rng_logs"
        audit_entry = find_dataset_entry(dictionary_3b, DATASET_RNG_AUDIT).entry
        trace_entry = find_dataset_entry(dictionary_3b, DATASET_RNG_TRACE).entry
        jitter_entry = find_dataset_entry(dictionary_3b, DATASET_RNG_EDGE_JITTER).entry
        tile_entry = find_dataset_entry(dictionary_3b, DATASET_RNG_EDGE_TILE).entry

        audit_paths = _resolve_event_paths(audit_entry, run_paths, config.external_roots, tokens)
        audit_schema = _schema_for_payload(schema_layer1, schema_layer1, "rng/core/rng_audit_log/record")
        audit_rows_total = 0
        audit_has_identity_match = False

        def _collect_audit_row(row: dict) -> None:
            nonlocal audit_rows_total, audit_has_identity_match
            audit_rows_total += 1
            if audit_has_identity_match:
                return
            audit_has_identity_match = (
                row.get("run_id") == str(run_id_value)
                and int(row.get("seed") or -1) == int(seed)
                and row.get("manifest_fingerprint") == str(manifest_fingerprint)
                and row.get("parameter_hash") == str(parameter_hash)
            )

        audit_digest, audit_bytes, audit_events = _hash_jsonl_with_validation(
            audit_paths,
            audit_schema,
            logger,
            "S5: hash rng_audit_log",
            on_record=_collect_audit_row,
        )
        if not audit_has_identity_match:
            _abort(
                "E3B_S5_RNG_ACCOUNTING_MISMATCH",
                "V-09",
                "rng_audit_identity_mismatch",
                {"records": audit_rows_total},
                manifest_fingerprint,
            )

        trace_paths = _resolve_event_paths(trace_entry, run_paths, config.external_roots, tokens)
        trace_schema = _schema_for_payload(schema_layer1, schema_layer1, "rng/core/rng_trace_log/record")
        trace_jitter_row: Optional[dict] = None
        trace_tile_row: Optional[dict] = None

        def _collect_trace_row(row: dict) -> None:
            nonlocal trace_jitter_row, trace_tile_row
            if row.get("module") != "3B.S2":
                return
            substream = str(row.get("substream_label") or "")
            if substream == "edge_jitter":
                trace_jitter_row = _pick_trace_row(trace_jitter_row, row)
            elif substream == "edge_tile_assign":
                trace_tile_row = _pick_trace_row(trace_tile_row, row)

        trace_digest, trace_bytes, trace_events = _hash_jsonl_with_validation(
            trace_paths,
            trace_schema,
            logger,
            "S5: hash rng_trace_log",
            on_record=_collect_trace_row,
        )
        jitter_trace = trace_jitter_row
        if jitter_trace is None:
            _abort(
                "E3B_S5_RNG_ACCOUNTING_MISMATCH",
                "V-09",
                "rng_trace_missing_jitter",
                {"detail": "no jitter trace rows found"},
                manifest_fingerprint,
            )

        jitter_paths = _resolve_event_paths(jitter_entry, run_paths, config.external_roots, tokens)
        jitter_schema = _schema_for_payload(schema_layer1, schema_layer1, "rng/events/edge_jitter")
        jitter_digest, jitter_bytes, jitter_events = _hash_jsonl_with_validation(
            jitter_paths, jitter_schema, logger, "S5: hash rng_event_edge_jitter"
        )
        jitter_events_total = int(jitter_trace.get("events_total") or 0)
        jitter_draws_total = int(jitter_trace.get("draws_total") or 0)
        jitter_blocks_total = int(jitter_trace.get("blocks_total") or 0)
        if jitter_events_total != jitter_events:
            _abort(
                "E3B_S5_RNG_ACCOUNTING_MISMATCH",
                "V-09",
                "rng_trace_event_mismatch",
                {"trace": jitter_events_total, "events": jitter_events},
                manifest_fingerprint,
            )

        draws_per_event = 2
        expected_draws = jitter_events * draws_per_event
        expected_blocks = jitter_events
        if jitter_draws_total != expected_draws or jitter_blocks_total != expected_blocks:
            _abort(
                "E3B_S5_RNG_ACCOUNTING_MISMATCH",
                "V-09",
                "rng_draws_blocks_mismatch",
                {
                    "expected_draws": expected_draws,
                    "actual_draws": jitter_draws_total,
                    "expected_blocks": expected_blocks,
                    "actual_blocks": jitter_blocks_total,
                },
                manifest_fingerprint,
            )
        if jitter_events < sum(edge_counts.values()):
            _abort(
                "E3B_S5_RNG_ACCOUNTING_MISMATCH",
                "V-09",
                "rng_events_lt_edges",
                {"events": jitter_events, "edges": sum(edge_counts.values())},
                manifest_fingerprint,
            )

        tile_events = 0
        tile_digest = ""
        tile_bytes = 0
        tile_trace = None
        tile_paths = []
        try:
            tile_paths = _resolve_event_paths(tile_entry, run_paths, config.external_roots, tokens)
        except InputResolutionError:
            tile_paths = []
        if tile_paths:
            tile_schema = _schema_for_payload(schema_layer1, schema_layer1, "rng/events/edge_tile_assign")
            tile_digest, tile_bytes, tile_events = _hash_jsonl_with_validation(
                tile_paths, tile_schema, logger, "S5: hash rng_event_edge_tile_assign"
            )
            tile_trace = trace_tile_row
            if tile_trace and int(tile_trace.get("events_total") or 0) != tile_events:
                _abort(
                    "E3B_S5_RNG_ACCOUNTING_MISMATCH",
                    "V-09",
                    "rng_tile_event_mismatch",
                    {"trace": int(tile_trace.get("events_total") or 0), "events": tile_events},
                    manifest_fingerprint,
                )
        else:
            logger.warning("S5: rng_event_edge_tile_assign missing; skipping tile-assign audit")

        checks.append(
            {
                "check_id": "S2_RNG_ACCOUNTING",
                "status": "PASS",
                "affected_count": jitter_events,
                "detail": "rng logs match edge jitter expectations",
            }
        )

        current_phase = "evidence"
        routing_policy_digest = _hash_dataset(routing_path)
        validation_contract_digest = _hash_dataset(validation_path)
        digest_summary = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "digests": {
                "edge_catalogue_index_digest": edge_catalogue_index_digest,
                "edge_alias_index_digest": edge_alias_index_digest,
                "edge_alias_blob_digest": alias_blob_digest,
                "edge_universe_hash": str(universe_payload.get("universe_hash")),
                "virtual_routing_policy_digest": routing_policy_digest,
                "virtual_validation_contract_digest": validation_contract_digest,
                "cdn_country_weights_digest": cdn_weights_digest,
                "mcc_channel_rules_digest": virtual_rules_digest,
                "route_rng_policy_digest": sealed_assets["route_rng_policy_v1"][2],
                "virtual_validation_policy_digest": sealed_assets["virtual_validation_policy"][2],
                "virtual_routing_fields_digest": sealed_assets["virtual_routing_fields_v1"][2],
            },
            "notes": "Digest summary for 3B artefacts and policies.",
        }
        _validate_payload(schema_3b, schema_layer1, "validation/s5_digest_summary_3B", digest_summary)

        structural_summary = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "status": "PASS",
            "checks": checks,
            "counts": {
                "virtual_merchants": len(virtual_ids),
                "edge_merchants": len(edge_counts),
                "alias_merchants": len(alias_counts),
                "edge_total": sum(edge_counts.values()),
                "validation_tests": int(validation_df.height),
            },
            "notes": "S5 structural checks summary.",
        }
        _validate_payload(schema_3b, schema_layer1, "validation/s5_structural_summary_3B", structural_summary)

        rng_summary = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "status": "PASS",
            "streams": [
                {
                    "module": "3B.S2",
                    "substream_label": "edge_jitter",
                    "events_total": int(jitter_events_total),
                    "draws_total": int(jitter_draws_total),
                    "blocks_total": int(jitter_blocks_total),
                    "expected_events": int(jitter_events),
                    "expected_draws": int(expected_draws),
                    "expected_blocks": int(expected_blocks),
                    "status": "PASS",
                    "notes": "jitter trace matches event logs",
                },
            ],
            "notes": "S5 RNG accounting summary.",
        }
        if tile_paths:
            tile_events_total = int(tile_trace.get("events_total") or 0) if tile_trace else 0
            rng_summary["streams"].append(
                {
                    "module": "3B.S2",
                    "substream_label": "edge_tile_assign",
                    "events_total": tile_events_total,
                    "draws_total": int(tile_trace.get("draws_total") or 0) if tile_trace else 0,
                    "blocks_total": int(tile_trace.get("blocks_total") or 0) if tile_trace else 0,
                    "expected_events": int(tile_events),
                    "expected_draws": int(tile_events),
                    "expected_blocks": int(tile_events),
                    "status": "PASS",
                    "notes": "tile-assign trace matches event logs",
                }
            )
        _validate_payload(schema_3b, schema_layer1, "validation/s5_rng_summary_3B", rng_summary)

        manifest_evidence = [
            {"logical_id": DATASET_S0_GATE, "sha256_hex": _hash_dataset(gate_path)},
            {"logical_id": DATASET_SEALED_INPUTS, "sha256_hex": _hash_dataset(sealed_path)},
            {"logical_id": DATASET_S1_CLASS, "sha256_hex": _hash_dataset(class_path)},
            {"logical_id": DATASET_S1_SETTLE, "sha256_hex": _hash_dataset(settle_path)},
            {"logical_id": DATASET_S2_EDGE_INDEX, "sha256_hex": edge_catalogue_index_digest},
            {"logical_id": DATASET_S3_ALIAS_INDEX, "sha256_hex": edge_alias_index_digest},
            {"logical_id": DATASET_S3_UNIVERSE, "sha256_hex": _hash_dataset(universe_path)},
            {"logical_id": DATASET_S4_POLICY, "sha256_hex": routing_policy_digest},
            {"logical_id": DATASET_S4_CONTRACT, "sha256_hex": validation_contract_digest},
        ]

        s5_manifest = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "status": "PASS",
            "evidence": manifest_evidence,
            "digests": {
                "edge_catalogue_digest_global": edge_catalogue_digest_global,
                "edge_alias_blob_digest": alias_blob_digest,
                "virtual_routing_policy_digest": routing_policy_digest,
            },
            "notes": "S5 bundle manifest for 3B validation.",
        }
        _validate_payload(schema_3b, schema_layer1, "validation/s5_manifest_3B", s5_manifest)

        current_phase = "bundle_build"
        bundle_entry = find_dataset_entry(dictionary_3b, DATASET_BUNDLE).entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        bundle_catalog_path = _render_catalog_path(bundle_entry, tokens)
        if f"manifest_fingerprint={manifest_fingerprint}" not in bundle_catalog_path:
            _abort(
                "E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION",
                "V-11",
                "bundle_partition_mismatch",
                {"path": bundle_catalog_path},
                manifest_fingerprint,
            )
        index_entry = find_dataset_entry(dictionary_3b, DATASET_BUNDLE_INDEX).entry
        index_path = _resolve_dataset_path(index_entry, run_paths, config.external_roots, tokens)
        flag_entry = find_dataset_entry(dictionary_3b, DATASET_FLAG).entry
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if index_path.parent != bundle_root or flag_path.parent != bundle_root:
            _abort(
                "E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION",
                "V-11",
                "bundle_paths_mismatch",
                {"bundle_root": str(bundle_root), "index_path": str(index_path), "flag_path": str(flag_path)},
                manifest_fingerprint,
            )

        tmp_root = run_paths.tmp_root / f"s5_validation_bundle_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        _write_json(tmp_root / "s0_gate_receipt_3B.json", gate_payload)
        _write_json(tmp_root / "sealed_inputs_3B.json", sealed_payload)
        _write_json(tmp_root / "s5_manifest_3B.json", s5_manifest)
        _write_json(tmp_root / "s5_structural_summary_3B.json", structural_summary)
        _write_json(tmp_root / "s5_rng_summary_3B.json", rng_summary)
        _write_json(tmp_root / "s5_digest_summary_3B.json", digest_summary)

        evidence_specs = [
            (DATASET_S0_GATE, "s0_gate_receipt_3B.json"),
            (DATASET_SEALED_INPUTS, "sealed_inputs_3B.json"),
            (DATASET_S5_MANIFEST, "s5_manifest_3B.json"),
            (DATASET_S5_STRUCT, "s5_structural_summary_3B.json"),
            (DATASET_S5_RNG, "s5_rng_summary_3B.json"),
            (DATASET_S5_DIGEST, "s5_digest_summary_3B.json"),
        ]

        s4_summary_path = None
        try:
            summary_entry = find_dataset_entry(dictionary_3b, DATASET_S4_SUMMARY).entry
            s4_summary_path = _resolve_dataset_path(summary_entry, run_paths, config.external_roots, tokens)
            if s4_summary_path.exists():
                s4_payload = _load_json(s4_summary_path)
                _validate_payload(schema_3b, schema_layer1, "validation/s4_run_summary_3B", s4_payload)
                _write_json(tmp_root / "s4_run_summary_3B.json", s4_payload)
                evidence_specs.append((DATASET_S4_SUMMARY, "s4_run_summary_3B.json"))
        except InputResolutionError:
            logger.info("S5: s4_run_summary_3B missing; skipping optional evidence.")

        members: list[dict] = []
        for logical_id, rel_path in evidence_specs:
            entry = find_dataset_entry(dictionary_3b, logical_id).entry
            schema_ref = str(entry.get("schema_ref") or "")
            if not schema_ref:
                _abort(
                    "E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION",
                    "V-11",
                    "member_schema_ref_missing",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            file_path = tmp_root / rel_path
            digest = sha256_file(file_path).sha256_hex
            size_bytes = file_path.stat().st_size
            members.append(
                {
                    "logical_id": logical_id,
                    "path": rel_path,
                    "schema_ref": schema_ref,
                    "sha256_hex": digest,
                    "role": "evidence",
                    "size_bytes": int(size_bytes),
                }
            )

        members = sorted(members, key=lambda item: str(item.get("path") or ""))
        if not members:
            _abort(
                "E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION",
                "V-11",
                "members_empty",
                {"detail": "no bundle members constructed"},
                manifest_fingerprint,
            )

        s5_manifest_digest = sha256_file(tmp_root / "s5_manifest_3B.json").sha256_hex
        index_payload = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "s5_manifest_digest": s5_manifest_digest,
            "members": members,
        }
        index_schema = _schema_for_payload(schema_layer1, schema_layer1, "validation/validation_bundle_index_3B")
        index_errors = list(Draft202012Validator(index_schema).iter_errors(index_payload))
        if index_errors:
            _abort(
                "E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION",
                "V-11",
                "index_schema_invalid",
                {"error": str(index_errors[0])},
                manifest_fingerprint,
            )
        _write_json(tmp_root / "index.json", index_payload)

        bundle_digest = _bundle_digest_for_members(tmp_root, members)
        flag_schema = _schema_for_payload(schema_layer1, schema_layer1, "validation/passed_flag_3B")
        flag_payload = f"sha256_hex = {bundle_digest}"
        flag_errors = list(Draft202012Validator(flag_schema).iter_errors(flag_payload))
        if flag_errors:
            _abort(
                "E3B_S5_FLAG_DIGEST_MISMATCH",
                "V-11",
                "flag_schema_invalid",
                {"error": str(flag_errors[0])},
                manifest_fingerprint,
            )
        _write_flag(tmp_root / "_passed.flag", bundle_digest)

        current_phase = "publish"
        if bundle_root.exists():
            existing_index_path = bundle_root / "index.json"
            existing_flag_path = bundle_root / "_passed.flag"
            if not existing_index_path.exists() or not existing_flag_path.exists():
                _abort(
                    "E3B_S5_OUTPUT_INCONSISTENT_REWRITE",
                    "V-12",
                    "bundle_partial_exists",
                    {"bundle_root": str(bundle_root)},
                    manifest_fingerprint,
                )
            existing_index = _load_json(existing_index_path)
            existing_members = sorted(existing_index.get("members") or [], key=lambda item: str(item.get("path") or ""))
            existing_digest = _bundle_digest_for_members(bundle_root, existing_members)
            existing_flag = existing_flag_path.read_text(encoding="ascii").strip()
            if existing_flag != f"sha256_hex = {existing_digest}":
                _abort(
                    "E3B_S5_FLAG_DIGEST_MISMATCH",
                    "V-12",
                    "flag_digest_mismatch",
                    {"expected": existing_digest, "actual": existing_flag},
                    manifest_fingerprint,
                )
            new_index_bytes = _json_bytes(index_payload)
            existing_index_bytes = existing_index_path.read_bytes()
            if existing_index_bytes != new_index_bytes or existing_flag != flag_payload:
                _abort(
                    "E3B_S5_OUTPUT_INCONSISTENT_REWRITE",
                    "V-12",
                    "bundle_immutability_violation",
                    {"bundle_root": str(bundle_root)},
                    manifest_fingerprint,
                )
            logger.info("S5: bundle already exists and is identical; skipping publish.")
        else:
            bundle_root.parent.mkdir(parents=True, exist_ok=True)
            tmp_root.replace(bundle_root)
            logger.info("S5: bundle published path=%s", bundle_root)

        status = "PASS"
        timer.info(
            f"S5: bundle complete (members={len(members)}, digest={bundle_digest})"
        )

    except EngineFailure as exc:
        if not error_code:
            error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except ContractError as exc:
        if not error_code:
            error_code = "E3B_S5_BUNDLE_INDEX_SCHEMA_VIOLATION"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3B_S5_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3B_S5_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id_value and parameter_hash and manifest_fingerprint and run_paths and dictionary_3b:
            try:
                run_report_entry = find_dataset_entry(dictionary_3b, DATASET_S5_REPORT).entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": str(run_id_value),
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "counts": {
                        "virtual_merchants": len(virtual_ids) if "virtual_ids" in locals() else 0,
                        "edge_merchants": len(edge_counts) if "edge_counts" in locals() else 0,
                        "alias_merchants": len(alias_counts) if "alias_counts" in locals() else 0,
                        "edge_total": sum(edge_counts.values()) if "edge_counts" in locals() else 0,
                        "validation_tests": int(validation_df.height) if "validation_df" in locals() else 0,
                    },
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "bundle_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, DATASET_BUNDLE).entry, tokens
                        ),
                        "index_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, DATASET_BUNDLE_INDEX).entry, tokens
                        ),
                        "flag_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, DATASET_FLAG).entry, tokens
                        ),
                        "format": "folder/json/text",
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S5: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S5: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3B_S5_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if bundle_root is None or index_path is None or flag_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3B_S5_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S5Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        bundle_root=bundle_root,
        index_path=index_path,
        flag_path=flag_path,
        run_report_path=run_report_path,
    )
