"""Observability helpers for Segment 1B state-5."""

from __future__ import annotations

from typing import Mapping

from ..l1.assignment import AssignmentResult

if False:  # pragma: no cover - typing imports only
    from ..l2.prepare import PreparedInputs


def build_run_report(
    *,
    prepared: "PreparedInputs",
    assignment: AssignmentResult,
    iso_version: str | None,
    determinism_receipt: Mapping[str, str],
    metrics: Mapping[str, object],
    anomalies: Mapping[str, int],
) -> Mapping[str, object]:
    """Construct the S5 run report payload."""

    ingress_versions: dict[str, str] = {}
    if iso_version:
        ingress_versions["iso3166_canonical_2024"] = iso_version

    report: dict[str, object] = {
        "seed": prepared.config.seed,
        "manifest_fingerprint": prepared.config.manifest_fingerprint,
        "parameter_hash": prepared.config.parameter_hash,
        "run_id": assignment.run_id,
        "rows_emitted": assignment.rows_emitted,
        "pairs_total": assignment.pairs_total,
        "rng_events_emitted": assignment.rng_events_emitted,
        "expected_rng_events": assignment.rows_emitted,
        "determinism_receipt": determinism_receipt,
        "ties_broken_total": assignment.ties_broken_total,
    }

    if ingress_versions:
        report["ingress_versions"] = ingress_versions

    report.update({key: int(value) if isinstance(value, bool) else value for key, value in metrics.items()})
    report.update({key: int(value) for key, value in anomalies.items()})

    # Sanity defaults for anomaly counters if caller omitted any optional fields.
    for field in ("quota_mismatches", "dup_sites", "tile_not_in_index", "fk_country_violations"):
        report.setdefault(field, 0)

    for field in ("bytes_read_alloc_plan", "bytes_read_tile_index", "bytes_read_iso"):
        report.setdefault(field, 0)

    return report


__all__ = ["build_run_report"]
