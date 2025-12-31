"""Materialize repo-scoped inputs into a run-scoped bundle."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)


class RunBundleError(RuntimeError):
    """Raised when run bundle materialization fails."""


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _try_hardlink(source: Path, target: Path) -> bool:
    try:
        os.link(source, target)
        return True
    except OSError:
        return False


def _validate_existing(source: Path, target: Path) -> None:
    if target.stat().st_size != source.stat().st_size:
        raise RunBundleError(f"bundle mismatch: size differs for {target}")
    source_sha = _sha256_file(source)
    target_sha = _sha256_file(target)
    if source_sha != target_sha:
        raise RunBundleError(f"bundle mismatch: sha256 differs for {target}")


def materialize_repo_file(*, source_path: Path, repo_root: Path, run_root: Path) -> Path:
    """Copy or hardlink a repo file into the run tree and return the run path."""

    source_path = source_path.resolve()
    repo_root = repo_root.resolve()
    run_root = run_root.resolve()
    try:
        rel = source_path.relative_to(repo_root)
    except ValueError as exc:
        raise RunBundleError(f"source path '{source_path}' is outside repo root '{repo_root}'") from exc
    target_path = (run_root / rel).resolve()
    if target_path.exists():
        if not target_path.is_file():
            raise RunBundleError(f"bundle target exists but is not a file: {target_path}")
        _validate_existing(source_path, target_path)
        return target_path
    _ensure_parent(target_path)
    action = "hardlink" if _try_hardlink(source_path, target_path) else "copy"
    if action == "copy":
        shutil.copy2(source_path, target_path)
    logger.info("Run bundle: %s -> %s (%s)", rel, target_path, action)
    return target_path


def materialize_repo_asset(*, source_path: Path, repo_root: Path, run_root: Path) -> Path:
    """Materialize a repo-scoped file or directory into the run tree."""

    source_path = source_path.resolve()
    if not source_path.exists():
        raise RunBundleError(f"source path does not exist: {source_path}")
    if source_path.is_dir():
        files = [path for path in source_path.rglob("*") if path.is_file()]
        if not files:
            raise RunBundleError(f"source directory is empty: {source_path}")
        for file_path in files:
            materialize_repo_file(source_path=file_path, repo_root=repo_root, run_root=run_root)
        return (run_root / source_path.relative_to(repo_root)).resolve()
    return materialize_repo_file(source_path=source_path, repo_root=repo_root, run_root=run_root)


def materialize_repo_files(
    *, source_files: Sequence[Path], repo_root: Path, run_root: Path
) -> list[Path]:
    """Materialize a list of repo-scoped files into the run tree."""

    materialized: list[Path] = []
    for source in source_files:
        materialized.append(
            materialize_repo_file(source_path=source, repo_root=repo_root, run_root=run_root)
        )
    return materialized


def is_repo_scoped(*, source_path: Path, repo_root: Path) -> bool:
    try:
        source_path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


__all__ = [
    "RunBundleError",
    "is_repo_scoped",
    "materialize_repo_asset",
    "materialize_repo_file",
    "materialize_repo_files",
]
