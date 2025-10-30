"""Validator for Segment 1B State-4 allocation plan."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err
from ..l0.datasets import load_iso_countries, load_s3_requirements, load_tile_index, load_tile_weights
from ..l2.aggregate import AggregationContext, build_allocation


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S4 allocation output."""

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


class S4AllocPlanValidator:
    """Validate S4 allocation partitions against the specification."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()
        dataset_path = resolve_dataset_path(
            "s4_alloc_plan",
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
                "E405_SCHEMA_INVALID",
                f"s4_alloc_plan partition '{dataset_path}' missing",
            )

        dataset = pl.read_parquet(_parquet_pattern(dataset_path)).select(
            ["merchant_id", "legal_country_iso", "tile_id", "n_sites_tile"]
        )

        _ensure_schema(dataset)
        _ensure_sort(dataset)
        _ensure_positive_allocations(dataset)
        _ensure_pk(dataset)

        requirements = load_s3_requirements(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        tile_weights = load_tile_weights(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        tile_index = load_tile_index(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        iso_table, _ = load_iso_countries(
            base_path=config.data_root,
            dictionary=dictionary,
        )

        context = AggregationContext(
            requirements=requirements,
            tile_weights=tile_weights,
            tile_index=tile_index,
            iso_table=iso_table,
            dp=tile_weights.dp,
        )
        allocation = build_allocation(context)
        recomputed = (
            pl.scan_parquet(str(allocation.temp_dir / "*.parquet"))
            .select(["merchant_id", "legal_country_iso", "tile_id", "n_sites_tile"])
            .collect()
        )
        shutil.rmtree(allocation.temp_dir, ignore_errors=True)

        if dataset.height != recomputed.height or dataset.sort(["merchant_id", "legal_country_iso", "tile_id"]).rows() != recomputed.sort(["merchant_id", "legal_country_iso", "tile_id"]).rows():
            raise err(
                "E403_SHORTFALL_MISMATCH",
                "s4_alloc_plan dataset does not match recomputed allocations",
            )

        run_report_path = (
            config.run_report_path
            if config.run_report_path is not None
            else resolve_dataset_path(
                "s4_run_report",
                base_path=config.data_root,
                template_args={
                    "seed": config.seed,
                    "manifest_fingerprint": config.manifest_fingerprint,
                    "parameter_hash": config.parameter_hash,
                },
                dictionary=dictionary,
            )
        )
        _validate_run_report(
            report_path=run_report_path,
            dataset_path=dataset_path,
            dataset=dataset,
        )


def _parquet_pattern(path: Path) -> str:
    if path.is_dir():
        return str(path / "*.parquet")
    if path.suffix == ".parquet":
        return str(path)
    raise err(
        "E405_SCHEMA_INVALID",
        f"path '{path}' is neither parquet directory nor file",
    )


def _ensure_schema(frame: pl.DataFrame) -> None:
    expected = {"merchant_id", "legal_country_iso", "tile_id", "n_sites_tile"}
    columns = set(frame.columns)
    if columns != expected:
        raise err(
            "E405_SCHEMA_INVALID",
            f"s4_alloc_plan columns {columns} do not match expected {expected}",
        )


def _ensure_sort(frame: pl.DataFrame) -> None:
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "tile_id"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E406_SORT_INVALID",
            "s4_alloc_plan partition must be sorted by ['merchant_id','legal_country_iso','tile_id']",
        )


def _ensure_positive_allocations(frame: pl.DataFrame) -> None:
    if (frame.get_column("n_sites_tile") < 1).any():
        raise err("E403_SHORTFALL_MISMATCH", "s4_alloc_plan contains zero or negative allocations")


def _ensure_pk(frame: pl.DataFrame) -> None:
    dupes = (
        frame.group_by(["merchant_id", "legal_country_iso", "tile_id"])
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
    )
    if dupes.height:
        raise err("E407_PK_DUPLICATE", "s4_alloc_plan contains duplicate rows for the same tile")


def _validate_run_report(
    *,
    report_path: Path,
    dataset_path: Path,
    dataset: pl.DataFrame,
) -> None:
    if not report_path.exists():
        raise err(
            "E409_DETERMINISM",
            f"s4 run report missing at '{report_path}'",
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err(
            "E409_DETERMINISM",
            f"s4 run report is not valid JSON: {exc}",
        ) from exc

    required_fields = {
        "seed",
        "manifest_fingerprint",
        "parameter_hash",
        "rows_emitted",
        "merchants_total",
        "pairs_total",
        "shortfall_total",
        "ties_broken_total",
        "alloc_sum_equals_requirements",
        "ingress_versions",
        "determinism_receipt",
        "bytes_read_s3",
        "bytes_read_weights",
        "bytes_read_index",
        "wall_clock_seconds_total",
        "cpu_seconds_total",
        "workers_used",
        "max_worker_rss_bytes",
        "open_files_peak",
    }
    missing_fields = sorted(required_fields.difference(payload.keys()))
    if missing_fields:
        raise err(
            "E409_DETERMINISM",
            f"s4 run report missing fields: {missing_fields}",
        )

    if not bool(payload.get("alloc_sum_equals_requirements", False)):
        raise err("E403_SHORTFALL_MISMATCH", "run report indicates allocation conservation failed")

    receipt = payload.get("determinism_receipt")
    if not isinstance(receipt, Mapping):
        raise err("E409_DETERMINISM", "s4 run report determinism receipt malformed")
    if receipt.get("partition_path") != str(dataset_path):
        raise err("E409_DETERMINISM", "determinism receipt partition path mismatch")
    digest = receipt.get("sha256_hex")
    if not isinstance(digest, str):
        raise err("E409_DETERMINISM", "determinism receipt missing sha256_hex")
    actual_digest = compute_partition_digest(dataset_path)
    if actual_digest != digest:
        raise err("E409_DETERMINISM", "determinism receipt digest mismatch for s4_alloc_plan")

    # Basic metric sanity checks
    if int(payload["rows_emitted"]) != dataset.height:
        raise err("E409_DETERMINISM", "rows_emitted in run report does not match dataset height")

    for key in ("bytes_read_s3", "bytes_read_weights", "bytes_read_index"):
        value = payload.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise err("E409_DETERMINISM", f"{key} in run report must be a non-negative number")

    for key in ("wall_clock_seconds_total", "cpu_seconds_total"):
        value = payload.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise err("E409_DETERMINISM", f"{key} in run report must be a non-negative number")

    for key in ("workers_used", "max_worker_rss_bytes", "open_files_peak"):
        value = payload.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise err("E409_DETERMINISM", f"{key} in run report must be a non-negative number")

    merchant_summaries = payload.get("merchant_summaries")
    if merchant_summaries is not None:
        if not isinstance(merchant_summaries, list):
            raise err("E409_DETERMINISM", "merchant_summaries must be a list when present")


__all__ = ["S4AllocPlanValidator", "ValidatorConfig"]
