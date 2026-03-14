#!/usr/bin/env python3
"""Bounded Phase 7 ops/governance/meta assessment on the accepted Phase 6 chain."""

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


def s3_read_json(s3: Any, ref: str) -> dict[str, Any]:
    bucket, key = parse_s3_ref(ref)
    payload = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"json_not_object:{ref}")
    return value


def s3_readable(s3: Any, ref: str) -> bool:
    bucket, key = parse_s3_ref(ref)
    s3.head_object(Bucket=bucket, Key=key)
    return True


def run(cmd: list[str], *, timeout: int = 240, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def select_running_pod(namespace: str, app: str) -> str:
    payload = json.loads(run(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={app}", "-o", "json"]).stdout)
    for item in payload.get("items") or []:
        status = dict(item.get("status") or {})
        if str(status.get("phase") or "").strip() != "Running":
            continue
        conditions = list(status.get("conditions") or [])
        ready = any(
            str(cond.get("type") or "").strip() == "Ready" and str(cond.get("status") or "").strip() == "True"
            for cond in conditions
        )
        if ready:
            name = str(((item.get("metadata") or {}).get("name")) or "").strip()
            if name:
                return name
    raise RuntimeError(f"PHASE7_POD_UNAVAILABLE:{namespace}:{app}")


REMOTE_RUNTIME_DRIFT_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.decision_fabric.registry import RegistryResolutionPolicy, RegistryScopeKey, RegistrySnapshot
from fraud_detection.decision_fabric.worker import load_worker_config

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
snapshot = RegistrySnapshot.load(cfg.registry_snapshot_ref)
policy = RegistryResolutionPolicy.load(cfg.registry_policy_ref)
fraud_scope = RegistryScopeKey(environment="dev_full", mode="fraud", bundle_slot="primary").canonical_key()

record = snapshot.records_by_scope.get(fraud_scope)
fallback = policy.explicit_fallback_by_scope.get(fraud_scope)
print(json.dumps({
    "registry_snapshot_ref": str(cfg.registry_snapshot_ref),
    "registry_policy_ref": str(cfg.registry_policy_ref),
    "policy_id": policy.policy_rev.policy_id,
    "policy_revision": policy.policy_rev.revision,
    "fraud_primary": None if record is None else {
        "bundle_id": record.bundle_ref["bundle_id"],
        "bundle_version": record.bundle_ref["bundle_version"],
        "registry_ref": record.bundle_ref["registry_ref"],
    },
    "fraud_policy_fallback": None if fallback is None else dict(fallback),
}))
"""


def exec_json(namespace: str, pod: str, script: str, env_map: dict[str, str]) -> tuple[dict[str, Any], str]:
    env_bits = [f"{key}={value}" for key, value in sorted(env_map.items())]
    proc = run(["kubectl", "exec", "-n", namespace, pod, "--", "env", *env_bits, "python", "-c", script], check=False)
    if proc.returncode != 0:
        return {}, proc.stderr.strip() or proc.stdout.strip()
    text = proc.stdout.strip()
    if not text:
        return {}, ""
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return {}, f"json_decode_error:{exc}"


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
    ap = argparse.ArgumentParser(description="Bounded Phase 7 assessment")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--source-phase6-execution-id", required=True)
    ap.add_argument("--source-platform-run-id", required=True)
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--rtdl-namespace", default="fraud-platform-rtdl")
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    source_root = Path(args.run_control_root) / args.source_phase6_execution_id

    s3 = boto3.client("s3", region_name=args.aws_region)
    cw = boto3.client("cloudwatch", region_name=args.aws_region)
    cw_billing = boto3.client("cloudwatch", region_name="us-east-1")
    ssm = boto3.client("ssm", region_name=args.aws_region)
    budgets = boto3.client("budgets", region_name="us-east-1")
    ce = boto3.client("ce", region_name="us-east-1")
    eks = boto3.client("eks", region_name=args.aws_region)

    source_receipt = load_json(source_root / "phase6_learning_coupled_receipt.json")
    source_summary = load_json(source_root / "phase6_learning_coupled_summary.json")
    source_manifest = load_json(source_root / "phase6_registry_surface_manifest.json")

    blockers: list[str] = []
    idle_drill_path = root / "phase7_idle_restart_drill.json"
    idle_drill = load_json(idle_drill_path) if idle_drill_path.exists() else None
    if idle_drill is None:
        blockers.append("PHASE7_C_IDLE_DRILL_MISSING")
    elif not bool(idle_drill.get("overall_pass")):
        blockers.append("PHASE7_C_IDLE_DRILL_NOT_GREEN")

    alert_drill_path = root / "phase7_alert_runbook_drill.json"
    alert_drill = load_json(alert_drill_path) if alert_drill_path.exists() else None
    if alert_drill is None:
        blockers.append("PHASE7_B_ALERT_DRILL_MISSING")
    elif not bool(alert_drill.get("overall_pass")):
        blockers.append("PHASE7_B_ALERT_DRILL_NOT_GREEN")

    ml_day2_path = root / "phase7_ml_day2_operator_surface.json"
    ml_day2 = load_json(ml_day2_path) if ml_day2_path.exists() else None
    if ml_day2 is None:
        blockers.append("PHASE7_C_ML_DAY2_SURFACE_MISSING")
    elif not bool(ml_day2.get("overall_pass")):
        blockers.append("PHASE7_C_ML_DAY2_SURFACE_NOT_GREEN")

    required_local = [
        "phase6_learning_coupled_receipt.json",
        "phase6_learning_coupled_summary.json",
        "phase6_coupled_envelope_summary.json",
        "phase6_registry_surface_manifest.json",
        "phase6_coupled_cost_receipt.json",
        "phase6_coupled_scorecard.json",
        "g3a_runtime_materialization_summary.json",
        "phase6_candidate_bundle_probe.json",
        "phase6_rollback_bundle_probe.json",
        "phase6_restore_bundle_probe.json",
    ]
    local_presence = {name: (source_root / name).exists() for name in required_local}
    for name, present in local_presence.items():
        if not present:
            blockers.append(f"PHASE7_A_MISSING_LOCAL_EVIDENCE:{name}")

    readable_refs = {}
    phase5_refs = dict((source_summary.get("learning_authority") or {}).get("phase5_refs") or {})
    for key, ref in phase5_refs.items():
        text = str(ref or "").strip()
        if not text.startswith("s3://"):
            continue
        try:
            if text.endswith(".json"):
                s3_read_json(s3, text)
            else:
                s3_readable(s3, text)
            readable_refs[key] = text
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError):
            blockers.append(f"PHASE7_A_EVIDENCE_READBACK_FAIL:{key}")

    if str(source_receipt.get("verdict") or "").strip() != "PHASE6_READY":
        blockers.append("PHASE7_A_SOURCE_VERDICT_NOT_GREEN")

    operations_body = dashboard_body(cw, "fraud-platform-dev-full-operations")
    cost_body = dashboard_body(cw, "fraud-platform-dev-full-cost-guardrail")
    operations_widgets = list(operations_body.get("widgets") or [])
    cost_widgets = list(cost_body.get("widgets") or [])
    operations_markdown = dashboard_markdown_refs(operations_body)
    cost_markdown = dashboard_markdown_refs(cost_body)
    if len(operations_widgets) < 5:
        blockers.append("PHASE7_B_OPERATIONS_DASHBOARD_TOO_THIN")
    if len(cost_widgets) < 3:
        blockers.append("PHASE7_B_COST_DASHBOARD_TOO_THIN")
    if not Path(RUNBOOK_PATH).exists():
        blockers.append("PHASE7_B_RUNBOOK_MISSING")
    if not any(RUNBOOK_PATH in text for text in operations_markdown):
        blockers.append("PHASE7_B_OPERATIONS_RUNBOOK_LINK_MISSING")
    if not any(RUNBOOK_PATH in text for text in cost_markdown):
        blockers.append("PHASE7_B_COST_RUNBOOK_LINK_MISSING")

    alarms = cw.describe_alarms(AlarmNamePrefix="fraud-platform-dev-full-").get("MetricAlarms") or []
    alarms_billing = cw_billing.describe_alarms(AlarmNamePrefix="fraud-platform-dev-full-").get("MetricAlarms") or []
    required_alarms = [
        "fraud-platform-dev-full-ig-lambda-errors",
        "fraud-platform-dev-full-ig-lambda-throttles",
        "fraud-platform-dev-full-ig-apigw-5xx",
        "fraud-platform-dev-full-eks-unschedulable-pods",
        "fraud-platform-dev-full-eks-apiserver-5xx",
        "fraud-platform-dev-full-billing-estimated-charges",
    ]
    present_alarm_names = sorted(
        set(
            str(row.get("AlarmName") or "").strip()
            for row in [*alarms, *alarms_billing]
            if str(row.get("AlarmName") or "").strip()
        )
    )
    for name in required_alarms:
        if name not in present_alarm_names:
            blockers.append(f"PHASE7_B_ALARM_MISSING:{name}")

    freshness = {
        "lambda_duration": metric_freshness(
            cw,
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions=[{"Name": "FunctionName", "Value": "fraud-platform-dev-full-ig-handler"}],
            stat="Maximum",
            period=300,
            lookback_minutes=360,
        ),
        "apigw_count": metric_freshness(
            cw,
            namespace="AWS/ApiGateway",
            metric_name="Count",
            dimensions=[{"Name": "ApiId", "Value": "pd7rtjze95"}, {"Name": "Stage", "Value": "v1"}],
            stat="Sum",
            period=300,
            lookback_minutes=360,
        ),
        "eks_apiserver": metric_freshness(
            cw,
            namespace="AWS/EKS",
            metric_name="apiserver_request_total",
            dimensions=[{"Name": "ClusterName", "Value": "fraud-platform-dev-full"}],
            stat="Sum",
            period=300,
            lookback_minutes=360,
        ),
    }
    for name, payload in freshness.items():
        if not bool(payload.get("fresh")):
            blockers.append(f"PHASE7_B_METRIC_STALE:{name}")

    ssm_paths = {
        "aurora_endpoint": "/fraud-platform/dev_full/aurora/endpoint",
        "aurora_reader_endpoint": "/fraud-platform/dev_full/aurora/reader_endpoint",
        "aurora_username": "/fraud-platform/dev_full/aurora/username",
        "aurora_password": "/fraud-platform/dev_full/aurora/password",
        "databricks_token": "/fraud-platform/dev_full/databricks/token",
        "databricks_workspace_url": "/fraud-platform/dev_full/databricks/workspace_url",
        "ig_api_key": "/fraud-platform/dev_full/ig/api_key",
        "mlflow_tracking_uri": "/fraud-platform/dev_full/mlflow/tracking_uri",
        "msk_bootstrap_brokers": "/fraud-platform/dev_full/msk/bootstrap_brokers",
        "redis_endpoint": "/fraud-platform/dev_full/redis/endpoint",
        "sagemaker_model_exec_role_arn": "/fraud-platform/dev_full/sagemaker/model_exec_role_arn",
    }
    ssm_resolution: dict[str, dict[str, Any]] = {}
    for key, path in ssm_paths.items():
        try:
            parameter = ssm.get_parameter(Name=path, WithDecryption=True)["Parameter"]
            value = str(parameter.get("Value") or "")
            ssm_resolution[key] = {
                "path": path,
                "type": str(parameter.get("Type") or ""),
                "resolved": True,
                "placeholder_like": placeholder_flag(value),
            }
            if placeholder_flag(value):
                blockers.append(f"PHASE7_D_PLACEHOLDER_HANDLE:{key}")
        except (BotoCoreError, ClientError):
            ssm_resolution[key] = {"path": path, "resolved": False}
            blockers.append(f"PHASE7_D_HANDLE_RESOLUTION_FAIL:{key}")

    drift_probe = {}
    drift_probe_error = ""
    try:
        df_pod = select_running_pod(args.rtdl_namespace, "fp-pr3-df")
        drift_probe, drift_probe_error = exec_json(
            args.rtdl_namespace,
            df_pod,
            REMOTE_RUNTIME_DRIFT_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
    except Exception as exc:  # noqa: BLE001
        drift_probe_error = str(exc)
    if drift_probe_error:
        blockers.append(f"PHASE7_D_RUNTIME_DRIFT_PROBE_FAIL:{drift_probe_error}")
    else:
        expected = dict(source_manifest.get("promoted_bundle") or {})
        actual = dict(drift_probe.get("fraud_primary") or {})
        if actual.get("bundle_id") != expected.get("bundle_id") or actual.get("bundle_version") != expected.get("bundle_version"):
            blockers.append("PHASE7_D_ACTIVE_BUNDLE_DRIFT")
        if str(drift_probe.get("policy_revision") or "").strip() != str(source_manifest.get("promoted_policy_revision") or "").strip():
            blockers.append("PHASE7_D_ACTIVE_POLICY_DRIFT")

    budget = dict(budgets.describe_budget(AccountId="230372904534", BudgetName="fraud-platform-dev-full-monthly").get("Budget") or {})
    budget_last_updated = str(budget.get("LastUpdatedTime") or "")
    budget_surface_fresh = bool(budget_last_updated)
    if not budget_surface_fresh:
        blockers.append("PHASE7_B_BUDGET_SURFACE_STALE")

    nodegroup = eks.describe_nodegroup(
        clusterName="fraud-platform-dev-full", nodegroupName="fraud-platform-dev-full-m6f-workers"
    )["nodegroup"]
    deployments = json.loads(run(["kubectl", "get", "deploy", "-A", "-o", "json"]).stdout)
    active_deployments = [
        {
            "namespace": str(((item.get("metadata") or {}).get("namespace")) or ""),
            "name": str(((item.get("metadata") or {}).get("name")) or ""),
            "replicas": int((((item.get("spec") or {}).get("replicas")) or 0)),
        }
        for item in deployments.get("items") or []
        if int((((item.get("spec") or {}).get("replicas")) or 0)) > 0
    ]
    costs = ce.get_cost_and_usage(
        TimePeriod={
            "Start": (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat(),
            "End": datetime.now(timezone.utc).date().isoformat(),
        },
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )

    summary = {
        "phase": "PHASE7",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "source_platform_run_id": args.source_platform_run_id,
        "run_reconstruction": {
            "required_local_files_present": sum(1 for present in local_presence.values() if present),
            "required_local_file_total": len(local_presence),
            "local_presence": local_presence,
            "readable_phase5_refs": len(readable_refs),
            "phase5_ref_total": len([value for value in phase5_refs.values() if str(value or "").startswith("s3://")]),
            "readback_refs": readable_refs,
        },
        "observability": {
            "operations_dashboard_widgets": len(operations_widgets),
            "cost_dashboard_widgets": len(cost_widgets),
            "operations_markdown": operations_markdown,
            "cost_markdown": cost_markdown,
            "present_alarm_names": present_alarm_names,
            "metric_freshness": freshness,
            "budget_surface_fresh": budget_surface_fresh,
            "budget_last_updated": budget_last_updated,
        },
        "identity_and_drift": {
            "ssm_resolution": ssm_resolution,
            "runtime_drift_probe": drift_probe,
            "runtime_drift_probe_error": drift_probe_error,
            "expected_promoted_bundle": dict(source_manifest.get("promoted_bundle") or {}),
            "expected_policy_revision": str(source_manifest.get("promoted_policy_revision") or ""),
        },
        "cost_posture": {
            "budget": {
                "name": str(budget.get("BudgetName") or ""),
                "limit_amount": ((budget.get("BudgetLimit") or {}).get("Amount")),
                "actual_spend": ((((budget.get("CalculatedSpend") or {}).get("ActualSpend")) or {}).get("Amount")),
                "last_updated": str(budget.get("LastUpdatedTime") or ""),
            },
            "nodegroup_scaling": dict(nodegroup.get("scalingConfig") or {}),
            "active_deployments": active_deployments,
            "latest_cost_window": costs.get("ResultsByTime") or [],
        },
        "idle_restart_drill": idle_drill,
        "alert_runbook_drill": alert_drill,
        "ml_day2_operator_surface": ml_day2,
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    receipt = {
        "phase": "PHASE7",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "source_phase6_execution_id": args.source_phase6_execution_id,
        "verdict": "PHASE7_READY" if summary["overall_pass"] else "PHASE7_HOLD_REMEDIATE",
        "next_phase": "PHASE8" if summary["overall_pass"] else "PHASE7",
        "open_blockers": len(summary["blocker_ids"]),
        "blocker_ids": summary["blocker_ids"],
    }
    dump_json(root / "phase7_ops_gov_meta_summary.json", summary)
    dump_json(root / "phase7_ops_gov_meta_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))
    if not summary["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
