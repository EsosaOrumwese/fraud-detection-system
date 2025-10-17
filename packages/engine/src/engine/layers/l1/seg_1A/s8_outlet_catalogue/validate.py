"""Validation utilities for S8 outlet catalogue outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


class S8ValidationError(RuntimeError):
    """Raised when S8 validation fails."""


def validate_outputs(
    *,
    catalogue_path: Path,
    event_paths: Mapping[str, Path],
    bundle_dir: Path,
) -> Mapping[str, object]:
    """Run the S8 validation battery and return the metrics payload."""
    raise NotImplementedError("S8 validator has not been implemented yet.")


__all__ = [
    "S8ValidationError",
    "validate_outputs",
]
