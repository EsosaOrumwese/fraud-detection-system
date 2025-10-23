"""Runner for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

from .aggregate import (
    AssignmentContext,
    AssignmentResult,
    build_assignment_context,
    compute_assignments,
)
from .config import RunnerConfig
from .materialise import S5RunResult, materialise_assignment
from .prepare import PreparedInputs, prepare_inputs


class S5SiteTileAssignmentRunner:
    """High-level orchestration for S5 assignments."""

    def run(self, config: RunnerConfig, /) -> S5RunResult:
        prepared: PreparedInputs = prepare_inputs(config)
        context: AssignmentContext = build_assignment_context(prepared)
        assignment: AssignmentResult = compute_assignments(context)
        return materialise_assignment(
            prepared=prepared,
            assignment=assignment,
            iso_version=prepared.iso_version,
        )


__all__ = ["S5SiteTileAssignmentRunner"]
