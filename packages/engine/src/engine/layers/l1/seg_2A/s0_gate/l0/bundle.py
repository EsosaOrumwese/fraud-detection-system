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
    version: str | None = None

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

    index_version: str | None = None
    if isinstance(payload, dict):
        entries_key = None
        if "artifacts" in payload:
            entries_key = "artifacts"
        elif "files" in payload:
            entries_key = "files"
        elif "items" in payload:
            entries_key = "items"
        version_value = payload.get("version")
        if isinstance(version_value, str):
            index_version = version_value
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

        path_value = item.get("path")
        artifact_id = item.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            # tolerate legacy entries without artifact_id by falling back to path
            if isinstance(path_value, str) and path_value:
                artifact_id = path_value
            else:
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
        path_obj = Path(path_value)
        if path_obj.is_absolute():
            try:
                rel = path_obj.resolve().relative_to(bundle_dir.resolve())
                path_value = rel.as_posix()
            except Exception:
                path_value = path_obj.resolve().as_posix()

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
    return BundleIndex(entries=entries, version=index_version)


def _assert_index_matches_files(bundle_dir: Path, indexed_paths: set[str]) -> None:
    """Ensure the index exactly covers all non-flag files in the bundle."""

    ignore: set[str] = {"_passed.flag", "index.json"}
    indexed = {p for p in indexed_paths if not Path(p).is_absolute()} - ignore
    if not indexed:
        return
    non_flag_files = {
        path.relative_to(bundle_dir).as_posix()
        for path in bundle_dir.rglob("*")
        if path.is_file() and path.name not in ignore
    }
    if indexed != non_flag_files:
        missing = sorted(non_flag_files - indexed)
        extra = sorted(indexed - non_flag_files)
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
    # Newer indexes (e.g., 3A) carry per-entry sha256_hex; use those to mirror bundle assembly.
    use_component_hashes = bool(index.version)
    component_digests: list[str] = []
    for entry in sorted(index.iter_entries(), key=lambda e: e.path):
        relative_path = entry.path
        target = (bundle_dir / relative_path).resolve()
        sha_override = entry.raw.get("sha256_hex") if isinstance(entry.raw, dict) else None
        sha_match = isinstance(sha_override, str) and re.fullmatch(r"[a-f0-9]{64}", sha_override)
        if use_component_hashes and sha_match:
            component_digests.append(sha_override.lower())
            continue
        if not target.exists():
            if sha_match:
                component_digests.append(sha_override.lower())
                continue
            raise err("E_INDEX_IO", f"unable to read '{relative_path}' while computing digest (missing file)")
        if target.is_dir():
            files = sorted([p for p in target.rglob("*") if p.is_file()], key=lambda p: p.as_posix())
            if not files:
                raise err("E_INDEX_IO", f"unable to read '{relative_path}' while computing digest (empty directory)")
            dir_hasher = sha256()
            for file_path in files:
                try:
                    dir_hasher.update(file_path.read_bytes())
                except OSError as exc:
                    raise err(
                        "E_INDEX_IO",
                        f"unable to read '{file_path}' while computing digest for '{relative_path}'",
                    ) from exc
            component_digests.append(dir_hasher.hexdigest())
            continue
        try:
            file_bytes = target.read_bytes()
        except OSError as exc:
            if sha_match:
                component_digests.append(sha_override.lower())
                continue
            raise err("E_INDEX_IO", f"unable to read '{relative_path}' while computing digest") from exc
        if use_component_hashes:
            component_digests.append(sha256(file_bytes).hexdigest())
        else:
            digest.update(file_bytes)
    if use_component_hashes:
        concat = "".join(component_digests)
        return sha256(concat.encode("ascii")).hexdigest()
    return digest.hexdigest()


__all__ = ["BundleIndex", "IndexEntry", "load_index", "read_pass_flag", "compute_index_digest"]
