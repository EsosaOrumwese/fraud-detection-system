"""S4 calendar & scenario overlays runner for Segment 5A."""

from __future__ import annotations

import gc
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

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


MODULE_NAME = "5A.s4_calendar_overlays"
SEGMENT = "5A"
STATE = "S4"
S4_SPEC_VERSION = "1.0.0"
FAST_ROW_VALIDATION_ANCHORS = {
    "model/merchant_zone_profile_5A",
    "model/shape_grid_definition_5A",
    "model/merchant_zone_baseline_local_5A",
    "scenario/scenario_calendar_5A",
}
ROW_INDEX_COL = "__row_index"
OVERLAY_AFFECTED_EPS = 1.0e-9
OVERLAY_FAIRNESS_RATIO_TARGET = 1.6
OVERLAY_FAIRNESS_FLOOR_MIN = 0.02
OVERLAY_FAIRNESS_FLOOR_MAX = 0.30
OVERLAY_FAIRNESS_DELTA = 5.0e-4


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    scenario_local_path: Path
    overlay_factors_path: Optional[Path]
    scenario_utc_path: Optional[Path]
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
    def __init__(self, total: int, logger, label: str, min_interval_seconds: float = 5.0) -> None:
        self._total = max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0
        self._min_interval = float(min_interval_seconds)

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < self._min_interval and self._processed < self._total:
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
    logger = get_logger("engine.layers.l2.seg_5A.s4_calendar_overlays.runner")
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


def _env_flag(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _overlay_country_share_stats(
    overlay_df: pl.DataFrame,
    affected_eps: float,
) -> tuple[float, float, int]:
    if overlay_df.is_empty():
        return 0.0, 0.0, 0

    by_country = (
        overlay_df.with_columns(
            [
                (pl.col("lambda_local_base") * pl.col("overlay_factor_total")).alias("__lambda_scenario"),
                (
                    (pl.col("overlay_factor_total") - 1.0).abs() > affected_eps
                ).alias("__affected"),
            ]
        )
        .group_by("legal_country_iso")
        .agg(
            [
                pl.col("__lambda_scenario").sum().alias("total_vol"),
                (
                    pl.when(pl.col("__affected"))
                    .then(pl.col("__lambda_scenario"))
                    .otherwise(0.0)
                    .sum()
                ).alias("affected_vol"),
            ]
        )
        .filter(pl.col("total_vol") > 0.0)
        .with_columns((pl.col("affected_vol") / pl.col("total_vol")).alias("affected_share"))
    )
    if by_country.is_empty():
        return 0.0, 0.0, 0
    p10 = float(by_country.select(pl.col("affected_share").quantile(0.10)).item() or 0.0)
    p90 = float(by_country.select(pl.col("affected_share").quantile(0.90)).item() or 0.0)
    count = int(by_country.height)
    return p10, p90, count


def _apply_overlay_fairness_regularizer(
    overlay_df: pl.DataFrame,
    *,
    min_factor: float,
    max_factor: float,
) -> tuple[pl.DataFrame, dict[str, float | int | bool]]:
    diagnostics: dict[str, float | int | bool] = {
        "overlay_fairness_regularizer_enabled": False,
        "overlay_fairness_regularizer_target_ratio": float(OVERLAY_FAIRNESS_RATIO_TARGET),
        "overlay_fairness_regularizer_target_floor": 0.0,
        "overlay_fairness_regularizer_under_covered_countries": 0,
        "overlay_fairness_regularizer_adjusted_rows": 0,
        "overlay_fairness_regularizer_p10_before": 0.0,
        "overlay_fairness_regularizer_p90_before": 0.0,
        "overlay_fairness_regularizer_ratio_before": 0.0,
        "overlay_fairness_regularizer_p10_after": 0.0,
        "overlay_fairness_regularizer_p90_after": 0.0,
        "overlay_fairness_regularizer_ratio_after": 0.0,
    }
    if overlay_df.is_empty():
        return overlay_df, diagnostics

    p10_before, p90_before, country_count = _overlay_country_share_stats(overlay_df, OVERLAY_AFFECTED_EPS)
    ratio_before = float("inf") if p10_before <= OVERLAY_AFFECTED_EPS else float(p90_before / p10_before)
    diagnostics["overlay_fairness_regularizer_p10_before"] = p10_before
    diagnostics["overlay_fairness_regularizer_p90_before"] = p90_before
    diagnostics["overlay_fairness_regularizer_ratio_before"] = ratio_before
    if country_count < 2:
        diagnostics["overlay_fairness_regularizer_ratio_after"] = ratio_before
        diagnostics["overlay_fairness_regularizer_p10_after"] = p10_before
        diagnostics["overlay_fairness_regularizer_p90_after"] = p90_before
        return overlay_df, diagnostics

    target_floor = p90_before / OVERLAY_FAIRNESS_RATIO_TARGET if OVERLAY_FAIRNESS_RATIO_TARGET > 0 else p10_before
    target_floor = max(target_floor, OVERLAY_FAIRNESS_FLOOR_MIN)
    target_floor = min(target_floor, OVERLAY_FAIRNESS_FLOOR_MAX)
    diagnostics["overlay_fairness_regularizer_target_floor"] = float(target_floor)
    if p10_before >= target_floor - OVERLAY_AFFECTED_EPS:
        diagnostics["overlay_fairness_regularizer_ratio_after"] = ratio_before
        diagnostics["overlay_fairness_regularizer_p10_after"] = p10_before
        diagnostics["overlay_fairness_regularizer_p90_after"] = p90_before
        return overlay_df, diagnostics

    by_country_target = (
        overlay_df.with_columns(
            [
                (pl.col("lambda_local_base") * pl.col("overlay_factor_total")).alias("__lambda_scenario"),
                (
                    (pl.col("overlay_factor_total") - 1.0).abs() > OVERLAY_AFFECTED_EPS
                ).alias("__affected"),
            ]
        )
        .group_by("legal_country_iso")
        .agg(
            [
                pl.col("__lambda_scenario").sum().alias("total_vol"),
                (
                    pl.when(pl.col("__affected"))
                    .then(pl.col("__lambda_scenario"))
                    .otherwise(0.0)
                    .sum()
                ).alias("affected_vol"),
            ]
        )
        .filter(pl.col("total_vol") > 0.0)
        .with_columns(
            [
                (pl.col("affected_vol") / pl.col("total_vol")).alias("affected_share"),
                ((pl.lit(float(target_floor)) * pl.col("total_vol")) - pl.col("affected_vol"))
                .clip(lower_bound=0.0)
                .alias("needed_vol"),
            ]
        )
        .filter(pl.col("needed_vol") > OVERLAY_AFFECTED_EPS)
        .select(["legal_country_iso", "needed_vol"])
    )
    if by_country_target.is_empty():
        diagnostics["overlay_fairness_regularizer_ratio_after"] = ratio_before
        diagnostics["overlay_fairness_regularizer_p10_after"] = p10_before
        diagnostics["overlay_fairness_regularizer_p90_after"] = p90_before
        return overlay_df, diagnostics
    diagnostics["overlay_fairness_regularizer_under_covered_countries"] = int(by_country_target.height)

    neutral_candidates = (
        overlay_df.filter((pl.col("overlay_factor_total") - 1.0).abs() <= OVERLAY_AFFECTED_EPS)
        .join(by_country_target, on="legal_country_iso", how="inner")
        .with_columns((pl.col("lambda_local_base") * pl.col("overlay_factor_total")).alias("__lambda_scenario"))
    )
    if neutral_candidates.is_empty():
        diagnostics["overlay_fairness_regularizer_ratio_after"] = ratio_before
        diagnostics["overlay_fairness_regularizer_p10_after"] = p10_before
        diagnostics["overlay_fairness_regularizer_p90_after"] = p90_before
        return overlay_df, diagnostics

    neutral_candidates = (
        neutral_candidates.with_columns(
            pl.concat_str(
                [
                    pl.col("merchant_id").cast(pl.Utf8),
                    pl.col("tzid"),
                    pl.col("local_horizon_bucket_index").cast(pl.Utf8),
                ],
                separator="|",
            )
            .hash()
            .alias("__order_key")
        )
        .sort(
            [
                "legal_country_iso",
                "__order_key",
                "merchant_id",
                "tzid",
                "local_horizon_bucket_index",
            ]
        )
        .with_columns(
            [
                pl.col("__lambda_scenario").cum_sum().over("legal_country_iso").alias("__cum_vol"),
            ]
        )
        .with_columns((pl.col("__cum_vol") - pl.col("__lambda_scenario")).alias("__cum_prev"))
        .with_columns(
            [
                (
                    (pl.col("__cum_vol") <= pl.col("needed_vol"))
                    | (
                        (pl.col("__cum_prev") < pl.col("needed_vol"))
                        & (pl.col("__cum_vol") > pl.col("needed_vol"))
                    )
                ).alias("__selected"),
            ]
        )
    )

    selected_rows = neutral_candidates.filter(pl.col("__selected")).select(
        ["row_id", "local_horizon_bucket_index", "merchant_id"]
    )
    if selected_rows.is_empty():
        diagnostics["overlay_fairness_regularizer_ratio_after"] = ratio_before
        diagnostics["overlay_fairness_regularizer_p10_after"] = p10_before
        diagnostics["overlay_fairness_regularizer_p90_after"] = p90_before
        return overlay_df, diagnostics

    adjustments = (
        selected_rows.with_columns(
            pl.when(
                (
                    pl.concat_str(
                        [
                            pl.col("merchant_id").cast(pl.Utf8),
                            pl.col("local_horizon_bucket_index").cast(pl.Utf8),
                        ],
                        separator="|",
                    ).hash()
                    % 2
                )
                == 0
            )
            .then(pl.lit(1.0 + OVERLAY_FAIRNESS_DELTA))
            .otherwise(pl.lit(1.0 - OVERLAY_FAIRNESS_DELTA))
            .alias("__fair_mult")
        )
        .select(["row_id", "local_horizon_bucket_index", "__fair_mult"])
    )

    overlay_df = (
        overlay_df.join(adjustments, on=["row_id", "local_horizon_bucket_index"], how="left")
        .with_columns(
            (
                pl.col("overlay_factor_total") * pl.col("__fair_mult").fill_null(1.0)
            ).alias("overlay_factor_total")
        )
        .drop("__fair_mult")
    )
    if max_factor > 0:
        overlay_df = overlay_df.with_columns(
            pl.col("overlay_factor_total").clip(min_factor, max_factor).alias("overlay_factor_total")
        )

    diagnostics["overlay_fairness_regularizer_enabled"] = True
    diagnostics["overlay_fairness_regularizer_adjusted_rows"] = int(adjustments.height)

    p10_after, p90_after, _ = _overlay_country_share_stats(overlay_df, OVERLAY_AFFECTED_EPS)
    ratio_after = float("inf") if p10_after <= OVERLAY_AFFECTED_EPS else float(p90_after / p10_after)
    diagnostics["overlay_fairness_regularizer_p10_after"] = p10_after
    diagnostics["overlay_fairness_regularizer_p90_after"] = p90_after
    diagnostics["overlay_fairness_regularizer_ratio_after"] = ratio_after
    return overlay_df, diagnostics


def _schema_items(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    if schema.get("type") != "array":
        raise ContractError(f"Expected array schema at {anchor}, found {schema.get('type')}")
    items_schema = schema.get("items")
    if not isinstance(items_schema, dict):
        raise ContractError(f"Array schema missing items object at {anchor}")
    return items_schema


def _property_allows_null(schema: dict) -> bool:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return "null" in schema_type
    if isinstance(schema_type, str):
        return schema_type == "null"
    for key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(key)
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict) and _property_allows_null(option):
                    return True
    return False


def _validate_dataframe_fast(
    df: pl.DataFrame,
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    *,
    logger,
    label: str,
    sample_rows: int,
) -> None:
    items_schema = _schema_items(schema_pack, schema_layer1, schema_layer2, anchor)
    properties = items_schema.get("properties")
    if not isinstance(properties, dict):
        raise ContractError(f"Schema items missing properties at {anchor}")
    required = items_schema.get("required") or []
    if not isinstance(required, list):
        raise ContractError(f"Schema items required is not a list at {anchor}")
    required_set = {str(name) for name in required}
    columns = set(df.columns)
    missing = sorted(required_set - columns)
    if missing:
        raise SchemaValidationError(f"Missing required columns at {anchor}: {missing}", [])
    additional_props = items_schema.get("additionalProperties", True)
    extra = sorted(columns - set(properties.keys()))
    if extra and additional_props is False:
        raise SchemaValidationError(f"Unexpected columns at {anchor}: {extra}", [])

    for name, prop_schema in properties.items():
        if name not in columns or not isinstance(prop_schema, dict):
            continue
        if _property_allows_null(prop_schema):
            continue
        nulls = int(df.select(pl.col(name).null_count()).item())
        if nulls:
            raise SchemaValidationError(
                f"Non-nullable column {name} has {nulls} nulls at {anchor}",
                [],
            )

    sample_rows = max(int(sample_rows), 0)
    sample_rows = min(sample_rows, df.height)
    if sample_rows:
        sample_df = df.head(sample_rows)
        _validate_array_rows(
            sample_df.iter_rows(named=True),
            schema_pack,
            schema_layer1,
            schema_layer2,
            anchor,
            logger=logger,
            label=f"{label} sample",
            total_rows=sample_df.height,
            progress_min_rows=sample_rows + 1,
        )
    logger.info(
        "S4: %s schema validated (mode=fast sample_rows=%s total_rows=%s)",
        label,
        sample_rows,
        df.height,
    )


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
                "S4_OUTPUT_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(path), "label": label},
            )
        tmp_path.unlink()
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
        logger.info("S4: output already exists and is identical; skipping publish (%s).", label)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "S4_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(path), "label": label, "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info("S4: published %s to %s", label, path)
    return True


