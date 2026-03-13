#!/usr/bin/env python3
"""Bounded Phase 9 operator/governance surface probe for the widened stress slice."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


RUNBOOK_PATH = "docs/runbooks/dev_full_phase7_ops_gov_runbook.md"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_s3_ref(ref: str) -> tuple[str, str]:
    text = str(ref or "").strip()
    if not text.startswith("s3://"):
        raise ValueError(f"invalid_s3_ref:{text}")
    bucket, _, key = text[5:].partition("/")
    if not bucket or not key:
        raise ValueError(f"invalid_s3_ref:{text}")
    return bucket, key


def s3_readable(s3: Any, ref: str) -> bool:
    bucket, key = parse_s3_ref(ref)
    s3.head_object(Bucket=bucket, Key=key)
    return True


def run(cmd: list[str], *, timeout: int = 240, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def placeholder_flag(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in ("rotate-me", "example", "placeholder", "changeme", "todo"))


def metric_freshness(
    client: Any,
    *,
    namespace: str,
    metric_name: str,
    dimensions: list[dict[str, str]],
    stat: str,
    period: int,
    lookback_minutes: int,
) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=lookback_minutes)
    payload = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=period,
        Statistics=[stat],
    )
    points = sorted(payload.get("Datapoints") or [], key=lambda row: row["Timestamp"])
    latest = points[-1] if points else None
    return {
        "fresh": latest is not None,
        "latest_timestamp_utc": latest["Timestamp"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if latest
        else "",
        "sample_count": len(points),
    }


def dashboard_body(client: Any, name: str) -> dict[str, Any]:
    return json.loads(str(client.get_dashboard(DashboardName=name).get("DashboardBody") or "{}"))


def dashboard_markdown_refs(body: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for widget in body.get("widgets") or []:
        props = dict(widget.get("properties") or {})
        markdown = str(props.get("markdown") or "").strip()
        if markdown:
            values.append(markdown)
    return values


def main() -> None:
    ap = argparse.ArgumentParser(description="Bounded Phase 9 operator/governance stress probe")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-phase6-execution-id", required=True)
    ap.add_argument("--source-platform-run-id", required=True)
    ap.add_argument("--aws-region", default="eu-west-2")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_phase6_execution_id

    s3 = boto3.client("s3", region_name=args.aws_region)
    cw = boto3.client("cloudwatch", region_name=args.aws_region)
    cw_billing = boto3.client("cloudwatch", region_name="us-east-1")
    ssm = boto3.client("ssm", region_name=args.aws_region)
    budgets = boto3.client("budgets", region_name="us-east-1")
    ce = boto3.client("ce", region_name="us-east-1")

    phase6_receipt = load_json(source_root / "phase6_learning_coupled_receipt.json")
    phase6_summary = load_json(source_root / "phase6_learning_coupled_summary.json")
    phase6_manifest = load_json(source_root / "phase6_registry_surface_manifest.json")
    phase5_execution_id = str(phase6_summary.get("source_phase5_execution_id") or "").strip()
    phase5_summary = (
        load_json(Path(args.run_control_root) / phase5_execution_id / "phase5_learning_managed_summary.json")
        if phase5_execution_id
        else {}
    )

    blockers: list[str] = []
    if str(phase6_receipt.get("verdict") or "").strip() != "PHASE6_READY":
        blockers.append("PHASE9_C_SOURCE_PHASE6_NOT_GREEN")
    if str(phase6_summary.get("platform_run_id") or "").strip() != str(args.source_platform_run_id).strip():
        blockers.append("PHASE9_C_SOURCE_PLATFORM_RUN_DRIFT")

    required_local = [
        "phase6_learning_coupled_receipt.json",
        "phase6_learning_coupled_summary.json",
        "phase6_coupled_envelope_summary.json",
        "phase6_registry_surface_manifest.json",
        "phase6_coupled_scorecard.json",
        "phase6_candidate_bundle_probe.json",
        "phase6_rollback_bundle_probe.json",
        "phase6_restore_bundle_probe.json",
    ]
    local_presence = {name: (source_root / name).exists() for name in required_local}
    for name, present in local_presence.items():
        if not present:
            blockers.append(f"PHASE9_C_MISSING_LOCAL_EVIDENCE:{name}")

    readable_refs: dict[str, str] = {}
    phase5_refs = dict((phase6_summary.get("learning_authority") or {}).get("phase5_refs") or {})
    for key, ref in phase5_refs.items():
        text = str(ref or "").strip()
        if not text.startswith("s3://"):
            continue
        try:
            s3_readable(s3, text)
            readable_refs[key] = text
        except (BotoCoreError, ClientError, ValueError):
            blockers.append(f"PHASE9_C_EVIDENCE_READBACK_FAIL:{key}")

    operations_body = dashboard_body(cw, "fraud-platform-dev-full-operations")
    cost_body = dashboard_body(cw, "fraud-platform-dev-full-cost-guardrail")
    operations_markdown = dashboard_markdown_refs(operations_body)
    cost_markdown = dashboard_markdown_refs(cost_body)
    if not Path(RUNBOOK_PATH).exists():
        blockers.append("PHASE9_C_RUNBOOK_MISSING")
    if not any(RUNBOOK_PATH in text for text in operations_markdown):
        blockers.append("PHASE9_C_OPERATIONS_RUNBOOK_LINK_MISSING")
    if not any(RUNBOOK_PATH in text for text in cost_markdown):
        blockers.append("PHASE9_C_COST_RUNBOOK_LINK_MISSING")

    alarms = cw.describe_alarms(AlarmNamePrefix="fraud-platform-dev-full-").get("MetricAlarms") or []
    alarms_billing = cw_billing.describe_alarms(AlarmNamePrefix="fraud-platform-dev-full-").get("MetricAlarms") or []
    present_alarm_names = sorted(
        set(
            str(row.get("AlarmName") or "").strip()
            for row in [*alarms, *alarms_billing]
            if str(row.get("AlarmName") or "").strip()
        )
    )
    required_alarms = [
        "fraud-platform-dev-full-ig-lambda-errors",
        "fraud-platform-dev-full-ig-lambda-throttles",
        "fraud-platform-dev-full-ig-apigw-5xx",
        "fraud-platform-dev-full-eks-unschedulable-pods",
        "fraud-platform-dev-full-eks-apiserver-5xx",
        "fraud-platform-dev-full-billing-estimated-charges",
    ]
    for name in required_alarms:
        if name not in present_alarm_names:
            blockers.append(f"PHASE9_C_ALARM_MISSING:{name}")

    freshness = {
        "lambda_duration": metric_freshness(
            cw,
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions=[{"Name": "FunctionName", "Value": "fraud-platform-dev-full-ig-handler"}],
            stat="Maximum",
            period=300,
            lookback_minutes=720,
        ),
        "apigw_count": metric_freshness(
            cw,
            namespace="AWS/ApiGateway",
            metric_name="Count",
            dimensions=[{"Name": "ApiId", "Value": "pd7rtjze95"}, {"Name": "Stage", "Value": "v1"}],
            stat="Sum",
            period=300,
            lookback_minutes=720,
        ),
        "eks_apiserver": metric_freshness(
            cw,
            namespace="AWS/EKS",
            metric_name="apiserver_request_total",
            dimensions=[{"Name": "ClusterName", "Value": "fraud-platform-dev-full"}],
            stat="Sum",
            period=300,
            lookback_minutes=720,
        ),
    }
    for name, payload in freshness.items():
        if not bool(payload.get("fresh")):
            blockers.append(f"PHASE9_C_METRIC_STALE:{name}")

    ssm_paths = {
        "aurora_endpoint": "/fraud-platform/dev_full/aurora/endpoint",
        "aurora_reader_endpoint": "/fraud-platform/dev_full/aurora/reader_endpoint",
        "databricks_workspace_url": "/fraud-platform/dev_full/databricks/workspace_url",
        "ig_api_key": "/fraud-platform/dev_full/ig/api_key",
        "mlflow_tracking_uri": "/fraud-platform/dev_full/mlflow/tracking_uri",
        "msk_bootstrap_brokers": "/fraud-platform/dev_full/msk/bootstrap_brokers",
        "sagemaker_model_exec_role_arn": "/fraud-platform/dev_full/sagemaker/model_exec_role_arn",
    }
    ssm_resolution = {}
    for name, path in ssm_paths.items():
        try:
            param = ssm.get_parameter(Name=path, WithDecryption=True)["Parameter"]
            value = str(param.get("Value") or "")
            row = {
                "path": path,
                "type": str(param.get("Type") or ""),
                "resolved": True,
                "placeholder_like": placeholder_flag(value),
            }
            ssm_resolution[name] = row
            if row["placeholder_like"]:
                blockers.append(f"PHASE9_C_PLACEHOLDER_HANDLE:{name}")
        except (BotoCoreError, ClientError) as exc:
            ssm_resolution[name] = {"path": path, "resolved": False, "error": f"{type(exc).__name__}:{exc}"}
            blockers.append(f"PHASE9_C_HANDLE_UNRESOLVED:{name}")

    budget_payload = budgets.describe_budget(AccountId="230372904534", BudgetName="fraud-platform-dev-full-monthly")["Budget"]
    cost_window = ce.get_cost_and_usage(
        TimePeriod={
            "Start": (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat(),
            "End": datetime.now(timezone.utc).date().isoformat(),
        },
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    summary = {
        "phase": "PHASE9",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "source_platform_run_id": args.source_platform_run_id,
        "run_reconstruction": {
            "required_local_files_present": sum(1 for present in local_presence.values() if present),
            "required_local_file_total": len(local_presence),
            "local_presence": local_presence,
            "readable_phase5_refs": len(readable_refs),
            "phase5_ref_total": len([ref for ref in phase5_refs.values() if str(ref or "").startswith("s3://")]),
            "readback_refs": readable_refs,
        },
        "observability": {
            "operations_markdown": operations_markdown,
            "cost_markdown": cost_markdown,
            "present_alarm_names": present_alarm_names,
            "metric_freshness": freshness,
        },
        "identity_and_handles": {
            "ssm_resolution": ssm_resolution,
            "expected_promoted_bundle": dict(phase6_manifest.get("promoted_bundle") or {}),
            "expected_policy_revision": str(phase6_manifest.get("promoted_policy_revision") or ""),
        },
        "learning_basis": {
            "phase5_execution_id": phase5_execution_id,
            "dataset_sampling": dict(phase5_summary.get("dataset_sampling") or {}),
            "metrics": dict(phase5_summary.get("metrics") or {}),
        },
        "cost_posture": {
            "budget": {
                "name": str(budget_payload.get("BudgetName") or ""),
                "limit_amount": str((((budget_payload.get("BudgetLimit") or {}).get("Amount")) or "")),
                "actual_spend": str((((budget_payload.get("CalculatedSpend") or {}).get("ActualSpend") or {}).get("Amount")) or ""),
                "last_updated": str(budget_payload.get("LastUpdatedTime") or ""),
            },
            "latest_cost_window": cost_window.get("ResultsByTime") or [],
        },
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    receipt = {
        "phase": "PHASE9",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "verdict": "PHASE9_OPERATOR_READY" if summary["overall_pass"] else "PHASE9_OPERATOR_HOLD",
        "open_blockers": len(summary["blocker_ids"]),
        "blocker_ids": summary["blocker_ids"],
    }
    dump_json(root / "phase9_stress_operator_surface.json", summary)
    dump_json(root / "phase9_stress_operator_surface_receipt.json", receipt)

    if not summary["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
