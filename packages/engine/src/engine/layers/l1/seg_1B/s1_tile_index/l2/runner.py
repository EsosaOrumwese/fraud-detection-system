"""L2 orchestration for Segment 1B S1 (Tile Index)."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple
from uuid import uuid4

import numpy as np
import polars as pl
import rasterio.features
import rasterio.windows
from rasterio.transform import rowcol, xy
from shapely import wkb
from shapely.geometry import Polygon, mapping
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep as prepare_geometry

from ..l0.loaders import (
    CountryPolygon,
    CountryPolygons,
    IsoCountryTable,
    PopulationRaster,
    load_country_polygons,
    load_iso_countries,
    load_population_raster,
)
from ..l1.predicates import InclusionRule
from ...shared.dictionary import (
    get_dataset_entry,
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)

logger = logging.getLogger(__name__)

_TILE_COLUMNS = (
    "country_iso",
    "tile_id",
    "inclusion_rule",
    "raster_row",
    "raster_col",
    "centroid_lon",
    "centroid_lat",
    "pixel_area_m2",
)

_TILE_SCHEMA: dict[str, pl.DataType] = {
    "country_iso": pl.Utf8,
    "tile_id": pl.UInt64,
    "inclusion_rule": pl.Utf8,
    "raster_row": pl.UInt32,
    "raster_col": pl.UInt32,
    "centroid_lon": pl.Float64,
    "centroid_lat": pl.Float64,
    "pixel_area_m2": pl.Float64,
}

_BOUNDS_COLUMNS = (
    "country_iso",
    "tile_id",
    "west_lon",
    "east_lon",
    "south_lat",
    "north_lat",
)

_BOUNDS_SCHEMA: dict[str, pl.DataType] = {
    "country_iso": pl.Utf8,
    "tile_id": pl.UInt64,
    "west_lon": pl.Float64,
    "east_lon": pl.Float64,
    "south_lat": pl.Float64,
    "north_lat": pl.Float64,
}

_BATCH_SIZE = 200_000
_CHUNK_SIZE = 512


class S1RunError(RuntimeError):
    """Raised when S1 orchestration encounters a contract violation."""


@dataclass
class RunnerConfig:
    """Configuration inputs required to execute S1."""

    data_root: Path
    parameter_hash: str
    inclusion_rule: str = "center"
    dictionary: Mapping[str, object] | None = None
    workers: int = 1


@dataclass
class CountrySummary:
    """Per-country accounting for observability artefacts."""

    country_iso: str
    cells_visited: int = 0
    cells_included: int = 0
    cells_excluded_outside: int = 0
    cells_excluded_hole: int = 0
    tile_id_min: int | None = None
    tile_id_max: int | None = None

    def record_batch(self, *, visited: int, included: int, hole_count: int) -> None:
        self.cells_visited += visited
        self.cells_included += included
        self.cells_excluded_hole += hole_count
        self.cells_excluded_outside += visited - included - hole_count

    def record_included_tile(self, tile_id: int) -> None:
        if self.tile_id_min is None or tile_id < self.tile_id_min:
            self.tile_id_min = tile_id
        if self.tile_id_max is None or tile_id > self.tile_id_max:
            self.tile_id_max = tile_id

    def record_included_tiles(self, tile_ids: np.ndarray) -> None:
        if tile_ids.size == 0:
            return
        tile_min = int(tile_ids.min())
        tile_max = int(tile_ids.max())
        if self.tile_id_min is None or tile_min < self.tile_id_min:
            self.tile_id_min = tile_min
        if self.tile_id_max is None or tile_max > self.tile_id_max:
            self.tile_id_max = tile_max


@dataclass
class ExecutionResult:
    """Container for the side-effects of an S1 execution branch."""

    tile_temp_dir: Path
    bounds_temp_dir: Path
    summaries: Dict[str, CountrySummary]
    rows_emitted: int
    worker_runtimes: list["WorkerRuntimeStats"]


@dataclass
class RunReport:
    parameter_hash: str
    predicate: str
    ingress_versions: Dict[str, str]
    grid_dims: Dict[str, int]
    countries_total: int
    rows_emitted: int
    determinism_receipt: Dict[str, str]
    pat: Dict[str, int | float | None]

    def to_dict(self) -> Dict[str, object]:
        return {
            "parameter_hash": self.parameter_hash,
            "predicate": self.predicate,
            "ingress_versions": self.ingress_versions,
            "grid_dims": self.grid_dims,
            "countries_total": self.countries_total,
            "rows_emitted": self.rows_emitted,
            "determinism_receipt": self.determinism_receipt,
            "pat": self.pat,
        }


@dataclass
class S1RunResult:
    """Return object summarising an S1 execution."""

    tile_index_path: Path
    tile_bounds_path: Path
    report_path: Path
    country_summary_path: Path
    rows_emitted: int


@dataclass(frozen=True)
class WorkerCountryPayload:
    """Serialized geometry payload passed to worker processes."""

    country_iso: str
    geometry_wkb: bytes


@dataclass(frozen=True)
class WorkerAssignment:
    """Inputs required for a worker process to enumerate its countries."""

    worker_id: int
    countries: Tuple[WorkerCountryPayload, ...]
    tile_temp_dir: Path
    bounds_temp_dir: Path
    raster_path: Path
    inclusion_rule: InclusionRule


@dataclass
class WorkerResult:
    """Result emitted by each worker process."""

    worker_id: int
    rows_emitted: int
    summaries: Dict[str, CountrySummary]
    tile_temp_dir: Path
    bounds_temp_dir: Path
    countries_processed: int
    cells_scanned_total: int
    cells_included_total: int
    wall_clock_seconds: float
    cpu_seconds: float


@dataclass
class WorkerRuntimeStats:
    """Telemetry summary for inclusion in PAT/run-report artefacts."""

    worker_id: int
    countries_processed: int
    rows_emitted: int
    cells_scanned_total: int
    wall_clock_seconds: float
    cpu_seconds: float

    @property
    def tiles_per_second(self) -> float | None:
        if self.wall_clock_seconds <= 0:
            return None
        return self.rows_emitted / self.wall_clock_seconds


class S1TileIndexRunner:
    """Public orchestration entry point for S1."""

    def run(self, config: RunnerConfig) -> S1RunResult:
        dictionary = config.dictionary or load_dictionary()
        data_root = config.data_root.resolve()
        parameter_hash = config.parameter_hash
        inclusion_rule = InclusionRule.parse(config.inclusion_rule)
        requested_workers = max(1, config.workers)

        iso_path = data_root / Path(
            render_dataset_path("iso3166_canonical_2024", template_args={}, dictionary=dictionary)
        )
        country_path = data_root / Path(
            render_dataset_path("world_countries", template_args={}, dictionary=dictionary)
        )
        raster_path = data_root / Path(
            render_dataset_path("population_raster_2025", template_args={}, dictionary=dictionary)
        )

        logger.info("S1: loading ISO canonical table from %s", iso_path)
        iso_table = load_iso_countries(iso_path)
        logger.info("S1: ISO table loaded (rows=%d)", iso_table.table.height)
        iso_codes = iso_table.codes

        logger.info("S1: loading world polygon surface from %s", country_path)
        country_polygons = load_country_polygons(country_path)
        logger.info("S1: country polygons ready (countries=%d)", len(country_polygons))

        logger.info("S1: loading population raster metadata from %s", raster_path)
        raster = load_population_raster(raster_path)
        logger.info(
            "S1: population raster ready (rows=%d, cols=%d)",
            raster.nrows,
            raster.ncols,
        )

        start_wall = time.perf_counter()
        start_cpu = time.process_time()

        eligible_countries = [country for country in country_polygons if country.country_iso in iso_codes]
        if not eligible_countries:
            raise S1RunError("No eligible countries found in country polygon surface")
        total_countries = len(eligible_countries)
        worker_target = min(requested_workers, total_countries)
        if worker_target < requested_workers:
            logger.info(
                "S1: requested %d workers but only %d eligible countries available; using %d workers",
                requested_workers,
                total_countries,
                worker_target,
            )
        logger.info(
            "S1: enumerating tiles (countries=%d, inclusion_rule=%s, workers=%d)",
            total_countries,
            inclusion_rule.value,
            worker_target,
        )
        tile_index_dir = resolve_dataset_path(
            "tile_index",
            base_path=data_root,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
        tile_bounds_dir = resolve_dataset_path(
            "tile_bounds",
            base_path=data_root,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
        if tile_index_dir.exists():
            raise S1RunError(f"Output partition already exists: {tile_index_dir}")
        if tile_bounds_dir.exists():
            raise S1RunError(f"Output partition already exists: {tile_bounds_dir}")

        if worker_target == 1:
            execution = self._run_single(
                inclusion_rule=inclusion_rule,
                iso_codes=iso_codes,
                country_polygons=country_polygons,
                raster=raster,
                tile_index_dir=tile_index_dir,
                tile_bounds_dir=tile_bounds_dir,
            )
        else:
            execution = self._run_multi(
                inclusion_rule=inclusion_rule,
                countries=eligible_countries,
                raster_path=raster_path,
                tile_index_dir=tile_index_dir,
                tile_bounds_dir=tile_bounds_dir,
                worker_count=worker_target,
            )

        tile_temp_dir = execution.tile_temp_dir
        bounds_temp_dir = execution.bounds_temp_dir
        tile_temp_dir.replace(tile_index_dir)
        bounds_temp_dir.replace(tile_bounds_dir)

        summaries = execution.summaries
        rows_emitted = execution.rows_emitted

        digest = compute_partition_digest(tile_index_dir)

        wall_elapsed = time.perf_counter() - start_wall
        cpu_elapsed = time.process_time() - start_cpu
        bytes_read_raster = _safe_stat_size(raster_path)
        bytes_read_vectors = sum(
            _safe_stat_size(path) for path in (iso_path, country_path)
        )
        worker_runtimes = execution.worker_runtimes or []
        workers_used = max(1, len(worker_runtimes))
        tiles_per_second_avg = None if wall_elapsed <= 0 else rows_emitted / wall_elapsed
        worker_tile_rates: list[dict[str, object]] = []
        for stats in worker_runtimes:
            rate = stats.tiles_per_second
            worker_tile_rates.append(
                {
                    "worker_id": stats.worker_id,
                    "countries": stats.countries_processed,
                    "tiles": stats.rows_emitted,
                    "tiles_per_second": rate,
                }
            )
            logger.info(
                "S1: worker %d complete (countries=%d, tiles=%d, tiles/sec=%s)",
                stats.worker_id,
                stats.countries_processed,
                stats.rows_emitted,
                f"{rate:.1f}" if rate is not None else "n/a",
            )

        report_dir = data_root / "reports" / "l1" / "s1_tile_index" / f"parameter_hash={parameter_hash}"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "run_report.json"
        summary_path = report_dir / "country_summaries.jsonl"

        ingress_versions = {
            "iso3166_canonical_2024": get_dataset_entry(
                "iso3166_canonical_2024", dictionary=dictionary
            ).get("version", "unknown"),
            "world_countries": get_dataset_entry("world_countries", dictionary=dictionary).get("version", "unknown"),
            "population_raster_2025": get_dataset_entry(
                "population_raster_2025", dictionary=dictionary
            ).get("version", "unknown"),
        }
        run_report = RunReport(
            parameter_hash=parameter_hash,
            predicate=inclusion_rule.value,
            ingress_versions=ingress_versions,
            grid_dims={"nrows": raster.nrows, "ncols": raster.ncols},
            countries_total=len(summaries),
            rows_emitted=rows_emitted,
            determinism_receipt={
                "partition_path": str(tile_index_dir),
                "sha256_hex": digest,
            },
            pat={
                "wall_clock_seconds_total": wall_elapsed,
                "cpu_seconds_total": cpu_elapsed,
                "countries_processed": len(summaries),
                "cells_scanned_total": sum(s.cells_visited for s in summaries.values()),
                "cells_included_total": rows_emitted,
                "bytes_read_raster_total": bytes_read_raster,
                "bytes_read_vectors_total": bytes_read_vectors,
                "max_worker_rss_bytes": None,
                "open_files_peak": None,
                "workers_used": workers_used,
                "chunk_size": _CHUNK_SIZE,
                "io_baseline_raster_bps": None,
                "io_baseline_vectors_bps": None,
                "tiles_per_second_avg": tiles_per_second_avg,
                "tiles_per_second_per_worker": worker_tile_rates,
            },
        )
        report_path.write_text(json.dumps(run_report.to_dict(), indent=2), encoding="utf-8")
        self._write_country_summaries(summary_path, summaries.values())

        return S1RunResult(
            tile_index_path=tile_index_dir,
            tile_bounds_path=tile_bounds_dir,
            report_path=report_path,
            country_summary_path=summary_path,
            rows_emitted=rows_emitted,
        )

    def _run_single(
        self,
        *,
        inclusion_rule: InclusionRule,
        iso_codes: frozenset[str] | IsoCountryTable,
        country_polygons: CountryPolygons,
        raster: PopulationRaster,
        tile_index_dir: Path,
        tile_bounds_dir: Path,
    ) -> ExecutionResult:
        tile_temp_dir = tile_index_dir.parent / f".tmp.tile_index.{uuid4().hex}"
        bounds_temp_dir = tile_bounds_dir.parent / f".tmp.tile_bounds.{uuid4().hex}"
        tile_temp_dir.mkdir(parents=True, exist_ok=False)
        bounds_temp_dir.mkdir(parents=True, exist_ok=False)

        tile_writer = _ParquetBatchWriter(
            temp_dir=tile_temp_dir,
            columns=_TILE_COLUMNS,
            schema=_TILE_SCHEMA,
            batch_size=_BATCH_SIZE,
        )
        bounds_writer = _ParquetBatchWriter(
            temp_dir=bounds_temp_dir,
            columns=_BOUNDS_COLUMNS,
            schema=_BOUNDS_SCHEMA,
            batch_size=_BATCH_SIZE,
        )

        processed_count = sum(1 for country in country_polygons if country.country_iso in iso_codes)
        start_wall = time.perf_counter()
        start_cpu = time.process_time()
        try:
            summaries, rows_emitted = self._enumerate_tiles(
                inclusion_rule,
                iso_codes,
                country_polygons,
                raster,
                tile_writer=tile_writer,
                bounds_writer=bounds_writer,
                worker_label="main",
            )
            tile_writer.close()
            bounds_writer.close()
        except Exception:
            tile_writer.abort()
            bounds_writer.abort()
            shutil.rmtree(tile_temp_dir, ignore_errors=True)
            shutil.rmtree(bounds_temp_dir, ignore_errors=True)
            raise

        wall_elapsed = time.perf_counter() - start_wall
        cpu_elapsed = time.process_time() - start_cpu
        logger.info(
            "S1: tile enumeration finished (countries_with_tiles=%d, tiles=%d)",
            len(summaries),
            rows_emitted,
        )
        worker_stats = WorkerRuntimeStats(
            worker_id=0,
            countries_processed=processed_count,
            rows_emitted=rows_emitted,
            cells_scanned_total=sum(s.cells_visited for s in summaries.values()),
            wall_clock_seconds=wall_elapsed,
            cpu_seconds=cpu_elapsed,
        )

        return ExecutionResult(
            tile_temp_dir=tile_temp_dir,
            bounds_temp_dir=bounds_temp_dir,
            summaries=summaries,
            rows_emitted=rows_emitted,
            worker_runtimes=[worker_stats],
        )

    def _run_multi(
        self,
        *,
        inclusion_rule: InclusionRule,
        countries: Sequence[CountryPolygon],
        raster_path: Path,
        tile_index_dir: Path,
        tile_bounds_dir: Path,
        worker_count: int,
    ) -> ExecutionResult:
        merge_token = uuid4().hex
        tile_merge_dir = tile_index_dir.parent / f".tmp.tile_index.merge.{merge_token}"
        bounds_merge_dir = tile_bounds_dir.parent / f".tmp.tile_bounds.merge.{merge_token}"
        tile_merge_dir.mkdir(parents=True, exist_ok=False)
        bounds_merge_dir.mkdir(parents=True, exist_ok=False)

        partitions = _partition_countries(countries, worker_count)
        assignments: list[WorkerAssignment] = []
        for worker_id, batch in enumerate(partitions):
            tile_worker_dir = tile_index_dir.parent / f".tmp.tile_index.worker-{worker_id}.{uuid4().hex}"
            bounds_worker_dir = tile_bounds_dir.parent / f".tmp.tile_bounds.worker-{worker_id}.{uuid4().hex}"
            tile_worker_dir.mkdir(parents=True, exist_ok=False)
            bounds_worker_dir.mkdir(parents=True, exist_ok=False)
            logger.info(
                "S1: assigning worker %d (%d countries: %s)",
                worker_id,
                len(batch),
                ", ".join(sorted(country.country_iso for country in batch)) or "<none>",
            )
            payloads = tuple(
                WorkerCountryPayload(country_iso=country.country_iso, geometry_wkb=country.geometry.wkb)
                for country in batch
            )
            assignments.append(
                WorkerAssignment(
                    worker_id=worker_id,
                    countries=payloads,
                    tile_temp_dir=tile_worker_dir,
                    bounds_temp_dir=bounds_worker_dir,
                    raster_path=raster_path,
                    inclusion_rule=inclusion_rule,
                )
            )

        worker_results: list[WorkerResult] = []
        try:
            worker_results = _execute_worker_pool(assignments)
            worker_results.sort(key=lambda result: result.worker_id)
            _merge_worker_outputs(worker_results, tile_merge_dir, bounds_merge_dir)
        except Exception:
            shutil.rmtree(tile_merge_dir, ignore_errors=True)
            shutil.rmtree(bounds_merge_dir, ignore_errors=True)
            raise
        finally:
            for assignment in assignments:
                shutil.rmtree(assignment.tile_temp_dir, ignore_errors=True)
                shutil.rmtree(assignment.bounds_temp_dir, ignore_errors=True)

        summaries: Dict[str, CountrySummary] = {}
        rows_emitted = 0
        for result in worker_results:
            summaries.update(result.summaries)
            rows_emitted += result.rows_emitted

        worker_stats = [
            WorkerRuntimeStats(
                worker_id=result.worker_id,
                countries_processed=result.countries_processed,
                rows_emitted=result.rows_emitted,
                cells_scanned_total=result.cells_scanned_total,
                wall_clock_seconds=result.wall_clock_seconds,
                cpu_seconds=result.cpu_seconds,
            )
            for result in worker_results
        ]

        logger.info(
            "S1: tile enumeration finished (countries_with_tiles=%d, tiles=%d, workers=%d)",
            len(summaries),
            rows_emitted,
            worker_count,
        )

        return ExecutionResult(
            tile_temp_dir=tile_merge_dir,
            bounds_temp_dir=bounds_merge_dir,
            summaries=summaries,
            rows_emitted=rows_emitted,
            worker_runtimes=worker_stats,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _enumerate_tiles(
        self,
        inclusion_rule: InclusionRule,
        iso_codes: frozenset[str],
        country_polygons: CountryPolygons,
        raster: PopulationRaster,
        *,
        tile_writer: "_ParquetBatchWriter",
        bounds_writer: "_ParquetBatchWriter",
        worker_label: str | None = None,
    ) -> tuple[Dict[str, CountrySummary], int]:
        if isinstance(iso_codes, IsoCountryTable):
            iso_domain = iso_codes.codes
        else:
            iso_domain = iso_codes
        prefix = f"[{worker_label}] " if worker_label else ""
        summaries: Dict[str, CountrySummary] = {}
        pixel_area_cache = np.full(raster.nrows, np.nan, dtype=np.float64)
        total_countries = len(country_polygons)
        processed = 0
        rows_emitted = 0
        hole_cache: Dict[str, list[tuple[Polygon, int]]] = {}

        for idx, country in enumerate(country_polygons, start=1):
            processed += 1
            iso = country.country_iso
            if iso not in iso_domain:
                continue
            summary = CountrySummary(country_iso=iso)
            row_min, row_max, col_min, col_max = _raster_window_for_geometry(raster, country.geometry)
            if row_max < row_min or col_max < col_min:
                logger.warning(
                    "%sS1: skipping %s due to empty raster window (rows=%d..%d cols=%d..%d)",
                    prefix,
                    iso,
                    row_min,
                    row_max,
                    col_min,
                    col_max,
                )
                continue
            logger.info(
                "%sS1: country %d/%d (%s) window rows=%d..%d cols=%d..%d",
                prefix,
                idx,
                total_countries,
                iso,
                row_min,
                row_max,
                col_min,
                col_max,
            )
            window_height = row_max - row_min + 1
            window_width = col_max - col_min + 1
            base_window = rasterio.windows.Window(col_min, row_min, window_width, window_height)
            window_transform = rasterio.windows.transform(base_window, raster.transform)
            geom_for_mask = _mask_geometry_for_rule(country.geometry, raster, inclusion_rule)
            window_mask = rasterio.features.rasterize(
                [(mapping(geom_for_mask), 1)],
                out_shape=(window_height, window_width),
                transform=window_transform,
                fill=0,
                dtype="uint8",
                all_touched=inclusion_rule is InclusionRule.ANY_OVERLAP,
            )
            hole_shapes = hole_cache.get(iso)
            if hole_shapes is None:
                hole_shapes = _extract_hole_shapes(country.geometry)
                hole_cache[iso] = hole_shapes
            hole_mask_full: np.ndarray | None = None
            if hole_shapes:
                hole_mask_full = rasterio.features.rasterize(
                    hole_shapes,
                    out_shape=(window_height, window_width),
                    transform=window_transform,
                    fill=0,
                    dtype="uint8",
                    all_touched=False,
                )
            chunk_counter = 0

            for row_start in range(row_min, row_max + 1, _CHUNK_SIZE):
                chunk_height = min(_CHUNK_SIZE, row_max - row_start + 1)
                local_row_start = row_start - row_min
                local_row_end = local_row_start + chunk_height
                for col_start in range(col_min, col_max + 1, _CHUNK_SIZE):
                    chunk_width = min(_CHUNK_SIZE, col_max - col_start + 1)
                    local_col_start = col_start - col_min
                    local_col_end = local_col_start + chunk_width
                    chunk_counter += 1
                    chunk_start = time.perf_counter()

                    chunk_mask = window_mask[local_row_start:local_row_end, local_col_start:local_col_end]
                    included_mask = chunk_mask == 1
                    included_count = int(included_mask.sum())
                    hole_count = 0
                    if hole_mask_full is not None:
                        chunk_holes = hole_mask_full[local_row_start:local_row_end, local_col_start:local_col_end]
                        hole_count = int(chunk_holes.sum())
                    chunk_total = chunk_height * chunk_width
                    summary.record_batch(
                        visited=chunk_total,
                        included=included_count,
                        hole_count=hole_count,
                    )
                    if included_count == 0:
                        logger.info(
                            "%sS1: chunk %d country=%s rows=%d..%d cols=%d..%d visited=%d included=%d duration=%.2fs",
                            prefix,
                            chunk_counter,
                            iso,
                            row_start,
                            row_start + chunk_height - 1,
                            col_start,
                            col_start + chunk_width - 1,
                            chunk_total,
                            0,
                            time.perf_counter() - chunk_start,
                        )
                        continue

                    flat_indices = np.flatnonzero(included_mask)
                    local_rows = flat_indices // chunk_width
                    local_cols = flat_indices % chunk_width
                    rows_abs = row_start + local_rows
                    cols_abs = col_start + local_cols

                    missing_rows_mask = np.isnan(pixel_area_cache[rows_abs])
                    if np.any(missing_rows_mask):
                        for row_value in np.unique(rows_abs[missing_rows_mask]):
                            pixel_area_cache[row_value] = raster.tile_area(int(row_value), 0)
                    pixel_areas = pixel_area_cache[rows_abs]

                    tile_ids = (
                        rows_abs.astype(np.uint64, copy=False) * np.uint64(raster.ncols)
                        + cols_abs.astype(np.uint64, copy=False)
                    )

                    centroid_lon, centroid_lat = xy(
                        raster.transform,
                        rows_abs,
                        cols_abs,
                        offset="center",
                    )
                    centroid_lon = np.asarray(centroid_lon, dtype=np.float64)
                    centroid_lat = np.asarray(centroid_lat, dtype=np.float64)

                    west_vals, north_vals = xy(
                        raster.transform,
                        rows_abs,
                        cols_abs,
                        offset="ul",
                    )
                    east_vals, south_vals = xy(
                        raster.transform,
                        rows_abs,
                        cols_abs,
                        offset="lr",
                    )
                    west_vals = np.asarray(west_vals, dtype=np.float64)
                    north_vals = np.asarray(north_vals, dtype=np.float64)
                    east_vals = np.asarray(east_vals, dtype=np.float64)
                    south_vals = np.asarray(south_vals, dtype=np.float64)
                    west = np.minimum(west_vals, east_vals)
                    east = np.maximum(west_vals, east_vals)
                    south = np.minimum(south_vals, north_vals)
                    north = np.maximum(south_vals, north_vals)

                    country_values = np.full(included_count, iso, dtype=object)
                    rule_values = np.full(included_count, inclusion_rule.value, dtype=object)
                    rows_uint32 = rows_abs.astype(np.uint32, copy=False)
                    cols_uint32 = cols_abs.astype(np.uint32, copy=False)

                    tile_writer.append_batch(
                        country_iso=country_values,
                        tile_id=tile_ids,
                        inclusion_rule=rule_values,
                        raster_row=rows_uint32,
                        raster_col=cols_uint32,
                        centroid_lon=centroid_lon,
                        centroid_lat=centroid_lat,
                        pixel_area_m2=pixel_areas,
                    )
                    bounds_writer.append_batch(
                        country_iso=country_values,
                        tile_id=tile_ids,
                        west_lon=west,
                        east_lon=east,
                        south_lat=south,
                        north_lat=north,
                    )

                    summary.record_included_tiles(tile_ids)
                    rows_emitted += included_count

                    duration = time.perf_counter() - chunk_start
                    logger.info(
                        "%sS1: chunk %d country=%s rows=%d..%d cols=%d..%d visited=%d included=%d duration=%.2fs",
                        prefix,
                        chunk_counter,
                        iso,
                        row_start,
                        row_start + chunk_height - 1,
                        col_start,
                        col_start + chunk_width - 1,
                        chunk_total,
                        included_count,
                        duration,
                    )

            if summary.cells_visited:
                summaries[iso] = summary
            if total_countries > 0 and (processed % 25 == 0 or processed == total_countries):
                logger.info(
                    "%sS1: processed %d/%d countries (tiles_emitted=%d)",
                    prefix,
                    processed,
                    total_countries,
                    rows_emitted,
                )

        return summaries, rows_emitted

    def _write_country_summaries(self, target: Path, summaries: Iterable[CountrySummary]) -> None:
        lines = []
        for summary in summaries:
            payload = {
                "country_iso": summary.country_iso,
                "cells_visited": summary.cells_visited,
                "cells_included": summary.cells_included,
                "cells_excluded_outside": summary.cells_excluded_outside,
                "cells_excluded_hole": summary.cells_excluded_hole,
                "tile_id_min": summary.tile_id_min,
                "tile_id_max": summary.tile_id_max,
            }
            lines.append(json.dumps(payload))
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


class _ParquetBatchWriter:
    """Buffer rows and emit Parquet shards to keep memory usage bounded."""

    def __init__(
        self,
        *,
        temp_dir: Path,
        columns: Sequence[str],
        schema: Mapping[str, pl.DataType],
        batch_size: int,
    ) -> None:
        self.temp_dir = temp_dir
        self.columns = tuple(columns)
        self.schema = dict(schema)
        self.batch_size = batch_size
        self._buffers: dict[str, list[np.ndarray]] = {column: [] for column in self.columns}
        self._rows_buffered = 0
        self._rows_written = 0
        self._shard_index = 0
        self._closed = False

    @property
    def rows_written(self) -> int:
        return self._rows_written

    def append_row(self, **row: object) -> None:
        self.append_batch(**{column: [row[column]] for column in self.columns})

    def append_batch(self, **columns: object) -> None:
        if self._closed:
            raise RuntimeError("Cannot append to a closed writer")
        if set(columns.keys()) != set(self.columns):
            missing = set(self.columns) - set(columns.keys())
            extra = set(columns.keys()) - set(self.columns)
            raise ValueError(
                f"Batch columns must match schema. Missing={sorted(missing)}, extra={sorted(extra)}"
            )
        sample_column = self.columns[0]
        batch_len = len(columns[sample_column])  # type: ignore[arg-type]
        if batch_len == 0:
            return
        for column in self.columns:
            values = columns[column]
            if len(values) != batch_len:  # type: ignore[arg-type]
                raise ValueError(f"Column '{column}' length mismatch in append_batch")
            array = np.asarray(values)
            self._buffers[column].append(array)
        self._rows_buffered += batch_len
        if self._rows_buffered >= self.batch_size:
            self._flush()

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        if not any(self.temp_dir.glob("*.parquet")):
            empty = self._empty_frame()
            empty.write_parquet(self.temp_dir / "part-00000.parquet", compression="zstd")
            logger.info(
                "S1: %s produced no rows; wrote empty shard",
                self.temp_dir.name,
            )
        self._closed = True

    def abort(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._closed = True

    def _flush(self) -> None:
        if self._rows_buffered == 0:
            return
        data: dict[str, np.ndarray] = {}
        for column in self.columns:
            buffers = self._buffers[column]
            if not buffers:
                raise RuntimeError(f"No buffered data present for column '{column}' during flush")
            data[column] = buffers[0] if len(buffers) == 1 else np.concatenate(buffers)
            self._buffers[column] = []
        df = pl.DataFrame(data).with_columns(
            [pl.col(column).cast(dtype, strict=False) for column, dtype in self.schema.items()]
        )
        shard_name = f"part-{self._shard_index:05d}.parquet"
        shard_path = self.temp_dir / shard_name
        df.write_parquet(shard_path, compression="zstd")
        self._rows_written += len(df)
        self._shard_index += 1
        self._rows_buffered = 0
        logger.info(
            "S1: flushed %d rows to %s/%s (total=%d)",
            len(df),
            self.temp_dir.name,
            shard_name,
            self._rows_written,
        )
        for column in self.columns:
            self._buffers[column] = []

    def _empty_frame(self) -> pl.DataFrame:
        series = {
            column: pl.Series(column, [], dtype=self.schema[column])
            for column in self.columns
        }
        return pl.DataFrame(series)


def _raster_window_for_geometry(raster: PopulationRaster, geometry: Polygon) -> tuple[int, int, int, int]:
    rows, cols = _geometry_rowcol_bounds(raster, geometry)
    if not rows or not cols:
        minx, miny, maxx, maxy = geometry.bounds
        fallback_coords = [
            (minx, miny),
            (minx, maxy),
            (maxx, miny),
            (maxx, maxy),
            ((minx + maxx) / 2, (miny + maxy) / 2),
        ]
        for lon, lat in fallback_coords:
            try:
                row, col = rowcol(raster.transform, lon, lat)
            except Exception:
                continue
            rows.append(int(row))
            cols.append(int(col))
    if not rows or not cols:
        return (0, raster.nrows - 1, 0, raster.ncols - 1)
    row_min = max(0, min(rows) - 1)
    row_max = min(raster.nrows - 1, max(rows) + 1)
    col_min = max(0, min(cols) - 1)
    col_max = min(raster.ncols - 1, max(cols) + 1)
    return row_min, row_max, col_min, col_max


def _geometry_rowcol_bounds(raster: PopulationRaster, geometry: BaseGeometry) -> tuple[list[int], list[int]]:
    rows: list[int] = []
    cols: list[int] = []
    if geometry.is_empty:
        return rows, cols

    def _collect(poly: Polygon) -> None:
        coords = np.asarray(poly.exterior.coords, dtype=np.float64)
        if coords.size == 0:
            return
        for lon, lat in coords:
            try:
                row, col = rowcol(raster.transform, float(lon), float(lat))
            except Exception:
                continue
            rows.append(int(row))
            cols.append(int(col))

    if geometry.geom_type == "Polygon":
        _collect(geometry)
    elif geometry.geom_type == "MultiPolygon":
        for geom in geometry.geoms:  # type: ignore[attr-defined]
            _collect(geom)

    return rows, cols


def _extract_hole_shapes(geometry: BaseGeometry) -> list[tuple[Polygon, int]]:
    shapes: list[tuple[Polygon, int]] = []

    def _from_polygon(poly: Polygon) -> None:
        for ring in poly.interiors:
            try:
                hole = Polygon(ring)
            except ValueError:
                continue
            if not hole.is_empty:
                shapes.append((mapping(hole), 1))

    if geometry.geom_type == "Polygon":
        _from_polygon(geometry)
    elif geometry.geom_type == "MultiPolygon":
        for poly in geometry.geoms:  # type: ignore[attr-defined]
            _from_polygon(poly)

    return shapes


def _mask_geometry_for_rule(
    geometry: BaseGeometry, raster: PopulationRaster, rule: InclusionRule
) -> BaseGeometry:
    if rule is not InclusionRule.ANY_OVERLAP:
        return geometry
    pixel_width = abs(raster.transform.a)
    pixel_height = abs(raster.transform.e)
    buffer_distance = 0.5 * max(pixel_width, pixel_height)
    return geometry.buffer(buffer_distance)


def _partition_countries(
    countries: Sequence[CountryPolygon], worker_count: int
) -> list[list[CountryPolygon]]:
    countries_list = list(countries)
    total = len(countries_list)
    worker_count = max(1, min(worker_count, total))
    if worker_count == 1:
        return [countries_list]
    partitions: list[list[CountryPolygon]] = []
    base, remainder = divmod(total, worker_count)
    start = 0
    for idx in range(worker_count):
        size = base + (1 if idx < remainder else 0)
        end = start + size
        partitions.append(countries_list[start:end])
        start = end
    return [partition for partition in partitions if partition]


def _execute_worker_pool(assignments: Sequence[WorkerAssignment]) -> list[WorkerResult]:
    if not assignments:
        return []
    results: list[WorkerResult] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(assignments)) as executor:
        future_map = {executor.submit(_worker_entry, assignment): assignment.worker_id for assignment in assignments}
        try:
            for future in concurrent.futures.as_completed(future_map):
                results.append(future.result())
        except Exception:
            for future in future_map:
                future.cancel()
            raise
    return results


def _worker_entry(assignment: WorkerAssignment) -> WorkerResult:
    _configure_worker_logging()
    tile_writer = _ParquetBatchWriter(
        temp_dir=assignment.tile_temp_dir,
        columns=_TILE_COLUMNS,
        schema=_TILE_SCHEMA,
        batch_size=_BATCH_SIZE,
    )
    bounds_writer = _ParquetBatchWriter(
        temp_dir=assignment.bounds_temp_dir,
        columns=_BOUNDS_COLUMNS,
        schema=_BOUNDS_SCHEMA,
        batch_size=_BATCH_SIZE,
    )
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    try:
        raster = load_population_raster(assignment.raster_path)
        polygons = _build_country_polygons_from_payloads(assignment.countries)
        iso_codes = frozenset(payload.country_iso for payload in assignment.countries)
        runner = S1TileIndexRunner()
        summaries, rows_emitted = runner._enumerate_tiles(
            assignment.inclusion_rule,
            iso_codes,
            polygons,
            raster,
            tile_writer=tile_writer,
            bounds_writer=bounds_writer,
            worker_label=f"worker-{assignment.worker_id}",
        )
        tile_writer.close()
        bounds_writer.close()
    except Exception:
        tile_writer.abort()
        bounds_writer.abort()
        raise
    wall_elapsed = time.perf_counter() - start_wall
    cpu_elapsed = time.process_time() - start_cpu
    cells_scanned_total = sum(summary.cells_visited for summary in summaries.values())
    return WorkerResult(
        worker_id=assignment.worker_id,
        rows_emitted=rows_emitted,
        summaries=summaries,
        tile_temp_dir=assignment.tile_temp_dir,
        bounds_temp_dir=assignment.bounds_temp_dir,
        countries_processed=len(assignment.countries),
        cells_scanned_total=cells_scanned_total,
        cells_included_total=rows_emitted,
        wall_clock_seconds=wall_elapsed,
        cpu_seconds=cpu_elapsed,
    )


def _build_country_polygons_from_payloads(
    payloads: Sequence[WorkerCountryPayload],
) -> CountryPolygons:
    mapping: Dict[str, CountryPolygon] = {}
    for payload in payloads:
        geometry = wkb.loads(payload.geometry_wkb)
        mapping[payload.country_iso] = CountryPolygon(
            country_iso=payload.country_iso,
            geometry=geometry,
            prepared=prepare_geometry(geometry),
        )
    return CountryPolygons(mapping)


def _merge_worker_outputs(
    worker_results: Sequence[WorkerResult],
    tile_target_dir: Path,
    bounds_target_dir: Path,
) -> None:
    tile_index = 0
    bounds_index = 0
    for result in worker_results:
        tile_index = _move_parquet_shards(result.tile_temp_dir, tile_target_dir, tile_index)
        bounds_index = _move_parquet_shards(result.bounds_temp_dir, bounds_target_dir, bounds_index)
    if tile_index == 0:
        _write_empty_shard(tile_target_dir, _TILE_COLUMNS, _TILE_SCHEMA)
    if bounds_index == 0:
        _write_empty_shard(bounds_target_dir, _BOUNDS_COLUMNS, _BOUNDS_SCHEMA)


def _move_parquet_shards(source_dir: Path, target_dir: Path, start_index: int) -> int:
    shard_index = start_index
    shard_paths = sorted(source_dir.glob("*.parquet"))
    for shard_path in shard_paths:
        target_name = f"part-{shard_index:05d}.parquet"
        shutil.move(str(shard_path), target_dir / target_name)
        shard_index += 1
    return shard_index


def _write_empty_shard(target_dir: Path, columns: Sequence[str], schema: Mapping[str, pl.DataType]) -> None:
    series = {column: pl.Series(column, [], dtype=schema[column]) for column in columns}
    frame = pl.DataFrame(series)
    frame.write_parquet(target_dir / "part-00000.parquet", compression="zstd")


def _configure_worker_logging() -> None:
    """Ensure worker processes emit INFO logs like the parent."""

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    else:
        root.setLevel(logging.INFO)
    logging.getLogger(__name__).setLevel(logging.INFO)


__all__ = ["RunnerConfig", "S1RunResult", "S1TileIndexRunner", "S1RunError", "compute_partition_digest"]


def compute_partition_digest(partition_dir: Path) -> str:
    if not partition_dir.exists():
        raise S1RunError(f"Partition directory missing for digest computation: {partition_dir}")
    files = sorted(
        (p for p in partition_dir.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(partition_dir).as_posix(),
    )
    digest = hashlib.sha256()
    for file_path in files:
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _safe_stat_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0
