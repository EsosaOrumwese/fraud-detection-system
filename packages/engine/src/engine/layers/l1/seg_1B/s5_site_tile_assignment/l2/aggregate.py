"""Aggregation facade for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

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
    allowed_tiles = {
        (str(row[0]).upper(), int(row[1]))
        for row in prepared.tile_index.frame.iter_rows()
    }
    iso_codes = prepared.iso_table.codes

    return build_assignments(
        allocations=prepared.alloc_plan.frame,
        iso_codes=iso_codes,
        allowed_tiles=allowed_tiles,
        engine=context.engine,
        parameter_hash=prepared.config.parameter_hash,
        manifest_fingerprint=prepared.config.manifest_fingerprint,
        seed_int=context.seed_int,
        run_id=context.run_id,
    )


__all__ = ["AssignmentContext", "build_assignment_context", "compute_assignments"]
