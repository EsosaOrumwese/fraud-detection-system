#!/usr/bin/env python3
"""Build and publish M10.A authority/handle closure artifacts."""

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
    for token in ("SSM_*", "RDS_*", "SVC_*"):
        if token in s:
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


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M10A_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10A_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m9_execution = env.get("UPSTREAM_M9_EXECUTION", "").strip()
    upstream_m9h_execution = env.get("UPSTREAM_M9H_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10A_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10A_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m9_execution:
        raise SystemExit("UPSTREAM_M9_EXECUTION is required.")
    if not upstream_m9h_execution:
        raise SystemExit("UPSTREAM_M9H_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    m9_summary_key = f"evidence/dev_full/run_control/{upstream_m9_execution}/m9_execution_summary.json"
    m10_handoff_key = f"evidence/dev_full/run_control/{upstream_m9h_execution}/m10_handoff_pack.json"
    m9_summary: dict[str, Any] | None = None
    m10_handoff: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        m9_summary = s3_get_json(s3, evidence_bucket, m9_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m9_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B1", "message": "M9 closure summary unreadable."})

    if m9_summary:
        if not bool(m9_summary.get("overall_pass")):
            blockers.append({"code": "M10-B1", "message": "M9 summary is not pass posture."})
        if str(m9_summary.get("verdict", "")).strip() != "ADVANCE_TO_M10":
            blockers.append({"code": "M10-B1", "message": "M9 verdict is not ADVANCE_TO_M10."})
        if str(m9_summary.get("next_gate", "")).strip() != "M10_READY":
            blockers.append({"code": "M10-B1", "message": "M9 next_gate is not M10_READY."})
        platform_run_id = str(m9_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m9_summary.get("scenario_run_id", "")).strip()

    try:
        m10_handoff = s3_get_json(s3, evidence_bucket, m10_handoff_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10_handoff_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B1", "message": "M10 handoff pack unreadable from M9.H."})

    if m10_handoff:
        if str(m10_handoff.get("p12_verdict", "")).strip() != "ADVANCE_TO_P13":
            blockers.append({"code": "M10-B1", "message": "M10 handoff p12_verdict is not ADVANCE_TO_P13."})
        if not bool(m10_handoff.get("p12_overall_pass")):
            blockers.append({"code": "M10-B1", "message": "M10 handoff p12_overall_pass is false."})
        if str(m10_handoff.get("m10_entry_gate", {}).get("next_gate", "")).strip() != "M10_READY":
            blockers.append({"code": "M10-B1", "message": "M10 handoff entry gate is not M10_READY."})

        h_platform = str(m10_handoff.get("platform_run_id", "")).strip()
        h_scenario = str(m10_handoff.get("scenario_run_id", "")).strip()
        if platform_run_id and h_platform and platform_run_id != h_platform:
            blockers.append({"code": "M10-B1", "message": "platform_run_id mismatch between M9 summary and M10 handoff."})
        if scenario_run_id and h_scenario and scenario_run_id != h_scenario:
            blockers.append({"code": "M10-B1", "message": "scenario_run_id mismatch between M9 summary and M10 handoff."})
        if not platform_run_id:
            platform_run_id = h_platform
        if not scenario_run_id:
            scenario_run_id = h_scenario

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B1", "message": "Run scope unresolved for M10 entry."})

    required_handles = [
        "DBX_WORKSPACE_URL",
        "DBX_JOB_OFS_BUILD_V0",
        "DBX_JOB_OFS_QUALITY_GATES_V0",
        "OFS_MANIFEST_PATH_PATTERN",
        "OFS_FINGERPRINT_PATH_PATTERN",
        "OFS_TIME_BOUND_AUDIT_PATH_PATTERN",
        "DATA_TABLE_FORMAT_PRIMARY",
        "DATA_TABLE_CATALOG",
        "OFS_ICEBERG_DATABASE",
        "OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN",
        "PHASE_BUDGET_ENVELOPE_PATH_PATTERN",
        "PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN",
    ]

    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    wildcard_handles: list[str] = []
    handle_rows: list[dict[str, Any]] = []
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            handle_rows.append({"key": key, "raw_value": None, "state": "missing", "projects_blocker": True})
            continue
        placeholder = is_placeholder(value)
        wildcard = is_wildcard(value)
        state = "resolved"
        if placeholder:
            state = "placeholder"
            placeholder_handles.append(key)
        elif wildcard:
            state = "wildcard"
            wildcard_handles.append(key)
        handle_rows.append(
            {
                "key": key,
                "raw_value": value,
                "state": state,
                "projects_blocker": state != "resolved",
            }
        )

    if missing_handles or placeholder_handles or wildcard_handles:
        blockers.append({"code": "M10-B1", "message": "Required M10.A handles are missing, placeholder, or wildcard-valued."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.B_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.A",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m9_execution": upstream_m9_execution,
        "upstream_m9h_execution": upstream_m9h_execution,
        "upstream_m9_summary_key": m9_summary_key,
        "upstream_m10_handoff_key": m10_handoff_key,
        "required_handle_count": len(required_handles),
        "resolved_handle_count": len(required_handles) - len(missing_handles) - len(placeholder_handles) - len(wildcard_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "wildcard_handles": wildcard_handles,
        "handle_matrix": handle_rows,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.A",
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
        "phase": "M10.A",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10a_handle_closure_snapshot.json": snapshot,
        "m10a_blocker_register.json": register,
        "m10a_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.A artifacts."})
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
