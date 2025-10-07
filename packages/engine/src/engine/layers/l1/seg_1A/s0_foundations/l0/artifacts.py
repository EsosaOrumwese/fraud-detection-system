"""Filesystem helpers for artefact hashing (S0.2)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from ..exceptions import err

_BUFFER_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ArtifactDigest:
    """Metadata captured while hashing an artefact."""

    basename: str
    path: Path
    size_bytes: int
    mtime_ns: int
    sha256_digest: bytes

    @property
    def sha256_hex(self) -> str:
        return self.sha256_digest.hex()


def _ensure_ascii(name: str, *, error_code: str) -> None:
    try:
        name.encode("ascii")
    except UnicodeEncodeError as exc:  # pragma: no cover - extremely unlikely
        raise err(error_code, f"non-ASCII basename '{name}'") from exc


def hash_artifact(path: Path, *, error_prefix: str) -> ArtifactDigest:
    """Hash a file while guarding against TOCTOU races.

    Parameters
    ----------
    path:
        Absolute or relative path to hash.
    error_prefix:
        Used when raising spec-aligned errors, e.g. ``E_PARAM`` or ``E_ARTIFACT``.
    """

    if not path.exists():
        raise err(f"{error_prefix}_IO", f"artefact '{path}' not found")
    if not path.is_file():
        raise err(f"{error_prefix}_IO", f"artefact '{path}' is not a file")

    stat_before = path.stat()
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_BUFFER_SIZE):
            hasher.update(chunk)
    digest = hasher.digest()
    stat_after = path.stat()
    if stat_before.st_mtime_ns != stat_after.st_mtime_ns or stat_before.st_size != stat_after.st_size:
        raise err(f"{error_prefix}_RACE", f"artefact '{path}' changed while hashing")

    basename = path.name
    _ensure_ascii(basename, error_code=f"{error_prefix}_NONASCII_NAME")
    return ArtifactDigest(
        basename=basename,
        path=path,
        size_bytes=stat_after.st_size,
        mtime_ns=stat_after.st_mtime_ns,
        sha256_digest=digest,
    )


def hash_artifacts(paths: Iterable[Path], *, error_prefix: str) -> List[ArtifactDigest]:
    """Hash a collection of artefacts and enforce basename uniqueness."""

    digests: List[ArtifactDigest] = []
    seen = set()
    for path in paths:
        digest = hash_artifact(path, error_prefix=error_prefix)
        if digest.basename in seen:
            raise err(f"{error_prefix}_DUP_BASENAME", f"duplicate basename '{digest.basename}'")
        seen.add(digest.basename)
        digests.append(digest)
    return digests


__all__ = ["ArtifactDigest", "hash_artifact", "hash_artifacts"]
