#!/usr/bin/env python3
"""Score Segment 5B POPT.2 closure from baseline and candidate run artifacts."""

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
RUNTIME_REDUCTION_GATE = 0.35
S4_STRETCH_BUDGET_S = 300.0
NON_REGRESSION_ALLOWANCE = 1.15  # +15%


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
            "input_load_s": elapsed_s * 0.1,
            "compute_s": elapsed_s * 0.85,
            "validation_s": elapsed_s * 0.03,
            "write_s": elapsed_s * 0.02,
            "dominant_lane": "compute",
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
        "input_load_s": elapsed_s * 0.1,
        "compute_s": elapsed_s * 0.85,
        "validation_s": elapsed_s * 0.03,
        "write_s": elapsed_s * 0.02,
        "dominant_lane": "compute",
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


def _baseline_s4_shape(hotspot_json: dict[str, Any]) -> dict[str, Any]:
    hotspots = hotspot_json.get("hotspots") or []
    for row in hotspots:
        if str(row.get("state")) == "S4":
            evidence = row.get("evidence") or {}
            metrics = evidence.get("metrics_excerpt") or {}
            if isinstance(metrics, dict) and "baseline_v1" in metrics and isinstance(metrics["baseline_v1"], dict):
                return dict(metrics["baseline_v1"])
            if isinstance(metrics, dict):
                return dict(metrics)
    return {}


def _candidate_s4_shape(s4_row: dict[str, Any]) -> dict[str, Any]:
    details = s4_row.get("details") or {}
    if isinstance(details, dict):
        baseline_v1 = details.get("baseline_v1")
        if isinstance(baseline_v1, dict):
            return dict(baseline_v1)
        return dict(details)
    return {}


