#!/usr/bin/env python3
"""Emit Segment 6B POPT.1 replay witness for S1 outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl


DATASETS = ("s1_arrival_entities_6B", "s1_session_index_6B")


def _ensure_ascii(path: Path) -> str:
    return str(path).replace("\\", "/")


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _dataset_digest(run_root: Path, dataset: str) -> dict[str, Any]:
    root = run_root / "data" / "layer3" / "6B" / dataset
    files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    rels = [path.relative_to(run_root).as_posix() for path in files]
    digest = hashlib.sha256()
    for rel, path in zip(rels, files):
        digest.update(rel.encode("utf-8"))
        digest.update(_sha256(path).encode("ascii"))
    return {
        "file_count": len(files),
        "relative_files": rels,
        "dataset_digest": digest.hexdigest(),
    }


def _session_semantic_signature(path: Path) -> dict[str, Any]:
    row = (
        pl.scan_parquet(str(path))
        .select(
            [
                pl.len().alias("rows"),
                pl.col("session_id").sum().alias("sum_session_id"),
                pl.col("arrival_count").sum().alias("sum_arrival_count"),
                pl.col("session_id").min().alias("min_session_id"),
                pl.col("session_id").max().alias("max_session_id"),
                pl.col("arrival_count").min().alias("min_arrival_count"),
                pl.col("arrival_count").max().alias("max_arrival_count"),
                pl.col("party_id").sum().alias("sum_party_id"),
                pl.col("account_id").sum().alias("sum_account_id"),
                pl.col("device_id").sum().alias("sum_device_id"),
                pl.col("instrument_id").sum().alias("sum_instrument_id"),
                pl.col("merchant_id").sum().alias("sum_merchant_id"),
            ]
        )
        .collect()
        .to_dicts()[0]
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 6B POPT.1 replay witness.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_6B")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--replay-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_6B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    candidate_run_root = runs_root / args.candidate_run_id
    replay_run_root = runs_root / args.replay_run_id
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    candidate = {dataset: _dataset_digest(candidate_run_root, dataset) for dataset in DATASETS}
    replay = {dataset: _dataset_digest(replay_run_root, dataset) for dataset in DATASETS}

    checks: dict[str, Any] = {}
    for dataset in DATASETS:
        cand = candidate[dataset]
        rep = replay[dataset]
        files_match = cand["relative_files"] == rep["relative_files"]
        checks[dataset] = {
            "files_match": files_match,
            "candidate_file_count": cand["file_count"],
            "replay_file_count": rep["file_count"],
            "candidate_dataset_digest": cand["dataset_digest"],
            "replay_dataset_digest": rep["dataset_digest"],
            "byte_identical": files_match and cand["dataset_digest"] == rep["dataset_digest"],
        }

    cand_session_file = next(
        path for path in (candidate_run_root / "data" / "layer3" / "6B" / "s1_session_index_6B").rglob("*.parquet")
    )
    rep_session_file = next(
        path for path in (replay_run_root / "data" / "layer3" / "6B" / "s1_session_index_6B").rglob("*.parquet")
    )
    session_semantic_candidate = _session_semantic_signature(cand_session_file)
    session_semantic_replay = _session_semantic_signature(rep_session_file)
    session_semantic_match = session_semantic_candidate == session_semantic_replay

    decision = (
        "PASS_REPLAY_STRICT"
        if all(checks[dataset]["byte_identical"] for dataset in DATASETS)
        else "PASS_REPLAY_SEMANTIC"
        if checks["s1_arrival_entities_6B"]["byte_identical"] and session_semantic_match
        else "FAIL_REPLAY"
    )

    payload = {
        "phase": "POPT.1",
        "segment": "6B",
        "candidate_run_id": args.candidate_run_id,
        "replay_run_id": args.replay_run_id,
        "checks": checks,
        "session_semantic_candidate": session_semantic_candidate,
        "session_semantic_replay": session_semantic_replay,
        "session_semantic_match": session_semantic_match,
        "decision": decision,
        "generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    out_json = out_root / f"segment6b_popt1_replay_witness_{args.candidate_run_id}_vs_{args.replay_run_id}.json"
    out_md = out_root / f"segment6b_popt1_replay_witness_{args.candidate_run_id}_vs_{args.replay_run_id}.md"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Segment 6B POPT.1 Replay Witness",
        "",
        f"- candidate_run_id: `{args.candidate_run_id}`",
        f"- replay_run_id: `{args.replay_run_id}`",
        f"- decision: `{decision}`",
        "",
        "## Dataset Checks",
        "",
    ]
    for dataset in DATASETS:
        row = checks[dataset]
        lines.append(
            f"- {dataset}: byte_identical=`{row['byte_identical']}` files_match=`{row['files_match']}` "
            f"(candidate_files={row['candidate_file_count']}, replay_files={row['replay_file_count']})"
        )
    lines.extend(
        [
            "",
            "## Session Semantic Check",
            "",
            f"- semantic_match: `{session_semantic_match}`",
            f"- candidate_signature: `{session_semantic_candidate}`",
            f"- replay_signature: `{session_semantic_replay}`",
        ]
    )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[segment6b-popt1] replay_json={out_json}")
    print(f"[segment6b-popt1] replay_md={out_md}")
    print(f"[segment6b-popt1] decision={decision}")


if __name__ == "__main__":
    main()
