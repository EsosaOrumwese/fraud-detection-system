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
) -> Mapping[str, object]:
    """Construct the S4 run report payload."""

    report = {
        "seed": prepared.config.seed,
        "manifest_fingerprint": prepared.config.manifest_fingerprint,
        "parameter_hash": prepared.config.parameter_hash,
        "rows_emitted": allocation.rows_emitted,
        "pairs_total": allocation.pairs_total,
        "shortfall_total": allocation.shortfall_total,
        "ties_broken_total": allocation.ties_broken_total,
        "ingress_versions": {"iso3166": iso_version},
        "determinism_receipt": determinism_receipt,
    }
    return report


__all__ = ["build_run_report"]
