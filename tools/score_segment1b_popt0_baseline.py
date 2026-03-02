#!/usr/bin/env python3
"""Build Segment 1B POPT.0 baseline runtime and hotspot artifacts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
STATE_START_RE = re.compile(r"engine\.layers\.l1\.seg_1B\.(s\d+)_")
STATE_COMPLETE_RE = re.compile(r"\b(S\d+) 1B complete:")
S9_COMPLETE_RE = re.compile(r"\bS9 complete:")
ELAPSED_DELTA_RE = re.compile(r"\(elapsed=([0-9.]+)s, delta=([0-9.]+)s\)")


@dataclass
class StateTiming:
    state: str
    start_ts: datetime | None
    end_ts: datetime | None

    @property
    def elapsed_s(self) -> float | None:
        if self.start_ts is None or self.end_ts is None:
            return None
        return (self.end_ts - self.start_ts).total_seconds()


def _parse_ts(line: str) -> datetime | None:
    m = TS_RE.match(line)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)}.{m.group(2)}", "%Y-%m-%d %H:%M:%S.%f")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _find_single(path_glob: list[Path], label: str) -> Path:
    if not path_glob:
        raise FileNotFoundError(f"Missing {label} file")
    if len(path_glob) > 1:
        path_glob = sorted(path_glob, key=lambda p: p.stat().st_mtime, reverse=True)
    return path_glob[0]


def _parse_log_metrics(log_path: Path) -> dict[str, Any]:
    states: dict[str, dict[str, datetime | None]] = {}
    s5_assign_lines = 0
    s4_cache_summary: dict[str, int] | None = None
    s4_rank_cache_summary: dict[str, int] | None = None
    s5_cache_summary: dict[str, int] | None = None
    s9_markers: dict[str, dict[str, float]] = {}

    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ts = _parse_ts(line)
        if ts is None:
            continue

        ms = STATE_START_RE.search(line)
        if ms:
            state = ms.group(1).upper()
            bucket = states.setdefault(state, {"start_ts": None, "end_ts": None})
            if bucket["start_ts"] is None:
                bucket["start_ts"] = ts

        mc = STATE_COMPLETE_RE.search(line)
        if mc:
            state = mc.group(1)
            bucket = states.setdefault(state, {"start_ts": None, "end_ts": None})
            bucket["end_ts"] = ts
        elif S9_COMPLETE_RE.search(line):
            bucket = states.setdefault("S9", {"start_ts": None, "end_ts": None})
            bucket["end_ts"] = ts

        if "S5: assigning merchant_id=" in line:
            s5_assign_lines += 1

        if "S4: cache summary " in line:
            m = re.search(
                r"hits=(\d+)\s+misses=(\d+)\s+evictions=(\d+)\s+skipped_oversize=(\d+)\s+bytes_peak=(\d+)\s+unique_countries=(\d+)",
                line,
            )
            if m:
                s4_cache_summary = {
                    "hits": int(m.group(1)),
                    "misses": int(m.group(2)),
                    "evictions": int(m.group(3)),
                    "skipped_oversize": int(m.group(4)),
                    "bytes_peak": int(m.group(5)),
                    "unique_countries": int(m.group(6)),
                }

        if "S4: rank cache summary " in line:
            m = re.search(
                r"hits=(\d+)\s+misses=(\d+)\s+evictions=(\d+)\s+skipped_large_k=(\d+)\s+skipped_oversize=(\d+)\s+bytes_peak=(\d+)\s+entries=(\d+)",
                line,
            )
            if m:
                s4_rank_cache_summary = {
                    "hits": int(m.group(1)),
                    "misses": int(m.group(2)),
                    "evictions": int(m.group(3)),
                    "skipped_large_k": int(m.group(4)),
                    "skipped_oversize": int(m.group(5)),
                    "bytes_peak": int(m.group(6)),
                    "entries": int(m.group(7)),
                }

        if "S5: cache summary " in line:
            m = re.search(r"hits=(\d+)\s+misses=(\d+)\s+evictions=(\d+)", line)
            if m:
                s5_cache_summary = {
                    "hits": int(m.group(1)),
                    "misses": int(m.group(2)),
                    "evictions": int(m.group(3)),
                }

        if "S9:" in line and "(elapsed=" in line:
            for marker in (
                "S9: parity validation complete",
                "S9: RNG trace/audit scan start",
                "S9: RNG events scan start",
                "S9: computing egress checksums",
                "S9: bundle published decision",
            ):
                if marker in line:
                    em = ELAPSED_DELTA_RE.search(line)
                    if em:
                        s9_markers[marker] = {"elapsed_s": float(em.group(1)), "delta_s": float(em.group(2))}
                    break

    state_timings: dict[str, StateTiming] = {}
    for state in sorted(states, key=lambda x: int(x[1:])):
        bucket = states[state]
        state_timings[state] = StateTiming(
            state=state,
            start_ts=bucket["start_ts"],
            end_ts=bucket["end_ts"],
        )

    return {
        "state_timings": state_timings,
        "s5_assign_lines": s5_assign_lines,
        "s4_cache_summary": s4_cache_summary,
        "s4_rank_cache_summary": s4_rank_cache_summary,
        "s5_cache_summary": s5_cache_summary,
        "s9_markers": s9_markers,
    }


def _timing_payload(state_timings: dict[str, StateTiming]) -> tuple[list[dict[str, Any]], float]:
    rows: list[dict[str, Any]] = []
    segment_total = 0.0
    starts = [s.start_ts for s in state_timings.values() if s.start_ts is not None]
    ends = [s.end_ts for s in state_timings.values() if s.end_ts is not None]
    if starts and ends:
        segment_total = (max(ends) - min(starts)).total_seconds()
    for state in sorted(state_timings, key=lambda x: int(x[1:])):
        row = state_timings[state]
        elapsed = row.elapsed_s
        share = (elapsed / segment_total) if elapsed is not None and segment_total > 0 else None
        rows.append(
            {
                "state": state,
                "start_ts": row.start_ts.isoformat() if row.start_ts else None,
                "end_ts": row.end_ts.isoformat() if row.end_ts else None,
                "elapsed_s": elapsed,
                "elapsed_hms": _fmt_hms(elapsed) if elapsed is not None else None,
                "segment_share": share,
            }
        )
    return rows, segment_total


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _compute_hotspots(
    timing_rows: list[dict[str, Any]],
    segment_elapsed_s: float,
    s4_report: dict[str, Any],
    s5_report: dict[str, Any],
    s9_markers: dict[str, dict[str, float]],
    s4_cache_summary: dict[str, int] | None,
    s4_rank_cache_summary: dict[str, int] | None,
    s5_cache_summary: dict[str, int] | None,
    s5_assign_lines: int,
) -> list[dict[str, Any]]:
    state_elapsed = {row["state"]: float(row["elapsed_s"] or 0.0) for row in timing_rows}
    total = segment_elapsed_s if segment_elapsed_s > 0 else 1.0

    s4_pat = s4_report.get("pat", {})
    s5_pat = s5_report.get("pat", {})

    s9_event_scan = s9_markers.get("S9: computing egress checksums", {}).get("delta_s", 0.0)
    s9_trace_scan = s9_markers.get("S9: RNG events scan start", {}).get("delta_s", 0.0)
    s9_parity = s9_markers.get("S9: parity validation complete", {}).get("delta_s", 0.0)

    hotspots = [
        {
            "rank": 1,
            "state": "S4",
            "title": "Country asset reload + allocation loop dominates wall time",
            "elapsed_s": state_elapsed.get("S4", 0.0),
            "segment_share": state_elapsed.get("S4", 0.0) / total,
            "evidence": {
                "bytes_read_index_total": s4_pat.get("bytes_read_index_total"),
                "bytes_read_weights_total": s4_pat.get("bytes_read_weights_total"),
                "cache_summary": s4_cache_summary,
                "rank_cache_summary": s4_rank_cache_summary,
            },
            "code_refs": [
                "packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py:1134",
                "packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py:1375",
                "packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py:1485",
            ],
            "candidate_actions": [
                "Reduce reload thrash by improving per-country asset reuse strategy and cache admission/eviction policy.",
                "Cut repeated top-k rank recomputation with stronger prefix reuse for hot (country,n_sites,k) patterns.",
                "Move pair-loop invariants out of inner path and collapse repeated array transforms.",
            ],
        },
        {
            "rank": 2,
            "state": "S5",
            "title": "Tile-index IO amplification + per-site event writes",
            "elapsed_s": state_elapsed.get("S5", 0.0),
            "segment_share": state_elapsed.get("S5", 0.0) / total,
            "evidence": {
                "bytes_read_index_total": s5_pat.get("bytes_read_index_total"),
                "pairs_total": s5_pat.get("pairs_total"),
                "rows_emitted": s5_pat.get("rows_emitted"),
                "cache_summary": s5_cache_summary,
                "assigning_log_lines": s5_assign_lines,
            },
            "code_refs": [
                "packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/runner.py:64",
                "packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/runner.py:949",
                "packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/runner.py:1118",
            ],
            "candidate_actions": [
                "Increase effective tile-index locality (cache strategy/data layout) to reduce repeated parquet reads.",
                "Lower per-site overhead in assignment loop; batch event/trace emission where contract allows.",
                "Reduce per-pair info logging cadence to checkpoint-level by default.",
            ],
        },
        {
            "rank": 3,
            "state": "S9",
            "title": "Validation scans spend most time in RNG event pass",
            "elapsed_s": state_elapsed.get("S9", 0.0),
            "segment_share": state_elapsed.get("S9", 0.0) / total,
            "evidence": {
                "parity_delta_s": s9_parity,
                "trace_audit_delta_s": s9_trace_scan,
                "event_scan_delta_s": s9_event_scan,
            },
            "code_refs": [
                "packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/runner.py:858",
                "packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/runner.py:906",
                "packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/runner.py:1086",
            ],
            "candidate_actions": [
                "Convert multi-pass JSONL validation into tighter single-pass accounting where semantics stay equivalent.",
                "Avoid full-file readback when composing checksums; hash streaming path consistently.",
                "Keep required checks, move non-essential diagnostics to opt-in mode.",
            ],
        },
    ]

    return hotspots


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    timing_rows = payload["timing"]["state_table"]
    hotspots = payload["hotspots"]
    budgets = payload["budgets"]
    lines: list[str] = []
    lines.append("# Segment 1B POPT.0 Baseline and Hotspot Map")
    lines.append("")
    lines.append(f"- run_id: `{payload['run']['run_id']}`")
    lines.append(f"- seed: `{payload['run']['seed']}`")
    lines.append(f"- manifest_fingerprint: `{payload['run']['manifest_fingerprint']}`")
    lines.append("")
    lines.append("## Runtime Table")
    lines.append("")
    lines.append("| State | Elapsed | Share |")
    lines.append("|---|---:|---:|")
    for row in timing_rows:
        if row["elapsed_s"] is None:
            continue
        share = f"{100.0 * float(row['segment_share']):.2f}%"
        lines.append(f"| {row['state']} | {row['elapsed_hms']} | {share} |")
    lines.append("")
    lines.append(f"- segment_elapsed: `{_fmt_hms(payload['timing']['segment_elapsed_s'])}`")
    lines.append("")
    lines.append("## Runtime Budgets")
    lines.append("")
    lines.append(
        f"- S4 target/stretch: `{budgets['S4']['target_hms']}` / `{budgets['S4']['stretch_hms']}`"
    )
    lines.append(
        f"- S5 target/stretch: `{budgets['S5']['target_hms']}` / `{budgets['S5']['stretch_hms']}`"
    )
    lines.append(
        f"- S9 target/stretch: `{budgets['S9']['target_hms']}` / `{budgets['S9']['stretch_hms']}`"
    )
    lines.append("")
    lines.append("## Ranked Hotspots")
    lines.append("")
    for item in hotspots:
        lines.append(f"### {item['rank']}. {item['state']} - {item['title']}")
        lines.append(f"- elapsed: `{_fmt_hms(item['elapsed_s'])}`")
        lines.append(f"- segment_share: `{100.0 * float(item['segment_share']):.2f}%`")
        lines.append(f"- evidence: `{json.dumps(item['evidence'], sort_keys=True)}`")
        lines.append(f"- code_refs: `{', '.join(item['code_refs'])}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 1B POPT.0 baseline/hotspot artifacts.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_1B")
    parser.add_argument("--run-id", default="")
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

    s4_report_path = _find_single(
        list((run_root / "reports/layer1/1B").glob("state=S4/**/s4_run_report.json")),
        "s4_run_report",
    )
    s5_report_path = _find_single(
        list((run_root / "reports/layer1/1B").glob("state=S5/**/s5_run_report.json")),
        "s5_run_report",
    )

    parsed = _parse_log_metrics(log_path)
    timing_rows, segment_elapsed_s = _timing_payload(parsed["state_timings"])
    s4_report = _load_json(s4_report_path)
    s5_report = _load_json(s5_report_path)

    hotspots = _compute_hotspots(
        timing_rows=timing_rows,
        segment_elapsed_s=segment_elapsed_s,
        s4_report=s4_report,
        s5_report=s5_report,
        s9_markers=parsed["s9_markers"],
        s4_cache_summary=parsed["s4_cache_summary"],
        s4_rank_cache_summary=parsed["s4_rank_cache_summary"],
        s5_cache_summary=parsed["s5_cache_summary"],
        s5_assign_lines=parsed["s5_assign_lines"],
    )

    payload: dict[str, Any] = {
        "phase": "POPT.0",
        "segment": "1B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": run_id,
            "seed": receipt.get("seed"),
            "manifest_fingerprint": receipt.get("manifest_fingerprint"),
            "parameter_hash": receipt.get("parameter_hash"),
            "run_log_path": str(log_path).replace("\\", "/"),
            "s4_run_report_path": str(s4_report_path).replace("\\", "/"),
            "s5_run_report_path": str(s5_report_path).replace("\\", "/"),
        },
        "timing": {
            "segment_elapsed_s": segment_elapsed_s,
            "segment_elapsed_hms": _fmt_hms(segment_elapsed_s),
            "state_table": timing_rows,
        },
        "budgets": {
            "S4": {"target_s": 12 * 60, "target_hms": "00:12:00", "stretch_s": 15 * 60, "stretch_hms": "00:15:00"},
            "S5": {"target_s": 6 * 60, "target_hms": "00:06:00", "stretch_s": 8 * 60, "stretch_hms": "00:08:00"},
            "S9": {
                "target_s": 150,
                "target_hms": "00:02:30",
                "stretch_s": 210,
                "stretch_hms": "00:03:30",
            },
        },
        "hotspots": hotspots,
        "gates": {
            "progression_rule": "fail_closed",
            "require_runtime_improvement_vs_baseline": True,
            "require_movement_toward_budget": True,
            "block_statistical_tuning_while_over_stretch": True,
        },
    }

    out_json = Path(args.out_json) if args.out_json else runs_root / "reports" / f"segment1b_popt0_baseline_{run_id}.json"
    out_md = Path(args.out_md) if args.out_md else runs_root / "reports" / f"segment1b_popt0_hotspot_map_{run_id}.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
