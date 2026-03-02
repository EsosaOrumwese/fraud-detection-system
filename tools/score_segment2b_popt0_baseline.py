#!/usr/bin/env python3
"""Emit Segment 2B POPT.0 baseline runtime and hotspot artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
START_RE = re.compile(r"engine\.layers\.l1\.seg_2B\.s([0-8])_[^:]*: S[0-8]: run log initialized")
FALLBACK_START_RE = re.compile(r"engine\.layers\.l1\.seg_2B\.s([0-8])_[^:]*:")
COMPLETE_RE = re.compile(r"\bS([0-8]) 2B complete:")

STATE_ORDER = [f"S{i}" for i in range(9)]
STATE_TITLES = {
    "S0": "Gate verification and sealed-input inventory",
    "S1": "Site-weight synthesis and normalization path",
    "S2": "Alias table build and blob/index serialization",
    "S3": "Day-effect gamma generation across merchant-day-group",
    "S4": "Group-mix normalization across merchant-day-group",
    "S5": "Per-arrival routing loop (group + site draw)",
    "S6": "Virtual-edge routing for virtual arrivals",
    "S7": "Audit gate across S2/S3/S4 (and optional routing logs)",
    "S8": "Validation bundle/index assembly and digest pass",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l1/seg_2B/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l1/seg_2B/s2_alias_tables/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py"],
    "S6": ["packages/engine/src/engine/layers/l1/seg_2B/s6_edge_router/runner.py"],
    "S7": ["packages/engine/src/engine/layers/l1/seg_2B/s7_audit/runner.py"],
    "S8": ["packages/engine/src/engine/layers/l1/seg_2B/s8_validation_bundle/runner.py"],
}

# Minute-scale optimization budgets for POPT progression.
BUDGETS_S = {
    "S0": {"target": 1.0, "stretch": 2.0},
    "S1": {"target": 4.0, "stretch": 6.0},
    "S2": {"target": 3.0, "stretch": 5.0},
    "S3": {"target": 18.0, "stretch": 24.0},
    "S4": {"target": 18.0, "stretch": 24.0},
    "S5": {"target": 16.0, "stretch": 22.0},
    "S6": {"target": 1.0, "stretch": 2.0},
    "S7": {"target": 1.0, "stretch": 2.0},
    "S8": {"target": 1.0, "stretch": 2.0},
}


def _parse_ts(line: str) -> datetime | None:
    m = TS_RE.match(line)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)}.{m.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _status(elapsed_s: float, target_s: float, stretch_s: float) -> str:
    if elapsed_s <= target_s:
        return "GREEN"
    if elapsed_s <= stretch_s:
        return "AMBER"
    return "RED"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _find_single(paths: list[Path], label: str) -> Path:
    if not paths:
        raise FileNotFoundError(f"Missing {label}")
    if len(paths) > 1:
        paths = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0]


def _find_state_report(run_root: Path, state: str) -> Path:
    report_name = f"{state.lower()}_run_report.json"
    state_dir = run_root / "reports/layer1/2B" / f"state={state}"
    return _find_single(list(state_dir.rglob(report_name)), report_name)


def _parse_log_window(log_path: Path) -> dict[str, Any]:
    start_by_state: dict[str, datetime] = {}
    complete_by_state: dict[str, datetime] = {}
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue
        ms = START_RE.search(line)
        if ms:
            state = f"S{ms.group(1)}"
            if state not in start_by_state:
                start_by_state[state] = ts
        else:
            mf = FALLBACK_START_RE.search(line)
            if mf:
                state = f"S{mf.group(1)}"
                if state not in start_by_state:
                    start_by_state[state] = ts
        mc = COMPLETE_RE.search(line)
        if mc:
            state = f"S{mc.group(1)}"
            if state not in complete_by_state:
                complete_by_state[state] = ts

    starts = list(start_by_state.values())
    ends = list(complete_by_state.values())
    elapsed_s = (max(ends) - min(starts)).total_seconds() if starts and ends else None
    return {
        "start_by_state": {k: v.isoformat() for k, v in sorted(start_by_state.items())},
        "complete_by_state": {k: v.isoformat() for k, v in sorted(complete_by_state.items())},
        "segment_window_elapsed_s": elapsed_s,
        "segment_window_elapsed_hms": _fmt_hms(elapsed_s),
    }


def _state_evidence(state: str, reports: dict[str, dict[str, Any]], s7_report: dict[str, Any], s8_index: dict[str, Any]) -> dict[str, Any]:
    if state == "S0":
        r = reports["S0"]
        return {
            "inputs_total": r.get("inputs_summary", {}).get("inputs_total"),
            "inventory_rows": r.get("inventory_summary", {}).get("inventory_rows"),
            "publish_bytes_total": r.get("publish", {}).get("publish_bytes_total"),
        }
    if state == "S1":
        r = reports["S1"]
        return {
            "merchants_total": r.get("inputs_summary", {}).get("merchants_total"),
            "sites_total": r.get("inputs_summary", {}).get("sites_total"),
            "transform_rows": r.get("transforms", {}).get("floors_applied_rows"),
        }
    if state == "S2":
        r = reports["S2"]
        return {
            "merchants_count": r.get("counters", {}).get("merchants_count"),
            "sites_total": r.get("counters", {}).get("sites_total"),
            "blob_size_bytes": r.get("counters", {}).get("blob_size_bytes"),
        }
    if state == "S3":
        r = reports["S3"]
        return {
            "rows_written": r.get("rng_accounting", {}).get("rows_written"),
            "draws_total": r.get("rng_accounting", {}).get("draws_total"),
            "draw_ms": r.get("durations_ms", {}).get("draw_ms"),
            "write_ms": r.get("durations_ms", {}).get("write_ms"),
        }
    if state == "S4":
        r = reports["S4"]
        return {
            "rows_written": r.get("counters", {}).get("rows_written"),
            "normalise_ms": r.get("durations_ms", {}).get("normalise_ms"),
            "write_ms": r.get("durations_ms", {}).get("write_ms"),
            "days_total": r.get("counters", {}).get("days_total"),
        }
    if state == "S5":
        r = reports["S5"]
        return {
            "draws_total": r.get("rng_accounting", {}).get("draws_total"),
            "events_total": r.get("rng_accounting", {}).get("events_total"),
            "selection_log_enabled": r.get("logging", {}).get("selection_log_enabled"),
        }
    if state == "S6":
        r = reports["S6"]
        return {
            "virtual_arrivals": r.get("rng_accounting", {}).get("virtual_arrivals"),
            "draws_total": r.get("rng_accounting", {}).get("draws_total"),
            "elapsed_seconds_reported": r.get("environment", {}).get("elapsed_seconds"),
        }
    if state == "S7":
        return {
            "merchants_total": s7_report.get("metrics", {}).get("merchants_total"),
            "days_total": s7_report.get("metrics", {}).get("days_total"),
            "max_abs_mass_error_s4": s7_report.get("metrics", {}).get("max_abs_mass_error_s4"),
        }
    if state == "S8":
        files = s8_index.get("files", [])
        return {
            "files_indexed": len(files),
            "has_passed_flag": any(str(item.get("path", "")).endswith("_passed.flag") for item in files if isinstance(item, dict)),
        }
    return {}


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S4":
        return [
            "Reduce merchant-day-group normalization overhead by tightening grouping/materialization strategy.",
            "Cut write-path overhead with larger deterministic batch writes and reduced intermediate copies.",
            "Hoist repeated per-group invariants out of the inner normalization loop.",
        ]
    if state == "S3":
        return [
            "Vectorize day-effect draw preparation and remove repeated per-row policy lookups.",
            "Lower gamma write-path overhead via chunk sizing and projection discipline.",
            "Cache deterministic tz-group structures reused across merchants.",
        ]
    if state == "S5":
        return [
            "Optimize per-arrival group/site lookup path with pre-indexed structures.",
            "Reduce routing-loop overhead by minimizing repeated dictionary/record materialization.",
            "Keep logging at heartbeat cadence and avoid per-arrival debug payload in fast lane.",
        ]
    return [
        "Profile inner loop and remove repeated work on hot path.",
        "Tighten I/O footprint while preserving deterministic output bytes.",
    ]


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Segment 2B POPT.0 Baseline and Hotspot Map")
    lines.append("")
    lines.append(f"- authority_run_id: `{payload['run']['run_id']}`")
    lines.append(f"- authority_runs_root: `{payload['run']['runs_root']}`")
    lines.append(f"- seed: `{payload['run']['seed']}`")
    lines.append(f"- manifest_fingerprint: `{payload['run']['manifest_fingerprint']}`")
    lines.append("")
    lines.append("## Runtime Table")
    lines.append("")
    lines.append("| State | Elapsed | Share | Target | Stretch | Status |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for row in payload["timing"]["state_table"]:
        state = row["state"]
        budget = payload["budgets"][state]
        share = f"{100.0 * float(row['segment_share']):.2f}%"
        lines.append(
            f"| {state} | {row['elapsed_hms'] or 'n/a'} | {share} | {budget['target_hms']} | {budget['stretch_hms']} | {budget['status']} |"
        )
    lines.append("")
    lines.append(f"- log_window_elapsed: `{payload['timing']['log_window'].get('segment_window_elapsed_hms') or 'n/a'}`")
    lines.append("")
    lines.append("## Ranked Hotspots")
    lines.append("")
    for hotspot in payload["hotspots"]:
        lines.append(f"### {hotspot['rank']}. {hotspot['state']} ({hotspot['lane']})")
        lines.append(f"- title: {hotspot['title']}")
        lines.append(f"- elapsed: `{_fmt_hms(hotspot['elapsed_s'])}`")
        lines.append(f"- segment_share: `{100.0 * float(hotspot['segment_share']):.2f}%`")
        lines.append(
            f"- budget_status: `{hotspot['budget']['status']}` (target `{hotspot['budget']['target_hms']}`, stretch `{hotspot['budget']['stretch_hms']}`)"
        )
        lines.append(f"- evidence: `{json.dumps(hotspot['evidence'], sort_keys=True)}`")
        lines.append(f"- code_refs: `{', '.join(hotspot['code_refs'])}`")
        lines.append("")
    lines.append("## Progression Gate")
    lines.append("")
    lines.append(f"- decision: `{payload['progression_gate']['decision']}`")
    lines.append(f"- reason: {payload['progression_gate']['reason']}")
    lines.append(f"- next_state_for_popt1: `{payload['progression_gate']['next_state_for_popt1']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 2B POPT.0 baseline/hotspot artifacts.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2B/reports")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    seed = receipt.get("seed")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    log_path = run_root / f"run_log_{run_id}.log"
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")

    reports: dict[str, dict[str, Any]] = {}
    report_paths: dict[str, str] = {}
    for state in ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]:
        rp = _find_state_report(run_root, state)
        reports[state] = _load_json(rp)
        report_paths[state] = str(rp).replace("\\", "/")

    s7_path = run_root / "data/layer1/2B/s7_audit_report" / f"seed={seed}" / f"manifest_fingerprint={manifest_fingerprint}" / "s7_audit_report.json"
    s8_index_path = run_root / "data/layer1/2B/validation" / f"manifest_fingerprint={manifest_fingerprint}" / "index.json"
    s7_report = _load_json(s7_path)
    s8_index = _load_json(s8_index_path)

    log_window = _parse_log_window(log_path)
    start_by_state = {k: datetime.fromisoformat(v) for k, v in log_window["start_by_state"].items()}
    complete_by_state = {k: datetime.fromisoformat(v) for k, v in log_window["complete_by_state"].items()}

    rows: list[dict[str, Any]] = []
    elapsed_total_s = 0.0
    for state in STATE_ORDER:
        elapsed_s: float | None = None
        if state in start_by_state and state in complete_by_state:
            elapsed_s = (complete_by_state[state] - start_by_state[state]).total_seconds()
            if elapsed_s < 0:
                elapsed_s = None
        if elapsed_s is not None:
            elapsed_total_s += elapsed_s
        rows.append(
            {
                "state": state,
                "elapsed_s": elapsed_s,
                "elapsed_hms": _fmt_hms(elapsed_s),
            }
        )

    for row in rows:
        elapsed = float(row["elapsed_s"] or 0.0)
        row["segment_share"] = (elapsed / elapsed_total_s) if elapsed_total_s > 0 else 0.0

    sorted_rows = sorted((r for r in rows if r["elapsed_s"] is not None), key=lambda r: float(r["elapsed_s"]), reverse=True)
    top_three = sorted_rows[:3]
    lane_by_rank = {1: "primary", 2: "secondary", 3: "closure"}

    hotspots: list[dict[str, Any]] = []
    for idx, row in enumerate(top_three, start=1):
        state = row["state"]
        elapsed_s = float(row["elapsed_s"])
        budget = BUDGETS_S[state]
        status = _status(elapsed_s, budget["target"], budget["stretch"])
        hotspots.append(
            {
                "rank": idx,
                "lane": lane_by_rank[idx],
                "state": state,
                "title": STATE_TITLES[state],
                "elapsed_s": elapsed_s,
                "segment_share": row["segment_share"],
                "budget": {
                    "target_s": budget["target"],
                    "target_hms": _fmt_hms(budget["target"]),
                    "stretch_s": budget["stretch"],
                    "stretch_hms": _fmt_hms(budget["stretch"]),
                    "status": status,
                },
                "evidence": _state_evidence(state, reports, s7_report, s8_index),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
        )

    budgets_payload: dict[str, Any] = {}
    for state in STATE_ORDER:
        budget = BUDGETS_S[state]
        elapsed = float(next((r["elapsed_s"] for r in rows if r["state"] == state and r["elapsed_s"] is not None), 0.0))
        budgets_payload[state] = {
            "target_s": budget["target"],
            "target_hms": _fmt_hms(budget["target"]),
            "stretch_s": budget["stretch"],
            "stretch_hms": _fmt_hms(budget["stretch"]),
            "status": _status(elapsed, budget["target"], budget["stretch"]),
        }

    primary_status = hotspots[0]["budget"]["status"] if hotspots else "GREEN"
    progression_decision = "GO" if primary_status in {"RED", "AMBER"} else "HOLD"
    progression_reason = (
        f"Primary hotspot {hotspots[0]['state']} is {primary_status} vs POPT budget."
        if hotspots
        else "No complete state timing rows were discovered."
    )

    payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "2B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": receipt.get("parameter_hash"),
            "run_log_path": str(log_path).replace("\\", "/"),
            "report_paths": report_paths,
            "s7_report_path": str(s7_path).replace("\\", "/"),
            "s8_index_path": str(s8_index_path).replace("\\", "/"),
        },
        "timing": {
            "segment_elapsed_s": elapsed_total_s,
            "segment_elapsed_hms": _fmt_hms(elapsed_total_s),
            "state_table": rows,
            "log_window": log_window,
        },
        "budgets": budgets_payload,
        "hotspots": hotspots,
        "progression_gate": {
            "decision": progression_decision,
            "reason": progression_reason,
            "next_state_for_popt1": hotspots[0]["state"] if hotspots else None,
        },
    }

    out_root = Path(args.out_root)
    out_json = Path(args.out_json) if args.out_json else out_root / f"segment2b_popt0_baseline_{run_id}.json"
    out_md = Path(args.out_md) if args.out_md else out_root / f"segment2b_popt0_hotspot_map_{run_id}.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
