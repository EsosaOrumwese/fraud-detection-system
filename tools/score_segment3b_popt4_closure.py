#!/usr/bin/env python3
"""Emit Segment 3B POPT.4 integrated closure artifact."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_ORDER = ["S0", "S1", "S2", "S3", "S4", "S5"]
S0_ELAPSED_RE = re.compile(r"S0: completed gate and sealed inputs \(elapsed=([0-9.]+)s\)")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_latest_run_id(runs_root: Path) -> str:
    receipts = sorted(runs_root.glob("*/run_receipt.json"), key=lambda p: p.stat().st_mtime)
    if not receipts:
        raise FileNotFoundError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1].parent.name


def _find_state_report(run_root: Path, state: str) -> Path:
    state_dir = run_root / "reports/layer1/3B" / f"state={state}"
    reports = sorted(state_dir.rglob("run_report.json"))
    if not reports:
        raise FileNotFoundError(f"Missing {state} run_report.json under {state_dir}")
    return reports[-1]


def _parse_s0_elapsed_s(run_log_path: Path) -> float:
    for line in run_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = S0_ELAPSED_RE.search(line)
        if match:
            return float(match.group(1))
    raise RuntimeError(f"S0 elapsed line not found in log: {run_log_path}")


def _fmt_hms(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _extract_runtime_baseline_s(baseline_popt0_json: Path) -> float:
    payload = _load_json(baseline_popt0_json)
    rows = payload.get("timing", {}).get("state_table", [])
    if not rows:
        raise ValueError(f"Invalid baseline artifact (missing timing.state_table): {baseline_popt0_json}")
    return float(sum(float(row.get("elapsed_s") or 0.0) for row in rows))


def _extract_authority(output_json: Path) -> dict[str, Any]:
    payload = _load_json(output_json)
    run = payload.get("run") or {}
    output = run.get("output") or {}
    digest = str(run.get("bundle_digest_from_flag") or "")
    if not digest:
        raise ValueError(f"Authority digest missing in {output_json}")
    return {
        "run_id": str(run.get("run_id") or ""),
        "bundle_digest_from_flag": digest,
        "bundle_path": str(output.get("bundle_path") or ""),
        "index_path": str(output.get("index_path") or ""),
        "flag_path": str(output.get("flag_path") or ""),
    }


def _parse_flag_digest(flag_path: Path) -> str:
    raw = flag_path.read_text(encoding="ascii", errors="ignore").strip()
    prefix = "sha256_hex = "
    if not raw.startswith(prefix):
        raise ValueError(f"Invalid flag file format: {flag_path}")
    return raw[len(prefix) :].strip()


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    baseline = payload["baseline"]
    candidate = payload["candidate"]
    checks = payload["checks"]
    lines = [
        "# Segment 3B POPT.4 Closure",
        "",
        f"- decision: `{payload['decision']}`",
        f"- candidate_run_id: `{candidate['run_id']}`",
        "",
        "## Runtime",
        f"- baseline_total: `{baseline['segment_elapsed_hms']}` ({baseline['segment_elapsed_s']:.3f}s)",
        f"- candidate_total: `{candidate['segment_elapsed_hms']}` ({candidate['segment_elapsed_s']:.3f}s)",
        f"- improvement: `{candidate['runtime_improvement_percent']:.2f}%`",
        f"- runtime_material_pass: `{checks['runtime_material_pass']}`",
        "",
        "## Determinism",
        f"- digest_parity_pass: `{checks['digest_parity_pass']}`",
        f"- output_path_parity_pass: `{checks['output_path_parity_pass']}`",
        f"- determinism_pass: `{checks['determinism_pass']}`",
        "",
        "## Structural",
        f"- s0_receipt_exists: `{checks['s0_receipt_exists']}`",
        f"- state_status_pass: `{checks['state_status_pass']}`",
        f"- s5_bundle_files_present: `{checks['s5_bundle_files_present']}`",
        f"- structural_pass: `{checks['structural_pass']}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit Segment 3B POPT.4 closure artifact.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--candidate-run-id", default="")
    parser.add_argument(
        "--baseline-popt0-json",
        default="runs/fix-data-engine/segment_3B/reports/segment3b_popt0_baseline_724a63d3f8b242809b8ec3b746d0c776.json",
    )
    parser.add_argument(
        "--authority-log-budget-json",
        default="runs/fix-data-engine/segment_3B/reports/segment3b_popt3_log_budget_baseline_724a63d3f8b242809b8ec3b746d0c776.json",
    )
    parser.add_argument("--runtime-improvement-threshold", type=float, default=0.10)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    candidate_run_id = args.candidate_run_id.strip() or _resolve_latest_run_id(runs_root)
    candidate_root = runs_root / candidate_run_id
    if not candidate_root.exists():
        raise FileNotFoundError(f"Candidate run root not found: {candidate_root}")

    receipt = _load_json(candidate_root / "run_receipt.json")
    manifest = str(receipt.get("manifest_fingerprint") or "")
    if not manifest:
        raise ValueError(f"Missing manifest_fingerprint in run_receipt.json for {candidate_run_id}")

    baseline_total_s = _extract_runtime_baseline_s(Path(args.baseline_popt0_json))
    authority = _extract_authority(Path(args.authority_log_budget_json))

    run_log_path = candidate_root / f"run_log_{candidate_run_id}.log"
    s0_elapsed_s = _parse_s0_elapsed_s(run_log_path)

    reports: dict[str, dict[str, Any]] = {}
    report_paths: dict[str, str] = {}
    for state in ["S1", "S2", "S3", "S4", "S5"]:
        rp = _find_state_report(candidate_root, state)
        report_paths[state] = str(rp).replace("\\", "/")
        reports[state] = _load_json(rp)

    candidate_elapsed_map = {"S0": s0_elapsed_s}
    for state in ["S1", "S2", "S3", "S4", "S5"]:
        candidate_elapsed_map[state] = float(reports[state].get("durations", {}).get("wall_ms", 0.0)) / 1000.0
    candidate_total_s = sum(candidate_elapsed_map[state] for state in STATE_ORDER)
    runtime_improvement_fraction = (baseline_total_s - candidate_total_s) / baseline_total_s if baseline_total_s > 0 else 0.0

    s0_receipt_path = (
        candidate_root
        / "data/layer1/3B/s0_gate_receipt"
        / f"manifest_fingerprint={manifest}"
        / "s0_gate_receipt_3B.json"
    )
    s0_receipt_exists = s0_receipt_path.exists()

    state_status_pass = all(str(reports[state].get("status", "")).upper() == "PASS" for state in ["S1", "S2", "S3", "S4", "S5"])

    s5_output = reports["S5"].get("output") or {}
    bundle_rel = str(s5_output.get("bundle_path") or "")
    index_rel = str(s5_output.get("index_path") or "")
    flag_rel = str(s5_output.get("flag_path") or "")
    bundle_dir = candidate_root / bundle_rel if bundle_rel else Path("")
    index_path = candidate_root / index_rel if index_rel else Path("")
    flag_path = candidate_root / flag_rel if flag_rel else Path("")
    s5_bundle_files_present = bool(bundle_dir and bundle_dir.exists() and index_path.exists() and flag_path.exists())
    candidate_flag_digest = _parse_flag_digest(flag_path) if s5_bundle_files_present else ""

    digest_parity_pass = bool(candidate_flag_digest and candidate_flag_digest == authority["bundle_digest_from_flag"])
    output_path_parity_pass = bool(
        bundle_rel == authority["bundle_path"]
        and index_rel == authority["index_path"]
        and flag_rel == authority["flag_path"]
    )
    determinism_pass = bool(digest_parity_pass and output_path_parity_pass)
    runtime_material_pass = bool(runtime_improvement_fraction >= float(args.runtime_improvement_threshold))
    structural_pass = bool(s0_receipt_exists and state_status_pass and s5_bundle_files_present)

    checks = {
        "runtime_material_pass": runtime_material_pass,
        "s0_receipt_exists": s0_receipt_exists,
        "state_status_pass": state_status_pass,
        "s5_bundle_files_present": s5_bundle_files_present,
        "digest_parity_pass": digest_parity_pass,
        "output_path_parity_pass": output_path_parity_pass,
        "determinism_pass": determinism_pass,
        "structural_pass": structural_pass,
    }

    decision = "CLOSED" if all((runtime_material_pass, determinism_pass, structural_pass)) else "HOLD_POPT4_REOPEN"

    payload: dict[str, Any] = {
        "phase": "POPT.4",
        "segment": "3B",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "decision": decision,
        "baseline": {
            "popt0_json": str(Path(args.baseline_popt0_json)).replace("\\", "/"),
            "segment_elapsed_s": baseline_total_s,
            "segment_elapsed_hms": _fmt_hms(baseline_total_s),
        },
        "candidate": {
            "run_id": candidate_run_id,
            "run_root": str(candidate_root).replace("\\", "/"),
            "run_log_path": str(run_log_path).replace("\\", "/"),
            "report_paths": report_paths,
            "state_elapsed_s": candidate_elapsed_map,
            "segment_elapsed_s": candidate_total_s,
            "segment_elapsed_hms": _fmt_hms(candidate_total_s),
            "runtime_improvement_fraction": runtime_improvement_fraction,
            "runtime_improvement_percent": runtime_improvement_fraction * 100.0,
            "s5_output": {
                "bundle_path": bundle_rel,
                "index_path": index_rel,
                "flag_path": flag_rel,
            },
            "s5_bundle_digest_from_flag": candidate_flag_digest,
        },
        "authority": {
            "log_budget_json": str(Path(args.authority_log_budget_json)).replace("\\", "/"),
            "run_id": authority["run_id"],
            "bundle_digest_from_flag": authority["bundle_digest_from_flag"],
            "s5_output": {
                "bundle_path": authority["bundle_path"],
                "index_path": authority["index_path"],
                "flag_path": authority["flag_path"],
            },
        },
        "gates": {
            "runtime_improvement_threshold_fraction": float(args.runtime_improvement_threshold),
        },
        "checks": checks,
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3b_popt4_closure_{candidate_run_id}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3b_popt4_closure_{candidate_run_id}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
