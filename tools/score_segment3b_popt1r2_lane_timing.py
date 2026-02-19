#!/usr/bin/env python3
"""Emit Segment 3B S2 lane-timing artifact for POPT.1R.2 (read-only harness)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
S2_START_RE = re.compile(r"S2: run log initialized")
S2_VERIFY_RE = re.compile(r"S2: verified required sealed inputs and digests")
S2_TILE_ALLOC_RE = re.compile(r"S2: tile allocations prepared")
S2_LOOP_START_RE = re.compile(r"S2: starting edge placement loop")
S2_PROGRESS_RE = re.compile(r"S2: edge jitter/tz progress (\d+)/(\d+) \(elapsed=([0-9.]+)s,")
S2_REPORT_RE = re.compile(r"S2: run-report written")


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer1/3B" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing {state} run report under {state_dir}")
    return reports[-1]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _elapsed(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def _parse_s2_markers(run_log_path: Path) -> dict[str, Any]:
    s2_start_ts: datetime | None = None
    s2_verify_ts: datetime | None = None
    s2_tile_alloc_ts: datetime | None = None
    s2_loop_start_ts: datetime | None = None
    s2_progress_final_ts: datetime | None = None
    s2_progress_final_elapsed_s: float | None = None
    s2_report_written_ts: datetime | None = None
    progress_samples = 0
    progress_final = None

    for line in run_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "seg_3B.s2_edge_catalogue" not in line:
            continue
        ts = _parse_ts(line)
        if ts is None:
            continue
        if S2_START_RE.search(line):
            s2_start_ts = ts
        if S2_VERIFY_RE.search(line):
            s2_verify_ts = ts
        if S2_TILE_ALLOC_RE.search(line):
            s2_tile_alloc_ts = ts
        if S2_LOOP_START_RE.search(line):
            s2_loop_start_ts = ts
        m_progress = S2_PROGRESS_RE.search(line)
        if m_progress:
            progress_samples += 1
            current = int(m_progress.group(1))
            total = int(m_progress.group(2))
            elapsed_s = float(m_progress.group(3))
            if current == total:
                s2_progress_final_ts = ts
                s2_progress_final_elapsed_s = elapsed_s
                progress_final = [current, total]
        if S2_REPORT_RE.search(line):
            s2_report_written_ts = ts

    return {
        "s2_start_ts": s2_start_ts.isoformat() if s2_start_ts else None,
        "s2_verify_ts": s2_verify_ts.isoformat() if s2_verify_ts else None,
        "s2_tile_alloc_ts": s2_tile_alloc_ts.isoformat() if s2_tile_alloc_ts else None,
        "s2_loop_start_ts": s2_loop_start_ts.isoformat() if s2_loop_start_ts else None,
        "s2_progress_final_ts": s2_progress_final_ts.isoformat() if s2_progress_final_ts else None,
        "s2_report_written_ts": s2_report_written_ts.isoformat() if s2_report_written_ts else None,
        "progress_samples": progress_samples,
        "progress_final": progress_final,
        "s2_progress_final_elapsed_s": s2_progress_final_elapsed_s,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lane = payload["lane_timing"]
    qc = payload["quality_checks"]
    lines = [
        "# Segment 3B POPT.1R.2 Lane Timing",
        "",
        f"- run_id: `{payload['run']['run_id']}`",
        f"- baseline_authority: `{payload['run']['is_baseline_authority']}`",
        f"- s2_status: `{payload['run']['s2_status']}`",
        "",
        "## Lane Table",
        "",
        "| Lane | Seconds | HMS | Share of S2 wall |",
        "|---|---:|---:|---:|",
    ]
    for row in lane["table"]:
        share = f"{100.0 * float(row['share_of_s2_wall']):.2f}%" if row["share_of_s2_wall"] is not None else "n/a"
        sec = f"{row['seconds']:.3f}" if row["seconds"] is not None else "n/a"
        hms = row["hms"] or "n/a"
        lines.append(f"| {row['lane']} | {sec} | {hms} | {share} |")
    lines.extend(
        [
            "",
            f"- s2_wall_report: `{lane['s2_wall_hms']}` ({lane['s2_wall_s']:.3f}s)",
            f"- s2_window_from_log: `{lane['s2_window_hms'] or 'n/a'}`",
            f"- wall_vs_window_gap_s: `{lane['wall_vs_window_gap_s']:.3f}`",
            "",
            "## Profiler Harness",
            f"- harness_mode: `{payload['harness']['mode']}`",
            f"- runtime_overhead_estimate_s: `{payload['harness']['runtime_overhead_estimate_s']}`",
            f"- instrumentation_overhead_bounded: `{qc['instrumentation_overhead_bounded']}`",
            f"- lane_artifact_present: `{qc['lane_artifact_present']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 3B POPT.1R.2 S2 lane timing artifact")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--run-id", default="724a63d3f8b242809b8ec3b746d0c776")
    parser.add_argument("--baseline-run-id", default="724a63d3f8b242809b8ec3b746d0c776")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip()
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    s2_report_path = _find_state_report(run_root, "S2")
    s2_report = _load_json(s2_report_path)
    s2_status = str(s2_report.get("status") or "")
    s2_wall_s = float(s2_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0
    run_log_path = run_root / f"run_log_{run_id}.log"
    if not run_log_path.exists():
        raise FileNotFoundError(f"Run log missing: {run_log_path}")

    markers = _parse_s2_markers(run_log_path)
    ts = {
        key: (datetime.fromisoformat(value) if value else None)
        for key, value in markers.items()
        if key.endswith("_ts")
    }

    lane_input_verify_s = _elapsed(ts.get("s2_start_ts"), ts.get("s2_verify_ts"))
    lane_tile_prep_total_s = _elapsed(ts.get("s2_verify_ts"), ts.get("s2_tile_alloc_ts"))
    lane_pre_loop_aux_s = _elapsed(ts.get("s2_tile_alloc_ts"), ts.get("s2_loop_start_ts"))
    lane_edge_loop_s = _elapsed(ts.get("s2_loop_start_ts"), ts.get("s2_progress_final_ts"))
    lane_publish_finalize_s = _elapsed(ts.get("s2_progress_final_ts"), ts.get("s2_report_written_ts"))
    s2_window_s = _elapsed(ts.get("s2_start_ts"), ts.get("s2_report_written_ts"))
    wall_vs_window_gap_s = (s2_wall_s - s2_window_s) if s2_window_s is not None else 0.0

    table: list[dict[str, Any]] = []
    for lane_name, seconds in [
        ("input_resolve_and_seal", lane_input_verify_s),
        ("tile_read_map_alloc_project_total", lane_tile_prep_total_s),
        ("pre_loop_aux_assets", lane_pre_loop_aux_s),
        ("edge_jitter_tz_loop", lane_edge_loop_s),
        ("publish_finalize", lane_publish_finalize_s),
    ]:
        share = (float(seconds) / s2_wall_s) if seconds is not None and s2_wall_s > 0 else None
        table.append(
            {
                "lane": lane_name,
                "seconds": seconds,
                "hms": _fmt_hms(seconds),
                "share_of_s2_wall": share,
            }
        )

    payload: dict[str, Any] = {
        "phase": "POPT.1R.2",
        "segment": "3B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "baseline_run_id": args.baseline_run_id,
            "is_baseline_authority": run_id == args.baseline_run_id,
            "run_log_path": str(run_log_path).replace("\\", "/"),
            "s2_run_report_path": str(s2_report_path).replace("\\", "/"),
            "s2_status": s2_status,
        },
        "markers": markers,
        "lane_timing": {
            "table": table,
            "s2_wall_s": s2_wall_s,
            "s2_wall_hms": _fmt_hms(s2_wall_s),
            "s2_window_s": s2_window_s,
            "s2_window_hms": _fmt_hms(s2_window_s),
            "wall_vs_window_gap_s": wall_vs_window_gap_s,
            "edge_loop_elapsed_from_progress_s": markers.get("s2_progress_final_elapsed_s"),
        },
        "harness": {
            "mode": "read_only_log_report_parser",
            "runtime_overhead_estimate_s": 0.0,
            "notes": "No engine state code changes; profiler is offline parsing only.",
        },
        "quality_checks": {
            "lane_artifact_present": True,
            "instrumentation_overhead_bounded": True,
            "required_markers_found": bool(
                markers.get("s2_start_ts")
                and markers.get("s2_verify_ts")
                and markers.get("s2_tile_alloc_ts")
                and markers.get("s2_loop_start_ts")
                and markers.get("s2_progress_final_ts")
                and markers.get("s2_report_written_ts")
            ),
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3b_popt1r2_lane_timing_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt1r2_lane_timing_{run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
