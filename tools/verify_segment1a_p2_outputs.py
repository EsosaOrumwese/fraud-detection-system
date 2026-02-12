#!/usr/bin/env python3
"""Verify required Segment 1A P2 output surfaces for a run.

P2.1 scoring requires:
- s3_candidate_set
- s6_membership
- rng_event_ztp_final
- rng_event_ztp_rejection
- rng_event_gumbel_key
- s4_metrics_log

Conditional/diagnostic handling:
- rng_event_ztp_retry_exhausted: optional-presence diagnostic (may be absent).
- s3_integerised_counts: required only if sealed policy enables emit_integerised_counts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


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


def _load_receipt(run_root: Path) -> dict[str, object]:
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"run receipt not found: {receipt_path}")
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def _resolve_s3_integerisation_requirement(
    run_root: Path, manifest_fingerprint: str
) -> tuple[bool, Path]:
    sealed_inputs_path = (
        run_root
        / "data"
        / "layer1"
        / "1A"
        / "sealed_inputs"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "sealed_inputs_1A.json"
    )
    if not sealed_inputs_path.exists():
        raise FileNotFoundError(f"sealed inputs not found: {sealed_inputs_path}")
    sealed_inputs = json.loads(sealed_inputs_path.read_text(encoding="utf-8"))
    policy_entry = next(
        (
            row
            for row in sealed_inputs
            if isinstance(row, dict)
            and row.get("asset_id") == "policy.s3.integerisation.yaml"
        ),
        None,
    )
    if not isinstance(policy_entry, dict):
        raise KeyError(
            "asset_id=policy.s3.integerisation.yaml missing from sealed_inputs_1A.json"
        )
    policy_path = Path(str(policy_entry.get("path", "")))
    if not policy_path.exists():
        raise FileNotFoundError(f"s3 integerisation policy not found: {policy_path}")
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    required = bool(payload.get("emit_integerised_counts", False))
    return required, policy_path


def _patterns_for(run_id: str) -> dict[str, str]:
    return {
        "s3_candidate_set": "data/layer1/1A/s3_candidate_set/parameter_hash=*/part-*.parquet",
        "s3_integerised_counts": "data/layer1/1A/s3_integerised_counts/parameter_hash=*/part-*.parquet",
        "s6_membership": "data/layer1/1A/s6/membership/seed=*/parameter_hash=*/part-*.parquet",
        "rng_event_ztp_final": (
            "logs/layer1/1A/rng/events/ztp_final/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_ztp_rejection": (
            "logs/layer1/1A/rng/events/ztp_rejection/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_ztp_retry_exhausted": (
            "logs/layer1/1A/rng/events/ztp_retry_exhausted/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_gumbel_key": (
            "logs/layer1/1A/rng/events/gumbel_key/seed=*/parameter_hash=*/"
            f"run_id={run_id}/part-*.jsonl"
        ),
        "s4_metrics_log": (
            "logs/layer1/1A/metrics/s4/seed=*/parameter_hash=*/"
            f"run_id={run_id}/s4_metrics.jsonl"
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
        print(f"[segment1a-p2-check] runs_root not found: {runs_root}", file=sys.stderr)
        return 1

    try:
        run_id = _resolve_run_id(runs_root, args.run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[segment1a-p2-check] {exc}", file=sys.stderr)
        return 1

    run_root = runs_root / run_id
    try:
        receipt = _load_receipt(run_root)
        emit_integerised_counts, policy_path = _resolve_s3_integerisation_requirement(
            run_root=run_root,
            manifest_fingerprint=str(receipt["manifest_fingerprint"]),
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        print(f"[segment1a-p2-check] {exc}", file=sys.stderr)
        return 1

    patterns = _patterns_for(run_id)

    required_ids = {
        "s3_candidate_set",
        "s6_membership",
        "rng_event_ztp_final",
        "rng_event_ztp_rejection",
        "rng_event_gumbel_key",
        "s4_metrics_log",
    }
    if emit_integerised_counts:
        required_ids.add("s3_integerised_counts")

    counts: dict[str, int] = {}
    missing_required: list[tuple[str, str]] = []
    for dataset_id, pattern in patterns.items():
        matches = sorted(run_root.glob(pattern))
        counts[dataset_id] = len(matches)
        if dataset_id in required_ids and not matches:
            missing_required.append((dataset_id, pattern))

    if missing_required:
        print(f"[segment1a-p2-check] FAIL run_id={run_id}", file=sys.stderr)
        for dataset_id, pattern in missing_required:
            print(
                f"[segment1a-p2-check] missing required dataset={dataset_id} pattern={pattern}",
                file=sys.stderr,
            )
        return 1

    print(f"[segment1a-p2-check] PASS run_id={run_id}")
    print(
        "[segment1a-p2-check] s3_integerised_counts_policy "
        f"emit_integerised_counts={emit_integerised_counts} path={policy_path.as_posix()}"
    )
    print(
        "[segment1a-p2-check] rng_event_ztp_retry_exhausted optional: "
        "absence means zero exhaustion events."
    )
    for dataset_id in sorted(counts):
        print(f"[segment1a-p2-check] {dataset_id}: files={counts[dataset_id]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
