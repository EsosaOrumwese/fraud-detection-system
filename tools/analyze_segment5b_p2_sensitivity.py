#!/usr/bin/env python3
"""Emit Segment 5B P2 sensitivity and feasibility artifact."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_float_by_key(text: str, key: str) -> float:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Could not parse key `{key}` from routing policy.")
    return float(match.group(1))


def _read_bounds(text: str, key: str) -> tuple[float, float]:
    pattern = re.compile(
        rf"^\s*{re.escape(key)}\s*:\s*\[\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*\]\s*$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Could not parse bounds `{key}` from routing policy.")
    lo = float(match.group(1))
    hi = float(match.group(2))
    return lo, hi


def _format_pct(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value * 100.0:.4f}%"


def _safe_div(numer: float, denom: float) -> float:
    if denom <= 0.0:
        return 0.0
    return numer / denom


def _required_p(target: float, share_virtual_only: float, share_hybrid: float) -> float | None:
    if share_hybrid <= 0.0:
        return None
    return (target - share_virtual_only) / share_hybrid


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _resolve_paths(run_root: Path, seed: int, manifest_fingerprint: str) -> dict[str, Path]:
    return {
        "s3_counts": (
            run_root
            / "data"
            / "layer2"
            / "5B"
            / "s3_bucket_counts"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "scenario_id=baseline_v1"
            / "s3_bucket_counts_5B.parquet"
        ),
        "virtual_classification": (
            run_root
            / "data"
            / "layer1"
            / "3B"
            / "virtual_classification"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
        ),
        "arrivals_glob_root": (
            run_root
            / "data"
            / "layer2"
            / "5B"
            / "arrival_events"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "scenario_id=baseline_v1"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Segment 5B P2 sensitivity and feasibility.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument(
        "--p1-gateboard-path",
        default="",
        help="Optional P1 gateboard path. Defaults to out_root/segment5b_p1_realism_gateboard_<run_id>.json",
    )
    parser.add_argument("--routing-policy-path", default="config/layer2/5B/arrival_routing_policy_5B.yaml")
    args = parser.parse_args()

    run_id = args.run_id.strip() or RUN_ID_DEFAULT
    runs_root = Path(args.runs_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    if args.p1_gateboard_path:
        p1_path = Path(args.p1_gateboard_path)
    else:
        p1_path = out_root / f"segment5b_p1_realism_gateboard_{run_id}.json"
    if not p1_path.exists():
        raise FileNotFoundError(f"Missing P1 gateboard: {p1_path}")
    p1 = _load_json(p1_path)

    receipt = _load_json(run_root / "run_receipt.json")
    manifest_fingerprint = str(receipt["manifest_fingerprint"])
    seed = int(receipt["seed"])

    paths = _resolve_paths(run_root, seed, manifest_fingerprint)
    s3_path = paths["s3_counts"]
    virtual_dir = paths["virtual_classification"]
    arrivals_glob = str(paths["arrivals_glob_root"] / "*.parquet")
    if not s3_path.exists():
        raise FileNotFoundError(f"Missing S3 counts: {s3_path}")
    virtual_files = sorted(virtual_dir.glob("*.parquet"))
    if not virtual_files:
        raise FileNotFoundError(f"Missing virtual_classification parquet files under: {virtual_dir}")
    if not list(paths["arrivals_glob_root"].glob("*.parquet")):
        raise FileNotFoundError(f"Missing arrivals parquet files under: {paths['arrivals_glob_root']}")

    routing_policy_text = Path(args.routing_policy_path).read_text(encoding="utf-8-sig")
    p_current = _read_float_by_key(routing_policy_text, "p_virtual_hybrid")
    p_lo, p_hi = _read_bounds(routing_policy_text, "hybrid_p_virtual_bounds")

    merchant_arrivals = (
        pl.scan_parquet(str(s3_path))
        .group_by("merchant_id")
        .agg(pl.col("count_N").sum().alias("arrivals"))
        .collect()
    )
    virtual_cls = pl.read_parquet([str(p) for p in virtual_files]).select(["merchant_id", "virtual_mode"])
    weighted = merchant_arrivals.join(virtual_cls, on="merchant_id", how="left").with_columns(
        pl.col("virtual_mode").fill_null("NON_VIRTUAL").cast(pl.Utf8),
        pl.col("arrivals").cast(pl.Float64),
    )
    mode_summary = (
        weighted.group_by("virtual_mode").agg(pl.col("arrivals").sum().alias("arrivals")).sort("arrivals", descending=True)
    )
    total_arrivals = float(mode_summary["arrivals"].sum())
    share_by_mode = {
        str(row["virtual_mode"]): _safe_div(float(row["arrivals"]), total_arrivals)
        for row in mode_summary.iter_rows(named=True)
    }
    share_non_virtual = float(share_by_mode.get("NON_VIRTUAL", 0.0))
    share_hybrid = float(share_by_mode.get("HYBRID", 0.0))
    share_virtual_only = float(share_by_mode.get("VIRTUAL_ONLY", 0.0))

    t7_observed = float(((p1.get("gates") or {}).get("T7") or {}).get("value") or 0.0)
    t6_observed = float(((p1.get("gates") or {}).get("T6") or {}).get("value") or 0.0)
    t7_model_at_current = share_virtual_only + p_current * share_hybrid
    t7_model_at_lo = share_virtual_only + p_lo * share_hybrid
    t7_model_at_hi = share_virtual_only + p_hi * share_hybrid
    p_needed_b = _required_p(0.03, share_virtual_only, share_hybrid)
    p_needed_bplus = _required_p(0.05, share_virtual_only, share_hybrid)

    b_reachable = bool(p_needed_b is not None and p_needed_b <= p_hi + 1e-12)
    bplus_reachable = bool(p_needed_bplus is not None and p_needed_bplus <= p_hi + 1e-12)

    arrivals_lf = pl.scan_parquet(arrivals_glob).select(["tzid_primary", "is_virtual", "merchant_id"])
    totals = arrivals_lf.select([pl.len().alias("n_total"), pl.col("is_virtual").sum().alias("n_virtual")]).collect()
    n_total = int(totals["n_total"][0])
    n_virtual = int(totals["n_virtual"][0])
    tz_counts = arrivals_lf.group_by("tzid_primary").agg(pl.len().alias("n")).sort("n", descending=True).collect()
    top10 = tz_counts.head(10)
    top10_share = _safe_div(float(top10["n"].sum()), float(n_total))

    top10_tzids = top10["tzid_primary"].to_list()
    top10_merchant = (
        arrivals_lf.filter(pl.col("tzid_primary").is_in(top10_tzids))
        .group_by("merchant_id")
        .agg(pl.len().alias("n"))
        .sort("n", descending=True)
        .head(20)
        .collect()
    )
    top10_merchant_rows = [
        {
            "merchant_id": int(row["merchant_id"]),
            "arrivals": int(row["n"]),
            "share_of_total": _safe_div(float(row["n"]), float(n_total)),
            "share_of_top10": _safe_div(float(row["n"]), float(top10["n"].sum())),
        }
        for row in top10_merchant.iter_rows(named=True)
    ]

    candidate_grid: list[float] = []
    for value in [
        p_current,
        p_current + 0.10,
        p_current + 0.20,
        p_current + 0.30,
        p_needed_b if p_needed_b is not None else p_current,
        p_needed_bplus if p_needed_bplus is not None else p_current,
        p_hi,
    ]:
        candidate_grid.append(round(_clip(float(value), p_lo, p_hi), 4))
    candidate_grid = sorted(set(candidate_grid))

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P2.2",
        "segment": "5B",
        "run": {
            "run_id": run_id,
            "runs_root": str(runs_root),
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
        },
        "paths": {
            "p1_gateboard": str(p1_path),
            "routing_policy": str(Path(args.routing_policy_path)),
            "s3_bucket_counts": str(s3_path),
            "virtual_classification_dir": str(virtual_dir),
            "arrivals_glob": arrivals_glob,
        },
        "baseline_observed": {
            "t6_top10_share": t6_observed,
            "t6_top10_share_fmt": _format_pct(t6_observed),
            "t7_virtual_share": t7_observed,
            "t7_virtual_share_fmt": _format_pct(t7_observed),
            "top10_share_rescan": top10_share,
            "top10_share_rescan_fmt": _format_pct(top10_share),
            "virtual_share_rescan": _safe_div(float(n_virtual), float(n_total)),
            "virtual_share_rescan_fmt": _format_pct(_safe_div(float(n_virtual), float(n_total))),
        },
        "virtual_mode_mass": {
            "share_non_virtual": share_non_virtual,
            "share_hybrid": share_hybrid,
            "share_virtual_only": share_virtual_only,
            "total_weighted_arrivals": total_arrivals,
        },
        "hybrid_coin_policy": {
            "p_current": p_current,
            "p_bounds": [p_lo, p_hi],
            "t7_model_at_current": t7_model_at_current,
            "t7_model_at_lo": t7_model_at_lo,
            "t7_model_at_hi": t7_model_at_hi,
            "p_needed_for_b_low_edge_0_03": p_needed_b,
            "p_needed_for_bplus_low_edge_0_05": p_needed_bplus,
            "b_reachable_under_bounds": b_reachable,
            "bplus_reachable_under_bounds": bplus_reachable,
        },
        "concentration_decomposition": {
            "top10_tzids": top10_tzids,
            "top10_tz_counts": [
                {"tzid_primary": str(row["tzid_primary"]), "arrivals": int(row["n"])}
                for row in top10.iter_rows(named=True)
            ],
            "top10_merchant_contributors": top10_merchant_rows,
        },
        "candidate_shortlist": {
            "p_virtual_hybrid_grid": candidate_grid,
            "selection_rule": "bounded grid from current, step-up probes, analytic thresholds, and high bound",
        },
        "local_feasibility_verdict": {
            "t7_reachable_for_b": b_reachable,
            "t7_reachable_for_bplus": bplus_reachable,
            "t6_status": "open" if t6_observed > 0.72 else "already_b",
            "verdict": (
                "reachable_policy_only_for_t7_but_t6_requires_empirical_sweep"
                if b_reachable
                else "locally_blocked_for_t7_b_under_current_bounds"
            ),
        },
    }

    out_path = out_root / f"segment5b_p2_sensitivity_{run_id}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[segment5b-p2] sensitivity={out_path}")


if __name__ == "__main__":
    main()
