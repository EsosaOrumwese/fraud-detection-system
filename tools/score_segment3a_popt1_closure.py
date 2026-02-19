#!/usr/bin/env python3
"""Score Segment 3A POPT.1 closure status from baseline and candidate evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


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


def _state_elapsed(payload: dict[str, Any], state: str) -> float:
    rows = payload.get("timing", {}).get("state_table", [])
    for row in rows:
        if str(row.get("state")) == state:
            value = row.get("elapsed_s")
            if value is None:
                raise ValueError(f"Missing elapsed_s for {state}")
            return float(value)
    raise ValueError(f"Missing {state} row in timing.state_table")


def _find_single(paths: list[Path], label: str) -> Path:
    if not paths:
        raise FileNotFoundError(f"Missing {label}")
    if len(paths) > 1:
        paths = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[0]


def _find_state_report(run_root: Path, state: str) -> Path:
    return _find_single(
        list((run_root / "reports/layer1/3A" / f"state={state}").rglob("run_report.json")),
        f"{state} run_report.json",
    )


def _improvement_fraction(baseline_s: float, candidate_s: float) -> float:
    if baseline_s <= 0:
        return 0.0
    return (baseline_s - candidate_s) / baseline_s


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    rt = payload["runtime"]
    vt = payload["veto"]
    gt = payload["gates"]
    lines = [
        "# Segment 3A POPT.1 Closure",
        "",
        f"- candidate_run_id: `{payload['candidate']['run_id']}`",
        f"- baseline_run_id: `{payload['baseline']['run_id']}`",
        f"- decision: `{payload['decision']['progression_decision']}`",
        "",
        "## Runtime Deltas",
        f"- S6: `{_fmt_hms(rt['s6']['baseline_s'])}` -> `{_fmt_hms(rt['s6']['candidate_s'])}` (improvement `{100.0*rt['s6']['improvement_fraction']:.2f}%`, gate `{gt['s6_runtime_gate']}`)",
        f"- S7: `{_fmt_hms(rt['s7']['baseline_s'])}` -> `{_fmt_hms(rt['s7']['candidate_s'])}` (improvement `{100.0*rt['s7']['improvement_fraction']:.2f}%`, gate `{gt['s7_runtime_gate']}`)",
        f"- S5: `{_fmt_hms(rt['s5']['baseline_s'])}` -> `{_fmt_hms(rt['s5']['candidate_s'])}` (improvement `{100.0*rt['s5']['improvement_fraction']:.2f}%`, gate `{gt['s5_runtime_gate']}`, required `{gt['s5_gate_required']}`)",
        "",
        "## Structural Veto",
        f"- s6_status_pass: `{vt['s6_status_pass']}`",
        f"- s6_issues_error_zero: `{vt['s6_issues_error_zero']}`",
        f"- s7_status_pass: `{vt['s7_status_pass']}`",
        f"- s7_passed_flag_present: `{vt['s7_passed_flag_present']}`",
        f"- s5_conservation_zero: `{vt['s5_conservation_zero']}`",
        f"- identity_match: `{vt['identity_match']}`",
        "",
        "## Verdict",
        f"- all_veto_clear: `{payload['decision']['all_veto_clear']}`",
        f"- all_runtime_gates_clear: `{payload['decision']['all_runtime_gates_clear']}`",
        f"- reason: {payload['decision']['reason']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3A POPT.1 closure")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3A")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_3A/reports/segment3a_popt0_baseline_06b822558c294a0888e3f8f342e83947.json",
    )
    parser.add_argument("--candidate-json", default="")
    parser.add_argument("--require-s5-gate", action="store_true")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    candidate_run_id = args.candidate_run_id.strip()
    run_root = runs_root / candidate_run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {run_root}")

    baseline_json_path = Path(args.baseline_json)
    baseline_payload = _load_json(baseline_json_path)
    baseline_run_id = str(baseline_payload.get("run", {}).get("run_id") or "")
    if not baseline_run_id:
        raise ValueError("baseline_json missing run.run_id")
    candidate_json_path = (
        Path(args.candidate_json)
        if args.candidate_json
        else runs_root / "reports" / f"segment3a_popt0_baseline_{candidate_run_id}.json"
    )
    candidate_payload = _load_json(candidate_json_path)

    baseline_s6 = _state_elapsed(baseline_payload, "S6")
    baseline_s7 = _state_elapsed(baseline_payload, "S7")
    baseline_s5 = _state_elapsed(baseline_payload, "S5")
    candidate_s6 = _state_elapsed(candidate_payload, "S6")
    candidate_s7 = _state_elapsed(candidate_payload, "S7")
    candidate_s5 = _state_elapsed(candidate_payload, "S5")

    s5_report = _load_json(_find_state_report(run_root, "S5"))
    s6_report = _load_json(_find_state_report(run_root, "S6"))
    s7_report = _load_json(_find_state_report(run_root, "S7"))
    run_receipt = _load_json(run_root / "run_receipt.json")
    manifest_fingerprint = str(run_receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(run_receipt.get("parameter_hash") or "")
    s7_index_path = (
        run_root
        / "data/layer1/3A/validation"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "index.json"
    )
    s7_index = _load_json(s7_index_path)

    veto = {
        "s6_status_pass": str(s6_report.get("status")) == "PASS" and str(s6_report.get("overall_status")) == "PASS",
        "s6_issues_error_zero": int((s6_report.get("counts") or {}).get("issues_error") or 0) == 0,
        "s7_status_pass": str(s7_report.get("status")) == "PASS",
        "s7_passed_flag_present": any(
            str(item.get("path", "")).endswith("_passed.flag")
            for item in (s7_index.get("files") or [])
            if isinstance(item, dict)
        ),
        "s5_conservation_zero": int((s5_report.get("counts") or {}).get("pairs_count_conservation_violations") or 0) == 0,
        "identity_match": (
            str(s5_report.get("manifest_fingerprint")) == manifest_fingerprint
            and str(s6_report.get("manifest_fingerprint")) == manifest_fingerprint
            and str(s7_report.get("manifest_fingerprint")) == manifest_fingerprint
            and str(s5_report.get("parameter_hash")) == parameter_hash
            and str(s6_report.get("parameter_hash")) == parameter_hash
            and str(s7_report.get("parameter_hash")) == parameter_hash
        ),
    }

    s6_impr = _improvement_fraction(baseline_s6, candidate_s6)
    s7_impr = _improvement_fraction(baseline_s7, candidate_s7)
    s5_impr = _improvement_fraction(baseline_s5, candidate_s5)
    gates = {
        "s6_runtime_gate": (candidate_s6 <= 14.0) or (s6_impr >= 0.15),
        "s7_runtime_gate": (candidate_s7 <= 12.0) or (s7_impr >= 0.10),
        "s5_runtime_gate": (candidate_s5 <= 12.0) or (s5_impr >= 0.08),
    }
    s5_gate_required = bool(args.require_s5_gate) or (baseline_s5 > 12.0)
    gates["s5_gate_required"] = s5_gate_required

    all_veto_clear = all(bool(value) for value in veto.values())
    runtime_clear = bool(gates["s6_runtime_gate"]) and bool(gates["s7_runtime_gate"])
    if s5_gate_required:
        runtime_clear = runtime_clear and bool(gates["s5_runtime_gate"])

    progression_decision = "UNLOCK_P0" if all_veto_clear and runtime_clear else "HOLD_POPT1_REOPEN"
    reason = (
        "All veto and runtime gates cleared."
        if progression_decision == "UNLOCK_P0"
        else "At least one veto or runtime gate failed; continue POPT.1 optimization."
    )

    payload: dict[str, Any] = {
        "phase": "POPT.1",
        "segment": "3A",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "baseline": {
            "run_id": baseline_run_id,
            "json": str(baseline_json_path).replace("\\", "/"),
        },
        "candidate": {
            "run_id": candidate_run_id,
            "json": str(candidate_json_path).replace("\\", "/"),
            "run_root": str(run_root).replace("\\", "/"),
        },
        "runtime": {
            "s6": {
                "baseline_s": baseline_s6,
                "candidate_s": candidate_s6,
                "improvement_fraction": s6_impr,
            },
            "s7": {
                "baseline_s": baseline_s7,
                "candidate_s": candidate_s7,
                "improvement_fraction": s7_impr,
            },
            "s5": {
                "baseline_s": baseline_s5,
                "candidate_s": candidate_s5,
                "improvement_fraction": s5_impr,
            },
        },
        "veto": veto,
        "gates": gates,
        "decision": {
            "all_veto_clear": all_veto_clear,
            "all_runtime_gates_clear": runtime_clear,
            "progression_decision": progression_decision,
            "reason": reason,
        },
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3a_popt1_closure_{candidate_run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3a_popt1_closure_{candidate_run_id}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)

    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
