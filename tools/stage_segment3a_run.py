#!/usr/bin/env python3
"""Stage a fresh Segment 3A run folder with deterministic parameter hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_POLICY_PATHS = [
    "config/layer1/3A/policy/zone_mixture_policy.yaml",
    "config/layer1/3A/allocation/country_zone_alphas.yaml",
    "config/layer1/3A/allocation/zone_floor_policy.yaml",
    "config/layer1/2B/policy/day_effect_policy_v1.json",
]

DEFAULT_EXTERNAL_ROOTS = [
    "runs/fix-data-engine/segment_3A",
    "runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92",
    ".",
    "runs/local_full_run-5",
]

REQUIRED_UPSTREAM_RELATIVE_PATHS = [
    "data/layer1/1A/validation",
    "data/layer1/1A/outlet_catalogue",
    "data/layer1/1B/validation",
    "data/layer1/2A/validation",
    "data/layer1/2A/site_timezones",
    "data/layer1/2A/tz_timetable_cache",
    "data/layer1/2A/legality_report",
]


def _now_utc_micro() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _compute_parameter_hash(repo_root: Path, policy_paths: list[str]) -> str:
    hasher = hashlib.sha256()
    for rel in sorted(policy_paths):
        path = repo_root / rel
        if not path.exists():
            raise FileNotFoundError(f"Policy path not found: {path}")
        content = path.read_bytes()
        content_digest = hashlib.sha256(content).hexdigest()
        hasher.update(rel.replace("\\", "/").encode("utf-8"))
        hasher.update(b"\n")
        hasher.update(content_digest.encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Segment 3A run folder.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3A")
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--manifest-fingerprint",
        default="c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--upstream-source-run-root",
        default="runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92",
        help="Run root used to stage mandatory upstream 1A/1B/2A surfaces.",
    )
    parser.add_argument(
        "--policy-path",
        action="append",
        default=[],
        help="Relative path used to derive parameter hash (repeatable).",
    )
    parser.add_argument(
        "--external-root",
        action="append",
        default=[],
        help="External root path to write into run_receipt (repeatable).",
    )
    args = parser.parse_args()

    repo_root = Path.cwd()
    run_id = args.run_id.strip() or uuid.uuid4().hex
    runs_root = Path(args.runs_root)
    run_root = runs_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    policy_paths = args.policy_path if args.policy_path else DEFAULT_POLICY_PATHS
    external_roots = args.external_root if args.external_root else DEFAULT_EXTERNAL_ROOTS
    parameter_hash = _compute_parameter_hash(repo_root, policy_paths)

    upstream_root = (repo_root / args.upstream_source_run_root).resolve()
    if not upstream_root.exists():
        raise FileNotFoundError(f"Upstream source run root not found: {upstream_root}")
    for rel in REQUIRED_UPSTREAM_RELATIVE_PATHS:
        source = upstream_root / rel
        if not source.exists():
            raise FileNotFoundError(f"Missing upstream source path: {source}")
        target = run_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)

    receipt = {
        "contracts_layout": "model_spec",
        "contracts_root": str(repo_root).replace("\\", "/"),
        "created_utc": _now_utc_micro(),
        "external_roots": [str(item).replace("\\", "/") for item in external_roots],
        "manifest_fingerprint": str(args.manifest_fingerprint),
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "runs_root": str(runs_root).replace("\\", "/"),
        "seed": int(args.seed),
    }

    receipt_path = run_root / "run_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")

    print(run_id)
    print(str(receipt_path).replace("\\", "/"))
    print(parameter_hash)


if __name__ == "__main__":
    main()
