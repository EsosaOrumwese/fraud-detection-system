"""Deterministic context assembly for S2 (multi-site NB sampler).

This module wires the S1 hurdle outcomes with the S0 design vectors so that
S2 can compute the Negative Binomial parameters for multi-site merchants.
Only merchants that cleared the hurdle (``is_multi = True``) are admitted;
attempting to process any other merchant raises the S2 entry errors defined
in the specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from ...s0_foundations.exceptions import err
from ...s0_foundations.l1.design import (
    DesignVectors,
    DispersionCoefficients,
    HurdleCoefficients,
)
from ..s1_hurdle.l2.runner import HurdleDecision
from ..l1.links import NBLinks, compute_links_from_design


@dataclass(frozen=True)
class S2DeterministicRow:
    """Immutable NB context for a single multi-site merchant."""

    merchant_id: int
    bucket_id: int
    design_nb_mean: Tuple[float, ...]
    design_nb_dispersion: Tuple[float, ...]
    links: NBLinks


@dataclass(frozen=True)
class S2DeterministicContext:
    """Run-scoped, deterministic inputs handed to the stochastic sampler."""

    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    seed: int
    rows: Tuple[S2DeterministicRow, ...]

    def by_merchant(self) -> Mapping[int, S2DeterministicRow]:
        """Return a mapping keyed by merchant id for quick lookup."""

        return {row.merchant_id: row for row in self.rows}


def _decision_map(decisions: Sequence[HurdleDecision]) -> Dict[int, HurdleDecision]:
    mapping: Dict[int, HurdleDecision] = {}
    for decision in decisions:
        merchant_id = int(decision.merchant_id)
        if merchant_id in mapping:
            raise err(
                "E_VALIDATION_MISMATCH",
                f"duplicate hurdle decision for merchant {merchant_id}",
            )
        mapping[merchant_id] = decision
    return mapping


def _design_map(vectors: Iterable[DesignVectors]) -> Dict[int, DesignVectors]:
    mapping: Dict[int, DesignVectors] = {}
    for vector in vectors:
        merchant_id = int(vector.merchant_id)
        if merchant_id in mapping:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"duplicate design vector for merchant {merchant_id}",
        )
        mapping[merchant_id] = vector
    return mapping


def build_deterministic_context(
    *,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    seed: int,
    multi_merchant_ids: Sequence[int],
    decisions: Sequence[HurdleDecision],
    design_vectors: Iterable[DesignVectors],
    hurdle: HurdleCoefficients,
    dispersion: DispersionCoefficients,
) -> S2DeterministicContext:
    """Compute NB links for the multi-site merchants admitted to S2.

    Parameters
    ----------
    parameter_hash, manifest_fingerprint, run_id, seed
        Lineage anchors propagated from S0/S1; echoed by the stochastic steps.
    multi_merchant_ids
        Merchant identifiers that cleared the S1 hurdle (`is_multi = True`).
    decisions
        Full S1 hurdle decisions (used for guard rails and provenance checks).
    design_vectors
        Complete S0 design vectors (NB mean/dispersion components included).
    hurdle, dispersion
        Governed coefficient bundles used to evaluate the NB2 links.
    """

    decision_lookup = _decision_map(decisions)
    design_lookup = _design_map(design_vectors)
    rows: list[S2DeterministicRow] = []

    for raw_id in multi_merchant_ids:
        merchant_id = int(raw_id)
        decision = decision_lookup.get(merchant_id)
        if decision is None:
            raise err(
                "ERR_S2_ENTRY_MISSING_HURDLE",
                f"hurdle decision missing for merchant {merchant_id}",
            )
        if not decision.is_multi:
            raise err(
                "ERR_S2_ENTRY_NOT_MULTI",
                f"hurdle decision for merchant {merchant_id} is multi-site = False",
            )
        vector = design_lookup.get(merchant_id)
        if vector is None:
            raise err(
                "ERR_S2_INPUTS_INCOMPLETE:design_vector",
                f"design vector missing for merchant {merchant_id}",
            )

        links = compute_links_from_design(
            vector,
            hurdle=hurdle,
            dispersion=dispersion,
        )
        rows.append(
            S2DeterministicRow(
                merchant_id=merchant_id,
                bucket_id=int(vector.bucket),
                design_nb_mean=tuple(vector.x_nb_mean),
                design_nb_dispersion=tuple(vector.x_nb_dispersion),
                links=links,
            )
        )

    return S2DeterministicContext(
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        run_id=str(run_id),
        seed=int(seed),
        rows=tuple(rows),
    )


__all__ = [
    "S2DeterministicContext",
    "S2DeterministicRow",
    "build_deterministic_context",
]
