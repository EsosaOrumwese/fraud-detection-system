#!/usr/bin/env python3
"""Score Segment 2B remediation P3 candidate (S4 anti-dominance closure)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


B_THRESHOLDS = {
    "max_p_group_median_max": 0.85,
    "tail_share_max_ge_095_max": 0.35,
    "multigroup_share_min": 0.35,
    "entropy_p50_min": 0.35,
}

BPLUS_THRESHOLDS = {
    "max_p_group_median_max": 0.78,
    "tail_share_max_ge_095_max": 0.20,
    "multigroup_share_min": 0.50,
    "entropy_p50_min": 0.45,
}

EPSILON = 1.0e-12


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_glob(run_root: Path, state_id: str, seed: int, manifest_fingerprint: str) -> str:
    root = (
        run_root
        / "data"
        / "layer1"
        / "2B"
        / state_id
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not list(root.glob("*.parquet")):
        raise FileNotFoundError(f"No parquet files found under {root}")
    return str(root / "*.parquet").replace("\\", "/")


def _read_report(run_root: Path, state: str, seed: int, manifest_fingerprint: str) -> dict[str, Any]:
    path = (
        run_root
        / "reports"
        / "layer1"
        / "2B"
        / f"state={state}"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / f"{state.lower()}_run_report.json"
    )
    if not path.exists():
        return {}
    return _load_json(path)


def _read_s7_report(run_root: Path, seed: int, manifest_fingerprint: str) -> dict[str, Any]:
    report_path = (
        run_root
        / "data"
        / "layer1"
        / "2B"
        / "s7_audit_report"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s7_audit_report.json"
    )
    if not report_path.exists():
        return {}
    return _load_json(report_path)


def _compute_s1_metrics(glob_path: str) -> dict[str, float]:
    s1 = pl.scan_parquet(glob_path).with_columns([pl.len().over("merchant_id").alias("n_sites")]).with_columns(
        [(pl.col("p_weight") - (pl.lit(1.0) / pl.col("n_sites"))).abs().alias("abs_uniform_residual")]
    )
    merchant = (
        s1.group_by("merchant_id")
        .agg(
            [
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
        "residual_abs_uniform_median": float(merchant.select(pl.col("merchant_residual_median").median()).item()),
        "top1_top2_gap_median": float(merchant.select(pl.col("top1_top2_gap").median()).item()),
        "merchant_hhi_iqr": float(hhi_q[1] - hhi_q[0]),
    }


def _compute_s4_metrics(glob_path: str) -> dict[str, float]:
    md = (
        pl.scan_parquet(glob_path)
        .group_by(["merchant_id", "utc_day"])
        .agg(
            [
                pl.col("p_group").max().alias("max_p_group"),
                (pl.col("p_group") >= 0.05).sum().alias("groups_ge_005"),
                (-pl.when(pl.col("p_group") > 0.0).then(pl.col("p_group") * pl.col("p_group").log()).otherwise(0.0))
                .sum()
                .alias("entropy"),
                (pl.col("p_group").sum() - 1.0).abs().alias("sum_abs_error"),
            ]
        )
        .collect()
    )
    return {
        "max_p_group_median": float(md.select(pl.col("max_p_group").median()).item()),
        "tail_share_max_ge_095": float(md.select((pl.col("max_p_group") >= 0.95).mean()).item()),
        "multigroup_share_ge2_ge_005": float(md.select((pl.col("groups_ge_005") >= 2).mean()).item()),
        "entropy_p50": float(md.select(pl.col("entropy").median()).item()),
        "mass_abs_error_max": float(md.select(pl.col("sum_abs_error").max()).item()),
        "mass_abs_error_p99": float(md.select(pl.col("sum_abs_error").quantile(0.99)).item()),
        "mass_rows_over_epsilon": int(md.filter(pl.col("sum_abs_error") > EPSILON).height),
        "merchant_days_total": int(md.height),
    }


def _compute_s3_metrics_from_report(s3_report: dict[str, Any]) -> dict[str, float]:
    rng = (s3_report.get("rng_accounting") or {}) if isinstance(s3_report, dict) else {}
    rows_written = int(rng.get("rows_written", 0))
    clipped_rows = int(rng.get("gamma_clipped_rows", 0))
    clipped_share = (float(clipped_rows) / float(rows_written)) if rows_written > 0 else 0.0
    return {
        "rows_written": rows_written,
        "nonpositive_gamma_rows": int(rng.get("nonpositive_gamma_rows", 0)),
        "gamma_clipped_share": clipped_share,
        "max_abs_log_gamma": float(rng.get("max_abs_log_gamma", 0.0)),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    gates = payload["gates"]
    s4 = payload["candidate"]["s4_metrics"]
    lines: list[str] = []
    lines.append("# Segment 2B P3 Candidate Scorecard")
    lines.append("")
    lines.append(f"- p1_lock_run_id: `{payload['p1_lock']['run_id']}`")
    lines.append(f"- candidate_run_id: `{payload['candidate']['run_id']}`")
    lines.append(f"- verdict: `{payload['verdict']}`")
    lines.append("")
    lines.append("## S4 Metrics")
    lines.append("")
    lines.append(f"- max_p_group_median: `{s4['max_p_group_median']:.6f}`")
    lines.append(f"- tail_share_max_ge_095: `{s4['tail_share_max_ge_095']:.6f}`")
    lines.append(f"- multigroup_share_ge2_ge_005: `{s4['multigroup_share_ge2_ge_005']:.6f}`")
    lines.append(f"- entropy_p50: `{s4['entropy_p50']:.6f}`")
    lines.append(f"- mass_abs_error_max: `{s4['mass_abs_error_max']:.3e}`")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append(f"- p1_s1_non_regression: `{gates['p1_s1_non_regression']}`")
    lines.append(f"- s2_non_regression: `{gates['s2_non_regression']}`")
    lines.append(f"- s3_non_regression: `{gates['s3_non_regression']}`")
    lines.append(f"- s7_non_regression: `{gates['s7_non_regression']}`")
    lines.append(f"- s8_bundle_present: `{gates['s8_bundle_present']}`")
    lines.append(f"- s4_mass_conservation: `{gates['s4_mass_conservation']}`")
    lines.append(f"- s4_b_band: `{gates['s4_b_band']}`")
    lines.append(f"- s4_bplus_band: `{gates['s4_bplus_band']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 2B P3 candidate.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B")
    parser.add_argument("--p1-lock-run-id", default="c7e3f4f9715d4256b7802bdc28579d54")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    p1_lock_root = runs_root / args.p1_lock_run_id
    candidate_root = runs_root / args.candidate_run_id

    p1_receipt = _load_json(p1_lock_root / "run_receipt.json")
    cand_receipt = _load_json(candidate_root / "run_receipt.json")

    p1_seed = int(p1_receipt["seed"])
    p1_manifest = str(p1_receipt["manifest_fingerprint"])
    cand_seed = int(cand_receipt["seed"])
    cand_manifest = str(cand_receipt["manifest_fingerprint"])

    p1_s1 = _compute_s1_metrics(_resolve_glob(p1_lock_root, "s1_site_weights", p1_seed, p1_manifest))
    cand_s1 = _compute_s1_metrics(_resolve_glob(candidate_root, "s1_site_weights", cand_seed, cand_manifest))
    s1_delta = {
        "residual_abs_uniform_median": float(cand_s1["residual_abs_uniform_median"] - p1_s1["residual_abs_uniform_median"]),
        "top1_top2_gap_median": float(cand_s1["top1_top2_gap_median"] - p1_s1["top1_top2_gap_median"]),
        "merchant_hhi_iqr": float(cand_s1["merchant_hhi_iqr"] - p1_s1["merchant_hhi_iqr"]),
    }
    p1_s1_non_reg = all(abs(value) <= 1.0e-12 for value in s1_delta.values())

    s2_summary = (_read_report(candidate_root, "S2", cand_seed, cand_manifest).get("summary") or {})
    s2_non_reg = bool(s2_summary.get("overall_status") == "PASS" and int(s2_summary.get("fail_count", 0)) == 0)

    s3_report = _read_report(candidate_root, "S3", cand_seed, cand_manifest)
    s3_summary = (s3_report.get("summary") or {}) if isinstance(s3_report, dict) else {}
    s3_metrics = _compute_s3_metrics_from_report(s3_report)
    s3_non_reg = bool(
        s3_summary.get("overall_status") == "PASS"
        and int(s3_summary.get("fail_count", 0)) == 0
        and s3_metrics["nonpositive_gamma_rows"] == 0
        and s3_metrics["gamma_clipped_share"] <= 0.01
        and s3_metrics["max_abs_log_gamma"] <= 4.0
    )

    s7_summary = (_read_s7_report(candidate_root, cand_seed, cand_manifest).get("summary") or {})
    s7_non_reg = bool(s7_summary.get("overall_status") == "PASS" and int(s7_summary.get("fail_count", 0)) == 0)

    s8_flag = (
        candidate_root
        / "data"
        / "layer1"
        / "2B"
        / "validation"
        / f"manifest_fingerprint={cand_manifest}"
        / "_passed.flag"
    )
    s8_bundle_present = bool(s8_flag.exists())

    s4_metrics = _compute_s4_metrics(_resolve_glob(candidate_root, "s4_group_weights", cand_seed, cand_manifest))
    s4_mass_conservation = bool(
        s4_metrics["mass_rows_over_epsilon"] == 0 and s4_metrics["mass_abs_error_max"] <= EPSILON
    )

    s4_b_band = bool(
        s4_metrics["max_p_group_median"] <= B_THRESHOLDS["max_p_group_median_max"]
        and s4_metrics["tail_share_max_ge_095"] <= B_THRESHOLDS["tail_share_max_ge_095_max"]
        and s4_metrics["multigroup_share_ge2_ge_005"] >= B_THRESHOLDS["multigroup_share_min"]
        and s4_metrics["entropy_p50"] >= B_THRESHOLDS["entropy_p50_min"]
    )
    s4_bplus_band = bool(
        s4_metrics["max_p_group_median"] <= BPLUS_THRESHOLDS["max_p_group_median_max"]
        and s4_metrics["tail_share_max_ge_095"] <= BPLUS_THRESHOLDS["tail_share_max_ge_095_max"]
        and s4_metrics["multigroup_share_ge2_ge_005"] >= BPLUS_THRESHOLDS["multigroup_share_min"]
        and s4_metrics["entropy_p50"] >= BPLUS_THRESHOLDS["entropy_p50_min"]
    )

    rails_green = bool(
        p1_s1_non_reg and s2_non_reg and s3_non_reg and s7_non_reg and s8_bundle_present and s4_mass_conservation
    )
    if rails_green and s4_bplus_band:
        verdict = "PASS_BPLUS_P3"
    elif rails_green and s4_b_band:
        verdict = "PASS_B_P3"
    else:
        verdict = "FAIL_P3"

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P3",
        "segment": "2B",
        "p1_lock": {
            "run_id": args.p1_lock_run_id,
            "seed": p1_seed,
            "manifest_fingerprint": p1_manifest,
            "s1_metrics": p1_s1,
        },
        "candidate": {
            "run_id": args.candidate_run_id,
            "seed": cand_seed,
            "manifest_fingerprint": cand_manifest,
            "s1_metrics": cand_s1,
            "s2_summary": s2_summary,
            "s3_summary": s3_summary,
            "s3_metrics": s3_metrics,
            "s7_summary": s7_summary,
            "s4_metrics": s4_metrics,
            "s8_passed_flag_path": str(s8_flag),
        },
        "delta": {"s1_metrics_vs_p1_lock": s1_delta},
        "gates": {
            "p1_s1_non_regression": p1_s1_non_reg,
            "s2_non_regression": s2_non_reg,
            "s3_non_regression": s3_non_reg,
            "s7_non_regression": s7_non_reg,
            "s8_bundle_present": s8_bundle_present,
            "s4_mass_conservation": s4_mass_conservation,
            "s4_b_band": s4_b_band,
            "s4_bplus_band": s4_bplus_band,
        },
        "verdict": verdict,
    }

    out_root = Path(args.out_root)
    out_json = out_root / f"segment2b_p3_candidate_{args.candidate_run_id}.json"
    out_md = out_root / f"segment2b_p3_candidate_{args.candidate_run_id}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
