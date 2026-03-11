#!/usr/bin/env python3
"""Orchestrate PR3-S4 control bootstrap through an in-VPC EKS job."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import boto3

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fraud_detection.scenario_runner.config import load_policy
from fraud_detection.scenario_runner.storage import build_object_store


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
POLICY_PATH = Path("config/platform/sr/policy_v0.yaml")
WORKER_PATH = Path("scripts/dev_substrate/pr3_control_plane_bootstrap_worker.py")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def resolve_ssm(region: str, names: list[str]) -> dict[str, str]:
    ssm = boto3.client("ssm", region_name=region)
    response = ssm.get_parameters(Names=names, WithDecryption=True)
    values = {
        str(row.get("Name", "")).strip(): str(row.get("Value", "")).strip()
        for row in response.get("Parameters", [])
    }
    missing = [name for name in names if not values.get(name)]
    if missing:
        raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:MISSING_SSM:{','.join(missing)}")
    return values


def build_aurora_dsn(*, endpoint: str, username: str, password: str, db_name: str, port: int) -> str:
    return (
        f"postgresql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{endpoint}:{int(port)}/{db_name}?sslmode=require"
    )


def resolve_scenario_id(root: Path, fallback: str) -> str:
    for name in (
        "g3a_correctness_wsp_runtime_manifest.json",
        "g3a_s3_wsp_runtime_manifest.json",
        "g3a_s2_wsp_runtime_manifest.json",
        "g3a_s1_wsp_runtime_manifest.json",
    ):
        path = root / name
        if not path.exists():
            continue
        try:
            payload = load_json(path)
            value = str((((payload.get("identity") or {}).get("scenario_id")) or "")).strip()
            if value:
                return value
        except Exception:
            continue
    return fallback


def resolve_task_image(*, family: str, region: str) -> str:
    ecs = boto3.client("ecs", region_name=region)
    resp = ecs.describe_task_definition(taskDefinition=family)
    task_def = resp.get("taskDefinition", {})
    containers = list(task_def.get("containerDefinitions", []) or [])
    if not containers:
        raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:TASKDEF_EMPTY:{family}")
    image = str(containers[0].get("image", "")).strip()
    if not image:
        raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:TASKDEF_IMAGE_EMPTY:{family}")
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
        raise RuntimeError(
            f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def kubectl_apply(document: dict[str, Any]) -> None:
    run(["kubectl", "apply", "-f", "-"], input_text=json.dumps(document), timeout=300, check=True)


def kubectl_delete(kind: str, name: str, namespace: str | None = None) -> None:
    cmd = ["kubectl", "delete", kind, name, "--ignore-not-found=true"]
    if namespace:
        cmd.extend(["-n", namespace])
    run(cmd, timeout=180, check=False)


def namespace_manifest(name: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": name},
    }


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


def secret_manifest(namespace: str, name: str, string_data: dict[str, str]) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace},
        "type": "Opaque",
        "stringData": string_data,
    }


def job_manifest(
    *,
    namespace: str,
    name: str,
    image: str,
    service_account_name: str,
    config_map_name: str,
    secret_name: str,
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
                "fp.component": "control-bootstrap",
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
                        "fp.component": "control-bootstrap",
                    }
                },
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": service_account_name,
                    "containers": [
                        {
                            "name": "bootstrap",
                            "image": image,
                            "imagePullPolicy": "Always",
                            "command": ["python", "/bootstrap/pr3_control_plane_bootstrap_worker.py"],
                            "envFrom": [{"secretRef": {"name": secret_name}}],
                            "volumeMounts": [
                                {
                                    "name": "bootstrap-script",
                                    "mountPath": "/bootstrap",
                                    "readOnly": True,
                                }
                            ],
                            "resources": {
                                "requests": {"cpu": "500m", "memory": "1Gi"},
                                "limits": {"cpu": "2", "memory": "2Gi"},
                            },
                        }
                    ],
                    "volumes": [
                        {
                            "name": "bootstrap-script",
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
    proc = run(
        ["kubectl", "get", "pods", "-n", namespace, "-l", f"job-name={job_name}", "-o", "json"],
        timeout=60,
        check=True,
    )
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
    proc = run(["kubectl", "logs", pod_name, "-n", namespace], timeout=120, check=False)
    return (proc.stdout or proc.stderr or "").strip()


def pod_describe(namespace: str, pod_name: str) -> str:
    if not pod_name:
        return ""
    proc = run(["kubectl", "describe", "pod", pod_name, "-n", namespace], timeout=120, check=False)
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
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument("--scenario-id", default="baseline_v1")
    parser.add_argument("--bootstrap-summary-name", default="g3a_control_plane_bootstrap.json")
    parser.add_argument("--namespace", default="fraud-platform-rtdl")
    parser.add_argument("--service-account-name", default="rtdl")
    parser.add_argument("--service-account-role-arn", default="")
    parser.add_argument("--wsp-task-family", default="fraud-platform-dev-full-wsp-ephemeral")
    parser.add_argument("--image-uri", default="")
    parser.add_argument("--job-timeout-seconds", type=int, default=360)
    args = parser.parse_args()

    run_root = Path(args.run_control_root) / args.pr3_execution_id
    summary_path = run_root / args.bootstrap_summary_name
    blockers: list[str] = []

    config_map_name = ""
    secret_name = ""
    job_name = ""
    pod_name = ""

    try:
        if not WORKER_PATH.exists():
            raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:WORKER_SCRIPT_MISSING:{WORKER_PATH}")
        registry = parse_registry(REGISTRY_PATH)
        charter = load_json(run_root / "g3a_run_charter.active.json")
        ssm_values = resolve_ssm(
            args.aws_region,
            [
                str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip(),
                str(registry["SSM_AURORA_USERNAME_PATH"]).strip(),
                str(registry["SSM_AURORA_PASSWORD_PATH"]).strip(),
            ],
        )
        object_store_root = f"s3://{str(registry['S3_OBJECT_STORE_BUCKET']).strip()}"
        oracle_engine_run_root = (
            f"{object_store_root}/"
            f"{str(registry['S3_ORACLE_RUN_PREFIX_PATTERN']).strip().format(oracle_source_namespace=registry['ORACLE_SOURCE_NAMESPACE'], oracle_engine_run_id=registry['ORACLE_ENGINE_RUN_ID'])}"
        ).rstrip("/")
        oracle_receipt_ref = f"{oracle_engine_run_root}/run_receipt.json"
        store = build_object_store(object_store_root, s3_region=args.aws_region, s3_path_style=False)
        oracle_receipt = store.read_json(oracle_receipt_ref.replace(f"{object_store_root}/", "", 1))
        policy = load_policy(POLICY_PATH)
        scenario_id = resolve_scenario_id(run_root, args.scenario_id)
        image_uri = str(args.image_uri).strip() or resolve_task_image(
            family=args.wsp_task_family,
            region=args.aws_region,
        )
        role_arn = str(args.service_account_role_arn).strip() or str(registry.get("ROLE_EKS_IRSA_RTDL", "")).strip()
        if not role_arn:
            raise RuntimeError("PR3.B20_CONTROL_BOOTSTRAP_FAIL:IRSA_ROLE_UNRESOLVED")

        aurora_dsn = build_aurora_dsn(
            endpoint=ssm_values[str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip()],
            username=ssm_values[str(registry["SSM_AURORA_USERNAME_PATH"]).strip()],
            password=ssm_values[str(registry["SSM_AURORA_PASSWORD_PATH"]).strip()],
            db_name=str(registry.get("AURORA_DB_NAME", "fraud_platform")).strip() or "fraud_platform",
            port=int(str(registry.get("AURORA_PORT", "5432")).strip() or "5432"),
        )

        run_window = charter.get("mission_binding") or {}
        window_start = str(run_window.get("window_start_ts_utc") or "").strip()
        window_end = str(run_window.get("window_end_ts_utc") or "").strip()
        if not window_start or not window_end:
            raise RuntimeError("PR3.B20_CONTROL_BOOTSTRAP_FAIL:RUN_WINDOW_MISSING")

        suffix = stable_suffix(args.pr3_execution_id, args.platform_run_id)
        config_map_name = f"pr3-s4-bootstrap-script-{suffix}"
        secret_name = f"pr3-s4-bootstrap-env-{suffix}"
        job_name = f"pr3-s4-bootstrap-{suffix}"

        kubectl_apply(namespace_manifest(args.namespace))
        kubectl_apply(service_account_manifest(args.namespace, args.service_account_name, role_arn))
        kubectl_apply(
            config_map_manifest(
                args.namespace,
                config_map_name,
                {
                    "pr3_control_plane_bootstrap_worker.py": WORKER_PATH.read_text(encoding="utf-8"),
                },
            )
        )
        kubectl_apply(
            secret_manifest(
                args.namespace,
                secret_name,
                {
                    "PR3_EXECUTION_ID": args.pr3_execution_id,
                    "AWS_REGION": args.aws_region,
                    "PLATFORM_RUN_ID": str(args.platform_run_id).strip(),
                    "SCENARIO_ID": scenario_id,
                    "WINDOW_START_TS_UTC": window_start,
                    "WINDOW_END_TS_UTC": window_end,
                    "OBJECT_STORE_ROOT": object_store_root,
                    "ORACLE_ENGINE_RUN_ROOT": oracle_engine_run_root,
                    "CONTROL_BUS_TOPIC": str(registry["FP_BUS_CONTROL_V1"]).strip(),
                    "KAFKA_BOOTSTRAP_SERVERS": str(registry["MSK_BOOTSTRAP_BROKERS_SASL_IAM"]).strip(),
                    "AURORA_DSN": aurora_dsn,
                    "TRAFFIC_OUTPUT_IDS_JSON": json.dumps(list(policy.traffic_output_ids)),
                    "WORKER_SUMMARY_FORMAT": "json_line",
                    "ORACLE_RECEIPT_REF": oracle_receipt_ref,
                    "EXPECTED_MANIFEST_FINGERPRINT": str(oracle_receipt.get("manifest_fingerprint") or "").strip(),
                    "EXPECTED_PARAMETER_HASH": str(oracle_receipt.get("parameter_hash") or "").strip(),
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
                secret_name=secret_name,
            )
        )

        ok, status_payload = wait_for_job(args.namespace, job_name, timeout_seconds=args.job_timeout_seconds)
        pod_name = get_pod_name(args.namespace, job_name)
        pod_payload = get_pod_payload(args.namespace, pod_name)
        logs = pod_logs(args.namespace, pod_name)
        summary = parse_summary_from_logs(logs)
        if not ok:
            if not summary:
                container_statuses = ((pod_payload.get("status") or {}).get("containerStatuses") or []) if isinstance(pod_payload, dict) else []
                summary = {
                    "phase": "PR3",
                    "state": "S4",
                    "generated_at_utc": now_utc(),
                    "execution_id": args.pr3_execution_id,
                    "platform_run_id": str(args.platform_run_id).strip(),
                    "scenario_run_id": "",
                    "overall_pass": False,
                    "blocker_ids": ["PR3.B20_CONTROL_BOOTSTRAP_FAIL:EKS_JOB_FAILED"],
                    "error": "Remote control bootstrap job failed before producing a summary.",
                    "job": {
                        "namespace": args.namespace,
                        "job_name": job_name,
                        "pod_name": pod_name,
                        "status": status_payload.get("status", {}) if isinstance(status_payload, dict) else {},
                    },
                    "pod_status": (pod_payload.get("status") or {}) if isinstance(pod_payload, dict) else {},
                    "container_statuses": container_statuses,
                    "log_excerpt": logs.splitlines()[-200:],
                    "pod_describe_excerpt": pod_describe(args.namespace, pod_name).splitlines()[-120:],
                }
            dump_json(summary_path, summary)
            raise SystemExit(1)

        if not summary:
            summary = {
                "phase": "PR3",
                "state": "S4",
                "generated_at_utc": now_utc(),
                "execution_id": args.pr3_execution_id,
                "platform_run_id": str(args.platform_run_id).strip(),
                "scenario_run_id": "",
                "overall_pass": False,
                "blocker_ids": ["PR3.B20_CONTROL_BOOTSTRAP_FAIL:EKS_JOB_NO_SUMMARY"],
                "error": "Remote control bootstrap job completed without a parseable JSON summary.",
                "job": {
                    "namespace": args.namespace,
                    "job_name": job_name,
                    "pod_name": pod_name,
                    "status": status_payload.get("status", {}) if isinstance(status_payload, dict) else {},
                },
                "pod_status": (pod_payload.get("status") or {}) if isinstance(pod_payload, dict) else {},
                "log_excerpt": logs.splitlines()[-200:],
            }
            dump_json(summary_path, summary)
            raise SystemExit(1)

        summary["orchestration"] = {
            "mode": "eks_in_vpc_job",
            "namespace": args.namespace,
            "service_account_name": args.service_account_name,
            "service_account_role_arn": role_arn,
            "job_name": job_name,
            "pod_name": pod_name,
            "image_uri": image_uri,
        }
        dump_json(summary_path, summary)
        if not bool(summary.get("overall_pass")):
            raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))
        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": str(args.platform_run_id).strip(),
            "scenario_run_id": "",
            "overall_pass": False,
            "blocker_ids": blockers,
            "error": str(exc),
            "job": {
                "namespace": args.namespace,
                "job_name": job_name,
                "pod_name": pod_name,
            },
        }
        dump_json(summary_path, summary)
        raise SystemExit(1)
    finally:
        if job_name:
            kubectl_delete("job", job_name, args.namespace)
        if secret_name:
            kubectl_delete("secret", secret_name, args.namespace)
        if config_map_name:
            kubectl_delete("configmap", config_map_name, args.namespace)


if __name__ == "__main__":
    main()
