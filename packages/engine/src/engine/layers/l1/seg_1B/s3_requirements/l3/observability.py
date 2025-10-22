"""Observability helpers for S3 requirements."""

from __future__ import annotations

from typing import Mapping, TYPE_CHECKING

from ...shared.dictionary import get_dataset_entry
from ..l2.aggregate import AggregationResult

if TYPE_CHECKING:
    from ..l2.prepare import PreparedInputs


def build_run_report(
    *,
    prepared: 'PreparedInputs',
    aggregation: AggregationResult,
    determinism_receipt: Mapping[str, str],
) -> Mapping[str, object]:
    """Build the S3 run report payload."""

    dictionary = prepared.dictionary
    iso_entry = get_dataset_entry("iso3166_canonical_2024", dictionary=dictionary)

    ingress_versions = {
        "iso3166": iso_entry.get("version"),
    }

    report: dict[str, object] = {
        "seed": prepared.config.seed,
        "manifest_fingerprint": prepared.config.manifest_fingerprint,
        "parameter_hash": prepared.config.parameter_hash,
        "rows_emitted": aggregation.rows_emitted,
        "merchants_total": aggregation.merchants_total,
        "countries_total": aggregation.countries_total,
        "source_rows_total": aggregation.source_rows_total,
        "ingress_versions": ingress_versions,
        "determinism_receipt": determinism_receipt,
    }

    notes = prepared.receipt.payload.get("notes")
    if notes:
        report["notes"] = notes

    report["validation_flag_sha256_hex"] = prepared.receipt.flag_sha256_hex

    return report


__all__ = ["build_run_report"]
