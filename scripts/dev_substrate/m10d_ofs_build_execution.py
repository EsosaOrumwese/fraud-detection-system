#!/usr/bin/env python3
"""Build and publish M10.D OFS build-execution artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
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


def dbx_request_json(
    base_url: str,
    token: str,
    method: str,
    path: str,
    query: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = ""
    if query:
        q = "?" + urllib.parse.urlencode(query, doseq=True)
    url = f"{base_url.rstrip('/')}{path}{q}"
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
        raw = resp.read().decode("utf-8")
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("json_not_object")
    return parsed


def dbx_jobs_by_name(base_url: str, token: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    page_token = ""
    while True:
        query: dict[str, Any] = {"limit": 100}
        if page_token:
            query["page_token"] = page_token
        payload = dbx_request_json(base_url, token, "GET", "/api/2.1/jobs/list", query=query)
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
                    out[name] = job
        next_page = payload.get("next_page_token")
        if not next_page:
            break
        page_token = str(next_page).strip()
    return out


def dbx_import_python_source(
    base_url: str,
    token: str,
    *,
    workspace_root: str,
    workspace_notebook_path: str,
    source_text: str,
) -> None:
    dbx_request_json(
        base_url,
        token,
        "POST",
        "/api/2.0/workspace/mkdirs",
        payload={"path": workspace_root},
    )
    encoded = base64.b64encode(source_text.encode("utf-8")).decode("ascii")
    dbx_request_json(
        base_url,
        token,
        "POST",
        "/api/2.0/workspace/import",
        payload={
            "path": workspace_notebook_path,
            "format": "SOURCE",
            "language": "PYTHON",
            "content": encoded,
            "overwrite": True,
        },
    )


def load_source_file(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"source_missing:{path}")
    source = path.read_text(encoding="utf-8").strip()
    if not source:
        raise RuntimeError(f"source_empty:{path}")
    return source + "\n"


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M10D_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10D_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10c_execution = env.get("UPSTREAM_M10C_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    max_wait_seconds = int(env.get("M10D_MAX_WAIT_SECONDS", "4500").strip() or "4500")
    poll_seconds = int(env.get("M10D_POLL_SECONDS", "20").strip() or "20")

    if not execution_id:
        raise SystemExit("M10D_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10D_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10c_execution:
        raise SystemExit("UPSTREAM_M10C_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "DBX_JOB_OFS_BUILD_V0",
        "DBX_WORKSPACE_URL",
        "SSM_DATABRICKS_WORKSPACE_URL_PATH",
        "SSM_DATABRICKS_TOKEN_PATH",
        "S3_EVIDENCE_BUCKET",
    ]
    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
        elif is_placeholder(value):
            placeholder_handles.append(key)
    if missing_handles or placeholder_handles:
        blockers.append({"code": "M10-B4", "message": "Required M10.D handles are missing or placeholder-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != evidence_bucket:
        blockers.append({"code": "M10-B4", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    m10c_summary_key = f"evidence/dev_full/run_control/{upstream_m10c_execution}/m10c_execution_summary.json"
    m10c_register_key = f"evidence/dev_full/run_control/{upstream_m10c_execution}/m10c_blocker_register.json"
    m10c_summary: dict[str, Any] | None = None
    m10c_register: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""
    try:
        m10c_summary = s3_get_json(s3, evidence_bucket, m10c_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10c_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B4", "message": "M10.C summary unreadable for M10.D entry gate."})

    try:
        m10c_register = s3_get_json(s3, evidence_bucket, m10c_register_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10c_register_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B4", "message": "M10.C blocker register unreadable for M10.D entry gate."})

    if m10c_summary:
        if not bool(m10c_summary.get("overall_pass")):
            blockers.append({"code": "M10-B4", "message": "M10.C summary is not pass posture."})
        if str(m10c_summary.get("next_gate", "")).strip() != "M10.D_READY":
            blockers.append({"code": "M10-B4", "message": "M10.C next_gate is not M10.D_READY."})
        platform_run_id = str(m10c_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10c_summary.get("scenario_run_id", "")).strip()

    if m10c_register is not None:
        if int(m10c_register.get("blocker_count", 0)) != 0:
            blockers.append({"code": "M10-B4", "message": "M10.C blocker register is non-zero."})

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B4", "message": "Run scope unresolved for M10.D execution."})

    workspace_url = str(handles.get("DBX_WORKSPACE_URL", "")).strip()
    ssm_workspace_path = str(handles.get("SSM_DATABRICKS_WORKSPACE_URL_PATH", "")).strip()
    ssm_token_path = str(handles.get("SSM_DATABRICKS_TOKEN_PATH", "")).strip()
    workspace_url_ssm = ""
    token = ""
    if ssm_workspace_path:
        try:
            workspace_url_ssm = (
                ssm.get_parameter(Name=ssm_workspace_path)["Parameter"]["Value"].strip()
            )
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": ssm_workspace_path, "error": type(exc).__name__})
            blockers.append({"code": "M10-B4", "message": "Databricks workspace URL SSM parameter unreadable."})
    if ssm_token_path:
        try:
            token = (
                ssm.get_parameter(Name=ssm_token_path, WithDecryption=True)["Parameter"]["Value"].strip()
            )
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": ssm_token_path, "error": type(exc).__name__})
            blockers.append({"code": "M10-B4", "message": "Databricks token SSM parameter unreadable."})

    if workspace_url and workspace_url_ssm and workspace_url.rstrip("/") != workspace_url_ssm.rstrip("/"):
        blockers.append({"code": "M10-B4", "message": "SSM workspace URL does not match DBX_WORKSPACE_URL handle."})
    if is_placeholder(token):
        blockers.append({"code": "M10-B4", "message": "Databricks token appears placeholder-valued."})
    if len(token) < 20:
        blockers.append({"code": "M10-B4", "message": "Databricks token length is below minimum readiness threshold."})

    build_source_path = Path(env.get("OFS_BUILD_SOURCE_PATH", "platform/databricks/dev_full/ofs_build_v0.py").strip())
    workspace_root = str(
        env.get("DBX_WORKSPACE_PROJECT_ROOT", handles.get("DBX_WORKSPACE_PROJECT_ROOT", "/Shared/fraud-platform/dev_full"))
    ).strip().rstrip("/")
    if not workspace_root.startswith("/"):
        blockers.append({"code": "M10-B4", "message": "DBX workspace project root must be absolute."})
    workspace_python_file = f"{workspace_root}/ofs_build_v0"

    source_sha256 = ""
    source_text = ""
    try:
        source_text = load_source_file(build_source_path)
        source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    except Exception as exc:
        read_errors.append({"surface": str(build_source_path), "error": type(exc).__name__})
        blockers.append({"code": "M10-B4", "message": "OFS build source is missing/unreadable."})

    build_job_name = str(handles.get("DBX_JOB_OFS_BUILD_V0", "")).strip()
    dbx_meta: dict[str, Any] = {
        "workspace_url": workspace_url,
        "workspace_python_file": workspace_python_file,
        "build_job_name": build_job_name,
        "run_id": None,
        "job_id": None,
        "run_page_url": None,
        "terminal_life_cycle_state": None,
        "terminal_result_state": None,
        "terminal_state_message": None,
        "poll_iterations": 0,
        "poll_elapsed_seconds": 0,
    }
    poll_trace: list[dict[str, Any]] = []

    if len(blockers) == 0:
        try:
            dbx_import_python_source(
                workspace_url,
                token,
                workspace_root=workspace_root,
                workspace_notebook_path=workspace_python_file,
                source_text=source_text,
            )
            jobs = dbx_jobs_by_name(workspace_url, token)
            build_job = jobs.get(build_job_name)
            if not isinstance(build_job, dict):
                blockers.append({"code": "M10-B4", "message": "Configured Databricks build job is missing."})
            else:
                job_id = build_job.get("job_id")
                dbx_meta["job_id"] = job_id
                run_now_payload = {
                    "job_id": job_id,
                    "idempotency_token": execution_id,
                    "notebook_params": {
                        "platform_run_id": platform_run_id,
                        "scenario_run_id": scenario_run_id,
                        "m10_execution_id": execution_id,
                    },
                }
                run_now = dbx_request_json(workspace_url, token, "POST", "/api/2.1/jobs/run-now", payload=run_now_payload)
                run_id = run_now.get("run_id")
                if run_id is None:
                    blockers.append({"code": "M10-B4", "message": "Databricks run-now did not return run_id."})
                else:
                    run_id_str = str(run_id).strip()
                    dbx_meta["run_id"] = run_id_str
                    start = time.time()
                    terminal_states = {
                        "TERMINATED",
                        "SKIPPED",
                        "INTERNAL_ERROR",
                        "BLOCKED",
                    }
                    while True:
                        run_payload = dbx_request_json(
                            workspace_url,
                            token,
                            "GET",
                            "/api/2.1/jobs/runs/get",
                            query={"run_id": run_id_str},
                        )
                        state = run_payload.get("state", {}) if isinstance(run_payload.get("state", {}), dict) else {}
                        life_cycle = str(state.get("life_cycle_state", "")).strip()
                        result_state = str(state.get("result_state", "")).strip()
                        state_message = str(state.get("state_message", "")).strip()
                        run_page_url = str(run_payload.get("run_page_url", "")).strip()
                        dbx_meta["run_page_url"] = run_page_url or dbx_meta.get("run_page_url")
                        poll_trace.append(
                            {
                                "captured_at_utc": now_utc(),
                                "life_cycle_state": life_cycle,
                                "result_state": result_state,
                                "state_message": state_message,
                            }
                        )
                        elapsed = int(time.time() - start)
                        dbx_meta["poll_iterations"] = len(poll_trace)
                        dbx_meta["poll_elapsed_seconds"] = elapsed
                        if life_cycle in terminal_states:
                            dbx_meta["terminal_life_cycle_state"] = life_cycle
                            dbx_meta["terminal_result_state"] = result_state
                            dbx_meta["terminal_state_message"] = state_message
                            if not (life_cycle == "TERMINATED" and result_state == "SUCCESS"):
                                blockers.append({"code": "M10-B4", "message": "Databricks OFS build run did not terminate with SUCCESS."})
                            break
                        if elapsed > max_wait_seconds:
                            blockers.append({"code": "M10-B4", "message": "Databricks OFS build run timed out before terminal state."})
                            break
                        time.sleep(max(1, poll_seconds))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, RuntimeError, KeyError) as exc:
            read_errors.append({"surface": "databricks_api", "error": type(exc).__name__})
            blockers.append({"code": "M10-B4", "message": "Databricks OFS build execution failed during API workflow."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.E_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.D",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10c_execution": upstream_m10c_execution,
        "upstream_m10c_summary_key": m10c_summary_key,
        "upstream_m10c_blocker_register_key": m10c_register_key,
        "handles": {
            "DBX_JOB_OFS_BUILD_V0": build_job_name,
            "DBX_WORKSPACE_URL": workspace_url,
            "SSM_DATABRICKS_WORKSPACE_URL_PATH": ssm_workspace_path,
            "SSM_DATABRICKS_TOKEN_PATH": ssm_token_path,
            "S3_EVIDENCE_BUCKET": bucket_from_handle,
        },
        "source_provenance": {
            "repo_source_path": str(build_source_path).replace("\\", "/"),
            "repo_source_sha256": source_sha256,
            "workspace_python_file": workspace_python_file,
        },
        "databricks": dbx_meta,
        "poll_trace_tail": poll_trace[-8:],
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.D",
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
        "phase": "M10.D",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10d_ofs_build_execution_snapshot.json": snapshot,
        "m10d_blocker_register.json": register,
        "m10d_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.D artifacts."})
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
