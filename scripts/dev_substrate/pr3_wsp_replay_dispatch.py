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


def parse_execute_api_id(ingest_url: str) -> str:
    host = str(urlparse(str(ingest_url).strip()).netloc or "").strip().split(":", 1)[0]
    if ".execute-api." not in host:
        return ""
    return host.split(".", 1)[0].strip()


def resolve_live_ig_api(apigw: Any, *, api_name: str, api_id_hint: str) -> tuple[str, str]:
    hinted_id = str(api_id_hint).strip()
    if hinted_id:
        try:
            payload = apigw.get_api(ApiId=hinted_id)
        except (BotoCoreError, ClientError):
            payload = {}
        api_id = str(payload.get("ApiId", "")).strip()
        endpoint = str(payload.get("ApiEndpoint", "")).strip()
        if api_id and endpoint:
            return api_id, endpoint
    next_token: str | None = None
    wanted_name = str(api_name).strip()
    while True:
        kwargs: dict[str, Any] = {"MaxResults": "100"}
        if next_token:
            kwargs["NextToken"] = next_token
        payload = apigw.get_apis(**kwargs)
        for item in payload.get("Items", []) or []:
            if str(item.get("Name", "")).strip() != wanted_name:
                continue
            api_id = str(item.get("ApiId", "")).strip()
            endpoint = str(item.get("ApiEndpoint", "")).strip()
            if api_id and endpoint:
                return api_id, endpoint
        next_token = str(payload.get("NextToken", "")).strip() or None
        if not next_token:
            break
    raise RuntimeError(f"live ig api unresolved: name={wanted_name or 'empty'} hint={hinted_id or 'none'}")


def resolve_live_msk_network(kafka: Any, cluster_name: str) -> tuple[list[str], list[str]]:
    try:
        payload = kafka.list_clusters_v2(ClusterNameFilter=str(cluster_name).strip())
    except (BotoCoreError, ClientError):
        payload = {}
    items = list(payload.get("ClusterInfoList", []) or []) if isinstance(payload, dict) else []
    for item in items:
        if str(item.get("ClusterName", "")).strip() != str(cluster_name).strip():
            continue
        serverless = item.get("Serverless", {}) if isinstance(item, dict) else {}
        vpc_configs = list(serverless.get("VpcConfigs", []) or []) if isinstance(serverless, dict) else []
        if not vpc_configs:
            continue
        first = vpc_configs[0] if isinstance(vpc_configs[0], dict) else {}
        subnets = [str(value).strip() for value in (first.get("SubnetIds", []) or []) if str(value).strip()]
        security_groups = [str(value).strip() for value in (first.get("SecurityGroupIds", []) or []) if str(value).strip()]
        if subnets and security_groups:
            return subnets, security_groups
    return [], []


def resolve_vpc_id_for_subnets(ec2: Any, subnet_ids: list[str]) -> str:
    cleaned = [str(value).strip() for value in subnet_ids if str(value).strip()]
    if not cleaned:
        return ""
    try:
        payload = ec2.describe_subnets(SubnetIds=cleaned)
    except (BotoCoreError, ClientError):
        return ""
    for subnet in payload.get("Subnets", []) or []:
        vpc_id = str(subnet.get("VpcId", "")).strip()
        if vpc_id:
            return vpc_id
    return ""


def resolve_public_edge_subnets(ec2: Any, *, vpc_id: str) -> list[str]:
    if not str(vpc_id).strip():
        return []
    try:
        payload = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [str(vpc_id).strip()]}])
    except (BotoCoreError, ClientError):
        return []
    ranked: list[tuple[str, str, str]] = []
    for subnet in payload.get("Subnets", []) or []:
        subnet_id = str(subnet.get("SubnetId", "")).strip()
        if not subnet_id:
            continue
        tags = {str(row.get("Key", "")).strip(): str(row.get("Value", "")).strip() for row in (subnet.get("Tags", []) or [])}
        is_public = bool(subnet.get("MapPublicIpOnLaunch", False)) or tags.get("fp_subnet_tier", "").strip().lower() == "public"
        if not is_public:
            continue
        az = str(subnet.get("AvailabilityZone", "")).strip()
        ranked.append((az, subnet_id, tags.get("Name", "").strip()))
    ranked.sort(key=lambda row: (row[0], row[2], row[1]))
    return [subnet_id for _az, subnet_id, _name in ranked]


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


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


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


