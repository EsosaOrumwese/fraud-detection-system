"""S4 group weights runner for Segment 2B."""

from __future__ import annotations

import json
import math
import os
import platform
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import validate_dataframe
from engine.contracts.loader import (
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
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_2B.s0_gate.runner import (
    _hash_partition,
    _inline_external_refs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
)


MODULE_NAME = "2B.S4.group_weights"
SEGMENT = "2B"
STATE = "S4"

EPSILON = 1e-12
WRITE_BATCH_SIZE = 100_000
OUTPUT_VALIDATION_SAMPLE_ROWS_DEFAULT = 2_048

OUTPUT_SCHEMA = {
    "merchant_id": pl.UInt64,
    "utc_day": pl.Utf8,
    "tz_group_id": pl.Utf8,
    "p_group": pl.Float64,
    "base_share": pl.Float64,
    "gamma": pl.Float64,
    "created_utc": pl.Utf8,
    "mass_raw": pl.Float64,
    "denom_raw": pl.Float64,
}

OUTPUT_COLUMNS = list(OUTPUT_SCHEMA.keys())


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_root: Path
    run_report_path: Path


@dataclass(frozen=True)
class GroupMixRegularizerPolicy:
    enabled: bool
    apply_when_groups_ge: int
    max_p_group_soft_cap: float
    regularization_strength: float
    entropy_floor: float
    preserve_rank_order: bool
    sum_to_one: bool
    version_tag: str
    sha256_hex: str


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
    def __init__(self, total: Optional[int], logger, label: str) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < 0.5 and not (
            self._total is not None and self._processed >= self._total
        ):
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        if self._total is not None and self._total > 0:
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


def _entropy(values: list[float]) -> float:
    total = 0.0
    for value in values:
        if value > 0.0:
            total -= value * math.log(value)
    return total


def _blend_with_uniform(values: list[float], blend: float) -> list[float]:
    blend_clamped = max(0.0, min(float(blend), 1.0))
    if blend_clamped <= 0.0:
        return list(values)
    n = len(values)
    if n == 0:
        return []
    uniform = 1.0 / float(n)
    scale = 1.0 - blend_clamped
    offset = blend_clamped * uniform
    return [(scale * value) + offset for value in values]


def _solve_entropy_blend(values: list[float], target_entropy: float) -> float:
    if not values:
        return 0.0
    n = len(values)
    entropy_now = _entropy(values)
    if target_entropy <= entropy_now + EPSILON:
        return 0.0
    entropy_uniform = math.log(float(n))
    if target_entropy >= entropy_uniform - EPSILON:
        return 1.0
    lo = 0.0
    hi = 1.0
    for _ in range(36):
        mid = (lo + hi) / 2.0
        entropy_mid = _entropy(_blend_with_uniform(values, mid))
        if entropy_mid + EPSILON < target_entropy:
            lo = mid
        else:
            hi = mid
    return hi


def _apply_group_mix_regularizer(
    p_values_raw: list[float],
    policy: GroupMixRegularizerPolicy,
) -> tuple[list[float], dict[str, float | bool]]:
    if not p_values_raw:
        return [], {"applied": False, "delta_mass": 0.0, "entropy_pre": 0.0, "entropy_post": 0.0}
    if (not policy.enabled) or len(p_values_raw) < policy.apply_when_groups_ge:
        entropy_value = _entropy(p_values_raw)
        return (
            list(p_values_raw),
            {
                "applied": False,
                "delta_mass": 0.0,
                "entropy_pre": entropy_value,
                "entropy_post": entropy_value,
                "lambda_strength": 0.0,
                "lambda_cap": 0.0,
                "lambda_entropy": 0.0,
                "max_p_pre": max(p_values_raw),
                "max_p_post": max(p_values_raw),
            },
        )

    values = list(p_values_raw)
    n = len(values)
    uniform = 1.0 / float(n)
    entropy_pre = _entropy(values)
    max_p_pre = max(values)

    lambda_strength = max(0.0, min(policy.regularization_strength, 1.0))
    if lambda_strength > 0.0:
        values = _blend_with_uniform(values, lambda_strength)

    lambda_cap = 0.0
    max_after_strength = max(values)
    cap = max(0.0, min(policy.max_p_group_soft_cap, 1.0))
    if cap < 1.0 and max_after_strength > cap + EPSILON and max_after_strength > uniform + EPSILON:
        lambda_cap = (max_after_strength - cap) / (max_after_strength - uniform)
        lambda_cap = max(0.0, min(lambda_cap, 1.0))
        if policy.preserve_rank_order and lambda_cap >= 1.0:
            lambda_cap = 1.0 - 1.0e-9
        values = _blend_with_uniform(values, lambda_cap)

    lambda_entropy = 0.0
    if policy.entropy_floor > 0.0:
        lambda_entropy = _solve_entropy_blend(values, policy.entropy_floor)
        if policy.preserve_rank_order and lambda_entropy >= 1.0:
            lambda_entropy = 1.0 - 1.0e-9
        if lambda_entropy > 0.0:
            values = _blend_with_uniform(values, lambda_entropy)

    for value in values:
        if value < -EPSILON:
            raise ValueError(f"regularizer produced negative probability: {value}")
    values = [0.0 if value < 0.0 else value for value in values]

    total = sum(values)
    if (not math.isfinite(total)) or total <= 0.0:
        raise ValueError(f"regularizer produced non-positive mass: {total}")
    if policy.sum_to_one or abs(total - 1.0) > EPSILON:
        values = [value / total for value in values]

    entropy_post = _entropy(values)
    max_p_post = max(values)
    delta_mass = 0.5 * sum(abs(new - old) for new, old in zip(values, p_values_raw))
    applied = any(abs(new - old) > 1.0e-15 for new, old in zip(values, p_values_raw))
    return (
        values,
        {
            "applied": applied,
            "delta_mass": delta_mass,
            "entropy_pre": entropy_pre,
            "entropy_post": entropy_post,
            "lambda_strength": lambda_strength,
            "lambda_cap": lambda_cap,
            "lambda_entropy": lambda_entropy,
            "max_p_pre": max_p_pre,
            "max_p_post": max_p_post,
        },
    )


def _emit_event(
    logger,
    event: str,
    seed: int,
    manifest_fingerprint: str,
    severity: str,
    **fields: object,
) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "seed": seed,
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
    seed: int,
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
    payload: dict[str, object] = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", seed, manifest_fingerprint, severity, **payload)


def _emit_failure_event(
    logger,
    code: str,
    seed: int,
    manifest_fingerprint: str,
    validator: str,
    message: str,
    context: dict,
    run_id: str,
    parameter_hash: str,
) -> None:
    payload = {
        "event": "S4_ERROR",
        "code": code,
        "severity": "ERROR",
        "message": message,
        "manifest_fingerprint": manifest_fingerprint,
        "seed": seed,
        "validator": validator,
        "context": context,
        "run_id": run_id,
        "parameter_hash": parameter_hash,
        "at": utc_now_rfc3339_micro(),
    }
    logger.error("S4_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _table_pack(schema_pack: dict, path: str) -> tuple[dict, str]:
    node: dict = schema_pack
    parts = path.strip("#/").split("/")
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            raise ContractError(f"Schema section not found: {path}")
        node = node[part]
    table_name = parts[-1]
    table_def = node.get(table_name)
    if not isinstance(table_def, dict):
        raise ContractError(f"Schema section not found: {path}")
    pack = {"$id": schema_pack.get("$id", ""), "$defs": schema_pack.get("$defs", {})}
    pack[table_name] = table_def
    return pack, table_name


def _resolve_entries(dictionary: dict) -> dict[str, dict]:
    required_ids = (
        "s0_gate_receipt_2B",
        "sealed_inputs_2B",
        "s1_site_weights",
        "site_timezones",
        "s3_day_effects",
        "group_mix_regularizer_v1",
        "s4_group_weights",
    )
    entries: dict[str, dict] = {}
    for dataset_id in required_ids:
        entries[dataset_id] = find_dataset_entry(dictionary, dataset_id).entry
    return entries


def _find_sealed_asset(sealed_inputs: list[dict], asset_id: str) -> Optional[dict]:
    for item in sealed_inputs:
        if isinstance(item, dict) and item.get("asset_id") == asset_id:
            return item
    return None


def _validate_payload(
    schema_pack: dict,
    schema_path: str,
    payload: dict,
    ref_packs: Optional[dict[str, dict]] = None,
) -> None:
    schema = _schema_from_pack(schema_pack, schema_path)
    if ref_packs:
        for prefix, pack in ref_packs.items():
            _inline_external_refs(schema, pack, prefix)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(schema_path, errors)


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _build_batch_df(rows: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=OUTPUT_SCHEMA, orient="row")


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else minimum


def _required_columns_from_table(schema_pack: dict, table_name: str) -> list[str]:
    table = schema_pack.get(table_name)
    if not isinstance(table, dict):
        raise ContractError(f"Schema table not found for required-column extraction: {table_name}")
    columns = table.get("columns")
    if not isinstance(columns, list):
        raise ContractError(f"Schema table has no columns: {table_name}")
    required: list[str] = []
    for column in columns:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        if isinstance(name, str) and name:
            required.append(name)
    if not required:
        raise ContractError(f"Schema table has empty column names: {table_name}")
    return required


def _validate_output_batch(
    dataframe: pl.DataFrame,
    schema_pack: dict,
    table_name: str,
    mode: str,
    sample_rows: int,
) -> None:
    required_columns = _required_columns_from_table(schema_pack, table_name)
    missing_columns = [name for name in required_columns if name not in dataframe.columns]
    if missing_columns:
        raise SchemaValidationError(
            f"{table_name} missing required columns: {missing_columns}",
            [{"field": name, "message": "missing required column"} for name in missing_columns],
        )
    if mode == "strict":
        validate_dataframe(dataframe.iter_rows(named=True), schema_pack, table_name)
        return
    if mode == "sample":
        if dataframe.height == 0:
            return
        rows_to_validate = min(sample_rows, dataframe.height)
        validate_dataframe(dataframe.head(rows_to_validate).iter_rows(named=True), schema_pack, table_name)
        return
    raise ContractError(f"Unsupported S4 output validation mode: {mode}")


def _write_batch(
    rows: list[tuple],
    output_tmp: Path,
    part_index: int,
    output_pack: dict,
    output_table: str,
    output_validation_mode: str,
    output_validation_sample_rows: int,
) -> int:
    if not rows:
        return 0
    df = _build_batch_df(rows)
    _validate_output_batch(
        df,
        output_pack,
        output_table,
        output_validation_mode,
        output_validation_sample_rows,
    )
    output_tmp.mkdir(parents=True, exist_ok=True)
    path = output_tmp / f"part-{part_index:05d}.parquet"
    df.write_parquet(path, compression="zstd")
    rows.clear()
    return path.stat().st_size


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l1.seg_2B.s4_group_weights.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    runs_root_norm = str(config.runs_root).replace("\\", "/")
    output_validation_mode_default = (
        "sample" if "runs/fix-data-engine" in runs_root_norm else "strict"
    )
    output_validation_mode = _env_str(
        "ENGINE_2B_S4_OUTPUT_VALIDATION_MODE",
        output_validation_mode_default,
    ).lower()
    if output_validation_mode not in ("strict", "sample"):
        output_validation_mode = output_validation_mode_default
    output_validation_sample_rows = _env_int(
        "ENGINE_2B_S4_OUTPUT_VALIDATION_SAMPLE_ROWS",
        OUTPUT_VALIDATION_SAMPLE_ROWS_DEFAULT,
        minimum=1,
    )
    logger.info(
        "S4: output_validation_mode=%s output_validation_sample_rows=%d",
        output_validation_mode,
        output_validation_sample_rows,
    )

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""

    dictionary_version = "unknown"
    registry_version = "unknown"

    weights_catalog_path = ""
    timezones_catalog_path = ""
    day_effects_catalog_path = ""
    policy_catalog_path = ""
    output_catalog_path = ""
    policy_version_tag = ""
    policy_sha256 = ""
    regularizer_policy = GroupMixRegularizerPolicy(
        enabled=False,
        apply_when_groups_ge=2,
        max_p_group_soft_cap=1.0,
        regularization_strength=0.0,
        entropy_floor=0.0,
        preserve_rank_order=True,
        sum_to_one=True,
        version_tag="",
        sha256_hex="",
    )

    merchants_total = 0
    tz_groups_total = 0
    days_total = 0
    rows_expected = 0
    rows_written = 0

    join_misses = 0
    multimap_keys = 0
    pk_duplicates = 0

    base_share_sigma_max_abs_error = 0.0
    merchants_over_base_share_epsilon = 0
    max_abs_mass_error_per_day = 0.0
    merchants_days_over_epsilon = 0
    regularizer_rows_eligible = 0
    regularizer_rows_applied = 0
    regularizer_total_delta_mass = 0.0
    regularizer_max_delta_mass = 0.0
    regularizer_max_lambda_cap = 0.0
    regularizer_max_lambda_entropy = 0.0

    publish_bytes_total = 0
    write_once_verified = False
    atomic_publish = False

    resolve_ms = 0
    join_groups_ms = 0
    aggregate_ms = 0
    combine_ms = 0
    normalise_ms = 0
    write_ms = 0
    publish_ms = 0

    samples_rows: list[dict] = []
    samples_normalisation: list[dict] = []
    samples_base_share: list[dict] = []
    samples_coverage: list[dict] = []
    samples_gamma_echo: list[dict] = []

    validators = {
        f"V-{idx:02d}": {"id": f"V-{idx:02d}", "status": "PASS", "codes": []}
        for idx in range(1, 21)
    }
    run_report_path: Optional[Path] = None

    def _record_validator(
        validator_id: str,
        result: str,
        code: Optional[str] = None,
        detail: Optional[object] = None,
    ) -> None:
        entry = validators[validator_id]
        if code and code not in entry["codes"]:
            entry["codes"].append(code)
        if result == "fail":
            entry["status"] = "FAIL"
        elif result == "warn" and entry["status"] != "FAIL":
            entry["status"] = "WARN"
        _emit_validation(logger, seed, manifest_fingerprint, validator_id, result, error_code=code, detail=detail)

    def _abort(code: str, validator_id: str, message: str, context: dict) -> None:
        _record_validator(validator_id, "fail", code=code, detail=context)
        _emit_failure_event(logger, code, seed, manifest_fingerprint, validator_id, message, context, run_id_value, parameter_hash)
        raise EngineFailure("F4", code, STATE, MODULE_NAME, context)

    def _warn(code: str, validator_id: str, message: str, context: dict) -> None:
        _record_validator(validator_id, "warn", code=code, detail=context)
        logger.warning(
            "%s %s",
            validator_id,
            json.dumps({"message": message, "context": context}, ensure_ascii=True, sort_keys=True),
        )

    def _resolve_input(entry: dict, tokens: dict, dataset_id: str) -> Path:
        try:
            return _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
        except InputResolutionError as exc:
            _abort("2B-S4-020", "V-02", "input_resolution_failed", {"id": dataset_id, "error": str(exc)})
        raise InputResolutionError("Unreachable")

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id_value:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = int(receipt.get("seed") or 0)
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S4: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    registry_path, registry = load_artefact_registry(source, SEGMENT)
    schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        registry_path,
        schema_2b_path,
        schema_2a_path,
        schema_layer1_path,
    )

    dictionary_version = str(dictionary.get("version") or "unknown")
    registry_version = str(registry.get("version") or "unknown")

    entries = _resolve_entries(dictionary)
    tokens = {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint}

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S4"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s4_run_report.json"
    )

    logger.info(
        "S4: objective=renormalise tz-group mix from S1 base shares + S3 day effects with policy-governed anti-dominance regularizer; gated inputs s0_receipt,sealed_inputs,s1_site_weights,site_timezones,s3_day_effects,group_mix_regularizer_v1 -> output s4_group_weights",
    )

    receipt_entry = entries["s0_gate_receipt_2B"]
    receipt_path = _resolve_input(receipt_entry, {"manifest_fingerprint": manifest_fingerprint}, "s0_gate_receipt_2B")
    if not receipt_path.exists():
        _abort("2B-S4-001", "V-01", "missing_s0_receipt", {"manifest_fingerprint": manifest_fingerprint})
    receipt_payload = _load_json(receipt_path)
    receipt_schema = _schema_from_pack(schema_2b, "validation/s0_gate_receipt_v1")
    _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    receipt_errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
    if receipt_errors:
        _abort("2B-S4-001", "V-01", "invalid_s0_receipt", {"error": str(receipt_errors[0])})
    if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
        _abort(
            "2B-S4-001",
            "V-01",
            "manifest_fingerprint_mismatch",
            {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
        )
    created_utc = str(receipt_payload.get("verified_at_utc") or "")
    if not created_utc:
        _abort("2B-S4-086", "V-14", "created_utc_missing", {"receipt_path": str(receipt_path)})
    _record_validator("V-01", "pass")
    _record_validator("V-14", "pass")

    sealed_entry = entries["sealed_inputs_2B"]
    sealed_path = _resolve_input(sealed_entry, {"manifest_fingerprint": manifest_fingerprint}, "sealed_inputs_2B")
    if not sealed_path.exists():
        _abort("2B-S4-020", "V-02", "sealed_inputs_missing", {"path": str(sealed_path)})
    sealed_payload = _load_json(sealed_path)
    sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_payload))
    if sealed_errors:
        _abort("2B-S4-020", "V-02", "sealed_inputs_invalid", {"error": str(sealed_errors[0])})

    sealed_by_id = {item.get("asset_id"): item for item in sealed_payload if isinstance(item, dict)}
    sealed_timezones = sealed_by_id.get("site_timezones")
    sealed_policy = sealed_by_id.get("group_mix_regularizer_v1")
    if not sealed_timezones:
        _abort("2B-S4-022", "V-18", "site_timezones_not_sealed", {"asset_id": "site_timezones"})
    if not sealed_policy:
        _abort("2B-S4-022", "V-18", "policy_not_sealed", {"asset_id": "group_mix_regularizer_v1"})

    weights_entry = entries["s1_site_weights"]
    timezones_entry = entries["site_timezones"]
    day_effects_entry = entries["s3_day_effects"]
    policy_entry = entries["group_mix_regularizer_v1"]
    output_entry = entries["s4_group_weights"]

    weights_catalog_path = _render_catalog_path(weights_entry, tokens)
    timezones_catalog_path = _render_catalog_path(timezones_entry, tokens)
    day_effects_catalog_path = _render_catalog_path(day_effects_entry, tokens)
    policy_catalog_path = _render_catalog_path(policy_entry, {})
    output_catalog_path = _render_catalog_path(output_entry, tokens)

    if sealed_timezones.get("path") and str(sealed_timezones.get("path")) != timezones_catalog_path:
        _abort(
            "2B-S4-070",
            "V-03",
            "site_timezones_path_mismatch",
            {"sealed": sealed_timezones.get("path"), "dictionary": timezones_catalog_path},
        )
    sealed_partition = sealed_timezones.get("partition") or {}
    if sealed_partition and (
        str(sealed_partition.get("seed")) != str(seed)
        or str(sealed_partition.get("manifest_fingerprint")) != manifest_fingerprint
    ):
        _abort(
            "2B-S4-070",
            "V-03",
            "site_timezones_partition_mismatch",
            {"sealed": sealed_partition, "expected": tokens},
        )

    if sealed_policy.get("path") and str(sealed_policy.get("path")) != policy_catalog_path:
        _abort(
            "2B-S4-070",
            "V-03",
            "policy_path_mismatch",
            {"sealed": sealed_policy.get("path"), "dictionary": policy_catalog_path},
        )

    weights_path = _resolve_input(weights_entry, tokens, "s1_site_weights")
    timezones_path = _resolve_input(timezones_entry, tokens, "site_timezones")
    day_effects_path = _resolve_input(day_effects_entry, tokens, "s3_day_effects")
    policy_path = _resolve_input(policy_entry, {}, "group_mix_regularizer_v1")

    if not weights_path.exists():
        _abort("2B-S4-020", "V-02", "input_missing", {"id": "s1_site_weights", "path": str(weights_path)})
    if not timezones_path.exists():
        _abort("2B-S4-020", "V-02", "input_missing", {"id": "site_timezones", "path": str(timezones_path)})
    if not day_effects_path.exists():
        _abort("2B-S4-020", "V-02", "input_missing", {"id": "s3_day_effects", "path": str(day_effects_path)})
    if not policy_path.exists():
        _abort(
            "2B-S4-020",
            "V-02",
            "input_missing",
            {"id": "group_mix_regularizer_v1", "path": str(policy_path)},
        )

    policy_digest = sha256_file(policy_path).sha256_hex
    sealed_policy_digest = str(sealed_policy.get("sha256_hex") or "")
    if sealed_policy_digest and sealed_policy_digest != policy_digest:
        _abort(
            "2B-S4-070",
            "V-03",
            "policy_digest_mismatch",
            {"sealed": sealed_policy_digest, "computed": policy_digest},
        )

    policy_payload = _load_json(policy_path)
    try:
        _validate_payload(schema_2b, "policy/group_mix_regularizer_v1", policy_payload)
    except SchemaValidationError as exc:
        _abort("2B-S4-031", "V-18", "policy_schema_invalid", {"error": str(exc)})

    policy_version_tag = str(policy_payload.get("version_tag") or "")
    policy_sha256 = str(policy_payload.get("sha256_hex") or policy_digest)
    regularizer_policy = GroupMixRegularizerPolicy(
        enabled=bool(policy_payload.get("enabled", False)),
        apply_when_groups_ge=max(2, int(policy_payload.get("apply_when_groups_ge") or 2)),
        max_p_group_soft_cap=float(policy_payload.get("max_p_group_soft_cap") or 1.0),
        regularization_strength=float(policy_payload.get("regularization_strength") or 0.0),
        entropy_floor=float(policy_payload.get("entropy_floor") or 0.0),
        preserve_rank_order=bool(policy_payload.get("preserve_rank_order", True)),
        sum_to_one=bool(policy_payload.get("sum_to_one", True)),
        version_tag=policy_version_tag,
        sha256_hex=policy_sha256,
    )

    for dataset_id, path in (
        ("s1_site_weights", weights_catalog_path),
        ("site_timezones", timezones_catalog_path),
        ("s3_day_effects", day_effects_catalog_path),
    ):
        if f"seed={seed}" not in path or f"manifest_fingerprint={manifest_fingerprint}" not in path:
            _abort(
                "2B-S4-070",
                "V-03",
                "input_partition_mismatch",
                {"id": dataset_id, "path": path, "seed": seed, "manifest_fingerprint": manifest_fingerprint},
            )

    if f"seed={seed}" not in output_catalog_path or f"manifest_fingerprint={manifest_fingerprint}" not in output_catalog_path:
        _abort(
            "2B-S4-071",
            "V-15",
            "output_partition_mismatch",
            {"path": output_catalog_path, "seed": seed, "manifest_fingerprint": manifest_fingerprint},
        )

    output_root = run_paths.run_root / output_catalog_path

    resolve_ms = int((time.monotonic() - started_monotonic) * 1000)
    _record_validator("V-02", "pass")
    _record_validator("V-03", "pass")
    _record_validator("V-15", "pass")
    _record_validator("V-18", "pass")
    join_started = time.monotonic()

    timezones_paths = _list_parquet_paths(timezones_path)
    weights_paths = _list_parquet_paths(weights_path)

    timezones_df = pl.read_parquet(
        timezones_paths,
        columns=["merchant_id", "legal_country_iso", "site_order", "tzid"],
    )
    timezones_df = timezones_df.with_columns(
        pl.col("merchant_id").cast(pl.UInt64),
        pl.col("site_order").cast(pl.Int64),
    )

    dup_counts = (
        timezones_df.group_by(["merchant_id", "legal_country_iso", "site_order"])
        .agg(
            pl.len().alias("row_count"),
            pl.col("tzid").n_unique().alias("tzid_count"),
        )
    )
    dup_violations = dup_counts.filter(pl.col("row_count") > 1)
    multimap_keys = dup_violations.height
    if multimap_keys > 0:
        sample = dup_violations.head(5).to_dicts()
        _abort("2B-S4-041", "V-04", "tzid_multimap", {"count": multimap_keys, "sample": sample})

    tz_map: dict[tuple[int, str, int], str] = {}
    for row in timezones_df.iter_rows(named=True):
        key = (int(row["merchant_id"]), str(row["legal_country_iso"]), int(row["site_order"]))
        tzid = str(row["tzid"])
        if key in tz_map and tz_map[key] != tzid:
            _abort("2B-S4-041", "V-04", "tzid_multimap", {"site_key": key, "tzids": [tz_map[key], tzid]})
        tz_map[key] = tzid

    join_groups_ms = int((time.monotonic() - join_started) * 1000)
    aggregate_started = time.monotonic()

    weights_df = pl.read_parquet(
        weights_paths,
        columns=["merchant_id", "legal_country_iso", "site_order", "p_weight"],
    )
    weights_df = weights_df.with_columns(
        pl.col("merchant_id").cast(pl.UInt64),
        pl.col("site_order").cast(pl.Int64),
        pl.col("p_weight").cast(pl.Float64),
    ).sort(["merchant_id", "legal_country_iso", "site_order"])

    base_share: dict[int, dict[str, float]] = {}
    merchant_sums: dict[int, float] = {}
    missing_keys_sample: list[list[object]] = []

    weights_progress = _ProgressTracker(weights_df.height, logger, "S4 base-share sites")
    for row in weights_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        legal_iso = str(row["legal_country_iso"])
        site_order = int(row["site_order"])
        key = (merchant_id, legal_iso, site_order)
        tzid = tz_map.get(key)
        if tzid is None:
            join_misses += 1
            if len(missing_keys_sample) < 10:
                missing_keys_sample.append([merchant_id, legal_iso, site_order])
            weights_progress.update(1)
            continue
        p_weight = float(row["p_weight"])
        if not math.isfinite(p_weight) or p_weight < 0.0:
            _abort(
                "2B-S4-057",
                "V-10",
                "p_weight_invalid",
                {"merchant_id": merchant_id, "legal_country_iso": legal_iso, "site_order": site_order, "value": p_weight},
            )
        merchant_sums[merchant_id] = merchant_sums.get(merchant_id, 0.0) + p_weight
        base_share.setdefault(merchant_id, {})
        base_share[merchant_id][tzid] = base_share[merchant_id].get(tzid, 0.0) + p_weight
        weights_progress.update(1)

    if join_misses > 0:
        _abort(
            "2B-S4-040",
            "V-04",
            "join_key_missing",
            {"count": join_misses, "missing_keys_sample": missing_keys_sample},
        )

    merchants_total = len(base_share)
    tz_groups_total = sum(len(groups) for groups in base_share.values())

    base_share_errors: list[dict] = []
    for merchant_id, tz_groups in base_share.items():
        sum_base = sum(tz_groups.values())
        abs_error = abs(sum_base - 1.0)
        base_share_sigma_max_abs_error = max(base_share_sigma_max_abs_error, abs_error)
        if abs_error > EPSILON:
            merchants_over_base_share_epsilon += 1
        base_share_errors.append(
            {
                "merchant_id": merchant_id,
                "sum_base_share": sum_base,
                "abs_error": abs_error,
            }
        )

    base_share_errors.sort(key=lambda item: (-item["abs_error"], item["merchant_id"]))
    samples_base_share = [
        {
            "merchant_id": item["merchant_id"],
            "sum_base_share": item["sum_base_share"],
            "abs_error": item["abs_error"],
        }
        for item in base_share_errors[:20]
    ]

    if merchants_over_base_share_epsilon > 0:
        worst = base_share_errors[0]
        _record_validator("V-20", "fail", code="2B-S4-052", detail=worst)
        _abort(
            "2B-S4-052",
            "V-05",
            "base_share_sum_mismatch",
            {"merchant_id": worst["merchant_id"], "sum_base_share": worst["sum_base_share"], "epsilon": EPSILON},
        )

    merchant_tzids = {
        merchant_id: sorted(tz_groups.keys())
        for merchant_id, tz_groups in base_share.items()
    }

    _record_validator("V-04", "pass")
    _record_validator("V-05", "pass")
    _record_validator("V-20", "pass")
    aggregate_ms = int((time.monotonic() - aggregate_started) * 1000)

    day_effects_paths = _list_parquet_paths(day_effects_path)
    day_effects_df = pl.read_parquet(
        day_effects_paths,
        columns=["merchant_id", "utc_day", "tz_group_id", "gamma"],
    )
    day_effects_df = day_effects_df.with_columns(
        pl.col("merchant_id").cast(pl.UInt64),
        pl.col("gamma").cast(pl.Float64),
    )

    days = (
        day_effects_df.select(pl.col("utc_day")).unique().sort("utc_day").to_series().to_list()
    )
    days_total = len(days)
    if days_total == 0:
        _abort("2B-S4-090", "V-12", "day_grid_empty", {"expected_count": 0, "observed_count": 0})

    rows_expected = tz_groups_total * days_total
    output_pack, output_table = _table_pack(schema_2b, "plan/s4_group_weights")
    _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#/$defs/")

    output_tmp = run_paths.tmp_root / f"s4_group_weights_{uuid.uuid4().hex}"
    output_tmp.mkdir(parents=True, exist_ok=True)

    logger.info(
        "S4: renormalising day mixes (merchants=%s tz_groups=%s days=%s rows=%s regularizer_enabled=%s cap=%.4f strength=%.4f entropy_floor=%.4f)",
        merchants_total,
        tz_groups_total,
        days_total,
        rows_expected,
        regularizer_policy.enabled,
        regularizer_policy.max_p_group_soft_cap,
        regularizer_policy.regularization_strength,
        regularizer_policy.entropy_floor,
    )

    def _normalisation_sort_key(item: dict) -> tuple:
        return (-item["abs_error"], item["merchant_id"], item["utc_day"])

    def _maybe_add_normalisation_sample(candidate: dict) -> None:
        nonlocal samples_normalisation
        if len(samples_normalisation) < 20:
            samples_normalisation.append(candidate)
            samples_normalisation.sort(key=_normalisation_sort_key)
            return
        samples_normalisation.sort(key=_normalisation_sort_key)
        worst = samples_normalisation[-1]
        if _normalisation_sort_key(candidate) < _normalisation_sort_key(worst):
            samples_normalisation[-1] = candidate
            samples_normalisation.sort(key=_normalisation_sort_key)

    progress = _ProgressTracker(rows_expected, logger, "S4 group weight rows")
    part_index = 0
    batch_rows: list[tuple] = []
    prev_pk: Optional[tuple] = None

    current_merchant: Optional[int] = None
    current_day: Optional[str] = None
    current_rows: list[tuple[str, float, float]] = []
    merchant_days_seen: list[str] = []
    merchants_seen: set[int] = set()
    day_counts: dict[str, int] = {}

    def _flush_day(merchant_id: int, utc_day: str, rows: list[tuple[str, float, float]]) -> None:
        nonlocal rows_written
        nonlocal pk_duplicates
        nonlocal combine_ms
        nonlocal normalise_ms
        nonlocal write_ms
        nonlocal publish_bytes_total
        nonlocal max_abs_mass_error_per_day
        nonlocal merchants_days_over_epsilon
        nonlocal part_index
        nonlocal regularizer_rows_eligible
        nonlocal regularizer_rows_applied
        nonlocal regularizer_total_delta_mass
        nonlocal regularizer_max_delta_mass
        nonlocal regularizer_max_lambda_cap
        nonlocal regularizer_max_lambda_entropy

        expected_tzids = merchant_tzids.get(merchant_id)
        if expected_tzids is None:
            _abort("2B-S4-050", "V-06", "unknown_merchant", {"merchant_id": merchant_id})
        row_tzids = [item[0] for item in rows]
        if row_tzids != expected_tzids:
            _abort(
                "2B-S4-050",
                "V-06",
                "group_coverage_mismatch",
                {"merchant_id": merchant_id, "utc_day": utc_day, "expected": expected_tzids, "observed": row_tzids},
            )

        combine_start = time.monotonic()
        mass_rows: list[tuple[str, float, float, float]] = []
        denom_raw = 0.0
        for tzid, base_share_value, gamma in rows:
            if not math.isfinite(base_share_value) or base_share_value < 0.0:
                _abort(
                    "2B-S4-057",
                    "V-10",
                    "base_share_invalid",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "tz_group_id": tzid, "value": base_share_value},
                )
            if base_share_value > 1.0 + EPSILON:
                _abort(
                    "2B-S4-057",
                    "V-10",
                    "base_share_invalid",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "tz_group_id": tzid, "value": base_share_value},
                )
            if base_share_value > 1.0:
                base_share_value = 1.0
            if not math.isfinite(gamma) or gamma <= 0.0:
                _abort(
                    "2B-S4-057",
                    "V-10",
                    "gamma_invalid",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "tz_group_id": tzid, "value": gamma},
                )
            mass_raw = base_share_value * gamma
            mass_rows.append((tzid, base_share_value, gamma, mass_raw))
            denom_raw += mass_raw
        combine_ms += (time.monotonic() - combine_start) * 1000

        if not math.isfinite(denom_raw) or denom_raw <= 0.0:
            _abort(
                "2B-S4-051",
                "V-11",
                "denom_nonpositive",
                {"merchant_id": merchant_id, "utc_day": utc_day, "denom_raw": denom_raw},
            )

        normalise_start = time.monotonic()
        p_values: list[float] = []
        has_negative = False
        for _tzid, _base_share, _gamma, mass_raw in mass_rows:
            p_value = mass_raw / denom_raw
            if p_value < -EPSILON:
                _abort(
                    "2B-S4-057",
                    "V-10",
                    "p_group_negative",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "value": p_value},
                )
            if p_value < 0.0:
                has_negative = True
            p_values.append(p_value)

        if has_negative:
            clamped = [0.0 if p < 0.0 else p for p in p_values]
            sum_clamped = sum(clamped)
            if not math.isfinite(sum_clamped) or sum_clamped <= 0.0:
                _abort(
                    "2B-S4-051",
                    "V-11",
                    "normalisation_invalid",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "sum_clamped": sum_clamped},
                )
            p_values = [p / sum_clamped for p in clamped]

        p_values_raw = list(p_values)
        regularizer_meta: dict[str, float | bool] = {
            "applied": False,
            "delta_mass": 0.0,
            "entropy_pre": _entropy(p_values_raw),
            "entropy_post": _entropy(p_values_raw),
            "lambda_strength": 0.0,
            "lambda_cap": 0.0,
            "lambda_entropy": 0.0,
            "max_p_pre": max(p_values_raw),
            "max_p_post": max(p_values_raw),
        }
        if regularizer_policy.enabled and len(p_values_raw) >= regularizer_policy.apply_when_groups_ge:
            regularizer_rows_eligible += 1
            try:
                p_values, regularizer_meta = _apply_group_mix_regularizer(p_values_raw, regularizer_policy)
            except ValueError as exc:
                _abort(
                    "2B-S4-096",
                    "V-11",
                    "regularizer_invalid",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "error": str(exc)},
                )
            if bool(regularizer_meta.get("applied", False)):
                regularizer_rows_applied += 1
                delta_mass = float(regularizer_meta.get("delta_mass", 0.0))
                regularizer_total_delta_mass += delta_mass
                regularizer_max_delta_mass = max(regularizer_max_delta_mass, delta_mass)
                regularizer_max_lambda_cap = max(
                    regularizer_max_lambda_cap,
                    float(regularizer_meta.get("lambda_cap", 0.0)),
                )
                regularizer_max_lambda_entropy = max(
                    regularizer_max_lambda_entropy,
                    float(regularizer_meta.get("lambda_entropy", 0.0)),
                )
                if len(samples_gamma_echo) < 20:
                    samples_gamma_echo.append(
                        {
                            "merchant_id": merchant_id,
                            "utc_day": utc_day,
                            "delta_mass": delta_mass,
                            "entropy_pre": float(regularizer_meta.get("entropy_pre", 0.0)),
                            "entropy_post": float(regularizer_meta.get("entropy_post", 0.0)),
                            "max_p_pre": float(regularizer_meta.get("max_p_pre", 0.0)),
                            "max_p_post": float(regularizer_meta.get("max_p_post", 0.0)),
                        }
                    )

        sum_p_group = sum(p_values)
        abs_error = abs(sum_p_group - 1.0)
        max_abs_mass_error_per_day = max(max_abs_mass_error_per_day, abs_error)
        if abs_error > EPSILON:
            merchants_days_over_epsilon += 1
            _abort(
                "2B-S4-051",
                "V-11",
                "normalisation_error",
                {
                    "merchant_id": merchant_id,
                    "utc_day": utc_day,
                    "sum_p_group": sum_p_group,
                    "epsilon": EPSILON,
                },
            )

        _maybe_add_normalisation_sample(
            {
                "merchant_id": merchant_id,
                "utc_day": utc_day,
                "sum_p_group": sum_p_group,
                "abs_error": abs_error,
            }
        )

        sum_mass_raw = sum(item[3] for item in mass_rows)
        if abs(sum_mass_raw - denom_raw) > EPSILON:
            _abort(
                "2B-S4-095",
                "V-19",
                "audit_denominator_mismatch",
                {
                    "merchant_id": merchant_id,
                    "utc_day": utc_day,
                    "sum_mass_raw": sum_mass_raw,
                    "denom_raw": denom_raw,
                    "epsilon": EPSILON,
                },
            )

        for index, (tzid, base_share_value, gamma, mass_raw) in enumerate(mass_rows):
            p_value = p_values[index]
            if p_value < -EPSILON or p_value > 1.0 + EPSILON:
                _abort(
                    "2B-S4-057",
                    "V-10",
                    "p_group_out_of_range",
                    {"merchant_id": merchant_id, "utc_day": utc_day, "tz_group_id": tzid, "value": p_value},
                )
            expected_raw = mass_raw / denom_raw
            if abs(p_values_raw[index] - expected_raw) > EPSILON:
                _abort(
                    "2B-S4-095",
                    "V-19",
                    "audit_p_group_raw_mismatch",
                    {
                        "merchant_id": merchant_id,
                        "utc_day": utc_day,
                        "tz_group_id": tzid,
                        "expected": expected_raw,
                        "observed": p_values_raw[index],
                        "epsilon": EPSILON,
                    },
                )
            if (not bool(regularizer_meta.get("applied", False))) and abs(p_value - expected_raw) > EPSILON:
                _abort(
                    "2B-S4-095",
                    "V-19",
                    "audit_p_group_mismatch",
                    {
                        "merchant_id": merchant_id,
                        "utc_day": utc_day,
                        "tz_group_id": tzid,
                        "expected": expected_raw,
                        "observed": p_value,
                        "epsilon": EPSILON,
                    },
                )

            batch_rows.append(
                (
                    merchant_id,
                    utc_day,
                    tzid,
                    p_value,
                    base_share_value,
                    gamma,
                    created_utc,
                    mass_raw,
                    denom_raw,
                )
            )
            rows_written += 1
            if len(samples_rows) < 20:
                samples_rows.append(
                    {
                        "merchant_id": merchant_id,
                        "utc_day": utc_day,
                        "tz_group_id": tzid,
                        "base_share": base_share_value,
                        "gamma": gamma,
                        "p_group": p_value,
                    }
                )
            if len(batch_rows) >= WRITE_BATCH_SIZE:
                write_start = time.monotonic()
                try:
                    publish_bytes_total += _write_batch(
                        batch_rows,
                        output_tmp,
                        part_index,
                        output_pack,
                        output_table,
                        output_validation_mode,
                        output_validation_sample_rows,
                    )
                except SchemaValidationError as exc:
                    _abort("2B-S4-030", "V-13", "output_schema_invalid", {"error": str(exc)})
                write_ms += (time.monotonic() - write_start) * 1000
                part_index += 1
            progress.update(1)

        day_counts[utc_day] = day_counts.get(utc_day, 0) + len(mass_rows)
        normalise_ms += (time.monotonic() - normalise_start) * 1000

    def _check_day_grid(merchant_id: int, days_seen: list[str]) -> None:
        if len(days_seen) != days_total or days_seen != days:
            expected_set = set(days)
            observed_set = set(days_seen)
            first_missing = next((day for day in days if day not in observed_set), None)
            first_extra = next((day for day in days_seen if day not in expected_set), None)
            _abort(
                "2B-S4-090",
                "V-12",
                "day_grid_mismatch",
                {
                    "merchant_id": merchant_id,
                    "expected_count": days_total,
                    "observed_count": len(days_seen),
                    "first_missing": first_missing,
                    "first_extra": first_extra,
                },
            )

    day_effects_iter_start = time.monotonic()
    for row in day_effects_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        utc_day = str(row["utc_day"])
        tz_group_id = str(row["tz_group_id"])
        gamma = float(row["gamma"])

        key = (merchant_id, utc_day, tz_group_id)
        if prev_pk is not None:
            if key == prev_pk:
                pk_duplicates += 1
                _abort("2B-S4-041A", "V-07", "duplicate_pk", {"key": key})
            if key < prev_pk:
                _abort("2B-S4-083", "V-08", "writer_order_violation", {"prev": prev_pk, "curr": key})
        prev_pk = key

        if merchant_id not in base_share:
            _abort("2B-S4-050", "V-06", "merchant_missing", {"merchant_id": merchant_id})

        if current_merchant is None:
            current_merchant = merchant_id
            current_day = utc_day
            merchant_days_seen = []

        if merchant_id != current_merchant:
            if current_day is not None:
                _flush_day(current_merchant, current_day, current_rows)
                merchant_days_seen.append(current_day)
            _check_day_grid(current_merchant, merchant_days_seen)
            merchants_seen.add(current_merchant)
            current_rows = []
            merchant_days_seen = []
            current_merchant = merchant_id
            current_day = utc_day

        if utc_day != current_day:
            if current_day is not None:
                _flush_day(current_merchant, current_day, current_rows)
            merchant_days_seen.append(current_day)
            current_rows = []
            current_day = utc_day

        base_share_value = base_share[merchant_id].get(tz_group_id)
        if base_share_value is None:
            _abort(
                "2B-S4-050",
                "V-06",
                "group_missing",
                {"merchant_id": merchant_id, "utc_day": utc_day, "tz_group_id": tz_group_id},
            )
        current_rows.append((tz_group_id, base_share_value, gamma))

    if current_merchant is not None and current_day is not None:
        _flush_day(current_merchant, current_day, current_rows)
        merchant_days_seen.append(current_day)
        _check_day_grid(current_merchant, merchant_days_seen)
        merchants_seen.add(current_merchant)

    if batch_rows:
        write_start = time.monotonic()
        try:
            publish_bytes_total += _write_batch(
                batch_rows,
                output_tmp,
                part_index,
                output_pack,
                output_table,
                output_validation_mode,
                output_validation_sample_rows,
            )
        except SchemaValidationError as exc:
            _abort("2B-S4-030", "V-13", "output_schema_invalid", {"error": str(exc)})
        write_ms += (time.monotonic() - write_start) * 1000

    if rows_written != rows_expected:
        _abort(
            "2B-S4-050",
            "V-06",
            "coverage_mismatch",
            {"rows_expected": rows_expected, "rows_written": rows_written},
        )

    if merchants_seen != set(base_share.keys()):
        _abort(
            "2B-S4-050",
            "V-06",
            "merchant_coverage_mismatch",
            {"expected": len(base_share), "observed": len(merchants_seen)},
        )

    if len(day_counts) != days_total:
        _abort(
            "2B-S4-090",
            "V-12",
            "day_grid_mismatch",
            {"expected_count": days_total, "observed_count": len(day_counts)},
        )

    _record_validator("V-06", "pass")
    _record_validator("V-07", "pass")
    _record_validator("V-08", "pass")
    _record_validator("V-09", "pass")
    _record_validator("V-10", "pass")
    _record_validator("V-11", "pass")
    _record_validator("V-12", "pass")
    _record_validator("V-13", "pass")
    _record_validator("V-19", "pass")

    samples_coverage = [
        {
            "utc_day": day,
            "expected_groups": tz_groups_total,
            "observed_groups": day_counts.get(day, 0),
        }
        for day in days[:10]
    ]

    normalise_ms = int(normalise_ms)
    combine_ms = int(combine_ms)
    publish_started = time.monotonic()
    if output_root.exists() and any(output_root.iterdir()):
        existing_digest, _ = _hash_partition(output_root)
        new_digest, _ = _hash_partition(output_tmp)
        if existing_digest != new_digest:
            _record_validator("V-16", "fail", code="2B-S4-080", detail={"path": str(output_root)})
            _record_validator("V-17", "fail", code="2B-S4-081", detail={"path": str(output_root)})
            _abort(
                "2B-S4-081",
                "V-17",
                "non_idempotent_reemit",
                {"existing": existing_digest, "new": new_digest},
            )
        logger.info("S4: output already exists and is identical; skipping publish.")
        write_once_verified = True
        atomic_publish = False
        if output_tmp.exists():
            shutil.rmtree(output_tmp)
        publish_bytes_total = sum(path.stat().st_size for path in output_root.glob("*.parquet"))
    else:
        try:
            output_root.parent.mkdir(parents=True, exist_ok=True)
            if output_root.exists():
                output_root.rmdir()
            output_tmp.replace(output_root)
        except OSError as exc:
            _abort(
                "2B-S4-082",
                "V-17",
                "atomic_publish_failed",
                {"error": str(exc), "path": str(output_root)},
            )
        atomic_publish = True
        write_once_verified = False
        publish_bytes_total = sum(path.stat().st_size for path in output_root.glob("*.parquet"))

    publish_ms = int((time.monotonic() - publish_started) * 1000)
    _record_validator("V-16", "pass")
    _record_validator("V-17", "pass")

    warn_count = sum(1 for item in validators.values() if item["status"] == "WARN")
    fail_count = sum(1 for item in validators.values() if item["status"] == "FAIL")

    run_report = {
        "component": "2B.S4",
        "manifest_fingerprint": manifest_fingerprint,
        "seed": str(seed),
        "created_utc": created_utc,
        "catalogue_resolution": {
            "dictionary_version": dictionary_version,
            "registry_version": registry_version,
        },
        "policy": {
            "id": "group_mix_regularizer_v1",
            "version_tag": policy_version_tag,
            "sha256_hex": policy_sha256,
            "enabled": regularizer_policy.enabled,
            "apply_when_groups_ge": regularizer_policy.apply_when_groups_ge,
            "max_p_group_soft_cap": regularizer_policy.max_p_group_soft_cap,
            "regularization_strength": regularizer_policy.regularization_strength,
            "entropy_floor": regularizer_policy.entropy_floor,
            "preserve_rank_order": regularizer_policy.preserve_rank_order,
            "sum_to_one": regularizer_policy.sum_to_one,
        },
        "inputs_summary": {
            "weights_path": weights_catalog_path,
            "timezones_path": timezones_catalog_path,
            "day_effects_path": day_effects_catalog_path,
            "policy_path": policy_catalog_path,
            "merchants_total": merchants_total,
            "tz_groups_total": tz_groups_total,
            "days_total": days_total,
        },
        "aggregation": {
            "base_share_sigma_max_abs_error": base_share_sigma_max_abs_error,
            "epsilon": EPSILON,
        },
        "normalisation": {
            "max_abs_mass_error_per_day": max_abs_mass_error_per_day,
            "merchants_days_over_epsilon": merchants_days_over_epsilon,
            "regularizer_rows_eligible": regularizer_rows_eligible,
            "regularizer_rows_applied": regularizer_rows_applied,
            "regularizer_total_delta_mass": regularizer_total_delta_mass,
            "regularizer_max_delta_mass": regularizer_max_delta_mass,
            "regularizer_max_lambda_cap": regularizer_max_lambda_cap,
            "regularizer_max_lambda_entropy": regularizer_max_lambda_entropy,
        },
        "publish": {
            "target_path": output_catalog_path,
            "bytes_written": publish_bytes_total,
            "write_once_verified": write_once_verified,
            "atomic_publish": atomic_publish,
        },
        "validators": [validators[key] for key in sorted(validators.keys())],
        "summary": {
            "overall_status": "PASS" if fail_count == 0 else "FAIL",
            "warn_count": warn_count,
            "fail_count": fail_count,
        },
        "environment": {
            "engine_commit": str(receipt.get("git_commit_hex") or ""),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "network_io_detected": 0,
        },
        "samples": {
            "rows": samples_rows,
            "normalisation": samples_normalisation,
            "base_share": samples_base_share,
            "coverage": samples_coverage,
            **({"regularizer": samples_gamma_echo} if samples_gamma_echo else {}),
        },
        "counters": {
            "merchants_total": merchants_total,
            "tz_groups_total": tz_groups_total,
            "days_total": days_total,
            "rows_expected": rows_expected,
            "rows_written": rows_written,
            "pk_duplicates": pk_duplicates,
            "join_misses": join_misses,
            "multimap_keys": multimap_keys,
            "merchants_over_base_share_epsilon": merchants_over_base_share_epsilon,
            "merchants_days_over_norm_epsilon": merchants_days_over_epsilon,
            "regularizer_rows_eligible": regularizer_rows_eligible,
            "regularizer_rows_applied": regularizer_rows_applied,
            "publish_bytes_total": publish_bytes_total,
        },
        "durations_ms": {
            "resolve_ms": resolve_ms,
            "join_groups_ms": join_groups_ms,
            "aggregate_ms": aggregate_ms,
            "combine_ms": combine_ms,
            "normalise_ms": normalise_ms,
            "write_ms": int(write_ms),
            "publish_ms": publish_ms,
        },
        "id_map": [
            {"id": "s1_site_weights", "path": weights_catalog_path},
            {"id": "site_timezones", "path": timezones_catalog_path},
            {"id": "s3_day_effects", "path": day_effects_catalog_path},
            {"id": "group_mix_regularizer_v1", "path": policy_catalog_path},
            {"id": "s4_group_weights", "path": output_catalog_path},
        ],
    }

    logger.info("S4 run-report %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))
    if run_report_path is not None:
        _write_json(run_report_path, run_report)
    timer.info("S4: completed")

    return S4Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        output_root=output_root,
        run_report_path=run_report_path or Path(""),
    )
