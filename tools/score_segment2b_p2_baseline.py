#!/usr/bin/env python3
"""Emit Segment 2B remediation P2.1 baseline decomposition artifacts."""

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
    if not list(root.glob("*.parquet")):
        raise FileNotFoundError(f"No S1 parquet files found under {root}")
    return str(root / "*.parquet").replace("\\", "/")


def _resolve_s3_glob(run_root: Path, seed: int, manifest_fingerprint: str) -> str:
    root = (
        run_root
        / "data"
        / "layer1"
        / "2B"
        / "s3_day_effects"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not list(root.glob("*.parquet")):
        raise FileNotFoundError(f"No S3 parquet files found under {root}")
    return str(root / "*.parquet").replace("\\", "/")


def _read_s2_summary(run_root: Path, seed: int, manifest_fingerprint: str) -> dict[str, Any]:
    path = (
        run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S2"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s2_run_report.json"
    )
    if not path.exists():
        return {"overall_status": "MISSING", "warn_count": 0, "fail_count": 1}
    return (_load_json(path)).get("summary", {})


def _read_s3_report(run_root: Path, seed: int, manifest_fingerprint: str) -> dict[str, Any]:
    path = (
        run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S3"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s3_run_report.json"
    )
    if not path.exists():
        return {}
    return _load_json(path)


def _compute_s1_metrics(s1_glob: str) -> dict[str, float]:
    s1 = pl.scan_parquet(s1_glob).with_columns([pl.len().over("merchant_id").alias("n_sites")]).with_columns(
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


def _compute_s3_metrics(s3_glob: str, s3_report: dict[str, Any]) -> dict[str, float | int]:
    s3 = pl.scan_parquet(s3_glob)
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
    return {
        "merchant_gamma_std_median": float(merchant_std_df.select(pl.col("gamma_std").median()).item()),
        "merchant_gamma_std_p90": float(merchant_std_df.select(pl.col("gamma_std").quantile(0.90)).item()),
        "merchant_day_tz_std_median": float(md_multi.select(pl.col("tz_gamma_std").median()).item()) if md_multi.height > 0 else 0.0,
        "merchant_day_tz_nonzero_share": float(md_multi.select((pl.col("tz_gamma_std") > 1.0e-12).mean()).item())
        if md_multi.height > 0
        else 0.0,
        "gamma_median": float(gamma_df.select(pl.col("gamma").median()).item()),
        "gamma_iqr": float(gq[2] - gq[1]),
        "gamma_q01": float(gq[0]),
        "gamma_q99": float(gq[3]),
        "nonpositive_gamma_rows": int(rng.get("nonpositive_gamma_rows", 0)),
        "max_abs_log_gamma": float(rng.get("max_abs_log_gamma", 0.0)),
    }


def _build_tuning_envelope(reference_s3: dict[str, Any], witness_s3: dict[str, Any]) -> dict[str, Any]:
    q01 = min(float(reference_s3["gamma_q01"]), float(witness_s3["gamma_q01"]))
    q99 = max(float(reference_s3["gamma_q99"]), float(witness_s3["gamma_q99"]))
    clip_min = max(0.25, round(q01 * 0.75, 6))
    clip_max = min(4.0, round(q99 * 1.25, 6))
    return {
        "sigma_min": 0.07,
        "sigma_max": 0.22,
        "merchant_jitter_abs_max": 0.20,
        "weekly_amp_abs_max": 0.05,
        "gamma_clip_min": clip_min,
        "gamma_clip_max": clip_max,
        "notes": [
            "Bounds chosen to increase local heterogeneity while avoiding gamma-tail instability.",
            "Weekly amplitude is bounded conservatively to avoid synthetic oscillation artifacts.",
        ],
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    ref = payload["reference_run"]["s3_metrics"]
    wit = payload["witness_run"]["s3_metrics"]
    env = payload["tuning_envelope"]
    s1 = payload["p1_lock_non_regression"]
    lines: list[str] = []
    lines.append("# Segment 2B P2.1 Baseline Decomposition")
    lines.append("")
    lines.append(f"- reference_run_id: `{payload['reference_run']['run_id']}`")
    lines.append(f"- witness_run_id: `{payload['witness_run']['run_id']}`")
    lines.append("")
    lines.append("## S1 Lock Witness")
    lines.append("")
    lines.append(f"- locked_non_regression: `{s1['pass']}`")
    lines.append(f"- s2_non_regression: `{s1['s2_non_regression']}`")
    lines.append("")
    lines.append("## S3 Baseline")
    lines.append("")
    lines.append("| Metric | Reference | Witness |")
    lines.append("|---|---:|---:|")
    lines.append(f"| merchant_gamma_std_median | {ref['merchant_gamma_std_median']:.6f} | {wit['merchant_gamma_std_median']:.6f} |")
    lines.append(f"| merchant_gamma_std_p90 | {ref['merchant_gamma_std_p90']:.6f} | {wit['merchant_gamma_std_p90']:.6f} |")
    lines.append(f"| merchant_day_tz_nonzero_share | {ref['merchant_day_tz_nonzero_share']:.6f} | {wit['merchant_day_tz_nonzero_share']:.6f} |")
    lines.append(f"| gamma_q01 | {ref['gamma_q01']:.6f} | {wit['gamma_q01']:.6f} |")
    lines.append(f"| gamma_q99 | {ref['gamma_q99']:.6f} | {wit['gamma_q99']:.6f} |")
    lines.append("")
    lines.append("## Tuning Envelope")
    lines.append("")
    lines.append(f"- sigma_min: `{env['sigma_min']}`")
    lines.append(f"- sigma_max: `{env['sigma_max']}`")
    lines.append(f"- merchant_jitter_abs_max: `{env['merchant_jitter_abs_max']}`")
    lines.append(f"- weekly_amp_abs_max: `{env['weekly_amp_abs_max']}`")
    lines.append(f"- gamma_clip_min: `{env['gamma_clip_min']}`")
    lines.append(f"- gamma_clip_max: `{env['gamma_clip_max']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 2B P2.1 baseline decomposition artifact.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B")
    parser.add_argument("--reference-run-id", default="c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--p1-lock-run-id", default="c7e3f4f9715d4256b7802bdc28579d54")
    parser.add_argument("--witness-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    reference_root = runs_root / args.reference_run_id
    p1_lock_root = runs_root / args.p1_lock_run_id
    witness_root = runs_root / args.witness_run_id

    ref_receipt = _load_json(reference_root / "run_receipt.json")
    p1_receipt = _load_json(p1_lock_root / "run_receipt.json")
    witness_receipt = _load_json(witness_root / "run_receipt.json")

    ref_seed = int(ref_receipt["seed"])
    ref_manifest = str(ref_receipt["manifest_fingerprint"])
    p1_seed = int(p1_receipt["seed"])
    p1_manifest = str(p1_receipt["manifest_fingerprint"])
    witness_seed = int(witness_receipt["seed"])
    witness_manifest = str(witness_receipt["manifest_fingerprint"])

    s1_lock = _compute_s1_metrics(_resolve_s1_glob(p1_lock_root, p1_seed, p1_manifest))
    s1_witness = _compute_s1_metrics(_resolve_s1_glob(witness_root, witness_seed, witness_manifest))
    s1_delta = {
        "residual_abs_uniform_median": float(s1_witness["residual_abs_uniform_median"] - s1_lock["residual_abs_uniform_median"]),
        "top1_top2_gap_median": float(s1_witness["top1_top2_gap_median"] - s1_lock["top1_top2_gap_median"]),
        "merchant_hhi_iqr": float(s1_witness["merchant_hhi_iqr"] - s1_lock["merchant_hhi_iqr"]),
    }
    tol = 1.0e-12
    s1_pass = all(abs(v) <= tol for v in s1_delta.values())
    s2_summary = _read_s2_summary(witness_root, witness_seed, witness_manifest)
    s2_non_reg = bool(s2_summary.get("overall_status") == "PASS" and int(s2_summary.get("fail_count", 0)) == 0)

    ref_s3 = _compute_s3_metrics(
        _resolve_s3_glob(reference_root, ref_seed, ref_manifest),
        _read_s3_report(reference_root, ref_seed, ref_manifest),
    )
    witness_s3 = _compute_s3_metrics(
        _resolve_s3_glob(witness_root, witness_seed, witness_manifest),
        _read_s3_report(witness_root, witness_seed, witness_manifest),
    )
    envelope = _build_tuning_envelope(ref_s3, witness_s3)

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P2.1",
        "segment": "2B",
        "reference_run": {"run_id": args.reference_run_id, "seed": ref_seed, "manifest_fingerprint": ref_manifest, "s3_metrics": ref_s3},
        "witness_run": {"run_id": args.witness_run_id, "seed": witness_seed, "manifest_fingerprint": witness_manifest, "s3_metrics": witness_s3},
        "p1_lock_non_regression": {
            "pass": bool(s1_pass and s2_non_reg),
            "tolerance": tol,
            "s1_delta": s1_delta,
            "s2_non_regression": s2_non_reg,
            "s2_summary": s2_summary,
        },
        "tuning_envelope": envelope,
        "verdict": "PASS_P2_1" if bool(s1_pass and s2_non_reg) else "FAIL_P2_1",
    }

    out_root = Path(args.out_root)
    out_json = out_root / f"segment2b_p2_1_baseline_{args.witness_run_id}.json"
    out_md = out_root / f"segment2b_p2_1_baseline_{args.witness_run_id}.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
