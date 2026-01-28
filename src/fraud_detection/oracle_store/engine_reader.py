"""Helpers for reading engine-run artifacts without touching engine code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fraud_detection.scenario_runner.storage import LocalObjectStore, S3ObjectStore

from .config import OracleProfile


def resolve_engine_root(engine_run_root: str, oracle_root: str) -> str:
    if engine_run_root.startswith("s3://"):
        return engine_run_root
    local = Path(engine_run_root)
    if local.is_absolute() or local.exists():
        return str(local)
    if oracle_root.startswith("s3://"):
        return f"{oracle_root.rstrip('/')}/{engine_run_root.lstrip('/')}"
    return str(Path(oracle_root) / engine_run_root)


def join_engine_path(engine_root: str, relative_path: str) -> str:
    if not relative_path:
        return relative_path
    if relative_path.startswith("s3://"):
        return relative_path
    if engine_root.startswith("s3://"):
        return f"{engine_root.rstrip('/')}/{relative_path.lstrip('/')}"
    return str(Path(engine_root) / relative_path)


def read_run_receipt(engine_root: str, profile: OracleProfile) -> dict[str, Any]:
    if engine_root.startswith("s3://"):
        parsed = urlparse(engine_root)
        store = S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=profile.wiring.object_store_endpoint,
            region_name=profile.wiring.object_store_region,
            path_style=profile.wiring.object_store_path_style,
        )
        return store.read_json("run_receipt.json")
    path = Path(engine_root) / "run_receipt.json"
    return json.loads(path.read_text(encoding="utf-8"))


def discover_scenario_ids(engine_root: str) -> set[str]:
    if engine_root.startswith("s3://"):
        return set()
    root = Path(engine_root)
    candidates: set[str] = set()
    for base in ("data", "reports", "config"):
        base_path = root / base
        if not base_path.exists():
            continue
        for item in base_path.rglob("scenario_id=*"):
            if not item.is_dir():
                continue
            name = item.name
            if not name.startswith("scenario_id="):
                continue
            candidates.add(name.split("=", 1)[1])
            if len(candidates) > 5:
                return candidates
    return candidates
