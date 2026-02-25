#!/usr/bin/env python3
"""Score Segment 6B POPT.2 closure from baseline, witness, and candidate evidence."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_ORDER = ["S4", "S5"]
BASELINE_S4_SECONDS = 563.20
TARGET_S4_SECONDS = 420.0
STRETCH_S4_SECONDS = 500.0
REQUIRED_CHECKS = (
    "REQ_UPSTREAM_HASHGATES",
    "REQ_SEALED_INPUTS_PRESENT",
    "REQ_PK_UNIQUENESS",
    "REQ_FLOW_EVENT_PARITY",
    "REQ_FLOW_LABEL_COVERAGE",
    "REQ_RNG_BUDGETS",
    "REQ_TIME_MONOTONE",
    "REQ_SCENARIO_OOB",
)
WARN_METRIC_PATHS = {
    "WARN_FRAUD_REALISM": "fraud_fraction_sample",
    "WARN_BANK_VIEW_REALISM": "bank_view_rate_sample",
    "WARN_CASE_REALISM": "case_event_rate",
}
TOLERANCE = 1e-12

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[[A-Z]+\] ([^:]+): (.*)$")
MODULE_STATE_RE = re.compile(r"engine\.layers\.l3\.seg_6B\.s([4-5])_")
ELAPSED_RE = re.compile(r"elapsed=([0-9]+(?:\.[0-9]+)?)s")


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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _parse_log_events(log_path: Path) -> list[LogEvent]:
    events: list[LogEvent] = []
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue
        parsed = LOG_LINE_RE.match(line)
        if not parsed:
            continue
        events.append(LogEvent(ts=ts, module=parsed.group(1), message=parsed.group(2)))
    return events


def _module_state(event: LogEvent) -> str | None:
    match = MODULE_STATE_RE.search(event.module)
    if not match:
        return None
    return f"S{match.group(1)}"


def _state_events(events: list[LogEvent], state: str) -> list[LogEvent]:
    return [event for event in events if _module_state(event) == state]


def _extract_elapsed(message: str) -> float | None:
    matches = ELAPSED_RE.findall(message)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def _completion_elapsed(events: list[LogEvent], state: str) -> float:
    candidates: list[float] = []
    fallback: list[float] = []
    for event in _state_events(events, state):
        elapsed = _extract_elapsed(event.message)
        if elapsed is None:
            continue
        fallback.append(elapsed)
        if "completed" in event.message.lower():
            candidates.append(elapsed)
    if candidates:
        return float(candidates[-1])
    if fallback:
        return float(fallback[-1])
    if not candidates and not fallback:
        raise ValueError(f"Missing completion elapsed for {state}.")
    return 0.0


def _ensure_ascii(path: Path) -> str:
    return str(path).replace("\\", "/")


def _report_path(run_root: Path, manifest_fingerprint: str) -> Path:
    return (
        run_root
        / "data/layer3/6B/validation"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s5_validation_report_6B.json"
    )


def _checks_by_id(report_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = report_payload.get("checks")
    checks = checks if isinstance(checks, list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in checks:
        if not isinstance(row, dict):
            continue
        key = row.get("check_id")
        if isinstance(key, str) and key:
            out[key] = row
    return out


def _warn_metrics(checks: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for check_id, metric_key in WARN_METRIC_PATHS.items():
        row = checks.get(check_id) or {}
        metrics = row.get("metrics") if isinstance(row, dict) else {}
        value = metrics.get(metric_key) if isinstance(metrics, dict) else None
        try:
            out[check_id] = float(value) if value is not None else None
        except (TypeError, ValueError):
            out[check_id] = None
    return out


def _required_results(checks: dict[str, dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for check_id in REQUIRED_CHECKS:
        row = checks.get(check_id) or {}
        result = row.get("result") if isinstance(row, dict) else None
        out[check_id] = str(result or "MISSING")
    return out


def _required_pass(required_results: dict[str, str]) -> bool:
    return all(value == "PASS" for value in required_results.values())


def _parity_counts(checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    parity_row = checks.get("REQ_FLOW_EVENT_PARITY") or {}
    metrics = parity_row.get("metrics") if isinstance(parity_row, dict) else {}
    counts = metrics.get("counts") if isinstance(metrics, dict) else {}
    return counts if isinstance(counts, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 6B POPT.2 closure.")
    parser.add_argument("--baseline-runs-root", default="runs/local_full_run-5")
    parser.add_argument("--baseline-run-id", default="c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--witness-runs-root", default="runs/fix-data-engine/segment_6B")
    parser.add_argument("--witness-run-id", default="51496f8e24244f24a44077c57217b1ab")
    parser.add_argument("--candidate-runs-root", default="runs/fix-data-engine/segment_6B")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_6B/reports")
    args = parser.parse_args()

    baseline_runs_root = Path(args.baseline_runs_root)
    witness_runs_root = Path(args.witness_runs_root)
    candidate_runs_root = Path(args.candidate_runs_root)
    baseline_run_root = baseline_runs_root / args.baseline_run_id
    witness_run_root = witness_runs_root / args.witness_run_id
    candidate_run_root = candidate_runs_root / args.candidate_run_id
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    baseline_receipt = _load_json(baseline_run_root / "run_receipt.json")
    witness_receipt = _load_json(witness_run_root / "run_receipt.json")
    candidate_receipt = _load_json(candidate_run_root / "run_receipt.json")

    baseline_log = baseline_run_root / f"run_log_{args.baseline_run_id}.log"
    candidate_log = candidate_run_root / f"run_log_{args.candidate_run_id}.log"
    baseline_events = _parse_log_events(baseline_log)
    candidate_events = _parse_log_events(candidate_log)

    baseline_elapsed = {state: _completion_elapsed(baseline_events, state) for state in STATE_ORDER}
    candidate_elapsed = {state: _completion_elapsed(candidate_events, state) for state in STATE_ORDER}
    baseline_lane_elapsed = float(sum(baseline_elapsed.values()))
    candidate_lane_elapsed = float(sum(candidate_elapsed.values()))

    baseline_s4 = float(baseline_elapsed["S4"])
    candidate_s4 = float(candidate_elapsed["S4"])
    s4_reduction = ((baseline_s4 - candidate_s4) / baseline_s4) if baseline_s4 > 0 else 0.0

    witness_manifest = str(witness_receipt.get("manifest_fingerprint") or "")
    candidate_manifest = str(candidate_receipt.get("manifest_fingerprint") or "")
    witness_report = _load_json(_report_path(witness_run_root, witness_manifest))
    candidate_report = _load_json(_report_path(candidate_run_root, candidate_manifest))

    witness_checks = _checks_by_id(witness_report)
    candidate_checks = _checks_by_id(candidate_report)
    witness_required = _required_results(witness_checks)
    candidate_required = _required_results(candidate_checks)
    witness_required_pass = _required_pass(witness_required)
    candidate_required_pass = _required_pass(candidate_required)

    witness_warn = _warn_metrics(witness_checks)
    candidate_warn = _warn_metrics(candidate_checks)
    warn_delta: dict[str, float | None] = {}
    warn_stable = True
    for check_id in WARN_METRIC_PATHS:
        left = witness_warn.get(check_id)
        right = candidate_warn.get(check_id)
        if left is None or right is None:
            warn_delta[check_id] = None
            continue
        delta = float(right - left)
        warn_delta[check_id] = delta
        if abs(delta) > TOLERANCE:
            warn_stable = False

    witness_counts = _parity_counts(witness_checks)
    candidate_counts = _parity_counts(candidate_checks)
    counts_stable = witness_counts == candidate_counts

    runtime_reduction_pass = s4_reduction >= 0.30
    runtime_target_pass = candidate_s4 <= TARGET_S4_SECONDS
    runtime_stretch_pass = candidate_s4 <= STRETCH_S4_SECONDS
    non_regression_pass = witness_required_pass and candidate_required_pass and counts_stable and warn_stable

    decision = (
        "UNLOCK_POPT.3_CONTINUE"
        if (runtime_reduction_pass and runtime_target_pass and non_regression_pass)
        else "HOLD_POPT.2_REOPEN"
    )

    payload: dict[str, Any] = {
        "phase": "POPT.2",
        "segment": "6B",
        "decision": decision,
        "baseline": {
            "run_id": args.baseline_run_id,
            "runs_root": _ensure_ascii(baseline_runs_root),
            "run_root": _ensure_ascii(baseline_run_root),
            "seed": int(baseline_receipt.get("seed") or 0),
            "manifest_fingerprint": str(baseline_receipt.get("manifest_fingerprint") or ""),
            "parameter_hash": str(baseline_receipt.get("parameter_hash") or ""),
            "s4_elapsed_s": baseline_s4,
            "s4_elapsed_hms": _fmt_hms(baseline_s4),
            "lane_s4_to_s5_elapsed_s": baseline_lane_elapsed,
            "lane_s4_to_s5_elapsed_hms": _fmt_hms(baseline_lane_elapsed),
        },
        "witness": {
            "run_id": args.witness_run_id,
            "runs_root": _ensure_ascii(witness_runs_root),
            "run_root": _ensure_ascii(witness_run_root),
            "seed": int(witness_receipt.get("seed") or 0),
            "manifest_fingerprint": witness_manifest,
            "parameter_hash": str(witness_receipt.get("parameter_hash") or ""),
            "required_check_results": witness_required,
            "required_checks_pass": witness_required_pass,
            "warn_metrics": witness_warn,
            "overall_status": str(witness_report.get("overall_status") or ""),
        },
        "candidate": {
            "run_id": args.candidate_run_id,
            "runs_root": _ensure_ascii(candidate_runs_root),
            "run_root": _ensure_ascii(candidate_run_root),
            "seed": int(candidate_receipt.get("seed") or 0),
            "manifest_fingerprint": candidate_manifest,
            "parameter_hash": str(candidate_receipt.get("parameter_hash") or ""),
            "s4_elapsed_s": candidate_s4,
            "s4_elapsed_hms": _fmt_hms(candidate_s4),
            "lane_s4_to_s5_elapsed_s": candidate_lane_elapsed,
            "lane_s4_to_s5_elapsed_hms": _fmt_hms(candidate_lane_elapsed),
            "required_check_results": candidate_required,
            "required_checks_pass": candidate_required_pass,
            "warn_metrics": candidate_warn,
            "overall_status": str(candidate_report.get("overall_status") or ""),
        },
        "metrics": {
            "s4_reduction_ratio_vs_baseline": s4_reduction,
            "lane_reduction_ratio_vs_baseline": (
                ((baseline_lane_elapsed - candidate_lane_elapsed) / baseline_lane_elapsed)
                if baseline_lane_elapsed > 0
                else 0.0
            ),
            "runtime_reduction_pass": runtime_reduction_pass,
            "runtime_target_pass": runtime_target_pass,
            "runtime_stretch_pass": runtime_stretch_pass,
            "warn_metric_deltas": warn_delta,
            "warn_metrics_stable": warn_stable,
            "parity_counts_stable": counts_stable,
            "non_regression_pass": non_regression_pass,
        },
        "state_elapsed_s": {
            "baseline": baseline_elapsed,
            "candidate": candidate_elapsed,
        },
        "targets": {
            "s4_baseline_s": BASELINE_S4_SECONDS,
            "s4_target_s": TARGET_S4_SECONDS,
            "s4_stretch_s": STRETCH_S4_SECONDS,
            "required_reduction_ratio": 0.30,
        },
        "generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    out_json = out_root / f"segment6b_popt2_closure_{args.candidate_run_id}.json"
    out_md = out_root / f"segment6b_popt2_closure_{args.candidate_run_id}.md"
    out_csv = out_root / f"segment6b_popt2_state_elapsed_{args.candidate_run_id}.csv"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Segment 6B POPT.2 Closure",
        "",
        f"- baseline_run_id: `{args.baseline_run_id}`",
        f"- witness_run_id: `{args.witness_run_id}`",
        f"- candidate_run_id: `{args.candidate_run_id}`",
        f"- decision: `{decision}`",
        "",
        "## Runtime",
        "",
        f"- baseline S4: `{_fmt_hms(baseline_s4)}` ({baseline_s4:.2f}s)",
        f"- candidate S4: `{_fmt_hms(candidate_s4)}` ({candidate_s4:.2f}s)",
        f"- reduction: `{s4_reduction:.2%}`",
        f"- reduction gate (`>=30%`): `{runtime_reduction_pass}`",
        f"- target gate (`<=420s`): `{runtime_target_pass}`",
        f"- stretch gate (`<=500s`): `{runtime_stretch_pass}`",
        "",
        "## Non-Regression",
        "",
        f"- witness required checks pass: `{witness_required_pass}`",
        f"- candidate required checks pass: `{candidate_required_pass}`",
        f"- parity counts stable: `{counts_stable}`",
        f"- warn metrics stable: `{warn_stable}`",
        f"- non-regression gate: `{non_regression_pass}`",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["state", "baseline_elapsed_s", "candidate_elapsed_s", "delta_s", "delta_ratio"])
        for state in STATE_ORDER:
            base = float(baseline_elapsed[state])
            cand = float(candidate_elapsed[state])
            delta = cand - base
            ratio = (cand / base) if base > 0 else None
            writer.writerow([state, f"{base:.6f}", f"{cand:.6f}", f"{delta:.6f}", f"{ratio:.6f}" if ratio is not None else ""])

    print(f"[segment6b-popt2] closure_json={out_json}")
    print(f"[segment6b-popt2] closure_md={out_md}")
    print(f"[segment6b-popt2] state_csv={out_csv}")
    print(f"[segment6b-popt2] decision={decision}")


if __name__ == "__main__":
    main()
