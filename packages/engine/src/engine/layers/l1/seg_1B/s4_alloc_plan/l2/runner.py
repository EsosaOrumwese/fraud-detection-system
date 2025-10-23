"""Placeholder runner for Segment 1B State-4."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..exceptions import S4Error, err
from .config import RunnerConfig


class S4AllocPlanRunner:
    """Scaffolding for the S4 allocation plan orchestrator."""

    def run(
        self,
        config: RunnerConfig,
        *,
        dictionary: Optional[Mapping[str, object]] = None,
    ) -> Any:
        """Execute S4 once implemented.

        For now, raise a structured error to signal the state is not yet available.
        """

        raise err("S4_NOT_IMPLEMENTED", "State-4 allocation plan is not implemented yet")


__all__ = ["S4AllocPlanRunner"]
