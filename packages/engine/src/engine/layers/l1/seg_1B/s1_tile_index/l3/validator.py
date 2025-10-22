"""Validation harness for Segment 1B S1 (Tile Index)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from ..l0.loaders import (
    CountryPolygons,
    IsoCountryTable,
    PopulationRaster,
    load_country_polygons,
    load_iso_countries,
    load_population_raster,
)
from ..l1.geometry import compute_tile_metrics
from ..l1.predicates import InclusionRule, evaluate_inclusion
from ..l2.runner import compute_partition_digest
from ...shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)


class ValidationError(RuntimeError):
    """Raised when S1 outputs violate the specification."""


@dataclass
class ValidatorConfig:
    data_root: Path
    parameter_hash: str
    inclusion_rule: str | None = None
    dictionary: Mapping[str, object] | None = None


class S1TileIndexValidator:
    """Validates the materialised artefacts for S1."""

    COORD_ABS_TOL = 1e-7
    AREA_REL_TOL = 1e-8

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()
        data_root = config.data_root.resolve()
        parameter_hash = config.parameter_hash

        run_report = self._load_run_report(data_root, parameter_hash)
        predicate_value = config.inclusion_rule or run_report.get("predicate")
        if predicate_value is None:
            raise ValidationError("Inclusion rule must be provided either via config or run report")
        inclusion_rule = InclusionRule.parse(predicate_value)

        iso_path = data_root / Path(render_dataset_path("iso3166_canonical_2024", template_args={}, dictionary=dictionary))
        polygons_path = data_root / Path(render_dataset_path("world_countries", template_args={}, dictionary=dictionary))
        raster_path = data_root / Path(render_dataset_path("population_raster_2025", template_args={}, dictionary=dictionary))

        iso_table = load_iso_countries(iso_path)
        polygons = load_country_polygons(polygons_path)
        raster = load_population_raster(raster_path)

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
        tile_df = self._read_dataframe(tile_index_dir)
        bounds_df = self._read_dataframe(tile_bounds_dir)

        self._validate_schema(tile_df, bounds_df)
        self._validate_sort(tile_df, ["country_iso", "tile_id"])
        self._validate_tile_bounds_alignment(tile_df, bounds_df)
        self._validate_iso_domain(tile_df, iso_table)
        self._validate_centroid_bounds(tile_df)
        self._validate_area(tile_df)
        self._validate_raster_indices(tile_df, raster)
        self._validate_tile_id_formula(tile_df, raster)
        self._validate_geometry(tile_df, inclusion_rule, polygons, raster)
        self._validate_determinism_receipt(tile_index_dir, run_report)

    # ------------------------------------------------------------------ #
    # Core validation steps
    # ------------------------------------------------------------------ #

    def _validate_schema(self, tile_df: pl.DataFrame, bounds_df: pl.DataFrame) -> None:
        if tile_df.is_empty():
            return
        required_columns = {
            "country_iso",
            "tile_id",
            "inclusion_rule",
            "raster_row",
            "raster_col",
            "centroid_lon",
            "centroid_lat",
            "pixel_area_m2",
        }
        missing = required_columns - set(tile_df.columns)
        if missing:
            raise ValidationError(f"tile_index missing required columns: {sorted(missing)}")
        bounds_columns = {"country_iso", "tile_id", "west_lon", "east_lon", "south_lat", "north_lat"}
        missing_bounds = bounds_columns - set(bounds_df.columns)
        if missing_bounds:
            raise ValidationError(f"tile_bounds missing required columns: {sorted(missing_bounds)}")

    def _validate_sort(self, frame: pl.DataFrame, sort_keys: list[str]) -> None:
        if frame.is_empty():
            return
        sorted_frame = frame.sort(sort_keys)
        if frame.rows() != sorted_frame.rows():
            raise ValidationError(f"Dataset is not sorted by {sort_keys}")

    def _validate_tile_bounds_alignment(self, tile_df: pl.DataFrame, bounds_df: pl.DataFrame) -> None:
        if tile_df.height != bounds_df.height:
            raise ValidationError("tile_bounds row count does not match tile_index")
        merged = tile_df.select("country_iso", "tile_id").join(
            bounds_df.select("country_iso", "tile_id"),
            on=["country_iso", "tile_id"],
            how="left",
        )
        if merged.height != tile_df.height:
            raise ValidationError("tile_bounds does not contain a matching row for every tile_index entry")

    def _validate_iso_domain(self, tile_df: pl.DataFrame, iso_table: IsoCountryTable) -> None:
        iso_codes = iso_table.codes
        unknown = (
            tile_df.select(pl.col("country_iso").unique())
            .filter(~pl.col("country_iso").is_in(list(iso_codes)))
            .to_series()
        )
        if unknown.len() > 0:
            raise ValidationError(f"tile_index contains ISO codes not present in reference: {unknown.to_list()}")

    def _validate_centroid_bounds(self, tile_df: pl.DataFrame) -> None:
        violations = tile_df.filter(
            (pl.col("centroid_lon") < -180.0)
            | (pl.col("centroid_lon") > 180.0)
            | (pl.col("centroid_lat") < -90.0)
            | (pl.col("centroid_lat") > 90.0)
        )
        if violations.height > 0:
            raise ValidationError("Centroid coordinates fall outside WGS84 bounds")

    def _validate_area(self, tile_df: pl.DataFrame) -> None:
        non_positive = tile_df.filter(pl.col("pixel_area_m2") <= 0)
        if non_positive.height > 0:
            raise ValidationError("Found non-positive pixel_area_m2 values")

    def _validate_raster_indices(self, tile_df: pl.DataFrame, raster: PopulationRaster) -> None:
        out_of_bounds = tile_df.filter(
            (pl.col("raster_row") < 0)
            | (pl.col("raster_col") < 0)
            | (pl.col("raster_row") >= raster.nrows)
            | (pl.col("raster_col") >= raster.ncols)
        )
        if out_of_bounds.height > 0:
            raise ValidationError("Raster indices fall outside raster dimensions")

    def _validate_tile_id_formula(self, tile_df: pl.DataFrame, raster: PopulationRaster) -> None:
        expected_df = tile_df.select(
            "country_iso",
            "tile_id",
            "raster_row",
            "raster_col",
            expected=pl.col("raster_row").cast(pl.UInt64) * raster.ncols + pl.col("raster_col").cast(pl.UInt64),
        )
        mismatched = expected_df.filter(pl.col("tile_id") != pl.col("expected"))
        if mismatched.height > 0:
            raise ValidationError("tile_id does not match row-major formula for some rows")

    def _validate_geometry(
        self,
        tile_df: pl.DataFrame,
        inclusion_rule: InclusionRule,
        polygons: CountryPolygons,
        raster: PopulationRaster,
    ) -> None:
        for row in tile_df.iter_rows(named=True):
            country_iso = row["country_iso"]
            try:
                polygon = polygons[country_iso]
            except KeyError as exc:
                raise ValidationError(f"Missing polygon geometry for country '{country_iso}'") from exc

            metrics = compute_tile_metrics(
                raster,
                int(row["raster_row"]),
                int(row["raster_col"]),
            )

            if not math.isclose(metrics.centroid_lon, float(row["centroid_lon"]), abs_tol=self.COORD_ABS_TOL):
                raise ValidationError(f"Centroid longitude mismatch for country {country_iso}, tile {metrics.tile_id}")
            if not math.isclose(metrics.centroid_lat, float(row["centroid_lat"]), abs_tol=self.COORD_ABS_TOL):
                raise ValidationError(f"Centroid latitude mismatch for country {country_iso}, tile {metrics.tile_id}")
            if not math.isclose(
                metrics.pixel_area_m2, float(row["pixel_area_m2"]), rel_tol=self.AREA_REL_TOL, abs_tol=1e-6
            ):
                raise ValidationError(f"pixel_area_m2 mismatch for country {country_iso}, tile {metrics.tile_id}")

            if not evaluate_inclusion(inclusion_rule, polygon, metrics):
                raise ValidationError(
                    f"Inclusion predicate failed for country {country_iso}, tile {metrics.tile_id}"
                )

    def _validate_determinism_receipt(self, partition_dir: Path, run_report: Mapping[str, object]) -> None:
        expected = run_report.get("determinism_receipt")
        if not isinstance(expected, Mapping):
            raise ValidationError("Run report missing determinism_receipt entry")
        expected_digest = expected.get("sha256_hex")
        if not isinstance(expected_digest, str):
            raise ValidationError("determinism_receipt.sha256_hex missing from run report")
        observed = compute_partition_digest(partition_dir)
        if observed != expected_digest:
            raise ValidationError("Determinism receipt hash does not match run report")

    # ------------------------------------------------------------------ #
    # I/O helpers
    # ------------------------------------------------------------------ #

    def _load_run_report(self, data_root: Path, parameter_hash: str) -> Mapping[str, object]:
        report_path = data_root / "reports" / "l1" / "s1_tile_index" / f"parameter_hash={parameter_hash}" / "run_report.json"
        if not report_path.exists():
            return {}
        return json.loads(report_path.read_text(encoding="utf-8"))

    def _read_dataframe(self, partition_dir: Path) -> pl.DataFrame:
        if not partition_dir.exists():
            raise ValidationError(f"Expected partition directory missing: {partition_dir}")
        files = sorted(p for p in partition_dir.glob("*.parquet"))
        if not files:
            raise ValidationError(f"No parquet files found under partition {partition_dir}")
        return pl.concat([pl.read_parquet(file) for file in files], how="vertical_relaxed")


__all__ = ["ValidatorConfig", "S1TileIndexValidator", "ValidationError"]
