#!/usr/bin/env python3
"""Stage a fresh Segment 3B run folder with seeded run_receipt and upstream surfaces."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_UPSTREAM_RELATIVE_PATHS = [
    "data/layer1/1A/validation",
    "data/layer1/1A/sealed_inputs",
    "data/layer1/1A/outlet_catalogue",
    "data/layer1/1B/validation",
    "data/layer1/1B/sealed_inputs",
    "data/layer1/1B/site_locations",
    "data/layer1/1B/tile_index",
    "data/layer1/1B/tile_weights",
    "data/layer1/1B/tile_bounds",
    "data/layer1/2A/validation",
    "data/layer1/2A/sealed_inputs",
    "data/layer1/2A/site_timezones",
    "data/layer1/2A/tz_timetable_cache",
    "data/layer1/3A/validation",
    "data/layer1/3A/sealed_inputs",
    "data/layer1/3A/zone_alloc",
    "data/layer1/3A/zone_universe",
]

SEED_PARTITION_BASES = [
    "data/layer1/1A/outlet_catalogue",
    "data/layer1/1B/site_locations",
    "data/layer1/2A/site_timezones",
    "data/layer1/3A/zone_alloc",
]


def _now_utc_micro() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def _seed_surface_path(path: Path, from_seed: int, to_seed: int) -> Path:
    from_token = f"seed={from_seed}"
    to_token = f"seed={to_seed}"
    return Path(str(path).replace(from_token, to_token))


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Segment 3B run folder for a target seed.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--copy-s2-cache",
        action="store_true",
        help="Copy S2 tile-surface cache from source seed path into target seed path when available.",
    )
    args = parser.parse_args()

    repo_root = Path.cwd()
    runs_root = Path(args.runs_root)
    source_root = runs_root / args.source_run_id
    if not source_root.exists():
        raise FileNotFoundError(f"Source run root not found: {source_root}")

    source_receipt_path = source_root / "run_receipt.json"
    if not source_receipt_path.exists():
        raise FileNotFoundError(f"Source run receipt missing: {source_receipt_path}")
    source_receipt = json.loads(source_receipt_path.read_text(encoding="utf-8"))

    source_seed = int(source_receipt.get("seed"))
    manifest = str(source_receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(source_receipt.get("parameter_hash") or "")
    contracts_layout = str(source_receipt.get("contracts_layout") or "model_spec")
    contracts_root = str(source_receipt.get("contracts_root") or str(repo_root).replace("\\", "/"))
    external_roots = list(source_receipt.get("external_roots") or [])
    if not manifest or not parameter_hash:
        raise ValueError("Source run_receipt missing manifest_fingerprint or parameter_hash.")

    run_id = args.run_id.strip() or uuid.uuid4().hex
    target_root = runs_root / run_id
    target_root.mkdir(parents=True, exist_ok=True)

    for rel in REQUIRED_UPSTREAM_RELATIVE_PATHS:
        source = source_root / rel
        target = target_root / rel
        if not source.exists():
            raise FileNotFoundError(f"Missing required source path: {source}")
        _copy_tree(source, target)

    for base_rel in SEED_PARTITION_BASES:
        _clone_seed_partition(target_root, base_rel, source_seed, int(args.seed))

    if args.copy_s2_cache:
        source_cache_dir = (
            source_root
            / "reports/layer1/3B/state=S2"
            / f"seed={source_seed}"
            / f"manifest_fingerprint={manifest}"
        )
        if source_cache_dir.exists():
            target_cache_dir = _seed_surface_path(source_cache_dir, source_seed, int(args.seed))
            target_cache_dir.mkdir(parents=True, exist_ok=True)
            for cache_file in sorted(source_cache_dir.glob("tile_surface_cache_*.json")):
                shutil.copy2(cache_file, target_cache_dir / cache_file.name)

    receipt = {
        "contracts_layout": contracts_layout,
        "contracts_root": contracts_root,
        "created_utc": _now_utc_micro(),
        "external_roots": external_roots,
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "runs_root": str(runs_root).replace("\\", "/"),
        "seed": int(args.seed),
    }
    receipt_path = target_root / "run_receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )

    print(run_id)
    print(str(receipt_path).replace("\\", "/"))
    print(f"seed={int(args.seed)} source_seed={source_seed}")


if __name__ == "__main__":
    main()
