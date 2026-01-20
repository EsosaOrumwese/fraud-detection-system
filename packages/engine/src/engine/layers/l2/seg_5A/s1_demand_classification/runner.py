"""S1 demand classification runner for Segment 5A."""

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

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
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
    _table_pack,
)


MODULE_NAME = "5A.s1_demand_classification"
SEGMENT = "5A"
STATE = "S1"
S1_SPEC_VERSION = "1.0.0"


@dataclass(frozen=True)
class S1Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    profile_path: Path
    class_profile_path: Optional[Path]
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
    logger = get_logger("engine.layers.l2.seg_5A.s1_demand_classification.runner")
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


def _u_det(stage: str, merchant_id: int, legal_country_iso: str, tzid: str, parameter_hash: str) -> float:
    msg = f"5A.scale|{stage}|{merchant_id}|{legal_country_iso}|{tzid}|{parameter_hash}"
    digest = hashlib.sha256(msg.encode("utf-8")).digest()
    x = int.from_bytes(digest[:8], "big", signed=False)
    return (x + 0.5) / 18446744073709551616.0


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


def _publish_parquet_idempotent(path: Path, df: pl.DataFrame, logger, label: str) -> None:
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
                "S1_OUTPUT_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(path), "label": label},
            )
        tmp_path.unlink()
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
        logger.info("S1: output already exists and is identical; skipping publish (%s).", label)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "S1_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(path), "label": label, "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info("S1: published %s to %s", label, path)


