"""Filesystem helpers for Segment 2B S0."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ..exceptions import err


@dataclass(frozen=True)
class ArtifactDigest:
    """Digest metadata for a sealed artefact."""

    path: Path
    sha256_hex: str
    size_bytes: int

    @property
    def basename(self) -> str:
        return self.path.name


def ensure_within_base(target: Path, *, base_path: Path) -> None:
    """Ensure ``target`` resides under ``base_path``."""

    try:
        target.relative_to(base_path)
    except ValueError as exc:
        raise err(
            "E_PATH_ESCAPE",
            f"path '{target}' is outside base directory '{base_path}'",
        ) from exc


def expand_files(path: Path) -> list[Path]:
    """Expand ``path`` into a list of files (recursively for directories)."""

    if not path.exists():
        raise err("E_ASSET_MISSING", f"asset path '{path}' is missing")
    if path.is_file():
        return [path]
    results = sorted(file for file in path.rglob("*") if file.is_file())
    if not results:
        raise err("E_ASSET_EMPTY", f"directory '{path}' contains no files")
    return results


def hash_files(paths: Sequence[Path], *, error_prefix: str) -> list[ArtifactDigest]:
    """Hash the provided files using SHA-256."""

    digests: list[ArtifactDigest] = []
    for path in paths:
        if not path.exists():
            raise err(error_prefix, f"asset file '{path}' missing during hashing")
        if not path.is_file():
            raise err(error_prefix, f"asset path '{path}' is not a file")
        sha = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
                size += len(chunk)
        digests.append(
            ArtifactDigest(path=path, sha256_hex=sha.hexdigest(), size_bytes=size)
        )
    return digests


def aggregate_sha256(digests: Iterable[ArtifactDigest]) -> str:
    """Aggregate multiple digests into a single SHA-256."""

    sha = hashlib.sha256()
    for digest in sorted(
        digests, key=lambda entry: (entry.basename, str(entry.path))
    ):
        sha.update(digest.sha256_hex.encode("ascii"))
    return sha.hexdigest()


def total_size_bytes(digests: Iterable[ArtifactDigest]) -> int:
    """Compute the total size across digests."""

    return sum(digest.size_bytes for digest in digests)


__all__ = [
    "ArtifactDigest",
    "aggregate_sha256",
    "ensure_within_base",
    "expand_files",
    "hash_files",
    "total_size_bytes",
]

