#!/usr/bin/env python3
"""Score Segment 3B POPT.1 closure gates from baseline and candidate evidence."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TILE_PREP_RE = re.compile(r"S2: tile allocations prepared .*\(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)")
EDGE_PROGRESS_RE = re.compile(r"S2: edge jitter/tz progress (\d+)/(\d+) \(elapsed=([0-9.]+)s,")


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


def _extract_baseline_s2_elapsed(path: Path) -> float:
    payload = _load_json(path)
    rows = payload.get("timing", {}).get("state_table", [])
    for row in rows:
        if str(row.get("state")) == "S2":
            value = row.get("elapsed_s")
            if value is None:
                break
            return float(value)
    raise ValueError("Baseline payload missing S2 elapsed_s")


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer1/3B" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing run report for {state}: {state_dir}")
    return reports[-1]


def _parse_log(run_log_path: Path) -> dict[str, Any]:
    tile_prep_elapsed_s: float | None = None
    tile_prep_delta_s: float | None = None
    edge_loop_elapsed_s: float | None = None
    edge_progress_samples = 0
    final_progress = None

    for line in run_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m_tile = TILE_PREP_RE.search(line)
        if m_tile:
            tile_prep_elapsed_s = float(m_tile.group(1))
            tile_prep_delta_s = float(m_tile.group(2))
        m_edge = EDGE_PROGRESS_RE.search(line)
        if m_edge:
            edge_progress_samples += 1
            final_progress = (int(m_edge.group(1)), int(m_edge.group(2)))
            edge_loop_elapsed_s = float(m_edge.group(3))

    return {
        "tile_prep_elapsed_s": tile_prep_elapsed_s,
        "tile_prep_delta_s": tile_prep_delta_s,
        "edge_loop_elapsed_s": edge_loop_elapsed_s,
        "edge_progress_samples": edge_progress_samples,
        "edge_progress_final": final_progress,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    baseline = payload["baseline"]
    candidate = payload["candidate"]
    gates = payload["gates"]
    decision = payload["decision"]
    lines = [
        "# Segment 3B POPT.1 Closure",
        "",
        f"- baseline_run_id: `{baseline['run_id']}`",
        f"- candidate_run_id: `{candidate['run_id']}`",
        f"- decision: `{decision['result']}`",
        "",
        "## Runtime Gate",
        f"- baseline_s2: `{baseline['s2_elapsed_hms']}` ({baseline['s2_elapsed_s']:.3f}s)",
        f"- candidate_s2: `{candidate['s2_elapsed_hms']}` ({candidate['s2_elapsed_s']:.3f}s)",
        f"- reduction_vs_baseline: `{100.0 * candidate['s2_reduction_fraction']:.2f}%`",
        f"- runtime_gate_pass: `{gates['runtime_gate_pass']}`",
        "",
        "## Non-Regression Gate",
        f"- downstream_s3_s4_s5_pass: `{gates['downstream_pass']}`",
        f"- rng_accounting_coherent: `{gates['rng_accounting_coherent']}`",
        "",
        "## S2 Log Lane",
        f"- tile_prep_elapsed: `{_fmt_hms(candidate['log_lane'].get('tile_prep_elapsed_s')) or 'n/a'}`",
        f"- edge_loop_elapsed: `{_fmt_hms(candidate['log_lane'].get('edge_loop_elapsed_s')) or 'n/a'}`",
        f"- edge_progress_samples: `{candidate['log_lane'].get('edge_progress_samples')}`",
        "",
        "## Reopen",
        f"- reopen_lane: `{decision['reopen_lane']}`",
        f"- reason: {decision['reason']}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3B POPT.1 closure status")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_3B/reports/segment3b_popt0_baseline_724a63d3f8b242809b8ec3b746d0c776.json",
    )
    parser.add_argument("--baseline-run-id", default="724a63d3f8b242809b8ec3b746d0c776")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.candidate_run_id.strip()
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {run_root}")

    baseline_json = Path(args.baseline_json)
    baseline_s2_elapsed_s = _extract_baseline_s2_elapsed(baseline_json)

    s2_report = _load_json(_find_state_report(run_root, "S2"))
    s3_report = _load_json(_find_state_report(run_root, "S3"))
    s4_report = _load_json(_find_state_report(run_root, "S4"))
    s5_report = _load_json(_find_state_report(run_root, "S5"))
    run_log_path = run_root / f"run_log_{run_id}.log"
    log_lane = _parse_log(run_log_path)

    s2_elapsed_s = float(s2_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0
    reduction_fraction = (baseline_s2_elapsed_s - s2_elapsed_s) / baseline_s2_elapsed_s
    runtime_gate_pass = bool(s2_elapsed_s <= 300.0 or reduction_fraction >= 0.25)

    downstream_pass = all(
        str(report.get("status") or "").upper() == "PASS"
        for report in (s3_report, s4_report, s5_report)
    )

    s2_counts = s2_report.get("counts", {})
    edges_total = int(s2_counts.get("edges_total") or 0)
    rng_events_total = int(s2_counts.get("rng_events_total") or 0)
    rng_blocks_total = int(s2_counts.get("rng_blocks_total") or 0)
    rng_draws_total = int(str(s2_counts.get("rng_draws_total") or "0"))
    rng_accounting_coherent = bool(
        rng_events_total >= edges_total
        and rng_blocks_total == rng_events_total
        and rng_draws_total == (rng_events_total * 2)
    )

    if runtime_gate_pass and downstream_pass and rng_accounting_coherent:
        result = "UNLOCK_POPT2"
        reopen_lane = ""
        reason = "All runtime and non-regression gates passed."
    else:
        result = "HOLD_POPT1_REOPEN"
        reopen_lane = "S2 tile-allocation prep path redesign under strict memory budget"
        reason = (
            "Runtime gate failed and/or non-regression gate failed; keep POPT.1 open with "
            "bounded S2 prep-lane reopen."
        )

    payload: dict[str, Any] = {
        "phase": "POPT.1",
        "segment": "3B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline": {
            "run_id": args.baseline_run_id,
            "s2_elapsed_s": baseline_s2_elapsed_s,
            "s2_elapsed_hms": _fmt_hms(baseline_s2_elapsed_s),
            "source": str(baseline_json).replace("\\", "/"),
        },
        "candidate": {
            "run_id": run_id,
            "run_root": str(run_root).replace("\\", "/"),
            "run_log_path": str(run_log_path).replace("\\", "/"),
            "s2_elapsed_s": s2_elapsed_s,
            "s2_elapsed_hms": _fmt_hms(s2_elapsed_s),
            "s2_reduction_fraction": reduction_fraction,
            "s2_counts": s2_counts,
            "state_status": {
                "S2": str(s2_report.get("status") or ""),
                "S3": str(s3_report.get("status") or ""),
                "S4": str(s4_report.get("status") or ""),
                "S5": str(s5_report.get("status") or ""),
            },
            "log_lane": log_lane,
        },
        "gates": {
            "runtime_gate_pass": runtime_gate_pass,
            "runtime_gate_rule": "S2 <= 300s OR >=25% reduction vs baseline",
            "downstream_pass": downstream_pass,
            "rng_accounting_coherent": rng_accounting_coherent,
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
        else runs_root / "reports" / f"segment3b_popt1_closure_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt1_closure_{run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
