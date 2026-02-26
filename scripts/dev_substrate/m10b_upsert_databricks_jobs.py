#!/usr/bin/env python3
"""Upsert required Databricks jobs for M10.B readiness."""

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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dbx_request(
    base_url: str,
    token: str,
    method: str,
    path: str,
    query: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qs = ""
    if query:
        qs = "?" + urllib.parse.urlencode(query, doseq=True)
    url = f"{base_url.rstrip('/')}{path}{qs}"
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read().decode("utf-8")
    if not content:
        return {}
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("json_not_object")
    return parsed


def select_spark_version(base_url: str, token: str) -> str:
    payload = dbx_request(base_url, token, "GET", "/api/2.0/clusters/spark-versions")
    versions = payload.get("versions", [])
    if not isinstance(versions, list) or not versions:
        raise RuntimeError("no_spark_versions")
    for v in versions:
        if not isinstance(v, dict):
            continue
        key = str(v.get("key", "")).strip()
        name = str(v.get("name", "")).lower()
        if key and "lts" in name:
            return key
    for v in versions:
        if not isinstance(v, dict):
            continue
        key = str(v.get("key", "")).strip()
        if key:
            return key
    raise RuntimeError("spark_version_unresolved")


def select_node_type(base_url: str, token: str) -> str:
    payload = dbx_request(base_url, token, "GET", "/api/2.0/clusters/list-node-types")
    node_types = payload.get("node_types", [])
    if not isinstance(node_types, list) or not node_types:
        raise RuntimeError("no_node_types")
    preferred = ["i3.xlarge", "i3.2xlarge", "m5d.xlarge", "m5.xlarge"]
    by_id = {}
    for node in node_types:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_type_id", "")).strip()
        if node_id:
            by_id[node_id] = node
    for node_id in preferred:
        if node_id in by_id:
            return node_id
    for node in node_types:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_type_id", "")).strip()
        if node_id:
            return node_id
    raise RuntimeError("node_type_unresolved")


def list_jobs(base_url: str, token: str) -> dict[str, dict[str, Any]]:
    jobs_by_name: dict[str, dict[str, Any]] = {}
    page_token = None
    while True:
        query: dict[str, Any] = {"limit": 100}
        if page_token:
            query["page_token"] = page_token
        payload = dbx_request(base_url, token, "GET", "/api/2.1/jobs/list", query=query)
        jobs = payload.get("jobs", [])
        if isinstance(jobs, list):
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                settings = job.get("settings", {})
                if not isinstance(settings, dict):
                    continue
                name = str(settings.get("name", "")).strip()
                if name:
                    jobs_by_name[name] = job
        next_page_token = payload.get("next_page_token")
        if not next_page_token:
            break
        page_token = str(next_page_token)
    return jobs_by_name


def build_job_settings(
    *,
    job_name: str,
    task_key: str,
    python_file: str,
    spark_version: str,
    node_type_id: str,
    min_workers: int,
    max_workers: int,
    auto_terminate_minutes: int,
) -> dict[str, Any]:
    return {
        "name": job_name,
        "max_concurrent_runs": 1,
        "tasks": [
            {
                "task_key": task_key,
                "job_cluster_key": "main_cluster",
                "spark_python_task": {
                    "python_file": python_file,
                    "parameters": [],
                },
                "timeout_seconds": 7200,
            }
        ],
        "job_clusters": [
            {
                "job_cluster_key": "main_cluster",
                "new_cluster": {
                    "spark_version": spark_version,
                    "node_type_id": node_type_id,
                    "autoscale": {
                        "min_workers": min_workers,
                        "max_workers": max_workers,
                    },
                    "autotermination_minutes": auto_terminate_minutes,
                },
            }
        ],
    }


def build_serverless_job_settings(
    *,
    job_name: str,
    task_key: str,
    python_file: str,
) -> dict[str, Any]:
    return {
        "name": job_name,
        "max_concurrent_runs": 1,
        "tasks": [
            {
                "task_key": task_key,
                "spark_python_task": {
                    "python_file": python_file,
                    "parameters": [],
                },
                "environment_key": "default",
                "timeout_seconds": 7200,
            }
        ],
        "environments": [
            {
                "environment_key": "default",
                "spec": {
                    "client": "1",
                    "dependencies": [],
                },
            }
        ],
    }


def _workspace_serverless_only(exc: urllib.error.HTTPError) -> bool:
    try:
        body = exc.read().decode("utf-8", "ignore")
    except Exception:
        body = ""
    message = str(body or exc.reason or "")
    return bool(re.search(r"only\s+serverless\s+compute\s+is\s+supported", message, re.IGNORECASE))


def main() -> int:
    workspace_url = os.environ.get("DBX_WORKSPACE_URL", "").strip()
    token = os.environ.get("DBX_TOKEN", "").strip()
    build_job_name = os.environ.get("DBX_JOB_OFS_BUILD_V0", "").strip()
    quality_job_name = os.environ.get("DBX_JOB_OFS_QUALITY_GATES_V0", "").strip()
    autoscale = os.environ.get("DBX_AUTOSCALE_WORKERS", "1-8").strip()
    auto_terminate = int(os.environ.get("DBX_AUTO_TERMINATE_MINUTES", "20").strip())
    receipt_path = Path(os.environ.get("M10B_DBX_JOB_UPSERT_RECEIPT_PATH", "").strip())

    if not workspace_url:
        raise SystemExit("DBX_WORKSPACE_URL is required.")
    if not token:
        raise SystemExit("DBX_TOKEN is required.")
    if not build_job_name or not quality_job_name:
        raise SystemExit("DBX required job names are missing.")
    if not receipt_path:
        raise SystemExit("M10B_DBX_JOB_UPSERT_RECEIPT_PATH is required.")

    if "-" not in autoscale:
        raise SystemExit("DBX_AUTOSCALE_WORKERS must be in min-max format.")
    min_str, max_str = autoscale.split("-", 1)
    min_workers = int(min_str)
    max_workers = int(max_str)
    if min_workers < 1 or max_workers < min_workers:
        raise SystemExit("Invalid autoscale range.")

    captured_at = now_utc()
    outcome: dict[str, Any] = {
        "captured_at_utc": captured_at,
        "overall_pass": False,
        "workspace_url": workspace_url,
        "compute_mode": "job_clusters",
        "jobs": [],
        "errors": [],
    }

    try:
        spark_version = select_spark_version(workspace_url, token)
        node_type = select_node_type(workspace_url, token)
        existing = list_jobs(workspace_url, token)

        desired = [
            {
                "name": build_job_name,
                "settings": build_job_settings(
                    job_name=build_job_name,
                    task_key="ofs_build",
                    python_file="dbfs:/fraud-platform/dev_full/ofs_build_v0.py",
                    spark_version=spark_version,
                    node_type_id=node_type,
                    min_workers=min_workers,
                    max_workers=max_workers,
                    auto_terminate_minutes=auto_terminate,
                ),
            },
            {
                "name": quality_job_name,
                "settings": build_job_settings(
                    job_name=quality_job_name,
                    task_key="ofs_quality",
                    python_file="dbfs:/fraud-platform/dev_full/ofs_quality_v0.py",
                    spark_version=spark_version,
                    node_type_id=node_type,
                    min_workers=min_workers,
                    max_workers=max_workers,
                    auto_terminate_minutes=auto_terminate,
                ),
            },
        ]

        for item in desired:
            name = item["name"]
            settings = item["settings"]
            row: dict[str, Any] = {"name": name, "action": "", "job_id": None}
            existing_job = existing.get(name)
            if existing_job is None:
                created = dbx_request(
                    workspace_url,
                    token,
                    "POST",
                    "/api/2.1/jobs/create",
                    payload=settings,
                )
                row["action"] = "created"
                row["job_id"] = created.get("job_id")
            else:
                job_id = existing_job.get("job_id")
                row["action"] = "reset"
                row["job_id"] = job_id
                dbx_request(
                    workspace_url,
                    token,
                    "POST",
                    "/api/2.1/jobs/reset",
                    payload={"job_id": job_id, "new_settings": settings},
                )
            outcome["jobs"].append(row)

        outcome["spark_version"] = spark_version
        outcome["node_type_id"] = node_type
        outcome["overall_pass"] = True
    except urllib.error.HTTPError as exc:
        if _workspace_serverless_only(exc):
            outcome["compute_mode"] = "serverless"
            outcome["jobs"] = []
            desired = [
                {
                    "name": build_job_name,
                    "settings": build_serverless_job_settings(
                        job_name=build_job_name,
                        task_key="ofs_build",
                        python_file="dbfs:/fraud-platform/dev_full/ofs_build_v0.py",
                    ),
                },
                {
                    "name": quality_job_name,
                    "settings": build_serverless_job_settings(
                        job_name=quality_job_name,
                        task_key="ofs_quality",
                        python_file="dbfs:/fraud-platform/dev_full/ofs_quality_v0.py",
                    ),
                },
            ]
            try:
                existing = list_jobs(workspace_url, token)
                for item in desired:
                    name = item["name"]
                    settings = item["settings"]
                    row: dict[str, Any] = {"name": name, "action": "", "job_id": None}
                    existing_job = existing.get(name)
                    if existing_job is None:
                        created = dbx_request(
                            workspace_url,
                            token,
                            "POST",
                            "/api/2.1/jobs/create",
                            payload=settings,
                        )
                        row["action"] = "created"
                        row["job_id"] = created.get("job_id")
                    else:
                        job_id = existing_job.get("job_id")
                        row["action"] = "reset"
                        row["job_id"] = job_id
                        dbx_request(
                            workspace_url,
                            token,
                            "POST",
                            "/api/2.1/jobs/reset",
                            payload={"job_id": job_id, "new_settings": settings},
                        )
                    outcome["jobs"].append(row)
                outcome["overall_pass"] = True
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, RuntimeError, KeyError) as retry_exc:
                outcome["errors"].append({"type": type(retry_exc).__name__, "message": str(retry_exc)})
                outcome["overall_pass"] = False
        else:
            outcome["errors"].append({"type": type(exc).__name__, "message": str(exc)})
            outcome["overall_pass"] = False
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, RuntimeError, KeyError) as exc:
        outcome["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        outcome["overall_pass"] = False

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(outcome, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"overall_pass": outcome["overall_pass"], "receipt_path": str(receipt_path)}, ensure_ascii=True))
    return 0 if outcome["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
