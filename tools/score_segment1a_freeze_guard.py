#!/usr/bin/env python3
"""Score Segment 1A no-regression freeze guard for upstream reopen candidates."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

import score_segment1a_p1_4_lock as p1_score
import score_segment1a_p2_1_baseline as p2_score
import score_segment1a_p3_1_baseline as p3_score


RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")

B_BANDS = {
    "single_site_share": (0.25, 0.45),
    "median_outlets_per_merchant": (6.0, 20.0),
    "top10_outlet_share": (0.35, 0.55),
    "gini_outlets_per_merchant": (0.45, 0.62),
    "home_legal_mismatch_rate": (0.10, 0.25),
    "size_gradient_pp_top_minus_bottom": (5.0, math.inf),
    "multi_country_legal_spread": (0.20, 0.45),
    "candidate_count_median": (5.0, 15.0),
    "candidate_membership_correlation": (0.30, math.inf),
    "realization_ratio_median": (0.10, math.inf),
    "phi_cv": (0.05, 0.20),
    "phi_p95_p05_ratio": (1.25, 2.0),
}

BPLUS_BANDS = {
    "single_site_share": (0.35, 0.55),
    "median_outlets_per_merchant": (8.0, 18.0),
    "top10_outlet_share": (0.38, 0.50),
    "gini_outlets_per_merchant": (0.48, 0.58),
    "home_legal_mismatch_rate": (0.12, 0.20),
    "size_gradient_pp_top_minus_bottom": (8.0, math.inf),
    "multi_country_legal_spread": (0.25, 0.40),
    "candidate_count_median": (7.0, 12.0),
    "candidate_membership_correlation": (0.45, math.inf),
    "realization_ratio_median": (0.20, math.inf),
    "phi_cv": (0.10, 0.30),
    "phi_p95_p05_ratio": (1.50, 3.0),
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_run_id(runs_root: Path, run_id: str | None) -> str:
    if run_id:
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError(f"invalid run_id format: {run_id!r}")
        receipt = runs_root / run_id / "run_receipt.json"
        if not receipt.exists():
            raise FileNotFoundError(f"run receipt not found: {receipt}")
        return run_id

    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"no run_receipt.json under {runs_root}")
    return receipts[-1].parent.name


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(float(value))


def _band_pass(value: Any, lo: float, hi: float) -> bool:
    if not _is_number(value):
        return False
    val = float(value)
    return val >= lo and val <= hi


def _multi_country_legal_spread(run_root: Path, seed: int, manifest_fingerprint: str) -> float:
    paths = sorted(
        (
            run_root
            / "data"
            / "layer1"
            / "1A"
            / "outlet_catalogue"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
        ).glob("part-*.parquet")
    )
    if not paths:
        raise FileNotFoundError(f"outlet_catalogue not found for seed={seed} manifest={manifest_fingerprint}")

    outlet_df = pl.read_parquet(paths).select(["merchant_id", "legal_country_iso"])
    by_merchant = (
        outlet_df.unique()
        .group_by("merchant_id")
        .agg(pl.col("legal_country_iso").n_unique().alias("n_legal_countries"))
    )
    if by_merchant.height == 0:
        return 0.0
    multi = by_merchant.filter(pl.col("n_legal_countries") > 1).height
    return float(multi / by_merchant.height)


def _required_outputs_presence(run_root: Path, parameter_hash: str) -> dict[str, Any]:
    checks = {
        "s3_integerised_counts": sorted(
            run_root.glob(
                f"data/layer1/1A/s3_integerised_counts/parameter_hash={parameter_hash}/part-*.parquet"
            )
        ),
        "s3_site_sequence": sorted(
            run_root.glob(
                f"data/layer1/1A/s3_site_sequence/parameter_hash={parameter_hash}/part-*.parquet"
            )
        ),
        "sparse_flag": sorted(
            run_root.glob(
                f"data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/part-*.parquet"
            )
        ),
        "merchant_abort_log": sorted(
            run_root.glob(
                f"data/layer1/1A/prep/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet"
            )
        )
        or sorted(
            run_root.glob(
                f"data/layer1/1A/merchant_abort_log/parameter_hash={parameter_hash}/part-*.parquet"
            )
        ),
        "hurdle_stationarity_tests": sorted(
            run_root.glob(
                f"data/layer1/1A/hurdle_stationarity_tests/parameter_hash={parameter_hash}/part-*.parquet"
            )
        ),
    }
    counts = {name: len(paths) for name, paths in checks.items()}
    return {"counts": counts, "all_present": all(count > 0 for count in counts.values())}


def _load_authority(cert_json: Path) -> dict[str, Any]:
    if not cert_json.exists():
        raise FileNotFoundError(f"authority certification missing: {cert_json}")
    payload = json.loads(cert_json.read_text(encoding="utf-8"))
    metric_map = {
        str(item["metric"]): item for item in payload.get("target_band_checks", []) if isinstance(item, dict)
    }
    return {"payload": payload, "metric_map": metric_map}


def _candidate_snapshot(
    runs_root: Path,
    run_id: str,
    bootstrap_seed: int,
    bootstrap_samples: int,
) -> dict[str, Any]:
    run_root = runs_root / run_id
    receipt = json.loads((run_root / "run_receipt.json").read_text(encoding="utf-8"))
    seed = int(receipt["seed"])
    parameter_hash = str(receipt["parameter_hash"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])

    p1 = p1_score._load_metric_for_run(runs_root, run_id)
    p2 = p2_score.build_scorecard(runs_root, run_id)
    p3 = p3_score.build_scorecard(
        runs_root,
        run_id,
        bootstrap_seed=bootstrap_seed,
        bootstrap_samples=bootstrap_samples,
    )
    p2g = p2["metrics"]["global"]
    p3g = p3["metrics"]["global"]

    identity_ok = not bool(
        p3["metrics"]["identity_semantics_diagnostics"]["has_unexplained_duplicate_anomalies"]
    )
    outputs = _required_outputs_presence(run_root, parameter_hash)
    spread = _multi_country_legal_spread(run_root, seed, manifest_fingerprint)

    metrics = {
        "single_site_share": float(p1["single_share"]),
        "median_outlets_per_merchant": float(p1["median_outlets_per_merchant"]),
        "top10_outlet_share": float(p1["top10_outlet_share"]),
        "gini_outlets_per_merchant": float(p1["gini_outlets_per_merchant"]),
        "home_legal_mismatch_rate": float(p3g["home_legal_mismatch_rate"]),
        "size_gradient_pp_top_minus_bottom": float(p3g["size_gradient_pp_top_minus_bottom"]),
        "multi_country_legal_spread": float(spread),
        "candidate_count_median": float(p2g["median_C_m"]),
        "candidate_membership_correlation": (
            None
            if p2g["spearman_C_m_R_m"] is None
            else float(p2g["spearman_C_m_R_m"])
        ),
        "realization_ratio_median": float(p2g["median_rho_m"]),
        "phi_cv": float(p1["phi_cv"]),
        "phi_p95_p05_ratio": float(p1["phi_p95_p05_ratio"]),
        "identity_semantics_no_unexplained_duplicate_anomalies": bool(identity_ok),
        "required_outputs_present": bool(outputs["all_present"]),
    }

    checks: list[dict[str, Any]] = []
    for name in (
        "single_site_share",
        "median_outlets_per_merchant",
        "top10_outlet_share",
        "gini_outlets_per_merchant",
        "home_legal_mismatch_rate",
        "size_gradient_pp_top_minus_bottom",
        "multi_country_legal_spread",
        "candidate_count_median",
        "candidate_membership_correlation",
        "realization_ratio_median",
        "phi_cv",
        "phi_p95_p05_ratio",
    ):
        checks.append(
            {
                "metric": name,
                "value": metrics[name],
                "B_pass": _band_pass(metrics[name], *B_BANDS[name]),
                "B_plus_pass": _band_pass(metrics[name], *BPLUS_BANDS[name]),
            }
        )
    checks.extend(
        [
            {
                "metric": "identity_semantics_no_unexplained_duplicate_anomalies",
                "value": metrics["identity_semantics_no_unexplained_duplicate_anomalies"],
                "B_pass": bool(metrics["identity_semantics_no_unexplained_duplicate_anomalies"]),
                "B_plus_pass": bool(metrics["identity_semantics_no_unexplained_duplicate_anomalies"]),
            },
            {
                "metric": "required_outputs_present",
                "value": metrics["required_outputs_present"],
                "B_pass": bool(metrics["required_outputs_present"]),
                "B_plus_pass": bool(metrics["required_outputs_present"]),
            },
        ]
    )
    check_map = {str(item["metric"]): item for item in checks}

    hard_gates = {
        "single_site_tier_exists_materially": metrics["single_site_share"] >= 0.10,
        "candidate_not_near_global_by_default": metrics["candidate_count_median"] <= 15.0,
        "dispersion_heterogeneity_restored": (
            metrics["phi_cv"] >= 0.05 and metrics["phi_p95_p05_ratio"] >= 1.25
        ),
        "required_outputs_emitted": bool(metrics["required_outputs_present"]),
    }
    hard_pass = all(hard_gates.values())
    b_pass_count = sum(1 for item in checks if item["B_pass"])
    bplus_pass_count = sum(1 for item in checks if item["B_plus_pass"])
    total = len(checks)
    b_pass_share = float(b_pass_count / total) if total > 0 else 0.0
    bplus_pass_share = float(bplus_pass_count / total) if total > 0 else 0.0

    concentration_no_major_regression = (
        B_BANDS["top10_outlet_share"][0]
        <= metrics["top10_outlet_share"]
        <= B_BANDS["top10_outlet_share"][1]
        and B_BANDS["gini_outlets_per_merchant"][0]
        <= metrics["gini_outlets_per_merchant"]
        <= B_BANDS["gini_outlets_per_merchant"][1]
    )

    eligible_b = bool(hard_pass and b_pass_share >= 0.70)
    eligible_bplus = bool(hard_pass and bplus_pass_share >= 0.80 and concentration_no_major_regression)
    if eligible_bplus:
        grade = "B_plus"
    elif eligible_b:
        grade = "B"
    else:
        grade = "below_B"

    return {
        "run": {
            "run_id": run_id,
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
        },
        "metrics": metrics,
        "target_band_checks": checks,
        "target_band_check_map": check_map,
        "hard_gates": hard_gates,
        "band_coverage": {
            "total_checks": total,
            "B_pass_count": b_pass_count,
            "B_plus_pass_count": bplus_pass_count,
            "B_pass_share": b_pass_share,
            "B_plus_pass_share": bplus_pass_share,
            "B_threshold": 0.70,
            "B_plus_threshold": 0.80,
            "concentration_no_major_regression": concentration_no_major_regression,
        },
        "grade_decision": {
            "grade": grade,
            "eligible_B": eligible_b,
            "eligible_B_plus": eligible_bplus,
        },
        "p2_global": p2g,
        "p3_global": p3g,
        "p4_required_outputs": outputs,
    }


def score_freeze_guard(
    runs_root: Path,
    run_id: str,
    authority_cert_json: Path,
    out_path: Path,
    bootstrap_seed: int,
    bootstrap_samples: int,
    tolerance_abs: float,
    concentration_max_regression: float,
) -> dict[str, Any]:
    authority = _load_authority(authority_cert_json)
    a_payload = authority["payload"]
    a_metric_map = authority["metric_map"]
    candidate = _candidate_snapshot(
        runs_root=runs_root,
        run_id=run_id,
        bootstrap_seed=bootstrap_seed,
        bootstrap_samples=bootstrap_samples,
    )

    c_metric_map = candidate["target_band_check_map"]
    a_hard = a_payload["hard_gates"]["checks"]
    c_hard = candidate["hard_gates"]

    hard_gate_not_regressed = all(
        (not bool(a_hard.get(name, False))) or bool(c_hard.get(name, False))
        for name in (
            "single_site_tier_exists_materially",
            "candidate_not_near_global_by_default",
            "dispersion_heterogeneity_restored",
            "required_outputs_emitted",
        )
    )

    b_pass_metrics_not_regressed = True
    regressed_metrics: list[str] = []
    for metric, a_item in a_metric_map.items():
        if bool(a_item.get("B_pass", False)):
            cand_pass = bool(c_metric_map.get(metric, {}).get("B_pass", False))
            if not cand_pass:
                b_pass_metrics_not_regressed = False
                regressed_metrics.append(metric)

    a_band = a_payload["band_coverage"]
    c_band = candidate["band_coverage"]
    b_pass_count_not_below_authority = int(c_band["B_pass_count"]) >= int(a_band["B_pass_count"])

    a_surface = a_payload["surface_metrics"]["p1_representative"]
    c_metrics = candidate["metrics"]
    concentration_not_materially_worse_than_authority = bool(
        float(c_metrics["top10_outlet_share"])
        <= float(a_surface["top10_outlet_share"]) + concentration_max_regression
        and float(c_metrics["gini_outlets_per_merchant"])
        <= float(a_surface["gini_outlets_per_merchant"]) + concentration_max_regression
    )

    checks = {
        "grade_not_below_B": bool(candidate["grade_decision"]["eligible_B"]),
        "hard_gates_not_regressed": hard_gate_not_regressed,
        "authority_B_pass_metrics_not_regressed": b_pass_metrics_not_regressed,
        "B_pass_count_not_below_authority": b_pass_count_not_below_authority,
        "concentration_not_materially_worse_than_authority": concentration_not_materially_worse_than_authority,
    }
    all_pass = all(checks.values())

    payload = {
        "generated_utc": _now_utc(),
        "phase": "freeze_guard",
        "segment": "1A",
        "status": "PASS" if all_pass else "FAIL",
        "description": "Fail-closed no-regression guard for Segment 1A upstream reopen candidates.",
        "authority": {
            "certification_json": str(authority_cert_json.resolve()),
            "grade_decision": a_payload["grade_decision"],
            "hard_gates": a_payload["hard_gates"],
            "band_coverage": a_payload["band_coverage"],
            "surface_metrics": a_payload["surface_metrics"],
        },
        "candidate": candidate,
        "guard_checks": checks,
        "regressed_B_metrics": regressed_metrics,
        "tolerance_abs": float(tolerance_abs),
        "concentration_max_regression": float(concentration_max_regression),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        default="runs/fix-data-engine/segment_1A",
        help="Runs root containing Segment 1A run-id folders.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Candidate run-id to score; defaults to latest run under --runs-root.",
    )
    parser.add_argument(
        "--authority-cert-json",
        default="runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json",
        help="Frozen Segment 1A certification authority JSON.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: <runs-root>/reports/segment1a_freeze_guard_<run_id>.json).",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=20260213,
        help="Bootstrap seed forwarded to P3 scorer.",
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=400,
        help="Bootstrap samples forwarded to P3 scorer.",
    )
    parser.add_argument(
        "--tolerance-abs",
        type=float,
        default=1.0e-12,
        help="Absolute tolerance used for concentration no-worse comparison.",
    )
    parser.add_argument(
        "--concentration-max-regression",
        type=float,
        default=0.01,
        help="Allowed absolute regression budget for top10/gini versus authority representative.",
    )
    args = parser.parse_args()

    runs_root = Path(args.runs_root).resolve()
    run_id = _resolve_run_id(runs_root, args.run_id)
    out_path = (
        Path(args.out).resolve()
        if args.out
        else (runs_root / "reports" / f"segment1a_freeze_guard_{run_id}.json")
    )
    payload = score_freeze_guard(
        runs_root=runs_root,
        run_id=run_id,
        authority_cert_json=Path(args.authority_cert_json).resolve(),
        out_path=out_path,
        bootstrap_seed=int(args.bootstrap_seed),
        bootstrap_samples=int(args.bootstrap_samples),
        tolerance_abs=float(args.tolerance_abs),
        concentration_max_regression=float(args.concentration_max_regression),
    )
    print(str(out_path))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "run_id": payload["candidate"]["run"]["run_id"],
                "guard_checks": payload["guard_checks"],
                "regressed_B_metrics": payload["regressed_B_metrics"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
