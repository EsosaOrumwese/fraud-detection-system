"""Filesystem helpers for Segment 2A S0 implementation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, List, Sequence

from ....seg_1A.s0_foundations.l0.artifacts import ArtifactDigest, hash_artifacts
from ..exceptions import err


def ensure_within_base(path: Path, *, base_path: Path) -> None:
    """Ensure ``path`` resides within ``base_path``."""

    base_resolved = base_path.resolve()
    target = path.resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError as exc:
        raise err(
            "E_PATH_OUT_OF_SCOPE",
            f"path '{target}' escapes base directory '{base_resolved}'",
        ) from exc


def expand_files(path: Path) -> List[Path]:
    """Return a deterministic list of files anchored at ``path``."""

    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file())
    raise err("E_PATH_MISSING", f"expected file or directory at '{path}'")


def hash_files(paths: Sequence[Path], *, error_prefix: str) -> List[ArtifactDigest]:
    """Hash ``paths`` using the Segment 1A artefact helpers."""

    if not paths:
        raise err(f"{error_prefix}_EMPTY", "no files resolved for hashing")
    return hash_artifacts(paths, error_prefix=error_prefix)


def aggregate_sha256(digests: Iterable[ArtifactDigest]) -> str:
    """Aggregate a collection of digests into a single SHA-256 hex string."""

    hasher = hashlib.sha256()
    for digest in sorted(digests, key=lambda d: d.basename):
        hasher.update(digest.sha256_digest)
    return hasher.hexdigest()


def total_size_bytes(digests: Iterable[ArtifactDigest]) -> int:
    """Return the total size over all artefacts."""

    return sum(d.size_bytes for d in digests)


__all__ = [
    "ArtifactDigest",
    "ensure_within_base",
    "expand_files",
    "hash_files",
    "aggregate_sha256",
    "total_size_bytes",
]
