#!/usr/bin/env python3
"""Emit Segment 2A POPT.0 baseline runtime and hotspot artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
START_RE = re.compile(r"engine\.layers\.l1\.seg_2A\.s([0-5])_.*: S[0-5]: run log initialized")
COMPLETE_RE = re.compile(r"\bS([0-5]) 2A complete:")

STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
STATE_TITLES = {
    "S0": "Gate + sealed-input hashing and receipt publication",
    "S1": "Timezone polygon lookup and ambiguity resolution path",
    "S2": "Override precedence application and parquet emit path",
    "S3": "TZDB parse/compile and timetable cache canonicalization",
    "S4": "Legality coverage scan against timetable cache",
    "S5": "Validation bundle assembly and digest pass",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l1/seg_2A/s3_timetable/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l1/seg_2A/s4_legality/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l1/seg_2A/s5_validation_bundle/runner.py"],
}

# Budgets are intentionally tight to keep 2A in a minute-scale fast-iteration lane.
BUDGETS_S = {
    "S1": {"target": 10.0, "stretch": 12.0},
    "S3": {"target": 8.0, "stretch": 10.0},
    "S2": {"target": 7.0, "stretch": 9.0},
    "S0": {"target": 2.0, "stretch": 3.0},
    "S4": {"target": 1.0, "stretch": 2.0},
    "S5": {"target": 0.5, "stretch": 1.0},
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
    state_lower = state.lower()
    return _find_single(
        list((run_root / "reports/layer1/2A").glob(f"state={state}/**/{state_lower}_run_report.json")),
        f"{state_lower}_run_report.json",
    )


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
        mc = COMPLETE_RE.search(line)
        if mc:
            state = f"S{mc.group(1)}"
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


def _state_evidence(state: str, report: dict[str, Any]) -> dict[str, Any]:
    if state == "S0":
        return {
            "sealed_inputs_count": report.get("sealed_inputs", {}).get("count"),
            "sealed_inputs_bytes_total": report.get("sealed_inputs", {}).get("bytes_total"),
            "tzid_index_count": report.get("tz_assets", {}).get("tzid_index_count"),
            "tz_world_feature_count": report.get("tz_assets", {}).get("tz_world_feature_count"),
        }
    if state == "S1":
        counts = report.get("counts", {})
        return {
            "sites_total": counts.get("sites_total"),
            "rows_emitted": counts.get("rows_emitted"),
            "distinct_tzids": counts.get("distinct_tzids"),
            "overrides_applied": counts.get("overrides_applied"),
            "border_nudged": counts.get("border_nudged"),
            "fallback_nearest_within_threshold": counts.get("fallback_nearest_within_threshold"),
            "fallback_nearest_outside_threshold": counts.get("fallback_nearest_outside_threshold"),
        }
    if state == "S2":
        counts = report.get("counts", {})
        return {
            "sites_total": counts.get("sites_total"),
            "rows_emitted": counts.get("rows_emitted"),
            "distinct_tzids": counts.get("distinct_tzids"),
            "overridden_total": counts.get("overridden_total"),
            "overridden_by_scope": counts.get("overridden_by_scope"),
        }
    if state == "S3":
        return {
            "tzid_count": report.get("compiled", {}).get("tzid_count"),
            "transitions_total": report.get("compiled", {}).get("transitions_total"),
            "rle_cache_bytes": report.get("compiled", {}).get("rle_cache_bytes"),
            "adjustments_count": report.get("adjustments", {}).get("count"),
        }
    if state == "S4":
        counts = report.get("counts", {})
        return {
            "sites_total": counts.get("sites_total"),
            "tzids_total": counts.get("tzids_total"),
            "fold_windows_total": counts.get("fold_windows_total"),
            "gap_windows_total": counts.get("gap_windows_total"),
        }
    if state == "S5":
        return {
            "files_indexed": report.get("bundle", {}).get("files_indexed"),
            "bytes_indexed": report.get("bundle", {}).get("bytes_indexed"),
            "seeds_discovered": report.get("seeds", {}).get("discovered"),
            "digest_matches_flag": report.get("digest", {}).get("matches_flag"),
        }
    return {}


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S1":
        return [
            "Reduce polygon candidate resolution overhead with stronger country-level spatial index reuse.",
            "Trim fallback-path geometry calls by caching same-country nearest lookups within a run.",
            "Lower per-ambiguity logging/serialization overhead while keeping required audit counters.",
        ]
    if state == "S3":
        return [
            "Avoid unnecessary TZDB parse work when release tag + digest are unchanged for the lane.",
            "Tighten timetable compile memory layout to cut transition canonicalization overhead.",
            "Persist deterministic timetable cache fingerprints to skip redundant rebuilds.",
        ]
    if state == "S2":
        return [
            "Pre-index override keys to reduce repeated precedence lookups in the write loop.",
            "Minimize parquet write overhead by tighter chunk sizing and projection control.",
            "Keep scope counters aggregated in-process and emit once per checkpoint cadence.",
        ]
    if state == "S0":
        return [
            "Reuse deterministic hash manifests for immutable references in fix-data-engine lanes.",
            "Avoid repeated schema-load overhead by reusing validator objects per process.",
        ]
    if state == "S4":
        return [
            "Keep legality scan vectorized and avoid repeated cache metadata decoding.",
            "Gate verbose diagnostics behind explicit debug flags only.",
        ]
    if state == "S5":
        return [
            "Keep validation bundle indexing strictly minimal and stream-only.",
            "Avoid non-essential digest/readback passes when evidence set is unchanged.",
        ]
    return []


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Segment 2A POPT.0 Baseline and Hotspot Map")
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
            f"| {state} | {row['elapsed_hms']} | {share} | {budget['target_hms']} | {budget['stretch_hms']} | {budget['status']} |"
        )
    lines.append("")
    lines.append(f"- report_wall_elapsed: `{payload['timing']['segment_elapsed_hms']}`")
    lines.append(
        f"- log_window_elapsed: `{payload['timing']['log_window'].get('segment_window_elapsed_hms') or 'n/a'}`"
    )
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
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 2A POPT.0 baseline/hotspot artifacts.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_2A/reports")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    log_path = run_root / f"run_log_{run_id}.log"
    if not log_path.exists():
        raise FileNotFoundError(f"Run log not found: {log_path}")

    reports: dict[str, dict[str, Any]] = {}
    report_paths: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    elapsed_total_s = 0.0

    for state in STATE_ORDER:
        report_path = _find_state_report(run_root, state)
        report = _load_json(report_path)
        reports[state] = report
        report_paths[state] = str(report_path).replace("\\", "/")
        elapsed_s = float(report.get("durations", {}).get("wall_ms", 0.0)) / 1000.0
        elapsed_total_s += elapsed_s
        rows.append(
            {
                "state": state,
                "elapsed_s": elapsed_s,
                "elapsed_hms": _fmt_hms(elapsed_s),
            }
        )

    for row in rows:
        row["segment_share"] = row["elapsed_s"] / elapsed_total_s if elapsed_total_s > 0 else 0.0

    log_window = _parse_log_window(log_path)
    sorted_rows = sorted(rows, key=lambda r: r["elapsed_s"], reverse=True)
    top_three = sorted_rows[:3]
    lane_by_rank = {1: "primary", 2: "secondary", 3: "closure"}

    hotspots: list[dict[str, Any]] = []
    for idx, row in enumerate(top_three, start=1):
        state = row["state"]
        budget = BUDGETS_S[state]
        status = _status(row["elapsed_s"], budget["target"], budget["stretch"])
        hotspots.append(
            {
                "rank": idx,
                "lane": lane_by_rank[idx],
                "state": state,
                "title": STATE_TITLES[state],
                "elapsed_s": row["elapsed_s"],
                "segment_share": row["segment_share"],
                "budget": {
                    "target_s": budget["target"],
                    "target_hms": _fmt_hms(budget["target"]),
                    "stretch_s": budget["stretch"],
                    "stretch_hms": _fmt_hms(budget["stretch"]),
                    "status": status,
                },
                "evidence": _state_evidence(state, reports[state]),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
        )

    primary_status = hotspots[0]["budget"]["status"] if hotspots else "GREEN"
    progression_decision = "GO" if primary_status in {"RED", "AMBER"} else "HOLD"
    progression_reason = (
        f"Primary hotspot {hotspots[0]['state']} is {primary_status} vs tight budget."
        if hotspots
        else "No hotspot rows available."
    )

    budgets_payload: dict[str, Any] = {}
    for state in STATE_ORDER:
        budget = BUDGETS_S[state]
        elapsed = next((r["elapsed_s"] for r in rows if r["state"] == state), 0.0)
        budgets_payload[state] = {
            "target_s": budget["target"],
            "target_hms": _fmt_hms(budget["target"]),
            "stretch_s": budget["stretch"],
            "stretch_hms": _fmt_hms(budget["stretch"]),
            "status": _status(elapsed, budget["target"], budget["stretch"]),
        }

    payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "2A",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "seed": receipt.get("seed"),
            "manifest_fingerprint": receipt.get("manifest_fingerprint"),
            "parameter_hash": receipt.get("parameter_hash"),
            "run_log_path": str(log_path).replace("\\", "/"),
            "report_paths": report_paths,
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
    out_json = (
        Path(args.out_json)
        if args.out_json
        else out_root / f"segment2a_popt0_baseline_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else out_root / f"segment2a_popt0_hotspot_map_{run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()

