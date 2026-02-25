#!/usr/bin/env python3
"""Score Segment 6B POPT.1 closure from baseline and candidate run evidence."""

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


STATE_ORDER = ["S1", "S2", "S3", "S4", "S5"]
BASELINE_S1_SECONDS = 1333.75
TARGET_S1_SECONDS = 800.0
STRETCH_S1_SECONDS = 900.0
S1_DATASETS = ("s1_arrival_entities_6B", "s1_session_index_6B")

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
LOG_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[[A-Z]+\] ([^:]+): (.*)$")
MODULE_STATE_RE = re.compile(r"engine\.layers\.l3\.seg_6B\.s([1-5])_")
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
    for event in _state_events(events, state):
        msg = event.message.lower()
        if "completed" not in msg:
            continue
        elapsed = _extract_elapsed(event.message)
        if elapsed is None:
            continue
        candidates.append(elapsed)
    if not candidates:
        raise ValueError(f"Missing completion elapsed for {state}.")
    return float(candidates[-1])


def _parse_bucket_phase_elapsed(events: list[LogEvent], state: str, marker: str) -> float | None:
    for event in reversed(_state_events(events, state)):
        if marker not in event.message:
            continue
        elapsed = _extract_elapsed(event.message)
        if elapsed is not None:
            return elapsed
    return None


def _dataset_parquet_files(run_root: Path, dataset_name: str) -> list[Path]:
    base = run_root / "data" / "layer3" / "6B" / dataset_name
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*.parquet") if path.is_file())


def _schema_signature(path: Path) -> list[dict[str, str]]:
    schema = pq.ParquetFile(path).schema_arrow
    return [{"name": field.name, "type": str(field.type)} for field in schema]


def _row_count(files: list[Path]) -> int:
    total = 0
    for file in files:
        meta = pq.ParquetFile(file).metadata
        if meta is not None:
            total += int(meta.num_rows)
    return total


