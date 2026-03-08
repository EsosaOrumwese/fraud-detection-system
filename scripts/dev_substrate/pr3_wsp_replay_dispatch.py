#!/usr/bin/env python3
"""Generic canonical PR3 remote WSP replay dispatcher.

Runs the real WSP emitter on remote ECS/Fargate for any PR3 runtime window
(`steady`, `burst`, `soak`) without overwriting the prior state's artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any
from urllib.parse import quote_plus, urlparse

import boto3
import psycopg
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


def archive_existing_artifact(path: Path) -> None:
    if not path.exists():
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = path.parent / "attempt_history"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_path = archive_dir / f"{path.stem}.{timestamp}{path.suffix}"
    archived_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def blocker_code(prefix: str, code: str, detail: str = "") -> str:
    base = f"{str(prefix).strip()}.{str(code).strip()}"
    return base if not detail else f"{base}:{detail}"


def artifact_name(prefix: str, suffix: str) -> str:
    return f"{str(prefix).strip()}_{str(suffix).strip()}.json"


PLATFORM_RUN_ID_RX = re.compile(r"^platform_[0-9]{8}T[0-9]{6}Z$")
SCENARIO_RUN_ID_RX = re.compile(r"^[a-f0-9]{32}$")


def remap_blocker_prefix(prefix: str, message: str) -> str:
    return str(message).replace("PR3.S1.WSP", str(prefix).strip())


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def arn_suffix(arn: str, marker: str) -> str:
    raw = str(arn).strip()
    token = f"{marker}/"
    if token in raw:
        return raw.split(token, 1)[1]
    return raw


def alb_target_group_dimension(arn: str) -> str:
    raw = str(arn).strip()
    if not raw:
        return ""
    token = "targetgroup/"
    if token in raw:
        return f"{token}{raw.split(token, 1)[1]}"
    return raw


def stop_partial_launches(ecs: Any, *, cluster: str, lanes: list[dict[str, Any]], reason: str) -> None:
    for lane in lanes:
        task_arn = str(lane.get("task_arn", "")).strip()
        if not task_arn:
            continue
        try:
            ecs.stop_task(cluster=cluster, task=task_arn, reason=reason[:255])
        except (BotoCoreError, ClientError):
            continue


def resolve_task_definition(ecs: Any, family_or_revision: str) -> str:
    raw = str(family_or_revision).strip()
    if not raw:
        raise RuntimeError("Task definition value is empty.")
    if ":" in raw:
        return raw
    try:
        result = ecs.list_task_definitions(familyPrefix=raw, sort="DESC", status="ACTIVE", maxResults=1)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Unable to resolve active task definition for family {raw}: {type(exc).__name__}") from exc
    task_definitions = list(result.get("taskDefinitionArns", []))
    if not task_definitions:
        raise RuntimeError(f"No active task definitions found for family {raw}.")
    return str(task_definitions[0]).rsplit("/", 1)[-1]


def task_id_from_arn(task_arn: str) -> str:
    return str(task_arn).rsplit("/", 1)[-1]


def to_iso_utc(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def align_up_to_period(dt: datetime, period_seconds: int) -> datetime:
    ts = dt.astimezone(timezone.utc).timestamp()
    aligned = math.ceil(ts / period_seconds) * period_seconds
    return datetime.fromtimestamp(aligned, tz=timezone.utc)


def align_down_to_period(dt: datetime, period_seconds: int) -> datetime:
    ts = dt.astimezone(timezone.utc).timestamp()
    aligned = math.floor(ts / period_seconds) * period_seconds
    return datetime.fromtimestamp(aligned, tz=timezone.utc)


def measurement_start_boundary(active_confirmed_at: datetime, *, warmup_seconds: int, period_seconds: int = 60) -> datetime:
    effective_warmup = max(0, int(warmup_seconds))
    return align_up_to_period(active_confirmed_at + timedelta(seconds=effective_warmup), period_seconds)


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
          --scenario-id "$ORACLE_SCENARIO_ID" \
          --scenario-run-id "$SCENARIO_RUN_ID"
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


def refresh_task_statuses(ecs: Any, cluster: str, task_arns: list[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(task_arns), 100):
        batch = [arn for arn in task_arns[offset : offset + 100] if arn]
        if not batch:
            continue
        payload = ecs.describe_tasks(cluster=cluster, tasks=batch)
        for task in payload.get("tasks", []):
            task_arn = str(task.get("taskArn", "")).strip()
            if not task_arn:
                continue
            container = (task.get("containers") or [{}])[0]
            results[task_arn] = {
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
    return results


def get_apigw_totals(
    cw: Any,
    *,
    api_id: str,
    stage: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> dict[str, float]:
    effective_start = align_up_to_period(start_time, period_seconds)
    effective_end = align_down_to_period(end_time, period_seconds)
    covered_seconds = max(0.0, (effective_end - effective_start).total_seconds())
    if covered_seconds < float(period_seconds):
        return {
            "count_sum": 0.0,
            "4xx_sum": 0.0,
            "5xx_sum": 0.0,
            "covered_seconds": 0.0,
            "effective_start_utc": to_iso_utc(effective_start),
            "effective_end_utc": to_iso_utc(effective_end),
            "bin_count": 0,
        }
    dims = [{"Name": "ApiId", "Value": api_id}, {"Name": "Stage", "Value": stage}]

    def metric_stats(metric_name: str) -> list[dict[str, Any]]:
        result = cw.get_metric_statistics(
            Namespace="AWS/ApiGateway",
            MetricName=metric_name,
            Dimensions=dims,
            StartTime=effective_start,
            EndTime=effective_end,
            Period=period_seconds,
            Statistics=["Sum"],
        )
        return list(result.get("Datapoints", []))

    count_points = metric_stats("Count")
    four_xx_points = metric_stats("4xx")
    five_xx_points = metric_stats("5xx")

    return {
        "count_sum": float(sum(float(row.get("Sum", 0.0) or 0.0) for row in count_points)),
        "4xx_sum": float(sum(float(row.get("Sum", 0.0) or 0.0) for row in four_xx_points)),
        "5xx_sum": float(sum(float(row.get("Sum", 0.0) or 0.0) for row in five_xx_points)),
        "covered_seconds": covered_seconds,
        "effective_start_utc": to_iso_utc(effective_start),
        "effective_end_utc": to_iso_utc(effective_end),
        "bin_count": int(covered_seconds // period_seconds),
    }


def get_apigw_metric_statistics(
    cw: Any,
    *,
    api_id: str,
    stage: str,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
    statistics: list[str] | None = None,
    extended_statistics: list[str] | None = None,
) -> list[dict[str, Any]]:
    effective_start = align_up_to_period(start_time, period_seconds)
    effective_end = align_down_to_period(end_time, period_seconds)
    if (effective_end - effective_start).total_seconds() < float(period_seconds):
        return []
    req: dict[str, Any] = {
        "Namespace": "AWS/ApiGateway",
        "MetricName": metric_name,
        "Dimensions": [{"Name": "ApiId", "Value": api_id}, {"Name": "Stage", "Value": stage}],
        "StartTime": effective_start,
        "EndTime": effective_end,
        "Period": period_seconds,
    }
    if statistics:
        req["Statistics"] = statistics
    if extended_statistics:
        req["ExtendedStatistics"] = extended_statistics
    result = cw.get_metric_statistics(**req)
    return list(result.get("Datapoints", []))


def get_alb_totals(
    cw: Any,
    *,
    load_balancer_dimension: str,
    target_group_dimension: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> dict[str, float]:
    effective_start = align_up_to_period(start_time, period_seconds)
    effective_end = align_down_to_period(end_time, period_seconds)
    covered_seconds = max(0.0, (effective_end - effective_start).total_seconds())
    if covered_seconds < float(period_seconds):
        return {
            "count_sum": 0.0,
            "4xx_sum": 0.0,
            "5xx_sum": 0.0,
            "covered_seconds": 0.0,
            "effective_start_utc": to_iso_utc(effective_start),
            "effective_end_utc": to_iso_utc(effective_end),
            "bin_count": 0,
        }
    lb_dims = [{"Name": "LoadBalancer", "Value": load_balancer_dimension}]
    tg_dims = lb_dims + [{"Name": "TargetGroup", "Value": target_group_dimension}]

    def metric_stats(metric_name: str, dimensions: list[dict[str, str]]) -> list[dict[str, Any]]:
        result = cw.get_metric_statistics(
            Namespace="AWS/ApplicationELB",
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=effective_start,
            EndTime=effective_end,
            Period=period_seconds,
            Statistics=["Sum"],
        )
        return list(result.get("Datapoints", []))

    request_points = metric_stats("RequestCount", lb_dims)
    target_four_xx_points = metric_stats("HTTPCode_Target_4XX_Count", tg_dims)
    target_five_xx_points = metric_stats("HTTPCode_Target_5XX_Count", tg_dims)
    elb_four_xx_points = metric_stats("HTTPCode_ELB_4XX_Count", lb_dims)
    elb_five_xx_points = metric_stats("HTTPCode_ELB_5XX_Count", lb_dims)

    return {
        "count_sum": float(sum(float(row.get("Sum", 0.0) or 0.0) for row in request_points)),
        "4xx_sum": float(
            sum(float(row.get("Sum", 0.0) or 0.0) for row in target_four_xx_points)
            + sum(float(row.get("Sum", 0.0) or 0.0) for row in elb_four_xx_points)
        ),
        "5xx_sum": float(
            sum(float(row.get("Sum", 0.0) or 0.0) for row in target_five_xx_points)
            + sum(float(row.get("Sum", 0.0) or 0.0) for row in elb_five_xx_points)
        ),
        "covered_seconds": covered_seconds,
        "effective_start_utc": to_iso_utc(effective_start),
        "effective_end_utc": to_iso_utc(effective_end),
        "bin_count": int(covered_seconds // period_seconds),
    }


def get_alb_metric_statistics(
    cw: Any,
    *,
    load_balancer_dimension: str,
    target_group_dimension: str,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
    statistics: list[str] | None = None,
    extended_statistics: list[str] | None = None,
) -> list[dict[str, Any]]:
    effective_start = align_up_to_period(start_time, period_seconds)
    effective_end = align_down_to_period(end_time, period_seconds)
    if (effective_end - effective_start).total_seconds() < float(period_seconds):
        return []
    dims = [{"Name": "LoadBalancer", "Value": load_balancer_dimension}]
    if metric_name == "TargetResponseTime":
        dims = dims + [{"Name": "TargetGroup", "Value": target_group_dimension}]
    if metric_name == "TargetResponseTime" and extended_statistics:
        queries: list[dict[str, Any]] = []
        for idx, stat in enumerate(extended_statistics):
            queries.append(
                {
                    "Id": f"q{idx}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApplicationELB",
                            "MetricName": metric_name,
                            "Dimensions": dims,
                        },
                        "Period": period_seconds,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                }
            )
        result = cw.get_metric_data(
            MetricDataQueries=queries,
            StartTime=effective_start,
            EndTime=effective_end,
        )
        by_timestamp: dict[str, dict[str, Any]] = {}
        for query, series in zip(queries, result.get("MetricDataResults", []), strict=False):
            stat = str(query["MetricStat"]["Stat"]).lower()
            for timestamp, value in zip(series.get("Timestamps", []), series.get("Values", []), strict=False):
                key = to_iso_utc(timestamp)
                row = by_timestamp.setdefault(
                    key,
                    {"Timestamp": timestamp, "ExtendedStatistics": {}},
                )
                row["ExtendedStatistics"][stat] = float(value)
        return list(by_timestamp.values())
    req: dict[str, Any] = {
        "Namespace": "AWS/ApplicationELB",
        "MetricName": metric_name,
        "Dimensions": dims,
        "StartTime": effective_start,
        "EndTime": effective_end,
        "Period": period_seconds,
    }
    if statistics:
        req["Statistics"] = statistics
    if extended_statistics:
        req["ExtendedStatistics"] = extended_statistics
    result = cw.get_metric_statistics(**req)
    return list(result.get("Datapoints", []))


def resolve_ingress_surface(
    *,
    elbv2: Any,
    ingest_url: str,
    api_id: str,
    api_stage: str,
    blocker_prefix: str,
    prior_surface: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = urlparse(str(ingest_url).strip())
    host = str(parsed.netloc or "").strip().split(":", 1)[0]
    if ".execute-api." in host:
        return {
            "mode": "APIGW",
            "host": host,
            "api_id": api_id,
            "api_stage": api_stage,
        }
    if host.endswith(".elb.amazonaws.com"):
        prior_surface = prior_surface or {}
        try:
            paginator = elbv2.get_paginator("describe_load_balancers")
            matched_lb: dict[str, Any] | None = None
            for page in paginator.paginate():
                for row in page.get("LoadBalancers", []):
                    if str(row.get("DNSName", "")).strip() == host:
                        matched_lb = row
                        break
                if matched_lb:
                    break
        except (BotoCoreError, ClientError):
            matched_lb = None
        if not matched_lb:
            if (
                str(prior_surface.get("mode", "")).upper() == "ALB"
                and str(prior_surface.get("host", "")).strip() == host
                and str(prior_surface.get("load_balancer_dimension", "")).strip()
                and str(prior_surface.get("target_group_dimension", "")).strip()
            ):
                return dict(prior_surface)
            raise RuntimeError(blocker_code(blocker_prefix, "B05_INGRESS_SURFACE_UNRESOLVED", f"alb_dns_not_found:{host}"))
        lb_arn = str(matched_lb.get("LoadBalancerArn", "")).strip()
        try:
            target_groups = list(elbv2.describe_target_groups(LoadBalancerArn=lb_arn).get("TargetGroups", []))
        except (BotoCoreError, ClientError):
            if (
                str(prior_surface.get("mode", "")).upper() == "ALB"
                and str(prior_surface.get("host", "")).strip() == host
                and str(prior_surface.get("load_balancer_arn", "")).strip() == lb_arn
                and str(prior_surface.get("load_balancer_dimension", "")).strip()
                and str(prior_surface.get("target_group_dimension", "")).strip()
            ):
                return dict(prior_surface)
            raise
        if not target_groups:
            raise RuntimeError(blocker_code(blocker_prefix, "B05_INGRESS_SURFACE_UNRESOLVED", f"no_target_group:{host}"))
        target_group = target_groups[0]
        return {
            "mode": "ALB",
            "host": host,
            "load_balancer_arn": lb_arn,
            "load_balancer_dimension": arn_suffix(lb_arn, "loadbalancer"),
            "target_group_arn": str(target_group.get("TargetGroupArn", "")).strip(),
            "target_group_dimension": alb_target_group_dimension(str(target_group.get("TargetGroupArn", "")).strip()),
            "target_group_count": len(target_groups),
        }
    raise RuntimeError(blocker_code(blocker_prefix, "B05_INGRESS_SURFACE_UNRESOLVED", f"unsupported_host:{host}"))


def get_ingress_totals(
    cw: Any,
    *,
    surface: dict[str, Any],
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> dict[str, float]:
    mode = str(surface.get("mode", "")).upper()
    if mode == "APIGW":
        return get_apigw_totals(
            cw,
            api_id=str(surface.get("api_id", "")).strip(),
            stage=str(surface.get("api_stage", "")).strip(),
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
        )
    if mode == "ALB":
        return get_alb_totals(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
        )
    raise RuntimeError(f"Unsupported ingress surface mode: {mode}")


def get_ingress_latency_statistics(
    cw: Any,
    *,
    surface: dict[str, Any],
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mode = str(surface.get("mode", "")).upper()
    if mode == "APIGW":
        latency_rows = get_apigw_metric_statistics(
            cw,
            api_id=str(surface.get("api_id", "")).strip(),
            stage=str(surface.get("api_stage", "")).strip(),
            metric_name="Latency",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            extended_statistics=["p95", "p99"],
        )
        count_rows = get_apigw_metric_statistics(
            cw,
            api_id=str(surface.get("api_id", "")).strip(),
            stage=str(surface.get("api_stage", "")).strip(),
            metric_name="Count",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        )
        return latency_rows, count_rows
    if mode == "ALB":
        latency_rows = get_alb_metric_statistics(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            metric_name="TargetResponseTime",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            extended_statistics=["p95", "p99"],
        )
        count_rows = get_alb_metric_statistics(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            metric_name="RequestCount",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        )
        return latency_rows, count_rows
    raise RuntimeError(f"Unsupported ingress surface mode: {mode}")


def weighted_latency_ms(
    latency_points: list[dict[str, Any]],
    count_points: list[dict[str, Any]],
) -> tuple[float, float, str]:
    count_by_ts: dict[str, float] = {}
    for row in count_points:
        ts = row.get("Timestamp")
        if ts is None:
            continue
        count_by_ts[str(ts)] = float(row.get("Sum", 0.0) or 0.0)
    p95_num = 0.0
    p99_num = 0.0
    weight_total = 0.0
    for row in latency_points:
        ts = row.get("Timestamp")
        if ts is None:
            continue
        ext = row.get("ExtendedStatistics", {}) or {}
        p95 = float(ext.get("p95", -1.0) or -1.0)
        p99 = float(ext.get("p99", -1.0) or -1.0)
        weight = count_by_ts.get(str(ts), 0.0)
        if p95 < 0.0 or p99 < 0.0 or weight <= 0.0:
            continue
        p95_num += p95 * weight
        p99_num += p99 * weight
        weight_total += weight
    if weight_total > 0.0:
        return (p95_num / weight_total) * 1000.0, (p99_num / weight_total) * 1000.0, "weighted_by_count_alb_seconds"
    return -1.0, -1.0, "unavailable"


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


def get_log_stream_metadata(logs: Any, *, log_group: str, stream_name: str) -> dict[str, Any]:
    paginator = logs.get_paginator("describe_log_streams")
    for page in paginator.paginate(logGroupName=log_group, logStreamNamePrefix=stream_name):
        for row in page.get("logStreams", []):
            if str(row.get("logStreamName", "")).strip() != stream_name:
                continue
            return {
                "creation_time_epoch_ms": int(row.get("creationTime", 0) or 0),
                "first_event_timestamp_epoch_ms": int(row.get("firstEventTimestamp", 0) or 0),
                "last_event_timestamp_epoch_ms": int(row.get("lastEventTimestamp", 0) or 0),
                "last_ingestion_time_epoch_ms": int(row.get("lastIngestionTime", 0) or 0),
                "stored_bytes": int(row.get("storedBytes", 0) or 0),
            }
    return {}


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


def probe_platform_run_identity_usage(dsn: str, platform_run_id: str) -> dict[str, Any]:
    usage = {
        "platform_run_id": str(platform_run_id).strip(),
        "admissions_count": 0,
        "receipts_count": 0,
        "tables_present": {"admissions": False, "receipts": False},
    }
    if not usage["platform_run_id"]:
        return usage
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for table in ("admissions", "receipts"):
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                row = cur.fetchone()
                present = bool(row and row[0])
                usage["tables_present"][table] = present
                if not present:
                    continue
                cur.execute(
                    f"SELECT COUNT(*) FROM public.{table} WHERE platform_run_id = %s",
                    (usage["platform_run_id"],),
                )
                count_row = cur.fetchone()
                usage[f"{table}_count"] = int(count_row[0] or 0) if count_row else 0
    return usage


def require_canonical_scenario_run_id(value: str, *, blocker_prefix: str) -> str:
    resolved = str(value).strip()
    if not SCENARIO_RUN_ID_RX.fullmatch(resolved):
        raise RuntimeError(
            blocker_code(blocker_prefix, "B00_INVALID_SCENARIO_RUN_ID", resolved or "empty")
        )
    return resolved


def require_canonical_platform_run_id(value: str, *, blocker_prefix: str) -> str:
    resolved = str(value).strip()
    if not PLATFORM_RUN_ID_RX.fullmatch(resolved):
        raise RuntimeError(
            blocker_code(blocker_prefix, "B00_INVALID_PLATFORM_RUN_ID", resolved or "empty")
        )
    return resolved


def main() -> None:
    ap = argparse.ArgumentParser(description="Dispatch canonical remote WSP replay for a PR3 runtime window.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S1")
    ap.add_argument("--window-label", default="steady")
    ap.add_argument("--artifact-prefix", default="g3a_s1")
    ap.add_argument("--blocker-prefix", default="PR3.S1.WSP")
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--profile-path", default="config/platform/profiles/dev_full.yaml")
    ap.add_argument("--cluster", default="fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--task-definition", default="fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--subnet-ids", default="subnet-0a7a35898d0ca31a8,subnet-0e9647425f02e2f27")
    ap.add_argument("--security-group-ids", default="sg-01bfefedcd75ec4b2")
    ap.add_argument("--assign-public-ip", default="DISABLED")
    ap.add_argument("--api-id", default="ehwznd2uw7")
    ap.add_argument("--api-stage", default="v1")
    ap.add_argument("--ssm-ig-api-key-path", default="/fraud-platform/dev_full/ig/api_key")
    ap.add_argument("--ssm-ig-service-url-path", default="/fraud-platform/dev_full/ig/service_url")
    ap.add_argument("--ssm-aurora-endpoint-path", default="/fraud-platform/dev_full/aurora/endpoint")
    ap.add_argument("--ssm-aurora-username-path", default="/fraud-platform/dev_full/aurora/username")
    ap.add_argument("--ssm-aurora-password-path", default="/fraud-platform/dev_full/aurora/password")
    ap.add_argument("--platform-run-id", default="")
    ap.add_argument("--scenario-run-id", default="")
    ap.add_argument(
        "--allow-runtime-identity-reuse",
        action="store_true",
        help="Allow reuse of a platform_run_id that already has persisted IG state.",
    )
    ap.add_argument(
        "--skip-runtime-identity-probe",
        action="store_true",
        help="Skip the runner-local platform_run_id probe when the workflow already performed an in-VPC preflight.",
    )
    ap.add_argument(
        "--oracle-engine-run-root",
        default="s3://fraud-platform-dev-full-object-store/oracle-store/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1",
    )
    ap.add_argument("--oracle-root", default="s3://fraud-platform-dev-full-object-store")
    ap.add_argument("--scenario-id", default="baseline_v1")
    ap.add_argument("--object-store-root", default="s3://fraud-platform-dev-full-object-store")
    ap.add_argument("--ig-ingest-url", default="")
    ap.add_argument("--ig-ingest-url-fallback", default="https://ehwznd2uw7.execute-api.eu-west-2.amazonaws.com/v1/ingest/push")
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
    ap.add_argument("--warmup-seconds", type=int, default=0)
    ap.add_argument("--early-cutoff-seconds", type=int, default=300)
    ap.add_argument("--early-cutoff-floor-ratio", type=float, default=0.70)
    ap.add_argument("--expected-window-eps", type=float, default=3000.0)
    ap.add_argument("--lane-count", type=int, default=24)
    ap.add_argument("--lane-launch-stagger-seconds", type=float, default=0.5)
    ap.add_argument("--output-concurrency", type=int, default=4)
    ap.add_argument("--ig-push-concurrency", type=int, default=4)
    ap.add_argument("--http-pool-maxsize", type=int, default=512)
    ap.add_argument("--checkpoint-attempt-id", default="")
    ap.add_argument("--target-request-rate-eps", type=float, default=0.0)
    ap.add_argument("--target-burst-seconds", type=float, default=0.25)
    ap.add_argument("--target-initial-tokens", type=float, default=0.25)
    ap.add_argument("--task-cpu", default="")
    ap.add_argument("--task-memory", default="")
    ap.add_argument("--max-error-rate-ratio", type=float, default=0.002)
    ap.add_argument("--max-4xx-ratio", type=float, default=0.002)
    ap.add_argument("--max-5xx-ratio", type=float, default=0.0)
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--metric-settle-seconds", type=int, default=90)
    ap.add_argument("--log-group", default="/ecs/fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--lane-log-mode", choices=["auto", "full", "metadata"], default="auto")
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
    elbv2 = boto3.client("elbv2", region_name=args.region)
    ssm = boto3.client("ssm", region_name=args.region)
    logs = boto3.client("logs", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)
    task_definition = resolve_task_definition(ecs, args.task_definition)

    ig_api_key = ssm.get_parameter(Name=args.ssm_ig_api_key_path, WithDecryption=True)["Parameter"]["Value"]
    resolved_ig_ingest_url = str(args.ig_ingest_url).strip()
    if not resolved_ig_ingest_url:
        try:
            service_url = ssm.get_parameter(Name=args.ssm_ig_service_url_path, WithDecryption=False)["Parameter"]["Value"]
            resolved_ig_ingest_url = str(service_url or "").strip()
        except (BotoCoreError, ClientError):
            resolved_ig_ingest_url = ""
    if not resolved_ig_ingest_url:
        resolved_ig_ingest_url = str(args.ig_ingest_url_fallback).strip()
    prior_surface: dict[str, Any] | None = None
    prior_manifest_path = pr3_root / artifact_name(args.artifact_prefix, "wsp_runtime_manifest")
    if prior_manifest_path.exists():
        try:
            prior_manifest = load_json(prior_manifest_path)
            prior_surface = dict(prior_manifest.get("ingress", {}).get("metric_surface", {}) or {})
        except Exception:
            prior_surface = None
    ingress_surface = resolve_ingress_surface(
        elbv2=elbv2,
        ingest_url=resolved_ig_ingest_url,
        api_id=args.api_id,
        api_stage=args.api_stage,
        blocker_prefix=args.blocker_prefix,
        prior_surface=prior_surface,
    )
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
            raise RuntimeError(blocker_code(args.blocker_prefix, "B02_CHECKPOINT_DSN_UNRESOLVED", "missing_ssm_paths=" + ",".join(missing)))
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
    checkpoint_attempt_id = str(args.checkpoint_attempt_id).strip() or submitted_at.strftime("%Y%m%dT%H%M%SZ")

    lane_count = max(1, int(args.lane_count))
    resolved_platform_run_id = require_canonical_platform_run_id(
        str(args.platform_run_id).strip() or f"platform_{checkpoint_attempt_id}",
        blocker_prefix=args.blocker_prefix,
    )
    resolved_scenario_run_id = require_canonical_scenario_run_id(
        args.scenario_run_id,
        blocker_prefix=args.blocker_prefix,
    )
    if args.skip_runtime_identity_probe:
        identity_probe = {
            "platform_run_id": resolved_platform_run_id,
            "probe_mode": "skipped_runner_local_probe",
            "admissions_count": None,
            "receipts_count": None,
            "tables_present": {},
        }
    else:
        identity_probe = probe_platform_run_identity_usage(wsp_checkpoint_dsn, resolved_platform_run_id)
        reused_runtime_identity = (
            int(identity_probe.get("admissions_count", 0) or 0) > 0
            or int(identity_probe.get("receipts_count", 0) or 0) > 0
        )
        if reused_runtime_identity and not args.allow_runtime_identity_reuse:
            raise RuntimeError(
                blocker_code(
                    args.blocker_prefix,
                    "B26_RUNTIME_ID_REUSED",
                    f"platform_run_id={resolved_platform_run_id}:"
                    f"admissions={int(identity_probe.get('admissions_count', 0) or 0)}:"
                    f"receipts={int(identity_probe.get('receipts_count', 0) or 0)}",
                )
            )
    target_request_rate_eps = float(args.target_request_rate_eps) if float(args.target_request_rate_eps) > 0.0 else float(
        args.expected_window_eps
    )
    per_lane_target_eps = target_request_rate_eps / float(lane_count)
    base_env_rows = [
        {"name": "AWS_REGION", "value": args.region},
        {"name": "WSP_PROFILE_PATH", "value": args.profile_path},
        {"name": "IG_API_KEY", "value": ig_api_key},
        {"name": "IG_INGEST_URL", "value": resolved_ig_ingest_url},
        {"name": "PLATFORM_RUN_ID", "value": resolved_platform_run_id},
        {"name": "SCENARIO_RUN_ID", "value": resolved_scenario_run_id},
        {"name": "ORACLE_ENGINE_RUN_ROOT", "value": args.oracle_engine_run_root},
        {"name": "ORACLE_ROOT", "value": args.oracle_root},
        {"name": "ORACLE_SCENARIO_ID", "value": args.scenario_id},
        {"name": "OBJECT_STORE_ROOT", "value": args.object_store_root},
        {"name": "WSP_TRAFFIC_OUTPUT_IDS", "value": args.traffic_output_ids},
        {"name": "WSP_CONTEXT_OUTPUT_IDS", "value": args.context_output_ids},
        {"name": "WSP_STREAM_SPEEDUP", "value": str(args.stream_speedup)},
        {"name": "WSP_CHECKPOINT_ATTEMPT_ID", "value": checkpoint_attempt_id},
        {"name": "WSP_CHECKPOINT_DSN", "value": wsp_checkpoint_dsn},
        {"name": "WSP_OUTPUT_CONCURRENCY", "value": str(max(1, args.output_concurrency))},
        {"name": "WSP_IG_PUSH_CONCURRENCY", "value": str(max(1, args.ig_push_concurrency))},
        {"name": "WSP_HTTP_POOL_MAXSIZE", "value": str(max(16, args.http_pool_maxsize))},
        {"name": "WSP_TARGET_EPS", "value": f"{per_lane_target_eps:.9f}"},
        {"name": "WSP_TARGET_BURST_SECONDS", "value": f"{max(0.0, float(args.target_burst_seconds)):.6f}"},
        {"name": "WSP_TARGET_INITIAL_TOKENS", "value": f"{max(0.0, float(args.target_initial_tokens)):.6f}"},
        {"name": "WSP_PROGRESS_EVERY", "value": "50000"},
        {"name": "WSP_PROGRESS_SECONDS", "value": "30"},
    ]
    command_list = build_wsp_command()
    launched_lanes: list[dict[str, Any]] = []
    task_cpu_override = str(args.task_cpu).strip()
    task_memory_override = str(args.task_memory).strip()
    for lane_index in range(lane_count):
        lane_id = f"wsp_lane_{lane_index:02d}"
        env_rows = list(base_env_rows) + [
            {"name": "WSP_LANE_COUNT", "value": str(lane_count)},
            {"name": "WSP_LANE_INDEX", "value": str(lane_index)},
        ]
        run_overrides: dict[str, Any] = {
            "containerOverrides": [
                {
                    "name": "wsp",
                    "command": command_list,
                    "environment": env_rows,
                }
            ]
        }
        if task_cpu_override:
            run_overrides["cpu"] = task_cpu_override
        if task_memory_override:
            run_overrides["memory"] = task_memory_override
        try:
            run_resp = ecs.run_task(
                cluster=args.cluster,
                taskDefinition=task_definition,
                launchType="FARGATE",
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": subnets,
                        "securityGroups": security_groups,
                        "assignPublicIp": str(args.assign_public_ip).strip().upper(),
                    }
                },
                overrides=run_overrides,
            )
        except (BotoCoreError, ClientError) as exc:
            stop_partial_launches(
                ecs,
                cluster=args.cluster,
                lanes=launched_lanes,
                reason=f"PR3-{args.state_id} partial launch cleanup after run_task failure",
            )
            raise RuntimeError(
                blocker_code(args.blocker_prefix, "B01_RUN_TASK_FAILED", f"{lane_id}:{type(exc).__name__}:{exc}")
            ) from exc
        failures = run_resp.get("failures", [])
        if failures:
            reason = str(failures[0].get("reason", "unknown"))
            stop_partial_launches(
                ecs,
                cluster=args.cluster,
                lanes=launched_lanes,
                reason=f"PR3-{args.state_id} partial launch cleanup after quota-bound failure",
            )
            raise RuntimeError(blocker_code(args.blocker_prefix, "B01_RUN_TASK_FAILED", f"{lane_id}:{reason}"))
        task = (run_resp.get("tasks") or [{}])[0]
        task_arn = str(task.get("taskArn", "")).strip()
        if not task_arn:
            stop_partial_launches(
                ecs,
                cluster=args.cluster,
                lanes=launched_lanes,
                reason=f"PR3-{args.state_id} partial launch cleanup after empty task arn",
            )
            raise RuntimeError(blocker_code(args.blocker_prefix, "B01_RUN_TASK_FAILED", f"{lane_id}:empty_task_arn"))
        task_id = task_id_from_arn(task_arn)
        launched_lanes.append(
            {
                "lane_id": lane_id,
                "lane_index": lane_index,
                "task_arn": task_arn,
                "task_id": task_id,
                "log_stream_name": f"ecs/wsp/{task_id}",
            }
        )
        if args.lane_launch_stagger_seconds > 0:
            time.sleep(max(0.0, float(args.lane_launch_stagger_seconds)))

    manifest = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "dispatch_mode": "CANONICAL_REMOTE_WSP_REPLAY",
        "cluster": args.cluster,
        "task_definition": task_definition,
        "log_group": args.log_group,
        "lane_count": lane_count,
        "lanes": launched_lanes,
        "network": {
            "subnets": subnets,
            "security_groups": security_groups,
            "assign_public_ip": str(args.assign_public_ip).strip().upper(),
        },
        "campaign": {
            "expected_window_eps": args.expected_window_eps,
            "window_label": str(args.window_label).strip().lower(),
            "target_request_rate_eps": target_request_rate_eps,
            "per_lane_target_eps": per_lane_target_eps,
            "duration_seconds": args.duration_seconds,
            "warmup_seconds": max(0, int(args.warmup_seconds)),
            "early_cutoff_seconds": args.early_cutoff_seconds,
            "early_cutoff_floor_ratio": args.early_cutoff_floor_ratio,
            "stream_speedup": args.stream_speedup,
            "checkpoint_attempt_id": checkpoint_attempt_id,
            "lane_count": lane_count,
            "output_concurrency": max(1, args.output_concurrency),
            "ig_push_concurrency": max(1, args.ig_push_concurrency),
            "http_pool_maxsize": max(16, args.http_pool_maxsize),
            "target_burst_seconds": max(0.0, float(args.target_burst_seconds)),
            "target_initial_tokens": max(0.0, float(args.target_initial_tokens)),
            "traffic_output_ids": parse_csv(args.traffic_output_ids),
            "context_output_ids": parse_csv(args.context_output_ids),
        },
        "runtime_profile": {
            "profile_path": args.profile_path,
            "checkpoint_backend": "postgres",
            "checkpoint_dsn_mode": "explicit_or_ssm_aurora",
            "checkpoint_attempt_id": checkpoint_attempt_id,
            "aurora_db_name": args.aurora_db_name,
            "task_cpu_override": task_cpu_override or None,
            "task_memory_override": task_memory_override or None,
        },
        "identity": {
            "platform_run_id": resolved_platform_run_id,
            "scenario_run_id": resolved_scenario_run_id,
            "scenario_id": args.scenario_id,
            "allow_runtime_identity_reuse": bool(args.allow_runtime_identity_reuse),
            "fresh_identity_probe": identity_probe,
        },
        "oracle": {
            "oracle_root": args.oracle_root,
            "oracle_engine_run_root": args.oracle_engine_run_root,
        },
        "ingress": {
            "resolved_ig_ingest_url": resolved_ig_ingest_url,
            "ig_ingest_url_fallback": str(args.ig_ingest_url_fallback).strip(),
            "ssm_ig_service_url_path": args.ssm_ig_service_url_path,
            "metric_surface": ingress_surface,
        },
    }
    manifest_path = pr3_root / artifact_name(args.artifact_prefix, "wsp_runtime_manifest")
    archive_existing_artifact(manifest_path)
    dump_json(manifest_path, manifest)

    expected_floor_eps = float(args.expected_window_eps) * float(args.early_cutoff_floor_ratio)
    active_start = submitted_at
    active_confirmed_at = submitted_at
    start_wait_deadline = time.time() + 900
    lane_by_arn = {str(lane["task_arn"]): lane for lane in launched_lanes}
    while time.time() < start_wait_deadline:
        statuses = refresh_task_statuses(ecs, args.cluster, list(lane_by_arn))
        started_at_values: list[datetime] = []
        all_running = True
        for task_arn, lane in lane_by_arn.items():
            status = statuses.get(task_arn, {})
            lane["status"] = status
            started_at = status.get("started_at_utc")
            if started_at:
                started_at_values.append(datetime.fromisoformat(str(started_at).replace("Z", "+00:00")).astimezone(timezone.utc))
            if status.get("last_status") != "RUNNING":
                all_running = False
            if status.get("last_status") == "STOPPED" and not started_at:
                blockers.append(f"PR3.S1.WSP.B03_TASK_STOPPED_BEFORE_RUNNING:{lane['lane_id']}")
        if started_at_values and all_running:
            active_start = max(started_at_values)
            active_confirmed_at = datetime.now(timezone.utc)
        if blockers or all_running:
            break
        time.sleep(5)
    if not blockers:
        never_started = [lane["lane_id"] for lane in launched_lanes if not lane.get("status", {}).get("started_at_utc")]
        if never_started:
            blockers.extend(f"PR3.S1.WSP.B04_TASK_START_TIMEOUT:{lane_id}" for lane_id in never_started)

    hard_deadline = time.time() + max(120, args.duration_seconds + 900)
    steady_window_seconds = int(math.ceil(max(60, args.duration_seconds) / 60.0) * 60)
    measurement_start_at = measurement_start_boundary(
        active_confirmed_at,
        warmup_seconds=args.warmup_seconds,
        period_seconds=60,
    )
    measurement_end_at = measurement_start_at + timedelta(seconds=steady_window_seconds)
    window_end = measurement_end_at.timestamp()
    early_cutoff_triggered = False
    telemetry_error = ""
    window_closed_at: datetime | None = None
    while time.time() < hard_deadline and not blockers:
        statuses = refresh_task_statuses(ecs, args.cluster, list(lane_by_arn))
        for task_arn, lane in lane_by_arn.items():
            lane["status"] = statuses.get(task_arn, {})
        pending = [lane for lane in launched_lanes if lane.get("status", {}).get("last_status") != "STOPPED"]
        now_dt = datetime.now(timezone.utc)
        elapsed = max(1.0, time.time() - active_confirmed_at.timestamp())
        settled_observation_end = min(
            measurement_end_at,
            now_dt - timedelta(seconds=max(0, int(args.metric_settle_seconds))),
        )
        try:
            totals = get_ingress_totals(
                cw,
                surface=ingress_surface,
                start_time=measurement_start_at,
                end_time=settled_observation_end,
            )
            covered_seconds = max(0.0, float(totals.get("covered_seconds", 0.0) or 0.0))
            observed_eps = totals["count_sum"] / covered_seconds if covered_seconds > 0.0 else 0.0
        except (BotoCoreError, ClientError) as exc:
            totals = {
                "count_sum": 0.0,
                "4xx_sum": 0.0,
                "5xx_sum": 0.0,
                "covered_seconds": 0.0,
                "effective_start_utc": "",
                "effective_end_utc": "",
                "bin_count": 0,
            }
            observed_eps = 0.0
            telemetry_error = f"{type(exc).__name__}:{exc}"
        success_count = max(0.0, totals["count_sum"] - totals["4xx_sum"] - totals["5xx_sum"])
        covered_seconds = max(0.0, float(totals.get("covered_seconds", 0.0) or 0.0))
        observed_admitted_eps = success_count / covered_seconds if covered_seconds > 0.0 else 0.0

        if (
            now_dt >= measurement_start_at + timedelta(seconds=max(60, args.early_cutoff_seconds))
            and covered_seconds >= float(max(60, args.early_cutoff_seconds))
            and observed_admitted_eps < expected_floor_eps
        ):
            window_closed_at = datetime.now(timezone.utc)
            blockers.append(
                f"PR3.S1.WSP.B12_EARLY_THROUGHPUT_SHORTFALL:observed={observed_admitted_eps:.3f}:floor={expected_floor_eps:.3f}"
            )
            early_cutoff_triggered = True
            for lane in pending:
                try:
                    ecs.stop_task(
                        cluster=args.cluster,
                        task=str(lane["task_arn"]),
                        reason=f"PR3-{args.state_id} early cutoff: canonical WSP replay below throughput floor",
                    )
                except (BotoCoreError, ClientError) as exc:
                    blockers.append(f"PR3.S1.WSP.B13_STOP_TASK_FAILED:{lane['lane_id']}:{type(exc).__name__}")
            break

        if time.time() >= window_end:
            window_closed_at = datetime.now(timezone.utc)
            for lane in pending:
                try:
                    ecs.stop_task(
                        cluster=args.cluster,
                        task=str(lane["task_arn"]),
                        reason=f"PR3-{args.state_id} window complete: canonical WSP replay bounded by certification window",
                    )
                except (BotoCoreError, ClientError) as exc:
                    blockers.append(f"PR3.S1.WSP.B14_WINDOW_STOP_FAILED:{lane['lane_id']}:{type(exc).__name__}")
            break

        if not pending:
            break
        time.sleep(30)

    settle_deadline = time.time() + 180
    final_statuses: dict[str, dict[str, Any]] = {}
    while time.time() < settle_deadline:
        final_statuses = refresh_task_statuses(ecs, args.cluster, list(lane_by_arn))
        for task_arn, lane in lane_by_arn.items():
            lane["final_status"] = final_statuses.get(task_arn, {})
        if all(lane.get("final_status", {}).get("last_status") == "STOPPED" for lane in launched_lanes):
            break
        time.sleep(10)
    for lane in launched_lanes:
        final_status = lane.get("final_status", {})
        if final_status.get("last_status") != "STOPPED":
            blockers.append(f"PR3.S1.WSP.B15_TASK_NOT_STOPPED:{lane['lane_id']}")
        exit_code = final_status.get("container_exit_code")
        stop_code = str(final_status.get("stop_code", "")).strip()
        if exit_code not in (None, 0) and stop_code != "UserInitiated":
            blockers.append(f"PR3.S1.WSP.B18_CONTAINER_EXIT_NONZERO:{lane['lane_id']}:{exit_code}")

    all_log_events: list[dict[str, Any]] = []
    log_error = ""
    lane_results: list[dict[str, Any]] = []
    lane_log_mode = str(args.lane_log_mode).strip().lower()
    if lane_log_mode == "auto":
        lane_log_mode = "metadata" if lane_count > 32 else "full"
    for lane in launched_lanes:
        log_stream_name = str(lane.get("log_stream_name", "")).strip()
        if not log_stream_name:
            log_stream_name = resolve_log_stream_name(
                logs,
                log_group=args.log_group,
                window_start=active_start,
                window_end=datetime.now(timezone.utc),
            )
            lane["log_stream_name"] = log_stream_name
            if not log_stream_name:
                log_error = "LOG_STREAM_NOT_RESOLVED"
                blockers.append(f"PR3.S1.WSP.B16_LOG_UNREADABLE:{lane['lane_id']}")
                continue
        log_events: list[dict[str, Any]] = []
        log_metadata: dict[str, Any] = {}
        cli_result = None
        try:
            if lane_log_mode == "full":
                log_events = get_log_events(logs, log_group=args.log_group, stream_name=log_stream_name)
                all_log_events.extend(log_events)
                cli_result = parse_result_from_logs(log_events) if log_events else None
            else:
                log_metadata = get_log_stream_metadata(logs, log_group=args.log_group, stream_name=log_stream_name)
        except (BotoCoreError, ClientError) as exc:
            log_error = f"{type(exc).__name__}:{exc}"
            blockers.append(f"PR3.S1.WSP.B16_LOG_UNREADABLE:{lane['lane_id']}")
            continue
        lane_results.append(
            {
                "lane_id": lane["lane_id"],
                "lane_index": lane["lane_index"],
                "task_arn": lane["task_arn"],
                "log_stream_name": log_stream_name,
                "log_capture_mode": lane_log_mode,
                "log_event_count": len(log_events) if lane_log_mode == "full" else None,
                "log_metadata": log_metadata,
                "cli_result": cli_result or {},
                "final_status": lane.get("final_status", {}),
            }
        )

    totals = {
        "count_sum": 0.0,
        "4xx_sum": 0.0,
        "5xx_sum": 0.0,
        "covered_seconds": 0.0,
        "effective_start_utc": "",
        "effective_end_utc": "",
        "bin_count": 0,
    }
    metrics_error = ""
    latency_p95_ms = -1.0
    latency_p99_ms = -1.0
    latency_method = "unavailable"
    metrics_end_time = min(window_closed_at or datetime.now(timezone.utc), measurement_end_at)
    metrics_ready_at = metrics_end_time + timedelta(seconds=max(0, int(args.metric_settle_seconds)))
    while datetime.now(timezone.utc) < metrics_ready_at:
        time.sleep(5)
    try:
        totals = get_ingress_totals(
            cw,
            surface=ingress_surface,
            start_time=measurement_start_at,
            end_time=metrics_end_time,
        )
        latency_rows, count_rows = get_ingress_latency_statistics(
            cw,
            surface=ingress_surface,
            start_time=measurement_start_at,
            end_time=metrics_end_time,
        )
        latency_p95_ms, latency_p99_ms, latency_method = weighted_latency_ms(latency_rows, count_rows)
    except (BotoCoreError, ClientError) as exc:
        metrics_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PR3.S1.WSP.B17_METRICS_UNREADABLE")

    stopped_times = [
        datetime.fromisoformat(str(lane["final_status"]["stopped_at_utc"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        for lane in launched_lanes
        if lane.get("final_status", {}).get("stopped_at_utc")
    ]
    if window_closed_at is not None:
        perf_end_dt = window_closed_at
    elif stopped_times:
        perf_end_dt = max(stopped_times)
    else:
        perf_end_dt = datetime.now(timezone.utc)
    perf_end = to_iso_utc(perf_end_dt)
    elapsed_seconds = max(
        1.0,
        (datetime.fromisoformat(perf_end.replace("Z", "+00:00")) - active_confirmed_at).total_seconds(),
    )
    covered_seconds = max(0.0, float(totals.get("covered_seconds", 0.0) or 0.0))
    request_count_total = max(0.0, totals["count_sum"])
    request_4xx_total = max(0.0, totals["4xx_sum"])
    request_5xx_total = max(0.0, totals["5xx_sum"])
    success_count = max(0.0, request_count_total - request_4xx_total - request_5xx_total)
    observed_eps = request_count_total / covered_seconds if covered_seconds > 0.0 else 0.0
    observed_admitted_eps = success_count / covered_seconds if covered_seconds > 0.0 else 0.0
    error_ratio = ((request_4xx_total + request_5xx_total) / request_count_total) if request_count_total > 0.0 else 1.0
    error_4xx_ratio = (request_4xx_total / request_count_total) if request_count_total > 0.0 else 1.0
    error_5xx_ratio = (request_5xx_total / request_count_total) if request_count_total > 0.0 else 1.0
    aggregate_cli_emitted = sum(
        int(result.get("cli_result", {}).get("emitted", 0) or 0)
        for result in lane_results
        if isinstance(result.get("cli_result"), dict)
    )
    blockers = [remap_blocker_prefix(args.blocker_prefix, item) for item in blockers]
    if observed_admitted_eps < float(args.expected_window_eps):
        blockers.append(
            blocker_code(
                args.blocker_prefix,
                "B19_FINAL_THROUGHPUT_SHORTFALL",
                f"observed={observed_admitted_eps:.3f}:target={float(args.expected_window_eps):.3f}",
            )
        )
    if error_ratio > float(args.max_error_rate_ratio):
        blockers.append(
            f"PR3.S1.WSP.B20_ERROR_RATE_BREACH:observed={error_ratio:.6f}:max={float(args.max_error_rate_ratio):.6f}"
        )
    if error_4xx_ratio > float(args.max_4xx_ratio):
        blockers.append(
            f"PR3.S1.WSP.B21_4XX_RATE_BREACH:observed={error_4xx_ratio:.6f}:max={float(args.max_4xx_ratio):.6f}"
        )
    if error_5xx_ratio > float(args.max_5xx_ratio):
        blockers.append(
            f"PR3.S1.WSP.B22_5XX_RATE_BREACH:observed={error_5xx_ratio:.6f}:max={float(args.max_5xx_ratio):.6f}"
        )
    if request_count_total > 0.0 and (latency_p95_ms < 0.0 or latency_p99_ms < 0.0):
        blockers.append("PR3.S1.WSP.B23_LATENCY_UNREADABLE")
    if latency_p95_ms >= 0.0 and latency_p95_ms > float(args.max_latency_p95_ms):
        blockers.append(
            f"PR3.S1.WSP.B24_P95_LATENCY_BREACH:observed={latency_p95_ms:.3f}:max={float(args.max_latency_p95_ms):.3f}"
        )
    if latency_p99_ms >= 0.0 and latency_p99_ms > float(args.max_latency_p99_ms):
        blockers.append(
            f"PR3.S1.WSP.B25_P99_LATENCY_BREACH:observed={latency_p99_ms:.3f}:max={float(args.max_latency_p99_ms):.3f}"
        )
    blockers = [remap_blocker_prefix(args.blocker_prefix, item) for item in blockers]

    summary = {
        "phase": "PR3",
        "state": args.state_id,
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
            "fleet_started_utc": to_iso_utc(active_start),
            "start_utc": to_iso_utc(active_confirmed_at),
            "active_confirmed_utc": to_iso_utc(active_confirmed_at),
            "warmup_seconds": max(0, int(args.warmup_seconds)),
            "measurement_start_utc": to_iso_utc(measurement_start_at),
            "measurement_target_end_utc": to_iso_utc(measurement_end_at),
            "metric_effective_start_utc": str(totals.get("effective_start_utc", "") or ""),
            "metric_effective_end_utc": str(totals.get("effective_end_utc", "") or ""),
            "end_utc": perf_end,
            "elapsed_seconds": elapsed_seconds,
            "covered_metric_seconds": covered_seconds,
            "metric_period_seconds": 60,
            "metric_bin_count": int(totals.get("bin_count", 0) or 0),
            "metric_surface_mode": str(ingress_surface.get("mode", "")).upper(),
        },
        "campaign": manifest["campaign"],
        "observed": {
            "request_count_total": int(request_count_total),
            "admitted_request_count": int(success_count),
            "observed_request_eps": observed_eps,
            "observed_admitted_eps": observed_admitted_eps,
            "error_rate_ratio": error_ratio,
            "4xx_rate_ratio": error_4xx_ratio,
            "5xx_rate_ratio": error_5xx_ratio,
            "4xx_total": int(request_4xx_total),
            "5xx_total": int(request_5xx_total),
            "latency_p95_ms": latency_p95_ms if latency_p95_ms >= 0.0 else None,
            "latency_p99_ms": latency_p99_ms if latency_p99_ms >= 0.0 else None,
            "latency_derivation_method": latency_method,
            "early_cutoff_triggered": early_cutoff_triggered,
            "log_event_count": len(all_log_events),
            "aggregate_cli_emitted": aggregate_cli_emitted,
            "lane_result_count": len(lane_results),
            "lane_log_capture_mode": lane_log_mode,
            "metric_surface_mode": str(ingress_surface.get("mode", "")).upper(),
        },
        "lane_results": lane_results,
        "notes": {
            "telemetry_error": telemetry_error,
            "metrics_error": metrics_error,
            "log_error": log_error,
            "window_stop_reason": "steady window bounded by certification duration",
            "metric_settle_seconds": int(args.metric_settle_seconds),
            "ingress_metric_surface": ingress_surface,
        },
    }
    summary_path = pr3_root / artifact_name(args.artifact_prefix, "wsp_runtime_summary")
    archive_existing_artifact(summary_path)
    dump_json(summary_path, summary)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
