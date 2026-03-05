#!/usr/bin/env python3
"""Build and publish M10.E quality-gate adjudication artifacts."""

from __future__ import annotations

import json
import os
import re
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


def render(pattern: str, values: dict[str, str]) -> str:
    out = pattern
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out


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


def parse_csv_set(value: Any) -> set[str]:
    return {x.strip() for x in str(value or "").split(",") if x.strip()}


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M10E_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10E_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10d_execution = env.get("UPSTREAM_M10D_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10E_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10E_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10d_execution:
        raise SystemExit("UPSTREAM_M10D_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN",
        "LEARNING_FUTURE_TIMESTAMP_POLICY",
        "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS",
        "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS",
        "DBX_WORKSPACE_URL",
        "DBX_JOB_OFS_QUALITY_GATES_V0",
        "SSM_DATABRICKS_WORKSPACE_URL_PATH",
        "SSM_DATABRICKS_TOKEN_PATH",
    ]
    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    resolved_handle_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        resolved_handle_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)
    if missing_handles or placeholder_handles:
        blockers.append({"code": "M10-B5", "message": "Required M10.E handles are missing or placeholder-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != evidence_bucket:
        blockers.append({"code": "M10-B5", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    m10d_summary_key = f"evidence/dev_full/run_control/{upstream_m10d_execution}/m10d_execution_summary.json"
    m10d_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10d_execution}/m10d_ofs_build_execution_snapshot.json"
    m10d_summary: dict[str, Any] | None = None
    m10d_snapshot: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        m10d_summary = s3_get_json(s3, evidence_bucket, m10d_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10d_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B5", "message": "M10.D summary unreadable for M10.E entry gate."})

    try:
        m10d_snapshot = s3_get_json(s3, evidence_bucket, m10d_snapshot_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10d_snapshot_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B5", "message": "M10.D snapshot unreadable for M10.E entry gate."})

    if m10d_summary:
        if not bool(m10d_summary.get("overall_pass")):
            blockers.append({"code": "M10-B5", "message": "M10.D summary is not pass posture."})
        if str(m10d_summary.get("next_gate", "")).strip() != "M10.E_READY":
            blockers.append({"code": "M10-B5", "message": "M10.D next_gate is not M10.E_READY."})
        platform_run_id = str(m10d_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10d_summary.get("scenario_run_id", "")).strip()

    if m10d_snapshot:
        dbx = m10d_snapshot.get("databricks", {}) if isinstance(m10d_snapshot.get("databricks", {}), dict) else {}
        if str(dbx.get("terminal_life_cycle_state", "")).strip() != "TERMINATED":
            blockers.append({"code": "M10-B5", "message": "M10.D Databricks terminal lifecycle state is not TERMINATED."})
        if str(dbx.get("terminal_result_state", "")).strip() != "SUCCESS":
            blockers.append({"code": "M10-B5", "message": "M10.D Databricks terminal result state is not SUCCESS."})

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B5", "message": "Run scope unresolved for M10.E quality adjudication."})

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
            blockers.append({"code": "M10-B5", "message": "Databricks workspace URL SSM parameter unreadable."})
    if ssm_token_path:
        try:
            ssm_token_value = (
                ssm.get_parameter(Name=ssm_token_path, WithDecryption=True)["Parameter"]["Value"].strip()
            )
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": ssm_token_path, "error": type(exc).__name__})
            blockers.append({"code": "M10-B5", "message": "Databricks token SSM parameter unreadable."})

    if workspace_url and ssm_workspace_value and workspace_url.rstrip("/") != ssm_workspace_value.rstrip("/"):
        blockers.append({"code": "M10-B5", "message": "SSM workspace URL does not match DBX_WORKSPACE_URL handle."})
    if is_placeholder(ssm_token_value):
        blockers.append({"code": "M10-B5", "message": "SSM Databricks token appears placeholder-valued."})
    if len(ssm_token_value) < 20:
        blockers.append({"code": "M10-B5", "message": "SSM Databricks token length is below minimum readiness threshold."})

    leakage_report_key = ""
    leakage_report: dict[str, Any] | None = None
    leakage_violation_count = -1
    leakage_forbidden_intersection_count = -1
    leakage_pattern = str(handles.get("LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN", "")).strip()
    if platform_run_id and leakage_pattern:
        leakage_report_key = render(leakage_pattern, {"platform_run_id": platform_run_id})
    if leakage_report_key:
        try:
            leakage_report = s3_get_json(s3, evidence_bucket, leakage_report_key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": leakage_report_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B5", "message": "Leakage guardrail report unreadable for M10.E adjudication."})
    else:
        blockers.append({"code": "M10-B5", "message": "Unable to resolve leakage report path for M10.E adjudication."})

    policy_alignment = {
        "future_timestamp_policy_matches": False,
        "forbidden_truth_set_matches": False,
        "forbidden_future_field_set_matches": False,
    }
    if leakage_report:
        if not bool(leakage_report.get("overall_pass")):
            blockers.append({"code": "M10-B5", "message": "Leakage guardrail report is not pass posture."})
        if str(leakage_report.get("platform_run_id", "")).strip() != platform_run_id:
            blockers.append({"code": "M10-B5", "message": "Leakage report platform_run_id mismatch."})
        if str(leakage_report.get("scenario_run_id", "")).strip() != scenario_run_id:
            blockers.append({"code": "M10-B5", "message": "Leakage report scenario_run_id mismatch."})

        boundary_check = leakage_report.get("boundary_check", {}) if isinstance(leakage_report.get("boundary_check", {}), dict) else {}
        leakage_violation_count = int(boundary_check.get("violation_count", 0))
        if leakage_violation_count != 0:
            blockers.append({"code": "M10-B5", "message": "Leakage guardrail boundary violations are non-zero."})

        truth_surface_check = leakage_report.get("truth_surface_check", {}) if isinstance(leakage_report.get("truth_surface_check", {}), dict) else {}
        forbidden_intersection = truth_surface_check.get("forbidden_intersection", [])
        if not isinstance(forbidden_intersection, list):
            forbidden_intersection = []
        leakage_forbidden_intersection_count = len(forbidden_intersection)
        if leakage_forbidden_intersection_count != 0:
            blockers.append({"code": "M10-B5", "message": "Leakage guardrail forbidden truth intersection is non-zero."})

        policy = leakage_report.get("policy", {}) if isinstance(leakage_report.get("policy", {}), dict) else {}
        expected_future_policy = str(handles.get("LEARNING_FUTURE_TIMESTAMP_POLICY", "")).strip()
        expected_forbidden_truth = parse_csv_set(handles.get("LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS"))
        expected_forbidden_future_fields = parse_csv_set(handles.get("LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS"))
        actual_forbidden_truth = set(policy.get("forbidden_truth_output_ids", []) if isinstance(policy.get("forbidden_truth_output_ids", []), list) else [])
        actual_forbidden_future_fields = set(policy.get("forbidden_future_fields", []) if isinstance(policy.get("forbidden_future_fields", []), list) else [])
        policy_alignment["future_timestamp_policy_matches"] = str(policy.get("future_timestamp_policy", "")).strip() == expected_future_policy
        policy_alignment["forbidden_truth_set_matches"] = actual_forbidden_truth == expected_forbidden_truth
        policy_alignment["forbidden_future_field_set_matches"] = actual_forbidden_future_fields == expected_forbidden_future_fields
        if not all(policy_alignment.values()):
            blockers.append({"code": "M10-B5", "message": "Leakage policy continuity check failed in M10.E adjudication."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.F_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.E",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10d_execution": upstream_m10d_execution,
        "upstream_m10d_summary_key": m10d_summary_key,
        "upstream_m10d_snapshot_key": m10d_snapshot_key,
        "resolved_handle_values": resolved_handle_values,
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
        "leakage_report_key": leakage_report_key,
        "leakage_report_overall_pass": bool(leakage_report.get("overall_pass")) if leakage_report else False,
        "leakage_violation_count": leakage_violation_count,
        "leakage_forbidden_intersection_count": leakage_forbidden_intersection_count,
        "policy_alignment": policy_alignment,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.E",
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
        "phase": "M10.E",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10e_quality_gate_snapshot.json": snapshot,
        "m10e_blocker_register.json": register,
        "m10e_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.E artifacts."})
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
