"""Low-level helpers for working with upstream validation bundles."""

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

    if isinstance(payload, dict):
        entries_key = None
        if "artifacts" in payload:
            entries_key = "artifacts"
        elif "files" in payload:
            entries_key = "files"

        if entries_key is not None:
            entries_payload = payload.get(entries_key)
            if not isinstance(entries_payload, list):
                raise err(
                    "E_INDEX_INVALID",
                    f"index.json `{entries_key}` section must be a JSON array",
                )
            payload = entries_payload
        else:
            raise err(
                "E_INDEX_INVALID",
                "index.json must contain `artifacts` or `files` array",
            )
    elif not isinstance(payload, list):
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
        if path_value.startswith(("/", "\\")):
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


def read_pass_flag(bundle_dir: Path) -> str:
    """Read `_passed.flag` and return the declared digest."""

    flag_path = bundle_dir / "_passed.flag"
    if not flag_path.exists():
        raise err("E_PASS_MISSING", "validation bundle missing _passed.flag")
    content = flag_path.read_text(encoding="utf-8")
    match = _FLAG_PATTERN.match(content.strip())
    if not match:
        raise err(
            "E_FLAG_FORMAT_INVALID",
            "_passed.flag must be 'sha256_hex = <hex64>'",
        )
    return match.group(1)


def compute_index_digest(bundle_dir: Path, index: BundleIndex) -> str:
    """Compute the SHA-256 digest over the indexed files."""

    digest = sha256()
    for relative_path in index.ascii_paths():
        target = (bundle_dir / relative_path).resolve()
        try:
            digest.update(target.read_bytes())
        except OSError as exc:
            raise err(
                "E_INDEX_IO",
                f"unable to read '{relative_path}' while computing digest",
            ) from exc
    return digest.hexdigest()


__all__ = ["BundleIndex", "IndexEntry", "load_index", "read_pass_flag", "compute_index_digest"]
