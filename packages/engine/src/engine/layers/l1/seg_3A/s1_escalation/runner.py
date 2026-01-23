"""S1 escalation queue runner for Segment 3A."""

from __future__ import annotations

import hashlib
import json
import numbers
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import geopandas as gpd
import polars as pl
import shapely
from jsonschema import Draft202012Validator
from shapely.strtree import STRtree

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
from engine.layers.l1.seg_1B.s1_tile_index.runner import _split_antimeridian_geometries
from engine.layers.l1.seg_3A.s0_gate.runner import (
    _append_jsonl,
    _hash_partition,
    _inline_external_refs,
    _is_placeholder,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _segment_state_runs_path,
    _table_pack,
)


MODULE_NAME = "3A.s1_escalation"
SEGMENT = "3A"
STATE = "S1"

ESCALATED_REASONS = {"forced_escalation", "default_escalation"}
MONOLITHIC_REASONS = {"forced_monolithic", "below_min_sites", "legacy_default"}
ALLOWED_REASONS = ESCALATED_REASONS | MONOLITHIC_REASONS
ALLOWED_METRICS = {
    "site_count_lt",
    "zone_count_country_le",
    "site_count_ge",
    "zone_count_country_ge",
}


@dataclass(frozen=True)
class S1Result:
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
    logger = get_logger("engine.layers.l1.seg_3A.s1_escalation.l2.runner")
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


