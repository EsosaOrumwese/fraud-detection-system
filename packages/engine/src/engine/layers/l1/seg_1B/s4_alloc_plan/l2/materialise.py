"""Materialise S4 allocation results and emit run reports."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import resolve_dataset_path
from ..exceptions import err
from ..l1.allocation import AllocationResult
from ..l2.prepare import PreparedInputs
from ..l3.observability import build_run_report

try:
    import psutil  # type: ignore[import]
except ImportError:  # pragma: no cover - psutil optional
    psutil = None  # type: ignore[assignment]


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

    dictionary = prepared.dictionary
    try:
        start_wall = time.perf_counter()
        start_cpu = time.process_time()

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

        staged_dir = allocation.temp_dir
        if not staged_dir.exists():
            raise err(
                "E405_SCHEMA_INVALID",
                f"s4 allocation staging directory '{staged_dir}' missing",
            )
        staged_digest = compute_partition_digest(staged_dir)

        if dataset_path.exists():
            existing_digest = compute_partition_digest(dataset_path)
            if existing_digest != staged_digest:
                shutil.rmtree(staged_dir, ignore_errors=True)
                raise err(
                    "E411_IMMUTABLE_CONFLICT",
                    f"s4_alloc_plan partition '{dataset_path}' already exists with different content",
                )
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
            "workers_used": allocation.workers_used,
        }
        resource_metrics = _collect_resource_metrics()
        resource_metrics["workers_used"] = allocation.workers_used
        metrics.update(resource_metrics)

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
            merchant_summaries=allocation.merchant_summaries,
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
    except Exception as exc:
        _emit_failure_event(prepared=prepared, dictionary=dictionary, failure=exc)
        raise


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
    if psutil is None:  # pragma: no cover - executed when psutil unavailable
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


def _emit_failure_event(*, prepared: PreparedInputs, dictionary: Mapping[str, object], failure: Exception) -> None:
    try:
        event_path = resolve_dataset_path(
            "s4_failure_event",
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
    code_map = {
        "E401_REQUIREMENTS_MISSING": "E401_NO_S3_REQUIREMENTS",
        "E402_WEIGHTS_MISSING": "E402_MISSING_TILE_WEIGHTS",
        "E403_SHORTFALL_MISMATCH": "E404_ALLOCATION_MISMATCH",
        "E404_TIE_BREAK": "E411_TIE_RULE_VIOLATION",
        "E406_SORT_INVALID": "E408_UNSORTED",
        "E408_COVERAGE_MISSING": "E413_TILE_NOT_IN_INDEX",
        "E409_DETERMINISM": "E410_NONDETERMINISTIC_OUTPUT",
        "E410_TOKEN_MISMATCH": "E406_TOKEN_MISMATCH",
        "E411_IMMUTABLE_CONFLICT": "E410_NONDETERMINISTIC_OUTPUT",
    }
    if isinstance(code, str):
        code = code_map.get(code, code)
    payload = {
        "event": "S4_ERROR",
        "code": code if isinstance(code, str) else "E410_NONDETERMINISTIC_OUTPUT",
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


__all__ = ["S4RunResult", "materialise_allocation"]
