"""Engine configuration with contract-source switching."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from engine.core.paths import find_repo_root


@dataclass(frozen=True)
class EngineConfig:
    repo_root: Path
    contracts_root: Path
    contracts_layout: str
    runs_root: Path
    external_roots: tuple[Path, ...] = field(default_factory=tuple)

    @classmethod
    def default(cls) -> "EngineConfig":
        repo_root = find_repo_root()
        contracts_root = repo_root
        return cls(
            repo_root=repo_root,
            contracts_root=contracts_root,
            contracts_layout="model_spec",
            runs_root=repo_root / "runs",
            external_roots=(repo_root,),
        )

    def with_external_roots(self, roots: Iterable[Path]) -> "EngineConfig":
        return EngineConfig(
            repo_root=self.repo_root,
            contracts_root=self.contracts_root,
            contracts_layout=self.contracts_layout,
            runs_root=self.runs_root,
            external_roots=tuple(roots),
        )