def summarize_ingress_bins(
    bins: list[dict[str, Any]],
    *,
    expected_eps: float,
) -> dict[str, Any]:
    if not bins:
        return {
            "bin_count": 0,
            "shortfall_bin_count": 0,
            "first_bin": {},
            "tail_bins": {},
        }
    admitted_eps_values = [float(row.get("observed_admitted_eps", 0.0) or 0.0) for row in bins]
    shortfall_bin_count = sum(1 for value in admitted_eps_values if value < float(expected_eps))
    first_bin = bins[0]
    tail_bins = bins[1:]
    tail_values = [float(row.get("observed_admitted_eps", 0.0) or 0.0) for row in tail_bins]
    return {
        "bin_count": len(bins),
        "shortfall_bin_count": shortfall_bin_count,
        "first_bin": {
            "timestamp_utc": first_bin.get("timestamp_utc"),
            "observed_admitted_eps": float(first_bin.get("observed_admitted_eps", 0.0) or 0.0),
            "request_count": int(float(first_bin.get("request_count", 0.0) or 0.0)),
            "admitted_count": int(float(first_bin.get("admitted_count", 0.0) or 0.0)),
            "4xx_total": int(float(first_bin.get("4xx_total", 0.0) or 0.0)),
            "5xx_total": int(float(first_bin.get("5xx_total", 0.0) or 0.0)),
        },
        "tail_bins": {
            "count": len(tail_bins),
            "shortfall_count": sum(1 for value in tail_values if value < float(expected_eps)),
            "min_observed_admitted_eps": min(tail_values) if tail_values else None,
            "max_observed_admitted_eps": max(tail_values) if tail_values else None,
            "avg_observed_admitted_eps": (sum(tail_values) / len(tail_values)) if tail_values else None,
        },
    }


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


def parse_log_group_name_from_arn(log_group_arn: str) -> str:
    raw = str(log_group_arn or "").strip()
    if not raw:
        return ""
    marker = ":log-group:"
    if marker not in raw:
        return ""
    suffix = raw.split(marker, 1)[1]
    return suffix.split(":*", 1)[0].strip()


