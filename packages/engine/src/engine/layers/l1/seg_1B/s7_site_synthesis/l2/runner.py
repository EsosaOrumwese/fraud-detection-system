"""Runner for Segment 1B state-7 site synthesis."""

from __future__ import annotations

from .aggregate import build_context, execute_synthesis
from .config import RunnerConfig
from .materialise import S7RunResult, generate_run_id, materialise_synthesis
from .prepare import PreparedInputs, prepare_inputs


class S7SiteSynthesisRunner:
    """High-level orchestration for S7."""

    def run(self, config: RunnerConfig) -> S7RunResult:
        prepared: PreparedInputs = prepare_inputs(config)
        context = build_context(prepared)
        outcome = execute_synthesis(context)
        run_id = generate_run_id()
        return materialise_synthesis(
            prepared=prepared,
            outcome=outcome,
            run_id=run_id,
        )


__all__ = ["S7SiteSynthesisRunner"]
