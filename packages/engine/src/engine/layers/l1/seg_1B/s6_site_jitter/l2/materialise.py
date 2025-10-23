"""Materialisation for Segment 1B state-6."""

from __future__ import annotations

import json
import shutil
import time
import os
import platform
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from uuid import uuid4

import polars as pl

try:  # pragma: no cover - psutil optional
    import psutil  # type: ignore[import]
except ImportError:  # pragma: no cover - psutil optional
    psutil = None  # type: ignore[assignment]

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ..exceptions import err
from ..l1.jitter import JitterOutcome
from ...shared.dictionary import resolve_dataset_path
from .prepare import PreparedInputs


@dataclass(frozen=True)
class S6RunResult:
    """Artifacts emitted by the S6 runner."""

    dataset_path: Path
    rng_log_path: Path
    rng_audit_log_path: Path
    rng_trace_log_path: Path
    run_report_path: Path
    determinism_receipt: Mapping[str, str]
    rows_emitted: int
    rng_events_total: int
    counter_span: int
    run_id: str


def materialise_jitter(
    *,
    prepared: PreparedInputs,
    outcome: JitterOutcome,
    run_id: str,
) -> S6RunResult:
    """Write dataset, RNG logs, and observability payload for S6."""

    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    dictionary = prepared.dictionary
    seed_int = int(prepared.seed)
    dataset_path = resolve_dataset_path(
        "s6_site_jitter",
        base_path=prepared.data_root,
        template_args={
            "seed": prepared.seed,
            "manifest_fingerprint": prepared.manifest_fingerprint,
            "parameter_hash": prepared.parameter_hash,
        },
        dictionary=dictionary,
    )

    staged_dir = _write_staged_partition(outcome.frame, dataset_path)
    staged_digest = compute_partition_digest(staged_dir)

    if dataset_path.exists():
        existing_digest = compute_partition_digest(dataset_path)
        if existing_digest != staged_digest:
            shutil.rmtree(staged_dir, ignore_errors=True)
            raise err(
                "E604_PARTITION_OR_IDENTITY",
                f"s6_site_jitter partition '{dataset_path}' already exists with different content",
            )
        shutil.rmtree(staged_dir, ignore_errors=True)
        determinism_receipt = {
            "partition_path": str(dataset_path),
            "sha256_hex": existing_digest,
        }
    else:
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_dir), str(dataset_path))
        determinism_receipt = {
            "partition_path": str(dataset_path),
            "sha256_hex": staged_digest,
        }

    rng_log_path = _write_rng_events(
        base_path=prepared.data_root,
        dictionary=dictionary,
        seed=prepared.seed,
        parameter_hash=prepared.parameter_hash,
        run_id=run_id,
        events=outcome.rng_events,
    )

    rng_audit_log_path, rng_trace_log_path = _write_rng_core_logs(
        base_path=prepared.data_root,
        dictionary=dictionary,
        seed=seed_int,
        seed_token=prepared.seed,
        parameter_hash=prepared.parameter_hash,
        manifest_fingerprint=prepared.manifest_fingerprint,
        run_id=run_id,
        events=outcome.rng_events,
    )

    wall_clock_seconds = time.perf_counter() - start_wall
    cpu_seconds = time.process_time() - start_cpu

    iso_dataset_path = resolve_dataset_path(
        "iso3166_canonical_2024",
        base_path=prepared.data_root,
        template_args={},
        dictionary=dictionary,
    )

    metrics = {
        "bytes_read_assignments": _sum_file_sizes(prepared.assignments.path),
        "bytes_read_tile_bounds": _sum_file_sizes(prepared.tile_bounds.path),
        "bytes_read_tile_index": _sum_file_sizes(prepared.tile_index.path),
        "bytes_read_world_countries": _sum_file_sizes(prepared.country_polygons.path),
        "bytes_read_iso": _sum_file_sizes(iso_dataset_path),
        "wall_clock_seconds_total": wall_clock_seconds,
        "cpu_seconds_total": cpu_seconds,
    }
    metrics.update(_collect_resource_metrics())
    metrics["bytes_written_rng_events"] = _sum_file_sizes(rng_log_path)
    metrics["bytes_written_rng_audit"] = _sum_file_sizes(rng_audit_log_path)
    metrics["bytes_written_rng_trace"] = _sum_file_sizes(rng_trace_log_path)

    events_total = len(outcome.rng_events)
    if events_total != outcome.events_total:
        raise err(
            "E609_RNG_EVENT_COUNT",
            f"internal event count mismatch (expected {outcome.events_total}, observed {events_total})",
        )
    draws_total = sum(int(event.get("draws", "0")) for event in outcome.rng_events)
    blocks_total = sum(int(event.get("blocks", 0)) for event in outcome.rng_events)
    attempt_histogram = {
        str(attempts): count for attempts, count in sorted(outcome.attempt_histogram.items())
    }
    resample_sites_total = outcome.resample_sites
    resample_events_total = outcome.resample_events
    counter_span_str = str(outcome.counter_span)

    run_report_path = resolve_dataset_path(
        "s6_run_report",
        base_path=prepared.data_root,
        template_args={
            "seed": prepared.seed,
            "manifest_fingerprint": prepared.manifest_fingerprint,
            "parameter_hash": prepared.parameter_hash,
        },
        dictionary=dictionary,
    )
    run_report_path.parent.mkdir(parents=True, exist_ok=True)

    run_report = {
        "identity": {
            "seed": prepared.seed,
            "parameter_hash": prepared.parameter_hash,
            "manifest_fingerprint": prepared.manifest_fingerprint,
            "run_id": run_id,
        },
        "counts": {
            "sites_total": outcome.sites_total,
            "rng": {
                "events_total": events_total,
                "draws_total": str(draws_total),
                "blocks_total": blocks_total,
                "counter_span": counter_span_str,
                "resample_sites_total": resample_sites_total,
                "resample_events_total": resample_events_total,
                "attempt_histogram": attempt_histogram,
            },
        },
        "validation_counters": {
            "fk_tile_index_failures": outcome.fk_tile_index_failures,
            "point_outside_pixel": outcome.outside_pixel,
            "point_outside_country": outcome.outside_country,
            "path_embed_mismatches": outcome.path_embed_mismatches,
        },
        "by_country": outcome.by_country,
        "metrics": metrics,
    }
    run_report["determinism_receipt"] = determinism_receipt
    run_report["artefacts"] = {
        "dataset_path": str(dataset_path),
        "rng_event_log": str(rng_log_path),
        "rng_audit_log": str(rng_audit_log_path),
        "rng_trace_log": str(rng_trace_log_path),
    }
    if prepared.iso_version:
        run_report.setdefault("ingress_versions", {})["iso3166_canonical_2024"] = prepared.iso_version

    run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

    return S6RunResult(
        dataset_path=dataset_path,
        rng_log_path=rng_log_path,
        rng_audit_log_path=rng_audit_log_path,
        rng_trace_log_path=rng_trace_log_path,
        run_report_path=run_report_path,
        determinism_receipt=determinism_receipt,
        rows_emitted=outcome.sites_total,
        rng_events_total=events_total,
        counter_span=outcome.counter_span,
        run_id=run_id,
    )


