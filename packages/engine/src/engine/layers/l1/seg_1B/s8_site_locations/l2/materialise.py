"""Materialisation for Segment 1B state-8."""

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

from ..exceptions import err
from ..l0.datasets import resolve_site_locations_path
from ..l1.egress import S8Outcome
from .prepare import PreparedInputs


@dataclass(frozen=True)
class S8RunResult:
    """Artifacts emitted by the S8 runner."""

    dataset_path: Path
    run_summary_path: Path
    determinism_receipt: Mapping[str, str]
    wall_clock_seconds: float
    cpu_seconds: float
    run_id: str


def materialise_site_locations(
    *,
    prepared: PreparedInputs,
    outcome: S8Outcome,
    run_id: str,
) -> S8RunResult:
    """Write dataset and run summary for S8."""

    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    dictionary = prepared.dictionary
    dataset_path = resolve_site_locations_path(
    base_path=prepared.data_root,
        seed=prepared.seed,
        manifest_fingerprint=prepared.manifest_fingerprint,
        dictionary=dictionary,
    )

    stage_dir = _write_staged_partition(outcome.frame, dataset_path)
    staged_digest = compute_partition_digest(stage_dir)

    if dataset_path.exists():
        existing_digest = compute_partition_digest(dataset_path)
        if existing_digest != staged_digest:
            shutil.rmtree(stage_dir, ignore_errors=True)
            raise err(
                "E810_PUBLISH_POSTURE",
                f"site_locations partition '{dataset_path}' already exists with different content",
            )
        shutil.rmtree(stage_dir, ignore_errors=True)
        determinism_receipt = {
            "partition_path": str(dataset_path),
            "sha256_hex": existing_digest,
        }
    else:
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage_dir), str(dataset_path))
        determinism_receipt = {
            "partition_path": str(dataset_path),
            "sha256_hex": staged_digest,
        }

    run_summary_path = dataset_path.parent / "s8_run_summary.json"
    run_summary_path.parent.mkdir(parents=True, exist_ok=True)

    run_summary = _build_run_summary(
        prepared=prepared,
        outcome=outcome,
        dataset_path=dataset_path,
        run_summary_path=run_summary_path,
    )
    run_summary_path.write_text(json.dumps(run_summary, indent=2, sort_keys=True), encoding="utf-8")

    wall_clock_seconds = time.perf_counter() - start_wall
    cpu_seconds = time.process_time() - start_cpu

    return S8RunResult(
        dataset_path=dataset_path,
        run_summary_path=run_summary_path,
        determinism_receipt=determinism_receipt,
        wall_clock_seconds=wall_clock_seconds,
        cpu_seconds=cpu_seconds,
        run_id=run_id,
    )


def _write_staged_partition(frame: pl.DataFrame, dataset_path: Path) -> Path:
    _enforce_schema(frame)
    _enforce_sort_order(frame)

    stage_dir = dataset_path.parent / f".site_locations_stage_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(stage_dir / "part-00000.parquet", compression="zstd")
    return stage_dir


def _enforce_schema(frame: pl.DataFrame) -> None:
    expected = {
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "lon_deg",
        "lat_deg",
    }
    if set(frame.columns) != expected:
        raise err(
            "E804_SCHEMA_VIOLATION",
            "site_locations frame columns do not match expected schema",
        )


def _enforce_sort_order(frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E806_WRITER_SORT_VIOLATION",
            "site_locations must be sorted by ['merchant_id','legal_country_iso','site_order']",
        )


def _build_run_summary(
    *,
    prepared: PreparedInputs,
    outcome: S8Outcome,
    dataset_path: Path,
    run_summary_path: Path,
) -> dict:
    by_country = {
        iso: stats.to_dict()
        for iso, stats in sorted(outcome.by_country.items(), key=lambda item: item[0])
    }
    return {
        "identity": {
            "seed": prepared.seed,
            "manifest_fingerprint": prepared.manifest_fingerprint,
            "parameter_hash_consumed": prepared.parameter_hash,
        },
        "sizes": {
            "rows_s7": outcome.rows_s7,
            "rows_s8": outcome.rows_s8,
            "parity_ok": outcome.parity_ok,
        },
        "validation_counters": {
            "schema_fail_count": outcome.schema_fail_count,
            "path_embed_mismatches": outcome.path_embed_mismatches,
            "writer_sort_violations": outcome.writer_sort_violations,
            "order_leak_indicators": outcome.order_leak_indicators,
        },
        "by_country": by_country,
        "artefacts": {
            "dataset_path": str(dataset_path),
            "run_summary_path": str(run_summary_path),
        },
    }


def generate_run_id() -> str:
    """Generate a deterministic-friendly run identifier."""

    return uuid4().hex


__all__ = ["S8RunResult", "materialise_site_locations", "generate_run_id"]
