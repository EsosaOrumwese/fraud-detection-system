"""S2 country-zone priors runner for Segment 3A."""

from __future__ import annotations

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


MODULE_NAME = "3A.s2_priors"
SEGMENT = "3A"
STATE = "S2"
PRIOR_ID = "country_zone_alphas"
FLOOR_ID = "zone_floor_policy"
TOLERANCE = 1e-12


@dataclass(frozen=True)
class S2Result:
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
    logger = get_logger("engine.layers.l1.seg_3A.s2_priors.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _expected_release_tag(tz_world_id: str, tz_world_path: str) -> str:
    parts = tz_world_id.split("_")
    if len(parts) >= 2:
        return parts[-1]
    path_parts = Path(tz_world_path).parts
    for part in path_parts:
        if part.startswith("20") and len(part) >= 4:
            return part
    return ""


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
) -> dict[str, set[str]]:
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
    tracker = _ProgressTracker(len(countries), logger, "S2: deriving Z(c) per country")
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
        tracker.update(1)

    return zone_map


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


def _publish_partition(
    tmp_root: Path,
    final_root: Path,
    df: pl.DataFrame,
    logger,
) -> None:
    if final_root.exists():
        existing_df = pl.read_parquet(str(final_root / "*.parquet"))
        existing_df = existing_df.sort(["country_iso", "tzid"])
        if df.equals(existing_df):
            for path in tmp_root.rglob("*"):
                if path.is_file():
                    path.unlink()
            try:
                tmp_root.rmdir()
            except OSError:
                pass
            logger.info("S2: s2_country_zone_priors already exists and is identical; skipping publish.")
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
            "E3A_S2_011_IMMUTABILITY_VIOLATION",
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


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l1.seg_3A.s2_priors.l2.runner")
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
    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None
    segment_state_runs_path: Optional[Path] = None

    prior_pack_version = ""
    floor_policy_version = ""
    tz_cache_release_tag = ""

    counts = {
        "countries_total": 0,
        "zones_total": 0,
        "floors_applied": 0,
        "bumps_applied": 0,
    }
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
        logger.info("S2: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, "3A")
        registry_path, registry = load_artefact_registry(source, "3A")
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
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
                    str(schema_2a_path),
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
            "S2: objective=derive parameter-scoped country-zone priors; gated inputs "
            "(s0_gate_receipt_3A, sealed_inputs_3A, country_zone_alphas, zone_floor_policy, "
            "iso3166, world_countries, tz_world, optional tz_timetable_cache) -> outputs "
            "(s2_country_zone_priors, s2_run_report_3A)"
        )

        current_phase = "s0_receipt"
        receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_3A").entry
        gate_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        gate_payload = _load_json(gate_path)
        try:
            schema = _schema_for_payload(schema_3a, schema_layer1, "validation/s0_gate_receipt_3A")
            errors = list(Draft202012Validator(schema).iter_errors(gate_payload))
        except SchemaValidationError as exc:
            errors = [exc]
        if errors:
            _abort(
                "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                "V-01",
                "s0_gate_receipt_invalid",
                {"reason": "schema_invalid", "detail": str(errors[0]), "path": str(gate_path)},
                manifest_fingerprint,
            )
        if str(gate_payload.get("manifest_fingerprint")) != str(manifest_fingerprint) or str(
            gate_payload.get("parameter_hash")
        ) != str(parameter_hash):
            _abort(
                "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                "V-01",
                "s0_gate_receipt_identity_mismatch",
                {
                    "reason": "identity_mismatch",
                    "gate_manifest_fingerprint": gate_payload.get("manifest_fingerprint"),
                    "gate_parameter_hash": gate_payload.get("parameter_hash"),
                },
                manifest_fingerprint,
            )

        for segment_id in ("segment_1A", "segment_1B", "segment_2A"):
            status_value = gate_payload.get("upstream_gates", {}).get(segment_id, {}).get("status")
            if status_value != "PASS":
                _abort(
                    "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                    "V-02",
                    "upstream_gate_not_pass",
                    {
                        "reason": "upstream_gate_not_pass",
                        "segment": segment_id,
                        "reported_status": status_value,
                    },
                    manifest_fingerprint,
                )

        current_phase = "sealed_inputs"
        sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_3A").entry
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        try:
            sealed_payload = _load_sealed_inputs(sealed_path)
        except (InputResolutionError, json.JSONDecodeError) as exc:
            _abort(
                "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                "V-03",
                "sealed_inputs_unreadable",
                {"reason": "missing_sealed_inputs", "detail": str(exc), "path": str(sealed_path)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_for_payload(schema_3a, schema_layer1, "validation/sealed_inputs_3A")
        validator = Draft202012Validator(sealed_schema)
        sealed_rows: list[dict] = []
        for row in sealed_payload:
            if not isinstance(row, dict):
                _abort(
                    "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                    "V-03",
                    "sealed_inputs_not_object",
                    {"reason": "schema_invalid", "path": str(sealed_path)},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                    "V-03",
                    "sealed_inputs_schema_invalid",
                    {"reason": "schema_invalid", "detail": errors[0].message},
                    manifest_fingerprint,
                )
            if str(row.get("manifest_fingerprint")) != str(manifest_fingerprint):
                _abort(
                    "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                    "V-03",
                    "sealed_inputs_identity_mismatch",
                    {
                        "reason": "identity_mismatch",
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
                    "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                    "V-03",
                    "sealed_inputs_missing_logical_id",
                    {"reason": "schema_invalid"},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"reason": "schema_invalid", "logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        policy_set = gate_payload.get("sealed_policy_set") or []
        prior_entries = [row for row in policy_set if row.get("logical_id") == PRIOR_ID]
        floor_entries = [row for row in policy_set if row.get("logical_id") == FLOOR_ID]
        missing_roles = []
        conflicting_roles = []
        if len(prior_entries) == 0:
            missing_roles.append("country_zone_alphas")
        if len(floor_entries) == 0:
            missing_roles.append("zone_floor_policy")
        if len(prior_entries) > 1:
            conflicting_roles.append("country_zone_alphas")
        if len(floor_entries) > 1:
            conflicting_roles.append("zone_floor_policy")
        if missing_roles or conflicting_roles:
            _abort(
                "E3A_S2_003_PRIOR_OR_POLICY_MISSING_OR_AMBIGUOUS",
                "V-04",
                "policy_missing_or_ambiguous",
                {
                    "missing_roles": missing_roles,
                    "conflicting_roles": conflicting_roles,
                    "conflicting_ids": [row.get("logical_id") for row in policy_set],
                },
                manifest_fingerprint,
            )
        if PRIOR_ID not in sealed_by_id or FLOOR_ID not in sealed_by_id:
            _abort(
                "E3A_S2_006_SEALED_INPUT_MISMATCH",
                "V-05",
                "policy_missing_in_sealed_inputs",
                {"logical_id": PRIOR_ID if PRIOR_ID not in sealed_by_id else FLOOR_ID},
                manifest_fingerprint,
            )

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3A_S2_006_SEALED_INPUT_MISMATCH",
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
                    "E3A_S2_006_SEALED_INPUT_MISMATCH",
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
                    "E3A_S2_006_SEALED_INPUT_MISMATCH",
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
                    "E3A_S2_006_SEALED_INPUT_MISMATCH",
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

        prior_row, prior_path, prior_catalog_path = _verify_sealed_asset(PRIOR_ID)
        floor_row, floor_path, floor_catalog_path = _verify_sealed_asset(FLOOR_ID)
        iso_row, iso_path, iso_catalog_path = _verify_sealed_asset("iso3166_canonical_2024")
        world_row, world_path, world_catalog_path = _verify_sealed_asset("world_countries")
        tz_row, tz_path, tz_catalog_path = _verify_sealed_asset("tz_world_2025a")

        tz_cache_manifest = None
        tz_cache_catalog_path = ""
        if "tz_timetable_cache" in sealed_by_id:
            _, tz_cache_path, tz_cache_catalog_path = _verify_sealed_asset("tz_timetable_cache")
            tz_cache_manifest = _load_json(tz_cache_path / "tz_timetable_cache.json")

        timer.info("S2: resolved and verified sealed inputs")

        current_phase = "policy_load"
        prior_payload = _load_yaml(prior_path)
        if not isinstance(prior_payload, dict):
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "prior_payload_invalid",
                {
                    "logical_id": PRIOR_ID,
                    "schema_ref": prior_row.get("schema_ref"),
                    "violation_count": 1,
                },
                manifest_fingerprint,
            )
        prior_schema = _schema_for_payload(schema_3a, schema_layer1, "policy/country_zone_alphas_v1")
        prior_errors = list(Draft202012Validator(prior_schema).iter_errors(prior_payload))
        if prior_errors:
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "prior_schema_invalid",
                {
                    "logical_id": PRIOR_ID,
                    "schema_ref": prior_row.get("schema_ref"),
                    "violation_count": len(prior_errors),
                },
                manifest_fingerprint,
            )
        prior_pack_version = str(prior_payload.get("version") or "")
        if _is_placeholder(prior_pack_version):
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "prior_version_placeholder",
                {
                    "logical_id": PRIOR_ID,
                    "schema_ref": prior_row.get("schema_ref"),
                    "violation_count": 1,
                },
                manifest_fingerprint,
            )

        floor_payload = _load_yaml(floor_path)
        if not isinstance(floor_payload, dict):
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "floor_payload_invalid",
                {
                    "logical_id": FLOOR_ID,
                    "schema_ref": floor_row.get("schema_ref"),
                    "violation_count": 1,
                },
                manifest_fingerprint,
            )
        floor_schema = _schema_for_payload(schema_3a, schema_layer1, "policy/zone_floor_policy_v1")
        floor_errors = list(Draft202012Validator(floor_schema).iter_errors(floor_payload))
        if floor_errors:
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "floor_schema_invalid",
                {
                    "logical_id": FLOOR_ID,
                    "schema_ref": floor_row.get("schema_ref"),
                    "violation_count": len(floor_errors),
                },
                manifest_fingerprint,
            )
        floor_policy_version = str(floor_payload.get("version") or "")
        if _is_placeholder(floor_policy_version):
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "floor_version_placeholder",
                {
                    "logical_id": FLOOR_ID,
                    "schema_ref": floor_row.get("schema_ref"),
                    "violation_count": 1,
                },
                manifest_fingerprint,
            )

        floor_map: dict[str, tuple[float, float]] = {}
        for entry in floor_payload.get("floors", []):
            tzid = str(entry.get("tzid") or "")
            if not tzid:
                _abort(
                    "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                    "V-06",
                    "floor_tzid_missing",
                    {
                        "logical_id": FLOOR_ID,
                        "schema_ref": floor_row.get("schema_ref"),
                        "violation_count": 1,
                    },
                    manifest_fingerprint,
                )
            if tzid in floor_map:
                _abort(
                    "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                    "V-06",
                    "floor_tzid_duplicate",
                    {
                        "logical_id": FLOOR_ID,
                        "schema_ref": floor_row.get("schema_ref"),
                        "violation_count": 1,
                        "tzid": tzid,
                    },
                    manifest_fingerprint,
                )
            floor_value = float(entry.get("floor_value"))
            bump_threshold = float(entry.get("bump_threshold"))
            floor_map[tzid] = (floor_value, bump_threshold)

        timer.info("S2: prior pack + floor policy validated")

        current_phase = "zone_universe"
        prior_countries = prior_payload.get("countries") or {}
        if not isinstance(prior_countries, dict):
            _abort(
                "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                "V-06",
                "prior_countries_invalid",
                {
                    "logical_id": PRIOR_ID,
                    "schema_ref": prior_row.get("schema_ref"),
                    "violation_count": 1,
                },
                manifest_fingerprint,
            )
        countries_in_scope = sorted(str(country_iso) for country_iso in prior_countries.keys())
        counts["countries_total"] = len(countries_in_scope)

        iso_df = pl.read_parquet(iso_path, columns=["country_iso"])
        iso_set = {str(row[0]) for row in iso_df.iter_rows()}
        missing_iso = sorted([iso for iso in countries_in_scope if iso not in iso_set])
        if missing_iso:
            _abort(
                "E3A_S2_005_ZONE_UNIVERSE_MISMATCH",
                "V-07",
                "unknown_country_iso",
                {"country_iso": missing_iso[0], "reason": "unknown_country"},
                manifest_fingerprint,
            )

        world_gdf = gpd.read_parquet(world_path)
        world_gdf = world_gdf[world_gdf["country_iso"].isin(list(countries_in_scope))]
        if world_gdf.empty:
            _abort(
                "E3A_S2_005_ZONE_UNIVERSE_MISMATCH",
                "V-07",
                "world_countries_missing_scope",
                {"country_iso": countries_in_scope[0], "reason": "no_zones_for_country"},
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
                "E3A_S2_005_ZONE_UNIVERSE_MISMATCH",
                "V-07",
                "world_countries_missing_iso",
                {"country_iso": missing_world[0], "reason": "no_zones_for_country"},
                manifest_fingerprint,
            )

        tz_gdf = gpd.read_parquet(tz_path)
        tz_world_rows = [(row.tzid, _row_geometry(row)) for row in tz_gdf.itertuples(index=False)]
        zone_map = _build_zone_index(world_geom_map, tz_world_rows, logger)
        zone_zero = [iso for iso, tzids in zone_map.items() if not tzids]
        if zone_zero:
            _abort(
                "E3A_S2_005_ZONE_UNIVERSE_MISMATCH",
                "V-07",
                "zone_count_zero",
                {"country_iso": zone_zero[0], "reason": "no_zones_for_country"},
                manifest_fingerprint,
            )
        zone_counts.update(len(tzids) for tzids in zone_map.values())

        if tz_cache_manifest is not None:
            expected_tag = _expected_release_tag("tz_world_2025a", tz_catalog_path)
            actual_tag = str(tz_cache_manifest.get("tzdb_release_tag") or "")
            tz_cache_release_tag = actual_tag
            if expected_tag and actual_tag and expected_tag != actual_tag:
                _abort(
                    "E3A_S2_005_ZONE_UNIVERSE_MISMATCH",
                    "V-07",
                    "tz_release_tag_mismatch",
                    {
                        "reason": "unmappable_tzid",
                        "expected_tag": expected_tag,
                        "actual_tag": actual_tag,
                    },
                    manifest_fingerprint,
                )

        timer.info("S2: derived zone universe from world_countries + tz_world")

        current_phase = "domain_check"
        prior_map: dict[str, dict[str, float]] = {}
        for country_iso, country_entry in prior_countries.items():
            entry = country_entry or {}
            tzid_alphas = entry.get("tzid_alphas") if isinstance(entry, dict) else None
            if not isinstance(tzid_alphas, list):
                _abort(
                    "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                    "V-08",
                    "prior_tzid_alphas_invalid",
                    {
                        "logical_id": PRIOR_ID,
                        "schema_ref": prior_row.get("schema_ref"),
                        "violation_count": 1,
                        "country_iso": country_iso,
                    },
                    manifest_fingerprint,
                )
            tz_map: dict[str, float] = {}
            for item in tzid_alphas:
                tzid = str(item.get("tzid") or "")
                alpha = float(item.get("alpha"))
                if tzid in tz_map:
                    _abort(
                        "E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID",
                        "V-08",
                        "prior_tzid_duplicate",
                        {
                            "logical_id": PRIOR_ID,
                            "schema_ref": prior_row.get("schema_ref"),
                            "violation_count": 1,
                            "country_iso": country_iso,
                            "tzid": tzid,
                        },
                        manifest_fingerprint,
                    )
                tz_map[tzid] = alpha
            prior_map[str(country_iso)] = tz_map

        missing_pairs_count = 0
        extra_pairs_count = 0
        missing_sample = None
        extra_sample = None
        for country_iso in countries_in_scope:
            tzids_zone = zone_map.get(country_iso) or set()
            tzids_prior = set(prior_map.get(country_iso, {}).keys())
            extra = tzids_prior - tzids_zone
            missing = tzids_zone - tzids_prior
            if extra:
                extra_pairs_count += len(extra)
                if extra_sample is None:
                    extra_sample = (country_iso, sorted(extra)[0])
            if missing:
                missing_pairs_count += len(missing)
                if missing_sample is None:
                    missing_sample = (country_iso, sorted(missing)[0])
        if extra_pairs_count:
            _abort(
                "E3A_S2_005_ZONE_UNIVERSE_MISMATCH",
                "V-09",
                "prior_tzid_unmappable",
                {
                    "country_iso": extra_sample[0],
                    "tzid": extra_sample[1],
                    "reason": "unmappable_tzid",
                },
                manifest_fingerprint,
            )
        if missing_pairs_count:
            _abort(
                "E3A_S2_007_DOMAIN_MISMATCH_UNIVERSE",
                "V-09",
                "prior_tzid_missing",
                {
                    "missing_pairs_count": missing_pairs_count,
                    "extra_pairs_count": 0,
                    "sample_country_iso": missing_sample[0] if missing_sample else None,
                    "sample_tzid": missing_sample[1] if missing_sample else None,
                },
                manifest_fingerprint,
            )

        current_phase = "alpha_derivation"
        pairs_total = sum(len(zone_map.get(country_iso, [])) for country_iso in countries_in_scope)
        counts["zones_total"] = int(pairs_total)
        tracker = _ProgressTracker(pairs_total, logger, "S2: deriving alpha priors per (country, tzid)")

        output_rows: list[dict] = []
        for country_iso in countries_in_scope:
            tzids = sorted(zone_map[country_iso])
            raw_by_tzid = prior_map[country_iso]
            alpha_raw_values = [float(raw_by_tzid[tzid]) for tzid in tzids]
            alpha_sum_raw = sum(alpha_raw_values)
            share_raw_values = []
            for alpha_raw in alpha_raw_values:
                if alpha_sum_raw > 0:
                    share_raw_values.append(alpha_raw / alpha_sum_raw)
                else:
                    share_raw_values.append(0.0)

            alpha_effective_values: list[float] = []
            floor_flags: list[bool] = []
            bump_flags: list[bool] = []
            for tzid, alpha_raw, share_raw in zip(tzids, alpha_raw_values, share_raw_values):
                floor_value, bump_threshold = floor_map.get(tzid, (0.0, 1.0))
                bump_candidate = share_raw >= bump_threshold
                floor_alpha = floor_value if bump_candidate else 0.0
                alpha_effective = max(alpha_raw, floor_alpha)
                floor_applied = alpha_effective > alpha_raw
                bump_applied = floor_applied
                if alpha_raw < 0 or alpha_effective <= 0:
                    _abort(
                        "E3A_S2_008_ALPHA_VECTOR_DEGENERATE_OR_INCONSISTENT",
                        "V-10",
                        "alpha_invalid",
                        {
                            "country_iso": country_iso,
                            "reason": "alpha_negative_or_zero",
                            "alpha_raw": alpha_raw,
                            "alpha_effective": alpha_effective,
                        },
                        manifest_fingerprint,
                    )
                alpha_effective_values.append(alpha_effective)
                floor_flags.append(floor_applied)
                bump_flags.append(bump_applied)

            alpha_sum_country = sum(alpha_effective_values)
            if alpha_sum_country <= 0:
                _abort(
                    "E3A_S2_008_ALPHA_VECTOR_DEGENERATE_OR_INCONSISTENT",
                    "V-10",
                    "alpha_sum_nonpositive",
                    {"country_iso": country_iso, "reason": "alpha_sum_nonpositive"},
                    manifest_fingerprint,
                )

            share_effective_values = [alpha / alpha_sum_country for alpha in alpha_effective_values]
            share_sum = sum(share_effective_values)
            if abs(share_sum - 1.0) > TOLERANCE:
                _abort(
                    "E3A_S2_008_ALPHA_VECTOR_DEGENERATE_OR_INCONSISTENT",
                    "V-10",
                    "share_sum_mismatch",
                    {
                        "country_iso": country_iso,
                        "reason": "share_sum_mismatch",
                        "expected": 1.0,
                        "observed": share_sum,
                    },
                    manifest_fingerprint,
                )
            for tzid, alpha_raw, alpha_effective, share_effective, floor_applied, bump_applied in zip(
                tzids,
                alpha_raw_values,
                alpha_effective_values,
                share_effective_values,
                floor_flags,
                bump_flags,
            ):
                output_rows.append(
                    {
                        "parameter_hash": str(parameter_hash),
                        "country_iso": country_iso,
                        "tzid": tzid,
                        "alpha_raw": float(alpha_raw),
                        "alpha_effective": float(alpha_effective),
                        "alpha_sum_country": float(alpha_sum_country),
                        "prior_pack_id": PRIOR_ID,
                        "prior_pack_version": prior_pack_version,
                        "floor_policy_id": FLOOR_ID,
                        "floor_policy_version": floor_policy_version,
                        "floor_applied": bool(floor_applied),
                        "bump_applied": bool(bump_applied),
                        "share_effective": float(share_effective),
                        "notes": None,
                    }
                )
                tracker.update(1)

        counts["floors_applied"] = sum(1 for row in output_rows if row["floor_applied"])
        counts["bumps_applied"] = sum(1 for row in output_rows if row["bump_applied"])

        output_entry = find_dataset_entry(dictionary, "s2_country_zone_priors").entry
        output_root = _resolve_dataset_path(output_entry, run_paths, config.external_roots, tokens)
        output_catalog_path = _render_catalog_path(output_entry, tokens)
        tmp_root = run_paths.tmp_root / f"s2_country_zone_priors_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        output_pack, output_table = _table_pack(schema_3a, "plan/s2_country_zone_priors")
        _inline_external_refs(output_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(iter(output_rows), output_pack, output_table)
        except SchemaValidationError as exc:
            _abort(
                "E3A_S2_009_OUTPUT_SCHEMA_INVALID",
                "V-11",
                "output_schema_invalid",
                {"violation_count": len(exc.errors), "detail": str(exc)},
                manifest_fingerprint,
            )

        df = pl.DataFrame(
            output_rows,
            schema={
                "parameter_hash": pl.Utf8,
                "country_iso": pl.Utf8,
                "tzid": pl.Utf8,
                "alpha_raw": pl.Float64,
                "alpha_effective": pl.Float64,
                "alpha_sum_country": pl.Float64,
                "prior_pack_id": pl.Utf8,
                "prior_pack_version": pl.Utf8,
                "floor_policy_id": pl.Utf8,
                "floor_policy_version": pl.Utf8,
                "floor_applied": pl.Boolean,
                "bump_applied": pl.Boolean,
                "share_effective": pl.Float64,
                "notes": pl.Utf8,
            },
        )
        df = df.sort(["country_iso", "tzid"])
        output_path = tmp_root / "part-00000.parquet"
        df.write_parquet(output_path, compression="zstd")
        logger.info("S2: wrote %d rows to %s", df.height, output_path)

        _publish_partition(tmp_root, output_root, df, logger)
        timer.info("S2: published country-zone priors")

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
            error_code = "E3A_S2_002_CATALOGUE_MALFORMED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3A_S2_012_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3A_S2_012_INFRASTRUCTURE_IO_ERROR"
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
                logger.warning("S2: failed to write segment_state_runs: %s", exc)

            try:
                run_report_entry = find_dataset_entry(dictionary, "s2_run_report_3A").entry
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
                        "prior_pack_id": PRIOR_ID,
                        "prior_pack_version": prior_pack_version,
                        "floor_policy_id": FLOOR_ID,
                        "floor_policy_version": floor_policy_version,
                    },
                    "counts": counts,
                    "zone_count_buckets": {str(k): v for k, v in zone_counts.items()},
                    "tz_cache_release_tag": tz_cache_release_tag,
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {"path": output_catalog_path if output_root else None, "format": "parquet"},
                }
                _write_json(run_report_path, run_report)
                logger.info("S2: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S2: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3A_S2_012_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if output_root is None or run_report_path is None:
        raise EngineFailure(
            "F4",
            "E3A_S2_012_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S2Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        output_path=output_root,
        run_report_path=run_report_path,
    )
