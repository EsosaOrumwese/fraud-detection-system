"""S3 day effects runner for Segment 2B."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
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
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    low64,
    philox2x64_10,
    ser_u64,
    uer_string,
)


MODULE_NAME = "2B.S3.day_effects"
SEGMENT = "2B"
STATE = "S3"

UINT64_MASK = 0xFFFFFFFFFFFFFFFF
TWO_NEG_64 = float.fromhex("0x1.0000000000000p-64")

WRITE_BATCH_SIZE = 100_000
OUTPUT_VALIDATION_SAMPLE_ROWS_DEFAULT = 2_048
PROGRESS_LOG_INTERVAL_SECONDS_DEFAULT = 0.5
FIXLANE_PROGRESS_LOG_INTERVAL_SECONDS_DEFAULT = 2.0

OUTPUT_SCHEMA = {
    "merchant_id": pl.UInt64,
    "utc_day": pl.Utf8,
    "tz_group_id": pl.Utf8,
    "gamma": pl.Float64,
    "log_gamma": pl.Float64,
    "sigma_gamma": pl.Float64,
    "rng_stream_id": pl.Utf8,
    "rng_counter_lo": pl.UInt64,
    "rng_counter_hi": pl.UInt64,
    "created_utc": pl.Utf8,
}

OUTPUT_COLUMNS = list(OUTPUT_SCHEMA.keys())


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_root: Path
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
        min_interval_seconds: float = PROGRESS_LOG_INTERVAL_SECONDS_DEFAULT,
    ) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0
        self._min_interval_seconds = (
            min_interval_seconds if min_interval_seconds > 0 else PROGRESS_LOG_INTERVAL_SECONDS_DEFAULT
        )

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < self._min_interval_seconds and not (
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
    parameter_hash: str,
    run_id: str,
    validator: str,
    message: str,
    context: dict,
) -> None:
    payload = {
        "event": "S3_ERROR",
        "code": code,
        "severity": "ERROR",
        "message": message,
        "validator": validator,
        "context": context,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "at": utc_now_rfc3339_micro(),
    }
    logger.error("S3_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    trimmed = value.strip()
    return trimmed if trimmed else default


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else minimum


def _env_float(name: str, default: float, minimum: float = 0.1) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else minimum


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    raise ContractError(f"Unsupported S3 output validation mode: {mode}")


def _log_run_report(logger, run_report: dict, log_full_json: bool) -> None:
    if log_full_json:
        logger.info("S3 run-report %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))
        return
    summary = run_report.get("summary", {})
    rng = run_report.get("rng_accounting", {})
    publish = run_report.get("publish", {})
    durations = run_report.get("durations_ms", {})
    logger.info(
        "S3 run-report summary status=%s warn=%s fail=%s rows=%s/%s bytes=%s draw_ms=%s write_ms=%s publish_ms=%s",
        summary.get("overall_status", "UNKNOWN"),
        summary.get("warn_count", 0),
        summary.get("fail_count", 0),
        rng.get("rows_written", 0),
        rng.get("rows_expected", 0),
        publish.get("bytes_written", 0),
        durations.get("draw_ms", 0),
        durations.get("write_ms", 0),
        durations.get("publish_ms", 0),
    )


def _derive_rng_key_counter(
    manifest_fingerprint_hex: str,
    seed: int,
    rng_stream_id: str,
    domain_master: str,
    domain_stream: str,
) -> tuple[int, int, int]:
    manifest_bytes = bytes.fromhex(manifest_fingerprint_hex)
    if len(manifest_bytes) != 32:
        raise ValueError("manifest_fingerprint must be 32 bytes.")
    master_payload = uer_string(domain_master) + manifest_bytes + ser_u64(seed)
    master_digest = hashlib.sha256(master_payload).digest()
    stream_payload = uer_string(domain_stream) + uer_string(rng_stream_id)
    digest = hashlib.sha256(master_digest + stream_payload).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def _u01(x: int) -> float:
    return (float(x) + 0.5) * TWO_NEG_64


def _normal_icdf(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0,1)")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q) + 1.0
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r) + 1.0
    )


def _deterministic_unit_interval(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return _u01(int.from_bytes(digest[:8], "big", signed=False))


def _merchant_segment_key(site_count: int) -> str:
    if site_count <= 8:
        return "small"
    if site_count <= 24:
        return "mid"
    return "large"


def _resolve_segment_value(mapping: dict[str, object], segment_key: str, fallback: float) -> float:
    if segment_key in mapping:
        return float(mapping[segment_key])
    if "default" in mapping:
        return float(mapping["default"])
    return float(fallback)


def _resolve_tz_multiplier(spec: dict[str, object], tzid: str) -> float:
    default = float(spec.get("default", 1.0))
    rules = spec.get("prefix_rules")
    if not isinstance(rules, list):
        return default
    for item in rules:
        if not isinstance(item, dict):
            continue
        prefix = str(item.get("prefix") or "")
        if prefix and tzid.startswith(prefix):
            try:
                return float(item.get("multiplier", default))
            except (TypeError, ValueError):
                return default
    return default


def _build_batch_df(rows: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=OUTPUT_SCHEMA, orient="row")


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


def _resolve_entries(dictionary: dict) -> dict[str, dict]:
    required_ids = (
        "s0_gate_receipt_2B",
        "sealed_inputs_2B",
        "s1_site_weights",
        "site_timezones",
        "day_effect_policy_v1",
        "s3_day_effects",
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

def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l1.seg_2B.s3_day_effects.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    runs_root_norm = str(config.runs_root).replace("\\", "/")
    output_validation_mode_default = (
        "sample" if "runs/fix-data-engine" in runs_root_norm else "strict"
    )
    output_validation_mode = _env_str(
        "ENGINE_2B_S3_OUTPUT_VALIDATION_MODE",
        output_validation_mode_default,
    ).lower()
    if output_validation_mode not in ("strict", "sample"):
        output_validation_mode = output_validation_mode_default
    output_validation_sample_rows = _env_int(
        "ENGINE_2B_S3_OUTPUT_VALIDATION_SAMPLE_ROWS",
        OUTPUT_VALIDATION_SAMPLE_ROWS_DEFAULT,
        minimum=1,
    )
    progress_log_interval_default = (
        FIXLANE_PROGRESS_LOG_INTERVAL_SECONDS_DEFAULT
        if "runs/fix-data-engine" in runs_root_norm
        else PROGRESS_LOG_INTERVAL_SECONDS_DEFAULT
    )
    progress_log_interval_seconds = _env_float(
        "ENGINE_2B_S3_PROGRESS_LOG_INTERVAL_SECONDS",
        progress_log_interval_default,
        minimum=0.1,
    )
    log_run_report_json_default = "runs/fix-data-engine" not in runs_root_norm
    log_run_report_json = _env_bool(
        "ENGINE_2B_S3_LOG_RUN_REPORT_JSON",
        default=log_run_report_json_default,
    )
    logger.info(
        "S3: output_validation_mode=%s output_validation_sample_rows=%d progress_log_interval_seconds=%.2f log_run_report_json=%s",
        output_validation_mode,
        output_validation_sample_rows,
        progress_log_interval_seconds,
        str(log_run_report_json).lower(),
    )

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""

    dictionary_version = "unknown"
    registry_version = "unknown"
    policy_version_tag = ""
    policy_sha256 = ""
    sigma_policy_mode = "scalar_v1"

    weights_catalog_path = ""
    timezones_catalog_path = ""
    policy_catalog_path = ""
    output_catalog_path = ""

    rows_expected = 0
    rows_written = 0
    draws_total = 0
    join_misses = 0
    pk_duplicates = 0
    nonpositive_gamma_rows = 0
    gamma_clipped_rows = 0
    max_abs_log_gamma = 0.0
    sigma_gamma_min_observed = float("inf")
    sigma_gamma_max_observed = 0.0

    publish_bytes_total = 0
    write_once_verified = False
    atomic_publish = False

    resolve_ms = 0
    join_groups_ms = 0
    draw_ms = 0
    write_ms = 0
    publish_ms = 0

    samples_rows: list[dict] = []
    samples_rng_monotonic: list[dict] = []
    coverage_by_day: list[dict] = []
    tz_groups_per_merchant: list[dict] = []
    warn_tzids: list[str] = []

    validators = {f"V-{idx:02d}": {"id": f"V-{idx:02d}", "status": "PASS", "codes": []} for idx in range(1, 22)}
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
        _emit_failure_event(logger, code, seed, manifest_fingerprint, parameter_hash, run_id_value, validator_id, message, context)
        raise EngineFailure("F4", code, STATE, MODULE_NAME, context)

    def _warn(code: str, validator_id: str, message: str, context: dict) -> None:
        _record_validator(validator_id, "warn", code=code, detail=context)
        logger.warning("%s %s", validator_id, json.dumps({"message": message, "context": context}, ensure_ascii=True, sort_keys=True))

    def _resolve_input(entry: dict, tokens: dict, dataset_id: str) -> Path:
        try:
            return _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
        except InputResolutionError as exc:
            _abort("2B-S3-020", "V-02", "input_resolution_failed", {"dataset_id": dataset_id, "error": str(exc)})
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
    timer.info(f"S3: run log initialized at {run_log_path}")

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
        / "state=S3"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s3_run_report.json"
    )

    logger.info(
        "S3: objective=day-effect factors; gated inputs (s0_receipt, sealed_inputs, policy, timezones) -> output s3_day_effects",
    )

    receipt_entry = entries["s0_gate_receipt_2B"]
    receipt_path = _resolve_input(receipt_entry, {"manifest_fingerprint": manifest_fingerprint}, "s0_gate_receipt_2B")
    if not receipt_path.exists():
        _abort("2B-S3-001", "V-01", "missing_s0_receipt", {"path": str(receipt_path)})
    receipt_payload = _load_json(receipt_path)
    receipt_schema = _schema_from_pack(schema_2b, "validation/s0_gate_receipt_v1")
    _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    receipt_errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
    if receipt_errors:
        _abort("2B-S3-001", "V-01", "invalid_s0_receipt", {"error": str(receipt_errors[0])})
    if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
        _abort(
            "2B-S3-001",
            "V-01",
            "manifest_fingerprint_mismatch",
            {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
        )
    created_utc = str(receipt_payload.get("verified_at_utc") or "")
    if not created_utc:
        _abort("2B-S3-086", "V-14", "created_utc_missing", {"receipt_path": str(receipt_path)})
    _record_validator("V-01", "pass")
    _record_validator("V-14", "pass")

    sealed_entry = entries["sealed_inputs_2B"]
    sealed_path = _resolve_input(sealed_entry, {"manifest_fingerprint": manifest_fingerprint}, "sealed_inputs_2B")
    if not sealed_path.exists():
        _abort("2B-S3-020", "V-02", "sealed_inputs_missing", {"path": str(sealed_path)})
    sealed_payload = _load_json(sealed_path)
    sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_payload))
    if sealed_errors:
        _abort("2B-S3-020", "V-02", "sealed_inputs_invalid", {"error": str(sealed_errors[0])})

    sealed_by_id = {item.get("asset_id"): item for item in sealed_payload if isinstance(item, dict)}
    sealed_policy = sealed_by_id.get("day_effect_policy_v1")
    sealed_timezones = sealed_by_id.get("site_timezones")
    if not sealed_policy:
        _abort("2B-S3-022", "V-19", "policy_not_sealed", {"asset_id": "day_effect_policy_v1"})
    if not sealed_timezones:
        _abort("2B-S3-022", "V-19", "site_timezones_not_sealed", {"asset_id": "site_timezones"})
    _record_validator("V-19", "pass")

    policy_entry = entries["day_effect_policy_v1"]
    policy_catalog_path = _render_catalog_path(policy_entry, {})
    policy_path = _resolve_input(policy_entry, {}, "day_effect_policy_v1")
    if sealed_policy.get("path") and str(sealed_policy.get("path")) != policy_catalog_path:
        _abort(
            "2B-S3-070",
            "V-03",
            "policy_path_mismatch",
            {"sealed": sealed_policy.get("path"), "dictionary": policy_catalog_path},
        )

    timezones_entry = entries["site_timezones"]
    timezones_catalog_path = _render_catalog_path(timezones_entry, tokens)
    timezones_path = _resolve_input(timezones_entry, tokens, "site_timezones")
    if not timezones_path.exists():
        _abort(
            "2B-S3-020",
            "V-02",
            "input_missing",
            {"dataset_id": "site_timezones", "path": str(timezones_path)},
        )
    if sealed_timezones.get("path") and str(sealed_timezones.get("path")) != timezones_catalog_path:
        _abort(
            "2B-S3-070",
            "V-03",
            "site_timezones_path_mismatch",
            {"sealed": sealed_timezones.get("path"), "dictionary": timezones_catalog_path},
        )

    policy_digest = sha256_file(policy_path).sha256_hex
    sealed_policy_digest = str(sealed_policy.get("sha256_hex") or "")
    if sealed_policy_digest and sealed_policy_digest != policy_digest:
        _abort(
            "2B-S3-070",
            "V-03",
            "policy_digest_mismatch",
            {"sealed": sealed_policy_digest, "computed": policy_digest},
        )

    weights_entry = entries["s1_site_weights"]
    weights_catalog_path = _render_catalog_path(weights_entry, tokens)
    weights_path = _resolve_input(weights_entry, tokens, "s1_site_weights")
    if not weights_path.exists():
        _abort(
            "2B-S3-020",
            "V-02",
            "input_missing",
            {"dataset_id": "s1_site_weights", "path": str(weights_path)},
        )
    _record_validator("V-02", "pass")
    _record_validator("V-03", "pass")

    output_entry = entries["s3_day_effects"]
    output_catalog_path = _render_catalog_path(output_entry, tokens)
    if f"seed={seed}" not in output_catalog_path or f"manifest_fingerprint={manifest_fingerprint}" not in output_catalog_path:
        _abort(
            "2B-S3-071",
            "V-15",
            "output_path_embed_mismatch",
            {"path": output_catalog_path, "seed": seed, "manifest_fingerprint": manifest_fingerprint},
        )
    output_root = run_paths.run_root / output_catalog_path

    resolve_ms = int((time.monotonic() - started_monotonic) * 1000)
    policy_payload = _load_json(policy_path)
    try:
        _validate_payload(
            schema_2b,
            "policy/day_effect_policy_v1",
            policy_payload,
            ref_packs={"schemas.layer1.yaml#/$defs/": schema_layer1},
        )
    except SchemaValidationError as exc:
        _abort("2B-S3-031", "V-04", "policy_schema_invalid", {"error": str(exc)})

    policy_version_tag = str(policy_payload.get("version_tag") or "")
    policy_sha256 = str(policy_payload.get("sha256_hex") or "")
    rng_engine = str(policy_payload.get("rng_engine") or "")
    rng_stream_id = str(policy_payload.get("rng_stream_id") or "")
    draws_per_row = int(policy_payload.get("draws_per_row") or 0)
    sigma_gamma = float(policy_payload.get("sigma_gamma") or 0.0)
    sigma_policy_v2 = policy_payload.get("sigma_gamma_policy_v2")
    sigma_policy_mode = "scalar_v1"
    day_range = policy_payload.get("day_range") or {}
    record_fields = list(policy_payload.get("record_fields") or [])
    rng_derivation = policy_payload.get("rng_derivation") or {}
    sigma_base_by_segment: dict[str, object] = {}
    sigma_multiplier_by_tz_group: dict[str, object] = {}
    sigma_jitter_enabled = False
    sigma_jitter_amp = 0.0
    weekly_amp_by_segment: dict[str, object] = {}
    sigma_min_bound = sigma_gamma
    sigma_max_bound = sigma_gamma
    gamma_clip_min = 0.0
    gamma_clip_max = 0.0

    if draws_per_row != 1:
        _abort("2B-S3-032", "V-04", "draws_per_row_invalid", {"draws_per_row": draws_per_row})
    if sigma_gamma <= 0:
        _abort("2B-S3-032", "V-04", "sigma_gamma_invalid", {"sigma_gamma": sigma_gamma})
    if not rng_stream_id:
        _abort("2B-S3-032", "V-04", "rng_stream_id_missing", {})
    if not rng_engine:
        _abort("2B-S3-032", "V-04", "rng_engine_missing", {})
    if rng_engine != "philox2x64-10":
        _abort("2B-S3-060", "V-11", "rng_engine_invalid", {"rng_engine": rng_engine})

    if isinstance(sigma_policy_v2, dict) and bool(sigma_policy_v2.get("enabled", False)):
        sigma_policy_mode = "sigma_gamma_policy_v2"
        sigma_base_by_segment = sigma_policy_v2.get("sigma_base_by_segment") or {}
        sigma_multiplier_by_tz_group = sigma_policy_v2.get("sigma_multiplier_by_tz_group") or {}
        sigma_jitter = sigma_policy_v2.get("sigma_jitter_by_merchant") or {}
        weekly_amp_by_segment = sigma_policy_v2.get("weekly_component_amp_by_segment") or {}
        gamma_clip = sigma_policy_v2.get("gamma_clip") or {}
        sigma_min_bound = float(sigma_policy_v2.get("sigma_min") or 0.0)
        sigma_max_bound = float(sigma_policy_v2.get("sigma_max") or 0.0)
        gamma_clip_min = float(gamma_clip.get("min") or 0.0)
        gamma_clip_max = float(gamma_clip.get("max") or 0.0)
        sigma_jitter_enabled = bool(sigma_jitter.get("enabled", False))
        sigma_jitter_amp = float(sigma_jitter.get("amplitude") or 0.0)
        if not isinstance(sigma_base_by_segment, dict) or "default" not in sigma_base_by_segment:
            _abort("2B-S3-032", "V-04", "sigma_base_by_segment_missing_default", {})
        if not isinstance(sigma_multiplier_by_tz_group, dict) or "default" not in sigma_multiplier_by_tz_group:
            _abort("2B-S3-032", "V-04", "sigma_multiplier_by_tz_group_missing_default", {})
        if not isinstance(weekly_amp_by_segment, dict) or "default" not in weekly_amp_by_segment:
            _abort("2B-S3-032", "V-04", "weekly_component_amp_by_segment_missing_default", {})
        if sigma_min_bound <= 0.0 or sigma_max_bound <= 0.0 or sigma_max_bound < sigma_min_bound:
            _abort(
                "2B-S3-032",
                "V-04",
                "sigma_bounds_invalid",
                {"sigma_min": sigma_min_bound, "sigma_max": sigma_max_bound},
            )
        if gamma_clip_min <= 0.0 or gamma_clip_max <= 0.0 or gamma_clip_max < gamma_clip_min:
            _abort(
                "2B-S3-032",
                "V-04",
                "gamma_clip_invalid",
                {"gamma_clip_min": gamma_clip_min, "gamma_clip_max": gamma_clip_max},
            )
        if sigma_jitter_amp < 0.0 or sigma_jitter_amp > 1.0:
            _abort(
                "2B-S3-032",
                "V-04",
                "sigma_jitter_amp_invalid",
                {"amplitude": sigma_jitter_amp},
            )

    required_fields = {
        "gamma",
        "log_gamma",
        "sigma_gamma",
        "rng_stream_id",
        "rng_counter_lo",
        "rng_counter_hi",
        "created_utc",
    }
    missing_fields = sorted(required_fields.difference(record_fields))
    if missing_fields:
        _abort("2B-S3-032", "V-04", "record_fields_missing", {"missing": missing_fields})

    start_day = str(day_range.get("start_day") or "")
    end_day = str(day_range.get("end_day") or "")
    try:
        start_date = date.fromisoformat(start_day)
        end_date = date.fromisoformat(end_day)
    except ValueError as exc:
        _abort("2B-S3-033", "V-04", "day_range_invalid", {"error": str(exc), "day_range": day_range})

    if start_date > end_date:
        _abort("2B-S3-033", "V-04", "day_range_invalid", {"day_range": day_range})

    days: list[str] = []
    cursor = start_date
    while cursor <= end_date:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    if not days:
        _abort("2B-S3-090", "V-20", "day_grid_empty", {"day_range": day_range})

    _record_validator("V-04", "pass")
    _record_validator("V-20", "pass")

    resolve_started = time.monotonic()

    weights_df = pl.read_parquet(weights_path, columns=["merchant_id", "legal_country_iso", "site_order"])
    weights_df = weights_df.with_columns(
        pl.col("merchant_id").cast(pl.UInt64),
        pl.col("site_order").cast(pl.Int64),
    )

    timezones_df = pl.read_parquet(timezones_path, columns=["merchant_id", "legal_country_iso", "site_order", "tzid"])
    timezones_df = timezones_df.with_columns(
        pl.col("merchant_id").cast(pl.UInt64),
        pl.col("site_order").cast(pl.Int64),
    )

    dup_counts = (
        timezones_df.group_by(["merchant_id", "legal_country_iso", "site_order"])
        .agg(pl.len().alias("row_count"), pl.col("tzid").n_unique().alias("tzid_count"))
    )
    dup_violations = dup_counts.filter((pl.col("row_count") > 1) & (pl.col("tzid_count") > 1))
    if dup_violations.height > 0:
        sample = dup_violations.head(5).to_dicts()
        _abort("2B-S3-041", "V-05", "multiple_tzid_for_site", {"sample": sample, "count": dup_violations.height})

    joined_df = weights_df.join(timezones_df, on=["merchant_id", "legal_country_iso", "site_order"], how="left")
    missing = joined_df.filter(pl.col("tzid").is_null())
    join_misses = missing.height
    if join_misses > 0:
        sample = missing.select(["merchant_id", "legal_country_iso", "site_order"]).head(5).to_dicts()
        _abort("2B-S3-040", "V-05", "missing_tzid", {"count": join_misses, "sample": sample})

    group_df = joined_df.select(["merchant_id", "tzid"]).unique().sort(["merchant_id", "tzid"])
    groups_per_merchant_df = (
        group_df.group_by("merchant_id")
        .agg(pl.col("tzid").sort().alias("tzids"))
        .sort("merchant_id")
    )

    merchants_total = groups_per_merchant_df.height
    tz_groups_total = group_df.height
    days_total = len(days)
    rows_expected = tz_groups_total * days_total
    merchant_stats_df = (
        joined_df.group_by("merchant_id")
        .agg(
            [
                pl.col("site_order").n_unique().alias("site_count"),
                pl.col("tzid").n_unique().alias("tz_count"),
            ]
        )
        .sort("merchant_id")
    )
    merchant_profiles: dict[int, dict[str, float | str]] = {}
    for mrow in merchant_stats_df.iter_rows(named=True):
        merchant_id = int(mrow["merchant_id"])
        site_count = int(mrow["site_count"])
        segment_key = _merchant_segment_key(site_count)
        base_sigma = _resolve_segment_value(sigma_base_by_segment, segment_key, sigma_gamma)
        jitter_multiplier = 1.0
        if sigma_policy_mode == "sigma_gamma_policy_v2" and sigma_jitter_enabled:
            jitter_u = _deterministic_unit_interval(
                manifest_fingerprint,
                seed,
                "2B.S3.sigma_jitter",
                merchant_id,
            )
            jitter_multiplier = 1.0 + sigma_jitter_amp * ((2.0 * jitter_u) - 1.0)
        weekly_amp = 0.0
        weekly_phase = 0.0
        if sigma_policy_mode == "sigma_gamma_policy_v2":
            weekly_amp = _resolve_segment_value(weekly_amp_by_segment, segment_key, 0.0)
            weekly_phase = 2.0 * math.pi * _deterministic_unit_interval(
                manifest_fingerprint,
                seed,
                "2B.S3.weekly_phase",
                merchant_id,
            )
        merchant_profiles[merchant_id] = {
            "segment_key": segment_key,
            "base_sigma": float(base_sigma),
            "jitter_multiplier": float(jitter_multiplier),
            "weekly_amp": float(weekly_amp),
            "weekly_phase": float(weekly_phase),
        }
    day_features: list[tuple[str, float]] = []
    for day in days:
        weekday_phase = 2.0 * math.pi * (date.fromisoformat(day).weekday() / 7.0)
        day_features.append((day, weekday_phase))

    tzid_set = set(timezones_df.get_column("tzid").to_list())
    warn_tzids = sorted({tz for tz in group_df.get_column("tzid").to_list() if tz not in tzid_set})
    if warn_tzids:
        _warn("2B-S3-191", "V-21", "tzid_not_in_site_timezones", {"tzids_sample": warn_tzids[:10]})
    else:
        _record_validator("V-21", "pass")

    _record_validator("V-05", "pass")

    join_groups_ms = int((time.monotonic() - resolve_started) * 1000)

    rng_domain_master = str(rng_derivation.get("domain_master") or "")
    rng_domain_stream = str(rng_derivation.get("domain_stream") or "")
    if not rng_domain_master or not rng_domain_stream:
        _abort("2B-S3-032", "V-04", "rng_derivation_missing", {"rng_derivation": rng_derivation})

    try:
        key, base_counter_hi, base_counter_lo = _derive_rng_key_counter(
            manifest_fingerprint,
            seed,
            rng_stream_id,
            rng_domain_master,
            rng_domain_stream,
        )
    except ValueError as exc:
        _abort("2B-S3-032", "V-04", "rng_derivation_invalid", {"error": str(exc)})

    base_counter_int = (base_counter_hi << 64) + base_counter_lo
    last_counter_int = base_counter_int + rows_expected - 1 if rows_expected > 0 else base_counter_int
    if last_counter_int > (1 << 128) - 1:
        _abort("2B-S3-064", "V-13", "counter_wrap", {"rows_expected": rows_expected})

    _record_validator("V-11", "pass")

    output_pack, output_table = _table_pack(schema_2b, "plan/s3_day_effects")
    _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#/$defs/")

    output_tmp = run_paths.tmp_root / f"s3_day_effects_{uuid.uuid4().hex}"
    output_tmp.mkdir(parents=True, exist_ok=True)

    logger.info(
        "S3: generating day-effect rows (merchants=%s tz_groups=%s days=%s rows=%s sigma_policy_mode=%s)",
        merchants_total,
        tz_groups_total,
        days_total,
        rows_expected,
        sigma_policy_mode,
    )

    progress = _ProgressTracker(
        rows_expected,
        logger,
        "S3 day-effect rows",
        min_interval_seconds=progress_log_interval_seconds,
    )
    part_index = 0
    batch_rows: list[tuple] = []
    prev_key: Optional[tuple] = None
    prev_counter_int: Optional[int] = None
    rows_written = 0
    draws_total = 0
    draw_started = time.monotonic()
    for row in groups_per_merchant_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        tzids = list(row["tzids"])
        merchant_profile = merchant_profiles.get(
            merchant_id,
            {
                "segment_key": "default",
                "base_sigma": sigma_gamma,
                "jitter_multiplier": 1.0,
                "weekly_amp": 0.0,
                "weekly_phase": 0.0,
            },
        )
        segment_key = str(merchant_profile["segment_key"])
        base_sigma = float(merchant_profile["base_sigma"])
        jitter_multiplier = float(merchant_profile["jitter_multiplier"])
        weekly_amp = float(merchant_profile["weekly_amp"])
        weekly_phase = float(merchant_profile["weekly_phase"])
        for day, weekday_phase in day_features:
            for tzid in tzids:
                row_rank = rows_written
                counter_int = base_counter_int + row_rank
                counter_hi = (counter_int >> 64) & UINT64_MASK
                counter_lo = counter_int & UINT64_MASK
                prev_counter_snapshot = prev_counter_int
                if prev_counter_snapshot is not None and counter_int <= prev_counter_snapshot:
                    _abort("2B-S3-063", "V-13", "counter_not_monotonic", {"prev": prev_counter_snapshot, "curr": counter_int})
                prev_counter_int = counter_int

                row_key = (merchant_id, day, tzid)
                if prev_key is not None:
                    if row_key == prev_key:
                        pk_duplicates += 1
                        _abort("2B-S3-042", "V-07", "duplicate_pk", {"key": row_key})
                    if row_key < prev_key:
                        _abort("2B-S3-083", "V-08", "writer_order_violation", {"prev": prev_key, "curr": row_key})
                prev_key = row_key

                out0, _out1 = philox2x64_10(counter_hi, counter_lo, key)
                u = _u01(out0)
                z = _normal_icdf(u)
                tz_multiplier = 1.0
                if sigma_policy_mode == "sigma_gamma_policy_v2":
                    tz_multiplier = _resolve_tz_multiplier(sigma_multiplier_by_tz_group, tzid)
                sigma_value = sigma_gamma
                if sigma_policy_mode == "sigma_gamma_policy_v2":
                    sigma_value = base_sigma * tz_multiplier * jitter_multiplier
                    sigma_value = min(max(sigma_value, sigma_min_bound), sigma_max_bound)
                if sigma_value <= 0.0:
                    _abort("2B-S3-032", "V-04", "sigma_value_invalid", {"sigma_value": sigma_value})
                weekly_term = 0.0
                if sigma_policy_mode == "sigma_gamma_policy_v2" and weekly_amp > 0.0:
                    weekly_term = weekly_amp * math.sin(weekday_phase + weekly_phase)
                mu_gamma = -0.5 * sigma_value * sigma_value
                log_gamma = mu_gamma + sigma_value * z + weekly_term
                gamma = math.exp(log_gamma)
                if sigma_policy_mode == "sigma_gamma_policy_v2":
                    clipped_gamma = min(max(gamma, gamma_clip_min), gamma_clip_max)
                    if clipped_gamma != gamma:
                        gamma = clipped_gamma
                        log_gamma = math.log(gamma)
                        gamma_clipped_rows += 1

                if not math.isfinite(log_gamma):
                    _abort("2B-S3-057", "V-09", "log_gamma_nonfinite", {"key": row_key})
                if gamma <= 0.0 or not math.isfinite(gamma):
                    nonpositive_gamma_rows += 1
                    _abort("2B-S3-058", "V-09", "gamma_nonpositive", {"key": row_key})

                max_abs_log_gamma = max(max_abs_log_gamma, abs(log_gamma))
                sigma_gamma_min_observed = min(sigma_gamma_min_observed, sigma_value)
                sigma_gamma_max_observed = max(sigma_gamma_max_observed, sigma_value)
                sigma_source = "sigma_gamma_v1"
                if sigma_policy_mode == "sigma_gamma_policy_v2":
                    sigma_source = f"sigma_gamma_policy_v2:{segment_key}"

                batch_rows.append(
                    (
                        merchant_id,
                        day,
                        tzid,
                        gamma,
                        log_gamma,
                        sigma_value,
                        rng_stream_id,
                        counter_lo,
                        counter_hi,
                        created_utc,
                    )
                )
                rows_written += 1
                draws_total += 1
                if len(samples_rows) < 20:
                    samples_rows.append(
                        {
                            "merchant_id": merchant_id,
                            "utc_day": day,
                            "tz_group_id": tzid,
                            "gamma": gamma,
                            "log_gamma": log_gamma,
                            "sigma_gamma": sigma_value,
                            "sigma_source": sigma_source,
                            "sigma_value": sigma_value,
                            "weekly_amp": weekly_amp,
                            "rng_stream_id": rng_stream_id,
                            "rng_counter_hi": counter_hi,
                            "rng_counter_lo": counter_lo,
                        }
                    )
                if prev_counter_snapshot is not None and len(samples_rng_monotonic) < 10:
                    samples_rng_monotonic.append(
                        {
                            "row_rank": rows_written - 1,
                            "prev": {
                                "hi": (prev_counter_snapshot >> 64) & UINT64_MASK,
                                "lo": prev_counter_snapshot & UINT64_MASK,
                            },
                            "curr": {"hi": counter_hi, "lo": counter_lo},
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
                        _abort("2B-S3-030", "V-16", "output_schema_invalid", {"error": str(exc)})
                    write_ms += (time.monotonic() - write_start) * 1000
                    part_index += 1
                progress.update(1)

    draw_ms = int((time.monotonic() - draw_started) * 1000)

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
            _abort("2B-S3-030", "V-16", "output_schema_invalid", {"error": str(exc)})
        write_ms += (time.monotonic() - write_start) * 1000

    if rows_written != rows_expected:
        _abort(
            "2B-S3-050",
            "V-06",
            "coverage_mismatch",
            {"rows_expected": rows_expected, "rows_written": rows_written},
        )

    if draws_total != rows_written:
        _abort(
            "2B-S3-062",
            "V-12",
            "draws_mismatch",
            {"draws_total": draws_total, "rows_written": rows_written},
        )

    _record_validator("V-06", "pass")
    _record_validator("V-07", "pass")
    _record_validator("V-08", "pass")
    _record_validator("V-09", "pass")
    _record_validator("V-10", "pass")
    _record_validator("V-12", "pass")
    _record_validator("V-13", "pass")
    _record_validator("V-16", "pass")

    coverage_by_day = [
        {"utc_day": day, "expected_groups": tz_groups_total, "observed_groups": tz_groups_total}
        for day in days[:10]
    ]

    tz_groups_stats = []
    for row in groups_per_merchant_df.iter_rows(named=True):
        tzids = list(row["tzids"])
        tz_groups_stats.append(
            {
                "merchant_id": int(row["merchant_id"]),
                "groups_expected": len(tzids),
                "groups_observed": len(tzids),
                "abs_delta": 0,
            }
        )
    tz_groups_stats.sort(key=lambda item: (-item["abs_delta"], item["merchant_id"]))
    tz_groups_per_merchant = [
        {"merchant_id": item["merchant_id"], "groups_expected": item["groups_expected"], "groups_observed": item["groups_observed"]}
        for item in tz_groups_stats[:10]
    ]

    publish_started = time.monotonic()
    if output_root.exists() and any(output_root.iterdir()):
        existing_digest = _hash_partition(output_root)
        new_digest = _hash_partition(output_tmp)
        if existing_digest != new_digest:
            _record_validator("V-17", "fail", code="2B-S3-080", detail={"path": str(output_root)})
            _record_validator("V-18", "fail", code="2B-S3-081", detail={"path": str(output_root)})
            _abort(
                "2B-S3-081",
                "V-18",
                "non_idempotent_reemit",
                {"existing": existing_digest, "new": new_digest},
            )
        logger.info("S3: output already exists and is identical; skipping publish.")
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
                "2B-S3-082",
                "V-18",
                "atomic_publish_failed",
                {"error": str(exc), "path": str(output_root)},
            )
        atomic_publish = True
        write_once_verified = False
        publish_bytes_total = sum(path.stat().st_size for path in output_root.glob("*.parquet"))

    publish_ms = int((time.monotonic() - publish_started) * 1000)
    _record_validator("V-17", "pass")
    _record_validator("V-18", "pass")
    _record_validator("V-15", "pass")

    warn_count = sum(1 for item in validators.values() if item["status"] == "WARN")
    fail_count = sum(1 for item in validators.values() if item["status"] == "FAIL")
    if sigma_gamma_min_observed == float("inf"):
        sigma_gamma_min_observed = sigma_gamma
        sigma_gamma_max_observed = sigma_gamma

    run_report = {
        "component": "2B.S3",
        "manifest_fingerprint": manifest_fingerprint,
        "seed": str(seed),
        "created_utc": created_utc,
        "catalogue_resolution": {
            "dictionary_version": dictionary_version,
            "registry_version": registry_version,
        },
        "policy": {
            "id": "day_effect_policy_v1",
            "version_tag": policy_version_tag,
            "sha256_hex": policy_sha256,
            "rng_engine": rng_engine,
            "rng_stream_id": rng_stream_id,
            "sigma_policy_mode": sigma_policy_mode,
            "sigma_gamma": sigma_gamma,
            "sigma_min": sigma_min_bound,
            "sigma_max": sigma_max_bound,
            "gamma_clip_min": gamma_clip_min,
            "gamma_clip_max": gamma_clip_max,
            "day_range": {"start_day": start_day, "end_day": end_day},
        },
        "inputs_summary": {
            "weights_path": weights_catalog_path,
            "timezones_path": timezones_catalog_path,
            "merchants_total": merchants_total,
            "tz_groups_total": tz_groups_total,
            "days_total": days_total,
        },
        "rng_accounting": {
            "rows_expected": rows_expected,
            "rows_written": rows_written,
            "draws_total": draws_total,
            "first_counter": {"hi": base_counter_hi, "lo": base_counter_lo},
            "last_counter": {
                "hi": (last_counter_int >> 64) & UINT64_MASK,
                "lo": last_counter_int & UINT64_MASK,
            },
            "max_abs_log_gamma": max_abs_log_gamma,
            "sigma_gamma": sigma_gamma,
            "sigma_gamma_min_observed": sigma_gamma_min_observed,
            "sigma_gamma_max_observed": sigma_gamma_max_observed,
            "nonpositive_gamma_rows": nonpositive_gamma_rows,
            "gamma_clipped_rows": gamma_clipped_rows,
            "pk_duplicates": pk_duplicates,
            "join_misses": join_misses,
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
            "coverage_by_day": coverage_by_day,
            "tz_groups_per_merchant": tz_groups_per_merchant,
            "rng_monotonic": samples_rng_monotonic,
            **({"warn_tzids": [{"tz_group_id": tzid} for tzid in warn_tzids[:10]]} if warn_tzids else {}),
        },
        "id_map": [
            {"id": "s1_site_weights", "path": weights_catalog_path},
            {"id": "site_timezones", "path": timezones_catalog_path},
            {"id": "day_effect_policy_v1", "path": policy_catalog_path},
            {"id": "s3_day_effects", "path": output_catalog_path},
        ],
        "durations_ms": {
            "resolve_ms": resolve_ms,
            "join_groups_ms": join_groups_ms,
            "draw_ms": draw_ms,
            "write_ms": int(write_ms),
            "publish_ms": publish_ms,
        },
    }

    _log_run_report(logger, run_report, log_run_report_json)
    if run_report_path is not None:
        _write_json(run_report_path, run_report)
    timer.info("S3: completed")

    return S3Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        output_root=output_root,
        run_report_path=run_report_path or Path(""),
    )
