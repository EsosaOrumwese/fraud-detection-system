#!/usr/bin/env python3
"""Build and publish M11.B SageMaker runtime-readiness artifacts."""

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


def role_name_from_arn(role_arn: str) -> str:
    text = role_arn.strip()
    if ":role/" not in text:
        return text
    return text.rsplit("/", 1)[-1]


def trust_allows_sagemaker(doc: dict[str, Any]) -> bool:
    statements = doc.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        return False
    for row in statements:
        if not isinstance(row, dict):
            continue
        principal = row.get("Principal")
        if not isinstance(principal, dict):
            continue
        service = principal.get("Service")
        values: list[str] = []
        if isinstance(service, str):
            values = [service]
        elif isinstance(service, list):
            values = [str(x) for x in service]
        if any(v.strip().lower() == "sagemaker.amazonaws.com" for v in values):
            return True
    return False


def read_ssm_value(
    ssm_client: Any,
    name: str,
    decrypt: bool,
) -> tuple[str, str]:
    try:
        value = ssm_client.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]
        return str(value).strip(), ""
    except (BotoCoreError, ClientError, KeyError) as exc:
        return "", type(exc).__name__


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M11B_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M11B_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m11a_execution = env.get("UPSTREAM_M11A_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M11B_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M11B_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m11a_execution:
        raise SystemExit("UPSTREAM_M11A_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)

    s3 = boto3.client("s3", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)
    iam = boto3.client("iam", region_name=aws_region)
    sm = boto3.client("sagemaker", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    advisories: list[str] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    m11a_summary_key = f"evidence/dev_full/run_control/{upstream_m11a_execution}/m11a_execution_summary.json"
    m11a_summary: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        m11a_summary = s3_get_json(s3, evidence_bucket, m11a_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m11a_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M11-B2", "message": "M11.A summary unreadable for M11.B entry gate."})

    if m11a_summary is not None:
        if not bool(m11a_summary.get("overall_pass")):
            blockers.append({"code": "M11-B2", "message": "M11.A is not pass posture."})
        if str(m11a_summary.get("next_gate", "")).strip() != "M11.B_READY":
            blockers.append({"code": "M11-B2", "message": "M11.A next_gate is not M11.B_READY."})
        platform_run_id = str(m11a_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m11a_summary.get("scenario_run_id", "")).strip()

    required_handles = [
        "ROLE_SAGEMAKER_EXECUTION",
        "SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH",
        "SSM_MLFLOW_TRACKING_URI_PATH",
        "SM_TRAINING_JOB_NAME_PREFIX",
        "SM_BATCH_TRANSFORM_JOB_NAME_PREFIX",
        "SM_MODEL_PACKAGE_GROUP_NAME",
        "SM_ENDPOINT_NAME",
        "SM_ENDPOINT_COUNT_V0",
        "SM_SERVING_MODE",
    ]
    handle_values: dict[str, Any] = {}
    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    handle_rows: list[dict[str, Any]] = []
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            handle_rows.append(
                {
                    "handle": key,
                    "status": "missing",
                    "value": "",
                    "key": key,
                    "raw_value": None,
                    "state": "missing",
                    "projects_blocker": True,
                }
            )
            continue
        handle_values[key] = value
        placeholder = is_placeholder(value)
        status = "placeholder" if placeholder else "resolved"
        if placeholder:
            placeholder_handles.append(key)
        handle_rows.append(
            {
                "handle": key,
                "status": status,
                "value": value,
                "key": key,
                "raw_value": value,
                "state": status,
                "projects_blocker": status != "resolved",
            }
        )
    if missing_handles or placeholder_handles:
        blockers.append({"code": "M11-B2", "message": "Required M11.B handles are missing or placeholder-valued."})

    role_arn_handle = str(handles.get("ROLE_SAGEMAKER_EXECUTION", "")).strip()
    role_ssm_path = str(handles.get("SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH", "")).strip()
    mlflow_uri_path = str(handles.get("SSM_MLFLOW_TRACKING_URI_PATH", "")).strip()
    package_group_name = str(handles.get("SM_MODEL_PACKAGE_GROUP_NAME", "")).strip()

    role_ssm_value = ""
    mlflow_tracking_uri = ""
    if role_ssm_path and not is_placeholder(role_ssm_path):
        role_ssm_value, role_err = read_ssm_value(ssm, role_ssm_path, decrypt=False)
        if role_err:
            read_errors.append({"surface": role_ssm_path, "error": role_err})
            blockers.append({"code": "M11-B2", "message": "SageMaker execution role ARN SSM path unreadable."})
    else:
        blockers.append({"code": "M11-B2", "message": "SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH is unresolved."})

    if mlflow_uri_path and not is_placeholder(mlflow_uri_path):
        mlflow_tracking_uri, mlflow_err = read_ssm_value(ssm, mlflow_uri_path, decrypt=False)
        if mlflow_err:
            read_errors.append({"surface": mlflow_uri_path, "error": mlflow_err})
            blockers.append({"code": "M11-B2", "message": "MLflow tracking URI SSM path unreadable."})
    else:
        blockers.append({"code": "M11-B2", "message": "SSM_MLFLOW_TRACKING_URI_PATH is unresolved."})

    if role_arn_handle and role_ssm_value and role_arn_handle != role_ssm_value:
        blockers.append({"code": "M11-B2", "message": "ROLE_SAGEMAKER_EXECUTION does not match SSM role ARN value."})
    if is_placeholder(mlflow_tracking_uri):
        blockers.append({"code": "M11-B2", "message": "MLflow tracking URI is placeholder/empty."})

    role_exists = False
    trust_allows_sm = False
    role_name = role_name_from_arn(role_arn_handle)
    if role_name and not is_placeholder(role_name):
        try:
            role_obj = iam.get_role(RoleName=role_name).get("Role", {})
            role_exists = isinstance(role_obj, dict) and bool(role_obj)
            trust_allows_sm = trust_allows_sagemaker(role_obj.get("AssumeRolePolicyDocument", {})) if role_exists else False
            if role_exists and str(role_obj.get("Arn", "")).strip() and role_arn_handle:
                if str(role_obj.get("Arn", "")).strip() != role_arn_handle:
                    blockers.append({"code": "M11-B2", "message": "IAM role ARN does not match ROLE_SAGEMAKER_EXECUTION handle."})
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": f"iam:get_role:{role_name}", "error": type(exc).__name__})
            blockers.append({"code": "M11-B2", "message": "IAM get_role failed for ROLE_SAGEMAKER_EXECUTION."})
    else:
        blockers.append({"code": "M11-B2", "message": "ROLE_SAGEMAKER_EXECUTION role name unresolved."})
    if role_exists and not trust_allows_sm:
        blockers.append({"code": "M11-B2", "message": "ROLE_SAGEMAKER_EXECUTION trust policy does not include sagemaker.amazonaws.com."})

    sm_probe = {
        "list_training_jobs_ok": False,
        "list_model_package_groups_ok": False,
        "training_jobs_observed": 0,
        "model_package_groups_observed": 0,
        "package_group_check": "not_attempted",
    }
    try:
        jobs = sm.list_training_jobs(MaxResults=1).get("TrainingJobSummaries", [])
        sm_probe["list_training_jobs_ok"] = True
        sm_probe["training_jobs_observed"] = len(jobs) if isinstance(jobs, list) else 0
    except (BotoCoreError, ClientError, KeyError) as exc:
        read_errors.append({"surface": "sagemaker:list_training_jobs", "error": type(exc).__name__})
        blockers.append({"code": "M11-B2", "message": "SageMaker list_training_jobs probe failed."})

    try:
        groups = sm.list_model_package_groups(MaxResults=1).get("ModelPackageGroupSummaryList", [])
        sm_probe["list_model_package_groups_ok"] = True
        sm_probe["model_package_groups_observed"] = len(groups) if isinstance(groups, list) else 0
    except (BotoCoreError, ClientError, KeyError) as exc:
        read_errors.append({"surface": "sagemaker:list_model_package_groups", "error": type(exc).__name__})
        blockers.append({"code": "M11-B2", "message": "SageMaker list_model_package_groups probe failed."})

    package_group_ready = False
    if package_group_name and not is_placeholder(package_group_name):
        try:
            sm.describe_model_package_group(ModelPackageGroupName=package_group_name)
            package_group_ready = True
            sm_probe["package_group_check"] = "describe_ok"
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", "")).strip()
            if code in {"ResourceNotFound", "ValidationException"}:
                try:
                    sm.create_model_package_group(
                        ModelPackageGroupName=package_group_name,
                        ModelPackageGroupDescription="M11.B readiness create-if-missing",
                    )
                    package_group_ready = True
                    sm_probe["package_group_check"] = "created"
                except ClientError as cexc:
                    ccode = str(cexc.response.get("Error", {}).get("Code", "")).strip()
                    if ccode in {"AccessDeniedException", "AccessDenied", "UnauthorizedOperation"}:
                        advisories.append("Package-group create denied by IAM boundary; deferred to M11.G owner lane.")
                        sm_probe["package_group_check"] = "access_denied_deferred_to_m11g"
                    else:
                        read_errors.append({"surface": f"sagemaker:create_model_package_group:{package_group_name}", "error": ccode or type(cexc).__name__})
                        blockers.append({"code": "M11-B2", "message": "SageMaker model package group create failed."})
            elif code in {"AccessDeniedException", "AccessDenied", "UnauthorizedOperation"}:
                advisories.append("Package-group describe denied by IAM boundary; deferred to M11.G owner lane.")
                sm_probe["package_group_check"] = "access_denied_deferred_to_m11g"
            else:
                read_errors.append({"surface": f"sagemaker:describe_model_package_group:{package_group_name}", "error": code or type(exc).__name__})
                blockers.append({"code": "M11-B2", "message": "SageMaker model package group describe failed."})
        except (BotoCoreError, KeyError) as exc:
            read_errors.append({"surface": f"sagemaker:describe_model_package_group:{package_group_name}", "error": type(exc).__name__})
            blockers.append({"code": "M11-B2", "message": "SageMaker model package group readiness probe failed."})
    else:
        blockers.append({"code": "M11-B2", "message": "SM_MODEL_PACKAGE_GROUP_NAME is unresolved."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M11.C_READY" if overall_pass else "HOLD_REMEDIATE"
    verdict = "ADVANCE_TO_M11_C" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M11.B",
        "phase_id": "P14",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m11a_execution": upstream_m11a_execution,
        "upstream_m11a_summary_key": m11a_summary_key,
        "required_handles": handle_values,
        "handle_matrix": handle_rows,
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "ssm_checks": {
            "ssm_sagemaker_role_arn_path": role_ssm_path,
            "ssm_sagemaker_role_arn_value": role_ssm_value,
            "role_arn_handle": role_arn_handle,
            "role_arn_parity": bool(role_arn_handle and role_ssm_value and role_arn_handle == role_ssm_value),
            "ssm_mlflow_tracking_uri_path": mlflow_uri_path,
            "ssm_mlflow_tracking_uri_resolved": bool(mlflow_tracking_uri),
            "ssm_mlflow_tracking_uri_value": mlflow_tracking_uri,
        },
        "ssm_surfaces": {
            "role_arn_path": role_ssm_path,
            "mlflow_uri_path": mlflow_uri_path,
            "role_arn_value_matches_handle": bool(role_arn_handle and role_ssm_value and role_arn_handle == role_ssm_value),
            "mlflow_tracking_uri_materialized": bool(mlflow_tracking_uri),
            "mlflow_tracking_uri_placeholder_detected": is_placeholder(mlflow_tracking_uri),
        },
        "iam_role_checks": {
            "role_name": role_name,
            "role_exists": role_exists,
            "trust_allows_sagemaker": trust_allows_sm,
        },
        "sagemaker_probe": sm_probe,
        "package_group_name": package_group_name,
        "package_group_ready": package_group_ready,
        "advisories": advisories,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M11.B",
        "phase_id": "P14",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "advisories": advisories,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": captured_at,
        "phase": "M11.B",
        "phase_id": "P14",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "upstream_refs": {
            "m11a_execution_id": upstream_m11a_execution,
        },
        "artifact_keys": {
            "m11b_sagemaker_readiness_snapshot": f"evidence/dev_full/run_control/{execution_id}/m11b_sagemaker_readiness_snapshot.json",
            "m11b_blocker_register": f"evidence/dev_full/run_control/{execution_id}/m11b_blocker_register.json",
            "m11b_execution_summary": f"evidence/dev_full/run_control/{execution_id}/m11b_execution_summary.json",
        },
    }

    artifacts = {
        "m11b_sagemaker_readiness_snapshot.json": snapshot,
        "m11b_blocker_register.json": register,
        "m11b_execution_summary.json": summary,
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
        blockers.append({"code": "M11-B12", "message": "Failed to publish/readback one or more M11.B artifacts."})
        blockers = dedupe_blockers(blockers)
        register["upload_errors"] = upload_errors
        register["blockers"] = blockers
        register["blocker_count"] = len(blockers)
        summary["overall_pass"] = False
        summary["verdict"] = "HOLD_REMEDIATE"
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
