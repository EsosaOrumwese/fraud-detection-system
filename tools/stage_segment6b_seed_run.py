#!/usr/bin/env python3
"""Stage a fresh Segment 6B run folder for a target seed using junctioned inputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


NON_SEED_LINKS = [
    "data/layer3/6B/s0_gate_receipt",
    "data/layer3/6B/sealed_inputs",
    "data/layer1/1A/validation",
    "data/layer1/1B/validation",
    "data/layer1/2A/validation",
    "data/layer1/2B/validation",
    "data/layer1/3A/validation",
    "data/layer1/3B/validation",
    "data/layer2/5A/validation",
    "data/layer2/5B/validation",
    "data/layer3/6A/validation",
]

SEED_LINK_BASES = [
    "data/layer2/5B/arrival_events",
    "data/layer3/6A/s1_party_base_6A",
    "data/layer3/6A/s2_account_base_6A",
    "data/layer3/6A/s3_instrument_base_6A",
    "data/layer3/6A/s3_account_instrument_links_6A",
    "data/layer3/6A/s4_device_base_6A",
    "data/layer3/6A/s4_ip_base_6A",
    "data/layer3/6A/s4_device_links_6A",
    "data/layer3/6A/s4_ip_links_6A",
    "data/layer3/6A/s5_party_fraud_roles_6A",
    "data/layer3/6A/s5_account_fraud_roles_6A",
    "data/layer3/6A/s5_merchant_fraud_roles_6A",
    "data/layer3/6A/s5_device_fraud_roles_6A",
    "data/layer3/6A/s5_ip_fraud_roles_6A",
]


@dataclass(frozen=True)
class LinkReceipt:
    label: str
    src: str
    dst: str


def _now_utc_micro() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def _mklink_junction(dst: Path, src: Path) -> None:
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "mklink /J failed\n"
            f"stdout={proc.stdout.strip()}\n"
            f"stderr={proc.stderr.strip()}"
        )


def _must_exist(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {label}: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_6B")
    parser.add_argument("--src-runs-root", default=None)
    parser.add_argument("--src-run-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--dst-run-id", default="")
    parser.add_argument("--emit-json", default="")
    args = parser.parse_args()

    dst_runs_root = Path(args.runs_root).resolve()
    src_runs_root = Path(args.src_runs_root).resolve() if args.src_runs_root else dst_runs_root
    src_run_id = str(args.src_run_id).strip()
    dst_run_id = str(args.dst_run_id).strip() or uuid.uuid4().hex
    target_seed = int(args.seed)

    src_root = src_runs_root / src_run_id
    dst_root = dst_runs_root / dst_run_id
    _must_exist(src_root / "run_receipt.json", "source run_receipt")
    if dst_root.exists():
        raise FileExistsError(f"Destination run already exists: {dst_root}")

    src_receipt = _read_json(src_root / "run_receipt.json")
    source_seed = int(src_receipt.get("seed"))
    manifest = str(src_receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(src_receipt.get("parameter_hash") or "")
    if not manifest or not parameter_hash:
        raise ValueError("Source run_receipt missing manifest_fingerprint or parameter_hash.")

    dst_root.mkdir(parents=True, exist_ok=False)
    (dst_root / "data").mkdir(parents=True, exist_ok=True)
    (dst_root / "logs").mkdir(parents=True, exist_ok=True)
    (dst_root / "reports").mkdir(parents=True, exist_ok=True)
    (dst_root / "tmp").mkdir(parents=True, exist_ok=True)

    linked: list[LinkReceipt] = []

    for rel in NON_SEED_LINKS:
        src = src_root / rel
        dst = dst_root / rel
        _must_exist(src, rel)
        _mklink_junction(dst, src)
        linked.append(LinkReceipt(label=rel, src=str(src), dst=str(dst)))

    for rel in SEED_LINK_BASES:
        src_seed_dir = src_root / rel / f"seed={source_seed}"
        dst_seed_dir = dst_root / rel / f"seed={target_seed}"
        _must_exist(src_seed_dir, f"{rel}/seed={source_seed}")
        _mklink_junction(dst_seed_dir, src_seed_dir)
        linked.append(
            LinkReceipt(
                label=f"{rel}/seed={target_seed}",
                src=str(src_seed_dir),
                dst=str(dst_seed_dir),
            )
        )

    dst_receipt = dict(src_receipt)
    dst_receipt["run_id"] = dst_run_id
    dst_receipt["seed"] = target_seed
    dst_receipt["created_utc"] = _now_utc_micro()
    dst_receipt["runs_root"] = str(Path(args.runs_root).as_posix())
    dst_receipt["staged_from_run_id"] = src_run_id
    dst_receipt["staged_from_runs_root"] = str(src_runs_root.as_posix())
    dst_receipt["staged_mode"] = "junction_seed_lane_p5"
    dst_receipt["staged_utc"] = dst_receipt["created_utc"]
    _write_json(dst_root / "run_receipt.json", dst_receipt)

    payload = {
        "src_run_id": src_run_id,
        "dst_run_id": dst_run_id,
        "source_seed": source_seed,
        "target_seed": target_seed,
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "linked_paths": [lr.__dict__ for lr in linked],
        "next_commands_powershell": [
            f"make --no-print-directory segment6b-s1 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S1_RUN_ID={dst_run_id}",
            f"make --no-print-directory segment6b-s2 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S2_RUN_ID={dst_run_id}",
            f"make --no-print-directory segment6b-s3 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S3_RUN_ID={dst_run_id}",
            f"make --no-print-directory segment6b-s4 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S4_RUN_ID={dst_run_id}",
            f"make --no-print-directory segment6b-s5 ENGINE_RUNS_ROOT={args.runs_root} SEG6B_S5_RUN_ID={dst_run_id}",
        ],
    }
    if args.emit_json:
        _write_json(Path(args.emit_json).expanduser().resolve(), payload)

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
