"""Dataclasses describing resolved inputs for Segment 2A S5."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ValidationAssets:
    """Filesystem assets required by S5."""

    site_timezones_root: Path
    tz_cache_dir: Path


@dataclass(frozen=True)
class TzCacheManifestSummary:
    """Materialised tz cache manifest metadata."""

    path: Path
    tzdb_release_tag: str
    tzdb_archive_sha256: str
    tz_index_digest: str
    rle_cache_bytes: int
    created_utc: str


@dataclass(frozen=True)
class ValidationContext:
    """Run-scoped context prepared before the validation bundle kernel executes."""

    data_root: Path
    manifest_fingerprint: str
    receipt_path: Path
    verified_at_utc: str
    dictionary: Mapping[str, object]
    assets: ValidationAssets
    tz_cache_manifest: TzCacheManifestSummary
