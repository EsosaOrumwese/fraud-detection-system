"""Segment 3B package entrypoint."""

from .s0_gate import GateInputs as S0GateInputs, GateOutputs as S0GateOutputs, S0GateRunner
from .s1_virtuals import VirtualsInputs, VirtualsResult, VirtualsRunner
from .s2_edges import EdgesInputs, EdgesResult, EdgesRunner
from .s3_alias import AliasInputs, AliasResult, AliasRunner

__all__ = [
    "S0GateInputs",
    "S0GateOutputs",
    "S0GateRunner",
    "VirtualsInputs",
    "VirtualsResult",
    "VirtualsRunner",
    "EdgesInputs",
    "EdgesResult",
    "EdgesRunner",
    "AliasInputs",
    "AliasResult",
    "AliasRunner",
]
