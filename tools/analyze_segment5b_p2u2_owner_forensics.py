#!/usr/bin/env python3
"""Emit Segment 5B P2.U2.0 owner forensics for residual T6 concentration."""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_div(numer: float, denom: float) -> float:
    if denom <= 0.0:
        return 0.0
    return numer / denom


def _resolve_paths(run_root: Path, seed: int, manifest_fingerprint: str) -> dict[str, Path]:
    return {
        "arrivals_root": (
            run_root
            / "data"
            / "layer2"
            / "5B"
            / "arrival_events"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "scenario_id=baseline_v1"
        ),
        "virtual_classification_root": (
            run_root
            / "data"
            / "layer1"
            / "3B"
            / "virtual_classification"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Segment 5B residual T6 owner concentration.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument("--t6-target-b", type=float, default=0.72)
    parser.add_argument("--t6-target-bplus", type=float, default=0.62)
    parser.add_argument("--coverage-target", type=float, default=0.80)
    args = parser.parse_args()

    run_id = args.run_id.strip() or RUN_ID_DEFAULT
    runs_root = Path(args.runs_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    seed = int(receipt["seed"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])

    paths = _resolve_paths(run_root, seed, manifest_fingerprint)
    arrivals_root = paths["arrivals_root"]
    virtual_root = paths["virtual_classification_root"]
    arrivals_files = sorted(arrivals_root.glob("*.parquet"))
    virtual_files = sorted(virtual_root.glob("*.parquet"))
    if not arrivals_files:
        raise FileNotFoundError(f"No arrival parquet files under: {arrivals_root}")
    if not virtual_files:
        raise FileNotFoundError(f"No virtual classification parquet files under: {virtual_root}")

    arrivals_glob = str(arrivals_root / "*.parquet")
    arrivals_lf = pl.scan_parquet(arrivals_glob)

    total_df = arrivals_lf.select(pl.len().alias("n_total")).collect()
    n_total = int(total_df["n_total"][0])
    if n_total <= 0:
        raise ValueError("No arrivals found for forensics.")

    tz_counts = (
        arrivals_lf.group_by("tzid_primary")
        .agg(pl.len().alias("arrivals"))
        .sort("arrivals", descending=True)
        .collect()
    )
    top10_tz = tz_counts.head(10).with_row_index(name="rank", offset=1)
    top10_total = int(top10_tz["arrivals"].sum())
    t6_observed = _safe_div(float(top10_total), float(n_total))

    required_b = max(0, int(math.ceil((t6_observed - float(args.t6_target_b)) * float(n_total))))
    required_bplus = max(0, int(math.ceil((t6_observed - float(args.t6_target_bplus)) * float(n_total))))

    top10_tzids = top10_tz["tzid_primary"].to_list()
    top10_lf = arrivals_lf.filter(pl.col("tzid_primary").is_in(top10_tzids))

    merchant_meta = (
        pl.scan_parquet([str(path) for path in virtual_files])
        .select(["merchant_id", "virtual_mode", "rule_id"])
        .with_columns(
            pl.col("rule_id").cast(pl.Utf8).str.extract(r"MCC_(\d+)", 1).alias("mcc"),
            pl.col("rule_id").cast(pl.Utf8).str.extract(r"__CHANNEL_(.*?)__DECISION_", 1).alias("channel"),
        )
        .group_by("merchant_id")
        .agg(
            pl.col("virtual_mode").first().alias("virtual_mode"),
            pl.col("mcc").first().alias("mcc"),
            pl.col("channel").first().alias("channel"),
            pl.col("rule_id").first().alias("rule_id"),
        )
        .collect()
    )
    merchant_meta_lf = merchant_meta.lazy()

    merchant_top10 = (
        top10_lf.group_by("merchant_id")
        .agg(pl.len().alias("top10_arrivals"))
        .sort("top10_arrivals", descending=True)
        .collect()
        .join(merchant_meta, on="merchant_id", how="left")
        .with_columns(
            (pl.col("top10_arrivals") / float(n_total)).alias("share_of_total"),
            (pl.col("top10_arrivals") / float(top10_total)).alias("share_of_top10"),
            pl.col("top10_arrivals").cum_sum().alias("cum_top10_arrivals"),
        )
    )

    if required_b > 0:
        merchant_top10 = merchant_top10.with_columns(
            (pl.col("top10_arrivals") / float(required_b)).alias("share_of_required_b"),
            (pl.col("cum_top10_arrivals") / float(required_b)).alias("cum_required_b_coverage"),
        )
    else:
        merchant_top10 = merchant_top10.with_columns(
            pl.lit(0.0).alias("share_of_required_b"),
            pl.lit(1.0).alias("cum_required_b_coverage"),
        )

    coverage_target = float(args.coverage_target)
    cutoff_idx = 0
    coverage_reached = 1.0 if required_b <= 0 else 0.0
    if required_b > 0 and merchant_top10.height > 0:
        coverage_series = merchant_top10["cum_required_b_coverage"].to_list()
        cutoff_idx = len(coverage_series) - 1
        for idx, value in enumerate(coverage_series):
            if float(value) >= coverage_target:
                cutoff_idx = idx
                break
        coverage_reached = float(coverage_series[cutoff_idx])
    offender_count = min(cutoff_idx + 1, merchant_top10.height) if merchant_top10.height > 0 else 0
    offender_set = merchant_top10.head(offender_count)

    mcc_channel_summary = (
        merchant_top10.group_by(["mcc", "channel", "virtual_mode"])
        .agg(
            pl.len().alias("merchant_count"),
            pl.col("top10_arrivals").sum().alias("top10_arrivals"),
        )
        .sort("top10_arrivals", descending=True)
        .with_columns(
            (pl.col("top10_arrivals") / float(top10_total)).alias("share_of_top10"),
            (pl.col("top10_arrivals") / float(n_total)).alias("share_of_total"),
            pl.col("top10_arrivals").cum_sum().alias("cum_top10_arrivals"),
        )
    )
    if required_b > 0:
        mcc_channel_summary = mcc_channel_summary.with_columns(
            (pl.col("top10_arrivals") / float(required_b)).alias("share_of_required_b"),
            (pl.col("cum_top10_arrivals") / float(required_b)).alias("cum_required_b_coverage"),
        )
    else:
        mcc_channel_summary = mcc_channel_summary.with_columns(
            pl.lit(0.0).alias("share_of_required_b"),
            pl.lit(1.0).alias("cum_required_b_coverage"),
        )

    merchant_tz_hotspots = (
        top10_lf.group_by(["merchant_id", "tzid_primary"])
        .agg(pl.len().alias("arrivals"))
        .sort("arrivals", descending=True)
        .head(1000)
        .join(merchant_meta_lf, on="merchant_id", how="left")
        .with_columns(
            (pl.col("arrivals") / float(top10_total)).alias("share_of_top10"),
            (pl.col("arrivals") / float(n_total)).alias("share_of_total"),
        )
        .collect()
    )

    top10_tz = top10_tz.with_columns(
        (pl.col("arrivals") / float(n_total)).alias("share_of_total"),
        (pl.col("arrivals") / float(top10_total)).alias("share_of_top10"),
        (
            pl.col("arrivals") * (_safe_div(float(required_b), float(top10_total)))
        ).alias("proportional_required_b_reduction"),
    )

    summary = {
        "generated_utc": _now_utc(),
        "phase": "P2.U2.0",
        "segment": "5B",
        "run": {
            "run_id": run_id,
            "runs_root": str(runs_root),
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
        },
        "targets": {
            "t6_target_b": float(args.t6_target_b),
            "t6_target_bplus": float(args.t6_target_bplus),
            "coverage_target": coverage_target,
        },
        "observed": {
            "n_total": n_total,
            "top10_total": top10_total,
            "t6_observed": t6_observed,
            "t6_observed_fmt": f"{t6_observed * 100.0:.4f}%",
        },
        "required_reduction": {
            "to_b_count": required_b,
            "to_b_share_pp": max(0.0, (t6_observed - float(args.t6_target_b)) * 100.0),
            "to_bplus_count": required_bplus,
            "to_bplus_share_pp": max(0.0, (t6_observed - float(args.t6_target_bplus)) * 100.0),
        },
        "offender_set": {
            "merchant_count_for_coverage_target": offender_count,
            "coverage_reached": coverage_reached,
            "coverage_target_met": bool(coverage_reached >= coverage_target),
            "top_merchants_preview": offender_set.select(
                ["merchant_id", "top10_arrivals", "share_of_total", "share_of_required_b", "virtual_mode", "mcc", "channel"]
            )
            .head(20)
            .to_dicts(),
        },
        "paths": {
            "arrivals_root": str(arrivals_root),
            "virtual_classification_root": str(virtual_root),
        },
    }

    json_path = out_root / f"segment5b_p2u2_forensics_{run_id}.json"
    merchant_csv = out_root / f"segment5b_p2u2_offender_merchants_{run_id}.csv"
    mcc_channel_csv = out_root / f"segment5b_p2u2_offender_mcc_channel_{run_id}.csv"
    top10_tz_csv = out_root / f"segment5b_p2u2_top10_tz_{run_id}.csv"
    hotspot_csv = out_root / f"segment5b_p2u2_merchant_tz_hotspots_{run_id}.csv"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    merchant_top10.write_csv(merchant_csv)
    mcc_channel_summary.write_csv(mcc_channel_csv)
    top10_tz.write_csv(top10_tz_csv)
    merchant_tz_hotspots.write_csv(hotspot_csv)

    print(f"[segment5b-p2u2] summary={json_path}")
    print(f"[segment5b-p2u2] merchants={merchant_csv}")
    print(f"[segment5b-p2u2] mcc_channel={mcc_channel_csv}")
    print(f"[segment5b-p2u2] top10_tz={top10_tz_csv}")
    print(f"[segment5b-p2u2] merchant_tz_hotspots={hotspot_csv}")


if __name__ == "__main__":
    main()
