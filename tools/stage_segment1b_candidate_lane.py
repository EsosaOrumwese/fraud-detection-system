#!/usr/bin/env python3
"""
Stage a fresh Segment 1B candidate run-id folder by reusing upstream surfaces.

Primary use-case: Segment 1B performance iteration (POPT.*), where we want to
re-run hot states (e.g. S4) without re-running S0 and without manual copying
of prerequisites.

By default this uses NTFS junctions to avoid duplicating large parquet assets.
This is intentionally "safe by default": it only links/copies prerequisite
inputs and does not touch mutable outputs (S4+ outputs are expected to be
written into the new run-id folder).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class _LinkSpec:
    src: Path
    dst: Path
    label: str


def _utc_now_rfc3339_micro() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _ensure_exists(path: Path, *, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"[stage_1b_lane] missing required {label}: {path}")


def _mklink_junction(dst: Path, src: Path) -> None:
    # Junctions do not require admin privileges on Windows and are robust for
    # directory trees (unlike file symlinks in many environments).
    if dst.exists():
        raise SystemExit(f"[stage_1b_lane] refusing to overwrite existing path: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["cmd", "/c", "mklink", "/J", str(dst), str(src)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            "[stage_1b_lane] mklink failed:\n"
            f"  cmd: {cmd}\n"
            f"  stdout: {proc.stdout.strip()}\n"
            f"  stderr: {proc.stderr.strip()}"
        )


def _copytree(dst: Path, src: Path) -> None:
    import shutil

    if dst.exists():
        raise SystemExit(f"[stage_1b_lane] refusing to overwrite existing path: {dst}")
    shutil.copytree(src, dst)


def _iter_link_specs(runs_root: Path, src_run_id: str, dst_run_id: str) -> Iterable[_LinkSpec]:
    src_root = runs_root / src_run_id
    dst_root = runs_root / dst_run_id
    src_l1_1b = src_root / "data" / "layer1" / "1B"
    dst_l1_1b = dst_root / "data" / "layer1" / "1B"
    src_l1_1a = src_root / "data" / "layer1" / "1A"
    dst_l1_1a = dst_root / "data" / "layer1" / "1A"

    required_1b = [
        "s0_gate_receipt",
        "sealed_inputs",
        "tile_index",
        "tile_bounds",
        "tile_weights",
        "s3_requirements",
    ]
    for name in required_1b:
        yield _LinkSpec(
            src=src_l1_1b / name,
            dst=dst_l1_1b / name,
            label=f"1B/{name}",
        )

    # Downstream smoke for 1B uses the 1A outlet catalogue (S7 reads it).
    yield _LinkSpec(
        src=src_l1_1a / "outlet_catalogue",
        dst=dst_l1_1a / "outlet_catalogue",
        label="1A/outlet_catalogue",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_1B")
    parser.add_argument("--src-run-id", required=True, help="Run-id to source prerequisite surfaces from.")
    parser.add_argument(
        "--dst-run-id",
        default=None,
        help="Run-id to create. If omitted, a uuid4 hex is generated.",
    )
    parser.add_argument(
        "--mode",
        choices=["junction", "copy"],
        default="junction",
        help="How to stage prerequisite surfaces (default: junction).",
    )
    parser.add_argument(
        "--emit-json",
        default=None,
        help="Optional path to write a small staging receipt JSON for tooling.",
    )
    args = parser.parse_args(argv)

    runs_root = Path(args.runs_root).resolve()
    src_run_id = str(args.src_run_id).strip()
    dst_run_id = str(args.dst_run_id).strip() if args.dst_run_id else uuid.uuid4().hex
    mode = str(args.mode)

    src_root = runs_root / src_run_id
    dst_root = runs_root / dst_run_id
    _ensure_exists(src_root / "run_receipt.json", label="run_receipt.json")
    if dst_root.exists():
        raise SystemExit(f"[stage_1b_lane] destination run-id already exists: {dst_root}")

    # Seed the destination with the same identity tokens (parameter_hash, manifest_fingerprint, seed)
    # while changing only run_id + created_utc (+ provenance fields for humans/tools).
    src_receipt = _read_json(src_root / "run_receipt.json")
    dst_receipt = dict(src_receipt)
    dst_receipt["run_id"] = dst_run_id
    dst_receipt["created_utc"] = _utc_now_rfc3339_micro()
    dst_receipt["runs_root"] = str(Path(args.runs_root).as_posix())
    dst_receipt["staged_from_run_id"] = src_run_id
    dst_receipt["staged_mode"] = mode
    dst_receipt["staged_utc"] = dst_receipt["created_utc"]

    dst_root.mkdir(parents=True, exist_ok=False)
    (dst_root / "data").mkdir(parents=True, exist_ok=True)
    (dst_root / "logs").mkdir(parents=True, exist_ok=True)
    (dst_root / "reports").mkdir(parents=True, exist_ok=True)
    (dst_root / "tmp").mkdir(parents=True, exist_ok=True)
    _write_json(dst_root / "run_receipt.json", dst_receipt)

    specs = list(_iter_link_specs(runs_root, src_run_id, dst_run_id))
    for spec in specs:
        _ensure_exists(spec.src, label=spec.label)
        if mode == "junction":
            _mklink_junction(spec.dst, spec.src)
        else:
            _copytree(spec.dst, spec.src)

    payload = {
        "runs_root": str(Path(args.runs_root)),
        "src_run_id": src_run_id,
        "dst_run_id": dst_run_id,
        "mode": mode,
        "staged_at_utc": dst_receipt["created_utc"],
        "linked_surfaces": [{"label": s.label, "dst": str(s.dst), "src": str(s.src)} for s in specs],
        "next_commands_powershell": [
            f"python -m engine.cli.s4_alloc_plan --runs-root {args.runs_root} --run-id {dst_run_id}",
            f"python -m engine.cli.s5_site_tile_assignment --runs-root {args.runs_root} --run-id {dst_run_id}",
        ],
    }

    if args.emit_json:
        _write_json(Path(args.emit_json).expanduser().resolve(), payload)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
