"""Dataclasses describing resolved inputs for Segment 2A S1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProvisionalLookupAssets:
    """Filesystem paths to the artefacts required by S1."""

    site_locations: Path
    tz_world: Path
    tz_nudge: Path
    tz_overrides: Path | None


@dataclass(frozen=True)
class ProvisionalLookupContext:
    """Run-scoped context prepared before the lookup kernel executes."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    receipt_path: Path
    verified_at_utc: str
    assets: ProvisionalLookupAssets
