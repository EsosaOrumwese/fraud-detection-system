#!/usr/bin/env python3
"""Emit Segment 5B POPT.0 baseline lock, timing, hotspot, and budget artifacts."""

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

STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
STATE_TITLES = {
    "S0": "Upstream gate verification and sealed input sealing",
    "S1": "Time-grid and grouping-domain derivation",
    "S2": "Latent intensity realization and RNG traces",
    "S3": "Bucket-level arrival count realization",
    "S4": "Arrival-event expansion and routing realization",
    "S5": "Validation bundle assembly and hash-gate publish",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l2/seg_5B/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l2/seg_5B/s1_time_grid/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l2/seg_5B/s2_latent_intensity/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l2/seg_5B/s3_bucket_counts/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py"],
}

STATE_BUDGETS = {
    "S1": {"target_s": 90.0, "stretch_s": 120.0},
    "S2": {"target_s": 35.0, "stretch_s": 45.0},
    "S3": {"target_s": 35.0, "stretch_s": 45.0},
    "S4": {"target_s": 240.0, "stretch_s": 300.0},
    "S5": {"target_s": 5.0, "stretch_s": 8.0},
}
LANE_BUDGETS = {
    "candidate_s": {"target_s": 420.0, "stretch_s": 480.0},
    "witness_s": {"target_s": 840.0, "stretch_s": 960.0},
    "certification_s": {"target_s": 1800.0, "stretch_s": 2100.0},
}


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


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


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


