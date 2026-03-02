#!/usr/bin/env python3
"""Emit Segment 2A POPT.4 integrated lock artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _find_state_report(run_root: Path, state: str) -> Path:
    state_lower = state.lower()
    matches = list((run_root / "reports/layer1/2A").glob(f"state={state}/**/{state_lower}_run_report.json"))
    if not matches:
        raise FileNotFoundError(f"Missing {state_lower}_run_report.json under {run_root}")
    if len(matches) > 1:
        matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def _load_run_reports(runs_root: Path, run_id: str) -> dict[str, dict[str, Any]]:
    run_root = runs_root / run_id
    return {state: _load_json(_find_state_report(run_root, state)) for state in STATE_ORDER}


def _state_elapsed_map_from_popt0_json(path: Path) -> dict[str, float]:
    payload = _load_json(path)
    rows = payload.get("timing", {}).get("state_table", [])
    return {str(row["state"]): float(row["elapsed_s"]) for row in rows}


def _integrated_status(checks: dict[str, bool]) -> str:
    if all(checks.values()):
        return "GREEN_LOCKED"
    if checks.get("runtime_material", False) and checks.get("structural_all_pass", False):
        return "AMBER_RUNTIME_OK_GOVERNANCE_OPEN"
    return "RED_REOPEN_REQUIRED"


def score_popt4_integrated(
    runs_root: Path,
    candidate_run_id: str,
    baseline_popt0_json: Path,
    no_regression_run_id: str,
    output_dir: Path,
    runtime_improvement_threshold: float = 0.10,
) -> tuple[Path, dict[str, Any]]:
    candidate_reports = _load_run_reports(runs_root, candidate_run_id)
    no_reg_reports = _load_run_reports(runs_root, no_regression_run_id)
    baseline_elapsed = _state_elapsed_map_from_popt0_json(baseline_popt0_json)

    candidate_elapsed = {
        state: float(candidate_reports[state].get("durations", {}).get("wall_ms", 0.0)) / 1000.0
        for state in STATE_ORDER
    }
    no_reg_elapsed = {
        state: float(no_reg_reports[state].get("durations", {}).get("wall_ms", 0.0)) / 1000.0
        for state in STATE_ORDER
    }

    baseline_total = sum(float(baseline_elapsed.get(state, 0.0)) for state in STATE_ORDER)
    candidate_total = sum(candidate_elapsed.values())
    improvement_abs = baseline_total - candidate_total
    improvement_frac = (improvement_abs / baseline_total) if baseline_total > 0.0 else 0.0

    s1_c = candidate_reports["S1"].get("counts", {})
    s1_n = no_reg_reports["S1"].get("counts", {})
    s2_c = candidate_reports["S2"].get("counts", {})
    s2_n = no_reg_reports["S2"].get("counts", {})
    s4_c = candidate_reports["S4"].get("coverage", {})
    s5_c = candidate_reports["S5"]

    structural_checks = {
        "s0_pass": str(candidate_reports["S0"].get("status", "")).lower() == "pass",
        "s1_pass": str(candidate_reports["S1"].get("status", "")).lower() == "pass",
        "s2_pass": str(candidate_reports["S2"].get("status", "")).lower() == "pass",
        "s4_pass": str(candidate_reports["S4"].get("status", "")).lower() == "pass",
        "s5_pass": str(candidate_reports["S5"].get("status", "")).lower() == "pass",
        "s4_missing_tzids_zero": int(s4_c.get("missing_tzids_count", 0)) == 0,
        "s5_digest_matches_flag": bool((s5_c.get("digest") or {}).get("matches_flag", False)),
        "s5_index_root_scoped": bool((s5_c.get("bundle") or {}).get("index_path_root_scoped", False)),
        "s5_index_sorted": bool((s5_c.get("bundle") or {}).get("index_sorted_ascii_lex", False)),
    }

    governance_checks = {
        "s1_row_parity": int(s1_c.get("rows_emitted", -1)) == int(s1_c.get("sites_total", -2)),
        "s2_row_parity": int(s2_c.get("rows_emitted", -1)) == int(s2_c.get("sites_total", -2)),
        "fallback_outside_not_worse": int(s1_c.get("fallback_nearest_outside_threshold", 0))
        <= int(s1_n.get("fallback_nearest_outside_threshold", 0)),
        "fallback_within_not_worse": int(s1_c.get("fallback_nearest_within_threshold", 0))
        <= int(s1_n.get("fallback_nearest_within_threshold", 0)),
        "overrides_total_not_worse": int(s2_c.get("overridden_total", 0))
        <= int(s2_n.get("overridden_total", 0)),
    }

    checks = {
        "runtime_material": bool(improvement_frac >= runtime_improvement_threshold),
        "structural_all_pass": bool(all(structural_checks.values())),
        "governance_no_regression": bool(all(governance_checks.values())),
    }
    status = _integrated_status(checks)

    payload = {
        "generated_utc": _now_utc(),
        "phase": "POPT.4",
        "segment": "2A",
        "status": status,
        "authority": {
            "baseline_popt0_json": str(baseline_popt0_json.resolve()),
            "no_regression_run_id": no_regression_run_id,
            "candidate_run_id": candidate_run_id,
        },
        "runtime": {
            "runtime_improvement_threshold_fraction": runtime_improvement_threshold,
            "baseline_popt0_total_s": baseline_total,
            "candidate_total_s": candidate_total,
            "improvement_s": improvement_abs,
            "improvement_fraction": improvement_frac,
            "improvement_percent": improvement_frac * 100.0,
            "state_elapsed_baseline_s": baseline_elapsed,
            "state_elapsed_candidate_s": candidate_elapsed,
            "state_elapsed_no_regression_s": no_reg_elapsed,
        },
        "checks": checks,
        "structural_checks": structural_checks,
        "governance_checks": governance_checks,
        "candidate_counters": {
            "s1_counts": s1_c,
            "s2_counts": s2_c,
            "s4_coverage": s4_c,
            "s5_bundle": s5_c.get("bundle", {}),
            "s5_digest": s5_c.get("digest", {}),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"segment2a_popt4_integrated_{candidate_run_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return out_path, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 2A POPT.4 integrated lock candidate.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2A")
    parser.add_argument("--candidate-run-id", default="")
    parser.add_argument(
        "--baseline-popt0-json",
        default="runs/fix-data-engine/segment_2A/reports/segment2a_popt0_baseline_c25a2675fbfbacd952b13bb594880e92.json",
    )
    parser.add_argument("--no-regression-run-id", default="dd4ba47ab7b942a4930cbeee85eda331")
    parser.add_argument("--output-dir", default="runs/fix-data-engine/segment_2A/reports")
    parser.add_argument("--runtime-improvement-threshold", type=float, default=0.10)
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    candidate_run_id = args.candidate_run_id.strip() or _resolve_latest_run_id(runs_root)
    out_path, _payload = score_popt4_integrated(
        runs_root=runs_root,
        candidate_run_id=candidate_run_id,
        baseline_popt0_json=Path(args.baseline_popt0_json),
        no_regression_run_id=args.no_regression_run_id,
        output_dir=Path(args.output_dir),
        runtime_improvement_threshold=float(args.runtime_improvement_threshold),
    )
    print(str(out_path))


if __name__ == "__main__":
    main()
