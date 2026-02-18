#!/usr/bin/env python3
"""Emit Segment 2B remediation P0 baseline metrics and roster posture."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"

B_THRESHOLDS = {
    "s1_residual_abs_uniform_median_min": 0.003,
    "s1_top1_top2_gap_median_min": 0.03,
    "s1_merchant_hhi_iqr_min": 0.06,
    "s3_merchant_gamma_std_median_min": 0.03,
    "s4_max_p_group_median_max": 0.85,
    "s4_share_max_p_group_ge_095_max": 0.35,
    "s4_share_groups_ge_005_ge_2_min": 0.35,
    "s4_entropy_p50_min": 0.35,
}

BPLUS_THRESHOLDS = {
    "s1_residual_abs_uniform_median_min": 0.006,
    "s1_top1_top2_gap_median_min": 0.05,
    "s1_merchant_hhi_iqr_min": 0.10,
    "s3_merchant_gamma_std_median_min": 0.04,
    "s4_max_p_group_median_max": 0.78,
    "s4_share_max_p_group_ge_095_max": 0.20,
    "s4_share_groups_ge_005_ge_2_min": 0.50,
    "s4_entropy_p50_min": 0.45,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _resolve_glob(root: Path, pattern: str) -> str:
    target = root / pattern
    if not list(root.glob(pattern)):
        raise FileNotFoundError(f"No files found for pattern: {target}")
    return str(target).replace("\\", "/")


def _read_s3_report(run_root: Path, seed: int, manifest_fingerprint: str) -> dict[str, Any]:
    report = (
        run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S3"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s3_run_report.json"
    )
    if not report.exists():
        return {}
    return _load_json(report)


def _compute_s1_metrics(s1_glob: str) -> dict[str, Any]:
    s1 = pl.scan_parquet(s1_glob).with_columns([pl.len().over("merchant_id").alias("n_sites")]).with_columns(
        [(pl.col("p_weight") - (pl.lit(1.0) / pl.col("n_sites"))).abs().alias("abs_uniform_residual")]
    )
    merchant = (
        s1.group_by("merchant_id")
        .agg(
            [
                pl.col("n_sites").first().alias("n_sites"),
                pl.col("p_weight").max().alias("top1"),
                pl.col("p_weight").sort(descending=True).slice(1, 1).first().fill_null(0.0).alias("top2"),
                (pl.col("p_weight") * pl.col("p_weight")).sum().alias("hhi"),
                pl.col("abs_uniform_residual").median().alias("merchant_residual_median"),
            ]
        )
        .with_columns([(pl.col("top1") - pl.col("top2")).alias("top1_top2_gap")])
        .collect()
    )
    hhi_q = merchant.select(
        [pl.col("hhi").quantile(0.25).alias("q25"), pl.col("hhi").quantile(0.75).alias("q75")]
    ).row(0)
    return {
        "merchant_count": int(merchant.height),
        "residual_abs_uniform_median": float(merchant.select(pl.col("merchant_residual_median").median()).item()),
        "top1_top2_gap_median": float(merchant.select(pl.col("top1_top2_gap").median()).item()),
        "merchant_hhi_q25": float(hhi_q[0]),
        "merchant_hhi_q75": float(hhi_q[1]),
        "merchant_hhi_iqr": float(hhi_q[1] - hhi_q[0]),
    }


def _compute_s3_metrics(s3_glob: str, s3_report: dict[str, Any]) -> dict[str, Any]:
    s3 = pl.scan_parquet(s3_glob)
    merchant_std = s3.group_by("merchant_id").agg(pl.col("gamma").std(ddof=1).fill_null(0.0).alias("gamma_std"))
    merchant_day_tz = s3.group_by(["merchant_id", "utc_day"]).agg(
        [pl.col("tz_group_id").n_unique().alias("tz_groups"), pl.col("gamma").std(ddof=1).fill_null(0.0).alias("tz_gamma_std")]
    )
    md_multi = merchant_day_tz.filter(pl.col("tz_groups") >= 2).collect()
    gamma_df = s3.select("gamma").collect()
    gq = gamma_df.select(
        [pl.col("gamma").quantile(0.25).alias("q25"), pl.col("gamma").quantile(0.75).alias("q75")]
    ).row(0)

    rng = (s3_report.get("rng_accounting") or {}) if isinstance(s3_report, dict) else {}
    nonpositive_gamma_rows = int(rng.get("nonpositive_gamma_rows", 0))
    max_abs_log_gamma = float(rng.get("max_abs_log_gamma", 0.0))

    return {
        "merchant_count": int(merchant_std.collect().height),
        "merchant_gamma_std_median": float(merchant_std.select(pl.col("gamma_std").median()).collect().item()),
        "merchant_day_multi_tz_count": int(md_multi.height),
        "merchant_day_tz_std_median": float(md_multi.select(pl.col("tz_gamma_std").median()).item()) if md_multi.height > 0 else 0.0,
        "merchant_day_tz_nonzero_share": float(md_multi.select((pl.col("tz_gamma_std") > 1.0e-12).mean()).item())
        if md_multi.height > 0
        else 0.0,
        "gamma_median": float(gamma_df.select(pl.col("gamma").median()).item()),
        "gamma_iqr": float(gq[1] - gq[0]),
        "nonpositive_gamma_rows": nonpositive_gamma_rows,
        "max_abs_log_gamma": max_abs_log_gamma,
        "gamma_stability_proxy_pass": bool(nonpositive_gamma_rows == 0),
    }


def _compute_s4_metrics(s4_glob: str) -> dict[str, Any]:
    md = (
        pl.scan_parquet(s4_glob)
        .group_by(["merchant_id", "utc_day"])
        .agg(
            [
                pl.col("p_group").max().alias("max_p_group"),
                (pl.col("p_group") >= 0.05).sum().alias("groups_ge_005"),
                (-pl.when(pl.col("p_group") > 0.0).then(pl.col("p_group") * pl.col("p_group").log()).otherwise(0.0))
                .sum()
                .alias("entropy"),
                pl.col("p_group").sum().alias("mass_sum"),
            ]
        )
        .with_columns([(pl.col("mass_sum") - 1.0).abs().alias("mass_abs_error")])
        .collect()
    )
    return {
        "merchant_day_count": int(md.height),
        "max_p_group_median": float(md.select(pl.col("max_p_group").median()).item()),
        "share_max_p_group_ge_095": float(md.select((pl.col("max_p_group") >= 0.95).mean()).item()),
        "share_groups_ge_005_ge_2": float(md.select((pl.col("groups_ge_005") >= 2).mean()).item()),
        "entropy_p50": float(md.select(pl.col("entropy").median()).item()),
        "mass_abs_error_max": float(md.select(pl.col("mass_abs_error").max()).item()),
        "mass_abs_error_p99": float(md.select(pl.col("mass_abs_error").quantile(0.99)).item()),
        "mass_conservation_all_rows": bool(md.select((pl.col("mass_abs_error") <= 1.0e-9).all()).item()),
    }


def _compute_roster_posture(roster_path: Path) -> dict[str, Any]:
    merchant_day_counts: Counter[tuple[int, str]] = Counter()
    days: set[str] = set()
    total = 0
    virtual_true = 0
    with roster_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            total += 1
            row = json.loads(line)
            merchant_id = int(row["merchant_id"])
            utc_day = str(row["utc_day"])
            merchant_day_counts[(merchant_id, utc_day)] += 1
            days.add(utc_day)
            if bool(row.get("is_virtual", False)):
                virtual_true += 1
    ordered_days = sorted(days)
    horizon_span_days = 0
    if ordered_days:
        d0 = datetime.strptime(ordered_days[0], "%Y-%m-%d").date()
        d1 = datetime.strptime(ordered_days[-1], "%Y-%m-%d").date()
        horizon_span_days = (d1 - d0).days + 1
    merchant_day_total = len(merchant_day_counts)
    merchant_day_repeat_ge2 = sum(1 for count in merchant_day_counts.values() if count >= 2)
    repeat_share = (float(merchant_day_repeat_ge2) / float(merchant_day_total)) if merchant_day_total > 0 else 0.0
    class_channel_coverage_observable = False
    class_channel_retained = None
    return {
        "arrival_total": total,
        "virtual_arrival_total": virtual_true,
        "physical_arrival_total": total - virtual_true,
        "utc_day_count": len(ordered_days),
        "utc_day_min": ordered_days[0] if ordered_days else None,
        "utc_day_max": ordered_days[-1] if ordered_days else None,
        "horizon_span_days": horizon_span_days,
        "merchant_day_total": merchant_day_total,
        "merchant_day_repeat_ge2_total": merchant_day_repeat_ge2,
        "merchant_day_repeat_ge2_share": repeat_share,
        "class_channel_coverage_observable": class_channel_coverage_observable,
        "class_channel_retained": class_channel_retained,
        "preconditions": {
            "horizon_ge_28_days": bool(horizon_span_days >= 28),
            "repeated_arrivals_present": bool(merchant_day_repeat_ge2 > 0),
            "class_channel_retained": class_channel_retained,
            "ready_for_realism_grading": bool(
                horizon_span_days >= 28
                and merchant_day_repeat_ge2 > 0
                and class_channel_coverage_observable
                and bool(class_channel_retained)
            ),
        },
    }


def _evaluate_hard_gates(metrics: dict[str, Any], thresholds: dict[str, float]) -> dict[str, bool]:
    s1 = metrics["s1"]
    s3 = metrics["s3"]
    s4 = metrics["s4"]
    return {
        "s1_residual_abs_uniform_median": bool(
            float(s1["residual_abs_uniform_median"]) >= thresholds["s1_residual_abs_uniform_median_min"]
        ),
        "s1_top1_top2_gap_median": bool(float(s1["top1_top2_gap_median"]) >= thresholds["s1_top1_top2_gap_median_min"]),
        "s1_merchant_hhi_iqr": bool(float(s1["merchant_hhi_iqr"]) >= thresholds["s1_merchant_hhi_iqr_min"]),
        "s3_merchant_gamma_std_median": bool(
            float(s3["merchant_gamma_std_median"]) >= thresholds["s3_merchant_gamma_std_median_min"]
        ),
        "s3_tz_group_differentiation_nonzero": bool(float(s3["merchant_day_tz_nonzero_share"]) > 0.0),
        "s3_gamma_stability_proxy": bool(s3["gamma_stability_proxy_pass"]),
        "s4_max_p_group_median": bool(float(s4["max_p_group_median"]) <= thresholds["s4_max_p_group_median_max"]),
        "s4_share_max_p_group_ge_095": bool(
            float(s4["share_max_p_group_ge_095"]) <= thresholds["s4_share_max_p_group_ge_095_max"]
        ),
        "s4_share_groups_ge_005_ge_2": bool(
            float(s4["share_groups_ge_005_ge_2"]) >= thresholds["s4_share_groups_ge_005_ge_2_min"]
        ),
        "s4_entropy_p50": bool(float(s4["entropy_p50"]) >= thresholds["s4_entropy_p50_min"]),
        "s4_mass_conservation": bool(s4["mass_conservation_all_rows"]),
    }


def _verdict(roster_ready: bool, gates_b: dict[str, bool], gates_bplus: dict[str, bool]) -> str:
    all_b = all(gates_b.values())
    all_bplus = all(gates_bplus.values())
    if not roster_ready:
        return "INVALID_FOR_GRADING"
    if all_bplus:
        return "PASS_BPLUS"
    if all_b:
        return "PASS_B"
    return "FAIL_REALISM"


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    g = payload["hard_gates"]
    s1 = payload["metrics"]["s1"]
    s3 = payload["metrics"]["s3"]
    s4 = payload["metrics"]["s4"]
    roster = payload["roster_posture"]
    lines: list[str] = []
    lines.append("# Segment 2B P0 Baseline Metrics")
    lines.append("")
    lines.append(f"- run_id: `{payload['baseline_authority']['run_id']}`")
    lines.append(f"- seed: `{payload['baseline_authority']['seed']}`")
    lines.append(f"- manifest_fingerprint: `{payload['baseline_authority']['manifest_fingerprint']}`")
    lines.append(f"- parameter_hash: `{payload['baseline_authority']['parameter_hash']}`")
    lines.append("")
    lines.append("## Hard-Gate Baseline (Authority Run)")
    lines.append("")
    lines.append("| Axis | Value | B | B+ |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| S1 residual abs-uniform median | {s1['residual_abs_uniform_median']:.6f} | {'PASS' if g['B']['s1_residual_abs_uniform_median'] else 'FAIL'} | {'PASS' if g['BPLUS']['s1_residual_abs_uniform_median'] else 'FAIL'} |"
    )
    lines.append(
        f"| S1 top1-top2 gap median | {s1['top1_top2_gap_median']:.6f} | {'PASS' if g['B']['s1_top1_top2_gap_median'] else 'FAIL'} | {'PASS' if g['BPLUS']['s1_top1_top2_gap_median'] else 'FAIL'} |"
    )
    lines.append(
        f"| S1 merchant HHI IQR | {s1['merchant_hhi_iqr']:.6f} | {'PASS' if g['B']['s1_merchant_hhi_iqr'] else 'FAIL'} | {'PASS' if g['BPLUS']['s1_merchant_hhi_iqr'] else 'FAIL'} |"
    )
    lines.append(
        f"| S3 merchant gamma std median | {s3['merchant_gamma_std_median']:.6f} | {'PASS' if g['B']['s3_merchant_gamma_std_median'] else 'FAIL'} | {'PASS' if g['BPLUS']['s3_merchant_gamma_std_median'] else 'FAIL'} |"
    )
    lines.append(
        f"| S3 tz-group differentiation share>0 | {s3['merchant_day_tz_nonzero_share']:.6f} | {'PASS' if g['B']['s3_tz_group_differentiation_nonzero'] else 'FAIL'} | {'PASS' if g['BPLUS']['s3_tz_group_differentiation_nonzero'] else 'FAIL'} |"
    )
    lines.append(
        f"| S4 max_p_group median | {s4['max_p_group_median']:.6f} | {'PASS' if g['B']['s4_max_p_group_median'] else 'FAIL'} | {'PASS' if g['BPLUS']['s4_max_p_group_median'] else 'FAIL'} |"
    )
    lines.append(
        f"| S4 share max_p_group>=0.95 | {s4['share_max_p_group_ge_095']:.6f} | {'PASS' if g['B']['s4_share_max_p_group_ge_095'] else 'FAIL'} | {'PASS' if g['BPLUS']['s4_share_max_p_group_ge_095'] else 'FAIL'} |"
    )
    lines.append(
        f"| S4 share groups p>=0.05 and >=2 groups | {s4['share_groups_ge_005_ge_2']:.6f} | {'PASS' if g['B']['s4_share_groups_ge_005_ge_2'] else 'FAIL'} | {'PASS' if g['BPLUS']['s4_share_groups_ge_005_ge_2'] else 'FAIL'} |"
    )
    lines.append(
        f"| S4 entropy p50 | {s4['entropy_p50']:.6f} | {'PASS' if g['B']['s4_entropy_p50'] else 'FAIL'} | {'PASS' if g['BPLUS']['s4_entropy_p50'] else 'FAIL'} |"
    )
    lines.append(
        f"| S4 mass conservation | {1.0 - s4['mass_abs_error_max']:.12f} | {'PASS' if g['B']['s4_mass_conservation'] else 'FAIL'} | {'PASS' if g['BPLUS']['s4_mass_conservation'] else 'FAIL'} |"
    )
    lines.append("")
    lines.append("## Roster Posture")
    lines.append("")
    lines.append(f"- horizon_span_days: `{roster['horizon_span_days']}`")
    lines.append(f"- merchant_day_repeat_ge2_share: `{roster['merchant_day_repeat_ge2_share']:.6f}`")
    lines.append(
        f"- class_channel_coverage_observable: `{roster['class_channel_coverage_observable']}`"
    )
    lines.append(f"- ready_for_realism_grading: `{roster['preconditions']['ready_for_realism_grading']}`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- verdict: `{payload['verdict']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 2B remediation P0 baseline scorecard.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    seed = int(receipt["seed"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])
    parameter_hash = str(receipt["parameter_hash"])

    s1_glob = _resolve_glob(
        run_root / "data" / "layer1" / "2B" / "s1_site_weights" / f"seed={seed}" / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )
    s3_glob = _resolve_glob(
        run_root / "data" / "layer1" / "2B" / "s3_day_effects" / f"seed={seed}" / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )
    s4_glob = _resolve_glob(
        run_root / "data" / "layer1" / "2B" / "s4_group_weights" / f"seed={seed}" / f"manifest_fingerprint={manifest_fingerprint}",
        "*.parquet",
    )
    roster_path = (
        run_root
        / "data"
        / "layer1"
        / "2B"
        / "s5_arrival_roster"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
        / "arrival_roster.jsonl"
    )
    if not roster_path.exists():
        raise FileNotFoundError(f"Roster file not found: {roster_path}")

    s3_report = _read_s3_report(run_root, seed, manifest_fingerprint)

    metrics = {
        "s1": _compute_s1_metrics(s1_glob),
        "s3": _compute_s3_metrics(s3_glob, s3_report),
        "s4": _compute_s4_metrics(s4_glob),
    }
    roster_posture = _compute_roster_posture(roster_path)
    gates_b = _evaluate_hard_gates(metrics, B_THRESHOLDS)
    gates_bplus = _evaluate_hard_gates(metrics, BPLUS_THRESHOLDS)
    verdict = _verdict(bool(roster_posture["preconditions"]["ready_for_realism_grading"]), gates_b, gates_bplus)

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P0",
        "segment": "2B",
        "baseline_authority": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "lineage_tokens": {
                "seed": seed,
                "manifest_fingerprint": manifest_fingerprint,
                "parameter_hash": parameter_hash,
                "run_id": run_id,
            },
        },
        "paths": {
            "s1_glob": s1_glob,
            "s3_glob": s3_glob,
            "s4_glob": s4_glob,
            "roster_path": str(roster_path).replace("\\", "/"),
        },
        "thresholds": {"B": B_THRESHOLDS, "BPLUS": BPLUS_THRESHOLDS},
        "metrics": metrics,
        "hard_gates": {"B": gates_b, "BPLUS": gates_bplus},
        "roster_posture": roster_posture,
        "verdict": verdict,
    }

    out_root = Path(args.out_root)
    out_json = Path(args.out_json) if args.out_json else out_root / f"segment2b_p0_baseline_metrics_{run_id}.json"
    out_md = Path(args.out_md) if args.out_md else out_root / f"segment2b_p0_baseline_metrics_{run_id}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
