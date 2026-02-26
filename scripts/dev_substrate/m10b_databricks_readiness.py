#!/usr/bin/env python3
"""Build and publish M10.B Databricks runtime-readiness artifacts."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
            value: Any = raw[1:-1]
        elif raw.lower() == "true":
            value = True
        elif raw.lower() == "false":
            value = False
        else:
            try:
                value = int(raw) if "." not in raw else float(raw)
            except ValueError:
                value = raw
        out[key] = value
    return out


def is_placeholder(value: Any) -> bool:
    s = str(value).strip()
    s_lower = s.lower()
    if s == "":
        return True
    if s_lower in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "to_pin" in s_lower or "placeholder" in s_lower:
        return True
    if "<" in s and ">" in s:
        return True
    return False


def parse_worker_range(value: str) -> tuple[int, int] | None:
    text = value.strip()
    if "-" not in text:
        return None
    left, right = text.split("-", 1)
    try:
        return int(left), int(right)
    except ValueError:
        return None


def s3_get_json(s3_client: Any, bucket: str, key: str) -> dict[str, Any]:
    body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def s3_put_json(s3_client: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3_client.head_object(Bucket=bucket, Key=key)


def write_local_artifacts(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        message = str(blocker.get("message", "")).strip()
        sig = (code, message)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": message})
    return out


def dbx_request_json(base_url: str, token: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    q = ""
    if query:
        q = "?" + urllib.parse.urlencode(query, doseq=True)
    url = f"{base_url.rstrip('/')}{path}{q}"
    req = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def dbx_get_job(base_url: str, token: str, job_id: Any) -> dict[str, Any]:
    try:
        normalized = int(job_id)
    except (TypeError, ValueError):
        raise ValueError("job_id_invalid")
    return dbx_request_json(base_url, token, "/api/2.1/jobs/get", {"job_id": normalized})


def collect_cluster_specs(job_payload: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    settings = job_payload.get("settings", {})
    if not isinstance(settings, dict):
        return specs

    job_cluster_map: dict[str, dict[str, Any]] = {}
    for jc in settings.get("job_clusters", []) or []:
        if not isinstance(jc, dict):
            continue
        key = str(jc.get("job_cluster_key", "")).strip()
        nc = jc.get("new_cluster")
        if key and isinstance(nc, dict):
            job_cluster_map[key] = nc
            specs.append(nc)

    for task in settings.get("tasks", []) or []:
        if not isinstance(task, dict):
            continue
        nc = task.get("new_cluster")
        if isinstance(nc, dict):
            specs.append(nc)
        key = str(task.get("job_cluster_key", "")).strip()
        if key and key in job_cluster_map:
            specs.append(job_cluster_map[key])
    return specs


def job_uses_serverless_shape(job_payload: dict[str, Any]) -> bool:
    settings = job_payload.get("settings", {})
    if not isinstance(settings, dict):
        return False
    tasks = settings.get("tasks", []) or []
    if not isinstance(tasks, list) or not tasks:
        return False
    environments = settings.get("environments", []) or []
    has_env = isinstance(environments, list) and len(environments) > 0
    if not has_env:
        return False
    for task in tasks:
        if not isinstance(task, dict):
            return False
        if str(task.get("environment_key", "")).strip() == "":
            return False
        if task.get("existing_cluster_id") or task.get("new_cluster") or task.get("job_cluster_key"):
            return False
    return True


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M10B_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10B_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10a_execution = env.get("UPSTREAM_M10A_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10B_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10B_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10a_execution:
        raise SystemExit("UPSTREAM_M10A_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    m10a_summary_key = f"evidence/dev_full/run_control/{upstream_m10a_execution}/m10a_execution_summary.json"
    m10a_summary: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""
    try:
        m10a_summary = s3_get_json(s3, evidence_bucket, m10a_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10a_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B2", "message": "M10.A summary unreadable for M10.B entry gate."})

    if m10a_summary:
        if not bool(m10a_summary.get("overall_pass")):
            blockers.append({"code": "M10-B2", "message": "M10.A is not pass posture."})
        if str(m10a_summary.get("next_gate", "")).strip() != "M10.B_READY":
            blockers.append({"code": "M10-B2", "message": "M10.A next_gate is not M10.B_READY."})
        platform_run_id = str(m10a_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10a_summary.get("scenario_run_id", "")).strip()

    required_handles = [
        "DBX_WORKSPACE_URL",
        "DBX_JOB_OFS_BUILD_V0",
        "DBX_JOB_OFS_QUALITY_GATES_V0",
        "DBX_COMPUTE_POLICY",
        "DBX_AUTOSCALE_WORKERS",
        "DBX_AUTO_TERMINATE_MINUTES",
        "SSM_DATABRICKS_WORKSPACE_URL_PATH",
        "SSM_DATABRICKS_TOKEN_PATH",
    ]
    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    handle_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        handle_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)

    if missing_handles or placeholder_handles:
        blockers.append({"code": "M10-B2", "message": "Required M10.B handles are missing or placeholder-valued."})

    workspace_url = str(handles.get("DBX_WORKSPACE_URL", "")).strip()
    ssm_workspace_path = str(handles.get("SSM_DATABRICKS_WORKSPACE_URL_PATH", "")).strip()
    ssm_token_path = str(handles.get("SSM_DATABRICKS_TOKEN_PATH", "")).strip()

    ssm_workspace_value = ""
    ssm_token_value = ""
    if ssm_workspace_path:
        try:
            ssm_workspace_value = (
                ssm.get_parameter(Name=ssm_workspace_path)["Parameter"]["Value"].strip()
            )
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": ssm_workspace_path, "error": type(exc).__name__})
            blockers.append({"code": "M10-B2", "message": "Databricks workspace URL SSM parameter unreadable."})
    if ssm_token_path:
        try:
            ssm_token_value = (
                ssm.get_parameter(Name=ssm_token_path, WithDecryption=True)["Parameter"]["Value"].strip()
            )
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": ssm_token_path, "error": type(exc).__name__})
            blockers.append({"code": "M10-B2", "message": "Databricks token SSM parameter unreadable."})

    if workspace_url and ssm_workspace_value and workspace_url.rstrip("/") != ssm_workspace_value.rstrip("/"):
        blockers.append({"code": "M10-B2", "message": "SSM workspace URL does not match DBX_WORKSPACE_URL handle."})
    if is_placeholder(ssm_workspace_value):
        blockers.append({"code": "M10-B2", "message": "SSM workspace URL appears placeholder-valued."})
    if is_placeholder(ssm_token_value):
        blockers.append({"code": "M10-B2", "message": "SSM Databricks token appears placeholder-valued."})
    if len(ssm_token_value) < 20:
        blockers.append({"code": "M10-B2", "message": "SSM Databricks token length is below minimum readiness threshold."})

    dbx_probe: dict[str, Any] = {
        "workspace_probe_ok": False,
        "jobs_list_probe_ok": False,
        "job_count": 0,
    }
    jobs_by_name: dict[str, dict[str, Any]] = {}

    if workspace_url and ssm_token_value and not is_placeholder(ssm_token_value):
        try:
            me_payload = dbx_request_json(workspace_url, ssm_token_value, "/api/2.0/preview/scim/v2/Me")
            dbx_probe["workspace_probe_ok"] = bool(me_payload.get("id") or me_payload.get("userName"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            read_errors.append({"surface": "databricks_me_probe", "error": type(exc).__name__})
            blockers.append({"code": "M10-B2", "message": "Databricks workspace probe failed."})

        try:
            jobs_payload = dbx_request_json(workspace_url, ssm_token_value, "/api/2.1/jobs/list", {"limit": 100})
            jobs = jobs_payload.get("jobs", [])
            if not isinstance(jobs, list):
                jobs = []
            dbx_probe["jobs_list_probe_ok"] = True
            dbx_probe["job_count"] = len(jobs)
            for item in jobs:
                if not isinstance(item, dict):
                    continue
                settings = item.get("settings", {})
                if not isinstance(settings, dict):
                    continue
                name = str(settings.get("name", "")).strip()
                if name:
                    jobs_by_name[name] = item
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            read_errors.append({"surface": "databricks_jobs_list", "error": type(exc).__name__})
            blockers.append({"code": "M10-B2", "message": "Databricks jobs list probe failed."})
    else:
        blockers.append({"code": "M10-B2", "message": "Databricks probe skipped due missing/non-ready workspace or token materialization."})

    required_job_names = [
        str(handles.get("DBX_JOB_OFS_BUILD_V0", "")).strip(),
        str(handles.get("DBX_JOB_OFS_QUALITY_GATES_V0", "")).strip(),
    ]
    missing_jobs: list[str] = []
    job_policy_rows: list[dict[str, Any]] = []

    compute_policy = str(handles.get("DBX_COMPUTE_POLICY", "")).strip().lower()
    auto_terminate_cap = int(handles.get("DBX_AUTO_TERMINATE_MINUTES", 20))
    autoscale_range = parse_worker_range(str(handles.get("DBX_AUTOSCALE_WORKERS", "1-8")))

    for name in required_job_names:
        if not name:
            continue
        job = jobs_by_name.get(name)
        if job is None:
            missing_jobs.append(name)
            continue

        job_id = job.get("job_id")
        job_for_policy = job
        if workspace_url and ssm_token_value and dbx_probe.get("jobs_list_probe_ok"):
            try:
                job_for_policy = dbx_get_job(workspace_url, ssm_token_value, job_id)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                read_errors.append({"surface": f"databricks_jobs_get:{job_id}", "error": type(exc).__name__})
                blockers.append({"code": "M10-B2", "message": "Databricks jobs/get probe failed."})
        settings = job_for_policy.get("settings", {})
        policy_row: dict[str, Any] = {
            "job_name": name,
            "job_id": job_id,
            "exists": True,
            "all_tasks_job_cluster_only": True,
            "serverless_shape_ok": True,
            "autoscale_in_range": True,
            "autotermination_in_policy": True,
            "policy_conformance": True,
            "issues": [],
        }
        if not isinstance(settings, dict):
            policy_row["policy_conformance"] = False
            policy_row["issues"].append("settings_missing")
            job_policy_rows.append(policy_row)
            continue

        if "serverless" in compute_policy:
            if not job_uses_serverless_shape(job_for_policy):
                policy_row["serverless_shape_ok"] = False
                policy_row["issues"].append("serverless_shape_invalid")
            policy_row["all_tasks_job_cluster_only"] = False
            policy_row["autoscale_in_range"] = True
            policy_row["autotermination_in_policy"] = True
            policy_row["policy_conformance"] = policy_row["serverless_shape_ok"] and len(policy_row["issues"]) == 0
        else:
            cluster_specs = collect_cluster_specs(job)
            if not cluster_specs:
                policy_row["policy_conformance"] = False
                policy_row["issues"].append("no_job_cluster_spec")

            tasks = settings.get("tasks", []) or []
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                if task.get("existing_cluster_id"):
                    policy_row["all_tasks_job_cluster_only"] = False
                    policy_row["issues"].append("existing_cluster_id_detected")
                if not task.get("new_cluster") and not task.get("job_cluster_key"):
                    policy_row["all_tasks_job_cluster_only"] = False
                    policy_row["issues"].append("task_without_job_cluster")

            for spec in cluster_specs:
                if not isinstance(spec, dict):
                    continue
                if autoscale_range is not None:
                    min_workers, max_workers = autoscale_range
                    auto = spec.get("autoscale")
                    if isinstance(auto, dict):
                        try:
                            mn = int(auto.get("min_workers"))
                            mx = int(auto.get("max_workers"))
                            if mn < min_workers or mx > max_workers:
                                policy_row["autoscale_in_range"] = False
                                policy_row["issues"].append("autoscale_out_of_range")
                        except (TypeError, ValueError):
                            policy_row["autoscale_in_range"] = False
                            policy_row["issues"].append("autoscale_parse_error")
                    else:
                        policy_row["autoscale_in_range"] = False
                        policy_row["issues"].append("autoscale_missing")
                try:
                    atm = int(spec.get("autotermination_minutes"))
                    if atm > auto_terminate_cap:
                        policy_row["autotermination_in_policy"] = False
                        policy_row["issues"].append("autotermination_exceeds_cap")
                except (TypeError, ValueError):
                    policy_row["autotermination_in_policy"] = False
                    policy_row["issues"].append("autotermination_missing_or_invalid")

            policy_row["policy_conformance"] = (
                policy_row["all_tasks_job_cluster_only"]
                and policy_row["autoscale_in_range"]
                and policy_row["autotermination_in_policy"]
                and len(policy_row["issues"]) == 0
            )
        job_policy_rows.append(policy_row)

    if missing_jobs:
        blockers.append({"code": "M10-B2", "message": "Required Databricks jobs are missing."})
    if compute_policy == "job-clusters-only" or "serverless" in compute_policy:
        nonconformant = [row["job_name"] for row in job_policy_rows if not bool(row.get("policy_conformance"))]
        if nonconformant:
            blockers.append({"code": "M10-B2", "message": "Databricks compute policy conformance failed for required jobs."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.C_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.B",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10a_execution": upstream_m10a_execution,
        "upstream_m10a_summary_key": m10a_summary_key,
        "required_handles": handle_values,
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "ssm_surfaces": {
            "workspace_path": ssm_workspace_path,
            "token_path": ssm_token_path,
            "workspace_value_matches_handle": bool(
                workspace_url and ssm_workspace_value and workspace_url.rstrip("/") == ssm_workspace_value.rstrip("/")
            ),
            "token_materialized": bool(ssm_token_value),
            "token_placeholder_detected": is_placeholder(ssm_token_value),
            "token_length": len(ssm_token_value),
        },
        "databricks_probe": dbx_probe,
        "required_job_names": required_job_names,
        "missing_jobs": missing_jobs,
        "job_policy_rows": job_policy_rows,
        "compute_policy_expected": compute_policy,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.B",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": captured_at,
        "phase": "M10.B",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10b_databricks_readiness_snapshot.json": snapshot,
        "m10b_blocker_register.json": register,
        "m10b_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "error": type(exc).__name__, "key": key})

    if upload_errors:
        blockers = list(blockers)
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.B artifacts."})
        blockers = dedupe_blockers(blockers)
        register["upload_errors"] = upload_errors
        register["blockers"] = blockers
        register["blocker_count"] = len(blockers)
        summary["overall_pass"] = False
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = len(blockers)
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "next_gate": summary["next_gate"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{evidence_bucket}/{run_control_prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
