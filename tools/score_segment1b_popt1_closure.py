#!/usr/bin/env python3
"""Score Segment 1B POPT.1 closure status from baseline and candidate evidence."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

S4_DELTA_RE = re.compile(r"S4: allocation loop completed .*\(elapsed=[0-9.]+s, delta=([0-9.]+)s\)")
S4_IDENTICAL_RE = re.compile(r"S4: s4_alloc_plan partition already exists with identical bytes")
S9_COMPLETE_RE = re.compile(r"\bS9 complete: .*decision=(\w+)")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _budget_classification(seconds: float) -> str:
    if seconds <= 12 * 60:
        return "GREEN"
    if seconds <= 15 * 60:
        return "AMBER"
    return "RED"


def _top2_substages(path: Path) -> list[str]:
    payload = _load_json(path)
    sub = payload.get("substage_timing") or {}
    ranked = sorted(
        ((str(k), float((v or {}).get("seconds") or 0.0)) for k, v in sub.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    return [name for name, _ in ranked[:2]]


def _extract_baseline_s4_elapsed(path: Path) -> float:
    payload = _load_json(path)
    rows = payload.get("timing", {}).get("state_table", [])
    for row in rows:
        if str(row.get("state")) == "S4":
            value = row.get("elapsed_s")
            if value is None:
                raise ValueError("Baseline S4 elapsed_s is missing")
            return float(value)
    raise ValueError("Baseline state_table missing S4 row")


def _extract_candidate_series(log_path: Path) -> tuple[list[float], int, str | None]:
    deltas: list[float] = []
    identical_hits = 0
    s9_decision: str | None = None
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines:
        m = S4_DELTA_RE.search(line)
        if m:
            deltas.append(float(m.group(1)))
        if S4_IDENTICAL_RE.search(line):
            identical_hits += 1
        m9 = S9_COMPLETE_RE.search(line)
        if m9:
            s9_decision = m9.group(1)
    return deltas, identical_hits, s9_decision


def _state_complete(log_text: str, marker: str) -> bool:
    return marker in log_text


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    c = payload["candidate"]
    b = payload["baseline"]
    lines = [
        "# Segment 1B POPT.1 Closure",
        "",
        f"- candidate_run_id: `{c['run_id']}`",
        f"- classification_latest: `{payload['decision']['classification_latest']}`",
        f"- classification_best: `{payload['decision']['classification_best']}`",
        f"- progression_decision: `{payload['decision']['progression_decision']}`",
        "",
        "## Runtime",
        f"- baseline_s4: `{b['s4_elapsed_hms']}` ({b['s4_elapsed_s']:.2f}s)",
        f"- candidate_best_s4: `{c['s4_best_hms']}` ({c['s4_best_s']:.2f}s)",
        f"- candidate_latest_s4: `{c['s4_latest_hms']}` ({c['s4_latest_s']:.2f}s)",
        f"- improvement_best: `{100.0*c['improvement_best_fraction']:.2f}%`",
        f"- improvement_latest: `{100.0*c['improvement_latest_fraction']:.2f}%`",
        "",
        "## Witness",
        f"- deterministic_identical_partition_hits: `{c['determinism_identical_partition_hits']}`",
        f"- top2_stable_across_witnesses: `{c['top2_stable_across_witnesses']}`",
        f"- witness_a_top2: `{', '.join(c['witness_a_top2'])}`",
        f"- witness_b_top2: `{', '.join(c['witness_b_top2'])}`",
        "",
        "## Smoke",
        f"- s5_complete: `{c['smoke']['s5_complete']}`",
        f"- s6_complete: `{c['smoke']['s6_complete']}`",
        f"- s7_complete: `{c['smoke']['s7_complete']}`",
        f"- s8_complete: `{c['smoke']['s8_complete']}`",
        f"- s9_pass: `{c['smoke']['s9_pass']}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 1B POPT.1 closure status")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_1B")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_1B/reports/segment1b_popt0_baseline_9ebdd751ab7b4f9da246cc840ddff306.json",
    )
    parser.add_argument("--witness-a-json", default="")
    parser.add_argument("--witness-b-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.candidate_run_id
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {run_root}")

    baseline_path = Path(args.baseline_json)
    baseline_s4 = _extract_baseline_s4_elapsed(baseline_path)

    log_path = run_root / f"run_log_{run_id}.log"
    log_text = log_path.read_text(encoding="utf-8", errors="ignore")
    series, identical_hits, s9_decision = _extract_candidate_series(log_path)
    if not series:
        raise ValueError("No S4 allocation loop delta samples found in candidate log")

    witness_a = (
        Path(args.witness_a_json)
        if args.witness_a_json
        else runs_root
        / "reports"
        / f"segment1b_popt1_s4_witness_a_{run_id}.json"
    )
    witness_b = (
        Path(args.witness_b_json)
        if args.witness_b_json
        else runs_root
        / "reports"
        / f"segment1b_popt1_s4_witness_b_{run_id}.json"
    )
    top2_a = _top2_substages(witness_a)
    top2_b = _top2_substages(witness_b)

    latest_s4 = float(series[-1])
    best_s4 = float(min(series))
    improvement_latest = (baseline_s4 - latest_s4) / baseline_s4
    improvement_best = (baseline_s4 - best_s4) / baseline_s4

    classification_latest = _budget_classification(latest_s4)
    classification_best = _budget_classification(best_s4)

    smoke = {
        "s5_complete": _state_complete(log_text, "S5 1B complete:"),
        "s6_complete": _state_complete(log_text, "S6 1B complete:"),
        "s7_complete": _state_complete(log_text, "S7 1B complete:"),
        "s8_complete": _state_complete(log_text, "S8 1B complete:"),
        "s9_pass": str(s9_decision or "").upper() == "PASS",
    }

    decision = {
        "classification_latest": classification_latest,
        "classification_best": classification_best,
        "improvement_vs_baseline_latest": bool(latest_s4 < baseline_s4),
        "improvement_vs_baseline_best": bool(best_s4 < baseline_s4),
        "movement_toward_budget": bool(best_s4 < baseline_s4),
        "progression_decision": "GO_POPT2"
        if classification_latest in {"GREEN", "AMBER"}
        else "HOLD_POPT1",
    }

    payload: dict[str, Any] = {
        "phase": "POPT.1",
        "segment": "1B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline": {
            "run_id": "9ebdd751ab7b4f9da246cc840ddff306",
            "s4_elapsed_s": baseline_s4,
            "s4_elapsed_hms": _fmt_hms(baseline_s4),
            "source": str(baseline_path).replace("\\", "/"),
        },
        "candidate": {
            "run_id": run_id,
            "log_path": str(log_path).replace("\\", "/"),
            "s4_delta_series_s": series,
            "s4_best_s": best_s4,
            "s4_best_hms": _fmt_hms(best_s4),
            "s4_latest_s": latest_s4,
            "s4_latest_hms": _fmt_hms(latest_s4),
            "improvement_best_fraction": improvement_best,
            "improvement_latest_fraction": improvement_latest,
            "determinism_identical_partition_hits": identical_hits,
            "witness_a": str(witness_a).replace("\\", "/"),
            "witness_b": str(witness_b).replace("\\", "/"),
            "witness_a_top2": top2_a,
            "witness_b_top2": top2_b,
            "top2_stable_across_witnesses": top2_a == top2_b,
            "smoke": smoke,
        },
        "decision": decision,
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment1b_popt1_closure_{run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment1b_popt1_closure_{run_id}.md"
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
