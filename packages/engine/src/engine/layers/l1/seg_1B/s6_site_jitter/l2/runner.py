"""Runner for Segment 1B state-6 site jitter."""

from __future__ import annotations

from .aggregate import build_context, execute_jitter
from .config import RunnerConfig
from .materialise import S6RunResult, materialise_jitter
from .prepare import PreparedInputs, prepare_inputs


class S6SiteJitterRunner:
    """High-level orchestration for S6."""

    def run(self, config: RunnerConfig) -> S6RunResult:
        prepared: PreparedInputs = prepare_inputs(config)
        context = build_context(prepared)
        outcome = execute_jitter(context)
        return materialise_jitter(
            prepared=prepared,
            outcome=outcome,
            run_id=context.run_id,
        )


__all__ = ["S6SiteJitterRunner"]
