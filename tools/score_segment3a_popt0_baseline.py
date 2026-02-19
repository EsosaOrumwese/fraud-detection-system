#!/usr/bin/env python3
"""Emit Segment 3A POPT.0 baseline runtime and hotspot artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
START_RE = re.compile(r"engine\.layers\.l1\.seg_3A\.s([0-7])_[^:]*: S[0-7]: run log initialized")
FALLBACK_START_RE = re.compile(r"engine\.layers\.l1\.seg_3A\.s([0-7])_[^:]*:")
COMPLETE_RE = re.compile(r"\bS([0-7]) 3A complete:")

STATE_ORDER = [f"S{i}" for i in range(8)]
STATE_TITLES = {
    "S0": "Gate verification and sealed-input inventory",
    "S1": "Escalation queue classification path",
    "S2": "Country-zone prior derivation",
    "S3": "Dirichlet zone-share sampling for escalated pairs",
    "S4": "Integerized zone-count materialization",
    "S5": "Zone allocation projection and universe hash sealing",
    "S6": "Validation checks and issue table publication",
    "S7": "Validation bundle assembly and digest pass",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l1/seg_3A/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l1/seg_3A/s2_priors/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l1/seg_3A/s5_zone_alloc/runner.py"],
    "S6": ["packages/engine/src/engine/layers/l1/seg_3A/s6_validation/runner.py"],
    "S7": ["packages/engine/src/engine/layers/l1/seg_3A/s7_validation_bundle/runner.py"],
}

# Tight second-scale budgets to force hotspot surfacing for POPT.1 closure.
BUDGETS_S = {
    "S0": {"target": 1.5, "stretch": 2.5},
    "S1": {"target": 3.0, "stretch": 4.5},
    "S2": {"target": 4.0, "stretch": 6.0},
    "S3": {"target": 5.0, "stretch": 7.5},
    "S4": {"target": 6.0, "stretch": 9.0},
    "S5": {"target": 8.0, "stretch": 12.0},
    "S6": {"target": 10.0, "stretch": 14.0},
    "S7": {"target": 8.0, "stretch": 12.0},
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
    state_dir = run_root / "reports/layer1/3A" / f"state={state}"
    return _find_single(list(state_dir.rglob("run_report.json")), f"{state} run_report.json")


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


def _state_evidence(
    state: str,
    reports: dict[str, dict[str, Any]],
    s0_receipt: dict[str, Any],
    sealed_inputs: list[dict[str, Any]],
    s7_index: dict[str, Any],
) -> dict[str, Any]:
    if state == "S0":
        gates = s0_receipt.get("upstream_gates", {})
        return {
            "upstream_gate_count": len(gates),
            "sealed_policy_count": len(s0_receipt.get("sealed_policy_set", [])),
            "sealed_input_count": len(sealed_inputs),
        }
    if state == "S1":
        r = reports["S1"]
        return {
            "pairs_total": r.get("counts", {}).get("pairs_total"),
            "pairs_escalated": r.get("counts", {}).get("pairs_escalated"),
            "pairs_monolithic": r.get("counts", {}).get("pairs_monolithic"),
            "forced_escalation": r.get("reason_counts", {}).get("forced_escalation"),
        }
    if state == "S2":
        r = reports["S2"]
        return {
            "countries_total": r.get("counts", {}).get("countries_total"),
            "zones_total": r.get("counts", {}).get("zones_total"),
            "floors_applied": r.get("counts", {}).get("floors_applied"),
            "bumps_applied": r.get("counts", {}).get("bumps_applied"),
        }
    if state == "S3":
        r = reports["S3"]
        return {
            "pairs_escalated": r.get("counts", {}).get("pairs_escalated"),
            "rows_total": r.get("counts", {}).get("rows_total"),
            "rng_events": r.get("counts", {}).get("rng_events"),
            "rng_draws": r.get("rng_totals", {}).get("draws"),
        }
    if state == "S4":
        r = reports["S4"]
        return {
            "pairs_escalated": r.get("counts", {}).get("pairs_escalated"),
            "pairs_count_conserved": r.get("counts", {}).get("pairs_count_conserved"),
            "pairs_with_single_zone_nonzero": r.get("counts", {}).get("pairs_with_single_zone_nonzero"),
            "zone_rows_total": r.get("counts", {}).get("zone_rows_total"),
        }
    if state == "S5":
        r = reports["S5"]
        return {
            "pairs_escalated": r.get("counts", {}).get("pairs_escalated"),
            "zone_rows_total": r.get("counts", {}).get("zone_rows_total"),
            "pairs_count_conservation_violations": r.get("counts", {}).get("pairs_count_conservation_violations"),
            "routing_universe_hash": r.get("digests", {}).get("routing_universe_hash"),
        }
    if state == "S6":
        r = reports["S6"]
        return {
            "issues_total": r.get("counts", {}).get("issues_total"),
            "issues_error": r.get("counts", {}).get("issues_error"),
            "issues_warn": r.get("counts", {}).get("issues_warn"),
            "zone_alloc_rows": r.get("counts", {}).get("zone_alloc_rows"),
        }
    if state == "S7":
        r = reports["S7"]
        files = s7_index.get("files", [])
        return {
            "member_count": r.get("counts", {}).get("member_count"),
            "member_bytes": r.get("counts", {}).get("member_bytes"),
            "files_indexed": len(files),
            "has_passed_flag": any(str(item.get("path", "")).endswith("_passed.flag") for item in files if isinstance(item, dict)),
        }
    return {}


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S6":
        return [
            "Reduce validation-input reload overhead by caching immutable manifests once per run.",
            "Trim check-loop DataFrame materialization and keep scalar counters in a single pass.",
            "Defer expensive optional diagnostics behind explicit debug flags.",
        ]
    if state == "S7":
        return [
            "Avoid repeated member readback during bundle assembly when digest inputs are unchanged.",
            "Batch index member validation to reduce filesystem round-trips.",
            "Keep serialization at summary granularity only for fast iteration lanes.",
        ]
    if state == "S5":
        return [
            "Reduce zone_alloc write-path overhead via tighter projection and chunk sizing.",
            "Minimize non-essential digest/readback passes while preserving contract requirements.",
            "Hoist invariant hash inputs outside row-wise loops.",
        ]
    return [
        "Profile inner path and remove repeated work on the hot loop.",
        "Tighten I/O footprint while preserving deterministic output bytes.",
    ]


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Segment 3A POPT.0 Baseline and Hotspot Map")
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
    parser = argparse.ArgumentParser(description="Emit Segment 3A POPT.0 baseline/hotspot artifacts.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3A")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_3A/reports")
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
    for state in ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]:
        rp = _find_state_report(run_root, state)
        reports[state] = _load_json(rp)
        report_paths[state] = str(rp).replace("\\", "/")

    s0_receipt_path = (
        run_root
        / "data/layer1/3A/s0_gate_receipt"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s0_gate_receipt_3A.json"
    )
    sealed_inputs_path = (
        run_root
        / "data/layer1/3A/sealed_inputs"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "sealed_inputs_3A.json"
    )
    s7_index_path = (
        run_root
        / "data/layer1/3A/validation"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "index.json"
    )
    s0_receipt = _load_json(s0_receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)
    s7_index = _load_json(s7_index_path)

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
        rows.append({"state": state, "elapsed_s": elapsed_s, "elapsed_hms": _fmt_hms(elapsed_s)})

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
                "evidence": _state_evidence(state, reports, s0_receipt, sealed_inputs, s7_index),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
        )

    budgets_payload: dict[str, Any] = {}
    for state in STATE_ORDER:
        budget = BUDGETS_S[state]
        elapsed = next((r["elapsed_s"] for r in rows if r["state"] == state), None)
        if elapsed is None:
            status = "MISSING"
        else:
            status = _status(float(elapsed), budget["target"], budget["stretch"])
        budgets_payload[state] = {
            "target_s": budget["target"],
            "target_hms": _fmt_hms(budget["target"]),
            "stretch_s": budget["stretch"],
            "stretch_hms": _fmt_hms(budget["stretch"]),
            "status": status,
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
        "segment": "3A",
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
            "sealed_inputs_path": str(sealed_inputs_path).replace("\\", "/"),
            "s7_index_path": str(s7_index_path).replace("\\", "/"),
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
    out_json = Path(args.out_json) if args.out_json else out_root / f"segment3a_popt0_baseline_{run_id}.json"
    out_md = Path(args.out_md) if args.out_md else out_root / f"segment3a_popt0_hotspot_map_{run_id}.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
