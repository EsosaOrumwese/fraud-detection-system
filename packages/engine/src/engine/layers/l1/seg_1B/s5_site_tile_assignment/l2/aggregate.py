"""Aggregation facade for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import numpy as np
import polars as pl

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine

from ..exceptions import err
from ..l1.assignment import AssignmentResult, build_assignments
from .prepare import PreparedInputs


@dataclass(frozen=True)
class AssignmentContext:
    """Context payload passed to the assignment kernel."""

    prepared: PreparedInputs
    run_id: str
    seed_int: int
    engine: PhiloxEngine


def build_assignment_context(prepared: PreparedInputs) -> AssignmentContext:
    """Construct the RNG engine and run identity for assignment."""

    try:
        seed_int = int(prepared.config.seed)
    except ValueError as exc:
        raise err(
            "E501_INVALID_SEED",
            f"seed '{prepared.config.seed}' must be a base-10 integer",
        ) from exc
    if not (0 <= seed_int < 2**64):
        raise err(
            "E501_INVALID_SEED",
            f"seed {seed_int} outside [0, 2^64)",
        )

    engine = PhiloxEngine(
        seed=seed_int,
        manifest_fingerprint=prepared.config.manifest_fingerprint,
    )
    run_id = uuid4().hex
    return AssignmentContext(prepared=prepared, run_id=run_id, seed_int=seed_int, engine=engine)


def compute_assignments(context: AssignmentContext) -> AssignmentResult:
    """Execute the deterministic assignment kernel."""

    prepared = context.prepared
    allocations = prepared.alloc_plan.frame.with_columns(
        pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase()
    )
    if allocations.is_empty():
        raise err(
            "E504_SUM_TO_N_MISMATCH",
            "s4_alloc_plan contains no rows for the requested identity",
        )

    iso_codes = prepared.iso_table.codes
    countries = allocations.get_column("legal_country_iso").unique().to_list()

    tile_lookup: dict[str, np.ndarray] = {}
    for country_iso in countries:
        country = str(country_iso).upper()
        country_tiles = prepared.tile_index.collect_country(country)
        if country_tiles.is_empty():
            raise err(
                "E505_TILE_NOT_IN_INDEX",
                f"tile_index partition missing coverage for country '{country}'",
            )
        tile_ids = country_tiles.get_column("tile_id").to_numpy().astype(np.uint64, copy=False)
        tile_lookup[country] = tile_ids

    return build_assignments(
        allocations=allocations,
        iso_codes=iso_codes,
        allowed_tiles=tile_lookup,
        engine=context.engine,
        parameter_hash=prepared.config.parameter_hash,
        manifest_fingerprint=prepared.config.manifest_fingerprint,
        seed_int=context.seed_int,
        run_id=context.run_id,
    )


__all__ = ["AssignmentContext", "build_assignment_context", "compute_assignments"]