def _s1_structural_snapshot(run_root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for dataset in S1_DATASETS:
        files = _dataset_parquet_files(run_root, dataset)
        out[dataset] = {
            "files": len(files),
            "rows": _row_count(files),
            "schema": _schema_signature(files[0]) if files else [],
        }
    return out


def _ensure_ascii(path: Path) -> str:
    return str(path).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 6B POPT.1 closure.")
    parser.add_argument("--baseline-runs-root", default="runs/local_full_run-5")
    parser.add_argument("--baseline-run-id", default="c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--candidate-runs-root", default="runs/fix-data-engine/segment_6B")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_6B/reports")
    args = parser.parse_args()

    baseline_runs_root = Path(args.baseline_runs_root)
    candidate_runs_root = Path(args.candidate_runs_root)
    baseline_run_root = baseline_runs_root / args.baseline_run_id
    candidate_run_root = candidate_runs_root / args.candidate_run_id
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    baseline_receipt = _load_json(baseline_run_root / "run_receipt.json")
    candidate_receipt = _load_json(candidate_run_root / "run_receipt.json")
    baseline_log = baseline_run_root / f"run_log_{args.baseline_run_id}.log"
    candidate_log = candidate_run_root / f"run_log_{args.candidate_run_id}.log"
    baseline_events = _parse_log_events(baseline_log)
    candidate_events = _parse_log_events(candidate_log)

    baseline_elapsed = {state: _completion_elapsed(baseline_events, state) for state in STATE_ORDER}
    candidate_elapsed = {state: _completion_elapsed(candidate_events, state) for state in STATE_ORDER}
    baseline_lane_elapsed = float(sum(baseline_elapsed.values()))
    candidate_lane_elapsed = float(sum(candidate_elapsed.values()))

    baseline_s1 = float(baseline_elapsed["S1"])
    candidate_s1 = float(candidate_elapsed["S1"])
    reduction = ((baseline_s1 - candidate_s1) / baseline_s1) if baseline_s1 > 0 else 0.0

    baseline_bucket_agg = _parse_bucket_phase_elapsed(
        baseline_events, "S1", "bucket aggregation buckets_processed="
    )
    candidate_bucket_agg = _parse_bucket_phase_elapsed(
        candidate_events, "S1", "bucket aggregation buckets_processed="
    )
    baseline_bucketize = _parse_bucket_phase_elapsed(
        baseline_events, "S1", "bucketization parts_processed="
    )
    candidate_bucketize = _parse_bucket_phase_elapsed(
        candidate_events, "S1", "bucketization parts_processed="
    )

    baseline_struct = _s1_structural_snapshot(baseline_run_root)
    candidate_struct = _s1_structural_snapshot(candidate_run_root)
    structural_checks: dict[str, Any] = {}
    for dataset in S1_DATASETS:
        base = baseline_struct[dataset]
        cand = candidate_struct[dataset]
        structural_checks[dataset] = {
            "rows_match": int(base["rows"]) == int(cand["rows"]),
            "schema_match": base["schema"] == cand["schema"],
            "baseline_rows": int(base["rows"]),
            "candidate_rows": int(cand["rows"]),
            "baseline_files": int(base["files"]),
            "candidate_files": int(cand["files"]),
        }
    structural_pass = all(
        bool(item["rows_match"]) and bool(item["schema_match"]) for item in structural_checks.values()
    )

    runtime_reduction_pass = reduction >= 0.40
    runtime_target_pass = candidate_s1 <= TARGET_S1_SECONDS
    runtime_stretch_pass = candidate_s1 <= STRETCH_S1_SECONDS
    decision = "UNLOCK_POPT.2_CONTINUE" if (runtime_reduction_pass and runtime_target_pass and structural_pass) else "HOLD_POPT.1_REOPEN"

    payload: dict[str, Any] = {
        "phase": "POPT.1",
        "segment": "6B",
        "decision": decision,
        "baseline": {
            "run_id": args.baseline_run_id,
            "runs_root": _ensure_ascii(baseline_runs_root),
            "run_root": _ensure_ascii(baseline_run_root),
            "seed": int(baseline_receipt.get("seed") or 0),
            "manifest_fingerprint": str(baseline_receipt.get("manifest_fingerprint") or ""),
            "parameter_hash": str(baseline_receipt.get("parameter_hash") or ""),
            "s1_elapsed_s": baseline_s1,
            "s1_elapsed_hms": _fmt_hms(baseline_s1),
            "lane_s1_to_s5_elapsed_s": baseline_lane_elapsed,
            "lane_s1_to_s5_elapsed_hms": _fmt_hms(baseline_lane_elapsed),
            "bucketization_elapsed_s": baseline_bucketize,
            "bucket_aggregation_elapsed_s": baseline_bucket_agg,
        },
        "candidate": {
            "run_id": args.candidate_run_id,
            "runs_root": _ensure_ascii(candidate_runs_root),
            "run_root": _ensure_ascii(candidate_run_root),
            "seed": int(candidate_receipt.get("seed") or 0),
            "manifest_fingerprint": str(candidate_receipt.get("manifest_fingerprint") or ""),
            "parameter_hash": str(candidate_receipt.get("parameter_hash") or ""),
            "s1_elapsed_s": candidate_s1,
            "s1_elapsed_hms": _fmt_hms(candidate_s1),
            "lane_s1_to_s5_elapsed_s": candidate_lane_elapsed,
            "lane_s1_to_s5_elapsed_hms": _fmt_hms(candidate_lane_elapsed),
            "bucketization_elapsed_s": candidate_bucketize,
            "bucket_aggregation_elapsed_s": candidate_bucket_agg,
        },
        "metrics": {
            "s1_reduction_ratio": reduction,
            "runtime_reduction_pass": runtime_reduction_pass,
            "runtime_target_pass": runtime_target_pass,
            "runtime_stretch_pass": runtime_stretch_pass,
            "structural_pass": structural_pass,
            "lane_reduction_ratio": (
                ((baseline_lane_elapsed - candidate_lane_elapsed) / baseline_lane_elapsed)
                if baseline_lane_elapsed > 0
                else 0.0
            ),
        },
        "state_elapsed_s": {
            "baseline": baseline_elapsed,
            "candidate": candidate_elapsed,
        },
        "structural_checks": structural_checks,
        "targets": {
            "s1_baseline_s": BASELINE_S1_SECONDS,
            "s1_target_s": TARGET_S1_SECONDS,
            "s1_stretch_s": STRETCH_S1_SECONDS,
            "required_reduction_ratio": 0.40,
        },
        "generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    out_json = out_root / f"segment6b_popt1_closure_{args.candidate_run_id}.json"
    out_md = out_root / f"segment6b_popt1_closure_{args.candidate_run_id}.md"
    out_csv = out_root / f"segment6b_popt1_state_elapsed_{args.candidate_run_id}.csv"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Segment 6B POPT.1 Closure",
        "",
        f"- baseline_run_id: `{args.baseline_run_id}`",
        f"- candidate_run_id: `{args.candidate_run_id}`",
        f"- decision: `{decision}`",
        "",
        "## Runtime",
        "",
        f"- baseline S1: `{_fmt_hms(baseline_s1)}` ({baseline_s1:.2f}s)",
        f"- candidate S1: `{_fmt_hms(candidate_s1)}` ({candidate_s1:.2f}s)",
        f"- reduction: `{reduction:.2%}`",
        f"- reduction gate (`>=40%`): `{runtime_reduction_pass}`",
        f"- target gate (`<=800s`): `{runtime_target_pass}`",
        f"- stretch gate (`<=900s`): `{runtime_stretch_pass}`",
        f"- lane baseline S1..S5: `{_fmt_hms(baseline_lane_elapsed)}` ({baseline_lane_elapsed:.2f}s)",
        f"- lane candidate S1..S5: `{_fmt_hms(candidate_lane_elapsed)}` ({candidate_lane_elapsed:.2f}s)",
        "",
        "## Session Consolidation Trace",
        "",
        f"- baseline bucketization elapsed (if present): `{baseline_bucketize}`",
        f"- candidate bucketization elapsed (if present): `{candidate_bucketize}`",
        f"- baseline bucket aggregation elapsed: `{baseline_bucket_agg}`",
        f"- candidate bucket aggregation elapsed: `{candidate_bucket_agg}`",
        "",
        "## Structural Parity",
        "",
    ]
    for dataset in S1_DATASETS:
        row = structural_checks[dataset]
        lines.append(
            f"- {dataset}: rows_match=`{row['rows_match']}` schema_match=`{row['schema_match']}` "
            f"(baseline_rows={row['baseline_rows']}, candidate_rows={row['candidate_rows']}, "
            f"baseline_files={row['baseline_files']}, candidate_files={row['candidate_files']})"
        )
    lines.append("")
    lines.append(f"- structural_pass: `{structural_pass}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["state", "baseline_s", "candidate_s", "delta_s", "delta_ratio"])
        for state in STATE_ORDER:
            b = float(baseline_elapsed[state])
            c = float(candidate_elapsed[state])
            writer.writerow([state, f"{b:.6f}", f"{c:.6f}", f"{(c - b):.6f}", f"{((c - b) / b) if b > 0 else 0.0:.6f}"])

    print(f"[segment6b-popt1] closure_json={out_json}")
    print(f"[segment6b-popt1] closure_md={out_md}")
    print(f"[segment6b-popt1] state_csv={out_csv}")
    print(f"[segment6b-popt1] decision={decision}")


if __name__ == "__main__":
    main()