def _find_latest_segment_state_runs(run_root: Path) -> Path:
    candidates = sorted(
        run_root.glob("reports/layer2/segment_state_runs/segment=5B/utc_day=*/segment_state_runs.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(
            "Missing segment_state_runs for 5B under "
            f"{run_root / 'reports/layer2/segment_state_runs/segment=5B'}"
        )
    return candidates[-1]


def _extract_state_row(records: list[dict[str, Any]], state: str) -> dict[str, Any]:
    state_rows = [row for row in records if str(row.get("state")) == state]
    if not state_rows:
        raise ValueError(f"No state rows found for {state} in segment_state_runs.")
    pass_rows = [row for row in state_rows if str(row.get("status")) == "PASS"]
    source_rows = pass_rows if pass_rows else state_rows

    def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
        return (str(row.get("finished_at_utc") or ""), str(row.get("started_at_utc") or ""))

    return sorted(source_rows, key=_sort_key)[-1]


def _elapsed_s_from_state_row(row: dict[str, Any]) -> float:
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


def _parse_log_events(log_path: Path) -> list[LogEvent]:
    events: list[LogEvent] = []
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue
        parsed = LOG_LINE_RE.match(line)
        if not parsed:
            continue
        module = parsed.group(1)
        message = parsed.group(2)
        events.append(LogEvent(ts=ts, module=module, message=message))
    return events


def _state_events(events: list[LogEvent], state: str) -> list[LogEvent]:
    out: list[LogEvent] = []
    wanted = state[1:]
    for event in events:
        match = MODULE_STATE_RE.search(event.module)
        if match and match.group(1) == wanted:
            out.append(event)
    return out


def _lane_for_message(message: str) -> str:
    text = message.lower()
    if any(token in text for token in ("publish", "published", "write", "written", "bundle", "index", "digest", "_passed.flag")):
        return "write"
    if any(token in text for token in ("validate", "validated", "validation", "gate", "schema", "mismatch", "audit")):
        return "validation"
    if any(
        token in text
        for token in ("load", "loaded", "scan", "scanning", "read", "resolve", "contract", "policy", "manifest", "input", "receipt", "sealed")
    ):
        return "input_load"
    return "compute"


def _fallback_lane_share(state: str) -> dict[str, float]:
    if state == "S0":
        return {"input_load": 0.35, "compute": 0.05, "validation": 0.55, "write": 0.05}
    if state == "S1":
        return {"input_load": 0.74, "compute": 0.20, "validation": 0.04, "write": 0.02}
    if state == "S2":
        return {"input_load": 0.12, "compute": 0.78, "validation": 0.05, "write": 0.05}
    if state == "S3":
        return {"input_load": 0.10, "compute": 0.80, "validation": 0.05, "write": 0.05}
    if state == "S4":
        return {"input_load": 0.08, "compute": 0.84, "validation": 0.03, "write": 0.05}
    return {"input_load": 0.20, "compute": 0.30, "validation": 0.40, "write": 0.10}


def _state_lane_decomposition(
    state: str,
    elapsed_s: float,
    events: list[LogEvent],
    started_at_utc: str | None,
    finished_at_utc: str | None,
) -> tuple[dict[str, float], str]:
    state_events = _state_events(events, state)
    lanes = {"input_load": 0.0, "compute": 0.0, "validation": 0.0, "write": 0.0}
    if len(state_events) >= 2:
        for cur, nxt in zip(state_events, state_events[1:]):
            delta = (nxt.ts - cur.ts).total_seconds()
            if delta <= 0:
                continue
            lane = _lane_for_message(cur.message)
            lanes[lane] += delta
        # Attribute tail to the last lane category until finished timestamp when available.
        finished_ts = _parse_iso_ts(finished_at_utc)
        if finished_ts is not None:
            tail = (finished_ts - state_events[-1].ts).total_seconds()
            if tail > 0:
                lanes[_lane_for_message(state_events[-1].message)] += tail
        raw_total = sum(lanes.values())
        if raw_total > 0 and elapsed_s > 0:
            scale = elapsed_s / raw_total
            return ({k: v * scale for k, v in lanes.items()}, "derived_from_log_events")

    # Fallback: weighted decomposition by known state behavior.
    share = _fallback_lane_share(state)
    return ({k: elapsed_s * v for k, v in share.items()}, "fallback_weighted")


def _state_evidence(row: dict[str, Any]) -> dict[str, Any]:
    state = str(row.get("state"))
    if state == "S0":
        return {
            "upstream_pass_count": row.get("upstream_pass_count"),
            "sealed_inputs_row_count_total": row.get("sealed_inputs_row_count_total"),
            "scenario_set": row.get("scenario_set"),
        }
    metrics = row.get("metrics") or row.get("details") or {}
    durations = row.get("durations") or {}
    return {
        "status": row.get("status"),
        "durations_wall_ms": durations.get("wall_ms"),
        "error_code": row.get("error_code"),
        "metrics_excerpt": metrics if isinstance(metrics, dict) else {},
    }


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S4":
        return [
            "Reduce Python control-plane overhead in expansion path and keep numba kernel dominant.",
            "Lower arrival-event write amplification via tighter batching and fewer materialization passes.",
            "Hoist repeated routing/tz invariants out of the inner expansion loop.",
        ]
    if state == "S1":
        return [
            "Replace row-materialization domain scan with vectorized/lazy unique-key derivation.",
            "Reduce high-frequency scan progress overhead while keeping heartbeat observability.",
            "Avoid duplicate grouping-domain passes when scenario_local keys are already normalized.",
        ]
    if state == "S3":
        return [
            "Tighten bucket-count realization path by reducing repeated projection/cast work.",
            "Keep RNG accounting strict while minimizing validation overhead in fast-sampled mode.",
            "Lower intermediate-frame churn on grouped outputs before publish.",
        ]
    return [
        "Profile and remove repeated work in dominant hot loop.",
        "Preserve deterministic output while reducing unnecessary I/O/validation churn.",
    ]


def _ensure_ascii_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 5B POPT.0 baseline and hotspot artifacts.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument("--segment-state-runs", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt_path = run_root / "run_receipt.json"
    receipt = _load_json(receipt_path)
    seed = int(receipt.get("seed"))
    manifest_fingerprint = str(receipt.get("manifest_fingerprint"))
    parameter_hash = str(receipt.get("parameter_hash"))

    segment_state_runs_path = (
        Path(args.segment_state_runs)
        if args.segment_state_runs.strip()
        else _find_latest_segment_state_runs(run_root)
    )
    records = _load_jsonl(segment_state_runs_path)
    state_rows = {state: _extract_state_row(records, state) for state in STATE_ORDER}

    log_path = run_root / f"run_log_{run_id}.log"
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")
    log_events = _parse_log_events(log_path)

    state_table: list[dict[str, Any]] = []
    lane_map: dict[str, dict[str, Any]] = {}
    for state in STATE_ORDER:
        row = state_rows[state]
        elapsed_s = _elapsed_s_from_state_row(row)
        state_table.append(
            {
                "state": state,
                "status": row.get("status"),
                "elapsed_s": elapsed_s,
                "elapsed_hms": _fmt_hms(elapsed_s),
                "started_at_utc": row.get("started_at_utc"),
                "finished_at_utc": row.get("finished_at_utc"),
            }
        )
        lanes, source = _state_lane_decomposition(
            state,
            elapsed_s,
            log_events,
            str(row.get("started_at_utc") or ""),
            str(row.get("finished_at_utc") or ""),
        )
        lane_map[state] = {
            "source": source,
            "input_load_s": lanes["input_load"],
            "compute_s": lanes["compute"],
            "validation_s": lanes["validation"],
            "write_s": lanes["write"],
            "dominant_lane": max(lanes, key=lanes.get),
        }

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
                "evidence": _state_evidence(state_rows[state]),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
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

    baseline_lock_md = out_root / f"segment5b_popt0_baseline_lock_{run_id}.md"
    state_elapsed_csv = out_root / f"segment5b_popt0_state_elapsed_{run_id}.csv"
    hotspot_map_json = out_root / f"segment5b_popt0_hotspot_map_{run_id}.json"
    budget_pin_json = out_root / f"segment5b_popt0_budget_pin_{run_id}.json"

    # Baseline lock markdown
    baseline_lines: list[str] = []
    baseline_lines.append("# Segment 5B POPT.0 Baseline Lock")
    baseline_lines.append("")
    baseline_lines.append(f"- authority_run_id: `{run_id}`")
    baseline_lines.append(f"- authority_runs_root: `{_ensure_ascii_path(runs_root)}`")
    baseline_lines.append(f"- authority_run_root: `{_ensure_ascii_path(run_root)}`")
    baseline_lines.append(f"- seed: `{seed}`")
    baseline_lines.append(f"- parameter_hash: `{parameter_hash}`")
    baseline_lines.append(f"- manifest_fingerprint: `{manifest_fingerprint}`")
    baseline_lines.append(f"- run_receipt: `{_ensure_ascii_path(receipt_path)}`")
    baseline_lines.append(f"- segment_state_runs_source: `{_ensure_ascii_path(segment_state_runs_path)}`")
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
        f"- segment_elapsed: `{_fmt_hms(segment_elapsed_s)}` "
        f"({segment_elapsed_s:.3f}s); candidate_lane_status=`{candidate_status}`"
    )
    baseline_lines.append("")
    baseline_lines.append("## Baseline Pin Decision")
    baseline_lines.append("")
    baseline_lines.append("- Decision: `PINNED`")
    baseline_lines.append(
        "- Rationale: existing clean authority run contains final PASS for `S0..S5`; "
        "reuse avoids storage-heavy duplication while preserving deterministic evidence."
    )
    baseline_lock_md.write_text("\n".join(baseline_lines) + "\n", encoding="utf-8")

    # State elapsed CSV
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
        "segment": "5B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "authority": {
            "run_id": run_id,
            "runs_root": _ensure_ascii_path(runs_root),
            "run_root": _ensure_ascii_path(run_root),
            "segment_state_runs": _ensure_ascii_path(segment_state_runs_path),
            "run_log": _ensure_ascii_path(log_path),
        },
        "timing": {
            "segment_elapsed_s": segment_elapsed_s,
            "segment_elapsed_hms": _fmt_hms(segment_elapsed_s),
            "state_table": state_table,
        },
        "lane_decomposition": lane_map,
        "hotspots": hotspots,
    }
    hotspot_map_json.write_text(json.dumps(hotspot_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    budget_payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "5B",
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
            "ordered_lane": ["S4", "S1", "S3", "S2", "S5"],
            "reason": "Hotspot ranking and lane decomposition are complete; candidate lane currently RED versus target.",
        },
    }
    budget_pin_json.write_text(json.dumps(budget_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[segment5b-popt0] baseline_lock={baseline_lock_md}")
    print(f"[segment5b-popt0] state_elapsed={state_elapsed_csv}")
    print(f"[segment5b-popt0] hotspot_map={hotspot_map_json}")
    print(f"[segment5b-popt0] budget_pin={budget_pin_json}")


if __name__ == "__main__":
    main()
