"""Materialise S5 site→tile assignments and observability artefacts."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence
from uuid import uuid4

import numpy as np
import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import resolve_dataset_path
from ...shared.rng_trace import append_trace_records
from ..exceptions import err
from ..l0.datasets import TileIndexPartition
from ..l1.assignment import AssignmentResult
from ..l2.prepare import PreparedInputs
from ..l3.observability import build_run_report

try:
    import psutil  # type: ignore[import]
except ImportError:  # pragma: no cover - psutil optional
    psutil = None  # type: ignore[assignment]


@dataclass(frozen=True)
class S5RunResult:
    """Outputs emitted by the S5 runner."""

    dataset_path: Path
    rng_log_path: Path
    run_report_path: Path
    determinism_receipt: Mapping[str, str]
    rows_emitted: int
    pairs_total: int
    rng_events_emitted: int
    run_id: str


def materialise_assignment(
    *,
    prepared: PreparedInputs,
    assignment: AssignmentResult,
    iso_version: str | None,
) -> S5RunResult:
    """Write assignment outputs, RNG logs, and the control-plane run report."""

    dictionary = prepared.dictionary
    config = prepared.config

    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    dataset_path = resolve_dataset_path(
        "s5_site_tile_assignment",
        base_path=config.data_root,
        template_args={
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
            "parameter_hash": config.parameter_hash,
        },
        dictionary=dictionary,
    )

    staged_dir = _write_staged_partition(assignment.assignments, dataset_path)
    staged_digest = compute_partition_digest(staged_dir)

    if dataset_path.exists():
        existing_digest = compute_partition_digest(dataset_path)
        if existing_digest != staged_digest:
            shutil.rmtree(staged_dir, ignore_errors=True)
            raise err(
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                f"s5_site_tile_assignment partition '{dataset_path}' already exists with different content",
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

    rng_log_path = _write_rng_events(
        assignment.rng_events,
        base_path=config.data_root,
        dictionary=dictionary,
        seed=config.seed,
        parameter_hash=config.parameter_hash,
        run_id=assignment.run_id,
    )
    trace_path = resolve_dataset_path(
        "rng_trace_log",
        base_path=config.data_root,
        template_args={
            "seed": config.seed,
            "parameter_hash": config.parameter_hash,
            "run_id": assignment.run_id,
        },
        dictionary=dictionary,
    )
    append_trace_records(
        trace_path=trace_path,
        events=assignment.rng_events,
        seed=int(config.seed),
        run_id=assignment.run_id,
    )

    wall_clock_seconds_total = time.perf_counter() - start_wall
    cpu_seconds_total = time.process_time() - start_cpu

    iso_path = resolve_dataset_path(
        "iso3166_canonical_2024",
        base_path=config.data_root,
        template_args={},
        dictionary=dictionary,
    )
    metrics = {
        "bytes_read_alloc_plan": _sum_file_sizes(prepared.alloc_plan.path),
        "bytes_read_tile_index": _sum_file_sizes(prepared.tile_index.path),
        "bytes_read_iso": _sum_file_sizes(iso_path),
        "wall_clock_seconds_total": wall_clock_seconds_total,
        "cpu_seconds_total": cpu_seconds_total,
    }
    metrics.update(_collect_resource_metrics())

    anomalies = _compute_anomaly_counters(
        assignments=assignment.assignments,
        alloc_plan=prepared.alloc_plan.frame,
        tile_index=prepared.tile_index,
        iso_codes=prepared.iso_table.codes,
    )

    run_report_path = resolve_dataset_path(
        "s5_run_report",
        base_path=config.data_root,
        template_args={
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
            "parameter_hash": config.parameter_hash,
        },
        dictionary=dictionary,
    )
    run_report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = build_run_report(
        prepared=prepared,
        assignment=assignment,
        iso_version=iso_version,
        determinism_receipt=determinism_receipt,
        metrics=metrics,
        anomalies=anomalies,
    )
    run_report_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return S5RunResult(
        dataset_path=dataset_path,
        rng_log_path=rng_log_path,
        run_report_path=run_report_path,
        determinism_receipt=determinism_receipt,
        rows_emitted=assignment.rows_emitted,
        pairs_total=assignment.pairs_total,
        rng_events_emitted=assignment.rng_events_emitted,
        run_id=assignment.run_id,
    )


def _write_staged_partition(frame: pl.DataFrame, dataset_path: Path) -> Path:
    _enforce_schema(frame)
    _enforce_sort(frame)

    stage_parent = dataset_path.parent
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage_dir = stage_parent / f".s5_site_tile_assignment_stage_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    output_file = stage_dir / "part-00000.parquet"
    frame.write_parquet(output_file)
    return stage_dir


def _write_rng_events(
    events: Sequence[Mapping[str, object]],
    *,
    base_path: Path,
    dictionary: Mapping[str, object],
    seed: str,
    parameter_hash: str,
    run_id: str,
) -> Path:
    log_dir = resolve_dataset_path(
        "rng_event_site_tile_assign",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    output_file = log_dir / "part-00000.jsonl"
    payload_lines = [json.dumps(event, separators=(",", ":"), sort_keys=True) for event in events]
    payload = "\n".join(payload_lines)
    if payload:
        payload += "\n"

    if output_file.exists():
        existing = output_file.read_text(encoding="utf-8")
        if existing != payload:
            raise err(
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                f"rng log partition '{log_dir}' already exists with different content",
            )
        return log_dir

    output_file.write_text(payload, encoding="utf-8")
    return log_dir


def _enforce_schema(frame: pl.DataFrame) -> None:
    expected = {"merchant_id", "legal_country_iso", "site_order", "tile_id"}
    columns = set(frame.columns)
    if columns != expected:
        raise err(
            "E506_SCHEMA_INVALID",
            f"s5_site_tile_assignment columns {columns} do not match expected {expected}",
        )


def _enforce_sort(frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E509_UNSORTED",
            "s5_site_tile_assignment must be sorted by ['merchant_id','legal_country_iso','site_order']",
        )


def _compute_anomaly_counters(
    *,
    assignments: pl.DataFrame,
    alloc_plan: pl.DataFrame,
    tile_index: TileIndexPartition,
    iso_codes: frozenset[str],
) -> Mapping[str, int]:
    assignments_norm = assignments.with_columns(
        pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase()
    )
    alloc_plan_norm = alloc_plan.with_columns(
        pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase()
    )

    dup_sites = (
        assignments_norm.group_by(["merchant_id", "legal_country_iso", "site_order"])
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
        .height
    )

    per_tile_counts = (
        assignments_norm.group_by(["merchant_id", "legal_country_iso", "tile_id"])
        .agg(pl.len().alias("assigned_count"))
    )

    quota_join = per_tile_counts.join(
        alloc_plan_norm,
        on=["merchant_id", "legal_country_iso", "tile_id"],
        how="full",
    ).fill_null(0)

    quota_mismatches = quota_join.filter(
        pl.col("assigned_count") != pl.col("n_sites_tile")
    ).height

    countries = assignments_norm.get_column("legal_country_iso").unique().to_list()
    tile_lookup: dict[str, np.ndarray] = {}
    for country_iso in countries:
        tiles_df = tile_index.collect_country(country_iso)
        tile_lookup[country_iso] = tiles_df.get_column("tile_id").to_numpy().astype(np.uint64, copy=False)

    tile_not_in_index = 0
    for country_iso, tile_ids in tile_lookup.items():
        if tile_ids.size == 0:
            tile_not_in_index += int(
                assignments_norm.filter(pl.col("legal_country_iso") == country_iso).height
            )
            continue
        assigned_tiles = (
            assignments_norm.filter(pl.col("legal_country_iso") == country_iso)
            .get_column("tile_id")
            .to_numpy()
            .astype(np.uint64, copy=False)
        )
        positions = np.searchsorted(tile_ids, assigned_tiles)
        mask = (positions >= tile_ids.size) | (tile_ids[positions] != assigned_tiles)
        tile_not_in_index += int(mask.sum())

    fk_country_violations = assignments_norm.filter(
        ~pl.col("legal_country_iso").is_in(sorted(iso_codes))
    ).height

    return {
        "quota_mismatches": int(quota_mismatches),
        "dup_sites": int(dup_sites),
        "tile_not_in_index": int(tile_not_in_index),
        "fk_country_violations": int(fk_country_violations),
    }


def _sum_file_sizes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return 0


def _collect_resource_metrics() -> dict[str, int]:
    metrics = {
        "workers_used": 1,
        "max_worker_rss_bytes": 0,
        "open_files_peak": 0,
    }
    if psutil is None:  # pragma: no cover
        return metrics
    try:
        process = psutil.Process()
        metrics["workers_used"] = max(process.num_threads(), 1)
        metrics["max_worker_rss_bytes"] = int(process.memory_info().rss)
        if hasattr(process, "num_handles"):
            metrics["open_files_peak"] = int(process.num_handles())
        elif hasattr(process, "num_fds"):
            metrics["open_files_peak"] = int(process.num_fds())
    except Exception:  # pragma: no cover - defensive
        pass
    return metrics


__all__ = ["S5RunResult", "materialise_assignment"]
