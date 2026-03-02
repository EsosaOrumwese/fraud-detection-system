#!/usr/bin/env python3
"""Score Segment 2B P1 candidate against pinned P0 baseline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


B_THRESHOLDS = {
    "s1_residual_abs_uniform_median_min": 0.003,
    "s1_top1_top2_gap_median_min": 0.03,
    "s1_merchant_hhi_iqr_min": 0.06,
}

BPLUS_THRESHOLDS = {
    "s1_residual_abs_uniform_median_min": 0.006,
    "s1_top1_top2_gap_median_min": 0.05,
    "s1_merchant_hhi_iqr_min": 0.10,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_s1_glob(run_root: Path, seed: int, manifest_fingerprint: str) -> str:
    root = (
        run_root
        / "data"
        / "layer1"
        / "2B"
        / "s1_site_weights"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    files = list(root.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No S1 parquet files found under {root}")
    return str(root / "*.parquet").replace("\\", "/")


def _compute_s1_metrics(s1_glob: str) -> dict[str, float]:
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
        "merchant_count": float(merchant.height),
        "residual_abs_uniform_median": float(merchant.select(pl.col("merchant_residual_median").median()).item()),
        "top1_top2_gap_median": float(merchant.select(pl.col("top1_top2_gap").median()).item()),
        "merchant_hhi_q25": float(hhi_q[0]),
        "merchant_hhi_q75": float(hhi_q[1]),
        "merchant_hhi_iqr": float(hhi_q[1] - hhi_q[0]),
    }


def _s1_band_pass(metrics: dict[str, float], thresholds: dict[str, float]) -> dict[str, bool]:
    return {
        "residual": bool(metrics["residual_abs_uniform_median"] >= thresholds["s1_residual_abs_uniform_median_min"]),
        "top1_top2_gap": bool(metrics["top1_top2_gap_median"] >= thresholds["s1_top1_top2_gap_median_min"]),
        "hhi_iqr": bool(metrics["merchant_hhi_iqr"] >= thresholds["s1_merchant_hhi_iqr_min"]),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    base = payload["baseline"]["s1_metrics"]
    cand = payload["candidate"]["s1_metrics"]
    delta = payload["delta"]["s1_metrics"]
    lines: list[str] = []
    lines.append("# Segment 2B P1 Candidate Scorecard")
    lines.append("")
    lines.append(f"- baseline_run_id: `{payload['baseline']['run_id']}`")
    lines.append(f"- candidate_run_id: `{payload['candidate']['run_id']}`")
    lines.append(f"- verdict: `{payload['verdict']}`")
    lines.append("")
    lines.append("## S1 Metrics")
    lines.append("")
    lines.append("| Metric | Baseline | Candidate | Delta |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| residual_abs_uniform_median | {base['residual_abs_uniform_median']:.6f} | {cand['residual_abs_uniform_median']:.6f} | {delta['residual_abs_uniform_median']:.6f} |"
    )
    lines.append(
        f"| top1_top2_gap_median | {base['top1_top2_gap_median']:.6f} | {cand['top1_top2_gap_median']:.6f} | {delta['top1_top2_gap_median']:.6f} |"
    )
    lines.append(
        f"| merchant_hhi_iqr | {base['merchant_hhi_iqr']:.6f} | {cand['merchant_hhi_iqr']:.6f} | {delta['merchant_hhi_iqr']:.6f} |"
    )
    lines.append("")
    lines.append("## P1 Gates")
    lines.append("")
    lines.append(f"- movement: `{payload['gates']['movement']}`")
    lines.append(f"- b_band: `{payload['gates']['b_band']}`")
    lines.append(f"- bplus_band: `{payload['gates']['bplus_band']}`")
    lines.append(f"- s2_non_regression: `{payload['gates']['s2_non_regression']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 2B P1 candidate S1 movement and S2 non-regression.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B")
    parser.add_argument("--baseline-run-id", default="c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    baseline_root = runs_root / args.baseline_run_id
    candidate_root = runs_root / args.candidate_run_id
    baseline_receipt = _load_json(baseline_root / "run_receipt.json")
    candidate_receipt = _load_json(candidate_root / "run_receipt.json")

    base_seed = int(baseline_receipt["seed"])
    base_manifest = str(baseline_receipt["manifest_fingerprint"])
    cand_seed = int(candidate_receipt["seed"])
    cand_manifest = str(candidate_receipt["manifest_fingerprint"])

    baseline_metrics = _compute_s1_metrics(_resolve_s1_glob(baseline_root, base_seed, base_manifest))
    candidate_metrics = _compute_s1_metrics(_resolve_s1_glob(candidate_root, cand_seed, cand_manifest))

    s2_report_path = (
        candidate_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S2"
        / f"seed={cand_seed}"
        / f"manifest_fingerprint={cand_manifest}"
        / "s2_run_report.json"
    )
    s2_report = _load_json(s2_report_path)
    s2_summary = s2_report.get("summary", {})
    s2_non_regression = bool(s2_summary.get("overall_status") == "PASS" and int(s2_summary.get("fail_count", 0)) == 0)

    delta = {
        "residual_abs_uniform_median": float(candidate_metrics["residual_abs_uniform_median"] - baseline_metrics["residual_abs_uniform_median"]),
        "top1_top2_gap_median": float(candidate_metrics["top1_top2_gap_median"] - baseline_metrics["top1_top2_gap_median"]),
        "merchant_hhi_iqr": float(candidate_metrics["merchant_hhi_iqr"] - baseline_metrics["merchant_hhi_iqr"]),
    }
    movement = {
        "residual_activated": bool(delta["residual_abs_uniform_median"] > 1.0e-9),
        "top1_top2_gap_activated": bool(delta["top1_top2_gap_median"] > 1.0e-9),
        "hhi_spread_activated": bool(delta["merchant_hhi_iqr"] > 1.0e-9),
    }
    b_band = _s1_band_pass(candidate_metrics, B_THRESHOLDS)
    bplus_band = _s1_band_pass(candidate_metrics, BPLUS_THRESHOLDS)
    movement_pass = all(movement.values())
    b_pass = all(b_band.values())
    verdict = "PASS_P1" if movement_pass and s2_non_regression else "FAIL_P1"

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P1",
        "segment": "2B",
        "baseline": {
            "run_id": args.baseline_run_id,
            "seed": base_seed,
            "manifest_fingerprint": base_manifest,
            "s1_metrics": baseline_metrics,
        },
        "candidate": {
            "run_id": args.candidate_run_id,
            "seed": cand_seed,
            "manifest_fingerprint": cand_manifest,
            "s1_metrics": candidate_metrics,
            "s2_report_path": str(s2_report_path).replace("\\", "/"),
            "s2_summary": s2_summary,
        },
        "delta": {"s1_metrics": delta},
        "bands": {"B": b_band, "BPLUS": bplus_band},
        "gates": {
            "movement": movement_pass,
            "movement_detail": movement,
            "b_band": b_pass,
            "bplus_band": all(bplus_band.values()),
            "s2_non_regression": s2_non_regression,
        },
        "verdict": verdict,
    }

    out_root = Path(args.out_root)
    out_json = out_root / f"segment2b_p1_candidate_{args.candidate_run_id}.json"
    out_md = out_root / f"segment2b_p1_candidate_{args.candidate_run_id}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
