"""Scope helpers for instance-proof requirements."""

from __future__ import annotations


def is_instance_scope(scope: str | None) -> bool:
    if not scope:
        return False
    tokens = ("seed", "scenario_id", "parameter_hash", "run_id")
    return any(token in scope for token in tokens)
