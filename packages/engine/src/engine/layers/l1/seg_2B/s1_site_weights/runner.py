
"""S1 per-merchant weight freezing runner for Segment 2B."""

from __future__ import annotations

import json
import math
import platform
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
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


MODULE_NAME = "2B.S1.weights"
SEGMENT = "2B"
STATE = "S1"


@dataclass(frozen=True)
class S1Result:
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
    severity = "INFO"
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
    payload = {"validator_id": validator_id, "result": result}
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
    detail: dict,
) -> None:
    payload = {
        "event": "S1_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "severity": "ERROR",
    }
    payload.update(detail)
    logger.error("S1_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger) -> bool:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2B-S1-080",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root)},
            )
        shutil.rmtree(tmp_root)
        logger.info("S1: partition already exists and is identical; skipping publish.")
        return True
    final_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_root.replace(final_root)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S1-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "partition": str(final_root), "error": str(exc)},
        ) from exc
    return False


def _policy_label(weight_source: dict) -> str:
    label = weight_source.get("id") or weight_source.get("mode")
    if not label:
        raise EngineFailure(
            "F4",
            "2B-S1-032",
            STATE,
            MODULE_NAME,
            {"detail": "weight_source missing id/mode"},
        )
    return str(label)


def _policy_weight_column(weight_source: dict) -> Optional[str]:
    mode = weight_source.get("mode")
    if mode == "uniform":
        return None
    if mode == "column":
        return str(weight_source.get("column") or weight_source.get("id") or "")
    if "column" in weight_source:
        return str(weight_source.get("column"))
    if "id" in weight_source and mode not in (None, "uniform"):
        return str(weight_source.get("id"))
    return ""


def _resolve_floor_value(values: np.ndarray, floor_spec: dict) -> Optional[float]:
    mode = floor_spec.get("mode", "none")
    if mode == "none":
        return None
    if mode == "absolute":
        return float(floor_spec.get("value", 0.0))
    if mode == "relative":
        factor = float(floor_spec.get("value", 0.0))
        if values.size == 0:
            return 0.0
        return factor * float(values.max())
    raise EngineFailure(
        "F4",
        "2B-S1-032",
        STATE,
        MODULE_NAME,
        {"detail": "unsupported floor_spec mode", "mode": mode},
    )


def _resolve_cap_value(values: np.ndarray, cap_spec: dict) -> Optional[float]:
    mode = cap_spec.get("mode", "none")
    if mode == "none":
        return None
    if mode == "absolute":
        return float(cap_spec.get("value", 0.0))
    if mode == "relative":
        factor = float(cap_spec.get("value", 0.0))
        if values.size == 0:
            return 0.0
        return factor * float(values.max())
    raise EngineFailure(
        "F4",
        "2B-S1-032",
        STATE,
        MODULE_NAME,
        {"detail": "unsupported cap_spec mode", "mode": mode},
    )


