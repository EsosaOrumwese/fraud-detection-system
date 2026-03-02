#!/usr/bin/env python3
"""Score Segment 2B remediation P2 candidate and emit lock-ready artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


B_THRESHOLDS = {
    "s3_merchant_gamma_std_median_min": 0.03,
}


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


def _compute_s3_metrics(glob_path: str, s3_report: dict[str, Any]) -> dict[str, Any]:
    s3 = pl.scan_parquet(glob_path)
    merchant_std = s3.group_by("merchant_id").agg(pl.col("gamma").std(ddof=1).fill_null(0.0).alias("gamma_std"))
    merchant_std_df = merchant_std.collect()
    merchant_day_tz = s3.group_by(["merchant_id", "utc_day"]).agg(
        [pl.col("tz_group_id").n_unique().alias("tz_groups"), pl.col("gamma").std(ddof=1).fill_null(0.0).alias("tz_gamma_std")]
    )
    md_multi = merchant_day_tz.filter(pl.col("tz_groups") >= 2).collect()
    gamma_df = s3.select("gamma").collect()
    gq = gamma_df.select(
        [
            pl.col("gamma").quantile(0.01).alias("q01"),
            pl.col("gamma").quantile(0.25).alias("q25"),
            pl.col("gamma").quantile(0.75).alias("q75"),
            pl.col("gamma").quantile(0.99).alias("q99"),
        ]
    ).row(0)

    rng = (s3_report.get("rng_accounting") or {}) if isinstance(s3_report, dict) else {}
    samples = (s3_report.get("samples") or {}) if isinstance(s3_report, dict) else {}
    sample_rows = samples.get("rows") or []
    sigma_values = [float(row.get("sigma_value")) for row in sample_rows if isinstance(row, dict) and row.get("sigma_value") is not None]
    weekly_amps = [abs(float(row.get("weekly_amp"))) for row in sample_rows if isinstance(row, dict) and row.get("weekly_amp") is not None]
    sigma_sources = sorted(
        {
            str(row.get("sigma_source"))
            for row in sample_rows
            if isinstance(row, dict) and row.get("sigma_source") is not None
        }
    )

    clipped_rows = int(rng.get("gamma_clipped_rows", 0))
    rows_written = int(rng.get("rows_written", 0))
    clipped_share = (float(clipped_rows) / float(rows_written)) if rows_written > 0 else 0.0

    return {
        "merchant_gamma_std_median": float(merchant_std_df.select(pl.col("gamma_std").median()).item()),
        "merchant_gamma_std_p90": float(merchant_std_df.select(pl.col("gamma_std").quantile(0.90)).item()),
        "merchant_day_tz_nonzero_share": float(md_multi.select((pl.col("tz_gamma_std") > 1.0e-12).mean()).item())
        if md_multi.height > 0
        else 0.0,
        "gamma_median": float(gamma_df.select(pl.col("gamma").median()).item()),
        "gamma_iqr": float(gq[2] - gq[1]),
        "gamma_q01": float(gq[0]),
        "gamma_q99": float(gq[3]),
        "nonpositive_gamma_rows": int(rng.get("nonpositive_gamma_rows", 0)),
        "max_abs_log_gamma": float(rng.get("max_abs_log_gamma", 0.0)),
        "gamma_clipped_rows": clipped_rows,
        "gamma_clipped_share": clipped_share,
        "sample_sigma_min": min(sigma_values) if sigma_values else None,
        "sample_sigma_max": max(sigma_values) if sigma_values else None,
        "sample_weekly_amp_max_abs": max(weekly_amps) if weekly_amps else None,
        "sample_sigma_sources": sigma_sources,
    }


def _compute_s4_guard_metrics(glob_path: str) -> dict[str, float]:
    md = (
        pl.scan_parquet(glob_path)
        .group_by(["merchant_id", "utc_day"])
        .agg(
            [
                pl.col("p_group").max().alias("max_p_group"),
                (-pl.when(pl.col("p_group") > 0.0).then(pl.col("p_group") * pl.col("p_group").log()).otherwise(0.0))
                .sum()
                .alias("entropy"),
            ]
        )
        .collect()
    )
    return {
        "max_p_group_median": float(md.select(pl.col("max_p_group").median()).item()),
        "entropy_p50": float(md.select(pl.col("entropy").median()).item()),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    gates = payload["gates"]
    s3 = payload["candidate"]["s3_metrics"]
    lines: list[str] = []
    lines.append("# Segment 2B P2 Candidate Scorecard")
    lines.append("")
    lines.append(f"- baseline_run_id: `{payload['baseline']['run_id']}`")
    lines.append(f"- candidate_run_id: `{payload['candidate']['run_id']}`")
    lines.append(f"- verdict: `{payload['verdict']}`")
    lines.append("")
    lines.append("## S3 Metrics")
    lines.append("")
    lines.append(f"- merchant_gamma_std_median: `{s3['merchant_gamma_std_median']:.6f}`")
    lines.append(f"- merchant_day_tz_nonzero_share: `{s3['merchant_day_tz_nonzero_share']:.6f}`")
    lines.append(f"- gamma_clipped_share: `{s3['gamma_clipped_share']:.6f}`")
    lines.append(f"- sample_sigma_sources: `{','.join(s3['sample_sigma_sources']) if s3['sample_sigma_sources'] else 'NONE'}`")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append(f"- s3_b_hard_gates: `{gates['s3_b_hard_gates']}`")
    lines.append(f"- s3_stability_guard: `{gates['s3_stability_guard']}`")
    lines.append(f"- provenance_present: `{gates['provenance_present']}`")
    lines.append(f"- p1_s1_non_regression: `{gates['p1_s1_non_regression']}`")
    lines.append(f"- s2_non_regression: `{gates['s2_non_regression']}`")
    lines.append(f"- s4_guard_non_catastrophic: `{gates['s4_guard_non_catastrophic']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 2B P2 candidate.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B")
    parser.add_argument("--baseline-run-id", default="c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--p1-lock-run-id", default="c7e3f4f9715d4256b7802bdc28579d54")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    baseline_root = runs_root / args.baseline_run_id
    p1_lock_root = runs_root / args.p1_lock_run_id
    candidate_root = runs_root / args.candidate_run_id

    base_receipt = _load_json(baseline_root / "run_receipt.json")
    p1_receipt = _load_json(p1_lock_root / "run_receipt.json")
    cand_receipt = _load_json(candidate_root / "run_receipt.json")

    base_seed = int(base_receipt["seed"])
    base_manifest = str(base_receipt["manifest_fingerprint"])
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
    s1_tol = 1.0e-12
    s1_non_reg = all(abs(v) <= s1_tol for v in s1_delta.values())

    s2_summary = (_read_report(candidate_root, "S2", cand_seed, cand_manifest).get("summary") or {})
    s2_non_reg = bool(s2_summary.get("overall_status") == "PASS" and int(s2_summary.get("fail_count", 0)) == 0)

    cand_s3_report = _read_report(candidate_root, "S3", cand_seed, cand_manifest)
    cand_s3 = _compute_s3_metrics(_resolve_glob(candidate_root, "s3_day_effects", cand_seed, cand_manifest), cand_s3_report)
    base_s4 = _compute_s4_guard_metrics(_resolve_glob(baseline_root, "s4_group_weights", base_seed, base_manifest))
    cand_s4 = _compute_s4_guard_metrics(_resolve_glob(candidate_root, "s4_group_weights", cand_seed, cand_manifest))

    s3_b = bool(
        cand_s3["merchant_gamma_std_median"] >= B_THRESHOLDS["s3_merchant_gamma_std_median_min"]
        and cand_s3["merchant_day_tz_nonzero_share"] > 0.0
    )
    s3_stability = bool(
        cand_s3["nonpositive_gamma_rows"] == 0
        and cand_s3["gamma_clipped_share"] <= 0.01
        and cand_s3["max_abs_log_gamma"] <= 4.0
    )
    provenance_present = bool(
        cand_s3["sample_sigma_min"] is not None
        and cand_s3["sample_sigma_max"] is not None
        and cand_s3["sample_weekly_amp_max_abs"] is not None
        and len(cand_s3["sample_sigma_sources"]) > 0
    )
    s4_guard = bool(
        cand_s4["max_p_group_median"] <= max(0.97, base_s4["max_p_group_median"] + 0.05)
        and cand_s4["entropy_p50"] >= min(0.20, base_s4["entropy_p50"] - 0.05)
    )

    verdict = (
        "PASS_P2"
        if bool(s3_b and s3_stability and provenance_present and s1_non_reg and s2_non_reg and s4_guard)
        else "FAIL_P2"
    )

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P2",
        "segment": "2B",
        "baseline": {
            "run_id": args.baseline_run_id,
            "seed": base_seed,
            "manifest_fingerprint": base_manifest,
            "s4_guard_metrics": base_s4,
        },
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
            "s3_metrics": cand_s3,
            "s4_guard_metrics": cand_s4,
            "s2_summary": s2_summary,
        },
        "delta": {"s1_metrics_vs_p1_lock": s1_delta},
        "gates": {
            "s3_b_hard_gates": s3_b,
            "s3_stability_guard": s3_stability,
            "provenance_present": provenance_present,
            "p1_s1_non_regression": s1_non_reg,
            "s2_non_regression": s2_non_reg,
            "s4_guard_non_catastrophic": s4_guard,
        },
        "verdict": verdict,
    }

    out_root = Path(args.out_root)
    out_json = out_root / f"segment2b_p2_candidate_{args.candidate_run_id}.json"
    out_md = out_root / f"segment2b_p2_candidate_{args.candidate_run_id}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
