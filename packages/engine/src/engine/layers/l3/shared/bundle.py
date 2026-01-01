"""Shared validation bundle helpers for Layer-3 segments."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Iterable, List

_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")


@dataclass(frozen=True)
class IndexEntry:
    """Single artefact entry inside a validation bundle index."""

    artifact_id: str
    path: str
    raw: dict


@dataclass(frozen=True)
class BundleIndex:
    """Parsed representation of a validation bundle index."""

    entries: List[IndexEntry]

    def ascii_paths(self) -> list[str]:
        return sorted(entry.path for entry in self.entries)

    def iter_entries(self) -> Iterable[IndexEntry]:
        return iter(self.entries)


def load_index_file(index_path: Path, bundle_dir: Path) -> BundleIndex:
    """Parse and validate a validation bundle index from an explicit file path."""

    if not index_path.exists():
        raise FileNotFoundError(f"validation bundle index missing: {index_path}")

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"validation bundle index is not valid JSON: {exc}") from exc

    if isinstance(payload, dict):
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list):
            raise ValueError("validation bundle index `artifacts` section must be a JSON array")
        payload = artifacts
    elif not isinstance(payload, list):
        raise ValueError("validation bundle index must be a JSON array")

    entries: list[IndexEntry] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(
                f"validation bundle entry {idx} must be an object, found {type(item).__name__}"
            )
        artifact_id = item.get("artifact_id")
        path_value = item.get("path")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError(f"validation bundle entry {idx} missing string artifact_id")
        if not artifact_id.isascii():
            raise ValueError(f"validation bundle artifact_id '{artifact_id}' must be ASCII")
        if artifact_id in seen_ids:
            raise ValueError(f"duplicate validation bundle artifact_id '{artifact_id}'")
        seen_ids.add(artifact_id)

        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"validation bundle entry {artifact_id} missing string path")
        if not path_value.isascii():
            raise ValueError(f"validation bundle entry '{artifact_id}' has non-ASCII path")
        if path_value.startswith(("/", "\\")):
            raise ValueError(f"validation bundle entry '{artifact_id}' has absolute path '{path_value}'")

        posix = PurePosixPath(path_value)
        if ".." in posix.parts:
            raise ValueError(f"validation bundle entry '{artifact_id}' has non-relative path '{path_value}'")
        if path_value in seen_paths:
            raise ValueError(f"duplicate validation bundle index path '{path_value}'")
        seen_paths.add(path_value)
        entries.append(IndexEntry(artifact_id=artifact_id, path=path_value, raw=item))

    _assert_index_matches_files(bundle_dir, seen_paths)
    return BundleIndex(entries=entries)


def _assert_index_matches_files(bundle_dir: Path, indexed_paths: set[str]) -> None:
    """Ensure the index exactly covers all non-flag files in the bundle."""

    non_flag_files = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.name != "_passed.flag"
    }
    if indexed_paths != non_flag_files:
        missing = sorted(non_flag_files - indexed_paths)
        extra = sorted(indexed_paths - non_flag_files)
        parts: list[str] = []
        if missing:
            parts.append(f"missing entries for {missing}")
        if extra:
            parts.append(f"unexpected entries {extra}")
        detail = ", ".join(parts) if parts else "index/file mismatch"
        raise ValueError(detail)


def read_pass_flag(bundle_dir: Path, *, flag_name: str = "_passed.flag") -> str:
    """Read `_passed.flag` and return the declared digest."""

    flag_path = bundle_dir / flag_name
    if not flag_path.exists():
        raise FileNotFoundError(f"validation bundle missing {flag_name}")
    content = flag_path.read_text(encoding="utf-8")
    match = _FLAG_PATTERN.match(content.strip())
    if not match:
        raise ValueError(f"{flag_name} must be 'sha256_hex = <hex64>'")
    return match.group(1)


def compute_index_digest(bundle_dir: Path, index: BundleIndex) -> str:
    """Compute the SHA-256 digest over indexed files."""

    digest = sha256()
    for entry in sorted(index.iter_entries(), key=lambda e: e.path):
        relative_path = entry.path
        target = (bundle_dir / relative_path).resolve()
        sha_override = entry.raw.get("sha256_hex") if isinstance(entry.raw, dict) else None
        sha_match = isinstance(sha_override, str) and re.fullmatch(r"[a-f0-9]{64}", sha_override)
        if target.is_dir():
            if sha_match:
                digest.update(sha_override.encode("ascii"))
                continue
            raise ValueError(
                f"unable to read '{relative_path}' while computing digest (is directory)"
            )
        try:
            digest.update(target.read_bytes())
        except OSError as exc:
            if sha_match:
                digest.update(sha_override.encode("ascii"))
                continue
            raise ValueError(f"unable to read '{relative_path}' while computing digest") from exc
    return digest.hexdigest()


__all__ = ["BundleIndex", "IndexEntry", "compute_index_digest", "load_index_file", "read_pass_flag"]
