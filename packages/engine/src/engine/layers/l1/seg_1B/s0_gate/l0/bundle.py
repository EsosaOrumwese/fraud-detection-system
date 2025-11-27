"""Low-level helpers for working with the 1A validation bundle."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Iterable, List

from ..exceptions import err

_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")


@dataclass(frozen=True)
class IndexEntry:
    """Single artefact entry inside ``index.json``."""

    artifact_id: str
    path: str
    raw: dict


@dataclass(frozen=True)
class BundleIndex:
    """Parsed representation of ``index.json`` with light validation."""

    entries: List[IndexEntry]

    def ascii_paths(self) -> list[str]:
        return sorted(entry.path for entry in self.entries)

    def paths(self) -> set[str]:
        return {entry.path for entry in self.entries}

    def iter_entries(self) -> Iterable[IndexEntry]:
        return iter(self.entries)


def load_index(bundle_dir: Path) -> BundleIndex:
    """Parse and validate ``index.json`` from ``bundle_dir``."""

    index_path = bundle_dir / "index.json"
    if not index_path.exists():
        raise err("E_INDEX_MISSING", f"validation bundle missing '{index_path.name}'")

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("E_INDEX_INVALID", f"index.json is not valid JSON: {exc}") from exc

    if not isinstance(payload, list):
        raise err("E_INDEX_INVALID", "index.json must be a JSON array")

    entries: list[IndexEntry] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise err(
                "E_INDEX_INVALID",
                f"index.json entry {idx} must be an object, found {type(item).__name__}",
            )

        artifact_id = item.get("artifact_id")
        path_value = item.get("path")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise err(
                "E_INDEX_INVALID",
                f"index.json entry {idx} missing string artifact_id",
            )
        if not artifact_id.isascii():
            raise err(
                "E_INDEX_INVALID",
                f"index.json artifact_id '{artifact_id}' must be ASCII",
            )
        if artifact_id in seen_ids:
            raise err("E_INDEX_INVALID", f"duplicate artifact_id '{artifact_id}'")
        seen_ids.add(artifact_id)

        if not isinstance(path_value, str) or not path_value:
            raise err(
                "E_INDEX_INVALID",
                f"index.json entry {artifact_id} missing string path",
            )
        if not path_value.isascii():
            raise err(
                "E_INDEX_INVALID",
                f"index entry '{artifact_id}' has non-ASCII path",
            )
        if path_value.startswith("/") or path_value.startswith("\\"):
            raise err(
                "E_INDEX_INVALID",
                f"index entry '{artifact_id}' has absolute path '{path_value}'",
            )

        posix = PurePosixPath(path_value)
        if ".." in posix.parts:
            raise err(
                "E_INDEX_INVALID",
                f"index entry '{artifact_id}' has non-relative path '{path_value}'",
            )
        if path_value in seen_paths:
            raise err(
                "E_INDEX_INVALID",
                f"duplicate index path '{path_value}'",
            )
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
        raise err("E_INDEX_INVALID", detail)


def read_pass_flag(bundle_dir: Path, *, flag_name: str = "_passed.flag") -> str:
    """Read `_passed.flag` and return the declared digest."""

    flag_path = bundle_dir / flag_name
    if not flag_path.exists():
        raise err("E_PASS_MISSING", f"validation bundle missing {flag_name}")
    content = flag_path.read_text(encoding="utf-8")
    match = _FLAG_PATTERN.match(content.strip())
    if not match:
        raise err(
            "E_FLAG_FORMAT_INVALID",
            f"{flag_name} must be 'sha256_hex = <hex64>'",
        )
    return match.group(1)


def compute_index_digest(bundle_dir: Path, index: BundleIndex) -> str:
    """Compute the SHA-256 digest over the indexed files."""

    digest = sha256()
    for entry in sorted(index.iter_entries(), key=lambda e: e.path):
        relative_path = entry.path
        target = (bundle_dir / relative_path).resolve()
        try:
            target.relative_to(bundle_dir.resolve())
        except ValueError as exc:
            raise err(
                "E_INDEX_INVALID",
                f"indexed path '{relative_path}' escapes the bundle directory",
            ) from exc
        sha_override = entry.raw.get("sha256_hex") if isinstance(entry.raw, dict) else None
        sha_match = isinstance(sha_override, str) and re.fullmatch(r"[a-f0-9]{64}", sha_override)
        if target.is_dir():
            if sha_match:
                digest.update(sha_override.encode("ascii"))
                continue
            raise err(
                "E_INDEX_INVALID",
                f"indexed path '{relative_path}' points to a directory without sha256_hex",
            )
        if not target.exists():
            if sha_match:
                digest.update(sha_override.encode("ascii"))
                continue
            raise err(
                "E_INDEX_INVALID",
                f"indexed path '{relative_path}' does not exist on disk",
            )
        digest.update(target.read_bytes())
    return digest.hexdigest()


__all__ = ["BundleIndex", "IndexEntry", "load_index", "read_pass_flag", "compute_index_digest"]
