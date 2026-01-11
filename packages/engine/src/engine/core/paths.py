"""Path resolution for run isolation and external inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from engine.core.errors import InputResolutionError


def find_repo_root(start: Optional[Path] = None) -> Path:
    anchor = start or Path(__file__).resolve()
    for parent in [anchor] + list(anchor.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    raise InputResolutionError("Unable to locate repo root (missing pyproject.toml).")


@dataclass(frozen=True)
class RunPaths:
    repo_root: Path
    run_id: str

    @property
    def run_root(self) -> Path:
        return self.repo_root / "runs" / self.run_id

    @property
    def data_root(self) -> Path:
        return self.run_root / "data"

    @property
    def logs_root(self) -> Path:
        return self.run_root / "logs"

    @property
    def tmp_root(self) -> Path:
        return self.run_root / "tmp"

    @property
    def cache_root(self) -> Path:
        return self.run_root / "cache"

    @property
    def reference_root(self) -> Path:
        return self.run_root / "reference"


def resolve_input_path(
    relative_path: str,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
) -> Path:
    candidates = [run_paths.reference_root / relative_path]
    candidates.extend(Path(root) / relative_path for root in external_roots)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise InputResolutionError(
        "Input not found in run-local reference or external roots: "
        f"{relative_path}. Searched: {', '.join(str(p) for p in candidates)}"
    )