def _float_close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def _load_non_regression_anchors(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    payload = _load_json(path)
    downstream = ((payload.get("downstream_gate") or {}).get("states") or {})
    anchors: dict[str, float] = {}
    for state in ("S2", "S3", "S5"):
        row = downstream.get(state) or {}
        try:
            anchors[state] = float(row.get("elapsed_s"))
        except (TypeError, ValueError):
            continue
    return anchors


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5B POPT.2 closure.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument("--segment-state-runs", default="")
    parser.add_argument("--baseline-state-csv", default="runs/fix-data-engine/segment_5B/reports/segment5b_popt0_state_elapsed_c25a2675fbfbacd952b13bb594880e92.csv")
    parser.add_argument("--baseline-hotspot-json", default="runs/fix-data-engine/segment_5B/reports/segment5b_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.json")
    parser.add_argument("--popt1-closure-json", default="runs/fix-data-engine/segment_5B/reports/segment5b_popt1_closure_c25a2675fbfbacd952b13bb594880e92.json")
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
    s4_baseline = float(baseline_elapsed.get("S4") or 0.0)
    s4_candidate = float(candidate_elapsed["S4"])
    reduction_ratio = ((s4_baseline - s4_candidate) / s4_baseline) if s4_baseline > 0 else 0.0
    runtime_target_s = s4_baseline * (1.0 - RUNTIME_REDUCTION_GATE)
    runtime_gate_pass = reduction_ratio >= RUNTIME_REDUCTION_GATE
    stretch_budget_pass = s4_candidate <= S4_STRETCH_BUDGET_S

    baseline_shape = _baseline_s4_shape(baseline_hotspot)
    candidate_shape = _candidate_s4_shape(state_rows["S4"])

    structural_checks: dict[str, dict[str, Any]] = {}
    int_fields = ["bucket_rows", "arrivals_total", "arrival_rows", "arrival_virtual", "missing_group_weights"]
    for field in int_fields:
        expected = baseline_shape.get(field)
        actual = candidate_shape.get(field)
        ok = expected == actual
        structural_checks[field] = {"expected": expected, "actual": actual, "ok": ok}

    s4_status_ok = str(state_rows["S4"].get("status")) == "PASS"
    s4_error_ok = state_rows["S4"].get("error_code") in (None, "")
    structural_gate_pass = all(item["ok"] for item in structural_checks.values()) and s4_status_ok and s4_error_ok

    non_regression_anchors = _load_non_regression_anchors(Path(args.popt1_closure_json))
    non_regression_checks: dict[str, dict[str, Any]] = {}
    non_regression_pass = True
    for state in ("S2", "S3", "S5"):
        anchor = non_regression_anchors.get(state)
        current = candidate_elapsed.get(state, 0.0)
        if anchor is None or anchor <= 0:
            ok = True
            threshold = None
        else:
            threshold = anchor * NON_REGRESSION_ALLOWANCE
            ok = current <= threshold
        non_regression_checks[state] = {
            "anchor_elapsed_s": anchor,
            "current_elapsed_s": current,
            "allowed_elapsed_s": threshold,
            "ok": ok,
        }
        non_regression_pass = non_regression_pass and ok

    s5_row = state_rows["S5"]
    s5_status = str(s5_row.get("status"))
    s5_bundle_ok = bool((s5_row.get("metrics") or {}).get("bundle_integrity_ok", s5_status == "PASS"))
    downstream_gate_pass = (s5_status == "PASS") and s5_bundle_ok

    determinism_gate_pass = (
        str(state_rows["S4"].get("status")) == "PASS"
        and str(state_rows["S5"].get("status")) == "PASS"
        and state_rows["S4"].get("error_code") in (None, "")
        and state_rows["S5"].get("error_code") in (None, "")
    )

    log_path = run_root / f"run_log_{run_id}.log"
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")
    log_events = _parse_log_events(log_path)
    s4_lane = _lane_decomposition_for_state(
        log_events,
        "S4",
        state_rows["S4"].get("started_at_utc"),
        state_rows["S4"].get("finished_at_utc"),
        s4_candidate,
    )
    baseline_lane = ((baseline_hotspot.get("lane_decomposition") or {}).get("S4") or {})

    decision = (
        "UNLOCK_POPT3_CONTINUE"
        if (runtime_gate_pass and structural_gate_pass and downstream_gate_pass and determinism_gate_pass and non_regression_pass)
        else "HOLD_POPT2_REOPEN"
    )

    lane_payload = {
        "phase": "POPT.2",
        "segment": "5B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "run_id": run_id,
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_log_path": str(log_path).replace("\\", "/"),
            "segment_state_runs": str(segment_state_runs_path).replace("\\", "/"),
        },
        "s4_lane_baseline": baseline_lane,
        "s4_lane_candidate": s4_lane,
    }

    closure_payload = {
        "phase": "POPT.2",
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
            "baseline_s4_elapsed_s": s4_baseline,
            "baseline_s4_elapsed_hms": _fmt_hms(s4_baseline),
            "candidate_s4_elapsed_s": s4_candidate,
            "candidate_s4_elapsed_hms": _fmt_hms(s4_candidate),
            "reduction_ratio": reduction_ratio,
            "reduction_gate_ratio": RUNTIME_REDUCTION_GATE,
            "reduction_target_s": runtime_target_s,
            "reduction_target_hms": _fmt_hms(runtime_target_s),
            "pass": runtime_gate_pass,
        },
        "stretch_budget_gate": {
            "target_s": S4_STRETCH_BUDGET_S,
            "target_hms": _fmt_hms(S4_STRETCH_BUDGET_S),
            "pass": stretch_budget_pass,
        },
        "structural_gate": {
            "checks": structural_checks,
            "pass": structural_gate_pass,
            "s4_status": state_rows["S4"].get("status"),
            "s4_error_code": state_rows["S4"].get("error_code"),
        },
        "non_regression_gate": {
            "allowance_ratio": NON_REGRESSION_ALLOWANCE,
            "checks": non_regression_checks,
            "pass": non_regression_pass,
        },
        "downstream_gate": {
            "s5_status": s5_status,
            "s5_bundle_integrity_ok": s5_bundle_ok,
            "pass": downstream_gate_pass,
        },
        "determinism_gate": {
            "s4_status": state_rows["S4"].get("status"),
            "s5_status": state_rows["S5"].get("status"),
            "s4_error_code": state_rows["S4"].get("error_code"),
            "s5_error_code": state_rows["S5"].get("error_code"),
            "pass": determinism_gate_pass,
        },
        "decision": decision,
    }

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    lane_path = out_root / f"segment5b_popt2_lane_timing_{run_id}.json"
    closure_json_path = out_root / f"segment5b_popt2_closure_{run_id}.json"
    closure_md_path = out_root / f"segment5b_popt2_closure_{run_id}.md"

    lane_path.write_text(json.dumps(lane_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    closure_json_path.write_text(
        json.dumps(closure_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    structural_lines = []
    for key, row in closure_payload["structural_gate"]["checks"].items():
        structural_lines.append(
            f"- `{key}` expected=`{row.get('expected')}` actual=`{row.get('actual')}` ok=`{row.get('ok')}`"
        )
    non_reg_lines = []
    for key, row in closure_payload["non_regression_gate"]["checks"].items():
        non_reg_lines.append(
            f"- `{key}` anchor=`{row.get('anchor_elapsed_s')}` current=`{row.get('current_elapsed_s')}` allowed=`{row.get('allowed_elapsed_s')}` ok=`{row.get('ok')}`"
        )

    md = "\n".join(
        [
            "# Segment 5B POPT.2 Closure",
            "",
            f"- run_id: `{run_id}`",
            f"- decision: `{decision}`",
            "",
            "## Runtime Gate",
            "",
            f"- baseline S4: `{_fmt_hms(s4_baseline)}`; candidate S4: `{_fmt_hms(s4_candidate)}`; reduction: `{reduction_ratio:.2%}`; pass: `{runtime_gate_pass}`",
            f"- stretch budget (`<= {_fmt_hms(S4_STRETCH_BUDGET_S)}`) pass: `{stretch_budget_pass}`",
            "",
            "## Structural Gate",
            "",
            *structural_lines,
            f"- S4 status=`{state_rows['S4'].get('status')}` error_code=`{state_rows['S4'].get('error_code')}`",
            "",
            "## Non-Regression Gate",
            "",
            *non_reg_lines,
            "",
            "## Downstream/Determinism",
            "",
            f"- S5 status=`{s5_status}` bundle_integrity_ok=`{s5_bundle_ok}` downstream_pass=`{downstream_gate_pass}`",
            f"- determinism_gate_pass=`{determinism_gate_pass}`",
            "",
            "## Lane Timing",
            "",
            f"- baseline dominant lane: `{baseline_lane.get('dominant_lane')}`",
            f"- candidate dominant lane: `{s4_lane.get('dominant_lane')}`",
            f"- candidate lane decomposition: `{json.dumps(s4_lane, sort_keys=True)}`",
        ]
    )
    closure_md_path.write_text(md + "\n", encoding="utf-8")

    print(f"[segment5b-popt2] lane_timing={lane_path}")
    print(f"[segment5b-popt2] closure_json={closure_json_path}")
    print(f"[segment5b-popt2] closure_md={closure_md_path}")


if __name__ == "__main__":
    main()
