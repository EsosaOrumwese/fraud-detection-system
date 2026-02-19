"""S2 edge catalogue construction for Segment 3B."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import struct
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_FLOOR, getcontext
from pathlib import Path
from typing import Iterable, Iterator, Optional

import polars as pl
from jsonschema import Draft202012Validator
from shapely.errors import GEOSException
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

try:
    import geopandas as gpd

    _HAVE_GEOPANDAS = True
except Exception:  # pragma: no cover - optional dependency.
    gpd = None
    _HAVE_GEOPANDAS = False

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
from engine.layers.l1.seg_1A.s0_foundations.rng import RngTraceAccumulator
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    add_u128,
    low64,
    philox2x64_10,
    ser_u64,
    u01,
    uer_string,
)
from engine.layers.l1.seg_1B.s1_tile_index.runner import _split_antimeridian_geometries
from engine.layers.l1.seg_2A.s0_gate.runner import _extract_geo_crs, _is_wgs84
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


MODULE_NAME = "3B.S2.edge_catalogue"
SEGMENT = "3B"
STATE = "S2"
RNG_MODULE = "3B.S2"
SUBSTREAM_JITTER = "edge_jitter"
SUBSTREAM_TILE = "edge_tile_assign"
RNG_DOMAIN_MASTER = "mlr:3B.edge_catalogue.master"
RNG_DOMAIN_STREAM = "mlr:3B.edge_catalogue.stream"
EDGE_ID_PREFIX = "3B.EDGE"
MAX_ATTEMPTS = 64
EDGE_BATCH_SIZE = 100_000


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    edge_catalogue_root: Path
    index_path: Path
    run_report_path: Path
    event_root: Path
    trace_path: Path
    audit_path: Path


@dataclass(frozen=True)
class _CountryGeometry:
    parts: list
    prepared: list


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
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l1.seg_3B.s2_edge_catalogue.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_json_compact(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _tile_surface_cache_key(
    tile_index_digest: str,
    tile_weights_digest: str,
    tile_bounds_digest: str,
    countries_sorted: list[str],
    edge_scale: int,
) -> str:
    h = hashlib.sha256()
    h.update(tile_index_digest.encode("ascii"))
    h.update(b"|")
    h.update(tile_weights_digest.encode("ascii"))
    h.update(b"|")
    h.update(tile_bounds_digest.encode("ascii"))
    h.update(b"|")
    h.update(str(edge_scale).encode("ascii"))
    h.update(b"|")
    for country_iso in countries_sorted:
        h.update(country_iso.encode("ascii"))
        h.update(b",")
    return h.hexdigest()


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


def _country_from_partition_path(path: Path) -> Optional[str]:
    for token in path.parts:
        if token.startswith("country="):
            country_iso = token.split("=", 1)[1].strip().upper()
            if len(country_iso) == 2 and country_iso.isalpha():
                return country_iso
    return None


def _country_from_part_suffix(path: Path) -> Optional[str]:
    stem = path.stem
    if not stem.startswith("part-"):
        return None
    country_iso = stem.split("-", 1)[1].strip().upper()
    if len(country_iso) == 2 and country_iso.isalpha():
        return country_iso
    return None


def _group_paths_by_country(paths: list[Path], mode: str) -> tuple[dict[str, list[Path]], list[Path]]:
    grouped: dict[str, list[Path]] = {}
    unresolved: list[Path] = []
    for path in paths:
        if mode == "country_partition":
            country_iso = _country_from_partition_path(path)
        elif mode == "part_suffix":
            country_iso = _country_from_part_suffix(path)
        else:
            raise ValueError(f"unsupported country-group mode: {mode}")
        if country_iso:
            grouped.setdefault(country_iso, []).append(path)
        else:
            unresolved.append(path)
    for files in grouped.values():
        files.sort()
    unresolved.sort()
    return grouped, unresolved


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E3B_S2_020_IMMUTABILITY_VIOLATION",
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
        logger.info("S2: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E3B_S2_020_IMMUTABILITY_VIOLATION",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S2: %s file already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)


def _partition_size_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def _event_root_from_path(path: Path) -> Path:
    if "*" in path.name or path.suffix:
        return path.parent
    return path


def _event_file_from_root(root: Path) -> Path:
    if root.is_file():
        return root
    return root / "part-00000.jsonl"


def _iter_jsonl_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.jsonl") if path.is_file())


def _iter_jsonl_rows(paths: Iterable[Path], label: str) -> Iterator[dict]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                payload = line.strip()
                if not payload:
                    continue
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise EngineFailure(
                        "F4",
                        "E3B_S2_022_JSONL_PARSE",
                        STATE,
                        MODULE_NAME,
                        {"detail": str(exc), "path": str(path), "line": line_no, "label": label},
                    ) from exc


def _trace_has_substream(trace_path: Path, module: str, substream_label: str) -> bool:
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            try:
                record = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if record.get("module") == module and record.get("substream_label") == substream_label:
                return True
    return False


def _append_trace_from_events(
    event_root: Path, trace_handle, trace_acc: RngTraceAccumulator, logger
) -> int:
    event_paths = _iter_jsonl_paths(event_root)
    if not event_paths:
        raise EngineFailure(
            "F4",
            "E3B_S2_022_EVENT_LOG_EMPTY",
            STATE,
            MODULE_NAME,
            {"detail": "no_event_jsonl_files", "path": str(event_root)},
        )
    rows_written = 0
    for event in _iter_jsonl_rows(event_paths, "rng_event_edge_jitter"):
        trace_row = trace_acc.append_event(event)
        trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
        trace_handle.write("\n")
        rows_written += 1
    logger.info("S2: appended trace rows from existing events rows=%d", rows_written)
    return rows_written


def _ensure_rng_audit(audit_path: Path, audit_entry: dict, logger) -> None:
    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if (
                    payload.get("run_id") == audit_entry.get("run_id")
                    and payload.get("seed") == audit_entry.get("seed")
                    and payload.get("parameter_hash") == audit_entry.get("parameter_hash")
                    and payload.get("manifest_fingerprint") == audit_entry.get("manifest_fingerprint")
                ):
                    logger.info("S2: rng_audit_log already contains audit row for run_id=%s", audit_entry["run_id"])
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("S2: appended rng_audit_log entry for run_id=%s", audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("S2: wrote rng_audit_log entry for run_id=%s", audit_entry["run_id"])


def _normalize_lon(value: float) -> float:
    if value > 180.0:
        return value - 360.0
    if value < -180.0:
        return value + 360.0
    return value


def _wrap_lon(value: float) -> float:
    while value > 180.0:
        value -= 360.0
    while value < -180.0:
        value += 360.0
    return value


def _clamp_lat(value: float) -> float:
    return max(min(value, 90.0), -90.0)


def _load_world_countries(world_path: Path) -> dict[str, _CountryGeometry]:
    if not _HAVE_GEOPANDAS:
        raise EngineFailure(
            "F4",
            "E3B_S2_030_GEOPANDAS_MISSING",
            STATE,
            MODULE_NAME,
            {"detail": "geopandas_unavailable", "path": str(world_path)},
        )
    world_gdf = gpd.read_parquet(world_path)
    if "country_iso" not in world_gdf.columns or "geom" not in world_gdf.columns:
        raise InputResolutionError("world_countries missing required columns (country_iso, geom).")
    world_gdf["country_iso"] = world_gdf["country_iso"].astype(str).str.upper()
    grouped = world_gdf.groupby("country_iso")["geom"].agg(lambda items: unary_union(list(items)))
    world_map = grouped.to_dict()
    output: dict[str, _CountryGeometry] = {}
    for iso, geom in world_map.items():
        if geom is None or geom.is_empty:
            raise EngineFailure(
                "F4",
                "E3B_S2_031_COUNTRY_GEOM_EMPTY",
                STATE,
                MODULE_NAME,
                {"detail": "empty_geometry", "country_iso": iso},
            )
        if not geom.is_valid:
            raise EngineFailure(
                "F4",
                "E3B_S2_031_COUNTRY_GEOM_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": "invalid_geometry", "country_iso": iso},
            )
        try:
            parts = _split_antimeridian_geometries(geom)
        except GEOSException as exc:
            raise EngineFailure(
                "F4",
                "E3B_S2_031_COUNTRY_GEOM_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "country_iso": iso},
            ) from exc
        if not parts:
            raise EngineFailure(
                "F4",
                "E3B_S2_031_COUNTRY_GEOM_EMPTY",
                STATE,
                MODULE_NAME,
                {"detail": "no_geometry_parts", "country_iso": iso},
            )
        output[iso] = _CountryGeometry(parts=parts, prepared=[prep(part) for part in parts])
    return output


def _country_contains(geom: _CountryGeometry, point: Point) -> bool:
    for part, prepared in zip(geom.parts, geom.prepared):
        if prepared.contains(point) or part.touches(point):
            return True
    return False


def _tree_query_indices(tree: STRtree, geom_index: dict[int, int], point: Point) -> list[int]:
    result = tree.query(point)
    if hasattr(result, "dtype"):
        return result.tolist()
    if result and isinstance(result[0], int):
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
    candidates: set[str] = set()
    for idx in indices:
        geom = geoms[idx]
        if geom.contains(point) or geom.touches(point):
            candidates.add(tzids[idx])
    return candidates


def _build_tz_index(
    tz_world_path: Path,
    logger,
) -> tuple[list, list[str], STRtree, dict[int, int], set[str], list[Optional[str]]]:
    if not _HAVE_GEOPANDAS:
        raise EngineFailure(
            "F4",
            "E3B_S2_030_GEOPANDAS_MISSING",
            STATE,
            MODULE_NAME,
            {"detail": "geopandas_unavailable", "path": str(tz_world_path)},
        )
    gdf = gpd.read_parquet(tz_world_path, columns=["tzid", "country_iso", "geometry"])
    if "tzid" not in gdf.columns:
        raise EngineFailure(
            "F4",
            "E3B_S2_032_TZ_WORLD_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": "tz_world_missing_tzid", "path": str(tz_world_path)},
        )
    geoms: list = []
    tzids: list[str] = []
    geom_countries: list[Optional[str]] = []
    if "country_iso" in gdf.columns:
        country_values = gdf["country_iso"]
    else:
        country_values = [None] * len(gdf)
    for tzid, country_iso, geom in zip(gdf["tzid"].astype(str), country_values, gdf.geometry):
        if geom is None:
            raise EngineFailure(
                "F4",
                "E3B_S2_032_TZ_WORLD_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": "tz_world_null_geom", "path": str(tz_world_path)},
            )
        country = None
        if country_iso is not None:
            value = str(country_iso).strip().upper()
            if value:
                country = value
        parts = _split_antimeridian_geometries(geom)
        for part in parts:
            geoms.append(part)
            tzids.append(tzid)
            geom_countries.append(country)
    if not geoms:
        raise EngineFailure(
            "F4",
            "E3B_S2_032_TZ_WORLD_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": "tz_world_empty_geoms", "path": str(tz_world_path)},
        )
    geom_index = {id(geom): idx for idx, geom in enumerate(geoms)}
    tree = STRtree(geoms)
    logger.info("S2: tz_world polygons loaded=%d", len(geoms))
    return geoms, tzids, tree, geom_index, set(tzids), geom_countries


def _apply_nudge(lat: float, lon: float, epsilon: float) -> tuple[float, float]:
    return _clamp_lat(lat + epsilon), _wrap_lon(lon + epsilon)


def _parse_cutoff_date(verified_at_utc: str, fallback_utc: str) -> date:
    source = verified_at_utc or fallback_utc
    if not source:
        raise ValueError("missing cutoff timestamp")
    if source.endswith("Z"):
        source = source[:-1] + "+00:00"
    return datetime.fromisoformat(source).date()


def _override_active(expiry: Optional[str], cutoff: date) -> bool:
    if expiry is None:
        return True
    expiry_str = str(expiry).strip()
    if not expiry_str:
        return True
    return date.fromisoformat(expiry_str) >= cutoff


def _derive_rng_key_counter(
    parameter_hash_hex: str,
    run_id_hex: str,
    seed: int,
    rng_stream_id: str,
    domain_master: str,
    domain_stream: str,
) -> tuple[int, int, int]:
    parameter_bytes = bytes.fromhex(parameter_hash_hex)
    run_id_bytes = bytes.fromhex(run_id_hex)
    if len(parameter_bytes) != 32:
        raise ValueError("parameter_hash must be 32 bytes.")
    if len(run_id_bytes) != 16:
        raise ValueError("run_id must be 16 bytes.")
    master_payload = uer_string(domain_master) + parameter_bytes + run_id_bytes + ser_u64(seed)
    master_digest = hashlib.sha256(master_payload).digest()
    stream_payload = uer_string(domain_stream) + uer_string(rng_stream_id)
    digest = hashlib.sha256(master_digest + stream_payload).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def _allocate_edges_decimal(weights: dict[str, Decimal], total_edges: int) -> dict[str, int]:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("country weights sum to zero")
    allocations: dict[str, int] = {}
    remainders: list[tuple[Decimal, str]] = []
    for country, weight in weights.items():
        raw = (weight * Decimal(total_edges)) / total_weight
        base = int(raw.to_integral_value(rounding=ROUND_FLOOR))
        allocations[country] = base
        remainders.append((raw - Decimal(base), country))
    remaining = total_edges - sum(allocations.values())
    if remaining > 0:
        remainders.sort(key=lambda item: (-item[0], item[1]))
        for idx in range(remaining):
            allocations[remainders[idx][1]] += 1
    return allocations


def _allocate_edges_int(weights: dict[int, int], total_edges: int) -> dict[int, int]:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("tile weights sum to zero")
    allocations: dict[int, int] = {}
    remainders: list[tuple[int, int]] = []
    for tile_id, weight in weights.items():
        scaled = total_edges * weight
        base = scaled // total_weight
        allocations[tile_id] = int(base)
        remainders.append((scaled - base * total_weight, tile_id))
    remaining = total_edges - sum(allocations.values())
    if remaining > 0:
        remainders.sort(key=lambda item: (-item[0], item[1]))
        for idx in range(remaining):
            allocations[remainders[idx][1]] += 1
    return allocations


def _edge_id_from_seq(merchant_id: int, edge_seq_index: int) -> str:
    if edge_seq_index < 0 or edge_seq_index > 0xFFFFFFFF:
        raise ValueError("edge_seq_index out of range for LE32")
    payload = (
        EDGE_ID_PREFIX.encode("utf-8")
        + bytes([0x1F])
        + str(merchant_id).encode("utf-8")
        + bytes([0x1F])
        + struct.pack("<I", edge_seq_index)
    )
    digest = hashlib.sha256(payload).digest()
    low = int.from_bytes(digest[-8:], "big", signed=False)
    return f"{low:016x}"


def _edge_digest(row: dict, fields: list[str]) -> str:
    payload = {field: row.get(field) for field in fields}
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()



def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _resolve_git_hash(repo_root: Path) -> str:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash).hex()
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip()).hex()
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip()).hex()
    except Exception as exc:  # pragma: no cover - fallback when git unavailable
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


def _rng_event_id(rng_stream_id: str, merchant_id: int, edge_seq_index: int) -> str:
    payload = f"{rng_stream_id}|{merchant_id}|{edge_seq_index}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_hex_list(digests: list[str]) -> str:
    h = hashlib.sha256()
    for digest in digests:
        h.update(bytes.fromhex(digest))
    return h.hexdigest()


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l1.seg_3B.s2_edge_catalogue.l2.runner")
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
    policy_version = ""
    policy_digest = ""
    rng_stream_id = ""
    route_policy_version = ""
    edge_catalogue_root: Optional[Path] = None
    index_path: Optional[Path] = None
    event_root: Optional[Path] = None
    trace_path: Optional[Path] = None
    audit_path: Optional[Path] = None
    run_report_path: Optional[Path] = None

    counts = {
        "merchants_total": 0,
        "virtual_merchants": 0,
        "edges_per_merchant": 0,
        "edges_total": 0,
        "rng_events_total": 0,
        "rng_draws_total": "0",
        "rng_blocks_total": 0,
        "jitter_resamples_total": 0,
        "jitter_exhausted_total": 0,
    }
    tz_counts = {"POLYGON": 0, "NUDGE": 0, "OVERRIDE": 0}
    attempts_hist: dict[int, int] = {}
    edges_by_country: dict[str, int] = {}
    event_handle = None
    trace_handle = None

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
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        reg_3b_path, registry_3b = load_artefact_registry(source, "3B")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
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
            dict_3b_path,
            reg_3b_path,
            ",".join(
                [
                    str(schema_3b_path),
                    str(schema_2b_path),
                    str(schema_2a_path),
                    str(schema_1b_path),
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
            "run_id": str(run_id),
        }

        logger.info(
            "S2: objective=construct CDN edge catalogue for virtual merchants; gated inputs "
            "(s0_gate_receipt_3B, sealed_inputs_3B, virtual_classification_3B, "
            "virtual_settlement_3B, cdn_country_weights, route_rng_policy_v1, "
            "tile_index/tile_weights/tile_bounds, world_countries, tz_world_2025a, "
            "tz_nudge, tz_overrides, hrsl_raster) -> outputs "
            "(edge_catalogue_3B, edge_catalogue_index_3B, rng_event_edge_jitter, "
            "rng_trace_log, rng_audit_log)"
        )

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_3b, "s0_gate_receipt_3B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        try:
            _validate_payload(schema_3b, schema_layer1, "validation/s0_gate_receipt_3B", receipt_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_receipt_invalid",
                {"detail": str(exc), "path": str(receipt_path)},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
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
                "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
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
                    "E3B_S2_002_UPSTREAM_GATE_NOT_PASS",
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
                "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
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
                    "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_not_object",
                    {"row": str(row)[:200]},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_schema_invalid",
                    {"error": errors[0].message},
                    manifest_fingerprint,
                )
            if row.get("manifest_fingerprint") != str(manifest_fingerprint):
                _abort(
                    "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
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
                    "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_missing",
                    {"row": row},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3B_S2_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        required_ids = [
            "cdn_country_weights",
            "route_rng_policy_v1",
            "tile_index",
            "tile_weights",
            "tile_bounds",
            "world_countries",
            "tz_world_2025a",
            "tz_nudge",
            "tz_overrides",
            "hrsl_raster",
        ]
        optional_ids = ["site_locations", "site_timezones"]

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3B_S2_003_REQUIRED_INPUT_NOT_SEALED",
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
                    "E3B_S2_004_SEALED_INPUT_MISMATCH",
                    "V-04",
                    "sealed_path_mismatch",
                    {"logical_id": logical_id, "expected": expected_path, "actual": sealed_path_value},
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3B_S2_003_REQUIRED_INPUT_NOT_SEALED",
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
                    "E3B_S2_005_SEALED_INPUT_DIGEST_MISMATCH",
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
        optional_assets: dict[str, tuple[dict, Path, str, str]] = {}
        for logical_id in optional_ids:
            if logical_id in sealed_by_id:
                optional_assets[logical_id] = _verify_sealed_asset(logical_id)

        timer.info("S2: verified required sealed inputs and digests")

        digest_map = receipt_payload.get("digests") or {}
        if digest_map.get("cdn_weights_digest") and digest_map.get("cdn_weights_digest") != verified_assets["cdn_country_weights"][3]:
            _abort(
                "E3B_S2_005_SEALED_INPUT_DIGEST_MISMATCH",
                "V-05",
                "cdn_weights_digest_mismatch",
                {
                    "logical_id": "cdn_country_weights",
                    "sealed_digest": verified_assets["cdn_country_weights"][3],
                    "receipt_digest": digest_map.get("cdn_weights_digest"),
                },
                manifest_fingerprint,
            )
        if digest_map.get("hrsl_digest") and digest_map.get("hrsl_digest") != verified_assets["hrsl_raster"][3]:
            _abort(
                "E3B_S2_005_SEALED_INPUT_DIGEST_MISMATCH",
                "V-05",
                "hrsl_digest_mismatch",
                {
                    "logical_id": "hrsl_raster",
                    "sealed_digest": verified_assets["hrsl_raster"][3],
                    "receipt_digest": digest_map.get("hrsl_digest"),
                },
                manifest_fingerprint,
            )

        current_phase = "s1_outputs"
        class_entry = find_dataset_entry(dictionary_3b, "virtual_classification_3B").entry
        settle_entry = find_dataset_entry(dictionary_3b, "virtual_settlement_3B").entry
        class_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        settle_path = _resolve_dataset_path(settle_entry, run_paths, config.external_roots, tokens)

        class_files = _resolve_parquet_files(class_path)
        settle_files = _resolve_parquet_files(settle_path)
        class_df = pl.read_parquet(class_files)
        settle_df = pl.read_parquet(settle_files)

        class_pack, class_table = _table_pack(schema_3b, "plan/virtual_classification_3B")
        settle_pack, settle_table = _table_pack(schema_3b, "plan/virtual_settlement_3B")
        _inline_external_refs(class_pack, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(settle_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(class_df.iter_rows(named=True), class_pack, class_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "classification_schema_invalid",
                {"error": str(exc), "path": str(class_path)},
                manifest_fingerprint,
            )
        try:
            validate_dataframe(settle_df.iter_rows(named=True), settle_pack, settle_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_schema_invalid",
                {"error": str(exc), "path": str(settle_path)},
                manifest_fingerprint,
            )

        class_df = class_df.with_columns(
            pl.col("seed").cast(pl.UInt64),
            pl.col("manifest_fingerprint").cast(pl.Utf8),
            pl.col("merchant_id").cast(pl.UInt64),
        )
        settle_df = settle_df.with_columns(
            pl.col("seed").cast(pl.UInt64),
            pl.col("manifest_fingerprint").cast(pl.Utf8),
            pl.col("merchant_id").cast(pl.UInt64),
        )

        if class_df.get_column("merchant_id").is_null().any():
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "classification_merchant_missing",
                {"path": str(class_path)},
                manifest_fingerprint,
            )
        if settle_df.get_column("merchant_id").is_null().any():
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_merchant_missing",
                {"path": str(settle_path)},
                manifest_fingerprint,
            )
        if class_df.get_column("merchant_id").n_unique() != class_df.height:
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "classification_merchant_duplicate",
                {"path": str(class_path)},
                manifest_fingerprint,
            )
        if settle_df.get_column("merchant_id").n_unique() != settle_df.height:
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_merchant_duplicate",
                {"path": str(settle_path)},
                manifest_fingerprint,
            )

        class_seed = class_df.get_column("seed").unique()
        if class_seed.len() != 1 or int(class_seed[0]) != int(seed):
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "classification_seed_mismatch",
                {"expected": int(seed), "observed": class_seed.to_list()},
                manifest_fingerprint,
            )
        class_manifest = class_df.get_column("manifest_fingerprint").unique()
        if class_manifest.len() != 1 or str(class_manifest[0]) != str(manifest_fingerprint):
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "classification_manifest_mismatch",
                {"expected": str(manifest_fingerprint), "observed": class_manifest.to_list()},
                manifest_fingerprint,
            )

        settle_seed = settle_df.get_column("seed").unique()
        if settle_seed.len() != 1 or int(settle_seed[0]) != int(seed):
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_seed_mismatch",
                {"expected": int(seed), "observed": settle_seed.to_list()},
                manifest_fingerprint,
            )
        settle_manifest = settle_df.get_column("manifest_fingerprint").unique()
        if settle_manifest.len() != 1 or str(settle_manifest[0]) != str(manifest_fingerprint):
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_manifest_mismatch",
                {"expected": str(manifest_fingerprint), "observed": settle_manifest.to_list()},
                manifest_fingerprint,
            )

        total_merchants = int(class_df.height)
        counts["merchants_total"] = total_merchants

        virtual_ids = (
            class_df.filter(pl.col("is_virtual") == True)
            .select("merchant_id")
            .sort("merchant_id")
        )
        virtual_merchants = int(virtual_ids.height)
        counts["virtual_merchants"] = virtual_merchants
        if virtual_merchants == 0:
            logger.info("S2: no virtual merchants; edge catalogue will be empty.")

        settlement_ids = set(settle_df.get_column("merchant_id").to_list())
        missing_settlement = [
            int(mid) for mid in virtual_ids.get_column("merchant_id").to_list() if int(mid) not in settlement_ids
        ]
        if missing_settlement:
            _abort(
                "E3B_S2_007_S1_DOMAIN_MISMATCH",
                "V-06",
                "missing_settlement_rows",
                {"missing": missing_settlement[:10], "missing_count": len(missing_settlement)},
                manifest_fingerprint,
            )

        if settle_df.get_column("lat_deg").is_null().any() or settle_df.get_column("lon_deg").is_null().any():
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_coords_missing",
                {"path": str(settle_path)},
                manifest_fingerprint,
            )
        if settle_df.get_column("tzid_settlement").is_null().any():
            _abort(
                "E3B_S2_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_tz_missing",
                {"path": str(settle_path)},
                manifest_fingerprint,
            )

        current_phase = "cdn_policy"
        policy_path = verified_assets["cdn_country_weights"][1]
        policy_payload = _load_yaml(policy_path)
        policy_schema = _schema_for_payload(schema_3b, schema_layer1, "policy/cdn_country_weights_v1")
        errors = list(Draft202012Validator(policy_schema).iter_errors(policy_payload))
        if errors:
            _abort(
                "E3B_S2_008_POLICY_SCHEMA_INVALID",
                "V-07",
                "cdn_policy_schema_invalid",
                {"error": errors[0].message, "path": str(policy_path)},
                manifest_fingerprint,
            )
        policy_version = str(policy_payload.get("version") or "").strip()
        if _is_placeholder(policy_version):
            _abort(
                "E3B_S2_008_POLICY_SCHEMA_INVALID",
                "V-07",
                "cdn_policy_version_missing",
                {"path": str(policy_path)},
                manifest_fingerprint,
            )
        policy_digest = verified_assets["cdn_country_weights"][3]

        edge_scale = int(policy_payload.get("edge_scale") or 0)
        if edge_scale < 1:
            _abort(
                "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                "V-07",
                "edge_scale_invalid",
                {"edge_scale": edge_scale},
                manifest_fingerprint,
            )
        counts["edges_per_merchant"] = edge_scale

        getcontext().prec = 28
        country_weights: dict[str, Decimal] = {}
        countries = policy_payload.get("countries") or []
        if not isinstance(countries, list) or not countries:
            _abort(
                "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                "V-07",
                "country_weights_missing",
                {"path": str(policy_path)},
                manifest_fingerprint,
            )
        for entry in countries:
            if not isinstance(entry, dict):
                _abort(
                    "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                    "V-07",
                    "country_weight_not_object",
                    {"entry": str(entry)[:200]},
                    manifest_fingerprint,
                )
            country_iso = str(entry.get("country_iso") or "").upper()
            weight = entry.get("weight")
            if not country_iso or weight is None:
                _abort(
                    "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                    "V-07",
                    "country_weight_missing",
                    {"entry": entry},
                    manifest_fingerprint,
                )
            if country_iso in country_weights:
                _abort(
                    "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                    "V-07",
                    "country_weight_duplicate",
                    {"country_iso": country_iso},
                    manifest_fingerprint,
                )
            weight_dec = Decimal(str(weight))
            if weight_dec <= 0:
                _abort(
                    "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                    "V-07",
                    "country_weight_nonpositive",
                    {"country_iso": country_iso, "weight": str(weight)},
                    manifest_fingerprint,
                )
            country_weights[country_iso] = weight_dec

        edges_per_country = _allocate_edges_decimal(country_weights, edge_scale)
        if sum(edges_per_country.values()) != edge_scale:
            _abort(
                "E3B_S2_BUDGET_COUNTRY_WEIGHTS_INVALID",
                "V-07",
                "edge_scale_mismatch",
                {"edge_scale": edge_scale, "allocated": sum(edges_per_country.values())},
                manifest_fingerprint,
            )
        countries_sorted = sorted(edges_per_country)
        counts["edges_total"] = edge_scale * counts["virtual_merchants"]

        current_phase = "tile_surfaces"
        tile_index_root = verified_assets["tile_index"][1]
        tile_weights_root = verified_assets["tile_weights"][1]
        tile_bounds_root = verified_assets["tile_bounds"][1]
        tile_index_files = _resolve_parquet_files(tile_index_root)
        tile_weights_files = _resolve_parquet_files(tile_weights_root)
        tile_bounds_files = _resolve_parquet_files(tile_bounds_root)

        tile_weights_by_country, tile_weights_unresolved = _group_paths_by_country(
            tile_weights_files,
            "part_suffix",
        )
        tile_index_by_country, tile_index_unresolved = _group_paths_by_country(
            tile_index_files,
            "country_partition",
        )
        tile_bounds_by_country_files, tile_bounds_unresolved = _group_paths_by_country(
            tile_bounds_files,
            "country_partition",
        )

        unresolved_total = len(tile_weights_unresolved) + len(tile_index_unresolved) + len(tile_bounds_unresolved)
        if unresolved_total:
            _abort(
                "E3B_S2_TILE_SURFACE_INVALID",
                "V-08",
                "tile_surface_partition_unresolved",
                {
                    "weights_unresolved": [str(path) for path in tile_weights_unresolved[:5]],
                    "index_unresolved": [str(path) for path in tile_index_unresolved[:5]],
                    "bounds_unresolved": [str(path) for path in tile_bounds_unresolved[:5]],
                    "weights_unresolved_count": len(tile_weights_unresolved),
                    "index_unresolved_count": len(tile_index_unresolved),
                    "bounds_unresolved_count": len(tile_bounds_unresolved),
                },
                manifest_fingerprint,
            )

        precheck_payload = {
            "tile_weights_countries": len(tile_weights_by_country),
            "tile_index_countries": len(tile_index_by_country),
            "tile_bounds_countries": len(tile_bounds_by_country_files),
            "required_countries": len(countries_sorted),
            "sample_missing_weights": [iso for iso in countries_sorted if iso not in tile_weights_by_country][:10],
            "sample_missing_index": [iso for iso in countries_sorted if iso not in tile_index_by_country][:10],
            "sample_missing_bounds": [iso for iso in countries_sorted if iso not in tile_bounds_by_country_files][:10],
        }
        precheck_root = (
            run_paths.run_root
            / "reports"
            / "layer1"
            / SEGMENT
            / f"state={STATE}"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
        )
        _write_json(precheck_root / "tile_surface_partition_precheck.json", precheck_payload)
        logger.info(
            "S2: tile partition precheck written (weights=%d, index=%d, bounds=%d, required=%d)",
            precheck_payload["tile_weights_countries"],
            precheck_payload["tile_index_countries"],
            precheck_payload["tile_bounds_countries"],
            precheck_payload["required_countries"],
        )

        tile_allocations: dict[str, list[tuple[int, int]]] = {}
        tile_bounds_by_country: dict[str, dict[int, tuple[float, float, float, float, float, float]]] = {}
        cache_key = _tile_surface_cache_key(
            verified_assets["tile_index"][3],
            verified_assets["tile_weights"][3],
            verified_assets["tile_bounds"][3],
            countries_sorted,
            edge_scale,
        )
        cache_path = precheck_root / f"tile_surface_cache_{cache_key}.json"
        cache_hit = False

        if cache_path.exists():
            try:
                cache_payload = _load_json(cache_path)
                if (
                    str(cache_payload.get("cache_key") or "") == cache_key
                    and int(cache_payload.get("edge_scale") or -1) == edge_scale
                    and list(cache_payload.get("countries_sorted") or []) == countries_sorted
                    and str(cache_payload.get("tile_index_digest") or "") == verified_assets["tile_index"][3]
                    and str(cache_payload.get("tile_weights_digest") or "") == verified_assets["tile_weights"][3]
                    and str(cache_payload.get("tile_bounds_digest") or "") == verified_assets["tile_bounds"][3]
                ):
                    alloc_payload = cache_payload.get("tile_allocations") or {}
                    bounds_payload = cache_payload.get("tile_bounds_by_country") or {}
                    for country_iso in countries_sorted:
                        alloc_rows = alloc_payload.get(country_iso) or []
                        tile_allocations[country_iso] = [
                            (int(row[0]), int(row[1]))
                            for row in alloc_rows
                            if isinstance(row, list) and len(row) == 2 and int(row[1]) > 0
                        ]
                        bounds_rows = bounds_payload.get(country_iso) or {}
                        decoded_bounds: dict[int, tuple[float, float, float, float, float, float]] = {}
                        for tile_id_text, values in bounds_rows.items():
                            if not isinstance(values, list) or len(values) != 6:
                                continue
                            decoded_bounds[int(tile_id_text)] = (
                                float(values[0]),
                                float(values[1]),
                                float(values[2]),
                                float(values[3]),
                                float(values[4]),
                                float(values[5]),
                            )
                        tile_bounds_by_country[country_iso] = decoded_bounds
                    cache_hit = True
                    timer.info(
                        f"S2: tile allocations loaded from cache (countries={len(countries_sorted)}, "
                        f"edge_scale={edge_scale})"
                    )
                else:
                    logger.info("S2: tile surface cache key mismatch; recomputing allocations")
            except Exception as exc:  # noqa: BLE001
                logger.warning("S2: tile surface cache load failed; recomputing (%s)", exc)

        if not cache_hit:
            for country_iso in countries_sorted:
                country_weight_files = tile_weights_by_country.get(country_iso, [])
                country_index_files = tile_index_by_country.get(country_iso, [])
                country_bounds_files = tile_bounds_by_country_files.get(country_iso, [])

                if not country_weight_files:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_weights_missing",
                        {"country_iso": country_iso, "path": str(tile_weights_root)},
                        manifest_fingerprint,
                    )
                weights_df = (
                    pl.scan_parquet(country_weight_files)
                    .select(["tile_id", "weight_fp", "dp"])
                    .collect()
                )
                if weights_df.is_empty():
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_weights_missing",
                        {"country_iso": country_iso, "path": str(tile_weights_root)},
                        manifest_fingerprint,
                    )
                dp_values = weights_df.get_column("dp").unique()
                if dp_values.len() != 1:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_weights_dp_mismatch",
                        {"country_iso": country_iso, "dp_values": dp_values.to_list()},
                        manifest_fingerprint,
                    )
                weights_map: dict[int, int] = {}
                for tile_id, weight_fp in zip(
                    weights_df.get_column("tile_id").to_list(),
                    weights_df.get_column("weight_fp").to_list(),
                ):
                    weights_map[int(tile_id)] = int(weight_fp)
                if sum(weights_map.values()) <= 0:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_weights_zero_sum",
                        {"country_iso": country_iso},
                        manifest_fingerprint,
                    )

                if not country_index_files:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_index_missing",
                        {"country_iso": country_iso, "path": str(tile_index_root)},
                        manifest_fingerprint,
                    )
                index_df = (
                    pl.scan_parquet(country_index_files)
                    .select(["tile_id"])
                    .collect()
                )
                if index_df.is_empty():
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_index_missing",
                        {"country_iso": country_iso, "path": str(tile_index_root)},
                        manifest_fingerprint,
                    )
                index_ids = set(int(value) for value in index_df.get_column("tile_id").to_list())
                missing_index = [tile_id for tile_id in weights_map if tile_id not in index_ids]
                if missing_index:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_id_not_in_index",
                        {"country_iso": country_iso, "missing": missing_index[:10]},
                        manifest_fingerprint,
                    )

                tile_alloc = _allocate_edges_int(weights_map, edges_per_country[country_iso])
                allocations = [
                    (tile_id, count)
                    for tile_id, count in sorted(tile_alloc.items())
                    if count > 0
                ]
                needed_bounds = {tile_id for tile_id, count in allocations if count > 0}

                if not country_bounds_files:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_bounds_missing",
                        {"country_iso": country_iso, "path": str(tile_bounds_root)},
                        manifest_fingerprint,
                    )
                bounds_df = (
                    pl.scan_parquet(country_bounds_files)
                    .select(
                        [
                            "tile_id",
                            "min_lon_deg",
                            "max_lon_deg",
                            "min_lat_deg",
                            "max_lat_deg",
                            "centroid_lon_deg",
                            "centroid_lat_deg",
                        ]
                    )
                    .collect()
                )
                if bounds_df.is_empty():
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_bounds_missing",
                        {"country_iso": country_iso, "path": str(tile_bounds_root)},
                        manifest_fingerprint,
                    )
                bounds_all: dict[int, tuple[float, float, float, float, float, float]] = {}
                for row in bounds_df.iter_rows(named=True):
                    tile_id = int(row["tile_id"])
                    bounds_all[tile_id] = (
                        float(row["min_lon_deg"]),
                        float(row["max_lon_deg"]),
                        float(row["min_lat_deg"]),
                        float(row["max_lat_deg"]),
                        float(row["centroid_lon_deg"]),
                        float(row["centroid_lat_deg"]),
                    )
                bounds_ids = set(bounds_all)
                missing_bounds = [tile_id for tile_id in weights_map if tile_id not in bounds_ids]
                if missing_bounds:
                    _abort(
                        "E3B_S2_TILE_SURFACE_INVALID",
                        "V-08",
                        "tile_bounds_missing_ids",
                        {"country_iso": country_iso, "missing": missing_bounds[:10]},
                        manifest_fingerprint,
                    )
                bounds_map: dict[int, tuple[float, float, float, float, float, float]] = {}
                if needed_bounds:
                    for tile_id in sorted(needed_bounds):
                        bounds_map[tile_id] = bounds_all[tile_id]
                tile_allocations[country_iso] = allocations
                tile_bounds_by_country[country_iso] = bounds_map

            cache_payload = {
                "cache_key": cache_key,
                "edge_scale": int(edge_scale),
                "countries_sorted": countries_sorted,
                "tile_index_digest": verified_assets["tile_index"][3],
                "tile_weights_digest": verified_assets["tile_weights"][3],
                "tile_bounds_digest": verified_assets["tile_bounds"][3],
                "tile_allocations": {
                    iso: [[int(tile_id), int(count)] for tile_id, count in tile_allocations.get(iso, [])]
                    for iso in countries_sorted
                },
                "tile_bounds_by_country": {
                    iso: {
                        str(tile_id): [
                            float(values[0]),
                            float(values[1]),
                            float(values[2]),
                            float(values[3]),
                            float(values[4]),
                            float(values[5]),
                        ]
                        for tile_id, values in tile_bounds_by_country.get(iso, {}).items()
                    }
                    for iso in countries_sorted
                },
            }
            _write_json_compact(cache_path, cache_payload)
            logger.info("S2: tile surface cache written path=%s", cache_path)

        timer.info(
            f"S2: tile allocations prepared (countries={len(countries_sorted)}, "
            f"edge_scale={edge_scale})"
        )

        current_phase = "world_geometry"
        world_path = verified_assets["world_countries"][1]
        world_crs = _extract_geo_crs(world_path)
        if not _is_wgs84(world_crs):
            _abort(
                "E3B_S2_TILE_SURFACE_INVALID",
                "V-08",
                "world_countries_crs_invalid",
                {"path": str(world_path), "crs": world_crs},
                manifest_fingerprint,
            )
        world_geometry = _load_world_countries(world_path)
        for country_iso in countries_sorted:
            if country_iso not in world_geometry:
                _abort(
                    "E3B_S2_TILE_SURFACE_INVALID",
                    "V-08",
                    "world_country_missing",
                    {"country_iso": country_iso},
                    manifest_fingerprint,
                )

        current_phase = "tz_assets"
        tz_world_path = verified_assets["tz_world_2025a"][1]
        tz_crs = _extract_geo_crs(tz_world_path)
        if not _is_wgs84(tz_crs):
            _abort(
                "E3B_S2_TZ_ASSET_INVALID",
                "V-09",
                "tz_world_crs_invalid",
                {"path": str(tz_world_path), "crs": tz_crs},
                manifest_fingerprint,
            )
        (
            tz_geoms,
            tzids,
            tz_tree,
            tz_geom_index,
            tzid_set,
            tz_geom_countries,
        ) = _build_tz_index(tz_world_path, logger)

        tz_nudge_path = verified_assets["tz_nudge"][1]
        tz_nudge_payload = _load_yaml(tz_nudge_path)
        tz_nudge_schema = _schema_for_payload(schema_2a, schema_layer1, "policy/tz_nudge_v1")
        errors = list(Draft202012Validator(tz_nudge_schema).iter_errors(tz_nudge_payload))
        if errors:
            _abort(
                "E3B_S2_TZ_ASSET_INVALID",
                "V-09",
                "tz_nudge_invalid",
                {"error": errors[0].message, "path": str(tz_nudge_path)},
                manifest_fingerprint,
            )
        epsilon = float(tz_nudge_payload.get("epsilon_degrees") or 0.0)
        if epsilon <= 0.0:
            _abort(
                "E3B_S2_TZ_ASSET_INVALID",
                "V-09",
                "tz_nudge_epsilon_invalid",
                {"epsilon_degrees": epsilon},
                manifest_fingerprint,
            )

        tz_overrides_path = verified_assets["tz_overrides"][1]
        tz_overrides_payload = _load_yaml(tz_overrides_path)
        tz_overrides_schema = _schema_for_payload(schema_2a, schema_layer1, "policy/tz_overrides_v1")
        errors = list(Draft202012Validator(tz_overrides_schema).iter_errors(tz_overrides_payload))
        if errors:
            _abort(
                "E3B_S2_TZ_ASSET_INVALID",
                "V-09",
                "tz_overrides_invalid",
                {"error": errors[0].message, "path": str(tz_overrides_path)},
                manifest_fingerprint,
            )
        overrides_country: dict[str, str] = {}
        ignored_override_scopes: dict[str, int] = {}
        cutoff = _parse_cutoff_date(str(receipt_payload.get("verified_at_utc") or ""), started_utc)
        if isinstance(tz_overrides_payload, list):
            for entry in tz_overrides_payload:
                if not isinstance(entry, dict):
                    continue
                scope = str(entry.get("scope") or "")
                target = str(entry.get("target") or "")
                tzid = str(entry.get("tzid") or "")
                expiry = entry.get("expiry_yyyy_mm_dd")
                if not _override_active(expiry, cutoff):
                    continue
                if scope != "country":
                    ignored_override_scopes[scope] = ignored_override_scopes.get(scope, 0) + 1
                    continue
                if not target or not tzid:
                    continue
                country_iso = target.strip().upper()
                if country_iso in overrides_country:
                    _abort(
                        "E3B_S2_TZ_ASSET_INVALID",
                        "V-09",
                        "tz_override_duplicate",
                        {"country_iso": country_iso},
                        manifest_fingerprint,
                    )
                overrides_country[country_iso] = tzid
        if ignored_override_scopes:
            logger.warning(
                "S2: tz_overrides contains unsupported scopes for S2 (ignored=%s)",
                ignored_override_scopes,
            )

        for country_iso, tzid in overrides_country.items():
            if tzid not in tzid_set:
                _abort(
                    "E3B_S2_TZ_ASSET_INVALID",
                    "V-09",
                    "tz_override_unknown",
                    {"country_iso": country_iso, "tzid": tzid},
                    manifest_fingerprint,
                )

        current_phase = "rng_policy"
        rng_policy_path = verified_assets["route_rng_policy_v1"][1]
        rng_policy = _load_json(rng_policy_path)
        rng_policy_schema = _schema_for_payload(schema_2b, schema_layer1, "policy/route_rng_policy_v1")
        errors = list(Draft202012Validator(rng_policy_schema).iter_errors(rng_policy))
        if errors:
            _abort(
                "E3B_S2_RNG_POLICY_VIOLATION",
                "V-10",
                "rng_policy_invalid",
                {"error": errors[0].message, "path": str(rng_policy_path)},
                manifest_fingerprint,
            )
        route_policy_version = str(rng_policy.get("policy_version") or "")
        stream_cfg = (rng_policy.get("streams") or {}).get("virtual_edge_catalogue") or {}
        rng_stream_id = str(stream_cfg.get("rng_stream_id") or "")
        if not rng_stream_id:
            _abort(
                "E3B_S2_RNG_POLICY_VIOLATION",
                "V-10",
                "rng_stream_id_missing",
                {"path": str(rng_policy_path)},
                manifest_fingerprint,
            )
        draws_per_edge = (stream_cfg.get("draws_per_unit") or {}).get("draws_per_edge")
        if int(draws_per_edge or 0) != 2:
            _abort(
                "E3B_S2_RNG_POLICY_VIOLATION",
                "V-10",
                "draws_per_edge_invalid",
                {"draws_per_edge": draws_per_edge},
                manifest_fingerprint,
            )
        event_family = (stream_cfg.get("event_families") or {}).get("edge_jitter") or {}
        if str(event_family.get("draws") or "") != "2":
            _abort(
                "E3B_S2_RNG_POLICY_VIOLATION",
                "V-10",
                "edge_jitter_draws_invalid",
                {"draws": event_family.get("draws")},
                manifest_fingerprint,
            )

        rng_key, counter_hi, counter_lo = _derive_rng_key_counter(
            str(parameter_hash),
            str(run_id),
            int(seed),
            rng_stream_id,
            RNG_DOMAIN_MASTER,
            RNG_DOMAIN_STREAM,
        )

        current_phase = "rng_logs"
        event_entry = find_dataset_entry(dictionary_3b, "rng_event_edge_jitter").entry
        trace_entry = find_dataset_entry(dictionary_3b, "rng_trace_log").entry
        audit_entry = find_dataset_entry(dictionary_3b, "rng_audit_log").entry

        event_path = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens)
        event_root = _event_root_from_path(event_path)
        event_paths = _iter_jsonl_paths(event_root)
        event_enabled = not event_paths
        if not event_enabled:
            logger.info("S2: rng_event_edge_jitter already exists; skipping event emission")

        trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
        if trace_path.exists():
            trace_mode = (
                "skip"
                if _trace_has_substream(trace_path, RNG_MODULE, SUBSTREAM_JITTER)
                else "append"
            )
        else:
            trace_mode = "create"
        if trace_mode == "create":
            trace_handle = (run_paths.tmp_root / f"s2_trace_{uuid.uuid4().hex}.jsonl").open(
                "w", encoding="utf-8"
            )
            trace_acc = RngTraceAccumulator()
            trace_tmp_path = Path(trace_handle.name)
        elif trace_mode == "append":
            trace_handle = trace_path.open("a", encoding="utf-8")
            trace_acc = RngTraceAccumulator()
            trace_tmp_path = None
        else:
            trace_handle = None
            trace_acc = None
            trace_tmp_path = None
        logger.info("S2: rng_trace_log mode=%s", trace_mode)

        audit_path = _resolve_dataset_path(audit_entry, run_paths, config.external_roots, tokens)
        audit_entry_payload = {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": str(run_id),
            "seed": int(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "algorithm": "philox2x64-10",
            "build_commit": _resolve_git_hash(config.repo_root),
            "code_digest": None,
            "hostname": platform.node(),
            "platform": platform.platform(),
            "notes": None,
        }
        audit_entry_payload = {key: value for key, value in audit_entry_payload.items() if value is not None}
        _validate_payload(schema_layer1, schema_layer1, "rng/core/rng_audit_log/record", audit_entry_payload)

        current_phase = "outputs_prepare"
        tmp_root = run_paths.tmp_root / f"s2_edge_catalogue_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)
        edge_tmp = tmp_root / "edge_catalogue_3B"
        edge_tmp.mkdir(parents=True, exist_ok=True)
        event_tmp_dir = tmp_root / "rng_event_edge_jitter"
        event_tmp_dir.mkdir(parents=True, exist_ok=True)
        event_tmp_path = _event_file_from_root(event_tmp_dir)

        event_handle = event_tmp_path.open("w", encoding="utf-8") if event_enabled else None
        trace_inline = event_enabled and trace_handle is not None and trace_acc is not None

        edge_schema = {
            "seed": pl.UInt64,
            "manifest_fingerprint": pl.Utf8,
            "merchant_id": pl.UInt64,
            "edge_id": pl.Utf8,
            "edge_seq_index": pl.Int64,
            "country_iso": pl.Utf8,
            "lat_deg": pl.Float64,
            "lon_deg": pl.Float64,
            "tzid_operational": pl.Utf8,
            "tz_source": pl.Utf8,
            "edge_weight": pl.Float64,
            "hrsl_tile_id": pl.Utf8,
            "spatial_surface_id": pl.Utf8,
            "cdn_policy_id": pl.Utf8,
            "cdn_policy_version": pl.Utf8,
            "rng_stream_id": pl.Utf8,
            "rng_event_id": pl.Utf8,
            "sampling_rank": pl.Int64,
            "edge_digest": pl.Utf8,
        }
        index_schema = {
            "scope": pl.Utf8,
            "seed": pl.UInt64,
            "manifest_fingerprint": pl.Utf8,
            "merchant_id": pl.UInt64,
            "edge_count_total": pl.Int64,
            "edge_digest": pl.Utf8,
            "edge_catalogue_path": pl.Utf8,
            "edge_catalogue_size_bytes": pl.Int64,
            "country_mix_summary": pl.Utf8,
            "edge_count_total_all_merchants": pl.Int64,
            "edge_catalogue_digest_global": pl.Utf8,
            "notes": pl.Utf8,
        }
        edge_digest_fields = [
            "seed",
            "manifest_fingerprint",
            "merchant_id",
            "edge_id",
            "edge_seq_index",
            "country_iso",
            "lat_deg",
            "lon_deg",
            "tzid_operational",
            "tz_source",
            "edge_weight",
            "hrsl_tile_id",
            "spatial_surface_id",
            "cdn_policy_id",
            "cdn_policy_version",
            "rng_stream_id",
            "rng_event_id",
            "sampling_rank",
        ]

        edge_pack, edge_table = _table_pack(schema_3b, "plan/edge_catalogue_3B")
        index_pack, index_table = _table_pack(schema_3b, "plan/edge_catalogue_index_3B")
        _inline_external_refs(edge_pack, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(index_pack, schema_layer1, "schemas.layer1.yaml#")

        def _flush_edges(rows: list[dict], part_idx: int) -> int:
            if not rows:
                return part_idx
            edge_df = pl.DataFrame(rows, schema=edge_schema)
            try:
                validate_dataframe(edge_df.iter_rows(named=True), edge_pack, edge_table)
            except SchemaValidationError as exc:
                _abort(
                    "E3B_S2_EDGE_CATALOGUE_SCHEMA_VIOLATION",
                    "V-12",
                    "edge_catalogue_schema_invalid",
                    {"error": str(exc)},
                    manifest_fingerprint,
                )
            part_path = edge_tmp / f"part-{part_idx:05d}.parquet"
            edge_df.write_parquet(part_path, compression="zstd")
            rows.clear()
            return part_idx + 1

        def _resolve_tz(point: Point, country_iso: str) -> tuple[str, str]:
            candidates = _candidate_tzids(tz_tree, tz_geoms, tzids, tz_geom_index, point)
            if len(candidates) == 1:
                return next(iter(candidates)), "POLYGON"
            nudged_lat, nudged_lon = _apply_nudge(point.y, point.x, epsilon)
            nudge_point = Point(nudged_lon, nudged_lat)
            candidates = _candidate_tzids(tz_tree, tz_geoms, tzids, tz_geom_index, nudge_point)
            if len(candidates) == 1:
                return next(iter(candidates)), "NUDGE"
            override = overrides_country.get(country_iso)
            if override:
                return override, "OVERRIDE"
            _abort(
                "E3B_S2_TZ_RESOLUTION_FAILED",
                "V-11",
                "tz_resolution_failed",
                {"country_iso": country_iso, "point": [point.y, point.x]},
                manifest_fingerprint,
            )
            raise RuntimeError("tz_resolution_failed")

        virtual_merchants = [int(value) for value in virtual_ids.get_column("merchant_id").to_list()]
        edges_total = edge_scale * len(virtual_merchants)
        counts["edges_total"] = edges_total

        progress = _ProgressTracker(edges_total or None, logger, "S2: edge jitter/tz progress")
        logger.info(
            "S2: starting edge placement loop (virtual_merchants=%d, edges_per_merchant=%d, edges_total=%d)",
            len(virtual_merchants),
            edge_scale,
            edges_total,
        )

        edge_rows: list[dict] = []
        edge_part_idx = 0
        index_rows: list[dict] = []
        per_merchant_digests: list[tuple[int, str]] = []
        rng_events_emitted = 0
        resamples_total = 0
        jitter_exhausted = 0

        for merchant_id in virtual_merchants:
            edges_for_merchant: list[dict] = []
            edge_seq_index = 0
            for country_iso in countries_sorted:
                edges_country = edges_per_country[country_iso]
                if edges_country <= 0:
                    continue
                bounds_map = tile_bounds_by_country[country_iso]
                allocations = tile_allocations[country_iso]
                country_geom = world_geometry[country_iso]
                edges_by_country[country_iso] = edges_by_country.get(country_iso, 0) + edges_country
                for tile_id, tile_count in allocations:
                    bounds = bounds_map.get(tile_id)
                    if bounds is None:
                        _abort(
                            "E3B_S2_TILE_SURFACE_INVALID",
                            "V-08",
                            "tile_bounds_missing",
                            {"country_iso": country_iso, "tile_id": tile_id},
                            manifest_fingerprint,
                        )
                    min_lon, max_lon, min_lat, max_lat, _, _ = bounds
                    for _ in range(tile_count):
                        attempts = 0
                        accepted = False
                        candidate_lon = None
                        candidate_lat = None
                        point = None
                        while attempts < MAX_ATTEMPTS:
                            attempts += 1
                            before_hi = counter_hi
                            before_lo = counter_lo
                            out0, out1 = philox2x64_10(counter_hi, counter_lo, rng_key)
                            counter_hi, counter_lo = add_u128(counter_hi, counter_lo, 1)
                            u_lon = u01(out0)
                            u_lat = u01(out1)
                            span_lon = max_lon - min_lon
                            if span_lon < 0.0:
                                span_lon += 360.0
                            lon = min_lon + u_lon * span_lon
                            lon = _normalize_lon(lon)
                            lat = min_lat + u_lat * (max_lat - min_lat)
                            candidate_lon = float(lon)
                            candidate_lat = float(lat)
                            if not (min_lat - 1e-9 <= lat <= max_lat + 1e-9):
                                _abort(
                                    "E3B_S2_EDGE_OUTSIDE_COUNTRY",
                                    "V-10",
                                    "lat_outside_tile",
                                    {"tile_id": tile_id, "lat": lat, "bounds": [min_lat, max_lat]},
                                    manifest_fingerprint,
                                )
                            if span_lon <= 180.0 and not (min_lon - 1e-9 <= lon <= max_lon + 1e-9):
                                _abort(
                                    "E3B_S2_EDGE_OUTSIDE_COUNTRY",
                                    "V-10",
                                    "lon_outside_tile",
                                    {"tile_id": tile_id, "lon": lon, "bounds": [min_lon, max_lon]},
                                    manifest_fingerprint,
                                )
                            point = Point(lon, lat)
                            accepted = _country_contains(country_geom, point)
                            event_payload = {
                                "ts_utc": utc_now_rfc3339_micro(),
                                "run_id": str(run_id),
                                "seed": int(seed),
                                "parameter_hash": str(parameter_hash),
                                "manifest_fingerprint": str(manifest_fingerprint),
                                "module": RNG_MODULE,
                                "substream_label": SUBSTREAM_JITTER,
                                "rng_counter_before_lo": int(before_lo),
                                "rng_counter_before_hi": int(before_hi),
                                "rng_counter_after_lo": int(counter_lo),
                                "rng_counter_after_hi": int(counter_hi),
                                "draws": "2",
                                "blocks": 1,
                                "merchant_id": merchant_id,
                                "country_iso": country_iso,
                                "tile_id": str(tile_id),
                                "edge_seq_index": edge_seq_index,
                                "attempt": attempts,
                                "accepted": accepted,
                                "u_lon": float(u_lon),
                                "u_lat": float(u_lat),
                                "candidate_lon_deg": candidate_lon,
                                "candidate_lat_deg": candidate_lat,
                                "tz_resolution": None,
                            }
                            if event_enabled and event_handle is not None:
                                event_handle.write(json.dumps(event_payload, ensure_ascii=True, sort_keys=True))
                                event_handle.write("\n")
                            if trace_inline and trace_acc is not None and trace_handle is not None:
                                trace_row = trace_acc.append_event(event_payload)
                                trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
                                trace_handle.write("\n")
                            rng_events_emitted += 1
                            if accepted:
                                break
                        if not accepted or point is None:
                            jitter_exhausted += 1
                            _abort(
                                "E3B_S2_JITTER_RESAMPLE_EXHAUSTED",
                                "V-10",
                                "jitter_resample_exhausted",
                                {"merchant_id": merchant_id, "tile_id": tile_id, "attempts": attempts},
                                manifest_fingerprint,
                            )
                        tzid_operational, tz_source = _resolve_tz(point, country_iso)
                        tz_counts[tz_source] = tz_counts.get(tz_source, 0) + 1
                        edge_weight = 1.0 / edge_scale if edge_scale > 0 else 0.0
                        edge_id = _edge_id_from_seq(merchant_id, edge_seq_index)
                        rng_event_ref = _rng_event_id(rng_stream_id, merchant_id, edge_seq_index)
                        edge_row = {
                            "seed": int(seed),
                            "manifest_fingerprint": str(manifest_fingerprint),
                            "merchant_id": merchant_id,
                            "edge_id": edge_id,
                            "edge_seq_index": edge_seq_index,
                            "country_iso": country_iso,
                            "lat_deg": candidate_lat,
                            "lon_deg": candidate_lon,
                            "tzid_operational": tzid_operational,
                            "tz_source": tz_source,
                            "edge_weight": edge_weight,
                            "hrsl_tile_id": str(tile_id),
                            "spatial_surface_id": "tile_bounds",
                            "cdn_policy_id": "cdn_country_weights",
                            "cdn_policy_version": policy_version,
                            "rng_stream_id": rng_stream_id,
                            "rng_event_id": rng_event_ref,
                            "sampling_rank": None,
                        }
                        edge_row["edge_digest"] = _edge_digest(edge_row, edge_digest_fields)
                        edges_for_merchant.append(edge_row)
                        edge_seq_index += 1
                        resamples_total += max(attempts - 1, 0)
                        attempts_hist[attempts] = attempts_hist.get(attempts, 0) + 1
                        progress.update(1)
            if edge_seq_index != edge_scale:
                _abort(
                    "E3B_S2_EDGE_CATALOGUE_SCHEMA_VIOLATION",
                    "V-12",
                    "edge_count_mismatch",
                    {"merchant_id": merchant_id, "expected": edge_scale, "actual": edge_seq_index},
                    manifest_fingerprint,
                )
            edges_for_merchant.sort(key=lambda row: row["edge_id"])
            edge_ids = [row["edge_id"] for row in edges_for_merchant]
            if len(edge_ids) != len(set(edge_ids)):
                _abort(
                    "E3B_S2_EDGE_CATALOGUE_SCHEMA_VIOLATION",
                    "V-12",
                    "edge_id_duplicate",
                    {"merchant_id": merchant_id},
                    manifest_fingerprint,
                )
            merchant_digest = _hash_hex_list([row["edge_digest"] for row in edges_for_merchant])
            per_merchant_digests.append((merchant_id, merchant_digest))
            index_rows.append(
                {
                    "scope": "MERCHANT",
                    "seed": int(seed),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "merchant_id": merchant_id,
                    "edge_count_total": len(edges_for_merchant),
                    "edge_digest": merchant_digest,
                    "edge_catalogue_path": None,
                    "edge_catalogue_size_bytes": None,
                    "country_mix_summary": None,
                    "edge_count_total_all_merchants": None,
                    "edge_catalogue_digest_global": None,
                    "notes": None,
                }
            )
            edge_rows.extend(edges_for_merchant)
            if len(edge_rows) >= EDGE_BATCH_SIZE:
                edge_part_idx = _flush_edges(edge_rows, edge_part_idx)

        edge_part_idx = _flush_edges(edge_rows, edge_part_idx)
        if edges_total == 0 and edge_part_idx == 0:
            empty_df = pl.DataFrame(schema=edge_schema)
            empty_df.write_parquet(edge_tmp / "part-00000.parquet", compression="zstd")
            edge_part_idx = 1

        if not event_enabled and trace_handle is not None and trace_acc is not None:
            rng_events_emitted = _append_trace_from_events(event_root, trace_handle, trace_acc, logger)

        if rng_events_emitted < edges_total:
            _abort(
                "E3B_S2_RNG_POLICY_VIOLATION",
                "V-10",
                "rng_events_lt_edges",
                {"events": rng_events_emitted, "edges": edges_total},
                manifest_fingerprint,
            )

        counts["rng_events_total"] = rng_events_emitted
        counts["rng_draws_total"] = str(rng_events_emitted * 2)
        counts["rng_blocks_total"] = rng_events_emitted
        counts["jitter_resamples_total"] = resamples_total
        counts["jitter_exhausted_total"] = jitter_exhausted

        edge_catalogue_size_bytes = _partition_size_bytes(edge_tmp)
        per_merchant_digests.sort(key=lambda item: item[0])
        global_digest = _hash_hex_list([digest for _, digest in per_merchant_digests])

        edge_entry = find_dataset_entry(dictionary_3b, "edge_catalogue_3B").entry
        index_entry = find_dataset_entry(dictionary_3b, "edge_catalogue_index_3B").entry
        edge_catalogue_root = _resolve_dataset_path(edge_entry, run_paths, config.external_roots, tokens)
        index_path = _resolve_dataset_path(index_entry, run_paths, config.external_roots, tokens)

        index_rows.append(
            {
                "scope": "GLOBAL",
                "seed": int(seed),
                "manifest_fingerprint": str(manifest_fingerprint),
                "merchant_id": None,
                "edge_count_total": None,
                "edge_digest": None,
                "edge_catalogue_path": _render_catalog_path(edge_entry, tokens),
                "edge_catalogue_size_bytes": edge_catalogue_size_bytes,
                "country_mix_summary": None,
                "edge_count_total_all_merchants": edges_total,
                "edge_catalogue_digest_global": global_digest,
                "notes": None,
            }
        )

        index_df = pl.DataFrame(index_rows, schema=index_schema)
        try:
            validate_dataframe(index_df.iter_rows(named=True), index_pack, index_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S2_EDGE_INDEX_SCHEMA_INVALID",
                "V-12",
                "edge_index_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )
        index_tmp_path = tmp_root / "edge_catalogue_index_3B.parquet"
        index_df.write_parquet(index_tmp_path, compression="zstd")

        if event_handle is not None and not event_handle.closed:
            event_handle.close()
        if trace_handle is not None and not trace_handle.closed:
            trace_handle.close()

        _atomic_publish_dir(edge_tmp, edge_catalogue_root, logger, "edge_catalogue_3B")
        _atomic_publish_file(index_tmp_path, index_path, logger, "edge_catalogue_index_3B")

        if event_enabled:
            _atomic_publish_dir(event_tmp_dir, event_root, logger, "rng_event_edge_jitter")
        if trace_mode == "create" and trace_tmp_path:
            _atomic_publish_file(trace_tmp_path, trace_path, logger, "rng_trace_log")
        elif trace_mode == "append":
            logger.info("S2: rng_trace_log appended (existing log retained)")

        _ensure_rng_audit(audit_path, audit_entry_payload, logger)

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
            error_code = "E3B_S2_019_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3B_S2_019_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        if event_handle is not None and not event_handle.closed:
            event_handle.close()
        if trace_handle is not None and not trace_handle.closed:
            trace_handle.close()
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint:
            try:
                run_report_entry = find_dataset_entry(dictionary_3b, "s2_run_report_3B").entry
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
                        "cdn_policy_id": "cdn_country_weights",
                        "cdn_policy_version": policy_version,
                        "cdn_weights_digest": policy_digest,
                        "route_rng_policy_version": route_policy_version,
                        "rng_stream_id": rng_stream_id,
                    },
                    "counts": counts,
                    "tz_sources": tz_counts,
                    "edges_by_country": edges_by_country,
                    "attempt_histogram": {str(k): int(v) for k, v in sorted(attempts_hist.items())},
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "edge_catalogue_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "edge_catalogue_3B").entry, tokens
                        ),
                        "edge_catalogue_index_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "edge_catalogue_index_3B").entry, tokens
                        ),
                        "rng_event_edge_jitter_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "rng_event_edge_jitter").entry, tokens
                        ),
                        "rng_trace_log_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "rng_trace_log").entry, tokens
                        ),
                        "rng_audit_log_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "rng_audit_log").entry, tokens
                        ),
                        "format": "parquet",
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S2: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S2: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3B_S2_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if (
        edge_catalogue_root is None
        or index_path is None
        or run_report_path is None
        or event_root is None
        or trace_path is None
        or audit_path is None
    ):
        raise EngineFailure(
            "F4",
            "E3B_S2_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S2Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        edge_catalogue_root=edge_catalogue_root,
        index_path=index_path,
        run_report_path=run_report_path,
        event_root=event_root,
        trace_path=trace_path,
        audit_path=audit_path,
    )
