"""Platform run/session helpers (shared by SR + IG)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNS_ROOT = Path("runs/fraud-platform")
PLATFORM_RUNS_ROOT = RUNS_ROOT / "platform_runs"
ACTIVE_RUN_ID_PATH = PLATFORM_RUNS_ROOT / "ACTIVE_RUN_ID"


def resolve_platform_run_id(*, create_if_missing: bool) -> str | None:
    env_value = (os.getenv("PLATFORM_RUN_ID") or "").strip()
    if env_value:
        return env_value
    if ACTIVE_RUN_ID_PATH.exists():
        value = ACTIVE_RUN_ID_PATH.read_text(encoding="utf-8").strip()
        if value:
            return value
    if not create_if_missing:
        return None
    run_id = _new_run_id()
    PLATFORM_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    ACTIVE_RUN_ID_PATH.write_text(run_id + "\n", encoding="utf-8")
    return run_id


def platform_log_paths(*, create_if_missing: bool) -> list[str]:
    log_path = (os.getenv("PLATFORM_LOG_PATH") or "").strip()
    paths = [log_path] if log_path else [str(RUNS_ROOT / "platform.log")]
    run_id = resolve_platform_run_id(create_if_missing=create_if_missing)
    if run_id:
        paths.append(str(PLATFORM_RUNS_ROOT / run_id / "platform.log"))
    return paths


def append_session_event(
    component: str,
    event_kind: str,
    details: dict[str, Any],
    *,
    create_if_missing: bool,
) -> str | None:
    run_id = resolve_platform_run_id(create_if_missing=create_if_missing)
    if not run_id:
        return None
    session_dir = PLATFORM_RUNS_ROOT / run_id
    session_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "platform_run_id": run_id,
        "component": component,
        "event_kind": event_kind,
        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
        "details": details,
    }
    path = session_dir / "session.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n")
    return run_id


def _new_run_id() -> str:
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"platform_{stamp}"
