#!/usr/bin/env python3
"""Execute a bounded Phase 7 idle-to-zero and restart drill on the EKS runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def run(cmd: list[str], *, timeout: int = 240, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def get_deployments(namespace: str) -> dict[str, int]:
    payload = json.loads(run(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"]).stdout)
    rows: dict[str, int] = {}
    for item in payload.get("items") or []:
        name = str(((item.get("metadata") or {}).get("name")) or "").strip()
        if name:
            rows[name] = int((((item.get("spec") or {}).get("replicas")) or 0))
    return rows


def wait_for_deployments(namespace: str, expected: dict[str, int], *, timeout_seconds: int = 1200) -> list[str]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = json.loads(run(["kubectl", "get", "deploy", "-n", namespace, "-o", "json"]).stdout)
        blockers: list[str] = []
        for item in payload.get("items") or []:
            name = str(((item.get("metadata") or {}).get("name")) or "").strip()
            if name not in expected:
                continue
            desired = expected[name]
            spec_replicas = int((((item.get("spec") or {}).get("replicas")) or 0))
            available = int((((item.get("status") or {}).get("availableReplicas")) or 0))
            if spec_replicas != desired:
                blockers.append(f"DEPLOY_SPEC_DRIFT:{namespace}:{name}:{spec_replicas}:{desired}")
                continue
            if desired > 0 and available < desired:
                blockers.append(f"DEPLOY_NOT_AVAILABLE:{namespace}:{name}:{available}:{desired}")
        if not blockers:
            return []
        time.sleep(10)
    return blockers


def wait_for_node_count(expected_count: int, *, timeout_seconds: int = 1800) -> int:
    deadline = time.time() + timeout_seconds
    last_count = -1
    while time.time() < deadline:
        payload = json.loads(run(["kubectl", "get", "nodes", "-o", "json"]).stdout)
        last_count = len(payload.get("items") or [])
        if last_count == expected_count:
            return last_count
        time.sleep(15)
    return last_count


def wait_for_update(eks: Any, *, cluster_name: str, nodegroup_name: str, update_id: str, timeout_seconds: int = 1800) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = eks.describe_update(name=cluster_name, nodegroupName=nodegroup_name, updateId=update_id)["update"]
        status = str(payload.get("status") or "").strip()
        if status in {"Successful", "Failed", "Cancelled"}:
            return payload
        time.sleep(15)
    raise RuntimeError(f"PHASE7_IDLE_UPDATE_TIMEOUT:{update_id}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute Phase 7 idle/restart drill")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--cluster-name", default="fraud-platform-dev-full")
    ap.add_argument("--nodegroup-name", default="fraud-platform-dev-full-m6f-workers")
    ap.add_argument("--rtdl-namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="fraud-platform-case-labels")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    eks = boto3.client("eks", region_name=args.aws_region)

    nodegroup_before = eks.describe_nodegroup(clusterName=args.cluster_name, nodegroupName=args.nodegroup_name)["nodegroup"]
    scaling_before = dict(nodegroup_before.get("scalingConfig") or {})
    deployments_before = {
        args.rtdl_namespace: get_deployments(args.rtdl_namespace),
        args.case_labels_namespace: get_deployments(args.case_labels_namespace),
        "kube-system": {"coredns": int(get_deployments("kube-system").get("coredns", 0))},
    }

    blockers: list[str] = []
    try:
        for namespace, deployments in (
            (args.rtdl_namespace, deployments_before[args.rtdl_namespace]),
            (args.case_labels_namespace, deployments_before[args.case_labels_namespace]),
        ):
            for name in deployments:
                run(["kubectl", "scale", "deployment", name, "-n", namespace, "--replicas=0"])
        run(["kubectl", "scale", "deployment", "coredns", "-n", "kube-system", "--replicas=0"])
        update = eks.update_nodegroup_config(
            clusterName=args.cluster_name,
            nodegroupName=args.nodegroup_name,
            scalingConfig={"minSize": 0, "desiredSize": 0, "maxSize": int(scaling_before.get("maxSize") or 0)},
        )["update"]
        idle_update = wait_for_update(
            eks,
            cluster_name=args.cluster_name,
            nodegroup_name=args.nodegroup_name,
            update_id=str(update.get("id") or ""),
        )
        blockers.extend(wait_for_deployments(args.rtdl_namespace, {name: 0 for name in deployments_before[args.rtdl_namespace]}))
        blockers.extend(wait_for_deployments(args.case_labels_namespace, {name: 0 for name in deployments_before[args.case_labels_namespace]}))
        blockers.extend(wait_for_deployments("kube-system", {"coredns": 0}))
        node_count_after_idle = wait_for_node_count(0)
        if node_count_after_idle != 0:
            blockers.append(f"PHASE7_IDLE_RESIDUAL_NODES:{node_count_after_idle}")

        restore = eks.update_nodegroup_config(
            clusterName=args.cluster_name,
            nodegroupName=args.nodegroup_name,
            scalingConfig={
                "minSize": int(scaling_before.get("minSize") or 0),
                "desiredSize": int(scaling_before.get("desiredSize") or 0),
                "maxSize": int(scaling_before.get("maxSize") or 0),
            },
        )["update"]
        restore_update = wait_for_update(
            eks,
            cluster_name=args.cluster_name,
            nodegroup_name=args.nodegroup_name,
            update_id=str(restore.get("id") or ""),
        )
        wait_for_node_count(int(scaling_before.get("desiredSize") or 0))
        for namespace, deployments in (
            (args.rtdl_namespace, deployments_before[args.rtdl_namespace]),
            (args.case_labels_namespace, deployments_before[args.case_labels_namespace]),
        ):
            for name, replicas in deployments.items():
                run(["kubectl", "scale", "deployment", name, "-n", namespace, f"--replicas={replicas}"])
        run(["kubectl", "scale", "deployment", "coredns", "-n", "kube-system", f"--replicas={deployments_before['kube-system']['coredns']}"])
        blockers.extend(wait_for_deployments(args.rtdl_namespace, deployments_before[args.rtdl_namespace]))
        blockers.extend(wait_for_deployments(args.case_labels_namespace, deployments_before[args.case_labels_namespace]))
        blockers.extend(wait_for_deployments("kube-system", {"coredns": deployments_before["kube-system"]["coredns"]}))
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"PHASE7_IDLE_DRILL_FAIL:{exc}")
        idle_update = {}
        restore_update = {}
        node_count_after_idle = -1

    payload = {
        "phase": "PHASE7",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "cluster_name": args.cluster_name,
        "nodegroup_name": args.nodegroup_name,
        "scaling_before": scaling_before,
        "deployments_before": deployments_before,
        "idle_update": idle_update,
        "restore_update": restore_update,
        "node_count_after_idle": node_count_after_idle,
        "overall_pass": len(blockers) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    dump_json(root / "phase7_idle_restart_drill.json", payload)
    print(json.dumps(payload, indent=2, default=str))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
