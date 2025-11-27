"""Segment-state run-report helper reused by Segment 3B."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..s0_gate.exceptions import err


@dataclass(frozen=True)
class SegmentStateKey:
    layer: str
    segment: str
    state: str
    manifest_fingerprint: str
    parameter_hash: str
    seed: int | str

    def as_dict(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "segment": self.segment,
            "state": self.state,
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "seed": int(self.seed),
        }


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_existing(path: Path) -> list[Mapping[str, object]]:
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise err("E_RUN_REPORT_DECODE", f"segment-state run-report at '{path}' is not valid JSONL") from exc


def _keys_match(existing: Mapping[str, object], key: SegmentStateKey) -> bool:
    return all(existing.get(field) == value for field, value in key.as_dict().items())


def write_segment_state_run_report(
    *,
    path: Path,
    key: SegmentStateKey,
    payload: Mapping[str, object],
) -> Path:
    """Append (or idempotently keep) a segment-state run-report row."""

    _ensure_parent(path)
    rows = _load_existing(path)
    updated_rows = []
    replaced = False
    for row in rows:
        if _keys_match(row, key):
            if row == payload:
                return path
            updated_rows.append(payload)
            replaced = True
        else:
            updated_rows.append(row)
    if replaced:
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in updated_rows) + "\n", encoding="utf-8")
        return path

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return path


__all__ = ["SegmentStateKey", "write_segment_state_run_report"]
