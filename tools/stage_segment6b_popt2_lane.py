#!/usr/bin/env python3
"""
Stage a fresh Segment 6B POPT.2 candidate lane for S4->S5 execution.

This utility creates a new run-id folder under runs/fix-data-engine/segment_6B,
stages immutable S0..S3 prerequisites from a source run-id, and seeds a
run-id-normalized rng_trace_log containing required upstream modules
(6B.S1/6B.S2/6B.S3) so S5 REQ_RNG_BUDGETS can validate staged lanes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"[stage_6b_popt2_lane] invalid JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _ensure_exists(path: Path, *, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"[stage_6b_popt2_lane] missing required {label}: {path}")


def _mklink_junction(dst: Path, src: Path) -> None:
    if dst.exists():
        raise SystemExit(f"[stage_6b_popt2_lane] refusing to overwrite existing path: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "[stage_6b_popt2_lane] mklink failed:\n"
            f"  stdout: {proc.stdout.strip()}\n"
            f"  stderr: {proc.stderr.strip()}"
        )


def _copytree(dst: Path, src: Path) -> None:
    if dst.exists():
        raise SystemExit(f"[stage_6b_popt2_lane] refusing to overwrite existing path: {dst}")
    shutil.copytree(src, dst)


def _iter_link_specs(src_root: Path, dst_root: Path) -> Iterable[_LinkSpec]:
    src_6b = src_root / "data" / "layer3" / "6B"
    dst_6b = dst_root / "data" / "layer3" / "6B"
    names = [
        "s0_gate_receipt",
        "sealed_inputs",
        "s1_arrival_entities_6B",
        "s1_session_index_6B",
        "s2_flow_anchor_baseline_6B",
        "s2_event_stream_baseline_6B",
        "s3_campaign_catalogue_6B",
        "s3_flow_anchor_with_fraud_6B",
        "s3_event_stream_with_fraud_6B",
    ]
    for name in names:
        yield _LinkSpec(src=src_6b / name, dst=dst_6b / name, label=f"6B/{name}")

    # Upstream validation flags are required by S5 REQ_UPSTREAM_HASHGATES.
    upstream_validation_relpaths = [
        ("data/layer1/1A/validation", "1A/validation"),
        ("data/layer1/1B/validation", "1B/validation"),
        ("data/layer1/2A/validation", "2A/validation"),
        ("data/layer1/2B/validation", "2B/validation"),
        ("data/layer1/3A/validation", "3A/validation"),
        ("data/layer1/3B/validation", "3B/validation"),
        ("data/layer2/5A/validation", "5A/validation"),
        ("data/layer2/5B/validation", "5B/validation"),
        ("data/layer3/6A/validation", "6A/validation"),
    ]
    for relpath, label in upstream_validation_relpaths:
        yield _LinkSpec(
            src=src_root / relpath,
            dst=dst_root / relpath,
            label=f"upstream/{label}",
        )


def _seed_upstream_rng_trace(
    src_root: Path,
    dst_root: Path,
    src_run_id: str,
    dst_run_id: str,
    seed: int,
    parameter_hash: str,
) -> Path:
    src_trace = (
        src_root
        / "logs/layer3/6B/rng/trace"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={src_run_id}"
        / "rng_trace_log.jsonl"
    )
    _ensure_exists(src_trace, label="rng_trace_log (source)")

    dst_trace = (
        dst_root
        / "logs/layer3/6B/rng/trace"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={dst_run_id}"
        / "rng_trace_log.jsonl"
    )
    dst_trace.parent.mkdir(parents=True, exist_ok=True)

    keep_modules = {"6B.S1", "6B.S2", "6B.S3"}
    kept_rows = 0
    seen_modules: set[str] = set()
    with src_trace.open("r", encoding="utf-8") as src_handle, dst_trace.open("w", encoding="utf-8") as dst_handle:
        for raw_line in src_handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            module = payload.get("module")
            if module not in keep_modules:
                continue
            payload["run_id"] = dst_run_id
            dst_handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
            dst_handle.write("\n")
            kept_rows += 1
            seen_modules.add(str(module))

    missing_modules = sorted(keep_modules - seen_modules)
    if kept_rows == 0 or missing_modules:
        raise SystemExit(
            "[stage_6b_popt2_lane] failed to seed required upstream RNG modules: "
            f"missing={missing_modules} rows_written={kept_rows}"
        )
    return dst_trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        default="runs/fix-data-engine/segment_6B",
        help="Destination runs-root (default: runs/fix-data-engine/segment_6B).",
    )
    parser.add_argument(
        "--src-runs-root",
        default=None,
        help="Optional source runs-root. If omitted, uses --runs-root.",
    )
    parser.add_argument("--src-run-id", required=True, help="Source run-id for staged prerequisites.")
    parser.add_argument("--dst-run-id", default=None, help="Destination run-id. Default: generated uuid4 hex.")
    parser.add_argument(
        "--mode",
        choices=["junction", "copy"],
        default="junction",
        help="How to stage prerequisite directories (default: junction).",
    )
    parser.add_argument("--emit-json", default=None, help="Optional staging receipt JSON path.")
    args = parser.parse_args(argv)

    dst_runs_root = Path(args.runs_root).resolve()
    src_runs_root = Path(args.src_runs_root).resolve() if args.src_runs_root else dst_runs_root
    src_run_id = str(args.src_run_id).strip()
    dst_run_id = str(args.dst_run_id).strip() if args.dst_run_id else uuid.uuid4().hex
    mode = str(args.mode)

    src_root = src_runs_root / src_run_id
    dst_root = dst_runs_root / dst_run_id
    _ensure_exists(src_root / "run_receipt.json", label="run_receipt.json")
    if dst_root.exists():
        raise SystemExit(f"[stage_6b_popt2_lane] destination run-id already exists: {dst_root}")

    src_receipt = _read_json(src_root / "run_receipt.json")
    seed = int(src_receipt.get("seed"))
    parameter_hash = str(src_receipt.get("parameter_hash") or "")
    if not parameter_hash:
        raise SystemExit("[stage_6b_popt2_lane] missing parameter_hash in source run_receipt")

    dst_receipt = dict(src_receipt)
    dst_receipt["run_id"] = dst_run_id
    dst_receipt["created_utc"] = _utc_now_rfc3339_micro()
    dst_receipt["runs_root"] = str(Path(args.runs_root).as_posix())
    dst_receipt["staged_from_run_id"] = src_run_id
    dst_receipt["staged_mode"] = f"{mode}_s4s5_popt2"
    dst_receipt["staged_utc"] = dst_receipt["created_utc"]
    dst_receipt["staged_from_runs_root"] = str(src_runs_root.as_posix())

    dst_root.mkdir(parents=True, exist_ok=False)
    (dst_root / "data").mkdir(parents=True, exist_ok=True)
    (dst_root / "logs").mkdir(parents=True, exist_ok=True)
    (dst_root / "reports").mkdir(parents=True, exist_ok=True)
    (dst_root / "tmp").mkdir(parents=True, exist_ok=True)
    _write_json(dst_root / "run_receipt.json", dst_receipt)

    specs = list(_iter_link_specs(src_root, dst_root))
    for spec in specs:
        _ensure_exists(spec.src, label=spec.label)
        if mode == "junction":
            _mklink_junction(spec.dst, spec.src)
        else:
            _copytree(spec.dst, spec.src)

    rng_trace_seeded_path = _seed_upstream_rng_trace(
        src_root=src_root,
        dst_root=dst_root,
        src_run_id=src_run_id,
        dst_run_id=dst_run_id,
        seed=seed,
        parameter_hash=parameter_hash,
    )

    payload = {
        "dst_runs_root": str(Path(args.runs_root)),
        "src_runs_root": str(src_runs_root),
        "src_run_id": src_run_id,
        "dst_run_id": dst_run_id,
        "mode": mode,
        "staged_at_utc": dst_receipt["created_utc"],
        "seed": seed,
        "parameter_hash": parameter_hash,
        "linked_surfaces": [{"label": s.label, "dst": str(s.dst), "src": str(s.src)} for s in specs],
        "rng_trace_seeded_path": str(rng_trace_seeded_path),
        "next_commands_powershell": [
            f"make segment6b-s4 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S4_RUN_ID={dst_run_id}",
            f"make segment6b-s5 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S5_RUN_ID={dst_run_id}",
        ],
    }

    if args.emit_json:
        _write_json(Path(args.emit_json).expanduser().resolve(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
