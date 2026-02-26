#!/usr/bin/env python3
"""Managed M9.D as-of + maturity policy closure artifact builder."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
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


def parse_iso_utc(text: str) -> datetime:
    normalized = text.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def epoch_to_utc_iso(epoch_int: int) -> str:
    return datetime.fromtimestamp(epoch_int, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def as_int(value: Any) -> int:
    return int(str(value).strip())


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M9D_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9D_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m9c_execution = env.get("UPSTREAM_M9C_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9D_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9D_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m9c_execution:
        raise SystemExit("UPSTREAM_M9C_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    captured_dt = parse_iso_utc(captured)
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "LEARNING_FEATURE_ASOF_REQUIRED",
        "LEARNING_LABEL_ASOF_REQUIRED",
        "LEARNING_LABEL_MATURITY_DAYS_DEFAULT",
        "LEARNING_FUTURE_TIMESTAMP_POLICY",
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
        blockers.append({"code": "M9-B4", "message": "Required M9.D handles are missing, placeholder, or wildcard-valued."})

    feature_asof_required = bool(handles.get("LEARNING_FEATURE_ASOF_REQUIRED"))
    label_asof_required = bool(handles.get("LEARNING_LABEL_ASOF_REQUIRED"))
    future_policy = str(handles.get("LEARNING_FUTURE_TIMESTAMP_POLICY", "")).strip()
    maturity_days_raw = handles.get("LEARNING_LABEL_MATURITY_DAYS_DEFAULT")
    try:
        label_maturity_days = int(maturity_days_raw)
    except (TypeError, ValueError):
        label_maturity_days = -1

    if not feature_asof_required:
        blockers.append({"code": "M9-B4", "message": "LEARNING_FEATURE_ASOF_REQUIRED must be true."})
    if not label_asof_required:
        blockers.append({"code": "M9-B4", "message": "LEARNING_LABEL_ASOF_REQUIRED must be true."})
    if future_policy != "fail_closed":
        blockers.append({"code": "M9-B4", "message": "LEARNING_FUTURE_TIMESTAMP_POLICY must be fail_closed."})
    if label_maturity_days <= 0:
        blockers.append({"code": "M9-B4", "message": "LEARNING_LABEL_MATURITY_DAYS_DEFAULT must be a positive integer."})

    m9c_summary_key = f"evidence/dev_full/run_control/{upstream_m9c_execution}/m9c_execution_summary.json"
    m9c_receipt_key = f"evidence/dev_full/run_control/{upstream_m9c_execution}/m9c_replay_basis_receipt.json"
    m9c_summary: dict[str, Any] | None = None
    m9c_receipt: dict[str, Any] | None = None
    run_scoped_receipt: dict[str, Any] | None = None
    run_scoped_receipt_key = ""

    for key_name, key_value in [("m9c_summary", m9c_summary_key), ("m9c_receipt", m9c_receipt_key)]:
        try:
            payload = s3_get_json(s3, bucket, key_value)
            if key_name == "m9c_summary":
                m9c_summary = payload
            else:
                m9c_receipt = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key_value, "error": type(exc).__name__})
            blockers.append({"code": "M9-B4", "message": f"Required upstream artifact unreadable: {key_name}."})

    platform_run_id = ""
    scenario_run_id = ""
    if m9c_summary:
        upstream_ok = bool(m9c_summary.get("overall_pass")) and str(m9c_summary.get("next_gate", "")).strip() == "M9.D_READY"
        if not upstream_ok:
            blockers.append({"code": "M9-B4", "message": "M9.C posture is not pass with next_gate=M9.D_READY."})
        platform_run_id = str(m9c_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m9c_summary.get("scenario_run_id", "")).strip()
        run_scoped_receipt_key = str(m9c_summary.get("run_scoped_receipt_key", "")).strip()

    if run_scoped_receipt_key:
        try:
            run_scoped_receipt = s3_get_json(s3, bucket, run_scoped_receipt_key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": run_scoped_receipt_key, "error": type(exc).__name__})
            blockers.append({"code": "M9-B4", "message": "Run-scoped replay receipt is unreadable."})
    else:
        blockers.append({"code": "M9-B4", "message": "M9.C summary missing run-scoped replay receipt key."})

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M9-B4", "message": "Active run scope is unresolved for M9.D."})

    receipt_fingerprint_control = ""
    receipt_fingerprint_run = ""
    if m9c_receipt:
        receipt_fingerprint_control = str(m9c_receipt.get("replay_basis_fingerprint", "")).strip()
    if run_scoped_receipt:
        receipt_fingerprint_run = str(run_scoped_receipt.get("replay_basis_fingerprint", "")).strip()
    if not receipt_fingerprint_control or not receipt_fingerprint_run or receipt_fingerprint_control != receipt_fingerprint_run:
        blockers.append({"code": "M9-B4", "message": "Replay receipt fingerprint parity failed (run-control vs run-scoped)."})

    origin_offset_ranges = (m9c_receipt or {}).get("origin_offset_ranges", [])
    if not isinstance(origin_offset_ranges, list) or len(origin_offset_ranges) == 0:
        blockers.append({"code": "M9-B4", "message": "M9.C replay receipt has no origin_offset_ranges."})

    max_offset_epoch: int | None = None
    offset_parse_errors: list[str] = []
    if isinstance(origin_offset_ranges, list):
        for i, row in enumerate(origin_offset_ranges):
            if not isinstance(row, dict):
                offset_parse_errors.append(f"origin_offset_ranges[{i}] not object")
                continue
            try:
                last_offset = as_int(row.get("last_offset"))
            except (ValueError, TypeError):
                offset_parse_errors.append(f"origin_offset_ranges[{i}].last_offset parse failure")
                continue
            if max_offset_epoch is None or last_offset > max_offset_epoch:
                max_offset_epoch = last_offset

    if offset_parse_errors:
        blockers.append({"code": "M9-B4", "message": "Failed to parse replay last_offset values for as-of derivation."})
    if max_offset_epoch is None:
        blockers.append({"code": "M9-B4", "message": "As-of derivation anchor is unresolved (no valid last_offset)."})

    feature_asof_utc = ""
    label_asof_utc = ""
    label_maturity_cutoff_utc = ""
    temporal_checks = {
        "feature_asof_not_future": False,
        "label_asof_not_future": False,
        "maturity_cutoff_before_label_asof": False,
        "feature_label_asof_parity": False,
    }

    if max_offset_epoch is not None and label_maturity_days > 0:
        try:
            feature_dt = parse_iso_utc(epoch_to_utc_iso(max_offset_epoch))
            label_dt = feature_dt
            cutoff_dt = label_dt - timedelta(days=label_maturity_days)
            feature_asof_utc = feature_dt.isoformat().replace("+00:00", "Z")
            label_asof_utc = label_dt.isoformat().replace("+00:00", "Z")
            label_maturity_cutoff_utc = cutoff_dt.isoformat().replace("+00:00", "Z")
            temporal_checks["feature_asof_not_future"] = feature_dt <= captured_dt
            temporal_checks["label_asof_not_future"] = label_dt <= captured_dt
            temporal_checks["maturity_cutoff_before_label_asof"] = cutoff_dt <= label_dt
            temporal_checks["feature_label_asof_parity"] = feature_dt == label_dt
        except Exception:
            blockers.append({"code": "M9-B4", "message": "Failed to derive parseable as-of timestamps."})

    for key, ok in temporal_checks.items():
        if not ok:
            blockers.append({"code": "M9-B4", "message": f"Temporal invariant failed: {key}."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.E_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M9.D",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m9c_execution": upstream_m9c_execution,
        "upstream_refs": {
            "m9c_summary_ref": m9c_summary_key,
            "m9c_replay_receipt_ref": m9c_receipt_key,
            "run_scoped_replay_receipt_ref": run_scoped_receipt_key,
        },
        "required_handle_values": resolved_handle_values,
        "feature_asof_utc": feature_asof_utc,
        "label_asof_utc": label_asof_utc,
        "label_maturity_days": label_maturity_days,
        "label_maturity_cutoff_utc": label_maturity_cutoff_utc,
        "future_timestamp_policy": future_policy,
        "replay_basis_fingerprint": receipt_fingerprint_control,
        "temporal_checks": temporal_checks,
        "offset_parse_errors": offset_parse_errors,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M9.D",
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
        "phase": "M9.D",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m9d_asof_maturity_policy_snapshot.json": snapshot,
        "m9d_blocker_register.json": register,
        "m9d_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    publish_targets = [
        (f"{prefix}/m9d_asof_maturity_policy_snapshot.json", snapshot),
        (f"{prefix}/m9d_blocker_register.json", register),
        (f"{prefix}/m9d_execution_summary.json", summary),
    ]

    for key, payload in publish_targets:
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"key": key, "error": type(exc).__name__})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.D artifacts."})
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
