#!/usr/bin/env python3
"""Stage a fresh Segment 6A run folder for a target seed."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_COPY_PATHS = [
    "data/layer1/1A/outlet_catalogue",
    "data/layer3/6A/s0_gate_receipt",
    "data/layer3/6A/sealed_inputs",
    "data/layer3/6A/s1_party_base_6A",
    "data/layer3/6A/s2_account_base_6A",
    "data/layer3/6A/s3_instrument_base_6A",
    "data/layer3/6A/s3_account_instrument_links_6A",
    "data/layer3/6A/s4_device_base_6A",
    "data/layer3/6A/s4_device_links_6A",
    "data/layer3/6A/s4_ip_base_6A",
    "data/layer3/6A/s4_ip_links_6A",
]

OPTIONAL_COPY_PATHS = [
    "data/layer3/6A/s2_merchant_account_base_6A",
]

SEED_PARTITION_BASES = [
    "data/layer1/1A/outlet_catalogue",
    "data/layer3/6A/s1_party_base_6A",
    "data/layer3/6A/s2_account_base_6A",
    "data/layer3/6A/s2_merchant_account_base_6A",
    "data/layer3/6A/s3_instrument_base_6A",
    "data/layer3/6A/s3_account_instrument_links_6A",
    "data/layer3/6A/s4_device_base_6A",
    "data/layer3/6A/s4_device_links_6A",
    "data/layer3/6A/s4_ip_base_6A",
    "data/layer3/6A/s4_ip_links_6A",
]


def _now_utc_micro() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def _clone_seed_partition(run_root: Path, base_rel: str, source_seed: int, target_seed: int) -> None:
    if source_seed == target_seed:
        return
    base = run_root / base_rel
    source = base / f"seed={source_seed}"
    target = base / f"seed={target_seed}"
    if not source.exists():
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _remove_seed_partition(run_root: Path, base_rel: str, seed: int) -> None:
    base = run_root / base_rel
    source = base / f"seed={seed}"
    if source.exists():
        shutil.rmtree(source)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Segment 6A run folder for a target seed.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_6A")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    source_root = runs_root / str(args.source_run_id).strip()
    if not source_root.exists():
        raise FileNotFoundError(f"Source run root not found: {source_root}")

    source_receipt_path = source_root / "run_receipt.json"
    if not source_receipt_path.exists():
        raise FileNotFoundError(f"Source run receipt missing: {source_receipt_path}")
    source_receipt = json.loads(source_receipt_path.read_text(encoding="utf-8"))

    source_seed = int(source_receipt.get("seed"))
    manifest = str(source_receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(source_receipt.get("parameter_hash") or "")
    if not manifest or not parameter_hash:
        raise ValueError("Source run_receipt missing manifest_fingerprint or parameter_hash.")

    run_id = args.run_id.strip() or uuid.uuid4().hex
    target_root = runs_root / run_id
    target_root.mkdir(parents=True, exist_ok=True)

    for rel in REQUIRED_COPY_PATHS:
        source = source_root / rel
        if not source.exists():
            raise FileNotFoundError(f"Missing required source path: {source}")
        _copy_tree(source, target_root / rel)

    for rel in OPTIONAL_COPY_PATHS:
        source = source_root / rel
        if source.exists():
            _copy_tree(source, target_root / rel)

    for base_rel in SEED_PARTITION_BASES:
        _clone_seed_partition(target_root, base_rel, source_seed, int(args.seed))
        if int(args.seed) != source_seed:
            _remove_seed_partition(target_root, base_rel, source_seed)

    receipt = {
        "contracts_layout": str(source_receipt.get("contracts_layout") or "model_spec"),
        "contracts_root": str(source_receipt.get("contracts_root") or ""),
        "created_utc": _now_utc_micro(),
        "external_roots": list(source_receipt.get("external_roots") or []),
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "runs_root": str(runs_root).replace("\\", "/"),
        "seed": int(args.seed),
        "staged_from_run_id": str(args.source_run_id).strip(),
    }
    receipt_path = target_root / "run_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")

    print(run_id)
    print(str(receipt_path).replace("\\", "/"))
    print(f"seed={int(args.seed)} source_seed={source_seed}")


if __name__ == "__main__":
    main()
