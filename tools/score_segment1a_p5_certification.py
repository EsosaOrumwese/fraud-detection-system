#!/usr/bin/env python3
"""Build Segment 1A P5 certification report."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


DEFAULT_P2_AUTH_RUN = "9901b537de3a5a146f79365931bd514c"
DEFAULT_P3_AUTH_RUN = "da3e57e73e733b990a5aa3a46705f987"
DEFAULT_P4_AUTH_RUN = "416afa430db3f5bf87180f8514329fe8"
DEFAULT_DET_A = "29bdb537f5aac75aa48479272fc18161"
DEFAULT_DET_B = "a1753dc8ed8fb1703b336bd4a869f361"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_report(runs_root: Path, prefixes: list[str], run_id: str) -> Path:
    for prefix in prefixes:
        path = runs_root / "reports" / f"{prefix}_{run_id}.json"
        if path.exists():
            return path
    joined = ", ".join(prefixes)
    raise FileNotFoundError(
        f"missing report for run_id={run_id}; tried prefixes: {joined}"
    )


def _extract_global(report: dict[str, Any]) -> dict[str, Any]:
    if isinstance(report.get("metrics"), dict):
        metrics = report["metrics"]
        if isinstance(metrics.get("global"), dict):
            return metrics["global"]
    if isinstance(report.get("global"), dict):
        return report["global"]
    raise KeyError("report missing global metrics block")


def _range_ok(value: float, lo: float, hi: float) -> bool:
    return lo <= value <= hi


def _lower_ok(value: float, lo: float) -> bool:
    return value >= lo


def _bool_ok(value: bool) -> bool:
    return bool(value)


def _read_p1_representative(p1_lock_report: Path) -> dict[str, Any]:
    payload = _load_json(p1_lock_report)
    pass2 = payload.get("passes", {}).get("pass2")
    if not isinstance(pass2, list) or not pass2:
        raise ValueError("p1 lock scorecard missing passes.pass2")

    row = None
    for item in pass2:
        if int(item.get("seed", -1)) == 42:
            row = item
            break
    if row is None:
        row = pass2[0]
    return row


def _read_outlet_catalogue(run_root: Path) -> pl.DataFrame:
    paths = sorted(run_root.glob("data/layer1/1A/outlet_catalogue/seed=*/manifest_fingerprint=*/part-*.parquet"))
    if not paths:
        raise FileNotFoundError(f"outlet_catalogue parquet not found under {run_root}")
    return pl.read_parquet(paths)


def _multi_country_legal_spread(outlet_df: pl.DataFrame) -> float:
    if "merchant_id" not in outlet_df.columns or "legal_country_iso" not in outlet_df.columns:
        raise ValueError("outlet_catalogue missing merchant_id/legal_country_iso")

    by_merchant = (
        outlet_df.select(["merchant_id", "legal_country_iso"])
        .unique()
        .group_by("merchant_id")
        .agg(pl.col("legal_country_iso").n_unique().alias("n_legal_countries"))
    )
    total = by_merchant.height
    if total == 0:
        return 0.0
    multi = by_merchant.filter(pl.col("n_legal_countries") > 1).height
    return float(multi / total)


def _required_output_presence(run_root: Path, parameter_hash: str) -> dict[str, Any]:
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
    all_present = all(count > 0 for count in counts.values())
    return {"counts": counts, "all_present": all_present}


@dataclass
class CheckResult:
    metric: str
    value: Any
    b_pass: bool
    b_plus_pass: bool


def _phase_ablation_summary(
    p1: dict[str, Any],
    p2_global: dict[str, Any],
    p3_global: dict[str, Any],
    outputs_all_present: bool,
) -> dict[str, Any]:
    baseline = {
        "single_site_share": 0.0,
        "candidate_median": 38.0,
        "home_legal_mismatch_rate": 0.386,
        "phi_cv": 0.00053,
    }

    return {
        "published_baseline_snapshot": baseline,
        "phase_P1": {
            "single_site_share": float(p1["single_share"]),
            "median_outlets_per_merchant": float(p1["median_outlets_per_merchant"]),
            "top10_outlet_share": float(p1["top10_outlet_share"]),
            "gini_outlets_per_merchant": float(p1["gini_outlets_per_merchant"]),
            "phi_cv": float(p1["phi_cv"]),
            "phi_p95_p05_ratio": float(p1["phi_p95_p05_ratio"]),
        },
        "phase_P2": {
            "candidate_median": float(p2_global["median_C_m"]),
            "candidate_membership_spearman": float(p2_global["spearman_C_m_R_m"]),
            "realization_ratio_median": float(p2_global["median_rho_m"]),
        },
        "phase_P3": {
            "home_legal_mismatch_rate": float(p3_global["home_legal_mismatch_rate"]),
            "size_gradient_pp_top_minus_bottom": float(
                p3_global["size_gradient_pp_top_minus_bottom"]
            ),
        },
        "phase_P4": {
            "required_outputs_present": bool(outputs_all_present),
        },
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    runs_root = args.runs_root.resolve()
    p1_lock = args.p1_lock_report.resolve()

    p1 = _read_p1_representative(p1_lock)

    p2_report_path = _find_report(
        runs_root,
        ["segment1a_p2_1_baseline", "segment1a_p2_regression"],
        args.p2_authority_run,
    )
    p2_report = _load_json(p2_report_path)
    p2_global = _extract_global(p2_report)

    p3_report_path = _find_report(
        runs_root,
        ["segment1a_p3_1_baseline"],
        args.p3_authority_run,
    )
    p3_report = _load_json(p3_report_path)
    p3_global = _extract_global(p3_report)

    p4_run_root = runs_root / args.p4_authority_run
    receipt = _load_json(p4_run_root / "run_receipt.json")
    parameter_hash = str(receipt["parameter_hash"])

    outlet_df = _read_outlet_catalogue(p4_run_root)
    multi_country_legal_spread = _multi_country_legal_spread(outlet_df)

    outputs = _required_output_presence(p4_run_root, parameter_hash)
    global_checks = p3_report.get("metrics", {}).get("global", {}).get("checks", {})
    no_unexplained_duplicate_anomalies = global_checks.get(
        "no_unexplained_duplicate_anomalies"
    )
    if no_unexplained_duplicate_anomalies is None:
        no_unexplained_duplicate_anomalies = (
            p3_report.get("metrics", {})
            .get("identity_semantics", {})
            .get("checks", {})
            .get("no_unexplained_duplicate_anomalies")
        )
    if no_unexplained_duplicate_anomalies is None:
        diag_flag = (
            p3_report.get("metrics", {})
            .get("identity_semantics_diagnostics", {})
            .get("has_unexplained_duplicate_anomalies")
        )
        if diag_flag is not None:
            no_unexplained_duplicate_anomalies = not bool(diag_flag)
    if no_unexplained_duplicate_anomalies is None:
        # Backward compatibility with older top-level key shape.
        no_unexplained_duplicate_anomalies = not bool(
            p3_report.get("identity_semantics", {})
            .get("has_unexplained_duplicate_anomalies", True)
        )
    no_unexplained_duplicate_anomalies = bool(no_unexplained_duplicate_anomalies)

    checks: list[CheckResult] = [
        CheckResult(
            "single_site_share",
            float(p1["single_share"]),
            _range_ok(float(p1["single_share"]), 0.25, 0.45),
            _range_ok(float(p1["single_share"]), 0.35, 0.55),
        ),
        CheckResult(
            "median_outlets_per_merchant",
            float(p1["median_outlets_per_merchant"]),
            _range_ok(float(p1["median_outlets_per_merchant"]), 6.0, 20.0),
            _range_ok(float(p1["median_outlets_per_merchant"]), 8.0, 18.0),
        ),
        CheckResult(
            "top10_outlet_share",
            float(p1["top10_outlet_share"]),
            _range_ok(float(p1["top10_outlet_share"]), 0.35, 0.55),
            _range_ok(float(p1["top10_outlet_share"]), 0.38, 0.50),
        ),
        CheckResult(
            "gini_outlets_per_merchant",
            float(p1["gini_outlets_per_merchant"]),
            _range_ok(float(p1["gini_outlets_per_merchant"]), 0.45, 0.62),
            _range_ok(float(p1["gini_outlets_per_merchant"]), 0.48, 0.58),
        ),
        CheckResult(
            "home_legal_mismatch_rate",
            float(p3_global["home_legal_mismatch_rate"]),
            _range_ok(float(p3_global["home_legal_mismatch_rate"]), 0.10, 0.25),
            _range_ok(float(p3_global["home_legal_mismatch_rate"]), 0.12, 0.20),
        ),
        CheckResult(
            "size_gradient_pp_top_minus_bottom",
            float(p3_global["size_gradient_pp_top_minus_bottom"]),
            _lower_ok(float(p3_global["size_gradient_pp_top_minus_bottom"]), 5.0),
            _lower_ok(float(p3_global["size_gradient_pp_top_minus_bottom"]), 8.0),
        ),
        CheckResult(
            "multi_country_legal_spread",
            float(multi_country_legal_spread),
            _range_ok(float(multi_country_legal_spread), 0.20, 0.45),
            _range_ok(float(multi_country_legal_spread), 0.25, 0.40),
        ),
        CheckResult(
            "candidate_count_median",
            float(p2_global["median_C_m"]),
            _range_ok(float(p2_global["median_C_m"]), 5.0, 15.0),
            _range_ok(float(p2_global["median_C_m"]), 7.0, 12.0),
        ),
        CheckResult(
            "candidate_membership_correlation",
            float(p2_global["spearman_C_m_R_m"]),
            _lower_ok(float(p2_global["spearman_C_m_R_m"]), 0.30),
            _lower_ok(float(p2_global["spearman_C_m_R_m"]), 0.45),
        ),
        CheckResult(
            "realization_ratio_median",
            float(p2_global["median_rho_m"]),
            _lower_ok(float(p2_global["median_rho_m"]), 0.10),
            _lower_ok(float(p2_global["median_rho_m"]), 0.20),
        ),
        CheckResult(
            "phi_cv",
            float(p1["phi_cv"]),
            _range_ok(float(p1["phi_cv"]), 0.05, 0.20),
            _range_ok(float(p1["phi_cv"]), 0.10, 0.30),
        ),
        CheckResult(
            "phi_p95_p05_ratio",
            float(p1["phi_p95_p05_ratio"]),
            _range_ok(float(p1["phi_p95_p05_ratio"]), 1.25, 2.0),
            _range_ok(float(p1["phi_p95_p05_ratio"]), 1.5, 3.0),
        ),
        CheckResult(
            "identity_semantics_no_unexplained_duplicate_anomalies",
            bool(no_unexplained_duplicate_anomalies),
            _bool_ok(no_unexplained_duplicate_anomalies),
            _bool_ok(no_unexplained_duplicate_anomalies),
        ),
        CheckResult(
            "required_outputs_present",
            bool(outputs["all_present"]),
            _bool_ok(outputs["all_present"]),
            _bool_ok(outputs["all_present"]),
        ),
    ]

    b_pass = sum(1 for c in checks if c.b_pass)
    b_plus_pass = sum(1 for c in checks if c.b_plus_pass)
    total = len(checks)

    hard_gates = {
        "single_site_tier_exists_materially": float(p1["single_share"]) >= 0.10,
        "candidate_not_near_global_by_default": float(p2_global["median_C_m"]) <= 15.0,
        "dispersion_heterogeneity_restored": (
            float(p1["phi_cv"]) >= 0.05
            and float(p1["phi_p95_p05_ratio"]) >= 1.25
        ),
        "required_outputs_emitted": bool(outputs["all_present"]),
    }
    hard_gates_pass = all(hard_gates.values())

    concentration_no_major_regression = (
        _range_ok(float(p1["top10_outlet_share"]), 0.35, 0.55)
        and _range_ok(float(p1["gini_outlets_per_merchant"]), 0.45, 0.62)
    )

    b_coverage = b_pass / total
    b_plus_coverage = b_plus_pass / total

    if not hard_gates_pass:
        grade = "below_B"
    elif b_plus_coverage >= 0.80 and concentration_no_major_regression:
        grade = "B_plus"
    elif b_coverage >= 0.70:
        grade = "B"
    else:
        grade = "below_B"

    determinism = {
        "run_a": args.determinism_run_a,
        "run_b": args.determinism_run_b,
    }

    try:
        p2a = _extract_global(
            _load_json(
                _find_report(
                    runs_root,
                    ["segment1a_p2_1_baseline", "segment1a_p2_regression"],
                    args.determinism_run_a,
                )
            )
        )
        p2b = _extract_global(
            _load_json(
                _find_report(
                    runs_root,
                    ["segment1a_p2_1_baseline", "segment1a_p2_regression"],
                    args.determinism_run_b,
                )
            )
        )
        p3a = _extract_global(
            _load_json(
                _find_report(
                    runs_root,
                    ["segment1a_p3_1_baseline"],
                    args.determinism_run_a,
                )
            )
        )
        p3b = _extract_global(
            _load_json(
                _find_report(
                    runs_root,
                    ["segment1a_p3_1_baseline"],
                    args.determinism_run_b,
                )
            )
        )

        determinism["p2_global_equal"] = (
            p2a.get("median_C_m") == p2b.get("median_C_m")
            and p2a.get("spearman_C_m_R_m") == p2b.get("spearman_C_m_R_m")
            and p2a.get("median_rho_m") == p2b.get("median_rho_m")
        )
        determinism["p3_global_equal"] = (
            p3a.get("rows") == p3b.get("rows")
            and p3a.get("merchants") == p3b.get("merchants")
            and p3a.get("home_legal_mismatch_rate")
            == p3b.get("home_legal_mismatch_rate")
            and p3a.get("size_gradient_pp_top_minus_bottom")
            == p3b.get("size_gradient_pp_top_minus_bottom")
        )
    except Exception as exc:  # pragma: no cover - evidence attachment is best-effort
        determinism["error"] = str(exc)

    alt_seed = None
    if args.alt_seed_run:
        p2_alt = _extract_global(
            _load_json(
                _find_report(
                    runs_root,
                    ["segment1a_p2_1_baseline", "segment1a_p2_regression"],
                    args.alt_seed_run,
                )
            )
        )
        p3_alt = _extract_global(
            _load_json(
                _find_report(
                    runs_root,
                    ["segment1a_p3_1_baseline"],
                    args.alt_seed_run,
                )
            )
        )
        alt_seed = {
            "run_id": args.alt_seed_run,
            "p2": {
                "median_C_m": p2_alt.get("median_C_m"),
                "spearman_C_m_R_m": p2_alt.get("spearman_C_m_R_m"),
                "median_rho_m": p2_alt.get("median_rho_m"),
                "core_checks_pass": p2_alt.get("core_checks_pass"),
                "pathology_checks_pass": p2_alt.get("pathology_checks_pass"),
            },
            "p3": {
                "home_legal_mismatch_rate": p3_alt.get("home_legal_mismatch_rate"),
                "size_gradient_pp_top_minus_bottom": p3_alt.get(
                    "size_gradient_pp_top_minus_bottom"
                ),
                "mismatch_B_plus": _range_ok(
                    float(p3_alt.get("home_legal_mismatch_rate", 0.0)), 0.12, 0.20
                ),
                "gradient_B_plus": _lower_ok(
                    float(p3_alt.get("size_gradient_pp_top_minus_bottom", 0.0)), 8.0
                ),
            },
        }

    report = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wave": "P5",
        "description": "Segment 1A certification-grade scorecard (hard gates + B/B+ band coverage).",
        "authority_runs": {
            "p1_lock_report": str(p1_lock),
            "p2_authority_run": args.p2_authority_run,
            "p3_authority_run": args.p3_authority_run,
            "p4_authority_run": args.p4_authority_run,
            "determinism_pair": [args.determinism_run_a, args.determinism_run_b],
            "alternate_seed_run": args.alt_seed_run,
        },
        "hard_gates": {
            "checks": hard_gates,
            "all_pass": hard_gates_pass,
        },
        "target_band_checks": [
            {
                "metric": c.metric,
                "value": c.value,
                "B_pass": c.b_pass,
                "B_plus_pass": c.b_plus_pass,
            }
            for c in checks
        ],
        "band_coverage": {
            "total_checks": total,
            "B_pass_count": b_pass,
            "B_plus_pass_count": b_plus_pass,
            "B_pass_share": b_coverage,
            "B_plus_pass_share": b_plus_coverage,
            "B_threshold": 0.70,
            "B_plus_threshold": 0.80,
            "concentration_no_major_regression": concentration_no_major_regression,
        },
        "grade_decision": {
            "grade": grade,
            "eligible_B": hard_gates_pass and b_coverage >= 0.70,
            "eligible_B_plus": (
                hard_gates_pass
                and b_plus_coverage >= 0.80
                and concentration_no_major_regression
            ),
            "veto_notes": [] if hard_gates_pass else ["hard_gate_failure_caps_grade"],
        },
        "surface_metrics": {
            "p1_representative": {
                "run_id": p1.get("run_id"),
                "seed": p1.get("seed"),
                "single_share": p1.get("single_share"),
                "median_outlets_per_merchant": p1.get("median_outlets_per_merchant"),
                "top10_outlet_share": p1.get("top10_outlet_share"),
                "gini_outlets_per_merchant": p1.get("gini_outlets_per_merchant"),
                "phi_cv": p1.get("phi_cv"),
                "phi_p95_p05_ratio": p1.get("phi_p95_p05_ratio"),
            },
            "p2_authority": p2_global,
            "p3_authority": p3_global,
            "p4_required_outputs": outputs,
            "cross_border_topology": {
                "multi_country_legal_spread": multi_country_legal_spread
            },
            "identity_semantics": {
                "no_unexplained_duplicate_anomalies": no_unexplained_duplicate_anomalies
            },
        },
        "evidence": {
            "determinism": determinism,
            "ablation": _phase_ablation_summary(
                p1=p1,
                p2_global=p2_global,
                p3_global=p3_global,
                outputs_all_present=bool(outputs["all_present"]),
            ),
            "alternate_seed": alt_seed,
        },
    }

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Segment 1A P5 certification report"
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        required=True,
        help="Run root for Segment 1A (e.g., runs/fix-data-engine/segment_1A)",
    )
    parser.add_argument(
        "--p1-lock-report",
        type=Path,
        default=Path("runs/fix-data-engine/segment_1A/reports/p1_4_lock_scorecard.json"),
        help="Path to p1_4 lock scorecard JSON",
    )
    parser.add_argument(
        "--p2-authority-run",
        default=DEFAULT_P2_AUTH_RUN,
        help="Run id for P2 authority score",
    )
    parser.add_argument(
        "--p3-authority-run",
        default=DEFAULT_P3_AUTH_RUN,
        help="Run id for P3 authority score",
    )
    parser.add_argument(
        "--p4-authority-run",
        default=DEFAULT_P4_AUTH_RUN,
        help="Run id for P4 operational authority",
    )
    parser.add_argument(
        "--determinism-run-a",
        default=DEFAULT_DET_A,
        help="Run id A for same-seed determinism evidence",
    )
    parser.add_argument(
        "--determinism-run-b",
        default=DEFAULT_DET_B,
        help="Run id B for same-seed determinism evidence",
    )
    parser.add_argument(
        "--alt-seed-run",
        default=None,
        help="Run id for alternate-seed sensitivity evidence",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.out.as_posix()}")
    print(json.dumps(report["grade_decision"], indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
