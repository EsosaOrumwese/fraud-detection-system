#!/usr/bin/env python3
"""Run Segment 5B P2 policy-only sweep for hybrid virtual share calibration."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"


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


def _resolve_runtime_s4s5(run_root: Path) -> float:
    state_runs_path = _find_latest_segment_state_runs(run_root)
    rows = _load_jsonl(state_runs_path)
    s4 = _latest_state_row(rows, "S4")
    s5 = _latest_state_row(rows, "S5")
    s4_seconds = float(((s4.get("durations") or {}).get("wall_ms") or 0) / 1000.0)
    s5_seconds = float(((s5.get("durations") or {}).get("wall_ms") or 0) / 1000.0)
    return s4_seconds + s5_seconds


def _read_p(text: str) -> float:
    match = re.search(r"^\s*p_virtual_hybrid:\s*([0-9]+(?:\.[0-9]+)?)\s*$", text, flags=re.MULTILINE)
    if not match:
        raise ValueError("Could not parse `p_virtual_hybrid` from routing policy.")
    return float(match.group(1))


def _write_p(text: str, value: float) -> str:
    updated, n = re.subn(
        r"(^\s*p_virtual_hybrid:\s*)([0-9]+(?:\.[0-9]+)?)\s*$",
        lambda m: f"{m.group(1)}{value:.4f}",
        text,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise ValueError("Failed to update exactly one `p_virtual_hybrid` value.")
    return updated


def _cleanup_outputs(run_root: Path, seed: int, manifest_fingerprint: str) -> None:
    arrivals = (
        run_root
        / "data"
        / "layer2"
        / "5B"
        / "arrival_events"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "scenario_id=baseline_v1"
    )
    validation = run_root / "data" / "layer2" / "5B" / "validation" / f"manifest_fingerprint={manifest_fingerprint}"
    for path in [arrivals, validation]:
        if path.exists():
            shutil.rmtree(path)


def _run_checked(cmd: list[str], cwd: Path) -> None:
    print(f"[segment5b-p2-sweep] cmd={' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _score_candidate(
    repo_root: Path,
    runs_root: Path,
    run_id: str,
    out_root: Path,
    sample_target: int,
    baseline_runtime_seconds: float,
    label: str,
    suffix: str,
    baseline_p1_gateboard: Path,
) -> Path:
    p1_cmd = [
        sys.executable,
        "tools/score_segment5b_p1_realism.py",
        "--runs-root",
        str(runs_root),
        "--run-id",
        run_id,
        "--out-root",
        str(out_root),
        "--sample-target",
        str(sample_target),
    ]
    _run_checked(p1_cmd, repo_root)

    p2_cmd = [
        sys.executable,
        "tools/score_segment5b_p2_calibration.py",
        "--runs-root",
        str(runs_root),
        "--run-id",
        run_id,
        "--out-root",
        str(out_root),
        "--candidate-label",
        label,
        "--suffix",
        suffix,
        "--baseline-runtime-seconds",
        f"{baseline_runtime_seconds:.6f}",
        "--baseline-p1-gateboard-path",
        str(baseline_p1_gateboard),
    ]
    _run_checked(p2_cmd, repo_root)
    return out_root / f"segment5b_p2_gateboard_{run_id}_{suffix}.json"


def _candidate_rank(row: dict[str, Any]) -> tuple:
    return (
        int(bool(row["frozen_failures"])),
        int(bool(row["runtime_regression_veto"])),
        int(row["primary_failures_count"]),
        float(row["calibration_distance_to_b"]),
        float(row["lane_seconds"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded Segment 5B P2 policy-only sweep.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument("--routing-policy-path", default="config/layer2/5B/arrival_routing_policy_5B.yaml")
    parser.add_argument("--sample-target", type=int, default=200000)
    parser.add_argument(
        "--p-grid",
        default="",
        help="Comma-separated candidate p_virtual_hybrid values. If omitted, read from sensitivity artifact.",
    )
    parser.add_argument("--sensitivity-path", default="")
    args = parser.parse_args()

    repo_root = Path.cwd()
    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or RUN_ID_DEFAULT
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    manifest_fingerprint = str(receipt["manifest_fingerprint"])
    seed = int(receipt["seed"])

    routing_policy_path = Path(args.routing_policy_path)
    original_policy_text = routing_policy_path.read_text(encoding="utf-8-sig")
    p_original = _read_p(original_policy_text)

    baseline_runtime_seconds = _resolve_runtime_s4s5(run_root)
    runs_root_make = runs_root.as_posix()

    baseline_p1_gateboard = out_root / f"segment5b_p2_baseline_p1_gateboard_{run_id}.json"
    current_p1_gateboard = out_root / f"segment5b_p1_realism_gateboard_{run_id}.json"
    if not current_p1_gateboard.exists():
        _run_checked(
            [
                sys.executable,
                "tools/score_segment5b_p1_realism.py",
                "--runs-root",
                str(runs_root),
                "--run-id",
                run_id,
                "--out-root",
                str(out_root),
                "--sample-target",
                str(args.sample_target),
            ],
            repo_root,
        )
    shutil.copy2(current_p1_gateboard, baseline_p1_gateboard)

    if args.p_grid.strip():
        p_grid = [float(item.strip()) for item in args.p_grid.split(",") if item.strip()]
    else:
        sensitivity_path = Path(args.sensitivity_path) if args.sensitivity_path else out_root / f"segment5b_p2_sensitivity_{run_id}.json"
        if not sensitivity_path.exists():
            raise FileNotFoundError(
                f"Missing p-grid input: {sensitivity_path}. Provide --p-grid or generate sensitivity artifact first."
            )
        sensitivity = _load_json(sensitivity_path)
        p_grid = [float(v) for v in (sensitivity.get("candidate_shortlist") or {}).get("p_virtual_hybrid_grid", [])]
    if not p_grid:
        raise ValueError("Candidate p-grid is empty.")

    matrix_rows: list[dict[str, Any]] = []

    # Baseline row from current posture.
    _run_checked(
        [
            sys.executable,
            "tools/score_segment5b_p2_calibration.py",
            "--runs-root",
            str(runs_root),
            "--run-id",
            run_id,
            "--out-root",
            str(out_root),
            "--candidate-label",
            "baseline",
            "--suffix",
            "baseline",
            "--baseline-runtime-seconds",
            f"{baseline_runtime_seconds:.6f}",
            "--baseline-p1-gateboard-path",
            str(baseline_p1_gateboard),
        ],
        repo_root,
    )
    baseline_gateboard = _load_json(out_root / f"segment5b_p2_gateboard_{run_id}_baseline.json")
    baseline_summary = baseline_gateboard["summary"]
    matrix_rows.append(
        {
            "label": "baseline",
            "p_virtual_hybrid": p_original,
            "t6": float((baseline_gateboard["gates"]["T6"] or {}).get("value") or 0.0),
            "t7": float((baseline_gateboard["gates"]["T7"] or {}).get("value") or 0.0),
            "frozen_failures": len(baseline_summary["frozen_failures"]),
            "primary_failures_count": len(baseline_summary["primary_failures"]),
            "calibration_distance_to_b": float(baseline_summary["calibration_distance_to_b"]),
            "lane_seconds": float((baseline_summary["runtime"] or {}).get("lane_s4_s5_seconds") or 0.0),
            "runtime_regression_veto": bool((baseline_summary["runtime"] or {}).get("regression_veto")),
            "lane_decision": str(baseline_summary["lane_decision"]),
            "phase_grade": str(baseline_summary["phase_grade"]),
        }
    )

    # Candidate sweep.
    for candidate_p in p_grid:
        candidate_p = round(float(candidate_p), 4)
        if abs(candidate_p - p_original) < 1e-12:
            continue
        suffix = f"p{int(round(candidate_p * 10000)):05d}"
        label = f"p={candidate_p:.4f}"
        print(f"[segment5b-p2-sweep] candidate={label}")
        updated_policy_text = _write_p(original_policy_text, candidate_p)
        routing_policy_path.write_text(updated_policy_text, encoding="utf-8")

        _cleanup_outputs(run_root, seed, manifest_fingerprint)
        _run_checked(["make", "segment5b-s4", "segment5b-s5", f"RUNS_ROOT={runs_root_make}", f"RUN_ID={run_id}"], repo_root)
        gateboard_path = _score_candidate(
            repo_root=repo_root,
            runs_root=runs_root,
            run_id=run_id,
            out_root=out_root,
            sample_target=args.sample_target,
            baseline_runtime_seconds=baseline_runtime_seconds,
            label=label,
            suffix=suffix,
            baseline_p1_gateboard=baseline_p1_gateboard,
        )
        gateboard = _load_json(gateboard_path)
        summary = gateboard["summary"]
        matrix_rows.append(
            {
                "label": label,
                "p_virtual_hybrid": candidate_p,
                "t6": float((gateboard["gates"]["T6"] or {}).get("value") or 0.0),
                "t7": float((gateboard["gates"]["T7"] or {}).get("value") or 0.0),
                "frozen_failures": len(summary["frozen_failures"]),
                "primary_failures_count": len(summary["primary_failures"]),
                "calibration_distance_to_b": float(summary["calibration_distance_to_b"]),
                "lane_seconds": float((summary["runtime"] or {}).get("lane_s4_s5_seconds") or 0.0),
                "runtime_regression_veto": bool((summary["runtime"] or {}).get("regression_veto")),
                "lane_decision": str(summary["lane_decision"]),
                "phase_grade": str(summary["phase_grade"]),
            }
        )

    best = sorted(matrix_rows, key=_candidate_rank)[0]
    best_p = float(best["p_virtual_hybrid"])
    print(f"[segment5b-p2-sweep] best_candidate={best['label']} p={best_p:.4f}")

    # Final canonical rerun on selected policy.
    final_policy_text = _write_p(original_policy_text, best_p)
    routing_policy_path.write_text(final_policy_text, encoding="utf-8")
    _cleanup_outputs(run_root, seed, manifest_fingerprint)
    _run_checked(["make", "segment5b-s4", "segment5b-s5", f"RUNS_ROOT={runs_root_make}", f"RUN_ID={run_id}"], repo_root)
    _run_checked(
        [
            sys.executable,
            "tools/score_segment5b_p1_realism.py",
            "--runs-root",
            str(runs_root),
            "--run-id",
            run_id,
            "--out-root",
            str(out_root),
            "--sample-target",
            str(args.sample_target),
        ],
        repo_root,
    )
    _run_checked(
        [
            sys.executable,
            "tools/score_segment5b_p2_calibration.py",
            "--runs-root",
            str(runs_root),
            "--run-id",
            run_id,
            "--out-root",
            str(out_root),
            "--candidate-label",
            f"selected:{best['label']}",
            "--baseline-runtime-seconds",
            f"{baseline_runtime_seconds:.6f}",
            "--baseline-p1-gateboard-path",
            str(baseline_p1_gateboard),
        ],
        repo_root,
    )

    matrix_path = out_root / f"segment5b_p2_candidate_matrix_{run_id}.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "label",
                "p_virtual_hybrid",
                "t6",
                "t7",
                "frozen_failures",
                "primary_failures_count",
                "calibration_distance_to_b",
                "lane_seconds",
                "runtime_regression_veto",
                "lane_decision",
                "phase_grade",
            ],
        )
        writer.writeheader()
        for row in matrix_rows:
            writer.writerow(row)

    summary_path = out_root / f"segment5b_p2_sweep_summary_{run_id}.json"
    summary_path.write_text(
        json.dumps(
            {
                "generated_utc": _now_utc(),
                "phase": "P2.3",
                "run_id": run_id,
                "routing_policy_path": str(routing_policy_path),
                "baseline_runtime_seconds": baseline_runtime_seconds,
                "original_p_virtual_hybrid": p_original,
                "evaluated_candidates": matrix_rows,
                "best_candidate": best,
                "selected_p_virtual_hybrid": best_p,
                "matrix_csv_path": str(matrix_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[segment5b-p2-sweep] matrix_csv={matrix_path}")
    print(f"[segment5b-p2-sweep] sweep_summary={summary_path}")


if __name__ == "__main__":
    main()
