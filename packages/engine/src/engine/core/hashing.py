"""Hashing utilities with race checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from engine.core.errors import HashingError


@dataclass(frozen=True)
class FileDigest:
    path: Path
    size_bytes: int
    mtime_ns: int
    sha256_hex: str


def _stat(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> FileDigest:
    if not path.exists():
        raise HashingError(f"Missing file for hashing: {path}")
    size_before, mtime_before = _stat(path)
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    size_after, mtime_after = _stat(path)
    if size_before != size_after or mtime_before != mtime_after:
        raise HashingError(f"File changed during hashing: {path}")
    return FileDigest(path=path, size_bytes=size_after, mtime_ns=mtime_after, sha256_hex=h.hexdigest())


def sha256_concat(parts: Iterable[bytes]) -> bytes:
    h = hashlib.sha256()
    for part in parts:
        h.update(part)
    return h.digest()
