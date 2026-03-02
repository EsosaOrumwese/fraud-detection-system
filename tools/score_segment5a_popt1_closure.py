#!/usr/bin/env python3
"""Score Segment 5A POPT.1 closure gates from baseline/candidate artifacts."""

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
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _state_elapsed_from_baseline_json(path: Path, state: str) -> float:
    payload = _load_json(path)
    rows = payload.get("timing", {}).get("state_table", [])
    for row in rows:
        if str(row.get("state")) == state:
            value = row.get("elapsed_s")
            if value is None:
                break
            return float(value)
    raise ValueError(f"Missing elapsed_s for {state} in {path}")


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer2/5A" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing {state} run report under {state_dir}")
    return reports[-1]


def _baseline_s3_report_path(baseline_payload: dict[str, Any], runs_root: Path, baseline_run_id: str) -> Path:
    baseline_report = (
        baseline_payload.get("run", {}).get("report_paths", {}).get("S3")
        if isinstance(baseline_payload.get("run"), dict)
        else None
    )
    if baseline_report:
        path = Path(str(baseline_report))
        if path.exists():
            return path
    baseline_run_root = runs_root / baseline_run_id
    return _find_state_report(baseline_run_root, "S3")


def _improvement_fraction(baseline_s: float, candidate_s: float) -> float:
    if baseline_s <= 0:
        return 0.0
    return (baseline_s - candidate_s) / baseline_s


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    rt = payload["runtime"]
    veto = payload["veto"]
    gates = payload["gates"]
    decision = payload["decision"]
    lines = [
        "# Segment 5A POPT.1 Closure",
        "",
        f"- baseline_run_id: `{payload['baseline']['run_id']}`",
        f"- candidate_run_id: `{payload['candidate']['run_id']}`",
        f"- decision: `{decision['result']}`",
        "",
        "## Runtime Gate",
        f"- S3 baseline: `{_fmt_hms(rt['s3']['baseline_s'])}` ({rt['s3']['baseline_s']:.3f}s)",
        f"- S3 candidate: `{_fmt_hms(rt['s3']['candidate_s'])}` ({rt['s3']['candidate_s']:.3f}s)",
        f"- S3 improvement: `{100.0 * rt['s3']['improvement_fraction']:.2f}%`",
        f"- gate rule: `{gates['runtime_gate_rule']}`",
        f"- runtime_gate_pass: `{gates['runtime_gate_pass']}`",
        "",
        "## Structural Veto",
        f"- s3_status_pass: `{veto['s3_status_pass']}`",
        f"- s3_counts_unchanged: `{veto['s3_counts_unchanged']}`",
        f"- s3_weekly_sum_zero: `{veto['s3_weekly_sum_zero']}`",
        f"- s3_error_surface_clean: `{veto['s3_error_surface_clean']}`",
        f"- downstream_s4_pass: `{veto['downstream_s4_pass']}`",
        f"- downstream_s5_pass: `{veto['downstream_s5_pass']}`",
        "",
        "## Verdict",
        f"- all_veto_clear: `{decision['all_veto_clear']}`",
        f"- all_runtime_clear: `{decision['all_runtime_clear']}`",
        f"- reason: {decision['reason']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5A POPT.1 closure")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_5A")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_5A/reports/segment5a_popt0_baseline_7b08449ccffc44beaa99e64bf0201efc.json",
    )
    parser.add_argument("--candidate-baseline-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    candidate_run_id = args.candidate_run_id.strip()
    run_root = runs_root / candidate_run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {run_root}")

    baseline_json_path = Path(args.baseline_json)
    baseline_payload = _load_json(baseline_json_path)
    baseline_run_id = str(baseline_payload.get("run", {}).get("run_id") or "")
    if not baseline_run_id:
        raise ValueError("Baseline json missing run.run_id")

    candidate_baseline_json = (
        Path(args.candidate_baseline_json)
        if args.candidate_baseline_json
        else runs_root / "reports" / f"segment5a_popt0_baseline_{candidate_run_id}.json"
    )
    if not candidate_baseline_json.exists():
        raise FileNotFoundError(
            f"Candidate baseline json missing: {candidate_baseline_json}. "
            "Generate with tools/score_segment5a_popt0_baseline.py first."
        )

    baseline_s3 = _state_elapsed_from_baseline_json(baseline_json_path, "S3")
    candidate_s3 = _state_elapsed_from_baseline_json(candidate_baseline_json, "S3")
    s3_impr = _improvement_fraction(baseline_s3, candidate_s3)

    s3_report = _load_json(_find_state_report(run_root, "S3"))
    s4_report = _load_json(_find_state_report(run_root, "S4"))
    s5_report = _load_json(_find_state_report(run_root, "S5"))

    baseline_s3_report_path = _baseline_s3_report_path(baseline_payload, runs_root, baseline_run_id)
    baseline_s3_report = _load_json(baseline_s3_report_path)
    baseline_counts = baseline_s3_report.get("counts", {})
    candidate_counts = s3_report.get("counts", {})
    count_keys = ("baseline_rows", "class_baseline_rows", "domain_rows")
    s3_counts_unchanged = all(
        int(candidate_counts.get(key) or -1) == int(baseline_counts.get(key) or -2) for key in count_keys
    )

    runtime_gate_pass = bool(candidate_s3 <= 420.0 or s3_impr >= 0.25)
    veto = {
        "s3_status_pass": str(s3_report.get("status") or "").upper() == "PASS",
        "s3_counts_unchanged": s3_counts_unchanged,
        "s3_weekly_sum_zero": int(s3_report.get("weekly_sum_error_violations_count") or 0) == 0,
        "s3_error_surface_clean": not (s3_report.get("error_code") or s3_report.get("error_class")),
        "downstream_s4_pass": str(s4_report.get("status") or "").upper() == "PASS",
        "downstream_s5_pass": str(s5_report.get("status") or "").upper() == "PASS",
    }

    all_veto_clear = all(bool(v) for v in veto.values())
    all_runtime_clear = runtime_gate_pass

    if all_veto_clear and all_runtime_clear:
        result = "UNLOCK_POPT2"
        reason = "POPT.1 runtime + structural gates passed."
    else:
        result = "HOLD_POPT1_REOPEN"
        reason = "One or more runtime/structural gates failed; continue bounded POPT.1 reopen."

    payload: dict[str, Any] = {
        "phase": "POPT.1",
        "segment": "5A",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline": {
            "run_id": baseline_run_id,
            "source": str(baseline_json_path).replace("\\", "/"),
        },
        "candidate": {
            "run_id": candidate_run_id,
            "run_root": str(run_root).replace("\\", "/"),
            "baseline_source": str(candidate_baseline_json).replace("\\", "/"),
        },
        "count_anchors": {
            "source": str(baseline_s3_report_path).replace("\\", "/"),
            "keys": list(count_keys),
            "baseline_counts": {key: baseline_counts.get(key) for key in count_keys},
            "candidate_counts": {key: candidate_counts.get(key) for key in count_keys},
        },
        "runtime": {
            "s3": {
                "baseline_s": baseline_s3,
                "candidate_s": candidate_s3,
                "improvement_fraction": s3_impr,
            }
        },
        "veto": veto,
        "gates": {
            "runtime_gate_rule": "S3 <= 420s OR >=25% reduction vs baseline",
            "runtime_gate_pass": runtime_gate_pass,
        },
        "decision": {
            "all_veto_clear": all_veto_clear,
            "all_runtime_clear": all_runtime_clear,
            "result": result,
            "reason": reason,
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment5a_popt1_closure_{candidate_run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment5a_popt1_closure_{candidate_run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
