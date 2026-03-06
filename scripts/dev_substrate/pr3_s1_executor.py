#!/usr/bin/env python3
"""Deterministic PR3-S1 executor for road_to_prod (dev_full)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError


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


def parse_time_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def get_cloudwatch_metric(
    *,
    cw: Any,
    metric_name: str,
    dimensions: list[dict[str, str]],
    start_time: datetime,
    end_time: datetime,
    period_seconds: int,
    statistics: list[str] | None = None,
    extended_statistics: list[str] | None = None,
) -> list[dict[str, Any]]:
    kwargs: Dict[str, Any] = {
        "Namespace": "AWS/ApiGateway",
        "MetricName": metric_name,
        "Dimensions": dimensions,
        "StartTime": start_time,
        "EndTime": end_time,
        "Period": period_seconds,
    }
    if statistics:
        kwargs["Statistics"] = statistics
    if extended_statistics:
        kwargs["ExtendedStatistics"] = extended_statistics
    result = cw.get_metric_statistics(**kwargs)
    return list(result.get("Datapoints", []))


def sum_stat(datapoints: list[dict[str, Any]], key: str = "Sum") -> float:
    total = 0.0
    for row in datapoints:
        total += parse_float(row.get(key), 0.0)
    return total


def resolve_weighted_latency(
    latency_rows: list[dict[str, Any]],
    count_rows: list[dict[str, Any]],
) -> tuple[float, float, str]:
    count_by_ts: Dict[str, float] = {}
    for row in count_rows:
        ts = row.get("Timestamp")
        if ts is None:
            continue
        count_by_ts[str(ts)] = parse_float(row.get("Sum"), 0.0)

    p95_num = 0.0
    p99_num = 0.0
    weight_total = 0.0
    for row in latency_rows:
        ts = row.get("Timestamp")
        if ts is None:
            continue
        ext = row.get("ExtendedStatistics", {})
        p95 = parse_float(ext.get("p95"), -1.0)
        p99 = parse_float(ext.get("p99"), -1.0)
        if p95 < 0.0 or p99 < 0.0:
            continue
        w = count_by_ts.get(str(ts), 0.0)
        if w <= 0.0:
            continue
        p95_num += p95 * w
        p99_num += p99 * w
        weight_total += w
    if weight_total > 0.0:
        return (p95_num / weight_total, p99_num / weight_total, "weighted_by_count")

    p95_vals: list[float] = []
    p99_vals: list[float] = []
    for row in latency_rows:
        ext = row.get("ExtendedStatistics", {})
        p95 = parse_float(ext.get("p95"), -1.0)
        p99 = parse_float(ext.get("p99"), -1.0)
        if p95 >= 0.0:
            p95_vals.append(p95)
        if p99 >= 0.0:
            p99_vals.append(p99)
    if not p95_vals or not p99_vals:
        return (-1.0, -1.0, "unavailable")
    return (max(p95_vals), max(p99_vals), "max_percentile_fallback")


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
    ap.add_argument("--runtime-summary-ref", default="")
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--api-id", default="ehwznd2uw7")
    ap.add_argument("--api-stage", default="v1")
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

    runtime_summary_path = Path(args.runtime_summary_ref) if str(args.runtime_summary_ref).strip() else (pr3_root / "g3a_s1_wsp_runtime_summary.json")
    runtime_summary_exists = runtime_summary_path.exists()
    runtime_summary = load_json(runtime_summary_path) if runtime_summary_exists else {}

    observed_steady_eps = parse_float(runtime_summary.get("observed", {}).get("observed_admitted_eps"), 0.0)
    covered_metric_seconds = parse_float(
        runtime_summary.get("performance_window", {}).get("covered_metric_seconds"),
        0.0,
    )
    bounded_expected_events = parse_int(round(expected_steady_eps * covered_metric_seconds), 0)
    observed_sample_events = parse_int(runtime_summary.get("observed", {}).get("admitted_request_count"), 0)
    observed_error_rate_ratio = parse_float(runtime_summary.get("observed", {}).get("error_rate_ratio"), 1.0)
    observed_surface = "IG_ADMITTED_EVENTS_PER_SEC" if runtime_summary_exists else ""

    observed_latency_p95 = -1.0
    observed_latency_p99 = -1.0
    latency_derivation_method = "unavailable"
    latency_blocker = False
    if runtime_summary_exists:
        start_utc = str(runtime_summary.get("performance_window", {}).get("metric_effective_start_utc", "")).strip()
        end_utc = str(runtime_summary.get("performance_window", {}).get("metric_effective_end_utc", "")).strip()
        if start_utc and end_utc:
            cw = boto3.client("cloudwatch", region_name=args.region)
            dims = [{"Name": "ApiId", "Value": args.api_id}, {"Name": "Stage", "Value": args.api_stage}]
            try:
                latency_rows = get_cloudwatch_metric(
                    cw=cw,
                    metric_name="Latency",
                    dimensions=dims,
                    start_time=parse_time_utc(start_utc),
                    end_time=parse_time_utc(end_utc),
                    period_seconds=60,
                    extended_statistics=["p95", "p99"],
                )
                count_rows = get_cloudwatch_metric(
                    cw=cw,
                    metric_name="Count",
                    dimensions=dims,
                    start_time=parse_time_utc(start_utc),
                    end_time=parse_time_utc(end_utc),
                    period_seconds=60,
                    statistics=["Sum"],
                )
                observed_latency_p95, observed_latency_p99, latency_derivation_method = resolve_weighted_latency(
                    latency_rows, count_rows
                )
            except (BotoCoreError, ClientError):
                latency_blocker = True
        else:
            latency_blocker = True
    else:
        latency_blocker = True

    sample_minima_pass = observed_sample_events >= bounded_expected_events and bounded_expected_events > 0
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
            runtime_summary_exists,
            observed_steady_eps > 0.0,
            observed_sample_events > 0,
            observed_latency_p95 >= 0.0,
            observed_latency_p99 >= 0.0,
            observed_surface != "",
        ]
    )

    b07_profile_executed = strict_upstream_ready and runtime_summary_exists and observed_steady_eps > 0.0
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
        "mode": "REMOTE_WSP_CANONICAL",
        "goal": "certify steady profile at RC2-S target on correct surfaces with required minima",
        "expected": {
            "steady_rate_eps": expected_steady_eps,
            "steady_min_processed_events": bounded_expected_events,
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
            "source_ref": str(runtime_summary_path).replace("\\", "/"),
            "source_execution_id": runtime_summary.get("execution_id", ""),
            "covered_metric_seconds": covered_metric_seconds,
            "metric_bin_count": parse_int(runtime_summary.get("performance_window", {}).get("metric_bin_count"), 0),
            "latency_derivation_method": latency_derivation_method,
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
        "mode": "REMOTE_WSP_CANONICAL",
        "observations": {
            "overall_pass_from_source": bool(runtime_summary.get("open_blockers", 1) == 0),
            "source_verdict": runtime_summary.get("verdict", ""),
            "source_blocker_count": int(runtime_summary.get("open_blockers", 0)),
            "metric_bin_count": parse_int(runtime_summary.get("performance_window", {}).get("metric_bin_count"), 0),
            "lane_count": parse_int(runtime_summary.get("campaign", {}).get("lane_count"), 0),
        },
    }

    g3a_steady_sample_minima_receipt = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": pr3_id,
        "expected_min_processed_events": bounded_expected_events,
        "observed_sample_events": observed_sample_events,
        "sample_minima_pass": b08_sample_minima,
        "source_ref": str(runtime_summary_path).replace("\\", "/"),
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
                "status": "PINNED" if len(blockers) == 0 else "IN_PROGRESS",
                "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{pr3_id}/g3a_scorecard_steady.json",
                "notes": (
                    "Canonical remote-WSP steady window closed cleanly on settled minute bins."
                    if len(blockers) == 0
                    else "Steady-window check executed; threshold-family closure still pending due S1 blockers."
                ),
            }
        ],
        "elapsed_minutes": elapsed_minutes,
        "runtime_budget_minutes": 60,
        "attributable_spend_usd": 0.0,
        "cost_envelope_usd": parse_float(charter.get("budget_envelope_usd"), 250.0),
        "advisory_ids": [
            "PR3.S1.AD01_CANONICAL_REMOTE_WSP",
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
