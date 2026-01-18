from __future__ import annotations

import hashlib
import json
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
from engine.layers.l1.seg_3A.s0_gate.runner import (
    _append_jsonl,
    _hash_partition,
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _segment_state_runs_path,
    _table_pack,
)


MODULE_NAME = "3A.s5_zone_alloc"
SEGMENT = "3A"
STATE = "S5"
HEX64_ZERO = "0" * 64


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_path: Path
    universe_hash_path: Path
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
    logger = get_logger("engine.layers.l1.seg_3A.s5_zone_alloc.l2.runner")
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
    paths = sorted(root.rglob("*.parquet"), key=lambda path: path.relative_to(root).as_posix())
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _hash_parquet_partition(root: Path) -> tuple[str, int, int]:
    if root.is_file():
        files = [root]
    else:
        if not root.exists():
            raise InputResolutionError(f"Missing parquet directory: {root}")
        files = sorted(root.rglob("*.parquet"), key=lambda path: path.relative_to(root).as_posix())
    if not files:
        raise InputResolutionError(f"No parquet files found under {root}")
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
    return hasher.hexdigest(), total_bytes, len(files)


def _compute_masked_alloc_digest(
    df: pl.DataFrame,
    tmp_root: Path,
    logger,
) -> tuple[str, int, int]:
    tmp_dir = tmp_root / f"s5_zone_alloc_digest_{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / "part-00000.parquet"
    df.write_parquet(tmp_path, compression="zstd")
    digest, total_bytes, file_count = _hash_parquet_partition(tmp_dir)
    for path in tmp_dir.rglob("*"):
        if path.is_file():
            path.unlink()
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    logger.info(
        "S5: computed masked zone_alloc_parquet_digest (files=%d, bytes=%d)",
        file_count,
        total_bytes,
    )
    return digest, total_bytes, file_count


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
            logger.info("S5: zone_alloc already exists and is identical; skipping publish.")
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
            "E3A_S5_007_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {
                "artefact": "zone_alloc",
                "difference_kind": difference_kind,
                "difference_count": int(difference_count),
                "partition": str(final_root),
            },
        )
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _publish_json(path: Path, payload: dict, logger, label: str) -> None:
    payload_bytes = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing == payload_bytes:
            logger.info("S5: %s already exists and is identical; skipping publish.", label)
            return
        existing_obj = json.loads(existing.decode("utf-8"))
        difference_count = len(set(existing_obj.keys()) ^ set(payload.keys()))
        for key in payload:
            if key in existing_obj and existing_obj[key] != payload[key]:
                difference_count += 1
        raise EngineFailure(
            "F4",
            "E3A_S5_007_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {
                "artefact": "zone_alloc_universe_hash",
                "difference_kind": "field_value",
                "difference_count": int(difference_count),
                "path": str(path),
            },
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload_bytes)


def _error_class_label(error_code: Optional[str]) -> Optional[str]:
    mapping = {
        "E3A_S5_001_PRECONDITION_FAILED": "PRECONDITION",
        "E3A_S5_002_CATALOGUE_MALFORMED": "CATALOGUE",
        "E3A_S5_003_DOMAIN_MISMATCH": "DOMAIN",
        "E3A_S5_004_DIGEST_MISMATCH": "DIGEST",
        "E3A_S5_005_UNIVERSE_HASH_MISMATCH": "UNIVERSE_HASH",
        "E3A_S5_006_OUTPUT_SCHEMA_INVALID": "OUTPUT_SCHEMA",
        "E3A_S5_007_IMMUTABILITY_VIOLATION": "IMMUTABILITY",
        "E3A_S5_008_INFRASTRUCTURE_IO_ERROR": "INFRASTRUCTURE",
    }
    if not error_code:
        return None
    return mapping.get(error_code)


def _policy_version_from_payload(payload: object) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in ("version", "policy_version", "prior_pack_version", "version_tag"):
        if key in payload and payload[key] is not None:
            return str(payload[key])
    return None


def _is_placeholder(value: Optional[str]) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.lower() in {"tbd", "todo", "unknown"}:
        return True
    if "{" in text or "}" in text:
        return True
    return False


def _sha256_concat_hex(parts: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("ascii"))
    return hasher.hexdigest()


