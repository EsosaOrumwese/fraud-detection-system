"""Validator for S2 tile weights."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err
from ..l0 import load_tile_index_partition
from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import load_iso_countries
from ..l1 import compute_tile_masses, quantise_tile_weights, validate_tile_index
from ..l2.runner import PatCounters


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S2 tile weights."""

    data_root: Path
    parameter_hash: str
    dictionary: Mapping[str, object] | None = None
    run_report_path: Path | None = None
    basis: str | None = None
    dp: int | None = None


class S2TileWeightsValidator:
    """Performs contract validation for S2 outputs."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()
        data_root = config.data_root
        parameter_hash = config.parameter_hash

        report_path = config.run_report_path or resolve_dataset_path(
            "s2_run_report",
            base_path=data_root,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )

        run_report: Mapping[str, object] | None = None
        if report_path.exists():
            run_report = json.loads(report_path.read_text(encoding="utf-8"))

        basis = config.basis or (run_report.get("basis") if run_report else None)
        dp = config.dp or (run_report.get("dp") if run_report else None)
        if basis is None or dp is None:
            raise err("E105_NORMALIZATION", "basis and dp must be provided for validation")
        dp = int(dp)

        dataset_path = resolve_dataset_path(
            "tile_weights",
            base_path=data_root,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
        if not dataset_path.exists():
            raise err(
                "E108_WRITER_HYGIENE",
                f"tile_weights partition '{dataset_path}' missing",
            )

        parquet_files = sorted(p for p in dataset_path.glob("*.parquet") if p.is_file())
        if not parquet_files:
            raise err(
                "E108_WRITER_HYGIENE",
                f"tile_weights partition '{dataset_path}' contains no parquet files",
            )

        dataset_frame = pl.read_parquet(parquet_files)
        required_columns = {"country_iso", "tile_id", "weight_fp", "dp", "basis"}
        missing = required_columns.difference(set(dataset_frame.columns))
        if missing:
            raise err("E108_WRITER_HYGIENE", f"tile_weights missing columns: {sorted(missing)}")

        key_pairs = list(
            zip(
                dataset_frame.get_column("country_iso").to_list(),
                dataset_frame.get_column("tile_id").to_list(),
            )
        )
        if key_pairs != sorted(key_pairs):
            raise err(
                "E108_WRITER_HYGIENE",
                "tile_weights partition must be sorted by ['country_iso', 'tile_id']",
            )
        dataset_frame = dataset_frame.sort(["country_iso", "tile_id"])

        unique_dp = dataset_frame.select(pl.col("dp").unique()).get_column("dp").to_list()
        if len(unique_dp) != 1 or int(unique_dp[0]) != dp:
            raise err("E105_NORMALIZATION", "dp column inconsistent with expected value")

        basis_values = dataset_frame.select(pl.col("basis").unique()).get_column("basis").to_list()
        if any(value is not None and str(value) != basis for value in basis_values):
            raise err("E105_NORMALIZATION", "basis column inconsistent with expected value")

        tile_index = load_tile_index_partition(
            base_path=data_root,
            parameter_hash=parameter_hash,
            dictionary=dictionary,
        )
        iso_path = resolve_dataset_path(
            "iso3166_canonical_2024",
            base_path=data_root,
            template_args={},
            dictionary=dictionary,
        )
        iso_table = load_iso_countries(iso_path)
        validate_tile_index(partition=tile_index, iso_table=iso_table)

        expected_rows = tile_index.rows
        if dataset_frame.height != expected_rows:
            raise err(
                "E102_FK_MISMATCH",
                "tile_weights row count does not match tile_index coverage",
            )

        tile_keys = tile_index.frame.select(["country_iso", "tile_id"])
        extras = dataset_frame.select(["country_iso", "tile_id"]).join(
            tile_keys, on=["country_iso", "tile_id"], how="anti"
        )
        if extras.height > 0:
            raise err("E102_FK_MISMATCH", "tile_weights contains keys not present in tile_index")

        missing = tile_keys.join(
            dataset_frame.select(["country_iso", "tile_id"]),
            on=["country_iso", "tile_id"],
            how="anti",
        )
        if missing.height > 0:
            raise err("E102_FK_MISMATCH", "tile_weights missing rows from tile_index")

        dummy_pat = PatCounters(tile_index_bytes_reference=tile_index.byte_size)
        mass_frame = compute_tile_masses(
            tile_index=tile_index,
            basis=basis,
            data_root=data_root,
            dictionary=dictionary,
            pat=dummy_pat,
        )
        expected = quantise_tile_weights(mass_frame=mass_frame, dp=dp)

        comparison = dataset_frame.join(
            expected.frame.select(["country_iso", "tile_id", "weight_fp"]).rename(
                {"weight_fp": "expected_weight_fp"}
            ),
            on=["country_iso", "tile_id"],
            how="inner",
        )
        if comparison.height != dataset_frame.height:
            raise err("E102_FK_MISMATCH", "tile_weights failed FK coverage check")

        weight_mismatch = comparison.filter(
            pl.col("weight_fp") != pl.col("expected_weight_fp")
        )
        if weight_mismatch.height > 0:
            raise err("E105_NORMALIZATION", "weight_fp values do not match expected quantisation")

        if run_report and "determinism_receipt" in run_report:
            expected_receipt = run_report["determinism_receipt"]
            digest = compute_partition_digest(dataset_path)
            if expected_receipt.get("sha256_hex") != digest:
                raise err("E107_DETERMINISM", "determinism receipt mismatch for tile_weights")


__all__ = ["S2TileWeightsValidator", "ValidatorConfig"]
