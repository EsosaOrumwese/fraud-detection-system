"""Configuration models for S8 runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


@dataclass(frozen=True)
class RunnerConfig:
    """User-supplied configuration for executing S8."""

    data_root: Path
    manifest_fingerprint: str
    seed: str
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


__all__ = ["RunnerConfig"]
