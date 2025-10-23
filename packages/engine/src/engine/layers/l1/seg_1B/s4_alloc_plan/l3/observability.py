"""Observability helpers for Segment 1B State-4."""

from __future__ import annotations

from typing import Mapping, TYPE_CHECKING

from ...shared.dictionary import get_dataset_entry
from ..l1.allocation import AllocationResult

if TYPE_CHECKING:
    from ..l2.prepare import PreparedInputs


def build_run_report(
    *,
    prepared: "PreparedInputs",
    allocation: AllocationResult,
    iso_version: str | None,
    determinism_receipt: Mapping[str, str],
    metrics: Mapping[str, object],
    merchant_summaries: list[dict[str, object]],
) -> Mapping[str, object]:
    """Construct the S4 run report payload."""

    iso_entry = iso_version if iso_version is not None else "unknown"
    report = {
        "seed": prepared.config.seed,
        "manifest_fingerprint": prepared.config.manifest_fingerprint,
        "parameter_hash": prepared.config.parameter_hash,
        "rows_emitted": allocation.rows_emitted,
        "merchants_total": allocation.merchants_total,
        "pairs_total": allocation.pairs_total,
        "shortfall_total": allocation.shortfall_total,
        "ties_broken_total": allocation.ties_broken_total,
        "alloc_sum_equals_requirements": allocation.alloc_sum_equals_requirements,
        "ingress_versions": {"iso3166": iso_entry},
        "determinism_receipt": determinism_receipt,
        "bytes_read_s3": int(metrics.get("bytes_read_s3", 0)),
        "bytes_read_weights": int(metrics.get("bytes_read_weights", 0)),
        "bytes_read_index": int(metrics.get("bytes_read_index", 0)),
        "wall_clock_seconds_total": float(metrics.get("wall_clock_seconds_total", 0.0)),
        "cpu_seconds_total": float(metrics.get("cpu_seconds_total", 0.0)),
        "workers_used": int(metrics.get("workers_used", 0)),
        "max_worker_rss_bytes": int(metrics.get("max_worker_rss_bytes", 0)),
        "open_files_peak": int(metrics.get("open_files_peak", 0)),
    }
    if merchant_summaries:
        report["merchant_summaries"] = merchant_summaries
    return report


__all__ = ["build_run_report"]
