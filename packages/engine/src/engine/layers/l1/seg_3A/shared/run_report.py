"""Lightweight segment-state run-report helper for Segment 3A."""

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
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise err("E_RUN_REPORT_DECODE", f"segment-state run-report at '{path}' is not valid JSONL") from exc


def _keys_match(existing: Mapping[str, object], key: SegmentStateKey) -> bool:
    return all(existing.get(field) == value for field, value in key.as_dict().items())


def write_segment_state_run_report(
    *,
    base_path: Path,
    key: SegmentStateKey,
    payload: Mapping[str, object],
    filename: str = "segment_state_runs.jsonl",
) -> Path:
    """Append (or idempotently keep) a segment-state run-report row.

    We keep this intentionally simple: JSON Lines, one row per invocation key.
    If the same key exists with different content we raise to protect immutability.
    """

    report_path = base_path / "reports" / "l1" / "segment_states" / filename
    _ensure_parent(report_path)
    rows = _load_existing(report_path)
    for row in rows:
        if _keys_match(row, key):
            if row != payload:
                raise err(
                    "E_RUN_REPORT_IMMUTABLE",
                    f"segment-state run-report row for {key.state} already exists with different content at '{report_path}'",
                )
            return report_path

    with report_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return report_path


__all__ = ["SegmentStateKey", "write_segment_state_run_report"]
