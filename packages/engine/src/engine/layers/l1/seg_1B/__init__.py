"""Segment 1B package.

The initial surface is intentionally small: only the S0 gate is exposed while
the remaining states are implemented. Higher layers should import from this
module rather than reaching into the nested ``l0``/``l1``/``l2`` structure.
"""

from .s0_gate.l2.runner import S0GateRunner, GateInputs, GateResult

# S1 Tile Index scaffolding lives under ``s1_tile_index`` and will export its
# public surface once the state implementation is in place.

__all__ = ["S0GateRunner", "GateInputs", "GateResult"]
