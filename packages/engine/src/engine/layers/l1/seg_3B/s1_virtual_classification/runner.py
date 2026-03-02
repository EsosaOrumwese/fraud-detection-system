"""S1 virtual classification and settlement node construction for Segment 3B."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import (
    find_artifact_entry,
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
    _is_placeholder,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _table_pack,
)


MODULE_NAME = "3B.s1_virtual_classification"
SEGMENT = "3B"
STATE = "S1"

_DECISION_RULE_MATCH = "RULE_MATCH"
_DECISION_DEFAULT = "DEFAULT_GUARD"
_VIRTUAL_MODE_VIRTUAL = "VIRTUAL_ONLY"
_VIRTUAL_MODE_NON_VIRTUAL = "NON_VIRTUAL"


@dataclass(frozen=True)
class S1Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    classification_path: Path
    settlement_path: Path
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
    logger = get_logger("engine.layers.l1.seg_3B.s1_virtual_classification.l2.runner")
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


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E3B_S1_012_IMMUTABILITY_VIOLATION",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        for path in tmp_root.rglob("*"):
            if path.is_file():
                path.unlink()
        try:
            tmp_root.rmdir()
        except OSError:
            pass
        logger.info("S1: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _atomic_publish_pair(
    class_tmp: Path,
    class_final: Path,
    settle_tmp: Path,
    settle_final: Path,
    logger,
) -> None:
    class_exists = class_final.exists()
    settle_exists = settle_final.exists()
    if class_exists or settle_exists:
        if class_exists != settle_exists:
            raise EngineFailure(
                "F4",
                "E3B_S1_012_IMMUTABILITY_VIOLATION",
                STATE,
                MODULE_NAME,
                {
                    "detail": "partial outputs detected",
                    "classification_path": str(class_final),
                    "settlement_path": str(settle_final),
                },
            )
        class_tmp_hash, _ = _hash_partition(class_tmp)
        class_final_hash, _ = _hash_partition(class_final)
        settle_tmp_hash, _ = _hash_partition(settle_tmp)
        settle_final_hash, _ = _hash_partition(settle_final)
        if class_tmp_hash != class_final_hash or settle_tmp_hash != settle_final_hash:
            raise EngineFailure(
                "F4",
                "E3B_S1_012_IMMUTABILITY_VIOLATION",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists for classification or settlement"},
            )
        for root in (class_tmp, settle_tmp):
            for path in root.rglob("*"):
                if path.is_file():
                    path.unlink()
            try:
                root.rmdir()
            except OSError:
                pass
        logger.info("S1: virtual classification + settlement partitions already exist and are identical; skipping publish.")
        return
    class_final.parent.mkdir(parents=True, exist_ok=True)
    settle_final.parent.mkdir(parents=True, exist_ok=True)
    class_tmp.replace(class_final)
    settle_tmp.replace(settle_final)


def _resolve_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _extract_version_from_path(path: str, anchor: str) -> str:
    parts = Path(path).parts
    if anchor not in parts:
        raise InputResolutionError(f"Version anchor '{anchor}' not found in path: {path}")
    idx = parts.index(anchor)
    if idx + 1 >= len(parts):
        raise InputResolutionError(f"Version token missing after '{anchor}' in path: {path}")
    return parts[idx + 1]


def _policy_digest(policy_path: Path) -> str:
    return sha256_file(policy_path).sha256_hex


def _load_policy(policy_path: Path) -> dict:
    payload = _load_yaml(policy_path)
    if not isinstance(payload, dict):
        raise ContractError("mcc_channel_rules payload is not an object")
    return payload


def _build_settlement_site_id(merchant_id: int) -> str:
    key_bytes = b"3B.SETTLEMENT" + bytes([0x1F]) + str(merchant_id).encode("utf-8")
    digest = hashlib.sha256(key_bytes).digest()
    low64 = int.from_bytes(digest[-8:], "big", signed=False)
    return f"{low64:016x}"


def _normalize_mcc(series: pl.Series) -> pl.Series:
    as_int = series.cast(pl.Int64, strict=False)
    return as_int.cast(pl.Utf8).str.zfill(4)


def _resolve_coord_version(prov_path: Path) -> str:
    payload = _load_json(prov_path)
    coordinate_batch = payload.get("coordinate_batch")
    if _is_placeholder(str(coordinate_batch) if coordinate_batch is not None else ""):
        raise InputResolutionError("virtual_settlement_coords.provenance.json missing coordinate_batch")
    return str(coordinate_batch)

def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l1.seg_3B.s1_virtual_classification.l2.runner")
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
    policy_id = ""
    policy_version = ""
    policy_digest = ""
    settlement_digest = ""
    tz_policy_digest = ""
    coord_version = ""
    classification_path: Optional[Path] = None
    settlement_path: Optional[Path] = None
    run_report_path: Optional[Path] = None

    counts = {
        "merchants_total": 0,
        "virtual_merchants": 0,
        "settlement_rows": 0,
    }

    current_phase = "init"

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
        logger.info("S1: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        reg_3b_path, registry_3b = load_artefact_registry(source, "3B")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s",
            config.contracts_layout,
            config.contracts_root,
            dict_3b_path,
            reg_3b_path,
            ",".join(
                [
                    str(schema_3b_path),
                    str(schema_2a_path),
                    str(schema_1a_path),
                    str(schema_ingress_path),
                    str(schema_layer1_path),
                ]
            ),
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
        }

        logger.info(
            "S1: objective=classify merchants as virtual and construct settlement nodes; "
            "gated inputs (s0_gate_receipt_3B, sealed_inputs_3B, transaction_schema_merchant_ids, "
            "mcc_channel_rules, virtual_settlement_coords) -> outputs "
            "(virtual_classification_3B, virtual_settlement_3B)"
        )

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_3b, "s0_gate_receipt_3B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        try:
            _validate_payload(schema_3b, schema_layer1, "validation/s0_gate_receipt_3B", receipt_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_receipt_invalid",
                {"detail": str(exc), "path": str(receipt_path)},
                manifest_fingerprint,
            )

        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
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
                "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_identity_mismatch",
                {
                    "seed": receipt_payload.get("seed"),
                    "parameter_hash": receipt_payload.get("parameter_hash"),
                },
                manifest_fingerprint,
            )

        for segment_id in ("segment_1A", "segment_1B", "segment_2A", "segment_3A"):
            status_value = (
                receipt_payload.get("upstream_gates", {})
                .get(segment_id, {})
                .get("status")
            )
            if status_value != "PASS":
                _abort(
                    "E3B_S1_002_UPSTREAM_GATE_NOT_PASS",
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
                "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
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
                    "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_not_object",
                    {"row": str(row)[:200]},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_schema_invalid",
                    {"error": errors[0].message},
                    manifest_fingerprint,
                )
            if row.get("manifest_fingerprint") != str(manifest_fingerprint):
                _abort(
                    "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_manifest_mismatch",
                    {
                        "expected": str(manifest_fingerprint),
                        "actual": row.get("manifest_fingerprint"),
                    },
                    manifest_fingerprint,
                )
            sealed_rows.append(row)

        sealed_by_id: dict[str, dict] = {}
        for row in sealed_rows:
            logical_id = str(row.get("logical_id") or "")
            if not logical_id:
                _abort(
                    "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_missing",
                    {"row": row},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3B_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        if "transaction_schema_merchant_ids" not in sealed_by_id:
            _abort(
                "E3B_S1_003_REQUIRED_INPUT_NOT_SEALED",
                "V-04",
                "merchant_ids_missing",
                {"logical_id": "transaction_schema_merchant_ids"},
                manifest_fingerprint,
            )
        merchant_version = _extract_version_from_path(
            str(sealed_by_id["transaction_schema_merchant_ids"].get("path") or ""),
            "transaction_schema_merchant_ids",
        )
        tokens["version"] = merchant_version
        logger.info("S1: resolved transaction_schema_merchant_ids version=%s from sealed_inputs_3B", merchant_version)

        required_ids = [
            "transaction_schema_merchant_ids",
            "mcc_channel_rules",
            "virtual_settlement_coords",
            "pelias_cached_sqlite",
            "pelias_cached_bundle",
            "cdn_weights_ext_yaml",
        ]

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3B_S1_003_REQUIRED_INPUT_NOT_SEALED",
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
                    "E3B_S1_007_SEALED_INPUT_MISMATCH",
                    "V-04",
                    "sealed_path_mismatch",
                    {"logical_id": logical_id, "expected": expected_path, "actual": sealed_path_value},
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3B_S1_003_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "input_missing",
                    {"logical_id": logical_id, "path": str(asset_path)},
                    manifest_fingerprint,
                )
            if asset_path.is_dir():
                computed_digest, _ = _hash_partition(asset_path)
            else:
                computed_digest = sha256_file(asset_path).sha256_hex
            sealed_digest = str(sealed_row.get("sha256_hex") or "")
            if computed_digest != sealed_digest:
                _abort(
                    "E3B_S1_006_SEALED_INPUT_DIGEST_MISMATCH",
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

        timer.info("S1: verified required sealed inputs and digests")
        digest_map = receipt_payload.get("digests") or {}
        policy_digest = digest_map.get("virtual_rules_digest") or verified_assets["mcc_channel_rules"][3]
        settlement_digest = digest_map.get("settlement_coord_digest") or verified_assets["virtual_settlement_coords"][3]
        tz_policy_digest = (
            digest_map.get("tz_index_digest")
            or digest_map.get("tzdata_archive_digest")
            or ""
        )
        if not tz_policy_digest:
            _abort(
                "E3B_S1_010_TZ_POLICY_DIGEST_MISSING",
                "V-05",
                "tz_policy_digest_missing",
                {"digests": digest_map},
                manifest_fingerprint,
            )

        if digest_map.get("virtual_rules_digest") and digest_map.get("virtual_rules_digest") != verified_assets["mcc_channel_rules"][3]:
            _abort(
                "E3B_S1_006_SEALED_INPUT_DIGEST_MISMATCH",
                "V-05",
                "policy_digest_mismatch",
                {
                    "logical_id": "mcc_channel_rules",
                    "sealed_digest": verified_assets["mcc_channel_rules"][3],
                    "receipt_digest": digest_map.get("virtual_rules_digest"),
                },
                manifest_fingerprint,
            )
        if digest_map.get("settlement_coord_digest") and digest_map.get("settlement_coord_digest") != verified_assets["virtual_settlement_coords"][3]:
            _abort(
                "E3B_S1_006_SEALED_INPUT_DIGEST_MISMATCH",
                "V-05",
                "settlement_digest_mismatch",
                {
                    "logical_id": "virtual_settlement_coords",
                    "sealed_digest": verified_assets["virtual_settlement_coords"][3],
                    "receipt_digest": digest_map.get("settlement_coord_digest"),
                },
                manifest_fingerprint,
            )

        current_phase = "policy_load"
        policy_path = verified_assets["mcc_channel_rules"][1]
        policy_payload = _load_policy(policy_path)
        policy_schema = _schema_for_payload(schema_3b, schema_layer1, "policy/virtual_rules_policy_v1")
        errors = list(Draft202012Validator(policy_schema).iter_errors(policy_payload))
        if errors:
            _abort(
                "E3B_S1_005_POLICY_SCHEMA_INVALID",
                "V-06",
                "policy_schema_invalid",
                {"error": errors[0].message},
                manifest_fingerprint,
            )
        policy_version = str(policy_payload.get("version") or "").strip()
        if _is_placeholder(policy_version):
            _abort(
                "E3B_S1_005_POLICY_SCHEMA_INVALID",
                "V-06",
                "policy_version_missing",
                {"path": str(policy_path)},
                manifest_fingerprint,
            )
        reg_entry = find_artifact_entry(registry_3b, "mcc_channel_rules").entry
        policy_id = str(reg_entry.get("manifest_key") or "mcc_channel_rules")
        policy_digest = verified_assets["mcc_channel_rules"][3]

        rules = policy_payload.get("rules") or []
        if not isinstance(rules, list):
            _abort(
                "E3B_S1_005_POLICY_SCHEMA_INVALID",
                "V-06",
                "policy_rules_missing",
                {"path": str(policy_path)},
                manifest_fingerprint,
            )
        rule_map: dict[tuple[str, str], dict[str, str]] = {}
        for rule in rules:
            if not isinstance(rule, dict):
                _abort(
                    "E3B_S1_005_POLICY_SCHEMA_INVALID",
                    "V-06",
                    "policy_rule_not_object",
                    {"rule": str(rule)[:200]},
                    manifest_fingerprint,
                )
            key = (str(rule.get("mcc") or ""), str(rule.get("channel") or ""))
            if key in rule_map:
                _abort(
                    "E3B_S1_005_POLICY_SCHEMA_INVALID",
                    "V-06",
                    "policy_rule_duplicate",
                    {"mcc": key[0], "channel": key[1]},
                    manifest_fingerprint,
                )
            decision = str(rule.get("decision") or "").strip().lower()
            if decision not in ("virtual", "physical"):
                _abort(
                    "E3B_S1_005_POLICY_SCHEMA_INVALID",
                    "V-06",
                    "policy_rule_decision_invalid",
                    {"mcc": key[0], "channel": key[1], "decision": decision},
                    manifest_fingerprint,
                )
            explicit_rule_id = str(rule.get("rule_id") or "").strip()
            if _is_placeholder(explicit_rule_id) or not explicit_rule_id:
                explicit_rule_id = f"MCC_{key[0]}__CHANNEL_{key[1]}__DECISION_{decision.upper()}"
            explicit_rule_version = str(rule.get("rule_version") or "").strip()
            if _is_placeholder(explicit_rule_version) or not explicit_rule_version:
                explicit_rule_version = policy_version
            rule_map[key] = {
                "decision": decision,
                "rule_id": explicit_rule_id,
                "rule_version": explicit_rule_version,
            }
        logger.info("S1: loaded virtual rules (rules=%d, policy_version=%s)", len(rule_map), policy_version)

        current_phase = "merchant_universe"
        merchant_path = verified_assets["transaction_schema_merchant_ids"][1]
        merchant_files = _resolve_parquet_files(merchant_path)
        merchant_df = pl.read_parquet(merchant_files)
        required_columns = {"merchant_id", "mcc", "channel", "home_country_iso"}
        missing_cols = sorted(required_columns - set(merchant_df.columns))
        if missing_cols:
            _abort(
                "E3B_S1_008_DOMAIN_MISMATCH_INGRESS",
                "V-07",
                "merchant_columns_missing",
                {"missing": missing_cols, "path": str(merchant_path)},
                manifest_fingerprint,
            )
        try:
            merchant_rows = merchant_df.select(sorted(required_columns)).iter_rows(named=True)
            merchant_pack, merchant_table = _table_pack(schema_ingress, "merchant_ids")
            validate_dataframe(merchant_rows, merchant_pack, merchant_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S1_008_DOMAIN_MISMATCH_INGRESS",
                "V-07",
                "merchant_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )

        merchant_df = merchant_df.with_columns(
            pl.col("merchant_id").cast(pl.UInt64),
            _normalize_mcc(pl.col("mcc")).alias("mcc_str"),
            pl.col("channel").cast(pl.Utf8),
        )

        if merchant_df.get_column("merchant_id").is_null().any():
            _abort(
                "E3B_S1_008_DOMAIN_MISMATCH_INGRESS",
                "V-07",
                "merchant_id_missing",
                {"path": str(merchant_path)},
                manifest_fingerprint,
            )
        if merchant_df.get_column("mcc_str").is_null().any():
            _abort(
                "E3B_S1_008_DOMAIN_MISMATCH_INGRESS",
                "V-07",
                "mcc_invalid",
                {"path": str(merchant_path)},
                manifest_fingerprint,
            )
        if merchant_df.get_column("channel").is_null().any():
            _abort(
                "E3B_S1_008_DOMAIN_MISMATCH_INGRESS",
                "V-07",
                "channel_missing",
                {"path": str(merchant_path)},
                manifest_fingerprint,
            )

        total_merchants = int(merchant_df.height)
        unique_merchants = int(merchant_df.get_column("merchant_id").n_unique())
        if unique_merchants != total_merchants:
            _abort(
                "E3B_S1_008_DOMAIN_MISMATCH_INGRESS",
                "V-07",
                "merchant_id_duplicate",
                {"total": total_merchants, "unique": unique_merchants},
                manifest_fingerprint,
            )
        merchant_df = merchant_df.sort("merchant_id")
        counts["merchants_total"] = total_merchants
        timer.info(
            f"S1: merchant universe loaded (merchants_total={total_merchants}, parquet_files={len(merchant_files)})"
        )

        current_phase = "classification"
        rules_df = pl.DataFrame(
            [
                {
                    "mcc_str": mcc,
                    "channel": channel,
                    "rule_decision": rule_meta["decision"],
                    "rule_id": rule_meta["rule_id"],
                    "rule_version": rule_meta["rule_version"],
                }
                for (mcc, channel), rule_meta in rule_map.items()
            ]
        )
        classification_df = (
            merchant_df.join(rules_df, on=["mcc_str", "channel"], how="left")
            .with_columns(
                pl.when(pl.col("rule_decision") == "virtual")
                .then(True)
                .otherwise(False)
                .alias("is_virtual"),
                pl.when(pl.col("rule_decision").is_null())
                .then(pl.lit(_DECISION_DEFAULT))
                .otherwise(pl.lit(_DECISION_RULE_MATCH))
                .alias("decision_reason"),
                pl.when(pl.col("rule_decision") == "virtual")
                .then(pl.lit(_VIRTUAL_MODE_VIRTUAL))
                .otherwise(pl.lit(_VIRTUAL_MODE_NON_VIRTUAL))
                .alias("virtual_mode"),
            )
            .with_columns(
                pl.lit(int(seed)).alias("seed"),
                pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
                pl.lit(policy_id).alias("source_policy_id"),
                pl.lit(policy_version).alias("source_policy_version"),
                pl.lit(policy_digest).alias("classification_digest"),
                pl.when(pl.col("rule_id").is_null() | (pl.col("rule_id") == ""))
                .then(pl.lit(_DECISION_DEFAULT))
                .otherwise(pl.col("rule_id"))
                .cast(pl.Utf8)
                .alias("rule_id"),
                pl.when(pl.col("rule_version").is_null() | (pl.col("rule_version") == ""))
                .then(pl.lit(policy_version))
                .otherwise(pl.col("rule_version"))
                .cast(pl.Utf8)
                .alias("rule_version"),
                pl.lit(None, dtype=pl.Utf8).alias("notes"),
            )
            .select(
                [
                    "seed",
                    "manifest_fingerprint",
                    "merchant_id",
                    "is_virtual",
                    "virtual_mode",
                    "decision_reason",
                    "rule_id",
                    "rule_version",
                    "source_policy_id",
                    "source_policy_version",
                    "classification_digest",
                    "notes",
                ]
            )
        )
        virtual_merchants = int(classification_df.filter(pl.col("is_virtual")).height)
        lineage_counts = classification_df.select(
            [
                pl.col("rule_id").is_not_null().sum().alias("rule_id_non_null_rows"),
                pl.col("rule_version").is_not_null().sum().alias("rule_version_non_null_rows"),
                pl.col("rule_id").drop_nulls().n_unique().alias("active_rule_id_count"),
            ]
        ).row(0, named=True)
        counts["virtual_merchants"] = virtual_merchants
        counts["rule_id_non_null_rows"] = int(lineage_counts["rule_id_non_null_rows"] or 0)
        counts["rule_version_non_null_rows"] = int(lineage_counts["rule_version_non_null_rows"] or 0)
        counts["active_rule_id_count"] = int(lineage_counts["active_rule_id_count"] or 0)
        timer.info(f"S1: classification complete (virtual_merchants={virtual_merchants}, total={total_merchants})")

        current_phase = "settlement_coords"
        coords_path = verified_assets["virtual_settlement_coords"][1]
        coords_df = pl.read_csv(coords_path, schema_overrides={"merchant_id": pl.UInt64})
        coords_pack, coords_table = _table_pack(schema_3b, "reference/virtual_settlement_coords_v1")
        _inline_external_refs(coords_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(coords_df.iter_rows(named=True), coords_pack, coords_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S1_009_COORD_SCHEMA_INVALID",
                "V-08",
                "coord_schema_invalid",
                {"error": str(exc), "path": str(coords_path)},
                manifest_fingerprint,
            )
        coords_df = coords_df.with_columns(pl.col("merchant_id").cast(pl.UInt64))
        if coords_df.get_column("merchant_id").n_unique() != coords_df.height:
            _abort(
                "E3B_S1_009_COORD_SCHEMA_INVALID",
                "V-08",
                "coord_merchant_duplicate",
                {"path": str(coords_path)},
                manifest_fingerprint,
            )

        coord_version = _resolve_coord_version(coords_path.with_suffix(".provenance.json"))
        current_phase = "settlement_join"
        virtual_ids = classification_df.filter(pl.col("is_virtual")).select(["merchant_id"])
        settlement_df = virtual_ids.join(coords_df, on="merchant_id", how="left")
        if settlement_df.get_column("merchant_id").is_null().any():
            _abort(
                "E3B_S1_010_SETTLEMENT_COORD_MISSING",
                "V-09",
                "settlement_join_failed",
                {"path": str(coords_path)},
                manifest_fingerprint,
            )
        missing_coords = settlement_df.filter(
            pl.col("lat_deg").is_null()
            | pl.col("lon_deg").is_null()
            | pl.col("tzid_settlement").is_null()
        )
        if missing_coords.height > 0:
            sample = missing_coords.select(["merchant_id"]).head(5).to_dicts()
            _abort(
                "E3B_S1_010_SETTLEMENT_COORD_MISSING",
                "V-09",
                "settlement_coords_missing",
                {"missing_count": int(missing_coords.height), "sample": sample},
                manifest_fingerprint,
            )

        merchant_ids = settlement_df.get_column("merchant_id").to_list()
        settlement_ids: list[str] = []
        tracker = _ProgressTracker(len(merchant_ids), logger, "S1: building settlement_site_id")
        for merchant_id in merchant_ids:
            settlement_ids.append(_build_settlement_site_id(int(merchant_id)))
            tracker.update(1)

        settlement_df = settlement_df.with_columns(
            pl.Series("settlement_site_id", settlement_ids),
            pl.lit(int(seed)).alias("seed"),
            pl.lit(str(manifest_fingerprint)).alias("manifest_fingerprint"),
            pl.lit("INGEST").alias("tz_source"),
            pl.lit(settlement_digest).alias("settlement_coord_digest"),
            pl.lit(tz_policy_digest).alias("tz_policy_digest"),
            pl.lit(coord_version).alias("coord_source_version"),
        )
        settlement_df = settlement_df.with_columns(
            pl.when(pl.col("coord_source").is_null() | (pl.col("coord_source") == ""))
            .then(pl.lit("virtual_settlement_coords"))
            .otherwise(pl.col("coord_source"))
            .alias("coord_source_id"),
        )
        settlement_df = settlement_df.select(
            [
                "seed",
                "manifest_fingerprint",
                "merchant_id",
                "settlement_site_id",
                "lat_deg",
                "lon_deg",
                "tzid_settlement",
                "tz_source",
                "coord_source_id",
                "coord_source_version",
                "settlement_coord_digest",
                "tz_policy_digest",
                "evidence_url",
                "notes",
            ]
        )
        settlement_df = settlement_df.sort("merchant_id")
        counts["settlement_rows"] = int(settlement_df.height)
        timer.info(
            f"S1: settlement nodes constructed (rows={settlement_df.height}, coord_version={coord_version})"
        )

        current_phase = "output_validate"
        class_pack, class_table = _table_pack(schema_3b, "plan/virtual_classification_3B")
        settle_pack, settle_table = _table_pack(schema_3b, "plan/virtual_settlement_3B")
        _inline_external_refs(class_pack, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(settle_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(classification_df.iter_rows(named=True), class_pack, class_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S1_011_OUTPUT_SCHEMA_INVALID",
                "V-10",
                "classification_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )
        try:
            validate_dataframe(settlement_df.iter_rows(named=True), settle_pack, settle_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S1_011_OUTPUT_SCHEMA_INVALID",
                "V-10",
                "settlement_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )

        current_phase = "output_write"
        class_entry = find_dataset_entry(dictionary_3b, "virtual_classification_3B").entry
        settle_entry = find_dataset_entry(dictionary_3b, "virtual_settlement_3B").entry
        classification_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        settlement_path = _resolve_dataset_path(settle_entry, run_paths, config.external_roots, tokens)

        tmp_root = run_paths.tmp_root / "s1_virtual_classification"
        class_tmp = tmp_root / "virtual_classification_3B"
        settle_tmp = tmp_root / "virtual_settlement_3B"
        class_tmp.mkdir(parents=True, exist_ok=True)
        settle_tmp.mkdir(parents=True, exist_ok=True)

        classification_df.write_parquet(class_tmp / "part-00000.parquet", compression="zstd")
        settlement_df.write_parquet(settle_tmp / "part-00000.parquet", compression="zstd")

        _atomic_publish_pair(class_tmp, classification_path, settle_tmp, settlement_path, logger)
        timer.info("S1: published virtual classification and settlement datasets")

        status = "PASS"

    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3B_S1_013_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3B_S1_013_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint:
            try:
                run_report_entry = find_dataset_entry(dictionary_3b, "s1_run_report_3B").entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": run_id,
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": {
                        "virtual_rules_policy_id": policy_id,
                        "virtual_rules_policy_version": policy_version,
                        "virtual_rules_digest": policy_digest,
                        "settlement_coord_digest": settlement_digest,
                        "tz_policy_digest": tz_policy_digest,
                        "coord_source_version": coord_version,
                    },
                    "counts": counts,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "virtual_classification_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "virtual_classification_3B").entry, tokens
                        ),
                        "virtual_settlement_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "virtual_settlement_3B").entry, tokens
                        ),
                        "format": "parquet",
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S1: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S1: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3B_S1_013_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if classification_path is None or settlement_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3B_S1_013_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S1Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        classification_path=classification_path,
        settlement_path=settlement_path,
        run_report_path=run_report_path,
    )
