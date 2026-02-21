"""S3 baseline intensity runner for Segment 5A."""

from __future__ import annotations

import json
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


MODULE_NAME = "5A.s3_baseline_intensity"
SEGMENT = "5A"
STATE = "S3"
S3_SPEC_VERSION = "1.0.0"
PROGRESS_LOG_INTERVAL_SECONDS = 5.0
TAIL_RESCUE_COUNTRY_SUPPORT_WEIGHT = 0.20
FAST_ROW_VALIDATION_ANCHORS = {
    "model/merchant_zone_profile_5A",
    "model/shape_grid_definition_5A",
    "model/class_zone_shape_5A",
    "model/merchant_zone_baseline_local_5A",
    "model/class_zone_baseline_local_5A",
}
ROW_INDEX_COL = "__row_index"


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    baseline_local_path: Path
    class_baseline_path: Optional[Path]
    baseline_utc_path: Optional[Path]
    run_report_path: Path


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
        if now - self._last_log < PROGRESS_LOG_INTERVAL_SECONDS and self._processed < self._total:
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
    logger = get_logger("engine.layers.l2.seg_5A.s3_baseline_intensity.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


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
    logger=None,
    label: Optional[str] = None,
    total_rows: Optional[int] = None,
    progress_min_rows: int = 50000,
    frame: Optional[pl.DataFrame] = None,
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

    if frame is not None and anchor in FAST_ROW_VALIDATION_ANCHORS:
        if _validate_array_rows_fast(frame, item_schema, anchor, max_errors=max_errors):
            if logger and label and frame.height >= progress_min_rows:
                logger.info("%s fast-path validator rows=%s", label, frame.height)
            return

    validator = Draft202012Validator(item_schema)
    errors: list[dict[str, object]] = []
    tracker = None
    if logger and label and total_rows is not None and total_rows >= progress_min_rows:
        tracker = _ProgressTracker(total_rows, logger, label)
    for index, row in enumerate(rows):
        if tracker:
            tracker.update(1)
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


def _is_string_dtype(dtype: object) -> bool:
    return dtype in {pl.Utf8, pl.String, pl.Categorical, pl.Enum}


def _is_integer_dtype(dtype: object) -> bool:
    return bool(getattr(dtype, "is_integer", lambda: False)())


def _is_number_dtype(dtype: object) -> bool:
    return bool(getattr(dtype, "is_numeric", lambda: False)())


def _resolve_schema_ref(node: dict[str, object], defs: dict[str, object]) -> dict[str, object]:
    current: dict[str, object] = dict(node)
    while "$ref" in current:
        ref = str(current.get("$ref") or "")
        if not ref.startswith("#/$defs/"):
            raise ContractError(f"Unsupported schema ref for fast validator: {ref}")
        key = ref.split("/")[-1]
        target = defs.get(key)
        if not isinstance(target, dict):
            raise ContractError(f"Missing $defs target for fast validator: {ref}")
        merged = dict(target)
        for k, v in current.items():
            if k != "$ref":
                merged[k] = v
        current = merged
    return current


def _normalize_property_schema(raw_schema: dict[str, object], defs: dict[str, object]) -> dict[str, object]:
    schema = _resolve_schema_ref(raw_schema, defs)
    nullable = False

    if "anyOf" in schema:
        branches = schema.get("anyOf")
        if isinstance(branches, list):
            non_null_branch: Optional[dict[str, object]] = None
            for branch in branches:
                if not isinstance(branch, dict):
                    continue
                branch_resolved = _resolve_schema_ref(branch, defs)
                branch_type = branch_resolved.get("type")
                if branch_type == "null":
                    nullable = True
                    continue
                non_null_branch = branch_resolved
            if non_null_branch is not None:
                schema = non_null_branch

    schema_type = schema.get("type")
    schema_types: list[str] = []
    if isinstance(schema_type, str):
        schema_types = [schema_type]
    elif isinstance(schema_type, list):
        for item in schema_type:
            if isinstance(item, str):
                if item == "null":
                    nullable = True
                else:
                    schema_types.append(item)

    normalized: dict[str, object] = {
        "types": schema_types,
        "nullable": nullable,
    }
    for key in (
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "pattern",
        "enum",
        "minLength",
        "maxLength",
    ):
        if key in schema:
            normalized[key] = schema[key]
    return normalized


def _collect_row_indices(frame_idx: pl.DataFrame, expr: pl.Expr, limit: int) -> list[int]:
    if limit <= 0:
        return []
    sample = frame_idx.filter(expr).select(ROW_INDEX_COL).head(limit)
    if sample.is_empty():
        return []
    return [int(value) for value in sample.get_column(ROW_INDEX_COL).to_list()]


def _append_expr_errors(
    frame_idx: pl.DataFrame,
    expr: pl.Expr,
    field: str,
    message: str,
    errors: list[dict[str, object]],
    max_errors: int,
) -> None:
    remaining = max_errors - len(errors)
    if remaining <= 0:
        return
    indices = _collect_row_indices(frame_idx, expr, remaining)
    for row_index in indices:
        errors.append({"row_index": row_index, "field": field, "message": message})
        if len(errors) >= max_errors:
            break


def _validate_array_rows_fast(
    frame: pl.DataFrame,
    item_schema: dict[str, object],
    anchor: str,
    max_errors: int = 5,
) -> bool:
    defs = item_schema.get("$defs") or {}
    if not isinstance(defs, dict):
        return False

    required = item_schema.get("required") or []
    properties = item_schema.get("properties") or {}
    if not isinstance(required, list) or not isinstance(properties, dict):
        return False

    errors: list[dict[str, object]] = []
    for column in required:
        if isinstance(column, str) and column not in frame.columns:
            errors.append(
                {
                    "row_index": -1,
                    "field": column,
                    "message": f"required property '{column}' is missing",
                }
            )
        if len(errors) >= max_errors:
            break
    if errors:
        lines = [f"row {item['row_index']}: {item['field']} {item['message']}".strip() for item in errors]
        raise SchemaValidationError("Schema validation failed:\n" + "\n".join(lines), errors)

    frame_idx = frame.with_row_index(ROW_INDEX_COL)
    required_set = {str(item) for item in required if isinstance(item, str)}

    for column, raw_schema in properties.items():
        if column not in frame.columns:
            continue
        if not isinstance(raw_schema, dict):
            return False
        normalized = _normalize_property_schema(raw_schema, defs)
        types = normalized.get("types") or []
        if not isinstance(types, list) or len(types) != 1:
            return False
        schema_type = str(types[0])
        nullable = bool(normalized.get("nullable"))
        dtype = frame.schema.get(column)

        if not nullable:
            _append_expr_errors(
                frame_idx,
                pl.col(column).is_null(),
                column,
                "null is not allowed",
                errors,
                max_errors,
            )
            if len(errors) >= max_errors:
                break

        non_null = pl.col(column).is_not_null()
        if schema_type == "string":
            if not _is_string_dtype(dtype):
                _append_expr_errors(
                    frame_idx,
                    non_null,
                    column,
                    "value is not of type string",
                    errors,
                    max_errors,
                )
            else:
                pattern = normalized.get("pattern")
                if isinstance(pattern, str):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (~pl.col(column).str.contains(pattern)),
                        column,
                        "value does not match required pattern",
                        errors,
                        max_errors,
                    )
                min_len = normalized.get("minLength")
                if isinstance(min_len, int):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column).str.len_chars() < min_len),
                        column,
                        f"string length is less than minimum {min_len}",
                        errors,
                        max_errors,
                    )
                max_len = normalized.get("maxLength")
                if isinstance(max_len, int):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column).str.len_chars() > max_len),
                        column,
                        f"string length exceeds maximum {max_len}",
                        errors,
                        max_errors,
                    )
                enum_values = normalized.get("enum")
                if isinstance(enum_values, list) and enum_values:
                    _append_expr_errors(
                        frame_idx,
                        non_null & (~pl.col(column).is_in(enum_values)),
                        column,
                        "value is not in enum",
                        errors,
                        max_errors,
                    )
        elif schema_type == "integer":
            if not _is_integer_dtype(dtype):
                _append_expr_errors(
                    frame_idx,
                    non_null,
                    column,
                    "value is not of type integer",
                    errors,
                    max_errors,
                )
            else:
                minimum = normalized.get("minimum")
                if isinstance(minimum, (int, float)):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column) < minimum),
                        column,
                        f"value is less than minimum {minimum}",
                        errors,
                        max_errors,
                    )
                maximum = normalized.get("maximum")
                if isinstance(maximum, (int, float)):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column) > maximum),
                        column,
                        f"value exceeds maximum {maximum}",
                        errors,
                        max_errors,
                    )
        elif schema_type == "number":
            if not _is_number_dtype(dtype):
                _append_expr_errors(
                    frame_idx,
                    non_null,
                    column,
                    "value is not of type number",
                    errors,
                    max_errors,
                )
            else:
                minimum = normalized.get("minimum")
                if isinstance(minimum, (int, float)):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column) < minimum),
                        column,
                        f"value is less than minimum {minimum}",
                        errors,
                        max_errors,
                    )
                maximum = normalized.get("maximum")
                if isinstance(maximum, (int, float)):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column) > maximum),
                        column,
                        f"value exceeds maximum {maximum}",
                        errors,
                        max_errors,
                    )
                ex_min = normalized.get("exclusiveMinimum")
                if isinstance(ex_min, (int, float)):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column) <= ex_min),
                        column,
                        f"value must be > {ex_min}",
                        errors,
                        max_errors,
                    )
                ex_max = normalized.get("exclusiveMaximum")
                if isinstance(ex_max, (int, float)):
                    _append_expr_errors(
                        frame_idx,
                        non_null & (pl.col(column) >= ex_max),
                        column,
                        f"value must be < {ex_max}",
                        errors,
                        max_errors,
                    )
        elif schema_type == "boolean":
            if dtype != pl.Boolean:
                _append_expr_errors(
                    frame_idx,
                    non_null,
                    column,
                    "value is not of type boolean",
                    errors,
                    max_errors,
                )
        else:
            return False

        if len(errors) >= max_errors:
            break

        if column in required_set and column not in frame.columns:
            errors.append(
                {
                    "row_index": -1,
                    "field": column,
                    "message": f"required property '{column}' is missing",
                }
            )
            if len(errors) >= max_errors:
                break

    if errors:
        lines = [f"row {item['row_index']}: {item['field']} {item['message']}".strip() for item in errors]
        raise SchemaValidationError("Schema validation failed:\n" + "\n".join(lines), errors)
    return True


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
                "S3_OUTPUT_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(path), "label": label},
            )
        tmp_path.unlink()
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
        logger.info("S3: output already exists and is identical; skipping publish (%s).", label)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "S3_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(path), "label": label, "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info("S3: published %s to %s", label, path)
    return True


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l2.seg_5A.s3_baseline_intensity.runner")
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
    baseline_local_path: Optional[Path] = None
    class_baseline_path: Optional[Path] = None
    baseline_utc_path: Optional[Path] = None
    run_report_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    scenario_id: Optional[str] = None
    seed: int = 0

    policy_versions: dict[str, Optional[str]] = {
        "baseline_intensity_policy_version": None,
        "demand_scale_policy_version": None,
        "baseline_validation_policy_version": None,
    }

    counts: dict[str, object] = {
        "domain_rows": 0,
        "baseline_rows": 0,
        "shape_rows": 0,
        "grid_rows": 0,
        "class_baseline_rows": 0,
        "tail_target_rows": 0,
        "tail_rescued_rows": 0,
        "tail_rescue_enabled": False,
    }
    metrics: dict[str, Optional[float]] = {
        "lambda_local_base_min": None,
        "lambda_local_base_median": None,
        "lambda_local_base_p95": None,
        "lambda_local_base_max": None,
        "weekly_sum_relative_error_max": None,
        "weekly_sum_relative_error_p95": None,
        "tail_zero_rate_before_rescue": None,
        "tail_zero_rate_after_rescue": None,
        "tail_added_weekly_mass": None,
        "tail_support_strength_p95": None,
    }
    weekly_sum_error_violations = 0

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
        logger.info("S3: run log initialized at %s", run_log_path)

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
            "S3: objective=compose weekly merchant-zone baselines "
            "(gate S0/S1/S2 + baseline policy, output merchant_zone_baseline_local_5A + optional aggregates)"
        )
        logger.info(
            "S3: story=compose baseline intensities gate_inputs=s0_gate_receipt_5A,sealed_inputs_5A,"
            "merchant_zone_profile_5A,shape_grid_definition_5A,class_zone_shape_5A outputs="
            "merchant_zone_baseline_local_5A,class_zone_baseline_local_5A"
        )
        timer.info("S3: phase begin")

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
                "S3_GATE_OR_S2_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_id_value = receipt_payload.get("scenario_id")
        if isinstance(scenario_id_value, list):
            if len(scenario_id_value) != 1:
                _abort(
                    "S3_GATE_OR_S2_INVALID",
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
                "S3_GATE_OR_S2_INVALID",
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
                    "S3_UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        if not isinstance(sealed_inputs, list):
            _abort(
                "S3_GATE_OR_S2_INVALID",
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
                "S3_GATE_OR_S2_INVALID",
                "V-03",
                "sealed_inputs_duplicate_id",
                {"detail": "duplicate artifact_id in sealed_inputs_5A"},
                manifest_fingerprint,
            )
        for row in sealed_sorted:
            if not isinstance(row, dict):
                continue
            if str(row.get("parameter_hash")) != str(parameter_hash) or str(
                row.get("manifest_fingerprint")
            ) != str(manifest_fingerprint):
                _abort(
                    "S3_GATE_OR_S2_INVALID",
                    "V-03",
                    "sealed_inputs_identity_mismatch",
                    {
                        "artifact_id": row.get("artifact_id"),
                        "expected_parameter_hash": parameter_hash,
                        "expected_manifest_fingerprint": manifest_fingerprint,
                        "actual_parameter_hash": row.get("parameter_hash"),
                        "actual_manifest_fingerprint": row.get("manifest_fingerprint"),
                    },
                    manifest_fingerprint,
                )
        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if sealed_digest != receipt_payload.get("sealed_inputs_digest"):
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {
                    "expected": receipt_payload.get("sealed_inputs_digest"),
                    "actual": sealed_digest,
                },
                manifest_fingerprint,
            )

        sealed_by_id = {row.get("artifact_id"): row for row in sealed_sorted if isinstance(row, dict)}

        current_phase = "policy_load"
        profile_row = _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_profile_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S3_REQUIRED_INPUT_MISSING",
        )
        if profile_row is None:
            logger.warning(
                "S3: sealed_inputs_5A missing merchant_zone_profile_5A; proceeding with direct path resolution"
            )
        grid_row = _resolve_sealed_row(
            sealed_by_id,
            "shape_grid_definition_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S3_REQUIRED_INPUT_MISSING",
        )
        if grid_row is None:
            logger.warning(
                "S3: sealed_inputs_5A missing shape_grid_definition_5A; proceeding with direct path resolution"
            )
        shape_row = _resolve_sealed_row(
            sealed_by_id,
            "class_zone_shape_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S3_REQUIRED_INPUT_MISSING",
        )
        if shape_row is None:
            logger.warning(
                "S3: sealed_inputs_5A missing class_zone_shape_5A; proceeding with direct path resolution"
            )
        baseline_policy_row = sealed_by_id.get("baseline_intensity_policy_5A")
        demand_scale_row = sealed_by_id.get("demand_scale_policy_5A")
        if not baseline_policy_row:
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-04",
                "baseline_intensity_policy_missing",
                {"artifact_id": "baseline_intensity_policy_5A"},
                manifest_fingerprint,
            )
        if not demand_scale_row:
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-04",
                "demand_scale_policy_missing",
                {"artifact_id": "demand_scale_policy_5A"},
                manifest_fingerprint,
            )

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

        demand_scale_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "demand_scale_policy_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        demand_scale_policy = _load_yaml(demand_scale_path)
        _validate_payload(
            schema_5a, schema_layer1, schema_layer2, "policy/demand_scale_policy_5A", demand_scale_policy
        )
        policy_versions["demand_scale_policy_version"] = str(demand_scale_policy.get("version") or "")

        current_phase = "input_resolution"
        profile_entry = find_dataset_entry(dictionary_5a, "merchant_zone_profile_5A").entry
        profile_path = _resolve_dataset_path(profile_entry, run_paths, config.external_roots, tokens)
        if not profile_path.exists():
            _abort(
                "S3_REQUIRED_INPUT_MISSING",
                "V-05",
                "merchant_zone_profile_missing",
                {"path": str(profile_path)},
                manifest_fingerprint,
            )
        profile_df = pl.read_parquet(profile_path)
        if "channel_group" not in profile_df.columns:
            logger.warning(
                "S3: merchant_zone_profile_5A missing channel_group; defaulting to mixed for compatibility."
            )
            profile_df = profile_df.with_columns(pl.lit("mixed").alias("channel_group"))
        profile_required_columns = [
            "manifest_fingerprint",
            "parameter_hash",
            "merchant_id",
            "legal_country_iso",
            "tzid",
            "demand_class",
            "demand_subclass",
            "channel_group",
            "weekly_volume_expected",
            "scale_factor",
        ]
        missing_profile_columns = [column for column in profile_required_columns if column not in profile_df.columns]
        if missing_profile_columns:
            _abort(
                "S3_REQUIRED_INPUT_MISSING",
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
            logger=logger,
            label="S3: validate merchant_zone_profile_5A rows",
            total_rows=profile_df.height,
            frame=profile_df,
        )

        grid_entry = find_dataset_entry(dictionary_5a, "shape_grid_definition_5A").entry
        grid_path = _resolve_dataset_path(grid_entry, run_paths, config.external_roots, tokens)
        if not grid_path.exists():
            _abort(
                "S3_REQUIRED_INPUT_MISSING",
                "V-05",
                "shape_grid_definition_missing",
                {"path": str(grid_path)},
                manifest_fingerprint,
            )
        grid_df = pl.read_parquet(grid_path)
        _validate_array_rows(
            grid_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/shape_grid_definition_5A",
            logger=logger,
            label="S3: validate shape_grid_definition_5A rows",
            total_rows=grid_df.height,
            frame=grid_df,
        )

        shape_entry = find_dataset_entry(dictionary_5a, "class_zone_shape_5A").entry
        shape_path = _resolve_dataset_path(shape_entry, run_paths, config.external_roots, tokens)
        if not shape_path.exists():
            _abort(
                "S3_REQUIRED_INPUT_MISSING",
                "V-05",
                "class_zone_shape_missing",
                {"path": str(shape_path)},
                manifest_fingerprint,
            )
        shape_df = pl.read_parquet(shape_path)

        _validate_array_rows(
            shape_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/class_zone_shape_5A",
            logger=logger,
            label="S3: validate class_zone_shape_5A rows",
            total_rows=shape_df.height,
            frame=shape_df,
        )
        shape_df = shape_df.select(
            [
                "parameter_hash",
                "scenario_id",
                "demand_class",
                "legal_country_iso",
                "tzid",
                "channel_group",
                "bucket_index",
                "shape_value",
            ]
        )
        timer.info(
            "S3: phase input_load_schema_validation complete (profile_rows=%s, grid_rows=%s, shape_rows=%s)",
            profile_df.height,
            grid_df.height,
            shape_df.height,
        )

        grid_df = grid_df.filter(pl.col("parameter_hash") == str(parameter_hash))
        grid_df = grid_df.filter(pl.col("scenario_id") == str(scenario_id))
        if grid_df.is_empty():
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "grid_empty",
                {"parameter_hash": parameter_hash, "scenario_id": scenario_id},
                manifest_fingerprint,
            )
        grid_df = grid_df.sort("bucket_index")
        grid_bucket_indices = grid_df.get_column("bucket_index").to_list()
        if grid_bucket_indices != list(range(len(grid_bucket_indices))):
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "grid_bucket_index_invalid",
                {"bucket_index_sample": grid_bucket_indices[:5]},
                manifest_fingerprint,
            )

        shape_df = shape_df.filter(pl.col("parameter_hash") == str(parameter_hash))
        shape_df = shape_df.filter(pl.col("scenario_id") == str(scenario_id))
        if shape_df.is_empty():
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "shape_empty",
                {"parameter_hash": parameter_hash, "scenario_id": scenario_id},
                manifest_fingerprint,
            )
        if shape_df.filter(~pl.col("bucket_index").is_in(grid_bucket_indices)).height:
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "shape_bucket_out_of_range",
                {"grid_bucket_count": grid_df.height},
                manifest_fingerprint,
            )
        shape_grouped = shape_df.group_by(
            ["demand_class", "legal_country_iso", "tzid", "channel_group"]
        ).agg(
            [
                pl.col("bucket_index").n_unique().alias("bucket_unique"),
                pl.len().alias("bucket_rows"),
            ]
        )
        invalid_shape = shape_grouped.filter(
            (pl.col("bucket_unique") != grid_df.height) | (pl.col("bucket_rows") != grid_df.height)
        )
        if invalid_shape.height:
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "shape_bucket_coverage_invalid",
                {
                    "expected_bucket_count": grid_df.height,
                    "sample": invalid_shape.head(5).to_dicts(),
                },
                manifest_fingerprint,
            )
        counts["shape_rows"] = shape_df.height
        counts["grid_rows"] = grid_df.height
        logger.info(
            "S3: shape grid validated (grid_buckets=%s) and shapes filtered (rows=%s, scenario_id=%s)",
            grid_df.height,
            shape_df.height,
            scenario_id,
        )

        current_phase = "domain_scan"
        profile_params = profile_df.get_column("parameter_hash").drop_nulls().unique().to_list()
        if any(str(value) != str(parameter_hash) for value in profile_params):
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "parameter_hash_mismatch_in_profile",
                {"expected": parameter_hash, "found": profile_params},
                manifest_fingerprint,
            )
        profile_manifests = profile_df.get_column("manifest_fingerprint").drop_nulls().unique().to_list()
        if any(str(value) != str(manifest_fingerprint) for value in profile_manifests):
            _abort(
                "S3_GATE_OR_S2_INVALID",
                "V-05",
                "manifest_fingerprint_mismatch_in_profile",
                {"expected": manifest_fingerprint, "found": profile_manifests},
                manifest_fingerprint,
            )

        duplicate_counts = (
            profile_df.group_by(["merchant_id", "legal_country_iso", "tzid"])
            .len()
            .filter(pl.col("len") > 1)
        )
        if duplicate_counts.height:
            _abort(
                "S3_DOMAIN_ALIGNMENT_FAILED",
                "V-06",
                "duplicate_merchant_zone",
                {"rows": duplicate_counts.height},
                manifest_fingerprint,
            )

        counts["domain_rows"] = profile_df.height
        logger.info(
            "S3: domain derived from merchant_zone_profile_5A "
            "(merchants=%s zones=%s rows=%s)",
            profile_df.get_column("merchant_id").n_unique(),
            profile_df.select(["legal_country_iso", "tzid"]).unique().height,
            profile_df.height,
        )
        timer.info("S3: phase domain_alignment complete (domain_rows=%s)", profile_df.height)

        current_phase = "scale_policy"
        scale_source = baseline_policy.get("scale_source_field")
        if scale_source != "weekly_volume_expected":
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-07",
                "unsupported_scale_source",
                {"scale_source_field": scale_source},
                manifest_fingerprint,
            )
        clip_mode = baseline_policy.get("clip_mode")
        if clip_mode != "hard_fail":
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-07",
                "unsupported_clip_mode",
                {"clip_mode": clip_mode},
                manifest_fingerprint,
            )
        hard_limits = baseline_policy.get("hard_limits") or {}
        max_lambda_per_bucket = float(hard_limits.get("max_lambda_per_bucket") or 0)
        max_weekly_volume_expected = float(hard_limits.get("max_weekly_volume_expected") or 0)
        if max_lambda_per_bucket <= 0 or max_weekly_volume_expected <= 0:
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-07",
                "hard_limits_invalid",
                {"hard_limits": hard_limits},
                manifest_fingerprint,
            )

        weekly_sum_rel_tol = float(baseline_policy.get("weekly_sum_rel_tol") or 0)
        if weekly_sum_rel_tol <= 0:
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-07",
                "weekly_sum_rel_tol_invalid",
                {"weekly_sum_rel_tol": weekly_sum_rel_tol},
                manifest_fingerprint,
            )

        tail_rescue_policy = baseline_policy.get("tail_rescue") or {}
        tail_rescue_enabled = bool(tail_rescue_policy.get("enabled", False))
        tail_target_subclass = str(tail_rescue_policy.get("target_subclass") or "tail_zone")
        tail_floor_epsilon = float(tail_rescue_policy.get("tail_floor_epsilon") or 0.0)
        tail_lift_power = float(tail_rescue_policy.get("tail_lift_power") or 0.0)
        tail_lift_max_multiplier = float(tail_rescue_policy.get("tail_lift_max_multiplier") or 0.0)
        counts["tail_rescue_enabled"] = tail_rescue_enabled
        if tail_rescue_enabled:
            if tail_target_subclass != "tail_zone":
                _abort(
                    "S3_REQUIRED_POLICY_MISSING",
                    "V-07",
                    "tail_rescue_target_subclass_invalid",
                    {"target_subclass": tail_target_subclass},
                    manifest_fingerprint,
                )
            if tail_floor_epsilon < 0:
                _abort(
                    "S3_REQUIRED_POLICY_MISSING",
                    "V-07",
                    "tail_rescue_floor_invalid",
                    {"tail_floor_epsilon": tail_floor_epsilon},
                    manifest_fingerprint,
                )
            if tail_lift_power <= 0:
                _abort(
                    "S3_REQUIRED_POLICY_MISSING",
                    "V-07",
                    "tail_rescue_power_invalid",
                    {"tail_lift_power": tail_lift_power},
                    manifest_fingerprint,
                )
            if tail_lift_max_multiplier < 1:
                _abort(
                    "S3_REQUIRED_POLICY_MISSING",
                    "V-07",
                    "tail_rescue_multiplier_invalid",
                    {"tail_lift_max_multiplier": tail_lift_max_multiplier},
                    manifest_fingerprint,
                )

        if baseline_policy.get("utc_projection", {}).get("emit_utc_baseline"):
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-07",
                "utc_baseline_not_supported",
                {"detail": "emit_utc_baseline is true but UTC projection is not implemented."},
                manifest_fingerprint,
            )

        if profile_df.filter(pl.col("channel_group").is_null()).height:
            _abort(
                "S3_DOMAIN_ALIGNMENT_FAILED",
                "V-07",
                "profile_channel_group_missing",
                {"detail": "merchant_zone_profile_5A contains null channel_group"},
                manifest_fingerprint,
            )
        base_scale_col = pl.col("weekly_volume_expected").cast(pl.Float64)
        if profile_df.filter(base_scale_col.is_null()).height:
            _abort(
                "S3_SCALE_JOIN_FAILED",
                "V-07",
                "weekly_volume_missing",
                {"detail": "weekly_volume_expected contains null"},
                manifest_fingerprint,
            )
        profile_df = profile_df.with_columns(base_scale_col.alias("base_scale"))
        if profile_df.filter(~pl.col("base_scale").is_finite()).height:
            _abort(
                "S3_SCALE_JOIN_FAILED",
                "V-07",
                "weekly_volume_non_finite",
                {"detail": "weekly_volume_expected contains NaN/Inf"},
                manifest_fingerprint,
            )
        if profile_df.filter(pl.col("base_scale") < 0).height:
            _abort(
                "S3_SCALE_JOIN_FAILED",
                "V-07",
                "weekly_volume_negative",
                {"detail": "weekly_volume_expected contains negative values"},
                manifest_fingerprint,
            )
        if profile_df.filter(pl.col("base_scale") > max_weekly_volume_expected).height:
            _abort(
                "S3_INTENSITY_NUMERIC_INVALID",
                "V-07",
                "weekly_volume_exceeds_limit",
                {"max_weekly_volume_expected": max_weekly_volume_expected},
                manifest_fingerprint,
            )
        tail_target_rows = int(profile_df.filter(pl.col("demand_subclass") == "tail_zone").height)
        counts["tail_target_rows"] = tail_target_rows

        if tail_rescue_enabled and tail_target_rows > 0:
            non_tail_df = profile_df.filter(pl.col("demand_subclass") != tail_target_subclass)
            support_tz_df = non_tail_df.group_by("tzid").agg(pl.col("base_scale").sum().alias("support_tz"))
            support_country_df = non_tail_df.group_by("legal_country_iso").agg(
                pl.col("base_scale").sum().alias("support_country")
            )
            support_tz_denominator = float(
                support_tz_df.select(pl.col("support_tz").quantile(0.95)).item() or 0.0
            )
            support_country_denominator = float(
                support_country_df.select(pl.col("support_country").quantile(0.95)).item() or 0.0
            )
            support_tz_denominator = max(support_tz_denominator, 1.0)
            support_country_denominator = max(support_country_denominator, 1.0)

            tail_mask = pl.col("demand_subclass") == tail_target_subclass
            profile_df = (
                profile_df.join(support_tz_df, on="tzid", how="left")
                .join(support_country_df, on="legal_country_iso", how="left")
                .with_columns(
                    [
                        pl.col("support_tz").fill_null(0.0),
                        pl.col("support_country").fill_null(0.0),
                    ]
                )
                .with_columns(
                    [
                        pl.min_horizontal(
                            pl.lit(1.0), pl.col("support_tz") / pl.lit(float(support_tz_denominator))
                        ).alias("tail_support_tz_norm"),
                        pl.min_horizontal(
                            pl.lit(1.0),
                            pl.col("support_country") / pl.lit(float(support_country_denominator)),
                        ).alias("tail_support_country_norm"),
                    ]
                )
                .with_columns(
                    pl.max_horizontal(
                        pl.col("tail_support_tz_norm"),
                        pl.col("tail_support_country_norm") * pl.lit(float(TAIL_RESCUE_COUNTRY_SUPPORT_WEIGHT)),
                    ).alias("tail_support_strength")
                )
                .with_columns(
                    (
                        pl.lit(1.0)
                        + (pl.lit(float(tail_lift_max_multiplier)) - pl.lit(1.0))
                        * pl.col("tail_support_strength").pow(float(tail_lift_power))
                    ).alias("tail_lift_multiplier")
                )
                .with_columns(
                    (pl.lit(float(tail_floor_epsilon)) * pl.col("tail_lift_multiplier")).alias("tail_floor_target")
                )
                .with_columns(
                    pl.when(tail_mask & (pl.col("tail_support_strength") > 0))
                    .then(pl.max_horizontal(pl.col("base_scale"), pl.col("tail_floor_target")))
                    .otherwise(pl.col("base_scale"))
                    .alias("effective_base_scale")
                )
            )

            if profile_df.filter(pl.col("effective_base_scale") > max_weekly_volume_expected).height:
                _abort(
                    "S3_INTENSITY_NUMERIC_INVALID",
                    "V-07",
                    "weekly_volume_exceeds_limit_after_tail_rescue",
                    {"max_weekly_volume_expected": max_weekly_volume_expected},
                    manifest_fingerprint,
                )

            tail_stats_rows = profile_df.filter(tail_mask).select(
                [
                    pl.len().alias("tail_rows"),
                    (pl.col("base_scale") <= 0).cast(pl.Int64).sum().alias("tail_zero_before"),
                    (pl.col("effective_base_scale") <= 0).cast(pl.Int64).sum().alias("tail_zero_after"),
                    (pl.col("effective_base_scale") > pl.col("base_scale"))
                    .cast(pl.Int64)
                    .sum()
                    .alias("tail_rescued_rows"),
                    (
                        pl.max_horizontal(
                            pl.col("effective_base_scale") - pl.col("base_scale"),
                            pl.lit(0.0),
                        )
                    )
                    .sum()
                    .alias("tail_added_mass"),
                    pl.col("tail_support_strength").quantile(0.95).alias("tail_support_strength_p95"),
                ]
            ).to_dicts()
            tail_stats = tail_stats_rows[0] if tail_stats_rows else {}
            tail_rows = int(tail_stats.get("tail_rows") or 0)
            tail_zero_before = int(tail_stats.get("tail_zero_before") or 0)
            tail_zero_after = int(tail_stats.get("tail_zero_after") or 0)
            tail_rescued_rows = int(tail_stats.get("tail_rescued_rows") or 0)
            tail_added_mass = float(tail_stats.get("tail_added_mass") or 0.0)
            tail_support_strength_p95 = float(tail_stats.get("tail_support_strength_p95") or 0.0)

            counts["tail_rescued_rows"] = tail_rescued_rows
            metrics["tail_zero_rate_before_rescue"] = (
                float(tail_zero_before / tail_rows) if tail_rows > 0 else None
            )
            metrics["tail_zero_rate_after_rescue"] = (
                float(tail_zero_after / tail_rows) if tail_rows > 0 else None
            )
            metrics["tail_added_weekly_mass"] = tail_added_mass
            metrics["tail_support_strength_p95"] = tail_support_strength_p95
            logger.info(
                "S3: tail_rescue enabled target=%s rows=%s rescued=%s "
                "zero_rate_before=%.6f zero_rate_after=%.6f added_mass=%.6f support_p95=%.6f",
                tail_target_subclass,
                tail_rows,
                tail_rescued_rows,
                float(metrics["tail_zero_rate_before_rescue"] or 0.0),
                float(metrics["tail_zero_rate_after_rescue"] or 0.0),
                tail_added_mass,
                tail_support_strength_p95,
            )
            profile_df = profile_df.with_columns(
                [
                    pl.col("effective_base_scale").alias("base_scale"),
                    pl.when(tail_mask)
                    .then(pl.col("effective_base_scale"))
                    .otherwise(pl.col("weekly_volume_expected"))
                    .alias("weekly_volume_expected"),
                ]
            ).drop(
                [
                    "support_tz",
                    "support_country",
                    "tail_support_tz_norm",
                    "tail_support_country_norm",
                    "tail_support_strength",
                    "tail_lift_multiplier",
                    "tail_floor_target",
                    "effective_base_scale",
                ]
            )

        current_phase = "shape_join"
        join_keys = ["demand_class", "legal_country_iso", "tzid", "channel_group"]
        shape_df = shape_df.select(join_keys + ["bucket_index", "shape_value"])
        joined = profile_df.join(shape_df, on=join_keys, how="left")
        if joined.filter(pl.col("shape_value").is_null()).height:
            _abort(
                "S3_SHAPE_JOIN_FAILED",
                "V-08",
                "shape_missing",
                {"detail": "missing shape_value after join"},
                manifest_fingerprint,
            )
        expected_rows = profile_df.height * grid_df.height
        if joined.height != expected_rows:
            _abort(
                "S3_DOMAIN_ALIGNMENT_FAILED",
                "V-08",
                "baseline_row_count_mismatch",
                {"expected_rows": expected_rows, "actual_rows": joined.height},
                manifest_fingerprint,
            )
        bucket_counts = (
            joined.group_by(["merchant_id", "legal_country_iso", "tzid"]).len()
        )
        invalid_buckets = bucket_counts.filter(pl.col("len") != grid_df.height)
        if invalid_buckets.height:
            _abort(
                "S3_DOMAIN_ALIGNMENT_FAILED",
                "V-08",
                "bucket_coverage_mismatch",
                {
                    "expected_bucket_count": grid_df.height,
                    "sample": invalid_buckets.head(5).to_dicts(),
                },
                manifest_fingerprint,
            )
        logger.info(
            "S3: shape join expanded domain (merchant_zone_rows=%s, buckets_per_zone=%s, joined_rows=%s)",
            profile_df.height,
            grid_df.height,
            joined.height,
        )

        current_phase = "baseline_compute"
        joined = joined.with_columns(
            (pl.col("base_scale") * pl.col("shape_value")).alias("lambda_local_base")
        )
        if joined.filter(~pl.col("lambda_local_base").is_finite()).height:
            _abort(
                "S3_INTENSITY_NUMERIC_INVALID",
                "V-08",
                "lambda_non_finite",
                {"detail": "lambda_local_base contains NaN/Inf"},
                manifest_fingerprint,
            )
        if joined.filter(pl.col("lambda_local_base") < 0).height:
            _abort(
                "S3_INTENSITY_NUMERIC_INVALID",
                "V-08",
                "lambda_negative",
                {"detail": "lambda_local_base contains negative"},
                manifest_fingerprint,
            )
        if joined.filter(pl.col("lambda_local_base") > max_lambda_per_bucket).height:
            _abort(
                "S3_INTENSITY_NUMERIC_INVALID",
                "V-08",
                "lambda_exceeds_limit",
                {"max_lambda_per_bucket": max_lambda_per_bucket},
                manifest_fingerprint,
            )

        sums_df = (
            joined.group_by(["merchant_id", "legal_country_iso", "tzid"])
            .agg(
                [
                    pl.col("lambda_local_base").sum().alias("weekly_sum"),
                    pl.col("base_scale").first().alias("base_scale"),
                ]
            )
            .with_columns(
                (
                    (pl.col("weekly_sum") - pl.col("base_scale")).abs()
                    / pl.max_horizontal(pl.col("base_scale").abs(), pl.lit(1.0))
                ).alias("weekly_rel_error")
            )
        )
        violations = sums_df.filter(pl.col("weekly_rel_error") > weekly_sum_rel_tol)
        weekly_sum_error_violations = int(violations.height)
        if weekly_sum_error_violations:
            _abort(
                "S3_INTENSITY_NUMERIC_INVALID",
                "V-08",
                "weekly_sum_tolerance_failed",
                {"violations": weekly_sum_error_violations, "tolerance": weekly_sum_rel_tol},
                manifest_fingerprint,
            )

        if joined.height:
            metrics["lambda_local_base_min"] = float(joined.select(pl.col("lambda_local_base").min()).item())
            metrics["lambda_local_base_median"] = float(
                joined.select(pl.col("lambda_local_base").median()).item()
            )
            metrics["lambda_local_base_p95"] = float(
                joined.select(pl.col("lambda_local_base").quantile(0.95)).item()
            )
            metrics["lambda_local_base_max"] = float(joined.select(pl.col("lambda_local_base").max()).item())
            metrics["weekly_sum_relative_error_max"] = float(
                sums_df.select(pl.col("weekly_rel_error").max()).item()
            )
            metrics["weekly_sum_relative_error_p95"] = float(
                sums_df.select(pl.col("weekly_rel_error").quantile(0.95)).item()
            )
            logger.info(
                "S3: baseline computed (lambda_min=%s lambda_max=%s weekly_rel_error_p95=%s)",
                metrics["lambda_local_base_min"],
                metrics["lambda_local_base_max"],
                metrics["weekly_sum_relative_error_p95"],
            )
        timer.info(
            "S3: phase core_compute complete (joined_rows=%s, weekly_groups=%s)",
            joined.height,
            sums_df.height,
        )

        joined = joined.with_columns(
            [
                pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
                pl.lit(str(parameter_hash)).alias("parameter_hash"),
                pl.lit(str(scenario_id)).alias("scenario_id"),
                pl.lit(S3_SPEC_VERSION).alias("s3_spec_version"),
                pl.lit(str(scale_source)).alias("scale_source"),
                pl.lit(False).alias("baseline_clip_applied"),
            ]
        )
        baseline_local_df = joined.select(
            [
                "manifest_fingerprint",
                "parameter_hash",
                "scenario_id",
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "channel_group",
                "bucket_index",
                "lambda_local_base",
                "s3_spec_version",
                "scale_source",
                "weekly_volume_expected",
                "scale_factor",
                "baseline_clip_applied",
            ]
        ).sort(["merchant_id", "legal_country_iso", "tzid", "bucket_index"])
        counts["baseline_rows"] = baseline_local_df.height

        _validate_array_rows(
            baseline_local_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/merchant_zone_baseline_local_5A",
            logger=logger,
            label="S3: validate merchant_zone_baseline_local_5A rows",
            total_rows=baseline_local_df.height,
            frame=baseline_local_df,
        )

        class_baseline_df = (
            joined.group_by(
                [
                    "manifest_fingerprint",
                    "parameter_hash",
                    "scenario_id",
                    "demand_class",
                    "legal_country_iso",
                    "tzid",
                    "channel_group",
                    "bucket_index",
                ]
            ).agg(pl.col("lambda_local_base").sum().alias("lambda_local_base_class"))
            .with_columns(pl.lit(S3_SPEC_VERSION).alias("s3_spec_version"))
            .sort(["demand_class", "legal_country_iso", "tzid", "channel_group", "bucket_index"])
        )
        counts["class_baseline_rows"] = class_baseline_df.height
        _validate_array_rows(
            class_baseline_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/class_zone_baseline_local_5A",
            logger=logger,
            label="S3: validate class_zone_baseline_local_5A rows",
            total_rows=class_baseline_df.height,
            frame=class_baseline_df,
        )
        timer.info(
            "S3: phase output_schema_validation complete (baseline_rows=%s, class_rows=%s)",
            baseline_local_df.height,
            class_baseline_df.height,
        )

        current_phase = "output_write"
        baseline_entry = find_dataset_entry(dictionary_5a, "merchant_zone_baseline_local_5A").entry
        baseline_local_path = _resolve_dataset_path(baseline_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(baseline_local_path, baseline_local_df, logger, "merchant_zone_baseline_local_5A")

        class_entry = find_dataset_entry(dictionary_5a, "class_zone_baseline_local_5A").entry
        class_baseline_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(class_baseline_path, class_baseline_df, logger, "class_zone_baseline_local_5A")
        timer.info("S3: phase output_write complete")

        status = "PASS"
        timer.info("S3: completed baseline intensity synthesis")

    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "S3_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "S3_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint and run_paths is not None:
            try:
                run_report_entry = find_dataset_entry(dictionary_5a, "s3_run_report_5A").entry
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
                    "metrics": metrics,
                    "weekly_sum_error_violations_count": weekly_sum_error_violations,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "merchant_zone_baseline_local_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_zone_baseline_local_5A").entry,
                            tokens,
                        ),
                        "class_zone_baseline_local_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "class_zone_baseline_local_5A").entry,
                            tokens,
                        ),
                        "merchant_zone_baseline_utc_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_zone_baseline_utc_5A").entry,
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
                logger.info("S3: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S3: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "S3_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if baseline_local_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "S3_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S3Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        baseline_local_path=baseline_local_path,
        class_baseline_path=class_baseline_path,
        baseline_utc_path=baseline_utc_path,
        run_report_path=run_report_path,
    )
