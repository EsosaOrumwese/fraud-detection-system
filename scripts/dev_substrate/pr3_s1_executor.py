#!/usr/bin/env python3
"""Deterministic PR3-S1 executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def resolve_pr3_execution_id(root: Path, explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()
    latest = load_json(root / "pr3_latest.json")
    eid = str(latest.get("execution_id", "")).strip()
    if not eid:
        raise RuntimeError("Unable to resolve PR3 execution id from pr3_latest.json")
    return eid


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute PR3-S1 steady-profile gate from strict S0 upstream.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", default="")
    ap.add_argument(
        "--steady-evidence-ref",
        default="runs/dev_substrate/dev_full/m7/m7s_m7k_cert_20260226T000002Z/m7k_throughput_cert_snapshot.json",
        help="Steady evidence artifact used for strict S1 evaluation.",
    )
    ap.add_argument(
        "--steady-evidence-summary-ref",
        default="runs/dev_substrate/dev_full/m7/m7s_m7k_cert_20260226T000002Z/m7k_throughput_cert_execution_summary.json",
    )
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    t0 = time.perf_counter()
    ts = now_utc()

    root = Path(args.run_control_root)
    if not root.exists():
        raise RuntimeError(f"Run-control root missing: {root}")

    pr3_id = resolve_pr3_execution_id(root, args.pr3_execution_id)
    pr3_root = root / pr3_id
    if not pr3_root.exists():
        raise RuntimeError(f"PR3 execution root does not exist: {pr3_root}")

    s0_receipt = load_json(pr3_root / "pr3_s0_execution_receipt.json")
    charter = load_json(pr3_root / "g3a_run_charter.active.json")
    surface_map = load_json(pr3_root / "g3a_measurement_surface_map.json")

    strict_upstream_ready = (
        str(s0_receipt.get("verdict", "")) == "PR3_S0_READY"
        and int(s0_receipt.get("open_blockers", 1)) == 0
        and str(s0_receipt.get("next_state", "")) == "PR3-S1"
    )

    # Required S1 targets from charter.
    load_campaign = charter.get("load_campaign", {})
    runtime_thresholds = charter.get("runtime_thresholds", {})
    expected_steady_eps = parse_float(load_campaign.get("steady", {}).get("rate_eps"), 0.0)
    expected_steady_events = parse_int(load_campaign.get("steady", {}).get("min_processed_events"), 0)
    expected_latency_p95_max = parse_float(
        runtime_thresholds.get("hot_path_slo", {}).get("decision_latency_ms", {}).get("p95_max"), 0.0
    )
    expected_latency_p99_max = parse_float(
        runtime_thresholds.get("hot_path_slo", {}).get("decision_latency_ms", {}).get("p99_max"), 0.0
    )
    expected_error_max = parse_float(runtime_thresholds.get("hot_path_slo", {}).get("error_rate_max"), 0.0)
    expected_surface = ""
    for row in surface_map.get("required_metric_surfaces", []):
        if row.get("metric_id") == "throughput_steady_eps":
            expected_surface = str(row.get("surface", ""))
            break

    # Evidence-only posture (no local runtime orchestration).
    evidence_path = Path(args.steady_evidence_ref)
    summary_path = Path(args.steady_evidence_summary_ref)
    evidence_exists = evidence_path.exists()
    summary_exists = summary_path.exists()
    evidence = load_json(evidence_path) if evidence_exists else {}
    evidence_summary = load_json(summary_path) if summary_exists else {}

    observed_steady_eps = parse_float(evidence.get("observed_events_per_second"), 0.0)
    observed_sample_events = parse_int(evidence.get("sample_size_events"), 0)
    observed_error_rate_pct = parse_float(evidence.get("error_rate_pct_observed"), 100.0)
    observed_error_rate_ratio = observed_error_rate_pct / 100.0
    observed_latency_p95 = parse_float(evidence.get("decision_latency_ms_p95"), -1.0)
    observed_latency_p99 = parse_float(evidence.get("decision_latency_ms_p99"), -1.0)
    observed_surface = str(evidence.get("measurement_surface", "")).strip()

    sample_minima_pass = observed_sample_events >= expected_steady_events and expected_steady_events > 0
    surface_scope_pass = observed_surface == expected_surface and expected_surface != ""

    steady_threshold_pass = (
        observed_steady_eps >= expected_steady_eps
        and observed_error_rate_ratio <= expected_error_max
        and observed_latency_p95 >= 0
        and observed_latency_p95 <= expected_latency_p95_max
        and observed_latency_p99 >= 0
        and observed_latency_p99 <= expected_latency_p99_max
    )

    scorecard_complete = all(
        [
            evidence_exists,
            summary_exists,
            observed_steady_eps > 0.0,
            observed_sample_events > 0,
            observed_latency_p95 >= 0.0,
            observed_latency_p99 >= 0.0,
            observed_surface != "",
        ]
    )

    b07_profile_executed = strict_upstream_ready and evidence_exists and observed_steady_eps > 0.0
    b08_sample_minima = sample_minima_pass
    b09_surface_scope = surface_scope_pass
    b10_steady_thresholds = steady_threshold_pass
    b11_scorecard_complete = scorecard_complete

    blockers: List[str] = []
    if not b07_profile_executed:
        blockers.append("PR3.B07_STEADY_PROFILE_NOT_EXECUTED")
    if not b08_sample_minima:
        blockers.append("PR3.B08_STEADY_SAMPLE_MINIMA_FAIL")
    if not b09_surface_scope:
        blockers.append("PR3.B09_STEADY_SURFACE_SCOPE_MISMATCH")
    if not b10_steady_thresholds:
        blockers.append("PR3.B10_STEADY_THRESHOLD_BREACH")
    if not b11_scorecard_complete:
        blockers.append("PR3.B11_STEADY_SCORECARD_INCOMPLETE")

    g3a_scorecard_steady = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "mode": "EVIDENCE_ONLY_REUSE_STRICT",
        "goal": "certify steady profile at RC2-S target on correct surfaces with required minima",
        "expected": {
            "steady_rate_eps": expected_steady_eps,
            "steady_min_processed_events": expected_steady_events,
            "steady_surface": expected_surface,
            "latency_p95_max_ms": expected_latency_p95_max,
            "latency_p99_max_ms": expected_latency_p99_max,
            "error_rate_max_ratio": expected_error_max,
        },
        "observed": {
            "steady_rate_eps": observed_steady_eps,
            "sample_size_events": observed_sample_events,
            "steady_surface": observed_surface if observed_surface else "UNDECLARED_IN_EVIDENCE",
            "latency_p95_ms": observed_latency_p95 if observed_latency_p95 >= 0 else None,
            "latency_p99_ms": observed_latency_p99 if observed_latency_p99 >= 0 else None,
            "error_rate_ratio": observed_error_rate_ratio,
            "source_ref": str(evidence_path).replace("\\", "/"),
            "source_summary_ref": str(summary_path).replace("\\", "/"),
            "source_execution_id": evidence.get("execution_id", evidence_summary.get("execution_id", "")),
        },
        "checks": {
            "steady_profile_executed": b07_profile_executed,
            "sample_minima_pass": b08_sample_minima,
            "surface_scope_pass": b09_surface_scope,
            "steady_thresholds_pass": b10_steady_thresholds,
            "scorecard_complete": b11_scorecard_complete,
        },
    }

    g3a_component_health_steady = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "mode": "EVIDENCE_ONLY_REUSE_STRICT",
        "observations": {
            "overall_pass_from_source": bool(evidence.get("overall_pass", False)),
            "source_verdict": evidence_summary.get("verdict", ""),
            "source_blocker_count": int(evidence_summary.get("blocker_count", 0)),
            "provisional_component_count": parse_int(evidence.get("provisional_component_count"), 0),
            "component_modes": evidence.get("component_modes", []),
        },
    }

    g3a_steady_sample_minima_receipt = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "expected_min_processed_events": expected_steady_events,
        "observed_sample_events": observed_sample_events,
        "sample_minima_pass": b08_sample_minima,
        "source_ref": str(evidence_path).replace("\\", "/"),
    }

    elapsed_minutes = round((time.perf_counter() - t0) / 60.0, 3)
    receipt = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "verdict": "PR3_S1_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S2" if len(blockers) == 0 else "PR3-S1",
        "next_gate": "PR3_RUNTIME_S1_READY" if len(blockers) == 0 else "PR3_REMEDIATE_S1",
        "open_blockers": len(blockers),
        "blocker_ids": blockers,
        "outputs": [
            "g3a_scorecard_steady.json",
            "g3a_component_health_steady.json",
            "g3a_steady_sample_minima_receipt.json",
        ],
        "checks": {
            "B07_steady_profile_executed": b07_profile_executed,
            "B08_steady_sample_minima_pass": b08_sample_minima,
            "B09_steady_surface_scope_pass": b09_surface_scope,
            "B10_steady_thresholds_pass": b10_steady_thresholds,
            "B11_steady_scorecard_complete": b11_scorecard_complete,
        },
        "tgt_updates": [
            {
                "target_id": "TGT-08",
                "status": "IN_PROGRESS",
                "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr3_id}/g3a_scorecard_steady.json",
                "notes": "Steady-window check executed; threshold-family closure still pending due S1 blockers.",
            }
        ],
        "elapsed_minutes": elapsed_minutes,
        "runtime_budget_minutes": 60,
        "attributable_spend_usd": 0.0,
        "cost_envelope_usd": parse_float(charter.get("budget_envelope_usd"), 250.0),
        "advisory_ids": [
            "PR3.S1.AD01_EVIDENCE_REUSE_MODE",
            "PR2.S1.CN01_BURST_SHAPER_REQUIRED",
        ],
    }

    dump_json(pr3_root / "g3a_scorecard_steady.json", g3a_scorecard_steady)
    dump_json(pr3_root / "g3a_component_health_steady.json", g3a_component_health_steady)
    dump_json(pr3_root / "g3a_steady_sample_minima_receipt.json", g3a_steady_sample_minima_receipt)
    dump_json(pr3_root / "pr3_s1_execution_receipt.json", receipt)
    dump_json(
        root / "pr3_latest.json",
        {
            "phase": "PR3",
            "execution_id": pr3_id,
            "latest_state": "S1",
            "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr3_id}/pr3_s1_execution_receipt.json",
            "updated_at_utc": now_utc(),
        },
    )

    print(
        json.dumps(
            {
                "execution_id": pr3_id,
                "state": "S1",
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "next_gate": receipt["next_gate"],
                "open_blockers": receipt["open_blockers"],
                "blocker_ids": blockers,
                "observed_steady_eps": observed_steady_eps,
                "target_steady_eps": expected_steady_eps,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
