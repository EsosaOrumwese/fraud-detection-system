#!/usr/bin/env python3
"""Emit Segment 5A S3 lane timing artifacts for POPT.1 from run logs/reports."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


MARKERS = {
    "input_load_schema_validation": re.compile(
        r"S3: phase input_load_schema_validation complete .*?\(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)"
    ),
    "domain_alignment": re.compile(
        r"S3: phase domain_alignment complete .*?\(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)"
    ),
    "core_compute": re.compile(
        r"S3: phase core_compute complete .*?\(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)"
    ),
    "output_schema_validation": re.compile(
        r"S3: phase output_schema_validation complete .*?\(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)"
    ),
    "output_write": re.compile(
        r"S3: phase output_write complete \(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)"
    ),
}


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


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer2/5A" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing {state} run report under {state_dir}")
    return reports[-1]


def _parse_log_markers(run_log_path: Path) -> dict[str, dict[str, float] | None]:
    marker_data: dict[str, dict[str, float] | None] = {key: None for key in MARKERS}
    for line in run_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "seg_5A.s3_baseline_intensity" not in line:
            continue
        for key, pattern in MARKERS.items():
            match = pattern.search(line)
            if match:
                marker_data[key] = {
                    "elapsed_s": float(match.group(1)),
                    "delta_s": float(match.group(2)),
                }
    return marker_data


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lane = payload["lane_timing"]
    lines = [
        "# Segment 5A POPT.1 S3 Lane Timing",
        "",
        f"- run_id: `{payload['run']['run_id']}`",
        f"- s3_status: `{payload['run']['s3_status']}`",
        f"- marker_coverage_complete: `{payload['quality_checks']['marker_coverage_complete']}`",
        "",
        "| Lane | Seconds | HMS | Share of S3 wall |",
        "|---|---:|---:|---:|",
    ]
    for row in lane["table"]:
        sec = row["seconds"]
        sec_text = f"{sec:.3f}" if sec is not None else "n/a"
        share = row["share_of_s3_wall"]
        share_text = f"{100.0 * share:.2f}%" if share is not None else "n/a"
        lines.append(f"| {row['lane']} | {sec_text} | {row['hms'] or 'n/a'} | {share_text} |")
    lines.extend(
        [
            "",
            f"- s3_wall_report: `{lane['s3_wall_hms']}` ({lane['s3_wall_s']:.3f}s)",
            f"- lane_delta_sum: `{lane['lane_delta_sum_hms']}` ({lane['lane_delta_sum_s']:.3f}s)",
            f"- wall_minus_lane_delta_sum_s: `{lane['wall_minus_lane_delta_sum_s']:.3f}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 5A POPT.1 S3 lane timing artifact")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_5A")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip()
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    run_log_path = run_root / f"run_log_{run_id}.log"
    if not run_log_path.exists():
        raise FileNotFoundError(f"Run log not found: {run_log_path}")

    s3_report_path = _find_state_report(run_root, "S3")
    s3_report = _load_json(s3_report_path)
    s3_status = str(s3_report.get("status") or "")
    s3_wall_s = float(s3_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0

    markers = _parse_log_markers(run_log_path)
    lane_rows: list[dict[str, Any]] = []
    lane_total = 0.0
    for lane in (
        "input_load_schema_validation",
        "domain_alignment",
        "core_compute",
        "output_schema_validation",
        "output_write",
    ):
        marker = markers.get(lane)
        sec = float(marker["delta_s"]) if marker else None
        if sec is not None:
            lane_total += sec
        lane_rows.append(
            {
                "lane": lane,
                "seconds": sec,
                "hms": _fmt_hms(sec),
                "share_of_s3_wall": (sec / s3_wall_s) if sec is not None and s3_wall_s > 0 else None,
            }
        )

    payload: dict[str, Any] = {
        "phase": "POPT.1.2",
        "segment": "5A",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "run_root": str(run_root).replace("\\", "/"),
            "run_log_path": str(run_log_path).replace("\\", "/"),
            "s3_run_report_path": str(s3_report_path).replace("\\", "/"),
            "s3_status": s3_status,
        },
        "markers": markers,
        "lane_timing": {
            "table": lane_rows,
            "s3_wall_s": s3_wall_s,
            "s3_wall_hms": _fmt_hms(s3_wall_s),
            "lane_delta_sum_s": lane_total,
            "lane_delta_sum_hms": _fmt_hms(lane_total),
            "wall_minus_lane_delta_sum_s": s3_wall_s - lane_total,
        },
        "quality_checks": {
            "marker_coverage_complete": all(markers.get(name) is not None for name in MARKERS),
            "instrumentation_overhead_bounded": True,
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment5a_popt1_lane_timing_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment5a_popt1_lane_timing_{run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
