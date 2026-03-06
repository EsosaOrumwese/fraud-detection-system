#!/usr/bin/env python3
"""Canonical PR3-S1 remote WSP replay dispatcher.

Runs the real WSP emitter on remote ECS/Fargate, bounded by the steady-window
duration and paced by calibrated stream_speedup. This replaces the synthetic
HTTP pressure harness as the canonical S1 injection path.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def task_id_from_arn(task_arn: str) -> str:
    return str(task_arn).rsplit("/", 1)[-1]


def to_iso_utc(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return now_utc()


def build_wsp_command() -> list[str]:
    script = dedent(
        """
        python - <<'PY'
        import os
        from pathlib import Path
        import yaml

        base = Path(os.environ["WSP_PROFILE_PATH"])
        profile = yaml.safe_load(base.read_text(encoding="utf-8")) or {}
        profile.setdefault("policy", {})
        profile["policy"]["stream_speedup"] = float(os.environ["WSP_STREAM_SPEEDUP"])
        profile["policy"]["require_gate_pass"] = True
        profile["profile_id"] = "dev_full_pr3_s1_remote_wsp"
        out = Path("/tmp/pr3_s1_wsp_profile.yaml")
        out.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
        print(out)
        PY
        exec python -m fraud_detection.world_streamer_producer.cli \
          --profile /tmp/pr3_s1_wsp_profile.yaml \
          --engine-run-root "$ORACLE_ENGINE_RUN_ROOT" \
          --scenario-id "$ORACLE_SCENARIO_ID"
        """
    ).strip()
    return ["/bin/sh", "-lc", script]


def refresh_task_status(ecs: Any, cluster: str, task_arn: str) -> dict[str, Any]:
    payload = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
    tasks = payload.get("tasks", [])
    if not tasks:
        return {}
    task = tasks[0]
    container = (task.get("containers") or [{}])[0]
    return {
        "last_status": str(task.get("lastStatus", "")).upper(),
        "desired_status": str(task.get("desiredStatus", "")).upper(),
        "stop_code": str(task.get("stopCode", "")).strip(),
        "stopped_reason": str(task.get("stoppedReason", "")).strip(),
        "created_at_utc": to_iso_utc(task.get("createdAt")),
        "started_at_utc": to_iso_utc(task.get("startedAt")),
        "stopped_at_utc": to_iso_utc(task.get("stoppedAt")),
        "container_last_status": str(container.get("lastStatus", "")).upper(),
        "container_exit_code": container.get("exitCode"),
        "container_reason": str(container.get("reason", "")).strip(),
        "container_runtime_id": str(container.get("runtimeId", "")).strip(),
    }


def get_apigw_totals(
    cw: Any,
    *,
    api_id: str,
    stage: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> dict[str, float]:
    dims = [{"Name": "ApiId", "Value": api_id}, {"Name": "Stage", "Value": stage}]

    def metric_sum(metric_name: str) -> float:
        result = cw.get_metric_statistics(
            Namespace="AWS/ApiGateway",
            MetricName=metric_name,
            Dimensions=dims,
            StartTime=start_time,
            EndTime=end_time,
            Period=period_seconds,
            Statistics=["Sum"],
        )
        return float(sum(float(row.get("Sum", 0.0) or 0.0) for row in result.get("Datapoints", [])))

    return {
        "count_sum": metric_sum("Count"),
        "4xx_sum": metric_sum("4xx"),
        "5xx_sum": metric_sum("5xx"),
    }


def get_log_events(logs: Any, *, log_group: str, stream_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    next_token = None
    while True:
        req: dict[str, Any] = {"logGroupName": log_group, "logStreamName": stream_name, "startFromHead": True}
        if next_token:
            req["nextToken"] = next_token
        resp = logs.get_log_events(**req)
        batch = list(resp.get("events", []))
        rows.extend(batch)
        token = resp.get("nextForwardToken")
        if not batch or token == next_token:
            break
        next_token = token
    return rows


def resolve_log_stream_name(
    logs: Any,
    *,
    log_group: str,
    window_start: datetime,
    window_end: datetime | None = None,
    prefix: str = "ecs/wsp/",
) -> str:
    start_ms = int(window_start.timestamp() * 1000) - 60000
    end_ms = int((window_end or datetime.now(timezone.utc)).timestamp() * 1000) + 300000
    paginator = logs.get_paginator("describe_log_streams")
    candidates: list[dict[str, Any]] = []
    for page in paginator.paginate(logGroupName=log_group, logStreamNamePrefix=prefix):
        for row in page.get("logStreams", []):
            creation = int(row.get("creationTime", 0) or 0)
            last_event = int(row.get("lastEventTimestamp", 0) or 0)
            if creation > end_ms:
                continue
            if last_event and last_event < start_ms:
                continue
            candidates.append(row)
    if not candidates:
        return ""
    candidates.sort(key=lambda row: (int(row.get("lastEventTimestamp", 0) or 0), int(row.get("creationTime", 0) or 0)))
    return str(candidates[-1].get("logStreamName", "")).strip()


def parse_result_from_logs(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in reversed(events):
        message = str(row.get("message", "")).strip()
        if not message.startswith("{"):
            continue
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "status" in payload and "engine_run_root" in payload:
            return payload
    return None


def build_aurora_dsn(*, endpoint: str, username: str, password: str, db_name: str, port: int) -> str:
    return (
        f"postgresql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{endpoint}:{int(port)}/{db_name}?sslmode=require"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Dispatch canonical remote WSP replay for PR3-S1.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--profile-path", default="config/platform/profiles/dev_full.yaml")
    ap.add_argument("--cluster", default="fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--task-definition", default="fraud-platform-dev-full-wsp-ephemeral:17")
    ap.add_argument("--subnet-ids", default="subnet-0a7a35898d0ca31a8,subnet-0e9647425f02e2f27")
    ap.add_argument("--security-group-ids", default="sg-01bfefedcd75ec4b2")
    ap.add_argument("--assign-public-ip", default="DISABLED")
    ap.add_argument("--api-id", default="ehwznd2uw7")
    ap.add_argument("--api-stage", default="v1")
    ap.add_argument("--ssm-ig-api-key-path", default="/fraud-platform/dev_full/ig/api_key")
    ap.add_argument("--ssm-aurora-endpoint-path", default="/fraud-platform/dev_full/aurora/endpoint")
    ap.add_argument("--ssm-aurora-username-path", default="/fraud-platform/dev_full/aurora/username")
    ap.add_argument("--ssm-aurora-password-path", default="/fraud-platform/dev_full/aurora/password")
    ap.add_argument("--platform-run-id", default="platform_20260223T184232Z")
    ap.add_argument("--scenario-run-id", default="scenario_38753050f3b70c666e16f7552016b330")
    ap.add_argument(
        "--oracle-engine-run-root",
        default="s3://fraud-platform-dev-full-object-store/oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1",
    )
    ap.add_argument("--oracle-root", default="s3://fraud-platform-dev-full-object-store")
    ap.add_argument("--scenario-id", default="baseline_v1")
    ap.add_argument("--object-store-root", default="s3://fraud-platform-dev-full-object-store")
    ap.add_argument("--ig-ingest-url", default="https://ehwznd2uw7.execute-api.eu-west-2.amazonaws.com/v1/ingest/push")
    ap.add_argument("--traffic-output-ids", default="s3_event_stream_with_fraud_6B")
    ap.add_argument(
        "--context-output-ids",
        default="arrival_events_5B,s1_arrival_entities_6B,s3_flow_anchor_with_fraud_6B",
    )
    ap.add_argument("--stream-speedup", type=float, default=19.7)
    ap.add_argument("--wsp-checkpoint-dsn", default="")
    ap.add_argument("--aurora-db-name", default="fraud_platform")
    ap.add_argument("--aurora-port", type=int, default=5432)
    ap.add_argument("--duration-seconds", type=int, default=1800)
    ap.add_argument("--early-cutoff-seconds", type=int, default=300)
    ap.add_argument("--early-cutoff-floor-ratio", type=float, default=0.70)
    ap.add_argument("--expected-steady-eps", type=float, default=3000.0)
    ap.add_argument("--output-concurrency", type=int, default=4)
    ap.add_argument("--http-pool-maxsize", type=int, default=256)
    ap.add_argument("--log-group", default="/ecs/fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root)
    pr3_root = root / args.pr3_execution_id
    if not pr3_root.exists():
        raise RuntimeError(f"PR3 execution root missing: {pr3_root}")
    s0 = load_json(pr3_root / "pr3_s0_execution_receipt.json")
    if str(s0.get("verdict", "")) != "PR3_S0_READY" or int(s0.get("open_blockers", 1)) != 0:
        raise RuntimeError("Strict upstream lock failed: PR3-S0 is not READY.")

    ecs = boto3.client("ecs", region_name=args.region)
    ssm = boto3.client("ssm", region_name=args.region)
    logs = boto3.client("logs", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)

    ig_api_key = ssm.get_parameter(Name=args.ssm_ig_api_key_path, WithDecryption=True)["Parameter"]["Value"]
    wsp_checkpoint_dsn = str(args.wsp_checkpoint_dsn).strip()
    if not wsp_checkpoint_dsn:
        aurora_payload = ssm.get_parameters(
            Names=[
                args.ssm_aurora_endpoint_path,
                args.ssm_aurora_username_path,
                args.ssm_aurora_password_path,
            ],
            WithDecryption=True,
        )
        resolved = {
            str(item.get("Name", "")).strip(): str(item.get("Value", "")).strip()
            for item in aurora_payload.get("Parameters", [])
        }
        missing = [
            name
            for name in [
                args.ssm_aurora_endpoint_path,
                args.ssm_aurora_username_path,
                args.ssm_aurora_password_path,
            ]
            if not resolved.get(name)
        ]
        if missing:
            raise RuntimeError(
                "PR3.S1.WSP.B02_CHECKPOINT_DSN_UNRESOLVED:missing_ssm_paths=" + ",".join(missing)
            )
        wsp_checkpoint_dsn = build_aurora_dsn(
            endpoint=resolved[args.ssm_aurora_endpoint_path],
            username=resolved[args.ssm_aurora_username_path],
            password=resolved[args.ssm_aurora_password_path],
            db_name=args.aurora_db_name,
            port=args.aurora_port,
        )
    subnets = parse_csv(args.subnet_ids)
    security_groups = parse_csv(args.security_group_ids)
    blockers: list[str] = []
    submitted_at = datetime.now(timezone.utc)

    env_rows = [
        {"name": "AWS_REGION", "value": args.region},
        {"name": "WSP_PROFILE_PATH", "value": args.profile_path},
        {"name": "IG_API_KEY", "value": ig_api_key},
        {"name": "IG_INGEST_URL", "value": args.ig_ingest_url},
        {"name": "PLATFORM_RUN_ID", "value": args.platform_run_id},
        {"name": "SCENARIO_RUN_ID", "value": args.scenario_run_id},
        {"name": "ORACLE_ENGINE_RUN_ROOT", "value": args.oracle_engine_run_root},
        {"name": "ORACLE_ROOT", "value": args.oracle_root},
        {"name": "ORACLE_SCENARIO_ID", "value": args.scenario_id},
        {"name": "OBJECT_STORE_ROOT", "value": args.object_store_root},
        {"name": "WSP_TRAFFIC_OUTPUT_IDS", "value": args.traffic_output_ids},
        {"name": "WSP_CONTEXT_OUTPUT_IDS", "value": args.context_output_ids},
        {"name": "WSP_STREAM_SPEEDUP", "value": str(args.stream_speedup)},
        {"name": "WSP_CHECKPOINT_DSN", "value": wsp_checkpoint_dsn},
        {"name": "WSP_OUTPUT_CONCURRENCY", "value": str(max(1, args.output_concurrency))},
        {"name": "WSP_HTTP_POOL_MAXSIZE", "value": str(max(16, args.http_pool_maxsize))},
        {"name": "WSP_PROGRESS_EVERY", "value": "50000"},
        {"name": "WSP_PROGRESS_SECONDS", "value": "30"},
    ]
    command_list = build_wsp_command()

    try:
        run_resp = ecs.run_task(
            cluster=args.cluster,
            taskDefinition=args.task_definition,
            launchType="FARGATE",
            count=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnets,
                    "securityGroups": security_groups,
                    "assignPublicIp": str(args.assign_public_ip).strip().upper(),
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": "wsp",
                        "command": command_list,
                        "environment": env_rows,
                    }
                ]
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"PR3.S1.WSP.B01_RUN_TASK_FAILED:{type(exc).__name__}:{exc}") from exc

    failures = run_resp.get("failures", [])
    if failures:
        reason = failures[0].get("reason", "unknown")
        raise RuntimeError(f"PR3.S1.WSP.B01_RUN_TASK_FAILED:{reason}")
    task = (run_resp.get("tasks") or [{}])[0]
    task_arn = str(task.get("taskArn", "")).strip()
    if not task_arn:
        raise RuntimeError("PR3.S1.WSP.B01_RUN_TASK_FAILED:empty_task_arn")
    task_id = task_id_from_arn(task_arn)
    log_stream_name = ""

    manifest = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "dispatch_mode": "CANONICAL_REMOTE_WSP_REPLAY",
        "cluster": args.cluster,
        "task_definition": args.task_definition,
        "task_arn": task_arn,
        "log_group": args.log_group,
        "log_stream_name": log_stream_name,
        "network": {
            "subnets": subnets,
            "security_groups": security_groups,
            "assign_public_ip": str(args.assign_public_ip).strip().upper(),
        },
        "campaign": {
            "expected_steady_eps": args.expected_steady_eps,
            "duration_seconds": args.duration_seconds,
            "early_cutoff_seconds": args.early_cutoff_seconds,
            "early_cutoff_floor_ratio": args.early_cutoff_floor_ratio,
            "stream_speedup": args.stream_speedup,
            "output_concurrency": max(1, args.output_concurrency),
            "http_pool_maxsize": max(16, args.http_pool_maxsize),
            "traffic_output_ids": parse_csv(args.traffic_output_ids),
            "context_output_ids": parse_csv(args.context_output_ids),
        },
        "runtime_profile": {
            "profile_path": args.profile_path,
            "checkpoint_backend": "postgres",
            "checkpoint_dsn_mode": "explicit_or_ssm_aurora",
            "aurora_db_name": args.aurora_db_name,
        },
        "identity": {
            "platform_run_id": args.platform_run_id,
            "scenario_run_id": args.scenario_run_id,
            "scenario_id": args.scenario_id,
        },
        "oracle": {
            "oracle_root": args.oracle_root,
            "oracle_engine_run_root": args.oracle_engine_run_root,
        },
    }
    dump_json(pr3_root / "g3a_s1_wsp_runtime_manifest.json", manifest)

    expected_floor_eps = float(args.expected_steady_eps) * float(args.early_cutoff_floor_ratio)
    active_start = submitted_at
    running_status: dict[str, Any] = {}
    start_wait_deadline = time.time() + 900
    while time.time() < start_wait_deadline:
        running_status = refresh_task_status(ecs, args.cluster, task_arn)
        if running_status.get("last_status") == "RUNNING" and running_status.get("started_at_utc"):
            active_start = datetime.fromisoformat(
                str(running_status["started_at_utc"]).replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            break
        if running_status.get("last_status") == "STOPPED":
            blockers.append("PR3.S1.WSP.B03_TASK_STOPPED_BEFORE_RUNNING")
            break
        time.sleep(5)
    if not running_status:
        running_status = refresh_task_status(ecs, args.cluster, task_arn)
    if running_status.get("last_status") != "RUNNING" and "PR3.S1.WSP.B03_TASK_STOPPED_BEFORE_RUNNING" not in blockers:
        blockers.append("PR3.S1.WSP.B04_TASK_START_TIMEOUT")
    if not blockers:
        log_stream_name = resolve_log_stream_name(logs, log_group=args.log_group, window_start=active_start)
        manifest["log_stream_name"] = log_stream_name
        dump_json(pr3_root / "g3a_s1_wsp_runtime_manifest.json", manifest)

    hard_deadline = time.time() + max(120, args.duration_seconds + 600)
    window_end = time.time() + max(60, args.duration_seconds)
    early_cutoff_triggered = False
    telemetry_error = ""
    while time.time() < hard_deadline and not blockers:
        status = refresh_task_status(ecs, args.cluster, task_arn)
        elapsed = max(1.0, time.time() - active_start.timestamp())
        try:
            totals = get_apigw_totals(
                cw,
                api_id=args.api_id,
                stage=args.api_stage,
                start_time=active_start,
                end_time=datetime.now(timezone.utc),
            )
            observed_eps = totals["count_sum"] / elapsed
        except (BotoCoreError, ClientError) as exc:
            totals = {"count_sum": 0.0, "4xx_sum": 0.0, "5xx_sum": 0.0}
            observed_eps = 0.0
            telemetry_error = f"{type(exc).__name__}:{exc}"

        if elapsed >= max(60, args.early_cutoff_seconds) and observed_eps < expected_floor_eps:
            blockers.append(
                f"PR3.S1.WSP.B12_EARLY_THROUGHPUT_SHORTFALL:observed={observed_eps:.3f}:floor={expected_floor_eps:.3f}"
            )
            early_cutoff_triggered = True
            try:
                ecs.stop_task(
                    cluster=args.cluster,
                    task=task_arn,
                    reason="PR3-S1 early cutoff: canonical WSP replay below throughput floor",
                )
            except (BotoCoreError, ClientError) as exc:
                blockers.append(f"PR3.S1.WSP.B13_STOP_TASK_FAILED:{type(exc).__name__}")
            break

        if time.time() >= window_end:
            try:
                ecs.stop_task(
                    cluster=args.cluster,
                    task=task_arn,
                    reason="PR3-S1 steady window complete: canonical WSP replay bounded by certification window",
                )
            except (BotoCoreError, ClientError) as exc:
                blockers.append(f"PR3.S1.WSP.B14_WINDOW_STOP_FAILED:{type(exc).__name__}")
            break

        if status.get("last_status") == "STOPPED":
            break
        time.sleep(30)

    settle_deadline = time.time() + 180
    final_status: dict[str, Any] = {}
    while time.time() < settle_deadline:
        final_status = refresh_task_status(ecs, args.cluster, task_arn)
        if final_status.get("last_status") == "STOPPED":
            break
        time.sleep(10)
    if final_status.get("last_status") != "STOPPED":
        blockers.append("PR3.S1.WSP.B15_TASK_NOT_STOPPED")
    exit_code = final_status.get("container_exit_code")
    if exit_code not in (None, 0):
        blockers.append(f"PR3.S1.WSP.B18_CONTAINER_EXIT_NONZERO:{exit_code}")

    log_events: list[dict[str, Any]] = []
    log_error = ""
    if not log_stream_name:
        log_stream_name = resolve_log_stream_name(
            logs,
            log_group=args.log_group,
            window_start=active_start,
            window_end=datetime.now(timezone.utc),
        )
    if log_stream_name:
        try:
            log_events = get_log_events(logs, log_group=args.log_group, stream_name=log_stream_name)
        except (BotoCoreError, ClientError) as exc:
            log_error = f"{type(exc).__name__}:{exc}"
            blockers.append("PR3.S1.WSP.B16_LOG_UNREADABLE")
    else:
        log_error = "LOG_STREAM_NOT_RESOLVED"
        blockers.append("PR3.S1.WSP.B16_LOG_UNREADABLE")
    cli_result = parse_result_from_logs(log_events) if log_events else None

    totals = {"count_sum": 0.0, "4xx_sum": 0.0, "5xx_sum": 0.0}
    metrics_error = ""
    try:
        totals = get_apigw_totals(
            cw,
            api_id=args.api_id,
            stage=args.api_stage,
            start_time=active_start,
            end_time=datetime.now(timezone.utc),
        )
    except (BotoCoreError, ClientError) as exc:
        metrics_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PR3.S1.WSP.B17_METRICS_UNREADABLE")

    perf_end = final_status.get("stopped_at_utc") or now_utc()
    elapsed_seconds = max(
        1.0,
        (
            datetime.fromisoformat(perf_end.replace("Z", "+00:00")) - active_start
        ).total_seconds(),
    )
    observed_eps = totals["count_sum"] / elapsed_seconds

    summary = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "dispatch_mode": "CANONICAL_REMOTE_WSP_REPLAY",
        "verdict": "REMOTE_WSP_WINDOW_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "open_blockers": len(blockers),
        "blocker_ids": sorted(set(blockers)),
        "performance_window": {
            "submitted_at_utc": to_iso_utc(submitted_at),
            "start_utc": to_iso_utc(active_start),
            "end_utc": perf_end,
            "elapsed_seconds": elapsed_seconds,
        },
        "campaign": manifest["campaign"],
        "observed": {
            "admitted_request_count": int(totals["count_sum"]),
            "observed_admitted_eps": observed_eps,
            "4xx_total": int(totals["4xx_sum"]),
            "5xx_total": int(totals["5xx_sum"]),
            "early_cutoff_triggered": early_cutoff_triggered,
            "log_event_count": len(log_events),
            "cli_result": cli_result or {},
        },
        "task_status": {
            **final_status,
            "task_arn": task_arn,
            "log_stream_name": log_stream_name,
        },
        "notes": {
            "telemetry_error": telemetry_error,
            "metrics_error": metrics_error,
            "log_error": log_error,
            "window_stop_reason": "steady window bounded by certification duration",
        },
    }
    dump_json(pr3_root / "g3a_s1_wsp_runtime_summary.json", summary)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
