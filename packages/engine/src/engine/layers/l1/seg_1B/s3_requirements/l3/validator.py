"""Validator for S3 requirements outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import get_dataset_entry, load_dictionary, resolve_dataset_path
from ..exceptions import err
from ..l0 import (
    load_iso_countries,
    load_outlet_catalogue_partition,
    load_tile_weights_partition,
)
from ..l1.validators import (
    aggregate_site_requirements,
    ensure_iso_fk,
    ensure_positive_counts,
    ensure_weights_coverage,
)

EXPECTED_COLUMNS = {"merchant_id", "legal_country_iso", "n_sites"}
SORT_KEYS = ["merchant_id", "legal_country_iso"]


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S3 requirements outputs."""

    data_root: Path
    seed: str
    manifest_fingerprint: str
    parameter_hash: str
    dictionary: Mapping[str, object] | None = None
    run_report_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


class S3RequirementsValidator:
    """Perform contract validation for the S3 requirements dataset."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()

        dataset_path = resolve_dataset_path(
            "s3_requirements",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
        if not dataset_path.exists():
            raise err("E305_SCHEMA_INVALID", f"s3_requirements partition '{dataset_path}' missing")

        frame = _read_dataset(dataset_path)
        _validate_columns(frame)
        _ensure_sorted(frame)
        _ensure_unique_keys(frame)
        _ensure_positive_counts(frame)

        outlet = load_outlet_catalogue_partition(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        tile_weights = load_tile_weights_partition(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        iso_table = load_iso_countries(base_path=config.data_root, dictionary=dictionary)
        if "region" in iso_table.table.columns:
            synthetic_codes = frozenset(
                iso_table.table
                .with_columns(pl.col("region").cast(pl.Utf8).str.to_uppercase().alias("region_norm"))
                .filter(pl.col("region_norm") == "SYNTHETIC")
                .get_column("country_iso")
                .to_list()
            )
        else:
            synthetic_codes = frozenset()
        if synthetic_codes:
            synthetic_present = (
                frame.filter(pl.col("legal_country_iso").is_in(sorted(synthetic_codes)))
                .get_column("legal_country_iso")
                .to_list()
            )
            if synthetic_present:
                raise err(
                    "E305_SCHEMA_INVALID",
                    f"s3_requirements contains synthetic ISO codes: {sorted(set(synthetic_present))}",
                )

        expected = aggregate_site_requirements(outlet.frame)
        ensure_positive_counts(expected)
        ensure_iso_fk(expected, set(iso_table.codes))
        if synthetic_codes:
            expected = expected.filter(~pl.col("legal_country_iso").is_in(sorted(synthetic_codes)))
        ensure_weights_coverage(
            expected,
            tile_weights.frame.get_column("country_iso").cast(pl.Utf8).to_list(),
            ignored_countries=synthetic_codes,
        )

        _ensure_counts_match(frame, expected)

        run_report_path = config.run_report_path or resolve_dataset_path(
            "s3_run_report",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
        _validate_run_report(
            report_path=run_report_path,
            dataset_path=dataset_path,
            frame=frame,
            outlet_rows=outlet.frame.height,
            dictionary=dictionary,
            config=config,
        )


def _read_dataset(path: Path) -> pl.DataFrame:
    pattern = _parquet_pattern(path)
    return pl.scan_parquet(pattern).collect()


def _parquet_pattern(path: Path) -> str:
    if path.is_dir():
        return str(path / "*.parquet")
    if path.suffix == ".parquet":
        return str(path)
    raise err("E305_SCHEMA_INVALID", f"s3_requirements path '{path}' is neither directory nor parquet file")


def _validate_columns(frame: pl.DataFrame) -> None:
    columns = set(frame.columns)
    if columns != EXPECTED_COLUMNS:
        if EXPECTED_COLUMNS.issubset(columns):
            extras = sorted(columns.difference(EXPECTED_COLUMNS))
            raise err("E305_SCHEMA_EXTRAS", f"s3_requirements contains unexpected columns: {extras}")
        missing = sorted(EXPECTED_COLUMNS.difference(columns))
        raise err("E305_SCHEMA_INVALID", f"s3_requirements missing required columns: {missing}")


def _ensure_sorted(frame: pl.DataFrame) -> None:
    if frame.rows() != frame.sort(SORT_KEYS).rows():
        raise err(
            "E310_UNSORTED",
            "s3_requirements partition must be sorted by ['merchant_id','legal_country_iso']",
        )


def _ensure_unique_keys(frame: pl.DataFrame) -> None:
    dupes = (
        frame.group_by(SORT_KEYS)
        .agg(pl.len().alias("row_count"))
        .filter(pl.col("row_count") > 1)
    )
    if dupes.height:
        raise err(
            "E307_PK_DUPLICATE",
            f"s3_requirements contains duplicate keys: {dupes.select(SORT_KEYS).to_dicts()[:3]}",
        )


def _ensure_positive_counts(frame: pl.DataFrame) -> None:
    if (frame.get_column("n_sites") < 1).any():
        raise err("E304_ZERO_SITES_ROW", "s3_requirements contains zero-count rows")


def _ensure_counts_match(frame: pl.DataFrame, expected: pl.DataFrame) -> None:
    expected = expected.sort(SORT_KEYS)
    expected = expected.rename({"n_sites": "expected_n_sites"})

    merged = frame.sort(SORT_KEYS).join(expected, on=SORT_KEYS, how="full")

    missing_pairs = merged.filter(
        pl.col("n_sites").is_null() | pl.col("expected_n_sites").is_null()
    )
    if missing_pairs.height:
        raise err(
            "E308_COUNTS_MISMATCH",
            "s3_requirements does not align with outlet_catalogue pairs",
        )

    mismatched = merged.filter(pl.col("n_sites") != pl.col("expected_n_sites"))
    if mismatched.height:
        raise err(
            "E308_COUNTS_MISMATCH",
            "s3_requirements n_sites do not match outlet_catalogue counts",
        )


def _validate_run_report(
    *,
    report_path: Path,
    dataset_path: Path,
    frame: pl.DataFrame,
    outlet_rows: int,
    dictionary: Mapping[str, object],
    config: ValidatorConfig,
) -> None:
    if not report_path.exists():
        raise err("E313_NONDETERMINISTIC_OUTPUT", f"s3 run report missing at '{report_path}'")

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("E313_NONDETERMINISTIC_OUTPUT", f"s3 run report invalid JSON: {exc}") from exc

    required_fields = [
        "seed",
        "manifest_fingerprint",
        "parameter_hash",
        "rows_emitted",
        "merchants_total",
        "countries_total",
        "source_rows_total",
        "ingress_versions",
        "determinism_receipt",
    ]
    for field in required_fields:
        if field not in payload:
            raise err("E313_NONDETERMINISTIC_OUTPUT", f"s3 run report missing field '{field}'")

    if payload["seed"] != config.seed:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report seed mismatch")
    if payload["manifest_fingerprint"] != config.manifest_fingerprint:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report manifest_fingerprint mismatch")
    if payload["parameter_hash"] != config.parameter_hash:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report parameter_hash mismatch")

    if int(payload["rows_emitted"]) != frame.height:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report rows_emitted mismatch")
    merchants_total = frame.select(pl.col("merchant_id").n_unique()).item()  # type: ignore[no-any-return]
    countries_total = frame.select(pl.col("legal_country_iso").n_unique()).item()  # type: ignore[no-any-return]
    if int(payload["merchants_total"]) != merchants_total:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report merchants_total mismatch")
    if int(payload["countries_total"]) != countries_total:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report countries_total mismatch")
    if int(payload["source_rows_total"]) != outlet_rows:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report source_rows_total mismatch")

    ingress_versions = payload.get("ingress_versions", {})
    if not isinstance(ingress_versions, Mapping):
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report ingress_versions must be an object")
    iso_entry = get_dataset_entry("iso3166_canonical_2024", dictionary=dictionary)
    iso_version = iso_entry.get("version")
    if ingress_versions.get("iso3166") != iso_version:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report iso ingress version mismatch")

    determinism_receipt = payload.get("determinism_receipt")
    if not isinstance(determinism_receipt, Mapping):
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report determinism_receipt must be an object")
    partition_path = determinism_receipt.get("partition_path")
    sha256_hex = determinism_receipt.get("sha256_hex")
    if partition_path != str(dataset_path):
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report partition path mismatch")
    if not sha256_hex:
        raise err("E313_NONDETERMINISTIC_OUTPUT", "run report determinism receipt missing sha256_hex")
    actual_digest = compute_partition_digest(dataset_path)
    if actual_digest != sha256_hex:
        raise err(
            "E313_NONDETERMINISTIC_OUTPUT",
            "determinism receipt digest mismatch for s3_requirements",
        )


__all__ = ["ValidatorConfig", "S3RequirementsValidator"]