def _parse_rfc3339(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _scope_key(
    scope_global: bool,
    country_iso: Optional[str],
    tzid: Optional[str],
    demand_class: Optional[str],
    merchant_id: Optional[int],
) -> str:
    parts: list[str] = []
    if scope_global:
        parts.append("global=1")
    if country_iso:
        parts.append(f"country={country_iso}")
    if tzid:
        parts.append(f"tzid={tzid}")
    if demand_class:
        parts.append(f"class={demand_class}")
    if merchant_id is not None:
        parts.append(f"merchant={merchant_id}")
    if not parts:
        parts.append("global=0")
    return "|".join(parts)


def _scope_rank(
    scope_global: bool,
    country_iso: Optional[str],
    tzid: Optional[str],
    demand_class: Optional[str],
    merchant_id: Optional[int],
) -> int:
    if scope_global:
        return 0
    predicates = [value for value in (country_iso, tzid, demand_class, merchant_id) if value is not None]
    rank = len(predicates)
    if merchant_id is not None:
        rank += 10
    return rank


def _bucket_bounds(start: datetime, end: datetime, horizon_start: datetime, bucket_seconds: int) -> tuple[int, int]:
    start_offset = (start - horizon_start).total_seconds()
    end_offset = (end - horizon_start).total_seconds()
    start_idx = int(math.floor(start_offset / bucket_seconds))
    end_idx = int(math.ceil(end_offset / bucket_seconds))
    return start_idx, end_idx


def _ramp_factor(offset: int, duration: int, peak: float, ramp_in: int, ramp_out: int) -> float:
    if duration <= 0:
        return 1.0
    ramp_in = max(int(ramp_in), 0)
    ramp_out = max(int(ramp_out), 0)
    if ramp_in + ramp_out > duration:
        ramp_in = min(ramp_in, duration)
        ramp_out = max(min(ramp_out, duration - ramp_in), 0)
    plateau = max(duration - ramp_in - ramp_out, 0)
    if ramp_in > 0 and offset < ramp_in:
        return 1.0 + (peak - 1.0) * ((offset + 1) / ramp_in)
    if ramp_out > 0 and offset >= ramp_in + plateau:
        down_offset = offset - (ramp_in + plateau)
        return peak - (peak - 1.0) * ((down_offset + 1) / ramp_out)
    return peak

def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l2.seg_5A.s4_calendar_overlays.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)
    output_validate_full = _env_flag("ENGINE_S4_VALIDATE_FULL")
    output_sample_rows_env = os.environ.get("ENGINE_S4_VALIDATE_SAMPLE_ROWS", "5000")
    try:
        output_sample_rows = max(int(output_sample_rows_env), 0)
    except ValueError:
        output_sample_rows = 5000
    output_validation_mode = "full" if output_validate_full else "fast_sampled"
    current_phase = "init"
    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    run_paths: Optional[RunPaths] = None
    scenario_local_path: Optional[Path] = None
    overlay_factors_path: Optional[Path] = None
    scenario_utc_path: Optional[Path] = None
    run_report_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    scenario_id: Optional[str] = None
    seed: int = 0

    counts: dict[str, object] = {
        "domain_rows": 0,
        "horizon_buckets": 0,
        "event_rows": 0,
        "overlay_rows": 0,
        "scenario_rows": 0,
    }
    metrics: dict[str, Optional[float]] = {
        "overlay_factor_min": None,
        "overlay_factor_median": None,
        "overlay_factor_p95": None,
        "overlay_factor_max": None,
        "scenario_lambda_min": None,
        "scenario_lambda_median": None,
        "scenario_lambda_p95": None,
        "scenario_lambda_max": None,
    }
    warnings: dict[str, int] = {
        "overlay_warn_bounds_total": 0,
        "overlay_warn_aggregate": 0,
    }

    policy_versions: dict[str, Optional[str]] = {
        "scenario_horizon_config_version": None,
        "scenario_overlay_policy_version": None,
        "overlay_ordering_policy_version": None,
        "scenario_overlay_validation_policy_version": None,
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
        logger.info("S4: run log initialized at %s", run_log_path)

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
            "S4: objective=apply calendar/scenario overlays to baseline intensities "
            "(gate S0/S1/S2/S3 + overlay policies, output merchant_zone_scenario_local_5A)"
        )
        logger.info(
            "S4: story=overlay baselines gate_inputs=s0_gate_receipt_5A,sealed_inputs_5A,"
            "merchant_zone_profile_5A,shape_grid_definition_5A,merchant_zone_baseline_local_5A,"
            "scenario_calendar_5A outputs=merchant_zone_scenario_local_5A,merchant_zone_overlay_factors_5A"
        )
        logger.info(
            "S4: output schema validation mode=%s sample_rows=%s",
            output_validation_mode,
            output_sample_rows,
        )
        timer.info("S4: phase begin")

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
                "S4_GATE_OR_S3_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "S4_GATE_OR_S3_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_id_value = receipt_payload.get("scenario_id")
        if isinstance(scenario_id_value, list):
            if len(scenario_id_value) != 1:
                _abort(
                    "S4_GATE_OR_S3_INVALID",
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
                "S4_GATE_OR_S3_INVALID",
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
                    "S4_UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        if not isinstance(sealed_inputs, list):
            _abort(
                "S4_GATE_OR_S3_INVALID",
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
                "S4_GATE_OR_S3_INVALID",
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
                    "S4_GATE_OR_S3_INVALID",
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
                "S4_GATE_OR_S3_INVALID",
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
            "S4_REQUIRED_INPUT_MISSING",
        )
        if profile_row is None:
            logger.warning(
                "S4: sealed_inputs_5A missing merchant_zone_profile_5A; proceeding with direct path resolution"
            )
        grid_row = _resolve_sealed_row(
            sealed_by_id,
            "shape_grid_definition_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S4_REQUIRED_INPUT_MISSING",
        )
        if grid_row is None:
            logger.warning(
                "S4: sealed_inputs_5A missing shape_grid_definition_5A; proceeding with direct path resolution"
            )
        shape_row = _resolve_sealed_row(
            sealed_by_id,
            "class_zone_shape_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S4_REQUIRED_INPUT_MISSING",
        )
        if shape_row is None:
            logger.warning(
                "S4: sealed_inputs_5A missing class_zone_shape_5A; proceeding with direct path resolution"
            )
        baseline_row = _resolve_sealed_row(
            sealed_by_id,
            "merchant_zone_baseline_local_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S4_REQUIRED_INPUT_MISSING",
        )
        if baseline_row is None:
            logger.warning(
                "S4: sealed_inputs_5A missing merchant_zone_baseline_local_5A; proceeding with direct path resolution"
            )
        _resolve_sealed_row(
            sealed_by_id,
            "scenario_calendar_5A",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "S4_REQUIRED_INPUT_MISSING",
        )
        horizon_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_horizon_config_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S4_REQUIRED_POLICY_MISSING",
        )
        overlay_policy_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_overlay_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S4_REQUIRED_POLICY_MISSING",
        )
        ordering_row = _resolve_sealed_row(
            sealed_by_id,
            "overlay_ordering_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            False,
            "S4_REQUIRED_POLICY_MISSING",
        )
        validation_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_overlay_validation_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            False,
            "S4_REQUIRED_POLICY_MISSING",
        )
        metadata_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_metadata",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            False,
            "S4_REQUIRED_SCENARIO_MISSING",
        )

        current_phase = "policy_load"
        horizon_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "scenario_horizon_config_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        overlay_policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "scenario_overlay_policy_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        horizon_config = _load_yaml(horizon_path)
        overlay_policy = _load_yaml(overlay_policy_path)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "scenario/scenario_horizon_config_5A", horizon_config)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "scenario/scenario_overlay_policy_5A", overlay_policy)

        ordering_policy = None
        if ordering_row:
            ordering_path = _resolve_dataset_path(
                find_dataset_entry(dictionary_5a, "overlay_ordering_policy_5A").entry,
                run_paths,
                config.external_roots,
                tokens,
            )
            ordering_policy = _load_yaml(ordering_path)
            _validate_payload(schema_5a, schema_layer1, schema_layer2, "policy/overlay_ordering_policy_5A", ordering_policy)

        validation_policy = None
        if validation_row:
            validation_path = _resolve_dataset_path(
                find_dataset_entry(dictionary_5a, "scenario_overlay_validation_policy_5A").entry,
                run_paths,
                config.external_roots,
                tokens,
            )
            validation_policy = _load_yaml(validation_path)
            _validate_payload(
                schema_5a,
                schema_layer1,
                schema_layer2,
                "scenario/scenario_overlay_validation_policy_5A",
                validation_policy,
            )

        if metadata_row:
            metadata_path = _resolve_dataset_path(
                find_dataset_entry(dictionary_5a, "scenario_metadata").entry,
                run_paths,
                config.external_roots,
                tokens,
            )
            _validate_payload(schema_5a, schema_layer1, schema_layer2, "scenario/scenario_metadata", _load_yaml(metadata_path))

        policy_versions["scenario_horizon_config_version"] = str(horizon_config.get("version")) if isinstance(horizon_config, dict) else None
        policy_versions["scenario_overlay_policy_version"] = str(overlay_policy.get("version")) if isinstance(overlay_policy, dict) else None
        if ordering_policy:
            policy_versions["overlay_ordering_policy_version"] = str(ordering_policy.get("version"))
        if validation_policy:
            policy_versions["scenario_overlay_validation_policy_version"] = str(validation_policy.get("version"))

        scenario_cfg = None
        scenarios = horizon_config.get("scenarios") if isinstance(horizon_config, dict) else None
        if isinstance(scenarios, list):
            for scenario in scenarios:
                if isinstance(scenario, dict) and str(scenario.get("scenario_id")) == scenario_id:
                    scenario_cfg = scenario
                    break
        if not scenario_cfg:
            _abort(
                "S4_REQUIRED_SCENARIO_MISSING",
                "V-05",
                "scenario_not_in_horizon_config",
                {"scenario_id": scenario_id},
                manifest_fingerprint,
            )

        horizon_start = _parse_rfc3339(str(scenario_cfg.get("horizon_start_utc")))
        horizon_end = _parse_rfc3339(str(scenario_cfg.get("horizon_end_utc")))
        bucket_minutes = int(scenario_cfg.get("bucket_duration_minutes") or 0)
        emit_utc_intensities = bool(scenario_cfg.get("emit_utc_intensities"))
        if bucket_minutes <= 0:
            _abort(
                "S4_HORIZON_GRID_INVALID",
                "V-05",
                "bucket_duration_invalid",
                {"bucket_duration_minutes": bucket_minutes},
                manifest_fingerprint,
            )
        horizon_minutes = int((horizon_end - horizon_start).total_seconds() / 60)
        if horizon_minutes <= 0 or horizon_minutes % bucket_minutes != 0:
            _abort(
                "S4_HORIZON_GRID_INVALID",
                "V-05",
                "horizon_minutes_invalid",
                {
                    "horizon_minutes": horizon_minutes,
                    "bucket_duration_minutes": bucket_minutes,
                    "horizon_start_utc": scenario_cfg.get("horizon_start_utc"),
                    "horizon_end_utc": scenario_cfg.get("horizon_end_utc"),
                },
                manifest_fingerprint,
            )
        horizon_buckets = horizon_minutes // bucket_minutes
        counts["horizon_buckets"] = horizon_buckets
        bucket_seconds = bucket_minutes * 60

        current_phase = "input_load"
        profile_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "merchant_zone_profile_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        grid_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "shape_grid_definition_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        baseline_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "merchant_zone_baseline_local_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        calendar_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "scenario_calendar_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )

        profile_df = pl.read_parquet(profile_path)
        grid_df = pl.read_parquet(grid_path)
        baseline_df = pl.read_parquet(baseline_path)
        calendar_df = pl.read_parquet(calendar_path)

        _validate_array_rows(
            profile_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/merchant_zone_profile_5A",
            logger=logger,
            label="S4: validate merchant_zone_profile_5A rows",
            total_rows=profile_df.height,
            frame=profile_df,
        )
        _validate_array_rows(
            grid_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/shape_grid_definition_5A",
            logger=logger,
            label="S4: validate shape_grid_definition_5A rows",
            total_rows=grid_df.height,
            frame=grid_df,
        )
        _validate_array_rows(
            baseline_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/merchant_zone_baseline_local_5A",
            logger=logger,
            label="S4: validate merchant_zone_baseline_local_5A rows",
            total_rows=baseline_df.height,
            progress_min_rows=200000,
            frame=baseline_df,
        )
        _validate_array_rows(
            calendar_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "scenario/scenario_calendar_5A",
            logger=logger,
            label="S4: validate scenario_calendar_5A rows",
            total_rows=calendar_df.height,
            frame=calendar_df,
        )
        timer.info(
            "S4: phase input_load_schema_validation complete (profile_rows=%s, grid_rows=%s, baseline_rows=%s, calendar_rows=%s)",
            profile_df.height,
            grid_df.height,
            baseline_df.height,
            calendar_df.height,
        )

        current_phase = "domain_build"
        domain_df = (
            profile_df.select(
                ["merchant_id", "legal_country_iso", "tzid", "demand_class"]
            )
            .unique()
            .sort(["merchant_id", "legal_country_iso", "tzid"])
            .with_row_index("row_id")
        )
        counts["domain_rows"] = domain_df.height

        baseline_ids = baseline_df.select(
            ["merchant_id", "legal_country_iso", "tzid"]
        ).unique()
        if baseline_ids.height != domain_df.height:
            _abort(
                "S4_DOMAIN_ALIGNMENT_FAILED",
                "V-06",
                "domain_size_mismatch",
                {"domain_rows": domain_df.height, "baseline_zone_rows": baseline_ids.height},
                manifest_fingerprint,
            )

        baseline_df = baseline_df.join(
            domain_df.select(
                ["merchant_id", "legal_country_iso", "tzid", "demand_class", "row_id"]
            ),
            on=["merchant_id", "legal_country_iso", "tzid"],
            how="left",
        )
        if baseline_df.filter(pl.col("row_id").is_null()).height:
            _abort(
                "S4_DOMAIN_ALIGNMENT_FAILED",
                "V-06",
                "baseline_domain_missing",
                {"detail": "baseline rows missing from merchant_zone_profile_5A"},
                manifest_fingerprint,
            )

        manifest_vals = baseline_df.get_column("manifest_fingerprint").unique().to_list()
        if any(str(val) != str(manifest_fingerprint) for val in manifest_vals):
            _abort(
                "S4_GATE_OR_S3_INVALID",
                "V-06",
                "manifest_fingerprint_mismatch_in_baseline",
                {"expected": manifest_fingerprint, "found": manifest_vals},
                manifest_fingerprint,
            )
        parameter_vals = baseline_df.get_column("parameter_hash").unique().to_list()
        if any(str(val) != str(parameter_hash) for val in parameter_vals):
            _abort(
                "S4_GATE_OR_S3_INVALID",
                "V-06",
                "parameter_hash_mismatch_in_baseline",
                {"expected": parameter_hash, "found": parameter_vals},
                manifest_fingerprint,
            )
        scenario_vals = baseline_df.get_column("scenario_id").unique().to_list()
        if any(str(val) != str(scenario_id) for val in scenario_vals):
            _abort(
                "S4_GATE_OR_S3_INVALID",
                "V-06",
                "scenario_id_mismatch_in_baseline",
                {"expected": scenario_id, "found": scenario_vals},
                manifest_fingerprint,
            )

        grid_bucket_minutes = grid_df.get_column("bucket_duration_minutes").unique().to_list()
        if len(grid_bucket_minutes) != 1 or int(grid_bucket_minutes[0]) != bucket_minutes:
            _abort(
                "S4_HORIZON_GRID_INVALID",
                "V-06",
                "grid_bucket_duration_mismatch",
                {"grid_bucket_minutes": grid_bucket_minutes, "horizon_bucket_minutes": bucket_minutes},
                manifest_fingerprint,
            )

        current_phase = "grid_mapping"
        grid_pairs = grid_df.select(
            ["bucket_index", "local_day_of_week", "local_minutes_since_midnight"]
        ).to_dicts()
        grid_lookup: dict[tuple[int, int], int] = {}
        for row in grid_pairs:
            key = (int(row["local_day_of_week"]), int(row["local_minutes_since_midnight"]))
            if key in grid_lookup:
                _abort(
                    "S4_HORIZON_GRID_INVALID",
                    "V-06",
                    "grid_lookup_duplicate",
                    {"key": key},
                    manifest_fingerprint,
                )
            grid_lookup[key] = int(row["bucket_index"])

        tzids = domain_df.get_column("tzid").unique().to_list()
        horizon_map_rows: list[dict] = []
        total_map = len(tzids) * horizon_buckets
        tracker = _ProgressTracker(total_map, logger, "S4: build horizon->week mapping")
        for tzid in tzids:
            tz = ZoneInfo(str(tzid))
            for idx in range(horizon_buckets):
                tracker.update(1)
                utc_ts = horizon_start + timedelta(minutes=idx * bucket_minutes)
                local_ts = utc_ts.astimezone(tz)
                local_minutes = local_ts.hour * 60 + local_ts.minute
                local_minutes = (local_minutes // bucket_minutes) * bucket_minutes
                key = (local_ts.isoweekday(), local_minutes)
                bucket_index = grid_lookup.get(key)
                if bucket_index is None:
                    _abort(
                        "S4_HORIZON_GRID_INVALID",
                        "V-06",
                        "grid_lookup_missing",
                        {"tzid": tzid, "local_day_of_week": key[0], "local_minutes": key[1]},
                        manifest_fingerprint,
                    )
                horizon_map_rows.append(
                    {
                        "tzid": tzid,
                        "local_horizon_bucket_index": idx,
                        "bucket_index": bucket_index,
                    }
                )
        horizon_map_df = pl.DataFrame(horizon_map_rows)
        logger.info(
            "S4: horizon mapping built (tzids=%s horizon_buckets=%s rows=%s)",
            len(tzids),
            horizon_buckets,
            horizon_map_df.height,
        )

        current_phase = "baseline_projection"
        baseline_horizon_df = (
            baseline_df.select(["row_id", "tzid", "bucket_index", "lambda_local_base"])
            .join(horizon_map_df, on=["tzid", "bucket_index"], how="left")
            .select(["row_id", "local_horizon_bucket_index", "lambda_local_base"])
        )
        if baseline_horizon_df.filter(pl.col("local_horizon_bucket_index").is_null()).height:
            _abort(
                "S4_HORIZON_GRID_INVALID",
                "V-06",
                "baseline_horizon_mapping_failed",
                {"detail": "missing local_horizon_bucket_index after join"},
                manifest_fingerprint,
            )
        logger.info(
            "S4: baseline projected to horizon (rows=%s, buckets=%s)",
            baseline_horizon_df.height,
            horizon_buckets,
        )
        timer.info(
            "S4: phase domain_horizon_mapping complete (domain_rows=%s, horizon_rows=%s, projected_rows=%s)",
            domain_df.height,
            horizon_map_df.height,
            baseline_horizon_df.height,
        )
        del baseline_df
        del horizon_map_df
        gc.collect()

        current_phase = "calendar_validation"
        overlay_event_types = overlay_policy.get("event_types") if isinstance(overlay_policy, dict) else None
        if not isinstance(overlay_event_types, dict):
            _abort(
                "S4_REQUIRED_POLICY_MISSING",
                "V-07",
                "overlay_policy_event_types_missing",
                {"detail": "overlay_policy.event_types missing or invalid"},
                manifest_fingerprint,
            )
        calendar_validation = overlay_policy.get("calendar_validation") if isinstance(overlay_policy, dict) else {}
        require_type_vocab = bool(calendar_validation.get("require_event_type_in_vocab", True))
        require_scope_valid = bool(calendar_validation.get("require_scope_valid", True))
        require_time_within = bool(calendar_validation.get("require_time_within_horizon", True))
        disallow_empty_scope = bool(calendar_validation.get("disallow_empty_scope", True))
        max_events = int(calendar_validation.get("max_events_per_scenario") or 0)
        max_overlap = int(calendar_validation.get("max_overlap_events_per_row_bucket") or 0)

        event_rows = calendar_df.to_dicts()
        if max_events and len(event_rows) > max_events:
            _abort(
                "S4_CALENDAR_ALIGNMENT_FAILED",
                "V-07",
                "calendar_event_count_exceeds_max",
                {"events": len(event_rows), "max_events": max_events},
                manifest_fingerprint,
            )

        overlay_shape_kinds = overlay_policy.get("shape_kinds") if isinstance(overlay_policy, dict) else {}
        scope_rules = overlay_policy.get("scope_rules") if isinstance(overlay_policy, dict) else {}
        allowed_scope_kinds = set(scope_rules.get("allowed_scope_kinds") or [])
        scope_rule_flags = scope_rules.get("rules") if isinstance(scope_rules, dict) else {}

        current_phase = "event_expansion"
        expanded_rows: list[dict] = []
        total_buckets = 0
        for event in event_rows:
            start_utc = _parse_rfc3339(str(event.get("start_utc")))
            end_utc = _parse_rfc3339(str(event.get("end_utc")))
            start_idx, end_idx = _bucket_bounds(start_utc, end_utc, horizon_start, bucket_seconds)
            if require_time_within and (start_idx < 0 or end_idx > horizon_buckets):
                _abort(
                    "S4_CALENDAR_ALIGNMENT_FAILED",
                    "V-07",
                    "event_outside_horizon",
                    {"event_id": event.get("event_id")},
                    manifest_fingerprint,
                )
            start_idx = max(start_idx, 0)
            end_idx = min(end_idx, horizon_buckets)
            if end_idx <= start_idx:
                continue
            total_buckets += end_idx - start_idx

        tracker = _ProgressTracker(total_buckets, logger, "S4: expand scenario_calendar events")
        predicate_sets: set[tuple[str, ...]] = set()
        event_type_counts: dict[str, int] = {}
        for event in event_rows:
            event_type = str(event.get("event_type") or "")
            if require_type_vocab and event_type not in overlay_event_types:
                _abort(
                    "S4_CALENDAR_ALIGNMENT_FAILED",
                    "V-07",
                    "event_type_unknown",
                    {"event_type": event_type},
                    manifest_fingerprint,
                )
            event_def = overlay_event_types.get(event_type) if isinstance(overlay_event_types, dict) else None
            if not isinstance(event_def, dict):
                _abort(
                    "S4_CALENDAR_ALIGNMENT_FAILED",
                    "V-07",
                    "event_type_missing_def",
                    {"event_type": event_type},
                    manifest_fingerprint,
                )

            scope_global = bool(event.get("scope_global"))
            country_iso = event.get("country_iso")
            tzid = event.get("tzid")
            demand_class = event.get("demand_class")
            merchant_id = event.get("merchant_id")

            predicate_fields = []
            if country_iso is not None:
                predicate_fields.append("country_iso")
            if tzid is not None:
                predicate_fields.append("tzid")
            if demand_class is not None:
                predicate_fields.append("demand_class")
            if merchant_id is not None:
                predicate_fields.append("merchant_id")
            predicate_key = tuple(predicate_fields)
            if scope_global:
                predicate_key = tuple()

            if require_scope_valid:
                if scope_global and scope_rule_flags.get("global_cannot_combine", False):
                    if predicate_fields:
                        _abort(
                            "S4_CALENDAR_ALIGNMENT_FAILED",
                            "V-07",
                            "global_scope_combined",
                            {"event_id": event.get("event_id")},
                            manifest_fingerprint,
                        )
                if not scope_global:
                    if scope_rule_flags.get("require_at_least_one_predicate", False) and not predicate_fields:
                        _abort(
                            "S4_CALENDAR_ALIGNMENT_FAILED",
                            "V-07",
                            "event_scope_empty",
                            {"event_id": event.get("event_id")},
                            manifest_fingerprint,
                        )
                    if (
                        scope_rule_flags.get("merchant_scope_is_exclusive", False)
                        and merchant_id is not None
                        and (country_iso is not None or tzid is not None or demand_class is not None)
                    ):
                        _abort(
                            "S4_CALENDAR_ALIGNMENT_FAILED",
                            "V-07",
                            "merchant_scope_exclusive",
                            {"event_id": event.get("event_id")},
                            manifest_fingerprint,
                        )
                if allowed_scope_kinds:
                    if scope_global and "global" not in allowed_scope_kinds:
                        _abort(
                            "S4_CALENDAR_ALIGNMENT_FAILED",
                            "V-07",
                            "global_scope_not_allowed",
                            {"event_id": event.get("event_id")},
                            manifest_fingerprint,
                        )
                    for field in predicate_fields:
                        kind = "merchant" if field == "merchant_id" else field.replace("_iso", "")
                        if kind not in allowed_scope_kinds:
                            _abort(
                                "S4_CALENDAR_ALIGNMENT_FAILED",
                                "V-07",
                                "scope_kind_not_allowed",
                                {"event_id": event.get("event_id"), "scope_kind": kind},
                                manifest_fingerprint,
                            )

                allowed_event_scopes = set(event_def.get("allowed_scope_kinds") or [])
                if allowed_event_scopes:
                    if scope_global and "global" not in allowed_event_scopes:
                        _abort(
                            "S4_CALENDAR_ALIGNMENT_FAILED",
                            "V-07",
                            "event_scope_not_allowed",
                            {"event_id": event.get("event_id"), "event_type": event_type},
                            manifest_fingerprint,
                        )
                    for field in predicate_fields:
                        kind = "merchant" if field == "merchant_id" else field.replace("_iso", "")
                        if kind not in allowed_event_scopes:
                            _abort(
                                "S4_CALENDAR_ALIGNMENT_FAILED",
                                "V-07",
                                "event_scope_kind_not_allowed",
                                {"event_id": event.get("event_id"), "event_type": event_type, "scope_kind": kind},
                                manifest_fingerprint,
                            )

            if disallow_empty_scope and not scope_global and not predicate_fields:
                _abort(
                    "S4_CALENDAR_ALIGNMENT_FAILED",
                    "V-07",
                    "event_scope_empty",
                    {"event_id": event.get("event_id")},
                    manifest_fingerprint,
                )

            shape_kind = str(event.get("shape_kind") or "")
            if shape_kind not in overlay_shape_kinds:
                _abort(
                    "S4_OVERLAY_EVAL_FAILED",
                    "V-07",
                    "shape_kind_invalid",
                    {"event_id": event.get("event_id"), "shape_kind": shape_kind},
                    manifest_fingerprint,
                )
            shape_def = overlay_shape_kinds.get(shape_kind) if isinstance(overlay_shape_kinds, dict) else {}
            amplitude = event.get("amplitude")
            amplitude_peak = event.get("amplitude_peak")
            if shape_kind == "constant":
                if amplitude is None:
                    amplitude = event_def.get("default_amplitude")
                if amplitude is None:
                    _abort(
                        "S4_OVERLAY_EVAL_FAILED",
                        "V-07",
                        "constant_amplitude_missing",
                        {"event_id": event.get("event_id")},
                        manifest_fingerprint,
                    )
                min_amp = float(shape_def.get("amplitude_min") or 0)
                max_amp = float(shape_def.get("amplitude_max") or 0)
                if not (min_amp <= float(amplitude) <= max_amp):
                    _abort(
                        "S4_OVERLAY_EVAL_FAILED",
                        "V-07",
                        "constant_amplitude_out_of_bounds",
                        {"event_id": event.get("event_id"), "amplitude": amplitude},
                        manifest_fingerprint,
                    )
            else:
                if amplitude_peak is None:
                    amplitude_peak = event_def.get("default_amplitude")
                if amplitude_peak is None:
                    _abort(
                        "S4_OVERLAY_EVAL_FAILED",
                        "V-07",
                        "ramp_peak_missing",
                        {"event_id": event.get("event_id")},
                        manifest_fingerprint,
                    )
                peak_min = float(shape_def.get("amplitude_peak_min") or 0)
                peak_max = float(shape_def.get("amplitude_peak_max") or 0)
                if not (peak_min <= float(amplitude_peak) <= peak_max):
                    _abort(
                        "S4_OVERLAY_EVAL_FAILED",
                        "V-07",
                        "ramp_peak_out_of_bounds",
                        {"event_id": event.get("event_id"), "amplitude_peak": amplitude_peak},
                        manifest_fingerprint,
                    )
                ramp_in = int(event.get("ramp_in_buckets") or 0)
                ramp_out = int(event.get("ramp_out_buckets") or 0)
                if ramp_in < 0 or ramp_out < 0:
                    _abort(
                        "S4_OVERLAY_EVAL_FAILED",
                        "V-07",
                        "ramp_buckets_invalid",
                        {"event_id": event.get("event_id"), "ramp_in": ramp_in, "ramp_out": ramp_out},
                        manifest_fingerprint,
                    )
                ramp_in_max = int(shape_def.get("ramp_in_buckets_max") or ramp_in)
                ramp_out_max = int(shape_def.get("ramp_out_buckets_max") or ramp_out)
                if ramp_in > ramp_in_max or ramp_out > ramp_out_max:
                    _abort(
                        "S4_OVERLAY_EVAL_FAILED",
                        "V-07",
                        "ramp_buckets_exceed_max",
                        {"event_id": event.get("event_id"), "ramp_in": ramp_in, "ramp_out": ramp_out},
                        manifest_fingerprint,
                    )

            start_utc = _parse_rfc3339(str(event.get("start_utc")))
            end_utc = _parse_rfc3339(str(event.get("end_utc")))
            start_idx, end_idx = _bucket_bounds(start_utc, end_utc, horizon_start, bucket_seconds)
            if require_time_within and (start_idx < 0 or end_idx > horizon_buckets):
                _abort(
                    "S4_CALENDAR_ALIGNMENT_FAILED",
                    "V-07",
                    "event_outside_horizon",
                    {"event_id": event.get("event_id")},
                    manifest_fingerprint,
                )
            start_idx = max(start_idx, 0)
            end_idx = min(end_idx, horizon_buckets)
            if end_idx <= start_idx:
                continue

            scope_key = _scope_key(scope_global, country_iso, tzid, demand_class, merchant_id)
            specificity_rank = _scope_rank(scope_global, country_iso, tzid, demand_class, merchant_id)
            predicate_sets.add(predicate_key)
            predicate_label = "|".join(predicate_key) if predicate_key else "__global__"
            duration = end_idx - start_idx
            for offset in range(duration):
                tracker.update(1)
                if shape_kind == "constant":
                    factor = float(amplitude)
                else:
                    factor = _ramp_factor(offset, duration, float(amplitude_peak), int(event.get("ramp_in_buckets") or 0), int(event.get("ramp_out_buckets") or 0))
                expanded_rows.append(
                    {
                        "event_type": event_type,
                        "local_horizon_bucket_index": start_idx + offset,
                        "factor": factor,
                        "scope_key": scope_key,
                        "predicate_label": predicate_label,
                        "specificity_rank": specificity_rank,
                    }
                )
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

        counts["event_rows"] = len(event_rows)
        if max_overlap and expanded_rows:
            overlap_df = (
                pl.DataFrame(expanded_rows)
                .group_by(["scope_key", "local_horizon_bucket_index"])
                .len()
                .with_columns(pl.col("len").alias("overlap_count"))
            )
            max_seen = int(overlap_df.get_column("overlap_count").max()) if overlap_df.height else 0
            if max_seen > max_overlap:
                _abort(
                    "S4_CALENDAR_ALIGNMENT_FAILED",
                    "V-07",
                    "event_overlap_exceeds_max",
                    {"max_seen": max_seen, "max_allowed": max_overlap},
                    manifest_fingerprint,
                )
            logger.info(
                "S4: scenario calendar expanded (events=%s expanded_rows=%s max_overlap=%s)",
                len(event_rows),
                len(expanded_rows),
                max_seen,
            )
        else:
            logger.info(
                "S4: scenario calendar expanded (events=%s expanded_rows=%s)",
                len(event_rows),
                len(expanded_rows),
            )

        current_phase = "overlay_aggregation"
        overlay_df = baseline_horizon_df
        del baseline_horizon_df
        gc.collect()

        if expanded_rows:
            events_expanded_df = pl.DataFrame(expanded_rows)
            predicate_list = sorted(predicate_sets, key=lambda item: (len(item), item))
            total_keys = domain_df.height * max(len(predicate_list), 1)
            key_tracker = _ProgressTracker(total_keys, logger, "S4: build scope keys for domain")
            domain_scope_maps: dict[str, pl.DataFrame] = {}
            for predicate_key in predicate_list:
                predicate_label = "|".join(predicate_key) if predicate_key else "__global__"
                scope_rows: list[dict] = []
                for row in domain_df.iter_rows(named=True):
                    key_tracker.update(1)
                    if not predicate_key:
                        scope_key = _scope_key(True, None, None, None, None)
                    else:
                        scope_key = _scope_key(
                            False,
                            row.get("legal_country_iso") if "country_iso" in predicate_key else None,
                            row.get("tzid") if "tzid" in predicate_key else None,
                            row.get("demand_class") if "demand_class" in predicate_key else None,
                            row.get("merchant_id") if "merchant_id" in predicate_key else None,
                        )
                    scope_rows.append({"row_id": row["row_id"], "scope_key": scope_key})
                domain_scope_maps[predicate_label] = pl.DataFrame(scope_rows)
            event_types = sorted(event_type_counts.keys())

            for event_type in event_types:
                within_policy = None
                if ordering_policy:
                    within_policy = (ordering_policy.get("within_type_aggregation") or {}).get(event_type)
                selection = "ALL"
                mode = "MAX"
                if isinstance(within_policy, dict):
                    selection = str(within_policy.get("selection") or selection)
                    mode = str(within_policy.get("mode") or mode)

                agg_expr = pl.col("factor").min() if mode == "MIN" else pl.col("factor").max()
                lane_frames: list[pl.DataFrame] = []
                for predicate_key in predicate_list:
                    predicate_label = "|".join(predicate_key) if predicate_key else "__global__"
                    lane_grouped = (
                        events_expanded_df.lazy()
                        .filter(
                            (pl.col("event_type") == pl.lit(event_type))
                            & (pl.col("predicate_label") == pl.lit(predicate_label))
                        )
                        .group_by(["scope_key", "local_horizon_bucket_index", "specificity_rank"])
                        .agg(agg_expr.alias("factor"))
                        .collect(streaming=True)
                    )
                    if lane_grouped.is_empty():
                        continue
                    lane_rows = lane_grouped.join(domain_scope_maps[predicate_label], on="scope_key", how="inner")
                    if lane_rows.is_empty():
                        continue
                    lane_frames.append(
                        lane_rows.select(
                            ["row_id", "local_horizon_bucket_index", "specificity_rank", "factor"]
                        )
                    )
                if not lane_frames:
                    continue
                grouped = pl.concat(lane_frames, how="vertical_relaxed")
                if selection == "MOST_SPECIFIC_ONLY":
                    max_rank = grouped.group_by(["row_id", "local_horizon_bucket_index"]).agg(
                        pl.col("specificity_rank").max().alias("max_rank")
                    )
                    grouped = grouped.join(
                        max_rank, on=["row_id", "local_horizon_bucket_index"], how="inner"
                    ).filter(pl.col("specificity_rank") == pl.col("max_rank"))
                grouped = grouped.group_by(["row_id", "local_horizon_bucket_index"]).agg(
                    agg_expr.alias("factor")
                )

                factor_col = f"factor_{event_type.lower()}"
                active_col = f"active_{event_type.lower()}"
                grouped = grouped.select(
                    ["row_id", "local_horizon_bucket_index", pl.col("factor").alias(factor_col)]
                )
                overlay_df = overlay_df.join(grouped, on=["row_id", "local_horizon_bucket_index"], how="left")
                overlay_df = overlay_df.with_columns(
                    [
                        pl.col(factor_col).is_not_null().alias(active_col),
                        pl.col(factor_col).fill_null(1.0),
                    ]
                )
                del grouped
                gc.collect()
            domain_scope_maps.clear()
            del events_expanded_df
            gc.collect()
        else:
            logger.info("S4: no scenario events; overlay factors default to 1.0")
        event_types_for_product = sorted(event_type_counts.keys())
        for event_type in event_types_for_product:
            factor_col = f"factor_{event_type.lower()}"
            active_col = f"active_{event_type.lower()}"
            if factor_col not in overlay_df.columns:
                overlay_df = overlay_df.with_columns(
                    [
                        pl.lit(1.0).alias(factor_col),
                        pl.lit(False).alias(active_col),
                    ]
                )

        if ordering_policy and event_types_for_product:
            masking_rules = ordering_policy.get("masking_rules") or []
            for rule in masking_rules:
                when_types = rule.get("when_active_types") or []
                if not when_types:
                    continue
                when_cols = [pl.col(f"active_{str(t).lower()}") for t in when_types if f"active_{str(t).lower()}" in overlay_df.columns]
                if not when_cols:
                    continue
                active_any = pl.any_horizontal(when_cols)
                for apply_rule in rule.get("apply") or []:
                    target_types = apply_rule.get("target_types") or []
                    operator = str(apply_rule.get("operator") or "")
                    for target in target_types:
                        factor_col = f"factor_{str(target).lower()}"
                        if factor_col not in overlay_df.columns:
                            continue
                        if operator == "NEUTRALIZE":
                            overlay_df = overlay_df.with_columns(
                                pl.when(active_any).then(pl.lit(1.0)).otherwise(pl.col(factor_col)).alias(factor_col)
                            )
                        elif operator == "CAP_AT_ONE":
                            overlay_df = overlay_df.with_columns(
                                pl.when(active_any)
                                .then(pl.min_horizontal(pl.col(factor_col), pl.lit(1.0)))
                                .otherwise(pl.col(factor_col))
                                .alias(factor_col)
                            )
                        elif operator == "FLOOR_AT_ONE":
                            overlay_df = overlay_df.with_columns(
                                pl.when(active_any)
                                .then(pl.max_horizontal(pl.col(factor_col), pl.lit(1.0)))
                                .otherwise(pl.col(factor_col))
                                .alias(factor_col)
                            )

        factor_exprs = [pl.col(f"factor_{event_type.lower()}") for event_type in event_types_for_product]
        if factor_exprs:
            overlay_df = overlay_df.with_columns(
                pl.fold(pl.lit(1.0), lambda acc, x: acc * x, factor_exprs).alias("overlay_factor_total")
            )
        else:
            overlay_df = overlay_df.with_columns(pl.lit(1.0).alias("overlay_factor_total"))

        combination = overlay_policy.get("combination") if isinstance(overlay_policy, dict) else {}
        min_factor = float(combination.get("min_factor") or 0.0)
        max_factor = float(combination.get("max_factor") or 0.0)
        clamp_after = bool(combination.get("apply_clamp_after_product", True))
        if clamp_after and max_factor > 0:
            overlay_df = overlay_df.with_columns(
                pl.col("overlay_factor_total").clip(min_factor, max_factor).alias("overlay_factor_total")
            )

        domain_join_cols = ["row_id", "merchant_id", "legal_country_iso", "tzid"]
        if "channel_group" in domain_df.columns:
            domain_join_cols.append("channel_group")
        overlay_df = overlay_df.join(domain_df.select(domain_join_cols), on="row_id", how="left")
        missing_domain = overlay_df.filter(pl.col("merchant_id").is_null()).height
        if missing_domain:
            _abort(
                "S4_DOMAIN_ALIGNMENT_FAILED",
                "V-08",
                "overlay_domain_join_missing",
                {"missing_rows": missing_domain},
                manifest_fingerprint,
            )
        del domain_df
        gc.collect()

        overlay_df, fairness_diag = _apply_overlay_fairness_regularizer(
            overlay_df,
            min_factor=min_factor,
            max_factor=max_factor,
        )
        metrics.update(fairness_diag)
        logger.info(
            "S4: overlay fairness regularizer enabled=%s adjusted_rows=%s ratio_before=%.6f ratio_after=%.6f target_floor=%.6f",
            bool(fairness_diag.get("overlay_fairness_regularizer_enabled", False)),
            int(fairness_diag.get("overlay_fairness_regularizer_adjusted_rows", 0) or 0),
            float(fairness_diag.get("overlay_fairness_regularizer_ratio_before", 0.0) or 0.0),
            float(fairness_diag.get("overlay_fairness_regularizer_ratio_after", 0.0) or 0.0),
            float(fairness_diag.get("overlay_fairness_regularizer_target_floor", 0.0) or 0.0),
        )

        if overlay_df.filter(~pl.col("overlay_factor_total").is_finite()).height:
            _abort(
                "S4_INTENSITY_NUMERIC_INVALID",
                "V-08",
                "overlay_factor_non_finite",
                {"detail": "overlay_factor_total contains NaN/Inf"},
                manifest_fingerprint,
            )
        if overlay_df.filter(pl.col("overlay_factor_total") < 0).height:
            _abort(
                "S4_INTENSITY_NUMERIC_INVALID",
                "V-08",
                "overlay_factor_negative",
                {"detail": "overlay_factor_total contains negative values"},
                manifest_fingerprint,
            )

        if overlay_df.height:
            metrics["overlay_factor_min"] = float(overlay_df.select(pl.col("overlay_factor_total").min()).item())
            metrics["overlay_factor_median"] = float(overlay_df.select(pl.col("overlay_factor_total").median()).item())
            metrics["overlay_factor_p95"] = float(overlay_df.select(pl.col("overlay_factor_total").quantile(0.95)).item())
            metrics["overlay_factor_max"] = float(overlay_df.select(pl.col("overlay_factor_total").max()).item())

        current_phase = "overlay_validation"
        warn_violation_count = 0
        if validation_policy:
            warn_bounds = (validation_policy.get("warnings") or {}).get("warn_bounds_total") or {}
            min_warn = warn_bounds.get("min_warn")
            max_warn = warn_bounds.get("max_warn")
            suppress_low_types = (
                (warn_bounds.get("exceptions") or {}).get("suppress_low_warn_when_type_active") or []
            )
            if min_warn is not None or max_warn is not None:
                low_violation = pl.col("overlay_factor_total") < float(min_warn) if min_warn is not None else pl.lit(False)
                high_violation = pl.col("overlay_factor_total") > float(max_warn) if max_warn is not None else pl.lit(False)
                if suppress_low_types:
                    suppress_cols = [
                        pl.col(f"active_{str(t).lower()}") for t in suppress_low_types if f"active_{str(t).lower()}" in overlay_df.columns
                    ]
                    if suppress_cols:
                        low_violation = low_violation & ~pl.any_horizontal(suppress_cols)
                warn_df = overlay_df.select((low_violation | high_violation).alias("warn"))
                warn_violation_count = int(warn_df.get_column("warn").sum())
                warnings["overlay_warn_bounds_total"] = warn_violation_count

            aggregate_checks = (validation_policy.get("warnings") or {}).get("aggregate_warn_checks") or []
            scenario_type = "baseline" if scenario_cfg.get("is_baseline") else "stress" if scenario_cfg.get("is_stress") else "other"
            agg_warns = 0
            for check in aggregate_checks:
                selector = check.get("selector") or {}
                if selector.get("scenario_type") and selector.get("scenario_type") != scenario_type:
                    continue
                metric = str(check.get("metric") or "")
                bounds = check.get("bounds") or [None, None]
                value = None
                if metric == "mean":
                    value = float(overlay_df.select(pl.col("overlay_factor_total").mean()).item())
                elif metric == "p95":
                    value = float(overlay_df.select(pl.col("overlay_factor_total").quantile(0.95)).item())
                elif metric == "max":
                    value = float(overlay_df.select(pl.col("overlay_factor_total").max()).item())
                if value is None:
                    continue
                lower = bounds[0]
                upper = bounds[1] if len(bounds) > 1 else None
                if (lower is not None and value < float(lower)) or (upper is not None and value > float(upper)):
                    agg_warns += 1
                    logger.warning(
                        "S4: aggregate overlay warning %s (metric=%s value=%.4f bounds=%s)",
                        check.get("name"),
                        metric,
                        value,
                        bounds,
                    )
            warnings["overlay_warn_aggregate"] = agg_warns

            gating = validation_policy.get("gating") or {}
            warn_is_fatal = bool(gating.get("warn_violation_is_fatal"))
            max_warn_fail = float(gating.get("max_warn_violations_fraction_fail") or 0.0)
            max_warn_warn = float(gating.get("max_warn_violations_fraction_warn") or 0.0)
            total_points = max(int(overlay_df.height), 1)
            warn_fraction = warn_violation_count / total_points
            if warn_is_fatal and warn_violation_count:
                _abort(
                    "S4_INTENSITY_NUMERIC_INVALID",
                    "V-09",
                    "overlay_warn_violation_fatal",
                    {"warn_violations": warn_violation_count, "warn_fraction": warn_fraction},
                    manifest_fingerprint,
                )
            if max_warn_fail and warn_fraction > max_warn_fail:
                _abort(
                    "S4_INTENSITY_NUMERIC_INVALID",
                    "V-09",
                    "overlay_warn_fraction_exceeds_fail",
                    {"warn_fraction": warn_fraction, "threshold": max_warn_fail},
                    manifest_fingerprint,
                )
            if max_warn_warn and warn_fraction > max_warn_warn:
                logger.warning(
                    "S4: overlay warn fraction above warn threshold (fraction=%.6f threshold=%.6f)",
                    warn_fraction,
                    max_warn_warn,
                )
        current_phase = "scenario_compose"
        overlay_df = overlay_df.with_columns(
            (pl.col("lambda_local_base") * pl.col("overlay_factor_total")).alias("lambda_local_scenario")
        )
        if overlay_df.filter(~pl.col("lambda_local_scenario").is_finite()).height:
            _abort(
                "S4_INTENSITY_NUMERIC_INVALID",
                "V-10",
                "scenario_lambda_non_finite",
                {"detail": "lambda_local_scenario contains NaN/Inf"},
                manifest_fingerprint,
            )
        if overlay_df.filter(pl.col("lambda_local_scenario") < 0).height:
            _abort(
                "S4_INTENSITY_NUMERIC_INVALID",
                "V-10",
                "scenario_lambda_negative",
                {"detail": "lambda_local_scenario contains negative values"},
                manifest_fingerprint,
            )

        if overlay_df.height:
            metrics["scenario_lambda_min"] = float(overlay_df.select(pl.col("lambda_local_scenario").min()).item())
            metrics["scenario_lambda_median"] = float(overlay_df.select(pl.col("lambda_local_scenario").median()).item())
            metrics["scenario_lambda_p95"] = float(overlay_df.select(pl.col("lambda_local_scenario").quantile(0.95)).item())
            metrics["scenario_lambda_max"] = float(overlay_df.select(pl.col("lambda_local_scenario").max()).item())

        current_phase = "output_prepare"
        scenario_local_df = overlay_df.select(
            [
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "local_horizon_bucket_index",
                "lambda_local_scenario",
                "overlay_factor_total",
            ]
            + ([col for col in ["channel_group"] if col in overlay_df.columns])
        ).with_columns(
            [
                pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
                pl.lit(str(parameter_hash)).alias("parameter_hash"),
                pl.lit(str(scenario_id)).alias("scenario_id"),
                pl.lit(S4_SPEC_VERSION).alias("s4_spec_version"),
            ]
        ).select(
            [
                "manifest_fingerprint",
                "parameter_hash",
                "scenario_id",
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "local_horizon_bucket_index",
                "lambda_local_scenario",
                "overlay_factor_total",
            ]
            + ([col for col in ["channel_group"] if col in overlay_df.columns])
            + ["s4_spec_version"]
        )
        scenario_local_df = scenario_local_df.sort(
            ["merchant_id", "legal_country_iso", "tzid", "local_horizon_bucket_index"]
        )
        counts["scenario_rows"] = scenario_local_df.height
        timer.info(
            "S4: phase overlay_compute complete (event_rows=%s, expanded_rows=%s, scenario_rows=%s)",
            len(event_rows),
            len(expanded_rows),
            counts["scenario_rows"],
        )

        current_phase = "output_schema_validation"
        if output_validate_full:
            _validate_array_rows(
                scenario_local_df.iter_rows(named=True),
                schema_5a,
                schema_layer1,
                schema_layer2,
                "model/merchant_zone_scenario_local_5A",
                logger=logger,
                label="S4: validate merchant_zone_scenario_local_5A rows",
                total_rows=scenario_local_df.height,
                progress_min_rows=200000,
                frame=scenario_local_df,
            )
        else:
            _validate_dataframe_fast(
                scenario_local_df,
                schema_5a,
                schema_layer1,
                schema_layer2,
                "model/merchant_zone_scenario_local_5A",
                logger=logger,
                label="merchant_zone_scenario_local_5A",
                sample_rows=output_sample_rows,
            )

        del overlay_df
        gc.collect()

        overlay_factors_df = scenario_local_df.select(
            [
                "manifest_fingerprint",
                "parameter_hash",
                "scenario_id",
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "local_horizon_bucket_index",
                "overlay_factor_total",
                "s4_spec_version",
            ]
            + ([col for col in ["channel_group"] if col in scenario_local_df.columns])
        )
        counts["overlay_rows"] = overlay_factors_df.height

        if output_validate_full:
            _validate_array_rows(
                overlay_factors_df.iter_rows(named=True),
                schema_5a,
                schema_layer1,
                schema_layer2,
                "model/merchant_zone_overlay_factors_5A",
                logger=logger,
                label="S4: validate merchant_zone_overlay_factors_5A rows",
                total_rows=overlay_factors_df.height,
                progress_min_rows=200000,
                frame=overlay_factors_df,
            )
        else:
            _validate_dataframe_fast(
                overlay_factors_df,
                schema_5a,
                schema_layer1,
                schema_layer2,
                "model/merchant_zone_overlay_factors_5A",
                logger=logger,
                label="merchant_zone_overlay_factors_5A",
                sample_rows=output_sample_rows,
            )

        scenario_utc_df = None
        if emit_utc_intensities:
            scenario_utc_df = scenario_local_df.select(
                [
                    "manifest_fingerprint",
                    "parameter_hash",
                    "scenario_id",
                    "merchant_id",
                    "legal_country_iso",
                    "tzid",
                    pl.col("local_horizon_bucket_index").alias("utc_horizon_bucket_index"),
                    pl.col("lambda_local_scenario").alias("lambda_utc_scenario"),
                    "s4_spec_version",
                ]
                + ([col for col in ["channel_group"] if col in scenario_local_df.columns])
            )
            if output_validate_full:
                _validate_array_rows(
                    scenario_utc_df.iter_rows(named=True),
                    schema_5a,
                    schema_layer1,
                    schema_layer2,
                    "model/merchant_zone_scenario_utc_5A",
                    logger=logger,
                    label="S4: validate merchant_zone_scenario_utc_5A rows",
                    total_rows=scenario_utc_df.height,
                    progress_min_rows=200000,
                    frame=scenario_utc_df,
                )
            else:
                _validate_dataframe_fast(
                    scenario_utc_df,
                    schema_5a,
                    schema_layer1,
                    schema_layer2,
                    "model/merchant_zone_scenario_utc_5A",
                    logger=logger,
                    label="merchant_zone_scenario_utc_5A",
                    sample_rows=output_sample_rows,
                )
            logger.info("S4: UTC scenario intensities emitted (identity mapping to local horizon index).")
        else:
            logger.info("S4: UTC scenario intensities disabled by scenario_horizon_config.")

        timer.info(
            "S4: phase output_schema_validation complete (scenario_rows=%s, overlay_rows=%s, emit_utc=%s)",
            counts["scenario_rows"],
            counts["overlay_rows"],
            bool(scenario_utc_df is not None),
        )
        current_phase = "output_write"
        scenario_entry = find_dataset_entry(dictionary_5a, "merchant_zone_scenario_local_5A").entry
        scenario_local_path = _resolve_dataset_path(scenario_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(scenario_local_path, scenario_local_df, logger, "merchant_zone_scenario_local_5A")

        overlay_entry = find_dataset_entry(dictionary_5a, "merchant_zone_overlay_factors_5A").entry
        overlay_factors_path = _resolve_dataset_path(overlay_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(
            overlay_factors_path, overlay_factors_df, logger, "merchant_zone_overlay_factors_5A"
        )

        if scenario_utc_df is not None:
            utc_entry = find_dataset_entry(dictionary_5a, "merchant_zone_scenario_utc_5A").entry
            scenario_utc_path = _resolve_dataset_path(utc_entry, run_paths, config.external_roots, tokens)
            _publish_parquet_idempotent(
                scenario_utc_path, scenario_utc_df, logger, "merchant_zone_scenario_utc_5A"
            )

        timer.info("S4: phase output_write complete")
        status = "PASS"
        timer.info("S4: completed scenario overlay synthesis")

    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "S4_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "S4_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint and run_paths is not None:
            try:
                run_report_entry = find_dataset_entry(dictionary_5a, "s4_run_report_5A").entry
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
                    "validation": {
                        "output_schema_mode": output_validation_mode,
                        "output_sample_rows": None if output_validate_full else int(output_sample_rows),
                    },
                    "counts": counts,
                    "metrics": metrics,
                    "warnings": warnings,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "merchant_zone_scenario_local_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_zone_scenario_local_5A").entry,
                            tokens,
                        ),
                        "merchant_zone_overlay_factors_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_zone_overlay_factors_5A").entry,
                            tokens,
                        ),
                        "merchant_zone_scenario_utc_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_zone_scenario_utc_5A").entry,
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
                logger.info("S4: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S4: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "S4_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if scenario_local_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "S4_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S4Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        scenario_local_path=scenario_local_path,
        overlay_factors_path=overlay_factors_path,
        scenario_utc_path=scenario_utc_path,
        run_report_path=run_report_path,
    )
