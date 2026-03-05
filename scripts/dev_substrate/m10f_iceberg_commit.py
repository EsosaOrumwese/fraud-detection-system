#!/usr/bin/env python3
"""Build and publish M10.F Iceberg + Glue commit verification artifacts."""

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


def sanitize_id(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def normalize_prefix(prefix: str) -> str:
    p = str(prefix or "").strip().strip("/")
    return f"{p}/" if p else ""


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
    execution_id = env.get("M10F_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10F_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10e_execution = env.get("UPSTREAM_M10E_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10F_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10F_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10e_execution:
        raise SystemExit("UPSTREAM_M10E_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)
    glue = boto3.client("glue", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "S3_OBJECT_STORE_BUCKET",
        "S3_EVIDENCE_BUCKET",
        "OFS_ICEBERG_DATABASE",
        "OFS_ICEBERG_TABLE_PREFIX",
        "OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN",
        "DATA_TABLE_FORMAT_PRIMARY",
        "DATA_TABLE_CATALOG",
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
        blockers.append({"code": "M10-B6", "message": "Required M10.F handles are missing or placeholder-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != evidence_bucket:
        blockers.append({"code": "M10-B6", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    m10e_summary_key = f"evidence/dev_full/run_control/{upstream_m10e_execution}/m10e_execution_summary.json"
    m10e_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10e_execution}/m10e_quality_gate_snapshot.json"
    m10e_summary: dict[str, Any] | None = None
    m10e_snapshot: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        m10e_summary = s3_get_json(s3, evidence_bucket, m10e_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10e_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B6", "message": "M10.E summary unreadable for M10.F entry gate."})

    try:
        m10e_snapshot = s3_get_json(s3, evidence_bucket, m10e_snapshot_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10e_snapshot_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B6", "message": "M10.E snapshot unreadable for M10.F entry gate."})

    if m10e_summary:
        if not bool(m10e_summary.get("overall_pass")):
            blockers.append({"code": "M10-B6", "message": "M10.E summary is not pass posture."})
        if str(m10e_summary.get("next_gate", "")).strip() != "M10.F_READY":
            blockers.append({"code": "M10-B6", "message": "M10.E next_gate is not M10.F_READY."})
        platform_run_id = str(m10e_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10e_summary.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B6", "message": "Run scope unresolved for M10.F commit verification."})

    object_store_bucket = str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip()
    database_name = str(handles.get("OFS_ICEBERG_DATABASE", "")).strip()
    table_prefix = str(handles.get("OFS_ICEBERG_TABLE_PREFIX", "")).strip()
    warehouse_prefix = normalize_prefix(str(handles.get("OFS_ICEBERG_WAREHOUSE_PREFIX_PATTERN", "")).strip())
    table_name = f"{table_prefix}{sanitize_id(platform_run_id)}" if platform_run_id and table_prefix else ""
    table_location = f"s3://{object_store_bucket}/{warehouse_prefix}{table_name}/" if object_store_bucket and table_name else ""
    marker_key = f"{warehouse_prefix}{table_name}/_m10f_commit_marker.json" if table_name else ""
    marker_payload: dict[str, Any] | None = None
    db_payload: dict[str, Any] | None = None
    table_payload: dict[str, Any] | None = None

    if database_name:
        try:
            db_payload = glue.get_database(Name=database_name).get("Database", {})
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": f"glue:database:{database_name}", "error": type(exc).__name__})
            blockers.append({"code": "M10-B6", "message": "Glue database surface unreadable for M10.F verification."})
    if database_name and table_name:
        try:
            table_payload = glue.get_table(DatabaseName=database_name, Name=table_name).get("Table", {})
        except (BotoCoreError, ClientError, KeyError) as exc:
            read_errors.append({"surface": f"glue:table:{database_name}.{table_name}", "error": type(exc).__name__})
            blockers.append({"code": "M10-B6", "message": "Glue table surface unreadable for M10.F verification."})

    if db_payload and warehouse_prefix:
        db_location = str(db_payload.get("LocationUri", "")).strip()
        expected_db_location = f"s3://{object_store_bucket}/{warehouse_prefix}"
        if db_location.rstrip("/") + "/" != expected_db_location.rstrip("/") + "/":
            blockers.append({"code": "M10-B6", "message": "Glue database location does not match deterministic warehouse root."})

    table_location_matches = False
    table_type_matches = False
    if table_payload:
        location = str((table_payload.get("StorageDescriptor", {}) or {}).get("Location", "")).strip()
        table_location_matches = location.rstrip("/") + "/" == table_location.rstrip("/") + "/"
        if not table_location_matches:
            blockers.append({"code": "M10-B6", "message": "Glue table location does not match deterministic table location."})
        parameters = table_payload.get("Parameters", {}) if isinstance(table_payload.get("Parameters", {}), dict) else {}
        table_type_matches = str(parameters.get("table_type", "")).strip().upper() == "ICEBERG"
        if not table_type_matches:
            blockers.append({"code": "M10-B6", "message": "Glue table parameters do not declare ICEBERG table_type."})
        if str(parameters.get("platform_run_id", "")).strip() != platform_run_id:
            blockers.append({"code": "M10-B6", "message": "Glue table platform_run_id parameter mismatch."})

    if marker_key:
        try:
            marker_body = s3.get_object(Bucket=object_store_bucket, Key=marker_key)["Body"].read().decode("utf-8")
            parsed = json.loads(marker_body)
            marker_payload = parsed if isinstance(parsed, dict) else {}
        except (BotoCoreError, ClientError, json.JSONDecodeError, ValueError) as exc:
            read_errors.append({"surface": f"s3://{object_store_bucket}/{marker_key}", "error": type(exc).__name__})
            blockers.append({"code": "M10-B6", "message": "S3 commit marker is unreadable for M10.F verification."})
    else:
        blockers.append({"code": "M10-B6", "message": "Unable to derive deterministic S3 commit marker key for M10.F."})

    if marker_payload is not None and marker_payload:
        marker_db = str(marker_payload.get("database", "") or marker_payload.get("database_name", "")).strip()
        marker_table = str(marker_payload.get("table", "") or marker_payload.get("table_name", "")).strip()
        if marker_db != database_name:
            blockers.append({"code": "M10-B6", "message": "S3 commit marker database does not match deterministic database."})
        if marker_table != table_name:
            blockers.append({"code": "M10-B6", "message": "S3 commit marker table does not match deterministic table."})
        if str(marker_payload.get("platform_run_id", "")).strip() != platform_run_id:
            blockers.append({"code": "M10-B6", "message": "S3 commit marker platform_run_id mismatch."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.G_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.F",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10e_execution": upstream_m10e_execution,
        "upstream_m10e_summary_key": m10e_summary_key,
        "upstream_m10e_snapshot_key": m10e_snapshot_key,
        "resolved_handle_values": resolved_handle_values,
        "deterministic_surface": {
            "database_name": database_name,
            "table_name": table_name,
            "table_location": table_location,
            "s3_commit_marker_key": marker_key,
        },
        "verification": {
            "glue_database_present": bool(db_payload),
            "glue_table_present": bool(table_payload),
            "table_location_matches": table_location_matches,
            "table_type_matches": table_type_matches,
            "marker_present": bool(marker_payload),
        },
        "marker_payload": marker_payload or {},
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.F",
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
        "phase": "M10.F",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10f_iceberg_commit_snapshot.json": snapshot,
        "m10f_blocker_register.json": register,
        "m10f_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.F artifacts."})
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
