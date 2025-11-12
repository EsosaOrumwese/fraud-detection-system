"""Dataclasses describing resolved inputs for Segment 2A S4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ...shared.tz_assets import TzAdjustmentsSummary


@dataclass(frozen=True)
class LegalityAssets:
    """Filesystem assets required by S4."""

    site_timezones_path: Path
    tz_cache_dir: Path
    tz_cache_manifest_path: Path
    tz_cache_index_path: Path


@dataclass(frozen=True)
class LegalityContext:
    """Run-scoped context prepared before the legality kernel executes."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    receipt_path: Path
    verified_at_utc: str
    assets: LegalityAssets
    tz_adjustments: TzAdjustmentsSummary | None
    determinism_receipt: Mapping[str, object]
