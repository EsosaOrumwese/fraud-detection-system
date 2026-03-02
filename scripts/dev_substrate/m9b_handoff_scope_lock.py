#!/usr/bin/env python3
"""Managed M9.B handoff continuity + run-scope lock artifact builder."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def stable_scope_hash(platform_run_id: str, scenario_run_id: str, phases: list[str]) -> str:
    canonical = {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "phases": phases,
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M9B_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9B_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8_execution = env.get("UPSTREAM_M8_EXECUTION", "").strip()
    upstream_m9a_execution = env.get("UPSTREAM_M9A_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9B_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9B_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8_execution:
        raise SystemExit("UPSTREAM_M8_EXECUTION is required.")
    if not upstream_m9a_execution:
        raise SystemExit("UPSTREAM_M9A_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    m8_summary_key = f"evidence/dev_full/run_control/{upstream_m8_execution}/m8_execution_summary.json"
    m9a_summary_key = f"evidence/dev_full/run_control/{upstream_m9a_execution}/m9a_execution_summary.json"
    m9a_snapshot_key = f"evidence/dev_full/run_control/{upstream_m9a_execution}/m9a_handle_closure_snapshot.json"

    m8_summary: dict[str, Any] | None = None
    m9a_summary: dict[str, Any] | None = None
    m9a_snapshot: dict[str, Any] | None = None
    m8_handoff: dict[str, Any] | None = None
    m8_handoff_key = ""

    for key_name, key_value in [
        ("m8_summary", m8_summary_key),
        ("m9a_summary", m9a_summary_key),
        ("m9a_snapshot", m9a_snapshot_key),
    ]:
        try:
            payload = s3_get_json(s3, bucket, key_value)
            if key_name == "m8_summary":
                m8_summary = payload
            elif key_name == "m9a_summary":
                m9a_summary = payload
            elif key_name == "m9a_snapshot":
                m9a_snapshot = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key_value, "error": type(exc).__name__})
            blockers.append({"code": "M9-B2", "message": f"Required upstream artifact unreadable: {key_name}."})

    if m8_summary:
        m8_ok = (
            bool(m8_summary.get("overall_pass"))
            and str(m8_summary.get("verdict", "")).strip() == "ADVANCE_TO_M9"
            and str(m8_summary.get("next_gate", "")).strip() == "M9_READY"
        )
        if not m8_ok:
            blockers.append({"code": "M9-B2", "message": "M8 closure posture is not ADVANCE_TO_M9/M9_READY."})
        m8i_execution_id = str(m8_summary.get("upstream_refs", {}).get("m8i_execution_id", "")).strip()
        if not m8i_execution_id:
            blockers.append({"code": "M9-B2", "message": "M8 summary missing upstream m8i execution id."})
        else:
            m8_handoff_key = f"evidence/dev_full/run_control/{m8i_execution_id}/m9_handoff_pack.json"
            try:
                m8_handoff = s3_get_json(s3, bucket, m8_handoff_key)
            except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
                read_errors.append({"surface": m8_handoff_key, "error": type(exc).__name__})
                blockers.append({"code": "M9-B2", "message": "M8 handoff pack unreadable from derived m8i execution root."})

    if m9a_summary:
        m9a_ok = (
            bool(m9a_summary.get("overall_pass"))
            and str(m9a_summary.get("next_gate", "")).strip() == "M9.B_READY"
        )
        if not m9a_ok:
            blockers.append({"code": "M9-B2", "message": "M9.A posture is not pass with next_gate=M9.B_READY."})

    platform_values: list[str] = []
    scenario_values: list[str] = []
    for payload in [m8_summary, m8_handoff, m9a_summary, m9a_snapshot]:
        if not payload:
            continue
        p = str(payload.get("platform_run_id", "")).strip()
        s = str(payload.get("scenario_run_id", "")).strip()
        if p:
            platform_values.append(p)
        if s:
            scenario_values.append(s)

    platform_unique = sorted(set(platform_values))
    scenario_unique = sorted(set(scenario_values))
    platform_run_id = platform_unique[0] if len(platform_unique) == 1 else ""
    scenario_run_id = scenario_unique[0] if len(scenario_unique) == 1 else ""

    if not platform_run_id or len(platform_unique) != 1:
        blockers.append({"code": "M9-B2", "message": "Platform run scope continuity failed across M8/M9A sources."})
    if not scenario_run_id or len(scenario_unique) != 1:
        blockers.append({"code": "M9-B2", "message": "Scenario run scope continuity failed across M8/M9A sources."})

    required_evidence_refs = {}
    if m8_handoff:
        required_evidence_refs = m8_handoff.get("required_evidence_refs", {}) or {}
        if not isinstance(required_evidence_refs, dict) or len(required_evidence_refs) == 0:
            blockers.append({"code": "M9-B2", "message": "M8 handoff required_evidence_refs is empty or invalid."})
        m9_gate = str(m8_handoff.get("m9_entry_gate", {}).get("next_gate", "")).strip()
        if m9_gate != "M9_READY":
            blockers.append({"code": "M9-B2", "message": "M8 handoff entry gate is not M9_READY."})

    locked_subphases = ["M9.B", "M9.C", "M9.D", "M9.E", "M9.F", "M9.G", "M9.H", "M9.I", "M9.J"]
    scope_lock_matrix = [
        {
            "sub_phase": sub_phase,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "lock_mode": "run_scope_strict",
        }
        for sub_phase in locked_subphases
    ]
    scope_lock_hash = stable_scope_hash(platform_run_id, scenario_run_id, locked_subphases) if platform_run_id and scenario_run_id else ""

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.C_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M9.B",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m8_execution": upstream_m8_execution,
        "upstream_m8_summary_key": m8_summary_key,
        "upstream_m8_handoff_key": m8_handoff_key,
        "upstream_m9a_execution": upstream_m9a_execution,
        "upstream_m9a_summary_key": m9a_summary_key,
        "upstream_m9a_snapshot_key": m9a_snapshot_key,
        "platform_scope_candidates": platform_values,
        "scenario_scope_candidates": scenario_values,
        "scope_lock_hash": scope_lock_hash,
        "locked_subphase_count": len(scope_lock_matrix),
        "scope_lock_matrix": scope_lock_matrix,
        "required_evidence_refs": required_evidence_refs,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M9.B",
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
        "phase": "M9.B",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m9b_handoff_scope_snapshot.json": snapshot,
        "m9b_blocker_register.json": register,
        "m9b_execution_summary.json": summary,
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
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.B artifacts."})
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
