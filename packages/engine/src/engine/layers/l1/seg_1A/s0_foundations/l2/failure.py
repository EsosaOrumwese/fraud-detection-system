"""Failure record writer for S0 foundations.

The validation bundle spec mandates that every abort emit a structured record
under ``validation_failures/``.  This helper centralises the atomic write logic
so callers do not have to worry about temp directories or duplicate writes.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Mapping, Optional

from ..exceptions import S0Error


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def emit_failure_record(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    seed: int,
    run_id: str,
    failure: S0Error,
    state: str,
    module: str,
    parameter_hash: str,
    dataset_id: Optional[str] = None,
    merchant_id: Optional[str] = None,
    detail: Optional[Mapping[str, object]] = None,
) -> Path:
    """Write a structured failure record and return the final directory."""

    failures_root = base_path / "data" / "layer1" / "1A" / "validation" / "failures"
    failures_root.mkdir(parents=True, exist_ok=True)

    final_dir = (
        failures_root
        / f"manifest_fingerprint={manifest_fingerprint}"
        / f"seed={seed}"
        / f"run_id={run_id}"
    )
    temp_dir = final_dir.parent / f"_tmp.{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)

    try:
        detail_payload = {"message": failure.context.detail}
        if detail:
            detail_payload.update(detail)

        record = {
            "failure_class": failure.context.failure_category.name,
            "failure_code": failure.context.failure_code,
            "state": state,
            "module": module,
            "dataset_id": dataset_id,
            "merchant_id": merchant_id,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "seed": seed,
            "run_id": run_id,
            "ts_utc": time.time_ns(),
            "detail": detail_payload,
        }

        _write_json(temp_dir / "failure.json", record)
        _write_json(temp_dir / "_FAILED.SENTINEL.json", record)

        if final_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            return final_dir

        temp_dir.rename(final_dir)
        return final_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
