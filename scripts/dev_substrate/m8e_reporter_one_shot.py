#!/usr/bin/env python3
"""Managed M8.E reporter one-shot execution artifact builder."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError

HANDLES_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_handles(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\* `([^`=]+?)\s*=\s*([^`]+)`")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        key = m.group(1).strip()
        raw = m.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            val: Any = raw[1:-1]
        elif raw.lower() == "true":
            val = True
        elif raw.lower() == "false":
            val = False
        else:
            try:
                val = int(raw) if "." not in raw else float(raw)
            except ValueError:
                val = raw
        out[key] = val
    return out


def has_handle(path: Path, name: str) -> bool:
    rx = re.compile(rf"^\* `{re.escape(name)}`\s*$")
    return any(rx.match(x.strip()) for x in path.read_text(encoding="utf-8").splitlines())


def placeholder(v: Any) -> bool:
    s = str(v or "").strip().lower()
    return (not s) or (s in {"tbd", "todo", "none", "null", "unset"}) or ("placeholder" in s) or ("to_pin" in s) or ("<" in s and ">" in s)


def cmd(args: list[str], *, stdin: str | None = None, timeout: int = 120) -> tuple[int, str, str]:
    try:
        p = subprocess.run(args, input=stdin, text=True, capture_output=True, timeout=timeout, check=False)
        return int(p.returncode), str(p.stdout or ""), str(p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout:{timeout}"
    except OSError as exc:
        return 127, "", f"oserror:{type(exc).__name__}"


def s3_get_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(raw)


def s3_put_json(s3: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3.head_object(Bucket=bucket, Key=key)


def dedupe(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for b in blockers:
        k = (str(b.get("code", "")).strip(), str(b.get("message", "")).strip())
        if k in seen:
            continue
        seen.add(k)
        out.append({"code": k[0], "message": k[1]})
    return out


def dsn_from_parts(endpoint: str, user: str, password: str, db: str) -> str:
    host = endpoint.strip()
    if ":" not in host:
        host = f"{host}:5432"
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}/{quote_plus(db)}?sslmode=require&connect_timeout=5"


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M8E_EXECUTION_ID", "").strip()
    run_dir = Path(env.get("M8E_RUN_DIR", "").strip())
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream = env.get("UPSTREAM_M8D_EXECUTION", "").strip()
    region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    timeout_s = int(env.get("M8E_TIMEOUT_SECONDS", "900"))
    poll_s = max(2, int(env.get("M8E_POLL_SECONDS", "5")))
    sa_name = env.get("M8E_SERVICE_ACCOUNT", "obs-gov").strip() or "obs-gov"

    if not execution_id or not evidence_bucket or not upstream or not str(run_dir):
        raise SystemExit("M8E_EXECUTION_ID, M8E_RUN_DIR, EVIDENCE_BUCKET, UPSTREAM_M8D_EXECUTION are required.")

    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=region)
    ssm = boto3.client("ssm", region_name=region)
    ecr = boto3.client("ecr", region_name=region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []
    actions: list[str] = []

    up_key = f"evidence/dev_full/run_control/{upstream}/m8d_execution_summary.json"
    up = None
    try:
        up = s3_get_json(s3, evidence_bucket, up_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": up_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B5", "message": "Upstream M8.D summary unreadable."})

    run_id = env.get("PLATFORM_RUN_ID", "").strip()
    scenario_id = env.get("SCENARIO_RUN_ID", "").strip()
    if isinstance(up, dict):
        if not (bool(up.get("overall_pass")) and str(up.get("next_gate", "")).strip() == "M8.E_READY"):
            blockers.append({"code": "M8-B5", "message": "M8.D gate is not M8.E_READY."})
        run_id = run_id or str(up.get("platform_run_id", "")).strip()
        scenario_id = scenario_id or str(up.get("scenario_run_id", "")).strip()
    if not run_id or not scenario_id:
        blockers.append({"code": "M8-B5", "message": "Run scope unresolved for M8.E."})

    req = [
        "EKS_CLUSTER_NAME", "EKS_NAMESPACE_OBS_GOV", "ROLE_EKS_IRSA_OBS_GOV", "ECR_REPO_URI",
        "S3_OBJECT_STORE_BUCKET", "REPORTER_LOCK_BACKEND", "REPORTER_LOCK_KEY_PATTERN",
        "SSM_AURORA_ENDPOINT_PATH", "SSM_AURORA_USERNAME_PATH", "SSM_AURORA_PASSWORD_PATH", "AURORA_DB_NAME"
    ]
    missing = [k for k in req if k not in handles]
    bad = [k for k in req if k in handles and placeholder(handles.get(k))]
    if missing or bad:
        blockers.append({"code": "M8-B5", "message": "Required handles missing or placeholder-valued."})
    if not has_handle(HANDLES_PATH, "ENTRYPOINT_REPORTER"):
        blockers.append({"code": "M8-B5", "message": "ENTRYPOINT_REPORTER declaration missing."})

    cluster = str(handles.get("EKS_CLUSTER_NAME", "")).strip()
    namespace = str(handles.get("EKS_NAMESPACE_OBS_GOV", "")).strip()
    role_arn = str(handles.get("ROLE_EKS_IRSA_OBS_GOV", "")).strip()
    repo_uri = str(handles.get("ECR_REPO_URI", "")).strip()
    object_bucket = str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip()
    lock_backend = str(handles.get("REPORTER_LOCK_BACKEND", "")).strip()
    lock_backend_effective = "db_advisory_lock" if lock_backend == "aurora_advisory_lock" else lock_backend
    lock_pattern = str(handles.get("REPORTER_LOCK_KEY_PATTERN", "")).strip()
    db_name = str(handles.get("AURORA_DB_NAME", "fraud_platform")).strip() or "fraud_platform"

    dsn = ""
    dsn_host = ""
    if not blockers:
        try:
            endpoint = ssm.get_parameter(Name=str(handles["SSM_AURORA_ENDPOINT_PATH"]), WithDecryption=True)["Parameter"]["Value"].strip()
            user = ssm.get_parameter(Name=str(handles["SSM_AURORA_USERNAME_PATH"]), WithDecryption=True)["Parameter"]["Value"].strip()
            pwd = ssm.get_parameter(Name=str(handles["SSM_AURORA_PASSWORD_PATH"]), WithDecryption=True)["Parameter"]["Value"].strip()
            dsn = dsn_from_parts(endpoint, user, pwd, db_name)
            dsn_host = endpoint
        except (BotoCoreError, ClientError, KeyError) as exc:
            blockers.append({"code": "M8-B5", "message": f"Aurora DSN resolution failed:{type(exc).__name__}."})

    image_uri = env.get("M8E_IMAGE_URI", "").strip()
    image_meta: dict[str, Any] = {}
    if not blockers and not image_uri:
        try:
            repo_name = repo_uri.rsplit("/", 1)[-1]
            details = ecr.describe_images(repositoryName=repo_name).get("imageDetails", [])
            details = [d for d in details if d.get("imageDigest") and d.get("imagePushedAt")]
            if not details:
                blockers.append({"code": "M8-B5", "message": "No ECR image found for reporter run."})
            else:
                details.sort(key=lambda x: x.get("imagePushedAt"))
                top = details[-1]
                image_uri = f"{repo_uri}@{top['imageDigest']}"
                image_meta = {
                    "image_digest": str(top.get("imageDigest", "")),
                    "image_tags": list(top.get("imageTags") or []),
                    "image_pushed_at": str(top.get("imagePushedAt", "")),
                }
        except (BotoCoreError, ClientError) as exc:
            blockers.append({"code": "M8-B5", "message": f"ECR lookup failed:{type(exc).__name__}."})

    rc, _, err = cmd(["aws", "eks", "update-kubeconfig", "--region", region, "--name", cluster], timeout=120)
    if rc != 0:
        blockers.append({"code": "M8-B5", "message": f"EKS kubeconfig update failed:{err[:120]}"})

    namespace_created = False
    sa_ok = False
    concurrency = {"active_jobs": [], "active_pods": []}
    job_name = ""
    pod_name = ""
    pod_logs = ""
    pod_exit_code = None
    wait_state = {"timed_out": False, "success": False, "elapsed_seconds": 0.0}

    if not blockers:
        rc, _, _ = cmd(["kubectl", "get", "namespace", namespace], timeout=30)
        if rc != 0:
            rc, _, err = cmd(["kubectl", "create", "namespace", namespace], timeout=30)
            if rc != 0 and "AlreadyExists" not in err:
                blockers.append({"code": "M8-B5", "message": "Obs/Gov namespace materialization failed."})
            else:
                namespace_created = True
                actions.append(f"created_namespace:{namespace}")

    if not blockers:
        sa_manifest = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": sa_name,
                "namespace": namespace,
                "annotations": {"eks.amazonaws.com/role-arn": role_arn},
            },
        }
        rc, _, err = cmd(["kubectl", "apply", "-f", "-"], stdin=json.dumps(sa_manifest), timeout=45)
        if rc != 0:
            blockers.append({"code": "M8-B5", "message": "Obs/Gov service account apply failed."})
        else:
            sa_ok = True
            actions.append(f"applied_service_account:{namespace}/{sa_name}")

    if not blockers:
        label = f"app=platform-reporter,platform_run_id={run_id}"
        rc, out, _ = cmd(["kubectl", "get", "jobs", "-n", namespace, "-l", label, "-o", "json"], timeout=30)
        if rc == 0:
            jobs = json.loads(out)
            for it in jobs.get("items", []):
                if int((it.get("status") or {}).get("active", 0) or 0) > 0:
                    concurrency["active_jobs"].append(str((it.get("metadata") or {}).get("name", "")))
        rc, out, _ = cmd(["kubectl", "get", "pods", "-n", namespace, "-l", label, "-o", "json"], timeout=30)
        if rc == 0:
            pods = json.loads(out)
            for it in pods.get("items", []):
                phase = str((it.get("status") or {}).get("phase", ""))
                if phase in {"Pending", "Running"}:
                    concurrency["active_pods"].append(str((it.get("metadata") or {}).get("name", "")))
        if concurrency["active_jobs"] or concurrency["active_pods"]:
            blockers.append({"code": "M8-B5", "message": "Concurrent reporter writer detected."})

    if not blockers:
        job_name = f"m8e-reporter-{datetime.now(timezone.utc).strftime('%H%M%S')}".lower()
        script = (
            "set -euo pipefail\n"
            "python - <<'PY'\n"
            "import pathlib,yaml\n"
            "p=pathlib.Path('config/platform/profiles/dev_full.yaml')\n"
            "d=yaml.safe_load(p.read_text(encoding='utf-8'))\n"
            "d.setdefault('wiring',{})['admission_db_path']='${IG_ADMISSION_DSN}'\n"
            "pathlib.Path('/tmp/dev_full_m8e.yaml').write_text(yaml.safe_dump(d,sort_keys=False),encoding='utf-8')\n"
            "PY\n"
            "python - <<'PY'\n"
            "import os,psycopg\n"
            "dsn=os.environ['IG_ADMISSION_DSN']\n"
            "ddl=[\n"
            "  \"CREATE TABLE IF NOT EXISTS receipts (decision TEXT,event_type TEXT,receipt_ref TEXT,pins_json TEXT,evidence_refs_json TEXT)\",\n"
            "  \"CREATE TABLE IF NOT EXISTS quarantines (evidence_ref TEXT,pins_json TEXT)\",\n"
            "  \"CREATE TABLE IF NOT EXISTS admissions (platform_run_id TEXT,state TEXT,receipt_write_failed INTEGER DEFAULT 0)\"\n"
            "]\n"
            "with psycopg.connect(dsn) as conn:\n"
            "  with conn.cursor() as cur:\n"
            "    for q in ddl:\n"
            "      cur.execute(q)\n"
            "  conn.commit()\n"
            "PY\n"
            "python -m fraud_detection.platform_reporter.worker --profile /tmp/dev_full_m8e.yaml --once --required-platform-run-id \"${ACTIVE_PLATFORM_RUN_ID}\"\n"
        )
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": namespace,
                "labels": {"app": "platform-reporter", "platform_run_id": run_id, "phase": "m8e"},
            },
            "spec": {
                "backoffLimit": 0,
                "ttlSecondsAfterFinished": 600,
                "template": {
                    "metadata": {"labels": {"app": "platform-reporter", "platform_run_id": run_id, "phase": "m8e"}},
                    "spec": {
                        "serviceAccountName": sa_name,
                        "restartPolicy": "Never",
                        "containers": [{
                            "name": "reporter",
                            "image": image_uri,
                            "imagePullPolicy": "Always",
                            "command": ["/bin/sh", "-lc", script],
                            "env": [
                                {"name": "AWS_REGION", "value": region},
                                {"name": "ACTIVE_PLATFORM_RUN_ID", "value": run_id},
                                {"name": "PLATFORM_RUN_ID", "value": run_id},
                                {"name": "PLATFORM_REPORTER_REQUIRED_PLATFORM_RUN_ID", "value": run_id},
                                {"name": "REPORTER_LOCK_BACKEND", "value": lock_backend_effective},
                                {"name": "REPORTER_LOCK_KEY_PATTERN", "value": lock_pattern},
                                {"name": "IG_ADMISSION_DSN", "value": dsn},
                                {"name": "OBJECT_STORE_REGION", "value": region},
                                {"name": "SERVICE_RELEASE_ID", "value": "git:dev_full"},
                                {"name": "EVIDENCE_REF_RESOLVER_ALLOWLIST", "value": "SYSTEM::platform_run_reporter,svc:platform_run_reporter"},
                            ],
                            "resources": {"requests": {"cpu": "250m", "memory": "512Mi"}, "limits": {"cpu": "1", "memory": "1Gi"}},
                        }],
                    },
                },
            },
        }
        rc, _, err = cmd(["kubectl", "apply", "-f", "-"], stdin=json.dumps(job), timeout=90)
        if rc != 0:
            blockers.append({"code": "M8-B5", "message": f"Reporter job dispatch failed:{err[:120]}"})

    start = time.time()
    if not blockers and job_name:
        while True:
            rc, out, _ = cmd(["kubectl", "get", "job", job_name, "-n", namespace, "-o", "json"], timeout=30)
            if rc != 0:
                blockers.append({"code": "M8-B5", "message": "Reporter job status unreadable."})
                break
            job = json.loads(out)
            st = job.get("status", {})
            if int(st.get("succeeded", 0) or 0) > 0:
                wait_state["success"] = True
                break
            if int(st.get("failed", 0) or 0) > 0:
                blockers.append({"code": "M8-B5", "message": "Reporter job terminated failed."})
                break
            if time.time() - start > timeout_s:
                wait_state["timed_out"] = True
                blockers.append({"code": "M8-B5", "message": "Reporter job timeout."})
                break
            time.sleep(poll_s)
        wait_state["elapsed_seconds"] = round(time.time() - start, 3)

    if job_name:
        rc, out, _ = cmd(["kubectl", "get", "pods", "-n", namespace, "-l", f"job-name={job_name}", "-o", "json"], timeout=30)
        if rc == 0:
            pods = json.loads(out).get("items", [])
            if pods:
                p = pods[0]
                pod_name = str((p.get("metadata") or {}).get("name", ""))
                for cs in ((p.get("status") or {}).get("containerStatuses") or []):
                    term = ((cs.get("state") or {}).get("terminated") or {})
                    if term:
                        pod_exit_code = term.get("exitCode")
                        break
        if pod_name:
            _, logs, _ = cmd(["kubectl", "logs", pod_name, "-n", namespace, "--timestamps"], timeout=120)
            pod_logs = logs

    lock = {
        "lock_acquired_seen": "platform reporter lock acquired" in pod_logs,
        "lock_released_seen": "platform reporter lock released" in pod_logs,
        "lock_denied_seen": ("REPORTER_LOCK_NOT_ACQUIRED" in pod_logs) or ("platform reporter lock denied" in pod_logs),
        "lock_scope_match": f"reporter:{run_id}" in pod_logs,
    }
    if pod_name:
        if not (lock["lock_acquired_seen"] and lock["lock_released_seen"] and lock["lock_scope_match"]):
            blockers.append({"code": "M8-B5", "message": "Lock lifecycle evidence incomplete."})
        if lock["lock_denied_seen"]:
            blockers.append({"code": "M8-B5", "message": "Lock-denied conflict observed in one-shot run."})
        if pod_exit_code is None or int(pod_exit_code) != 0:
            blockers.append({"code": "M8-B5", "message": "Reporter container exit code non-zero or unavailable."})

    required_keys = [
        f"{run_id}/obs/platform_run_report.json",
        f"{run_id}/obs/run_report.json",
        f"{run_id}/obs/reconciliation.json",
        f"{run_id}/obs/replay_anchors.json",
        f"{run_id}/obs/environment_conformance.json",
        f"{run_id}/obs/anomaly_summary.json",
        f"{run_id}/run_completed.json",
    ]
    artifact_checks: list[dict[str, Any]] = []
    if run_id and object_bucket:
        for key in required_keys:
            row = {"bucket": object_bucket, "key": key, "readable": False}
            try:
                s3.head_object(Bucket=object_bucket, Key=key)
                row["readable"] = True
            except (BotoCoreError, ClientError) as exc:
                read_errors.append({"surface": f"s3://{object_bucket}/{key}", "error": type(exc).__name__})
                blockers.append({"code": "M8-B5", "message": f"Missing/unreadable closure artifact: {key}"})
            artifact_checks.append(row)

    blockers = dedupe(blockers)
    overall = len(blockers) == 0
    next_gate = "M8.F_READY" if overall else "HOLD_REMEDIATE"
    captured = now_utc()

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M8.E",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "source_m8d_summary_uri": f"s3://{evidence_bucket}/{up_key}",
        "entry_gate_ok": bool(isinstance(up, dict) and bool(up.get("overall_pass")) and str(up.get("next_gate", "")).strip() == "M8.E_READY"),
        "runtime_contract": {
            "eks_cluster": cluster,
            "namespace": namespace,
            "namespace_created": namespace_created,
            "service_account": sa_name,
            "service_account_ok": sa_ok,
            "role_arn": role_arn,
            "image_uri": image_uri,
            "entrypoint_reporter_declared": has_handle(HANDLES_PATH, "ENTRYPOINT_REPORTER"),
            "lock_backend": lock_backend,
            "lock_backend_effective": lock_backend_effective,
            "lock_key_pattern": lock_pattern,
        },
        "job_execution": {
            "job_name": job_name,
            "pod_name": pod_name,
            "container_exit_code": pod_exit_code,
            "wait": wait_state,
            "pod_logs_excerpt": pod_logs[-4000:],
        },
        "precheck": {"concurrency": concurrency},
        "aurora_runtime_path": {"dsn_resolved": bool(dsn), "endpoint_preview": dsn_host},
        "lock_lifecycle_checks": lock,
        "object_store_closure_artifact_checks": artifact_checks,
        "image_meta": image_meta,
        "actions": actions,
        "read_errors": read_errors,
        "blockers": blockers,
        "overall_pass": overall,
        "next_gate": next_gate,
    }

    blocker_register = {
        "captured_at_utc": captured,
        "phase": "M8.E",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "overall_pass": overall,
        "next_gate": next_gate,
    }

    summary = {
        "captured_at_utc": captured,
        "phase": "M8.E",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "upstream_refs": {"m8d_execution_id": upstream},
        "runtime_contract": {
            "managed_mode": "EKS_JOB_ONE_SHOT",
            "eks_cluster_name": cluster,
            "namespace": namespace,
            "service_account": sa_name,
            "role_arn": role_arn,
            "image_uri": image_uri,
            "lock_backend_effective": lock_backend_effective,
        },
        "durable_artifacts": {
            "m8e_snapshot_key": f"evidence/dev_full/run_control/{execution_id}/m8e_reporter_execution_snapshot.json",
            "m8e_blocker_register_key": f"evidence/dev_full/run_control/{execution_id}/m8e_blocker_register.json",
            "m8e_execution_summary_key": f"evidence/dev_full/run_control/{execution_id}/m8e_execution_summary.json",
        },
        "read_error_count": len(read_errors),
        "overall_pass": overall,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_gate": next_gate,
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    local = {
        "m8e_reporter_execution_snapshot.json": snapshot,
        "m8e_blocker_register.json": blocker_register,
        "m8e_execution_summary.json": summary,
    }
    for n, p in local.items():
        (run_dir / n).write_text(json.dumps(p, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    for n, p in local.items():
        key = f"evidence/dev_full/run_control/{execution_id}/{n}"
        try:
            s3_put_json(s3, evidence_bucket, key, p)
        except (BotoCoreError, ClientError) as exc:
            upload_errors.append({"surface": key, "error": type(exc).__name__})

    if upload_errors:
        blockers.append({"code": "M8-B12", "message": "M8.E artifact publication/readback parity failed."})
        blockers = dedupe(blockers)
        overall = len(blockers) == 0
        next_gate = "M8.F_READY" if overall else "HOLD_REMEDIATE"
        for p in (snapshot, blocker_register, summary):
            p["blockers"] = blockers
            p["overall_pass"] = overall
            p["next_gate"] = next_gate
            p["upload_errors"] = upload_errors
        blocker_register["blocker_count"] = len(blockers)
        summary["blocker_count"] = len(blockers)
        summary["upload_error_count"] = len(upload_errors)
        for n, p in local.items():
            (run_dir / n).write_text(json.dumps(p, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps({"overall_pass": overall, "blocker_count": len(blockers), "next_gate": next_gate}, indent=2, ensure_ascii=True))
    return 0 if overall else 2


if __name__ == "__main__":
    raise SystemExit(main())
