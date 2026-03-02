#!/usr/bin/env python3
"""Score Segment 3B POPT.3 closure gates from baseline and candidate evidence."""

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
    candidate = payload.get("candidate") or {}
    value = candidate.get("s5_elapsed_s")
    if value is not None:
        return float(value)
    baseline = payload.get("baseline") or {}
    value = baseline.get("s5_elapsed_s")
    if value is not None:
        return float(value)
    raise ValueError("Baseline source missing s5_elapsed_s")


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
        "# Segment 3B POPT.3 Closure",
        "",
        f"- baseline_run_id: `{baseline['run_id']}`",
        f"- candidate_run_id: `{candidate['run_id']}`",
        f"- decision: `{decision['result']}`",
        "",
        "## Runtime Guard",
        f"- baseline_s5: `{baseline['s5_elapsed_hms']}` ({baseline['s5_elapsed_s']:.3f}s)",
        f"- candidate_s5: `{candidate['s5_elapsed_hms']}` ({candidate['s5_elapsed_s']:.3f}s)",
        f"- movement_vs_baseline: `{100.0 * candidate['s5_reduction_fraction']:.2f}%`",
        f"- runtime_guard_pass: `{gates['runtime_guard_pass']}`",
        "",
        "## Log Guard",
        f"- progress_lines_baseline: `{baseline['log_counts']['progress_lines']}`",
        f"- progress_lines_candidate: `{candidate['log_counts']['progress_lines']}`",
        f"- progress_line_budget_max: `{gates['progress_line_budget_max']}`",
        f"- required_narrative_present: `{gates['required_narrative_present']}`",
        f"- log_guard_pass: `{gates['log_guard_pass']}`",
        "",
        "## Non-Regression",
        f"- digest_parity_pass: `{gates['digest_parity_pass']}`",
        f"- output_path_stable: `{gates['output_path_stable']}`",
        f"- candidate_s5_status_pass: `{gates['candidate_s5_status_pass']}`",
    ]
    if decision["result"] != "UNLOCK_POPT4":
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
    parser = argparse.ArgumentParser(description="Score Segment 3B POPT.3 closure status")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--baseline-run-id", default="724a63d3f8b242809b8ec3b746d0c776")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-source-json",
        default="runs/fix-data-engine/segment_3B/reports/segment3b_popt2r2_closure_724a63d3f8b242809b8ec3b746d0c776.json",
    )
    parser.add_argument("--baseline-log-json", required=True)
    parser.add_argument("--candidate-log-json", required=True)
    parser.add_argument("--progress-line-budget-max", type=int, default=16)
    parser.add_argument("--max-runtime-regression-fraction", type=float, default=0.15)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    baseline_run_id = args.baseline_run_id.strip()
    candidate_run_id = args.candidate_run_id.strip()

    baseline_s5_elapsed_s = _extract_baseline_s5_elapsed_s(Path(args.baseline_source_json))
    baseline_log = _load_json(Path(args.baseline_log_json))
    candidate_log = _load_json(Path(args.candidate_log_json))

    candidate_run_root = runs_root / candidate_run_id
    if not candidate_run_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {candidate_run_root}")
    candidate_s5_report = _load_json(_find_state_report(candidate_run_root, "S5"))
    candidate_s5_elapsed_s = float(candidate_s5_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0

    reduction_fraction = (baseline_s5_elapsed_s - candidate_s5_elapsed_s) / baseline_s5_elapsed_s
    runtime_guard_pass = bool(
        candidate_s5_elapsed_s <= 55.0 and candidate_s5_elapsed_s <= baseline_s5_elapsed_s * (1.0 + args.max_runtime_regression_fraction)
    )

    baseline_required = baseline_log.get("required_presence") or {}
    candidate_required = candidate_log.get("required_presence") or {}
    required_narrative_present = bool(all(candidate_required.values()))
    progress_lines_candidate = int((candidate_log.get("counts") or {}).get("progress_lines") or 0)
    log_guard_pass = bool(
        progress_lines_candidate <= int(args.progress_line_budget_max)
        and required_narrative_present
    )

    baseline_digest = str((baseline_log.get("run") or {}).get("bundle_digest_from_flag") or "")
    candidate_digest = str((candidate_log.get("run") or {}).get("bundle_digest_from_flag") or "")
    digest_parity_pass = bool(baseline_digest and candidate_digest and baseline_digest == candidate_digest)

    baseline_output = (baseline_log.get("run") or {}).get("output") or {}
    candidate_output = (candidate_log.get("run") or {}).get("output") or {}
    output_path_stable = bool(
        baseline_output.get("bundle_path") == candidate_output.get("bundle_path")
        and baseline_output.get("index_path") == candidate_output.get("index_path")
        and baseline_output.get("flag_path") == candidate_output.get("flag_path")
    )
    candidate_s5_status_pass = str(candidate_s5_report.get("status") or "").upper() == "PASS"

    non_regression_pass = bool(digest_parity_pass and output_path_stable and candidate_s5_status_pass)

    if runtime_guard_pass and log_guard_pass and non_regression_pass:
        result = "UNLOCK_POPT4"
        reopen_lane = ""
        reason = "Runtime/log-budget/non-regression guards passed."
    else:
        result = "HOLD_POPT3_REOPEN"
        reopen_lane = "S5 log/serialization hardening lane"
        reason = "One or more POPT.3 guards failed."

    payload: dict[str, Any] = {
        "phase": "POPT.3",
        "segment": "3B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline": {
            "run_id": baseline_run_id,
            "s5_elapsed_s": baseline_s5_elapsed_s,
            "s5_elapsed_hms": _fmt_hms(baseline_s5_elapsed_s),
            "log_counts": baseline_log.get("counts") or {},
            "log_source": str(Path(args.baseline_log_json)).replace("\\", "/"),
            "runtime_source": str(Path(args.baseline_source_json)).replace("\\", "/"),
        },
        "candidate": {
            "run_id": candidate_run_id,
            "run_root": str(candidate_run_root).replace("\\", "/"),
            "s5_elapsed_s": candidate_s5_elapsed_s,
            "s5_elapsed_hms": _fmt_hms(candidate_s5_elapsed_s),
            "s5_reduction_fraction": reduction_fraction,
            "s5_status": str(candidate_s5_report.get("status") or ""),
            "s5_error_code": candidate_s5_report.get("error_code"),
            "log_counts": candidate_log.get("counts") or {},
            "log_source": str(Path(args.candidate_log_json)).replace("\\", "/"),
        },
        "gates": {
            "runtime_guard_pass": runtime_guard_pass,
            "runtime_guard_rule": "S5 <= 55s and <=15% regression vs baseline",
            "progress_line_budget_max": int(args.progress_line_budget_max),
            "required_narrative_present": required_narrative_present,
            "log_guard_pass": log_guard_pass,
            "digest_parity_pass": digest_parity_pass,
            "output_path_stable": output_path_stable,
            "candidate_s5_status_pass": candidate_s5_status_pass,
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
        else runs_root / "reports" / f"segment3b_popt3_closure_{candidate_run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt3_closure_{candidate_run_id}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
