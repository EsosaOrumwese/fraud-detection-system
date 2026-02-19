#!/usr/bin/env python3
"""Emit Segment 3B POPT.0 baseline runtime and hotspot artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
S0_ELAPSED_RE = re.compile(r"S0: completed gate and sealed inputs \(elapsed=([0-9.]+)s\)")
S5_COMPLETE_RE = re.compile(r"\bS5 3B complete:")

STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
STATE_TITLES = {
    "S0": "Gate verification and sealed-input inventory",
    "S1": "Virtual merchant classification and settlement-node build",
    "S2": "Edge-catalogue synthesis with jitter/tz assignment",
    "S3": "Alias table and universe-hash construction",
    "S4": "Virtual routing policy and validation contract build",
    "S5": "Validation bundle assembly and digest pass",
}
STATE_CODE_REFS = {
    "S0": ["packages/engine/src/engine/layers/l1/seg_3B/s0_gate/runner.py"],
    "S1": ["packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py"],
    "S2": ["packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py"],
    "S3": ["packages/engine/src/engine/layers/l1/seg_3B/s3_alias_tables/runner.py"],
    "S4": ["packages/engine/src/engine/layers/l1/seg_3B/s4_virtual_contracts/runner.py"],
    "S5": ["packages/engine/src/engine/layers/l1/seg_3B/s5_validation_bundle/runner.py"],
}

# Build-plan runtime budgets (lane-level) for POPT.0.
LANE_BUDGETS_S = {
    "fast_candidate_lane": 15 * 60,
    "witness_lane": 30 * 60,
    "certification_lane": 75 * 60,
}


def _parse_ts(line: str) -> datetime | None:
    match = TS_RE.match(line)
    if not match:
        return None
    return datetime.strptime(f"{match.group(1)}.{match.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


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
    state_dir = run_root / "reports/layer1/3B" / f"state={state}"
    return _find_single(list(state_dir.rglob("run_report.json")), f"{state} run_report.json")


def _parse_log_metrics(log_path: Path) -> dict[str, Any]:
    s0_start_ts: datetime | None = None
    s0_elapsed_s: float | None = None
    s5_complete_ts: datetime | None = None

    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue

        if "S0: run log initialized" in line:
            s0_start_ts = ts

        m_s0 = S0_ELAPSED_RE.search(line)
        if m_s0:
            s0_elapsed_s = float(m_s0.group(1))

        if S5_COMPLETE_RE.search(line):
            s5_complete_ts = ts

    log_window_elapsed_s: float | None = None
    if s0_start_ts is not None and s5_complete_ts is not None:
        log_window_elapsed_s = (s5_complete_ts - s0_start_ts).total_seconds()

    return {
        "s0_start_ts": s0_start_ts.isoformat() if s0_start_ts else None,
        "s0_elapsed_s": s0_elapsed_s,
        "s5_complete_ts": s5_complete_ts.isoformat() if s5_complete_ts else None,
        "segment_window_elapsed_s": log_window_elapsed_s,
        "segment_window_elapsed_hms": _fmt_hms(log_window_elapsed_s),
    }


def _state_evidence(
    state: str,
    reports: dict[str, dict[str, Any]],
    s0_receipt: dict[str, Any],
    sealed_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    if state == "S0":
        return {
            "upstream_gate_count": len(s0_receipt.get("upstream_gates", {})),
            "sealed_policy_count": len(s0_receipt.get("sealed_policy_set", [])),
            "sealed_input_count": len(sealed_inputs),
        }
    if state == "S1":
        counts = reports["S1"].get("counts", {})
        return {
            "merchants_total": counts.get("merchants_total"),
            "virtual_merchants": counts.get("virtual_merchants"),
            "settlement_rows": counts.get("settlement_rows"),
        }
    if state == "S2":
        report = reports["S2"]
        counts = report.get("counts", {})
        return {
            "merchants_total": counts.get("merchants_total"),
            "edges_total": counts.get("edges_total"),
            "rng_events_total": counts.get("rng_events_total"),
            "rng_draws_total": counts.get("rng_draws_total"),
            "jitter_resamples_total": counts.get("jitter_resamples_total"),
        }
    if state == "S3":
        counts = reports["S3"].get("counts", {})
        return {
            "merchants_total": counts.get("merchants_total"),
            "edges_total": counts.get("edges_total"),
            "fallback_uniform_total": counts.get("fallback_uniform_total"),
        }
    if state == "S4":
        counts = reports["S4"].get("counts", {})
        return {
            "virtual_merchants": counts.get("virtual_merchants"),
            "edge_total": counts.get("edge_total"),
            "validation_tests": counts.get("validation_tests"),
        }
    if state == "S5":
        counts = reports["S5"].get("counts", {})
        return {
            "virtual_merchants": counts.get("virtual_merchants"),
            "edge_total": counts.get("edge_total"),
            "validation_tests": counts.get("validation_tests"),
        }
    return {}


def _candidate_actions_for_state(state: str) -> list[str]:
    if state == "S2":
        return [
            "Optimize tile-allocation and edge-placement loops to reduce country-level reload and per-edge overhead.",
            "Tighten tz resolution path to minimize repeated polygon/nearest computations inside jitter loop.",
            "Reduce high-frequency progress logging overhead while preserving required audit counters.",
        ]
    if state == "S5":
        return [
            "Streamline RNG event hashing path to reduce scan time over edge_jitter event parts.",
            "Avoid redundant readbacks when bundle member digests are already available in-memory.",
            "Keep deterministic digest law intact while reducing per-file open/close churn.",
        ]
    if state == "S4":
        return [
            "Tighten validation-contract row construction and avoid repeated materialization.",
            "Precompute stable invariants for alias/index comparisons to reduce repeated scans.",
            "Keep strict checks but lower overhead in the non-failure fast path.",
        ]
    return [
        "Profile hot loop and remove repeated work while preserving deterministic outputs.",
        "Lower I/O overhead without weakening contract checks.",
    ]


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Segment 3B POPT.0 Baseline and Hotspot Map")
    lines.append("")
    lines.append(f"- authority_run_id: `{payload['run']['run_id']}`")
    lines.append(f"- authority_runs_root: `{payload['run']['runs_root']}`")
    lines.append(f"- seed: `{payload['run']['seed']}`")
    lines.append(f"- manifest_fingerprint: `{payload['run']['manifest_fingerprint']}`")
    lines.append("")
    lines.append("## Runtime Table")
    lines.append("")
    lines.append("| State | Elapsed | Share |")
    lines.append("|---|---:|---:|")
    for row in payload["timing"]["state_table"]:
        share = f"{100.0 * float(row['segment_share']):.2f}%" if row["segment_share"] is not None else "n/a"
        lines.append(f"| {row['state']} | {row['elapsed_hms'] or 'n/a'} | {share} |")
    lines.append("")
    lines.append(f"- report_elapsed_sum: `{payload['timing']['segment_elapsed_hms']}`")
    lines.append(f"- log_window_elapsed: `{payload['timing']['log_window'].get('segment_window_elapsed_hms') or 'n/a'}`")
    lines.append("")
    lines.append("## Lane Budgets")
    lines.append("")
    budgets = payload["lane_budgets"]
    lines.append(
        f"- fast_candidate_lane: observed `{budgets['observed_segment_elapsed_hms']}`, "
        f"target `{budgets['fast_candidate_lane_target_hms']}`, status `{budgets['fast_candidate_lane_status']}`"
    )
    lines.append(
        f"- witness_lane_target: `{budgets['witness_lane_target_hms']}`; "
        f"certification_lane_target: `{budgets['certification_lane_target_hms']}`"
    )
    lines.append("")
    lines.append("## Ranked Hotspots")
    lines.append("")
    for hotspot in payload["hotspots"]:
        lines.append(f"### {hotspot['rank']}. {hotspot['state']} ({hotspot['lane']})")
        lines.append(f"- title: {hotspot['title']}")
        lines.append(f"- elapsed: `{_fmt_hms(hotspot['elapsed_s'])}`")
        lines.append(f"- segment_share: `{100.0 * float(hotspot['segment_share']):.2f}%`")
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
    parser = argparse.ArgumentParser(description="Emit Segment 3B POPT.0 baseline/hotspot artifacts.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_3B/reports")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or _resolve_latest_run_id(runs_root)
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    seed = int(receipt.get("seed"))
    manifest_fingerprint = str(receipt.get("manifest_fingerprint"))
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
        / "data/layer1/3B/s0_gate_receipt"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s0_gate_receipt_3B.json"
    )
    sealed_inputs_path = (
        run_root
        / "data/layer1/3B/sealed_inputs"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "sealed_inputs_3B.json"
    )
    s0_receipt = _load_json(s0_receipt_path)
    sealed_inputs = _load_json(sealed_inputs_path)

    log_window = _parse_log_metrics(log_path)

    rows: list[dict[str, Any]] = []
    s0_elapsed = log_window.get("s0_elapsed_s")
    rows.append(
        {
            "state": "S0",
            "elapsed_s": s0_elapsed,
            "elapsed_hms": _fmt_hms(s0_elapsed),
        }
    )
    for state in ["S1", "S2", "S3", "S4", "S5"]:
        elapsed_s = float(reports[state].get("durations", {}).get("wall_ms", 0.0)) / 1000.0
        rows.append(
            {
                "state": state,
                "elapsed_s": elapsed_s,
                "elapsed_hms": _fmt_hms(elapsed_s),
            }
        )

    segment_elapsed_s = sum(float(row["elapsed_s"] or 0.0) for row in rows)
    for row in rows:
        elapsed_s = float(row["elapsed_s"] or 0.0)
        row["segment_share"] = (elapsed_s / segment_elapsed_s) if segment_elapsed_s > 0 else None

    ranked = sorted(rows, key=lambda r: float(r["elapsed_s"] or 0.0), reverse=True)
    top_three = ranked[:3]
    lane_by_rank = {1: "primary", 2: "secondary", 3: "closure"}
    hotspots: list[dict[str, Any]] = []
    for idx, row in enumerate(top_three, start=1):
        state = str(row["state"])
        hotspots.append(
            {
                "rank": idx,
                "lane": lane_by_rank[idx],
                "state": state,
                "title": STATE_TITLES[state],
                "elapsed_s": float(row["elapsed_s"] or 0.0),
                "segment_share": float(row["segment_share"] or 0.0),
                "evidence": _state_evidence(state, reports, s0_receipt, sealed_inputs),
                "code_refs": STATE_CODE_REFS[state],
                "candidate_actions": _candidate_actions_for_state(state),
            }
        )

    observed_segment_elapsed_s = segment_elapsed_s
    fast_target_s = float(LANE_BUDGETS_S["fast_candidate_lane"])
    fast_status = "PASS" if observed_segment_elapsed_s <= fast_target_s else "FAIL"

    payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "3B",
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
        },
        "timing": {
            "segment_elapsed_s": observed_segment_elapsed_s,
            "segment_elapsed_hms": _fmt_hms(observed_segment_elapsed_s),
            "state_table": rows,
            "log_window": log_window,
        },
        "lane_budgets": {
            "fast_candidate_lane_target_s": fast_target_s,
            "fast_candidate_lane_target_hms": _fmt_hms(fast_target_s),
            "witness_lane_target_s": float(LANE_BUDGETS_S["witness_lane"]),
            "witness_lane_target_hms": _fmt_hms(float(LANE_BUDGETS_S["witness_lane"])),
            "certification_lane_target_s": float(LANE_BUDGETS_S["certification_lane"]),
            "certification_lane_target_hms": _fmt_hms(float(LANE_BUDGETS_S["certification_lane"])),
            "observed_segment_elapsed_s": observed_segment_elapsed_s,
            "observed_segment_elapsed_hms": _fmt_hms(observed_segment_elapsed_s),
            "fast_candidate_lane_status": fast_status,
        },
        "hotspots": hotspots,
        "progression_gate": {
            "decision": "GO_POPT1",
            "reason": f"Primary hotspot is {hotspots[0]['state']} with the largest share of runtime.",
            "next_state_for_popt1": hotspots[0]["state"],
        },
    }

    out_root = Path(args.out_root)
    out_json = Path(args.out_json) if args.out_json else out_root / f"segment3b_popt0_baseline_{run_id}.json"
    out_md = Path(args.out_md) if args.out_md else out_root / f"segment3b_popt0_hotspot_map_{run_id}.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
