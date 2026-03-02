#!/usr/bin/env python3
"""Emit Segment 6B POPT.0 baseline lock, timing, hotspot, part-shape, and budget artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[[A-Z]+\] ([^:]+): (.*)$")
MODULE_STATE_RE = re.compile(r"engine\.layers\.l3\.seg_6B\.s([0-5])_")
ELAPSED_RE = re.compile(r"elapsed=([0-9]+(?:\.[0-9]+)?)s")

STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
STATE_TITLES = {
    "S0": "Upstream gate verification and sealed input sealing",
    "S1": "Arrival-to-entity attachment and session index synthesis",
    "S2": "Baseline flow and event stream synthesis",
    "S3": "Fraud campaign overlay realization",
    "S4": "Truth, bank-view, and case timeline labelling",
    "S5": "Validation bundle assembly and pass-flag publish",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l3/seg_6B/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l3/seg_6B/s3_fraud_overlay/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l3/seg_6B/s5_validation_gate/runner.py"],
}

STATE_BUDGETS = {
    "S1": {"target_s": 800.0, "stretch_s": 900.0},
    "S2": {"target_s": 120.0, "stretch_s": 150.0},
    "S3": {"target_s": 300.0, "stretch_s": 360.0},
    "S4": {"target_s": 420.0, "stretch_s": 500.0},
    "S5": {"target_s": 10.0, "stretch_s": 12.0},
}
LANE_BUDGETS = {
    "candidate_s": {"target_s": 1320.0, "stretch_s": 1500.0},
    "witness_s": {"target_s": 2700.0, "stretch_s": 3000.0},
    "certification_s": {"target_s": 5700.0, "stretch_s": 6300.0},
}

DATASET_SURFACES = [
    "s1_arrival_entities_6B",
    "s1_session_index_6B",
    "s2_flow_anchor_baseline_6B",
    "s2_event_stream_baseline_6B",
    "s3_campaign_catalogue_6B",
    "s3_flow_anchor_with_fraud_6B",
    "s3_event_stream_with_fraud_6B",
    "s4_flow_truth_labels_6B",
    "s4_flow_bank_view_6B",
    "s4_event_labels_6B",
    "s4_case_timeline_6B",
]


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


def _status(value_s: float, target_s: float, stretch_s: float) -> str:
    if value_s <= target_s:
        return "GREEN"
    if value_s <= stretch_s:
        return "AMBER"
    return "RED"


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _completion_event(events: list[LogEvent], state: str) -> LogEvent:
    candidates: list[LogEvent] = []
    for event in _state_events(events, state):
        msg = event.message.lower()
        if "completed" not in msg:
            continue
        if _extract_elapsed(event.message) is None:
            continue
        candidates.append(event)
    if not candidates:
        raise ValueError(f"Missing completion event for {state} in 6B run log.")
    return sorted(candidates, key=lambda event: event.ts)[-1]


def _lane_for_message(message: str) -> str:
    text = message.lower()
    if any(token in text for token in ("publish", "published", "write", "written", "bundle", "index", "digest", "_passed.flag")):
        return "write"
    if any(token in text for token in ("validate", "validated", "validation", "gate", "schema", "mismatch", "audit", "check")):
        return "validation"
    if any(
        token in text
        for token in ("load", "loaded", "scan", "scanning", "read", "resolve", "contract", "policy", "manifest", "input", "receipt", "sealed")
    ):
        return "input_load"
    return "compute"


def _fallback_lane_share(state: str) -> dict[str, float]:
    if state == "S0":
        return {"input_load": 0.35, "compute": 0.10, "validation": 0.45, "write": 0.10}
    if state == "S1":
        return {"input_load": 0.08, "compute": 0.84, "validation": 0.03, "write": 0.05}
    if state == "S2":
        return {"input_load": 0.12, "compute": 0.75, "validation": 0.03, "write": 0.10}
    if state == "S3":
        return {"input_load": 0.08, "compute": 0.80, "validation": 0.03, "write": 0.09}
    if state == "S4":
        return {"input_load": 0.06, "compute": 0.86, "validation": 0.02, "write": 0.06}
    return {"input_load": 0.20, "compute": 0.35, "validation": 0.30, "write": 0.15}


def _state_lane_decomposition(state: str, elapsed_s: float, state_events: list[LogEvent]) -> tuple[dict[str, float], str]:
    lanes = {"input_load": 0.0, "compute": 0.0, "validation": 0.0, "write": 0.0}
    if len(state_events) >= 2:
        ordered = sorted(state_events, key=lambda event: event.ts)
        for cur, nxt in zip(ordered, ordered[1:]):
            delta = (nxt.ts - cur.ts).total_seconds()
            if delta <= 0:
                continue
            lanes[_lane_for_message(cur.message)] += delta
        raw_total = sum(lanes.values())
        if raw_total > 0 and elapsed_s > 0:
            scale = elapsed_s / raw_total
            return ({key: value * scale for key, value in lanes.items()}, "derived_from_log_events")
    share = _fallback_lane_share(state)
    return ({key: elapsed_s * frac for key, frac in share.items()}, "fallback_weighted")


def _find_line(events: list[LogEvent], state: str, pattern: re.Pattern[str]) -> str | None:
    for event in reversed(_state_events(events, state)):
        if pattern.search(event.message):
            return event.message
    return None


def _state_evidence(events: list[LogEvent], state: str) -> dict[str, Any]:
    if state == "S1":
        out: dict[str, Any] = {}
        line = _find_line(events, "S1", re.compile(r"attachments_complete arrivals=\d+ sessions=\d+"))
        if line:
            m = re.search(r"arrivals=(\d+)\s+sessions=(\d+)", line)
            if m:
                out["arrivals"] = int(m.group(1))
                out["sessions"] = int(m.group(2))
        bline = _find_line(events, "S1", re.compile(r"bucketization parts_processed=591/591"))
        if bline:
            elapsed = _extract_elapsed(bline)
            if elapsed is not None:
                out["session_bucketization_elapsed_s"] = elapsed
        aline = _find_line(events, "S1", re.compile(r"bucket aggregation buckets_processed=128/128"))
        if aline:
            elapsed = _extract_elapsed(aline)
            if elapsed is not None:
                out["session_aggregation_elapsed_s"] = elapsed
        return out
    if state == "S2":
        out: dict[str, Any] = {}
        line = _find_line(events, "S2", re.compile(r"S2 6B complete:"))
        if line:
            m = re.search(r"flows=(\d+)\s+events=(\d+)", line)
            if m:
                out["flows"] = int(m.group(1))
                out["events"] = int(m.group(2))
        return out
    if state == "S3":
        out: dict[str, Any] = {}
        line = _find_line(events, "S3", re.compile(r"S3 6B complete:"))
        if line:
            m = re.search(r"flows=(\d+)\s+events=(\d+)\s+campaigns=(\d+)", line)
            if m:
                out["flows"] = int(m.group(1))
                out["events"] = int(m.group(2))
                out["campaigns"] = int(m.group(3))
        return out
    if state == "S4":
        out: dict[str, Any] = {}
        line = _find_line(events, "S4", re.compile(r"S4 6B complete:"))
        if line:
            m = re.search(r"flows=(\d+)\s+events=(\d+)\s+cases=(\d+)", line)
            if m:
                out["flows"] = int(m.group(1))
                out["events"] = int(m.group(2))
                out["cases"] = int(m.group(3))
        fline = _find_line(events, "S4", re.compile(r"flows_processed 124724153/124724153"))
        if fline:
            elapsed = _extract_elapsed(fline)
            if elapsed is not None:
                out["flow_label_pass_elapsed_s"] = elapsed
        eline = _find_line(events, "S4", re.compile(r"events_processed 249448306/249448306"))
        if eline:
            elapsed = _extract_elapsed(eline)
            if elapsed is not None:
                out["event_label_pass_elapsed_s"] = elapsed
        return out
    if state == "S5":
        out: dict[str, Any] = {}
        line = _find_line(events, "S5", re.compile(r"bundle complete \(entries=\d+, digest=[0-9a-f]+"))
        if line:
            m = re.search(r"entries=(\d+),\s*digest=([0-9a-f]+)", line)
            if m:
                out["bundle_entries"] = int(m.group(1))
                out["bundle_digest"] = m.group(2)
        return out
    return {}


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S1":
        return [
            "Replace repeated join-heavy attachment expansions with pre-indexed gather paths.",
            "Collapse two-pass session bucketization+aggregation into a deterministic merge-light path.",
            "Reduce per-batch write churn while keeping replay/idempotence invariants intact.",
        ]
    if state == "S4":
        return [
            "Compute flow truth/bank labels once and derive event labels via deterministic carry-through.",
            "Refactor case timeline emission to reduce repeated dataframe concat/materialization.",
            "Reduce duplicated policy-expression evaluation across flow/event passes.",
        ]
    if state == "S3":
        return [
            "Reduce output part fragmentation by buffering writes to larger deterministic parts.",
            "Tighten overlay path to avoid repeated projection/cast work.",
            "Preserve campaign determinism while reducing per-batch overhead.",
        ]
    return [
        "Profile and remove repeated work in dominant path while preserving determinism.",
        "Reduce avoidable validation/write overhead without contract weakening.",
    ]


def _dataset_part_shape(dataset_root: Path) -> dict[str, Any]:
    parquet_files = sorted(dataset_root.rglob("*.parquet"))
    file_count = len(parquet_files)
    total_bytes = 0
    total_rows = 0
    for part in parquet_files:
        total_bytes += part.stat().st_size
        try:
            total_rows += int(pq.ParquetFile(part).metadata.num_rows)
        except Exception:
            pass
    avg_file_mb = (float(total_bytes) / float(file_count) / (1024.0 * 1024.0)) if file_count > 0 else 0.0
    return {
        "file_count": file_count,
        "total_bytes": int(total_bytes),
        "total_mb": float(total_bytes) / (1024.0 * 1024.0),
        "avg_file_mb": avg_file_mb,
        "row_count": int(total_rows),
        "rows_per_file": (float(total_rows) / float(file_count)) if file_count > 0 else 0.0,
    }


def _ensure_ascii_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 6B POPT.0 baseline artifacts.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default="c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_6B/reports")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip()
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt_path = run_root / "run_receipt.json"
    receipt = _load_json(receipt_path)
    seed = int(receipt.get("seed"))
    manifest_fingerprint = str(receipt.get("manifest_fingerprint"))
    parameter_hash = str(receipt.get("parameter_hash"))

    log_path = run_root / f"run_log_{run_id}.log"
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")
    log_events = _parse_log_events(log_path)

    segment_events = [event for event in log_events if MODULE_STATE_RE.search(event.module)]
    if not segment_events:
        raise RuntimeError("No Segment 6B events found in run log.")

    completion_map: dict[str, LogEvent] = {state: _completion_event(segment_events, state) for state in STATE_ORDER}

    state_table: list[dict[str, Any]] = []
    lane_map: dict[str, dict[str, Any]] = {}
    prev_complete_ts: datetime | None = None
    for state in STATE_ORDER:
        complete_event = completion_map[state]
        elapsed_s = _extract_elapsed(complete_event.message)
        if elapsed_s is None:
            raise RuntimeError(f"Missing elapsed value in completion message for {state}.")

        events_in_state = [
            event
            for event in _state_events(segment_events, state)
            if event.ts <= complete_event.ts and (prev_complete_ts is None or event.ts > prev_complete_ts)
        ]
        start_ts = min((event.ts for event in events_in_state), default=complete_event.ts)
        status = "PASS"
        if state == "S5":
            status = "PASS" if "status=pass" in complete_event.message.lower() else "FAIL"

        state_table.append(
            {
                "state": state,
                "status": status,
                "elapsed_s": float(elapsed_s),
                "elapsed_hms": _fmt_hms(float(elapsed_s)),
                "started_at_utc": start_ts.isoformat(timespec="milliseconds") + "Z",
                "finished_at_utc": complete_event.ts.isoformat(timespec="milliseconds") + "Z",
            }
        )

        lanes, source = _state_lane_decomposition(state, float(elapsed_s), events_in_state)
        lane_map[state] = {
            "source": source,
            "input_load_s": lanes["input_load"],
            "compute_s": lanes["compute"],
            "validation_s": lanes["validation"],
            "write_s": lanes["write"],
            "dominant_lane": max(lanes, key=lanes.get),
        }
        prev_complete_ts = complete_event.ts

    segment_elapsed_s = sum(float(item["elapsed_s"]) for item in state_table)
    for item in state_table:
        elapsed = float(item["elapsed_s"])
        item["segment_share"] = (elapsed / segment_elapsed_s) if segment_elapsed_s > 0 else 0.0

    ranked = sorted(state_table, key=lambda item: float(item["elapsed_s"]), reverse=True)
    top_three = ranked[:3]
    hotspots: list[dict[str, Any]] = []
    for idx, row in enumerate(top_three, start=1):
        state = str(row["state"])
        hotspots.append(
            {
                "rank": idx,
                "lane": "primary" if idx == 1 else ("secondary" if idx == 2 else "tertiary"),
                "state": state,
                "title": STATE_TITLES[state],
                "elapsed_s": float(row["elapsed_s"]),
                "elapsed_hms": row["elapsed_hms"],
                "segment_share": float(row["segment_share"]),
                "lane_decomposition": lane_map[state],
                "evidence": _state_evidence(segment_events, state),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
        )

    segment_data_root = run_root / "data/layer3/6B"
    part_shape_by_dataset: dict[str, Any] = {}
    for dataset in DATASET_SURFACES:
        part_shape_by_dataset[dataset] = _dataset_part_shape(segment_data_root / dataset)
    small_file_hotspots = sorted(
        [
            {"dataset": dataset, **stats}
            for dataset, stats in part_shape_by_dataset.items()
            if int(stats.get("file_count") or 0) >= 200 and float(stats.get("avg_file_mb") or 0.0) <= 8.0
        ],
        key=lambda row: (int(row["file_count"]), -float(row["avg_file_mb"])),
        reverse=True,
    )

    state_budget_rows: dict[str, Any] = {}
    for state, budget in STATE_BUDGETS.items():
        elapsed = next(float(row["elapsed_s"]) for row in state_table if row["state"] == state)
        state_budget_rows[state] = {
            "baseline_elapsed_s": elapsed,
            "baseline_elapsed_hms": _fmt_hms(elapsed),
            "target_s": budget["target_s"],
            "target_hms": _fmt_hms(budget["target_s"]),
            "stretch_s": budget["stretch_s"],
            "stretch_hms": _fmt_hms(budget["stretch_s"]),
            "status_vs_target": _status(elapsed, budget["target_s"], budget["stretch_s"]),
            "required_reduction_s_to_target": max(elapsed - budget["target_s"], 0.0),
        }

    candidate_status = _status(
        segment_elapsed_s,
        LANE_BUDGETS["candidate_s"]["target_s"],
        LANE_BUDGETS["candidate_s"]["stretch_s"],
    )

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    baseline_lock_md = out_root / f"segment6b_popt0_baseline_lock_{run_id}.md"
    state_elapsed_csv = out_root / f"segment6b_popt0_state_elapsed_{run_id}.csv"
    hotspot_map_json = out_root / f"segment6b_popt0_hotspot_map_{run_id}.json"
    hotspot_map_md = out_root / f"segment6b_popt0_hotspot_map_{run_id}.md"
    budget_pin_json = out_root / f"segment6b_popt0_budget_pin_{run_id}.json"
    baseline_json = out_root / f"segment6b_popt0_baseline_{run_id}.json"
    part_shape_json = out_root / f"segment6b_popt0_part_shape_{run_id}.json"

    baseline_lines: list[str] = []
    baseline_lines.append("# Segment 6B POPT.0 Baseline Lock")
    baseline_lines.append("")
    baseline_lines.append(f"- authority_run_id: `{run_id}`")
    baseline_lines.append(f"- authority_runs_root: `{_ensure_ascii_path(runs_root)}`")
    baseline_lines.append(f"- authority_run_root: `{_ensure_ascii_path(run_root)}`")
    baseline_lines.append(f"- seed: `{seed}`")
    baseline_lines.append(f"- parameter_hash: `{parameter_hash}`")
    baseline_lines.append(f"- manifest_fingerprint: `{manifest_fingerprint}`")
    baseline_lines.append(f"- run_receipt: `{_ensure_ascii_path(receipt_path)}`")
    baseline_lines.append(f"- run_log_source: `{_ensure_ascii_path(log_path)}`")
    baseline_lines.append("")
    baseline_lines.append("## State PASS Check")
    baseline_lines.append("")
    baseline_lines.append("| State | Status | Elapsed |")
    baseline_lines.append("|---|---|---:|")
    for row in state_table:
        baseline_lines.append(f"| {row['state']} | {row['status']} | {row['elapsed_hms']} |")
    baseline_lines.append("")
    baseline_lines.append(
        f"- segment_elapsed: `{_fmt_hms(segment_elapsed_s)}` ({segment_elapsed_s:.3f}s); "
        f"candidate_lane_status=`{candidate_status}`"
    )
    baseline_lines.append("")
    baseline_lines.append("## Baseline Pin Decision")
    baseline_lines.append("")
    baseline_lines.append("- Decision: `PINNED`")
    baseline_lines.append(
        "- Rationale: reuse clean full-chain authority run to avoid storage-heavy duplication while preserving deterministic evidence."
    )
    baseline_lock_md.write_text("\n".join(baseline_lines) + "\n", encoding="utf-8")

    with state_elapsed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "state",
                "status",
                "elapsed_s",
                "elapsed_hms",
                "segment_share",
                "started_at_utc",
                "finished_at_utc",
            ],
        )
        writer.writeheader()
        for row in state_table:
            writer.writerow(row)

    hotspot_payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "6B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "authority": {
            "run_id": run_id,
            "runs_root": _ensure_ascii_path(runs_root),
            "run_root": _ensure_ascii_path(run_root),
            "run_log": _ensure_ascii_path(log_path),
        },
        "timing": {
            "segment_elapsed_s": segment_elapsed_s,
            "segment_elapsed_hms": _fmt_hms(segment_elapsed_s),
            "state_table": state_table,
            "log_window": {
                "s0_start_ts": state_table[0]["started_at_utc"],
                "s5_complete_ts": state_table[-1]["finished_at_utc"],
                "segment_window_elapsed_s": (
                    datetime.fromisoformat(state_table[-1]["finished_at_utc"].replace("Z", ""))
                    - datetime.fromisoformat(state_table[0]["started_at_utc"].replace("Z", ""))
                ).total_seconds(),
            },
        },
        "lane_decomposition": lane_map,
        "hotspots": hotspots,
        "part_shape_summary": {
            "dataset_stats": part_shape_by_dataset,
            "small_file_hotspots": small_file_hotspots,
        },
    }
    hotspot_map_json.write_text(json.dumps(hotspot_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    hotspot_md: list[str] = []
    hotspot_md.append("# Segment 6B POPT.0 Baseline and Hotspot Map")
    hotspot_md.append("")
    hotspot_md.append(f"- authority_run_id: `{run_id}`")
    hotspot_md.append(f"- authority_runs_root: `{_ensure_ascii_path(runs_root)}`")
    hotspot_md.append(f"- seed: `{seed}`")
    hotspot_md.append(f"- manifest_fingerprint: `{manifest_fingerprint}`")
    hotspot_md.append("")
    hotspot_md.append("## Runtime Table")
    hotspot_md.append("")
    hotspot_md.append("| State | Elapsed | Share |")
    hotspot_md.append("|---|---:|---:|")
    for row in state_table:
        hotspot_md.append(f"| {row['state']} | {row['elapsed_hms']} | {float(row['segment_share'])*100.0:.2f}% |")
    hotspot_md.append("")
    hotspot_md.append(f"- report_elapsed_sum: `{_fmt_hms(segment_elapsed_s)}`")
    hotspot_md.append("")
    hotspot_md.append("## Ranked Hotspots")
    hotspot_md.append("")
    for row in hotspots:
        hotspot_md.append(f"### {row['rank']}. {row['state']} ({row['lane']})")
        hotspot_md.append(f"- title: {row['title']}")
        hotspot_md.append(f"- elapsed: `{row['elapsed_hms']}`")
        hotspot_md.append(f"- segment_share: `{float(row['segment_share'])*100.0:.2f}%`")
        hotspot_md.append(f"- dominant_lane: `{row['lane_decomposition']['dominant_lane']}`")
        hotspot_md.append(f"- evidence: `{json.dumps(row['evidence'], sort_keys=True)}`")
        hotspot_md.append("")
    hotspot_md.append("## Small-File Hotspots")
    hotspot_md.append("")
    hotspot_md.append("| Dataset | Files | Avg File MB | Rows |")
    hotspot_md.append("|---|---:|---:|---:|")
    for row in small_file_hotspots[:8]:
        hotspot_md.append(
            f"| {row['dataset']} | {int(row['file_count'])} | {float(row['avg_file_mb']):.2f} | {int(row['row_count'])} |"
        )
    hotspot_map_md.write_text("\n".join(hotspot_md) + "\n", encoding="utf-8")

    budget_payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "6B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "authority_run_id": run_id,
        "state_budgets": state_budget_rows,
        "lane_budgets": {
            "candidate": {
                **LANE_BUDGETS["candidate_s"],
                "target_hms": _fmt_hms(LANE_BUDGETS["candidate_s"]["target_s"]),
                "stretch_hms": _fmt_hms(LANE_BUDGETS["candidate_s"]["stretch_s"]),
                "baseline_elapsed_s": segment_elapsed_s,
                "baseline_elapsed_hms": _fmt_hms(segment_elapsed_s),
                "status_vs_budget": candidate_status,
            },
            "witness": {
                **LANE_BUDGETS["witness_s"],
                "target_hms": _fmt_hms(LANE_BUDGETS["witness_s"]["target_s"]),
                "stretch_hms": _fmt_hms(LANE_BUDGETS["witness_s"]["stretch_s"]),
            },
            "certification": {
                **LANE_BUDGETS["certification_s"],
                "target_hms": _fmt_hms(LANE_BUDGETS["certification_s"]["target_s"]),
                "stretch_hms": _fmt_hms(LANE_BUDGETS["certification_s"]["stretch_s"]),
            },
        },
        "handoff_recommendation": {
            "decision": "GO_POPT.1",
            "ordered_lane": ["S1", "S4", "S3", "S2", "S5"],
            "reason": "POPT.0 hotspot decomposition complete; S1 and S4 dominate runtime and control iteration speed.",
        },
    }
    budget_pin_json.write_text(json.dumps(budget_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    part_shape_payload = {
        "phase": "POPT.0",
        "segment": "6B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "authority_run_id": run_id,
        "dataset_stats": part_shape_by_dataset,
        "small_file_hotspots": small_file_hotspots,
    }
    part_shape_json.write_text(json.dumps(part_shape_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    baseline_payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "6B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "run_id": run_id,
            "runs_root": _ensure_ascii_path(runs_root),
            "run_root": _ensure_ascii_path(run_root),
            "run_receipt_path": _ensure_ascii_path(receipt_path),
            "run_log_path": _ensure_ascii_path(log_path),
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
        },
        "timing": {
            "segment_elapsed_s": segment_elapsed_s,
            "segment_elapsed_hms": _fmt_hms(segment_elapsed_s),
            "state_table": state_table,
        },
        "hotspots": hotspots,
        "lane_decomposition": lane_map,
        "part_shape_summary": {
            "small_file_hotspot_count": len(small_file_hotspots),
        },
        "artifacts": {
            "baseline_lock_md": _ensure_ascii_path(baseline_lock_md),
            "state_elapsed_csv": _ensure_ascii_path(state_elapsed_csv),
            "hotspot_map_json": _ensure_ascii_path(hotspot_map_json),
            "hotspot_map_md": _ensure_ascii_path(hotspot_map_md),
            "budget_pin_json": _ensure_ascii_path(budget_pin_json),
            "part_shape_json": _ensure_ascii_path(part_shape_json),
        },
        "progression_gate": budget_payload["handoff_recommendation"],
    }
    baseline_json.write_text(json.dumps(baseline_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[segment6b-popt0] baseline_lock={baseline_lock_md}")
    print(f"[segment6b-popt0] state_elapsed={state_elapsed_csv}")
    print(f"[segment6b-popt0] hotspot_map_json={hotspot_map_json}")
    print(f"[segment6b-popt0] hotspot_map_md={hotspot_map_md}")
    print(f"[segment6b-popt0] budget_pin={budget_pin_json}")
    print(f"[segment6b-popt0] part_shape={part_shape_json}")
    print(f"[segment6b-popt0] baseline_json={baseline_json}")


if __name__ == "__main__":
    main()
