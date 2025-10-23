"""Materialisation for Segment 1B state-7."""

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
from ..l1.synthesis import S7Outcome
from .prepare import PreparedInputs


@dataclass(frozen=True)
class S7RunResult:
    """Artefacts emitted by the S7 runner."""

    dataset_path: Path
    run_summary_path: Path
    determinism_receipt: Mapping[str, str]
    run_id: str
    wall_clock_seconds: float
    cpu_seconds: float


def materialise_synthesis(
    *,
    prepared: PreparedInputs,
    outcome: S7Outcome,
    run_id: str,
) -> S7RunResult:
    """Write dataset and run summary for S7."""

    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    dictionary = prepared.dictionary
    dataset_path = _resolve_s7_dataset_path(
        base_path=prepared.data_root,
        seed=prepared.seed,
        manifest_fingerprint=prepared.manifest_fingerprint,
        parameter_hash=prepared.parameter_hash,
        dictionary=dictionary,
    )

    stage_dir = _write_staged_partition(outcome.frame, dataset_path)
    staged_digest = compute_partition_digest(stage_dir)

    if dataset_path.exists():
        existing_digest = compute_partition_digest(dataset_path)
        if existing_digest != staged_digest:
            shutil.rmtree(stage_dir, ignore_errors=True)
            raise err(
                "E712_ATOMIC_PUBLISH_VIOLATION",
                f"s7_site_synthesis partition '{dataset_path}' already exists with different content",
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

    run_summary_path = dataset_path.parent / "s7_run_summary.json"
    run_summary_path.parent.mkdir(parents=True, exist_ok=True)

    run_summary = _build_run_summary(
        prepared=prepared,
        outcome=outcome,
        run_id=run_id,
        determinism_receipt=determinism_receipt,
        dataset_path=dataset_path,
        run_summary_path=run_summary_path,
    )
    run_summary_path.write_text(json.dumps(run_summary, indent=2, sort_keys=True), encoding="utf-8")

    wall_clock_seconds = time.perf_counter() - start_wall
    cpu_seconds = time.process_time() - start_cpu

    return S7RunResult(
        dataset_path=dataset_path,
        run_summary_path=run_summary_path,
        determinism_receipt=determinism_receipt,
        run_id=run_id,
        wall_clock_seconds=wall_clock_seconds,
        cpu_seconds=cpu_seconds,
    )


def _resolve_s7_dataset_path(
    *,
    base_path: Path,
    seed: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    dictionary: Mapping[str, object],
) -> Path:
    from ...shared.dictionary import resolve_dataset_path

    return resolve_dataset_path(
        "s7_site_synthesis",
        base_path=base_path,
        template_args={
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        },
        dictionary=dictionary,
    )


def _write_staged_partition(frame: pl.DataFrame, dataset_path: Path) -> Path:
    _enforce_schema(frame)
    _enforce_sort_order(frame)

    stage_dir = dataset_path.parent / f".s7_site_synthesis_stage_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(stage_dir / "part-00000.parquet", compression="zstd")
    return stage_dir


def _enforce_schema(frame: pl.DataFrame) -> None:
    expected = {
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "tile_id",
        "lon_deg",
        "lat_deg",
    }
    if set(frame.columns) != expected:
        raise err(
            "E704_SCHEMA_VIOLATION",
            "s7_site_synthesis frame columns do not match expected schema",
        )


def _enforce_sort_order(frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E706_WRITER_SORT_VIOLATION",
            "s7_site_synthesis must be sorted by ['merchant_id','legal_country_iso','site_order']",
        )


def _build_run_summary(
    *,
    prepared: PreparedInputs,
    outcome: S7Outcome,
    run_id: str,
    determinism_receipt: Mapping[str, str],
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
            "parameter_hash": prepared.parameter_hash,
            "manifest_fingerprint": prepared.manifest_fingerprint,
            "run_id": run_id,
        },
        "counts": {
            "sites_total_s5": outcome.sites_total_s5,
            "sites_total_s6": outcome.sites_total_s6,
            "sites_total_s7": outcome.sites_total_s7,
            "parity": {
                "s5_eq_s7": outcome.parity_s5_s7_ok,
                "s5_eq_s6": outcome.parity_s5_s6_ok,
            },
        },
        "validation_counters": {
            "fk_tile_ok_count": outcome.fk_tile_ok_count,
            "fk_tile_fail_count": outcome.fk_tile_fail_count,
            "inside_pixel_ok_count": outcome.inside_pixel_ok_count,
            "inside_pixel_fail_count": outcome.inside_pixel_fail_count,
            "path_embed_mismatches": 0,
            "coverage_1a_ok_count": outcome.coverage_ok_count,
            "coverage_1a_miss_count": outcome.coverage_miss_count,
        },
        "by_country": by_country,
        "consumer_gate": {
            "flag_sha256_hex": prepared.gate.flag_sha256_hex,
        },
        "artefacts": {
            "dataset_path": str(dataset_path),
            "run_summary_path": str(run_summary_path),
        },
        "determinism_receipt": dict(determinism_receipt),
    }


def generate_run_id() -> str:
    """Generate a deterministic-friendly run identifier."""

    return uuid4().hex


__all__ = ["S7RunResult", "materialise_synthesis", "generate_run_id"]
