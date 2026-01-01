"""Persistence helpers for Segment 1B S9 validation outputs."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from uuid import uuid4

from ..shared import dictionary as dict_utils
from . import constants as c
from .exceptions import err


@dataclass(frozen=True)
class PersistConfig:
    """Configuration for publishing the validation bundle."""

    base_path: Path
    manifest_fingerprint: str
    dictionary: Mapping[str, object]


def write_validation_bundle(
    *,
    artifacts: Mapping[str, bytes],
    config: PersistConfig,
    passed: bool,
) -> tuple[Path, Path | None]:
    """Write bundle artefacts to the governed fingerprint folder."""

    base_path = Path(config.base_path).expanduser().resolve()
    dictionary = config.dictionary
    bundle_path = dict_utils.resolve_dataset_path(
        c.BUNDLE_ROOT_DATASET_ID,
        base_path=base_path,
        template_args={"manifest_fingerprint": config.manifest_fingerprint},
        dictionary=dictionary,
    )

    stage_dir = bundle_path.parent / f".s9_validation_bundle_{uuid4().hex}"
    stage_dir.mkdir(parents=True, exist_ok=True)

    try:
        for relative_path, payload in artifacts.items():
            target = stage_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)

        flag_bytes: bytes | None = None
        if passed:
            digest = _compute_bundle_digest(stage_dir)
            flag_bytes = f"sha256_hex = {digest}".encode("ascii")
            (stage_dir / "_passed.flag").write_bytes(flag_bytes)

        if bundle_path.exists():
            _ensure_existing_bundle_identity(bundle_path, artifacts, flag_bytes)
            shutil.rmtree(stage_dir, ignore_errors=True)
        else:
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stage_dir), str(bundle_path))

    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    flag_path = bundle_path / "_passed.flag"
    if not flag_path.exists():
        flag_path = None

    return bundle_path, flag_path


def write_stage_log(*, path: Path, records: Sequence[Mapping[str, object]]) -> None:
    """Persist stage log records to disk."""

    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _ensure_existing_bundle_identity(
    bundle_path: Path,
    artifacts: Mapping[str, bytes],
    flag_bytes: bytes | None,
) -> None:
    for relative_path, payload in artifacts.items():
        existing_file = bundle_path / relative_path
        if not existing_file.exists():
            raise err(
                "E913_ATOMIC_PUBLISH_VIOLATION",
                f"existing bundle missing expected artifact '{relative_path}'",
            )
        if existing_file.read_bytes() != payload:
            raise err(
                "E913_ATOMIC_PUBLISH_VIOLATION",
                f"existing bundle artifact '{relative_path}' differs from staged content",
            )

    existing_flag = bundle_path / "_passed.flag"
    if flag_bytes is None:
        return

    if not existing_flag.exists():
        raise err(
            "E913_ATOMIC_PUBLISH_VIOLATION",
            "existing bundle missing _passed.flag for a passing run",
        )
    if existing_flag.read_bytes() != flag_bytes:
        raise err(
            "E913_ATOMIC_PUBLISH_VIOLATION",
            "_passed.flag content mismatch for re-publish",
        )


def _compute_bundle_digest(bundle_dir: Path) -> str:
    index_path = bundle_dir / "index.json"
    if not index_path.exists():
        raise err("E908_BUNDLE_CONTENTS_MISSING", "index.json missing from bundle")
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("E909_INDEX_INVALID", f"index.json invalid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise err("E909_INDEX_INVALID", "index.json must be a list of entries")

    hasher = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item.get("path", "")):
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise err("E909_INDEX_INVALID", "index entry missing path")
        if path == "_passed.flag":
            continue
        file_path = bundle_dir / path
        if not file_path.exists():
            raise err("E908_BUNDLE_CONTENTS_MISSING", f"bundle file missing: {path}")
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


__all__ = ["PersistConfig", "write_validation_bundle", "write_stage_log"]