def _theta_mix_u(merchant_id: int, country_iso: str, parameter_hash: str) -> float:
    msg = f"3A.S1.theta_mix|{merchant_id}|{country_iso}|{parameter_hash}"
    digest = hashlib.sha256(msg.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big", signed=False)
    return (value + 0.5) / (2**64)


def _expected_release_tag(tz_world_id: str, tz_world_path: str) -> str:
    parts = tz_world_id.split("_")
    if len(parts) >= 2:
        return parts[-1]
    path_parts = Path(tz_world_path).parts
    for part in path_parts:
        if part.startswith("20") and len(part) >= 4:
            return part
    return ""


def _policy_digest(policy_path: Path) -> str:
    return sha256_file(policy_path).sha256_hex


def _load_policy(policy_path: Path) -> dict:
    payload = _load_yaml(policy_path)
    if not isinstance(payload, dict):
        raise ContractError("zone_mixture_policy payload is not an object")
    return payload


def _validate_policy_payload(
    policy_payload: dict, policy_digest: str, manifest_fingerprint: Optional[str]
) -> tuple[str, str, float, list[dict]]:
    policy_id = str(policy_payload.get("policy_id") or "")
    policy_version = str(policy_payload.get("version") or "")
    theta_mix = float(policy_payload.get("theta_mix") or 0.0)
    rules = policy_payload.get("rules")

    problems: list[dict] = []

    if policy_id != "zone_mixture_policy_3A":
        problems.append({"detail": "policy_id_invalid", "policy_id": policy_id})
    if _is_placeholder(policy_version):
        problems.append({"detail": "policy_version_placeholder", "policy_version": policy_version})
    if not (0.0 <= theta_mix <= 1.0):
        problems.append({"detail": "theta_mix_out_of_range", "theta_mix": theta_mix})
    if not (0.10 <= theta_mix <= 0.70):
        problems.append({"detail": "theta_mix_sanity_failed", "theta_mix": theta_mix})

    if not isinstance(rules, list) or len(rules) < 3:
        problems.append(
            {
                "detail": "rules_missing_or_too_few",
                "rules_count": 0 if not isinstance(rules, list) else len(rules),
            }
        )
        rules = []

    has_site_lt = False
    has_zone_le_one = False
    has_forced_escalation = False

    for rule in rules:
        metric = str(rule.get("metric") or "")
        decision_reason = str(rule.get("decision_reason") or "")
        threshold = rule.get("threshold")
        if metric not in ALLOWED_METRICS:
            problems.append({"detail": "metric_invalid", "metric": metric})
        if decision_reason not in ALLOWED_REASONS:
            problems.append({"detail": "decision_reason_invalid", "decision_reason": decision_reason})
        if threshold is None:
            problems.append({"detail": "threshold_missing", "metric": metric})
            continue
        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            problems.append({"detail": "threshold_not_numeric", "metric": metric, "threshold": threshold})
            continue

        if metric == "site_count_lt":
            has_site_lt = True
            if not (2 <= threshold_value <= 10):
                problems.append({"detail": "site_count_lt_threshold_invalid", "threshold": threshold_value})
        if metric == "zone_count_country_le" and threshold_value == 1:
            has_zone_le_one = True
        if metric == "zone_count_country_ge":
            if not (3 <= threshold_value <= 12):
                problems.append({"detail": "zone_count_country_ge_threshold_invalid", "threshold": threshold_value})
        if metric == "site_count_ge":
            if not (20 <= threshold_value <= 200):
                problems.append({"detail": "site_count_ge_threshold_invalid", "threshold": threshold_value})
        if decision_reason == "forced_escalation":
            if metric in ("site_count_ge", "zone_count_country_ge"):
                has_forced_escalation = True

    if not has_site_lt:
        problems.append({"detail": "missing_site_count_lt_rule"})
    if not has_zone_le_one:
        problems.append({"detail": "missing_zone_count_le_one_rule"})
    if not has_forced_escalation:
        problems.append({"detail": "missing_forced_escalation_rule"})

    if problems:
        _abort(
            "E3A_S1_005_POLICY_SCHEMA_INVALID",
            "V-04",
            "policy_validation_failed",
            {"policy_digest": policy_digest, "issues": problems},
            manifest_fingerprint,
        )

    return policy_id, policy_version, theta_mix, list(rules)


def _resolve_candidate_geoms(tree: STRtree, tz_geoms: list, geom) -> list:
    candidates = tree.query(geom)
    resolved = []
    for candidate in candidates:
        if isinstance(candidate, numbers.Integral):
            resolved.append(tz_geoms[int(candidate)])
        else:
            resolved.append(candidate)
    return resolved


def _row_geometry(row) -> Optional[object]:
    if hasattr(row, "geometry"):
        return row.geometry
    if hasattr(row, "geom"):
        return row.geom
    return None


def _build_zone_index(
    countries: dict[str, object],
    tz_world: list[tuple[str, object]],
    logger,
) -> tuple[dict[str, set[str]], dict[str, int]]:
    tz_geoms: list = []
    tz_ids: list[str] = []
    for tzid, geom in tz_world:
        if geom is None:
            continue
        parts = _split_antimeridian_geometries(geom)
        for part in parts:
            if part is None or getattr(part, "is_empty", False):
                continue
            tz_geoms.append(part)
            tz_ids.append(str(tzid))

    if not tz_geoms:
        raise ContractError("tz_world geometries missing")

    tree = STRtree(tz_geoms)
    geom_to_tzid = {id(geom): tzid for geom, tzid in zip(tz_geoms, tz_ids)}

    zone_map: dict[str, set[str]] = {}
    zone_count: dict[str, int] = {}
    tracker = _ProgressTracker(len(countries), logger, "S1: deriving Z(c) per country")
    for country_iso, geom in countries.items():
        tzids: set[str] = set()
        parts = _split_antimeridian_geometries(geom)
        for part in parts:
            if part is None or getattr(part, "is_empty", False):
                continue
            for candidate in _resolve_candidate_geoms(tree, tz_geoms, part):
                if candidate is None or getattr(candidate, "is_empty", False):
                    continue
                if candidate.intersects(part):
                    tzids.add(geom_to_tzid[id(candidate)])
        zone_map[country_iso] = tzids
        zone_count[country_iso] = len(tzids)
        tracker.update(1)

    return zone_map, zone_count


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E3A_S1_012_IMMUTABILITY_VIOLATION",
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


def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l1.seg_3A.s1_escalation.l2.runner")
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
    theta_digest = ""
    theta_mix = 0.0
    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None
    segment_state_runs_path: Optional[Path] = None

    counts = {
        "pairs_total": 0,
        "pairs_escalated": 0,
        "pairs_monolithic": 0,
        "countries_total": 0,
    }
    reason_counts: Counter[str] = Counter()
    zone_counts: Counter[int] = Counter()

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
        dict_path, dictionary = load_dataset_dictionary(source, "3A")
        registry_path, registry = load_artefact_registry(source, "3A")
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s",
            config.contracts_layout,
            config.contracts_root,
            dict_path,
            registry_path,
            ",".join(
                [
                    str(schema_3a_path),
                    str(schema_2b_path),
                    str(schema_2a_path),
                    str(schema_1b_path),
                    str(schema_1a_path),
                    str(schema_layer1_path),
                    str(schema_ingress_path),
                ]
            ),
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "run_id": run_id,
        }

        logger.info(
            "S1: objective=classify merchant-country pairs into monolithic vs escalation; gated inputs "
            "(s0_gate_receipt_3A, sealed_inputs_3A, outlet_catalogue, iso3166, world_countries, tz_world, "
            "zone_mixture_policy, optional tz_timetable_cache) -> outputs (s1_escalation_queue, s1_run_report_3A)"
        )

        current_phase = "s0_receipt"
        receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_3A").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        try:
            _validate_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A", receipt_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_receipt_invalid",
                {"detail": str(exc), "path": str(receipt_path)},
                manifest_fingerprint,
            )

        for segment_id in ("segment_1A", "segment_1B", "segment_2A"):
            status_value = (
                receipt_payload.get("upstream_gates", {})
                .get(segment_id, {})
                .get("status")
            )
            if status_value != "PASS":
                _abort(
                    "E3A_S1_002_UPSTREAM_GATE_NOT_PASS",
                    "V-02",
                    "upstream_gate_not_pass",
                    {"segment": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        current_phase = "sealed_inputs"
        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_3A").entry
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        sealed_payload = _load_json(sealed_path)
        if not isinstance(sealed_payload, list):
            _abort(
                "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                "V-03",
                "sealed_inputs_not_list",
                {"path": str(sealed_path)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/sealed_inputs_3A")
        validator = Draft202012Validator(sealed_schema)
        sealed_rows: list[dict] = []
        for row in sealed_payload:
            if not isinstance(row, dict):
                _abort(
                    "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_not_object",
                    {"row": str(row)[:200]},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_schema_invalid",
                    {"error": errors[0].message},
                    manifest_fingerprint,
                )
            if row.get("manifest_fingerprint") != str(manifest_fingerprint):
                _abort(
                    "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
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
                    "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_missing",
                    {"row": row},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        policy_set = receipt_payload.get("sealed_policy_set") or []
        policy_entries = [row for row in policy_set if row.get("logical_id") == "zone_mixture_policy"]
        if len(policy_entries) != 1:
            _abort(
                "E3A_S1_004_POLICY_MISSING_OR_AMBIGUOUS",
                "V-04",
                "policy_missing_or_ambiguous",
                {"logical_id": "zone_mixture_policy", "count": len(policy_entries)},
                manifest_fingerprint,
            )
        if "zone_mixture_policy" not in sealed_by_id:
            _abort(
                "E3A_S1_004_POLICY_MISSING_OR_AMBIGUOUS",
                "V-04",
                "policy_missing_in_sealed_inputs",
                {"logical_id": "zone_mixture_policy"},
                manifest_fingerprint,
            )

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3A_S1_001_S0_GATE_MISSING_OR_INVALID",
                    "V-05",
                    "sealed_input_missing",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_row = sealed_by_id[logical_id]
            entry = find_dataset_entry(dictionary, logical_id).entry
            expected_path = _render_catalog_path(entry, tokens).rstrip("/")
            sealed_path_value = str(sealed_row.get("path") or "").rstrip("/")
            if expected_path != sealed_path_value:
                _abort(
                    "E3A_S1_007_SEALED_INPUT_MISMATCH",
                    "V-05",
                    "sealed_path_mismatch",
                    {
                        "logical_id": logical_id,
                        "expected": expected_path,
                        "actual": sealed_path_value,
                    },
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3A_S1_003_CATALOGUE_MALFORMED",
                    "V-05",
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
                    "E3A_S1_007_SEALED_INPUT_MISMATCH",
                    "V-05",
                    "sealed_digest_mismatch",
                    {
                        "logical_id": logical_id,
                        "path": str(asset_path),
                        "sealed_sha256_hex": sealed_digest,
                        "computed_sha256_hex": computed_digest,
                    },
                    manifest_fingerprint,
                )
            return sealed_row, asset_path, expected_path

        outlet_row, outlet_path, outlet_catalog_path = _verify_sealed_asset("outlet_catalogue")
        iso_row, iso_path, iso_catalog_path = _verify_sealed_asset("iso3166_canonical_2024")
        world_row, world_path, world_catalog_path = _verify_sealed_asset("world_countries")
        tz_row, tz_path, tz_catalog_path = _verify_sealed_asset("tz_world_2025a")
        policy_row, policy_path, policy_catalog_path = _verify_sealed_asset("zone_mixture_policy")

        tz_cache_manifest = None
        tz_cache_catalog_path = ""
        if "tz_timetable_cache" in sealed_by_id:
            _, tz_cache_path, tz_cache_catalog_path = _verify_sealed_asset("tz_timetable_cache")
            manifest_path = tz_cache_path / "tz_timetable_cache.json"
            tz_cache_manifest = _load_json(manifest_path)

        timer.info("S1: resolved and verified sealed inputs")

        current_phase = "policy_load"
        policy_payload = _load_policy(policy_path)
        policy_schema = _schema_for_payload(schema_3a, schema_layer1, "policy/zone_mixture_policy_v1")
        errors = list(Draft202012Validator(policy_schema).iter_errors(policy_payload))
        if errors:
            _abort(
                "E3A_S1_005_POLICY_SCHEMA_INVALID",
                "V-04",
                "policy_schema_invalid",
                {"error": errors[0].message},
                manifest_fingerprint,
            )
        theta_digest = _policy_digest(policy_path)
        policy_id, policy_version, theta_mix, rules = _validate_policy_payload(
            policy_payload, theta_digest, manifest_fingerprint
        )
        timer.info("S1: mixture policy loaded and validated")

        current_phase = "outlet_aggregate"
        outlet_scan = pl.scan_parquet(str(outlet_path / "*.parquet")).select(
            ["merchant_id", "legal_country_iso"]
        )
        site_counts_df = (
            outlet_scan.group_by(["merchant_id", "legal_country_iso"])
            .agg(pl.count().alias("site_count"))
            .collect()
        )
        if site_counts_df.height == 0:
            _abort(
                "E3A_S1_008_DOMAIN_MISMATCH_1A",
                "V-06",
                "outlet_catalogue_empty",
                {"path": outlet_catalog_path},
                manifest_fingerprint,
            )
        site_counts_df = site_counts_df.sort(["merchant_id", "legal_country_iso"])
        counts["pairs_total"] = int(site_counts_df.height)
        countries_in_scope = set(site_counts_df.get_column("legal_country_iso").to_list())
        counts["countries_total"] = len(countries_in_scope)
        timer.info("S1: aggregated outlet_catalogue into merchant-country site counts")

        current_phase = "zone_structure"
        iso_df = pl.read_parquet(iso_path, columns=["country_iso"])
        iso_set = {str(row[0]) for row in iso_df.iter_rows()}
        missing_iso = sorted([iso for iso in countries_in_scope if iso not in iso_set])
        if missing_iso:
            _abort(
                "E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT",
                "V-07",
                "unknown_country_iso",
                {"missing_sample": missing_iso[:10], "missing_count": len(missing_iso)},
                manifest_fingerprint,
            )

        world_gdf = gpd.read_parquet(world_path)
        world_gdf = world_gdf[world_gdf["country_iso"].isin(list(countries_in_scope))]
        if world_gdf.empty:
            _abort(
                "E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT",
                "V-07",
                "world_countries_missing_scope",
                {"countries": len(countries_in_scope)},
                manifest_fingerprint,
            )
        world_geom_map: dict[str, object] = {}
        for row in world_gdf.itertuples(index=False):
            country_iso = str(row.country_iso)
            geom = _row_geometry(row)
            if geom is None:
                continue
            if country_iso in world_geom_map:
                existing = world_geom_map[country_iso]
                world_geom_map[country_iso] = shapely.union_all([existing, geom])
            else:
                world_geom_map[country_iso] = geom
        missing_world = sorted([iso for iso in countries_in_scope if iso not in world_geom_map])
        if missing_world:
            _abort(
                "E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT",
                "V-07",
                "world_countries_missing_iso",
                {"missing_sample": missing_world[:10], "missing_count": len(missing_world)},
                manifest_fingerprint,
            )

        tz_gdf = gpd.read_parquet(tz_path)
        tz_world_rows = [(row.tzid, _row_geometry(row)) for row in tz_gdf.itertuples(index=False)]
        zone_map, zone_count = _build_zone_index(world_geom_map, tz_world_rows, logger)
        zone_zero = [iso for iso, count in zone_count.items() if count == 0]
        if zone_zero:
            _abort(
                "E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT",
                "V-07",
                "zone_count_zero",
                {"missing_sample": zone_zero[:10], "missing_count": len(zone_zero)},
                manifest_fingerprint,
            )
        zone_counts.update(zone_count.values())

        if tz_cache_manifest is not None:
            expected_tag = _expected_release_tag("tz_world_2025a", tz_catalog_path)
            actual_tag = str(tz_cache_manifest.get("tzdb_release_tag") or "")
            if expected_tag and actual_tag and expected_tag != actual_tag:
                _abort(
                    "E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT",
                    "V-07",
                    "tz_release_tag_mismatch",
                    {"expected": expected_tag, "actual": actual_tag},
                    manifest_fingerprint,
                )

        timer.info("S1: derived zone-count structure from world_countries + tz_world")

        current_phase = "decision_eval"
        output_rows: list[dict] = []
        tracker = _ProgressTracker(site_counts_df.height, logger, "S1: evaluating escalation decisions")
        for merchant_id, country_iso, site_count in site_counts_df.iter_rows():
            merchant_id = int(merchant_id)
            country_iso = str(country_iso)
            site_count_value = int(site_count)
            zone_count_value = zone_count.get(country_iso)
            if zone_count_value is None:
                _abort(
                    "E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT",
                    "V-07",
                    "zone_count_missing",
                    {"country_iso": country_iso},
                    manifest_fingerprint,
                )
            decision_reason = ""
            rule_bucket = None
            for rule in rules:
                metric = str(rule.get("metric") or "")
                threshold = float(rule.get("threshold"))
                match = False
                if metric == "site_count_lt" and site_count_value < threshold:
                    match = True
                elif metric == "zone_count_country_le" and zone_count_value <= threshold:
                    match = True
                elif metric == "site_count_ge" and site_count_value >= threshold:
                    match = True
                elif metric == "zone_count_country_ge" and zone_count_value >= threshold:
                    match = True
                if match:
                    decision_reason = str(rule.get("decision_reason") or "")
                    rule_bucket = rule.get("bucket")
                    break

            if not decision_reason:
                u_det = _theta_mix_u(merchant_id, country_iso, str(parameter_hash))
                if u_det < theta_mix:
                    decision_reason = "default_escalation"
                else:
                    decision_reason = "legacy_default"

            if decision_reason not in ALLOWED_REASONS:
                _abort(
                    "E3A_S1_005_POLICY_SCHEMA_INVALID",
                    "V-08",
                    "decision_reason_invalid",
                    {"decision_reason": decision_reason},
                    manifest_fingerprint,
                )

            is_escalated = decision_reason in ESCALATED_REASONS
            eligible_for_escalation = decision_reason in {
                "forced_escalation",
                "default_escalation",
                "legacy_default",
            }

            output_rows.append(
                {
                    "seed": int(seed),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "merchant_id": merchant_id,
                    "legal_country_iso": country_iso,
                    "site_count": site_count_value,
                    "zone_count_country": int(zone_count_value),
                    "is_escalated": bool(is_escalated),
                    "decision_reason": decision_reason,
                    "mixture_policy_id": policy_id,
                    "mixture_policy_version": policy_version,
                    "theta_digest": theta_digest,
                    "eligible_for_escalation": eligible_for_escalation,
                    "dominant_zone_share_bucket": rule_bucket,
                    "notes": None,
                }
            )
            reason_counts[decision_reason] += 1
            tracker.update(1)

        counts["pairs_escalated"] = sum(1 for row in output_rows if row["is_escalated"])
        counts["pairs_monolithic"] = counts["pairs_total"] - counts["pairs_escalated"]

        output_entry = find_dataset_entry(dictionary, "s1_escalation_queue").entry
        output_root = _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        output_catalog_path = _render_catalog_path(output_entry, tokens)
        tmp_root = run_paths.tmp_root / f"s1_escalation_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        output_pack, output_table = _table_pack(schema_3a, "plan/s1_escalation_queue")
        _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(iter(output_rows), output_pack, output_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S1_010_OUTPUT_SCHEMA_INVALID",
                "V-09",
                "output_schema_invalid",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        df = pl.DataFrame(
            output_rows,
            schema={
                "seed": pl.UInt64,
                "manifest_fingerprint": pl.Utf8,
                "merchant_id": pl.UInt64,
                "legal_country_iso": pl.Utf8,
                "site_count": pl.UInt32,
                "zone_count_country": pl.UInt32,
                "is_escalated": pl.Boolean,
                "decision_reason": pl.Utf8,
                "mixture_policy_id": pl.Utf8,
                "mixture_policy_version": pl.Utf8,
                "theta_digest": pl.Utf8,
                "eligible_for_escalation": pl.Boolean,
                "dominant_zone_share_bucket": pl.Utf8,
                "notes": pl.Utf8,
            },
        )
        df = df.sort(["merchant_id", "legal_country_iso"])
        output_path = tmp_root / "part-00000.parquet"
        df.write_parquet(output_path, compression="zstd")
        logger.info("S1: wrote %d rows to %s", df.height, output_path)

        _atomic_publish_dir(tmp_root, output_root, logger, "s1_escalation_queue")
        timer.info("S1: published escalation queue")

        status = "PASS"
    except EngineFailure as exc:
        if not error_code:
            error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S1_013_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S1_013_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint:
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
                        "run_id": run_id,
                        "status": status,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("S1: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s1_run_report_3A").entry
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
                        "mixture_policy_id": policy_id,
                        "mixture_policy_version": policy_version,
                        "theta_mix": theta_mix,
                        "theta_digest": theta_digest,
                    },
                    "counts": counts,
                    "reason_counts": dict(reason_counts),
                    "zone_count_buckets": {str(k): v for k, v in zone_counts.items()},
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "path": _render_catalog_path(find_dataset_entry(dictionary, "s1_escalation_queue").entry, tokens),
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
            error_code or "E3A_S1_013_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if output_root is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S1_013_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S1Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        output_path=output_root,
        run_report_path=run_report_path,
    )
