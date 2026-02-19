#!/usr/bin/env python3
"""Emit Segment 3B S5 lane-timing artifact for POPT.2.1 (read-only harness)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
S5_START_RE = re.compile(r"S5: run log initialized")
S5_SEALED_OK_RE = re.compile(r"S5: sealed inputs validated and required policy digests verified")
S5_VALIDATE_S2_INDEX_RE = re.compile(r"S5: validate S2 index files")
S5_HASH_AUDIT_RE = re.compile(r"S5: hash rng_audit_log")
S5_RUN_REPORT_RE = re.compile(r"S5: run-report written")
HASH_PROGRESS_RE = re.compile(
    r"S5: hash (?P<label>[a-zA-Z0-9_]+)\s+"
    r"(?:(?P<done>\d+)/(?P<total>\d+)|processed=(?P<processed>\d+))\s+"
    r"\(elapsed=(?P<elapsed>[0-9.]+)s,\s+rate=(?P<rate>[0-9.]+)/s"
)


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _elapsed(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer1/3B" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing {state} run report under {state_dir}")
    return reports[-1]


def _parse_bundle_digest(flag_path: Path) -> str:
    if not flag_path.exists():
        return ""
    raw = flag_path.read_text(encoding="ascii", errors="ignore").strip()
    prefix = "sha256_hex = "
    if not raw.startswith(prefix):
        return ""
    return raw[len(prefix) :].strip()


def _parse_last_s5_session(run_log_path: Path) -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in run_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "seg_3B.s5_validation_bundle" not in raw_line:
            continue
        ts = _parse_ts(raw_line)
        if ts is None:
            continue
        if S5_START_RE.search(raw_line):
            current = {
                "start_ts": ts,
                "sealed_ok_ts": None,
                "validate_s2_index_ts": None,
                "hash_audit_ts": None,
                "run_report_ts": None,
                "hash_progress": {},
            }
        if current is None:
            continue
        if S5_SEALED_OK_RE.search(raw_line):
            current["sealed_ok_ts"] = ts
        if S5_VALIDATE_S2_INDEX_RE.search(raw_line) and current.get("validate_s2_index_ts") is None:
            current["validate_s2_index_ts"] = ts
        if S5_HASH_AUDIT_RE.search(raw_line) and current.get("hash_audit_ts") is None:
            current["hash_audit_ts"] = ts
        progress = HASH_PROGRESS_RE.search(raw_line)
        if progress:
            label = str(progress.group("label"))
            done_str = progress.group("done")
            total_str = progress.group("total")
            processed_str = progress.group("processed")
            done = int(done_str) if done_str else int(processed_str or "0")
            total = int(total_str) if total_str else None
            current["hash_progress"][label] = {
                "timestamp": ts.isoformat(),
                "elapsed_s": float(progress.group("elapsed")),
                "rate_rows_per_s": float(progress.group("rate")),
                "done": done,
                "total": total,
            }
        if S5_RUN_REPORT_RE.search(raw_line):
            current["run_report_ts"] = ts
            sessions.append(current)
            current = None

    if not sessions:
        raise RuntimeError(f"No completed S5 sessions found in run log: {run_log_path}")
    return sessions[-1]


def _build_table(session: dict[str, Any], s5_wall_s: float) -> list[dict[str, Any]]:
    hash_progress = session.get("hash_progress") or {}
    hash_trace = hash_progress.get("rng_trace_log")
    hash_jitter = hash_progress.get("rng_event_edge_jitter")
    hash_tile = hash_progress.get("rng_event_edge_tile_assign")

    sealed_ok_ts = session.get("sealed_ok_ts")
    validate_s2_index_ts = session.get("validate_s2_index_ts")
    hash_audit_ts = session.get("hash_audit_ts")
    run_report_ts = session.get("run_report_ts")
    jitter_ts = (
        datetime.fromisoformat(str(hash_jitter["timestamp"]))
        if hash_jitter and hash_jitter.get("timestamp")
        else None
    )
    trace_ts = (
        datetime.fromisoformat(str(hash_trace["timestamp"]))
        if hash_trace and hash_trace.get("timestamp")
        else None
    )
    tile_ts = (
        datetime.fromisoformat(str(hash_tile["timestamp"]))
        if hash_tile and hash_tile.get("timestamp")
        else None
    )
    hash_end_ts = jitter_ts or tile_ts or trace_ts
    bundle_publish_finalize_s = _elapsed(hash_end_ts, run_report_ts)

    table = [
        ("validate_s1_s4_inputs", _elapsed(sealed_ok_ts, validate_s2_index_ts)),
        ("validate_s2_edges_index", _elapsed(validate_s2_index_ts, hash_audit_ts)),
        ("hash_rng_trace_log", float(hash_trace["elapsed_s"]) if hash_trace else None),
        ("hash_rng_event_edge_jitter", float(hash_jitter["elapsed_s"]) if hash_jitter else None),
        ("bundle_publish_finalize", bundle_publish_finalize_s),
    ]

    rows: list[dict[str, Any]] = []
    for lane, seconds in table:
        share = (float(seconds) / s5_wall_s) if seconds is not None and s5_wall_s > 0 else None
        rows.append(
            {
                "lane": lane,
                "seconds": seconds,
                "hms": _fmt_hms(seconds),
                "share_of_s5_wall": share,
            }
        )
    return rows


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lane = payload["lane_timing"]
    throughput = payload["throughput"]
    checks = payload["quality_checks"]
    lines = [
        "# Segment 3B POPT.2 S5 Lane Timing",
        "",
        f"- run_id: `{payload['run']['run_id']}`",
        f"- baseline_authority: `{payload['run']['is_baseline_authority']}`",
        f"- s5_status: `{payload['run']['s5_status']}`",
        "",
        "## Lane Table",
        "",
        "| Lane | Seconds | HMS | Share of S5 wall |",
        "|---|---:|---:|---:|",
    ]
    for row in lane["table"]:
        sec = f"{row['seconds']:.3f}" if row["seconds"] is not None else "n/a"
        hms = row["hms"] or "n/a"
        share = f"{100.0 * float(row['share_of_s5_wall']):.2f}%" if row["share_of_s5_wall"] is not None else "n/a"
        lines.append(f"| {row['lane']} | {sec} | {hms} | {share} |")

    lines.extend(
        [
            "",
            "## Throughput",
            f"- hash_rng_trace_log: `{throughput['hash_rng_trace_log_rows_per_s']}` rows/s",
            f"- hash_rng_event_edge_jitter: `{throughput['hash_rng_event_edge_jitter_rows_per_s']}` rows/s",
            "",
            "## Checks",
            f"- lane_artifact_present: `{checks['lane_artifact_present']}`",
            f"- top2_hot_lanes_pinned: `{checks['top2_hot_lanes_pinned']}`",
            f"- read_only_overhead_estimate_s: `{payload['harness']['runtime_overhead_estimate_s']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 3B POPT.2 S5 lane timing artifact")
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

    run_log_path = run_root / f"run_log_{run_id}.log"
    if not run_log_path.exists():
        raise FileNotFoundError(f"Run log missing: {run_log_path}")
    session = _parse_last_s5_session(run_log_path)

    s5_report_path = _find_state_report(run_root, "S5")
    s5_report = _load_json(s5_report_path)
    s5_wall_s = float(s5_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0
    output = s5_report.get("output") or {}
    flag_rel = str(output.get("flag_path") or "")
    flag_path = (run_root / flag_rel) if flag_rel else Path("")
    bundle_digest = _parse_bundle_digest(flag_path) if flag_rel else ""

    table = _build_table(session, s5_wall_s)
    table_sorted = sorted(
        [row for row in table if row.get("seconds") is not None],
        key=lambda row: float(row["seconds"]),
        reverse=True,
    )
    top2 = [str(row["lane"]) for row in table_sorted[:2]]

    hash_progress = session.get("hash_progress") or {}
    trace = hash_progress.get("rng_trace_log") or {}
    jitter = hash_progress.get("rng_event_edge_jitter") or {}

    payload: dict[str, Any] = {
        "phase": "POPT.2.1",
        "segment": "3B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "baseline_run_id": args.baseline_run_id,
            "is_baseline_authority": run_id == args.baseline_run_id,
            "run_log_path": str(run_log_path).replace("\\", "/"),
            "s5_run_report_path": str(s5_report_path).replace("\\", "/"),
            "s5_status": str(s5_report.get("status") or ""),
            "s5_wall_s": s5_wall_s,
            "s5_wall_hms": _fmt_hms(s5_wall_s),
            "output": output,
            "bundle_digest_from_flag": bundle_digest,
        },
        "markers": {
            "start_ts": session.get("start_ts").isoformat() if session.get("start_ts") else None,
            "sealed_ok_ts": session.get("sealed_ok_ts").isoformat() if session.get("sealed_ok_ts") else None,
            "validate_s2_index_ts": (
                session.get("validate_s2_index_ts").isoformat() if session.get("validate_s2_index_ts") else None
            ),
            "hash_audit_ts": session.get("hash_audit_ts").isoformat() if session.get("hash_audit_ts") else None,
            "run_report_ts": session.get("run_report_ts").isoformat() if session.get("run_report_ts") else None,
        },
        "hash_progress": hash_progress,
        "lane_timing": {
            "table": table,
            "top2_hot_lanes": top2,
        },
        "throughput": {
            "hash_rng_trace_log_rows_per_s": trace.get("rate_rows_per_s"),
            "hash_rng_event_edge_jitter_rows_per_s": jitter.get("rate_rows_per_s"),
        },
        "harness": {
            "mode": "read_only_log_report_parser",
            "runtime_overhead_estimate_s": 0.0,
            "notes": "No engine code changes required for profiling pass.",
        },
        "quality_checks": {
            "lane_artifact_present": True,
            "top2_hot_lanes_pinned": len(top2) >= 2,
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3b_popt2_s5_lane_timing_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt2_s5_lane_timing_{run_id}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
