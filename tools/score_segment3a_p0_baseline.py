#!/usr/bin/env python3
"""Emit Segment 3A remediation P0 baseline metrics and gate posture."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


RUN_ID_DEFAULT = "81599ab107ba4c8db7fc5850287360fe"
MONOTONIC_MIN_BUCKET_SUPPORT = 25

HARD_THRESHOLDS: dict[str, float] = {
    "s2_top1_median_multi_tz_max": 0.85,
    "s2_share_top1_ge_099_multi_tz_max": 0.20,
    "s4_escalated_multi_zone_rate_min": 0.35,
    "s3_merchant_share_std_median_min": 0.02,
    "s4_top1_share_median_max": 0.90,
    "s4_top1_share_p75_max": 0.97,
    "zone_alloc_top1_share_median_max": 0.90,
}

STRETCH_THRESHOLDS: dict[str, float] = {
    "s2_top1_median_multi_tz_max": 0.75,
    "s2_share_top1_ge_099_multi_tz_max": 0.10,
    "s4_escalated_multi_zone_rate_min": 0.55,
    "s3_merchant_share_std_median_min": 0.04,
    "s4_top1_share_median_max": 0.85,
    "zone_alloc_top1_share_median_max": 0.85,
    "s1_escalation_curve_major_dip_max_abs": 0.10,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda path: path.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _resolve_glob(root: Path, pattern: str) -> str:
    if not list(root.glob(pattern)):
        raise FileNotFoundError(f"No files found for pattern: {root / pattern}")
    return str((root / pattern)).replace("\\", "/")


def _resolve_run_context(runs_root: Path, run_id: str) -> dict[str, Any]:
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    receipt = _load_json(run_root / "run_receipt.json")
    seed = int(receipt["seed"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])
    parameter_hash = str(receipt["parameter_hash"])

    s1_glob = _resolve_glob(
        run_root
        / "data"
        / "layer1"
        / "3A"
        / "s1_escalation_queue"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )
    s2_glob = _resolve_glob(
        run_root
        / "data"
        / "layer1"
        / "3A"
        / "s2_country_zone_priors"
        / f"parameter_hash={parameter_hash}",
        "*.parquet",
    )
    s3_glob = _resolve_glob(
        run_root
        / "data"
        / "layer1"
        / "3A"
        / "s3_zone_shares"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )
    s4_glob = _resolve_glob(
        run_root
        / "data"
        / "layer1"
        / "3A"
        / "s4_zone_counts"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )
    zone_alloc_glob = _resolve_glob(
        run_root
        / "data"
        / "layer1"
        / "3A"
        / "zone_alloc"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )

    return {
        "runs_root": str(runs_root).replace("\\", "/"),
        "run_root": str(run_root).replace("\\", "/"),
        "run_id": run_id,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "paths": {
            "s1_glob": s1_glob,
            "s2_glob": s2_glob,
            "s3_glob": s3_glob,
            "s4_glob": s4_glob,
            "zone_alloc_glob": zone_alloc_glob,
        },
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _compute_s1_metrics(s1_df: pl.DataFrame) -> dict[str, Any]:
    pairs_total = int(s1_df.height)
    pairs_escalated = int(s1_df.select(pl.col("is_escalated").sum()).item())
    pairs_monolithic = int(pairs_total - pairs_escalated)
    escalation_rate = (float(pairs_escalated) / float(pairs_total)) if pairs_total > 0 else 0.0

    reason_df = s1_df.group_by("decision_reason").len().sort("len", descending=True)
    decision_reason_counts = {
        str(row[0]): int(row[1]) for row in reason_df.select(["decision_reason", "len"]).iter_rows()
    }

    zcurve_df = (
        s1_df.group_by("zone_count_country")
        .agg(
            [
                pl.len().alias("pairs"),
                pl.col("is_escalated").sum().alias("pairs_escalated"),
            ]
        )
        .with_columns((pl.col("pairs_escalated") / pl.col("pairs")).alias("escalation_rate"))
        .sort("zone_count_country")
    )
    zcurve_rows = [
        {
            "zone_count_country": int(row[0]),
            "pairs": int(row[1]),
            "pairs_escalated": int(row[2]),
            "escalation_rate": float(row[3]),
        }
        for row in zcurve_df.select(
            ["zone_count_country", "pairs", "pairs_escalated", "escalation_rate"]
        ).iter_rows()
    ]

    filtered = [row for row in zcurve_rows if row["pairs"] >= MONOTONIC_MIN_BUCKET_SUPPORT]
    major_dip_max_abs = 0.0
    major_dip_count_gt_010 = 0
    monotonic_violations = 0
    for prev, current in zip(filtered, filtered[1:]):
        delta = float(current["escalation_rate"] - prev["escalation_rate"])
        if delta < 0.0:
            monotonic_violations += 1
            dip = abs(delta)
            if dip > major_dip_max_abs:
                major_dip_max_abs = dip
            if dip > 0.10:
                major_dip_count_gt_010 += 1

    return {
        "pairs_total": pairs_total,
        "pairs_escalated": pairs_escalated,
        "pairs_monolithic": pairs_monolithic,
        "escalation_rate": escalation_rate,
        "decision_reason_counts": decision_reason_counts,
        "zone_count_curve": zcurve_rows,
        "zone_count_curve_support_min_pairs": MONOTONIC_MIN_BUCKET_SUPPORT,
        "zone_count_curve_supported_buckets": len(filtered),
        "zone_count_curve_monotonic_violations": monotonic_violations,
        "zone_count_curve_major_dip_max_abs": major_dip_max_abs,
        "zone_count_curve_major_dip_count_gt_010": major_dip_count_gt_010,
    }


def _compute_s2_metrics(s2_df: pl.DataFrame) -> dict[str, Any]:
    country_df = (
        s2_df.group_by("country_iso")
        .agg(
            [
                pl.col("tzid").n_unique().alias("tz_count"),
                pl.col("share_effective").max().alias("top1_share"),
                (pl.col("share_effective") * pl.col("share_effective")).sum().alias("hhi"),
            ]
        )
        .sort("country_iso")
    )
    multi = country_df.filter(pl.col("tz_count") > 1)
    countries_total = int(country_df.height)
    countries_multi_tz_total = int(multi.height)
    share_top1_ge_099_multi_tz = (
        _safe_float(multi.select((pl.col("top1_share") >= 0.99).mean()).item(), 0.0)
        if countries_multi_tz_total > 0
        else 0.0
    )

    return {
        "countries_total": countries_total,
        "countries_multi_tz_total": countries_multi_tz_total,
        "tz_count_median": _safe_float(country_df.select(pl.col("tz_count").median()).item(), 0.0),
        "tz_count_p90": _safe_float(country_df.select(pl.col("tz_count").quantile(0.90)).item(), 0.0),
        "top1_share_median_multi_tz": _safe_float(multi.select(pl.col("top1_share").median()).item(), 0.0),
        "top1_share_p75_multi_tz": _safe_float(multi.select(pl.col("top1_share").quantile(0.75)).item(), 0.0),
        "share_top1_ge_099_multi_tz": share_top1_ge_099_multi_tz,
        "hhi_median_multi_tz": _safe_float(multi.select(pl.col("hhi").median()).item(), 0.0),
        "floor_applied_rate": _safe_float(s2_df.select(pl.col("floor_applied").cast(pl.Float64).mean()).item(), 0.0),
        "bump_applied_rate": _safe_float(s2_df.select(pl.col("bump_applied").cast(pl.Float64).mean()).item(), 0.0),
    }


def _compute_s3_metrics(s3_df: pl.DataFrame) -> dict[str, Any]:
    pair_df = (
        s3_df.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            [
                pl.col("share_drawn").max().alias("top1_share"),
                (pl.col("share_drawn") >= 0.05).sum().alias("zones_ge_005"),
                pl.len().alias("zone_rows"),
            ]
        )
        .sort(["merchant_id", "legal_country_iso"])
    )
    by_country_tz = (
        s3_df.group_by(["legal_country_iso", "tzid"])
        .agg(
            [
                pl.col("merchant_id").n_unique().alias("merchant_count"),
                pl.col("share_drawn").std(ddof=1).fill_null(0.0).alias("merchant_share_std"),
            ]
        )
        .filter(pl.col("merchant_count") > 1)
    )

    return {
        "pairs_total": int(pair_df.height),
        "top1_share_median": _safe_float(pair_df.select(pl.col("top1_share").median()).item(), 0.0),
        "top1_share_p90": _safe_float(pair_df.select(pl.col("top1_share").quantile(0.90)).item(), 0.0),
        "share_pairs_zones_ge_005_ge_2": _safe_float(
            pair_df.select((pl.col("zones_ge_005") >= 2).cast(pl.Float64).mean()).item(),
            0.0,
        ),
        "zones_ge_005_p50": _safe_float(pair_df.select(pl.col("zones_ge_005").median()).item(), 0.0),
        "merchant_share_std_groups": int(by_country_tz.height),
        "merchant_share_std_median": _safe_float(by_country_tz.select(pl.col("merchant_share_std").median()).item(), 0.0),
        "merchant_share_std_p90": _safe_float(by_country_tz.select(pl.col("merchant_share_std").quantile(0.90)).item(), 0.0),
    }


def _aggregate_pair_top1(df: pl.DataFrame, count_col: str, total_col: str) -> pl.DataFrame:
    return (
        df.group_by(["merchant_id", "legal_country_iso"])
        .agg(
            [
                pl.col(count_col).sum().alias("zone_total"),
                pl.col(count_col).max().alias("zone_max"),
                (pl.col(count_col) > 0).sum().alias("nonzero_zone_count"),
                pl.col(total_col).first().alias("reported_total"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("zone_total") > 0)
                .then(pl.col("zone_max") / pl.col("zone_total"))
                .otherwise(0.0)
                .alias("top1_share"),
                (pl.col("zone_total") == pl.col("reported_total")).alias("count_conserved"),
            ]
        )
    )


def _compute_s4_metrics(s4_df: pl.DataFrame, s1_df: pl.DataFrame) -> dict[str, Any]:
    s4_pair = _aggregate_pair_top1(s4_df, "zone_site_count", "zone_site_count_sum")
    esc_pairs = s1_df.filter(pl.col("is_escalated")).select(["merchant_id", "legal_country_iso"]).unique()
    esc_join = esc_pairs.join(s4_pair, on=["merchant_id", "legal_country_iso"], how="left")
    if esc_join.select(pl.col("top1_share").is_null().any()).item():
        raise ValueError("S4 missing escalated pair rows from S1 escalation queue")

    return {
        "pairs_total": int(s4_pair.height),
        "pairs_escalated_total": int(esc_join.height),
        "escalated_multi_zone_rate": _safe_float(
            esc_join.select((pl.col("nonzero_zone_count") > 1).cast(pl.Float64).mean()).item(),
            0.0,
        ),
        "top1_share_median": _safe_float(esc_join.select(pl.col("top1_share").median()).item(), 0.0),
        "top1_share_p75": _safe_float(esc_join.select(pl.col("top1_share").quantile(0.75)).item(), 0.0),
        "share_pairs_single_zone": _safe_float(
            esc_join.select((pl.col("nonzero_zone_count") == 1).cast(pl.Float64).mean()).item(),
            0.0,
        ),
        "count_conservation_all_pairs": bool(s4_pair.select(pl.col("count_conserved").all()).item()),
    }


def _compute_zone_alloc_metrics(zone_alloc_df: pl.DataFrame) -> dict[str, Any]:
    pair_df = _aggregate_pair_top1(zone_alloc_df, "zone_site_count", "zone_site_count_sum")
    return {
        "pairs_total": int(pair_df.height),
        "top1_share_median": _safe_float(pair_df.select(pl.col("top1_share").median()).item(), 0.0),
        "top1_share_p75": _safe_float(pair_df.select(pl.col("top1_share").quantile(0.75)).item(), 0.0),
        "count_conservation_all_pairs": bool(pair_df.select(pl.col("count_conserved").all()).item()),
    }


def compute_metrics_from_context(ctx: dict[str, Any]) -> dict[str, Any]:
    s1_df = pl.read_parquet(ctx["paths"]["s1_glob"])
    s2_df = pl.read_parquet(ctx["paths"]["s2_glob"])
    s3_df = pl.read_parquet(ctx["paths"]["s3_glob"])
    s4_df = pl.read_parquet(ctx["paths"]["s4_glob"])
    zone_alloc_df = pl.read_parquet(ctx["paths"]["zone_alloc_glob"])

    return {
        "s1": _compute_s1_metrics(s1_df),
        "s2": _compute_s2_metrics(s2_df),
        "s3": _compute_s3_metrics(s3_df),
        "s4": _compute_s4_metrics(s4_df, s1_df),
        "zone_alloc": _compute_zone_alloc_metrics(zone_alloc_df),
    }


def evaluate_gates(metrics: dict[str, Any]) -> dict[str, dict[str, bool]]:
    s1 = metrics["s1"]
    s2 = metrics["s2"]
    s3 = metrics["s3"]
    s4 = metrics["s4"]
    zone_alloc = metrics["zone_alloc"]

    hard = {
        "3A-V01_s2_top1_median_multi_tz": bool(
            float(s2["top1_share_median_multi_tz"]) <= HARD_THRESHOLDS["s2_top1_median_multi_tz_max"]
        ),
        "3A-V02_s2_share_top1_ge_099_multi_tz": bool(
            float(s2["share_top1_ge_099_multi_tz"]) <= HARD_THRESHOLDS["s2_share_top1_ge_099_multi_tz_max"]
        ),
        "3A-V03_s4_escalated_multi_zone_rate": bool(
            float(s4["escalated_multi_zone_rate"]) >= HARD_THRESHOLDS["s4_escalated_multi_zone_rate_min"]
        ),
        "3A-V04_s3_merchant_share_std_median": bool(
            float(s3["merchant_share_std_median"]) >= HARD_THRESHOLDS["s3_merchant_share_std_median_min"]
        ),
        "3A-V05_s4_top1_share_median": bool(
            float(s4["top1_share_median"]) <= HARD_THRESHOLDS["s4_top1_share_median_max"]
        ),
        "3A-V06_s4_top1_share_p75": bool(
            float(s4["top1_share_p75"]) <= HARD_THRESHOLDS["s4_top1_share_p75_max"]
        ),
        "3A-V07_zone_alloc_top1_share_median": bool(
            float(zone_alloc["top1_share_median"]) <= HARD_THRESHOLDS["zone_alloc_top1_share_median_max"]
        ),
        "3A-VXX_s4_count_conservation": bool(s4["count_conservation_all_pairs"]),
        "3A-VXY_zone_alloc_count_conservation": bool(zone_alloc["count_conservation_all_pairs"]),
    }

    stretch = {
        "3A-S01_s2_top1_median_multi_tz": bool(
            float(s2["top1_share_median_multi_tz"]) <= STRETCH_THRESHOLDS["s2_top1_median_multi_tz_max"]
        ),
        "3A-S02_s2_share_top1_ge_099_multi_tz": bool(
            float(s2["share_top1_ge_099_multi_tz"]) <= STRETCH_THRESHOLDS["s2_share_top1_ge_099_multi_tz_max"]
        ),
        "3A-S03_s4_escalated_multi_zone_rate": bool(
            float(s4["escalated_multi_zone_rate"]) >= STRETCH_THRESHOLDS["s4_escalated_multi_zone_rate_min"]
        ),
        "3A-S04_s3_merchant_share_std_median": bool(
            float(s3["merchant_share_std_median"]) >= STRETCH_THRESHOLDS["s3_merchant_share_std_median_min"]
        ),
        "3A-S05_s4_top1_share_median": bool(
            float(s4["top1_share_median"]) <= STRETCH_THRESHOLDS["s4_top1_share_median_max"]
        ),
        "3A-S06_zone_alloc_top1_share_median": bool(
            float(zone_alloc["top1_share_median"]) <= STRETCH_THRESHOLDS["zone_alloc_top1_share_median_max"]
        ),
        "3A-S07_s1_escalation_curve_no_major_dips": bool(
            float(s1["zone_count_curve_major_dip_max_abs"])
            <= STRETCH_THRESHOLDS["s1_escalation_curve_major_dip_max_abs"]
        ),
    }
    return {"hard": hard, "stretch": stretch}


def verdict_from_gates(gates: dict[str, dict[str, bool]]) -> str:
    hard_ok = all(bool(value) for value in gates["hard"].values())
    stretch_ok = all(bool(value) for value in gates["stretch"].values())
    if stretch_ok:
        return "PASS_BPLUS"
    if hard_ok:
        return "PASS_B"
    return "FAIL_REALISM"


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    s1 = metrics["s1"]
    s2 = metrics["s2"]
    s3 = metrics["s3"]
    s4 = metrics["s4"]
    za = metrics["zone_alloc"]
    hard = payload["gates"]["hard"]
    stretch = payload["gates"]["stretch"]
    lines: list[str] = []
    lines.append("# Segment 3A P0 Baseline Metrics")
    lines.append("")
    lines.append(f"- run_id: `{payload['baseline_authority']['run_id']}`")
    lines.append(f"- seed: `{payload['baseline_authority']['seed']}`")
    lines.append(f"- manifest_fingerprint: `{payload['baseline_authority']['manifest_fingerprint']}`")
    lines.append(f"- parameter_hash: `{payload['baseline_authority']['parameter_hash']}`")
    lines.append("")
    lines.append("## Key Metrics")
    lines.append("")
    lines.append(f"- S2 top1 median (multi-TZ): `{s2['top1_share_median_multi_tz']:.6f}`")
    lines.append(f"- S2 share top1>=0.99 (multi-TZ): `{s2['share_top1_ge_099_multi_tz']:.6f}`")
    lines.append(f"- S3 merchant share-std median: `{s3['merchant_share_std_median']:.6f}`")
    lines.append(f"- S4 escalated multi-zone rate: `{s4['escalated_multi_zone_rate']:.6f}`")
    lines.append(f"- S4 top1 median / p75: `{s4['top1_share_median']:.6f}` / `{s4['top1_share_p75']:.6f}`")
    lines.append(f"- zone_alloc top1 median / p75: `{za['top1_share_median']:.6f}` / `{za['top1_share_p75']:.6f}`")
    lines.append(f"- S1 major dip max (supported buckets): `{s1['zone_count_curve_major_dip_max_abs']:.6f}`")
    lines.append("")
    lines.append("## Hard Gates (B)")
    lines.append("")
    for key, value in hard.items():
        lines.append(f"- {key}: `{'PASS' if value else 'FAIL'}`")
    lines.append("")
    lines.append("## Stretch Gates (B+)")
    lines.append("")
    for key, value in stretch.items():
        lines.append(f"- {key}: `{'PASS' if value else 'FAIL'}`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- verdict: `{payload['verdict']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 3A remediation P0 baseline scorecard.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3A")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_3A/reports")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    ctx = _resolve_run_context(runs_root, run_id)
    metrics = compute_metrics_from_context(ctx)
    gates = evaluate_gates(metrics)
    verdict = verdict_from_gates(gates)

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P0",
        "segment": "3A",
        "baseline_authority": {
            "runs_root": ctx["runs_root"],
            "run_root": ctx["run_root"],
            "run_id": ctx["run_id"],
            "seed": ctx["seed"],
            "manifest_fingerprint": ctx["manifest_fingerprint"],
            "parameter_hash": ctx["parameter_hash"],
            "lineage_tokens": {
                "seed": ctx["seed"],
                "manifest_fingerprint": ctx["manifest_fingerprint"],
                "parameter_hash": ctx["parameter_hash"],
                "run_id": ctx["run_id"],
            },
        },
        "paths": ctx["paths"],
        "thresholds": {
            "hard_B": HARD_THRESHOLDS,
            "stretch_BPLUS": STRETCH_THRESHOLDS,
        },
        "metrics": metrics,
        "gates": gates,
        "verdict": verdict,
    }

    out_root = Path(args.out_root)
    out_json = Path(args.out_json) if args.out_json else out_root / f"segment3a_p0_baseline_metrics_{ctx['run_id']}.json"
    out_md = Path(args.out_md) if args.out_md else out_root / f"segment3a_p0_baseline_metrics_{ctx['run_id']}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
