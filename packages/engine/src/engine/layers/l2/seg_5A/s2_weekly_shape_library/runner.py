"""S2 weekly shape library runner for Segment 5A."""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
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
from engine.layers.l2.seg_5A.s0_gate.runner import (
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _sealed_inputs_digest,
)


MODULE_NAME = "5A.s2_weekly_shape_library"
SEGMENT = "5A"
STATE = "S2"
S2_SPEC_VERSION = "1.0.0"
EPS = 1e-6


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    grid_path: Path
    shape_path: Path
    catalogue_path: Optional[Path]
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
    def __init__(self, total: int, logger, label: str) -> None:
        self._total = max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < 0.5 and self._processed < self._total:
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


def _emit_event(logger, event: str, manifest_fingerprint: str, severity: str, **fields: object) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint,
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
    manifest_fingerprint: str,
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


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: str) -> None:
    logger = get_logger("engine.layers.l2.seg_5A.s2_weekly_shape_library.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(schema, schema_layer2, "schemas.layer2.yaml#")
    return normalize_nullable_schema(schema)


def _validate_payload(
    schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str, payload: object
) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(str(errors[0]), [])


def _validate_array_rows(
    rows: Iterable[dict],
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    max_errors: int = 5,
) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    if schema.get("type") != "array":
        raise ContractError(f"Expected array schema at {anchor}, found {schema.get('type')}")
    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        raise ContractError(f"Array schema missing items object at {anchor}")
    item_schema = dict(items_schema)
    parent_defs = schema.get("$defs") or {}
    if parent_defs:
        merged_defs = dict(parent_defs)
        if isinstance(item_schema.get("$defs"), dict):
            merged_defs.update(item_schema.get("$defs", {}))
        item_schema["$defs"] = merged_defs
    validator = Draft202012Validator(item_schema)
    errors: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        for error in validator.iter_errors(row):
            field = ".".join(str(part) for part in error.path) if error.path else ""
            errors.append(
                {
                    "row_index": index,
                    "field": field,
                    "message": error.message,
                }
            )
            if len(errors) >= max_errors:
                break
        if errors and len(errors) >= max_errors:
            break
    if errors:
        lines = [
            f"row {item['row_index']}: {item['field']} {item['message']}".strip()
            for item in errors
        ]
        raise SchemaValidationError("Schema validation failed:\n" + "\n".join(lines), errors)


def _resolve_sealed_row(
    sealed_by_id: dict[str, dict],
    artifact_id: str,
    manifest_fingerprint: str,
    read_scopes: set[str],
    required: bool,
    error_code: str,
) -> Optional[dict]:
    row = sealed_by_id.get(artifact_id)
    if not row or row.get("status") == "IGNORED":
        if required:
            _abort(
                error_code,
                "V-04",
                "required_input_missing",
                {"artifact_id": artifact_id},
                manifest_fingerprint,
            )
        return None
    if required and row.get("status") != "REQUIRED":
        _abort(
            error_code,
            "V-04",
            "required_input_unusable",
            {"artifact_id": artifact_id, "status": row.get("status")},
            manifest_fingerprint,
        )
    if row.get("read_scope") not in read_scopes:
        _abort(
            error_code,
            "V-04",
            "read_scope_invalid",
            {"artifact_id": artifact_id, "read_scope": row.get("read_scope")},
            manifest_fingerprint,
        )
    return row


def _publish_parquet_idempotent(path: Path, df: pl.DataFrame, logger, label: str) -> bool:
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    df.write_parquet(tmp_path, compression="zstd")
    if path.exists():
        existing_hash = sha256_file(path).sha256_hex
        tmp_hash = sha256_file(tmp_path).sha256_hex
        if existing_hash != tmp_hash:
            raise EngineFailure(
                "F4",
                "S2_OUTPUT_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(path), "label": label},
            )
        tmp_path.unlink()
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
        logger.info("S2: output already exists and is identical; skipping publish (%s).", label)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "S2_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(path), "label": label, "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info("S2: published %s to %s", label, path)
    return True


def _hash_u64(message: str) -> int:
    digest = hashlib.sha256(message.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _u_det_from_hash(x: int) -> float:
    return (x + 0.5) / 18446744073709551616.0


def _pick_template_index(message: str, count: int) -> int:
    if count <= 0:
        return 0
    x = _hash_u64(message)
    u_det = _u_det_from_hash(x)
    idx = int(math.floor(u_det * count))
    if idx >= count:
        idx = count - 1
    return idx


def _gaussian_peak(minute: float, center: float, sigma: float, amplitude: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (minute - center) / sigma
    return amplitude * math.exp(-0.5 * z * z)


def _in_window(minute: int, start: int, end: int) -> bool:
    if start <= end:
        return start <= minute < end
    return minute >= start or minute < end


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l2.seg_5A.s2_weekly_shape_library.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)
    current_phase = "init"
    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    run_paths: Optional[RunPaths] = None
    grid_path: Optional[Path] = None
    shape_path: Optional[Path] = None
    catalogue_path: Optional[Path] = None
    run_report_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    scenario_id: Optional[str] = None
    seed: int = 0

    policy_versions: dict[str, Optional[str]] = {
        "baseline_intensity_policy_version": None,
        "shape_library_version": None,
        "shape_time_grid_policy_version": None,
        "zone_shape_modifiers_version": None,
    }

    counts: dict[str, object] = {
        "domain_rows": 0,
        "grid_rows": 0,
        "shape_rows": 0,
        "template_rows": 0,
        "classes_total": 0,
    }

    dictionary_5a: dict = {}
    tokens: dict[str, str] = {}

    try:
        current_phase = "run_receipt"
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id = receipt.get("run_id")
        if not run_id:
            raise InputResolutionError("run_receipt missing run_id.")
        if receipt_path.parent.name != run_id:
            raise InputResolutionError("run_receipt path does not match embedded run_id.")
        parameter_hash = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if manifest_fingerprint is None or parameter_hash is None:
            raise InputResolutionError("run_receipt missing manifest_fingerprint or parameter_hash.")
        seed = int(receipt.get("seed") or 0)

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S2: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5a_path, dictionary_5a = load_dataset_dictionary(source, "5A")
        reg_5a_path, registry_5a = load_artefact_registry(source, "5A")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_5a_path),
            str(reg_5a_path),
            str(schema_5a_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
        )

        logger.info(
            "S2: objective=build weekly shape grid and class-zone templates "
            "(gate S0/S1 + shape policies, output shape_grid_definition_5A + class_zone_shape_5A + optional catalogue)"
        )

        tokens = {
            "seed": str(seed),
            "parameter_hash": str(parameter_hash),
            "manifest_fingerprint": str(manifest_fingerprint),
            "run_id": str(run_id),
        }

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_5a, "s0_gate_receipt_5A").entry
        sealed_entry = find_dataset_entry(dictionary_5a, "sealed_inputs_5A").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        sealed_inputs = _load_json(sealed_inputs_path)

        _validate_payload(schema_5a, schema_layer1, schema_layer2, "validation/s0_gate_receipt_5A", receipt_payload)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "validation/sealed_inputs_5A", sealed_inputs)

        if receipt_payload.get("parameter_hash") != parameter_hash:
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_id_value = receipt_payload.get("scenario_id")
        if isinstance(scenario_id_value, list):
            if len(scenario_id_value) != 1:
                _abort(
                    "S2_GATE_OR_S1_INVALID",
                    "V-03",
                    "scenario_id_multi",
                    {"scenario_id": scenario_id_value},
                    manifest_fingerprint,
                )
            scenario_id = str(scenario_id_value[0])
        else:
            scenario_id = str(scenario_id_value) if scenario_id_value is not None else None

        if not scenario_id:
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "scenario_id_missing",
                {"scenario_id": scenario_id_value},
                manifest_fingerprint,
            )
        tokens["scenario_id"] = scenario_id

        upstream = receipt_payload.get("verified_upstream_segments") or {}
        for segment_id in ("1A", "1B", "2A", "2B", "3A", "3B"):
            status_value = None
            if isinstance(upstream, dict):
                status_value = (upstream.get(segment_id) or {}).get("status")
            if status_value != "PASS":
                _abort(
                    "S2_UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        if not isinstance(sealed_inputs, list):
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "sealed_inputs_invalid",
                {"detail": "sealed_inputs_5A payload is not a list"},
                manifest_fingerprint,
            )
        sealed_sorted = sorted(
            sealed_inputs,
            key=lambda row: (
                row.get("owner_layer"),
                row.get("owner_segment"),
                row.get("role"),
                row.get("artifact_id"),
            ),
        )
        if len({row.get("artifact_id") for row in sealed_sorted}) != len(sealed_sorted):
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "sealed_inputs_duplicate_id",
                {"detail": "duplicate artifact_id in sealed_inputs_5A"},
                manifest_fingerprint,
            )
        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if sealed_digest != receipt_payload.get("sealed_inputs_digest"):
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {
                    "expected": receipt_payload.get("sealed_inputs_digest"),
                    "actual": sealed_digest,
                },
                manifest_fingerprint,
            )

        sealed_by_id = {row.get("artifact_id"): row for row in sealed_sorted if isinstance(row, dict)}

        current_phase = "input_resolution"
        profile_row = _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_profile_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S2_REQUIRED_INPUT_MISSING",
        )
        if profile_row is None:
            logger.warning(
                "S2: sealed_inputs_5A missing merchant_zone_profile_5A; proceeding with direct path resolution"
            )
        baseline_policy_row = _resolve_sealed_row(
            sealed_by_id,
            "baseline_intensity_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S2_REQUIRED_SHAPE_POLICY_MISSING",
        )
        shape_library_row = _resolve_sealed_row(
            sealed_by_id,
            "shape_library_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S2_REQUIRED_SHAPE_POLICY_MISSING",
        )
        grid_policy_row = _resolve_sealed_row(
            sealed_by_id,
            "shape_time_grid_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S2_REQUIRED_SHAPE_POLICY_MISSING",
        )
        scenario_meta_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_metadata",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S2_REQUIRED_INPUT_MISSING",
        )
        zone_modifiers_row = _resolve_sealed_row(
            sealed_by_id,
            "zone_shape_modifiers_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            False,
            "S2_REQUIRED_SHAPE_POLICY_MISSING",
        )
        scenario_manifest_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_manifest_5A",
            manifest_fingerprint,
            {"ROW_LEVEL", "METADATA_ONLY"},
            False,
            "S2_REQUIRED_INPUT_MISSING",
        )

        current_phase = "policy_load"
        baseline_policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "baseline_intensity_policy_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        baseline_policy = _load_yaml(baseline_policy_path)
        _validate_payload(
            schema_5a, schema_layer1, schema_layer2, "policy/baseline_intensity_policy_5A", baseline_policy
        )
        policy_versions["baseline_intensity_policy_version"] = str(baseline_policy.get("version") or "")

        shape_library_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "shape_library_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        shape_library = _load_yaml(shape_library_path)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "policy/shape_library_5A", shape_library)
        policy_versions["shape_library_version"] = str(shape_library.get("version") or "")

        grid_policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "shape_time_grid_policy_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        grid_policy = _load_yaml(grid_policy_path)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "policy/shape_time_grid_policy_5A", grid_policy)
        policy_versions["shape_time_grid_policy_version"] = str(grid_policy.get("version") or "")

        scenario_metadata_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "scenario_metadata").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        scenario_metadata = _load_yaml(scenario_metadata_path)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "scenario/scenario_metadata", scenario_metadata)

        zone_modifiers = None
        if zone_modifiers_row:
            zone_modifiers_path = _resolve_dataset_path(
                find_dataset_entry(dictionary_5a, "zone_shape_modifiers_5A").entry,
                run_paths,
                config.external_roots,
                tokens,
            )
            zone_modifiers = _load_yaml(zone_modifiers_path)
            _validate_payload(
                schema_5a, schema_layer1, schema_layer2, "policy/zone_shape_modifiers_5A", zone_modifiers
            )
            policy_versions["zone_shape_modifiers_version"] = str(zone_modifiers.get("version") or "")

        scenario_ids = []
        if isinstance(scenario_metadata, dict):
            scenario_ids = [str(item) for item in scenario_metadata.get("scenario_ids") or []]
        if scenario_ids and scenario_id not in scenario_ids:
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-03",
                "scenario_id_not_in_metadata",
                {"scenario_id": scenario_id, "scenario_ids": scenario_ids},
                manifest_fingerprint,
            )

        if scenario_manifest_row:
            scenario_manifest_path = _resolve_dataset_path(
                find_dataset_entry(dictionary_5a, "scenario_manifest_5A").entry,
                run_paths,
                config.external_roots,
                tokens,
            )
            scenario_manifest_df = pl.read_parquet(scenario_manifest_path)
            if "scenario_id" not in scenario_manifest_df.columns:
                _abort(
                    "S2_REQUIRED_INPUT_MISSING",
                    "V-04",
                    "scenario_manifest_missing_id",
                    {"detail": "scenario_manifest_5A missing scenario_id column"},
                    manifest_fingerprint,
                )
            scenario_manifest_ids = set(
                scenario_manifest_df.get_column("scenario_id").drop_nulls().unique().to_list()
            )
            if scenario_id not in scenario_manifest_ids:
                _abort(
                    "S2_REQUIRED_INPUT_MISSING",
                    "V-04",
                    "scenario_id_missing_from_manifest",
                    {"scenario_id": scenario_id},
                    manifest_fingerprint,
                )
            logger.info("S2: scenario_manifest_5A present for scenario_id=%s", scenario_id)
        else:
            logger.info("S2: scenario_manifest_5A missing; proceeding without scenario traits")

        current_phase = "grid_build"
        grid = grid_policy.get("grid") or {}
        try:
            bucket_duration = int(grid.get("bucket_duration_minutes") or 0)
            minutes_per_day = int(grid.get("minutes_per_day") or 0)
            days_per_week = int(grid.get("days_per_week") or 0)
            buckets_per_day = int(grid.get("buckets_per_day") or 0)
            t_week = int(grid.get("T_week") or 0)
        except (TypeError, ValueError) as exc:
            _abort(
                "S2_TIME_GRID_INVALID",
                "V-05",
                "grid_fields_invalid",
                {"detail": str(exc)},
                manifest_fingerprint,
            )
        if bucket_duration <= 0 or minutes_per_day <= 0 or days_per_week <= 0 or buckets_per_day <= 0 or t_week <= 0:
            _abort(
                "S2_TIME_GRID_INVALID",
                "V-05",
                "grid_fields_missing",
                {
                    "bucket_duration_minutes": bucket_duration,
                    "minutes_per_day": minutes_per_day,
                    "days_per_week": days_per_week,
                    "buckets_per_day": buckets_per_day,
                    "T_week": t_week,
                },
                manifest_fingerprint,
            )
        if bucket_duration * buckets_per_day != minutes_per_day or days_per_week * buckets_per_day != t_week:
            _abort(
                "S2_TIME_GRID_INVALID",
                "V-05",
                "grid_invariant_failed",
                {
                    "bucket_duration_minutes": bucket_duration,
                    "minutes_per_day": minutes_per_day,
                    "days_per_week": days_per_week,
                    "buckets_per_day": buckets_per_day,
                    "T_week": t_week,
                },
                manifest_fingerprint,
            )

        derived_flags = grid.get("derived_flags") or {}
        weekend_days_raw = derived_flags.get("weekend_days") or [6, 7]
        weekend_days = {int(day) for day in weekend_days_raw if day}
        nominal_open_hours = derived_flags.get("nominal_open_hours") if isinstance(derived_flags, dict) else None
        nominal_days = set()
        nominal_start = None
        nominal_end = None
        if isinstance(nominal_open_hours, dict):
            nominal_days = {int(day) for day in nominal_open_hours.get("days") or []}
            nominal_start = nominal_open_hours.get("start_minute")
            nominal_end = nominal_open_hours.get("end_minute_exclusive")

        bucket_dows = []
        bucket_minutes = []
        grid_rows: list[dict] = []
        for k in range(t_week):
            dow = 1 + k // buckets_per_day
            minute = (k % buckets_per_day) * bucket_duration
            bucket_dows.append(dow)
            bucket_minutes.append(minute)
            row = {
                "parameter_hash": str(parameter_hash),
                "scenario_id": str(scenario_id),
                "bucket_index": k,
                "local_day_of_week": dow,
                "local_minutes_since_midnight": minute,
                "bucket_duration_minutes": bucket_duration,
            }
            if weekend_days:
                row["is_weekend"] = dow in weekend_days
            if nominal_start is not None and nominal_end is not None and nominal_days:
                row["is_nominal_open_hours"] = dow in nominal_days and _in_window(
                    minute, int(nominal_start), int(nominal_end)
                )
            time_grid_version = grid_policy.get("version")
            if time_grid_version:
                row["time_grid_version"] = str(time_grid_version)
            grid_rows.append(row)

        counts["grid_rows"] = len(grid_rows)
        _validate_array_rows(
            grid_rows,
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/shape_grid_definition_5A",
        )
        logger.info(
            "S2: grid definition built (bucket_duration=%s buckets_per_day=%s T_week=%s weekend_days=%s)",
            bucket_duration,
            buckets_per_day,
            t_week,
            sorted(weekend_days),
        )

        current_phase = "domain_scan"
        profile_entry = find_dataset_entry(dictionary_5a, "merchant_zone_profile_5A").entry
        try:
            profile_path = _resolve_dataset_path(profile_entry, run_paths, config.external_roots, tokens)
        except InputResolutionError as exc:
            _abort(
                "S2_REQUIRED_INPUT_MISSING",
                "V-05",
                "merchant_zone_profile_missing",
                {"detail": str(exc)},
                manifest_fingerprint,
            )
        if not profile_path.exists():
            _abort(
                "S2_REQUIRED_INPUT_MISSING",
                "V-05",
                "merchant_zone_profile_missing",
                {"path": str(profile_path)},
                manifest_fingerprint,
            )
        profile_df = pl.read_parquet(profile_path)
        if "channel_group" not in profile_df.columns:
            logger.warning(
                "S2: merchant_zone_profile_5A missing channel_group; defaulting to mixed for compatibility."
            )
            profile_df = profile_df.with_columns(pl.lit("mixed").alias("channel_group"))
        profile_required_columns = [
            "manifest_fingerprint",
            "parameter_hash",
            "merchant_id",
            "legal_country_iso",
            "tzid",
            "demand_class",
            "channel_group",
        ]
        missing_profile_columns = [column for column in profile_required_columns if column not in profile_df.columns]
        if missing_profile_columns:
            _abort(
                "S2_REQUIRED_INPUT_MISSING",
                "V-05",
                "merchant_zone_profile_columns_missing",
                {"missing_columns": missing_profile_columns},
                manifest_fingerprint,
            )
        profile_df = profile_df.select(profile_required_columns)
        _validate_array_rows(
            profile_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/merchant_zone_profile_5A",
        )
        profile_params = profile_df.get_column("parameter_hash").drop_nulls().unique().to_list()
        if any(str(value) != str(parameter_hash) for value in profile_params):
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-05",
                "parameter_hash_mismatch_in_profile",
                {"expected": parameter_hash, "found": profile_params},
                manifest_fingerprint,
            )
        profile_manifests = profile_df.get_column("manifest_fingerprint").drop_nulls().unique().to_list()
        if any(str(value) != str(manifest_fingerprint) for value in profile_manifests):
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-05",
                "manifest_fingerprint_mismatch_in_profile",
                {"expected": manifest_fingerprint, "found": profile_manifests},
                manifest_fingerprint,
            )

        domain_df = (
            profile_df.select(["demand_class", "legal_country_iso", "tzid", "channel_group"])
            .unique()
            .sort(["demand_class", "legal_country_iso", "tzid", "channel_group"])
        )
        missing_domain_channels = domain_df.filter(pl.col("channel_group").is_null()).height
        if missing_domain_channels:
            _abort(
                "S2_GATE_OR_S1_INVALID",
                "V-05",
                "domain_channel_group_missing",
                {"rows": int(missing_domain_channels)},
                manifest_fingerprint,
            )
        domain_rows = domain_df.height
        counts["domain_rows"] = domain_rows
        counts["classes_total"] = domain_df.select("demand_class").unique().height if domain_rows else 0
        counts["channel_groups_realized"] = (
            domain_df.select("channel_group").unique().height if domain_rows else 0
        )
        logger.info(
            "S2: domain derived from merchant_zone_profile_5A "
            "(classes=%s channels=%s zones=%s rows=%s)",
            counts["classes_total"],
            counts["channel_groups_realized"],
            domain_df.select(["legal_country_iso", "tzid"]).unique().height if domain_rows else 0,
            domain_rows,
        )

        current_phase = "template_plan"
        if shape_library.get("scenario_mode") != "scenario_agnostic":
            _abort(
                "S2_REQUIRED_SHAPE_POLICY_MISSING",
                "V-06",
                "shape_library_scenario_mode_invalid",
                {"scenario_mode": shape_library.get("scenario_mode")},
                manifest_fingerprint,
            )

        channel_groups = shape_library.get("channel_groups") or []
        if not isinstance(channel_groups, list) or not channel_groups:
            _abort(
                "S2_REQUIRED_SHAPE_POLICY_MISSING",
                "V-06",
                "shape_library_channel_groups_invalid",
                {"channel_groups": channel_groups},
                manifest_fingerprint,
            )
        channel_groups = [str(channel).strip() for channel in channel_groups]
        if any(not channel for channel in channel_groups):
            _abort(
                "S2_REQUIRED_SHAPE_POLICY_MISSING",
                "V-06",
                "shape_library_channel_groups_invalid",
                {"channel_groups": channel_groups},
                manifest_fingerprint,
            )
        policy_channel_groups = set(channel_groups)
        domain_channel_groups = (
            set(domain_df.get_column("channel_group").drop_nulls().unique().to_list()) if domain_rows else set()
        )
        missing_policy_channels = sorted(domain_channel_groups - policy_channel_groups)
        if missing_policy_channels:
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "domain_channel_group_missing_in_policy",
                {"missing_channel_groups": missing_policy_channels},
                manifest_fingerprint,
            )

        zone_group_mode = shape_library.get("zone_group_mode") or {}
        zone_group_mode_name = zone_group_mode.get("mode")
        zone_group_buckets = zone_group_mode.get("buckets")
        zone_group_prefix = zone_group_mode.get("zone_group_id_prefix")
        if zone_group_mode_name != "tzid_hash_bucket_v1" or not zone_group_buckets or not zone_group_prefix:
            _abort(
                "S2_REQUIRED_SHAPE_POLICY_MISSING",
                "V-06",
                "shape_library_zone_group_invalid",
                {"zone_group_mode": zone_group_mode},
                manifest_fingerprint,
            )

        templates = shape_library.get("templates") or []
        if not isinstance(templates, list) or not templates:
            _abort(
                "S2_REQUIRED_SHAPE_POLICY_MISSING",
                "V-06",
                "shape_library_templates_missing",
                {"detail": "shape_library_5A.templates empty"},
                manifest_fingerprint,
            )

        template_map: dict[str, dict] = {}
        templates_by_key: dict[tuple[str, str], list[str]] = {}
        for template in templates:
            if not isinstance(template, dict):
                _abort(
                    "S2_REQUIRED_SHAPE_POLICY_MISSING",
                    "V-06",
                    "shape_library_template_invalid",
                    {"detail": "template entry is not object"},
                    manifest_fingerprint,
                )
            template_id = template.get("template_id")
            if not template_id:
                _abort(
                    "S2_REQUIRED_SHAPE_POLICY_MISSING",
                    "V-06",
                    "template_id_missing",
                    {"template": template},
                    manifest_fingerprint,
                )
            if template_id in template_map:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_id_duplicate",
                    {"template_id": template_id},
                    manifest_fingerprint,
                )
            template_map[template_id] = template
            demand_class = str(template.get("demand_class") or "")
            channel = str(template.get("channel_group") or "")
            templates_by_key.setdefault((demand_class, channel), []).append(template_id)

        resolution = shape_library.get("template_resolution") or {}
        if resolution.get("mode") != "deterministic_choice_by_tzid_v1":
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "template_resolution_mode_invalid",
                {"mode": resolution.get("mode")},
                manifest_fingerprint,
            )

        default_template_id = resolution.get("default_template_id")
        if default_template_id not in template_map:
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "default_template_missing",
                {"template_id": default_template_id},
                manifest_fingerprint,
            )

        rules_map: dict[tuple[str, str], dict[str, object]] = {}
        for rule in resolution.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            rule_class = str(rule.get("demand_class") or "")
            rule_channel = str(rule.get("channel_group") or "")
            selection_law = rule.get("selection_law")
            candidate_ids = [str(item) for item in rule.get("candidate_template_ids") or []]
            if not rule_class or not rule_channel or not candidate_ids:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_rule_invalid",
                    {"rule": rule},
                    manifest_fingerprint,
                )
            if selection_law != "u_det_pick_index_v1":
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_selection_law_invalid",
                    {"selection_law": selection_law},
                    manifest_fingerprint,
                )
            rule_key = (rule_class, rule_channel)
            if rule_key in rules_map:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_rule_duplicate",
                    {"rule_key": rule_key},
                    manifest_fingerprint,
                )
            for candidate_id in candidate_ids:
                template = template_map.get(candidate_id)
                if not template:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "template_candidate_missing",
                        {"template_id": candidate_id, "rule_key": rule_key},
                        manifest_fingerprint,
                    )
                if str(template.get("demand_class")) != rule_class or str(template.get("channel_group")) != rule_channel:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "template_candidate_mismatch",
                        {"template_id": candidate_id, "rule_key": rule_key},
                        manifest_fingerprint,
                    )
            rules_map[rule_key] = {"candidate_ids": candidate_ids, "selection_law": selection_law}

        domain_classes = set(domain_df.get_column("demand_class").to_list()) if domain_rows else set()
        domain_class_channel_pairs = (
            set(tuple(row) for row in domain_df.select(["demand_class", "channel_group"]).iter_rows()) if domain_rows else set()
        )
        for demand_class, channel_group in domain_class_channel_pairs:
            if (demand_class, channel_group) not in rules_map:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_rule_missing",
                    {"demand_class": demand_class, "channel_group": channel_group},
                    manifest_fingerprint,
                )

        constraints = shape_library.get("constraints") or {}
        night_window = constraints.get("night_window_minutes") or {}
        office_window = constraints.get("office_hours_window") or {}
        try:
            min_mass_night = float(constraints.get("min_mass_night"))
            night_start = int(night_window.get("start_min"))
            night_end = int(night_window.get("end_min"))
            min_weekend_mass = float(constraints.get("min_weekend_mass_for_weekend_classes"))
            office_start = int(office_window.get("weekday_start_min"))
            office_end = int(office_window.get("weekday_end_min"))
            min_weekday_office_mass = float(office_window.get("min_weekday_office_mass"))
            nonflat_ratio_min = float(constraints.get("shape_nonflat_ratio_min"))
        except (TypeError, ValueError) as exc:
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "shape_constraints_invalid",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        realism_floors = shape_library.get("realism_floors") or {}
        try:
            min_total_templates = int(realism_floors.get("min_total_templates") or 0)
            min_templates_per_key = int(realism_floors.get("min_templates_per_class_per_channel") or 0)
            require_all_classes_present = bool(realism_floors.get("require_all_classes_present"))
            require_all_channel_groups_present = bool(realism_floors.get("require_all_channel_groups_present"))
            min_nonflat_templates_fraction = float(realism_floors.get("min_nonflat_templates_fraction") or 0)
            min_night_mass_online24h = float(realism_floors.get("min_night_mass_online24h") or 0)
            min_weekend_mass_evening_weekend = float(realism_floors.get("min_weekend_mass_evening_weekend") or 0)
            min_weekday_mass_office_hours = float(realism_floors.get("min_weekday_mass_office_hours") or 0)
        except (TypeError, ValueError) as exc:
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "realism_floors_invalid",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        is_night = [
            _in_window(minute, night_start, night_end) for minute in bucket_minutes
        ]
        is_weekend = [dow in weekend_days for dow in bucket_dows]
        weekday_days = {1, 2, 3, 4, 5}
        is_office = [
            (dow in weekday_days and _in_window(minute, office_start, office_end))
            for dow, minute in zip(bucket_dows, bucket_minutes)
        ]

        current_phase = "template_compile"
        template_vectors: dict[str, list[float]] = {}
        template_metrics: dict[str, dict[str, float]] = {}
        tracker = _ProgressTracker(
            len(template_map),
            logger,
            "S2: compile base templates (policy=shape_library_5A)",
        )
        for template_id, template in template_map.items():
            tracker.update(1)
            dow_weights = template.get("dow_weights") or []
            if len(dow_weights) != days_per_week:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_dow_weights_invalid",
                    {"template_id": template_id, "len": len(dow_weights)},
                    manifest_fingerprint,
                )
            daily_components = template.get("daily_components") or []
            baseline_floor = float(template.get("baseline_floor") or 0)
            power = float(template.get("power") or 1.0)
            values: list[float] = []
            for idx in range(t_week):
                dow = bucket_dows[idx]
                minute = bucket_minutes[idx]
                g_val = baseline_floor
                for component in daily_components:
                    if not isinstance(component, dict):
                        continue
                    if component.get("kind") != "gaussian_peak":
                        continue
                    g_val += _gaussian_peak(
                        float(minute),
                        float(component.get("center_min")),
                        float(component.get("sigma_min")),
                        float(component.get("amplitude")),
                    )
                v_val = (float(dow_weights[dow - 1]) * g_val) ** power
                if not math.isfinite(v_val) or v_val < 0:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "template_value_invalid",
                        {"template_id": template_id, "bucket_index": idx, "value": v_val},
                        manifest_fingerprint,
                    )
                values.append(v_val)
            total = sum(values)
            if total <= 0 or not math.isfinite(total):
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_total_invalid",
                    {"template_id": template_id, "total": total},
                    manifest_fingerprint,
                )
            shape = [value / total for value in values]
            max_val = max(shape) if shape else 0.0
            min_val = min(shape) if shape else 0.0
            nonflat_ratio = max_val / max(min_val, EPS)
            night_mass = sum(value for value, flag in zip(shape, is_night) if flag)
            weekend_mass = sum(value for value, flag in zip(shape, is_weekend) if flag)
            office_mass = sum(value for value, flag in zip(shape, is_office) if flag)
            template_vectors[template_id] = values
            template_metrics[template_id] = {
                "nonflat_ratio": nonflat_ratio,
                "night_mass": night_mass,
                "weekend_mass": weekend_mass,
                "office_mass": office_mass,
            }

        counts["template_rows"] = len(template_vectors)

        if counts["template_rows"] < min_total_templates:
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "template_realism_total_low",
                {"templates": counts["template_rows"], "min_total_templates": min_total_templates},
                manifest_fingerprint,
            )

        classes_to_check = domain_classes if require_all_classes_present else {key[0] for key in templates_by_key}
        for demand_class in classes_to_check:
            for channel in channel_groups:
                template_count = len(templates_by_key.get((demand_class, channel), []))
                if template_count < min_templates_per_key:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "template_realism_class_channel_low",
                        {
                            "demand_class": demand_class,
                            "channel_group": channel,
                            "templates": template_count,
                            "min_templates_per_class_per_channel": min_templates_per_key,
                        },
                        manifest_fingerprint,
                    )

        if require_all_channel_groups_present:
            for channel in channel_groups:
                if not any(key[1] == channel for key in templates_by_key):
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "template_realism_channel_missing",
                        {"channel_group": channel},
                        manifest_fingerprint,
                    )

        if require_all_classes_present:
            for demand_class in domain_classes:
                if not any(key[0] == demand_class for key in templates_by_key):
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "template_realism_class_missing",
                        {"demand_class": demand_class},
                        manifest_fingerprint,
                    )

        nonflat_templates = sum(
            1 for metrics in template_metrics.values() if metrics.get("nonflat_ratio", 0.0) >= nonflat_ratio_min
        )
        nonflat_fraction = nonflat_templates / counts["template_rows"] if counts["template_rows"] else 0.0
        if nonflat_fraction < min_nonflat_templates_fraction:
            _abort(
                "S2_TEMPLATE_RESOLUTION_FAILED",
                "V-06",
                "template_realism_nonflat_low",
                {
                    "nonflat_fraction": nonflat_fraction,
                    "min_nonflat_templates_fraction": min_nonflat_templates_fraction,
                },
                manifest_fingerprint,
            )

        for template_id, template in template_map.items():
            demand_class = str(template.get("demand_class") or "")
            metrics = template_metrics.get(template_id) or {}
            if demand_class == "online_24h" and metrics.get("night_mass", 0.0) < min_night_mass_online24h:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_realism_night_low",
                    {"template_id": template_id, "night_mass": metrics.get("night_mass")},
                    manifest_fingerprint,
                )
            if demand_class == "evening_weekend" and metrics.get("weekend_mass", 0.0) < min_weekend_mass_evening_weekend:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_realism_weekend_low",
                    {"template_id": template_id, "weekend_mass": metrics.get("weekend_mass")},
                    manifest_fingerprint,
                )
            if demand_class == "office_hours" and metrics.get("office_mass", 0.0) < min_weekday_mass_office_hours:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_realism_office_low",
                    {"template_id": template_id, "office_mass": metrics.get("office_mass")},
                    manifest_fingerprint,
                )

        current_phase = "zone_modifiers"
        profile_multipliers: dict[str, list[float]] = {}
        profile_flags: dict[str, list[list[str]]] = {}
        override_rules = []
        neutral_profile_id = None
        emit_adjustment_flags = False
        if zone_modifiers:
            if zone_modifiers.get("mode") != "bucket_profiles_v1":
                _abort(
                    "S2_REQUIRED_SHAPE_POLICY_MISSING",
                    "V-06",
                    "zone_modifiers_mode_invalid",
                    {"mode": zone_modifiers.get("mode")},
                    manifest_fingerprint,
                )
            zone_mode = zone_modifiers.get("zone_group_mode") or {}
            if zone_mode.get("mode") != "tzid_hash_bucket_v1":
                _abort(
                    "S2_REQUIRED_SHAPE_POLICY_MISSING",
                    "V-06",
                    "zone_modifiers_zone_mode_invalid",
                    {"zone_group_mode": zone_mode},
                    manifest_fingerprint,
                )
            if int(zone_mode.get("buckets") or 0) != int(zone_group_buckets) or str(
                zone_mode.get("zone_group_id_prefix")
            ) != str(zone_group_prefix):
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "zone_modifiers_group_mismatch",
                    {"shape_library": zone_group_mode, "zone_modifiers": zone_mode},
                    manifest_fingerprint,
                )

            defaults = zone_modifiers.get("defaults") or {}
            neutral_profile_id = defaults.get("neutral_profile_id")
            emit_adjustment_flags = bool(defaults.get("emit_adjustment_flags"))
            on_missing_profile = defaults.get("on_missing_profile_id")
            if on_missing_profile != "FAIL_CLOSED":
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "zone_modifiers_missing_policy",
                    {"on_missing_profile_id": on_missing_profile},
                    manifest_fingerprint,
                )

            profiles = zone_modifiers.get("profiles") or []
            profile_map: dict[str, dict] = {}
            for profile in profiles:
                if not isinstance(profile, dict):
                    continue
                profile_id = profile.get("profile_id")
                if not profile_id:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "zone_modifier_profile_id_missing",
                        {"profile": profile},
                        manifest_fingerprint,
                    )
                if profile_id in profile_map:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "zone_modifier_profile_duplicate",
                        {"profile_id": profile_id},
                        manifest_fingerprint,
                    )
                profile_map[profile_id] = profile

            if neutral_profile_id not in profile_map:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "zone_modifier_neutral_missing",
                    {"neutral_profile_id": neutral_profile_id},
                    manifest_fingerprint,
                )

            override_rules = zone_modifiers.get("overrides") or []

            for profile_id, profile in profile_map.items():
                dow_multipliers = profile.get("dow_multipliers") or []
                if len(dow_multipliers) != days_per_week:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "zone_modifier_dow_multipliers_invalid",
                        {"profile_id": profile_id},
                        manifest_fingerprint,
                    )
                window_defs = profile.get("time_window_multipliers") or []
                multipliers: list[float] = []
                flags: list[list[str]] = []
                for idx in range(t_week):
                    dow = bucket_dows[idx]
                    minute = bucket_minutes[idx]
                    mult = float(dow_multipliers[dow - 1])
                    bucket_flags: list[str] = []
                    for window in window_defs:
                        if not isinstance(window, dict):
                            continue
                        days = window.get("days")
                        if days != "*" and dow not in set(days or []):
                            continue
                        start = int(window.get("start_minute"))
                        end = int(window.get("end_minute_exclusive"))
                        if start % bucket_duration != 0 or end % bucket_duration != 0:
                            _abort(
                                "S2_TEMPLATE_RESOLUTION_FAILED",
                                "V-06",
                                "zone_modifier_window_unaligned",
                                {"profile_id": profile_id, "window_id": window.get("window_id")},
                                manifest_fingerprint,
                            )
                        if _in_window(minute, start, end):
                            mult *= float(window.get("multiplier"))
                            if emit_adjustment_flags and window.get("window_id"):
                                bucket_flags.append(f"zone_window:{window.get('window_id')}")
                    if not math.isfinite(mult) or mult <= 0:
                        _abort(
                            "S2_TEMPLATE_RESOLUTION_FAILED",
                            "V-06",
                            "zone_modifier_multiplier_invalid",
                            {"profile_id": profile_id, "multiplier": mult},
                            manifest_fingerprint,
                        )
                    multipliers.append(mult)
                    flags.append(bucket_flags)
                profile_multipliers[profile_id] = multipliers
                profile_flags[profile_id] = flags
            logger.info(
                "S2: zone modifiers enabled (profiles=%s overrides=%s emit_adjustment_flags=%s)",
                len(profile_multipliers),
                len(override_rules),
                emit_adjustment_flags,
            )
        else:
            logger.info("S2: zone modifiers absent; using neutral multipliers")

        current_phase = "shape_synthesis"
        shape_sum_abs_tol = float(baseline_policy.get("shape_sum_abs_tol") or EPS)
        shape_rows: list[dict] = []
        tracker = _ProgressTracker(
            domain_rows,
            logger,
            "S2: build class-zone shapes (domain=merchant_zone_profile_5A)",
        )
        for row in domain_df.iter_rows(named=True):
            tracker.update(1)
            demand_class = row.get("demand_class")
            legal_country_iso = row.get("legal_country_iso")
            tzid = row.get("tzid")
            channel_group = row.get("channel_group")

            rule = rules_map.get((demand_class, channel_group))
            if not rule:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_rule_missing",
                    {"demand_class": demand_class, "channel_group": channel_group},
                    manifest_fingerprint,
                )
            candidate_ids = rule.get("candidate_ids") or []
            message = f"5A.S2.template|{demand_class}|{channel_group}|{tzid}|{parameter_hash}"
            hash_value = _hash_u64(message)
            u_det = _u_det_from_hash(hash_value)
            idx = int(math.floor(u_det * len(candidate_ids)))
            if idx >= len(candidate_ids):
                idx = len(candidate_ids) - 1
            template_id = candidate_ids[idx]
            base_vector = template_vectors.get(template_id)
            if base_vector is None:
                _abort(
                    "S2_TEMPLATE_RESOLUTION_FAILED",
                    "V-06",
                    "template_vector_missing",
                    {"template_id": template_id},
                    manifest_fingerprint,
                )

            multipliers = None
            bucket_flags = None
            base_flags: list[str] = []
            if zone_modifiers:
                profile_id = None
                matched_override = None
                for override in override_rules:
                    if not isinstance(override, dict):
                        continue
                    match = override.get("match") or {}
                    if match.get("legal_country_iso_in") and legal_country_iso not in match.get("legal_country_iso_in"):
                        continue
                    if match.get("tzid_in") and tzid not in match.get("tzid_in"):
                        continue
                    if match.get("tzid_prefix_in"):
                        prefixes = match.get("tzid_prefix_in") or []
                        if not any(str(tzid).startswith(str(prefix)) for prefix in prefixes):
                            continue
                    matched_override = override
                    break
                if matched_override:
                    profile_id = matched_override.get("force_profile_id")
                    if emit_adjustment_flags and matched_override.get("override_id"):
                        base_flags.append(f"zone_override:{matched_override.get('override_id')}")
                else:
                    profile_id = f"{zone_group_prefix}{int(hash_value) % int(zone_group_buckets)}"
                if profile_id not in profile_multipliers:
                    _abort(
                        "S2_TEMPLATE_RESOLUTION_FAILED",
                        "V-06",
                        "zone_modifier_profile_missing",
                        {"profile_id": profile_id},
                        manifest_fingerprint,
                    )
                if emit_adjustment_flags and profile_id != neutral_profile_id:
                    base_flags.append(f"zone_profile:{profile_id}")
                multipliers = profile_multipliers.get(profile_id)
                bucket_flags = profile_flags.get(profile_id)

            if multipliers:
                adjusted = [value * multipliers[idx] for idx, value in enumerate(base_vector)]
            else:
                adjusted = list(base_vector)
                if emit_adjustment_flags:
                    bucket_flags = [[] for _ in range(t_week)]

            total = sum(adjusted)
            if total <= 0 or not math.isfinite(total):
                _abort(
                    "S2_SHAPE_NORMALISATION_FAILED",
                    "V-07",
                    "shape_total_invalid",
                    {"demand_class": demand_class, "tzid": tzid, "total": total},
                    manifest_fingerprint,
                )

            shape_values = [value / total for value in adjusted]
            sum_check = abs(sum(shape_values) - 1.0)
            if sum_check > shape_sum_abs_tol:
                _abort(
                    "S2_SHAPE_NORMALISATION_FAILED",
                    "V-07",
                    "shape_sum_tolerance_failed",
                    {"sum": sum_check, "tolerance": shape_sum_abs_tol},
                    manifest_fingerprint,
                )
            if any((not math.isfinite(value) or value < 0) for value in shape_values):
                _abort(
                    "S2_SHAPE_NORMALISATION_FAILED",
                    "V-07",
                    "shape_values_invalid",
                    {"demand_class": demand_class, "tzid": tzid},
                    manifest_fingerprint,
                )

            max_val = max(shape_values) if shape_values else 0.0
            min_val = min(shape_values) if shape_values else 0.0
            nonflat_ratio = max_val / max(min_val, EPS)
            if nonflat_ratio < nonflat_ratio_min:
                _abort(
                    "S2_SHAPE_NORMALISATION_FAILED",
                    "V-07",
                    "shape_nonflat_ratio_low",
                    {"demand_class": demand_class, "tzid": tzid, "ratio": nonflat_ratio},
                    manifest_fingerprint,
                )

            night_mass = sum(value for value, flag in zip(shape_values, is_night) if flag)
            if night_mass < min_mass_night:
                _abort(
                    "S2_SHAPE_NORMALISATION_FAILED",
                    "V-07",
                    "shape_night_mass_low",
                    {"demand_class": demand_class, "tzid": tzid, "night_mass": night_mass},
                    manifest_fingerprint,
                )

            if "weekend" in str(demand_class):
                weekend_mass = sum(value for value, flag in zip(shape_values, is_weekend) if flag)
                if weekend_mass < min_weekend_mass:
                    _abort(
                        "S2_SHAPE_NORMALISATION_FAILED",
                        "V-07",
                        "shape_weekend_mass_low",
                        {"demand_class": demand_class, "tzid": tzid, "weekend_mass": weekend_mass},
                        manifest_fingerprint,
                    )

            if "office_hours" in str(demand_class):
                office_mass = sum(value for value, flag in zip(shape_values, is_office) if flag)
                if office_mass < min_weekday_office_mass:
                    _abort(
                        "S2_SHAPE_NORMALISATION_FAILED",
                        "V-07",
                        "shape_office_mass_low",
                        {"demand_class": demand_class, "tzid": tzid, "office_mass": office_mass},
                        manifest_fingerprint,
                    )

            for idx in range(t_week):
                row_payload = {
                    "parameter_hash": str(parameter_hash),
                    "scenario_id": str(scenario_id),
                    "demand_class": demand_class,
                    "legal_country_iso": legal_country_iso,
                    "tzid": tzid,
                    "channel_group": channel_group,
                    "bucket_index": idx,
                    "shape_value": float(shape_values[idx]),
                    "s2_spec_version": S2_SPEC_VERSION,
                }
                if emit_adjustment_flags:
                    flags = list(base_flags)
                    if bucket_flags:
                        flags.extend(bucket_flags[idx])
                    row_payload["adjustment_flags"] = flags
                shape_rows.append(row_payload)

        counts["shape_rows"] = len(shape_rows)

        current_phase = "output_prepare"
        if shape_rows:
            shape_df = pl.DataFrame(shape_rows)
        else:
            shape_schema = {
                "parameter_hash": pl.Series([], dtype=pl.Utf8),
                "scenario_id": pl.Series([], dtype=pl.Utf8),
                "demand_class": pl.Series([], dtype=pl.Utf8),
                "legal_country_iso": pl.Series([], dtype=pl.Utf8),
                "tzid": pl.Series([], dtype=pl.Utf8),
                "channel_group": pl.Series([], dtype=pl.Utf8),
                "bucket_index": pl.Series([], dtype=pl.Int64),
                "shape_value": pl.Series([], dtype=pl.Float64),
                "s2_spec_version": pl.Series([], dtype=pl.Utf8),
            }
            if emit_adjustment_flags:
                shape_schema["adjustment_flags"] = pl.Series([], dtype=pl.List(pl.Utf8))
            shape_df = pl.DataFrame(shape_schema)
        shape_df = shape_df.sort(["demand_class", "legal_country_iso", "tzid", "channel_group", "bucket_index"])
        _validate_array_rows(
            shape_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/class_zone_shape_5A",
        )

        grid_df = pl.DataFrame(grid_rows).sort("bucket_index")

        catalogue_rows: list[dict] = []
        if domain_rows:
            catalogue_keys = (
                domain_df.select(["demand_class", "channel_group"]).unique().sort(["demand_class", "channel_group"])
            )
            for key_row in catalogue_keys.iter_rows(named=True):
                demand_class = key_row.get("demand_class")
                channel_group = key_row.get("channel_group")
                rule = rules_map.get((demand_class, channel_group))
                if not rule:
                    continue
                candidate_ids = rule.get("candidate_ids") or []
                if not candidate_ids:
                    continue
                template_id = candidate_ids[0]
                template = template_map.get(template_id) or {}
                catalogue_rows.append(
                    {
                        "parameter_hash": str(parameter_hash),
                        "scenario_id": str(scenario_id),
                        "demand_class": demand_class,
                        "channel_group": channel_group,
                        "template_id": template_id,
                        "template_type": template.get("shape_kind"),
                        "template_params": {
                            "selection_law": rule.get("selection_law"),
                            "candidate_template_ids": candidate_ids,
                        },
                        "policy_version": policy_versions.get("shape_library_version"),
                        "s2_spec_version": S2_SPEC_VERSION,
                    }
                )

        catalogue_df = None
        if catalogue_rows:
            _validate_array_rows(
                catalogue_rows,
                schema_5a,
                schema_layer1,
                schema_layer2,
                "model/class_shape_catalogue_5A",
            )
            catalogue_df = pl.DataFrame(catalogue_rows).sort(["demand_class", "channel_group"])

        current_phase = "output_write"
        grid_entry = find_dataset_entry(dictionary_5a, "shape_grid_definition_5A").entry
        grid_path = _resolve_dataset_path(grid_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(grid_path, grid_df, logger, "shape_grid_definition_5A")

        shape_entry = find_dataset_entry(dictionary_5a, "class_zone_shape_5A").entry
        shape_path = _resolve_dataset_path(shape_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(shape_path, shape_df, logger, "class_zone_shape_5A")

        if catalogue_df is not None:
            catalogue_entry = find_dataset_entry(dictionary_5a, "class_shape_catalogue_5A").entry
            catalogue_path = _resolve_dataset_path(
                catalogue_entry, run_paths, config.external_roots, tokens
            )
            _publish_parquet_idempotent(catalogue_path, catalogue_df, logger, "class_shape_catalogue_5A")
        else:
            logger.info("S2: class_shape_catalogue_5A not emitted (empty domain)")

        status = "PASS"
        timer.info("S2: completed weekly shape synthesis")
    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "S2_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "S2_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint and run_paths is not None:
            try:
                run_report_entry = find_dataset_entry(dictionary_5a, "s2_run_report_5A").entry
                run_report_path = _resolve_dataset_path(
                    run_report_entry, run_paths, config.external_roots, tokens
                )
                run_report = {
                    "layer": "layer2",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": run_id,
                    "status": status,
                    "seed": int(seed),
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": dict(policy_versions),
                    "scenario_id": scenario_id,
                    "counts": counts,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "shape_grid_definition_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "shape_grid_definition_5A").entry,
                            tokens,
                        ),
                        "class_zone_shape_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "class_zone_shape_5A").entry,
                            tokens,
                        ),
                        "class_shape_catalogue_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "class_shape_catalogue_5A").entry,
                            tokens,
                        ),
                        "format": "parquet",
                    },
                }
                run_report_path.parent.mkdir(parents=True, exist_ok=True)
                run_report_path.write_text(
                    json.dumps(run_report, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                logger.info("S2: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S2: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "S2_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if grid_path is None or shape_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "S2_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S2Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        grid_path=grid_path,
        shape_path=shape_path,
        catalogue_path=catalogue_path,
        run_report_path=run_report_path,
    )
