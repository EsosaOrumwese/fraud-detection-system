"""Lightweight segment-state run-report helper for Segment 5B."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class RunReportError(RuntimeError):
    """Raised when run-report persistence fails."""


@dataclass(frozen=True)
class SegmentStateKey:
    layer: str
    segment: str
    state: str
    manifest_fingerprint: str
    parameter_hash: str
    run_id: str

    def as_dict(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "segment": self.segment,
            "state": self.state,
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "run_id": self.run_id,
        }


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_existing(path: Path) -> list[Mapping[str, object]]:
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RunReportError(f"segment-state run-report at '{path}' is not valid JSONL") from exc


def _keys_match(existing: Mapping[str, object], key: SegmentStateKey) -> bool:
    return all(existing.get(field) == value for field, value in key.as_dict().items())


def write_segment_state_run_report(
    *, path: Path, key: SegmentStateKey, payload: Mapping[str, object]
) -> Path:
    """Append (or idempotently keep) a segment-state run-report row."""

    _ensure_parent(path)
    rows = _load_existing(path)
    for row in rows:
        if _keys_match(row, key):
            return path

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return path


__all__ = ["SegmentStateKey", "write_segment_state_run_report", "RunReportError"]
