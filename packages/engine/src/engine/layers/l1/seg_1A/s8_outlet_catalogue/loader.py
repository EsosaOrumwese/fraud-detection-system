"""Load deterministic inputs required by the S8 pipeline."""

from __future__ import annotations

from pathlib import Path

from .contexts import S8DeterministicContext


def load_deterministic_context(
    *,
    base_path: Path,
    parameter_hash: str,
    manifest_fingerprint: str,
    seed: int,
    run_id: str,
) -> S8DeterministicContext:
    """Resolve upstream artefacts and build the immutable S8 context."""
    raise NotImplementedError("S8 deterministic loader has not been implemented yet.")


__all__ = [
    "load_deterministic_context",
]
