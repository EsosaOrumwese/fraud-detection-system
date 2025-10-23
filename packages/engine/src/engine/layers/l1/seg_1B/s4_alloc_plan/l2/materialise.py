"""Materialise S4 allocation results and emit run reports."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from uuid import uuid4

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import resolve_dataset_path
from ..exceptions import err
from ..l1.allocation import AllocationResult
from ..l2.prepare import PreparedInputs
from ..l3.observability import build_run_report


@dataclass(frozen=True)
class S4RunResult:
    """Artefacts emitted by the S4 runner."""

    alloc_plan_path: Path
    report_path: Path
    determinism_receipt: Mapping[str, str]
    rows_emitted: int
    pairs_total: int
    merchants_total: int
    shortfall_total: int
    ties_broken_total: int
    alloc_sum_equals_requirements: bool


def materialise_allocation(
    *,
    prepared: PreparedInputs,
    allocation: AllocationResult,
    iso_version: str | None,
) -> S4RunResult:
    """Write allocation parquet and evidence bundles."""

    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    frame = allocation.frame
    dictionary = prepared.dictionary
    dataset_path = resolve_dataset_path(
        "s4_alloc_plan",
        base_path=prepared.config.data_root,
        template_args={
            "seed": prepared.config.seed,
            "manifest_fingerprint": prepared.config.manifest_fingerprint,
            "parameter_hash": prepared.config.parameter_hash,
        },
        dictionary=dictionary,
    )

    staged_dir = _write_staged_partition(frame, dataset_path)
    staged_digest = compute_partition_digest(staged_dir)

    if dataset_path.exists():
        existing_digest = compute_partition_digest(dataset_path)
        if existing_digest != staged_digest:
            shutil.rmtree(staged_dir, ignore_errors=True)
            raise err(
                "E411_IMMUTABLE_CONFLICT",
                f"s4_alloc_plan partition '{dataset_path}' already exists with different content",
            )
        shutil.rmtree(staged_dir, ignore_errors=True)
        digest = existing_digest
    else:
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_dir), str(dataset_path))
        digest = staged_digest

    determinism_receipt = {
        "partition_path": str(dataset_path),
        "sha256_hex": digest,
    }

    wall_clock_seconds_total = time.perf_counter() - start_wall
    cpu_seconds_total = time.process_time() - start_cpu
    metrics = {
        "bytes_read_s3": _sum_file_sizes(prepared.requirements.path),
        "bytes_read_weights": _sum_file_sizes(prepared.tile_weights.path),
        "bytes_read_index": _sum_file_sizes(prepared.tile_index.path),
        "wall_clock_seconds_total": wall_clock_seconds_total,
        "cpu_seconds_total": cpu_seconds_total,
        "workers_used": 1,
        "max_worker_rss_bytes": 0,
        "open_files_peak": 0,
    }

    report_path = resolve_dataset_path(
        "s4_run_report",
        base_path=prepared.config.data_root,
        template_args={
            "seed": prepared.config.seed,
            "manifest_fingerprint": prepared.config.manifest_fingerprint,
            "parameter_hash": prepared.config.parameter_hash,
        },
        dictionary=dictionary,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    run_report = build_run_report(
        prepared=prepared,
        allocation=allocation,
        iso_version=iso_version,
        determinism_receipt=determinism_receipt,
        metrics=metrics,
    )
    report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

    return S4RunResult(
        alloc_plan_path=dataset_path,
        report_path=report_path,
        determinism_receipt=determinism_receipt,
        rows_emitted=allocation.rows_emitted,
        pairs_total=allocation.pairs_total,
        merchants_total=allocation.merchants_total,
        shortfall_total=allocation.shortfall_total,
        ties_broken_total=allocation.ties_broken_total,
        alloc_sum_equals_requirements=allocation.alloc_sum_equals_requirements,
    )


def _write_staged_partition(frame: pl.DataFrame, dataset_path: Path) -> Path:
    _enforce_schema(frame)
    _enforce_sort_order(frame)

    stage_parent = dataset_path.parent
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage_dir = stage_parent / f".s4_alloc_plan_stage_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    output_file = stage_dir / "part-00000.parquet"
    frame.write_parquet(output_file)
    return stage_dir


def _enforce_schema(frame: pl.DataFrame) -> None:
    expected = {"merchant_id", "legal_country_iso", "tile_id", "n_sites_tile"}
    columns = set(frame.columns)
    if columns != expected:
        raise err(
            "E405_SCHEMA_INVALID",
            f"s4_alloc_plan frame columns {columns} do not match expected {expected}",
        )


def _enforce_sort_order(frame: pl.DataFrame) -> None:
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "tile_id"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E406_SORT_INVALID",
            "s4_alloc_plan must be sorted by ['merchant_id','legal_country_iso','tile_id']",
        )


def _sum_file_sizes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return 0


__all__ = ["S4RunResult", "materialise_allocation"]