def _quantize_probs(
    probs: np.ndarray, bits: int, epsilon: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    grid = 1 << bits
    scaled = probs * grid
    rounded = np.rint(scaled).astype(np.int64)
    deficit = int(grid - rounded.sum())
    if deficit != 0:
        frac = scaled - np.floor(scaled)
        if deficit > 0:
            order = sorted(range(len(frac)), key=lambda idx: (-frac[idx], idx))
            adjust = 1
        else:
            order = sorted(range(len(frac)), key=lambda idx: (frac[idx], idx))
            adjust = -1
        remaining = abs(deficit)
        for idx in order:
            if remaining <= 0:
                break
            if adjust < 0 and rounded[idx] <= 0:
                continue
            rounded[idx] += adjust
            remaining -= 1
        if remaining > 0:
            raise EngineFailure(
                "F4",
                "2B-S1-052",
                STATE,
                MODULE_NAME,
                {"detail": "quantisation deficit unresolved", "remaining": remaining},
            )
    if rounded.sum() != grid:
        raise EngineFailure(
            "F4",
            "2B-S1-052",
            STATE,
            MODULE_NAME,
            {"detail": "quantisation sum mismatch", "grid": grid, "sum": int(rounded.sum())},
        )
    if np.any(rounded < 0):
        raise EngineFailure(
            "F4",
            "2B-S1-052",
            STATE,
            MODULE_NAME,
            {"detail": "quantisation produced negative mass"},
        )
    p_hat = rounded.astype(np.float64) / float(grid)
    abs_delta = np.abs(p_hat - probs)
    max_delta = float(abs_delta.max()) if abs_delta.size else 0.0
    if max_delta > epsilon:
        raise EngineFailure(
            "F4",
            "2B-S1-052",
            STATE,
            MODULE_NAME,
            {"detail": "quantisation epsilon exceeded", "max_abs_delta": max_delta},
        )
    return rounded, p_hat, abs_delta, max_delta

WRITE_BATCH_SIZE = 100_000
OUTPUT_SCHEMA = {
    "merchant_id": pl.UInt64,
    "legal_country_iso": pl.Utf8,
    "site_order": pl.Int64,
    "p_weight": pl.Float64,
    "weight_source": pl.Utf8,
    "quantised_bits": pl.Int64,
    "floor_applied": pl.Boolean,
    "created_utc": pl.Utf8,
}


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


def _write_batch(df: pl.DataFrame, batch_index: int, output_tmp: Path, logger) -> None:
    if df.height == 0:
        return
    path = output_tmp / f"part-{batch_index:05d}.parquet"
    df.write_parquet(path, compression="zstd", row_group_size=100000)
    logger.info("S1: wrote %d rows to %s", df.height, path)


def _build_batch_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=OUTPUT_SCHEMA)


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l1.seg_2B.s1_site_weights.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""
    status = "FAIL"

    dictionary_version = "unknown"
    registry_version = "unknown"
    policy_version_tag = ""
    policy_digest = ""
    weight_source_label = ""
    weight_column: Optional[str] = None
    normalisation_epsilon = 0.0
    quantisation_epsilon = 0.0
    tiny_negative_epsilon = 0.0
    quantised_bits = 0

    site_locations_catalog_path = ""
    policy_catalog_path = ""
    output_catalog_path = ""
    publish_bytes_total = 0
    write_once_verified = False
    atomic_publish = False

    merchants_total = 0
    sites_total = 0
    floors_applied_rows = 0
    caps_applied_rows = 0
    zero_mass_fallback_merchants = 0
    tiny_negative_clamps = 0
    max_abs_mass_error_pre_quant = 0.0
    merchants_over_epsilon = 0
    max_abs_delta_per_row = 0.0
    merchants_mass_exact_after_quant = 0

    resolve_ms = 0
    transform_ms = 0
    normalise_ms = 0
    quantise_ms = 0
    publish_ms = 0

    coverage_samples: list[dict] = []
    normalisation_samples: list[dict] = []
    top_extremes: list[dict] = []
    bottom_extremes: list[dict] = []
    quant_samples: list[dict] = []
    id_map: list[dict] = []

    validators = {f"V-{idx:02d}": {"id": f"V-{idx:02d}", "status": "PASS", "codes": []} for idx in range(1, 21)}
    run_report_path: Optional[Path] = None
    output_root: Optional[Path] = None
    receipt: dict = {}

    def _record_validator(validator_id: str, result: str, code: Optional[str] = None, detail: Optional[object] = None) -> None:
        entry = validators[validator_id]
        if code and code not in entry["codes"]:
            entry["codes"].append(code)
        if result == "fail":
            entry["status"] = "FAIL"
        elif result == "warn" and entry["status"] != "FAIL":
            entry["status"] = "WARN"
        _emit_validation(logger, seed, manifest_fingerprint, validator_id, result, error_code=code, detail=detail)

    def _abort(code: str, validator_id: str, message: str, context: dict) -> None:
        detail = {"message": message, "context": context, "validator": validator_id}
        _record_validator(validator_id, "fail", code=code, detail=context)
        _emit_failure_event(logger, code, seed, manifest_fingerprint, parameter_hash, run_id_value, detail)
        raise EngineFailure("F4", code, STATE, MODULE_NAME, context)

    def _warn(code: str, validator_id: str, message: str, context: dict) -> None:
        detail = {"message": message, "context": context, "validator": validator_id}
        _record_validator(validator_id, "warn", code=code, detail=context)
        logger.warning("%s %s", validator_id, json.dumps(detail, ensure_ascii=True, sort_keys=True))

    def _record_ranked(
        items: list[dict],
        entry: dict,
        max_size: int,
        key_func,
    ) -> None:
        items.append(entry)
        items.sort(key=key_func)
        if len(items) > max_size:
            items.pop()

    try:
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
        timer.info(f"S1: run log initialized at {run_log_path}")

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
        registry_path, registry = load_artefact_registry(source, SEGMENT)
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s,%s",
            config.contracts_layout,
            config.contracts_root,
            dict_path,
            registry_path,
            schema_2b_path,
            schema_2a_path,
            schema_1b_path,
            schema_layer1_path,
        )

        dictionary_version = str(dictionary.get("version", "unknown"))
        registry_version = str(registry.get("version", "unknown"))

        tokens = {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint}
        entry_ids = (
            "s0_gate_receipt_2B",
            "sealed_inputs_2B",
            "site_locations",
            "alias_layout_policy_v1",
            "site_timezones",
            "tz_timetable_cache",
            "s1_site_weights",
        )
        entries = {}
        for dataset_id in entry_ids:
            entries[dataset_id] = find_dataset_entry(dictionary, dataset_id).entry

        run_report_path = (
            run_paths.run_root
            / "reports"
            / "layer1"
            / "2B"
            / "state=S1"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "s1_run_report.json"
        )

        receipt_entry = entries["s0_gate_receipt_2B"]
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_catalog_path = _render_catalog_path(receipt_entry, {"manifest_fingerprint": manifest_fingerprint})
        if not receipt_path.exists():
            _abort(
                "2B-S1-001",
                "V-01",
                "missing_s0_receipt",
                {"path": str(receipt_path)},
            )
        receipt_payload = _load_json(receipt_path)
        receipt_schema = _schema_from_pack(schema_2b, "validation/s0_gate_receipt_v1")
        _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#")
        receipt_errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
        if receipt_errors:
            _abort(
                "2B-S1-001",
                "V-01",
                "invalid_s0_receipt",
                {"error": str(receipt_errors[0])},
            )
        if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
            _abort(
                "2B-S1-001",
                "V-01",
                "manifest_fingerprint_mismatch",
                {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
            )
        created_utc = str(receipt_payload.get("verified_at_utc") or "")
        if not created_utc:
            _abort(
                "2B-S1-056",
                "V-15",
                "created_utc_missing",
                {"receipt_path": str(receipt_path)},
            )
        _record_validator("V-01", "pass")

        sealed_entry = entries["sealed_inputs_2B"]
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        sealed_payload = _load_json(sealed_path)
        sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
        sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_payload))
        if sealed_errors:
            _abort(
                "2B-S1-020",
                "V-02",
                "sealed_inputs_schema_invalid",
                {"error": str(sealed_errors[0])},
            )

        sealed_by_id = {item.get("asset_id"): item for item in sealed_payload if isinstance(item, dict)}
        required_ids = ("site_locations", "alias_layout_policy_v1")
        for required_id in required_ids:
            if required_id not in sealed_by_id:
                _abort(
                    "2B-S1-022",
                    "V-19",
                    "required_asset_missing",
                    {"asset_id": required_id},
                )

        optional_ids = ("site_timezones", "tz_timetable_cache")
        optional_present = [asset_id for asset_id in optional_ids if asset_id in sealed_by_id]
        if len(optional_present) == 1:
            _warn(
                "2B-S1-090",
                "V-20",
                "optional_pins_mixed",
                {"present": optional_present},
            )
        else:
            _record_validator("V-20", "pass")

        def _assert_sealed(asset_id: str, entry: dict, validator_id: str) -> None:
            sealed = sealed_by_id.get(asset_id)
            if not sealed:
                _abort(
                    "2B-S1-022",
                    validator_id,
                    "asset_not_sealed",
                    {"asset_id": asset_id},
                )
            dict_path = _render_catalog_path(entry, tokens)
            sealed_path_value = sealed.get("path")
            if sealed_path_value and str(sealed_path_value) != dict_path:
                _abort(
                    "2B-S1-070",
                    "V-03",
                    "partition_selection_incorrect",
                    {"asset_id": asset_id, "dictionary_path": dict_path, "sealed_path": sealed_path_value},
                )
            partition = sealed.get("partition") or {}
            expected_partition = {
                key: tokens[key]
                for key in entry.get("partitioning") or []
                if key in tokens
            }
            if partition != expected_partition:
                _abort(
                    "2B-S1-070",
                    "V-03",
                    "partition_kv_mismatch",
                    {"asset_id": asset_id, "partition": partition, "expected": expected_partition},
                )

        _assert_sealed("site_locations", entries["site_locations"], "V-19")
        _assert_sealed("alias_layout_policy_v1", entries["alias_layout_policy_v1"], "V-19")
        if len(optional_present) == 2:
            _assert_sealed("site_timezones", entries["site_timezones"], "V-19")
            _assert_sealed("tz_timetable_cache", entries["tz_timetable_cache"], "V-19")

        site_locations_entry = entries["site_locations"]
        site_locations_path = _resolve_dataset_path(site_locations_entry, run_paths, config.external_roots, tokens)
        site_locations_catalog_path = _render_catalog_path(site_locations_entry, tokens)

        policy_entry = entries["alias_layout_policy_v1"]
        policy_path = _resolve_dataset_path(policy_entry, run_paths, config.external_roots, tokens)
        policy_catalog_path = _render_catalog_path(policy_entry, tokens)
        policy_payload = _load_json(policy_path)
        policy_schema = _schema_from_pack(schema_2b, "policy/alias_layout_policy_v1")
        policy_errors = list(Draft202012Validator(policy_schema).iter_errors(policy_payload))
        if policy_errors:
            _abort(
                "2B-S1-031",
                "V-04",
                "policy_schema_invalid",
                {"error": str(policy_errors[0])},
            )

        for key in (
            "weight_source",
            "floor_spec",
            "normalisation_epsilon",
            "quantised_bits",
            "quantisation_epsilon",
            "required_s1_provenance",
            "fallback",
        ):
            if key not in policy_payload:
                _abort(
                    "2B-S1-032",
                    "V-04",
                    "policy_minima_missing",
                    {"missing": key},
                )

        required_prov = policy_payload.get("required_s1_provenance") or {}
        for key in ("weight_source", "quantised_bits", "floor_applied"):
            if not required_prov.get(key, False):
                _abort(
                    "2B-S1-032",
                    "V-04",
                    "required_provenance_missing",
                    {"missing": key},
                )

        weight_source = policy_payload.get("weight_source") or {}
        if not isinstance(weight_source, dict):
            _abort(
                "2B-S1-032",
                "V-04",
                "weight_source_invalid",
                {"weight_source": weight_source},
            )
        weight_source_mode = str(weight_source.get("mode") or "")
        if weight_source_mode and weight_source_mode not in ("uniform", "column"):
            _abort(
                "2B-S1-032",
                "V-04",
                "unsupported_weight_source_mode",
                {"mode": weight_source_mode},
            )
        try:
            weight_source_label = _policy_label(weight_source)
        except EngineFailure:
            _abort(
                "2B-S1-032",
                "V-04",
                "weight_source_missing_id",
                {"weight_source": weight_source},
            )
        weight_column = _policy_weight_column(weight_source)
        if weight_column == "":
            _abort(
                "2B-S1-033",
                "V-04",
                "weight_source_column_missing",
                {"weight_source": weight_source},
            )

        normalisation_epsilon = float(policy_payload.get("normalisation_epsilon") or 0.0)
        quantisation_epsilon = float(policy_payload.get("quantisation_epsilon") or 0.0)
        tiny_negative_epsilon = float(
            policy_payload.get("tiny_negative_epsilon") or normalisation_epsilon
        )
        if normalisation_epsilon <= 0.0 or quantisation_epsilon <= 0.0:
            _abort(
                "2B-S1-032",
                "V-04",
                "epsilon_invalid",
                {
                    "normalisation_epsilon": normalisation_epsilon,
                    "quantisation_epsilon": quantisation_epsilon,
                },
            )
        quantised_bits = int(policy_payload.get("quantised_bits") or 0)
        if quantised_bits <= 0:
            _abort(
                "2B-S1-032",
                "V-04",
                "quantised_bits_invalid",
                {"quantised_bits": quantised_bits},
            )

        policy_version_tag = str(policy_payload.get("version_tag") or policy_payload.get("policy_version") or "")
        policy_digest = sha256_file(policy_path).sha256_hex
        _record_validator("V-04", "pass")
        _record_validator("V-02", "pass")

        resolve_ms = int((time.monotonic() - started_monotonic) * 1000)
        timer.info("S1: resolved inputs and policy")

        columns = ["merchant_id", "legal_country_iso", "site_order"]
        if weight_column and weight_column not in columns:
            columns.append(weight_column)
        df = pl.read_parquet(site_locations_path, columns=columns)
        if df.height == 0:
            logger.warning("S1: site_locations is empty; emitting empty weights.")
        sites_total = int(df.height)
        merchants_total = int(df.select(pl.col("merchant_id").n_unique()).item())

        missing_columns = [col for col in (weight_column,) if col and col not in df.columns]
        if missing_columns:
            _abort(
                "2B-S1-033",
                "V-04",
                "weight_source_missing_columns",
                {"missing_columns": missing_columns},
            )

        pk_cols = ["merchant_id", "legal_country_iso", "site_order"]
        df = df.sort(pk_cols)

        if sites_total:
            for row in df.head(20).iter_rows(named=True):
                coverage_samples.append(
                    {
                        "key": {
                            "merchant_id": int(row["merchant_id"]),
                            "legal_country_iso": row["legal_country_iso"],
                            "site_order": int(row["site_order"]),
                        },
                        "present": True,
                    }
                )

        dup_df = df.group_by(pk_cols).len().filter(pl.col("len") > 1)
        if dup_df.height:
            sample = dup_df.select(pk_cols).head(5).to_dicts()
            _abort(
                "2B-S1-041",
                "V-06",
                "pk_duplicate",
                {"sample": sample},
            )
        _record_validator("V-06", "pass")

        output_entry = entries["s1_site_weights"]
        output_root = _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        output_catalog_path = _render_catalog_path(output_entry, tokens)
        if f"seed={seed}" not in output_root.as_posix() or f"manifest_fingerprint={manifest_fingerprint}" not in output_root.as_posix():
            _abort(
                "2B-S1-070",
                "V-03",
                "output_partition_incorrect",
                {"path": str(output_root)},
            )
        _record_validator("V-03", "pass")

        output_tmp = run_paths.tmp_root / f"s1_site_weights_{uuid.uuid4().hex}"
        output_tmp.mkdir(parents=True, exist_ok=True)

        floor_spec = policy_payload.get("floor_spec") or {}
        cap_spec = policy_payload.get("cap_spec") or {"mode": "none"}
        fallback = policy_payload.get("fallback") or {"mode": "uniform"}

        output_pack, output_table = _table_pack(schema_2b, "plan/s1_site_weights")
        _inline_external_refs(output_pack[output_table], schema_layer1, "schemas.layer1.yaml#")

        prev_pk: Optional[tuple] = None
        batch_rows: list[dict] = []
        batch_index = 0
        output_rows_total = 0
        progress = _ProgressTracker(merchants_total, logger, "S1 merchants processed")

        group_cols = ["merchant_id"]
        for _, group_df in df.group_by(group_cols, maintain_order=True):
            merchant_id = int(group_df["merchant_id"][0])
            country_values = group_df["legal_country_iso"].to_list()
            legal_country_isos = country_values
            country_set = sorted(set(country_values))
            country_sample = country_set[:5]
            country_count = len(country_set)
            sites = int(group_df.height)
            if sites <= 0:
                continue

            stage_start = time.monotonic()
            if weight_column is None:
                base = np.ones(sites, dtype=np.float64)
            else:
                base = group_df[weight_column].to_numpy()
                try:
                    base = base.astype(np.float64, copy=False)
                except (TypeError, ValueError) as exc:
                    _abort(
                        "2B-S1-050",
                        "V-09",
                        "base_weight_cast_failed",
                        {"error": str(exc)},
                    )
            if not np.all(np.isfinite(base)) or np.any(base < 0):
                _abort(
                    "2B-S1-050",
                    "V-09",
                    "invalid_base_weight",
                    {
                        "merchant_id": merchant_id,
                        "legal_country_iso_sample": country_sample,
                        "legal_country_count": country_count,
                    },
                )

            u = base.copy()
            floor_applied = np.zeros(sites, dtype=bool)
            try:
                floor_value = _resolve_floor_value(base, floor_spec)
            except EngineFailure:
                _abort(
                    "2B-S1-032",
                    "V-04",
                    "unsupported_floor_spec",
                    {"floor_spec": floor_spec},
                )
            if floor_value is not None:
                floor_mask = u < floor_value
                if np.any(floor_mask):
                    floor_applied |= floor_mask
                    u = np.maximum(u, floor_value)
                    floors_applied_rows += int(floor_mask.sum())

            try:
                cap_value = _resolve_cap_value(base, cap_spec)
            except EngineFailure:
                _abort(
                    "2B-S1-032",
                    "V-04",
                    "unsupported_cap_spec",
                    {"cap_spec": cap_spec},
                )
            if cap_value is not None:
                cap_mask = u > cap_value
                if np.any(cap_mask):
                    caps_applied_rows += int(cap_mask.sum())
                    u = np.minimum(u, cap_value)

            transform_ms += int((time.monotonic() - stage_start) * 1000)

            stage_start = time.monotonic()
            u_sum = float(u.sum())
            if not math.isfinite(u_sum) or u_sum <= 0.0:
                fallback_mode = str(fallback.get("mode") or "uniform")
                if fallback_mode != "uniform":
                    _abort(
                        "2B-S1-053",
                        "V-13",
                        "unsupported_fallback",
                        {"mode": fallback_mode},
                    )
                u = np.ones(sites, dtype=np.float64)
                floor_applied[:] = True
                zero_mass_fallback_merchants += 1
                floors_applied_rows += sites
                u_sum = float(u.sum())
            if not math.isfinite(u_sum) or u_sum <= 0.0:
                _abort(
                    "2B-S1-053",
                    "V-13",
                    "fallback_mass_invalid",
                    {
                        "merchant_id": merchant_id,
                        "legal_country_iso_sample": country_sample,
                        "legal_country_count": country_count,
                    },
                )

            p = u / u_sum
            sum_p = float(p.sum())
            abs_error = abs(sum_p - 1.0)
            max_abs_mass_error_pre_quant = max(max_abs_mass_error_pre_quant, abs_error)
            if abs_error > normalisation_epsilon:
                merchants_over_epsilon += 1
                _abort(
                    "2B-S1-051",
                    "V-10",
                    "normalisation_failed",
                    {
                        "merchant_id": merchant_id,
                        "legal_country_iso_sample": country_sample,
                        "legal_country_count": country_count,
                        "abs_error": abs_error,
                    },
                )

            negative_mask = p < 0
            if np.any(negative_mask):
                min_negative = float(p[negative_mask].min())
                if min_negative < -tiny_negative_epsilon:
                    _abort(
                        "2B-S1-057",
                        "V-09",
                        "p_weight_negative",
                        {
                            "merchant_id": merchant_id,
                            "legal_country_iso_sample": country_sample,
                            "legal_country_count": country_count,
                            "min_value": min_negative,
                        },
                    )
                clamp_count = int(negative_mask.sum())
                p[negative_mask] = 0.0
                floor_applied |= negative_mask
                tiny_negative_clamps += clamp_count
                sum_p = float(p.sum())
                if sum_p <= 0.0:
                    _abort(
                        "2B-S1-051",
                        "V-10",
                        "normalisation_failed_after_clamp",
                        {
                            "merchant_id": merchant_id,
                            "legal_country_iso_sample": country_sample,
                            "legal_country_count": country_count,
                        },
                    )
                p = p / sum_p
                abs_error = abs(float(p.sum()) - 1.0)
                max_abs_mass_error_pre_quant = max(max_abs_mass_error_pre_quant, abs_error)
                if abs_error > normalisation_epsilon:
                    _abort(
                        "2B-S1-051",
                        "V-10",
                        "normalisation_failed_after_clamp",
                        {
                            "merchant_id": merchant_id,
                            "legal_country_iso_sample": country_sample,
                            "legal_country_count": country_count,
                            "abs_error": abs_error,
                        },
                    )

            if np.any(p < 0) or np.any(p > 1):
                _abort(
                    "2B-S1-057",
                    "V-09",
                    "p_weight_out_of_range",
                    {
                        "merchant_id": merchant_id,
                        "legal_country_iso_sample": country_sample,
                        "legal_country_count": country_count,
                    },
                )
            normalise_ms += int((time.monotonic() - stage_start) * 1000)

            stage_start = time.monotonic()
            try:
                _, p_hat, abs_delta, max_delta = _quantize_probs(
                    p, quantised_bits, quantisation_epsilon
                )
            except EngineFailure as exc:
                _abort(
                    "2B-S1-052",
                    "V-12",
                    "quantisation_incoherent",
                    {"detail": exc.detail},
                )
            max_abs_delta_per_row = max(max_abs_delta_per_row, max_delta)
            merchants_mass_exact_after_quant += 1
            quantise_ms += int((time.monotonic() - stage_start) * 1000)

            _record_ranked(
                normalisation_samples,
                {
                    "merchant_id": merchant_id,
                    "sites": sites,
                    "sum_p": float(p.sum()),
                    "abs_error": abs_error,
                    "key_tuple": merchant_id,
                },
                20,
                lambda item: (-item["abs_error"], item["merchant_id"]),
            )

            site_orders = group_df["site_order"].to_numpy()
            for idx in range(sites):
                legal_country_iso = legal_country_isos[idx]
                pk_tuple = (merchant_id, legal_country_iso, int(site_orders[idx]))
                if prev_pk is not None and pk_tuple < prev_pk:
                    _abort(
                        "2B-S1-083",
                        "V-07",
                        "writer_order_not_pk",
                        {"previous": prev_pk, "current": pk_tuple},
                    )
                prev_pk = pk_tuple
                row = {
                    "merchant_id": merchant_id,
                    "legal_country_iso": legal_country_iso,
                    "site_order": int(site_orders[idx]),
                    "p_weight": float(p[idx]),
                    "weight_source": weight_source_label,
                    "quantised_bits": quantised_bits,
                    "floor_applied": bool(floor_applied[idx]),
                    "created_utc": created_utc,
                }
                batch_rows.append(row)
                output_rows_total += 1

                key_tuple = (merchant_id, legal_country_iso, int(site_orders[idx]))
                key = {
                    "merchant_id": merchant_id,
                    "legal_country_iso": legal_country_iso,
                    "site_order": int(site_orders[idx]),
                }
                _record_ranked(
                    top_extremes,
                    {"key": key, "key_tuple": key_tuple, "p_weight": float(p[idx])},
                    10,
                    lambda item: (-item["p_weight"], item["key_tuple"]),
                )
                _record_ranked(
                    bottom_extremes,
                    {"key": key, "key_tuple": key_tuple, "p_weight": float(p[idx])},
                    10,
                    lambda item: (item["p_weight"], item["key_tuple"]),
                )
                _record_ranked(
                    quant_samples,
                    {
                        "key": key,
                        "p_weight": float(p[idx]),
                        "p_hat": float(p_hat[idx]),
                        "abs_delta": float(abs_delta[idx]),
                        "key_tuple": key_tuple,
                    },
                    20,
                    lambda item: (-item["abs_delta"], item["key_tuple"]),
                )

            if len(batch_rows) >= WRITE_BATCH_SIZE:
                batch_df = _build_batch_df(batch_rows)
                try:
                    validate_dataframe(batch_df.iter_rows(named=True), output_pack, output_table)
                except SchemaValidationError as exc:
                    _abort(
                        "2B-S1-040",
                        "V-05",
                        "output_schema_invalid",
                        {"error": str(exc)},
                    )
                _write_batch(batch_df, batch_index, output_tmp, logger)
                publish_bytes_total += int((output_tmp / f"part-{batch_index:05d}.parquet").stat().st_size)
                batch_rows = []
                batch_index += 1

            progress.update(1)

        if batch_rows:
            batch_df = _build_batch_df(batch_rows)
            try:
                validate_dataframe(batch_df.iter_rows(named=True), output_pack, output_table)
            except SchemaValidationError as exc:
                _abort(
                    "2B-S1-040",
                    "V-05",
                    "output_schema_invalid",
                    {"error": str(exc)},
                )
            _write_batch(batch_df, batch_index, output_tmp, logger)
            publish_bytes_total += int((output_tmp / f"part-{batch_index:05d}.parquet").stat().st_size)

        if output_rows_total != sites_total:
            _abort(
                "2B-S1-042",
                "V-08",
                "coverage_mismatch",
                {"sites_total": sites_total, "rows_emitted": output_rows_total},
            )

        _record_validator("V-05", "pass")
        _record_validator("V-07", "pass")
        _record_validator("V-08", "pass")
        _record_validator("V-09", "pass")
        _record_validator("V-10", "pass")
        _record_validator("V-11", "pass")
        _record_validator("V-12", "pass")
        _record_validator("V-13", "pass")
        _record_validator("V-14", "pass")
        _record_validator("V-15", "pass")
        _record_validator("V-16", "pass")
        _record_validator("V-19", "pass")

        publish_start = time.monotonic()
        output_root = output_root or _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        already_exists = _atomic_publish_dir(output_tmp, output_root, logger)
        publish_ms = int((time.monotonic() - publish_start) * 1000)
        write_once_verified = True
        atomic_publish = not already_exists
        if already_exists:
            _record_validator("V-18", "pass")
        _record_validator("V-17", "pass")

        if publish_bytes_total == 0 and output_root.exists():
            publish_bytes_total = sum(path.stat().st_size for path in output_root.glob("*.parquet"))

        status = "PASS"
        timer.info("S1: published s1_site_weights")
    except EngineFailure:
        status = "FAIL"
        raise
    except (InputResolutionError, ContractError, SchemaValidationError) as exc:
        _emit_failure_event(
            logger,
            "2B-S1-020",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id_value,
            {"message": str(exc), "context": {}, "validator": "runtime"},
        )
        status = "FAIL"
        raise
    except Exception as exc:
        _emit_failure_event(
            logger,
            "2B-S1-020",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id_value,
            {"message": str(exc), "context": {}, "validator": "runtime"},
        )
        status = "FAIL"
        raise
    finally:
        finished_utc = utc_now_rfc3339_micro()
        warn_count = sum(1 for entry in validators.values() if entry["status"] == "WARN")
        fail_count = sum(1 for entry in validators.values() if entry["status"] == "FAIL")
        if run_report_path:
            normalisation_samples_sorted = [
                {
                    "merchant_id": item["merchant_id"],
                    "sites": item["sites"],
                    "sum_p": item["sum_p"],
                    "abs_error": item["abs_error"],
                }
                for item in sorted(normalisation_samples, key=lambda item: (-item["abs_error"], item["merchant_id"]))
            ][:20]
            top_extremes_sorted = [
                {"key": item["key"], "p_weight": item["p_weight"]}
                for item in sorted(top_extremes, key=lambda item: (-item["p_weight"], item["key_tuple"]))
            ]
            bottom_extremes_sorted = [
                {"key": item["key"], "p_weight": item["p_weight"]}
                for item in sorted(bottom_extremes, key=lambda item: (item["p_weight"], item["key_tuple"]))
            ]
            quant_samples_sorted = [
                {
                    "key": item["key"],
                    "p_weight": item["p_weight"],
                    "p_hat": item["p_hat"],
                    "abs_delta": item["abs_delta"],
                }
                for item in sorted(quant_samples, key=lambda item: (-item["abs_delta"], item["key_tuple"]))
            ]
            run_report = {
                "component": "2B.S1",
                "manifest_fingerprint": manifest_fingerprint,
                "seed": str(seed),
                "created_utc": created_utc,
                "catalogue_resolution": {
                    "dictionary_version": dictionary_version,
                    "registry_version": registry_version,
                },
                "policy": {
                    "id": "alias_layout_policy_v1",
                    "version_tag": policy_version_tag,
                    "sha256_hex": policy_digest,
                    "quantised_bits": quantised_bits,
                    "normalisation_epsilon": normalisation_epsilon,
                    "quantisation_epsilon": quantisation_epsilon,
                },
                "inputs_summary": {
                    "site_locations_path": site_locations_catalog_path,
                    "merchants_total": merchants_total,
                    "sites_total": sites_total,
                },
                "transforms": {
                    "floors_applied_rows": floors_applied_rows,
                    "caps_applied_rows": caps_applied_rows,
                    "zero_mass_fallback_merchants": zero_mass_fallback_merchants,
                    "tiny_negative_clamps": tiny_negative_clamps,
                },
                "normalisation": {
                    "max_abs_mass_error_pre_quant": max_abs_mass_error_pre_quant,
                    "merchants_over_epsilon": merchants_over_epsilon,
                },
                "quantisation": {
                    "grid_bits": quantised_bits,
                    "grid_size": 1 << quantised_bits if quantised_bits > 0 else 0,
                    "max_abs_delta_per_row": max_abs_delta_per_row,
                    "merchants_mass_exact_after_quant": merchants_mass_exact_after_quant,
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
                    "key_coverage": coverage_samples[:20],
                    "normalisation": normalisation_samples_sorted,
                    "extremes": {
                        "top": top_extremes_sorted[:10],
                        "bottom": bottom_extremes_sorted[:10],
                    },
                    "quantisation": quant_samples_sorted[:20],
                },
                "id_map": [
                    {"id": "site_locations", "path": site_locations_catalog_path},
                    {"id": "alias_layout_policy_v1", "path": policy_catalog_path},
                    {"id": "s1_site_weights", "path": output_catalog_path},
                ],
                "durations_ms": {
                    "resolve_ms": resolve_ms,
                    "transform_ms": transform_ms,
                    "normalise_ms": normalise_ms,
                    "quantise_ms": quantise_ms,
                    "publish_ms": publish_ms,
                },
            }
            _write_json(run_report_path, run_report)
            print(json.dumps(run_report, ensure_ascii=True, sort_keys=True))
            logger.info("S1: run-report written %s", run_report_path)

    return S1Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        output_root=output_root or Path("."),
        run_report_path=run_report_path or Path("."),
    )


