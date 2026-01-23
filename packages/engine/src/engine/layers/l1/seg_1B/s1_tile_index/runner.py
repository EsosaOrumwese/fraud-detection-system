"""S1 tile index runner for Segment 1B."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import geopandas as gpd
import numpy as np
import polars as pl
import psutil
import rasterio
import shapely
from pyproj import Geod
from rasterio.features import geometry_mask
from rasterio.windows import Window, transform as window_transform
from shapely import wkb
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union
from shapely.validation import explain_validity

from engine.contracts.loader import (
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import EngineFailure, InputResolutionError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt


MODULE_NAME = "1B.s1_tile_index"
ALLOWED_PREDICATES = {"center", "any_overlap"}


@dataclass(frozen=True)
class CountryTask:
    country_iso: str
    geometry_wkb: bytes
    predicate: str
    raster_path: str
    tile_index_root: str
    tile_bounds_root: str


@dataclass(frozen=True)
class CountryResult:
    country_iso: str
    rows_emitted: int
    cells_visited: int
    cells_included: int
    cells_excluded_outside: int
    cells_excluded_hole: int
    tile_id_min: Optional[int]
    tile_id_max: Optional[int]
    max_worker_rss_bytes: int
    open_files_peak: int
    cpu_seconds_total: float


@dataclass(frozen=True)
class S1Result:
    run_id: str
    parameter_hash: str
    tile_index_path: Path
    tile_bounds_path: Path
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


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    return pick_latest_run_receipt(runs_root)


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
        return receipt_path, _load_json(receipt_path)
    receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


def _resolve_dataset_path(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> Path:
    path_template = entry.get("path")
    if not path_template:
        raise InputResolutionError("Dataset entry missing path.")
    resolved = path_template
    for key, value in tokens.items():
        resolved = resolved.replace(f"{{{key}}}", value)
    if resolved.startswith(("data/", "logs/", "reports/", "artefacts/")):
        return run_paths.run_root / resolved
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _open_files_count(proc: psutil.Process) -> int:
    if hasattr(proc, "num_handles"):
        return proc.num_handles()
    if hasattr(proc, "num_fds"):
        return proc.num_fds()
    return 0


def _read_proj_minor_version(proj_db: Path) -> Optional[int]:
    try:
        conn = sqlite3.connect(proj_db)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "select value from metadata where key='DATABASE.LAYOUT.VERSION.MINOR'"
            )
            row = cursor.fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _ensure_proj_db(logger) -> None:
    from pyproj import datadir as proj_datadir

    proj_data_dir = Path(proj_datadir.get_data_dir())
    env_path = os.environ.get("PROJ_LIB") or os.environ.get("PROJ_DATA")
    if env_path:
        env_dir = Path(env_path)
        proj_db = env_dir / "proj.db"
        override = False
        if not proj_db.exists():
            override = True
        else:
            minor = _read_proj_minor_version(proj_db)
            if minor is not None and minor < 4:
                override = True
        if override:
            os.environ["PROJ_LIB"] = str(proj_data_dir)
            os.environ["PROJ_DATA"] = str(proj_data_dir)
            logger.info(
                "S1: overriding PROJ_LIB to %s (previous=%s)",
                proj_data_dir,
                env_path,
            )
    else:
        os.environ["PROJ_LIB"] = str(proj_data_dir)
        os.environ["PROJ_DATA"] = str(proj_data_dir)
        logger.info("S1: setting PROJ_LIB to %s (was unset)", proj_data_dir)


def _emit_failure_event(logger, code: str, parameter_hash: str, detail: dict) -> None:
    payload = {"event": "S1_ERROR", "code": code, "at": utc_now_rfc3339_micro(), "parameter_hash": parameter_hash}
    payload.update(detail)
    logger.error("S1_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _hash_partition(root: Path) -> tuple[str, int]:
    files = sorted(
        [path for path in root.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    h = hashlib.sha256()
    total_bytes = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                h.update(chunk)
    return h.hexdigest(), total_bytes


def _atomic_publish_dir(
    tmp_root: Path,
    final_root: Path,
    logger,
    label: str,
) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                "S1",
                MODULE_NAME,
                {"partition": str(final_root), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S1: %s partition already exists and is identical; skipping publish.", label)
        return
    tmp_root.replace(final_root)


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                "S1",
                MODULE_NAME,
                {"path": str(final_path), "tmp_hash": tmp_hash, "final_hash": final_hash, "label": label},
            )
        tmp_path.unlink()
        logger.info("S1: %s already exists and is identical; skipping publish.", label)
        return
    tmp_path.replace(final_path)


def _needs_antimeridian_shift(bounds: tuple[float, float, float, float]) -> bool:
    minx, _, maxx, _ = bounds
    return (maxx - minx) > 180.0


_ANTIMERIDIAN_EPS = 1e-9
_ANTIMERIDIAN_WEST = box(0.0, -90.0, 180.0 - _ANTIMERIDIAN_EPS, 90.0)
_ANTIMERIDIAN_EAST = box(180.0 - _ANTIMERIDIAN_EPS, -90.0, 360.0, 90.0)


def _shift_geometry_to_360(geom):
    def _shift(x, y, z=None):
        if isinstance(x, (list, tuple, np.ndarray)):
            x = np.asarray(x)
            return np.where(x < 0.0, x + 360.0, x), y
        return (x + 360.0 if x < 0.0 else x), y

    return shapely_transform(_shift, geom)


def _shift_geometry_from_360(geom):
    def _shift(x, y, z=None):
        if isinstance(x, (list, tuple, np.ndarray)):
            x = np.asarray(x)
            return x - 360.0, y
        return x - 360.0, y

    return shapely_transform(_shift, geom)


def _polygonal_only(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if getattr(geom, "geom_type", "") == "GeometryCollection":
        polys = [item for item in geom.geoms if isinstance(item, (Polygon, MultiPolygon)) and not item.is_empty]
        if not polys:
            return None
        return unary_union(polys)
    return None


def _split_antimeridian_geometries(geom) -> list:
    if not _needs_antimeridian_shift(geom.bounds):
        return [geom]
    geom_360 = _shift_geometry_to_360(geom)
    if not geom_360.is_valid:
        geom_360 = shapely.make_valid(geom_360)
        if geom_360 is None or geom_360.is_empty:
            return []
    west = _polygonal_only(geom_360.intersection(_ANTIMERIDIAN_WEST))
    east = _polygonal_only(geom_360.intersection(_ANTIMERIDIAN_EAST))
    parts: list = []
    if west is not None and not west.is_empty:
        parts.append(west)
    if east is not None and not east.is_empty:
        parts.append(_shift_geometry_from_360(east))
    return parts


def _normalize_lon_array(values: np.ndarray) -> np.ndarray:
    normalized = np.where(values > 180.0, values - 360.0, values)
    normalized = np.where(normalized < -180.0, normalized + 360.0, normalized)
    return normalized


def _extract_exterior_only(geom):
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)
    if isinstance(geom, MultiPolygon):
        exteriors = [Polygon(poly.exterior) for poly in geom.geoms]
        return unary_union(exteriors)
    return geom


def _extract_holes(geom) -> Optional[Polygon | MultiPolygon]:
    holes = []
    if isinstance(geom, Polygon):
        holes.extend(Polygon(ring) for ring in geom.interiors)
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            holes.extend(Polygon(ring) for ring in poly.interiors)
    if not holes:
        return None
    return unary_union(holes)

def _process_country(task: CountryTask) -> CountryResult:
    start_cpu = time.process_time()
    proc = psutil.Process()
    open_files_peak = _open_files_count(proc)
    max_rss = proc.memory_info().rss
    country = task.country_iso
    geom = wkb.loads(task.geometry_wkb)
    predicate = task.predicate
    raster_path = Path(task.raster_path)
    tile_index_root = Path(task.tile_index_root)
    tile_bounds_root = Path(task.tile_bounds_root)

    if not geom.is_valid:
        raise EngineFailure(
            "F4",
            "E001_GEO_INVALID",
            "S1",
            MODULE_NAME,
            {"country_iso": country, "detail": explain_validity(geom)},
        )

    with rasterio.open(raster_path) as dataset:
        transform = dataset.transform
        ncols = dataset.width
        rotated = not (transform.b == 0 and transform.d == 0)
        geod = Geod(ellps="WGS84")

        try:
            geom_parts = _split_antimeridian_geometries(geom)
        except GEOSException as exc:
            raise EngineFailure(
                "F4",
                "E001_GEO_INVALID",
                "S1",
                MODULE_NAME,
                {"country_iso": country, "detail": str(exc)},
            ) from exc
        if not geom_parts:
            return CountryResult(
                country_iso=country,
                rows_emitted=0,
                cells_visited=0,
                cells_included=0,
                cells_excluded_outside=0,
                cells_excluded_hole=0,
                tile_id_min=None,
                tile_id_max=None,
                max_worker_rss_bytes=max_rss,
                open_files_peak=open_files_peak,
                cpu_seconds_total=time.process_time() - start_cpu,
            )

        included_rows_all: list[np.ndarray] = []
        included_cols_all: list[np.ndarray] = []
        cells_visited_total = 0
        cells_excluded_outside = 0
        cells_excluded_hole = 0

        for part in geom_parts:
            try:
                window = rasterio.features.geometry_window(dataset, [part], pad_x=0, pad_y=0)
            except Exception:
                window = None

            if window is None or window.width <= 0 or window.height <= 0:
                continue

            window = Window(
                col_off=int(window.col_off),
                row_off=int(window.row_off),
                width=int(window.width),
                height=int(window.height),
            )
            win_transform = window_transform(window, transform)
            window_cells = int(window.width * window.height)
            cells_visited_total += window_cells

            exterior_geom = _extract_exterior_only(part)
            hole_geom = _extract_holes(part)
            all_touched = predicate == "any_overlap"

            exterior_mask = geometry_mask(
                [exterior_geom],
                out_shape=(window.height, window.width),
                transform=win_transform,
                invert=True,
                all_touched=all_touched,
            )

            if predicate == "center":
                include_mask = geometry_mask(
                    [part],
                    out_shape=(window.height, window.width),
                    transform=win_transform,
                    invert=True,
                    all_touched=False,
                )
                hole_mask = None
                if hole_geom is not None:
                    hole_mask = geometry_mask(
                        [hole_geom],
                        out_shape=(window.height, window.width),
                        transform=win_transform,
                        invert=True,
                        all_touched=False,
                    )
                included_rows, included_cols = np.nonzero(include_mask)
                cells_excluded_outside += window_cells - int(exterior_mask.sum())
                if hole_mask is not None:
                    cells_excluded_hole += int(hole_mask.sum())
            else:
                candidate_rows, candidate_cols = np.nonzero(exterior_mask)
                cells_candidates = candidate_rows.size
                cells_excluded_outside += window_cells - int(cells_candidates)
                included_rows = []
                included_cols = []
                if cells_candidates:
                    for row_idx, col_idx in zip(candidate_rows, candidate_cols):
                        row_global = row_idx + window.row_off
                        col_global = col_idx + window.col_off
                        if rotated:
                            ul_x, ul_y = rasterio.transform.xy(transform, row_global, col_global, offset="ul")
                            lr_x, lr_y = rasterio.transform.xy(transform, row_global, col_global, offset="lr")
                            min_lon = min(ul_x, lr_x)
                            max_lon = max(ul_x, lr_x)
                            min_lat = min(ul_y, lr_y)
                            max_lat = max(ul_y, lr_y)
                            cell_poly = box(min_lon, min_lat, max_lon, max_lat)
                        else:
                            lon_left = transform.c + transform.a * col_global
                            lon_right = lon_left + transform.a
                            lat_top = transform.f + transform.e * row_global
                            lat_bottom = lat_top + transform.e
                            min_lon = min(lon_left, lon_right)
                            max_lon = max(lon_left, lon_right)
                            min_lat = min(lat_top, lat_bottom)
                            max_lat = max(lat_top, lat_bottom)
                            cell_poly = box(min_lon, min_lat, max_lon, max_lat)
                        full_area = cell_poly.intersection(part).area
                        if full_area > 0.0:
                            included_rows.append(row_idx)
                            included_cols.append(col_idx)
                        else:
                            ext_area = cell_poly.intersection(exterior_geom).area
                            if ext_area > 0.0:
                                cells_excluded_hole += 1
                            else:
                                cells_excluded_outside += 1
                included_rows = np.asarray(included_rows, dtype=np.int64)
                included_cols = np.asarray(included_cols, dtype=np.int64)

            if included_rows.size:
                included_rows_all.append(included_rows + window.row_off)
                included_cols_all.append(included_cols + window.col_off)

        if not included_rows_all:
            return CountryResult(
                country_iso=country,
                rows_emitted=0,
                cells_visited=cells_visited_total,
                cells_included=0,
                cells_excluded_outside=cells_excluded_outside,
                cells_excluded_hole=cells_excluded_hole,
                tile_id_min=None,
                tile_id_max=None,
                max_worker_rss_bytes=max_rss,
                open_files_peak=open_files_peak,
                cpu_seconds_total=time.process_time() - start_cpu,
            )

        global_rows = np.concatenate(included_rows_all).astype(np.int64)
        global_cols = np.concatenate(included_cols_all).astype(np.int64)
        tile_ids = global_rows.astype(np.uint64) * np.uint64(ncols) + global_cols.astype(np.uint64)
        if np.unique(tile_ids).size != tile_ids.size:
            raise EngineFailure(
                "F4",
                "E003_DUP_TILE",
                "S1",
                MODULE_NAME,
                {"country_iso": country, "detail": "duplicate_tile_id"},
            )

        if rotated:
            ul_x, ul_y = rasterio.transform.xy(transform, global_rows, global_cols, offset="ul")
            ur_x, ur_y = rasterio.transform.xy(transform, global_rows, global_cols, offset="ur")
            ll_x, ll_y = rasterio.transform.xy(transform, global_rows, global_cols, offset="ll")
            lr_x, lr_y = rasterio.transform.xy(transform, global_rows, global_cols, offset="lr")
            cent_x, cent_y = rasterio.transform.xy(transform, global_rows, global_cols, offset="center")
            corners_x = np.vstack([np.array(ul_x), np.array(ur_x), np.array(ll_x), np.array(lr_x)])
            corners_y = np.vstack([np.array(ul_y), np.array(ur_y), np.array(ll_y), np.array(lr_y)])
            min_lon = corners_x.min(axis=0)
            max_lon = corners_x.max(axis=0)
            min_lat = corners_y.min(axis=0)
            max_lat = corners_y.max(axis=0)
            centroid_lon = np.array(cent_x)
            centroid_lat = np.array(cent_y)
        else:
            lon_left = transform.c + transform.a * global_cols
            lon_right = lon_left + transform.a
            lat_top = transform.f + transform.e * global_rows
            lat_bottom = lat_top + transform.e
            min_lon = np.minimum(lon_left, lon_right)
            max_lon = np.maximum(lon_left, lon_right)
            min_lat = np.minimum(lat_top, lat_bottom)
            max_lat = np.maximum(lat_top, lat_bottom)
            centroid_lon = (min_lon + max_lon) / 2.0
            centroid_lat = (min_lat + max_lat) / 2.0

        min_lon = _normalize_lon_array(min_lon)
        max_lon = _normalize_lon_array(max_lon)
        centroid_lon = _normalize_lon_array(centroid_lon)

        bounds_ok = (
            np.all(centroid_lon >= -180.0)
            and np.all(centroid_lon <= 180.0)
            and np.all(centroid_lat >= -90.0)
            and np.all(centroid_lat <= 90.0)
            and np.all(min_lon >= -180.0)
            and np.all(min_lon <= 180.0)
            and np.all(max_lon >= -180.0)
            and np.all(max_lon <= 180.0)
            and np.all(min_lat >= -90.0)
            and np.all(min_lat <= 90.0)
            and np.all(max_lat >= -90.0)
            and np.all(max_lat <= 90.0)
        )
        if not bounds_ok:
            raise EngineFailure(
                "F4",
                "E004_BOUNDS",
                "S1",
                MODULE_NAME,
                {"country_iso": country, "detail": "coordinate_out_of_bounds"},
            )

        if rotated:
            pixel_area = np.zeros_like(centroid_lon, dtype=float)
            for idx in range(pixel_area.size):
                polygon = [
                    (float(min_lon[idx]), float(min_lat[idx])),
                    (float(max_lon[idx]), float(min_lat[idx])),
                    (float(max_lon[idx]), float(max_lat[idx])),
                    (float(min_lon[idx]), float(max_lat[idx])),
                ]
                area, _ = geod.polygon_area_perimeter(
                    [pt[0] for pt in polygon], [pt[1] for pt in polygon]
                )
                pixel_area[idx] = abs(area)
        else:
            unique_rows = np.unique(global_rows)
            row_area = {}
            delta_lon = abs(transform.a)
            for row_idx in unique_rows:
                lat_top = transform.f + transform.e * row_idx
                lat_bottom = lat_top + transform.e
                lat_min = min(lat_top, lat_bottom)
                lat_max = max(lat_top, lat_bottom)
                area, _ = geod.polygon_area_perimeter(
                    [0.0, delta_lon, delta_lon, 0.0],
                    [lat_min, lat_min, lat_max, lat_max],
                )
                row_area[int(row_idx)] = abs(area)
            pixel_area = np.array([row_area[int(row)] for row in global_rows], dtype=float)

        if np.any(pixel_area <= 0.0):
            raise EngineFailure(
                "F4",
                "E006_AREA_NONPOS",
                "S1",
                MODULE_NAME,
                {"country_iso": country, "detail": "pixel_area_nonpos"},
            )

        open_files_peak = max(open_files_peak, _open_files_count(proc))
        max_rss = max(max_rss, proc.memory_info().rss)

        tile_id_min = int(tile_ids.min()) if tile_ids.size else None
        tile_id_max = int(tile_ids.max()) if tile_ids.size else None

        tile_index_df = pl.DataFrame(
            {
                "country_iso": [country] * tile_ids.size,
                "tile_id": tile_ids,
                "raster_row": global_rows.astype(np.uint64),
                "raster_col": global_cols.astype(np.uint64),
                "centroid_lon": centroid_lon,
                "centroid_lat": centroid_lat,
                "pixel_area_m2": pixel_area,
                "inclusion_rule": [predicate] * tile_ids.size,
            }
        ).sort("tile_id")

        tile_bounds_df = pl.DataFrame(
            {
                "country_iso": [country] * tile_ids.size,
                "tile_id": tile_ids,
                "min_lat_deg": min_lat,
                "max_lat_deg": max_lat,
                "min_lon_deg": min_lon,
                "max_lon_deg": max_lon,
                "centroid_lat_deg": centroid_lat,
                "centroid_lon_deg": centroid_lon,
            }
        ).sort("tile_id")

        tile_index_path = tile_index_root / f"country={country}"
        tile_bounds_path = tile_bounds_root / f"country={country}"
        tile_index_path.mkdir(parents=True, exist_ok=True)
        tile_bounds_path.mkdir(parents=True, exist_ok=True)
        tile_index_df.write_parquet(tile_index_path / "part-000.parquet", compression="zstd", row_group_size=100000)
        tile_bounds_df.write_parquet(tile_bounds_path / "part-000.parquet", compression="zstd", row_group_size=100000)

        return CountryResult(
            country_iso=country,
            rows_emitted=tile_ids.size,
            cells_visited=cells_visited_total,
            cells_included=int(tile_ids.size),
            cells_excluded_outside=cells_excluded_outside,
            cells_excluded_hole=cells_excluded_hole,
            tile_id_min=tile_id_min,
            tile_id_max=tile_id_max,
            max_worker_rss_bytes=max_rss,
            open_files_peak=open_files_peak,
            cpu_seconds_total=time.process_time() - start_cpu,
        )

def run_s1(
    config: EngineConfig,
    run_id: Optional[str] = None,
    predicate: str = "center",
    workers: int = 1,
) -> S1Result:
    logger = get_logger("engine.layers.l1.seg_1B.s1_tile_index.l2.runner")
    _ensure_proj_db(logger)
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing parameter_hash or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    registry_path, registry = load_artefact_registry(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        registry_path,
        schema_1b_path,
        schema_ingress_path,
    )

    if predicate not in ALLOWED_PREDICATES:
        _emit_failure_event(
            logger,
            "E008_INCLUSION_RULE",
            str(parameter_hash),
            {"detail": "unsupported_predicate", "predicate": predicate},
        )
        raise EngineFailure(
            "F4",
            "E008_INCLUSION_RULE",
            "S1",
            MODULE_NAME,
            {"predicate": predicate},
        )

    sealed_entry = find_dataset_entry(dictionary, "sealed_inputs_1B").entry
    sealed_path = _resolve_dataset_path(
        sealed_entry, run_paths, config.external_roots, {"manifest_fingerprint": str(manifest_fingerprint)}
    )
    sealed_inputs = json.loads(sealed_path.read_text(encoding="utf-8"))
    sealed_index = {item["asset_id"]: item for item in sealed_inputs}
    required_ids = ["iso3166_canonical_2024", "world_countries", "population_raster_2025"]
    missing = [asset_id for asset_id in required_ids if asset_id not in sealed_index]
    if missing:
        _emit_failure_event(
            logger,
            "E005_ISO_FK",
            str(parameter_hash),
            {"detail": "missing_sealed_inputs", "missing": missing},
        )
        raise EngineFailure(
            "F4",
            "E005_ISO_FK",
            "S1",
            MODULE_NAME,
            {"missing": missing},
        )

    iso_entry = find_dataset_entry(dictionary, "iso3166_canonical_2024").entry
    iso_path_expected = _resolve_dataset_path(iso_entry, run_paths, config.external_roots, {})
    iso_path = Path(sealed_index["iso3166_canonical_2024"]["path"])
    if iso_path.resolve() != iso_path_expected.resolve():
        raise InputResolutionError(f"iso3166 path mismatch: {iso_path} vs {iso_path_expected}")
    world_entry = find_dataset_entry(dictionary, "world_countries").entry
    world_path_expected = _resolve_dataset_path(world_entry, run_paths, config.external_roots, {})
    world_path = Path(sealed_index["world_countries"]["path"])
    if world_path.resolve() != world_path_expected.resolve():
        raise InputResolutionError(f"world_countries path mismatch: {world_path} vs {world_path_expected}")
    raster_entry = find_dataset_entry(dictionary, "population_raster_2025").entry
    raster_path_expected = _resolve_dataset_path(raster_entry, run_paths, config.external_roots, {})
    raster_path = Path(sealed_index["population_raster_2025"]["path"])
    if raster_path.resolve() != raster_path_expected.resolve():
        raise InputResolutionError(f"population_raster path mismatch: {raster_path} vs {raster_path_expected}")

    logger.info("S1: loading vector inputs (ISO + world_countries).")
    vector_start = time.monotonic()
    iso_df = pl.read_parquet(iso_path).select("country_iso").with_columns(
        pl.col("country_iso").str.to_uppercase()
    )
    world_gdf = gpd.read_parquet(world_path)
    vector_elapsed = time.monotonic() - vector_start
    bytes_read_vectors_total = iso_path.stat().st_size + world_path.stat().st_size
    io_baseline_vectors_bps = (
        bytes_read_vectors_total / vector_elapsed if vector_elapsed > 0 else 0.0
    )
    logger.info(
        "S1: vector baseline bytes=%d elapsed=%.2fs baseline_bps=%.2f",
        bytes_read_vectors_total,
        vector_elapsed,
        io_baseline_vectors_bps,
    )

    iso_codes = sorted(iso_df["country_iso"].unique().to_list())
    logger.info("S1: ISO codes loaded (count=%d).", len(iso_codes))

    if "country_iso" not in world_gdf.columns or "geom" not in world_gdf.columns:
        raise InputResolutionError("world_countries missing required columns (country_iso, geom).")
    world_gdf["country_iso"] = world_gdf["country_iso"].astype(str).str.upper()
    world_grouped = world_gdf.groupby("country_iso")["geom"].agg(lambda items: unary_union(list(items)))
    world_map = world_grouped.to_dict()

    missing_geom = [code for code in iso_codes if code not in world_map]
    if missing_geom:
        _emit_failure_event(
            logger,
            "E005_ISO_FK",
            str(parameter_hash),
            {"detail": "missing_world_countries", "missing": missing_geom},
        )
        raise EngineFailure(
            "F4",
            "E005_ISO_FK",
            "S1",
            MODULE_NAME,
            {"missing": missing_geom},
        )

    for code, geom in world_map.items():
        if geom is None or geom.is_empty or not geom.is_valid:
            _emit_failure_event(
                logger,
                "E001_GEO_INVALID",
                str(parameter_hash),
                {"country_iso": code, "detail": "invalid_geometry"},
            )
            raise EngineFailure(
                "F4",
                "E001_GEO_INVALID",
                "S1",
                MODULE_NAME,
                {"country_iso": code},
            )

    logger.info(
        "S1: starting tile enumeration (countries=%d predicate=%s workers=%d).",
        len(iso_codes),
        predicate,
        workers,
    )
    logger.info("S1: chunk_size=0 (per-country windows; no tile block chunking).")

    start_wall = time.monotonic()
    start_cpu = time.process_time()
    proc = psutil.Process()
    open_files_peak = _open_files_count(proc)
    max_worker_rss_bytes = proc.memory_info().rss

    with rasterio.open(raster_path) as dataset:
        nrows, ncols = dataset.height, dataset.width
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            _emit_failure_event(
                logger,
                "E002_RASTER_MISMATCH",
                str(parameter_hash),
                {"detail": "unexpected_crs", "crs": str(dataset.crs)},
            )
            raise EngineFailure(
                "F4",
                "E002_RASTER_MISMATCH",
                "S1",
                MODULE_NAME,
                {"crs": str(dataset.crs)},
            )

        bytes_per_pixel = np.dtype(dataset.dtypes[0]).itemsize
        target_bytes = min(1024 * 1024 * 1024, nrows * ncols * bytes_per_pixel)
        rows_to_read = max(1, int(math.ceil(target_bytes / (ncols * bytes_per_pixel))))
        rows_to_read = min(rows_to_read, nrows)
        baseline_window = Window(0, 0, ncols, rows_to_read)
        baseline_start = time.monotonic()
        baseline_array = dataset.read(1, window=baseline_window)
        baseline_elapsed = time.monotonic() - baseline_start
        bytes_read_raster_total = int(baseline_array.nbytes)
        io_baseline_raster_bps = (
            bytes_read_raster_total / baseline_elapsed if baseline_elapsed > 0 else 0.0
        )
        logger.info(
            "S1: raster baseline bytes=%d elapsed=%.2fs baseline_bps=%.2f",
            bytes_read_raster_total,
            baseline_elapsed,
            io_baseline_raster_bps,
        )

    tmp_root = run_paths.tmp_root / f"_tmp.s1.{uuid.uuid4().hex}"
    tile_index_tmp = tmp_root / "tile_index"
    tile_bounds_tmp = tmp_root / "tile_bounds"
    tile_index_tmp.mkdir(parents=True, exist_ok=True)
    tile_bounds_tmp.mkdir(parents=True, exist_ok=True)

    tasks = [
        CountryTask(
            country_iso=code,
            geometry_wkb=world_map[code].wkb,
            predicate=predicate,
            raster_path=str(raster_path),
            tile_index_root=str(tile_index_tmp),
            tile_bounds_root=str(tile_bounds_tmp),
        )
        for code in iso_codes
    ]

    rows_emitted_total = 0
    cells_scanned_total = 0
    cells_included_total = 0
    worker_cpu_total = 0.0
    per_country_summaries = []

    if workers > 1:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_process_country, task): task.country_iso for task in tasks}
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                except EngineFailure as exc:
                    _emit_failure_event(
                        logger, exc.failure_code, str(parameter_hash), exc.detail
                    )
                    raise
                completed += 1
                rows_emitted_total += result.rows_emitted
                cells_scanned_total += result.cells_visited
                cells_included_total += result.cells_included
                worker_cpu_total += result.cpu_seconds_total
                max_worker_rss_bytes = max(max_worker_rss_bytes, result.max_worker_rss_bytes)
                open_files_peak = max(open_files_peak, result.open_files_peak)
                per_country_summaries.append(result)
                logger.info(
                    "S1 progress countries_processed=%d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                    completed,
                    len(tasks),
                    time.monotonic() - start_wall,
                    completed / max(0.001, time.monotonic() - start_wall),
                    (len(tasks) - completed)
                    / max(0.001, completed / max(0.001, time.monotonic() - start_wall)),
                )
    else:
        completed = 0
        for task in tasks:
            try:
                result = _process_country(task)
            except EngineFailure as exc:
                _emit_failure_event(
                    logger, exc.failure_code, str(parameter_hash), exc.detail
                )
                raise
            completed += 1
            rows_emitted_total += result.rows_emitted
            cells_scanned_total += result.cells_visited
            cells_included_total += result.cells_included
            worker_cpu_total += result.cpu_seconds_total
            max_worker_rss_bytes = max(max_worker_rss_bytes, result.max_worker_rss_bytes)
            open_files_peak = max(open_files_peak, result.open_files_peak)
            per_country_summaries.append(result)
            logger.info(
                "S1 progress countries_processed=%d/%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                completed,
                len(tasks),
                time.monotonic() - start_wall,
                completed / max(0.001, time.monotonic() - start_wall),
                (len(tasks) - completed)
                / max(0.001, completed / max(0.001, time.monotonic() - start_wall)),
            )

    for summary in sorted(per_country_summaries, key=lambda item: item.country_iso):
        audit_payload = {
            "country_iso": summary.country_iso,
            "cells_visited": summary.cells_visited,
            "cells_included": summary.cells_included,
            "cells_excluded_outside": summary.cells_excluded_outside,
            "cells_excluded_hole": summary.cells_excluded_hole,
            "tile_id_min": summary.tile_id_min,
            "tile_id_max": summary.tile_id_max,
        }
        logger.info("AUDIT_S1_COUNTRY: %s", json.dumps(audit_payload, ensure_ascii=True, sort_keys=True))

    tile_index_hash, _ = _hash_partition(tile_index_tmp)
    determinism_receipt = {
        "partition_path": f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}/",
        "sha256_hex": tile_index_hash,
    }

    wall_clock = time.monotonic() - start_wall
    main_cpu = time.process_time() - start_cpu
    cpu_seconds_total = main_cpu + (worker_cpu_total if workers > 1 else 0.0)
    pat = {
        "wall_clock_seconds_total": wall_clock,
        "cpu_seconds_total": cpu_seconds_total,
        "countries_processed": len(tasks),
        "cells_scanned_total": cells_scanned_total,
        "cells_included_total": cells_included_total,
        "bytes_read_raster_total": bytes_read_raster_total,
        "bytes_read_vectors_total": bytes_read_vectors_total,
        "max_worker_rss_bytes": max_worker_rss_bytes,
        "open_files_peak": open_files_peak,
        "workers_used": max(1, workers),
        "chunk_size": 0,
        "io_baseline_raster_bps": io_baseline_raster_bps,
        "io_baseline_vectors_bps": io_baseline_vectors_bps,
    }

    run_report = {
        "parameter_hash": str(parameter_hash),
        "predicate": predicate,
        "ingress_versions": {
            "iso3166": sealed_index["iso3166_canonical_2024"]["version_tag"],
            "world_countries": sealed_index["world_countries"]["version_tag"],
            "population_raster": sealed_index["population_raster_2025"]["version_tag"],
        },
        "grid_dims": {"nrows": nrows, "ncols": ncols},
        "countries_total": len(iso_codes),
        "rows_emitted": rows_emitted_total,
        "determinism_receipt": determinism_receipt,
        "pat": pat,
    }

    tile_index_entry = find_dataset_entry(dictionary, "tile_index").entry
    tile_bounds_entry = find_dataset_entry(dictionary, "tile_bounds").entry
    report_entry = find_dataset_entry(dictionary, "s1_run_report").entry

    tile_index_root = _resolve_dataset_path(
        tile_index_entry, run_paths, config.external_roots, {"parameter_hash": str(parameter_hash)}
    )
    tile_bounds_root = _resolve_dataset_path(
        tile_bounds_entry, run_paths, config.external_roots, {"parameter_hash": str(parameter_hash)}
    )
    report_path = _resolve_dataset_path(
        report_entry, run_paths, config.external_roots, {"parameter_hash": str(parameter_hash)}
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_tmp = report_path.parent / f"_tmp.{uuid.uuid4().hex}.json"
    _write_json(report_tmp, run_report)

    tile_index_root.parent.mkdir(parents=True, exist_ok=True)
    tile_bounds_root.parent.mkdir(parents=True, exist_ok=True)
    _atomic_publish_dir(tile_index_tmp, tile_index_root, logger, "tile_index")
    _atomic_publish_dir(tile_bounds_tmp, tile_bounds_root, logger, "tile_bounds")
    _atomic_publish_file(report_tmp, report_path, logger, "s1_run_report")

    if tmp_root.exists():
        shutil.rmtree(tmp_root, ignore_errors=True)

    timer.info(f"S1: completed tile index publish (rows_emitted={rows_emitted_total})")
    return S1Result(
        run_id=run_id,
        parameter_hash=str(parameter_hash),
        tile_index_path=tile_index_root,
        tile_bounds_path=tile_bounds_root,
        run_report_path=report_path,
    )
