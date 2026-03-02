#!/usr/bin/env python3
"""Analyze whether Segment 2B P1/S1 reopen moves the S4 dominance tail floor."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_s4_glob(run_root: Path, seed: int, manifest_fingerprint: str) -> str:
    root = (
        run_root
        / "data"
        / "layer1"
        / "2B"
        / "s4_group_weights"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not list(root.glob("*.parquet")):
        raise FileNotFoundError(f"No parquet files found under {root}")
    return str(root / "*.parquet").replace("\\", "/")


def _resolve_tz_glob(run_root: Path, seed: int, manifest_fingerprint: str) -> str:
    root = (
        run_root
        / "data"
        / "layer1"
        / "2A"
        / "site_timezones"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not list(root.glob("*.parquet")):
        raise FileNotFoundError(f"No parquet files found under {root}")
    return str(root / "*.parquet").replace("\\", "/")


def _compute_tail_floor_metrics(run_root: Path, run_id: str) -> dict[str, Any]:
    receipt = _load_json(run_root / run_id / "run_receipt.json")
    seed = int(receipt["seed"])
    manifest = str(receipt["manifest_fingerprint"])

    s4_md = (
        pl.scan_parquet(_resolve_s4_glob(run_root / run_id, seed, manifest))
        .group_by(["merchant_id", "utc_day"])
        .agg(
            [
                pl.len().alias("n_groups"),
                pl.col("p_group").max().alias("max_p_group"),
            ]
        )
        .collect()
    )

    share_n_groups_eq_1 = float(s4_md.select((pl.col("n_groups") == 1).mean()).item())
    share_max_p_ge_095 = float(s4_md.select((pl.col("max_p_group") >= 0.95).mean()).item())
    share_max_p_ge_095_given_multigroup = float(
        s4_md.filter(pl.col("n_groups") > 1).select((pl.col("max_p_group") >= 0.95).mean()).item()
    )

    tz = (
        pl.scan_parquet(_resolve_tz_glob(run_root / run_id, seed, manifest))
        .group_by("merchant_id")
        .agg(pl.col("tzid").n_unique().alias("tz_groups"))
        .collect()
    )
    merchant_share_single_tz = float(tz.select((pl.col("tz_groups") == 1).mean()).item())

    return {
        "run_id": run_id,
        "seed": seed,
        "manifest_fingerprint": manifest,
        "merchant_days_total": int(s4_md.height),
        "merchant_share_single_tz": merchant_share_single_tz,
        "share_n_groups_eq_1": share_n_groups_eq_1,
        "share_max_p_ge_095": share_max_p_ge_095,
        "share_max_p_ge_095_given_multigroup": share_max_p_ge_095_given_multigroup,
        "tail_floor_binding": abs(share_n_groups_eq_1 - share_max_p_ge_095) <= 1.0e-12,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    baseline = payload["baseline"]
    candidate = payload["candidate"]
    delta = payload["delta"]
    lines: list[str] = []
    lines.append("# Segment 2B P1 Reopen Tail-Floor Analysis")
    lines.append("")
    lines.append(f"- baseline_run_id: `{baseline['run_id']}`")
    lines.append(f"- candidate_run_id: `{candidate['run_id']}`")
    lines.append(f"- decision: `{payload['decision']}`")
    lines.append("")
    lines.append("## Baseline")
    lines.append("")
    lines.append(f"- share_n_groups_eq_1: `{baseline['share_n_groups_eq_1']:.6f}`")
    lines.append(f"- share_max_p_ge_095: `{baseline['share_max_p_ge_095']:.6f}`")
    lines.append(
        f"- share_max_p_ge_095_given_multigroup: `{baseline['share_max_p_ge_095_given_multigroup']:.6f}`"
    )
    lines.append("")
    lines.append("## Candidate")
    lines.append("")
    lines.append(f"- share_n_groups_eq_1: `{candidate['share_n_groups_eq_1']:.6f}`")
    lines.append(f"- share_max_p_ge_095: `{candidate['share_max_p_ge_095']:.6f}`")
    lines.append(
        f"- share_max_p_ge_095_given_multigroup: `{candidate['share_max_p_ge_095_given_multigroup']:.6f}`"
    )
    lines.append("")
    lines.append("## Delta")
    lines.append("")
    lines.append(f"- delta_share_n_groups_eq_1: `{delta['share_n_groups_eq_1']:.6f}`")
    lines.append(f"- delta_share_max_p_ge_095: `{delta['share_max_p_ge_095']:.6f}`")
    lines.append("")
    lines.append(f"- conclusion: {payload['conclusion']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze P1/S1 reopen tail-floor movement.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B")
    parser.add_argument("--baseline-run-id", default="80d9c9df1221400f82db77e27a0d63b2")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    baseline = _compute_tail_floor_metrics(runs_root, args.baseline_run_id)
    candidate = _compute_tail_floor_metrics(runs_root, args.candidate_run_id)
    delta = {
        "share_n_groups_eq_1": candidate["share_n_groups_eq_1"] - baseline["share_n_groups_eq_1"],
        "share_max_p_ge_095": candidate["share_max_p_ge_095"] - baseline["share_max_p_ge_095"],
    }

    moved = abs(delta["share_n_groups_eq_1"]) >= 0.01 or abs(delta["share_max_p_ge_095"]) >= 0.01
    decision = "GO_P3_RETRY" if moved else "NO_GO_P1_REOPEN_S1_ONLY"
    conclusion = (
        "S1 reopen materially moved the tail floor; retry P3 on this upstream posture."
        if moved
        else "S1 reopen did not materially move the S4 tail floor; broader upstream reopen is required."
    )

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P1.REOPEN",
        "segment": "2B",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "decision": decision,
        "conclusion": conclusion,
    }

    out_root = Path(args.out_root)
    out_json = out_root / f"segment2b_p1_reopen_floor_{args.candidate_run_id}.json"
    out_md = out_root / f"segment2b_p1_reopen_floor_{args.candidate_run_id}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
