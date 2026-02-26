#!/usr/bin/env python3
"""Managed M9.C replay-basis receipt closure artifact builder."""

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


def render_pattern(pattern: str, platform_run_id: str) -> str:
    return pattern.replace("{platform_run_id}", platform_run_id)


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


def stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def as_int(value: Any) -> int:
    return int(str(value).strip())


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M9C_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9C_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m9b_execution = env.get("UPSTREAM_M9B_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9C_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9C_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m9b_execution:
        raise SystemExit("UPSTREAM_M9B_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "LEARNING_REPLAY_BASIS_MODE",
        "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
        "RECEIPT_SUMMARY_PATH_PATTERN",
        "LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN",
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
        blockers.append({"code": "M9-B3", "message": "Required M9.C handles are missing, placeholder, or wildcard-valued."})

    mode = str(handles.get("LEARNING_REPLAY_BASIS_MODE", "")).strip()
    if mode != "origin_offset_ranges":
        blockers.append({"code": "M9-B3", "message": "LEARNING_REPLAY_BASIS_MODE is not origin_offset_ranges."})

    m9b_summary_key = f"evidence/dev_full/run_control/{upstream_m9b_execution}/m9b_execution_summary.json"
    m9b_snapshot_key = f"evidence/dev_full/run_control/{upstream_m9b_execution}/m9b_handoff_scope_snapshot.json"
    m9b_summary: dict[str, Any] | None = None
    m9b_snapshot: dict[str, Any] | None = None

    for key_name, key_value in [("m9b_summary", m9b_summary_key), ("m9b_snapshot", m9b_snapshot_key)]:
        try:
            payload = s3_get_json(s3, bucket, key_value)
            if key_name == "m9b_summary":
                m9b_summary = payload
            else:
                m9b_snapshot = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key_value, "error": type(exc).__name__})
            blockers.append({"code": "M9-B3", "message": f"Required upstream artifact unreadable: {key_name}."})

    platform_run_id = ""
    scenario_run_id = ""
    if m9b_summary:
        upstream_ok = bool(m9b_summary.get("overall_pass")) and str(m9b_summary.get("next_gate", "")).strip() == "M9.C_READY"
        if not upstream_ok:
            blockers.append({"code": "M9-B3", "message": "M9.B posture is not pass with next_gate=M9.C_READY."})
        platform_run_id = str(m9b_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m9b_summary.get("scenario_run_id", "")).strip()

    if m9b_snapshot:
        snap_platform = str(m9b_snapshot.get("platform_run_id", "")).strip()
        snap_scenario = str(m9b_snapshot.get("scenario_run_id", "")).strip()
        if platform_run_id and snap_platform and platform_run_id != snap_platform:
            blockers.append({"code": "M9-B3", "message": "Platform run scope mismatch between M9.B summary and snapshot."})
        if scenario_run_id and snap_scenario and scenario_run_id != snap_scenario:
            blockers.append({"code": "M9-B3", "message": "Scenario run scope mismatch between M9.B summary and snapshot."})
        if not platform_run_id:
            platform_run_id = snap_platform
        if not scenario_run_id:
            scenario_run_id = snap_scenario

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M9-B3", "message": "Active run scope is unresolved for M9.C."})

    offsets_key = ""
    receipt_summary_key = ""
    replay_receipt_run_key = ""
    kafka_offsets_snapshot: dict[str, Any] | None = None
    receipt_summary: dict[str, Any] | None = None

    if platform_run_id:
        offsets_key = render_pattern(str(handles.get("KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", "")), platform_run_id)
        receipt_summary_key = render_pattern(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")), platform_run_id)
        replay_receipt_run_key = render_pattern(str(handles.get("LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN", "")), platform_run_id)
        for key_name, key_value in [("kafka_offsets_snapshot", offsets_key), ("receipt_summary", receipt_summary_key)]:
            try:
                payload = s3_get_json(s3, bucket, key_value)
                if key_name == "kafka_offsets_snapshot":
                    kafka_offsets_snapshot = payload
                else:
                    receipt_summary = payload
            except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
                read_errors.append({"surface": key_value, "error": type(exc).__name__})
                blockers.append({"code": "M9-B3", "message": f"Run-scoped replay source unreadable: {key_name}."})

    origin_offset_ranges: list[dict[str, Any]] = []
    offset_validation_errors: list[str] = []
    if kafka_offsets_snapshot:
        topics = kafka_offsets_snapshot.get("topics")
        if not isinstance(topics, list) or len(topics) == 0:
            blockers.append({"code": "M9-B3", "message": "kafka_offsets_snapshot.topics is missing or empty."})
        else:
            for i, row in enumerate(topics):
                if not isinstance(row, dict):
                    offset_validation_errors.append(f"topics[{i}] not object")
                    continue
                topic = str(row.get("topic", "")).strip()
                partition_raw = row.get("partition")
                first_raw = row.get("first_offset")
                last_raw = row.get("last_offset")
                observed_raw = row.get("observed_count")
                if not topic:
                    offset_validation_errors.append(f"topics[{i}].topic missing")
                    continue
                try:
                    partition = as_int(partition_raw)
                    first_offset = as_int(first_raw)
                    last_offset = as_int(last_raw)
                    observed_count = as_int(observed_raw)
                except (ValueError, TypeError):
                    offset_validation_errors.append(f"topics[{i}] offset/partition parse failure")
                    continue
                if first_offset > last_offset:
                    offset_validation_errors.append(f"topics[{i}] first_offset greater than last_offset")
                    continue
                if observed_count <= 0:
                    offset_validation_errors.append(f"topics[{i}] observed_count <= 0")
                    continue
                origin_offset_ranges.append(
                    {
                        "topic": topic,
                        "partition": partition,
                        "first_offset": str(first_offset),
                        "last_offset": str(last_offset),
                        "observed_count": observed_count,
                    }
                )

    if offset_validation_errors:
        blockers.append({"code": "M9-B3", "message": "Offset-range validation failed in kafka_offsets_snapshot."})

    if not origin_offset_ranges:
        blockers.append({"code": "M9-B3", "message": "No valid origin_offset ranges were materialized."})

    receipt_totals = {}
    if receipt_summary:
        receipt_totals = {
            "total_receipts": int(receipt_summary.get("total_receipts", 0)) if str(receipt_summary.get("total_receipts", "")).strip() else 0,
            "counts_by_decision": receipt_summary.get("counts_by_decision", {}),
        }

    fingerprint_basis = {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "replay_basis_mode": mode,
        "origin_offset_ranges": origin_offset_ranges,
        "offset_source_key": offsets_key,
        "offset_mode": str((kafka_offsets_snapshot or {}).get("offset_mode", "")),
    }
    replay_basis_fingerprint = stable_hash(fingerprint_basis) if origin_offset_ranges else ""

    receipt_payload = {
        "captured_at_utc": captured,
        "phase": "M9.C",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "replay_basis_mode": mode,
        "selector_translation_mode": "direct_offsets_from_ingest_snapshot",
        "origin_offset_ranges": origin_offset_ranges,
        "origin_offset_range_count": len(origin_offset_ranges),
        "replay_basis_fingerprint": replay_basis_fingerprint,
        "source_refs": {
            "m9b_summary_ref": m9b_summary_key,
            "m9b_scope_lock_ref": m9b_snapshot_key,
            "kafka_offsets_snapshot_ref": offsets_key,
            "receipt_summary_ref": receipt_summary_key,
            "run_scoped_receipt_ref": replay_receipt_run_key,
        },
        "offset_source_meta": {
            "offset_mode": str((kafka_offsets_snapshot or {}).get("offset_mode", "")),
            "evidence_basis": str((kafka_offsets_snapshot or {}).get("evidence_basis", "")),
            "topics_total": len((kafka_offsets_snapshot or {}).get("topics", []) if isinstance((kafka_offsets_snapshot or {}).get("topics"), list) else []),
        },
        "receipt_totals_context": receipt_totals,
        "validation": {
            "offset_validation_errors": offset_validation_errors,
            "run_scope_locked": bool(platform_run_id and scenario_run_id),
        },
    }

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.D_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = receipt_payload

    register = {
        "captured_at_utc": captured,
        "phase": "M9.C",
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
        "phase": "M9.C",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
        "run_scoped_receipt_key": replay_receipt_run_key,
    }

    artifacts = {
        "m9c_replay_basis_receipt.json": snapshot,
        "m9c_blocker_register.json": register,
        "m9c_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    publish_targets: list[tuple[str, dict[str, Any]]] = [
        (f"{prefix}/m9c_replay_basis_receipt.json", snapshot),
        (f"{prefix}/m9c_blocker_register.json", register),
        (f"{prefix}/m9c_execution_summary.json", summary),
    ]
    if replay_receipt_run_key:
        publish_targets.append((replay_receipt_run_key, snapshot))

    for key, payload in publish_targets:
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"key": key, "error": type(exc).__name__})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.C artifacts."})
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
