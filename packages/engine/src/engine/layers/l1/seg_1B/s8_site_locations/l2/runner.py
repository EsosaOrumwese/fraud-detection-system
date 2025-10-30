"""Runner for Segment 1B state-8 site_locations."""

from __future__ import annotations

from .aggregate import build_context, execute_egress
from .config import RunnerConfig
from .materialise import S8RunResult, generate_run_id, materialise_site_locations
from .prepare import PreparedInputs, prepare_inputs


class S8SiteLocationsRunner:
    """High-level orchestration for S8."""

    def run(self, config: RunnerConfig) -> S8RunResult:
        prepared: PreparedInputs = prepare_inputs(config)
        context = build_context(prepared)
        outcome = execute_egress(context)
        run_id = generate_run_id()
        return materialise_site_locations(
            prepared=prepared,
            outcome=outcome,
            run_id=run_id,
        )


__all__ = ["S8SiteLocationsRunner"]
