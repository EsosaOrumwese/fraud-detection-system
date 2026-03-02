#!/usr/bin/env python3
"""Managed M8.B runtime identity + lock readiness artifact builder."""

from __future__ import annotations

import hashlib
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


def has_handle_declaration(path: Path, handle_name: str) -> bool:
    rx = re.compile(rf"^\* `{re.escape(handle_name)}`\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        if rx.match(line.strip()):
            return True
    return False


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
    return json.loads(body)


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
    return role_arn.rsplit("/", 1)[-1]


def deterministic_lock_key(lock_pattern: str, platform_run_id: str) -> dict[str, Any]:
    rendered = lock_pattern.replace("{platform_run_id}", platform_run_id)
    digest_hex = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]
    lock_key_int = int(digest_hex, 16)
    return {
        "lock_key_pattern": lock_pattern,
        "rendered_lock_key": rendered,
        "advisory_lock_key_uint64": str(lock_key_int),
    }


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M8B_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M8B_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8a_execution = env.get("UPSTREAM_M8A_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M8B_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M8B_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8a_execution:
        raise SystemExit("UPSTREAM_M8A_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)
    iam = boto3.client("iam", region_name=aws_region)
    eks = boto3.client("eks", region_name=aws_region)
    ssm = boto3.client("ssm", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    upstream_key = f"evidence/dev_full/run_control/{upstream_m8a_execution}/m8a_execution_summary.json"
    upstream_summary: dict[str, Any] | None = None
    try:
        upstream_summary = s3_get_json(s3, bucket, upstream_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": upstream_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B2", "message": "Upstream M8.A summary is unreadable."})

    platform_run_id = env.get("PLATFORM_RUN_ID", "").strip()
    scenario_run_id = env.get("SCENARIO_RUN_ID", "").strip()

    if upstream_summary:
        upstream_ok = bool(upstream_summary.get("overall_pass")) and str(upstream_summary.get("next_gate", "")).strip() == "M8.B_READY"
        if not upstream_ok:
            blockers.append({"code": "M8-B2", "message": "M8.A upstream gate is not M8.B_READY."})
        if not platform_run_id:
            platform_run_id = str(upstream_summary.get("platform_run_id", "")).strip()
        if not scenario_run_id:
            scenario_run_id = str(upstream_summary.get("scenario_run_id", "")).strip()
    else:
        upstream_ok = False

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B2", "message": "Active run scope is unresolved for M8.B."})

    required_handles = [
        "ROLE_EKS_IRSA_OBS_GOV",
        "EKS_CLUSTER_NAME",
        "EKS_NAMESPACE_OBS_GOV",
        "REPORTER_LOCK_BACKEND",
        "REPORTER_LOCK_KEY_PATTERN",
        "SSM_AURORA_ENDPOINT_PATH",
        "SSM_AURORA_USERNAME_PATH",
        "SSM_AURORA_PASSWORD_PATH",
        "AURORA_DB_NAME",
    ]

    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    resolved_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        resolved_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)

    if missing_handles or placeholder_handles:
        blockers.append({"code": "M8-B2", "message": "Required M8.B handles are missing or placeholder-valued."})

    entrypoint_reporter_declared = has_handle_declaration(HANDLES_PATH, "ENTRYPOINT_REPORTER")
    if not entrypoint_reporter_declared:
        blockers.append({"code": "M8-B2", "message": "ENTRYPOINT_REPORTER declaration missing in handle registry."})

    identity_probe: dict[str, Any] = {
        "role_exists": False,
        "eks_cluster_status": "UNREADABLE",
        "obs_gov_namespace_handle": str(handles.get("EKS_NAMESPACE_OBS_GOV", "")),
    }
    lock_probe: dict[str, Any] = {
        "backend": str(handles.get("REPORTER_LOCK_BACKEND", "")),
        "lock_key_rendering": None,
        "aurora_ssm_values_readable": False,
        "aurora_ssm_paths": {
            "endpoint": str(handles.get("SSM_AURORA_ENDPOINT_PATH", "")),
            "username": str(handles.get("SSM_AURORA_USERNAME_PATH", "")),
            "password": str(handles.get("SSM_AURORA_PASSWORD_PATH", "")),
        },
    }

    role_arn = str(handles.get("ROLE_EKS_IRSA_OBS_GOV", ""))
    if role_arn:
        try:
            iam.get_role(RoleName=role_name_from_arn(role_arn))
            identity_probe["role_exists"] = True
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": "iam:GetRole", "error": type(exc).__name__})
            blockers.append({"code": "M8-B2", "message": "ROLE_EKS_IRSA_OBS_GOV is unreadable/non-existent."})

    eks_cluster_name = str(handles.get("EKS_CLUSTER_NAME", ""))
    if eks_cluster_name:
        try:
            cluster = eks.describe_cluster(name=eks_cluster_name)["cluster"]
            identity_probe["eks_cluster_status"] = str(cluster.get("status", "UNKNOWN"))
            if identity_probe["eks_cluster_status"] != "ACTIVE":
                blockers.append({"code": "M8-B2", "message": "EKS cluster for M8.B is not ACTIVE."})
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": "eks:DescribeCluster", "error": type(exc).__name__})
            blockers.append({"code": "M8-B2", "message": "EKS cluster is unreadable for M8.B."})

    if platform_run_id and str(handles.get("REPORTER_LOCK_KEY_PATTERN", "")):
        lock_probe["lock_key_rendering"] = deterministic_lock_key(
            str(handles.get("REPORTER_LOCK_KEY_PATTERN", "")),
            platform_run_id,
        )

    backend = str(handles.get("REPORTER_LOCK_BACKEND", ""))
    if backend == "aurora_advisory_lock":
        endpoint_path = str(handles.get("SSM_AURORA_ENDPOINT_PATH", ""))
        username_path = str(handles.get("SSM_AURORA_USERNAME_PATH", ""))
        password_path = str(handles.get("SSM_AURORA_PASSWORD_PATH", ""))
        try:
            endpoint = ssm.get_parameter(Name=endpoint_path, WithDecryption=True)["Parameter"]["Value"]
            username = ssm.get_parameter(Name=username_path, WithDecryption=True)["Parameter"]["Value"]
            password = ssm.get_parameter(Name=password_path, WithDecryption=True)["Parameter"]["Value"]
            lock_probe["aurora_ssm_values_readable"] = True
            lock_probe["aurora_endpoint_preview"] = endpoint[:64]
            lock_probe["aurora_username_preview"] = username[:32]
            lock_probe["aurora_password_length"] = len(password)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": "ssm:GetParameter(aurora)", "error": type(exc).__name__})
            blockers.append({"code": "M8-B2", "message": "Aurora lock backend SSM surfaces unreadable."})
    else:
        blockers.append({"code": "M8-B2", "message": f"Unsupported REPORTER_LOCK_BACKEND for M8.B: {backend}"})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.C_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M8.B",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m8a_execution": upstream_m8a_execution,
        "upstream_m8a_summary_key": upstream_key,
        "upstream_ok": upstream_ok,
        "required_handle_count": len(required_handles),
        "resolved_handle_count": len(required_handles) - len(missing_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "resolved_handle_values": resolved_values,
        "entrypoint_reporter_declared": entrypoint_reporter_declared,
        "identity_probe": identity_probe,
        "lock_probe": lock_probe,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M8.B",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": captured,
        "phase": "M8.B",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m8b_runtime_lock_readiness_snapshot.json": snapshot,
        "m8b_blocker_register.json": register,
        "m8b_execution_summary.json": summary,
    }

    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        key = f"{prefix}/{name}"
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "error": type(exc).__name__, "key": key})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.B artifacts."})
        register["blocker_count"] = len(register["blockers"])
        summary["overall_pass"] = False
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = register["blocker_count"]
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{bucket}/{prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
