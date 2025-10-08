"""Filesystem helpers for the artefact hashing steps performed in S0.2.

S0 treats every external file it opens (parameters, references, governance) as
part of the manifest.  These utilities provide the deterministic hashing logic
that underpins ``parameter_hash`` and ``manifest_fingerprint``.  Keeping the
helpers close to the disk I/O layer keeps higher-level code focused on the
business rules while still making the manifest logic easy to audit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from ..exceptions import err

_BUFFER_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ArtifactDigest:
    """Metadata captured while hashing an artefact.

    The dataclass mirrors the columns we later emit into
    ``param_digest_log.jsonl`` / ``fingerprint_artifacts.jsonl``.  Using a
    strong typed container instead of a loose dict means upstream callers can
    rely on attribute names and we get a tiny amount of linting support for
    free.
    """

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
    """Return the deterministic SHA-256 digest for ``path``.

    The helper double-checks file size and modification time before and after
    reading so a racing writer cannot slip new bytes into the hash.  Any
    anomaly is surfaced via the spec-aligned error code provided by
    ``error_prefix`` (e.g. ``E_PARAM`` during parameter hashing or
    ``E_ARTIFACT`` when computing the manifest fingerprint).
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
    if (
        stat_before.st_mtime_ns != stat_after.st_mtime_ns
        or stat_before.st_size != stat_after.st_size
    ):
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
    """Hash a collection of artefacts and enforce basename uniqueness.

    The manifest specs require that basenames are unique so that validation can
    match rows back to files unambiguously.  This function performs that check
    while preserving the order in which the caller supplied the paths.
    """

    digests: List[ArtifactDigest] = []
    seen = set()
    for path in paths:
        digest = hash_artifact(path, error_prefix=error_prefix)
        if digest.basename in seen:
            raise err(
                f"{error_prefix}_DUP_BASENAME",
                f"duplicate basename '{digest.basename}'",
            )
        seen.add(digest.basename)
        digests.append(digest)
    return digests


__all__ = ["ArtifactDigest", "hash_artifact", "hash_artifacts"]