def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l1.seg_3A.s5_zone_alloc.l2.runner")
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
    universe_hash_path: Optional[Path] = None
    run_report_path: Optional[Path] = None
    output_catalog_path: Optional[str] = None
    universe_catalog_path: Optional[str] = None

    mixture_policy_id: Optional[str] = None
    mixture_policy_version: Optional[str] = None
    day_effect_policy_id: Optional[str] = None
    day_effect_policy_version: Optional[str] = None
    prior_pack_id: Optional[str] = None
    prior_pack_version: Optional[str] = None
    floor_policy_id: Optional[str] = None
    floor_policy_version: Optional[str] = None

    zone_alpha_digest = ""
    theta_digest = ""
    zone_floor_digest = ""
    day_effect_digest = ""
    zone_alloc_parquet_digest = ""
    routing_universe_hash = ""

    counts = {
        "pairs_total": 0,
        "pairs_escalated": 0,
        "pairs_monolithic": 0,
        "zone_rows_total": 0,
        "zones_per_pair_avg": 0.0,
        "missing_escalated_pairs_count": 0,
        "unexpected_pairs_count": 0,
        "affected_zone_triplets_count": 0,
        "pairs_count_conservation_violations": 0,
    }

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
        timer.info(f"S5: run log initialized at {run_log_path}")

        logger.info(
            "S5: objective=project S4 zone counts into zone_alloc and seal routing_universe_hash "
            "(priors + mixture + floors + day-effect + allocation)"
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
        reg_path, registry = load_artefact_registry(source, SEGMENT)
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        timer.info("S5: contracts loaded")

        current_phase = "s0_gate"
        s0_entry = find_dataset_entry(dictionary, "s0_gate_receipt_3A").entry
        try:
            s0_path = _resolve_dataset_path(s0_entry, run_paths, config.external_roots, tokens)
            s0_gate = _load_json(s0_path)
        except InputResolutionError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-01",
                "s0_gate_missing",
                {"component": "S0_GATE", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s0_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A")
        s0_errors = list(Draft202012Validator(s0_schema).iter_errors(s0_gate))
        if s0_errors:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
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
                    "E3A_S5_001_PRECONDITION_FAILED",
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
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_inputs_missing",
                {"component": "S0_SEALED_INPUTS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_from_pack(schema_3a, "validation/sealed_inputs_3A")
        _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
        sealed_validator = Draft202012Validator(normalize_nullable_schema(sealed_schema))
        sealed_rows: list[dict] = []
        for row in sealed_inputs:
            errors = list(sealed_validator.iter_errors(row))
            if errors:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_schema_invalid",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )
            if str(row.get("manifest_fingerprint")) != str(manifest_fingerprint):
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_identity_mismatch",
                    {
                        "component": "S0_SEALED_INPUTS",
                        "reason": "schema_invalid",
                        "row_manifest_fingerprint": row.get("manifest_fingerprint"),
                    },
                    manifest_fingerprint,
                )
            sealed_rows.append(row)

        sealed_by_id: dict[str, dict] = {}
        for row in sealed_rows:
            logical_id = str(row.get("logical_id") or "")
            if not logical_id:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_inputs_missing_logical_id",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid"},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_logical_id_duplicate",
                    {"component": "S0_SEALED_INPUTS", "reason": "schema_invalid", "logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        sealed_policy_set = s0_gate.get("sealed_policy_set") or []
        sealed_policy_ids = {str(item.get("logical_id") or "") for item in sealed_policy_set}
        required_policies = ["zone_mixture_policy", "country_zone_alphas", "zone_floor_policy", "day_effect_policy_v1"]
        missing_policies = sorted(policy_id for policy_id in required_policies if policy_id not in sealed_policy_ids)
        if missing_policies:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-01",
                "sealed_policy_missing",
                {"component": "S0_GATE", "reason": "schema_invalid", "missing_policies": missing_policies},
                manifest_fingerprint,
            )

        def _verify_sealed_policy(logical_id: str, component_label: str, schema_pack: dict, schema_anchor: str) -> dict:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "policy_missing_in_sealed_inputs",
                    {"component": component_label, "reason": "missing", "logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_row = sealed_by_id[logical_id]
            entry = find_dataset_entry(dictionary, logical_id).entry
            expected_path = _render_catalog_path(entry, tokens).rstrip("/")
            sealed_path_value = str(sealed_row.get("path") or "").rstrip("/")
            if expected_path != sealed_path_value:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_path_mismatch",
                    {
                        "component": component_label,
                        "reason": "schema_invalid",
                        "logical_id": logical_id,
                        "expected": expected_path,
                        "actual": sealed_path_value,
                    },
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "policy_missing",
                    {"component": component_label, "reason": "missing", "path": str(asset_path)},
                    manifest_fingerprint,
                )
            if asset_path.is_dir():
                computed_digest, _ = _hash_partition(asset_path)
            else:
                computed_digest = sha256_file(asset_path).sha256_hex
            sealed_digest = str(sealed_row.get("sha256_hex") or "")
            if computed_digest != sealed_digest:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "sealed_digest_mismatch",
                    {
                        "component": component_label,
                        "reason": "schema_invalid",
                        "logical_id": logical_id,
                        "path": str(asset_path),
                        "sealed_sha256_hex": sealed_digest,
                        "computed_sha256_hex": computed_digest,
                    },
                    manifest_fingerprint,
                )
            payload = _load_yaml(asset_path) if asset_path.suffix.lower() in {".yaml", ".yml"} else _load_json(asset_path)
            schema = _schema_from_pack(schema_pack, schema_anchor)
            _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
            errors = list(Draft202012Validator(schema).iter_errors(payload))
            if errors:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "policy_schema_invalid",
                    {"component": component_label, "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )
            version = _policy_version_from_payload(payload)
            if _is_placeholder(version):
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "policy_version_placeholder",
                    {"component": component_label, "reason": "schema_invalid", "logical_id": logical_id},
                    manifest_fingerprint,
                )
            policy_id = str(payload.get("policy_id") or logical_id)
            return {
                "logical_id": logical_id,
                "policy_id": policy_id,
                "version": str(version),
                "path": asset_path,
            }

        mixture_policy = _verify_sealed_policy(
            "zone_mixture_policy",
            "MIXTURE_POLICY",
            schema_3a,
            "policy/zone_mixture_policy_v1",
        )
        prior_policy = _verify_sealed_policy(
            "country_zone_alphas",
            "PRIOR_PACK",
            schema_3a,
            "policy/country_zone_alphas_v1",
        )
        floor_policy = _verify_sealed_policy(
            "zone_floor_policy",
            "FLOOR_POLICY",
            schema_3a,
            "policy/zone_floor_policy_v1",
        )
        day_effect_policy = _verify_sealed_policy(
            "day_effect_policy_v1",
            "DAY_EFFECT_POLICY",
            schema_2b,
            "policy/day_effect_policy_v1",
        )

        mixture_policy_id = mixture_policy["policy_id"]
        mixture_policy_version = mixture_policy["version"]
        day_effect_policy_id = day_effect_policy["policy_id"]
        day_effect_policy_version = day_effect_policy["version"]

        timer.info("S5: S0 gate + sealed inputs verified")

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
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_run_report_missing",
                    {"component": component, "reason": "missing", "detail": entry_id},
                    manifest_fingerprint,
                )
                return
            errors = list(run_report_validator.iter_errors(report_payload))
            if errors:
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
                    "V-01",
                    "upstream_run_report_schema_invalid",
                    {"component": component, "reason": "schema_invalid", "error": str(errors[0])},
                    manifest_fingerprint,
                )
            status_value = report_payload.get("status")
            if status_value != "PASS":
                _abort(
                    "E3A_S5_001_PRECONDITION_FAILED",
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
        _require_run_report("s4_run_report_3A", "S4_ZONE_COUNTS", "S4")

        current_phase = "s1_escalation_queue"
        s1_entry = find_dataset_entry(dictionary, "s1_escalation_queue").entry
        try:
            s1_path = _resolve_dataset_path(s1_entry, run_paths, config.external_roots, tokens)
            s1_paths = _list_parquet_paths(s1_path)
            s1_df = pl.read_parquet(s1_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
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
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-02",
                "s1_escalation_schema_invalid",
                {"component": "S1_ESCALATION_QUEUE", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        counts["pairs_total"] = s1_df.height
        s1_pairs = s1_df.select(["merchant_id", "legal_country_iso"])
        if s1_pairs.unique().height != s1_pairs.height:
            _abort(
                "E3A_S5_003_DOMAIN_MISMATCH",
                "V-02",
                "s1_duplicate_pairs",
                {
                    "missing_escalated_pairs_count": 0,
                    "unexpected_pairs_count": 0,
                    "affected_zone_triplets_count": 0,
                    "detail": "duplicate merchant-country pairs in s1_escalation_queue",
                },
                manifest_fingerprint,
            )

        esc_df = s1_df.filter(pl.col("is_escalated") == True)  # noqa: E712
        esc_df = esc_df.select(["merchant_id", "legal_country_iso", "site_count"]).sort(
            ["merchant_id", "legal_country_iso"]
        )
        counts["pairs_escalated"] = esc_df.height
        counts["pairs_monolithic"] = counts["pairs_total"] - counts["pairs_escalated"]

        current_phase = "s2_priors"
        s2_entry = find_dataset_entry(dictionary, "s2_country_zone_priors").entry
        try:
            s2_path = _resolve_dataset_path(s2_entry, run_paths, config.external_roots, tokens)
            s2_paths = _list_parquet_paths(s2_path)
            s2_df = pl.read_parquet(s2_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
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
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-03",
                "s2_priors_schema_invalid",
                {"component": "S2_PRIORS", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        current_phase = "s3_zone_shares"
        s3_entry = find_dataset_entry(dictionary, "s3_zone_shares").entry
        try:
            s3_path = _resolve_dataset_path(s3_entry, run_paths, config.external_roots, tokens)
            s3_paths = _list_parquet_paths(s3_path)
            s3_df = pl.read_parquet(s3_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-04",
                "s3_shares_missing",
                {"component": "S3_ZONE_SHARES", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s3_pack, s3_table = _table_pack(schema_3a, "plan/s3_zone_shares")
        _inline_external_refs(s3_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s3_df.iter_rows(named=True), s3_pack, s3_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-04",
                "s3_shares_schema_invalid",
                {"component": "S3_ZONE_SHARES", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        current_phase = "s4_zone_counts"
        s4_entry = find_dataset_entry(dictionary, "s4_zone_counts").entry
        try:
            s4_path = _resolve_dataset_path(s4_entry, run_paths, config.external_roots, tokens)
            s4_paths = _list_parquet_paths(s4_path)
            s4_df = pl.read_parquet(s4_paths)
        except InputResolutionError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-05",
                "s4_counts_missing",
                {"component": "S4_ZONE_COUNTS", "reason": "missing", "detail": str(exc)},
                manifest_fingerprint,
            )
        s4_pack, s4_table = _table_pack(schema_3a, "plan/s4_zone_counts")
        _inline_external_refs(s4_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(s4_df.iter_rows(named=True), s4_pack, s4_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S5_001_PRECONDITION_FAILED",
                "V-05",
                "s4_counts_schema_invalid",
                {"component": "S4_ZONE_COUNTS", "reason": "schema_invalid", "error": str(exc)},
                manifest_fingerprint,
            )

        counts["zone_rows_total"] = s4_df.height
        if counts["pairs_escalated"] > 0:
            counts["zones_per_pair_avg"] = counts["zone_rows_total"] / counts["pairs_escalated"]

        s4_pairs = s4_df.select(["merchant_id", "legal_country_iso"]).unique()
        s4_triplets = s4_df.select(["merchant_id", "legal_country_iso", "tzid"])
        if s4_triplets.unique().height != s4_triplets.height:
            _abort(
                "E3A_S5_003_DOMAIN_MISMATCH",
                "V-06",
                "s4_duplicate_triplets",
                {
                    "missing_escalated_pairs_count": 0,
                    "unexpected_pairs_count": 0,
                    "affected_zone_triplets_count": 0,
                    "detail": "duplicate merchant-country-tzid rows in s4_zone_counts",
                },
                manifest_fingerprint,
            )

        missing_pairs_df = esc_df.select(["merchant_id", "legal_country_iso"]).join(
            s4_pairs, on=["merchant_id", "legal_country_iso"], how="anti"
        )
        unexpected_pairs_df = s4_pairs.join(
            esc_df.select(["merchant_id", "legal_country_iso"]),
            on=["merchant_id", "legal_country_iso"],
            how="anti",
        )
        counts["missing_escalated_pairs_count"] = missing_pairs_df.height
        counts["unexpected_pairs_count"] = unexpected_pairs_df.height
        if counts["missing_escalated_pairs_count"] or counts["unexpected_pairs_count"]:
            sample = missing_pairs_df.vstack(unexpected_pairs_df).head(1)
            sample_row = sample.row(0) if sample.height else None
            _abort(
                "E3A_S5_003_DOMAIN_MISMATCH",
                "V-06",
                "pair_domain_mismatch",
                {
                    "missing_escalated_pairs_count": counts["missing_escalated_pairs_count"],
                    "unexpected_pairs_count": counts["unexpected_pairs_count"],
                    "affected_zone_triplets_count": 0,
                    "sample_merchant_id": sample_row[0] if sample_row else None,
                    "sample_country_iso": sample_row[1] if sample_row else None,
                },
                manifest_fingerprint,
            )

        s2_zones = s2_df.select(["country_iso", "tzid"]).unique()
        expected_zone_counts = s2_zones.group_by("country_iso").agg(
            pl.count().alias("expected_zone_count")
        )
        s4_zone_bad = s4_df.join(
            s2_zones, left_on=["legal_country_iso", "tzid"], right_on=["country_iso", "tzid"], how="anti"
        )
        s3_zone_bad = s3_df.join(
            s2_zones, left_on=["legal_country_iso", "tzid"], right_on=["country_iso", "tzid"], how="anti"
        )

        affected_triplets = s4_zone_bad.height + s3_zone_bad.height

        s4_zone_counts = s4_pairs.join(
            s4_df.group_by(["merchant_id", "legal_country_iso"]).agg(pl.count().alias("observed_zone_count")),
            on=["merchant_id", "legal_country_iso"],
            how="left",
        )
        s4_zone_counts = s4_zone_counts.join(
            expected_zone_counts,
            left_on="legal_country_iso",
            right_on="country_iso",
            how="left",
        )
        s4_mismatch = s4_zone_counts.filter(
            pl.col("expected_zone_count").is_null()
            | (pl.col("observed_zone_count") != pl.col("expected_zone_count"))
        )
        if s4_mismatch.height:
            diff_counts = s4_mismatch.select(
                (pl.col("observed_zone_count") - pl.col("expected_zone_count").fill_null(0)).abs().alias("diff")
            )
            affected_triplets += int(diff_counts.select(pl.sum("diff")).item())

        s3_zone_counts = s3_df.group_by(["merchant_id", "legal_country_iso"]).agg(
            pl.count().alias("observed_zone_count")
        )
        s3_zone_counts = s3_zone_counts.join(
            expected_zone_counts,
            left_on="legal_country_iso",
            right_on="country_iso",
            how="left",
        )
        s3_mismatch = s3_zone_counts.filter(
            pl.col("expected_zone_count").is_null()
            | (pl.col("observed_zone_count") != pl.col("expected_zone_count"))
        )
        if s3_mismatch.height:
            diff_counts = s3_mismatch.select(
                (pl.col("observed_zone_count") - pl.col("expected_zone_count").fill_null(0)).abs().alias("diff")
            )
            affected_triplets += int(diff_counts.select(pl.sum("diff")).item())

        counts["affected_zone_triplets_count"] = affected_triplets
        if affected_triplets:
            sample_row = None
            if s4_zone_bad.height:
                sample_row = s4_zone_bad.select(["merchant_id", "legal_country_iso", "tzid"]).row(0)
            elif s3_zone_bad.height:
                sample_row = s3_zone_bad.select(["merchant_id", "legal_country_iso", "tzid"]).row(0)
            _abort(
                "E3A_S5_003_DOMAIN_MISMATCH",
                "V-06",
                "zone_domain_mismatch",
                {
                    "missing_escalated_pairs_count": counts["missing_escalated_pairs_count"],
                    "unexpected_pairs_count": counts["unexpected_pairs_count"],
                    "affected_zone_triplets_count": counts["affected_zone_triplets_count"],
                    "sample_merchant_id": sample_row[0] if sample_row else None,
                    "sample_country_iso": sample_row[1] if sample_row else None,
                    "sample_tzid": sample_row[2] if sample_row else None,
                },
                manifest_fingerprint,
            )

        s4_sum = s4_df.group_by(["merchant_id", "legal_country_iso"]).agg(
            pl.sum("zone_site_count").alias("zone_site_count_sum_calc"),
            pl.first("zone_site_count_sum").alias("zone_site_count_sum_reported"),
        )
        s4_sum = s4_sum.join(
            esc_df.select(["merchant_id", "legal_country_iso", "site_count"]),
            on=["merchant_id", "legal_country_iso"],
            how="left",
        )
        s4_sum_bad = s4_sum.filter(
            pl.col("site_count").is_null()
            | (pl.col("zone_site_count_sum_calc") != pl.col("zone_site_count_sum_reported"))
            | (pl.col("zone_site_count_sum_reported") != pl.col("site_count"))
        )
        counts["pairs_count_conservation_violations"] = s4_sum_bad.height
        if s4_sum_bad.height:
            sample = s4_sum_bad.row(0)
            _abort(
                "E3A_S5_003_DOMAIN_MISMATCH",
                "V-06",
                "count_conservation_mismatch",
                {
                    "missing_escalated_pairs_count": counts["missing_escalated_pairs_count"],
                    "unexpected_pairs_count": counts["unexpected_pairs_count"],
                    "affected_zone_triplets_count": counts["affected_zone_triplets_count"],
                    "sample_merchant_id": sample[0],
                    "sample_country_iso": sample[1],
                },
                manifest_fingerprint,
            )

        logger.info(
            "S5: domain checks passed (pairs_total=%d, escalated=%d, zone_rows=%d)",
            counts["pairs_total"],
            counts["pairs_escalated"],
            counts["zone_rows_total"],
        )

        prior_pack_id = str(s4_df.get_column("prior_pack_id")[0]) if s4_df.height else None
        prior_pack_version = str(s4_df.get_column("prior_pack_version")[0]) if s4_df.height else None
        floor_policy_id = str(s4_df.get_column("floor_policy_id")[0]) if s4_df.height else None
        floor_policy_version = str(s4_df.get_column("floor_policy_version")[0]) if s4_df.height else None

        current_phase = "zone_alloc_build"
        zone_alloc_df = s4_df.join(
            esc_df.select(["merchant_id", "legal_country_iso", "site_count"]),
            on=["merchant_id", "legal_country_iso"],
            how="left",
        )
        if zone_alloc_df.filter(pl.col("site_count").is_null()).height:
            _abort(
                "E3A_S5_003_DOMAIN_MISMATCH",
                "V-06",
                "missing_site_count",
                {
                    "missing_escalated_pairs_count": counts["missing_escalated_pairs_count"],
                    "unexpected_pairs_count": counts["unexpected_pairs_count"],
                    "affected_zone_triplets_count": counts["affected_zone_triplets_count"],
                },
                manifest_fingerprint,
            )
        zone_alloc_df = zone_alloc_df.with_columns(
            [
                pl.lit(mixture_policy_id).alias("mixture_policy_id"),
                pl.lit(mixture_policy_version).alias("mixture_policy_version"),
                pl.lit(day_effect_policy_id).alias("day_effect_policy_id"),
                pl.lit(day_effect_policy_version).alias("day_effect_policy_version"),
                pl.lit(HEX64_ZERO).alias("routing_universe_hash"),
                pl.lit(None).cast(pl.Utf8).alias("notes"),
            ]
        )

        zone_alloc_df = zone_alloc_df.select(
            [
                "seed",
                "manifest_fingerprint",
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "zone_site_count",
                "zone_site_count_sum",
                "site_count",
                "prior_pack_id",
                "prior_pack_version",
                "floor_policy_id",
                "floor_policy_version",
                "mixture_policy_id",
                "mixture_policy_version",
                "day_effect_policy_id",
                "day_effect_policy_version",
                "routing_universe_hash",
                "alpha_sum_country",
                "notes",
            ]
        ).sort(["merchant_id", "legal_country_iso", "tzid"])

        masked_df = zone_alloc_df.with_columns(pl.lit(HEX64_ZERO).alias("routing_universe_hash"))
        logger.info(
            "S5: computing zone_alloc_parquet_digest using masked routing_universe_hash (approved deviation)"
        )
        zone_alloc_parquet_digest, _, _ = _compute_masked_alloc_digest(masked_df, run_paths.tmp_root, logger)

        zone_alpha_digest, _, _ = _hash_parquet_partition(s2_path)
        theta_digest = sha256_file(Path(mixture_policy["path"])).sha256_hex
        zone_floor_digest = sha256_file(Path(floor_policy["path"])).sha256_hex
        day_effect_digest = sha256_file(Path(day_effect_policy["path"])).sha256_hex
        routing_universe_hash = _sha256_concat_hex(
            [zone_alpha_digest, theta_digest, zone_floor_digest, day_effect_digest, zone_alloc_parquet_digest]
        )

        zone_alloc_df = zone_alloc_df.with_columns(pl.lit(routing_universe_hash).alias("routing_universe_hash"))

        output_pack, output_table = _table_pack(schema_3a, "egress/zone_alloc")
        _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(zone_alloc_df.iter_rows(named=True), output_pack, output_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S5_006_OUTPUT_SCHEMA_INVALID",
                "V-07",
                "zone_alloc_schema_invalid",
                {"output_id": "zone_alloc", "violation_count": len(exc.errors), "example_field": str(exc.errors[0].path[0])},
                manifest_fingerprint,
            )

        output_entry = find_dataset_entry(dictionary, "zone_alloc").entry
        output_root = _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        output_catalog_path = _render_catalog_path(output_entry, tokens)
        if f"seed={seed}" not in output_catalog_path or f"manifest_fingerprint={manifest_fingerprint}" not in output_catalog_path:
            _abort(
                "E3A_S5_002_CATALOGUE_MALFORMED",
                "V-07",
                "output_partition_mismatch",
                {"catalogue_id": "zone_alloc", "path": output_catalog_path},
                manifest_fingerprint,
            )
        tmp_root = run_paths.tmp_root / f"s5_zone_alloc_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)
        output_path = tmp_root / "part-00000.parquet"
        zone_alloc_df.write_parquet(output_path, compression="zstd")
        logger.info("S5: wrote %d rows to %s", zone_alloc_df.height, output_path)

        _publish_partition(tmp_root, output_root, zone_alloc_df, logger)
        timer.info("S5: published zone_alloc")

        current_phase = "zone_alloc_universe_hash"
        universe_entry = find_dataset_entry(dictionary, "zone_alloc_universe_hash").entry
        universe_hash_path = _resolve_dataset_path(universe_entry, run_paths, config.external_roots, tokens)
        universe_catalog_path = _render_catalog_path(universe_entry, tokens)
        universe_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "zone_alpha_digest": zone_alpha_digest,
            "theta_digest": theta_digest,
            "zone_floor_digest": zone_floor_digest,
            "day_effect_digest": day_effect_digest,
            "zone_alloc_parquet_digest": zone_alloc_parquet_digest,
            "routing_universe_hash": routing_universe_hash,
            "notes": "zone_alloc_parquet_digest computed with routing_universe_hash masked to hex-zero",
        }
        universe_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/zone_alloc_universe_hash")
        universe_errors = list(Draft202012Validator(universe_schema).iter_errors(universe_payload))
        if universe_errors:
            _abort(
                "E3A_S5_006_OUTPUT_SCHEMA_INVALID",
                "V-07",
                "zone_alloc_universe_hash_schema_invalid",
                {
                    "output_id": "zone_alloc_universe_hash",
                    "violation_count": len(universe_errors),
                    "example_field": str(universe_errors[0].path[0]),
                },
                manifest_fingerprint,
            )
        _publish_json(universe_hash_path, universe_payload, logger, "zone_alloc_universe_hash")
        timer.info("S5: published zone_alloc_universe_hash")

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
            error_code = "E3A_S5_002_CATALOGUE_MALFORMED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S5_008_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S5_008_INFRASTRUCTURE_IO_ERROR"
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
                logger.warning("S5: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s5_run_report_3A").entry
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
                        "mixture_policy_id": mixture_policy_id,
                        "mixture_policy_version": mixture_policy_version,
                        "day_effect_policy_id": day_effect_policy_id,
                        "day_effect_policy_version": day_effect_policy_version,
                    },
                    "counts": counts,
                    "digests": {
                        "zone_alpha_digest": zone_alpha_digest,
                        "theta_digest": theta_digest,
                        "zone_floor_digest": zone_floor_digest,
                        "day_effect_digest": day_effect_digest,
                        "zone_alloc_parquet_digest": zone_alloc_parquet_digest,
                        "routing_universe_hash": routing_universe_hash,
                        "zone_alloc_digest_rule": "mask_routing_universe_hash",
                    },
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "error_class_detail": _error_class_label(error_code),
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "zone_alloc_path": output_catalog_path if output_root else None,
                        "zone_alloc_universe_hash_path": universe_catalog_path if universe_hash_path else None,
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S5: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S5: failed to write run-report: %s", exc)

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
                    zone_rows_total=counts["zone_rows_total"],
                    zone_alloc_parquet_digest=zone_alloc_parquet_digest,
                    routing_universe_hash=routing_universe_hash,
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
            error_code or "E3A_S5_008_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if output_root is None or universe_hash_path is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S5_008_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S5Result(
        run_id=str(run_id_value),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        output_path=output_root,
        universe_hash_path=universe_hash_path,
        run_report_path=run_report_path,
    )
