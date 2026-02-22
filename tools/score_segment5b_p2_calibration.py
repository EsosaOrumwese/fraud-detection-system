#!/usr/bin/env python3
"""Emit Segment 5B P2 calibration gateboard and decision artifact."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"
FROZEN_VETO_GATES = ["T1", "T2", "T3", "T4", "T5", "T11", "T12"]
PRIMARY_GATES = ["T6", "T7"]
CONTEXT_GATES = ["T8", "T9"]


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _find_latest_segment_state_runs(run_root: Path) -> Path:
    candidates = sorted(
        run_root.glob("reports/layer2/segment_state_runs/segment=5B/utc_day=*/segment_state_runs.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"Missing 5B segment_state_runs under {run_root}")
    return candidates[-1]


def _latest_state_row(records: list[dict[str, Any]], state: str) -> dict[str, Any]:
    rows = [r for r in records if str(r.get("state")) == state]
    if not rows:
        raise ValueError(f"No rows found for {state}")
    return sorted(rows, key=lambda r: (str(r.get("finished_at_utc") or ""), str(r.get("started_at_utc") or "")))[-1]


def _md_table(items: list[tuple[str, str, str]]) -> list[str]:
    lines = ["| Axis | Value | Status |", "|---|---:|:---|"]
    for axis, value, status in items:
        lines.append(f"| {axis} | {value} | {status} |")
    return lines


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100.0:.4f}%"


def _band_status(value: float | None, lo: float, hi: float) -> str:
    if value is None:
        return "FAIL"
    return "PASS" if (lo <= value <= hi) else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5B P2 calibration posture.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument(
        "--p1-gateboard-path",
        default="",
        help="Optional path to P1 gateboard for current candidate. Defaults to out_root/segment5b_p1_realism_gateboard_<run_id>.json",
    )
    parser.add_argument(
        "--baseline-p1-gateboard-path",
        default="",
        help="Optional path to baseline P1 gateboard for delta reporting.",
    )
    parser.add_argument("--candidate-label", default="current")
    parser.add_argument("--suffix", default="")
    parser.add_argument("--runtime-budget-seconds", type=float, default=540.0)
    parser.add_argument("--runtime-regression-veto-fraction", type=float, default=0.20)
    parser.add_argument("--baseline-runtime-seconds", type=float, default=0.0)
    args = parser.parse_args()

    run_id = args.run_id.strip() or RUN_ID_DEFAULT
    runs_root = Path(args.runs_root)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    if args.p1_gateboard_path:
        p1_path = Path(args.p1_gateboard_path)
    else:
        p1_path = out_root / f"segment5b_p1_realism_gateboard_{run_id}.json"
    if not p1_path.exists():
        raise FileNotFoundError(f"Missing P1 gateboard: {p1_path}")
    p1 = _load_json(p1_path)
    gates = p1.get("gates") or {}

    missing = [gid for gid in (FROZEN_VETO_GATES + PRIMARY_GATES + CONTEXT_GATES) if gid not in gates]
    if missing:
        raise ValueError(f"P1 gateboard missing expected gates: {missing}")

    baseline_gates = None
    baseline_path = None
    if args.baseline_p1_gateboard_path:
        baseline_path = Path(args.baseline_p1_gateboard_path)
        if baseline_path.exists():
            baseline_gates = (_load_json(baseline_path) or {}).get("gates")

    state_runs_path = _find_latest_segment_state_runs(run_root)
    state_rows = _load_jsonl(state_runs_path)
    s4 = _latest_state_row(state_rows, "S4")
    s5 = _latest_state_row(state_rows, "S5")
    s4_seconds = float(((s4.get("durations") or {}).get("wall_ms") or 0) / 1000.0)
    s5_seconds = float(((s5.get("durations") or {}).get("wall_ms") or 0) / 1000.0)
    lane_seconds = s4_seconds + s5_seconds
    runtime_budget_pass = lane_seconds <= float(args.runtime_budget_seconds)

    baseline_runtime = float(args.baseline_runtime_seconds)
    runtime_regression = ((lane_seconds - baseline_runtime) / baseline_runtime) if baseline_runtime > 0 else 0.0
    runtime_regression_veto = baseline_runtime > 0 and runtime_regression > float(args.runtime_regression_veto_fraction)

    frozen_failures = [gid for gid in FROZEN_VETO_GATES if not bool((gates.get(gid) or {}).get("b_pass"))]
    primary_failures = [gid for gid in PRIMARY_GATES if not bool((gates.get(gid) or {}).get("b_pass"))]
    primary_bplus_failures = [gid for gid in PRIMARY_GATES if not bool((gates.get(gid) or {}).get("bplus_pass"))]
    context_failures = [gid for gid in CONTEXT_GATES if not bool((gates.get(gid) or {}).get("b_pass"))]

    t6 = float((gates["T6"] or {}).get("value") or 0.0)
    t7 = (gates["T7"] or {}).get("value")
    t7_value = float(t7) if t7 is not None else None
    t7_band_distance = (
        0.0
        if t7_value is not None and 0.03 <= t7_value <= 0.08
        else (0.03 - t7_value if t7_value is not None and t7_value < 0.03 else (t7_value - 0.08 if t7_value is not None else 1.0))
    )
    t6_distance = max(0.0, t6 - 0.72)
    calibration_distance = t6_distance + max(0.0, t7_band_distance)

    if frozen_failures:
        lane_decision = "REJECT_FROZEN_RAIL_REGRESSION"
    elif runtime_regression_veto:
        lane_decision = "REJECT_RUNTIME_REGRESSION"
    elif primary_failures:
        lane_decision = "HOLD_P2_REOPEN"
    else:
        lane_decision = "UNLOCK_P3"

    if lane_decision == "UNLOCK_P3":
        phase_grade = "PASS_BPLUS_CANDIDATE" if not primary_bplus_failures else "PASS_B_CANDIDATE"
    else:
        phase_grade = "HOLD_REMEDIATE"

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P2",
        "segment": "5B",
        "run": {
            "run_id": run_id,
            "runs_root": str(runs_root),
            "segment_state_runs": str(state_runs_path),
        },
        "candidate": {
            "label": args.candidate_label,
            "suffix": args.suffix,
            "source_p1_gateboard": str(p1_path),
            "baseline_p1_gateboard": str(baseline_path) if baseline_path else None,
        },
        "gates": {gid: gates[gid] for gid in (FROZEN_VETO_GATES + PRIMARY_GATES + CONTEXT_GATES)},
        "summary": {
            "frozen_failures": frozen_failures,
            "primary_failures": primary_failures,
            "primary_bplus_failures": primary_bplus_failures,
            "context_failures": context_failures,
            "t6_distance_to_b": t6_distance,
            "t7_distance_to_b_band": max(0.0, t7_band_distance),
            "calibration_distance_to_b": calibration_distance,
            "runtime": {
                "s4_seconds": s4_seconds,
                "s5_seconds": s5_seconds,
                "lane_s4_s5_seconds": lane_seconds,
                "budget_seconds": float(args.runtime_budget_seconds),
                "budget_pass": runtime_budget_pass,
                "baseline_seconds": baseline_runtime if baseline_runtime > 0 else None,
                "regression_fraction_vs_baseline": runtime_regression if baseline_runtime > 0 else None,
                "regression_veto": runtime_regression_veto,
            },
            "lane_decision": lane_decision,
            "phase_grade": phase_grade,
        },
    }
    if baseline_gates:
        payload["baseline_delta_vs_p1_baseline"] = {
            gid: ((gates[gid].get("value") if isinstance(gates[gid], dict) else None) - (baseline_gates.get(gid) or {}).get("value"))
            if isinstance((gates[gid] if isinstance(gates[gid], dict) else None), dict)
            and isinstance((baseline_gates.get(gid) if isinstance(baseline_gates, dict) else None), dict)
            and isinstance((gates[gid].get("value")), (int, float))
            and isinstance(((baseline_gates.get(gid) or {}).get("value")), (int, float))
            else None
            for gid in ["T6", "T7"]
        }

    suffix = f"_{args.suffix}" if args.suffix else ""
    json_path = out_root / f"segment5b_p2_gateboard_{run_id}{suffix}.json"
    md_path = out_root / f"segment5b_p2_gateboard_{run_id}{suffix}.md"
    closure_path = out_root / f"segment5b_p2_closure_{run_id}{suffix}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    closure_path.write_text(
        json.dumps(
            {
                "generated_utc": _now_utc(),
                "phase": "P2.6" if not args.suffix else "P2.candidate",
                "run_id": run_id,
                "candidate_label": args.candidate_label,
                "lane_decision": lane_decision,
                "phase_grade": phase_grade,
                "frozen_failures": frozen_failures,
                "primary_failures": primary_failures,
                "runtime_budget_pass": runtime_budget_pass,
                "runtime_regression_veto": runtime_regression_veto,
                "gateboard_path": str(json_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    t6_status = "PASS" if bool((gates["T6"] or {}).get("b_pass")) else "FAIL"
    t7_status = _band_status(t7_value, 0.03, 0.08)
    frozen_status = "PASS" if not frozen_failures else "FAIL"
    runtime_status = "PASS" if (runtime_budget_pass and not runtime_regression_veto) else "FAIL"
    rows = _md_table(
        [
            ("T6 top10 share", _fmt_pct(t6), t6_status),
            ("T7 virtual share", _fmt_pct(t7_value), t7_status),
            ("Frozen rails", f"{len(FROZEN_VETO_GATES) - len(frozen_failures)}/{len(FROZEN_VETO_GATES)}", frozen_status),
            ("S4+S5 runtime", f"{lane_seconds:.3f}s", runtime_status),
            ("Lane decision", lane_decision, "INFO"),
        ]
    )
    md_lines = [
        f"# Segment 5B P2 Gateboard ({args.candidate_label})",
        "",
        f"- Generated UTC: `{payload['generated_utc']}`",
        f"- Run: `{run_id}`",
        f"- Source P1 gateboard: `{p1_path}`",
        "",
    ]
    md_lines.extend(rows)
    md_lines.append("")
    md_lines.append(f"- Phase grade: `{phase_grade}`")
    md_lines.append(f"- Closure artifact: `{closure_path}`")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[segment5b-p2] gateboard_json={json_path}")
    print(f"[segment5b-p2] gateboard_md={md_path}")
    print(f"[segment5b-p2] closure_json={closure_path}")


if __name__ == "__main__":
    main()
