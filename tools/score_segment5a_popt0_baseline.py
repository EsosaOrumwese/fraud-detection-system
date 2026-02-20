#!/usr/bin/env python3
"""Emit Segment 5A POPT.0 baseline runtime and hotspot/profile artifacts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[[A-Z]+\] ([^:]+): (.*)$")
START_RE = re.compile(r"engine\.layers\.l2\.seg_5A\.s([0-5])_[^:]*: S[0-5]: run log initialized")
COMPLETE_RE = re.compile(r"\bS([0-5]) 5A complete:")
MODULE_STATE_RE = re.compile(r"engine\.layers\.l2\.seg_5A\.s([0-5])_")

STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
STATE_TITLES = {
    "S0": "Upstream gate verification and sealed input hashing",
    "S1": "Merchant-zone demand classification and class profile synthesis",
    "S2": "Weekly shape synthesis and class-zone template materialization",
    "S3": "Baseline intensity composition and normalization",
    "S4": "Scenario calendar overlay expansion and horizon projection",
    "S5": "Validation bundle recomposition checks and digest publication",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l2/seg_5A/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l2/seg_5A/s1_demand_classification/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l2/seg_5A/s2_weekly_shape_library/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l2/seg_5A/s3_baseline_intensity/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l2/seg_5A/s4_calendar_overlays/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l2/seg_5A/s5_validation_bundle/runner.py"],
}

# POPT.0 budget posture: candidate lane <= 20m with state budgets pinned from this baseline.
BUDGETS_S = {
    "S0": {"target": 4.0, "stretch": 6.0},
    "S1": {"target": 10.0, "stretch": 14.0},
    "S2": {"target": 30.0, "stretch": 40.0},
    "S3": {"target": 420.0, "stretch": 520.0},
    "S4": {"target": 360.0, "stretch": 440.0},
    "S5": {"target": 180.0, "stretch": 240.0},
}
LANE_BUDGETS_S = {
    "candidate": {"target": 1200.0, "stretch": 1320.0},
    "witness": {"target": 2400.0, "stretch": 2700.0},
    "certification": {"target": 5400.0, "stretch": 6000.0},
}


@dataclass(frozen=True)
class LogEvent:
    ts: datetime
    module: str
    message: str


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


def _load_json(path: Path) -> Any:
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
    state_dir = run_root / "reports/layer2/5A" / f"state={state}"
    return _find_single(list(state_dir.rglob("run_report.json")), f"{state} run_report.json")


def _parse_log(log_path: Path) -> tuple[list[LogEvent], dict[str, datetime], dict[str, datetime]]:
    events: list[LogEvent] = []
    start_by_state: dict[str, datetime] = {}
    complete_by_state: dict[str, datetime] = {}
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue
        start_match = START_RE.search(line)
        if start_match:
            state = f"S{start_match.group(1)}"
            start_by_state.setdefault(state, ts)
        complete_match = COMPLETE_RE.search(line)
        if complete_match:
            state = f"S{complete_match.group(1)}"
            complete_by_state[state] = ts
        parsed = LOG_LINE_RE.match(line)
        if parsed:
            module = parsed.group(1)
            message = parsed.group(2)
            events.append(LogEvent(ts=ts, module=module, message=message))
    return events, start_by_state, complete_by_state


def _state_events(events: list[LogEvent], state: str) -> list[LogEvent]:
    out: list[LogEvent] = []
    state_num = state[1:]
    for event in events:
        match = MODULE_STATE_RE.search(event.module)
        if match and match.group(1) == state_num:
            out.append(event)
    return out


def _first_ts(events: list[LogEvent], predicate: Callable[[str], bool]) -> datetime | None:
    for event in events:
        if predicate(event.message):
            return event.ts
    return None


def _last_ts(events: list[LogEvent], predicate: Callable[[str], bool]) -> datetime | None:
    for event in reversed(events):
        if predicate(event.message):
            return event.ts
    return None


def _fallback_decomposition(state: str, elapsed_s: float) -> dict[str, float]:
    if state == "S2":
        shares = {
            "input_resolution": 0.10,
            "input_load_schema_validation": 0.16,
            "core_compute": 0.59,
            "output_write_idempotency": 0.15,
        }
    elif state == "S4":
        shares = {
            "input_resolution": 0.06,
            "input_load_schema_validation": 0.18,
            "core_compute": 0.68,
            "output_write_idempotency": 0.08,
        }
    else:
        shares = {
            "input_resolution": 0.10,
            "input_load_schema_validation": 0.17,
            "core_compute": 0.65,
            "output_write_idempotency": 0.08,
        }
    return {k: elapsed_s * v for k, v in shares.items()}


def _decompose_state(
    state: str,
    events: list[LogEvent],
    elapsed_s: float,
    b1_pred: Callable[[str], bool],
    b2_pred: Callable[[str], bool],
    b3_pred: Callable[[str], bool],
    end_pred: Callable[[str], bool],
) -> tuple[dict[str, float], dict[str, str | None], str]:
    if not events:
        return _fallback_decomposition(state, elapsed_s), {}, "fallback_no_events"
    t0 = events[0].ts
    t1 = _first_ts(events, b1_pred)
    t2 = _first_ts(events, b2_pred)
    t3 = _first_ts(events, b3_pred)
    te = _last_ts(events, end_pred) or events[-1].ts
    if t1 is None or t2 is None or t3 is None:
        return _fallback_decomposition(state, elapsed_s), {
            "start": t0.isoformat(),
            "end": te.isoformat(),
        }, "fallback_missing_markers"
    if not (t0 <= t1 <= t2 <= t3 <= te):
        return _fallback_decomposition(state, elapsed_s), {
            "start": t0.isoformat(),
            "b1": t1.isoformat(),
            "b2": t2.isoformat(),
            "b3": t3.isoformat(),
            "end": te.isoformat(),
        }, "fallback_non_monotonic_markers"
    raw = {
        "input_resolution": (t1 - t0).total_seconds(),
        "input_load_schema_validation": (t2 - t1).total_seconds(),
        "core_compute": (t3 - t2).total_seconds(),
        "output_write_idempotency": (te - t3).total_seconds(),
    }
    raw_total = sum(max(v, 0.0) for v in raw.values())
    if raw_total <= 0:
        return _fallback_decomposition(state, elapsed_s), {
            "start": t0.isoformat(),
            "end": te.isoformat(),
        }, "fallback_zero_raw_total"
    scale = elapsed_s / raw_total
    scaled = {k: max(v, 0.0) * scale for k, v in raw.items()}
    markers = {
        "start": t0.isoformat(),
        "input_resolution_end": t1.isoformat(),
        "input_load_schema_validation_end": t2.isoformat(),
        "output_write_start": t3.isoformat(),
        "end": te.isoformat(),
    }
    return scaled, markers, "derived_from_log_markers"


def _state_evidence(state: str, reports: dict[str, dict[str, Any]], s0_receipt: dict[str, Any]) -> dict[str, Any]:
    if state == "S0":
        return {
            "sealed_inputs_count_total": s0_receipt.get("sealed_inputs_count_total"),
            "sealed_inputs_count_by_role": s0_receipt.get("sealed_inputs_count_by_role"),
            "upstream_segments": sorted((s0_receipt.get("upstream_gates") or {}).keys()),
        }
    if state == "S1":
        counts = reports["S1"].get("counts", {})
        return {
            "rows_emitted": counts.get("profile_rows"),
            "merchants_total": counts.get("merchants_total"),
            "zones_total": counts.get("zones_total"),
            "countries_total": counts.get("countries_total"),
        }
    if state == "S2":
        counts = reports["S2"].get("counts", {})
        return {
            "shape_rows": counts.get("shape_rows"),
            "domain_rows": counts.get("domain_rows"),
            "template_rows": counts.get("template_rows"),
            "grid_rows": counts.get("grid_rows"),
        }
    if state == "S3":
        counts = reports["S3"].get("counts", {})
        return {
            "baseline_rows": counts.get("baseline_rows"),
            "domain_rows": counts.get("domain_rows"),
            "shape_rows": counts.get("shape_rows"),
            "grid_rows": counts.get("grid_rows"),
        }
    if state == "S4":
        counts = reports["S4"].get("counts", {})
        return {
            "scenario_rows": counts.get("scenario_rows"),
            "overlay_rows": counts.get("overlay_rows"),
            "event_rows": counts.get("event_rows"),
            "domain_rows": counts.get("domain_rows"),
        }
    if state == "S5":
        counts = reports["S5"].get("counts", {})
        return {
            "s1_rows": counts.get("s1_rows"),
            "s1_merchants": counts.get("s1_merchants"),
            "s1_tzids": counts.get("s1_tzids"),
            "s1_countries": counts.get("s1_countries"),
        }
    return {}


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S4":
        return [
            "Reduce repeated schema scans in S4 by collecting schema once and reusing validated projections.",
            "Collapse horizon-mapping and scope-key materializations to minimize intermediate allocations.",
            "Tighten overlay expansion loops to avoid avoidable recompute across identical scope keys.",
        ]
    if state == "S5":
        return [
            "Replace repeated LazyFrame column-introspection with collect_schema() once per dataset.",
            "Bound recomposition sample passes and avoid redundant full-width scans for already-validated subsets.",
            "Keep bundle publication idempotent while reducing duplicate digest/readback overhead.",
        ]
    if state == "S3":
        return [
            "Streamline baseline validation passes to reduce repeated high-volume scan cost before publish.",
            "Precompute class-zone lookup maps once and reuse through baseline composition path.",
            "Minimize repeated projection/cast operations inside core synthesis loops.",
        ]
    if state == "S2":
        return [
            "Reuse compiled template intermediates across zones with identical class/channel modifiers.",
            "Reduce post-compute write overhead by tighter projection/chunk policy on parquet writes.",
            "Avoid repeated path-resolution and sealed-input fallback checks in inner path.",
        ]
    return [
        "Profile hot loops and remove repeated work on dominant wall-time path.",
        "Lower I/O amplification while preserving deterministic output bytes.",
    ]


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Segment 5A POPT.0 Baseline and Hotspot Map")
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
        budget = payload["budgets"]["state"][state]
        share = f"{100.0 * float(row['segment_share']):.2f}%"
        lines.append(
            f"| {state} | {row['elapsed_hms']} | {share} | {budget['target_hms']} | {budget['stretch_hms']} | {budget['status']} |"
        )
    lines.append("")
    lane = payload["budgets"]["lane"]["candidate"]
    lines.append(
        f"- candidate_lane_budget: target `{lane['target_hms']}` stretch `{lane['stretch_hms']}` status `{lane['status']}`"
    )
    lines.append(f"- segment_elapsed: `{payload['timing']['segment_elapsed_hms']}`")
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
    parser = argparse.ArgumentParser(description="Emit Segment 5A POPT.0 baseline/hotspot/profile artifacts.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_5A")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5A/reports")
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
    for state in ["S1", "S2", "S3", "S4", "S5"]:
        rp = _find_state_report(run_root, state)
        reports[state] = _load_json(rp)
        report_paths[state] = str(rp).replace("\\", "/")

    s0_receipt_path = (
        run_root
        / "data/layer2/5A/s0_gate_receipt"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s0_gate_receipt_5A.json"
    )
    s0_receipt = _load_json(s0_receipt_path)

    events, start_by_state, complete_by_state = _parse_log(log_path)
    rows: list[dict[str, Any]] = []
    elapsed_total_s = 0.0

    s0_elapsed = None
    if "S0" in start_by_state and "S0" in complete_by_state:
        s0_elapsed = max((complete_by_state["S0"] - start_by_state["S0"]).total_seconds(), 0.0)
    s0_elapsed = float(s0_elapsed or 0.0)
    rows.append({"state": "S0", "elapsed_s": s0_elapsed, "elapsed_hms": _fmt_hms(s0_elapsed)})
    elapsed_total_s += s0_elapsed

    for state in ["S1", "S2", "S3", "S4", "S5"]:
        elapsed = float(reports[state].get("durations", {}).get("wall_ms", 0.0)) / 1000.0
        rows.append({"state": state, "elapsed_s": elapsed, "elapsed_hms": _fmt_hms(elapsed)})
        elapsed_total_s += elapsed

    for row in rows:
        row["segment_share"] = row["elapsed_s"] / elapsed_total_s if elapsed_total_s > 0 else 0.0

    log_starts = list(start_by_state.values())
    log_ends = list(complete_by_state.values())
    log_window_elapsed = (max(log_ends) - min(log_starts)).total_seconds() if log_starts and log_ends else None

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
                "evidence": _state_evidence(state, reports, s0_receipt),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
        )

    state_budgets: dict[str, Any] = {}
    for row in rows:
        state = row["state"]
        budget = BUDGETS_S[state]
        state_budgets[state] = {
            "target_s": budget["target"],
            "target_hms": _fmt_hms(budget["target"]),
            "stretch_s": budget["stretch"],
            "stretch_hms": _fmt_hms(budget["stretch"]),
            "status": _status(row["elapsed_s"], budget["target"], budget["stretch"]),
        }

    lane_budgets: dict[str, Any] = {}
    for lane, budget in LANE_BUDGETS_S.items():
        lane_budgets[lane] = {
            "target_s": budget["target"],
            "target_hms": _fmt_hms(budget["target"]),
            "stretch_s": budget["stretch"],
            "stretch_hms": _fmt_hms(budget["stretch"]),
            "status": _status(elapsed_total_s, budget["target"], budget["stretch"]),
        }

    s2_events = _state_events(events, "S2")
    s4_events = _state_events(events, "S4")
    s5_events = _state_events(events, "S5")

    s2_lanes, s2_markers, s2_basis = _decompose_state(
        "S2",
        s2_events,
        float(reports["S2"].get("durations", {}).get("wall_ms", 0.0)) / 1000.0,
        lambda msg: msg.startswith("Contracts layout="),
        lambda msg: "domain derived from merchant_zone_profile_5A" in msg,
        lambda msg: msg.startswith("S2: published "),
        lambda msg: "S2: completed weekly shape synthesis" in msg,
    )
    s4_lanes, s4_markers, s4_basis = _decompose_state(
        "S4",
        s4_events,
        float(reports["S4"].get("durations", {}).get("wall_ms", 0.0)) / 1000.0,
        lambda msg: msg.startswith("Contracts layout="),
        lambda msg: "horizon mapping built" in msg,
        lambda msg: msg.startswith("S4: published "),
        lambda msg: "S4: completed scenario overlay synthesis" in msg,
    )
    s5_lanes, s5_markers, s5_basis = _decompose_state(
        "S5",
        s5_events,
        float(reports["S5"].get("durations", {}).get("wall_ms", 0.0)) / 1000.0,
        lambda msg: msg.startswith("Contracts layout="),
        lambda msg: msg.startswith("S5: discovered scenarios="),
        lambda msg: msg.startswith("S5: bundle published path=") or "bundle already exists and is identical" in msg,
        lambda msg: "S5: bundle complete" in msg,
    )

    profile_payloads = {
        "S2": {
            "state": "S2",
            "run_id": run_id,
            "segment": "5A",
            "basis": s2_basis,
            "markers": s2_markers,
            "lane_seconds": s2_lanes,
            "lane_share_of_state": {
                k: (v / max(float(reports["S2"].get("durations", {}).get("wall_ms", 0.0)) / 1000.0, 1e-9))
                for k, v in s2_lanes.items()
            },
            "evidence": _state_evidence("S2", reports, s0_receipt),
            "report_path": report_paths["S2"],
        },
        "S4": {
            "state": "S4",
            "run_id": run_id,
            "segment": "5A",
            "basis": s4_basis,
            "markers": s4_markers,
            "lane_seconds": s4_lanes,
            "lane_share_of_state": {
                k: (v / max(float(reports["S4"].get("durations", {}).get("wall_ms", 0.0)) / 1000.0, 1e-9))
                for k, v in s4_lanes.items()
            },
            "evidence": _state_evidence("S4", reports, s0_receipt),
            "report_path": report_paths["S4"],
        },
        "S5": {
            "state": "S5",
            "run_id": run_id,
            "segment": "5A",
            "basis": s5_basis,
            "markers": s5_markers,
            "lane_seconds": s5_lanes,
            "lane_share_of_state": {
                k: (v / max(float(reports["S5"].get("durations", {}).get("wall_ms", 0.0)) / 1000.0, 1e-9))
                for k, v in s5_lanes.items()
            },
            "evidence": _state_evidence("S5", reports, s0_receipt),
            "report_path": report_paths["S5"],
        },
    }

    candidate_status = lane_budgets["candidate"]["status"]
    primary = hotspots[0]["state"] if hotspots else None
    decision = "GO_POPT1" if candidate_status in {"RED", "AMBER"} else "HOLD_POPT0_REOPEN"
    reason = (
        f"Candidate lane is {candidate_status} vs pinned budget and hotspot {primary} dominates wall-time."
        if primary
        else "No hotspot rows available."
    )

    payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "5A",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "seed": seed,
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": receipt.get("parameter_hash"),
            "run_log_path": str(log_path).replace("\\", "/"),
            "report_paths": report_paths,
            "s0_receipt_path": str(s0_receipt_path).replace("\\", "/"),
        },
        "timing": {
            "segment_elapsed_s": elapsed_total_s,
            "segment_elapsed_hms": _fmt_hms(elapsed_total_s),
            "state_table": rows,
            "log_window": {
                "start_by_state": {k: v.isoformat() for k, v in sorted(start_by_state.items())},
                "complete_by_state": {k: v.isoformat() for k, v in sorted(complete_by_state.items())},
                "segment_window_elapsed_s": log_window_elapsed,
                "segment_window_elapsed_hms": _fmt_hms(log_window_elapsed),
            },
        },
        "budgets": {
            "state": state_budgets,
            "lane": lane_budgets,
        },
        "hotspots": hotspots,
        "profiles": profile_payloads,
        "progression_gate": {
            "decision": decision,
            "reason": reason,
            "next_state_for_popt1": primary,
        },
    }

    out_root = Path(args.out_root)
    out_json = Path(args.out_json) if args.out_json else out_root / f"segment5a_popt0_baseline_{run_id}.json"
    out_md = Path(args.out_md) if args.out_md else out_root / f"segment5a_popt0_hotspot_map_{run_id}.md"
    out_s2 = out_root / f"segment5a_popt0_profile_s2_{run_id}.json"
    out_s4 = out_root / f"segment5a_popt0_profile_s4_{run_id}.json"
    out_s5 = out_root / f"segment5a_popt0_profile_s5_{run_id}.json"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    out_s2.write_text(json.dumps(profile_payloads["S2"], indent=2, sort_keys=True), encoding="utf-8")
    out_s4.write_text(json.dumps(profile_payloads["S4"], indent=2, sort_keys=True), encoding="utf-8")
    out_s5.write_text(json.dumps(profile_payloads["S5"], indent=2, sort_keys=True), encoding="utf-8")

    print(str(out_json))
    print(str(out_md))
    print(str(out_s2))
    print(str(out_s4))
    print(str(out_s5))


if __name__ == "__main__":
    main()
