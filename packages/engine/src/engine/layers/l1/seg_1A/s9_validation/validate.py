"""Thin wrapper re-exporting the Segment 1A S9 validator."""

from __future__ import annotations

from .validator_core import validate_outputs

__all__ = ["validate_outputs"]
