"""Score Segment 1B P4 integrated candidate against B/B+ gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import score_segment1b_p3_candidate as p3_score


B_THRESHOLDS = {
    "country_gini_max": 0.68,
    "top10_share_max": 0.50,
    "top5_share_max": 0.33,
    "top1_share_max": 0.10,
    "eligible_country_nonzero_share_min": 0.85,
    "southern_hemisphere_share_min": 0.12,
    "nn_improvement_min": 0.20,
}

BPLUS_THRESHOLDS = {
    "country_gini_max": 0.60,
    "top10_share_max": 0.42,
    "top5_share_max": 0.27,
    "top1_share_max": 0.08,
    "eligible_country_nonzero_share_min": 0.92,
    "southern_hemisphere_share_min": 0.18,
    "nn_improvement_min": 0.35,
}


def _grade_checks(cand: dict[str, Any], nn_improvement: float, thresholds: dict[str, float]) -> dict[str, bool]:
    return {
        "country_gini": bool(cand["country_gini"] <= thresholds["country_gini_max"]),
        "top10_share": bool(cand["top10_share"] <= thresholds["top10_share_max"]),
        "top5_share": bool(cand["top5_share"] <= thresholds["top5_share_max"]),
        "top1_share": bool(cand["top1_share"] <= thresholds["top1_share_max"]),
        "eligible_country_nonzero_share": bool(
            cand["eligible_country_nonzero_share"] >= thresholds["eligible_country_nonzero_share_min"]
        ),
        "southern_hemisphere_share": bool(
            cand["southern_hemisphere_share"] >= thresholds["southern_hemisphere_share_min"]
        ),
        "nn_tail_contraction": bool(nn_improvement >= thresholds["nn_improvement_min"]),
    }


def score_p4(
    runs_root: Path,
    baseline_json: Path,
    no_regression_run_id: str,
    candidate_run_id: str,
    output_dir: Path,
    s3_policy_path: Path = p3_score.DEFAULT_S3_POLICY_PATH,
) -> dict[str, Any]:
    baseline_payload = json.loads(baseline_json.read_text(encoding="utf-8"))
    baseline_metrics = baseline_payload["metrics"]
    policy_meta, excluded_countries = p3_score._load_s3_country_policy(s3_policy_path)
    eligible_country_total_baseline = int(baseline_metrics["eligible_country_total"])
    eligible_country_total = (
        max(eligible_country_total_baseline - len(excluded_countries), 0)
        if policy_meta["enabled"]
        else eligible_country_total_baseline
    )
    baseline_nn_ratio = float(baseline_metrics["nn_p99_p50_ratio"])

    no_reg_ctx = p3_score._load_run_context(runs_root, no_regression_run_id)
    candidate_ctx = p3_score._load_run_context(runs_root, candidate_run_id)
    no_reg = p3_score._snapshot(no_reg_ctx, eligible_country_total, excluded_countries)
    candidate = p3_score._snapshot(candidate_ctx, eligible_country_total, excluded_countries)

    cand = candidate["metrics"]
    p3_lock = no_reg["metrics"]
    nn_improvement = (
        float((baseline_nn_ratio - cand["nn_p99_p50_ratio"]) / baseline_nn_ratio)
        if baseline_nn_ratio > 0.0
        else 0.0
    )

    structural_checks = {
        "s6_policy_present": bool("jitter_policy" in candidate["s6_report"]),
        "s6_mode_mixture_v2": str((candidate["s6_report"].get("jitter_policy") or {}).get("mode", ""))
        == "mixture_v2",
        "s8_parity_ok": bool(
            candidate["s8_report"].get("parity_ok", False)
            or (candidate["s8_report"].get("sizes") or {}).get("parity_ok", False)
        ),
        "coordinate_bounds_valid": bool(cand["coordinate_bounds_valid"]),
        "top_country_no_collapse": bool(cand["collapse_sentinel"]["all_clear"]),
    }
    no_regression_checks = {
        "concentration_not_worse_than_p3_lock": bool(
            cand["country_gini"] <= p3_lock["country_gini"] + 1.0e-12
            and cand["top10_share"] <= p3_lock["top10_share"] + 1.0e-12
            and cand["top5_share"] <= p3_lock["top5_share"] + 1.0e-12
            and cand["top1_share"] <= p3_lock["top1_share"] + 1.0e-12
        ),
        "coverage_not_worse_than_p3_lock": bool(
            cand["eligible_country_nonzero_share"] >= p3_lock["eligible_country_nonzero_share"] - 1.0e-12
            and cand["southern_hemisphere_share"] >= p3_lock["southern_hemisphere_share"] - 1.0e-12
        ),
    }

    b_checks = _grade_checks(cand, nn_improvement, B_THRESHOLDS)
    bplus_checks = _grade_checks(cand, nn_improvement, BPLUS_THRESHOLDS)
    b_hard_pass = bool(all(b_checks.values()))
    bplus_hard_pass = bool(all(bplus_checks.values()))
    structural_pass = bool(all(structural_checks.values()))
    no_regression_pass = bool(all(no_regression_checks.values()))

    b_all_pass = bool(b_hard_pass and structural_pass and no_regression_pass)
    bplus_all_pass = bool(bplus_hard_pass and structural_pass and no_regression_pass)

    if b_all_pass:
        status = "GREEN_B" if bplus_all_pass else "AMBER_NEAR_BPLUS"
    else:
        status = "RED_REOPEN_REQUIRED"

    payload = {
        "generated_utc": p3_score._now_utc(),
        "phase": "P4",
        "segment": "1B",
        "status": status,
        "p4_3_required": bool(status == "AMBER_NEAR_BPLUS"),
        "reopen_required": bool(status == "RED_REOPEN_REQUIRED"),
        "country_filter_policy": {
            **policy_meta,
            "eligible_country_total_baseline": eligible_country_total_baseline,
            "eligible_country_total_scored": eligible_country_total,
        },
        "baseline": {
            "baseline_json": str(baseline_json.resolve()),
            "metrics": baseline_metrics,
        },
        "no_regression_authority": no_reg,
        "candidate": candidate,
        "thresholds": {
            "B": B_THRESHOLDS,
            "B_plus": BPLUS_THRESHOLDS,
        },
        "nn_contraction_vs_p0_baseline": {
            "baseline_nn_p99_p50_ratio": baseline_nn_ratio,
            "candidate_nn_p99_p50_ratio": float(cand["nn_p99_p50_ratio"]),
            "improvement_fraction": float(nn_improvement),
            "improvement_percent": float(nn_improvement * 100.0),
        },
        "grade_checks": {
            "B": b_checks,
            "B_plus": bplus_checks,
        },
        "structural_checks": structural_checks,
        "no_regression_checks": no_regression_checks,
        "grade_pass": {
            "B_hard": b_hard_pass,
            "B_plus_hard": bplus_hard_pass,
            "structural": structural_pass,
            "no_regression": no_regression_pass,
            "B_all": b_all_pass,
            "B_plus_all": bplus_all_pass,
        },
        "delta_vs_p3_lock": {
            "country_gini": float(cand["country_gini"] - p3_lock["country_gini"]),
            "top10_share": float(cand["top10_share"] - p3_lock["top10_share"]),
            "top5_share": float(cand["top5_share"] - p3_lock["top5_share"]),
            "top1_share": float(cand["top1_share"] - p3_lock["top1_share"]),
            "eligible_country_nonzero_share": float(
                cand["eligible_country_nonzero_share"] - p3_lock["eligible_country_nonzero_share"]
            ),
            "southern_hemisphere_share": float(
                cand["southern_hemisphere_share"] - p3_lock["southern_hemisphere_share"]
            ),
            "nn_p99_p50_ratio": float(cand["nn_p99_p50_ratio"] - p3_lock["nn_p99_p50_ratio"]),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"segment1b_p4_integrated_{candidate_run_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return {"candidate_path": out_path, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 1B P4 integrated candidate.")
    parser.add_argument(
        "--runs-root",
        default="runs/fix-data-engine/segment_1B",
        help="Runs root containing run-id folders.",
    )
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92.json",
        help="P0 baseline scorecard JSON used for absolute B/B+ gates.",
    )
    parser.add_argument(
        "--no-regression-run-id",
        default="979129e39a89446b942df9a463f09508",
        help="Locked P3 run-id used as no-regression authority.",
    )
    parser.add_argument("--candidate-run-id", required=True, help="P4 integrated candidate run-id.")
    parser.add_argument(
        "--output-dir",
        default="runs/fix-data-engine/segment_1B/reports",
        help="Output directory for P4 score artifacts.",
    )
    parser.add_argument(
        "--s3-policy-path",
        default=str(p3_score.DEFAULT_S3_POLICY_PATH),
        help="Governed S3 requirements policy path for country exclusion handling.",
    )
    args = parser.parse_args()
    result = score_p4(
        runs_root=Path(args.runs_root),
        baseline_json=Path(args.baseline_json),
        no_regression_run_id=args.no_regression_run_id,
        candidate_run_id=args.candidate_run_id,
        output_dir=Path(args.output_dir),
        s3_policy_path=Path(args.s3_policy_path),
    )
    print(str(result["candidate_path"]))


if __name__ == "__main__":
    main()
