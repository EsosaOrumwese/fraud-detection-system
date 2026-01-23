"""Helpers for selecting and parsing run receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from engine.core.errors import InputResolutionError
from engine.core.time import parse_rfc3339


def _receipt_created_ts(path: Path) -> Optional[float]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    created = parse_rfc3339(payload.get("created_utc") if isinstance(payload, dict) else None)
    if created is None:
        return None
    return created.timestamp()


def _receipt_sort_key(path: Path) -> tuple[float, float]:
    created_ts = _receipt_created_ts(path)
    mtime = path.stat().st_mtime
    if created_ts is None:
        return (mtime, mtime)
    return (created_ts, mtime)


def pick_latest_run_receipt(runs_root: Path) -> Path:
    candidates = list(runs_root.glob("*/run_receipt.json"))
    if not candidates:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return max(candidates, key=_receipt_sort_key)
