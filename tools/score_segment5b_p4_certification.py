#!/usr/bin/env python3
"""Score Segment 5B P4 multi-seed certification posture."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REQUIRED_SEEDS = (42, 7, 101, 202)
HARD_GATES = ("T1", "T2", "T3", "T4", "T5", "T11", "T12")
MAJOR_GATES = ("T6", "T7")
T10_METRICS = ("T1", "T2", "T3", "T6", "T7")


@dataclass(frozen=True)
class SeedRun:
    seed: int
    run_id: str


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _find_latest_segment_state_runs(run_root: Path) -> Path:
    candidates = sorted(
        run_root.glob("reports/layer2/segment_state_runs/segment=5B/utc_day=*/segment_state_runs.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"Missing 5B segment_state_runs under {run_root}")
    return candidates[-1]


def _latest_state_row(records: list[dict[str, Any]], state: str) -> dict[str, Any]:
    rows = [r for r in records if str(r.get("state")) == state]
    if not rows:
        raise ValueError(f"No rows found for {state}")
    return sorted(rows, key=lambda r: (str(r.get("finished_at_utc") or ""), str(r.get("started_at_utc") or "")))[-1]


def _state_wall_s(row: dict[str, Any]) -> float:
    try:
        return float(((row.get("durations") or {}).get("wall_ms") or 0) / 1000.0)
    except Exception:
        return 0.0


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _cv(values: list[float]) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return 0.0
    mu = mean(values)
    sigma = pstdev(values)
    if abs(mu) < 1e-12:
        return 0.0 if sigma < 1e-12 else float("inf")
    return abs(sigma / mu)


def _parse_seed_run(text: str) -> SeedRun:
    if ":" not in text:
        raise ValueError(f"Invalid --seed-run '{text}', expected '<seed>:<run_id>'")
    seed_str, run_id = text.split(":", 1)
    seed = int(seed_str)
    run = run_id.strip()
    if not run:
        raise ValueError(f"Invalid --seed-run '{text}', run_id is empty")
    return SeedRun(seed=seed, run_id=run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5B P4 multi-seed certification.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_5B")
    parser.add_argument("--reports-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument(
        "--seed-run",
        action="append",
        default=[],
        help="Seed to run mapping as '<seed>:<run_id>'. Repeat for each seed.",
    )
    parser.add_argument("--s4s5-budget-seconds", type=float, default=720.0)
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    reports_root = Path(args.reports_root)
    reports_root.mkdir(parents=True, exist_ok=True)

    if args.seed_run:
        mappings = [_parse_seed_run(raw) for raw in args.seed_run]
    else:
        raise ValueError("At least one --seed-run mapping is required")

    by_seed = {m.seed: m for m in mappings}
    missing_required = [seed for seed in REQUIRED_SEEDS if seed not in by_seed]
    if missing_required:
        raise ValueError(f"Missing required seeds in run map: {missing_required}")

    panel_rows: list[dict[str, Any]] = []
    t10_metric_values: dict[str, list[float]] = {metric: [] for metric in T10_METRICS}
    veto_reasons: list[str] = []

    for seed in REQUIRED_SEEDS:
        mapping = by_seed[seed]
        run_id = mapping.run_id
        run_root = runs_root / run_id
        if not run_root.exists():
            raise FileNotFoundError(f"Run root not found: {run_root}")

        p1_path = reports_root / f"segment5b_p1_realism_gateboard_{run_id}.json"
        p2_path = reports_root / f"segment5b_p2_gateboard_{run_id}.json"
        if not p1_path.exists():
            raise FileNotFoundError(f"Missing P1 gateboard for seed={seed}: {p1_path}")
        if not p2_path.exists():
            raise FileNotFoundError(f"Missing P2 gateboard for seed={seed}: {p2_path}")

        p1 = _load_json(p1_path)
        p2 = _load_json(p2_path)
        gates = p1.get("gates") or {}

        state_runs_path = _find_latest_segment_state_runs(run_root)
        state_rows = _load_jsonl(state_runs_path)
        s4 = _latest_state_row(state_rows, "S4")
        s5 = _latest_state_row(state_rows, "S5")
        s4_s = _state_wall_s(s4)
        s5_s = _state_wall_s(s5)
        s4s5_s = s4_s + s5_s

        hard_failures = [gid for gid in HARD_GATES if not bool((gates.get(gid) or {}).get("b_pass"))]
        major_failures = [gid for gid in MAJOR_GATES if not bool((gates.get(gid) or {}).get("b_pass"))]
        major_bplus_failures = [gid for gid in MAJOR_GATES if not bool((gates.get(gid) or {}).get("bplus_pass"))]
        s5_status = str(s5.get("status") or "")
        s5_pass = s5_status == "PASS"
        runtime_budget_pass = s4s5_s <= float(args.s4s5_budget_seconds)

        metric_values: dict[str, float | None] = {}
        for metric in T10_METRICS:
            value = _safe_float((gates.get(metric) or {}).get("value"))
            metric_values[metric] = value
            if value is not None:
                t10_metric_values[metric].append(value)

        row = {
            "seed": seed,
            "run_id": run_id,
            "hard_failures": hard_failures,
            "major_failures": major_failures,
            "major_bplus_failures": major_bplus_failures,
            "s5_status": s5_status,
            "s5_pass": s5_pass,
            "validation_report_status": (p1.get("summary") or {}).get("validation_report_status"),
            "s4_seconds": s4_s,
            "s5_seconds": s5_s,
            "s4s5_seconds": s4s5_s,
            "runtime_budget_seconds": float(args.s4s5_budget_seconds),
            "runtime_budget_pass": runtime_budget_pass,
            "metrics": metric_values,
            "p1_gateboard_path": str(p1_path),
            "p2_gateboard_path": str(p2_path),
            "state_runs_path": str(state_runs_path),
            "p2_lane_decision": ((p2.get("summary") or {}).get("lane_decision")),
            "p2_phase_grade": ((p2.get("summary") or {}).get("phase_grade")),
        }
        panel_rows.append(row)

        if hard_failures:
            veto_reasons.append(f"seed={seed}:hard_failures={hard_failures}")
        if major_failures:
            veto_reasons.append(f"seed={seed}:major_failures={major_failures}")
        if not s5_pass:
            veto_reasons.append(f"seed={seed}:s5_status={s5_status}")

    t10_rows: list[dict[str, Any]] = []
    t10_values: list[float] = []
    for metric in T10_METRICS:
        vals = t10_metric_values.get(metric) or []
        if len(vals) < len(REQUIRED_SEEDS):
            value = float("inf")
            sufficient = False
        else:
            value = _cv(vals)
            sufficient = math.isfinite(value)
            if sufficient:
                t10_values.append(value)
        t10_rows.append(
            {
                "metric": metric,
                "seed_values": vals,
                "cv": value if math.isfinite(value) else None,
                "sufficient": sufficient,
            }
        )

    if len(t10_values) != len(T10_METRICS):
        t10_overall = float("inf")
    else:
        t10_overall = max(t10_values)

    if t10_overall <= 0.15:
        t10_class = "BPLUS"
    elif t10_overall <= 0.25:
        t10_class = "B"
    else:
        t10_class = "FAIL"

    all_bplus_majors_pass = all(not row["major_bplus_failures"] for row in panel_rows)
    if veto_reasons:
        decision = "HOLD_P4_REMEDIATE"
    elif t10_class == "FAIL":
        decision = "HOLD_P4_REMEDIATE"
    elif all_bplus_majors_pass and t10_class == "BPLUS":
        decision = "PASS_BPLUS_ROBUST"
    else:
        decision = "PASS_B_ROBUST"

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    seed_gateboard_path = reports_root / f"segment5b_p4_seed_gateboard_{stamp}.json"
    t10_path = reports_root / f"segment5b_p4_t10_stability_{stamp}.json"
    closure_path = reports_root / f"segment5b_p4_closure_{stamp}.json"
    closure_md_path = reports_root / f"segment5b_p4_closure_{stamp}.md"

    seed_gateboard = {
        "generated_utc": _now_utc(),
        "phase": "P4.4",
        "segment": "5B",
        "required_seeds": list(REQUIRED_SEEDS),
        "rows": panel_rows,
        "veto_reasons": veto_reasons,
    }
    seed_gateboard_path.write_text(json.dumps(seed_gateboard, indent=2), encoding="utf-8")

    t10_payload = {
        "generated_utc": _now_utc(),
        "phase": "P4.5",
        "segment": "5B",
        "required_seeds": list(REQUIRED_SEEDS),
        "metrics": t10_rows,
        "t10_overall_cv": t10_overall if math.isfinite(t10_overall) else None,
        "t10_class": t10_class,
        "thresholds": {"BPLUS": 0.15, "B": 0.25},
    }
    t10_path.write_text(json.dumps(t10_payload, indent=2), encoding="utf-8")

    closure = {
        "generated_utc": _now_utc(),
        "phase": "P4.6",
        "segment": "5B",
        "decision": decision,
        "required_seeds": list(REQUIRED_SEEDS),
        "summary": {
            "veto_reasons": veto_reasons,
            "t10_overall_cv": t10_overall if math.isfinite(t10_overall) else None,
            "t10_class": t10_class,
            "all_bplus_majors_pass": all_bplus_majors_pass,
        },
        "artifacts": {
            "seed_gateboard": str(seed_gateboard_path),
            "t10_stability": str(t10_path),
        },
    }
    closure_path.write_text(json.dumps(closure, indent=2), encoding="utf-8")

    md_lines = [
        "# Segment 5B P4 Certification Closure",
        "",
        f"- Generated UTC: `{closure['generated_utc']}`",
        f"- Decision: `{decision}`",
        f"- T10 class: `{t10_class}`",
        f"- T10 overall CV: `{closure['summary']['t10_overall_cv']}`",
        "",
        "## Seed Summary",
        "| Seed | Run ID | S5 | Hard Failures | Major Failures | S4+S5 (s) | Budget Pass |",
        "|---:|---|:---:|---|---|---:|:---:|",
    ]
    for row in panel_rows:
        md_lines.append(
            f"| {row['seed']} | `{row['run_id']}` | `{row['s5_status']}` | "
            f"`{row['hard_failures']}` | `{row['major_failures']}` | {row['s4s5_seconds']:.3f} | `{row['runtime_budget_pass']}` |"
        )
    veto_lines = [f"- `{reason}`" for reason in veto_reasons] if veto_reasons else ["- none"]
    md_lines.extend(
        [
            "",
            "## Veto Reasons",
            *veto_lines,
            "",
            "## Artifacts",
            f"- seed gateboard: `{seed_gateboard_path}`",
            f"- t10 stability: `{t10_path}`",
            f"- closure json: `{closure_path}`",
            "",
        ]
    )
    closure_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"[segment5b-p4] seed_gateboard={seed_gateboard_path}")
    print(f"[segment5b-p4] t10_stability={t10_path}")
    print(f"[segment5b-p4] closure_json={closure_path}")
    print(f"[segment5b-p4] closure_md={closure_md_path}")
    print(f"[segment5b-p4] decision={decision}")


if __name__ == "__main__":
    main()