def _write_staged_partition(frame: pl.DataFrame, dataset_path: Path) -> Path:
    _enforce_schema(frame)
    _enforce_sort_order(frame)

    stage_dir = dataset_path.parent / f".s6_site_jitter_stage_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(stage_dir / "part-00000.parquet", compression="zstd")
    return stage_dir


def _write_rng_events(
    *,
    base_path: Path,
    dictionary: Mapping[str, object],
    seed: str,
    parameter_hash: str,
    run_id: str,
    events: list[Mapping[str, object]],
) -> Path:
    log_dir = resolve_dataset_path(
        "rng_event_in_cell_jitter",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "part-00000.jsonl"
    payload = "\n".join(json.dumps(event, sort_keys=True) for event in events)
    if payload:
        payload += "\n"

    if log_file.exists():
        existing = log_file.read_text(encoding="utf-8")
        if existing != payload:
            raise err(
                "E611_LOG_PARTITION_LAW",
                f"rng event partition '{log_dir}' already exists with different content",
            )
        return log_dir

    log_file.write_text(payload, encoding="utf-8")
    return log_dir


def _write_rng_core_logs(
    *,
    base_path: Path,
    dictionary: Mapping[str, object],
    seed: int,
    seed_token: str,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    events: list[Mapping[str, object]],
) -> tuple[Path, Path]:
    audit_path = resolve_dataset_path(
        "rng_audit_log",
        base_path=base_path,
        template_args={
            "seed": seed_token,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    audit_record = {
        "ts_utc": _utc_timestamp(),
        "run_id": run_id,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": _resolve_build_commit(dictionary),
        "code_digest": os.getenv("ENGINE_CODE_DIGEST"),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "notes": None,
    }
    audit_record = _write_single_jsonl_record(audit_path, audit_record)

    trace_path = resolve_dataset_path(
        "rng_trace_log",
        base_path=base_path,
        template_args={
            "seed": seed_token,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    _write_trace_records(
        trace_path=trace_path,
        events=events,
        seed=seed,
        run_id=run_id,
    )

    return audit_path, trace_path


def _write_single_jsonl_record(path: Path, record: Mapping[str, object]) -> Mapping[str, object]:
    payload = json.dumps(record, sort_keys=True)
    payload_with_newline = payload + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing.strip():
            try:
                existing_record = json.loads(existing.splitlines()[0])
            except json.JSONDecodeError as exc:
                raise err("E611_LOG_PARTITION_LAW", f"rng audit log at '{path}' is not valid JSONL") from exc
            if existing_record != record:
                raise err(
                    "E611_LOG_PARTITION_LAW",
                    f"rng audit log '{path}' already exists with different content",
                )
            return existing_record
    path.write_text(payload_with_newline, encoding="utf-8")
    return record


def _write_trace_records(
    *,
    trace_path: Path,
    events: list[Mapping[str, object]],
    seed: int,
    run_id: str,
) -> None:
    totals: dict[tuple[str, str], dict[str, int]] = {}
    records: list[Mapping[str, object]] = []
    for event in events:
        module = str(event.get("module", ""))
        substream_label = str(event.get("substream_label", ""))
        key = (module, substream_label)
        stats = totals.setdefault(key, {"events": 0, "blocks": 0, "draws": 0})
        blocks = int(event.get("blocks", 0))
        draws = int(event.get("draws", "0"))
        stats["events"] += 1
        stats["blocks"] += blocks
        stats["draws"] += draws
        record = {
            "ts_utc": event.get("ts_utc"),
            "run_id": run_id,
            "seed": seed,
            "module": module,
            "substream_label": substream_label,
            "draws_total": stats["draws"],
            "blocks_total": stats["blocks"],
            "events_total": stats["events"],
            "rng_counter_before_lo": int(event.get("rng_counter_before_lo", 0)),
            "rng_counter_before_hi": int(event.get("rng_counter_before_hi", 0)),
            "rng_counter_after_lo": int(event.get("rng_counter_after_lo", 0)),
            "rng_counter_after_hi": int(event.get("rng_counter_after_hi", 0)),
        }
        records.append(record)

    payload = "\n".join(json.dumps(record, sort_keys=True) for record in records)
    if payload:
        payload += "\n"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    if trace_path.exists():
        existing = trace_path.read_text(encoding="utf-8")
        if existing != payload:
            raise err(
                "E611_LOG_PARTITION_LAW",
                f"rng trace log '{trace_path}' already exists with different content",
            )
        return
    trace_path.write_text(payload, encoding="utf-8")


def _resolve_build_commit(dictionary: Mapping[str, object]) -> str:
    metadata = dictionary.get("metadata") if isinstance(dictionary, Mapping) else None
    commit: str | None = None
    if isinstance(metadata, Mapping):
        raw = metadata.get("build_commit")
        if isinstance(raw, str) and raw.strip():
            commit = raw.strip()
    if not commit:
        for env_var in ("ENGINE_BUILD_COMMIT", "GIT_COMMIT", "BUILD_COMMIT"):
            value = os.getenv(env_var)
            if value:
                commit = value
                break
    return commit or "unknown"


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


def _enforce_schema(frame: pl.DataFrame) -> None:
    expected = {
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "tile_id",
        "delta_lat_deg",
        "delta_lon_deg",
        "manifest_fingerprint",
    }
    if set(frame.columns) != expected:
        raise err("E612_DICT_SCHEMA_MISMATCH", "s6_site_jitter frame columns do not match expected schema")


def _enforce_sort_order(frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows()
    if frame.rows() != sorted_rows:
        raise err("E605_SORT_VIOLATION", "s6_site_jitter must be sorted by ['merchant_id','legal_country_iso','site_order']")


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


__all__ = ["S6RunResult", "materialise_jitter"]
