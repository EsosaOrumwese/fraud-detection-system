"""Observability helpers for S2 tile weights."""

from __future__ import annotations

from typing import Mapping, TYPE_CHECKING

from ...shared.dictionary import get_dataset_entry

if TYPE_CHECKING:
    from ..l2.runner import PreparedInputs
    from ..l1.quantize import QuantisationResult


def build_run_report(
    *,
    prepared: PreparedInputs,
    quantised: QuantisationResult,
    determinism_receipt: Mapping[str, str],
) -> Mapping[str, object]:
    """Construct the S2 run report payload."""

    dictionary = prepared.dictionary

    iso_entry = get_dataset_entry("iso3166_canonical_2024", dictionary=dictionary)
    population_entry = None
    if prepared.governed.basis == "population":
        population_entry = get_dataset_entry("population_raster_2025", dictionary=dictionary)

    ingress_versions = {
        "iso3166": iso_entry.get("version"),
        "population_raster": population_entry.get("version") if population_entry else None,
    }

    report = {
        "parameter_hash": prepared.tile_index.parameter_hash,
        "basis": prepared.governed.basis,
        "dp": prepared.governed.dp,
        "rows_emitted": quantised.frame.height,
        "countries_total": len(quantised.summaries),
        "ingress_versions": ingress_versions,
        "pat": prepared.pat.to_dict(),
        "normalisation_summaries": quantised.summaries,
        "determinism_receipt": determinism_receipt,
    }
    return report


__all__ = ["build_run_report"]