def _resolve_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l2.seg_5A.s1_demand_classification.runner")
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
    profile_path: Optional[Path] = None
    class_profile_path: Optional[Path] = None
    run_report_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    seed: int = 0
    policy_class_version = None
    policy_scale_version = None
    scenario_id = None

    counts: dict[str, object] = {
        "domain_rows": 0,
        "merchants_total": 0,
        "zones_total": 0,
        "classes_total": 0,
    }

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
        logger.info("S1: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5a_path, dictionary_5a = load_dataset_dictionary(source, "5A")
        reg_5a_path, registry_5a = load_artefact_registry(source, "5A")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_ingress_layer1_path, schema_ingress_layer1 = load_schema_pack(source, "1A", "ingress.layer1")
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
            "S1: objective=classify merchant-zone demand and base scale "
            "(gate S0 + sealed inputs, domain from zone_alloc, outputs merchant_zone_profile_5A + merchant_class_profile_5A)"
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
                "S1_GATE_RECEIPT_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "S1_GATE_RECEIPT_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_id = receipt_payload.get("scenario_id")
        upstream = receipt_payload.get("verified_upstream_segments") or {}
        for segment_id in ("1A", "1B", "2A", "2B", "3A", "3B"):
            status_value = None
            if isinstance(upstream, dict):
                status_value = (upstream.get(segment_id) or {}).get("status")
            if status_value != "PASS":
                _abort(
                    "S1_UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        if not isinstance(sealed_inputs, list):
            _abort(
                "S1_GATE_RECEIPT_INVALID",
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
                "S1_GATE_RECEIPT_INVALID",
                "V-03",
                "sealed_inputs_duplicate_id",
                {"detail": "duplicate artifact_id in sealed_inputs_5A"},
                manifest_fingerprint,
            )
        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if sealed_digest != receipt_payload.get("sealed_inputs_digest"):
            _abort(
                "S1_GATE_RECEIPT_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {
                    "expected": receipt_payload.get("sealed_inputs_digest"),
                    "actual": sealed_digest,
                },
                manifest_fingerprint,
            )

        sealed_by_id = {row.get("artifact_id"): row for row in sealed_sorted if isinstance(row, dict)}
        zone_alloc_row = _resolve_sealed_row(
            sealed_by_id,
            "zone_alloc",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "S1_REQUIRED_INPUT_MISSING",
        )
        merchant_ids_row = _resolve_sealed_row(
            sealed_by_id,
            "transaction_schema_merchant_ids",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "S1_REQUIRED_INPUT_MISSING",
        )
        class_policy_row = _resolve_sealed_row(
            sealed_by_id,
            "merchant_class_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S1_REQUIRED_POLICY_MISSING",
        )
        scale_policy_row = _resolve_sealed_row(
            sealed_by_id,
            "demand_scale_policy_5A",
            manifest_fingerprint,
            {"METADATA_ONLY", "ROW_LEVEL"},
            True,
            "S1_REQUIRED_POLICY_MISSING",
        )
        virtual_row = _resolve_sealed_row(
            sealed_by_id,
            "virtual_classification_3B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            False,
            "S1_REQUIRED_INPUT_MISSING",
        )
        scenario_manifest_row = _resolve_sealed_row(
            sealed_by_id,
            "scenario_manifest_5A",
            manifest_fingerprint,
            {"ROW_LEVEL", "METADATA_ONLY"},
            False,
            "S1_REQUIRED_INPUT_MISSING",
        )

        current_phase = "policy_load"
        class_policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "merchant_class_policy_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        scale_policy_path = _resolve_dataset_path(
            find_dataset_entry(dictionary_5a, "demand_scale_policy_5A").entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        class_policy = _load_yaml(class_policy_path)
        scale_policy = _load_yaml(scale_policy_path)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "policy/merchant_class_policy_5A", class_policy)
        _validate_payload(schema_5a, schema_layer1, schema_layer2, "policy/demand_scale_policy_5A", scale_policy)

        policy_class_version = class_policy.get("version") if isinstance(class_policy, dict) else None
        policy_scale_version = scale_policy.get("version") if isinstance(scale_policy, dict) else None

        if not isinstance(class_policy, dict) or not isinstance(scale_policy, dict):
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "policy_payload_invalid",
                {"detail": "policy payload is not an object"},
                manifest_fingerprint,
            )

        demand_class_catalog = class_policy.get("demand_class_catalog") or []
        if not isinstance(demand_class_catalog, list) or not demand_class_catalog:
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "class_catalog_missing",
                {"detail": "demand_class_catalog missing or empty"},
                manifest_fingerprint,
            )
        class_order = {entry.get("demand_class"): idx for idx, entry in enumerate(demand_class_catalog)}
        if None in class_order or len(class_order) != len(demand_class_catalog):
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "class_catalog_invalid",
                {"detail": "demand_class_catalog has missing or duplicate ids"},
                manifest_fingerprint,
            )

        mcc_sector_map = class_policy.get("mcc_sector_map") or {}
        channel_group_map = class_policy.get("channel_group_map") or {}
        decision_tree = class_policy.get("decision_tree_v1") or {}
        virtual_branch = decision_tree.get("virtual_branch") or {}
        nonvirtual_branch = decision_tree.get("nonvirtual_branch") or {}
        by_channel = (nonvirtual_branch.get("by_channel_group") or {}) if isinstance(nonvirtual_branch, dict) else {}

        virtual_only_class = virtual_branch.get("virtual_only_class")
        hybrid_class = virtual_branch.get("hybrid_class")
        default_class = decision_tree.get("default_class")

        if not isinstance(mcc_sector_map, dict) or not isinstance(channel_group_map, dict):
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "policy_maps_invalid",
                {"detail": "mcc_sector_map or channel_group_map invalid"},
                manifest_fingerprint,
            )
        if not virtual_only_class or not hybrid_class or not default_class:
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "decision_tree_invalid",
                {"detail": "virtual branch or default_class missing"},
                manifest_fingerprint,
            )

        class_params = scale_policy.get("class_params") or []
        class_param_map = {entry.get("demand_class"): entry for entry in class_params if isinstance(entry, dict)}
        if len(class_param_map) != len(class_params):
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "class_params_invalid",
                {"detail": "class_params has missing demand_class entries"},
                manifest_fingerprint,
            )
        missing_class_params = [cls for cls in class_order if cls not in class_param_map]
        if missing_class_params:
            _abort(
                "S1_REQUIRED_POLICY_MISSING",
                "V-05",
                "class_params_missing",
                {"detail": missing_class_params},
                manifest_fingerprint,
            )

        zone_role_cfg = ((decision_tree.get("subclass_rules") or {}).get("zone_role") or {}) if isinstance(decision_tree, dict) else {}
        primary_share_ge = float(zone_role_cfg.get("primary_share_ge", 0.6))
        tail_share_le = float(zone_role_cfg.get("tail_share_le", 0.1))

        zone_role_multipliers = scale_policy.get("zone_role_multipliers") or {}
        virtual_mode_multipliers = scale_policy.get("virtual_mode_multipliers") or {}
        channel_group_multipliers = scale_policy.get("channel_group_multipliers") or {}
        thresholds = scale_policy.get("thresholds") or {}
        realism_targets = scale_policy.get("realism_targets") or {}

        weekly_volume_unit = scale_policy.get("weekly_volume_unit") or "arrivals_per_local_week"
        global_multiplier = float(scale_policy.get("global_multiplier") or 1.0)
        brand_size_exponent = float(scale_policy.get("brand_size_exponent") or 0.0)
        low_volume_threshold = float(thresholds.get("low_volume_weekly_lt") or 0.0)
        max_weekly_volume = realism_targets.get("max_weekly_volume_expected")

        current_phase = "domain_build"
        zone_alloc_entry = find_dataset_entry(dictionary_5a, "zone_alloc").entry
        zone_alloc_path = _resolve_dataset_path(zone_alloc_entry, run_paths, config.external_roots, tokens)
        zone_alloc_df = pl.read_parquet(zone_alloc_path)
        zone_pack, zone_table = _table_pack(schema_3a, "egress/zone_alloc")
        _inline_external_refs(zone_pack, schema_layer1, "schemas.layer1.yaml#")
        validate_dataframe(zone_alloc_df.iter_rows(named=True), zone_pack, zone_table)
        zone_alloc_df = zone_alloc_df.select(
            [
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "zone_site_count",
                "zone_site_count_sum",
            ]
        )

        zone_stats = zone_alloc_df.group_by(["merchant_id", "legal_country_iso"]).agg(
            pl.col("tzid").n_unique().alias("zones_per_merchant_country")
        )
        zone_df = zone_alloc_df.join(zone_stats, on=["merchant_id", "legal_country_iso"], how="left").with_columns(
            [
                pl.col("zone_site_count_sum").alias("merchant_country_site_count"),
                pl.when(pl.col("zone_site_count_sum") > 0)
                .then(pl.col("zone_site_count") / pl.col("zone_site_count_sum"))
                .otherwise(0.0)
                .alias("zone_site_share"),
            ]
        )
        zone_df = zone_df.with_columns(
            pl.when(pl.col("zone_site_count_sum") <= 0)
            .then(pl.lit("tail_zone"))
            .when(pl.col("zone_site_share") >= primary_share_ge)
            .then(pl.lit("primary_zone"))
            .when(pl.col("zone_site_share") <= tail_share_le)
            .then(pl.lit("tail_zone"))
            .otherwise(pl.lit("secondary_zone"))
            .alias("zone_role")
        )

        counts["domain_rows"] = zone_df.height
        counts["merchants_total"] = zone_df.select("merchant_id").unique().height
        counts["zones_total"] = zone_df.select("tzid").unique().height

        logger.info(
            "S1: domain built from zone_alloc (rows=%d, merchants=%d, zones=%d)",
            counts["domain_rows"],
            counts["merchants_total"],
            counts["zones_total"],
        )

        current_phase = "merchant_attributes"
        merchant_ids_entry = find_dataset_entry(dictionary_5a, "transaction_schema_merchant_ids").entry
        merchant_version = str(merchant_ids_row.get("version") or "").strip()
        tokens_with_version = dict(tokens)
        if merchant_version:
            tokens_with_version["version"] = merchant_version
        merchant_ids_path = _resolve_dataset_path(
            merchant_ids_entry, run_paths, config.external_roots, tokens_with_version
        )
        merchant_files = _resolve_parquet_files(merchant_ids_path)
        merchant_df = pl.read_parquet(merchant_files).select(
            ["merchant_id", "mcc", "channel", "home_country_iso"]
        )
        merchant_pack, merchant_table = _table_pack(schema_ingress_layer1, "merchant_ids")
        _inline_external_refs(merchant_pack, schema_layer1, "schemas.layer1.yaml#")
        validate_dataframe(merchant_df.iter_rows(named=True), merchant_pack, merchant_table)

        mcc_map_df = pl.DataFrame(
            {"mcc_str": list(mcc_sector_map.keys()), "mcc_sector": list(mcc_sector_map.values())}
        )
        channel_map_df = pl.DataFrame(
            {"channel": list(channel_group_map.keys()), "channel_group": list(channel_group_map.values())}
        )

        features_df = zone_df.join(merchant_df, on="merchant_id", how="left").with_columns(
            pl.col("mcc").cast(pl.Utf8).str.zfill(4).alias("mcc_str")
        )
        features_df = features_df.join(mcc_map_df, on="mcc_str", how="left")
        features_df = features_df.join(channel_map_df, on="channel", how="left")

        missing_mcc = features_df.filter(pl.col("mcc_sector").is_null()).height
        missing_channel = features_df.filter(pl.col("channel_group").is_null()).height
        if missing_mcc or missing_channel:
            _abort(
                "S1_FEATURE_DERIVATION_FAILED",
                "V-06",
                "merchant_attributes_unmapped",
                {"missing_mcc": missing_mcc, "missing_channel": missing_channel},
                manifest_fingerprint,
            )

        current_phase = "virtual_flags"
        if virtual_row:
            virtual_entry = find_dataset_entry(dictionary_5a, "virtual_classification_3B").entry
            virtual_path = _resolve_dataset_path(virtual_entry, run_paths, config.external_roots, tokens)
            virtual_df = pl.read_parquet(virtual_path)
            virtual_pack, virtual_table = _table_pack(schema_3b, "plan/virtual_classification_3B")
            _inline_external_refs(virtual_pack, schema_layer1, "schemas.layer1.yaml#")
            validate_dataframe(virtual_df.iter_rows(named=True), virtual_pack, virtual_table)
            virtual_df = virtual_df.select(["merchant_id", "virtual_mode", "is_virtual"])
            features_df = features_df.join(virtual_df, on="merchant_id", how="left")
            missing_virtual = features_df.filter(pl.col("virtual_mode").is_null()).height
            if missing_virtual:
                _abort(
                    "S1_FEATURE_DERIVATION_FAILED",
                    "V-06",
                    "virtual_flags_missing",
                    {"missing_virtual": missing_virtual},
                    manifest_fingerprint,
                )
        else:
            features_df = features_df.with_columns(
                [pl.lit("NON_VIRTUAL").alias("virtual_mode"), pl.lit(False).alias("is_virtual")]
            )

        if scenario_manifest_row:
            logger.info("S1: scenario_manifest_5A present for scenario_id=%s", scenario_id)
        else:
            logger.info("S1: scenario_manifest_5A missing; proceeding without scenario traits")

        current_phase = "classify_and_scale"
        total_rows = features_df.height
        tracker = _ProgressTracker(total_rows, logger, "S1: classify+scale rows")

        merchant_ids = features_df.get_column("merchant_id").to_list()
        countries = features_df.get_column("legal_country_iso").to_list()
        tzids = features_df.get_column("tzid").to_list()
        zone_site_counts = features_df.get_column("zone_site_count").to_list()
        merchant_country_counts = features_df.get_column("merchant_country_site_count").to_list()
        zone_roles = features_df.get_column("zone_role").to_list()
        mcc_sectors = features_df.get_column("mcc_sector").to_list()
        channel_groups = features_df.get_column("channel_group").to_list()
        virtual_modes = features_df.get_column("virtual_mode").to_list()

        demand_classes: list[str] = []
        demand_subclasses: list[Optional[str]] = []
        profile_ids: list[Optional[str]] = []
        class_sources: list[str] = []
        weekly_volume_expected: list[float] = []
        scale_factors: list[float] = []
        high_variability_flags: list[bool] = []
        low_volume_flags: list[bool] = []
        virtual_preferred_flags: list[bool] = []

        for idx in range(total_rows):
            tracker.update(1)
            merchant_id = merchant_ids[idx]
            legal_country_iso = countries[idx]
            tzid = tzids[idx]
            zone_site_count = int(zone_site_counts[idx])
            merchant_country_count = int(merchant_country_counts[idx])
            zone_role = zone_roles[idx]
            mcc_sector = mcc_sectors[idx]
            channel_group = channel_groups[idx]
            virtual_mode = virtual_modes[idx]

            if virtual_mode in {"VIRTUAL_ONLY", "HYBRID"}:
                demand_class = virtual_only_class if virtual_mode == "VIRTUAL_ONLY" else hybrid_class
                class_source = "virtual_branch"
            else:
                channel_branch = by_channel.get(channel_group, {})
                if isinstance(channel_branch, dict) and "by_sector" in channel_branch:
                    channel_branch = channel_branch.get("by_sector") or {}
                demand_class = channel_branch.get(mcc_sector) if isinstance(channel_branch, dict) else None
                class_source = f"nonvirtual_branch.{channel_group}.{mcc_sector}"
                if not demand_class:
                    _abort(
                        "S1_CLASS_ASSIGNMENT_FAILED",
                        "V-07",
                        "class_assignment_missing",
                        {
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "tzid": tzid,
                            "channel_group": channel_group,
                            "mcc_sector": mcc_sector,
                        },
                        manifest_fingerprint,
                    )
            if demand_class not in class_param_map:
                _abort(
                    "S1_CLASS_ASSIGNMENT_FAILED",
                    "V-07",
                    "class_assignment_failed",
                    {
                        "merchant_id": merchant_id,
                        "legal_country_iso": legal_country_iso,
                        "tzid": tzid,
                        "demand_class": demand_class,
                    },
                    manifest_fingerprint,
                )

            demand_subclass = zone_role if zone_role else None
            profile_id = None
            if demand_subclass and channel_group:
                profile_id = f"{demand_class}.{demand_subclass}.{channel_group}"
                if len(profile_id) > 64:
                    _abort(
                        "S1_CLASS_ASSIGNMENT_FAILED",
                        "V-07",
                        "profile_id_too_long",
                        {"profile_id": profile_id, "merchant_id": merchant_id},
                        manifest_fingerprint,
                    )

            params = class_param_map[demand_class]
            median_per_site = float(params.get("median_per_site_weekly"))
            pareto_alpha = float(params.get("pareto_alpha"))
            clip_max = float(params.get("clip_max_per_site_weekly"))
            ref_per_site = float(params.get("ref_per_site_weekly"))
            high_variability = bool(params.get("high_variability_flag"))

            u = _u_det("per_site", merchant_id, legal_country_iso, tzid, str(parameter_hash))
            x_m = median_per_site / (2.0 ** (1.0 / pareto_alpha))
            per_site_weekly = x_m / ((1.0 - u) ** (1.0 / pareto_alpha))
            if per_site_weekly > clip_max:
                per_site_weekly = clip_max

            zone_mult = float(zone_role_multipliers.get(zone_role, 1.0))
            brand_size = max(1, merchant_country_count)
            brand_mult = brand_size ** brand_size_exponent
            virtual_mult = float(virtual_mode_multipliers.get(virtual_mode, 1.0))
            channel_mult = float(channel_group_multipliers.get(channel_group, 1.0))

            if zone_site_count <= 0:
                weekly = 0.0
                scale_factor = 0.0
            else:
                weekly = (
                    global_multiplier
                    * zone_site_count
                    * per_site_weekly
                    * zone_mult
                    * brand_mult
                    * virtual_mult
                    * channel_mult
                )
                scale_factor = weekly / (zone_site_count * ref_per_site) if ref_per_site > 0 else 0.0

            if weekly < 0 or math.isnan(weekly) or math.isinf(weekly):
                _abort(
                    "S1_SCALE_ASSIGNMENT_FAILED",
                    "V-08",
                    "scale_invalid",
                    {"merchant_id": merchant_id, "weekly_volume_expected": weekly},
                    manifest_fingerprint,
                )
            if max_weekly_volume is not None and weekly > float(max_weekly_volume):
                _abort(
                    "S1_SCALE_ASSIGNMENT_FAILED",
                    "V-08",
                    "scale_exceeds_max",
                    {"merchant_id": merchant_id, "weekly_volume_expected": weekly},
                    manifest_fingerprint,
                )

            demand_classes.append(demand_class)
            demand_subclasses.append(demand_subclass)
            profile_ids.append(profile_id)
            class_sources.append(class_source)
            weekly_volume_expected.append(float(weekly))
            scale_factors.append(float(scale_factor))
            high_variability_flags.append(high_variability)
            low_volume_flags.append(float(weekly) < low_volume_threshold)
            virtual_preferred_flags.append(virtual_mode != "NON_VIRTUAL")

        counts["classes_total"] = len(set(demand_classes))

        profile_df = (
            pl.DataFrame(
                {
                    "manifest_fingerprint": [manifest_fingerprint] * total_rows,
                    "parameter_hash": [parameter_hash] * total_rows,
                    "merchant_id": merchant_ids,
                    "legal_country_iso": countries,
                    "tzid": tzids,
                    "demand_class": demand_classes,
                    "demand_subclass": demand_subclasses,
                    "profile_id": profile_ids,
                    "weekly_volume_expected": weekly_volume_expected,
                    "weekly_volume_unit": [weekly_volume_unit] * total_rows,
                    "scale_factor": scale_factors,
                    "high_variability_flag": high_variability_flags,
                    "low_volume_flag": low_volume_flags,
                    "virtual_preferred_flag": virtual_preferred_flags,
                    "class_source": class_sources,
                }
            )
            .with_columns(pl.lit(S1_SPEC_VERSION).alias("s1_spec_version"))
            .sort(["merchant_id", "legal_country_iso", "tzid"])
        )

        _validate_array_rows(
            profile_df.iter_rows(named=True),
            schema_5a,
            schema_layer1,
            schema_layer2,
            "model/merchant_zone_profile_5A",
        )

        if profile_df.height != zone_df.height:
            _abort(
                "S1_DOMAIN_ALIGNMENT_FAILED",
                "V-09",
                "domain_mismatch",
                {"expected": zone_df.height, "actual": profile_df.height},
                manifest_fingerprint,
            )

        current_phase = "class_profile"
        class_profile_rows: list[dict] = []
        class_profile_emitted = True
        if total_rows:
            volume_by_merchant: dict[int, dict[str, float]] = {}
            count_by_merchant: dict[int, dict[str, int]] = {}
            total_by_merchant: dict[int, float] = {}

            tracker = _ProgressTracker(total_rows, logger, "S1: aggregate class profile rows")
            for idx in range(total_rows):
                tracker.update(1)
                merchant_id = merchant_ids[idx]
                demand_class = demand_classes[idx]
                weekly = weekly_volume_expected[idx]
                volume_by_merchant.setdefault(merchant_id, {})
                count_by_merchant.setdefault(merchant_id, {})
                total_by_merchant[merchant_id] = total_by_merchant.get(merchant_id, 0.0) + weekly
                volume_by_merchant[merchant_id][demand_class] = (
                    volume_by_merchant[merchant_id].get(demand_class, 0.0) + weekly
                )
                count_by_merchant[merchant_id][demand_class] = (
                    count_by_merchant[merchant_id].get(demand_class, 0) + 1
                )

            tracker = _ProgressTracker(len(total_by_merchant), logger, "S1: build class profile rows")
            for merchant_id, total_volume in total_by_merchant.items():
                tracker.update(1)
                class_volume = volume_by_merchant.get(merchant_id, {})
                class_counts = count_by_merchant.get(merchant_id, {})
                if total_volume > 0:
                    metric = class_volume
                else:
                    metric = {cls: float(count) for cls, count in class_counts.items()}
                primary_class = None
                best_value = -1.0
                for cls, value in metric.items():
                    if value > best_value:
                        best_value = value
                        primary_class = cls
                    elif value == best_value and primary_class is not None:
                        if class_order.get(cls, 999999) < class_order.get(primary_class, 999999):
                            primary_class = cls
                classes_seen = sorted(class_counts.keys(), key=lambda cls: class_order.get(cls, 999999))
                class_profile_rows.append(
                    {
                        "manifest_fingerprint": manifest_fingerprint,
                        "parameter_hash": parameter_hash,
                        "merchant_id": merchant_id,
                        "primary_demand_class": primary_class,
                        "classes_seen": classes_seen,
                        "weekly_volume_total_expected": total_volume,
                    }
                )
        else:
            class_profile_emitted = False

        class_profile_df = None
        if class_profile_emitted:
            class_profile_df = pl.DataFrame(
                class_profile_rows, schema_overrides={"merchant_id": pl.UInt64}
            ).sort("merchant_id")
            _validate_array_rows(
                class_profile_df.iter_rows(named=True),
                schema_5a,
                schema_layer1,
                schema_layer2,
                "model/merchant_class_profile_5A",
            )

        current_phase = "output_write"
        profile_entry = find_dataset_entry(dictionary_5a, "merchant_zone_profile_5A").entry
        profile_path = _resolve_dataset_path(profile_entry, run_paths, config.external_roots, tokens)
        _publish_parquet_idempotent(profile_path, profile_df, logger, "merchant_zone_profile_5A")

        if class_profile_emitted and class_profile_df is not None:
            class_entry = find_dataset_entry(dictionary_5a, "merchant_class_profile_5A").entry
            class_profile_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
            _publish_parquet_idempotent(class_profile_path, class_profile_df, logger, "merchant_class_profile_5A")
        else:
            logger.info("S1: merchant_class_profile_5A not emitted (empty domain)")

        status = "PASS"
        timer.info("S1: completed demand classing and scale derivation")

    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "S1_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "S1_IO_READ_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint and run_paths is not None:
            try:
                run_report_entry = find_dataset_entry(dictionary_5a, "s1_run_report_5A").entry
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
                    "policy": {
                        "merchant_class_policy_version": policy_class_version,
                        "demand_scale_policy_version": policy_scale_version,
                    },
                    "scenario_id": scenario_id,
                    "counts": counts,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "merchant_zone_profile_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_zone_profile_5A").entry,
                            tokens,
                        ),
                        "merchant_class_profile_path": _render_catalog_path(
                            find_dataset_entry(dictionary_5a, "merchant_class_profile_5A").entry,
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
                logger.info("S1: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S1: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "S1_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if profile_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "S1_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S1Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        profile_path=profile_path,
        class_profile_path=class_profile_path,
        run_report_path=run_report_path,
    )
