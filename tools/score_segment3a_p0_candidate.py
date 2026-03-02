#!/usr/bin/env python3
"""Score Segment 3A P0 candidate against pinned baseline metrics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import score_segment3a_p0_baseline as p0


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_deltas(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float]:
    return {
        "s2_top1_share_median_multi_tz": float(candidate["s2"]["top1_share_median_multi_tz"])
        - float(baseline["s2"]["top1_share_median_multi_tz"]),
        "s2_share_top1_ge_099_multi_tz": float(candidate["s2"]["share_top1_ge_099_multi_tz"])
        - float(baseline["s2"]["share_top1_ge_099_multi_tz"]),
        "s3_merchant_share_std_median": float(candidate["s3"]["merchant_share_std_median"])
        - float(baseline["s3"]["merchant_share_std_median"]),
        "s4_escalated_multi_zone_rate": float(candidate["s4"]["escalated_multi_zone_rate"])
        - float(baseline["s4"]["escalated_multi_zone_rate"]),
        "s4_top1_share_median": float(candidate["s4"]["top1_share_median"])
        - float(baseline["s4"]["top1_share_median"]),
        "s4_top1_share_p75": float(candidate["s4"]["top1_share_p75"])
        - float(baseline["s4"]["top1_share_p75"]),
        "zone_alloc_top1_share_median": float(candidate["zone_alloc"]["top1_share_median"])
        - float(baseline["zone_alloc"]["top1_share_median"]),
    }


def _directional_uplift(delta: dict[str, float]) -> dict[str, bool]:
    return {
        "s2_top1_share_median_multi_tz_down": bool(delta["s2_top1_share_median_multi_tz"] < 0.0),
        "s2_share_top1_ge_099_multi_tz_down": bool(delta["s2_share_top1_ge_099_multi_tz"] < 0.0),
        "s3_merchant_share_std_median_up": bool(delta["s3_merchant_share_std_median"] > 0.0),
        "s4_escalated_multi_zone_rate_up": bool(delta["s4_escalated_multi_zone_rate"] > 0.0),
        "s4_top1_share_median_down": bool(delta["s4_top1_share_median"] < 0.0),
        "s4_top1_share_p75_down": bool(delta["s4_top1_share_p75"] < 0.0),
        "zone_alloc_top1_share_median_down": bool(delta["zone_alloc_top1_share_median"] < 0.0),
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    d = payload["delta_candidate_minus_baseline"]
    lines: list[str] = []
    lines.append("# Segment 3A P0 Candidate vs Baseline")
    lines.append("")
    lines.append(f"- baseline_run_id: `{payload['baseline']['run_id']}`")
    lines.append(f"- candidate_run_id: `{payload['candidate']['run_id']}`")
    lines.append(f"- baseline_verdict: `{payload['baseline']['verdict']}`")
    lines.append(f"- candidate_verdict: `{payload['candidate']['verdict']}`")
    lines.append("")
    lines.append("## Delta (candidate - baseline)")
    lines.append("")
    for key in [
        "s2_top1_share_median_multi_tz",
        "s2_share_top1_ge_099_multi_tz",
        "s3_merchant_share_std_median",
        "s4_escalated_multi_zone_rate",
        "s4_top1_share_median",
        "s4_top1_share_p75",
        "zone_alloc_top1_share_median",
    ]:
        lines.append(f"- {key}: `{d[key]:+.6f}`")
    lines.append("")
    lines.append("## Candidate Gates")
    lines.append("")
    for family in ["hard", "stretch"]:
        lines.append(f"- {family}:")
        for key, value in payload["candidate"]["gates"][family].items():
            lines.append(f"  - {key}: {'PASS' if value else 'FAIL'}")
    lines.append("")
    lines.append("## Baseline-vs-Candidate Gate Drift")
    lines.append("")
    for family in ["hard", "stretch"]:
        lines.append(f"- {family}:")
        for key, value in payload["gate_drift"][family].items():
            lines.append(f"  - {key}: `{value}`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- progression_decision: `{payload['progression_decision']}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3A P0 candidate against baseline.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3A")
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_3A/reports/segment3a_p0_baseline_metrics_81599ab107ba4c8db7fc5850287360fe.json",
    )
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    baseline_json = Path(args.baseline_json)
    baseline_payload = _load_json(baseline_json)
    baseline_metrics = baseline_payload["metrics"]
    baseline_gates = baseline_payload["gates"]
    baseline_run_id = str(baseline_payload["baseline_authority"]["run_id"])
    baseline_verdict = str(baseline_payload["verdict"])

    candidate_ctx = p0._resolve_run_context(runs_root, args.candidate_run_id.strip())
    candidate_metrics = p0.compute_metrics_from_context(candidate_ctx)
    candidate_gates = p0.evaluate_gates(candidate_metrics)
    candidate_verdict = p0.verdict_from_gates(candidate_gates)

    delta = _metric_deltas(candidate_metrics, baseline_metrics)
    uplift = _directional_uplift(delta)
    gate_drift: dict[str, dict[str, str]] = {"hard": {}, "stretch": {}}
    for family in ["hard", "stretch"]:
        for key, base_value in baseline_gates[family].items():
            cand_value = candidate_gates[family][key]
            if bool(base_value) == bool(cand_value):
                status = "UNCHANGED"
            elif bool(base_value) and not bool(cand_value):
                status = "REGRESSED"
            else:
                status = "IMPROVED"
            gate_drift[family][key] = status

    progression_decision = "HOLD_REMEDIATE" if candidate_verdict == "FAIL_REALISM" else "CANDIDATE_MEETS_GATE"

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P0",
        "segment": "3A",
        "baseline": {
            "json": str(baseline_json).replace("\\", "/"),
            "run_id": baseline_run_id,
            "verdict": baseline_verdict,
            "metrics": baseline_metrics,
            "gates": baseline_gates,
        },
        "candidate": {
            "runs_root": str(runs_root).replace("\\", "/"),
            "run_id": candidate_ctx["run_id"],
            "run_root": candidate_ctx["run_root"],
            "seed": candidate_ctx["seed"],
            "manifest_fingerprint": candidate_ctx["manifest_fingerprint"],
            "parameter_hash": candidate_ctx["parameter_hash"],
            "metrics": candidate_metrics,
            "gates": candidate_gates,
            "verdict": candidate_verdict,
        },
        "delta_candidate_minus_baseline": delta,
        "uplift_directional": uplift,
        "gate_drift": gate_drift,
        "progression_decision": progression_decision,
    }

    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment3a_p0_candidate_vs_baseline_{candidate_ctx['run_id']}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment3a_p0_candidate_vs_baseline_{candidate_ctx['run_id']}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
