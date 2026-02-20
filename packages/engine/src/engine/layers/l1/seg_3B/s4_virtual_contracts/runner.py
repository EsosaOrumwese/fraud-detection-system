"""S4 virtual routing semantics & validation contracts for Segment 3B."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import find_artifact_entry, find_dataset_entry, load_artefact_registry, load_dataset_dictionary
from engine.contracts.loader import load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
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


MODULE_NAME = "3B.S4.virtual_contracts"
SEGMENT = "3B"
STATE = "S4"


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    routing_policy_path: Path
    validation_contract_path: Path
    run_summary_path: Optional[Path]
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
    elif result == "pass":
        severity = "INFO"
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l1.seg_3B.s4_virtual_contracts.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


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


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E3B_S4_OUTPUT_INCONSISTENT_REWRITE",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink()
        logger.info("S4: %s already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)


def _atomic_publish_json(path: Path, payload: object, logger, label: str) -> None:
    payload_bytes = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing == payload_bytes:
            logger.info("S4: %s already exists and is identical; skipping publish.", label)
            return
        raise EngineFailure(
            "F4",
            "E3B_S4_OUTPUT_INCONSISTENT_REWRITE",
            STATE,
            MODULE_NAME,
            {"detail": "non-identical output exists", "path": str(path), "label": label},
        )
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_bytes(payload_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "E3B_S4_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(path), "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _validate_parquet_rows(
    files: list[Path],
    schema_pack: dict,
    schema_layer1: dict,
    anchor: str,
    label: str,
    manifest_fingerprint: Optional[str],
) -> None:
    logger = get_logger("engine.layers.l1.seg_3B.s4_virtual_contracts.l2.runner")
    pack, table_name = _table_pack(schema_pack, anchor)
    _inline_external_refs(pack, schema_layer1, "schemas.layer1.yaml#")
    progress = _ProgressTracker(len(files), logger, f"S4: validate {label} files")
    for file_path in files:
        df = pl.read_parquet(file_path)
        try:
            validate_dataframe(df.iter_rows(named=True), pack, table_name)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S4_INPUT_SCHEMA_INVALID",
                "V-10",
                f"{label}_schema_invalid",
                {"error": str(exc), "path": str(file_path)},
                manifest_fingerprint,
            )
        progress.update(1)


def _build_test_id(test_type: str, scope: str, target_population: dict) -> str:
    payload = {"test_type": test_type, "scope": scope, "target_population": target_population}
    packed = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(packed).hexdigest()[:12]
    return f"{test_type}:{scope}:{digest}"


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l1.seg_3B.s4_virtual_contracts.l2.runner")
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
    current_phase = "init"
    run_report_path: Optional[Path] = None
    routing_policy_path: Optional[Path] = None
    validation_contract_path: Optional[Path] = None
    run_summary_path: Optional[Path] = None
    edge_count_total_all: Optional[int] = None

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
        seed = int(receipt.get("seed"))

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S4: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        dict_2b_path, dictionary_2b = load_dataset_dictionary(source, "2B")
        reg_3b_path, registry_3b = load_artefact_registry(source, "3B")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s dictionary_2b=%s registry=%s schemas=%s",
            config.contracts_layout,
            config.contracts_root,
            dict_3b_path,
            dict_2b_path,
            reg_3b_path,
            ",".join(
                [
                    str(schema_3b_path),
                    str(schema_2b_path),
                    str(schema_1a_path),
                    str(schema_layer1_path),
                ]
            ),
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "run_id": str(run_id),
        }

        logger.info(
            "S4: objective=compile virtual routing semantics + validation contracts; gated inputs "
            "(s0_gate_receipt_3B, sealed_inputs_3B, virtual_classification_3B, virtual_settlement_3B, "
            "edge_catalogue_3B, edge_catalogue_index_3B, edge_alias_blob_3B, edge_alias_index_3B, "
            "edge_universe_hash_3B, virtual_validation_policy, cdn_key_digest, alias_layout_policy_v1, "
            "route_rng_policy_v1, virtual_routing_fields_v1) -> outputs "
            "(virtual_routing_policy_3B, virtual_validation_contract_3B, s4_run_summary_3B)"
        )

        find_dataset_entry(dictionary_2b, "s6_edge_log")

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_3b, "s0_gate_receipt_3B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        try:
            _validate_payload(schema_3b, schema_layer1, "validation/s0_gate_receipt_3B", receipt_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_schema_invalid",
                {"error": str(exc), "path": str(receipt_path)},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _abort(
                "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        if receipt_payload.get("seed") not in (None, seed) or receipt_payload.get("parameter_hash") not in (
            None,
            parameter_hash,
        ):
            _abort(
                "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_identity_mismatch",
                {
                    "seed": receipt_payload.get("seed"),
                    "parameter_hash": receipt_payload.get("parameter_hash"),
                },
                manifest_fingerprint,
            )
        for segment_id in ("segment_1A", "segment_1B", "segment_2A", "segment_3A"):
            status_value = receipt_payload.get("upstream_gates", {}).get(segment_id, {}).get("status")
            if status_value != "PASS":
                _abort(
                    "E3B_S4_002_UPSTREAM_GATE_NOT_PASS",
                    "V-02",
                    "upstream_gate_not_pass",
                    {"segment": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        current_phase = "sealed_inputs"
        sealed_entry = find_dataset_entry(dictionary_3b, "sealed_inputs_3B").entry
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        sealed_payload = _load_json(sealed_path)
        if not isinstance(sealed_payload, list):
            _abort(
                "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                "V-03",
                "sealed_inputs_not_list",
                {"path": str(sealed_path)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_for_payload(schema_3b, schema_layer1, "validation/sealed_inputs_3B")
        validator = Draft202012Validator(sealed_schema)
        sealed_rows: list[dict] = []
        for row in sealed_payload:
            if not isinstance(row, dict):
                _abort(
                    "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_not_object",
                    {"row": str(row)[:200]},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_schema_invalid",
                    {"error": errors[0].message},
                    manifest_fingerprint,
                )
            if row.get("manifest_fingerprint") != str(manifest_fingerprint):
                _abort(
                    "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_manifest_mismatch",
                    {"expected": str(manifest_fingerprint), "actual": row.get("manifest_fingerprint")},
                    manifest_fingerprint,
                )
            sealed_rows.append(row)

        sealed_by_id: dict[str, dict] = {}
        for row in sealed_rows:
            logical_id = str(row.get("logical_id") or "")
            if not logical_id:
                _abort(
                    "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_missing",
                    {"row": row},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3B_S4_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        required_ids = [
            "virtual_validation_policy",
            "cdn_key_digest",
            "route_rng_policy_v1",
            "alias_layout_policy_v1",
            "virtual_routing_fields_v1",
        ]

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3B_S4_003_REQUIRED_INPUT_NOT_SEALED",
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
                    "E3B_S4_004_SEALED_INPUT_MISMATCH",
                    "V-04",
                    "sealed_path_mismatch",
                    {"logical_id": logical_id, "expected": expected_path, "actual": sealed_path_value},
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3B_S4_003_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "input_missing",
                    {"logical_id": logical_id, "path": str(asset_path)},
                    manifest_fingerprint,
                )
            computed_digest = _hash_dataset(asset_path)
            sealed_digest = str(sealed_row.get("sha256_hex") or "")
            if computed_digest != sealed_digest:
                _abort(
                    "E3B_S4_005_SEALED_INPUT_DIGEST_MISMATCH",
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
            return sealed_row, asset_path, expected_path, computed_digest

        verified_assets: dict[str, tuple[dict, Path, str, str]] = {}
        for logical_id in required_ids:
            verified_assets[logical_id] = _verify_sealed_asset(logical_id)

        timer.info("S4: verified required sealed inputs and digests")

        current_phase = "policy_payloads"
        validation_policy_path = verified_assets["virtual_validation_policy"][1]
        validation_policy_payload = _load_yaml(validation_policy_path)
        _validate_payload(schema_3b, schema_layer1, "policy/virtual_validation_policy_v1", validation_policy_payload)

        cdn_key_path = verified_assets["cdn_key_digest"][1]
        cdn_key_payload = _load_yaml(cdn_key_path)
        _validate_payload(schema_3b, schema_layer1, "policy/cdn_key_digest_v1", cdn_key_payload)

        routing_fields_path = verified_assets["virtual_routing_fields_v1"][1]
        routing_fields_payload = _load_yaml(routing_fields_path)
        _validate_payload(schema_3b, schema_layer1, "policy/virtual_routing_fields_v1", routing_fields_payload)

        route_policy_path = verified_assets["route_rng_policy_v1"][1]
        route_policy_payload = _load_json(route_policy_path)
        _validate_payload(schema_2b, schema_layer1, "policy/route_rng_policy_v1", route_policy_payload)

        alias_policy_path = verified_assets["alias_layout_policy_v1"][1]
        alias_policy_payload = _load_json(alias_policy_path)
        _validate_payload(schema_2b, schema_layer1, "policy/alias_layout_policy_v1", alias_policy_payload)

        validation_policy_version = str(validation_policy_payload.get("version") or "")
        if not validation_policy_version:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "virtual_validation_version_missing",
                {"path": str(validation_policy_path)},
                manifest_fingerprint,
            )
        realism_mode = str(validation_policy_payload.get("realism_enforcement_mode") or "").strip().lower()
        if realism_mode not in {"observe", "enforce"}:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "realism_enforcement_mode_invalid",
                {"path": str(validation_policy_path), "value": validation_policy_payload.get("realism_enforcement_mode")},
                manifest_fingerprint,
            )
        realism_checks = validation_policy_payload.get("realism_checks")
        if not isinstance(realism_checks, dict):
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "realism_checks_missing_or_invalid",
                {"path": str(validation_policy_path)},
                manifest_fingerprint,
            )
        try:
            edge_count_cv_min = float(realism_checks["edge_count_cv_min"])
            country_count_cv_min = float(realism_checks["country_count_cv_min"])
            top1_share_p50_min = float(realism_checks["top1_share_p50_min"])
            top1_share_p50_max = float(realism_checks["top1_share_p50_max"])
            js_divergence_median_min = float(realism_checks["js_divergence_median_min"])
            settlement_overlap_median_min = float(realism_checks["settlement_overlap_median_min"])
            settlement_overlap_p75_min = float(realism_checks["settlement_overlap_p75_min"])
            settlement_distance_median_max_km = float(realism_checks["settlement_distance_median_max_km"])
            rule_id_non_null_rate_min = float(realism_checks["rule_id_non_null_rate_min"])
            rule_version_non_null_rate_min = float(realism_checks["rule_version_non_null_rate_min"])
            active_rule_id_count_min = int(realism_checks["active_rule_id_count_min"])
            alias_max_abs_delta_max = float(realism_checks["alias_max_abs_delta_max"])
        except (KeyError, TypeError, ValueError) as exc:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "realism_checks_parse_failed",
                {"path": str(validation_policy_path), "error": str(exc)},
                manifest_fingerprint,
            )
        if top1_share_p50_min > top1_share_p50_max:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "realism_top1_range_invalid",
                {
                    "top1_share_p50_min": top1_share_p50_min,
                    "top1_share_p50_max": top1_share_p50_max,
                    "path": str(validation_policy_path),
                },
                manifest_fingerprint,
            )

        routing_policy_id = str(route_policy_payload.get("policy_id") or "route_rng_policy_v1")
        routing_policy_version = str(
            route_policy_payload.get("policy_version") or route_policy_payload.get("version_tag") or ""
        )
        if not routing_policy_version:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "route_rng_policy_version_missing",
                {"path": str(route_policy_path)},
                manifest_fingerprint,
            )

        alias_layout_version = str(alias_policy_payload.get("layout_version") or "")
        if not alias_layout_version:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "alias_layout_version_missing",
                {"path": str(alias_policy_path)},
                manifest_fingerprint,
            )

        cdn_key_digest = str(cdn_key_payload.get("cdn_key_digest") or "")
        if not cdn_key_digest:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-05",
                "cdn_key_digest_missing",
                {"path": str(cdn_key_path)},
                manifest_fingerprint,
            )

        current_phase = "s1_outputs"
        class_entry = find_dataset_entry(dictionary_3b, "virtual_classification_3B").entry
        settle_entry = find_dataset_entry(dictionary_3b, "virtual_settlement_3B").entry
        class_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        settle_path = _resolve_dataset_path(settle_entry, run_paths, config.external_roots, tokens)
        class_files = _resolve_parquet_files(class_path)
        settle_files = _resolve_parquet_files(settle_path)
        _validate_parquet_rows(
            class_files,
            schema_3b,
            schema_layer1,
            "plan/virtual_classification_3B",
            "virtual_classification_3B",
            manifest_fingerprint,
        )
        _validate_parquet_rows(
            settle_files,
            schema_3b,
            schema_layer1,
            "plan/virtual_settlement_3B",
            "virtual_settlement_3B",
            manifest_fingerprint,
        )
        class_df = pl.read_parquet(class_files)
        settle_df = pl.read_parquet(settle_files)

        virtual_ids = set(
            int(row["merchant_id"]) for row in class_df.iter_rows(named=True) if row.get("is_virtual")
        )
        settlement_ids = set(int(row["merchant_id"]) for row in settle_df.iter_rows(named=True))
        missing_settlement = sorted(virtual_ids - settlement_ids)
        extra_settlement = sorted(settlement_ids - virtual_ids)
        if missing_settlement or extra_settlement:
            _abort(
                "E3B_S4_006_S1_INPUT_INVALID",
                "V-06",
                "classification_settlement_mismatch",
                {
                    "missing_settlement": missing_settlement[:10],
                    "extra_settlement": extra_settlement[:10],
                    "missing_count": len(missing_settlement),
                    "extra_count": len(extra_settlement),
                },
                manifest_fingerprint,
            )
        timer.info(
            f"S4: validated S1 inputs (virtual_merchants={len(virtual_ids)}, settlement_rows={len(settlement_ids)})"
        )

        current_phase = "s2_edge_catalogue_index"
        edge_index_entry = find_dataset_entry(dictionary_3b, "edge_catalogue_index_3B").entry
        edge_index_path = _resolve_dataset_path(edge_index_entry, run_paths, config.external_roots, tokens)
        edge_index_files = _resolve_parquet_files(edge_index_path)
        _validate_parquet_rows(
            edge_index_files,
            schema_3b,
            schema_layer1,
            "plan/edge_catalogue_index_3B",
            "edge_catalogue_index_3B",
            manifest_fingerprint,
        )
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

        current_phase = "s2_edge_catalogue"
        edge_entry = find_dataset_entry(dictionary_3b, "edge_catalogue_3B").entry
        edge_path = _resolve_dataset_path(edge_entry, run_paths, config.external_roots, tokens)
        edge_files = _resolve_parquet_files(edge_path)
        _validate_parquet_rows(
            edge_files,
            schema_3b,
            schema_layer1,
            "plan/edge_catalogue_3B",
            "edge_catalogue_3B",
            manifest_fingerprint,
        )
        edge_scan = pl.scan_parquet(edge_files).select(["merchant_id", "edge_id"])
        edge_counts_df = edge_scan.group_by("merchant_id").len().collect()
        edge_counts = {
            int(row["merchant_id"]): int(row["len"]) for row in edge_counts_df.iter_rows(named=True)
        }
        extra_edges = sorted(set(edge_counts.keys()) - virtual_ids)
        if extra_edges:
            _abort(
                "E3B_S4_007_S2_INPUT_INVALID",
                "V-07",
                "edge_catalogue_non_virtual",
                {"extra_merchants": extra_edges[:10], "extra_count": len(extra_edges)},
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
                "E3B_S4_007_S2_INPUT_INVALID",
                "V-07",
                "edge_count_mismatch",
                {"examples": count_mismatch, "mismatch_count": len(count_mismatch)},
                manifest_fingerprint,
            )
        timer.info(
            f"S4: validated S2 edge catalogue (edge_merchants={len(edge_counts)}, edges_total={sum(edge_counts.values())})"
        )

        current_phase = "s3_alias_index"
        alias_index_entry = find_dataset_entry(dictionary_3b, "edge_alias_index_3B").entry
        alias_index_path = _resolve_dataset_path(alias_index_entry, run_paths, config.external_roots, tokens)
        alias_index_files = _resolve_parquet_files(alias_index_path)
        _validate_parquet_rows(
            alias_index_files,
            schema_3b,
            schema_layer1,
            "plan/edge_alias_index_3B",
            "edge_alias_index_3B",
            manifest_fingerprint,
        )
        alias_index_df = pl.read_parquet(alias_index_files)
        alias_index_df = alias_index_df.with_columns(pl.col("scope").cast(pl.Utf8))
        alias_merchant_rows = alias_index_df.filter(pl.col("scope") == "MERCHANT")
        alias_counts = {
            int(row["merchant_id"]): int(row["edge_count_total"])
            for row in alias_merchant_rows.iter_rows(named=True)
            if row.get("merchant_id") is not None
        }
        alias_layout_versions = {
            str(row.get("alias_layout_version") or "")
            for row in alias_index_df.iter_rows(named=True)
            if row.get("alias_layout_version")
        }
        if alias_layout_version and alias_layout_versions and alias_layout_version not in alias_layout_versions:
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "alias_layout_version_mismatch",
                {"policy": alias_layout_version, "alias_versions": sorted(alias_layout_versions)},
                manifest_fingerprint,
            )
        missing_alias = sorted(set(expected_counts.keys()) - set(alias_counts.keys()))
        if missing_alias:
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
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
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "alias_edge_count_mismatch",
                {"examples": alias_count_mismatch, "mismatch_count": len(alias_count_mismatch)},
                manifest_fingerprint,
            )

        current_phase = "s3_universe_hash"
        universe_entry = find_dataset_entry(dictionary_3b, "edge_universe_hash_3B").entry
        universe_path = _resolve_dataset_path(universe_entry, run_paths, config.external_roots, tokens)
        universe_payload = _load_json(universe_path)
        _validate_payload(schema_3b, schema_layer1, "validation/edge_universe_hash_3B", universe_payload)
        if universe_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "universe_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": universe_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        if universe_payload.get("parameter_hash") not in (None, str(parameter_hash)):
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "universe_parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": universe_payload.get("parameter_hash")},
                manifest_fingerprint,
            )

        edge_catalogue_index_digest = _hash_dataset(edge_index_path)
        edge_alias_index_digest = _hash_dataset(alias_index_path)
        if universe_payload.get("edge_catalogue_index_digest") != edge_catalogue_index_digest:
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "edge_catalogue_index_digest_mismatch",
                {
                    "expected": universe_payload.get("edge_catalogue_index_digest"),
                    "actual": edge_catalogue_index_digest,
                },
                manifest_fingerprint,
            )
        if universe_payload.get("edge_alias_index_digest") != edge_alias_index_digest:
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "edge_alias_index_digest_mismatch",
                {
                    "expected": universe_payload.get("edge_alias_index_digest"),
                    "actual": edge_alias_index_digest,
                },
                manifest_fingerprint,
            )

        components = [
            ("cdn_weights", universe_payload.get("cdn_weights_digest")),
            ("edge_alias_index", edge_alias_index_digest),
            ("edge_catalogue_index", edge_catalogue_index_digest),
            ("virtual_rules", universe_payload.get("virtual_rules_digest")),
        ]
        if any(not item[1] for item in components):
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "universe_components_missing",
                {"components": components},
                manifest_fingerprint,
            )
        components.sort(key=lambda item: item[0])
        digest_bytes = b"".join(bytes.fromhex(str(item[1])) for item in components)
        recomputed_universe_hash = hashlib.sha256(digest_bytes).hexdigest()
        if recomputed_universe_hash != universe_payload.get("universe_hash"):
            _abort(
                "E3B_S4_008_S3_INPUT_INVALID",
                "V-08",
                "universe_hash_mismatch",
                {"expected": universe_payload.get("universe_hash"), "actual": recomputed_universe_hash},
                manifest_fingerprint,
            )

        alias_blob_entry = find_dataset_entry(dictionary_3b, "edge_alias_blob_3B").entry
        alias_blob_path = _resolve_dataset_path(alias_blob_entry, run_paths, config.external_roots, tokens)
        alias_blob_digest = sha256_file(alias_blob_path).sha256_hex
        alias_blob_global = alias_index_df.filter(pl.col("scope") == "GLOBAL")
        if alias_blob_global.height > 0:
            blob_sha = alias_blob_global.to_dicts()[0].get("blob_sha256_hex")
            if blob_sha and blob_sha != alias_blob_digest:
                _abort(
                    "E3B_S4_008_S3_INPUT_INVALID",
                    "V-08",
                    "alias_blob_digest_mismatch",
                    {"expected": blob_sha, "actual": alias_blob_digest},
                    manifest_fingerprint,
                )

        timer.info(
            f"S4: validated S3 alias & universe hash (alias_merchants={len(alias_counts)}, "
            f"universe_hash={universe_payload.get('universe_hash')})"
        )

        current_phase = "routing_policy"
        routing_fields = {
            "tzid_settlement_field": str(routing_fields_payload.get("tzid_settlement_field") or ""),
            "tzid_operational_field": str(routing_fields_payload.get("tzid_operational_field") or ""),
            "settlement_day_field": str(routing_fields_payload.get("settlement_day_field") or ""),
            "settlement_cutoff_rule": str(routing_fields_payload.get("settlement_cutoff_rule") or ""),
            "ip_country_field": str(routing_fields_payload.get("ip_country_field") or ""),
            "ip_latitude_field": str(routing_fields_payload.get("ip_latitude_field") or ""),
            "ip_longitude_field": str(routing_fields_payload.get("ip_longitude_field") or ""),
        }
        missing_fields = [key for key, value in routing_fields.items() if not value]
        if missing_fields:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-09",
                "routing_fields_missing",
                {"missing_fields": missing_fields},
                manifest_fingerprint,
            )

        edge_catalogue_index_path = _render_catalog_path(edge_index_entry, tokens)
        edge_alias_blob_path = _render_catalog_path(alias_blob_entry, tokens)
        edge_alias_index_path = _render_catalog_path(alias_index_entry, tokens)

        alias_blob_manifest_key = find_artifact_entry(registry_3b, "edge_alias_blob_3B").entry.get("manifest_key")
        alias_index_manifest_key = find_artifact_entry(registry_3b, "edge_alias_index_3B").entry.get("manifest_key")
        edge_universe_manifest_key = find_artifact_entry(registry_3b, "edge_universe_hash_3B").entry.get(
            "manifest_key"
        )
        if not alias_blob_manifest_key or not alias_index_manifest_key or not edge_universe_manifest_key:
            _abort(
                "E3B_S4_009_POLICY_INVALID",
                "V-09",
                "manifest_key_missing",
                {
                    "alias_blob_manifest_key": alias_blob_manifest_key,
                    "alias_index_manifest_key": alias_index_manifest_key,
                    "edge_universe_hash_manifest_key": edge_universe_manifest_key,
                },
                manifest_fingerprint,
            )

        routing_policy = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "edge_universe_hash": str(universe_payload.get("universe_hash")),
            "routing_policy_id": routing_policy_id,
            "routing_policy_version": routing_policy_version,
            "virtual_validation_policy_id": "virtual_validation_policy",
            "virtual_validation_policy_version": validation_policy_version,
            "cdn_key_digest": cdn_key_digest,
            "alias_layout_version": alias_layout_version,
            "alias_blob_manifest_key": alias_blob_manifest_key,
            "alias_index_manifest_key": alias_index_manifest_key,
            "edge_universe_hash_manifest_key": edge_universe_manifest_key,
            "dual_timezone_semantics": {
                "tzid_settlement_field": routing_fields["tzid_settlement_field"],
                "tzid_operational_field": routing_fields["tzid_operational_field"],
                "settlement_cutoff_rule": routing_fields["settlement_cutoff_rule"],
            },
            "geo_field_bindings": {
                "ip_country_field": routing_fields["ip_country_field"],
                "ip_latitude_field": routing_fields["ip_latitude_field"],
                "ip_longitude_field": routing_fields["ip_longitude_field"],
            },
            "artefact_paths": {
                "edge_catalogue_index": edge_catalogue_index_path,
                "edge_alias_blob": edge_alias_blob_path,
                "edge_alias_index": edge_alias_index_path,
            },
            "virtual_edge_rng_binding": {
                "module": "2B.virtual_edge",
                "substream_label": "cdn_edge_pick",
                "event_schema": "schemas.layer1.yaml#/rng/events/cdn_edge_pick",
            },
            "notes": "S4 routing semantics for virtual flows.",
        }
        _validate_payload(schema_3b, schema_layer1, "egress/virtual_routing_policy_3B", routing_policy)

        current_phase = "validation_contract"
        test_rows = []
        target_population = {"virtual_only": True}
        realism_severity = "BLOCKING" if realism_mode == "enforce" else "WARNING"

        ip_country_tolerance = float(validation_policy_payload.get("ip_country_tolerance") or 0.0)
        cutoff_tolerance = int(validation_policy_payload.get("cutoff_tolerance_seconds") or 0)

        ip_mix_id = _build_test_id("IP_COUNTRY_MIX", "GLOBAL", target_population)
        test_rows.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "test_id": ip_mix_id,
                "test_type": "IP_COUNTRY_MIX",
                "scope": "GLOBAL",
                "target_population": target_population,
                "inputs": {
                    "datasets": [
                        {"logical_id": "s6_edge_log", "role": "events"},
                        {"logical_id": "edge_catalogue_3B", "role": "edge_reference"},
                    ],
                    "fields": [{"schema_anchor": routing_fields["ip_country_field"], "role": "ip_country"}],
                    "join_keys": ["merchant_id", "edge_id"],
                },
                "thresholds": {"max_abs_error": ip_country_tolerance},
                "severity": "BLOCKING",
                "enabled": True,
                "description": "Validate IP-country mix against edge catalogue country mix.",
                "profile": None,
            }
        )

        cutoff_id = _build_test_id("SETTLEMENT_CUTOFF", "PER_MERCHANT", target_population)
        test_rows.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "test_id": cutoff_id,
                "test_type": "SETTLEMENT_CUTOFF",
                "scope": "PER_MERCHANT",
                "target_population": target_population,
                "inputs": {
                    "datasets": [
                        {"logical_id": "s6_edge_log", "role": "events"},
                        {"logical_id": "virtual_settlement_3B", "role": "settlement_reference"},
                    ],
                    "fields": [
                        {"schema_anchor": routing_fields["settlement_day_field"], "role": "settlement_day"},
                        {"schema_anchor": routing_fields["tzid_settlement_field"], "role": "tzid_settlement"},
                    ],
                    "join_keys": ["merchant_id"],
                },
                "thresholds": {"cutoff_tolerance_seconds": cutoff_tolerance},
                "severity": "BLOCKING",
                "enabled": True,
                "description": "Validate settlement cut-off assignment against tzid_settlement.",
                "profile": None,
            }
        )

        edge_heterogeneity_id = _build_test_id("EDGE_HETEROGENEITY", "GLOBAL", target_population)
        test_rows.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "test_id": edge_heterogeneity_id,
                "test_type": "EDGE_HETEROGENEITY",
                "scope": "GLOBAL",
                "target_population": target_population,
                "inputs": {
                    "datasets": [
                        {"logical_id": "edge_catalogue_3B", "role": "edge_surface"},
                        {"logical_id": "edge_catalogue_index_3B", "role": "merchant_edge_index"},
                    ],
                    "fields": [
                        {"schema_anchor": "edge_weight", "role": "edge_weight"},
                        {"schema_anchor": "country_iso", "role": "country_code"},
                    ],
                    "join_keys": ["merchant_id"],
                },
                "thresholds": {
                    "edge_count_cv_min": edge_count_cv_min,
                    "country_count_cv_min": country_count_cv_min,
                    "top1_share_p50_min": top1_share_p50_min,
                    "top1_share_p50_max": top1_share_p50_max,
                    "js_divergence_median_min": js_divergence_median_min,
                },
                "severity": realism_severity,
                "enabled": True,
                "description": "Guard merchant-level edge heterogeneity realism metrics.",
                "profile": realism_mode,
            }
        )

        settlement_coherence_id = _build_test_id("SETTLEMENT_COHERENCE", "GLOBAL", target_population)
        test_rows.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "test_id": settlement_coherence_id,
                "test_type": "SETTLEMENT_COHERENCE",
                "scope": "GLOBAL",
                "target_population": target_population,
                "inputs": {
                    "datasets": [
                        {"logical_id": "edge_catalogue_3B", "role": "edge_surface"},
                        {"logical_id": "virtual_settlement_3B", "role": "settlement_surface"},
                    ],
                    "fields": [
                        {"schema_anchor": "country_iso", "role": "edge_country"},
                        {"schema_anchor": "lat_deg", "role": "edge_lat"},
                        {"schema_anchor": "lon_deg", "role": "edge_lon"},
                    ],
                    "join_keys": ["merchant_id"],
                },
                "thresholds": {
                    "settlement_overlap_median_min": settlement_overlap_median_min,
                    "settlement_overlap_p75_min": settlement_overlap_p75_min,
                    "settlement_distance_median_max_km": settlement_distance_median_max_km,
                },
                "severity": realism_severity,
                "enabled": True,
                "description": "Guard settlement-to-edge coherence metrics.",
                "profile": realism_mode,
            }
        )

        classification_explainability_id = _build_test_id(
            "CLASSIFICATION_EXPLAINABILITY", "GLOBAL", target_population
        )
        test_rows.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "test_id": classification_explainability_id,
                "test_type": "CLASSIFICATION_EXPLAINABILITY",
                "scope": "GLOBAL",
                "target_population": target_population,
                "inputs": {
                    "datasets": [{"logical_id": "virtual_classification_3B", "role": "classification_surface"}],
                    "fields": [
                        {"schema_anchor": "rule_id", "role": "rule_id"},
                        {"schema_anchor": "rule_version", "role": "rule_version"},
                    ],
                    "join_keys": ["merchant_id"],
                },
                "thresholds": {
                    "rule_id_non_null_rate_min": rule_id_non_null_rate_min,
                    "rule_version_non_null_rate_min": rule_version_non_null_rate_min,
                    "active_rule_id_count_min": active_rule_id_count_min,
                },
                "severity": realism_severity,
                "enabled": True,
                "description": "Guard classification lineage completeness and rule diversity.",
                "profile": realism_mode,
            }
        )

        alias_fidelity_id = _build_test_id("ALIAS_FIDELITY", "GLOBAL", target_population)
        test_rows.append(
            {
                "manifest_fingerprint": str(manifest_fingerprint),
                "test_id": alias_fidelity_id,
                "test_type": "ALIAS_FIDELITY",
                "scope": "GLOBAL",
                "target_population": target_population,
                "inputs": {
                    "datasets": [
                        {"logical_id": "edge_alias_blob_3B", "role": "alias_surface"},
                        {"logical_id": "edge_alias_index_3B", "role": "alias_index"},
                        {"logical_id": "edge_catalogue_3B", "role": "edge_surface"},
                    ],
                    "fields": [{"schema_anchor": "edge_weight", "role": "edge_weight"}],
                    "join_keys": ["merchant_id", "edge_id"],
                },
                "thresholds": {"alias_max_abs_delta_max": alias_max_abs_delta_max},
                "severity": realism_severity,
                "enabled": True,
                "description": "Guard alias decode fidelity against edge weights.",
                "profile": realism_mode,
            }
        )

        test_rows = sorted(test_rows, key=lambda row: row["test_id"])
        validation_pack, validation_table = _table_pack(schema_3b, "egress/virtual_validation_contract_3B")
        _inline_external_refs(validation_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(test_rows, validation_pack, validation_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S4_011_VALIDATION_CONTRACT_INVALID",
                "V-11",
                "validation_contract_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )

        validation_df = pl.DataFrame(test_rows)

        current_phase = "publish_outputs"
        routing_entry = find_dataset_entry(dictionary_3b, "virtual_routing_policy_3B").entry
        routing_policy_path = _resolve_dataset_path(routing_entry, run_paths, config.external_roots, tokens)
        validation_entry = find_dataset_entry(dictionary_3b, "virtual_validation_contract_3B").entry
        validation_contract_path = _resolve_dataset_path(validation_entry, run_paths, config.external_roots, tokens)

        if routing_policy_path.exists() != validation_contract_path.exists():
            _abort(
                "E3B_S4_OUTPUT_ATOMICITY_VIOLATION",
                "V-12",
                "partial_outputs_present",
                {
                    "routing_policy_path": str(routing_policy_path),
                    "validation_contract_path": str(validation_contract_path),
                },
                manifest_fingerprint,
            )

        tmp_root = run_paths.tmp_root / f"s4_contracts_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmp_routing_path = tmp_root / "virtual_routing_policy_3B.json"
        tmp_validation_path = tmp_root / "virtual_validation_contract_3B.parquet"

        _write_json(tmp_routing_path, routing_policy)
        validation_df.write_parquet(tmp_validation_path, compression="zstd")

        if routing_policy_path.exists():
            _atomic_publish_file(tmp_routing_path, routing_policy_path, logger, "virtual_routing_policy_3B")
            _atomic_publish_file(tmp_validation_path, validation_contract_path, logger, "virtual_validation_contract_3B")
        else:
            try:
                routing_policy_path.parent.mkdir(parents=True, exist_ok=True)
                validation_contract_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_routing_path.replace(routing_policy_path)
                tmp_validation_path.replace(validation_contract_path)
            except OSError as exc:
                if routing_policy_path.exists() and not validation_contract_path.exists():
                    try:
                        routing_policy_path.unlink()
                    except OSError:
                        pass
                raise EngineFailure(
                    "F4",
                    "E3B_S4_019_INFRASTRUCTURE_IO_ERROR",
                    STATE,
                    MODULE_NAME,
                    {"detail": "atomic publish failed", "error": str(exc)},
                ) from exc

        current_phase = "run_summary"
        run_summary_entry = find_dataset_entry(dictionary_3b, "s4_run_summary_3B").entry
        run_summary_path = _resolve_dataset_path(run_summary_entry, run_paths, config.external_roots, tokens)
        run_summary = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "status": "PASS",
            "cdn_key_digest": cdn_key_digest,
            "virtual_validation_digest": sha256_file(validation_policy_path).sha256_hex,
            "routing_policy_version": routing_policy_version,
            "notes": "S4 virtual routing policy + validation contract compiled.",
        }
        _validate_payload(schema_3b, schema_layer1, "validation/s4_run_summary_3B", run_summary)
        _atomic_publish_json(run_summary_path, run_summary, logger, "s4_run_summary_3B")

        status = "PASS"
        timer.info(
            f"S4: outputs published (routing_policy={routing_policy_path}, "
            f"validation_contract={validation_contract_path}, tests={len(test_rows)})"
        )

    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (InputResolutionError, SchemaValidationError, ValueError) as exc:
        status = "FAIL"
        if not error_code:
            error_code = "E3B_S4_019_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        status = "FAIL"
        if not error_code:
            error_code = "E3B_S4_019_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint:
            try:
                run_report_entry = find_dataset_entry(dictionary_3b, "s4_run_report_3B").entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": str(run_id),
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": {
                        "route_rng_policy_id": routing_policy_id if "routing_policy_id" in locals() else "",
                        "route_rng_policy_version": routing_policy_version if "routing_policy_version" in locals() else "",
                        "virtual_validation_policy_version": validation_policy_version
                        if "validation_policy_version" in locals()
                        else "",
                        "alias_layout_version": alias_layout_version if "alias_layout_version" in locals() else "",
                    },
                    "counts": {
                        "virtual_merchants": len(virtual_ids) if "virtual_ids" in locals() else 0,
                        "edge_merchants": len(edge_counts) if "edge_counts" in locals() else 0,
                        "alias_merchants": len(alias_counts) if "alias_counts" in locals() else 0,
                        "validation_tests": len(test_rows) if "test_rows" in locals() else 0,
                        "edge_total": sum(edge_counts.values()) if "edge_counts" in locals() else 0,
                        "edge_total_index": edge_count_total_all if edge_count_total_all is not None else 0,
                    },
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "virtual_routing_policy_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "virtual_routing_policy_3B").entry, tokens
                        ),
                        "virtual_validation_contract_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "virtual_validation_contract_3B").entry, tokens
                        ),
                        "s4_run_summary_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "s4_run_summary_3B").entry, tokens
                        ),
                        "format": "json/parquet/json",
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S4: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S4: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3B_S4_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if routing_policy_path is None or validation_contract_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3B_S4_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S4Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        routing_policy_path=routing_policy_path,
        validation_contract_path=validation_contract_path,
        run_summary_path=run_summary_path,
        run_report_path=run_report_path,
    )
