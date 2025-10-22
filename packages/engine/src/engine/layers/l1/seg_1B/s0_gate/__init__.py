"""Public facade for Segment 1B state-0 (gate-in & foundations).

Only re-export the orchestration surface so callers can drive the state
without being coupled to the internal module layout.
"""

from .l2.runner import S0GateRunner, GateInputs, GateResult

__all__ = ["S0GateRunner", "GateInputs", "GateResult"]
