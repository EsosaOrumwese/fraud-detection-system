#!/usr/bin/env python3
"""Verify required Segment 1A P3 output surfaces for a run.

P3.1 scoring requires:
- outlet_catalogue
- s3_candidate_set
- s6_membership
- rng_event_nb_final
- rng_event_sequence_finalize

Diagnostic-only:
- rng_event_site_sequence_overflow (optional; may be absent)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _resolve_run_id(runs_root: Path, run_id: str | None) -> str:
    if run_id:
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError(f"invalid run_id format: {run_id!r}")
        receipt_path = runs_root / run_id / "run_receipt.json"
        if not receipt_path.exists():
            raise FileNotFoundError(f"run receipt not found: {receipt_path}")
        return run_id

    receipts = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not receipts:
        raise FileNotFoundError(f"no run_receipt.json files found under {runs_root}")
    return receipts[-1].parent.name


def _patterns_for(run_id: str) -> dict[str, str]:
    return {
        "outlet_catalogue": (
            "data/layer1/1A/outlet_catalogue/seed=*/manifest_fingerprint=*/part-*.parquet"
        ),
        "s3_candidate_set": "data/layer1/1A/s3_candidate_set/parameter_hash=*/part-*.parquet",
        "s6_membership": "data/layer1/1A/s6/membership/seed=*/parameter_hash=*/part-*.parquet",
        "rng_event_nb_final": (
            "logs/layer1/1A/rng/events/nb_final/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_sequence_finalize": (
            "logs/layer1/1A/rng/events/sequence_finalize/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_site_sequence_overflow": (
            "logs/layer1/1A/rng/events/site_sequence_overflow/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        required=True,
        help="Root directory containing run-id folders.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run id to inspect; defaults to latest run under --runs-root.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    runs_root = Path(args.runs_root).resolve()
    if not runs_root.exists():
        print(f"[segment1a-p3-check] runs_root not found: {runs_root}", file=sys.stderr)
        return 1

    try:
        run_id = _resolve_run_id(runs_root, args.run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[segment1a-p3-check] {exc}", file=sys.stderr)
        return 1

    run_root = runs_root / run_id
    patterns = _patterns_for(run_id)
    required_ids = {
        "outlet_catalogue",
        "s3_candidate_set",
        "s6_membership",
        "rng_event_nb_final",
        "rng_event_sequence_finalize",
    }

    counts: dict[str, int] = {}
    missing_required: list[tuple[str, str]] = []
    for dataset_id, pattern in patterns.items():
        matches = sorted(run_root.glob(pattern))
        counts[dataset_id] = len(matches)
        if dataset_id in required_ids and not matches:
            missing_required.append((dataset_id, pattern))

    if missing_required:
        print(f"[segment1a-p3-check] FAIL run_id={run_id}", file=sys.stderr)
        for dataset_id, pattern in missing_required:
            print(
                f"[segment1a-p3-check] missing required dataset={dataset_id} pattern={pattern}",
                file=sys.stderr,
            )
        return 1

    print(f"[segment1a-p3-check] PASS run_id={run_id}")
    print(
        "[segment1a-p3-check] rng_event_site_sequence_overflow optional: "
        "absence means no overflow guardrail events."
    )
    for dataset_id in sorted(counts):
        print(f"[segment1a-p3-check] {dataset_id}: files={counts[dataset_id]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
