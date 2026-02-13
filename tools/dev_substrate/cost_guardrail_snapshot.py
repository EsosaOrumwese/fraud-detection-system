#!/usr/bin/env python3
"""
Emit a non-secret cost guardrail snapshot for dev-substrate work.

This utility combines:
- Cost Explorer monthly/daily service view (lagged but official),
- budget state,
- live resource posture (RDS/ECS/NAT) for immediate cost-risk visibility.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
from typing import Any


def run_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Command returned non-JSON output: {' '.join(cmd)}\n{proc.stdout[:300]}"
        ) from exc


def run_json_or_none(cmd: list[str]) -> Any | None:
    try:
        return run_json(cmd)
    except RuntimeError:
        return None


def extract_monthly_service_costs(ce_month: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    results = ce_month.get("ResultsByTime", [])
    if not results:
        return out
    groups = results[0].get("Groups", [])
    for g in groups:
        keys = g.get("Keys", [])
        service = keys[0] if keys else "UNKNOWN"
        amount = g.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", "0")
        unit = g.get("Metrics", {}).get("UnblendedCost", {}).get("Unit", "USD")
        out.append({"service": service, "amount": amount, "unit": unit})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument("--dashboard-name", default="fraud-platform-dev-min-cost-guardrail")
    parser.add_argument(
        "--output",
        default="",
        help="Output path. Default: runs/dev_substrate/cost_guardrail/<timestamp>/cost_guardrail_snapshot.json",
    )
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    start_month = today.replace(day=1).isoformat()
    tomorrow = (today + dt.timedelta(days=1)).isoformat()
    week_start = (today - dt.timedelta(days=7)).isoformat()
    ts = now.strftime("%Y%m%dT%H%M%SZ")

    if args.output:
        out_path = pathlib.Path(args.output)
    else:
        out_path = pathlib.Path(
            f"runs/dev_substrate/cost_guardrail/{ts}/cost_guardrail_snapshot.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    identity = run_json(["aws", "sts", "get-caller-identity", "--output", "json"])
    account_id = identity["Account"]

    ce_month = run_json(
        [
            "aws",
            "ce",
            "get-cost-and-usage",
            "--time-period",
            f"Start={start_month},End={tomorrow}",
            "--granularity",
            "MONTHLY",
            "--metrics",
            "UnblendedCost",
            "--group-by",
            "Type=DIMENSION,Key=SERVICE",
            "--output",
            "json",
        ]
    )
    ce_daily = run_json(
        [
            "aws",
            "ce",
            "get-cost-and-usage",
            "--time-period",
            f"Start={week_start},End={tomorrow}",
            "--granularity",
            "DAILY",
            "--metrics",
            "UnblendedCost",
            "--group-by",
            "Type=DIMENSION,Key=SERVICE",
            "--output",
            "json",
        ]
    )

    budgets = run_json_or_none(
        [
            "aws",
            "budgets",
            "describe-budgets",
            "--account-id",
            account_id,
            "--output",
            "json",
        ]
    )
    budget_rows: list[dict[str, Any]] = []
    if budgets:
        for b in budgets.get("Budgets", []):
            name = b.get("BudgetName", "")
            if "fraud-platform" not in name:
                continue
            budget_rows.append(
                {
                    "name": name,
                    "limit_amount": b.get("BudgetLimit", {}).get("Amount"),
                    "limit_unit": b.get("BudgetLimit", {}).get("Unit"),
                    "actual_amount": b.get("CalculatedSpend", {})
                    .get("ActualSpend", {})
                    .get("Amount"),
                    "forecast_amount": b.get("CalculatedSpend", {})
                    .get("ForecastedSpend", {})
                    .get("Amount"),
                }
            )

    demo_outputs = run_json_or_none(
        ["terraform", "-chdir=infra/terraform/dev_min/demo", "output", "-json"]
    ) or {}
    vpc_id = (demo_outputs.get("vpc_id") or {}).get("value")
    ecs_cluster = (demo_outputs.get("ecs_cluster_name") or {}).get("value")
    ecs_service = (demo_outputs.get("ecs_probe_service_name") or {}).get("value")
    rds_identifier = (demo_outputs.get("rds_instance_id") or {}).get("value")

    rds_desc = run_json_or_none(
        [
            "aws",
            "rds",
            "describe-db-instances",
            "--db-instance-identifier",
            rds_identifier or "fraud-platform-dev-min-db",
            "--output",
            "json",
        ]
    )
    rds_instances: list[dict[str, Any]] = []
    if rds_desc:
        for inst in rds_desc.get("DBInstances", []):
            rds_instances.append(
                {
                    "identifier": inst.get("DBInstanceIdentifier"),
                    "status": inst.get("DBInstanceStatus"),
                    "instance_class": inst.get("DBInstanceClass"),
                    "engine": inst.get("Engine"),
                    "engine_version": inst.get("EngineVersion"),
                    "allocated_storage_gb": inst.get("AllocatedStorage"),
                }
            )

    ecs_service_desc = None
    if ecs_cluster and ecs_service:
        ecs_service_desc = run_json_or_none(
            [
                "aws",
                "ecs",
                "describe-services",
                "--cluster",
                ecs_cluster,
                "--services",
                ecs_service,
                "--output",
                "json",
            ]
        )
    ecs_summary: dict[str, Any] = {}
    if ecs_service_desc and ecs_service_desc.get("services"):
        svc = ecs_service_desc["services"][0]
        ecs_summary = {
            "cluster": ecs_cluster,
            "service": ecs_service,
            "status": svc.get("status"),
            "desired_count": svc.get("desiredCount"),
            "running_count": svc.get("runningCount"),
            "pending_count": svc.get("pendingCount"),
        }

    nat_ids: list[str] = []
    if vpc_id:
        nat = run_json_or_none(
            [
                "aws",
                "ec2",
                "describe-nat-gateways",
                "--filter",
                f"Name=vpc-id,Values={vpc_id}",
                "--query",
                "NatGateways[].NatGatewayId",
                "--output",
                "json",
            ]
        )
        if isinstance(nat, list):
            nat_ids = [str(x) for x in nat]

    monthly_services = extract_monthly_service_costs(ce_month)
    has_running_rds = any(i.get("status") == "available" for i in rds_instances)
    has_nat = len(nat_ids) > 0
    ecs_running = int(ecs_summary.get("running_count", 0) or 0)

    recommendations: list[str] = []
    if has_running_rds:
        recommendations.append(
            "RDS is running; use strict demo window teardown/stop policy when idle."
        )
    if has_nat:
        recommendations.append("NAT gateway detected; this violates dev_min no-NAT guardrail.")
    if ecs_running > 0:
        recommendations.append(
            "ECS tasks are running; validate they are required for the active phase."
        )
    if not recommendations:
        recommendations.append("No immediate high-risk runtime cost posture detected.")
    recommendations.append("Track Confluent Cloud spend separately (outside AWS Cost Explorer).")
    recommendations.append(
        "Use Cost Explorer trend + live resource posture together; CE data is delayed."
    )

    payload = {
        "captured_at_utc": now.isoformat(),
        "account_id": account_id,
        "dashboard_name": args.dashboard_name,
        "ce_window": {
            "monthly_start": start_month,
            "daily_start": week_start,
            "end_exclusive": tomorrow,
        },
        "ce_monthly_by_service": monthly_services,
        "ce_daily_by_service": ce_daily.get("ResultsByTime", []),
        "budgets_fraud_platform": budget_rows,
        "live_resource_posture": {
            "rds_instances": rds_instances,
            "ecs_service": ecs_summary,
            "nat_gateway_ids": nat_ids,
        },
        "risk_flags": {
            "running_rds": has_running_rds,
            "nat_present": has_nat,
            "ecs_running_tasks": ecs_running,
        },
        "recommendations": recommendations,
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
