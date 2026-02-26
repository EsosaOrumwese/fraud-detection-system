#!/usr/bin/env python3
"""Score Segment 6B P5 integrated certification and freeze decision."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REQUIRED_SEEDS_DEFAULT = (42, 7, 101, 202)
HARD_GATES = (
    "T1",
    "T2",
    "T3",
    "T4",
    "T5",
    "T6",
    "T7",
    "T8",
    "T9",
    "T10",
    "T11",
    "T12",
    "T13",
    "T14",
    "T15",
    "T16",
    "T21",
    "T22",
)
STRETCH_GATES = ("T17", "T18", "T19", "T20")

CV_FLOORS = {
    "t1_legit_share": 1.0e-2,
    "t2_truth_mean": 1.0e-3,
    "t5_cramers_v": 1.0e-3,
    "t6_effect_size": 1.0e-3,
    "t7_spread": 1.0e-3,
    "t9_fixed_spike_share": 1.0e-4,
    "t11_distinct_amount_values": 10.0,
    "t12_amount_p99_p50": 1.0e-2,
    "t13_top8_share": 1.0e-3,
    "t14_latency_p50": 1.0e-2,
    "t15_latency_p99": 1.0e-2,
    "t16_zero_latency_share": 1.0e-3,
    "t17_campaign_count": 1.0,
    "t17_class_v": 1.0e-3,
    "t18_tz_corridor_v": 1.0e-3,
    "t18_median_tz_per_campaign": 1.0,
    "t19_singleton_session_share": 1.0e-3,
    "t20_richness_score": 1.0e-3,
    "t21_coverage_ratio": 1.0e-3,
    "t22_effective_collision_count": 1.0,
}


@dataclass(frozen=True)
class RunContext:
    seed: int
    run_id: str
    run_root: Path
    receipt_mtime_ns: int


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_seed_list(text: str) -> list[int]:
    values: list[int] = []
    for token in str(text).split(","):
        token = token.strip()
        if not token:
            continue
        values.append(int(token))
    if not values:
        raise ValueError("required seed list cannot be empty")
    return values


def _parse_seed_run(raw: str) -> tuple[int, str]:
    if ":" not in raw:
        raise ValueError(f"Invalid --seed-run '{raw}', expected '<seed>:<run_id>'")
    left, right = raw.split(":", 1)
    seed = int(left.strip())
    run_id = right.strip()
    if not run_id:
        raise ValueError(f"Invalid --seed-run '{raw}', run_id is empty")
    return seed, run_id


def _load_contexts(runs_root: Path) -> list[RunContext]:
    contexts: list[RunContext] = []
    for receipt in runs_root.glob("*/run_receipt.json"):
        try:
            payload = _load_json(receipt)
            run_id = str(payload["run_id"])
            seed = int(payload["seed"])
            contexts.append(
                RunContext(
                    seed=seed,
                    run_id=run_id,
                    run_root=receipt.parent,
                    receipt_mtime_ns=receipt.stat().st_mtime_ns,
                )
            )
        except Exception:
            continue
    contexts.sort(key=lambda ctx: ctx.receipt_mtime_ns, reverse=True)
    return contexts


def _gateboard_path(reports_root: Path, run_id: str) -> Path:
    return reports_root / f"segment6b_p0_realism_gateboard_{run_id}.json"


def _select_seed_map(
    runs_root: Path,
    reports_root: Path,
    required_seeds: list[int],
    explicit_seed_map: dict[int, str],
) -> tuple[dict[int, RunContext], list[int]]:
    contexts = _load_contexts(runs_root)
    by_run = {ctx.run_id: ctx for ctx in contexts}
    selected: dict[int, RunContext] = {}
    missing: list[int] = []

    for seed in required_seeds:
        explicit = explicit_seed_map.get(seed)
        if explicit:
            ctx = by_run.get(explicit)
            if ctx is None or ctx.seed != seed or not _gateboard_path(reports_root, ctx.run_id).exists():
                missing.append(seed)
                continue
            selected[seed] = ctx
            continue

        candidate = None
        for ctx in contexts:
            if ctx.seed != seed:
                continue
            if not _gateboard_path(reports_root, ctx.run_id).exists():
                continue
            candidate = ctx
            break
        if candidate is None:
            missing.append(seed)
            continue
        selected[seed] = candidate

    return selected, missing


def _cv(values: list[float], floor: float) -> tuple[float, float]:
    if not values:
        return float("inf"), float("nan")
    if len(values) == 1:
        return 0.0, max(abs(values[0]), floor)
    mu = mean(values)
    sigma = pstdev(values)
    denom = max(abs(mu), float(floor))
    if denom < 1.0e-12:
        return (0.0 if sigma < 1.0e-12 else float("inf")), denom
    return abs(sigma / denom), denom


def _extract_metric_vector(gates: dict[str, Any]) -> dict[str, float]:
    def gate_value(key: str) -> Any:
        return (gates.get(key) or {}).get("value")

    t17 = gate_value("T17") or {}
    t18 = gate_value("T18") or {}
    t20 = gate_value("T20") or {}
    t21 = gate_value("T21") or {}
    t22 = gate_value("T22") or {}

    vector: dict[str, float | None] = {
        "t1_legit_share": _safe_float(gate_value("T1")),
        "t2_truth_mean": _safe_float(gate_value("T2")),
        "t5_cramers_v": _safe_float(gate_value("T5")),
        "t6_effect_size": _safe_float(gate_value("T6")),
        "t7_spread": _safe_float(gate_value("T7")),
        "t9_fixed_spike_share": _safe_float(gate_value("T9")),
        "t11_distinct_amount_values": _safe_float(gate_value("T11")),
        "t12_amount_p99_p50": _safe_float(gate_value("T12")),
        "t13_top8_share": _safe_float(gate_value("T13")),
        "t14_latency_p50": _safe_float(gate_value("T14")),
        "t15_latency_p99": _safe_float(gate_value("T15")),
        "t16_zero_latency_share": _safe_float(gate_value("T16")),
        "t17_campaign_count": _safe_float((t17 or {}).get("campaign_count")),
        "t17_class_v": _safe_float((t17 or {}).get("class_v")),
        "t18_tz_corridor_v": _safe_float((t18 or {}).get("tz_corridor_v")),
        "t18_median_tz_per_campaign": _safe_float((t18 or {}).get("median_tz_per_campaign")),
        "t19_singleton_session_share": _safe_float(gate_value("T19")),
        "t20_richness_score": _safe_float((t20 or {}).get("richness_score")),
        "t21_coverage_ratio": _safe_float((t21 or {}).get("coverage_ratio")),
        "t22_effective_collision_count": _safe_float((t22 or {}).get("effective_collision_count")),
    }

    missing = [k for k, v in vector.items() if v is None]
    if missing:
        raise ValueError(f"Missing metric values in gateboard vector: {missing}")
    return {k: float(v) for k, v in vector.items() if v is not None}


def _required_check_failures(s5_report: dict[str, Any]) -> list[str]:
    checks = list(s5_report.get("checks") or [])
    failures: list[str] = []
    for row in checks:
        severity = str((row or {}).get("severity") or "").upper()
        if severity != "REQUIRED":
            continue
        result = str((row or {}).get("result") or "").upper()
        if result != "PASS":
            failures.append(str((row or {}).get("check_id") or "UNKNOWN_CHECK"))
    return sorted(failures)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_6B")
    parser.add_argument("--reports-root", default="runs/fix-data-engine/segment_6B/reports")
    parser.add_argument("--required-seeds", default="42,7,101,202")
    parser.add_argument("--seed-run", action="append", default=[], help="Map as '<seed>:<run_id>' (repeatable).")
    parser.add_argument("--cv-threshold-b", type=float, default=0.25)
    parser.add_argument("--cv-threshold-bplus", type=float, default=0.15)
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    reports_root = Path(args.reports_root)
    reports_root.mkdir(parents=True, exist_ok=True)

    required_seeds = _parse_seed_list(args.required_seeds)
    explicit_seed_map = dict(_parse_seed_run(raw) for raw in args.seed_run)
    selected, missing_required = _select_seed_map(runs_root, reports_root, required_seeds, explicit_seed_map)

    blocker_register: list[dict[str, Any]] = []
    if missing_required:
        blocker_register.append(
            {
                "id": "P5-B1",
                "severity": "BLOCKER",
                "issue": "missing_required_seeds",
                "details": {"missing_seeds": missing_required},
            }
        )

    seed_rows: list[dict[str, Any]] = []
    per_metric_values: dict[str, list[float]] = {k: [] for k in CV_FLOORS.keys()}

    for seed in required_seeds:
        ctx = selected.get(seed)
        if ctx is None:
            continue

        run_root = ctx.run_root
        receipt = _load_json(run_root / "run_receipt.json")
        receipt_seed = int(receipt.get("seed"))
        if receipt_seed != seed:
            blocker_register.append(
                {
                    "id": "P5-B2",
                    "severity": "BLOCKER",
                    "issue": "seed_receipt_mismatch",
                    "details": {"seed": seed, "run_id": ctx.run_id, "receipt_seed": receipt_seed},
                }
            )
            continue

        gateboard_path = _gateboard_path(reports_root, ctx.run_id)
        gateboard = _load_json(gateboard_path)
        gates = gateboard.get("gates") or {}
        summary = gateboard.get("summary") or {}

        hard_fail_b = [g for g in HARD_GATES if not bool((gates.get(g) or {}).get("b_pass"))]
        hard_fail_bplus = [g for g in HARD_GATES if not bool((gates.get(g) or {}).get("bplus_pass"))]
        stretch_fail_b = [g for g in STRETCH_GATES if not bool((gates.get(g) or {}).get("b_pass"))]
        stretch_fail_bplus = [g for g in STRETCH_GATES if not bool((gates.get(g) or {}).get("bplus_pass"))]

        manifest = str(receipt.get("manifest_fingerprint") or "")
        s5_path = (
            run_root
            / "data/layer3/6B/validation"
            / f"manifest_fingerprint={manifest}"
            / "s5_validation_report_6B.json"
        )
        required_check_failures: list[str] = []
        s5_status = "MISSING"
        if s5_path.exists():
            s5_payload = _load_json(s5_path)
            s5_status = str(s5_payload.get("overall_status") or "")
            required_check_failures = _required_check_failures(s5_payload)
        else:
            required_check_failures = ["MISSING_S5_REPORT"]

        s5_required_pass = len(required_check_failures) == 0
        if not s5_required_pass:
            blocker_register.append(
                {
                    "id": "P5-B3",
                    "severity": "BLOCKER",
                    "issue": "s5_required_checks_failed",
                    "details": {
                        "seed": seed,
                        "run_id": ctx.run_id,
                        "required_check_failures": required_check_failures,
                    },
                }
            )

        vector = _extract_metric_vector(gates)
        for metric, value in vector.items():
            per_metric_values[metric].append(float(value))

        seed_rows.append(
            {
                "seed": seed,
                "run_id": ctx.run_id,
                "overall_verdict": str(summary.get("overall_verdict") or ""),
                "phase_decision": str(summary.get("phase_decision") or ""),
                "hard_failures_b": hard_fail_b,
                "hard_failures_bplus": hard_fail_bplus,
                "stretch_failures_b": stretch_fail_b,
                "stretch_failures_bplus": stretch_fail_bplus,
                "s5_overall_status": s5_status,
                "s5_required_check_failures": required_check_failures,
                "gateboard_path": str(gateboard_path),
                "metric_vector": vector,
            }
        )

    cv_rows: list[dict[str, Any]] = []
    finite_cvs: list[float] = []
    for metric in sorted(CV_FLOORS.keys()):
        vals = per_metric_values.get(metric) or []
        cv, denom = _cv(vals, CV_FLOORS[metric])
        finite = math.isfinite(cv)
        if finite:
            finite_cvs.append(float(cv))
        cv_rows.append(
            {
                "metric": metric,
                "seed_values": vals,
                "cv": cv if finite else None,
                "cv_denom": denom,
                "cv_floor": CV_FLOORS[metric],
            }
        )

    cv_overall = max(finite_cvs) if finite_cvs else float("inf")
    cv_pass_b = bool(math.isfinite(cv_overall) and cv_overall <= float(args.cv_threshold_b))
    cv_pass_bplus = bool(math.isfinite(cv_overall) and cv_overall <= float(args.cv_threshold_bplus))
    if not cv_pass_b:
        blocker_register.append(
            {
                "id": "P5-B4",
                "severity": "BLOCKER",
                "issue": "cross_seed_stability_fail",
                "details": {
                    "cv_overall": (cv_overall if math.isfinite(cv_overall) else None),
                    "threshold_b": float(args.cv_threshold_b),
                    "threshold_bplus": float(args.cv_threshold_bplus),
                },
            }
        )

    all_seeds_present = len(missing_required) == 0 and len(seed_rows) == len(required_seeds)
    all_seed_pass_b = all(
        (len(row["hard_failures_b"]) == 0)
        and (len(row["stretch_failures_b"]) == 0)
        and (len(row["s5_required_check_failures"]) == 0)
        for row in seed_rows
    )
    all_seed_pass_bplus = all(
        (len(row["hard_failures_bplus"]) == 0)
        and (len(row["stretch_failures_bplus"]) == 0)
        and (len(row["s5_required_check_failures"]) == 0)
        for row in seed_rows
    )

    if all_seeds_present and all_seed_pass_bplus and cv_pass_bplus:
        decision = "PASS_BPLUS_ROBUST"
    elif all_seeds_present and all_seed_pass_b and cv_pass_b:
        decision = "PASS_B"
    else:
        decision = "HOLD_REMEDIATE"

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    summary_path = reports_root / f"segment6b_p5_validation_summary_{stamp}.json"
    csv_path = reports_root / f"segment6b_p5_seed_comparison_{stamp}.csv"
    md_path = reports_root / f"segment6b_p5_regression_report_{stamp}.md"
    decision_path = reports_root / f"segment6b_p5_gate_decision_{stamp}.json"

    summary_payload = {
        "generated_utc": _now_utc(),
        "phase": "P5",
        "segment": "6B",
        "required_seeds": required_seeds,
        "selected_seed_run_map": {str(row["seed"]): str(row["run_id"]) for row in seed_rows},
        "seed_rows": seed_rows,
        "stability": {
            "metrics": cv_rows,
            "cv_overall": cv_overall if math.isfinite(cv_overall) else None,
            "threshold_b": float(args.cv_threshold_b),
            "threshold_bplus": float(args.cv_threshold_bplus),
            "pass_b": cv_pass_b,
            "pass_bplus": cv_pass_bplus,
        },
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "seed",
                "run_id",
                "overall_verdict",
                "hard_failures_b",
                "hard_failures_bplus",
                "stretch_failures_b",
                "stretch_failures_bplus",
                "s5_status",
                "s5_required_check_failures",
                "t19_singleton_session_share",
                "t20_richness_score",
                "t17_class_v",
                "t18_tz_corridor_v",
            ]
        )
        for row in seed_rows:
            vec = row["metric_vector"]
            writer.writerow(
                [
                    row["seed"],
                    row["run_id"],
                    row["overall_verdict"],
                    "|".join(row["hard_failures_b"]),
                    "|".join(row["hard_failures_bplus"]),
                    "|".join(row["stretch_failures_b"]),
                    "|".join(row["stretch_failures_bplus"]),
                    row["s5_overall_status"],
                    "|".join(row["s5_required_check_failures"]),
                    vec.get("t19_singleton_session_share"),
                    vec.get("t20_richness_score"),
                    vec.get("t17_class_v"),
                    vec.get("t18_tz_corridor_v"),
                ]
            )

    md_lines = [
        "# Segment 6B P5 Regression Report",
        "",
        f"- Generated UTC: `{_now_utc()}`",
        f"- Decision: `{decision}`",
        f"- Required seeds: `{required_seeds}`",
        f"- Missing required seeds: `{missing_required}`",
        f"- CV overall: `{cv_overall if math.isfinite(cv_overall) else 'inf'}`",
        f"- CV pass B / B+: `{cv_pass_b}` / `{cv_pass_bplus}`",
        "",
        "## Seed Summary",
        "| Seed | Run ID | Verdict | Hard B Fails | Stretch B Fails | S5 Required Fails |",
        "|---:|---|---|---|---|---|",
    ]
    for row in seed_rows:
        md_lines.append(
            f"| {row['seed']} | `{row['run_id']}` | `{row['overall_verdict']}` | "
            f"`{row['hard_failures_b']}` | `{row['stretch_failures_b']}` | "
            f"`{row['s5_required_check_failures']}` |"
        )
    md_lines.extend(
        [
            "",
            "## Blocker Register",
            *(["- none"] if not blocker_register else [f"- `{json.dumps(item, sort_keys=True)}`" for item in blocker_register]),
            "",
            "## Artifact Paths",
            f"- validation_summary: `{summary_path}`",
            f"- seed_comparison: `{csv_path}`",
            f"- regression_report: `{md_path}`",
            f"- gate_decision: `{decision_path}`",
        ]
    )
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    decision_payload = {
        "generated_utc": _now_utc(),
        "phase": "P5",
        "segment": "6B",
        "decision": decision,
        "required_seeds": required_seeds,
        "selected_seed_run_map": {str(row["seed"]): str(row["run_id"]) for row in seed_rows},
        "all_seeds_present": all_seeds_present,
        "all_seed_pass_b": all_seed_pass_b,
        "all_seed_pass_bplus": all_seed_pass_bplus,
        "stability": {
            "cv_overall": cv_overall if math.isfinite(cv_overall) else None,
            "pass_b": cv_pass_b,
            "pass_bplus": cv_pass_bplus,
        },
        "blocker_register": blocker_register,
        "artifacts": {
            "validation_summary": str(summary_path),
            "seed_comparison": str(csv_path),
            "regression_report": str(md_path),
        },
    }
    decision_path.write_text(json.dumps(decision_payload, indent=2), encoding="utf-8")

    print(f"[segment6b-p5] validation_summary={summary_path}")
    print(f"[segment6b-p5] seed_comparison={csv_path}")
    print(f"[segment6b-p5] regression_report={md_path}")
    print(f"[segment6b-p5] gate_decision={decision_path}")
    print(f"[segment6b-p5] decision={decision}")


if __name__ == "__main__":
    main()
