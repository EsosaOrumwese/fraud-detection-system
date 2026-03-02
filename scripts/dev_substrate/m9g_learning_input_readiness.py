#!/usr/bin/env python3
"""Managed M9.G learning-input readiness snapshot builder."""

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


def is_wildcard(value: Any) -> bool:
    s = str(value).strip()
    if s in {"*", "**"}:
        return True
    if "SSM_*" in s or "RDS_*" in s or "SVC_*" in s:
        return True
    return False


def render(pattern: str, values: dict[str, str]) -> str:
    out = pattern
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
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


def s3_exists(s3_client: Any, bucket: str, key: str) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


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


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M9G_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9G_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m9c_execution = env.get("UPSTREAM_M9C_EXECUTION", "").strip()
    upstream_m9d_execution = env.get("UPSTREAM_M9D_EXECUTION", "").strip()
    upstream_m9e_execution = env.get("UPSTREAM_M9E_EXECUTION", "").strip()
    upstream_m9f_execution = env.get("UPSTREAM_M9F_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9G_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9G_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m9c_execution:
        raise SystemExit("UPSTREAM_M9C_EXECUTION is required.")
    if not upstream_m9d_execution:
        raise SystemExit("UPSTREAM_M9D_EXECUTION is required.")
    if not upstream_m9e_execution:
        raise SystemExit("UPSTREAM_M9E_EXECUTION is required.")
    if not upstream_m9f_execution:
        raise SystemExit("UPSTREAM_M9F_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "S3_EVIDENCE_BUCKET",
        "LEARNING_INPUT_READINESS_PATH_PATTERN",
        "S3_RUN_CONTROL_ROOT_PATTERN",
    ]
    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    wildcard_handles: list[str] = []
    resolved_handle_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        resolved_handle_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)
        if is_wildcard(value):
            wildcard_handles.append(key)
    if missing_handles or placeholder_handles or wildcard_handles:
        blockers.append({"code": "M9-B7", "message": "Required M9.G handles are missing, placeholder, or wildcard-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != bucket:
        blockers.append({"code": "M9-B7", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    upstream_refs = {
        "m9c": {
            "execution_id": upstream_m9c_execution,
            "summary_key": f"evidence/dev_full/run_control/{upstream_m9c_execution}/m9c_execution_summary.json",
            "expected_next_gate": "M9.D_READY",
        },
        "m9d": {
            "execution_id": upstream_m9d_execution,
            "summary_key": f"evidence/dev_full/run_control/{upstream_m9d_execution}/m9d_execution_summary.json",
            "expected_next_gate": "M9.E_READY",
        },
        "m9e": {
            "execution_id": upstream_m9e_execution,
            "summary_key": f"evidence/dev_full/run_control/{upstream_m9e_execution}/m9e_execution_summary.json",
            "expected_next_gate": "M9.F_READY",
        },
        "m9f": {
            "execution_id": upstream_m9f_execution,
            "summary_key": f"evidence/dev_full/run_control/{upstream_m9f_execution}/m9f_execution_summary.json",
            "expected_next_gate": "M9.G_READY",
        },
    }

    summaries: dict[str, dict[str, Any]] = {}
    for lane, lane_info in upstream_refs.items():
        key = str(lane_info["summary_key"])
        try:
            summaries[lane] = s3_get_json(s3, bucket, key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M9-B7", "message": f"Unable to read upstream summary for {lane}."})

    platform_run_ids: list[str] = []
    scenario_run_ids: list[str] = []
    gate_chain_results: dict[str, dict[str, Any]] = {}
    for lane in ["m9c", "m9d", "m9e", "m9f"]:
        summary = summaries.get(lane, {})
        if summary:
            platform_run_ids.append(str(summary.get("platform_run_id", "")).strip())
            scenario_run_ids.append(str(summary.get("scenario_run_id", "")).strip())
        overall_pass = bool(summary.get("overall_pass"))
        next_gate = str(summary.get("next_gate", "")).strip()
        expected_next_gate = str(upstream_refs[lane]["expected_next_gate"])
        gate_chain_results[lane] = {
            "overall_pass": overall_pass,
            "next_gate": next_gate,
            "expected_next_gate": expected_next_gate,
            "pass": overall_pass and next_gate == expected_next_gate,
        }
        if not gate_chain_results[lane]["pass"]:
            blockers.append({"code": "M9-B7", "message": f"Upstream gate chain mismatch for {lane}."})

    platform_run_id_values = sorted(set([x for x in platform_run_ids if x]))
    scenario_run_id_values = sorted(set([x for x in scenario_run_ids if x]))
    platform_run_id = platform_run_id_values[0] if len(platform_run_id_values) == 1 else ""
    scenario_run_id = scenario_run_id_values[0] if len(scenario_run_id_values) == 1 else ""
    if len(platform_run_id_values) != 1:
        blockers.append({"code": "M9-B7", "message": "platform_run_id is inconsistent across M9.C..M9.F summaries."})
    if len(scenario_run_id_values) != 1:
        blockers.append({"code": "M9-B7", "message": "scenario_run_id is inconsistent across M9.C..M9.F summaries."})

    run_scoped_refs = {
        "m9c_replay_basis_receipt_key": str(summaries.get("m9c", {}).get("run_scoped_receipt_key", "")).strip(),
        "m9e_leakage_guardrail_report_key": str(summaries.get("m9e", {}).get("run_scoped_report_key", "")).strip(),
    }

    run_scoped_ref_checks: dict[str, dict[str, Any]] = {}
    for ref_name, key in run_scoped_refs.items():
        exists = False
        if not key:
            blockers.append({"code": "M9-B7", "message": f"{ref_name} is missing from upstream summary."})
        else:
            try:
                exists = s3_exists(s3, bucket, key)
            except (BotoCoreError, ClientError) as exc:
                read_errors.append({"surface": key, "error": type(exc).__name__})
            if not exists:
                blockers.append({"code": "M9-B7", "message": f"Run-scoped learning artifact is missing: {ref_name}."})
        run_scoped_ref_checks[ref_name] = {"key": key, "exists": exists}

    readiness_path_pattern = str(handles.get("LEARNING_INPUT_READINESS_PATH_PATTERN", "")).strip()
    run_scoped_readiness_key = ""
    if platform_run_id and readiness_path_pattern:
        run_scoped_readiness_key = render(readiness_path_pattern, {"platform_run_id": platform_run_id})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.H_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M9.G",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_refs": {
            "m9c_execution_id": upstream_m9c_execution,
            "m9d_execution_id": upstream_m9d_execution,
            "m9e_execution_id": upstream_m9e_execution,
            "m9f_execution_id": upstream_m9f_execution,
            "m9c_summary_ref": upstream_refs["m9c"]["summary_key"],
            "m9d_summary_ref": upstream_refs["m9d"]["summary_key"],
            "m9e_summary_ref": upstream_refs["m9e"]["summary_key"],
            "m9f_summary_ref": upstream_refs["m9f"]["summary_key"],
        },
        "gate_chain_results": gate_chain_results,
        "run_scope_continuity": {
            "platform_run_id_values": platform_run_id_values,
            "scenario_run_id_values": scenario_run_id_values,
            "single_platform_run_id": platform_run_id,
            "single_scenario_run_id": scenario_run_id,
        },
        "run_scoped_artifact_checks": run_scoped_ref_checks,
        "publish_targets": {
            "run_scoped_readiness_snapshot_key": run_scoped_readiness_key,
        },
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M9.G",
        "phase_id": "P12",
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
        "phase": "M9.G",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
        "run_scoped_readiness_key": run_scoped_readiness_key,
    }

    artifacts = {
        "m9g_learning_input_readiness_snapshot.json": snapshot,
        "m9g_blocker_register.json": register,
        "m9g_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    publish_targets: list[tuple[str, dict[str, Any]]] = [
        (f"{prefix}/m9g_learning_input_readiness_snapshot.json", snapshot),
        (f"{prefix}/m9g_blocker_register.json", register),
        (f"{prefix}/m9g_execution_summary.json", summary),
    ]
    if run_scoped_readiness_key:
        publish_targets.append((run_scoped_readiness_key, snapshot))

    for key, payload in publish_targets:
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"key": key, "error": type(exc).__name__})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.G artifacts."})
        register["blocker_count"] = len(register["blockers"])
        summary["overall_pass"] = False
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = register["blocker_count"]
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "next_gate": summary["next_gate"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{bucket}/{prefix}/",
        "run_scoped_readiness_key": run_scoped_readiness_key,
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
