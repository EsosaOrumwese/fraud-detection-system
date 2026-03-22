#!/usr/bin/env python3
"""Safely tear down or restore the dev_full streaming substrate.

This is the standing-cost control for the `infra/terraform/dev_full/streaming`
stack, which materially seats the MSK Serverless cluster and its adjacent
streaming handles. The default posture is conservative:

- teardown refuses to run unless the runtime is already in standby
- restore re-applies only the streaming stack
- both actions write a durable receipt under `runs/`
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


ROOT = Path(__file__).resolve().parents[2]
STREAMING_TF_DIR = ROOT / "infra" / "terraform" / "dev_full" / "streaming"
DEFAULT_BACKEND_CONFIG = STREAMING_TF_DIR / "backend.hcl.example"
DEFAULT_RUN_ROOT = ROOT / "runs" / "dev_substrate" / "dev_full" / "proving_plane" / "run_control"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def run(cmd: list[str], *, timeout: int = 1800, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(
            "command_failed:"
            + " ".join(cmd)
            + f"\nstdout={proc.stdout[-4000:]}\nstderr={proc.stderr[-4000:]}"
        )
    return proc


def tf_cmd(*args: str, timeout: int = 1800, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["terraform", f"-chdir={STREAMING_TF_DIR}", *args], timeout=timeout, check=check)


def resolve_backend_config(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser() if raw_path else DEFAULT_BACKEND_CONFIG
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"backend_config_missing:{candidate}")
    return candidate


def failure_payload(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def tf_init(backend_config: Path) -> dict[str, Any]:
    proc = tf_cmd("init", "-reconfigure", "-backend-config", str(backend_config), timeout=900)
    return {
        "command": f"terraform init -reconfigure -backend-config {backend_config}",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def tf_outputs() -> dict[str, Any]:
    proc = tf_cmd("output", "-json", timeout=240, check=False)
    if proc.returncode != 0:
        return {
            "available": False,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
            "values": {},
        }
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {
            "available": False,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": f"json_decode_failed:{exc}",
            "values": {},
        }
    values: dict[str, Any] = {}
    for key, node in payload.items():
        if isinstance(node, dict) and "value" in node:
            values[key] = node["value"]
    return {"available": True, "returncode": 0, "values": values}


def tf_state_list() -> list[str]:
    proc = tf_cmd("state", "list", timeout=240, check=False)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def find_cluster_by_name(kafka: Any, cluster_name: str) -> dict[str, Any] | None:
    next_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"MaxResults": 100}
        if next_token:
            kwargs["NextToken"] = next_token
        payload = kafka.list_clusters_v2(**kwargs)
        for row in payload.get("ClusterInfoList") or []:
            if str(row.get("ClusterName") or "").strip() == cluster_name:
                return row
        next_token = payload.get("NextToken")
        if not next_token:
            break
    return None


def get_parameter_state(ssm: Any, parameter_name: str) -> dict[str, Any]:
    try:
        payload = ssm.get_parameter(Name=parameter_name, WithDecryption=False)["Parameter"]
        return {
            "present": True,
            "name": str(payload.get("Name") or "").strip(),
            "type": str(payload.get("Type") or "").strip(),
            "version": int(payload.get("Version") or 0),
            "last_modified": str(payload.get("LastModifiedDate") or ""),
        }
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code") or "").strip()
        if code == "ParameterNotFound":
            return {"present": False, "code": code}
        raise


def runtime_standby_posture(
    *,
    region: str,
    cluster_name: str,
    nodegroup_name: str,
    aurora_cluster_id: str,
) -> dict[str, Any]:
    eks = boto3.client("eks", region_name=region)
    rds = boto3.client("rds", region_name=region)

    blockers: list[str] = []
    desired = 0
    minimum = 0
    maximum = 0
    try:
        nodegroup = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup_name)["nodegroup"]
        scaling = dict(nodegroup.get("scalingConfig") or {})
        desired = int(scaling.get("desiredSize") or 0)
        minimum = int(scaling.get("minSize") or 0)
        maximum = int(scaling.get("maxSize") or 0)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code") or "").strip()
        blockers.append(f"EKS_NODEGROUP_DESCRIBE_FAILED:{code or 'UNKNOWN'}")
    except BotoCoreError as exc:
        blockers.append(f"EKS_NODEGROUP_DESCRIBE_FAILED:{type(exc).__name__}")

    cluster_status = ""
    try:
        rds_payload = rds.describe_db_clusters(DBClusterIdentifier=aurora_cluster_id)["DBClusters"][0]
        cluster_status = str(rds_payload.get("Status") or "").strip().lower()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code") or "").strip()
        cluster_status = f"describe_failed:{code or 'UNKNOWN'}"
        blockers.append(f"AURORA_DESCRIBE_FAILED:{code or 'UNKNOWN'}")
    except BotoCoreError as exc:
        cluster_status = f"describe_failed:{type(exc).__name__}"
        blockers.append(f"AURORA_DESCRIBE_FAILED:{type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        cluster_status = f"describe_failed:{exc}"
        blockers.append(f"AURORA_DESCRIBE_FAILED:{type(exc).__name__}")

    if desired != 0:
        blockers.append(f"EKS_NODEGROUP_DESIRED_NOT_ZERO:{desired}")
    if minimum != 0:
        blockers.append(f"EKS_NODEGROUP_MIN_NOT_ZERO:{minimum}")
    if cluster_status not in {"stopped", "stopping"}:
        blockers.append(f"AURORA_NOT_STOPPED:{cluster_status or 'unknown'}")

    return {
        "cluster_name": cluster_name,
        "nodegroup_name": nodegroup_name,
        "aurora_cluster_id": aurora_cluster_id,
        "nodegroup_scaling": {"min": minimum, "desired": desired, "max": maximum},
        "aurora_status": cluster_status,
        "standby_ready": len(blockers) == 0,
        "blocker_ids": blockers,
    }


def build_execution_root(run_root: Path, prefix: str, execution_id: str | None) -> Path:
    eid = execution_id.strip() if execution_id else ""
    if not eid:
        eid = f"{prefix}_{compact_timestamp()}"
    return run_root / eid


def do_teardown(args: argparse.Namespace) -> int:
    kafka = boto3.client("kafka", region_name=args.aws_region)
    ssm = boto3.client("ssm", region_name=args.aws_region)
    execution_root = build_execution_root(Path(args.run_control_root), "streaming_teardown", args.execution_id)
    execution_root.mkdir(parents=True, exist_ok=True)
    receipt_path = execution_root / "streaming_teardown_receipt.json"

    receipt: dict[str, Any] = {
        "action": "teardown",
        "generated_at_utc": now_utc(),
        "execution_root": str(execution_root),
        "terraform_dir": str(STREAMING_TF_DIR),
        "aws_region": args.aws_region,
        "precondition_force": bool(args.force),
    }
    try:
        backend_config = resolve_backend_config(args.backend_config)
        receipt["backend_config"] = str(backend_config)

        if args.force:
            standby = {
                "standby_ready": True,
                "skipped": True,
                "reason": "force_bypass",
                "cluster_name": args.eks_cluster_name,
                "nodegroup_name": args.nodegroup_name,
                "aurora_cluster_id": args.aurora_cluster_id,
                "blocker_ids": [],
            }
        else:
            standby = runtime_standby_posture(
                region=args.aws_region,
                cluster_name=args.eks_cluster_name,
                nodegroup_name=args.nodegroup_name,
                aurora_cluster_id=args.aurora_cluster_id,
            )
        receipt["runtime_standby_precheck"] = standby
        if not args.force and not standby["standby_ready"]:
            receipt["overall_pass"] = False
            receipt["blocker_ids"] = ["STREAMING_TEARDOWN_PRECONDITION_FAILED", *standby["blocker_ids"]]
            dump_json(receipt_path, receipt)
            return 1

        receipt["terraform_init"] = tf_init(backend_config)
        outputs_before = tf_outputs()
        receipt["terraform_outputs_before"] = outputs_before

        values = outputs_before.get("values") or {}
        cluster_name = str(values.get("msk_cluster_name") or args.msk_cluster_name).strip()
        cluster_arn = str(values.get("msk_cluster_arn") or "").strip()
        param_name = str(values.get("ssm_msk_bootstrap_brokers_path") or args.ssm_bootstrap_param).strip()

        cluster_before = None
        try:
            cluster_before = find_cluster_by_name(kafka, cluster_name)
        except (BotoCoreError, ClientError) as exc:
            cluster_before = {"lookup_error": str(exc)}
        receipt["cluster_before"] = cluster_before
        try:
            receipt["ssm_parameter_before"] = get_parameter_state(ssm, param_name)
        except (BotoCoreError, ClientError) as exc:
            receipt["ssm_parameter_before"] = {"present": False, "lookup_error": str(exc)}

        destroy = tf_cmd(
            "destroy",
            "-auto-approve",
            "-input=false",
            "-lock-timeout=5m",
            timeout=args.destroy_timeout_seconds,
        )
        receipt["terraform_destroy"] = {
            "returncode": destroy.returncode,
            "stdout_tail": destroy.stdout[-4000:],
            "stderr_tail": destroy.stderr[-4000:],
        }

        time.sleep(10)
        try:
            cluster_after = find_cluster_by_name(kafka, cluster_name)
        except (BotoCoreError, ClientError) as exc:
            cluster_after = {"lookup_error": str(exc)}
        receipt["cluster_after"] = cluster_after
        try:
            receipt["ssm_parameter_after"] = get_parameter_state(ssm, param_name)
        except (BotoCoreError, ClientError) as exc:
            receipt["ssm_parameter_after"] = {"present": False, "lookup_error": str(exc)}
        receipt["terraform_state_after"] = tf_state_list()

        blockers: list[str] = []
        if cluster_after:
            blockers.append("MSK_CLUSTER_STILL_PRESENT_AFTER_DESTROY")
        if receipt["ssm_parameter_after"].get("present"):
            blockers.append("MSK_BOOTSTRAP_PARAM_STILL_PRESENT_AFTER_DESTROY")
        if receipt["terraform_state_after"]:
            blockers.append("STREAMING_TF_STATE_NOT_EMPTY_AFTER_DESTROY")

        receipt["cluster_arn_before"] = cluster_arn
        receipt["overall_pass"] = len(blockers) == 0
        receipt["blocker_ids"] = blockers
        dump_json(receipt_path, receipt)
        return 0 if receipt["overall_pass"] else 1
    except Exception as exc:  # noqa: BLE001
        receipt["overall_pass"] = False
        receipt["blocker_ids"] = ["STREAMING_TEARDOWN_EXECUTION_FAILED"]
        receipt["exception"] = failure_payload(exc)
        dump_json(receipt_path, receipt)
        return 1


def do_restore(args: argparse.Namespace) -> int:
    kafka = boto3.client("kafka", region_name=args.aws_region)
    ssm = boto3.client("ssm", region_name=args.aws_region)
    execution_root = build_execution_root(Path(args.run_control_root), "streaming_restore", args.execution_id)
    execution_root.mkdir(parents=True, exist_ok=True)
    receipt_path = execution_root / "streaming_restore_receipt.json"

    receipt: dict[str, Any] = {
        "action": "restore",
        "generated_at_utc": now_utc(),
        "execution_root": str(execution_root),
        "terraform_dir": str(STREAMING_TF_DIR),
        "aws_region": args.aws_region,
    }
    try:
        backend_config = resolve_backend_config(args.backend_config)
        receipt["backend_config"] = str(backend_config)

        receipt["terraform_init"] = tf_init(backend_config)
        apply = tf_cmd("apply", "-auto-approve", "-input=false", "-lock-timeout=5m", timeout=args.apply_timeout_seconds)
        receipt["terraform_apply"] = {
            "returncode": apply.returncode,
            "stdout_tail": apply.stdout[-4000:],
            "stderr_tail": apply.stderr[-4000:],
        }

        outputs_after = tf_outputs()
        receipt["terraform_outputs_after"] = outputs_after
        values = outputs_after.get("values") or {}
        cluster_name = str(values.get("msk_cluster_name") or args.msk_cluster_name).strip()
        param_name = str(values.get("ssm_msk_bootstrap_brokers_path") or args.ssm_bootstrap_param).strip()

        try:
            cluster_after = find_cluster_by_name(kafka, cluster_name)
        except (BotoCoreError, ClientError) as exc:
            cluster_after = {"lookup_error": str(exc)}
        receipt["cluster_after"] = cluster_after

        try:
            receipt["ssm_parameter_after"] = get_parameter_state(ssm, param_name)
        except (BotoCoreError, ClientError) as exc:
            receipt["ssm_parameter_after"] = {"present": False, "lookup_error": str(exc)}

        blockers: list[str] = []
        state = str((cluster_after or {}).get("State") or "").strip()
        if not cluster_after:
            blockers.append("MSK_CLUSTER_MISSING_AFTER_RESTORE")
        elif state not in {"ACTIVE", "CREATING"}:
            blockers.append(f"MSK_CLUSTER_UNEXPECTED_STATE_AFTER_RESTORE:{state or 'unknown'}")
        if not receipt["ssm_parameter_after"].get("present"):
            blockers.append("MSK_BOOTSTRAP_PARAM_MISSING_AFTER_RESTORE")

        receipt["overall_pass"] = len(blockers) == 0
        receipt["blocker_ids"] = blockers
        dump_json(receipt_path, receipt)
        return 0 if receipt["overall_pass"] else 1
    except Exception as exc:  # noqa: BLE001
        receipt["overall_pass"] = False
        receipt["blocker_ids"] = ["STREAMING_RESTORE_EXECUTION_FAILED"]
        receipt["exception"] = failure_payload(exc)
        dump_json(receipt_path, receipt)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely tear down or restore the dev_full streaming substrate")
    sub = ap.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--aws-region", default="eu-west-2")
    common.add_argument("--run-control-root", default=str(DEFAULT_RUN_ROOT))
    common.add_argument("--execution-id", default="")
    common.add_argument("--backend-config", default=str(DEFAULT_BACKEND_CONFIG))
    common.add_argument("--msk-cluster-name", default="fraud-platform-dev-full-msk")
    common.add_argument("--ssm-bootstrap-param", default="/fraud-platform/dev_full/msk/bootstrap_brokers")

    teardown = sub.add_parser("teardown", parents=[common], help="Destroy the streaming stack after standby precheck")
    teardown.add_argument("--eks-cluster-name", default="fraud-platform-dev-full")
    teardown.add_argument("--nodegroup-name", default="fraud-platform-dev-full-m6f-workers")
    teardown.add_argument("--aurora-cluster-id", default="fraud-platform-dev-full-aurora")
    teardown.add_argument("--destroy-timeout-seconds", type=int, default=3600)
    teardown.add_argument("--force", action="store_true", help="Bypass standby precheck and destroy anyway")

    restore = sub.add_parser("restore", parents=[common], help="Re-apply the streaming stack")
    restore.add_argument("--apply-timeout-seconds", type=int, default=3600)

    args = ap.parse_args()
    if args.command == "teardown":
        return do_teardown(args)
    if args.command == "restore":
        return do_restore(args)
    raise SystemExit("unsupported_command")


if __name__ == "__main__":
    raise SystemExit(main())
