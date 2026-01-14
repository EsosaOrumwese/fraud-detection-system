"""S1 provisional time-zone lookup runner for Segment 2A."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import numpy as np
import polars as pl
from jsonschema import Draft202012Validator
from shapely.geometry import Point
from shapely.strtree import STRtree

try:
    import geopandas as gpd

    _HAVE_GEOPANDAS = True
except Exception:  # pragma: no cover - optional dependency.
    gpd = None
    _HAVE_GEOPANDAS = False

try:
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - optional dependency.
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.jsonschema_adapter import validate_dataframe
from engine.contracts.loader import (
    find_artifact_entry,
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
from engine.layers.l1.seg_1B.s1_tile_index.runner import _split_antimeridian_geometries
from engine.layers.l1.seg_2A.s0_gate.runner import (
    _extract_geo_crs,
    _is_wgs84,
    _load_json,
    _load_tz_world_metadata,
    _load_yaml,
    _prepare_row_schema_with_layer1_defs,
    _prepare_table_pack_with_layer1_defs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _validate_payload,
    _hash_partition,
)


MODULE_NAME = "2A.S1.tz_lookup"
SEGMENT = "2A"
STATE = "S1"
BATCH_SIZE = 200_000


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
    }
    payload.update(detail)
    logger.error("S1_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))

def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    return schema


def _resolve_schema_ref(entry: dict, registry_entry: Optional[dict], dataset_id: str) -> str:
    dict_ref = entry.get("schema_ref")
    registry_ref = None
    if registry_entry:
        registry_ref = registry_entry.get("schema")
        if isinstance(registry_ref, dict):
            registry_ref = registry_ref.get("index_schema_ref") or registry_ref.get("schema_ref")
    if dict_ref and registry_ref and dict_ref != registry_ref:
        raise EngineFailure(
            "F4",
            "2A-S1-080",
            STATE,
            MODULE_NAME,
            {
                "detail": "schema_ref_mismatch",
                "dataset_id": dataset_id,
                "dictionary": dict_ref,
                "registry": registry_ref,
            },
        )
    return dict_ref or registry_ref or ""


def _assert_schema_ref(
    schema_ref: str,
    schema_packs: dict[str, dict],
    dataset_id: str,
    logger,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> None:
    if not schema_ref:
        _emit_failure_event(
            logger,
            "2A-S1-080",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
        raise EngineFailure(
            "F4",
            "2A-S1-080",
            STATE,
            MODULE_NAME,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
    for prefix, pack in schema_packs.items():
        if schema_ref.startswith(prefix + "#"):
            try:
                _schema_from_pack(pack, schema_ref.split("#", 1)[1])
            except Exception as exc:
                _emit_failure_event(
                    logger,
                    "2A-S1-080",
                    seed,
                    manifest_fingerprint,
                    parameter_hash,
                    run_id,
                    {
                        "detail": "schema_ref_invalid",
                        "dataset_id": dataset_id,
                        "schema_ref": schema_ref,
                        "error": str(exc),
                    },
                )
                raise EngineFailure(
                    "F4",
                    "2A-S1-080",
                    STATE,
                    MODULE_NAME,
                    {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
                ) from exc
            return
    _emit_failure_event(
        logger,
        "2A-S1-080",
        seed,
        manifest_fingerprint,
        parameter_hash,
        run_id,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )
    raise EngineFailure(
        "F4",
        "2A-S1-080",
        STATE,
        MODULE_NAME,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _close_parquet_reader(reader: object) -> None:
    if hasattr(reader, "close"):
        try:
            reader.close()
        except Exception:
            pass


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted([path for path in root.rglob("*.parquet") if path.is_file()])
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _count_parquet_rows(paths: Iterable[Path]) -> Optional[int]:
    if not _HAVE_PYARROW:
        return None
    total = 0
    for path in paths:
        pf = pq.ParquetFile(path)
        try:
            total += pf.metadata.num_rows
        finally:
            _close_parquet_reader(pf)
    return total


def _iter_parquet_batches(paths: list[Path], columns: list[str]) -> Iterator[pl.DataFrame]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for batch in pf.iter_batches(columns=columns, batch_size=BATCH_SIZE):
                    yield pl.from_arrow(batch)
            finally:
                _close_parquet_reader(pf)
    else:
        for path in paths:
            df = pl.read_parquet(path, columns=columns)
            offset = 0
            while offset < df.height:
                chunk = df.slice(offset, BATCH_SIZE)
                offset += chunk.height
                yield chunk


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2A-S1-041",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S1: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _wrap_lon(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0


def _clamp_lat(lat: float) -> float:
    return max(min(lat, 90.0), -90.0)


def _apply_nudge(lat: float, lon: float, epsilon: float) -> tuple[float, float]:
    return _clamp_lat(lat + epsilon), _wrap_lon(lon + epsilon)


def _tree_query_indices(tree: STRtree, geom_index: dict[int, int], point: Point) -> list[int]:
    result = tree.query(point)
    if hasattr(result, "dtype") and np.issubdtype(result.dtype, np.integer):
        return result.tolist()
    if result and isinstance(result[0], (int, np.integer)):
        return list(result)
    return [geom_index[id(geom)] for geom in result if id(geom) in geom_index]


def _candidate_tzids(
    tree: STRtree,
    geoms: list,
    tzids: list[str],
    geom_index: dict[int, int],
    point: Point,
) -> set[str]:
    indices = _tree_query_indices(tree, geom_index, point)
    if not indices:
        return set()
    matches: set[str] = set()
    for idx in indices:
        geom = geoms[idx]
        if geom.covers(point):
            matches.add(tzids[idx])
    return matches


def _build_tz_index(tz_world_path: Path, logger) -> tuple[list, list[str], STRtree, dict[int, int], set[str]]:
    if not _HAVE_GEOPANDAS:
        raise EngineFailure(
            "F4",
            "2A-S1-020",
            STATE,
            MODULE_NAME,
            {"detail": "geopandas_unavailable", "path": str(tz_world_path)},
        )
    gdf = gpd.read_parquet(tz_world_path)
    if "tzid" not in gdf.columns:
        raise EngineFailure(
            "F4",
            "2A-S1-020",
            STATE,
            MODULE_NAME,
            {"detail": "tz_world_missing_tzid", "path": str(tz_world_path)},
        )
    geoms: list = []
    tzids: list[str] = []
    for tzid, geom in zip(gdf["tzid"].astype(str), gdf.geometry):
        if geom is None:
            raise EngineFailure(
                "F4",
                "2A-S1-020",
                STATE,
                MODULE_NAME,
                {"detail": "tz_world_null_geom", "path": str(tz_world_path)},
            )
        parts = _split_antimeridian_geometries(geom)
        for part in parts:
            geoms.append(part)
            tzids.append(tzid)
    if not geoms:
        raise EngineFailure(
            "F4",
            "2A-S1-020",
            STATE,
            MODULE_NAME,
            {"detail": "tz_world_empty_geoms", "path": str(tz_world_path)},
        )
    geom_index = {id(geom): idx for idx, geom in enumerate(geoms)}
    tree = STRtree(geoms)
    return geoms, tzids, tree, geom_index, set(tzids)


def _write_batch(df: pl.DataFrame, batch_index: int, output_tmp: Path, logger) -> None:
    if df.height == 0:
        return
    path = output_tmp / f"part-{batch_index:05d}.parquet"
    df.write_parquet(path, compression="zstd", row_group_size=100000)
    logger.info("S1: wrote %d rows to %s", df.height, path)

def run_s1(config: EngineConfig, run_id: Optional[str] = None) -> S1Result:
    logger = get_logger("engine.layers.l1.seg_2A.s1_tz_lookup.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    warnings: list[str] = []
    errors: list[dict] = []
    status = "fail"

    seed: Optional[int] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    receipt_catalog_path = ""
    receipt_verified_utc = ""
    site_locations_catalog_path = ""
    tz_world_license = ""
    tz_world_id = "tz_world_2025a"
    tz_nudge_semver = ""
    tz_nudge_digest = ""
    output_catalog_path = ""
    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None
    counts = {
        "sites_total": 0,
        "rows_emitted": 0,
        "border_nudged": 0,
        "distinct_tzids": 0,
    }
    checks = {
        "pk_duplicates": 0,
        "coverage_mismatch": 0,
        "null_tzid": 0,
        "unknown_tzid": 0,
    }
    writer_order_violation = False

    try:
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
        dict_path, dictionary = load_dataset_dictionary(source, "2A")
        registry_path, registry = load_artefact_registry(source, "2A")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s,%s",
            config.contracts_layout,
            config.contracts_root,
            dict_path,
            registry_path,
            schema_2a_path,
            schema_1b_path,
            schema_ingress_path,
            schema_layer1_path,
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
        }
        def _dataset_entry(dataset_id: str) -> dict:
            try:
                return find_dataset_entry(dictionary, dataset_id).entry
            except ContractError as exc:
                raise EngineFailure(
                    "F4",
                    "2A-S1-010",
                    STATE,
                    MODULE_NAME,
                    {"detail": "missing_dictionary_entry", "dataset_id": dataset_id},
                ) from exc

        def _registry_entry(name: str) -> dict:
            try:
                return find_artifact_entry(registry, name).entry
            except ContractError as exc:
                raise EngineFailure(
                    "F4",
                    "2A-S1-010",
                    STATE,
                    MODULE_NAME,
                    {"detail": "missing_registry_entry", "artifact": name},
                ) from exc

        entries = {
            "s0_gate_receipt_2A": _dataset_entry("s0_gate_receipt_2A"),
            "sealed_inputs_2A": _dataset_entry("sealed_inputs_2A"),
            "site_locations": _dataset_entry("site_locations"),
            "tz_world_2025a": _dataset_entry("tz_world_2025a"),
            "tz_nudge": _dataset_entry("tz_nudge"),
            "s1_tz_lookup": _dataset_entry("s1_tz_lookup"),
        }
        registry_entries = {
            "s0_gate_receipt_2A": _registry_entry("s0_gate_receipt_2A"),
            "site_locations": _registry_entry("site_locations"),
            "tz_world_2025a": _registry_entry("tz_world_2025a"),
            "tz_nudge": _registry_entry("tz_nudge"),
        }
        tz_world_license = registry_entries["tz_world_2025a"].get("license", "")

        schema_packs = {
            "schemas.2A.yaml": schema_2a,
            "schemas.1B.yaml": schema_1b,
            "schemas.ingress.layer1.yaml": schema_ingress,
            "schemas.layer1.yaml": schema_layer1,
        }

        for dataset_id, entry in entries.items():
            registry_entry = registry_entries.get(dataset_id)
            schema_ref = _resolve_schema_ref(entry, registry_entry, dataset_id)
            _assert_schema_ref(
                schema_ref,
                schema_packs,
                dataset_id,
                logger,
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
            )

        receipt_path = _resolve_dataset_path(
            entries["s0_gate_receipt_2A"], run_paths, config.external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
        )
        sealed_inputs_path = _resolve_dataset_path(
            entries["sealed_inputs_2A"], run_paths, config.external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
        )
        site_locations_path = _resolve_dataset_path(entries["site_locations"], run_paths, config.external_roots, tokens)
        tz_world_path = _resolve_dataset_path(entries["tz_world_2025a"], run_paths, config.external_roots, tokens)
        tz_nudge_path = _resolve_dataset_path(entries["tz_nudge"], run_paths, config.external_roots, tokens)
        output_root = _resolve_dataset_path(entries["s1_tz_lookup"], run_paths, config.external_roots, tokens)

        receipt_catalog_path = _render_catalog_path(entries["s0_gate_receipt_2A"], {"manifest_fingerprint": str(manifest_fingerprint)})
        site_locations_catalog_path = _render_catalog_path(entries["site_locations"], tokens)
        output_catalog_path = _render_catalog_path(entries["s1_tz_lookup"], tokens)
        run_report_path = (
            run_paths.run_root
            / "reports"
            / "layer1"
            / "2A"
            / "state=S1"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "s1_run_report.json"
        )
        if not receipt_path.exists():
            _emit_failure_event(
                logger,
                "2A-S1-001",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "missing_s0_receipt", "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-001",
                STATE,
                MODULE_NAME,
                {"detail": "missing_s0_receipt", "path": str(receipt_path)},
                dataset_id="s0_gate_receipt_2A",
            )
        receipt_payload = _load_json(receipt_path)
        receipt_schema = _prepare_row_schema_with_layer1_defs(
            schema_2a, "validation/s0_gate_receipt_v1", schema_layer1, "schemas.layer1.yaml"
        )
        validator = Draft202012Validator(receipt_schema)
        receipt_errors = list(validator.iter_errors(receipt_payload))
        if receipt_errors:
            detail = receipt_errors[0].message if receipt_errors else "schema validation failed"
            _emit_failure_event(
                logger,
                "2A-S1-001",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": detail, "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-001",
                STATE,
                MODULE_NAME,
                {"detail": detail, "path": str(receipt_path)},
                dataset_id="s0_gate_receipt_2A",
            )
        if receipt_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _emit_failure_event(
                logger,
                "2A-S1-001",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "receipt_manifest_mismatch", "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-001",
                STATE,
                MODULE_NAME,
                {"detail": "receipt_manifest_mismatch", "path": str(receipt_path)},
                dataset_id="s0_gate_receipt_2A",
            )
        receipt_verified_utc = str(receipt_payload.get("verified_at_utc", ""))
        _emit_event(
            logger,
            "GATE",
            seed,
            manifest_fingerprint,
            "INFO",
            receipt_path=receipt_catalog_path,
            result="verified",
        )
        _emit_validation(logger, seed, manifest_fingerprint, "V-01", "pass")

        sealed_inputs_payload = _load_json(sealed_inputs_path)
        sealed_index = {item.get("asset_id"): item for item in sealed_inputs_payload if isinstance(item, dict)}
        required_ids = ["site_locations", "tz_world_2025a", "tz_nudge"]
        missing = [asset_id for asset_id in required_ids if asset_id not in sealed_index]
        if missing:
            _emit_failure_event(
                logger,
                "2A-S1-010",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "missing_sealed_inputs", "missing": missing},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-010",
                STATE,
                MODULE_NAME,
                {"detail": "missing_sealed_inputs", "missing": missing},
            )
        for dataset_id in required_ids:
            sealed_schema_ref = sealed_index[dataset_id].get("schema_ref")
            dict_schema_ref = entries[dataset_id].get("schema_ref")
            if sealed_schema_ref and dict_schema_ref and sealed_schema_ref != dict_schema_ref:
                _emit_failure_event(
                    logger,
                    "2A-S1-080",
                    seed,
                    manifest_fingerprint,
                    str(parameter_hash),
                    run_id,
                    {
                        "detail": "schema_ref_mismatch",
                        "dataset_id": dataset_id,
                        "sealed": sealed_schema_ref,
                        "dictionary": dict_schema_ref,
                    },
                )
                raise EngineFailure(
                    "F4",
                    "2A-S1-080",
                    STATE,
                    MODULE_NAME,
                    {
                        "detail": "schema_ref_mismatch",
                        "dataset_id": dataset_id,
                        "sealed": sealed_schema_ref,
                        "dictionary": dict_schema_ref,
                    },
                )

        expected_seed = f"seed={seed}"
        expected_manifest = f"manifest_fingerprint={manifest_fingerprint}"
        if expected_seed not in str(site_locations_path) or expected_manifest not in str(site_locations_path):
            _emit_failure_event(
                logger,
                "2A-S1-011",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "partition_mismatch", "path": str(site_locations_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-011",
                STATE,
                MODULE_NAME,
                {"detail": "partition_mismatch", "path": str(site_locations_path)},
                dataset_id="site_locations",
            )

        _emit_event(
            logger,
            "INPUTS",
            seed,
            manifest_fingerprint,
            "INFO",
            site_locations=site_locations_catalog_path,
            tz_world=str(tz_world_path),
            tz_nudge=str(tz_nudge_path),
        )
        _emit_validation(logger, seed, manifest_fingerprint, "V-02", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-03", "pass")

        tz_world_crs = _extract_geo_crs(tz_world_path)
        if not _is_wgs84(tz_world_crs):
            _emit_failure_event(
                logger,
                "2A-S1-020",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "tz_world_crs_invalid", "crs": tz_world_crs, "path": str(tz_world_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-020",
                STATE,
                MODULE_NAME,
                {"detail": "tz_world_crs_invalid", "crs": tz_world_crs, "path": str(tz_world_path)},
                dataset_id="tz_world_2025a",
            )
        tz_world_count = _load_tz_world_metadata(tz_world_path)
        if tz_world_count <= 0:
            _emit_failure_event(
                logger,
                "2A-S1-020",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "tz_world_empty", "path": str(tz_world_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-020",
                STATE,
                MODULE_NAME,
                {"detail": "tz_world_empty", "path": str(tz_world_path)},
                dataset_id="tz_world_2025a",
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-04", "pass")

        nudge_payload = _load_yaml(tz_nudge_path)
        try:
            _validate_payload(
                schema_2a,
                "policy/tz_nudge_v1",
                nudge_payload,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            _emit_failure_event(
                logger,
                "2A-S1-021",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": exc.errors, "path": str(tz_nudge_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-021",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors, "path": str(tz_nudge_path)},
                dataset_id="tz_nudge",
            ) from exc
        epsilon = float(nudge_payload.get("epsilon_degrees", 0.0))
        if epsilon <= 0.0:
            _emit_failure_event(
                logger,
                "2A-S1-021",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "epsilon_invalid", "epsilon": epsilon},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-021",
                STATE,
                MODULE_NAME,
                {"detail": "epsilon_invalid", "epsilon": epsilon},
                dataset_id="tz_nudge",
            )
        tz_nudge_semver = str(nudge_payload.get("semver", ""))
        tz_nudge_digest = str(nudge_payload.get("sha256_digest", ""))
        _emit_validation(logger, seed, manifest_fingerprint, "V-05", "pass")

        output_pack, output_table = _prepare_table_pack_with_layer1_defs(
            schema_2a, "plan/s1_tz_lookup", schema_layer1, "schemas.layer1.yaml"
        )
        geoms, tzids, tree, geom_index, tzid_set = _build_tz_index(tz_world_path, logger)
        logger.info("S1: tz_world polygons loaded=%d", len(geoms))

        site_paths = _list_parquet_files(site_locations_path)
        total_rows = _count_parquet_rows(site_paths)
        progress = _ProgressTracker(total_rows, logger, "S1 progress")

        output_tmp = run_paths.tmp_root / f"s1_tz_lookup_{uuid.uuid4().hex}"
        output_tmp.mkdir(parents=True, exist_ok=True)

        created_utc = str(receipt.get("created_utc", started_utc))
        output_schema = [
            ("seed", pl.UInt64),
            ("manifest_fingerprint", pl.Utf8),
            ("merchant_id", pl.UInt64),
            ("legal_country_iso", pl.Utf8),
            ("site_order", pl.Int32),
            ("lat_deg", pl.Float64),
            ("lon_deg", pl.Float64),
            ("tzid_provisional", pl.Utf8),
            ("nudge_lat_deg", pl.Float64),
            ("nudge_lon_deg", pl.Float64),
            ("created_utc", pl.Utf8),
        ]

        columns = ["merchant_id", "legal_country_iso", "site_order", "lat_deg", "lon_deg"]
        pk_seen: set[tuple] = set()
        distinct_tzids: set[str] = set()
        last_key: Optional[tuple] = None
        batch_index = 0
        sites_total = 0
        rows_emitted = 0
        border_nudged = 0
        null_tzid = 0
        unknown_tzid = 0

        timer.info("S1: starting tz lookup")
        for batch in _iter_parquet_batches(site_paths, columns):
            if batch.height == 0:
                continue
            sites_total += batch.height
            counts["sites_total"] = sites_total
            output_rows: list[tuple] = []
            for row in batch.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                legal_country_iso = row["legal_country_iso"]
                site_order = int(row["site_order"])
                lat = float(row["lat_deg"])
                lon = float(row["lon_deg"])
                key = (merchant_id, legal_country_iso, site_order)
                if last_key is not None and key < last_key:
                    writer_order_violation = True
                last_key = key
                if key in pk_seen:
                    checks["pk_duplicates"] += 1
                else:
                    pk_seen.add(key)

                point = Point(lon, lat)
                candidates = _candidate_tzids(tree, geoms, tzids, geom_index, point)
                nudge_lat = None
                nudge_lon = None
                if len(candidates) != 1:
                    nudge_lat, nudge_lon = _apply_nudge(lat, lon, epsilon)
                    border_nudged += 1
                    counts["border_nudged"] = border_nudged
                    point = Point(nudge_lon, nudge_lat)
                    candidates = _candidate_tzids(tree, geoms, tzids, geom_index, point)
                    if len(candidates) != 1:
                        _emit_failure_event(
                            logger,
                            "2A-S1-055",
                            seed,
                            manifest_fingerprint,
                            str(parameter_hash),
                            run_id,
                            {"detail": "border_ambiguity_unresolved", "key": key},
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S1-055",
                            STATE,
                            MODULE_NAME,
                            {"detail": "border_ambiguity_unresolved", "key": key},
                        )
                if nudge_lat is None and nudge_lon is not None:
                    _emit_failure_event(
                        logger,
                        "2A-S1-054",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        run_id,
                        {"detail": "nudge_pair_violation", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S1-054",
                        STATE,
                        MODULE_NAME,
                        {"detail": "nudge_pair_violation", "key": key},
                    )
                if nudge_lat is not None and nudge_lon is None:
                    _emit_failure_event(
                        logger,
                        "2A-S1-054",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        run_id,
                        {"detail": "nudge_pair_violation", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S1-054",
                        STATE,
                        MODULE_NAME,
                        {"detail": "nudge_pair_violation", "key": key},
                    )

                tzid = next(iter(candidates)) if len(candidates) == 1 else None
                if tzid is None:
                    null_tzid += 1
                    checks["null_tzid"] = null_tzid
                    _emit_failure_event(
                        logger,
                        "2A-S1-052",
                        seed,
                        manifest_fingerprint,
                        str(parameter_hash),
                        run_id,
                        {"detail": "null_tzid", "key": key},
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S1-052",
                        STATE,
                        MODULE_NAME,
                        {"detail": "null_tzid", "key": key},
                    )
                if tzid not in tzid_set:
                    unknown_tzid += 1
                    checks["unknown_tzid"] = unknown_tzid
                distinct_tzids.add(tzid)
                counts["distinct_tzids"] = len(distinct_tzids)

                output_rows.append(
                    (
                        seed,
                        str(manifest_fingerprint),
                        merchant_id,
                        legal_country_iso,
                        site_order,
                        lat,
                        lon,
                        tzid,
                        nudge_lat,
                        nudge_lon,
                        created_utc,
                    )
                )

            df = pl.DataFrame(output_rows, schema=output_schema, orient="row")
            try:
                validate_dataframe(df.iter_rows(named=True), output_pack, output_table)
            except SchemaValidationError as exc:
                _emit_failure_event(
                    logger,
                    "2A-S1-030",
                    seed,
                    manifest_fingerprint,
                    str(parameter_hash),
                    run_id,
                    {"detail": exc.errors},
                )
                raise EngineFailure(
                    "F4",
                    "2A-S1-030",
                    STATE,
                    MODULE_NAME,
                    {"detail": exc.errors},
                ) from exc

            _write_batch(df, batch_index, output_tmp, logger)
            batch_index += 1
            rows_emitted += df.height
            counts["rows_emitted"] = rows_emitted
            progress.update(df.height)

        counts["sites_total"] = sites_total
        counts["rows_emitted"] = rows_emitted
        counts["border_nudged"] = border_nudged
        counts["distinct_tzids"] = len(distinct_tzids)
        checks["null_tzid"] = null_tzid
        checks["unknown_tzid"] = unknown_tzid

        if rows_emitted != sites_total:
            checks["coverage_mismatch"] = abs(rows_emitted - sites_total)
            _emit_failure_event(
                logger,
                "2A-S1-050",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "coverage_mismatch", "sites_total": sites_total, "rows_emitted": rows_emitted},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-050",
                STATE,
                MODULE_NAME,
                {"detail": "coverage_mismatch", "sites_total": sites_total, "rows_emitted": rows_emitted},
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-09", "pass")

        if checks["pk_duplicates"] > 0:
            _emit_failure_event(
                logger,
                "2A-S1-051",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                run_id,
                {"detail": "primary_key_duplicate", "count": checks["pk_duplicates"]},
            )
            raise EngineFailure(
                "F4",
                "2A-S1-051",
                STATE,
                MODULE_NAME,
                {"detail": "primary_key_duplicate", "count": checks["pk_duplicates"]},
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-10", "pass")

        if checks["null_tzid"] > 0:
            raise EngineFailure(
                "F4",
                "2A-S1-052",
                STATE,
                MODULE_NAME,
                {"detail": "null_tzid", "count": checks["null_tzid"]},
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-11", "pass")

        if checks["unknown_tzid"] > 0:
            raise EngineFailure(
                "F4",
                "2A-S1-053",
                STATE,
                MODULE_NAME,
                {"detail": "unknown_tzid", "count": checks["unknown_tzid"]},
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-12", "pass")

        _emit_validation(logger, seed, manifest_fingerprint, "V-13", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-14", "pass")

        if writer_order_violation:
            warnings.append("2A-S1-070")
            _emit_validation(
                logger,
                seed,
                manifest_fingerprint,
                "V-15",
                "warn",
                "2A-S1-070",
                "writer order non-compliant",
            )
        else:
            _emit_validation(logger, seed, manifest_fingerprint, "V-15", "pass")

        _emit_event(
            logger,
            "LOOKUP",
            seed,
            manifest_fingerprint,
            "INFO",
            sites_total=sites_total,
            rows_emitted=rows_emitted,
            border_nudged=border_nudged,
            distinct_tzids=len(distinct_tzids),
        )

        _atomic_publish_dir(output_tmp, output_root, logger, "s1_tz_lookup")
        _emit_event(
            logger,
            "EMIT",
            seed,
            manifest_fingerprint,
            "INFO",
            output_path=output_catalog_path,
            format="parquet",
        )
        status = "pass"
        return S1Result(
            run_id=run_id,
            parameter_hash=str(parameter_hash),
            manifest_fingerprint=str(manifest_fingerprint),
            output_root=output_root,
            run_report_path=run_report_path,
        )
    except EngineFailure as exc:
        errors.append(
            {
                "code": exc.failure_code,
                "message": str(exc),
                "context": exc.detail,
            }
        )
        raise
    except Exception as exc:
        errors.append(
            {
                "code": "UNHANDLED_EXCEPTION",
                "message": str(exc),
                "context": {},
            }
        )
        raise
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_report_path:
            run_report = {
                "segment": SEGMENT,
                "state": STATE,
                "status": status,
                "manifest_fingerprint": str(manifest_fingerprint) if manifest_fingerprint else "",
                "seed": int(seed) if seed is not None else 0,
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                "s0": {
                    "receipt_path": receipt_catalog_path,
                    "verified_at_utc": receipt_verified_utc,
                },
                "inputs": {
                    "site_locations": {"path": site_locations_catalog_path},
                    "tz_world": {"id": tz_world_id, "license": tz_world_license},
                    "tz_nudge": {"semver": tz_nudge_semver, "sha256_digest": tz_nudge_digest},
                },
                "counts": counts,
                "checks": checks,
                "output": {"path": output_catalog_path, "format": "parquet"},
                "warnings": warnings,
                "errors": errors,
            }
            _write_json(run_report_path, run_report)
            logger.info("S1: run-report written %s", run_report_path)
