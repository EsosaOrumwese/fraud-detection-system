#!/usr/bin/env python3
"""Run the PR3-S4 learning proof inside the VPC via a short-lived EKS job."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
WORKER_PATH = Path("scripts/dev_substrate/pr3_s4_learning_bound.py")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_registry(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    pattern = re.compile(r"^\*\s*`([^`]+)`")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if not match:
            continue
        body = match.group(1)
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        payload[key.strip()] = value.strip().strip('"')
    return payload


def resolve_task_image(*, family: str, region: str) -> str:
    ecs = boto3.client("ecs", region_name=region)
    resp = ecs.describe_task_definition(taskDefinition=family)
    task_def = resp.get("taskDefinition", {})
    containers = list(task_def.get("containerDefinitions", []) or [])
    if not containers:
        raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:TASKDEF_EMPTY:{family}")
    image = str(containers[0].get("image", "")).strip()
    if not image:
        raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:TASKDEF_IMAGE_EMPTY:{family}")
    return image


def run(cmd: list[str], *, input_text: str | None = None, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def kubectl_apply(document: dict[str, Any]) -> None:
    run(["kubectl", "apply", "-f", "-"], input_text=json.dumps(document), timeout=300, check=True)


def kubectl_delete(kind: str, name: str, namespace: str | None = None) -> None:
    cmd = ["kubectl", "delete", kind, name, "--ignore-not-found=true"]
    if namespace:
        cmd.extend(["-n", namespace])
    run(cmd, timeout=180, check=False)


def namespace_manifest(name: str) -> dict[str, Any]:
    return {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": name}}


def service_account_manifest(namespace: str, name: str, role_arn: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "annotations": {"eks.amazonaws.com/role-arn": role_arn},
        },
    }


def config_map_manifest(namespace: str, name: str, data: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": namespace},
        "data": data,
    }


def job_manifest(
    *,
    namespace: str,
    name: str,
    image: str,
    service_account_name: str,
    config_map_name: str,
    pr3_execution_id: str,
    platform_run_id: str,
    scenario_run_id: str,
    aws_region: str,
) -> dict[str, Any]:
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "fp.phase": "PR3",
                "fp.state": "S4",
                "fp.component": "learning-bound",
            },
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 300,
            "template": {
                "metadata": {
                    "labels": {
                        "job-name": name,
                        "fp.phase": "PR3",
                        "fp.state": "S4",
                        "fp.component": "learning-bound",
                    }
                },
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": service_account_name,
                    "containers": [
                        {
                            "name": "learning-bound",
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": [
                                "python",
                                "/learning/pr3_s4_learning_bound.py",
                                "--pr3-execution-id",
                                pr3_execution_id,
                                "--platform-run-id",
                                platform_run_id,
                                "--scenario-run-id",
                                scenario_run_id,
                                "--aws-region",
                                aws_region,
                            ],
                            "env": [
                                {"name": "AWS_REGION", "value": aws_region},
                                {"name": "AWS_DEFAULT_REGION", "value": aws_region},
                                {"name": "PLATFORM_RUN_ID", "value": platform_run_id},
                                {"name": "ACTIVE_PLATFORM_RUN_ID", "value": platform_run_id},
                                {"name": "ACTIVE_SCENARIO_RUN_ID", "value": scenario_run_id},
                                {"name": "PR3_REGISTRY_PATH", "value": "/learning/dev_full_handles.registry.v0.md"},
                            ],
                            "volumeMounts": [
                                {
                                    "name": "learning-script",
                                    "mountPath": "/learning",
                                    "readOnly": True,
                                }
                            ],
                            "resources": {
                                "requests": {"cpu": "1000m", "memory": "2Gi"},
                                "limits": {"cpu": "2", "memory": "4Gi"},
                            },
                        }
                    ],
                    "volumes": [
                        {
                            "name": "learning-script",
                            "configMap": {"name": config_map_name},
                        }
                    ],
                },
            },
        },
    }


def get_job_status(namespace: str, name: str) -> dict[str, Any]:
    proc = run(["kubectl", "get", "job", name, "-n", namespace, "-o", "json"], timeout=60, check=True)
    return json.loads(proc.stdout or "{}")


def get_pod_name(namespace: str, job_name: str) -> str:
    proc = run(["kubectl", "get", "pods", "-n", namespace, "-l", f"job-name={job_name}", "-o", "json"], timeout=60, check=True)
    payload = json.loads(proc.stdout or "{}")
    items = list(payload.get("items", []) or [])
    if not items:
        return ""
    return str(items[0].get("metadata", {}).get("name", "")).strip()


def get_pod_payload(namespace: str, pod_name: str) -> dict[str, Any]:
    if not pod_name:
        return {}
    proc = run(["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"], timeout=60, check=True)
    return json.loads(proc.stdout or "{}")


def pod_logs(namespace: str, pod_name: str) -> str:
    if not pod_name:
        return ""
    proc = run(["kubectl", "logs", pod_name, "-n", namespace], timeout=180, check=False)
    return (proc.stdout or proc.stderr or "").strip()


def pod_describe(namespace: str, pod_name: str) -> str:
    if not pod_name:
        return ""
    proc = run(["kubectl", "describe", "pod", pod_name, "-n", namespace], timeout=180, check=False)
    return (proc.stdout or proc.stderr or "").strip()


def wait_for_job(namespace: str, name: str, *, timeout_seconds: int) -> tuple[bool, dict[str, Any]]:
    deadline = time.time() + max(timeout_seconds, 30)
    latest: dict[str, Any] = {}
    while time.time() < deadline:
        latest = get_job_status(namespace, name)
        status = latest.get("status", {}) if isinstance(latest, dict) else {}
        if int(status.get("succeeded", 0) or 0) >= 1:
            return True, latest
        if int(status.get("failed", 0) or 0) >= 1:
            return False, latest
        time.sleep(5)
    return False, latest


def parse_summary_from_logs(log_text: str) -> dict[str, Any]:
    for line in reversed([row.strip() for row in log_text.splitlines() if row.strip()]):
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("phase") == "PR3" and payload.get("state") == "S4":
            return payload
    return {}


def stable_suffix(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:10]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr3-execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    parser.add_argument("--summary-name", default="g3a_correctness_learning_summary.json")
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument("--namespace", default="fraud-platform-rtdl")
    parser.add_argument("--service-account-name", default="rtdl")
    parser.add_argument("--service-account-role-arn", default="")
    parser.add_argument("--wsp-task-family", default="fraud-platform-dev-full-wsp-ephemeral")
    parser.add_argument("--image-uri", default="")
    parser.add_argument("--job-timeout-seconds", type=int, default=1200)
    args = parser.parse_args()

    run_root = Path(args.run_control_root) / args.pr3_execution_id
    summary_path = run_root / args.summary_name
    blockers: list[str] = []
    config_map_name = ""
    job_name = ""
    pod_name = ""
    image_uri = ""
    role_arn = ""

    try:
        if not WORKER_PATH.exists():
            raise RuntimeError(f"PR3.B29_LEARNING_BOUND_FAIL:WORKER_SCRIPT_MISSING:{WORKER_PATH}")
        registry = parse_registry(REGISTRY_PATH)
        image_uri = str(args.image_uri).strip() or resolve_task_image(
            family=args.wsp_task_family,
            region=args.aws_region,
        )
        role_arn = str(args.service_account_role_arn).strip() or str(registry.get("ROLE_EKS_IRSA_RTDL", "")).strip()
        if not role_arn:
            raise RuntimeError("PR3.B29_LEARNING_BOUND_FAIL:IRSA_ROLE_UNRESOLVED")

        suffix = stable_suffix(args.pr3_execution_id, args.platform_run_id, args.scenario_run_id)
        config_map_name = f"pr3-s4-learning-script-{suffix}"
        job_name = f"pr3-s4-learning-{suffix}"

        kubectl_apply(namespace_manifest(args.namespace))
        kubectl_apply(service_account_manifest(args.namespace, args.service_account_name, role_arn))
        kubectl_apply(
            config_map_manifest(
                args.namespace,
                config_map_name,
                {
                    "pr3_s4_learning_bound.py": WORKER_PATH.read_text(encoding="utf-8"),
                    "dev_full_handles.registry.v0.md": REGISTRY_PATH.read_text(encoding="utf-8"),
                },
            )
        )
        kubectl_apply(
            job_manifest(
                namespace=args.namespace,
                name=job_name,
                image=image_uri,
                service_account_name=args.service_account_name,
                config_map_name=config_map_name,
                pr3_execution_id=args.pr3_execution_id,
                platform_run_id=args.platform_run_id,
                scenario_run_id=args.scenario_run_id,
                aws_region=args.aws_region,
            )
        )

        job_ok, job_payload = wait_for_job(args.namespace, job_name, timeout_seconds=args.job_timeout_seconds)
        pod_name = get_pod_name(args.namespace, job_name)
        pod_payload = get_pod_payload(args.namespace, pod_name)
        log_text = pod_logs(args.namespace, pod_name)
        describe_text = pod_describe(args.namespace, pod_name)
        summary = parse_summary_from_logs(log_text)
        if not summary:
            blockers.append("PR3.B29_LEARNING_BOUND_FAIL:EKS_JOB_SUMMARY_MISSING")
            summary = {
                "phase": "PR3",
                "state": "S4",
                "generated_at_utc": now_utc(),
                "execution_id": args.pr3_execution_id,
                "platform_run_id": args.platform_run_id,
                "scenario_run_id": args.scenario_run_id,
                "overall_pass": False,
                "blocker_ids": list(blockers),
                "error": "learning summary missing from pod logs",
            }

        summary["orchestration"] = {
            "mode": "eks_in_vpc_job",
            "namespace": args.namespace,
            "service_account_name": args.service_account_name,
            "service_account_role_arn": role_arn,
            "job_name": job_name,
            "pod_name": pod_name,
            "image_uri": image_uri,
            "job_succeeded": bool(job_ok),
            "job_status": (job_payload or {}).get("status", {}),
            "pod_phase": ((pod_payload or {}).get("status") or {}).get("phase"),
            "pod_reason": ((pod_payload or {}).get("status") or {}).get("reason"),
            "container_statuses": ((pod_payload or {}).get("status") or {}).get("containerStatuses"),
            "log_excerpt": "\n".join(log_text.splitlines()[-80:]) if log_text else "",
            "pod_describe_excerpt": "\n".join(describe_text.splitlines()[-80:]) if describe_text else "",
        }
        dump_json(summary_path, summary)
        if not job_ok or not bool(summary.get("overall_pass")):
            raise RuntimeError(
                "PR3.B29_LEARNING_BOUND_FAIL:EKS_JOB_FAILED"
                if not summary.get("blocker_ids")
                else str((summary.get("blocker_ids") or [])[0])
            )
    except Exception as exc:  # noqa: BLE001
        if not summary_path.exists():
            fallback = {
                "phase": "PR3",
                "state": "S4",
                "generated_at_utc": now_utc(),
                "execution_id": args.pr3_execution_id,
                "platform_run_id": args.platform_run_id,
                "scenario_run_id": args.scenario_run_id,
                "overall_pass": False,
                "blocker_ids": [str(exc)],
                "error": str(exc),
                "orchestration": {
                    "mode": "eks_in_vpc_job",
                    "namespace": args.namespace,
                    "service_account_name": args.service_account_name,
                    "service_account_role_arn": role_arn,
                    "job_name": job_name,
                    "pod_name": pod_name,
                    "image_uri": image_uri,
                },
            }
            dump_json(summary_path, fallback)
        raise
    finally:
        if job_name:
            kubectl_delete("job", job_name, args.namespace)
        if config_map_name:
            kubectl_delete("configmap", config_map_name, args.namespace)


if __name__ == "__main__":
    main()
