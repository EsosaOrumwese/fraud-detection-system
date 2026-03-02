#!/usr/bin/env python3
"""Emit Segment 3B S5 log-budget artifact for POPT.3.1 (read-only harness)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
SEVERITY_RE = re.compile(r"\[(INFO|WARNING|ERROR|DEBUG)\]")
S5_START_RE = re.compile(r"S5: run log initialized")
S5_RUN_REPORT_RE = re.compile(r"S5: run-report written")
S5_PROGRESS_RE = re.compile(r"S5: hash [a-zA-Z0-9_]+\s+(?:\d+/\d+|processed=\d+)\s+\(elapsed=")
S5_VALIDATOR_BACKEND_RE = re.compile(r"validator_backend=")


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


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


def _parse_last_s5_session_lines(run_log_path: Path) -> dict[str, Any]:
    sessions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in run_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "seg_3B.s5_validation_bundle" not in raw_line:
            continue
        ts = _parse_ts(raw_line)
        if ts is None:
            continue
        if S5_START_RE.search(raw_line):
            current = {"start_ts": ts, "run_report_ts": None, "lines": []}
        if current is None:
            continue
        current["lines"].append(raw_line)
        if S5_RUN_REPORT_RE.search(raw_line):
            current["run_report_ts"] = ts
            sessions.append(current)
            current = None

    if not sessions:
        raise RuntimeError(f"No completed S5 sessions found in run log: {run_log_path}")
    return sessions[-1]


def _severity_counts(lines: list[str]) -> dict[str, int]:
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "DEBUG": 0}
    for line in lines:
        match = SEVERITY_RE.search(line)
        if not match:
            continue
        counts[match.group(1)] += 1
    return counts


def _required_presence(lines: list[str]) -> dict[str, bool]:
    return {
        "objective_header": any("S5: objective=" in line for line in lines),
        "sealed_inputs_validated": any("S5: sealed inputs validated and required policy digests verified" in line for line in lines),
        "bundle_complete": any("S5: bundle complete" in line for line in lines),
        "run_report_written": any("S5: run-report written" in line for line in lines),
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    required = payload["required_presence"]
    severity = payload["severity_counts"]
    lines = [
        "# Segment 3B POPT.3 Log Budget",
        "",
        f"- run_id: `{payload['run']['run_id']}`",
        f"- s5_status: `{payload['run']['s5_status']}`",
        f"- s5_wall_s: `{payload['run']['s5_wall_s']}`",
        "",
        "## Volume",
        f"- total_lines: `{counts['total_lines']}`",
        f"- total_bytes_approx: `{counts['total_bytes_approx']}`",
        f"- progress_lines: `{counts['progress_lines']}`",
        f"- validator_backend_lines: `{counts['validator_backend_lines']}`",
        "",
        "## Severity",
        f"- INFO: `{severity['INFO']}`",
        f"- WARNING: `{severity['WARNING']}`",
        f"- ERROR: `{severity['ERROR']}`",
        f"- DEBUG: `{severity['DEBUG']}`",
        "",
        "## Required Narrative",
        f"- objective_header: `{required['objective_header']}`",
        f"- sealed_inputs_validated: `{required['sealed_inputs_validated']}`",
        f"- bundle_complete: `{required['bundle_complete']}`",
        f"- run_report_written: `{required['run_report_written']}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 3B POPT.3 log-budget artifact")
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
    session = _parse_last_s5_session_lines(run_log_path)
    lines = list(session.get("lines") or [])

    s5_report_path = _find_state_report(run_root, "S5")
    s5_report = _load_json(s5_report_path)
    s5_wall_s = float(s5_report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0
    output = s5_report.get("output") or {}
    flag_rel = str(output.get("flag_path") or "")
    flag_path = (run_root / flag_rel) if flag_rel else Path("")
    bundle_digest = _parse_bundle_digest(flag_path) if flag_rel else ""

    severity = _severity_counts(lines)
    required = _required_presence(lines)
    total_bytes = sum(len(line.encode("utf-8", errors="ignore")) + 1 for line in lines)
    progress_lines = sum(1 for line in lines if S5_PROGRESS_RE.search(line))
    validator_backend_lines = sum(1 for line in lines if S5_VALIDATOR_BACKEND_RE.search(line))

    payload: dict[str, Any] = {
        "phase": "POPT.3.1",
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
            "output": output,
            "bundle_digest_from_flag": bundle_digest,
            "session_start_ts": session.get("start_ts").isoformat() if session.get("start_ts") else None,
            "session_end_ts": session.get("run_report_ts").isoformat() if session.get("run_report_ts") else None,
        },
        "counts": {
            "total_lines": len(lines),
            "total_bytes_approx": int(total_bytes),
            "progress_lines": int(progress_lines),
            "validator_backend_lines": int(validator_backend_lines),
        },
        "severity_counts": severity,
        "required_presence": required,
        "quality_checks": {
            "required_narrative_present": all(required.values()),
            "log_artifact_present": True,
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3b_popt3_log_budget_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt3_log_budget_{run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
