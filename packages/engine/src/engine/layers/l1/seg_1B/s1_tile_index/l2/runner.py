"""L2 orchestration for Segment 1B S1 (Tile Index)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence
from uuid import uuid4

import hashlib

import polars as pl
from rasterio.transform import rowcol
from shapely.geometry import Point, Polygon

from ..l0.loaders import (
    CountryPolygon,
    CountryPolygons,
    IsoCountryTable,
    PopulationRaster,
    load_country_polygons,
    load_iso_countries,
    load_population_raster,
)
from ..l1.geometry import TileMetrics, compute_tile_metrics
from ..l1.predicates import InclusionRule, evaluate_inclusion
from ...shared.dictionary import (
    get_dataset_entry,
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)


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

        iso_table = load_iso_countries(iso_path)
        country_polygons = load_country_polygons(country_path)
        raster = load_population_raster(raster_path)

        tile_records, bounds_records, summaries = self._enumerate_tiles(
            inclusion_rule,
            iso_table,
            country_polygons,
            raster,
        )

        tile_df = self._build_tile_index_frame(tile_records)
        bounds_df = self._build_tile_bounds_frame(bounds_records)

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

        self._write_partition(tile_df, tile_index_dir)
        self._write_partition(bounds_df, tile_bounds_dir)

        digest = compute_partition_digest(tile_index_dir)

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
            rows_emitted=len(tile_records),
            determinism_receipt={
                "partition_path": str(tile_index_dir),
                "sha256_hex": digest,
            },
            pat={
                "wall_clock_seconds_total": 0,
                "cpu_seconds_total": 0,
                "countries_processed": len(summaries),
                "cells_scanned_total": sum(s.cells_visited for s in summaries.values()),
                "cells_included_total": len(tile_records),
                "bytes_read_raster_total": 0,
                "bytes_read_vectors_total": 0,
                "max_worker_rss_bytes": 0,
                "open_files_peak": 0,
                "workers_used": 0,
                "chunk_size": 0,
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
            rows_emitted=len(tile_records),
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
    ) -> tuple[list[dict], list[dict], Dict[str, CountrySummary]]:
        iso_domain = iso_table.codes
        tile_records: list[dict] = []
        bounds_records: list[dict] = []
        summaries: Dict[str, CountrySummary] = {}

        for country in country_polygons:
            if country.country_iso not in iso_domain:
                continue
            summary = CountrySummary(country_iso=country.country_iso)
            row_min, row_max, col_min, col_max = _raster_window_for_geometry(raster, country.geometry)
            for row in range(row_min, row_max + 1):
                for col in range(col_min, col_max + 1):
                    metrics = compute_tile_metrics(raster, row, col)
                    point = Point(metrics.centroid_lon, metrics.centroid_lat)
                    included = evaluate_inclusion(inclusion_rule, country, metrics)
                    if included:
                        summary.register_included(metrics)
                        tile_records.append(
                            {
                                "country_iso": country.country_iso,
                                "tile_id": metrics.tile_id,
                                "inclusion_rule": inclusion_rule.value,
                                "raster_row": metrics.raster_row,
                                "raster_col": metrics.raster_col,
                                "centroid_lon": metrics.centroid_lon,
                                "centroid_lat": metrics.centroid_lat,
                                "pixel_area_m2": metrics.pixel_area_m2,
                            }
                        )
                        bounds_records.append(
                            {
                                "country_iso": country.country_iso,
                                "tile_id": metrics.tile_id,
                                "west_lon": metrics.bounds.west,
                                "east_lon": metrics.bounds.east,
                                "south_lat": metrics.bounds.south,
                                "north_lat": metrics.bounds.north,
                            }
                        )
                    else:
                        summary.register_excluded(_point_in_hole(country, point))
            if summary.cells_visited:
                summaries[country.country_iso] = summary

        return tile_records, bounds_records, summaries

    def _build_tile_index_frame(self, records: Sequence[Mapping[str, object]]) -> pl.DataFrame:
        if not records:
            schema = {
                "country_iso": pl.String,
                "tile_id": pl.UInt64,
                "inclusion_rule": pl.String,
                "raster_row": pl.UInt32,
                "raster_col": pl.UInt32,
                "centroid_lon": pl.Float64,
                "centroid_lat": pl.Float64,
                "pixel_area_m2": pl.Float64,
            }
            return pl.DataFrame(schema=schema).with_columns(pl.col("tile_id").cast(pl.UInt64))

        df = pl.DataFrame(records).with_columns(
            pl.col("tile_id").cast(pl.UInt64),
            pl.col("raster_row").cast(pl.UInt32),
            pl.col("raster_col").cast(pl.UInt32),
            pl.col("centroid_lon").cast(pl.Float64),
            pl.col("centroid_lat").cast(pl.Float64),
            pl.col("pixel_area_m2").cast(pl.Float64),
        )
        return df.sort(["country_iso", "tile_id"])

    def _build_tile_bounds_frame(self, records: Sequence[Mapping[str, object]]) -> pl.DataFrame:
        if not records:
            schema = {
                "country_iso": pl.String,
                "tile_id": pl.UInt64,
                "west_lon": pl.Float64,
                "east_lon": pl.Float64,
                "south_lat": pl.Float64,
                "north_lat": pl.Float64,
            }
            return pl.DataFrame(schema=schema).with_columns(pl.col("tile_id").cast(pl.UInt64))

        df = pl.DataFrame(records).with_columns(
            pl.col("tile_id").cast(pl.UInt64),
            pl.col("west_lon").cast(pl.Float64),
            pl.col("east_lon").cast(pl.Float64),
            pl.col("south_lat").cast(pl.Float64),
            pl.col("north_lat").cast(pl.Float64),
        )
        return df.sort(["country_iso", "tile_id"])

    def _write_partition(self, frame: pl.DataFrame, final_dir: Path) -> None:
        final_dir = final_dir.resolve()
        if final_dir.exists():
            raise S1RunError(f"Output partition already exists: {final_dir}")
        temp_dir = final_dir.parent / f".tmp.{uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            frame.write_parquet(temp_dir / "part-00000.parquet", compression="zstd")
            temp_dir.replace(final_dir)
        except Exception as exc:  # noqa: BLE001 - atomic publish enforcement
            if temp_dir.exists():
                for child in temp_dir.glob("**/*"):
                    if child.is_file():
                        child.unlink()
                temp_dir.rmdir()
            raise S1RunError(f"Failed to publish partition '{final_dir}': {exc}") from exc

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
