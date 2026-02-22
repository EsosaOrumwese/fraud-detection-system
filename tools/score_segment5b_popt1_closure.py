#!/usr/bin/env python3
"""Score Segment 5B POPT.1 closure from baseline and candidate run artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[[A-Z]+\] ([^:]+): (.*)$")
MODULE_STATE_RE = re.compile(r"engine\.layers\.l2\.seg_5B\.s([0-5])_")

STATE_ORDER = ["S1", "S2", "S3", "S4", "S5"]
S1_TARGET_S = 90.0
S1_REDUCTION_GATE = 0.40  # 40%


@dataclass(frozen=True)
class LogEvent:
    ts: datetime
    module: str
    message: str


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _parse_iso_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _find_latest_segment_state_runs(run_root: Path) -> Path:
    candidates = sorted(
        run_root.glob("reports/layer2/segment_state_runs/segment=5B/utc_day=*/segment_state_runs.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(
            "Missing 5B segment_state_runs under "
            f"{run_root / 'reports/layer2/segment_state_runs/segment=5B'}"
        )
    return candidates[-1]


def _extract_latest_state_row(records: list[dict[str, Any]], state: str) -> dict[str, Any]:
    rows = [row for row in records if str(row.get("state")) == state]
    if not rows:
        raise ValueError(f"No state rows found for {state}")
    pass_rows = [row for row in rows if str(row.get("status")) == "PASS"]
    source = pass_rows if pass_rows else rows
    return sorted(source, key=lambda r: (str(r.get("finished_at_utc") or ""), str(r.get("started_at_utc") or "")))[-1]


def _elapsed_s_from_row(row: dict[str, Any]) -> float:
    durations = row.get("durations") or {}
    wall_ms = durations.get("wall_ms")
    if wall_ms is not None:
        try:
            return float(wall_ms) / 1000.0
        except (TypeError, ValueError):
            pass
    started = _parse_iso_ts(row.get("started_at_utc"))
    finished = _parse_iso_ts(row.get("finished_at_utc"))
    if started and finished:
        delta = (finished - started).total_seconds()
        if delta >= 0:
            return float(delta)
    return 0.0


def _parse_log_events(path: Path) -> list[LogEvent]:
    events: list[LogEvent] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue
        parsed = LOG_LINE_RE.match(line)
        if not parsed:
            continue
        events.append(LogEvent(ts=ts, module=parsed.group(1), message=parsed.group(2)))
    return events


def _lane_for_message(message: str) -> str:
    text = message.lower()
    if any(token in text for token in ("publish", "published", "write", "written", "bundle", "index", "digest", "_passed.flag")):
        return "write"
    if any(token in text for token in ("validate", "validated", "validation", "gate", "schema", "mismatch", "audit")):
        return "validation"
    if any(token in text for token in ("load", "loaded", "scan", "scanning", "read", "resolve", "contract", "policy", "manifest", "input", "receipt", "sealed")):
        return "input_load"
    return "compute"


def _lane_decomposition_for_state(events: list[LogEvent], state: str, started_at_utc: str | None, finished_at_utc: str | None, elapsed_s: float) -> dict[str, Any]:
    started = _parse_iso_ts(started_at_utc)
    finished = _parse_iso_ts(finished_at_utc)
    lanes = {"input_load": 0.0, "compute": 0.0, "validation": 0.0, "write": 0.0}
    if started is None or finished is None or finished <= started:
        return {
            "source": "fallback_no_window",
            "input_load_s": elapsed_s * 0.7,
            "compute_s": elapsed_s * 0.2,
            "validation_s": elapsed_s * 0.08,
            "write_s": elapsed_s * 0.02,
            "dominant_lane": "input_load",
        }

    state_events = []
    wanted = state[1:]
    for event in events:
        match = MODULE_STATE_RE.search(event.module)
        if not (match and match.group(1) == wanted):
            continue
        if started <= event.ts <= finished:
            state_events.append(event)

    if len(state_events) >= 2:
        for cur, nxt in zip(state_events, state_events[1:]):
            delta = (nxt.ts - cur.ts).total_seconds()
            if delta <= 0:
                continue
            lanes[_lane_for_message(cur.message)] += delta
        tail = (finished - state_events[-1].ts).total_seconds()
        if tail > 0:
            lanes[_lane_for_message(state_events[-1].message)] += tail
        raw_total = sum(lanes.values())
        if raw_total > 0:
            scale = elapsed_s / raw_total if elapsed_s > 0 else 1.0
            scaled = {k: v * scale for k, v in lanes.items()}
            return {
                "source": "derived_from_log_events",
                "input_load_s": scaled["input_load"],
                "compute_s": scaled["compute"],
                "validation_s": scaled["validation"],
                "write_s": scaled["write"],
                "dominant_lane": max(scaled, key=scaled.get),
            }

    return {
        "source": "fallback_weighted",
        "input_load_s": elapsed_s * 0.7,
        "compute_s": elapsed_s * 0.2,
        "validation_s": elapsed_s * 0.08,
        "write_s": elapsed_s * 0.02,
        "dominant_lane": "input_load",
    }


def _read_baseline_elapsed(csv_path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            state = str(row.get("state") or "")
            if not state:
                continue
            out[state] = float(row.get("elapsed_s") or 0.0)
    return out


def _baseline_s1_shape(hotspot_json: dict[str, Any]) -> dict[str, Any]:
    hotspots = hotspot_json.get("hotspots") or []
    for row in hotspots:
        if str(row.get("state")) == "S1":
            evidence = row.get("evidence") or {}
            metrics = evidence.get("metrics_excerpt") or {}
            if isinstance(metrics, dict) and "baseline_v1" in metrics and isinstance(metrics["baseline_v1"], dict):
                return dict(metrics["baseline_v1"])
            if isinstance(metrics, dict):
                return dict(metrics)
    return {}


def _candidate_s1_shape(s1_row: dict[str, Any]) -> dict[str, Any]:
    details = s1_row.get("details") or {}
    if isinstance(details, dict):
        baseline_v1 = details.get("baseline_v1")
        if isinstance(baseline_v1, dict):
            return dict(baseline_v1)
        return dict(details)
    return {}


def _float_close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5B POPT.1 closure.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument("--segment-state-runs", default="")
    parser.add_argument("--baseline-state-csv", default="runs/fix-data-engine/segment_5B/reports/segment5b_popt0_state_elapsed_c25a2675fbfbacd952b13bb594880e92.csv")
    parser.add_argument("--baseline-hotspot-json", default="runs/fix-data-engine/segment_5B/reports/segment5b_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.json")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    segment_state_runs_path = (
        Path(args.segment_state_runs)
        if args.segment_state_runs.strip()
        else _find_latest_segment_state_runs(run_root)
    )
    records = _load_jsonl(segment_state_runs_path)
    state_rows = {state: _extract_latest_state_row(records, state) for state in STATE_ORDER}

    baseline_elapsed = _read_baseline_elapsed(Path(args.baseline_state_csv))
    baseline_hotspot = _load_json(Path(args.baseline_hotspot_json))

    candidate_elapsed = {state: _elapsed_s_from_row(row) for state, row in state_rows.items()}
    s1_baseline = float(baseline_elapsed.get("S1") or 0.0)
    s1_candidate = float(candidate_elapsed["S1"])
    reduction_ratio = ((s1_baseline - s1_candidate) / s1_baseline) if s1_baseline > 0 else 0.0
    runtime_gate_pass = (s1_candidate <= S1_TARGET_S) or (reduction_ratio >= S1_REDUCTION_GATE)

    baseline_shape = _baseline_s1_shape(baseline_hotspot)
    candidate_shape = _candidate_s1_shape(state_rows["S1"])

    structural_checks: dict[str, dict[str, Any]] = {}
    int_fields = ["bucket_count", "group_id_count", "grouping_row_count"]
    float_fields = ["max_group_share", "median_members_per_group", "multi_member_fraction"]
    for field in int_fields:
        expected = baseline_shape.get(field)
        actual = candidate_shape.get(field)
        ok = (expected == actual)
        structural_checks[field] = {"expected": expected, "actual": actual, "ok": ok}
    for field in float_fields:
        expected = baseline_shape.get(field)
        actual = candidate_shape.get(field)
        if expected is None or actual is None:
            ok = (expected == actual)
        else:
            ok = _float_close(float(expected), float(actual), tol=1e-9)
        structural_checks[field] = {"expected": expected, "actual": actual, "ok": ok}

    s1_status_ok = str(state_rows["S1"].get("status")) == "PASS"
    s1_error_ok = state_rows["S1"].get("error_code") in (None, "")
    structural_gate_pass = all(item["ok"] for item in structural_checks.values()) and s1_status_ok and s1_error_ok

    downstream: dict[str, dict[str, Any]] = {}
    downstream_pass = True
    for state in ["S2", "S3", "S4", "S5"]:
        status = str(state_rows[state].get("status"))
        ok = status == "PASS"
        downstream[state] = {"status": status, "ok": ok, "elapsed_s": candidate_elapsed[state], "elapsed_hms": _fmt_hms(candidate_elapsed[state])}
        downstream_pass = downstream_pass and ok

    log_path = run_root / f"run_log_{run_id}.log"
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")
    log_events = _parse_log_events(log_path)
    s1_lane = _lane_decomposition_for_state(
        log_events,
        "S1",
        state_rows["S1"].get("started_at_utc"),
        state_rows["S1"].get("finished_at_utc"),
        s1_candidate,
    )
    baseline_lane = ((baseline_hotspot.get("lane_decomposition") or {}).get("S1") or {})

    decision = "UNLOCK_POPT2_CONTINUE" if (runtime_gate_pass and structural_gate_pass and downstream_pass) else "HOLD_POPT1_REOPEN"

    lane_payload = {
        "phase": "POPT.1",
        "segment": "5B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "run_id": run_id,
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_log_path": str(log_path).replace("\\", "/"),
            "segment_state_runs": str(segment_state_runs_path).replace("\\", "/"),
        },
        "s1_lane_baseline": baseline_lane,
        "s1_lane_candidate": s1_lane,
    }

    closure_payload = {
        "phase": "POPT.1",
        "segment": "5B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "run_id": run_id,
            "seed": int(receipt.get("seed")),
            "parameter_hash": receipt.get("parameter_hash"),
            "manifest_fingerprint": receipt.get("manifest_fingerprint"),
            "runs_root": str(runs_root).replace("\\", "/"),
            "segment_state_runs": str(segment_state_runs_path).replace("\\", "/"),
        },
        "runtime_gate": {
            "baseline_s1_elapsed_s": s1_baseline,
            "baseline_s1_elapsed_hms": _fmt_hms(s1_baseline),
            "candidate_s1_elapsed_s": s1_candidate,
            "candidate_s1_elapsed_hms": _fmt_hms(s1_candidate),
            "reduction_ratio": reduction_ratio,
            "target_s": S1_TARGET_S,
            "target_hms": _fmt_hms(S1_TARGET_S),
            "reduction_gate_ratio": S1_REDUCTION_GATE,
            "pass": runtime_gate_pass,
        },
        "structural_gate": {
            "s1_status": state_rows["S1"].get("status"),
            "s1_error_code": state_rows["S1"].get("error_code"),
            "checks": structural_checks,
            "pass": structural_gate_pass,
        },
        "downstream_gate": {
            "states": downstream,
            "pass": downstream_pass,
        },
        "decision": decision,
    }

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    lane_json = out_root / f"segment5b_popt1_lane_timing_{run_id}.json"
    closure_json = out_root / f"segment5b_popt1_closure_{run_id}.json"
    closure_md = out_root / f"segment5b_popt1_closure_{run_id}.md"

    lane_json.write_text(json.dumps(lane_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    closure_json.write_text(json.dumps(closure_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Segment 5B POPT.1 Closure")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- decision: `{decision}`")
    lines.append("")
    lines.append("## Runtime Gate")
    lines.append("")
    lines.append(
        f"- baseline S1: `{_fmt_hms(s1_baseline)}`; candidate S1: `{_fmt_hms(s1_candidate)}`; "
        f"reduction: `{reduction_ratio * 100:.2f}%`; pass: `{runtime_gate_pass}`"
    )
    lines.append("")
    lines.append("## Structural Gate")
    lines.append("")
    for field, row in structural_checks.items():
        lines.append(
            f"- `{field}` expected=`{row['expected']}` actual=`{row['actual']}` ok=`{row['ok']}`"
        )
    lines.append(f"- S1 status=`{state_rows['S1'].get('status')}` error_code=`{state_rows['S1'].get('error_code')}`")
    lines.append("")
    lines.append("## Downstream Gate")
    lines.append("")
    for state in ["S2", "S3", "S4", "S5"]:
        row = downstream[state]
        lines.append(f"- `{state}` status=`{row['status']}` elapsed=`{row['elapsed_hms']}` ok=`{row['ok']}`")
    lines.append("")
    lines.append("## Lane Timing")
    lines.append("")
    lines.append(f"- baseline dominant lane: `{(baseline_lane or {}).get('dominant_lane')}`")
    lines.append(f"- candidate dominant lane: `{s1_lane.get('dominant_lane')}`")
    lines.append(f"- candidate lane decomposition: `{json.dumps(s1_lane, sort_keys=True)}`")
    closure_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[segment5b-popt1] lane_timing={lane_json}")
    print(f"[segment5b-popt1] closure_json={closure_json}")
    print(f"[segment5b-popt1] closure_md={closure_md}")


if __name__ == "__main__":
    main()

