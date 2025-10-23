"""Runner for Segment 1B state-5 site→tile assignment (placeholder)."""

from __future__ import annotations

from .config import RunnerConfig
from ..exceptions import err


class S5SiteTileAssignmentRunner:
    """High-level orchestration for S5 (currently a scaffold)."""

    def run(self, config: RunnerConfig, /) -> None:
        raise err("E500_NOT_IMPLEMENTED", "state-5 site→tile assignment not implemented yet")


__all__ = ["S5SiteTileAssignmentRunner"]
