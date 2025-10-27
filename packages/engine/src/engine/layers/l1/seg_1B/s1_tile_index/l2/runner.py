"""L2 orchestration for Segment 1B S1 (Tile Index)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence
from uuid import uuid4

import polars as pl
from rasterio.transform import rowcol
from shapely.geometry import Point, Polygon

from ..l0.loaders import (
    CountryPolygon,
    CountryPolygons,
    IsoCountryTable,
    PopulationRaster,
    TileBounds,
    load_country_polygons,
    load_iso_countries,
    load_population_raster,
)
from ..l1.geometry import TileMetrics
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


class S1RunError(RuntimeError):
    """Raised when S1 orchestration encounters a contract violation."""


@dataclass
class RunnerConfig:
    """Configuration inputs required to execute S1."""

    data_root: Path
    parameter_hash: str
    inclusion_rule: str = "center"
    dictionary: Mapping[str, object] | None = None


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

    def register_included(self, metrics: TileMetrics) -> None:
        self.cells_visited += 1
        self.cells_included += 1
        tile_id = metrics.tile_id
        if self.tile_id_min is None or tile_id < self.tile_id_min:
            self.tile_id_min = tile_id
        if self.tile_id_max is None or tile_id > self.tile_id_max:
            self.tile_id_max = tile_id

    def register_excluded(self, hole: bool) -> None:
        self.cells_visited += 1
        if hole:
            self.cells_excluded_hole += 1
        else:
            self.cells_excluded_outside += 1


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


class S1TileIndexRunner:
    """Public orchestration entry point for S1."""

    def run(self, config: RunnerConfig) -> S1RunResult:
        dictionary = config.dictionary or load_dictionary()
        data_root = config.data_root.resolve()
        parameter_hash = config.parameter_hash
        inclusion_rule = InclusionRule.parse(config.inclusion_rule)

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

        total_countries = len(country_polygons)
        logger.info(
            "S1: enumerating tiles (countries=%d, inclusion_rule=%s)",
            total_countries,
            inclusion_rule.value,
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

        try:
            summaries, rows_emitted = self._enumerate_tiles(
                inclusion_rule,
                iso_table,
                country_polygons,
                raster,
                tile_writer=tile_writer,
                bounds_writer=bounds_writer,
            )
            tile_writer.close()
            bounds_writer.close()
        except Exception:
            tile_writer.abort()
            bounds_writer.abort()
            raise
        logger.info(
            "S1: tile enumeration finished (countries_with_tiles=%d, tiles=%d)",
            len(summaries),
            rows_emitted,
        )

        tile_temp_dir.replace(tile_index_dir)
        bounds_temp_dir.replace(tile_bounds_dir)

        digest = compute_partition_digest(tile_index_dir)

        wall_elapsed = time.perf_counter() - start_wall
        cpu_elapsed = time.process_time() - start_cpu
        bytes_read_raster = _safe_stat_size(raster_path)
        bytes_read_vectors = sum(
            _safe_stat_size(path) for path in (iso_path, country_path)
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
                "workers_used": 1,
                "chunk_size": rows_emitted,
                "io_baseline_raster_bps": None,
                "io_baseline_vectors_bps": None,
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

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _enumerate_tiles(
        self,
        inclusion_rule: InclusionRule,
        iso_table: IsoCountryTable,
        country_polygons: CountryPolygons,
        raster: PopulationRaster,
        *,
        tile_writer: "_ParquetBatchWriter",
        bounds_writer: "_ParquetBatchWriter",
    ) -> tuple[Dict[str, CountrySummary], int]:
        iso_domain = iso_table.codes
        summaries: Dict[str, CountrySummary] = {}

        total_countries = len(country_polygons)
        processed = 0
        rows_emitted = 0
        for country in country_polygons:
            if country.country_iso not in iso_domain:
                processed += 1
                continue
            summary = CountrySummary(country_iso=country.country_iso)
            row_min, row_max, col_min, col_max = _raster_window_for_geometry(raster, country.geometry)
            for row in range(row_min, row_max + 1):
                for col in range(col_min, col_max + 1):
                    tile_id = raster.tile_id(row, col)
                    centroid_lon, centroid_lat = raster.tile_centroid(row, col)
                    centroid_point = Point(centroid_lon, centroid_lat)
                    included = False
                    bounds: TileBounds | None = None

                    if inclusion_rule is InclusionRule.CENTER:
                        included = country.prepared.covers(centroid_point)
                    else:
                        bounds = raster.tile_bounds(row, col)
                        tile_polygon = bounds.to_polygon()
                        if country.prepared.intersects(tile_polygon):
                            intersection = country.geometry.intersection(tile_polygon)
                            included = intersection.area > 0.0

                    if included:
                        if bounds is None:
                            bounds = raster.tile_bounds(row, col)
                        pixel_area = raster.tile_area(row, col)
                        metrics = TileMetrics(
                            raster_row=row,
                            raster_col=col,
                            tile_id=tile_id,
                            centroid_lon=centroid_lon,
                            centroid_lat=centroid_lat,
                            pixel_area_m2=pixel_area,
                            bounds=bounds,
                        )
                        summary.register_included(metrics)
                        tile_writer.append_row(
                            country_iso=country.country_iso,
                            tile_id=metrics.tile_id,
                            inclusion_rule=inclusion_rule.value,
                            raster_row=metrics.raster_row,
                            raster_col=metrics.raster_col,
                            centroid_lon=metrics.centroid_lon,
                            centroid_lat=metrics.centroid_lat,
                            pixel_area_m2=metrics.pixel_area_m2,
                        )
                        bounds_writer.append_row(
                            country_iso=country.country_iso,
                            tile_id=metrics.tile_id,
                            west_lon=metrics.bounds.west,
                            east_lon=metrics.bounds.east,
                            south_lat=metrics.bounds.south,
                            north_lat=metrics.bounds.north,
                        )
                        rows_emitted += 1
                    else:
                        summary.register_excluded(_point_in_hole(country, centroid_point))
            if summary.cells_visited:
                summaries[country.country_iso] = summary
            processed += 1
            if total_countries > 0 and (processed % 25 == 0 or processed == total_countries):
                logger.info(
                    "S1: processed %d/%d countries (tiles_emitted=%d)",
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
        self._buffers = {column: [] for column in self.columns}
        self._rows_written = 0
        self._shard_index = 0
        self._closed = False

    @property
    def rows_written(self) -> int:
        return self._rows_written

    def append_row(self, **row: object) -> None:
        if self._closed:
            raise RuntimeError("Cannot append to a closed writer")
        for column in self.columns:
            self._buffers[column].append(row[column])
        if len(self._buffers[self.columns[0]]) >= self.batch_size:
            self._flush()

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        if not any(self.temp_dir.glob("*.parquet")):
            empty = self._empty_frame()
            empty.write_parquet(self.temp_dir / "part-00000.parquet", compression="zstd")
        self._closed = True

    def abort(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._closed = True

    def _flush(self) -> None:
        batch_len = len(self._buffers[self.columns[0]])
        if batch_len == 0:
            return
        data = {column: self._buffers[column] for column in self.columns}
        df = pl.DataFrame(data).with_columns(
            [pl.col(column).cast(dtype, strict=False) for column, dtype in self.schema.items()]
        )
        shard_path = self.temp_dir / f"part-{self._shard_index:05d}.parquet"
        df.write_parquet(shard_path, compression="zstd")
        self._rows_written += batch_len
        self._shard_index += 1
        for column in self.columns:
            self._buffers[column] = []

    def _empty_frame(self) -> pl.DataFrame:
        series = {
            column: pl.Series(column, [], dtype=self.schema[column])
            for column in self.columns
        }
        return pl.DataFrame(series)


def _raster_window_for_geometry(raster: PopulationRaster, geometry: Polygon) -> tuple[int, int, int, int]:
    minx, miny, maxx, maxy = geometry.bounds
    coordinates = [
        (minx, miny),
        (minx, maxy),
        (maxx, miny),
        (maxx, maxy),
        ((minx + maxx) / 2, (miny + maxy) / 2),
    ]
    rows: list[int] = []
    cols: list[int] = []
    for lon, lat in coordinates:
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


def _point_in_hole(country: CountryPolygon, point: Point) -> bool:
    geom = country.geometry
    if geom.geom_type == "Polygon":
        return _polygon_contains_hole_point(geom, point)
    if geom.geom_type == "MultiPolygon":
        return any(_polygon_contains_hole_point(poly, point) for poly in geom.geoms)  # type: ignore[attr-defined]
    return False


def _polygon_contains_hole_point(polygon: Polygon, point: Point) -> bool:
    for ring in polygon.interiors:
        try:
            hole = Polygon(ring)
        except ValueError:
            continue
        if hole.contains(point):
            return True
    return False


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
