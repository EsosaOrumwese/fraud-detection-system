from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import (
    find_dataset_entry,
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
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_3A.s0_gate.runner import (
    _append_jsonl,
    _inline_external_refs,
    _load_json,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _segment_state_runs_path,
    _table_pack,
)


MODULE_NAME = "3A.s4_zone_counts"
SEGMENT = "3A"
STATE = "S4"

TOLERANCE = 1e-12


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_path: Path
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
    logger = get_logger("engine.layers.l1.seg_3A.s4_zone_counts.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _load_sealed_inputs(path: Path) -> list[dict]:
    try:
        payload = _load_json(path)
    except (InputResolutionError, json.JSONDecodeError):
        if path.suffix.lower() == ".parquet":
            return pl.read_parquet(path).to_dicts()
        raise
    if not isinstance(payload, list):
        raise InputResolutionError("sealed_inputs_3A payload is not a list")
    return payload


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _publish_partition(tmp_root: Path, final_root: Path, df: pl.DataFrame, logger) -> None:
    if final_root.exists():
        existing_df = pl.read_parquet(str(final_root / "*.parquet"))
        existing_df = existing_df.sort(["merchant_id", "legal_country_iso", "tzid"])
        if df.equals(existing_df):
            for path in tmp_root.rglob("*"):
                if path.is_file():
                    path.unlink()
            try:
                tmp_root.rmdir()
            except OSError:
                pass
            logger.info("S4: s4_zone_counts already exists and is identical; skipping publish.")
            return
        difference_kind = "row_set"
        difference_count = abs(df.height - existing_df.height)
        if df.height == existing_df.height and df.columns == existing_df.columns:
            difference_kind = "field_value"
            diff_left = df.join(existing_df, on=df.columns, how="anti")
            diff_right = existing_df.join(df, on=df.columns, how="anti")
            difference_count = diff_left.height + diff_right.height
        raise EngineFailure(
            "F4",
            "E3A_S4_008_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {
                "detail": "non-identical output exists",
                "difference_kind": difference_kind,
                "difference_count": int(difference_count),
                "partition": str(final_root),
            },
        )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _error_class_label(error_code: Optional[str]) -> Optional[str]:
    mapping = {
        "E3A_S4_001_PRECONDITION_FAILED": "PRECONDITION",
        "E3A_S4_002_CATALOGUE_MALFORMED": "CATALOGUE",
        "E3A_S4_003_DOMAIN_MISMATCH_S1": "DOMAIN_S1",
        "E3A_S4_004_DOMAIN_MISMATCH_ZONES": "DOMAIN_ZONES",
        "E3A_S4_005_COUNT_CONSERVATION_BROKEN": "COUNT_CONSERVATION",
        "E3A_S4_006_OUTPUT_SCHEMA_INVALID": "OUTPUT_SCHEMA",
        "E3A_S4_007_OUTPUT_INCONSISTENT": "OUTPUT_INCONSISTENT",
        "E3A_S4_008_IMMUTABILITY_VIOLATION": "IMMUTABILITY",
        "E3A_S4_009_INFRASTRUCTURE_IO_ERROR": "INFRASTRUCTURE",
    }
    if not error_code:
        return None
    return mapping.get(error_code)


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l1.seg_3A.s4_zone_counts.l2.runner")
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
    run_id_value: Optional[str] = None
    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None
    output_catalog_path: Optional[str] = None

    counts = {
        "pairs_total": 0,
        "pairs_escalated": 0,
        "pairs_monolithic": 0,
        "zone_rows_total": 0,
        "zones_per_pair_avg": 0.0,
        "zones_zero_allocated": 0,
        "pairs_with_single_zone_nonzero": 0,
        "pairs_count_conserved": 0,
        "pairs_count_conservation_violations": 0,
    }

    prior_pack_id: Optional[str] = None
    prior_pack_version: Optional[str] = None
    floor_policy_id: Optional[str] = None
    floor_policy_version: Optional[str] = None

    start_logged = False
    current_phase = "run_receipt"

    try:
        _receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        seed = int(receipt.get("seed") or 0)
        parameter_hash = str(receipt.get("parameter_hash") or "")
        manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
        if not run_id_value or not parameter_hash or not manifest_fingerprint:
            raise InputResolutionError("run_receipt missing run_id, parameter_hash, or manifest_fingerprint.")

        run_paths = RunPaths(config.runs_root, run_id_value)
        run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
        add_file_handler(run_log_path)
        timer.info(f"S4: run log initialized at {run_log_path}")

        logger.info(
            "S4: objective=integerise zone counts for escalated merchant-country pairs "
            "(S1 site_count + S3 shares) -> outputs (s4_zone_counts)"
        )

        tokens = {
            "seed": str(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id_value,
        }

        _emit_event(
            logger,
            "STATE_START",
            manifest_fingerprint,
            "INFO",
            layer="layer1",
            segment=SEGMENT,
            state=STATE,
            parameter_hash=parameter_hash,
            seed=seed,
            run_id=run_id_value,
            attempt=1,
        )
        start_logged = True

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        timer.info("S4: contracts loaded")

        current_phase = "s0_gate"
        s0_entry = find_dataset_entry(dictionary, "s0_gate_receipt_3A").entry
        try:
            s0_path = _resolve_dataset_path(s0_entry, run_paths, config.external_roots, tokens)
            s0_gate = _load_json(s0_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-01",
                "s0_gate_missing",
                {"component": "S0_GATE", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s0_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A")
        s0_errors = list(Draft202012Validator(s0_schema).iter_errors(s0_gate))
        if s0_errors:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-01",
                "s0_gate_schema_invalid",
                {"component": "S0_GATE", "reason": "schema_invalid", "error": str(s0_errors[0])},
                manifest_fingerprint,
            )
        upstream_gates = s0_gate.get("upstream_gates") or {}
        for segment in ("1A", "1B", "2A"):
            status_value = (upstream_gates.get(f"segment_{segment}") or {}).get("status")
            if status_value != "PASS":
                _abort(
                    "E3A_S4_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_gate_not_pass",
                    {
                        "component": "S0_GATE",
                        "reason": "upstream_gate_not_pass",
                        "segment": segment,
                        "reported_status": status_value,
                    },
                    manifest_fingerprint,
                )

        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_3A").entry
        try:
            sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
            sealed_inputs = _load_sealed_inputs(sealed_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_inputs_missing",
                {"component": "S0_SEALED_INPUTS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_from_pack(schema_3a, "validation/sealed_inputs_3A")
        _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
        sealed_validator = Draft202012Validator(normalize_nullable_schema(sealed_schema))
        for row in sealed_inputs:
            errors = list(sealed_validator.iter_errors(row))
            if errors:
                _abort(
                    "E3A_S4_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_schema_invalid",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )

        sealed_policy_set = s0_gate.get("sealed_policy_set") or []
        sealed_policy_ids = {str(item.get("logical_id") or "") for item in sealed_policy_set}
        missing_policies = sorted(
            policy_id
            for policy_id in ("zone_mixture_policy", "country_zone_alphas", "zone_floor_policy")
            if policy_id not in sealed_policy_ids
        )
        if missing_policies:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_policy_missing",
                {"component": "S0_GATE", "reason": "missing", "missing_policies": missing_policies},
                manifest_fingerprint,
            )

        timer.info("S4: S0 gate + sealed inputs verified")

        current_phase = "s1_run_report"
        run_report_schema = normalize_nullable_schema(_schema_from_pack(schema_layer1, "run_report/segment_state_run"))
        run_report_validator = Draft202012Validator(run_report_schema)

        def _require_run_report(entry_id: str, component: str, state_label: str) -> None:
            report_entry = find_dataset_entry(dictionary, entry_id).entry
            report_path = _resolve_dataset_path(report_entry, run_paths, config.external_roots, tokens)
            try:
                report_payload = _load_json(report_path)
            except InputResolutionError:
                _abort(
                    "E3A_S4_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_run_report_missing",
                    {"component": component, "reason": "missing", "detail": entry_id},
                    manifest_fingerprint,
                )
                return
            errors = list(run_report_validator.iter_errors(report_payload))
            if errors:
                _abort(
                    "E3A_S4_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_run_report_schema_invalid",
                    {"component": component, "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )
            status_value = report_payload.get("status")
            if status_value != "PASS":
                _abort(
                    "E3A_S4_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_state_not_pass",
                    {
                        "component": component,
                        "reason": "upstream_state_not_pass",
                        "state": state_label,
                        "reported_status": status_value,
                    },
                    manifest_fingerprint,
                )

        _require_run_report("s1_run_report_3A", "S1_ESCALATION_QUEUE", "S1")
        _require_run_report("s2_run_report_3A", "S2_PRIORS", "S2")
        _require_run_report("s3_run_report_3A", "S3_ZONE_SHARES", "S3")

        current_phase = "s1_escalation_queue"
        s1_entry = find_dataset_entry(dictionary, "s1_escalation_queue").entry
        try:
            s1_path = _resolve_dataset_path(s1_entry, run_paths, config.external_roots, tokens)
            s1_paths = _list_parquet_paths(s1_path)
            s1_df = pl.read_parquet(s1_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-02",
                "s1_escalation_missing",
                {"component": "S1_ESCALATION_QUEUE", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s1_pack, s1_table = _table_pack(schema_3a, "plan/s1_escalation_queue")
        _inline_external_refs(s1_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s1_df.iter_rows(named=True), s1_pack, s1_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-02",
                "s1_escalation_schema_invalid",
                {"component": "S1_ESCALATION_QUEUE", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        counts["pairs_total"] = s1_df.height
        s1_pairs = s1_df.select(["merchant_id", "legal_country_iso"])
        if s1_pairs.unique().height != s1_pairs.height:
            _abort(
                "E3A_S4_003_DOMAIN_MISMATCH_S1",
                "V-02",
                "s1_duplicate_pairs",
                {
                    "missing_escalated_pairs_count": 0,
                    "unexpected_pairs_count": 0,
                    "detail": "duplicate merchant-country pairs in s1_escalation_queue",
                },
                manifest_fingerprint,
            )

        esc_df = s1_df.filter(pl.col("is_escalated") == True)  # noqa: E712
        esc_df = esc_df.select(["merchant_id", "legal_country_iso", "site_count"]).sort(
            ["merchant_id", "legal_country_iso"]
        )
        escalated_pairs = list(esc_df.select(["merchant_id", "legal_country_iso"]).iter_rows())
        counts["pairs_escalated"] = len(escalated_pairs)
        counts["pairs_monolithic"] = counts["pairs_total"] - counts["pairs_escalated"]

        site_count_map: dict[tuple[int, str], int] = {}
        for merchant_id, country_iso, site_count in esc_df.iter_rows():
            site_count_value = int(site_count)
            if site_count_value < 1:
                _abort(
                    "E3A_S4_003_DOMAIN_MISMATCH_S1",
                    "V-02",
                    "site_count_invalid",
                    {
                        "missing_escalated_pairs_count": 0,
                        "unexpected_pairs_count": 0,
                        "sample_merchant_id": int(merchant_id),
                        "sample_country_iso": str(country_iso),
                        "detail": "site_count_invalid",
                    },
                    manifest_fingerprint,
                )
            site_count_map[(int(merchant_id), str(country_iso))] = site_count_value

        logger.info(
            "S4: escalation queue loaded (pairs_total=%d escalated_pairs=%d)",
            counts["pairs_total"],
            counts["pairs_escalated"],
        )

        current_phase = "s2_priors"
        s2_entry = find_dataset_entry(dictionary, "s2_country_zone_priors").entry
        try:
            s2_path = _resolve_dataset_path(s2_entry, run_paths, config.external_roots, tokens)
            s2_paths = _list_parquet_paths(s2_path)
            s2_df = pl.read_parquet(s2_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-03",
                "s2_priors_missing",
                {"component": "S2_PRIORS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s2_pack, s2_table = _table_pack(schema_3a, "plan/s2_country_zone_priors")
        _inline_external_refs(s2_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s2_df.iter_rows(named=True), s2_pack, s2_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-03",
                "s2_priors_schema_invalid",
                {"component": "S2_PRIORS", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        s2_pairs = s2_df.select(["country_iso", "tzid"])
        if s2_pairs.unique().height != s2_pairs.height:
            _abort(
                "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                "V-03",
                "s2_duplicate_country_tzid",
                {"affected_pairs_count": 0, "detail": "duplicate country_iso/tzid rows in s2_country_zone_priors"},
                manifest_fingerprint,
            )

        unique_prior_ids = s2_df.select("prior_pack_id").unique()
        unique_prior_versions = s2_df.select("prior_pack_version").unique()
        unique_floor_ids = s2_df.select("floor_policy_id").unique()
        unique_floor_versions = s2_df.select("floor_policy_version").unique()
        if (
            unique_prior_ids.height != 1
            or unique_prior_versions.height != 1
            or unique_floor_ids.height != 1
            or unique_floor_versions.height != 1
        ):
            _abort(
                "E3A_S4_007_OUTPUT_INCONSISTENT",
                "V-03",
                "lineage_inconsistent",
                {
                    "reason": "lineage_inconsistent",
                    "prior_pack_id": unique_prior_ids.to_series().to_list(),
                    "prior_pack_version": unique_prior_versions.to_series().to_list(),
                    "floor_policy_id": unique_floor_ids.to_series().to_list(),
                    "floor_policy_version": unique_floor_versions.to_series().to_list(),
                },
                manifest_fingerprint,
            )
        prior_pack_id = str(unique_prior_ids.to_series()[0])
        prior_pack_version = str(unique_prior_versions.to_series()[0])
        floor_policy_id = str(unique_floor_ids.to_series()[0])
        floor_policy_version = str(unique_floor_versions.to_series()[0])

        zones_by_country: dict[str, list[str]] = {}
        alpha_sum_by_country: dict[str, float] = {}
        for country_key, group in s2_df.partition_by("country_iso", as_dict=True).items():
            country_iso = country_key[0] if isinstance(country_key, tuple) else country_key
            country_iso = str(country_iso)
            tzids = sorted(group["tzid"].to_list())
            if not tzids:
                _abort(
                    "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                    "V-03",
                    "zones_empty",
                    {"affected_pairs_count": 0, "sample_country_iso": country_iso},
                    manifest_fingerprint,
                )
            alpha_unique = group.select("alpha_sum_country").unique()
            if alpha_unique.height != 1:
                _abort(
                    "E3A_S4_007_OUTPUT_INCONSISTENT",
                    "V-03",
                    "alpha_sum_inconsistent",
                    {"reason": "lineage_inconsistent", "sample_country_iso": country_iso},
                    manifest_fingerprint,
                )
            alpha_sum_value = float(alpha_unique.to_series()[0])
            if not math.isfinite(alpha_sum_value) or alpha_sum_value <= 0.0:
                _abort(
                    "E3A_S4_007_OUTPUT_INCONSISTENT",
                    "V-03",
                    "alpha_sum_invalid",
                    {"reason": "lineage_inconsistent", "sample_country_iso": country_iso},
                    manifest_fingerprint,
                )
            zones_by_country[country_iso] = tzids
            alpha_sum_by_country[country_iso] = alpha_sum_value

        escalated_countries = sorted({country for _merchant, country in escalated_pairs})
        missing_countries = [c for c in escalated_countries if c not in zones_by_country]
        if missing_countries:
            _abort(
                "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                "V-03",
                "prior_surface_incomplete",
                {"affected_pairs_count": len(missing_countries), "sample_country_iso": missing_countries[0]},
                manifest_fingerprint,
            )

        timer.info("S4: priors loaded and validated")

        current_phase = "s3_zone_shares"
        s3_entry = find_dataset_entry(dictionary, "s3_zone_shares").entry
        try:
            s3_path = _resolve_dataset_path(s3_entry, run_paths, config.external_roots, tokens)
            s3_paths = _list_parquet_paths(s3_path)
            s3_df = pl.read_parquet(s3_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-04",
                "s3_zone_shares_missing",
                {"component": "S3_ZONE_SHARES", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s3_pack, s3_table = _table_pack(schema_3a, "plan/s3_zone_shares")
        _inline_external_refs(s3_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s3_df.iter_rows(named=True), s3_pack, s3_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S4_001_PRECONDITION_FAILED",
                "V-04",
                "s3_zone_shares_schema_invalid",
                {"component": "S3_ZONE_SHARES", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        s3_pairs = s3_df.select(["merchant_id", "legal_country_iso", "tzid"])
        if s3_pairs.unique().height != s3_pairs.height:
            _abort(
                "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                "V-04",
                "s3_duplicate_rows",
                {"affected_pairs_count": 0, "detail": "duplicate merchant-country-tzid rows in s3_zone_shares"},
                manifest_fingerprint,
            )

        s3_unique_pairs = {
            (int(row[0]), str(row[1]))
            for row in s3_df.select(["merchant_id", "legal_country_iso"]).unique().iter_rows()
        }
        esc_pair_set = {(int(m), str(c)) for m, c in escalated_pairs}
        missing_pairs = sorted(esc_pair_set - s3_unique_pairs)
        unexpected_pairs = sorted(s3_unique_pairs - esc_pair_set)
        if missing_pairs or unexpected_pairs:
            sample_pair = missing_pairs[0] if missing_pairs else unexpected_pairs[0]
            _abort(
                "E3A_S4_003_DOMAIN_MISMATCH_S1",
                "V-04",
                "s3_domain_mismatch",
                {
                    "missing_escalated_pairs_count": len(missing_pairs),
                    "unexpected_pairs_count": len(unexpected_pairs),
                    "sample_merchant_id": int(sample_pair[0]),
                    "sample_country_iso": str(sample_pair[1]),
                },
                manifest_fingerprint,
            )

        s3_unique_prior_ids = s3_df.select("prior_pack_id").unique()
        s3_unique_prior_versions = s3_df.select("prior_pack_version").unique()
        s3_unique_floor_ids = s3_df.select("floor_policy_id").unique()
        s3_unique_floor_versions = s3_df.select("floor_policy_version").unique()
        if (
            s3_unique_prior_ids.height != 1
            or s3_unique_prior_versions.height != 1
            or s3_unique_floor_ids.height != 1
            or s3_unique_floor_versions.height != 1
        ):
            _abort(
                "E3A_S4_007_OUTPUT_INCONSISTENT",
                "V-04",
                "s3_lineage_inconsistent",
                {"reason": "lineage_inconsistent"},
                manifest_fingerprint,
            )
        if (
            str(s3_unique_prior_ids.to_series()[0]) != prior_pack_id
            or str(s3_unique_prior_versions.to_series()[0]) != prior_pack_version
            or str(s3_unique_floor_ids.to_series()[0]) != floor_policy_id
            or str(s3_unique_floor_versions.to_series()[0]) != floor_policy_version
        ):
            _abort(
                "E3A_S4_007_OUTPUT_INCONSISTENT",
                "V-04",
                "s3_lineage_mismatch",
                {"reason": "lineage_inconsistent"},
                manifest_fingerprint,
            )

        s3_by_pair = s3_df.partition_by(["merchant_id", "legal_country_iso"], as_dict=True)

        logger.info("S4: shares loaded and validated (pairs_escalated=%d)", counts["pairs_escalated"])

        current_phase = "integerisation"
        logger.info(
            "S4: entering integerisation loop for escalated pairs; targets=%d",
            counts["pairs_escalated"],
        )
        tracker = _ProgressTracker(counts["pairs_escalated"], logger, "S4 progress")

        output_rows: list[dict] = []
        affected_zone_pairs = 0
        for merchant_id, country_iso in escalated_pairs:
            merchant_id = int(merchant_id)
            country_iso = str(country_iso)
            key = (merchant_id, country_iso)
            site_count = site_count_map.get(key)
            if site_count is None:
                _abort(
                    "E3A_S4_003_DOMAIN_MISMATCH_S1",
                    "V-05",
                    "missing_site_count",
                    {
                        "missing_escalated_pairs_count": 1,
                        "unexpected_pairs_count": 0,
                        "sample_merchant_id": merchant_id,
                        "sample_country_iso": country_iso,
                    },
                    manifest_fingerprint,
                )
            group = s3_by_pair.get((merchant_id, country_iso))
            if group is None:
                _abort(
                    "E3A_S4_003_DOMAIN_MISMATCH_S1",
                    "V-05",
                    "missing_s3_pair",
                    {
                        "missing_escalated_pairs_count": 1,
                        "unexpected_pairs_count": 0,
                        "sample_merchant_id": merchant_id,
                        "sample_country_iso": country_iso,
                    },
                    manifest_fingerprint,
                )

            expected_tzids = zones_by_country.get(country_iso) or []
            observed_tzids = sorted(group["tzid"].to_list())
            if expected_tzids != observed_tzids:
                affected_zone_pairs += 1
                _abort(
                    "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                    "V-05",
                    "zone_set_mismatch",
                    {
                        "affected_pairs_count": affected_zone_pairs,
                        "sample_merchant_id": merchant_id,
                        "sample_country_iso": country_iso,
                        "sample_tzid": observed_tzids[0] if observed_tzids else None,
                    },
                    manifest_fingerprint,
                )

            share_sum_unique = group.select("share_sum_country").unique()
            if share_sum_unique.height != 1:
                _abort(
                    "E3A_S4_007_OUTPUT_INCONSISTENT",
                    "V-05",
                    "share_sum_inconsistent",
                    {"reason": "share_sum_inconsistent", "sample_country_iso": country_iso},
                    manifest_fingerprint,
                )
            share_sum_country = float(share_sum_unique.to_series()[0])
            if not math.isfinite(share_sum_country) or share_sum_country <= 0.0:
                _abort(
                    "E3A_S4_007_OUTPUT_INCONSISTENT",
                    "V-05",
                    "share_sum_invalid",
                    {"reason": "share_sum_inconsistent", "sample_country_iso": country_iso},
                    manifest_fingerprint,
                )
            if abs(share_sum_country - 1.0) > TOLERANCE:
                _abort(
                    "E3A_S4_007_OUTPUT_INCONSISTENT",
                    "V-05",
                    "share_sum_out_of_range",
                    {
                        "reason": "share_sum_inconsistent",
                        "sample_country_iso": country_iso,
                        "expected": 1.0,
                        "observed": share_sum_country,
                    },
                    manifest_fingerprint,
                )

            share_by_tzid = {str(tzid): float(share) for tzid, share in group.select(["tzid", "share_drawn"]).iter_rows()}
            share_sum_raw = float(sum(share_by_tzid.values()))
            if abs(share_sum_raw - share_sum_country) > TOLERANCE:
                _abort(
                    "E3A_S4_007_OUTPUT_INCONSISTENT",
                    "V-05",
                    "share_sum_mismatch",
                    {
                        "reason": "share_sum_inconsistent",
                        "sample_country_iso": country_iso,
                        "expected": share_sum_country,
                        "observed": share_sum_raw,
                    },
                    manifest_fingerprint,
                )

            items: list[dict] = []
            base_sum = 0
            for stable_index, tzid in enumerate(expected_tzids, start=0):
                share = share_by_tzid.get(tzid)
                if share is None:
                    _abort(
                        "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                        "V-05",
                        "missing_tzid_share",
                        {
                            "affected_pairs_count": 1,
                            "sample_merchant_id": merchant_id,
                            "sample_country_iso": country_iso,
                            "sample_tzid": tzid,
                        },
                        manifest_fingerprint,
                    )
                if not math.isfinite(share) or share < 0.0 or share > 1.0:
                    _abort(
                        "E3A_S4_007_OUTPUT_INCONSISTENT",
                        "V-05",
                        "share_invalid",
                        {"reason": "share_sum_inconsistent", "sample_country_iso": country_iso, "sample_tzid": tzid},
                        manifest_fingerprint,
                    )
                target = site_count * share
                base = int(math.floor(target))
                residual = target - base
                if residual < 0.0 or residual >= 1.0:
                    _abort(
                        "E3A_S4_007_OUTPUT_INCONSISTENT",
                        "V-05",
                        "residual_out_of_range",
                        {"reason": "integerisation_mismatch", "sample_country_iso": country_iso, "sample_tzid": tzid},
                        manifest_fingerprint,
                    )
                base_sum += base
                items.append(
                    {
                        "tzid": tzid,
                        "target": float(target),
                        "base": base,
                        "residual": residual,
                        "stable_index": stable_index,
                    }
                )

            remainder = site_count - base_sum
            if remainder < 0 or remainder > len(items):
                counts["pairs_count_conservation_violations"] += 1
                _abort(
                    "E3A_S4_005_COUNT_CONSERVATION_BROKEN",
                    "V-05",
                    "remainder_invalid",
                    {
                        "affected_pairs_count": counts["pairs_count_conservation_violations"],
                        "sample_merchant_id": merchant_id,
                        "sample_country_iso": country_iso,
                        "site_count": site_count,
                        "zone_site_count_sum": base_sum,
                    },
                    manifest_fingerprint,
                )

            ordered = sorted(
                items,
                key=lambda item: (-item["residual"], item["tzid"], item["stable_index"]),
            )
            for rank, item in enumerate(ordered, start=1):
                item["residual_rank"] = rank

            top_tzids = {item["tzid"] for item in ordered[:remainder]} if remainder > 0 else set()
            nonzero_zones = 0
            zero_zones = 0
            total_count = 0
            alpha_sum_country = alpha_sum_by_country.get(country_iso)
            if alpha_sum_country is None:
                _abort(
                    "E3A_S4_004_DOMAIN_MISMATCH_ZONES",
                    "V-05",
                    "missing_alpha_sum",
                    {
                        "affected_pairs_count": 1,
                        "sample_merchant_id": merchant_id,
                        "sample_country_iso": country_iso,
                    },
                    manifest_fingerprint,
                )
            for item in items:
                bump = 1 if item["tzid"] in top_tzids else 0
                count = item["base"] + bump
                if count < 0:
                    counts["pairs_count_conservation_violations"] += 1
                    _abort(
                        "E3A_S4_005_COUNT_CONSERVATION_BROKEN",
                        "V-05",
                        "negative_count",
                        {
                            "affected_pairs_count": counts["pairs_count_conservation_violations"],
                            "sample_merchant_id": merchant_id,
                            "sample_country_iso": country_iso,
                            "site_count": site_count,
                            "zone_site_count_sum": total_count,
                        },
                        manifest_fingerprint,
                    )
                total_count += count
                if count == 0:
                    zero_zones += 1
                else:
                    nonzero_zones += 1
                output_rows.append(
                    {
                        "seed": seed,
                        "manifest_fingerprint": manifest_fingerprint,
                        "merchant_id": merchant_id,
                        "legal_country_iso": country_iso,
                        "tzid": item["tzid"],
                        "zone_site_count": count,
                        "zone_site_count_sum": site_count,
                        "share_sum_country": share_sum_country,
                        "fractional_target": item["target"],
                        "residual_rank": item["residual_rank"],
                        "prior_pack_id": prior_pack_id,
                        "prior_pack_version": prior_pack_version,
                        "floor_policy_id": floor_policy_id,
                        "floor_policy_version": floor_policy_version,
                        "alpha_sum_country": alpha_sum_country,
                        "notes": None,
                    }
                )

            counts["zone_rows_total"] += len(items)
            counts["zones_zero_allocated"] += zero_zones
            if nonzero_zones == 1:
                counts["pairs_with_single_zone_nonzero"] += 1
            if total_count != site_count:
                counts["pairs_count_conservation_violations"] += 1
                _abort(
                    "E3A_S4_005_COUNT_CONSERVATION_BROKEN",
                    "V-05",
                    "count_sum_mismatch",
                    {
                        "affected_pairs_count": counts["pairs_count_conservation_violations"],
                        "sample_merchant_id": merchant_id,
                        "sample_country_iso": country_iso,
                        "site_count": site_count,
                        "zone_site_count_sum": total_count,
                    },
                    manifest_fingerprint,
                )
            counts["pairs_count_conserved"] += 1

            tracker.update(1)

        if counts["pairs_escalated"] > 0:
            counts["zones_per_pair_avg"] = counts["zone_rows_total"] / counts["pairs_escalated"]

        output_entry = find_dataset_entry(dictionary, "s4_zone_counts").entry
        output_root = _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        output_catalog_path = _render_catalog_path(output_entry, tokens)
        if f"seed={seed}" not in output_catalog_path or f"manifest_fingerprint={manifest_fingerprint}" not in output_catalog_path:
            _abort(
                "E3A_S4_002_CATALOGUE_MALFORMED",
                "V-06",
                "output_partition_mismatch",
                {"catalogue_id": "s4_zone_counts", "path": output_catalog_path},
                manifest_fingerprint,
            )
        tmp_root = run_paths.tmp_root / f"s4_zone_counts_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        output_pack, output_table = _table_pack(schema_3a, "plan/s4_zone_counts")
        _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(iter(output_rows), output_pack, output_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S4_006_OUTPUT_SCHEMA_INVALID",
                "V-06",
                "output_schema_invalid",
                {"violation_count": len(exc.errors), "example_field": str(exc.errors[0].path[0])},
                manifest_fingerprint,
            )

        df = pl.DataFrame(
            output_rows,
            schema={
                "seed": pl.UInt64,
                "manifest_fingerprint": pl.Utf8,
                "merchant_id": pl.UInt64,
                "legal_country_iso": pl.Utf8,
                "tzid": pl.Utf8,
                "zone_site_count": pl.Int64,
                "zone_site_count_sum": pl.Int64,
                "share_sum_country": pl.Float64,
                "fractional_target": pl.Float64,
                "residual_rank": pl.Int64,
                "prior_pack_id": pl.Utf8,
                "prior_pack_version": pl.Utf8,
                "floor_policy_id": pl.Utf8,
                "floor_policy_version": pl.Utf8,
                "alpha_sum_country": pl.Float64,
                "notes": pl.Utf8,
            },
        ).sort(["merchant_id", "legal_country_iso", "tzid"])

        if df.height != df.unique(subset=["merchant_id", "legal_country_iso", "tzid"]).height:
            _abort(
                "E3A_S4_007_OUTPUT_INCONSISTENT",
                "V-06",
                "duplicate_output_rows",
                {"reason": "integerisation_mismatch", "detail": "duplicate merchant-country-tzid rows detected"},
                manifest_fingerprint,
            )

        output_path = tmp_root / "part-00000.parquet"
        df.write_parquet(output_path, compression="zstd")
        logger.info("S4: wrote %d rows to %s", df.height, output_path)

        _publish_partition(tmp_root, output_root, df, logger)
        timer.info("S4: published s4_zone_counts")

        status = "PASS"
    except EngineFailure as exc:
        if not error_code:
            error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except ContractError as exc:
        if not error_code:
            error_code = "E3A_S4_002_CATALOGUE_MALFORMED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S4_009_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S4_009_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id_value and parameter_hash and manifest_fingerprint:
            utc_day = finished_utc[:10]
            try:
                segment_state_runs_path = _segment_state_runs_path(run_paths, dictionary, utc_day)
                _append_jsonl(
                    segment_state_runs_path,
                    {
                        "layer": "layer1",
                        "segment": SEGMENT,
                        "state": STATE,
                        "parameter_hash": str(parameter_hash),
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "run_id": run_id_value,
                        "status": status,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("S4: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s4_run_report_3A").entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": run_id_value,
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": {
                        "prior_pack_id": prior_pack_id,
                        "prior_pack_version": prior_pack_version,
                        "floor_policy_id": floor_policy_id,
                        "floor_policy_version": floor_policy_version,
                    },
                    "counts": counts,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "error_class_detail": _error_class_label(error_code),
                    "first_failure_phase": first_failure_phase,
                    "output": {"path": output_catalog_path if output_root else None, "format": "parquet"},
                }
                _write_json(run_report_path, run_report)
                logger.info("S4: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S4: failed to write run-report: %s", exc)

            if start_logged and status == "PASS":
                _emit_event(
                    logger,
                    "STATE_SUCCESS",
                    manifest_fingerprint,
                    "INFO",
                    layer="layer1",
                    segment=SEGMENT,
                    state=STATE,
                    parameter_hash=parameter_hash,
                    seed=seed,
                    run_id=run_id_value,
                    attempt=1,
                    status=status,
                    error_code=None,
                    pairs_total=counts["pairs_total"],
                    pairs_escalated=counts["pairs_escalated"],
                    pairs_monolithic=counts["pairs_monolithic"],
                    zone_rows_total=counts["zone_rows_total"],
                    zones_per_pair_avg=counts["zones_per_pair_avg"],
                    zones_zero_allocated=counts["zones_zero_allocated"],
                    pairs_with_single_zone_nonzero=counts["pairs_with_single_zone_nonzero"],
                    pairs_count_conserved=counts["pairs_count_conserved"],
                    pairs_count_conservation_violations=counts["pairs_count_conservation_violations"],
                    prior_pack_id=prior_pack_id,
                    prior_pack_version=prior_pack_version,
                    floor_policy_id=floor_policy_id,
                    floor_policy_version=floor_policy_version,
                )
            if start_logged and status != "PASS":
                _emit_event(
                    logger,
                    "STATE_FAILURE",
                    manifest_fingerprint,
                    "ERROR",
                    layer="layer1",
                    segment=SEGMENT,
                    state=STATE,
                    parameter_hash=parameter_hash,
                    seed=seed,
                    run_id=run_id_value,
                    attempt=1,
                    status=status,
                    error_code=error_code,
                    error_class=_error_class_label(error_code),
                    error_details=error_context,
                    pairs_total=counts["pairs_total"],
                    pairs_escalated=counts["pairs_escalated"],
                    zone_rows_total=counts["zone_rows_total"],
                )

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3A_S4_009_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if output_root is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S4_009_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S4Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        output_path=output_root,
        run_report_path=run_report_path,
    )
