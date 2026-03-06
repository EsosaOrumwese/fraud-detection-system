#!/usr/bin/env python3
"""Dispatch in-cloud PR3-S1 steady speedup lanes on ECS Fargate."""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def to_iso_utc(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return now_utc()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def build_loader_command() -> str:
    script = """import json
import math
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from random import random

target_rps = max(1.0, float(os.environ.get("TARGET_RPS", "100")))
duration_seconds = max(1, int(float(os.environ.get("DURATION_SECONDS", "300"))))
max_workers = max(1, int(float(os.environ.get("MAX_WORKERS", "64"))))
timeout_seconds = max(0.5, float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "5")))
max_attempts = max(1, int(float(os.environ.get("RETRY_MAX_ATTEMPTS", "3"))))
backoff_ms = max(0.0, float(os.environ.get("RETRY_BACKOFF_MS", "200")))
heartbeat_seconds = max(5.0, float(os.environ.get("HEARTBEAT_SECONDS", "15")))
ig_url = os.environ["IG_URL"]
api_key = os.environ["IG_API_KEY"]
platform_run_id = os.environ["PLATFORM_RUN_ID"]
scenario_run_id = os.environ["SCENARIO_RUN_ID"]
phase_id = os.environ.get("PHASE_ID", "PR3-S1")
lane_id = os.environ.get("LANE_ID", "lane-00")
trace_seed = f"{lane_id}:{int(time.time())}"
target_events = max(1, int(math.ceil(target_rps * duration_seconds)))
worker_count = min(max_workers, target_events)

headers = {
    "Content-Type": "application/json",
    "X-IG-Api-Key": api_key,
}
dispatch_started = time.time()
admitted = 0
non_202 = 0
failed = 0
status_counts = {}
failure_samples = []
completed_events = 0
last_heartbeat_at = dispatch_started

def record_status(code: int) -> None:
    key = str(code)
    status_counts[key] = int(status_counts.get(key, 0)) + 1

def emit_heartbeat(force: bool = False) -> None:
    global last_heartbeat_at
    now = time.time()
    if not force and (now - last_heartbeat_at) < heartbeat_seconds:
        return
    elapsed = max(0.001, now - dispatch_started)
    payload = {
        "heartbeat": {
            "lane_id": lane_id,
            "elapsed_seconds": elapsed,
            "completed_events": completed_events,
            "admitted_events": admitted,
            "non_202_events": non_202,
            "observed_admitted_rps": admitted / elapsed,
            "observed_attempted_rps": completed_events / elapsed,
            "status_counts": status_counts,
        }
    }
    print(json.dumps(payload, ensure_ascii=True), flush=True)
    last_heartbeat_at = now

def send_once(idx: int):
    event_id = f"pr3_s1_speedup:{lane_id}:{idx}:{trace_seed}"
    payload = {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "phase_id": phase_id,
        "event_class": "pr3_s1_speedup",
        "event_id": event_id,
        "runtime_lane": lane_id,
        "trace_id": event_id,
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(ig_url, data=body, method="POST", headers=headers)
    reason = ""
    status = 0
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                status = int(resp.status)
            if status == 202:
                return status, reason
            reason = f"status_{status}"
            retryable = status == 429 or status >= 500
            if not retryable or attempt >= max_attempts:
                return status, reason
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            reason = f"http_{status}"
            retryable = status == 429 or status >= 500
            if not retryable or attempt >= max_attempts:
                return status, reason
        except Exception as exc:
            status = 599
            reason = f"{type(exc).__name__}"
            if attempt >= max_attempts:
                return status, reason
        base = (backoff_ms / 1000.0) * (2 ** (attempt - 1))
        time.sleep(base + min(0.05, random() * 0.05))
    return status, reason

def maybe_pace(idx: int) -> None:
    target_epoch = dispatch_started + (idx / target_rps)
    now = time.time()
    if target_epoch > now:
        time.sleep(min(0.01, target_epoch - now))

next_idx = 0
in_flight = set()
with ThreadPoolExecutor(max_workers=worker_count) as pool:
    while next_idx < target_events and len(in_flight) < worker_count:
        maybe_pace(next_idx)
        in_flight.add(pool.submit(send_once, next_idx))
        next_idx += 1
    while in_flight:
        done, pending = wait(in_flight, return_when=FIRST_COMPLETED)
        in_flight = pending
        for fut in done:
            status, reason = fut.result()
            completed_events += 1
            record_status(status)
            if status == 202:
                admitted += 1
            else:
                non_202 += 1
                failed += 1
                if len(failure_samples) < 12:
                    failure_samples.append(reason or f"status_{status}")
        emit_heartbeat(force=False)
        while next_idx < target_events and len(in_flight) < worker_count:
            maybe_pace(next_idx)
            in_flight.add(pool.submit(send_once, next_idx))
            next_idx += 1

elapsed = max(0.001, time.time() - dispatch_started)
emit_heartbeat(force=True)
summary = {
    "lane_id": lane_id,
    "target_rps": target_rps,
    "duration_seconds": duration_seconds,
    "target_events": target_events,
    "attempted_events": target_events,
    "admitted_events": admitted,
    "non_202_events": non_202,
    "failed_events": failed,
    "status_counts": status_counts,
    "failure_samples": failure_samples,
    "observed_admitted_rps": admitted / elapsed,
    "elapsed_seconds": elapsed,
    "platform_run_id": platform_run_id,
    "scenario_run_id": scenario_run_id,
    "phase_id": phase_id,
}
print(json.dumps({"summary": summary}, ensure_ascii=True), flush=True)
if admitted <= 0:
    raise SystemExit(2)
"""
    # Keep command shell-safe and deterministic.
    return f"python - <<'PY'\n{script}\nPY"


def parse_lane_summary(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in reversed(events):
        text = str(row.get("message", "")).strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("summary"), dict):
            return payload["summary"]
    return None


def parse_lane_latest_heartbeat(events: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    for row in reversed(events):
        text = str(row.get("message", "")).strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("heartbeat"), dict):
            ts_ms = row.get("timestamp")
            hb_ts = None
            if isinstance(ts_ms, (int, float)):
                hb_ts = datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            return payload["heartbeat"], hb_ts
    return None, None


def stop_running_tasks(
    ecs: Any,
    cluster: str,
    task_arns: list[str],
    reason: str,
    blockers: list[str],
) -> None:
    for arn in task_arns:
        if not arn:
            continue
        try:
            ecs.stop_task(cluster=cluster, task=arn, reason=reason)
        except (BotoCoreError, ClientError) as exc:
            blockers.append(f"PR3.S1.SPD.B11_STOP_TASK_FAILED:{arn.rsplit('/', 1)[-1]}:{type(exc).__name__}")


def refresh_task_status(
    ecs: Any,
    cluster: str,
    lane_index: dict[str, dict[str, Any]],
    task_arns: list[str],
    blockers: list[str],
) -> None:
    for offset in range(0, len(task_arns), 100):
        batch = task_arns[offset : offset + 100]
        if not batch:
            continue
        try:
            desc = ecs.describe_tasks(cluster=cluster, tasks=batch)
        except (BotoCoreError, ClientError) as exc:
            blockers.append(f"PR3.S1.SPD.B02_DESCRIBE_TASKS_FAILED:{type(exc).__name__}")
            continue
        for task in desc.get("tasks", []):
            task_arn = str(task.get("taskArn", "")).strip()
            lane = lane_index.get(task_arn)
            if lane is None:
                continue
            lane["last_status"] = str(task.get("lastStatus", "")).strip()
            lane["desired_status"] = str(task.get("desiredStatus", "")).strip()
            lane["started_at_utc"] = to_iso_utc(task.get("startedAt"))
            lane["stopped_at_utc"] = to_iso_utc(task.get("stoppedAt"))
            lane["stopped_reason"] = str(task.get("stoppedReason", "")).strip()
            containers = task.get("containers", [])
            if containers:
                c0 = containers[0]
                lane["container_last_status"] = str(c0.get("lastStatus", "")).strip()
                lane["container_exit_code"] = c0.get("exitCode")
                lane["container_reason"] = str(c0.get("reason", "")).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Dispatch managed PR3-S1 steady speedup lanes.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--cluster", default="fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--task-definition", default="fraud-platform-dev-full-wsp-ephemeral:17")
    ap.add_argument("--subnets", default="subnet-005205ea65a9027fc,subnet-01fd5f1585bfcca47")
    ap.add_argument("--security-groups", default="sg-01bfefedcd75ec4b2")
    ap.add_argument("--assign-public-ip", default="ENABLED")
    ap.add_argument("--platform-run-id", default="platform_20260223T184232Z")
    ap.add_argument("--scenario-run-id", default="scenario_38753050f3b70c666e16f7552016b330")
    ap.add_argument("--ig-url", default="https://ehwznd2uw7.execute-api.eu-west-2.amazonaws.com/v1/ingest/push")
    ap.add_argument("--ig-api-key-param", default="/fraud-platform/dev_full/ig/api_key")
    ap.add_argument("--phase-id", default="PR3-S1")
    ap.add_argument("--lane-count", type=int, default=8)
    ap.add_argument("--target-rps-per-lane", type=float, default=450.0)
    ap.add_argument("--duration-seconds", type=int, default=900)
    ap.add_argument("--max-workers-per-lane", type=int, default=96)
    ap.add_argument("--request-timeout-seconds", type=float, default=5.0)
    ap.add_argument("--retry-max-attempts", type=int, default=3)
    ap.add_argument("--retry-backoff-ms", type=float, default=150.0)
    ap.add_argument("--heartbeat-seconds", type=float, default=15.0)
    ap.add_argument("--dispatch-stagger-seconds", type=float, default=1.0)
    ap.add_argument("--task-poll-seconds", type=int, default=20)
    ap.add_argument("--task-timeout-seconds", type=int, default=5400)
    ap.add_argument("--early-cutoff-grace-seconds", type=int, default=180)
    ap.add_argument("--early-cutoff-min-throughput-fraction", type=float, default=0.70)
    ap.add_argument("--early-cutoff-min-lane-coverage-fraction", type=float, default=0.50)
    ap.add_argument("--disable-early-cutoff", action="store_true")
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    started_at = now_utc()
    t0 = time.perf_counter()

    root = Path(args.run_control_root)
    pr3_root = root / args.pr3_execution_id
    if not pr3_root.exists():
        raise RuntimeError(f"PR3 execution root missing: {pr3_root}")

    s0 = load_json(pr3_root / "pr3_s0_execution_receipt.json")
    if str(s0.get("verdict", "")) != "PR3_S0_READY" or int(s0.get("open_blockers", 1)) != 0:
        raise RuntimeError("Strict upstream lock failed: PR3-S0 is not READY.")

    subnets = parse_csv(args.subnets)
    sec_groups = parse_csv(args.security_groups)
    if len(subnets) < 2:
        raise RuntimeError("At least two subnets are required for managed speedup dispatch.")
    if len(sec_groups) < 1:
        raise RuntimeError("At least one security group is required for managed speedup dispatch.")

    ssm = boto3.client("ssm", region_name=args.region)
    ecs = boto3.client("ecs", region_name=args.region)
    logs = boto3.client("logs", region_name=args.region)

    param = ssm.get_parameter(Name=args.ig_api_key_param, WithDecryption=True)
    ig_api_key = str(param.get("Parameter", {}).get("Value", "")).strip()
    if not ig_api_key:
        raise RuntimeError("Unable to resolve IG API key from SSM.")

    launched_lanes: list[dict[str, Any]] = []
    blockers: list[str] = []
    loader_command = build_loader_command()
    launch_started_dt = datetime.now(timezone.utc)
    for idx in range(max(1, args.lane_count)):
        lane_id = f"pr3_s1_speedup_lane_{idx:02d}"
        env_rows = [
            {"name": "IG_API_KEY", "value": ig_api_key},
            {"name": "IG_URL", "value": args.ig_url},
            {"name": "PLATFORM_RUN_ID", "value": args.platform_run_id},
            {"name": "SCENARIO_RUN_ID", "value": args.scenario_run_id},
            {"name": "PHASE_ID", "value": args.phase_id},
            {"name": "LANE_ID", "value": lane_id},
            {"name": "TARGET_RPS", "value": str(args.target_rps_per_lane)},
            {"name": "DURATION_SECONDS", "value": str(args.duration_seconds)},
            {"name": "MAX_WORKERS", "value": str(args.max_workers_per_lane)},
            {"name": "REQUEST_TIMEOUT_SECONDS", "value": str(args.request_timeout_seconds)},
            {"name": "RETRY_MAX_ATTEMPTS", "value": str(args.retry_max_attempts)},
            {"name": "RETRY_BACKOFF_MS", "value": str(args.retry_backoff_ms)},
            {"name": "HEARTBEAT_SECONDS", "value": str(args.heartbeat_seconds)},
        ]
        try:
            run_resp = ecs.run_task(
                cluster=args.cluster,
                taskDefinition=args.task_definition,
                launchType="FARGATE",
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": subnets,
                        "securityGroups": sec_groups,
                        "assignPublicIp": str(args.assign_public_ip).strip().upper(),
                    }
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": "wsp",
                            "command": ["/bin/sh", "-lc", loader_command],
                            "environment": env_rows,
                        }
                    ]
                },
            )
        except (BotoCoreError, ClientError) as exc:
            blockers.append(f"PR3.S1.SPD.B01_RUN_TASK_FAILED:{lane_id}:{type(exc).__name__}")
            continue
        failures = run_resp.get("failures", [])
        if failures:
            reason = str(failures[0].get("reason", "unknown"))
            blockers.append(f"PR3.S1.SPD.B01_RUN_TASK_FAILED:{lane_id}:{reason}")
            continue
        tasks = run_resp.get("tasks", [])
        if not tasks:
            blockers.append(f"PR3.S1.SPD.B01_RUN_TASK_FAILED:{lane_id}:empty_task_list")
            continue
        task_arn = str(tasks[0].get("taskArn", "")).strip()
        launched_lanes.append(
            {
                "lane_id": lane_id,
                "task_arn": task_arn,
                "dispatched_at_utc": now_utc(),
                "target_rps": args.target_rps_per_lane,
                "duration_seconds": args.duration_seconds,
            }
        )
        if args.dispatch_stagger_seconds > 0:
            time.sleep(args.dispatch_stagger_seconds)

    # Poll tasks to completion with fail-fast throughput cutoffs.
    task_deadline = time.time() + max(60, int(args.task_timeout_seconds))
    lane_index = {row["task_arn"]: row for row in launched_lanes}
    lane_count_launched = len(launched_lanes)
    expected_total_rps = float(args.target_rps_per_lane) * max(1, lane_count_launched)
    throughput_floor_rps = expected_total_rps * max(0.0, float(args.early_cutoff_min_throughput_fraction))
    min_lane_coverage = max(0.0, min(1.0, float(args.early_cutoff_min_lane_coverage_fraction)))
    poll_seconds = max(5, int(args.task_poll_seconds))
    early_cutoff_enabled = not bool(args.disable_early_cutoff)
    early_cutoff_grace = max(30, int(args.early_cutoff_grace_seconds))
    launch_epoch = time.time()
    early_cutoff_triggered = False
    early_cutoff_reason = ""
    log_group = "/ecs/fraud-platform-dev-full-wsp-ephemeral"
    for lane in launched_lanes:
        task_arn = str(lane.get("task_arn", "")).strip()
        task_id = task_arn.rsplit("/", 1)[-1] if task_arn else ""
        lane["log_stream_name"] = f"ecs/wsp/{task_id}" if task_id else ""
        lane["log_next_token"] = None
        lane["log_event_count"] = 0

    while time.time() < task_deadline:
        pending = [arn for arn, lane in lane_index.items() if str(lane.get("last_status", "")).upper() != "STOPPED"]
        if not pending:
            break
        refresh_task_status(
            ecs=ecs,
            cluster=args.cluster,
            lane_index=lane_index,
            task_arns=pending,
            blockers=blockers,
        )

        # Refresh incremental lane telemetry from CloudWatch.
        for lane in launched_lanes:
            stream_name = str(lane.get("log_stream_name", "")).strip()
            if not stream_name:
                continue
            req: dict[str, Any] = {"logGroupName": log_group, "logStreamName": stream_name}
            next_token = lane.get("log_next_token")
            if isinstance(next_token, str) and next_token.strip():
                req["nextToken"] = next_token
            else:
                req["startFromHead"] = True
            try:
                resp = logs.get_log_events(**req)
            except (BotoCoreError, ClientError):
                continue
            lane["log_next_token"] = resp.get("nextForwardToken")
            events = resp.get("events", [])
            lane["log_event_count"] = int(lane.get("log_event_count", 0) or 0) + len(events)
            if not events:
                continue
            heartbeat, heartbeat_ts = parse_lane_latest_heartbeat(events)
            if heartbeat is not None:
                lane["lane_heartbeat"] = heartbeat
                lane["lane_heartbeat_at_utc"] = heartbeat_ts or now_utc()
            summary = parse_lane_summary(events)
            if summary is not None:
                lane["lane_summary"] = summary

        if early_cutoff_enabled and pending:
            elapsed = time.time() - launch_epoch
            if elapsed >= early_cutoff_grace:
                reporting_lanes = 0
                observed_rps = 0.0
                now_dt = datetime.now(timezone.utc)
                freshness_sec = max(60, poll_seconds * 3)
                for lane in launched_lanes:
                    hb = lane.get("lane_heartbeat")
                    if not isinstance(hb, dict):
                        continue
                    hb_ts = str(lane.get("lane_heartbeat_at_utc", "")).strip()
                    if hb_ts.endswith("Z"):
                        hb_ts = hb_ts.replace("Z", "+00:00")
                    try:
                        hb_dt = datetime.fromisoformat(hb_ts)
                    except ValueError:
                        hb_dt = now_dt
                    age = (now_dt - hb_dt).total_seconds()
                    if age > freshness_sec:
                        continue
                    reporting_lanes += 1
                    observed_rps += float(hb.get("observed_admitted_rps", 0.0) or 0.0)

                coverage = reporting_lanes / max(1, lane_count_launched)
                if coverage >= min_lane_coverage and observed_rps < throughput_floor_rps:
                    early_cutoff_triggered = True
                    early_cutoff_reason = (
                        f"PR3.S1.SPD.B12_EARLY_THROUGHPUT_SHORTFALL:"
                        f"observed={observed_rps:.3f}:floor={throughput_floor_rps:.3f}:coverage={coverage:.3f}"
                    )
                    blockers.append(early_cutoff_reason)
                elif elapsed >= (early_cutoff_grace + freshness_sec) and coverage < min_lane_coverage:
                    early_cutoff_triggered = True
                    early_cutoff_reason = (
                        f"PR3.S1.SPD.B13_EARLY_TELEMETRY_COVERAGE_LOW:"
                        f"coverage={coverage:.3f}:required={min_lane_coverage:.3f}"
                    )
                    blockers.append(early_cutoff_reason)

                if early_cutoff_triggered:
                    stop_running_tasks(
                        ecs=ecs,
                        cluster=args.cluster,
                        task_arns=pending,
                        reason="PR3-S1 early cutoff: throughput floor not met",
                        blockers=blockers,
                    )
                    break

        if early_cutoff_triggered:
            break
        time.sleep(poll_seconds)

    if early_cutoff_triggered:
        settle_deadline = time.time() + 120
        while time.time() < settle_deadline:
            pending = [arn for arn, lane in lane_index.items() if str(lane.get("last_status", "")).upper() != "STOPPED"]
            if not pending:
                break
            refresh_task_status(
                ecs=ecs,
                cluster=args.cluster,
                lane_index=lane_index,
                task_arns=pending,
                blockers=blockers,
            )
            time.sleep(5)

    timed_out = [lane for lane in launched_lanes if str(lane.get("last_status", "")).upper() != "STOPPED"]
    if timed_out:
        if early_cutoff_triggered:
            blockers.append(f"PR3.S1.SPD.B14_EARLY_STOP_NOT_CONFIRMED:{len(timed_out)}")
        else:
            blockers.append(f"PR3.S1.SPD.B03_TASK_TIMEOUT:{len(timed_out)}")

    # Fetch lane summaries from CloudWatch task logs.
    for lane in launched_lanes:
        task_arn = str(lane.get("task_arn", ""))
        task_id = task_arn.rsplit("/", 1)[-1] if task_arn else ""
        if not task_id:
            continue
        stream_name = f"ecs/wsp/{task_id}"
        lane["log_stream_name"] = stream_name
        try:
            resp = logs.get_log_events(
                logGroupName="/ecs/fraud-platform-dev-full-wsp-ephemeral",
                logStreamName=stream_name,
                startFromHead=True,
            )
            events = resp.get("events", [])
            lane["log_event_count"] = len(events)
            parsed = parse_lane_summary(events)
            if parsed is not None:
                lane["lane_summary"] = parsed
            else:
                lane["lane_summary"] = {}
                if str(lane.get("container_last_status", "")).upper() == "STOPPED" and not early_cutoff_triggered:
                    blockers.append(f"PR3.S1.SPD.B04_LANE_SUMMARY_MISSING:{lane.get('lane_id')}")
        except (BotoCoreError, ClientError):
            lane["lane_summary"] = {}
            blockers.append(f"PR3.S1.SPD.B05_LOG_READ_FAILED:{lane.get('lane_id')}")

    # Aggregate dispatch metrics.
    admitted_total = 0
    attempted_total = 0
    observed_rps_sum = 0.0
    non_202_total = 0
    lane_failures = 0
    for lane in launched_lanes:
        summary = lane.get("lane_summary") if isinstance(lane.get("lane_summary"), dict) else {}
        if summary:
            admitted_total += int(summary.get("admitted_events", 0) or 0)
            attempted_total += int(summary.get("attempted_events", 0) or 0)
            non_202_total += int(summary.get("non_202_events", 0) or 0)
            observed_rps_sum += float(summary.get("observed_admitted_rps", 0.0) or 0.0)
        else:
            hb = lane.get("lane_heartbeat") if isinstance(lane.get("lane_heartbeat"), dict) else {}
            admitted_total += int(hb.get("admitted_events", 0) or 0)
            attempted_total += int(hb.get("completed_events", 0) or 0)
            non_202_total += int(hb.get("non_202_events", 0) or 0)
            observed_rps_sum += float(hb.get("observed_admitted_rps", 0.0) or 0.0)
        exit_code = lane.get("container_exit_code")
        if exit_code not in (0, None):
            stop_reason = str(lane.get("stopped_reason", "")).lower()
            forced_early_cutoff = early_cutoff_triggered and int(exit_code) == 137 and "early cutoff" in stop_reason
            if forced_early_cutoff:
                lane["exit_classification"] = "EARLY_CUTOFF_FORCED_STOP"
            else:
                lane_failures += 1
                blockers.append(f"PR3.S1.SPD.B06_LANE_EXIT_NONZERO:{lane.get('lane_id')}:{exit_code}")

    started_candidates = [lane.get("started_at_utc") for lane in launched_lanes if lane.get("started_at_utc")]
    stopped_candidates = [lane.get("stopped_at_utc") for lane in launched_lanes if lane.get("stopped_at_utc")]
    perf_window_start = min(started_candidates) if started_candidates else to_iso_utc(launch_started_dt)
    perf_window_end = max(stopped_candidates) if stopped_candidates else now_utc()

    manifest = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "dispatch_mode": "ECS_FARGATE_MANAGED_SPEEDUP",
        "cluster": args.cluster,
        "task_definition": args.task_definition,
        "network": {
            "subnets": subnets,
            "security_groups": sec_groups,
            "assign_public_ip": str(args.assign_public_ip).strip().upper(),
        },
        "campaign": {
            "lane_count_requested": int(args.lane_count),
            "lane_count_launched": len(launched_lanes),
            "target_rps_per_lane": float(args.target_rps_per_lane),
            "duration_seconds": int(args.duration_seconds),
            "max_workers_per_lane": int(args.max_workers_per_lane),
            "request_timeout_seconds": float(args.request_timeout_seconds),
            "retry_max_attempts": int(args.retry_max_attempts),
            "retry_backoff_ms": float(args.retry_backoff_ms),
            "heartbeat_seconds": float(args.heartbeat_seconds),
            "early_cutoff_enabled": early_cutoff_enabled,
            "early_cutoff_grace_seconds": early_cutoff_grace,
            "early_cutoff_min_throughput_fraction": float(args.early_cutoff_min_throughput_fraction),
            "early_cutoff_min_lane_coverage_fraction": float(args.early_cutoff_min_lane_coverage_fraction),
            "expected_total_rps": expected_total_rps,
            "throughput_floor_rps": throughput_floor_rps,
        },
        "identity": {
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "phase_id": args.phase_id,
        },
        "performance_window": {
            "start_utc": perf_window_start,
            "end_utc": perf_window_end,
        },
        "lanes": launched_lanes,
    }

    summary = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "verdict": "MANAGED_SPEEDUP_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": sorted(set(blockers)),
        "dispatch_mode": "ECS_FARGATE_MANAGED_SPEEDUP",
        "lane_count_launched": len(launched_lanes),
        "lane_failures": lane_failures,
        "attempted_events_total": attempted_total,
        "admitted_events_total": admitted_total,
        "non_202_events_total": non_202_total,
        "observed_admitted_rps_sum": observed_rps_sum,
        "expected_total_rps": expected_total_rps,
        "throughput_floor_rps": throughput_floor_rps,
        "early_cutoff_triggered": early_cutoff_triggered,
        "early_cutoff_reason": early_cutoff_reason,
        "performance_window": manifest["performance_window"],
        "elapsed_minutes": round((time.perf_counter() - t0) / 60.0, 3),
    }

    dump_json(pr3_root / "g3a_s1_speedup_dispatch_manifest.json", manifest)
    dump_json(pr3_root / "g3a_s1_speedup_dispatch_summary.json", summary)

    print(
        json.dumps(
            {
                "execution_id": args.pr3_execution_id,
                "verdict": summary["verdict"],
                "open_blockers": summary["open_blockers"],
                "lane_count_launched": summary["lane_count_launched"],
                "observed_admitted_rps_sum": summary["observed_admitted_rps_sum"],
                "performance_window": summary["performance_window"],
                "started_at_utc": started_at,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
