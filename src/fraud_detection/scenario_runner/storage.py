"""Local object-store utilities for SR artifacts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    digest: str | None = None


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _full_path(self, relative_path: str) -> Path:
        return self.root / relative_path

    def ensure_dir(self, relative_path: str) -> Path:
        path = self._full_path(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        tmp_path.write_text(data + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
        return ArtifactRef(path=str(path))

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self._full_path(relative_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
        return ArtifactRef(path=str(path))

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                line = json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                handle.write(line + "\n")
        return ArtifactRef(path=str(path))

    def exists(self, relative_path: str) -> bool:
        return self._full_path(relative_path).exists()

    def read_text(self, relative_path: str) -> str:
        return self._full_path(relative_path).read_text(encoding="utf-8")

    def list_files(self, relative_dir: str) -> list[str]:
        base = self._full_path(relative_dir)
        if not base.exists():
            return []
        return [str(path) for path in base.rglob("*") if path.is_file()]
