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
    }
    metrics: dict[str, Optional[float]] = {
        "lambda_local_base_min": None,
        "lambda_local_base_median": None,
        "lambda_local_base_p95": None,
        "lambda_local_base_max": None,
        "weekly_sum_relative_error_max": None,
        "weekly_sum_relative_error_p95": None,
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
        profile_df = pl.read_parquet(
            profile_path,
            columns=[
                "manifest_fingerprint",
                "parameter_hash",
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "demand_class",
                "weekly_volume_expected",
                "scale_factor",
            ],
        )
        _validate_array_rows(
            profile_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/merchant_zone_profile_5A",
            logger=logger,
            label="S3: validate merchant_zone_profile_5A rows",
            total_rows=profile_df.height,
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
        shape_df = shape_df.filter(pl.col("channel_group") == "mixed")
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

        if baseline_policy.get("utc_projection", {}).get("emit_utc_baseline"):
            _abort(
                "S3_REQUIRED_POLICY_MISSING",
                "V-07",
                "utc_baseline_not_supported",
                {"detail": "emit_utc_baseline is true but UTC projection is not implemented."},
                manifest_fingerprint,
            )

        profile_df = profile_df.with_columns(pl.lit("mixed").alias("channel_group"))
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
        )

        current_phase = "output_write"
        baseline_entry = find_dataset_entry(dictionary_5a, "merchant_zone_baseline_local_5A").entry
        baseline_local_path = _resolve_dataset_path(baseline_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(baseline_local_path, baseline_local_df, logger, "merchant_zone_baseline_local_5A")

        class_entry = find_dataset_entry(dictionary_5a, "class_zone_baseline_local_5A").entry
        class_baseline_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(class_baseline_path, class_baseline_df, logger, "class_zone_baseline_local_5A")

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
