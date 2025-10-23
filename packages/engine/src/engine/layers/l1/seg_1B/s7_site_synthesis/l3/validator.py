"""Validator for Segment 1B state-7 site synthesis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

import polars as pl

from ..exceptions import err
from ..l0.datasets import (
    OutletCataloguePartition,
    S5AssignmentPartition,
    S6JitterPartition,
    TileBoundsPartition,
    VerifiedGate,
    load_outlet_catalogue,
    load_s5_assignments,
    load_s6_jitter,
    load_tile_bounds,
    verify_consumer_gate,
)
from ...shared.dictionary import load_dictionary, resolve_dataset_path


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S7 outputs."""

    data_root: Path
    seed: str
    manifest_fingerprint: str
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    run_summary_path: Optional[Path] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


class S7SiteSynthesisValidator:
    """Validate S7 outputs according to the specification."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()

        dataset_path = resolve_dataset_path(
            "s7_site_synthesis",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
        if not dataset_path.exists():
            raise err(
                "E701_ROW_MISSING",
                f"s7_site_synthesis partition missing at '{dataset_path}'",
            )

        dataset = self._read_dataset(dataset_path)
        self._validate_sort(dataset)
        self._ensure_unique_pk(dataset)
        self._validate_identity(dataset_path, dataset, config)

        gate = verify_consumer_gate(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )

        assignments = load_s5_assignments(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        jitter = load_s6_jitter(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        tile_bounds = load_tile_bounds(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        outlet = load_outlet_catalogue(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )

        self._validate_row_parity(dataset, assignments.frame)
        self._validate_parity_with_s6(dataset, jitter.frame)
        self._validate_geometry(dataset, jitter.frame, tile_bounds.frame)
        self._validate_coverage(dataset, outlet.frame)

        run_summary_path = (
            config.run_summary_path
            if config.run_summary_path is not None
            else dataset_path.parent / "s7_run_summary.json"
        )
        self._validate_run_summary(
            run_summary_path=run_summary_path,
            dataset=dataset,
            assignments=assignments.frame,
            jitter=jitter.frame,
            outcome_gate=gate,
        )

    # -- dataset helpers -------------------------------------------------

    def _read_dataset(self, path: Path) -> pl.DataFrame:
        return (
            pl.scan_parquet(str(path / "*.parquet"))
            .select(
                [
                    "merchant_id",
                    "legal_country_iso",
                    "site_order",
                    "tile_id",
                    "lon_deg",
                    "lat_deg",
                ]
            )
            .collect()
        )

    def _validate_sort(self, frame: pl.DataFrame) -> None:
        if frame.height == 0:
            return
        if frame.rows() != frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows():
            raise err(
                "E706_WRITER_SORT_VIOLATION",
                "s7_site_synthesis must be sorted by ['merchant_id','legal_country_iso','site_order']",
            )

    def _ensure_unique_pk(self, frame: pl.DataFrame) -> None:
        dupes = (
            frame.group_by(["merchant_id", "legal_country_iso", "site_order"])
            .agg(pl.len().alias("count"))
            .filter(pl.col("count") > 1)
        )
        if dupes.height:
            raise err("E703_DUP_KEY", "duplicate site keys found in s7_site_synthesis")

    def _validate_identity(
        self,
        dataset_path: Path,
        frame: pl.DataFrame,
        config: ValidatorConfig,
    ) -> None:
        path_parts = _partition_tokens(dataset_path)
        expected = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
            "parameter_hash": config.parameter_hash,
        }
        if path_parts != expected:
            raise err(
                "E705_PARTITION_OR_IDENTITY",
                f"s7_site_synthesis path tokens {path_parts} != expected {expected}",
            )

    def _validate_row_parity(self, dataset: pl.DataFrame, assignments: pl.DataFrame) -> None:
        keys = ["merchant_id", "legal_country_iso", "site_order"]
        missing = assignments.select(keys).join(dataset.select(keys), on=keys, how="anti")
        if missing.height:
            raise err(
                "E701_ROW_MISSING",
                "s7_site_synthesis missing site rows present in s5_site_tile_assignment",
            )
        extra = dataset.select(keys).join(assignments.select(keys), on=keys, how="anti")
        if extra.height:
            raise err(
                "E702_ROW_EXTRA",
                "s7_site_synthesis contains site rows not present in s5_site_tile_assignment",
            )

    def _validate_parity_with_s6(self, dataset: pl.DataFrame, jitter: pl.DataFrame) -> None:
        keys = ["merchant_id", "legal_country_iso", "site_order"]
        missing = jitter.select(keys).join(dataset.select(keys), on=keys, how="anti")
        if missing.height:
            raise err(
                "E701_ROW_MISSING",
                "s7_site_synthesis missing site rows present in s6_site_jitter",
            )
        extra = dataset.select(keys).join(jitter.select(keys), on=keys, how="anti")
        if extra.height:
            raise err(
                "E702_ROW_EXTRA",
                "s7_site_synthesis contains site rows not present in s6_site_jitter",
            )

    def _validate_geometry(
        self,
        dataset: pl.DataFrame,
        jitter: pl.DataFrame,
        tile_bounds: pl.DataFrame,
    ) -> None:
        jitter_map = {
            (int(row["merchant_id"]), str(row["legal_country_iso"]).upper(), int(row["site_order"])): (
                float(row["delta_lon_deg"]),
                float(row["delta_lat_deg"]),
                int(row["tile_id"]),
            )
            for row in jitter.iter_rows(named=True)
        }

        tile_map = {
            (str(row["country_iso"]).upper(), int(row["tile_id"])): (
                float(row["min_lon_deg"]),
                float(row["max_lon_deg"]),
                float(row["min_lat_deg"]),
                float(row["max_lat_deg"]),
                float(row["centroid_lon_deg"]),
                float(row["centroid_lat_deg"]),
            )
            for row in tile_bounds.iter_rows(named=True)
        }

        for row in dataset.iter_rows(named=True):
            key = (int(row["merchant_id"]), str(row["legal_country_iso"]).upper(), int(row["site_order"]))
            jitter_row = jitter_map.get(key)
            if jitter_row is None:
                raise err("E701_ROW_MISSING", f"missing jitter row for site {key}")
            (delta_lon, delta_lat, tile_id) = jitter_row

            tile_key = (key[1], tile_id)
            tile_record = tile_map.get(tile_key)
            if tile_record is None:
                raise err("E709_TILE_FK_VIOLATION", f"tile {tile_key} missing from tile_bounds")

            min_lon, max_lon, min_lat, max_lat, centroid_lon, centroid_lat = tile_record
            reconstructed_lon = centroid_lon + delta_lon
            reconstructed_lat = centroid_lat + delta_lat

            if not _almost_equal(reconstructed_lon, float(row["lon_deg"])) or not _almost_equal(
                reconstructed_lat, float(row["lat_deg"])
            ):
                raise err(
                    "E707_POINT_OUTSIDE_PIXEL",
                    f"reconstructed coordinates ({reconstructed_lon},{reconstructed_lat}) "
                    f"do not match stored values {row['lon_deg']},{row['lat_deg']}",
                )

            if not _point_inside_pixel(reconstructed_lon, reconstructed_lat, min_lon, max_lon, min_lat, max_lat):
                raise err(
                    "E707_POINT_OUTSIDE_PIXEL",
                    f"reconstructed point ({reconstructed_lon},{reconstructed_lat}) outside "
                    f"tile bounds for {tile_key}",
                )

    def _validate_coverage(self, dataset: pl.DataFrame, outlet: pl.DataFrame) -> None:
        dataset_keys = _key_set(dataset)
        outlet_keys = _key_set(outlet)
        if dataset_keys != outlet_keys:
            raise err(
                "E708_1A_COVERAGE_FAIL",
                "s7_site_synthesis site keyset does not match outlet_catalogue",
            )

    def _validate_run_summary(
        self,
        *,
        run_summary_path: Path,
        dataset: pl.DataFrame,
        assignments: pl.DataFrame,
        jitter: pl.DataFrame,
        outcome_gate: VerifiedGate,
    ) -> None:
        if not run_summary_path.exists():
            raise err("E705_PARTITION_OR_IDENTITY", f"s7 run summary missing at '{run_summary_path}'")

        try:
            payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise err("E704_SCHEMA_VIOLATION", f"s7 run summary is not valid JSON: {exc}") from exc

        if not isinstance(payload, Mapping):
            raise err("E704_SCHEMA_VIOLATION", "s7 run summary must be a JSON object")

        counts = payload.get("counts")
        if not isinstance(counts, Mapping):
            raise err("E704_SCHEMA_VIOLATION", "run summary missing counts block")
        if counts.get("sites_total_s5") != assignments.height:
            raise err("E704_SCHEMA_VIOLATION", "run summary sites_total_s5 mismatch")
        if counts.get("sites_total_s6") != jitter.height:
            raise err("E704_SCHEMA_VIOLATION", "run summary sites_total_s6 mismatch")
        if counts.get("sites_total_s7") != dataset.height:
            raise err("E704_SCHEMA_VIOLATION", "run summary sites_total_s7 mismatch")

        validation_counters = payload.get("validation_counters")
        if not isinstance(validation_counters, Mapping):
            raise err("E704_SCHEMA_VIOLATION", "run summary missing validation counters")
        expected_ok = dataset.height
        for field, expected in (
            ("fk_tile_ok_count", expected_ok),
            ("inside_pixel_ok_count", expected_ok),
            ("coverage_1a_ok_count", expected_ok),
        ):
            if int(validation_counters.get(field, -1)) != expected:
                raise err("E704_SCHEMA_VIOLATION", f"run summary field '{field}' mismatch")
        for field in ("fk_tile_fail_count", "inside_pixel_fail_count", "coverage_1a_miss_count", "path_embed_mismatches"):
            if int(validation_counters.get(field, 0)) != 0:
                raise err("E704_SCHEMA_VIOLATION", f"run summary field '{field}' expected zero")

        consumer_gate = payload.get("consumer_gate", {})
        if consumer_gate.get("flag_sha256_hex") != outcome_gate.flag_sha256_hex:
            raise err("E704_SCHEMA_VIOLATION", "run summary consumer gate hash mismatch")


def _key_set(frame: pl.DataFrame) -> set[Tuple[int, str, int]]:
    return {
        (int(row[0]), str(row[1]).upper(), int(row[2]))
        for row in frame.select(["merchant_id", "legal_country_iso", "site_order"]).iter_rows()
    }


def _partition_tokens(path: Path) -> Mapping[str, str]:
    parts = {
        part.split("=")[0]: part.split("=", 1)[1]
        for part in path.parts
        if "=" in part
    }
    return {
        "seed": parts.get("seed", ""),
        "manifest_fingerprint": parts.get("fingerprint", ""),
        "parameter_hash": parts.get("parameter_hash", ""),
    }


def _point_inside_pixel(
    lon_deg: float,
    lat_deg: float,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
) -> bool:
    lon = lon_deg
    if max_lon < min_lon:
        adjusted_max = max_lon + 360.0
        lon = lon if lon >= min_lon else lon + 360.0
        max_lon = adjusted_max
    epsilon = 1e-9
    lon_ok = (min_lon - epsilon) <= lon <= (max_lon + epsilon)
    lat_ok = (min_lat - epsilon) <= lat_deg <= (max_lat + epsilon)
    return lon_ok and lat_ok


def _almost_equal(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


__all__ = ["S7SiteSynthesisValidator", "ValidatorConfig"]
