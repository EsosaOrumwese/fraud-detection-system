"""Dataclasses describing resolved inputs for Segment 2A S3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimetableAssets:
    """Filesystem assets required by S3."""

    tzdb_dir: Path
    tz_world: Path
    sealed_inventory_path: Path
    tzdb_release_tag: str
    tzdb_archive_sha256: str
    tz_world_dataset_id: str


@dataclass(frozen=True)
class TimetableContext:
    """Run-scoped context prepared before the timetable cache kernel executes."""

    data_root: Path
    manifest_fingerprint: str
    receipt_path: Path
    verified_at_utc: str
    assets: TimetableAssets
