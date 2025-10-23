"""Persistence helpers for Segment 1B S9 validation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class PersistConfig:
    """Configuration for publishing the validation bundle."""

    base_path: Path
    manifest_fingerprint: str


def write_validation_bundle(
    *,
    artifacts: Mapping[str, bytes],
    config: PersistConfig,
) -> tuple[Path, Path | None]:
    """Write bundle artefacts to the governed fingerprint folder."""

    raise NotImplementedError("S9 bundle persistence not implemented yet")


def write_stage_log(*, path: Path, records: Sequence[Mapping[str, object]]) -> None:
    """Persist stage log records to disk."""

    raise NotImplementedError("S9 stage logging not implemented yet")


__all__ = ["PersistConfig", "write_validation_bundle", "write_stage_log"]
