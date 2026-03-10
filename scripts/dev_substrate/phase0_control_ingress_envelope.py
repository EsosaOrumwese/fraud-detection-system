#!/usr/bin/env python3
"""Phase 0.C bounded envelope and recovery proof on API Gateway -> Lambda."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

import boto3


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_stamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def to_iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_python_executable() -> str:
    override = Path.cwd() / ".venv" / "Scripts" / "python.exe"
    if override.exists():
        return str(override)
    return sys.executable


def seeded_segment_tokens(*, target_eps: float, burst_seconds: float, minimum_tokens: float) -> float:
    bucket_capacity = max(0.0, float(target_eps)) * max(0.0, float(burst_seconds))
    return max(float(minimum_tokens), bucket_capacity)


def _cwli_scalar(rows: list[list[dict[str, str]]], field_name: str) -> str:
    for row in rows:
        for cell in row:
            if str(cell.get("field", "")).strip() == str(field_name).strip():
                return str(cell.get("value", "")).strip()
    return ""


def _cwli_float(rows: list[list[dict[str, str]]], field_name: str) -> float | None:
    text = _cwli_scalar(rows, field_name)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def get_apigw_access_log_window_stats(
    logs: Any,
    *,
    log_group_name: str,
    start_time: datetime,
    end_time: datetime,
    route_key: str = "POST /ingest/push",
    poll_timeout_seconds: int = 45,
) -> dict[str, Any]:
    exact_start = start_time.astimezone(timezone.utc)
    exact_end = end_time.astimezone(timezone.utc)
    covered_seconds = max(0.0, (exact_end - exact_start).total_seconds())
    if covered_seconds <= 0.0:
        return {
            "request_count_total": 0.0,
            "request_4xx_total": 0.0,
            "request_5xx_total": 0.0,
            "covered_seconds": covered_seconds,
            "effective_start_utc": to_iso_utc(exact_start),
            "effective_end_utc": to_iso_utc(exact_end),
            "latency_p95_ms": None,
            "latency_p99_ms": None,
            "query_status": "SKIPPED",
            "query_id": "",
            "records_matched": 0.0,
            "records_scanned": 0.0,
            "bytes_scanned": 0.0,
        }
    escaped_route_key = str(route_key).replace('"', '\\"')
    query = dedent(
        f"""
        fields @timestamp, status, route_key, response_latency_ms
        | filter route_key = "{escaped_route_key}"
        | stats count(*) as request_count_total,
                sum(if(status >= 400 and status < 500, 1, 0)) as request_4xx_total,
                sum(if(status >= 500 and status < 600, 1, 0)) as request_5xx_total,
                pct(response_latency_ms, 95) as latency_p95_ms,
                pct(response_latency_ms, 99) as latency_p99_ms
        """
    ).strip()
    started = logs.start_query(
        logGroupName=str(log_group_name).strip(),
        startTime=int(exact_start.timestamp()),
        endTime=int(math.ceil(exact_end.timestamp())),
        queryString=query,
        limit=10,
    )
    query_id = str(started.get("queryId", "")).strip()
    if not query_id:
        raise RuntimeError("APIGW access-log query started without queryId")
    deadline = time.time() + max(5, int(poll_timeout_seconds))
    result: dict[str, Any] = {}
    while time.time() < deadline:
        result = logs.get_query_results(queryId=query_id)
        status = str(result.get("status", "")).strip()
        if status in {"Complete", "Failed", "Cancelled", "Timeout", "Unknown"}:
            break
        time.sleep(2)
    status = str(result.get("status", "")).strip() or "Unknown"
    if status != "Complete":
        raise RuntimeError(f"APIGW access-log query not complete: {status}")
    rows = list(result.get("results", []) or [])
    statistics = result.get("statistics", {}) if isinstance(result, dict) else {}
    return {
        "request_count_total": float(_cwli_float(rows, "request_count_total") or 0.0),
        "request_4xx_total": float(_cwli_float(rows, "request_4xx_total") or 0.0),
        "request_5xx_total": float(_cwli_float(rows, "request_5xx_total") or 0.0),
        "covered_seconds": covered_seconds,
        "effective_start_utc": to_iso_utc(exact_start),
        "effective_end_utc": to_iso_utc(exact_end),
        "latency_p95_ms": _cwli_float(rows, "latency_p95_ms"),
        "latency_p99_ms": _cwli_float(rows, "latency_p99_ms"),
        "query_status": status,
        "query_id": query_id,
        "records_matched": float(statistics.get("recordsMatched", 0.0) or 0.0),
        "records_scanned": float(statistics.get("recordsScanned", 0.0) or 0.0),
        "bytes_scanned": float(statistics.get("bytesScanned", 0.0) or 0.0),
    }


def get_stable_apigw_access_log_window_stats(
    logs: Any,
    *,
    log_group_name: str,
    start_time: datetime,
    end_time: datetime,
    route_key: str = "POST /ingest/push",
    max_attempts: int = 8,
    retry_sleep_seconds: int = 15,
    stability_ratio: float = 0.001,
) -> dict[str, Any]:
    previous_count: float | None = None
    best: dict[str, Any] | None = None
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        current = get_apigw_access_log_window_stats(
            logs,
            log_group_name=log_group_name,
            start_time=start_time,
            end_time=end_time,
            route_key=route_key,
        )
        current["stability_attempt"] = attempt
        best = current
        current_count = float(current.get("request_count_total", 0.0) or 0.0)
        if previous_count is not None:
            growth = current_count - previous_count
            baseline = max(1.0, previous_count)
            if growth <= (baseline * float(stability_ratio)):
                current["stability_state"] = "stable"
                return current
        previous_count = current_count
        current["stability_state"] = "growing"
        if attempt < int(max_attempts):
            time.sleep(max(1, int(retry_sleep_seconds)))
    if best is None:
        raise RuntimeError("APIGW access-log stability query produced no result")
    best["stability_state"] = "max_attempts_exhausted"
    return best


def get_lambda_metric_sum(
    cw: Any,
    *,
    function_name: str,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> float:
    payload = cw.get_metric_statistics(
        Namespace="AWS/Lambda",
        MetricName=metric_name,
        Dimensions=[{"Name": "FunctionName", "Value": function_name}],
        StartTime=start_time.astimezone(timezone.utc),
        EndTime=end_time.astimezone(timezone.utc),
        Period=max(60, int(period_seconds)),
        Statistics=["Sum"],
    )
    return float(sum(float(row.get("Sum", 0.0) or 0.0) for row in payload.get("Datapoints", []) or []))


def summarize_window(
    *,
    label: str,
    stats: dict[str, Any],
    expected_eps: float,
    max_latency_p95_ms: float,
    max_latency_p99_ms: float,
) -> tuple[dict[str, Any], list[str]]:
    request_count_total = max(0.0, float(stats.get("request_count_total", 0.0) or 0.0))
    request_4xx_total = max(0.0, float(stats.get("request_4xx_total", 0.0) or 0.0))
    request_5xx_total = max(0.0, float(stats.get("request_5xx_total", 0.0) or 0.0))
    covered_seconds = max(0.0, float(stats.get("covered_seconds", 0.0) or 0.0))
    admitted_count = max(0.0, request_count_total - request_4xx_total - request_5xx_total)
    observed_admitted_eps = admitted_count / covered_seconds if covered_seconds > 0.0 else 0.0
    latency_p95_ms = stats.get("latency_p95_ms")
    latency_p99_ms = stats.get("latency_p99_ms")
    blockers: list[str] = []
    if observed_admitted_eps < float(expected_eps):
        blockers.append(
            f"{label.upper()}_THROUGHPUT_SHORTFALL:observed={observed_admitted_eps:.3f}:target={float(expected_eps):.3f}"
        )
    if request_4xx_total > 0.0:
        blockers.append(f"{label.upper()}_4XX_PRESENT:count={int(request_4xx_total)}")
    if request_5xx_total > 0.0:
        blockers.append(f"{label.upper()}_5XX_PRESENT:count={int(request_5xx_total)}")
    if latency_p95_ms is None:
        blockers.append(f"{label.upper()}_P95_UNREADABLE")
    elif float(latency_p95_ms) > float(max_latency_p95_ms):
        blockers.append(
            f"{label.upper()}_P95_BREACH:observed={float(latency_p95_ms):.3f}:max={float(max_latency_p95_ms):.3f}"
        )
    if latency_p99_ms is None:
        blockers.append(f"{label.upper()}_P99_UNREADABLE")
    elif float(latency_p99_ms) > float(max_latency_p99_ms):
        blockers.append(
            f"{label.upper()}_P99_BREACH:observed={float(latency_p99_ms):.3f}:max={float(max_latency_p99_ms):.3f}"
        )
    summary = {
        "label": label,
        "measurement_start_utc": stats.get("effective_start_utc"),
        "measurement_end_utc": stats.get("effective_end_utc"),
        "covered_seconds": covered_seconds,
        "request_count_total": int(request_count_total),
        "admitted_request_count": int(admitted_count),
        "observed_admitted_eps": observed_admitted_eps,
        "4xx_total": int(request_4xx_total),
        "5xx_total": int(request_5xx_total),
        "latency_p95_ms": latency_p95_ms,
        "latency_p99_ms": latency_p99_ms,
        "query_status": stats.get("query_status"),
        "query_id": stats.get("query_id"),
        "stability_state": stats.get("stability_state"),
        "status": "GREEN" if not blockers else "RED",
        "blockers": blockers,
    }
    return summary, blockers


def dlq_counts(sqs: Any, *, queue_url: str) -> dict[str, int]:
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
            "ApproximateNumberOfMessagesDelayed",
        ],
    ).get("Attributes", {})
    visible = int(str(attrs.get("ApproximateNumberOfMessages", "0")).strip() or "0")
    not_visible = int(str(attrs.get("ApproximateNumberOfMessagesNotVisible", "0")).strip() or "0")
    delayed = int(str(attrs.get("ApproximateNumberOfMessagesDelayed", "0")).strip() or "0")
    return {
        "visible": visible,
        "not_visible": not_visible,
        "delayed": delayed,
        "total": visible + not_visible + delayed,
    }


def align_future_campaign_start(*, lead_seconds: int) -> datetime:
    base = now_utc() + timedelta(seconds=max(30, int(lead_seconds)))
    rounded_epoch = int(math.ceil(base.timestamp() / 30.0) * 30.0)
    return datetime.fromtimestamp(rounded_epoch, tz=timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Run Phase 0.C envelope and recovery proof on AWS.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", default="")
    ap.add_argument("--state-id", default="PHASE0C")
    ap.add_argument("--artifact-prefix", default="phase0c")
    ap.add_argument("--blocker-prefix", default="PHASE0.C.INGRESS")
    ap.add_argument("--window-label", default="envelope")
    ap.add_argument("--platform-run-id", default="")
    ap.add_argument("--scenario-run-id", default="")
    ap.add_argument("--generated-by", default="phase0-control-ingress-envelope")
    ap.add_argument("--steady-seconds", type=int, default=90)
    ap.add_argument("--burst-seconds", type=int, default=30)
    ap.add_argument("--recovery-seconds", type=int, default=180)
    ap.add_argument("--presteady-seconds", type=int, default=60)
    ap.add_argument("--campaign-start-lead-seconds", type=int, default=120)
    ap.add_argument("--presteady-eps", type=float, default=1500.0)
    ap.add_argument("--steady-eps", type=float, default=3000.0)
    ap.add_argument("--burst-eps", type=float, default=6000.0)
    ap.add_argument("--recovery-bound-seconds", type=float, default=180.0)
    ap.add_argument("--recovery-bin-seconds", type=int, default=30)
    ap.add_argument("--lane-count", type=int, default=48)
    ap.add_argument("--stream-speedup", type=float, default=600.0)
    ap.add_argument("--lane-launch-stagger-seconds", type=float, default=0.5)
    ap.add_argument("--campaign-start-stagger-seconds", type=float, default=0.5)
    ap.add_argument("--output-concurrency", type=int, default=4)
    ap.add_argument("--ig-push-concurrency", type=int, default=4)
    ap.add_argument("--http-pool-maxsize", type=int, default=512)
    ap.add_argument("--target-burst-seconds", type=float, default=0.25)
    ap.add_argument("--target-initial-tokens", type=float, default=0.25)
    ap.add_argument("--early-cutoff-seconds", type=int, default=60)
    ap.add_argument("--early-cutoff-floor-ratio", type=float, default=0.0)
    ap.add_argument("--metric-settle-seconds", type=int, default=90)
    ap.add_argument("--lane-log-mode", choices=("auto", "full", "metadata"), default="auto")
    ap.add_argument("--wsp-checkpoint-backend", default="file")
    ap.add_argument("--wsp-checkpoint-root", default="/tmp/wsp-checkpoints")
    ap.add_argument("--wsp-checkpoint-flush-every", default="50000")
    ap.add_argument("--traffic-output-ids", default="s3_event_stream_with_fraud_6B")
    ap.add_argument(
        "--context-output-ids",
        default="arrival_events_5B,s1_arrival_entities_6B,s3_flow_anchor_with_fraud_6B",
    )
    ap.add_argument("--oracle-engine-run-root", default="")
    ap.add_argument("--api-id", default="pd7rtjze95")
    ap.add_argument("--ig-api-name", default="fraud-platform-dev-full-ig-edge")
    ap.add_argument("--api-stage", default="v1")
    ap.add_argument("--lambda-function-name", default="fraud-platform-dev-full-ig-handler")
    ap.add_argument("--dlq-url", default="https://sqs.eu-west-2.amazonaws.com/230372904534/fraud-platform-dev-full-ig-dlq")
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--dry-run", action="store_true")
    return ap


def main() -> None:
    args = build_parser().parse_args()
    execution_id = str(args.execution_id).strip() or f"phase0_{now_stamp()}"
    platform_run_id = str(args.platform_run_id).strip() or f"platform_{now_stamp()}"
    scenario_run_id = str(args.scenario_run_id).strip() or uuid.uuid4().hex
    campaign_start = align_future_campaign_start(lead_seconds=args.campaign_start_lead_seconds)
    presteady_seconds = max(0, int(args.presteady_seconds))
    steady_seconds = max(60, int(args.steady_seconds))
    burst_seconds = max(1, int(args.burst_seconds))
    recovery_seconds = max(60, int(args.recovery_seconds))
    lane_count = max(1, int(args.lane_count))
    campaign_start_stagger_seconds = max(0.0, float(args.campaign_start_stagger_seconds))
    campaign_start_spread_seconds = max(0.0, float(lane_count - 1) * campaign_start_stagger_seconds)
    if campaign_start_spread_seconds >= float(presteady_seconds):
        raise RuntimeError(
            "Phase 0.C startup spread exceeds or equals presteady window; not all lanes would be active by steady start"
        )
    duration_seconds = presteady_seconds + steady_seconds + burst_seconds + recovery_seconds
    presteady_per_lane_eps = float(args.presteady_eps) / float(lane_count)
    steady_per_lane_eps = float(args.steady_eps) / float(lane_count)
    burst_per_lane_eps = float(args.burst_eps) / float(lane_count)
    recovery_per_lane_eps = float(args.steady_eps) / float(lane_count)
    segment_burst_seconds = max(0.0, float(args.target_burst_seconds))
    segment_minimum_tokens = max(0.0, float(args.target_initial_tokens))
    rate_plan: list[dict[str, Any]] = []
    segment_offset = 0
    if presteady_seconds > 0:
        rate_plan.append(
            {
                "start_offset_seconds": segment_offset,
                "target_eps": presteady_per_lane_eps,
                "burst_seconds": segment_burst_seconds,
                "initial_tokens": seeded_segment_tokens(
                    target_eps=presteady_per_lane_eps,
                    burst_seconds=segment_burst_seconds,
                    minimum_tokens=segment_minimum_tokens,
                ),
            }
        )
        segment_offset += presteady_seconds
    rate_plan.extend(
        [
            {
                "start_offset_seconds": segment_offset,
                "target_eps": steady_per_lane_eps,
                "burst_seconds": segment_burst_seconds,
                "initial_tokens": seeded_segment_tokens(
                    target_eps=steady_per_lane_eps,
                    burst_seconds=segment_burst_seconds,
                    minimum_tokens=segment_minimum_tokens,
                ),
            },
            {
                "start_offset_seconds": segment_offset + steady_seconds,
                "target_eps": burst_per_lane_eps,
                "burst_seconds": segment_burst_seconds,
                "initial_tokens": seeded_segment_tokens(
                    target_eps=burst_per_lane_eps,
                    burst_seconds=segment_burst_seconds,
                    minimum_tokens=segment_minimum_tokens,
                ),
            },
            {
                "start_offset_seconds": segment_offset + steady_seconds + burst_seconds,
                "target_eps": recovery_per_lane_eps,
                "burst_seconds": segment_burst_seconds,
                "initial_tokens": seeded_segment_tokens(
                    target_eps=recovery_per_lane_eps,
                    burst_seconds=segment_burst_seconds,
                    minimum_tokens=segment_minimum_tokens,
                ),
            },
        ]
    )
    execution_root = Path(args.run_control_root) / execution_id
    execution_root.mkdir(parents=True, exist_ok=True)
    compatibility_receipt = execution_root / "pr3_s0_execution_receipt.json"
    if not compatibility_receipt.exists():
        dump_json(
            compatibility_receipt,
            {
                "generated_by": str(args.generated_by),
                "generated_at_utc": to_iso_utc(now_utc()),
                "compatibility_mode": "phase0c_wrapper_seed",
                "verdict": "PR3_S0_READY",
                "open_blockers": 0,
            },
        )

    dispatch_script = Path(__file__).with_name("pr3_wsp_replay_dispatch.py")
    api_stage = str(args.api_stage).strip().strip("/")
    explicit_ig_ingest_url = f"https://{str(args.api_id).strip()}.execute-api.{str(args.region).strip()}.amazonaws.com/{api_stage}/ingest/push"
    dispatch_command = [
        resolve_python_executable(),
        str(dispatch_script),
        "--run-control-root",
        str(args.run_control_root),
        "--pr3-execution-id",
        execution_id,
        "--state-id",
        str(args.state_id),
        "--window-label",
        str(args.window_label),
        "--artifact-prefix",
        str(args.artifact_prefix),
        "--blocker-prefix",
        str(args.blocker_prefix),
        "--platform-run-id",
        platform_run_id,
        "--scenario-run-id",
        scenario_run_id,
        "--duration-seconds",
        str(duration_seconds),
        "--warmup-seconds",
        "0",
        "--early-cutoff-seconds",
        str(max(0, int(args.early_cutoff_seconds))),
        "--early-cutoff-floor-ratio",
        str(max(0.0, float(args.early_cutoff_floor_ratio))),
        "--expected-window-eps",
        str(float(args.steady_eps)),
        "--stream-speedup",
        str(float(args.stream_speedup)),
        "--lane-count",
        str(lane_count),
        "--lane-launch-stagger-seconds",
        str(float(args.lane_launch_stagger_seconds)),
        "--campaign-start-stagger-seconds",
        str(campaign_start_stagger_seconds),
        "--output-concurrency",
        str(max(1, int(args.output_concurrency))),
        "--ig-push-concurrency",
        str(max(1, int(args.ig_push_concurrency))),
        "--http-pool-maxsize",
        str(max(16, int(args.http_pool_maxsize))),
        "--target-request-rate-eps",
        str(float(args.steady_eps)),
        "--target-burst-seconds",
        str(max(0.0, float(args.target_burst_seconds))),
        "--target-initial-tokens",
        str(max(0.0, float(args.target_initial_tokens))),
        "--campaign-start-utc",
        str(to_iso_utc(campaign_start)),
        "--rate-plan-json",
        json.dumps(rate_plan, separators=(",", ":")),
        "--wsp-disable-replay-delay-when-rate-plan",
        "--metric-settle-seconds",
        str(max(0, int(args.metric_settle_seconds))),
        "--lane-log-mode",
        str(args.lane_log_mode),
        "--wsp-checkpoint-backend",
        str(args.wsp_checkpoint_backend),
        "--wsp-checkpoint-root",
        str(args.wsp_checkpoint_root),
        "--wsp-checkpoint-flush-every",
        str(args.wsp_checkpoint_flush_every),
        "--traffic-output-ids",
        str(args.traffic_output_ids),
        "--context-output-ids",
        str(args.context_output_ids),
        "--api-id",
        str(args.api_id),
        "--ig-api-name",
        str(args.ig_api_name),
        "--api-stage",
        str(args.api_stage),
        "--ig-ingest-url",
        explicit_ig_ingest_url,
        "--generated-by",
        str(args.generated_by),
        "--checkpoint-attempt-id",
        now_stamp(),
        "--skip-final-threshold-check",
    ]
    oracle_engine_run_root = str(args.oracle_engine_run_root).strip()
    if oracle_engine_run_root:
        dispatch_command.extend(["--oracle-engine-run-root", oracle_engine_run_root])

    preview = {
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "campaign_start_utc": to_iso_utc(campaign_start),
        "campaign_start_stagger_seconds": campaign_start_stagger_seconds,
        "campaign_start_spread_seconds": campaign_start_spread_seconds,
        "rate_plan_start_utc": to_iso_utc(campaign_start),
        "common_segment_seconds": {
            "steady": float(steady_seconds),
            "burst": float(burst_seconds),
            "recovery": float(recovery_seconds),
        },
        "duration_seconds": duration_seconds,
        "rate_plan_per_lane": rate_plan,
        "dispatch_command": dispatch_command,
    }
    if args.dry_run:
        print(json.dumps(preview, indent=2))
        return

    logs = boto3.client("logs", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)
    sqs = boto3.client("sqs", region_name=args.region)
    dlq_before = dlq_counts(sqs, queue_url=str(args.dlq_url).strip())

    subprocess.run(dispatch_command, check=True)

    dispatch_summary_path = execution_root / f"{str(args.artifact_prefix).strip()}_wsp_runtime_summary.json"
    dispatch_manifest_path = execution_root / f"{str(args.artifact_prefix).strip()}_wsp_runtime_manifest.json"
    dispatch_summary = load_json(dispatch_summary_path)
    dispatch_manifest = load_json(dispatch_manifest_path)
    ingress_surface = dict((((dispatch_summary.get("notes") or {}).get("ingress_metric_surface")) or {}))
    access_log_group = str(ingress_surface.get("apigw_access_log_group") or "").strip()
    if not access_log_group:
        raise RuntimeError("Phase 0.C APIGW access log group unresolved from dispatcher summary")

    steady_segment_start = campaign_start + timedelta(seconds=presteady_seconds)
    steady_segment_end = steady_segment_start + timedelta(seconds=steady_seconds)
    burst_segment_start = steady_segment_end
    burst_segment_end = burst_segment_start + timedelta(seconds=burst_seconds)
    recovery_segment_start = burst_segment_end
    recovery_segment_end = recovery_segment_start + timedelta(seconds=recovery_seconds)

    steady_start = steady_segment_start
    steady_end = steady_segment_end
    burst_start = burst_segment_start
    burst_end = burst_segment_end
    recovery_start = recovery_segment_start
    recovery_end = recovery_segment_end

    steady_stats = get_stable_apigw_access_log_window_stats(
        logs,
        log_group_name=access_log_group,
        start_time=steady_start,
        end_time=steady_end,
    )
    burst_stats = get_stable_apigw_access_log_window_stats(
        logs,
        log_group_name=access_log_group,
        start_time=burst_start,
        end_time=burst_end,
    )
    recovery_stats = get_stable_apigw_access_log_window_stats(
        logs,
        log_group_name=access_log_group,
        start_time=recovery_start,
        end_time=recovery_end,
    )

    steady_summary, steady_blockers = summarize_window(
        label="steady",
        stats=steady_stats,
        expected_eps=float(args.steady_eps),
        max_latency_p95_ms=float(args.max_latency_p95_ms),
        max_latency_p99_ms=float(args.max_latency_p99_ms),
    )
    burst_summary, burst_blockers = summarize_window(
        label="burst",
        stats=burst_stats,
        expected_eps=float(args.burst_eps),
        max_latency_p95_ms=float(args.max_latency_p95_ms),
        max_latency_p99_ms=float(args.max_latency_p99_ms),
    )
    recovery_summary, recovery_blockers = summarize_window(
        label="recovery",
        stats=recovery_stats,
        expected_eps=float(args.steady_eps),
        max_latency_p95_ms=float(args.max_latency_p95_ms),
        max_latency_p99_ms=float(args.max_latency_p99_ms),
    )

    recovery_bin_seconds = max(10, int(args.recovery_bin_seconds))
    recovery_bins: list[dict[str, Any]] = []
    cursor = recovery_start
    while cursor < recovery_end:
        window_end = min(recovery_end, cursor + timedelta(seconds=recovery_bin_seconds))
        bin_stats = get_stable_apigw_access_log_window_stats(
            logs,
            log_group_name=access_log_group,
            start_time=cursor,
            end_time=window_end,
            max_attempts=6,
            retry_sleep_seconds=10,
        )
        bin_summary, bin_blockers = summarize_window(
            label="recovery_bin",
            stats=bin_stats,
            expected_eps=float(args.steady_eps),
            max_latency_p95_ms=float(args.max_latency_p95_ms),
            max_latency_p99_ms=float(args.max_latency_p99_ms),
        )
        recovery_bins.append(
            {
                "measurement_start_utc": bin_summary["measurement_start_utc"],
                "measurement_end_utc": bin_summary["measurement_end_utc"],
                "covered_seconds": bin_summary["covered_seconds"],
                "observed_admitted_eps": bin_summary["observed_admitted_eps"],
                "4xx_total": bin_summary["4xx_total"],
                "5xx_total": bin_summary["5xx_total"],
                "latency_p95_ms": bin_summary["latency_p95_ms"],
                "latency_p99_ms": bin_summary["latency_p99_ms"],
                "status": "GREEN" if not bin_blockers else "RED",
                "blockers": bin_blockers,
            }
        )
        cursor = window_end

    sustained_green_start_utc = None
    for index, row in enumerate(recovery_bins):
        if row["status"] == "GREEN" and all(next_row["status"] == "GREEN" for next_row in recovery_bins[index:]):
            sustained_green_start_utc = str(row.get("measurement_start_utc") or "").strip() or None
            break
    recovery_seconds_to_sustained_green = None
    if sustained_green_start_utc:
        sustained_green_start = parse_utc(sustained_green_start_utc)
        if sustained_green_start is not None:
            recovery_seconds_to_sustained_green = max(0.0, (sustained_green_start - recovery_start).total_seconds())

    lambda_errors_sum = get_lambda_metric_sum(
        cw,
        function_name=str(args.lambda_function_name).strip(),
        metric_name="Errors",
        start_time=steady_start,
        end_time=recovery_end,
    )
    lambda_throttles_sum = get_lambda_metric_sum(
        cw,
        function_name=str(args.lambda_function_name).strip(),
        metric_name="Throttles",
        start_time=steady_start,
        end_time=recovery_end,
    )
    dlq_after = dlq_counts(sqs, queue_url=str(args.dlq_url).strip())
    dlq_delta_total = int(dlq_after["total"] - dlq_before["total"])

    blockers: list[str] = []
    blockers.extend(steady_blockers)
    blockers.extend(burst_blockers)
    blockers.extend(recovery_blockers)
    if recovery_seconds_to_sustained_green is None:
        blockers.append("RECOVERY_NOT_SUSTAINED_GREEN")
    elif recovery_seconds_to_sustained_green > float(args.recovery_bound_seconds):
        blockers.append(
            f"RECOVERY_BOUND_EXCEEDED:observed={recovery_seconds_to_sustained_green:.3f}:max={float(args.recovery_bound_seconds):.3f}"
        )
    if lambda_errors_sum > 0.0:
        blockers.append(f"LAMBDA_ERRORS_PRESENT:sum={lambda_errors_sum:.3f}")
    if lambda_throttles_sum > 0.0:
        blockers.append(f"LAMBDA_THROTTLES_PRESENT:sum={lambda_throttles_sum:.3f}")
    if dlq_delta_total > 0:
        blockers.append(f"DLQ_GROWTH_PRESENT:delta={dlq_delta_total}")
    if int(dispatch_summary.get("open_blockers", 0) or 0) > 0:
        blockers.append(f"DISPATCH_BLOCKERS_PRESENT:count={int(dispatch_summary.get('open_blockers', 0) or 0)}")

    envelope_summary = {
        "phase": "PHASE0",
        "state": str(args.state_id),
        "generated_at_utc": to_iso_utc(now_utc()),
        "generated_by": str(args.generated_by),
        "execution_id": execution_id,
        "verdict": "PHASE0C_READY" if not blockers else "HOLD_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": sorted(set(blockers)),
        "identity": {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
        },
        "campaign": {
            "campaign_start_utc": to_iso_utc(campaign_start),
            "campaign_start_stagger_seconds": campaign_start_stagger_seconds,
            "campaign_start_spread_seconds": campaign_start_spread_seconds,
            "rate_plan_start_utc": to_iso_utc(campaign_start),
            "common_segment_seconds": {
                "steady": float(steady_seconds),
                "burst": float(burst_seconds),
                "recovery": float(recovery_seconds),
            },
            "presteady_seconds": presteady_seconds,
            "presteady_eps": float(args.presteady_eps),
            "steady_seconds": steady_seconds,
            "burst_seconds": burst_seconds,
            "recovery_seconds": recovery_seconds,
            "duration_seconds": duration_seconds,
            "steady_eps": float(args.steady_eps),
            "burst_eps": float(args.burst_eps),
            "lane_count": lane_count,
            "stream_speedup": float(args.stream_speedup),
            "rate_plan_per_lane": rate_plan,
            "accepted_cost_posture": {
                "wsp_checkpoint_backend": str(args.wsp_checkpoint_backend),
                "wsp_checkpoint_root": str(args.wsp_checkpoint_root),
                "wsp_checkpoint_flush_every": str(args.wsp_checkpoint_flush_every),
            },
        },
        "windows": {
            "steady": steady_summary,
            "burst": burst_summary,
            "recovery": recovery_summary,
        },
        "recovery_analysis": {
            "bin_seconds": recovery_bin_seconds,
            "bins": recovery_bins,
            "sustained_green_start_utc": sustained_green_start_utc,
            "recovery_seconds_to_sustained_green": recovery_seconds_to_sustained_green,
            "recovery_bound_seconds": float(args.recovery_bound_seconds),
        },
        "supporting": {
            "dispatch_summary_path": str(dispatch_summary_path),
            "dispatch_manifest_path": str(dispatch_manifest_path),
            "dispatch_verdict": dispatch_summary.get("verdict"),
            "dispatch_open_blockers": dispatch_summary.get("open_blockers"),
            "ingress_surface": ingress_surface,
            "lambda_function_name": str(args.lambda_function_name).strip(),
            "lambda_errors_sum": lambda_errors_sum,
            "lambda_throttles_sum": lambda_throttles_sum,
            "dlq_url": str(args.dlq_url).strip(),
            "dlq_before": dlq_before,
            "dlq_after": dlq_after,
            "dlq_delta_total": dlq_delta_total,
        },
    }

    dump_json(execution_root / f"{str(args.artifact_prefix).strip()}_envelope_summary.json", envelope_summary)
    dump_json(
        execution_root / f"{str(args.artifact_prefix).strip()}_envelope_windows.json",
        {
            "generated_at_utc": to_iso_utc(now_utc()),
            "execution_id": execution_id,
            "windows": {
                "steady": steady_stats,
                "burst": burst_stats,
                "recovery": recovery_stats,
            },
            "recovery_bins": recovery_bins,
        },
    )
    print(json.dumps(envelope_summary, indent=2))


if __name__ == "__main__":
    main()
