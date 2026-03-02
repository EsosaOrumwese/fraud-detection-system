#!/usr/bin/env python3
"""Score Segment 3B POPT.2 closure gates from baseline and candidate evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _extract_baseline_s5_elapsed_s(path: Path) -> float:
    payload = _load_json(path)
    rows = payload.get("timing", {}).get("state_table", [])
    for row in rows:
        if str(row.get("state")) == "S5":
            value = row.get("elapsed_s")
            if value is not None:
                return float(value)
    raise ValueError("Baseline payload missing S5 elapsed_s")


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer1/3B" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing run report for {state}: {state_dir}")
    return reports[-1]


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    baseline = payload["baseline"]
    candidate = payload["candidate"]
    gates = payload["gates"]
    decision = payload["decision"]
    lines = [
        "# Segment 3B POPT.2 Closure",
        "",
        f"- baseline_run_id: `{baseline['run_id']}`",
        f"- candidate_run_id: `{candidate['run_id']}`",
        f"- decision: `{decision['result']}`",
        "",
        "## Runtime Gate",
        f"- baseline_s5: `{baseline['s5_elapsed_hms']}` ({baseline['s5_elapsed_s']:.3f}s)",
        f"- candidate_s5: `{candidate['s5_elapsed_hms']}` ({candidate['s5_elapsed_s']:.3f}s)",
        f"- reduction_vs_baseline: `{100.0 * candidate['s5_reduction_fraction']:.2f}%`",
        f"- runtime_gate_pass: `{gates['runtime_gate_pass']}`",
        "",
        "## Non-Regression Gates",
        f"- candidate_s5_status_pass: `{gates['candidate_s5_status_pass']}`",
        f"- digest_parity_pass: `{gates['digest_parity_pass']}`",
        f"- output_path_stable: `{gates['output_path_stable']}`",
        "",
        "## Lane Hotspots",
        f"- baseline_top2: `{', '.join(baseline['lane_top2'])}`",
        f"- candidate_top2: `{', '.join(candidate['lane_top2'])}`",
    ]
    if decision["result"] != "UNLOCK_POPT3":
        lines.extend(
            [
                "",
                "## Reopen",
                f"- reopen_lane: `{decision['reopen_lane']}`",
                f"- reason: {decision['reason']}",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3B POPT.2 closure status")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--baseline-run-id", default="724a63d3f8b242809b8ec3b746d0c776")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_3B/reports/segment3b_popt0_baseline_724a63d3f8b242809b8ec3b746d0c776.json",
    )
    parser.add_argument("--baseline-lane-json", default="")
    parser.add_argument("--candidate-lane-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    baseline_run_id = args.baseline_run_id.strip()
    candidate_run_id = args.candidate_run_id.strip()

    baseline_lane_json = (
        Path(args.baseline_lane_json)
        if args.baseline_lane_json
        else runs_root / "reports" / f"segment3b_popt2_s5_lane_timing_{baseline_run_id}.json"
    )
    candidate_lane_json = (
        Path(args.candidate_lane_json)
        if args.candidate_lane_json
        else runs_root / "reports" / f"segment3b_popt2_s5_lane_timing_{candidate_run_id}.json"
    )
    baseline_lane = _load_json(baseline_lane_json)
    candidate_lane = _load_json(candidate_lane_json)

    baseline_s5_elapsed_s = _extract_baseline_s5_elapsed_s(Path(args.baseline_json))

    candidate_run_root = runs_root / candidate_run_id
    if not candidate_run_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {candidate_run_root}")
    candidate_s5_report = _load_json(_find_state_report(candidate_run_root, "S5"))
    candidate_s5_elapsed_s = float(candidate_s5_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0

    reduction_fraction = (baseline_s5_elapsed_s - candidate_s5_elapsed_s) / baseline_s5_elapsed_s
    runtime_gate_pass = bool(candidate_s5_elapsed_s <= 180.0 or reduction_fraction >= 0.25)

    baseline_bundle_digest = str(baseline_lane.get("run", {}).get("bundle_digest_from_flag") or "")
    candidate_bundle_digest = str(candidate_lane.get("run", {}).get("bundle_digest_from_flag") or "")
    digest_parity_pass = bool(
        baseline_bundle_digest and candidate_bundle_digest and baseline_bundle_digest == candidate_bundle_digest
    )

    baseline_output = baseline_lane.get("run", {}).get("output") or {}
    candidate_output = candidate_lane.get("run", {}).get("output") or {}
    output_path_stable = bool(
        baseline_output.get("bundle_path") == candidate_output.get("bundle_path")
        and baseline_output.get("index_path") == candidate_output.get("index_path")
        and baseline_output.get("flag_path") == candidate_output.get("flag_path")
    )

    candidate_s5_status_pass = str(candidate_s5_report.get("status") or "").upper() == "PASS"
    non_regression_pass = candidate_s5_status_pass and digest_parity_pass and output_path_stable

    if runtime_gate_pass and non_regression_pass:
        result = "UNLOCK_POPT3"
        reopen_lane = ""
        reason = "Runtime and non-regression gates passed."
    else:
        result = "HOLD_POPT2_REOPEN"
        reopen_lane = "S5 hash-lane redesign and evidence assembly trim"
        reason = (
            "Runtime gate and/or non-regression gate failed; keep POPT.2 open with bounded "
            "S5-focused reopen lane."
        )

    payload: dict[str, Any] = {
        "phase": "POPT.2",
        "segment": "3B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline": {
            "run_id": baseline_run_id,
            "s5_elapsed_s": baseline_s5_elapsed_s,
            "s5_elapsed_hms": _fmt_hms(baseline_s5_elapsed_s),
            "lane_top2": baseline_lane.get("lane_timing", {}).get("top2_hot_lanes", []),
            "bundle_digest": baseline_bundle_digest,
            "lane_source": str(baseline_lane_json).replace("\\", "/"),
            "runtime_source": str(Path(args.baseline_json)).replace("\\", "/"),
        },
        "candidate": {
            "run_id": candidate_run_id,
            "run_root": str(candidate_run_root).replace("\\", "/"),
            "s5_elapsed_s": candidate_s5_elapsed_s,
            "s5_elapsed_hms": _fmt_hms(candidate_s5_elapsed_s),
            "s5_reduction_fraction": reduction_fraction,
            "lane_top2": candidate_lane.get("lane_timing", {}).get("top2_hot_lanes", []),
            "bundle_digest": candidate_bundle_digest,
            "s5_status": str(candidate_s5_report.get("status") or ""),
            "s5_error_code": candidate_s5_report.get("error_code"),
            "lane_source": str(candidate_lane_json).replace("\\", "/"),
        },
        "gates": {
            "runtime_gate_pass": runtime_gate_pass,
            "runtime_gate_rule": "S5 <= 180s OR >=25% reduction vs baseline",
            "candidate_s5_status_pass": candidate_s5_status_pass,
            "digest_parity_pass": digest_parity_pass,
            "output_path_stable": output_path_stable,
            "non_regression_pass": non_regression_pass,
        },
        "decision": {
            "result": result,
            "reopen_lane": reopen_lane,
            "reason": reason,
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3b_popt2_closure_{candidate_run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt2_closure_{candidate_run_id}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
