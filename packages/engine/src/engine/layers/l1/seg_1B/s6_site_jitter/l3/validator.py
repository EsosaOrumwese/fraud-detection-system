"""Validator placeholder for Segment 1B state-6."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from ..exceptions import err


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S6 outputs."""

    data_root: Path
    seed: str
    manifest_fingerprint: str
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    run_report_path: Optional[Path] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


class S6SiteJitterValidator:
    """Validate S6 outputs (to be implemented in a later phase)."""

    def validate(self, config: ValidatorConfig) -> None:
        raise err("E699_NOT_IMPLEMENTED", "state-6 validator not implemented yet")


__all__ = ["S6SiteJitterValidator", "ValidatorConfig"]
