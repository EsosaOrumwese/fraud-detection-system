
"""S7 audit/CI gate runner for Segment 2B."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
from engine.core.errors import ContractError, EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s1_hurdle.rng import low64
from engine.layers.l1.seg_2B.s0_gate.runner import (
    _inline_external_refs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
)


MODULE_NAME = "2B.S7.audit"
SEGMENT = "2B"
STATE = "S7"

EPSILON = 1e-9
MAX_SAMPLE = 32


@dataclass(frozen=True)
class S7Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    audit_report_path: Path


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str, *args: object) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        if args:
            message = message % args
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
        "event": "S7_ERROR",
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
    logger.error("S7_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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


def _resolve_entries(dictionary: dict) -> dict[str, dict]:
    required_ids = (
        "s0_gate_receipt_2B",
        "sealed_inputs_2B",
        "s2_alias_index",
        "s2_alias_blob",
        "s3_day_effects",
        "s4_group_weights",
        "alias_layout_policy_v1",
        "route_rng_policy_v1",
        "virtual_edge_policy_v1",
        "rng_audit_log",
        "rng_trace_log",
        "rng_event_alias_pick_group",
        "rng_event_alias_pick_site",
        "rng_event_cdn_edge_pick",
        "s7_audit_report",
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


def _render_output_path(run_paths: RunPaths, catalog_path: str) -> Path:
    rendered = catalog_path
    if "*" in rendered:
        rendered = rendered.replace("*", "00000")
    return run_paths.run_root / rendered


def _glob_catalog_paths(run_paths: RunPaths, catalog_path: str) -> list[Path]:
    base = run_paths.run_root / catalog_path
    return sorted(base.parent.glob(base.name))


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


def _count_jsonl_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for _ in handle:
            count += 1
    return count


def _iter_jsonl_rows(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {line_no}: {exc}") from exc


def _resolve_jsonl_paths(run_paths: RunPaths, catalog_path: str) -> list[Path]:
    paths = _glob_catalog_paths(run_paths, catalog_path)
    if not paths:
        raise InputResolutionError(f"No jsonl files found for catalog path: {catalog_path}")
    return paths


def _prepare_row_schema(schema_pack: dict, schema_layer1: dict, path: str) -> dict:
    schema = _schema_from_pack(schema_pack, path)
    schema = normalize_nullable_schema(schema)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    return schema


def _decode_probabilities(prob: list[float], alias: list[int]) -> list[float]:
    count = len(prob)
    if count == 0:
        return []
    p_hat = [value / float(count) for value in prob]
    residual = [(1.0 - value) / float(count) for value in prob]
    for idx, target in enumerate(alias):
        p_hat[int(target)] += residual[idx]
    return p_hat


def _unpack_u32(data: bytes, offset: int, endianness: str) -> int:
    fmt = "<I" if endianness == "little" else ">I"
    return struct.unpack_from(fmt, data, offset)[0]


def _site_id_from_key(merchant_id: int, legal_country_iso: str, site_order: int) -> int:
    payload = f"{merchant_id}:{legal_country_iso}:{site_order}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return low64(digest)


def _atomic_publish_file(
    tmp_path: Path,
    final_path: Path,
    logger,
    label: str,
) -> None:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2B-S7-502",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S7: %s already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S7-504",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(final_path), "error": str(exc)},
        ) from exc


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths

def run_s7(config: EngineConfig, run_id: Optional[str] = None) -> S7Result:
    logger = get_logger("engine.layers.l1.seg_2B.s7_audit.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""

    dictionary_version = "unknown"
    registry_version = "unknown"

    alias_decode_samples: list[dict] = []
    group_norm_samples: list[dict] = []
    log_samples: list[dict] = []

    merchants_total = 0
    groups_total = 0
    days_total = 0
    selections_checked = 0
    draws_expected = 0
    draws_observed = 0
    alias_decode_max_abs_delta = 0.0
    max_abs_mass_error_s4 = 0.0

    validators = {
        "V-01": {"id": "V-01", "status": "PASS", "codes": ["2B-S7-001"]},
        "V-02": {"id": "V-02", "status": "PASS", "codes": ["2B-S7-020", "2B-S7-021", "2B-S7-023"]},
        "V-03": {"id": "V-03", "status": "PASS", "codes": ["2B-S7-070"]},
        "V-04": {"id": "V-04", "status": "PASS", "codes": ["2B-S7-200", "2B-S7-201"]},
        "V-05": {"id": "V-05", "status": "PASS", "codes": ["2B-S7-202", "2B-S7-205"]},
        "V-06": {"id": "V-06", "status": "PASS", "codes": ["2B-S7-203", "2B-S7-204"]},
        "V-07": {"id": "V-07", "status": "PASS", "codes": ["2B-S7-206"]},
        "V-08": {"id": "V-08", "status": "PASS", "codes": ["2B-S7-300"]},
        "V-09": {"id": "V-09", "status": "PASS", "codes": ["2B-S7-301"]},
        "V-10": {"id": "V-10", "status": "PASS", "codes": ["2B-S7-302"]},
        "V-11": {"id": "V-11", "status": "PASS", "codes": ["2B-S7-303", "2B-S7-304"]},
        "V-12": {"id": "V-12", "status": "PASS", "codes": ["2B-S7-400", "2B-S7-401", "2B-S7-503"]},
        "V-13": {"id": "V-13", "status": "PASS", "codes": ["2B-S7-402", "2B-S7-403", "2B-S7-404", "2B-S7-405"]},
        "V-14": {"id": "V-14", "status": "PASS", "codes": ["2B-S7-402", "2B-S7-403", "2B-S7-404", "2B-S7-405"]},
        "V-15": {"id": "V-15", "status": "PASS", "codes": ["2B-S7-410", "2B-S7-411"]},
        "V-16": {"id": "V-16", "status": "PASS", "codes": ["2B-S7-402"]},
        "V-17": {"id": "V-17", "status": "PASS", "codes": ["2B-S7-500", "2B-S7-503"]},
        "V-18": {"id": "V-18", "status": "PASS", "codes": ["2B-S7-501", "2B-S7-502", "2B-S7-504"]},
    }

    def _record_validator(
        validator_id: str,
        result: str,
        code: Optional[str] = None,
        context: Optional[object] = None,
    ) -> None:
        entry = validators[validator_id]
        if result == "fail":
            entry["status"] = "FAIL"
        elif result == "warn" and entry["status"] != "FAIL":
            entry["status"] = "WARN"
        if code and code not in entry["codes"]:
            entry["codes"].append(code)
        if context is not None:
            entry["context"] = context
        _emit_validation(logger, seed, manifest_fingerprint, validator_id, result, error_code=code, detail=context)

    def _abort(code: str, validator_id: str, message: str, context: dict) -> None:
        _record_validator(validator_id, "fail", code=code, context=context)
        _emit_failure_event(
            logger,
            code,
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id_value,
            validator_id,
            message,
            context,
        )
        raise EngineFailure("F4", code, STATE, MODULE_NAME, context)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        raise InputResolutionError("run_receipt missing run_id.")
    seed = int(receipt.get("seed") or 0)
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S7: run log initialized at {run_log_path}")

    logger.info(
        "S7: objective=audit S2/S3/S4 integrity and optional routing logs; gated inputs "
        "(s0_receipt, sealed_inputs, policies, s2/s3/s4, optional s5/s6 logs + rng evidence) "
        "-> outputs (s7_audit_report + stdout run-report)"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    _dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    _registry_path, registry = load_artefact_registry(source, SEGMENT)
    _schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    _schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    _schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")

    dictionary_version = str(dictionary.get("version") or "unknown")
    registry_version = str(registry.get("version") or "unknown")

    entries = _resolve_entries(dictionary)
    selection_entry = None
    edge_log_entry = None
    site_timezones_entry = None
    try:
        selection_entry = find_dataset_entry(dictionary, "s5_selection_log").entry
    except KeyError:
        selection_entry = None
    try:
        edge_log_entry = find_dataset_entry(dictionary, "s6_edge_log").entry
    except KeyError:
        edge_log_entry = None
    try:
        site_timezones_entry = find_dataset_entry(load_dataset_dictionary(source, "2A")[1], "site_timezones").entry
    except KeyError:
        site_timezones_entry = None

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id_value,
    }

    try:
        receipt_entry = entries["s0_gate_receipt_2B"]
        receipt_path = _resolve_dataset_path(
            receipt_entry,
            run_paths,
            config.external_roots,
            {"manifest_fingerprint": manifest_fingerprint},
        )
        if not receipt_path.exists():
            _abort("2B-S7-001", "V-01", "s0_receipt_missing", {"path": str(receipt_path)})
        receipt_payload = _load_json(receipt_path)
        _validate_payload(
            schema_2b,
            "validation/s0_gate_receipt_v1",
            receipt_payload,
            {"schemas.layer1.yaml#/$defs/": schema_layer1},
        )
        if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
            _abort(
                "2B-S7-001",
                "V-01",
                "manifest_fingerprint_mismatch",
                {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
            )
        created_utc = str(receipt_payload.get("verified_at_utc") or "")
        if not created_utc:
            _abort("2B-S7-001", "V-01", "created_utc_missing", {"receipt_path": str(receipt_path)})
        timer.info("S7: S0 receipt verified; created_utc=%s", created_utc)
        _record_validator("V-01", "pass")
    except (ContractError, SchemaValidationError) as exc:
        _abort("2B-S7-001", "V-01", "s0_receipt_invalid", {"error": str(exc)})

    sealed_entry = entries["sealed_inputs_2B"]
    sealed_path = _resolve_dataset_path(
        sealed_entry,
        run_paths,
        config.external_roots,
        {"manifest_fingerprint": manifest_fingerprint},
    )
    if not sealed_path.exists():
        _abort("2B-S7-001", "V-01", "sealed_inputs_missing", {"path": str(sealed_path)})
    sealed_inputs = _load_json(sealed_path)
    sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_inputs))
    if sealed_errors:
        _abort("2B-S7-001", "V-01", "sealed_inputs_invalid", {"error": sealed_errors[0].message})

    sealed_by_id: dict[str, dict] = {}
    for item in sealed_inputs:
        if isinstance(item, dict) and item.get("asset_id"):
            sealed_by_id[str(item["asset_id"])] = item

    def _require_sealed_asset(
        asset_id: str,
        entry: dict,
        token_values: dict[str, str],
        require_partition: Optional[dict[str, str]],
        validator_id: str,
    ) -> tuple[Path, dict, str]:
        sealed = _find_sealed_asset(sealed_inputs, asset_id)
        if not sealed:
            _abort("2B-S7-020", validator_id, "sealed_asset_missing", {"asset_id": asset_id})
        catalog_path = _render_catalog_path(entry, token_values)
        sealed_path_value = str(sealed.get("path") or "")
        if sealed_path_value and sealed_path_value != catalog_path:
            _abort(
                "2B-S7-070",
                validator_id,
                "sealed_path_mismatch",
                {"asset_id": asset_id, "sealed": sealed_path_value, "dictionary": catalog_path},
            )
        partition = sealed.get("partition") or {}
        if require_partition is not None and partition != require_partition:
            _abort(
                "2B-S7-070",
                validator_id,
                "partition_mismatch",
                {"asset_id": asset_id, "sealed": partition, "expected": require_partition},
            )
        resolved = _resolve_dataset_path(entry, run_paths, config.external_roots, token_values)
        if not resolved.exists():
            _abort("2B-S7-020", validator_id, "required_asset_missing", {"asset_id": asset_id, "path": str(resolved)})
        digest = sha256_file(resolved).sha256_hex
        sealed_digest = str(sealed.get("sha256_hex") or "")
        if sealed_digest and sealed_digest != digest:
            _abort(
                "2B-S7-070",
                validator_id,
                "sealed_digest_mismatch",
                {"asset_id": asset_id, "sealed": sealed_digest, "computed": digest},
            )
        return resolved, sealed, catalog_path

    def _require_output_asset(
        asset_id: str,
        entry: dict,
        token_values: dict[str, str],
        validator_id: str,
    ) -> tuple[Path, str]:
        catalog_path = _render_catalog_path(entry, token_values)
        resolved = _resolve_dataset_path(entry, run_paths, config.external_roots, token_values)
        if not resolved.exists():
            _abort("2B-S7-020", validator_id, "required_asset_missing", {"asset_id": asset_id, "path": str(resolved)})
        return resolved, catalog_path

    alias_index_entry = entries["s2_alias_index"]
    alias_index_path, alias_index_catalog = _require_output_asset(
        "s2_alias_index",
        alias_index_entry,
        {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint},
        "V-03",
    )
    alias_blob_entry = entries["s2_alias_blob"]
    alias_blob_path, alias_blob_catalog = _require_output_asset(
        "s2_alias_blob",
        alias_blob_entry,
        {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint},
        "V-03",
    )
    s3_entry = entries["s3_day_effects"]
    s3_path, s3_catalog = _require_output_asset(
        "s3_day_effects",
        s3_entry,
        {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint},
        "V-03",
    )
    s4_entry = entries["s4_group_weights"]
    s4_path, s4_catalog = _require_output_asset(
        "s4_group_weights",
        s4_entry,
        {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint},
        "V-03",
    )
    alias_policy_entry = entries["alias_layout_policy_v1"]
    alias_policy_path, alias_policy_sealed, alias_policy_catalog = _require_sealed_asset(
        "alias_layout_policy_v1",
        alias_policy_entry,
        {},
        {},
        "V-03",
    )
    route_policy_entry = entries["route_rng_policy_v1"]
    route_policy_path, route_policy_sealed, route_policy_catalog = _require_sealed_asset(
        "route_rng_policy_v1",
        route_policy_entry,
        {},
        {},
        "V-03",
    )
    edge_policy_entry = entries["virtual_edge_policy_v1"]
    edge_policy_path, edge_policy_sealed, edge_policy_catalog = _require_sealed_asset(
        "virtual_edge_policy_v1",
        edge_policy_entry,
        {},
        {},
        "V-03",
    )

    _record_validator("V-02", "pass")
    _record_validator("V-03", "pass")
    timer.info("S7: sealed inputs resolved for policies; run-local outputs resolved for S2/S3/S4")

    alias_policy_payload = _load_json(alias_policy_path)
    alias_policy_schema = _schema_from_pack(schema_2b, "policy/alias_layout_policy_v1")
    _inline_external_refs(alias_policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    alias_policy_errors = list(Draft202012Validator(alias_policy_schema).iter_errors(alias_policy_payload))
    if alias_policy_errors:
        _abort("2B-S7-070", "V-03", "alias_policy_schema_invalid", {"error": alias_policy_errors[0].message})

    route_policy_payload = _load_json(route_policy_path)
    route_policy_schema = _schema_from_pack(schema_2b, "policy/route_rng_policy_v1")
    _inline_external_refs(route_policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    route_policy_errors = list(Draft202012Validator(route_policy_schema).iter_errors(route_policy_payload))
    if route_policy_errors:
        _abort("2B-S7-070", "V-03", "route_policy_schema_invalid", {"error": route_policy_errors[0].message})

    edge_policy_payload = _load_json(edge_policy_path)
    edge_policy_schema = _schema_from_pack(schema_2b, "policy/virtual_edge_policy_v1")
    _inline_external_refs(edge_policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    edge_policy_errors = list(Draft202012Validator(edge_policy_schema).iter_errors(edge_policy_payload))
    if edge_policy_errors:
        _abort("2B-S7-070", "V-03", "edge_policy_schema_invalid", {"error": edge_policy_errors[0].message})

    alias_policy_digest = str(alias_policy_sealed.get("sha256_hex") or "")
    policy_layout_version = str(alias_policy_payload.get("layout_version") or "")
    policy_endianness = str(alias_policy_payload.get("endianness") or "")
    policy_alignment_bytes = int(alias_policy_payload.get("alignment_bytes") or 0)
    policy_quantised_bits = int(alias_policy_payload.get("quantised_bits") or 0)
    quantisation_epsilon = float(alias_policy_payload.get("quantisation_epsilon") or 0.0)
    record_layout = alias_policy_payload.get("record_layout") or {}
    prob_qbits = int(record_layout.get("prob_qbits") or 0)
    if prob_qbits <= 0 or prob_qbits > 32:
        _abort(
            "2B-S7-205",
            "V-05",
            "prob_qbits_invalid",
            {"prob_qbits": prob_qbits},
        )

    index_payload = _load_json(alias_index_path)
    try:
        _validate_payload(
            schema_2b,
            "plan/s2_alias_index",
            index_payload,
            {"schemas.layer1.yaml#/$defs/": schema_layer1},
        )
    except SchemaValidationError as exc:
        _abort("2B-S7-200", "V-04", "alias_index_schema_invalid", {"error": str(exc)})
    _record_validator("V-04", "pass")

    if str(index_payload.get("policy_digest") or "") != alias_policy_digest:
        _abort(
            "2B-S7-202",
            "V-05",
            "policy_digest_mismatch",
            {"index": index_payload.get("policy_digest"), "sealed": alias_policy_digest},
        )
    if str(index_payload.get("layout_version") or "") != policy_layout_version:
        _abort(
            "2B-S7-202",
            "V-05",
            "layout_version_mismatch",
            {"index": index_payload.get("layout_version"), "policy": policy_layout_version},
        )
    if str(index_payload.get("endianness") or "") != policy_endianness:
        _abort(
            "2B-S7-202",
            "V-05",
            "endianness_mismatch",
            {"index": index_payload.get("endianness"), "policy": policy_endianness},
        )
    if int(index_payload.get("alignment_bytes") or 0) != policy_alignment_bytes:
        _abort(
            "2B-S7-202",
            "V-05",
            "alignment_mismatch",
            {"index": index_payload.get("alignment_bytes"), "policy": policy_alignment_bytes},
        )
    if int(index_payload.get("quantised_bits") or 0) != policy_quantised_bits:
        _abort(
            "2B-S7-205",
            "V-05",
            "bit_depth_mismatch",
            {"index": index_payload.get("quantised_bits"), "policy": policy_quantised_bits},
        )

    blob_sha256 = sha256_file(alias_blob_path).sha256_hex
    if str(index_payload.get("blob_sha256") or "") != blob_sha256:
        _abort(
            "2B-S7-202",
            "V-05",
            "blob_digest_mismatch",
            {"index": index_payload.get("blob_sha256"), "computed": blob_sha256},
        )
    _record_validator("V-05", "pass")

    blob_size_bytes = int(index_payload.get("blob_size_bytes") or 0)
    if alias_blob_path.stat().st_size != blob_size_bytes:
        _abort(
            "2B-S7-201",
            "V-04",
            "blob_size_mismatch",
            {"index": blob_size_bytes, "actual": alias_blob_path.stat().st_size},
        )

    merchants = list(index_payload.get("merchants") or [])
    merchants_total = len(merchants)
    if int(index_payload.get("merchants_count") or 0) != merchants_total:
        _abort(
            "2B-S7-200",
            "V-04",
            "merchants_count_mismatch",
            {"index": index_payload.get("merchants_count"), "actual": merchants_total},
        )

    offset_rows = sorted(merchants, key=lambda row: int(row.get("offset") or 0))
    prev_end = 0
    for row in offset_rows:
        offset = int(row.get("offset") or 0)
        length = int(row.get("length") or 0)
        if policy_alignment_bytes and offset % policy_alignment_bytes != 0:
            _abort(
                "2B-S7-204",
                "V-06",
                "alignment_error",
                {"merchant_id": row.get("merchant_id"), "offset": offset, "alignment_bytes": policy_alignment_bytes},
            )
        if offset < prev_end:
            _abort(
                "2B-S7-203",
                "V-06",
                "offset_overlap",
                {"merchant_id": row.get("merchant_id"), "offset": offset, "prev_end": prev_end},
            )
        if offset + length > blob_size_bytes:
            _abort(
                "2B-S7-203",
                "V-06",
                "offset_out_of_bounds",
                {"merchant_id": row.get("merchant_id"), "offset": offset, "length": length, "blob_size": blob_size_bytes},
            )
        if int(row.get("quantised_bits") or 0) != policy_quantised_bits:
            _abort(
                "2B-S7-205",
                "V-05",
                "row_bit_depth_mismatch",
                {"merchant_id": row.get("merchant_id"), "row": row.get("quantised_bits"), "policy": policy_quantised_bits},
            )
        prev_end = max(prev_end, offset + length)
    _record_validator("V-06", "pass")

    sample_rows = sorted(merchants, key=lambda row: int(row.get("merchant_id") or 0))[:MAX_SAMPLE]
    with alias_blob_path.open("rb") as handle:
        progress = _ProgressTracker(len(sample_rows), logger, "S7 alias decode sample")
        for row in sample_rows:
            merchant_id = int(row.get("merchant_id") or 0)
            offset = int(row.get("offset") or 0)
            sites = int(row.get("sites") or 0)
            slice_len = 16 + 8 * sites
            handle.seek(offset)
            slice_bytes = handle.read(slice_len)
            if len(slice_bytes) != slice_len:
                _abort(
                    "2B-S7-201",
                    "V-04",
                    "slice_truncated",
                    {"merchant_id": merchant_id, "expected": slice_len, "actual": len(slice_bytes)},
                )
            checksum = hashlib.sha256(slice_bytes).hexdigest()
            if checksum != str(row.get("checksum") or ""):
                _abort(
                    "2B-S7-201",
                    "V-04",
                    "slice_checksum_mismatch",
                    {"merchant_id": merchant_id, "row_checksum": row.get("checksum"), "computed": checksum},
                )
            endianness = policy_endianness or str(index_payload.get("endianness") or "")
            header_sites = _unpack_u32(slice_bytes, 0, endianness)
            header_qbits = _unpack_u32(slice_bytes, 4, endianness)
            if header_sites != sites:
                _abort(
                    "2B-S7-201",
                    "V-04",
                    "slice_header_sites_mismatch",
                    {"merchant_id": merchant_id, "header": header_sites, "row": sites},
                )
            if header_qbits != prob_qbits:
                _abort(
                    "2B-S7-205",
                    "V-05",
                    "slice_header_qbits_mismatch",
                    {"merchant_id": merchant_id, "header": header_qbits, "policy": prob_qbits},
                )
            prob_q: list[int] = []
            alias: list[int] = []
            offset_cursor = 16
            for _ in range(sites):
                prob_q.append(_unpack_u32(slice_bytes, offset_cursor, endianness))
                alias.append(_unpack_u32(slice_bytes, offset_cursor + 4, endianness))
                offset_cursor += 8
            if any(idx >= sites for idx in alias):
                _abort(
                    "2B-S7-206",
                    "V-07",
                    "alias_index_out_of_range",
                    {"merchant_id": merchant_id, "sites": sites},
                )
            q_scale = float(1 << prob_qbits)
            prob = [value / q_scale for value in prob_q]
            p_hat = _decode_probabilities(prob, alias)
            sum_p = float(sum(p_hat))
            abs_delta = abs(sum_p - 1.0)
            alias_decode_max_abs_delta = max(alias_decode_max_abs_delta, abs_delta)
            if abs_delta > quantisation_epsilon:
                _abort(
                    "2B-S7-206",
                    "V-07",
                    "alias_decode_incoherent",
                    {"merchant_id": merchant_id, "sum_p_hat": sum_p, "epsilon": quantisation_epsilon},
                )
            alias_decode_samples.append(
                {"merchant_id": merchant_id, "max_abs_delta": abs_delta, "sum_p_hat": sum_p}
            )
            progress.update(1)
    _record_validator("V-07", "pass")
    timer.info("S7: alias index/blob integrity checks complete (sampled merchants=%s)", len(sample_rows))

    s3_paths = _list_parquet_paths(s3_path)
    s4_paths = _list_parquet_paths(s4_path)
    s3_scan = pl.scan_parquet(s3_paths).select(
        ["merchant_id", "utc_day", "tz_group_id", "gamma"]
    )
    s4_scan = pl.scan_parquet(s4_paths).select(
        ["merchant_id", "utc_day", "tz_group_id", "p_group", "gamma", "base_share"]
    )

    s3_keys = s3_scan.select(["merchant_id", "utc_day", "tz_group_id"]).unique()
    s4_keys = s4_scan.select(["merchant_id", "utc_day", "tz_group_id"]).unique()
    missing_in_s4 = s3_keys.join(s4_keys, on=["merchant_id", "utc_day", "tz_group_id"], how="anti")
    missing_in_s3 = s4_keys.join(s3_keys, on=["merchant_id", "utc_day", "tz_group_id"], how="anti")
    missing_s4_rows = missing_in_s4.collect()
    missing_s3_rows = missing_in_s3.collect()
    if missing_s4_rows.height or missing_s3_rows.height:
        _abort(
            "2B-S7-300",
            "V-08",
            "day_grid_mismatch",
            {
                "missing_in_s4": missing_s4_rows.head(5).to_dicts(),
                "missing_in_s3": missing_s3_rows.head(5).to_dicts(),
            },
        )
    _record_validator("V-08", "pass")

    joined = s4_scan.join(
        s3_scan,
        on=["merchant_id", "utc_day", "tz_group_id"],
        how="inner",
        suffix="_s3",
    )
    gamma_mismatch = joined.filter(pl.col("gamma") != pl.col("gamma_s3")).limit(5).collect()
    if gamma_mismatch.height:
        _abort(
            "2B-S7-301",
            "V-09",
            "gamma_echo_mismatch",
            {"samples": gamma_mismatch.to_dicts()},
        )
    _record_validator("V-09", "pass")

    mass = s4_scan.group_by(["merchant_id", "utc_day"]).agg(
        sum_p_group=pl.col("p_group").sum()
    )
    mass_df = mass.collect()
    if mass_df.height:
        mass_df = mass_df.with_columns((pl.col("sum_p_group") - 1.0).abs().alias("abs_error"))
        max_abs_mass_error_s4 = float(mass_df["abs_error"].max())
        bad_mass = mass_df.filter(pl.col("abs_error") > EPSILON)
        if bad_mass.height:
            _abort(
                "2B-S7-302",
                "V-10",
                "s4_normalisation_failed",
                {"samples": bad_mass.head(5).to_dicts()},
            )
        _record_validator("V-10", "pass")
        group_norm_samples = (
            mass_df.sort(["merchant_id", "utc_day"]).head(MAX_SAMPLE).to_dicts()
        )
    else:
        _record_validator("V-10", "pass")

    if "s1_site_weights" in sealed_by_id:
        if "base_share" not in s4_scan.columns:
            _abort(
                "2B-S7-303",
                "V-11",
                "base_share_missing",
                {"note": "s1_site_weights sealed but s4 base_share absent"},
            )
        base_mass = s4_scan.group_by("merchant_id").agg(sum_base=pl.col("base_share").sum())
        base_df = base_mass.collect()
        if base_df.height:
            base_df = base_df.with_columns((pl.col("sum_base") - 1.0).abs().alias("abs_error"))
            bad_base = base_df.filter(pl.col("abs_error") > EPSILON)
            if bad_base.height:
                _abort(
                    "2B-S7-304",
                    "V-11",
                    "base_share_incoherent",
                    {"samples": bad_base.head(5).to_dicts()},
                )
        _record_validator("V-11", "pass")
    else:
        _record_validator("V-11", "pass", context={"note": "s1_site_weights not sealed; base_share check skipped"})

    merchants_total = int(s4_scan.select(pl.col("merchant_id").n_unique()).collect()[0, 0])
    groups_total = int(s4_scan.select(pl.col("tz_group_id").n_unique()).collect()[0, 0])
    days_total = int(s4_scan.select(pl.col("utc_day").n_unique()).collect()[0, 0])

    selection_log_paths: list[Path] = []
    edge_log_paths: list[Path] = []
    selection_log_present = False
    edge_log_present = False

    if selection_entry:
        base = (
            run_paths.run_root
            / "data"
            / "layer1"
            / "2B"
            / "s5_selection_log"
            / f"seed={seed}"
            / f"parameter_hash={parameter_hash}"
            / f"run_id={run_id_value}"
        )
        if base.exists():
            selection_log_paths = sorted(base.glob("utc_day=*/selection_log.jsonl"))
            selection_log_present = bool(selection_log_paths)

    if edge_log_entry:
        base = (
            run_paths.run_root
            / "logs"
            / "layer1"
            / "2B"
            / "edge"
            / f"seed={seed}"
            / f"parameter_hash={parameter_hash}"
            / f"run_id={run_id_value}"
        )
        if base.exists():
            edge_log_paths = sorted(base.glob("utc_day=*/s6_edge_log.jsonl"))
            edge_log_present = bool(edge_log_paths)

    route_stream = route_policy_payload.get("streams", {}).get("routing_selection", {})
    edge_stream = route_policy_payload.get("streams", {}).get("routing_edge", {})
    routing_stream_id = str(route_stream.get("rng_stream_id") or "")
    edge_stream_id = str(edge_stream.get("rng_stream_id") or "")

    selection_schema = _prepare_row_schema(schema_2b, schema_layer1, "trace/s5_selection_log_row")
    edge_log_schema = _prepare_row_schema(schema_2b, schema_layer1, "trace/s6_edge_log_row")
    selection_validator = Draft202012Validator(selection_schema)
    edge_log_validator = Draft202012Validator(edge_log_schema)

    selection_sample_rows: list[dict] = []
    edge_sample_rows: list[dict] = []

    if selection_log_present:
        logger.info("S7: validating S5 selection logs (ordering, lineage, stream id)")
        total_rows = sum(_count_jsonl_rows(path) for path in selection_log_paths)
        selections_checked = total_rows
        progress = _ProgressTracker(total_rows, logger, "S7 selection log audit")
        last_ts: Optional[str] = None
        for path in selection_log_paths:
            utc_day = path.parent.name.split("utc_day=")[-1]
            try:
                for row in _iter_jsonl_rows(path):
                    errors = list(selection_validator.iter_errors(row))
                    if errors:
                        _abort("2B-S7-400", "V-12", "selection_log_schema_invalid", {"error": errors[0].message})
                    if str(row.get("manifest_fingerprint")) != manifest_fingerprint or str(row.get("created_utc")) != created_utc:
                        _abort(
                            "2B-S7-503",
                            "V-12",
                            "selection_log_embed_mismatch",
                            {"row_manifest": row.get("manifest_fingerprint"), "created_utc": row.get("created_utc")},
                        )
                    if str(row.get("rng_stream_id") or "") != routing_stream_id:
                        _abort(
                            "2B-S7-405",
                            "V-13",
                            "selection_log_stream_mismatch",
                            {"rng_stream_id": row.get("rng_stream_id"), "expected": routing_stream_id},
                        )
                    timestamp = str(row.get("utc_timestamp") or "")
                    if last_ts and timestamp < last_ts:
                        _abort(
                            "2B-S7-401",
                            "V-12",
                            "selection_log_order_violation",
                            {"utc_day": utc_day, "prev": last_ts, "current": timestamp},
                        )
                    last_ts = timestamp
                    if len(selection_sample_rows) < MAX_SAMPLE:
                        selection_sample_rows.append(row)
                    progress.update(1)
            except ValueError as exc:
                _abort("2B-S7-400", "V-12", "selection_log_json_invalid", {"error": str(exc)})
        _record_validator("V-12", "pass")
        _record_validator("V-13", "pass")
    else:
        _record_validator("V-12", "pass", context={"note": "s5_selection_log absent; skipped"})
        _record_validator("V-13", "pass", context={"note": "s5_selection_log absent; skipped"})

    virtual_total = 0
    if edge_log_present:
        logger.info("S7: validating S6 edge logs (ordering, lineage, attributes)")
        total_rows = sum(_count_jsonl_rows(path) for path in edge_log_paths)
        progress = _ProgressTracker(total_rows, logger, "S7 edge log audit")
        last_ts: Optional[str] = None
        for path in edge_log_paths:
            utc_day = path.parent.name.split("utc_day=")[-1]
            try:
                for row in _iter_jsonl_rows(path):
                    errors = list(edge_log_validator.iter_errors(row))
                    if errors:
                        _abort("2B-S7-400", "V-12", "edge_log_schema_invalid", {"error": errors[0].message})
                    if str(row.get("manifest_fingerprint")) != manifest_fingerprint or str(row.get("created_utc")) != created_utc:
                        _abort(
                            "2B-S7-503",
                            "V-12",
                            "edge_log_embed_mismatch",
                            {"row_manifest": row.get("manifest_fingerprint"), "created_utc": row.get("created_utc")},
                        )
                    if str(row.get("rng_stream_id") or "") != edge_stream_id:
                        _abort(
                            "2B-S7-405",
                            "V-14",
                            "edge_log_stream_mismatch",
                            {"rng_stream_id": row.get("rng_stream_id"), "expected": edge_stream_id},
                        )
                    timestamp = str(row.get("utc_timestamp") or "")
                    if last_ts and timestamp < last_ts:
                        _abort(
                            "2B-S7-401",
                            "V-12",
                            "edge_log_order_violation",
                            {"utc_day": utc_day, "prev": last_ts, "current": timestamp},
                        )
                    last_ts = timestamp
                    virtual_total += 1 if bool(row.get("is_virtual")) else 0
                    if len(edge_sample_rows) < MAX_SAMPLE:
                        edge_sample_rows.append(row)
                    progress.update(1)
            except ValueError as exc:
                _abort("2B-S7-400", "V-12", "edge_log_json_invalid", {"error": str(exc)})
        _record_validator("V-12", "pass")
        _record_validator("V-14", "pass")
    else:
        _record_validator("V-12", "pass", context={"note": "s6_edge_log absent; skipped"})
        _record_validator("V-14", "pass", context={"note": "s6_edge_log absent; skipped"})

    rng_evidence_required = selection_log_present or edge_log_present
    draws_expected = 0
    if selection_log_present:
        draws_expected += selections_checked * 2
    if edge_log_present:
        draws_expected += virtual_total

    def _scan_event_log(
        paths: list[Path],
        event_validator: Draft202012Validator,
        label: str,
        expected_stream_id: str,
        validator_id: str,
    ) -> int:
        total_rows = sum(_count_jsonl_rows(path) for path in paths)
        progress = _ProgressTracker(total_rows, logger, f"S7 {label} events")
        count = 0
        last_after: Optional[tuple[int, int]] = None
        for path in paths:
            try:
                for row in _iter_jsonl_rows(path):
                    errors = list(event_validator.iter_errors(row))
                    if errors:
                        _abort(
                            "2B-S7-402",
                            validator_id,
                            "rng_event_schema_invalid",
                            {"error": errors[0].message, "label": label},
                        )
                    if str(row.get("rng_stream_id") or "") != expected_stream_id:
                        _abort(
                            "2B-S7-405",
                            validator_id,
                            "rng_stream_misconfigured",
                            {"rng_stream_id": row.get("rng_stream_id"), "expected": expected_stream_id},
                        )
                    if str(row.get("substream_label") or "") != label:
                        _abort(
                            "2B-S7-405",
                            validator_id,
                            "rng_stream_misconfigured",
                            {"substream_label": row.get("substream_label"), "expected": label},
                        )
                    draws = int(row.get("draws") or 0)
                    blocks = int(row.get("blocks") or 0)
                    if draws != 1 or blocks != 1:
                        _abort(
                            "2B-S7-402",
                            validator_id,
                            "rng_draws_mismatch",
                            {"draws": draws, "blocks": blocks, "label": label},
                        )
                    before = (int(row.get("rng_counter_before_hi") or 0), int(row.get("rng_counter_before_lo") or 0))
                    after = (int(row.get("rng_counter_after_hi") or 0), int(row.get("rng_counter_after_lo") or 0))
                    if after < before:
                        _abort(
                            "2B-S7-404",
                            validator_id,
                            "rng_counter_wrap",
                            {"before": list(before), "after": list(after)},
                        )
                    if after == before:
                        _abort(
                            "2B-S7-403",
                            validator_id,
                            "rng_counter_not_monotone",
                            {"before": list(before), "after": list(after)},
                        )
                    if last_after is not None and after <= last_after:
                        _abort(
                            "2B-S7-403",
                            validator_id,
                            "rng_counter_not_monotone",
                            {"prev_after": list(last_after), "after": list(after)},
                        )
                    last_after = after
                    count += 1
                    progress.update(1)
            except ValueError as exc:
                _abort(
                    "2B-S7-402",
                    validator_id,
                    "rng_event_json_invalid",
                    {"error": str(exc), "label": label},
                )
        return count

    if rng_evidence_required:
        logger.info("S7: reconciling RNG evidence logs (events + trace)")
        audit_entry = entries["rng_audit_log"]
        audit_catalog = _render_catalog_path(audit_entry, tokens)
        try:
            audit_paths = _resolve_jsonl_paths(run_paths, audit_catalog)
        except InputResolutionError as exc:
            _abort("2B-S7-402", "V-16", "rng_audit_log_missing", {"error": str(exc)})
        audit_schema = _schema_from_pack(schema_layer1, "rng/core/rng_audit_log/record")
        audit_validator = Draft202012Validator(audit_schema)
        audit_rows = 0
        for path in audit_paths:
            try:
                for row in _iter_jsonl_rows(path):
                    audit_rows += 1
                    errors = list(audit_validator.iter_errors(row))
                    if errors:
                        _abort(
                            "2B-S7-402",
                            "V-16",
                            "rng_audit_log_invalid",
                            {"error": errors[0].message},
                        )
                    if str(row.get("run_id") or "") != run_id_value or int(row.get("seed") or 0) != seed:
                        _abort(
                            "2B-S7-503",
                            "V-16",
                            "rng_audit_log_embed_mismatch",
                            {"run_id": row.get("run_id"), "seed": row.get("seed")},
                        )
            except ValueError as exc:
                _abort("2B-S7-402", "V-16", "rng_audit_log_json_invalid", {"error": str(exc)})
        if audit_rows == 0:
            _abort("2B-S7-402", "V-16", "rng_audit_log_missing", {"path": str(audit_paths[0])})

        trace_entry = entries["rng_trace_log"]
        trace_catalog = _render_catalog_path(trace_entry, tokens)
        try:
            trace_paths = _resolve_jsonl_paths(run_paths, trace_catalog)
        except InputResolutionError as exc:
            _abort("2B-S7-402", "V-16", "rng_trace_log_missing", {"error": str(exc)})
        trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
        trace_validator = Draft202012Validator(trace_schema)
        trace_totals: dict[tuple[str, str], dict[str, int]] = {}
        for path in trace_paths:
            try:
                for row in _iter_jsonl_rows(path):
                    errors = list(trace_validator.iter_errors(row))
                    if errors:
                        _abort(
                            "2B-S7-402",
                            "V-16",
                            "rng_trace_log_invalid",
                            {"error": errors[0].message},
                        )
                    key = (str(row.get("module") or ""), str(row.get("substream_label") or ""))
                    trace_totals[key] = {
                        "draws_total": int(row.get("draws_total") or 0),
                        "events_total": int(row.get("events_total") or 0),
                    }
            except ValueError as exc:
                _abort("2B-S7-402", "V-16", "rng_trace_log_json_invalid", {"error": str(exc)})

        event_group_schema = _schema_from_pack(schema_layer1, "rng/events/alias_pick_group")
        event_site_schema = _schema_from_pack(schema_layer1, "rng/events/alias_pick_site")
        event_edge_schema = _schema_from_pack(schema_layer1, "rng/events/cdn_edge_pick")
        event_group_validator = Draft202012Validator(event_group_schema)
        event_site_validator = Draft202012Validator(event_site_schema)
        event_edge_validator = Draft202012Validator(event_edge_schema)

        group_events = 0
        site_events = 0
        edge_events = 0

        if selection_log_present:
            group_catalog = _render_catalog_path(entries["rng_event_alias_pick_group"], tokens)
            site_catalog = _render_catalog_path(entries["rng_event_alias_pick_site"], tokens)
            try:
                group_paths = _resolve_jsonl_paths(run_paths, group_catalog)
                site_paths = _resolve_jsonl_paths(run_paths, site_catalog)
            except InputResolutionError as exc:
                _abort("2B-S7-402", "V-13", "rng_event_missing", {"error": str(exc)})
            group_events = _scan_event_log(
                group_paths,
                event_group_validator,
                "alias_pick_group",
                routing_stream_id,
                "V-13",
            )
            site_events = _scan_event_log(
                site_paths,
                event_site_validator,
                "alias_pick_site",
                routing_stream_id,
                "V-13",
            )
            if group_events != selections_checked or site_events != selections_checked:
                _abort(
                    "2B-S7-402",
                    "V-13",
                    "rng_draws_mismatch",
                    {
                        "selections": selections_checked,
                        "group_events": group_events,
                        "site_events": site_events,
                    },
                )
            _record_validator("V-13", "pass", context={"selections": selections_checked})

        if edge_log_present:
            edge_catalog = _render_catalog_path(entries["rng_event_cdn_edge_pick"], tokens)
            try:
                edge_paths = _resolve_jsonl_paths(run_paths, edge_catalog)
            except InputResolutionError as exc:
                _abort("2B-S7-402", "V-14", "rng_event_missing", {"error": str(exc)})
            edge_events = _scan_event_log(
                edge_paths,
                event_edge_validator,
                "cdn_edge_pick",
                edge_stream_id,
                "V-14",
            )
            if edge_events != virtual_total:
                _abort(
                    "2B-S7-402",
                    "V-14",
                    "rng_draws_mismatch",
                    {"virtual_total": virtual_total, "edge_events": edge_events},
                )
            _record_validator("V-14", "pass", context={"virtual_total": virtual_total})

        def _trace_totals_for(key: tuple[str, str], expected_events: int) -> int:
            totals = trace_totals.get(key)
            if totals is None:
                _abort("2B-S7-402", "V-16", "rng_trace_missing", {"substream": list(key)})
            if totals["draws_total"] != expected_events or totals["events_total"] != expected_events:
                _abort(
                    "2B-S7-402",
                    "V-16",
                    "rng_trace_totals_mismatch",
                    {"substream": list(key), "totals": totals, "expected": expected_events},
                )
            return totals["draws_total"]

        draws_observed = 0
        if selection_log_present:
            draws_observed += _trace_totals_for(("2B.S5.router", "alias_pick_group"), group_events)
            draws_observed += _trace_totals_for(("2B.S5.router", "alias_pick_site"), site_events)
        if edge_log_present:
            draws_observed += _trace_totals_for(("2B.S6.edge_router", "cdn_edge_pick"), edge_events)

        if draws_observed != draws_expected:
            _abort(
                "2B-S7-402",
                "V-16",
                "rng_draws_mismatch",
                {"draws_expected": draws_expected, "draws_observed": draws_observed},
            )
        _record_validator("V-16", "pass", context={"draws_expected": draws_expected, "draws_observed": draws_observed})
    else:
        _record_validator("V-16", "pass", context={"note": "rng evidence skipped; logs absent"})

    if selection_sample_rows:
        if not site_timezones_entry:
            _abort("2B-S7-410", "V-15", "site_timezones_missing", {})
        tz_path = _resolve_dataset_path(
            site_timezones_entry,
            run_paths,
            config.external_roots,
            {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint},
        )
        tz_paths = _list_parquet_paths(tz_path)
        tz_df = pl.read_parquet(
            tz_paths,
            columns=["merchant_id", "legal_country_iso", "site_order", "tzid"],
        )
        tz_index: dict[tuple[int, int], str] = {}
        for row in tz_df.iter_rows(named=True):
            site_id = _site_id_from_key(
                int(row["merchant_id"]),
                str(row["legal_country_iso"]),
                int(row["site_order"]),
            )
            tz_index[(int(row["merchant_id"]), site_id)] = str(row["tzid"])
        for sample in selection_sample_rows:
            merchant_id = int(sample["merchant_id"])
            site_id = int(sample["site_id"])
            tz_group_id = str(sample["tz_group_id"])
            tz_lookup = tz_index.get((merchant_id, site_id))
            if tz_lookup != tz_group_id:
                _abort(
                    "2B-S7-410",
                    "V-15",
                    "group_site_mismatch",
                    {"merchant_id": merchant_id, "site_id": site_id, "expected": tz_lookup, "actual": tz_group_id},
                )

    if edge_sample_rows:
        edge_map: dict[str, dict] = {}
        for edge in edge_policy_payload.get("edges", []) or []:
            edge_map[str(edge.get("edge_id"))] = edge
        for edge in edge_policy_payload.get("default_edges", []) or []:
            edge_id = str(edge.get("edge_id"))
            edge_map.setdefault(edge_id, edge)
        for overrides in (edge_policy_payload.get("merchant_overrides") or {}).values():
            for edge in overrides or []:
                edge_id = str(edge.get("edge_id"))
                edge_map.setdefault(edge_id, edge)
        for sample in edge_sample_rows:
            edge_id = str(sample.get("edge_id") or "")
            if edge_id not in edge_map:
                _abort(
                    "2B-S7-411",
                    "V-15",
                    "edge_attr_missing",
                    {"edge_id": edge_id},
                )

    _record_validator(
        "V-15",
        "pass",
        context={
            "selection_samples": selection_sample_rows[:5],
            "edge_samples": edge_sample_rows[:5],
        }
        if selection_sample_rows or edge_sample_rows
        else {"note": "no selection/edge samples available"},
    )

    inputs_digest: dict[str, object] = {}
    for asset_id in (
        "s2_alias_index",
        "s2_alias_blob",
        "s3_day_effects",
        "s4_group_weights",
        "alias_layout_policy_v1",
        "route_rng_policy_v1",
        "virtual_edge_policy_v1",
    ):
        if asset_id in sealed_by_id:
            inputs_digest[asset_id] = sealed_by_id[asset_id]

    checks = []
    warn_count = 0
    fail_count = 0
    for validator_id in sorted(validators.keys()):
        entry = validators[validator_id]
        status = entry["status"]
        if status == "WARN":
            warn_count += 1
        if status == "FAIL":
            fail_count += 1
        check = {"id": entry["id"], "status": status, "codes": entry["codes"]}
        if "context" in entry:
            check["context"] = entry["context"]
        checks.append(check)

    overall_status = "FAIL" if fail_count else "PASS"
    audit_report = {
        "component": "2B.S7",
        "manifest_fingerprint": manifest_fingerprint,
        "seed": seed,
        "created_utc": created_utc,
        "catalogue_resolution": {
            "dictionary_version": dictionary_version,
            "registry_version": registry_version,
        },
        "inputs_digest": inputs_digest,
        "checks": checks,
        "metrics": {
            "merchants_total": int(merchants_total),
            "groups_total": int(groups_total),
            "days_total": int(days_total),
            "selections_checked": int(selections_checked),
            "draws_expected": int(draws_expected),
            "draws_observed": int(draws_observed),
            "alias_decode_max_abs_delta": float(alias_decode_max_abs_delta),
            "max_abs_mass_error_s4": float(max_abs_mass_error_s4),
        },
        "summary": {"overall_status": overall_status, "warn_count": warn_count, "fail_count": fail_count},
    }

    audit_schema = _schema_from_pack(schema_2b, "validation/s7_audit_report_v1")
    _inline_external_refs(audit_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    audit_errors = list(Draft202012Validator(audit_schema).iter_errors(audit_report))
    if audit_errors:
        _abort("2B-S7-500", "V-17", "audit_report_schema_invalid", {"error": audit_errors[0].message})
    _record_validator("V-17", "pass")

    audit_catalog = _render_catalog_path(entries["s7_audit_report"], tokens)
    audit_path = _render_output_path(run_paths, audit_catalog)
    tmp_path = run_paths.tmp_root / f"_tmp.s7_audit_{uuid.uuid4().hex}.json"
    _write_json(tmp_path, audit_report)
    _atomic_publish_file(tmp_path, audit_path, logger, "s7_audit_report")
    _record_validator("V-18", "pass")

    run_report = {
        "event": "S7_RUN_REPORT",
        "segment": SEGMENT,
        "state": STATE,
        "run_id": run_id_value,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "summary": audit_report["summary"],
        "metrics": audit_report["metrics"],
    }
    logger.info("S7_RUN_REPORT %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))

    timer.info("S7: completed audit report (status=%s)", overall_status)
    return S7Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        audit_report_path=audit_path,
    )
