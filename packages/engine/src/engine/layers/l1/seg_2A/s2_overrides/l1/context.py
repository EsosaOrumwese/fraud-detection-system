"""Dataclasses describing resolved inputs for Segment 2A S2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ...shared.receipt import SealedInputRecord

@dataclass(frozen=True)
class OverridesAssets:
    """Filesystem assets required by S2."""

    s1_tz_lookup: Path
    tz_overrides: Path
    tz_world: Path
    merchant_mcc_map: Path | None = None


@dataclass(frozen=True)
class OverridesContext:
    """Run-scoped context prepared before the overrides kernel executes."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    upstream_manifest_fingerprint: str
    receipt_path: Path
    verified_at_utc: str
    assets: OverridesAssets
    sealed_assets: Mapping[str, SealedInputRecord]
    determinism_receipt: Mapping[str, object]