def resolve_apigw_access_log_group(apigw: Any, *, api_id: str, stage: str) -> str:
    if not str(api_id).strip() or not str(stage).strip():
        return ""
    try:
        payload = apigw.get_stage(ApiId=str(api_id).strip(), StageName=str(stage).strip())
    except (BotoCoreError, ClientError):
        return ""
    access_log_settings = payload.get("AccessLogSettings", {}) if isinstance(payload, dict) else {}
    destination_arn = str(access_log_settings.get("DestinationArn", "")).strip() if isinstance(access_log_settings, dict) else ""
    return parse_log_group_name_from_arn(destination_arn)


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
    if covered_seconds <= 0.0 or not str(log_group_name).strip():
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
    start_epoch = int(exact_start.timestamp())
    end_epoch = int(math.ceil(exact_end.timestamp()))
    started = logs.start_query(
        logGroupName=str(log_group_name).strip(),
        startTime=start_epoch,
        endTime=end_epoch,
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
    request_count_total = float(_cwli_float(rows, "request_count_total") or 0.0)
    request_4xx_total = float(_cwli_float(rows, "request_4xx_total") or 0.0)
    request_5xx_total = float(_cwli_float(rows, "request_5xx_total") or 0.0)
    return {
        "request_count_total": request_count_total,
        "request_4xx_total": request_4xx_total,
        "request_5xx_total": request_5xx_total,
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
    aligned_metric_count_hint: float = 0.0,
    min_aligned_match_ratio: float = 0.995,
    max_attempts: int = 8,
    retry_sleep_seconds: int = 15,
    stability_ratio: float = 0.001,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    previous_count: float | None = None
    min_expected_from_aligned = max(0.0, float(aligned_metric_count_hint) * float(min_aligned_match_ratio))
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        current = get_apigw_access_log_window_stats(
            logs,
            log_group_name=log_group_name,
            start_time=start_time,
            end_time=end_time,
            route_key=route_key,
        )
        current["stability_attempt"] = attempt
        current["aligned_metric_count_hint"] = float(aligned_metric_count_hint)
        current["min_expected_from_aligned"] = min_expected_from_aligned
        best = current
        current_count = float(current.get("request_count_total", 0.0) or 0.0)
        if current_count >= min_expected_from_aligned > 0.0:
            current["stability_state"] = "aligned_lag_guard_satisfied"
            return current
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
    *,
    mode: str,
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
        upper_mode = str(mode).upper()
        scale = 1.0 if upper_mode == "APIGW" else 1000.0
        method = "weighted_by_count_apigw_ms" if upper_mode == "APIGW" else "weighted_by_count_alb_seconds"
        return (p95_num / weight_total) * scale, (p99_num / weight_total) * scale, method
    return -1.0, -1.0, "unavailable"


def get_ingress_metric_bins(
    cw: Any,
    *,
    surface: dict[str, Any],
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> list[dict[str, Any]]:
    mode = str(surface.get("mode", "")).upper()
    count_rows: list[dict[str, Any]]
    four_xx_rows: list[dict[str, Any]]
    five_xx_rows: list[dict[str, Any]]
    latency_rows: list[dict[str, Any]]
    if mode == "APIGW":
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
        four_xx_rows = get_apigw_metric_statistics(
            cw,
            api_id=str(surface.get("api_id", "")).strip(),
            stage=str(surface.get("api_stage", "")).strip(),
            metric_name="4xx",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        )
        five_xx_rows = get_apigw_metric_statistics(
            cw,
            api_id=str(surface.get("api_id", "")).strip(),
            stage=str(surface.get("api_stage", "")).strip(),
            metric_name="5xx",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        )
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
    elif mode == "ALB":
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
        four_xx_rows = get_alb_metric_statistics(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            metric_name="HTTPCode_Target_4XX_Count",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        ) + get_alb_metric_statistics(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            metric_name="HTTPCode_ELB_4XX_Count",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        )
        five_xx_rows = get_alb_metric_statistics(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            metric_name="HTTPCode_Target_5XX_Count",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        ) + get_alb_metric_statistics(
            cw,
            load_balancer_dimension=str(surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(surface.get("target_group_dimension", "")).strip(),
            metric_name="HTTPCode_ELB_5XX_Count",
            start_time=start_time,
            end_time=end_time,
            period_seconds=period_seconds,
            statistics=["Sum"],
        )
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
    else:
        raise RuntimeError(f"Unsupported ingress surface mode: {mode}")

    def _sum_map(rows: list[dict[str, Any]]) -> dict[str, float]:
        totals: dict[str, float] = {}
        for row in rows:
            stamp = to_iso_utc(row.get("Timestamp"))
            if not stamp:
                continue
            totals[stamp] = totals.get(stamp, 0.0) + float(row.get("Sum", 0.0) or 0.0)
        return totals

    count_map = _sum_map(count_rows)
    four_xx_map = _sum_map(four_xx_rows)
    five_xx_map = _sum_map(five_xx_rows)
    latency_map: dict[str, dict[str, float | None]] = {}
    for row in latency_rows:
        stamp = to_iso_utc(row.get("Timestamp"))
        if not stamp:
            continue
        ext = row.get("ExtendedStatistics", {}) or {}
        scale = 1.0 if mode == "APIGW" else 1000.0
        latency_map[stamp] = {
            "p95_ms": (float(ext.get("p95", -1.0) or -1.0) * scale) if ext.get("p95") is not None else None,
            "p99_ms": (float(ext.get("p99", -1.0) or -1.0) * scale) if ext.get("p99") is not None else None,
        }

    effective_start = align_up_to_period(start_time, period_seconds)
    effective_end = align_down_to_period(end_time, period_seconds)
    bins: list[dict[str, Any]] = []
    cursor = effective_start
    while cursor < effective_end:
        stamp = to_iso_utc(cursor) or ""
        request_count = float(count_map.get(stamp, 0.0))
        total_4xx = float(four_xx_map.get(stamp, 0.0))
        total_5xx = float(five_xx_map.get(stamp, 0.0))
        admitted = max(0.0, request_count - total_4xx - total_5xx)
        latency = latency_map.get(stamp, {})
        bins.append(
            {
                "timestamp_utc": stamp,
                "window_end_utc": to_iso_utc(cursor + timedelta(seconds=period_seconds)),
                "request_count": request_count,
                "admitted_count": admitted,
                "observed_request_eps": (request_count / float(period_seconds)) if request_count > 0.0 else 0.0,
                "observed_admitted_eps": (admitted / float(period_seconds)) if request_count > 0.0 else 0.0,
                "4xx_total": total_4xx,
                "5xx_total": total_5xx,
                "error_rate_ratio": ((total_4xx + total_5xx) / request_count) if request_count > 0.0 else 0.0,
                "4xx_rate_ratio": (total_4xx / request_count) if request_count > 0.0 else 0.0,
                "5xx_rate_ratio": (total_5xx / request_count) if request_count > 0.0 else 0.0,
                "latency_p95_ms": latency.get("p95_ms"),
                "latency_p99_ms": latency.get("p99_ms"),
            }
        )
        cursor += timedelta(seconds=period_seconds)
    return bins


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


def get_log_event_tail(
    logs: Any,
    *,
    log_group: str,
    stream_name: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    resp = logs.get_log_events(
        logGroupName=log_group,
        logStreamName=stream_name,
        startFromHead=False,
        limit=max(1, int(limit)),
    )
    return list(resp.get("events", []))


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
    emitted_by_output: dict[str, int] = {}
    run_id = ""
    progress_pattern = re.compile(r"output_id=(?P<output_id>\S+)\s+emitted=(?P<emitted>\d+)")
    run_pattern = re.compile(r"run_id=(?P<run_id>\S+)")
    for row in events:
        message = " ".join(str(row.get("message", "")).strip().split())
        if not message or " emitted=" not in message or "output_id=" not in message:
            continue
        match = progress_pattern.search(message)
        if not match:
            continue
        output_id = str(match.group("output_id")).strip()
        emitted = int(match.group("emitted"))
        emitted_by_output[output_id] = max(emitted_by_output.get(output_id, 0), emitted)
        if not run_id:
            run_match = run_pattern.search(message)
            if run_match:
                run_id = str(run_match.group("run_id")).strip()
    if emitted_by_output:
        return {
            "status": "LOG_DERIVED_PROGRESS",
            "engine_run_root": None,
            "run_id": run_id or None,
            "emitted": int(sum(emitted_by_output.values())),
            "outputs": emitted_by_output,
            "derived_from": "progress_logs",
        }
    return None


def summarize_log_tail(events: list[dict[str, Any]], *, max_lines: int = 8) -> list[str]:
    lines: list[str] = []
    for row in events[-max(1, int(max_lines)) :]:
        message = " ".join(str(row.get("message", "")).strip().split())
        if not message:
            continue
        lines.append(message[:400])
    return lines


def extract_failure_markers(lines: list[str]) -> list[str]:
    markers: list[str] = []
    wanted = (
        "IG_PUSH_REJECTED",
        "PUBLISH_AMBIGUOUS",
        "KAFKA_PUBLISH_TIMEOUT",
        "IG_UNHEALTHY",
        "BUS_UNHEALTHY",
        "http_503",
        "http_429",
        "timeout",
    )
    for line in lines:
        upper = line.upper()
        for marker in wanted:
            if marker.upper() not in upper:
                continue
            if marker not in markers:
                markers.append(marker)
    return markers


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
        "probe_mode": "runner_local_probe",
        "probe_error": "",
    }
    if not usage["platform_run_id"]:
        return usage
    try:
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
    except Exception as exc:
        usage["probe_mode"] = "runner_local_probe_unreachable"
        usage["probe_error"] = f"{type(exc).__name__}:{str(exc).strip()[:240]}"
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
    ap.add_argument("--msk-cluster-name", default="fraud-platform-dev-full-msk")
    ap.add_argument("--source-posture", choices=["auto", "public_edge", "private_runtime"], default="auto")
    ap.add_argument("--assign-public-ip", default="DISABLED")
    ap.add_argument("--api-id", default="")
    ap.add_argument("--ig-api-name", default="fraud-platform-dev-full-ig-edge")
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
    ap.add_argument("--ig-ingest-url-fallback", default="")
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
    ap.add_argument("--campaign-start-utc", default="")
    ap.add_argument("--rate-plan-json", default="")
    ap.add_argument("--skip-final-threshold-check", action="store_true")
    ap.add_argument("--task-cpu", default="")
    ap.add_argument("--task-memory", default="")
    ap.add_argument("--wsp-checkpoint-backend", default="")
    ap.add_argument("--wsp-checkpoint-root", default="")
    ap.add_argument("--wsp-checkpoint-flush-every", default="")
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
    kafka = boto3.client("kafka", region_name=args.region)
    ssm = boto3.client("ssm", region_name=args.region)
    logs = boto3.client("logs", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)
    apigw = boto3.client("apigatewayv2", region_name=args.region)
    ec2 = boto3.client("ec2", region_name=args.region)
    task_definition = resolve_task_definition(ecs, args.task_definition)

    ig_api_key = ssm.get_parameter(Name=args.ssm_ig_api_key_path, WithDecryption=True)["Parameter"]["Value"]
    resolved_api_id, live_api_endpoint = resolve_live_ig_api(
        apigw,
        api_name=args.ig_api_name,
        api_id_hint=args.api_id,
    )
    live_ig_ingest_url = f"{str(live_api_endpoint).rstrip('/')}/{str(args.api_stage).strip().strip('/')}/ingest/push"
    requested_ig_ingest_url = str(args.ig_ingest_url).strip()
    requested_api_id = parse_execute_api_id(requested_ig_ingest_url)
    resolved_ig_ingest_url = requested_ig_ingest_url
    if not resolved_ig_ingest_url:
        try:
            service_url = ssm.get_parameter(Name=args.ssm_ig_service_url_path, WithDecryption=False)["Parameter"]["Value"]
            resolved_ig_ingest_url = str(service_url or "").strip()
        except (BotoCoreError, ClientError):
            resolved_ig_ingest_url = ""
    if not resolved_ig_ingest_url or (requested_api_id and requested_api_id != resolved_api_id):
        resolved_ig_ingest_url = live_ig_ingest_url
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
        api_id=resolved_api_id,
        api_stage=args.api_stage,
        blocker_prefix=args.blocker_prefix,
        prior_surface=prior_surface,
    )
    if str(ingress_surface.get("mode", "")).upper() == "APIGW":
        ingress_surface["apigw_access_log_group"] = resolve_apigw_access_log_group(
            apigw,
            api_id=str(ingress_surface.get("api_id", "")).strip(),
            stage=str(ingress_surface.get("api_stage", "")).strip(),
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
    live_private_subnets, live_security_groups = resolve_live_msk_network(kafka, args.msk_cluster_name)
    subnets = list(live_private_subnets or parse_csv(args.subnet_ids))
    security_groups = list(live_security_groups or parse_csv(args.security_group_ids))
    resolved_source_posture = str(args.source_posture).strip().lower() or "auto"
    resolved_assign_public_ip = str(args.assign_public_ip).strip().upper() or "DISABLED"
    if resolved_source_posture == "auto":
        resolved_source_posture = "public_edge" if str(ingress_surface.get("mode", "")).upper() == "APIGW" else "private_runtime"
    if resolved_source_posture == "public_edge":
        vpc_id = resolve_vpc_id_for_subnets(ec2, subnets)
        public_subnets = resolve_public_edge_subnets(ec2, vpc_id=vpc_id)
        if public_subnets:
            subnets = public_subnets
        resolved_assign_public_ip = "ENABLED"
    elif resolved_source_posture == "private_runtime":
        resolved_assign_public_ip = "DISABLED"
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
    raw_rate_plan = str(args.rate_plan_json).strip()
    parsed_rate_plan: list[dict[str, Any]] = []
    if raw_rate_plan:
        try:
            payload = json.loads(raw_rate_plan)
            if isinstance(payload, list):
                parsed_rate_plan = [row for row in payload if isinstance(row, dict)]
        except json.JSONDecodeError as exc:
            raise RuntimeError(blocker_code(args.blocker_prefix, "B27_RATE_PLAN_INVALID", type(exc).__name__)) from exc
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
    if str(args.wsp_checkpoint_backend).strip():
        base_env_rows.append({"name": "WSP_CHECKPOINT_BACKEND", "value": str(args.wsp_checkpoint_backend).strip()})
    if str(args.wsp_checkpoint_root).strip():
        base_env_rows.append({"name": "WSP_CHECKPOINT_ROOT", "value": str(args.wsp_checkpoint_root).strip()})
    if str(args.wsp_checkpoint_flush_every).strip():
        base_env_rows.append(
            {"name": "WSP_CHECKPOINT_FLUSH_EVERY", "value": str(args.wsp_checkpoint_flush_every).strip()}
        )
    if str(args.campaign_start_utc).strip():
        base_env_rows.append({"name": "WSP_CAMPAIGN_START_UTC", "value": str(args.campaign_start_utc).strip()})
    if raw_rate_plan:
        base_env_rows.append({"name": "WSP_RATE_PLAN_JSON", "value": raw_rate_plan})
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
                        "assignPublicIp": resolved_assign_public_ip,
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
            "assign_public_ip": resolved_assign_public_ip,
            "resolved_source_posture": resolved_source_posture,
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
            "campaign_start_utc": str(args.campaign_start_utc).strip() or None,
            "rate_plan": parsed_rate_plan,
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
            "resolved_api_id": resolved_api_id,
            "ig_api_name": args.ig_api_name,
            "metric_surface": ingress_surface,
        },
    }
    manifest_path = pr3_root / artifact_name(args.artifact_prefix, "wsp_runtime_manifest")
    archive_existing_artifact(manifest_path)
    dump_json(manifest_path, manifest)

    expected_floor_eps = float(args.expected_window_eps) * float(args.early_cutoff_floor_ratio)
    active_start = submitted_at
    active_confirmed_at = submitted_at
    fleet_confirmation_mode = "submitted_at_fallback"
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
        all_started = len(started_at_values) == len(lane_by_arn)
        if started_at_values and all_running:
            active_start = max(started_at_values)
            active_confirmed_at = datetime.now(timezone.utc)
            fleet_confirmation_mode = "all_running"
        elif all_started:
            active_start = max(started_at_values)
            active_confirmed_at = datetime.now(timezone.utc)
            fleet_confirmation_mode = "all_started"
        if blockers or all_running or all_started:
            break
        time.sleep(5)
    if not blockers:
        never_started = [lane["lane_id"] for lane in launched_lanes if not lane.get("status", {}).get("started_at_utc")]
        if never_started:
            blockers.extend(f"PR3.S1.WSP.B04_TASK_START_TIMEOUT:{lane_id}" for lane_id in never_started)

    hard_deadline = time.time() + max(120, args.duration_seconds + 900)
    steady_window_seconds = int(math.ceil(max(60, args.duration_seconds) / 60.0) * 60)
    configured_campaign_start = parse_utc(args.campaign_start_utc) if str(args.campaign_start_utc).strip() else None
    measurement_start_at = (
        configured_campaign_start
        if configured_campaign_start is not None
        else measurement_start_boundary(
            active_confirmed_at,
            warmup_seconds=args.warmup_seconds,
            period_seconds=60,
        )
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
        log_tail_events: list[dict[str, Any]] = []
        cli_result = None
        try:
            if lane_log_mode == "full":
                log_events = get_log_events(logs, log_group=args.log_group, stream_name=log_stream_name)
                all_log_events.extend(log_events)
                cli_result = parse_result_from_logs(log_events) if log_events else None
            else:
                log_metadata = get_log_stream_metadata(logs, log_group=args.log_group, stream_name=log_stream_name)
                final_status = lane.get("final_status", {})
                exit_code = final_status.get("container_exit_code")
                stop_code = str(final_status.get("stop_code", "")).strip()
                if exit_code not in (None, 0) and stop_code != "UserInitiated":
                    log_tail_events = get_log_event_tail(
                        logs,
                        log_group=args.log_group,
                        stream_name=log_stream_name,
                        limit=12,
                    )
        except (BotoCoreError, ClientError) as exc:
            log_error = f"{type(exc).__name__}:{exc}"
            blockers.append(f"PR3.S1.WSP.B16_LOG_UNREADABLE:{lane['lane_id']}")
            continue
        log_tail_messages = summarize_log_tail(log_tail_events) if log_tail_events else []
        lane_results.append(
            {
                "lane_id": lane["lane_id"],
                "lane_index": lane["lane_index"],
                "task_arn": lane["task_arn"],
                "log_stream_name": log_stream_name,
                "log_capture_mode": lane_log_mode,
                "log_event_count": len(log_events) if lane_log_mode == "full" else None,
                "log_metadata": log_metadata,
                "log_tail_messages": log_tail_messages,
                "failure_markers": extract_failure_markers(log_tail_messages) if log_tail_messages else [],
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
        latency_p95_ms, latency_p99_ms, latency_method = weighted_latency_ms(
            latency_rows,
            count_rows,
            mode=str(ingress_surface.get("mode", "")).upper(),
        )
    except (BotoCoreError, ClientError) as exc:
        metrics_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PR3.S1.WSP.B17_METRICS_UNREADABLE")
    ingress_bins: list[dict[str, Any]] = []
    if not metrics_error:
        try:
            ingress_bins = get_ingress_metric_bins(
                cw,
                surface=ingress_surface,
                start_time=measurement_start_at,
                end_time=metrics_end_time,
            )
        except (BotoCoreError, ClientError) as exc:
            metrics_error = f"{type(exc).__name__}:{exc}"
            blockers.append("PR3.S1.WSP.B17_METRIC_BINS_UNREADABLE")
    ingress_bin_summary = summarize_ingress_bins(
        ingress_bins,
        expected_eps=float(args.expected_window_eps),
    )

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
    aligned_metric_covered_seconds = max(0.0, float(totals.get("covered_seconds", 0.0) or 0.0))
    aligned_metric_request_count_total = max(0.0, totals["count_sum"])
    aligned_metric_request_4xx_total = max(0.0, totals["4xx_sum"])
    aligned_metric_request_5xx_total = max(0.0, totals["5xx_sum"])
    aligned_metric_success_count = max(
        0.0,
        aligned_metric_request_count_total - aligned_metric_request_4xx_total - aligned_metric_request_5xx_total,
    )
    aligned_metric_observed_eps = (
        aligned_metric_request_count_total / aligned_metric_covered_seconds if aligned_metric_covered_seconds > 0.0 else 0.0
    )
    aligned_metric_observed_admitted_eps = (
        aligned_metric_success_count / aligned_metric_covered_seconds if aligned_metric_covered_seconds > 0.0 else 0.0
    )
    final_gate_source = "aligned_metric_bins"
    exact_window_error = ""
    exact_window_stats: dict[str, Any] | None = None
    exact_measurement_start_at = measurement_start_at
    exact_measurement_end_target = measurement_end_at
    exact_measurement_end_at = min(exact_measurement_end_target, perf_end_dt)
    if (
        str(ingress_surface.get("mode", "")).upper() == "APIGW"
        and str(ingress_surface.get("apigw_access_log_group", "")).strip()
        and exact_measurement_end_at > exact_measurement_start_at
    ):
        try:
            exact_window_stats = get_stable_apigw_access_log_window_stats(
                logs,
                log_group_name=str(ingress_surface.get("apigw_access_log_group", "")).strip(),
                start_time=exact_measurement_start_at,
                end_time=exact_measurement_end_at,
                aligned_metric_count_hint=aligned_metric_request_count_total,
            )
        except (BotoCoreError, ClientError, RuntimeError) as exc:
            exact_window_error = f"{type(exc).__name__}:{exc}"
    covered_seconds = aligned_metric_covered_seconds
    request_count_total = aligned_metric_request_count_total
    request_4xx_total = aligned_metric_request_4xx_total
    request_5xx_total = aligned_metric_request_5xx_total
    success_count = aligned_metric_success_count
    observed_eps = aligned_metric_observed_eps
    observed_admitted_eps = aligned_metric_observed_admitted_eps
    if exact_window_stats and float(exact_window_stats.get("covered_seconds", 0.0) or 0.0) > 0.0:
        final_gate_source = "apigw_access_log_exact_window"
        covered_seconds = max(0.0, float(exact_window_stats.get("covered_seconds", 0.0) or 0.0))
        request_count_total = max(0.0, float(exact_window_stats.get("request_count_total", 0.0) or 0.0))
        request_4xx_total = max(0.0, float(exact_window_stats.get("request_4xx_total", 0.0) or 0.0))
        request_5xx_total = max(0.0, float(exact_window_stats.get("request_5xx_total", 0.0) or 0.0))
        success_count = max(0.0, request_count_total - request_4xx_total - request_5xx_total)
        observed_eps = request_count_total / covered_seconds if covered_seconds > 0.0 else 0.0
        observed_admitted_eps = success_count / covered_seconds if covered_seconds > 0.0 else 0.0
        exact_latency_p95 = exact_window_stats.get("latency_p95_ms")
        exact_latency_p99 = exact_window_stats.get("latency_p99_ms")
        if exact_latency_p95 is not None:
            latency_p95_ms = float(exact_latency_p95)
        if exact_latency_p99 is not None:
            latency_p99_ms = float(exact_latency_p99)
    aligned_metric_window = {
        "request_count_total": int(aligned_metric_request_count_total),
        "admitted_request_count": int(aligned_metric_success_count),
        "observed_request_eps": aligned_metric_observed_eps,
        "observed_admitted_eps": aligned_metric_observed_admitted_eps,
        "4xx_total": int(aligned_metric_request_4xx_total),
        "5xx_total": int(aligned_metric_request_5xx_total),
        "covered_seconds": aligned_metric_covered_seconds,
        "effective_start_utc": str(totals.get("effective_start_utc", "") or ""),
        "effective_end_utc": str(totals.get("effective_end_utc", "") or ""),
        "metric_bin_count": int(totals.get("bin_count", 0) or 0),
    }
    error_ratio = ((request_4xx_total + request_5xx_total) / request_count_total) if request_count_total > 0.0 else 1.0
    error_4xx_ratio = (request_4xx_total / request_count_total) if request_count_total > 0.0 else 1.0
    error_5xx_ratio = (request_5xx_total / request_count_total) if request_count_total > 0.0 else 1.0
    aggregate_cli_emitted = sum(
        int(result.get("cli_result", {}).get("emitted", 0) or 0)
        for result in lane_results
        if isinstance(result.get("cli_result"), dict)
    )
    blockers = [remap_blocker_prefix(args.blocker_prefix, item) for item in blockers]
    if not args.skip_final_threshold_check:
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
            "fleet_confirmation_mode": fleet_confirmation_mode,
            "measurement_alignment_mode": (
                "explicit_campaign_start" if configured_campaign_start is not None else "align_up_from_active_confirmed_plus_warmup"
            ),
            "warmup_seconds": max(0, int(args.warmup_seconds)),
            "measurement_start_utc": to_iso_utc(measurement_start_at),
            "measurement_target_end_utc": to_iso_utc(measurement_end_at),
            "exact_measurement_start_utc": to_iso_utc(exact_measurement_start_at),
            "exact_measurement_target_end_utc": to_iso_utc(exact_measurement_end_target),
            "exact_measurement_end_utc": to_iso_utc(exact_measurement_end_at),
            "metric_effective_start_utc": str(totals.get("effective_start_utc", "") or ""),
            "metric_effective_end_utc": str(totals.get("effective_end_utc", "") or ""),
            "end_utc": perf_end,
            "elapsed_seconds": elapsed_seconds,
            "covered_metric_seconds": covered_seconds,
            "metric_period_seconds": 60,
            "metric_bin_count": int(totals.get("bin_count", 0) or 0),
            "metric_surface_mode": str(ingress_surface.get("mode", "")).upper(),
            "fleet_start_to_confirmation_seconds": max(0.0, (active_confirmed_at - active_start).total_seconds()),
            "fleet_start_to_measurement_start_seconds": max(0.0, (measurement_start_at - active_start).total_seconds()),
            "confirmation_to_measurement_start_seconds": max(0.0, (measurement_start_at - active_confirmed_at).total_seconds()),
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
            "final_gate_source": final_gate_source,
            "aligned_metric_window": aligned_metric_window,
            "exact_window": exact_window_stats,
            "ingress_bin_summary": ingress_bin_summary,
        },
        "lane_results": lane_results,
        "notes": {
            "telemetry_error": telemetry_error,
            "metrics_error": metrics_error,
            "exact_window_error": exact_window_error,
            "log_error": log_error,
            "window_stop_reason": "steady window bounded by certification duration",
            "metric_settle_seconds": int(args.metric_settle_seconds),
            "skip_final_threshold_check": bool(args.skip_final_threshold_check),
            "ingress_metric_surface": ingress_surface,
        },
    }
    summary_path = pr3_root / artifact_name(args.artifact_prefix, "wsp_runtime_summary")
    archive_existing_artifact(summary_path)
    dump_json(summary_path, summary)
    ingress_bins_path = pr3_root / artifact_name(args.artifact_prefix, "ingress_bins")
    archive_existing_artifact(ingress_bins_path)
    dump_json(
        ingress_bins_path,
        {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "generated_by": args.generated_by,
            "version": args.version,
            "execution_id": args.pr3_execution_id,
            "artifact_prefix": args.artifact_prefix,
            "window_label": str(args.window_label).strip().lower(),
            "measurement_start_utc": to_iso_utc(measurement_start_at),
            "measurement_end_utc": to_iso_utc(metrics_end_time),
            "metric_surface": ingress_surface,
            "bins": ingress_bins,
        },
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
