"""Materialisation pipeline for S3 requirements."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, TYPE_CHECKING
from uuid import uuid4

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import resolve_dataset_path
from ..exceptions import err
from ..l2.aggregate import AggregationResult
from ..l3.observability import build_run_report

if TYPE_CHECKING:
    from ..l2.prepare import PreparedInputs

EXPECTED_COLUMNS = ["merchant_id", "legal_country_iso", "n_sites"]
SORT_KEYS = ["merchant_id", "legal_country_iso"]


@dataclass(frozen=True)
class S3RunResult:
    """Output artefacts materialised by the S3 runner."""

    requirements_path: Path
    report_path: Path
    determinism_receipt: Mapping[str, str]
    rows_emitted: int
    merchants_total: int
    countries_total: int
    source_rows_total: int


def materialise_requirements(
    *,
    prepared: "PreparedInputs",
    aggregation: AggregationResult,
) -> S3RunResult:
    """Write the requirements dataset and associated run report."""

    dictionary = prepared.dictionary
    try:
        frame = _normalise_frame(aggregation.frame)
        _enforce_schema(frame)
        _enforce_sort_order(frame)
        _enforce_positive_counts(frame)

        dataset_path = resolve_dataset_path(
            "s3_requirements",
            base_path=prepared.config.data_root,
            template_args={
                "seed": prepared.config.seed,
                "manifest_fingerprint": prepared.config.manifest_fingerprint,
                "parameter_hash": prepared.config.parameter_hash,
            },
            dictionary=dictionary,
        )

        stage_dir = _write_staged_partition(frame, dataset_path)
        staged_digest = compute_partition_digest(stage_dir)

        if dataset_path.exists():
            existing_digest = compute_partition_digest(dataset_path)
            if existing_digest != staged_digest:
                shutil.rmtree(stage_dir, ignore_errors=True)
                raise err(
                    "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                    f"s3_requirements partition '{dataset_path}' already exists with different content",
                )
            shutil.rmtree(stage_dir, ignore_errors=True)
            digest = existing_digest
        else:
            dataset_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stage_dir), str(dataset_path))
            digest = staged_digest

        determinism_receipt = {
            "partition_path": str(dataset_path),
            "sha256_hex": digest,
        }

        report_path = resolve_dataset_path(
            "s3_run_report",
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
            aggregation=aggregation,
            determinism_receipt=determinism_receipt,
        )
        report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        return S3RunResult(
            requirements_path=dataset_path,
            report_path=report_path,
            determinism_receipt=determinism_receipt,
            rows_emitted=aggregation.rows_emitted,
            merchants_total=aggregation.merchants_total,
            countries_total=aggregation.countries_total,
            source_rows_total=aggregation.source_rows_total,
        )
    except Exception as exc:
        _emit_failure_event(prepared=prepared, dictionary=dictionary, failure=exc)
        raise


def _normalise_frame(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.select(
        [
            pl.col("merchant_id").cast(pl.UInt64),
            pl.col("legal_country_iso").cast(pl.Utf8),
            pl.col("n_sites").cast(pl.Int64),
        ]
    )


def _enforce_schema(frame: pl.DataFrame) -> None:
    if frame.columns != EXPECTED_COLUMNS:
        raise err(
            "E305_SCHEMA_INVALID",
            f"s3_requirements columns {frame.columns} do not match expected {EXPECTED_COLUMNS}",
        )


def _enforce_sort_order(frame: pl.DataFrame) -> None:
    sorted_frame = frame.sort(SORT_KEYS)
    if frame.rows() != sorted_frame.rows():
        raise err(
            "E310_UNSORTED",
            "s3_requirements partition must be sorted by ['merchant_id','legal_country_iso']",
        )


def _enforce_positive_counts(frame: pl.DataFrame) -> None:
    if (frame.get_column("n_sites") < 1).any():
        raise err("E304_ZERO_SITES_ROW", "s3_requirements contains zero-count rows")


def _write_staged_partition(frame: pl.DataFrame, dataset_path: Path) -> Path:
    stage_parent = dataset_path.parent
    stage_parent.mkdir(parents=True, exist_ok=True)
    stage_dir = stage_parent / f".s3_requirements_stage_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    output_file = stage_dir / "part-00000.parquet"
    frame.write_parquet(output_file)
    return stage_dir


def _emit_failure_event(*, prepared: "PreparedInputs", dictionary: Mapping[str, object], failure: Exception) -> None:
    try:
        event_path = resolve_dataset_path(
            "s3_failure_event",
            base_path=prepared.config.data_root,
            template_args={
                "seed": prepared.config.seed,
                "manifest_fingerprint": prepared.config.manifest_fingerprint,
                "parameter_hash": prepared.config.parameter_hash,
            },
            dictionary=dictionary,
        )
    except Exception:
        return
    event_path.parent.mkdir(parents=True, exist_ok=True)
    code = getattr(getattr(failure, "context", None), "code", None)
    if isinstance(code, str):
        if code == "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL":
            code = "E313_NONDETERMINISTIC_OUTPUT"
    payload = {
        "event": "S3_ERROR",
        "code": code if isinstance(code, str) else "E313_NONDETERMINISTIC_OUTPUT",
        "at": _utc_now_rfc3339_micros(),
        "seed": str(prepared.config.seed),
        "manifest_fingerprint": prepared.config.manifest_fingerprint,
        "parameter_hash": prepared.config.parameter_hash,
    }
    merchant_id = getattr(failure, "merchant_id", None)
    if merchant_id is not None:
        payload["merchant_id"] = merchant_id
    legal_country_iso = getattr(failure, "legal_country_iso", None)
    if isinstance(legal_country_iso, str) and legal_country_iso:
        payload["legal_country_iso"] = legal_country_iso
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _utc_now_rfc3339_micros() -> str:
    now = time.time()
    seconds = time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime(now))
    micros = int((now % 1) * 1_000_000)
    return f"{seconds}{micros:06d}Z"


__all__ = ["S3RunResult", "materialise_requirements"]
