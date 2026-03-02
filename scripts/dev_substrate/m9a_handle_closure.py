#!/usr/bin/env python3
"""Managed M9.A authority/handle closure artifact builder."""

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
    execution_id = env.get("M9A_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9A_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8_execution = env.get("UPSTREAM_M8_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9A_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9A_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8_execution:
        raise SystemExit("UPSTREAM_M8_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    upstream_m8_summary_key = f"evidence/dev_full/run_control/{upstream_m8_execution}/m8_execution_summary.json"
    upstream_key = f"evidence/dev_full/run_control/{upstream_m8_execution}/m9_handoff_pack.json"
    upstream_handoff: dict[str, Any] | None = None
    upstream_m8_summary: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        upstream_m8_summary = s3_get_json(s3, bucket, upstream_m8_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": upstream_m8_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M9-B1", "message": "M8 execution summary unreadable for M9.A entry continuity."})

    if upstream_m8_summary:
        m8_verdict = str(upstream_m8_summary.get("verdict", "")).strip()
        m8_next_gate = str(upstream_m8_summary.get("next_gate", "")).strip()
        m8_pass = bool(upstream_m8_summary.get("overall_pass"))
        if m8_verdict != "ADVANCE_TO_M9" or m8_next_gate != "M9_READY" or not m8_pass:
            blockers.append({"code": "M9-B1", "message": "M8 summary posture is not ADVANCE_TO_M9/M9_READY."})
        m8i_execution_id = str(upstream_m8_summary.get("upstream_refs", {}).get("m8i_execution_id", "")).strip()
        if m8i_execution_id:
            upstream_key = f"evidence/dev_full/run_control/{m8i_execution_id}/m9_handoff_pack.json"

    try:
        upstream_handoff = s3_get_json(s3, bucket, upstream_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": upstream_key, "error": type(exc).__name__})
        blockers.append({"code": "M9-B1", "message": "M8->M9 handoff evidence unreadable."})

    if upstream_handoff:
        handoff_gate = str(upstream_handoff.get("m9_entry_gate", {}).get("next_gate", "")).strip()
        handoff_verdict = str(upstream_handoff.get("m8_verdict", "")).strip()
        handoff_pass = bool(upstream_handoff.get("m8_overall_pass"))
        if handoff_gate != "M9_READY" or handoff_verdict != "ADVANCE_TO_M9" or not handoff_pass:
            blockers.append({"code": "M9-B1", "message": "M8 handoff is not in M9_READY/ADVANCE_TO_M9 posture."})
        platform_run_id = str(upstream_handoff.get("platform_run_id", "")).strip()
        scenario_run_id = str(upstream_handoff.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M9-B1", "message": "Active run scope (platform_run_id/scenario_run_id) is unresolved."})

    required_handles = [
        "LEARNING_INPUT_READINESS_PATH_PATTERN",
        "LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN",
        "LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN",
        "LEARNING_REPLAY_BASIS_MODE",
        "LEARNING_FEATURE_ASOF_REQUIRED",
        "LEARNING_LABEL_ASOF_REQUIRED",
        "LEARNING_LABEL_MATURITY_DAYS_DEFAULT",
        "LEARNING_FUTURE_TIMESTAMP_POLICY",
        "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS",
        "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS",
        "PHASE_BUDGET_ENVELOPE_PATH_PATTERN",
        "PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN",
    ]

    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    wildcard_handles: list[str] = []
    handle_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        handle_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)
        if is_wildcard(value):
            wildcard_handles.append(key)

    if missing_handles or placeholder_handles or wildcard_handles:
        blockers.append({"code": "M9-B1", "message": "Required M9.A handles are missing, placeholder, or wildcard-valued."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.B_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M9.A",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m8_execution": upstream_m8_execution,
        "upstream_handoff_key": upstream_key,
        "required_handle_count": len(required_handles),
        "resolved_handle_count": len(required_handles) - len(missing_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "wildcard_handles": wildcard_handles,
        "required_handle_values": handle_values,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M9.A",
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
        "phase": "M9.A",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m9a_handle_closure_snapshot.json": snapshot,
        "m9a_blocker_register.json": register,
        "m9a_execution_summary.json": summary,
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
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.A artifacts."})
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
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
