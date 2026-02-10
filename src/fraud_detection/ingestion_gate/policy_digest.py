"""Policy digest computation for IG."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import yaml


def compute_policy_digest(paths: Iterable[Path]) -> str:
    items = []
    for path in sorted({str(Path(p)) for p in paths}):
        payload = _load_yaml(Path(path))
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        items.append({"path": path, "content": canonical})
    blob = json.dumps(items, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
