"""Validator for Segment 1B state-5 site→tile assignment (placeholder)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from ..exceptions import err


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S5 site→tile assignment output."""

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


class S5SiteTileAssignmentValidator:
    """Validate S5 outputs (scaffold)."""

    def validate(self, config: ValidatorConfig) -> None:
        raise err("E500_NOT_IMPLEMENTED", "state-5 validator not implemented yet")


__all__ = ["S5SiteTileAssignmentValidator", "ValidatorConfig"]
