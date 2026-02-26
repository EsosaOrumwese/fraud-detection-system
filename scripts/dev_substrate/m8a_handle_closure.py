#!/usr/bin/env python3
"""Managed M8.A authority/handle closure artifact builder.

This script validates M7->M8 handoff continuity and required P11 handle closure,
then writes local and durable run-control artifacts for M8.A.
"""

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


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M8A_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M8A_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m7_execution = env.get("UPSTREAM_M7_EXECUTION", "").strip()

    if not execution_id:
        raise SystemExit("M8A_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M8A_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m7_execution:
        raise SystemExit("UPSTREAM_M7_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3")

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    upstream_key = f"evidence/dev_full/run_control/{upstream_m7_execution}/m8_handoff_pack.json"
    upstream_handoff: dict[str, Any] | None = None
    platform_run_id = env.get("PLATFORM_RUN_ID", "").strip()
    scenario_run_id = env.get("SCENARIO_RUN_ID", "").strip()

    try:
        upstream_handoff = s3_get_json(s3, bucket, upstream_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": upstream_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B1", "message": "M7->M8 handoff evidence unreadable."})

    if upstream_handoff:
        handoff_gate = str(upstream_handoff.get("m8_entry_gate", "")).strip()
        handoff_verdict = str(upstream_handoff.get("m7_verdict", "")).strip()
        if handoff_gate != "M8_READY" or handoff_verdict != "ADVANCE_TO_M8":
            blockers.append({"code": "M8-B1", "message": "M7 handoff is not in M8_READY/ADVANCE_TO_M8 posture."})
        if not platform_run_id:
            platform_run_id = str(upstream_handoff.get("platform_run_id", "")).strip()
        if not scenario_run_id:
            scenario_run_id = str(upstream_handoff.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B1", "message": "Active run scope (platform_run_id/scenario_run_id) is unresolved."})

    required_handles = [
        "SPINE_RUN_REPORT_PATH_PATTERN",
        "SPINE_RECONCILIATION_PATH_PATTERN",
        "SPINE_NON_REGRESSION_PACK_PATTERN",
        "GOV_APPEND_LOG_PATH_PATTERN",
        "GOV_RUN_CLOSE_MARKER_PATH_PATTERN",
        "REPORTER_LOCK_BACKEND",
        "REPORTER_LOCK_KEY_PATTERN",
        "ROLE_EKS_IRSA_OBS_GOV",
        "EKS_NAMESPACE_OBS_GOV",
        "S3_EVIDENCE_BUCKET",
        "S3_EVIDENCE_RUN_ROOT_PATTERN",
        "PHASE_BUDGET_ENVELOPE_PATH_PATTERN",
        "PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN",
        "M7_HANDOFF_PACK_PATH_PATTERN",
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
        blockers.append({"code": "M8-B1", "message": "Required M8.A handles are missing or placeholder-valued."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.B_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M8.A",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m7_execution": upstream_m7_execution,
        "upstream_handoff_key": upstream_key,
        "required_handle_count": len(required_handles),
        "resolved_handle_count": len(required_handles) - len(missing_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "required_handle_values": handle_values,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M8.A",
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
        "phase": "M8.A",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m8a_handle_closure_snapshot.json": snapshot,
        "m8a_blocker_register.json": register,
        "m8a_execution_summary.json": summary,
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
        register["blockers"].append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.A artifacts."})
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
