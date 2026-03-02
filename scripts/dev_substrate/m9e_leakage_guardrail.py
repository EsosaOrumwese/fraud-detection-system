#!/usr/bin/env python3
"""Managed M9.E leakage guardrail closure artifact builder."""

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


def parse_iso_utc(text: str) -> datetime:
    normalized = text.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def as_int(value: Any) -> int:
    return int(str(value).strip())


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


def list_stream_view_output_ids(s3_client: Any, bucket: str, prefix: str) -> list[str]:
    output_ids: list[str] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            sub_prefix = str(cp.get("Prefix", ""))
            marker = "output_id="
            if marker in sub_prefix:
                tail = sub_prefix.split(marker, 1)[1]
                output_id = tail.split("/", 1)[0].strip()
                if output_id:
                    output_ids.append(output_id)
    return sorted(set(output_ids))


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M9E_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9E_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m9d_execution = env.get("UPSTREAM_M9D_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9E_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9E_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m9d_execution:
        raise SystemExit("UPSTREAM_M9D_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    captured_dt = parse_iso_utc(captured)
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN",
        "LEARNING_FUTURE_TIMESTAMP_POLICY",
        "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS",
        "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS",
        "ORACLE_STORE_BUCKET",
        "ORACLE_SOURCE_NAMESPACE",
        "ORACLE_ENGINE_RUN_ID",
        "S3_STREAM_VIEW_PREFIX_PATTERN",
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
        blockers.append({"code": "M9-B5", "message": "Required M9.E handles are missing, placeholder, or wildcard-valued."})

    m9d_summary_key = f"evidence/dev_full/run_control/{upstream_m9d_execution}/m9d_execution_summary.json"
    m9d_snapshot_key = f"evidence/dev_full/run_control/{upstream_m9d_execution}/m9d_asof_maturity_policy_snapshot.json"
    m9d_summary: dict[str, Any] | None = None
    m9d_snapshot: dict[str, Any] | None = None
    m9c_receipt: dict[str, Any] | None = None
    m9c_receipt_key = ""

    for key_name, key_value in [("m9d_summary", m9d_summary_key), ("m9d_snapshot", m9d_snapshot_key)]:
        try:
            payload = s3_get_json(s3, bucket, key_value)
            if key_name == "m9d_summary":
                m9d_summary = payload
            else:
                m9d_snapshot = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key_value, "error": type(exc).__name__})
            blockers.append({"code": "M9-B5", "message": f"Required upstream artifact unreadable: {key_name}."})

    platform_run_id = ""
    scenario_run_id = ""
    if m9d_summary:
        upstream_ok = bool(m9d_summary.get("overall_pass")) and str(m9d_summary.get("next_gate", "")).strip() == "M9.E_READY"
        if not upstream_ok:
            blockers.append({"code": "M9-B5", "message": "M9.D posture is not pass with next_gate=M9.E_READY."})
        platform_run_id = str(m9d_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m9d_summary.get("scenario_run_id", "")).strip()

    if m9d_snapshot:
        if not platform_run_id:
            platform_run_id = str(m9d_snapshot.get("platform_run_id", "")).strip()
        if not scenario_run_id:
            scenario_run_id = str(m9d_snapshot.get("scenario_run_id", "")).strip()
        m9c_exec = str(m9d_snapshot.get("upstream_m9c_execution", "")).strip()
        if m9c_exec:
            m9c_receipt_key = f"evidence/dev_full/run_control/{m9c_exec}/m9c_replay_basis_receipt.json"
            try:
                m9c_receipt = s3_get_json(s3, bucket, m9c_receipt_key)
            except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
                read_errors.append({"surface": m9c_receipt_key, "error": type(exc).__name__})
                blockers.append({"code": "M9-B5", "message": "M9.C replay-basis receipt is unreadable from upstream reference."})
        else:
            blockers.append({"code": "M9-B5", "message": "M9.D snapshot missing upstream_m9c_execution reference."})

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M9-B5", "message": "Active run scope is unresolved for M9.E."})

    future_policy = str(handles.get("LEARNING_FUTURE_TIMESTAMP_POLICY", "")).strip()
    if future_policy != "fail_closed":
        blockers.append({"code": "M9-B5", "message": "LEARNING_FUTURE_TIMESTAMP_POLICY must be fail_closed for leakage guardrail."})

    future_fields_raw = str(handles.get("LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS", "")).strip()
    forbidden_future_fields = [x.strip() for x in future_fields_raw.split(",") if x.strip()]
    if len(forbidden_future_fields) == 0:
        blockers.append({"code": "M9-B5", "message": "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS is empty."})

    forbidden_truth_raw = str(handles.get("LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS", "")).strip()
    forbidden_truth_outputs = [x.strip() for x in forbidden_truth_raw.split(",") if x.strip()]
    if len(forbidden_truth_outputs) == 0:
        blockers.append({"code": "M9-B5", "message": "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS is empty."})

    feature_asof_utc = str((m9d_snapshot or {}).get("feature_asof_utc", "")).strip()
    label_asof_utc = str((m9d_snapshot or {}).get("label_asof_utc", "")).strip()
    feature_asof_epoch = None
    label_asof_epoch = None
    try:
        feature_asof_epoch = int(parse_iso_utc(feature_asof_utc).timestamp())
        label_asof_epoch = int(parse_iso_utc(label_asof_utc).timestamp())
    except Exception:
        blockers.append({"code": "M9-B5", "message": "M9.D as-of timestamps are missing or unparseable."})

    boundary_rows: list[dict[str, Any]] = []
    boundary_violations: list[dict[str, Any]] = []
    origin_rows = (m9c_receipt or {}).get("origin_offset_ranges", [])
    if not isinstance(origin_rows, list) or len(origin_rows) == 0:
        blockers.append({"code": "M9-B5", "message": "M9.C origin_offset_ranges is empty for leakage boundary checks."})
    else:
        for row in origin_rows:
            if not isinstance(row, dict):
                continue
            topic = str(row.get("topic", "")).strip()
            partition = row.get("partition")
            last_raw = row.get("last_offset")
            try:
                last_epoch = as_int(last_raw)
            except (TypeError, ValueError):
                boundary_violations.append(
                    {
                        "topic": topic,
                        "partition": partition,
                        "reason": "last_offset_parse_failure",
                        "last_offset": str(last_raw),
                    }
                )
                continue
            feature_ok = feature_asof_epoch is not None and last_epoch <= int(feature_asof_epoch)
            label_ok = label_asof_epoch is not None and last_epoch <= int(label_asof_epoch)
            row_check = {
                "topic": topic,
                "partition": partition,
                "last_offset_epoch": last_epoch,
                "feature_asof_epoch": feature_asof_epoch,
                "label_asof_epoch": label_asof_epoch,
                "feature_boundary_ok": feature_ok,
                "label_boundary_ok": label_ok,
            }
            boundary_rows.append(row_check)
            if not feature_ok or not label_ok:
                violation = dict(row_check)
                violation["reason"] = "future_timestamp_boundary_breach"
                boundary_violations.append(violation)

    if boundary_violations:
        blockers.append({"code": "M9-B5", "message": "DFULL-RUN-B12.2 future timestamp boundary breach detected."})

    active_stream_view_outputs: list[str] = []
    truth_output_intersection: list[str] = []
    oracle_bucket = str(handles.get("ORACLE_STORE_BUCKET", "")).strip()
    stream_prefix_pattern = str(handles.get("S3_STREAM_VIEW_PREFIX_PATTERN", "")).strip()
    oracle_namespace = str(handles.get("ORACLE_SOURCE_NAMESPACE", "")).strip()
    oracle_engine_run_id = str(handles.get("ORACLE_ENGINE_RUN_ID", "")).strip()
    stream_prefix = ""
    if oracle_bucket and stream_prefix_pattern and oracle_namespace and oracle_engine_run_id:
        stream_prefix = render(
            stream_prefix_pattern,
            {
                "oracle_source_namespace": oracle_namespace,
                "oracle_engine_run_id": oracle_engine_run_id,
            },
        )
        try:
            active_stream_view_outputs = list_stream_view_output_ids(s3, oracle_bucket, stream_prefix)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": f"s3://{oracle_bucket}/{stream_prefix}", "error": type(exc).__name__})
            blockers.append({"code": "M9-B5", "message": "Unable to enumerate active stream-view outputs for truth-surface leakage check."})

    if active_stream_view_outputs and forbidden_truth_outputs:
        truth_output_intersection = sorted(set(active_stream_view_outputs).intersection(set(forbidden_truth_outputs)))
    if truth_output_intersection:
        blockers.append({"code": "M9-B5", "message": "Forbidden truth outputs detected in active stream-view output surface."})

    run_scoped_report_key = ""
    if platform_run_id:
        run_scoped_report_key = render(
            str(handles.get("LEARNING_LEAKAGE_GUARDRAIL_REPORT_PATH_PATTERN", "")).strip(),
            {"platform_run_id": platform_run_id},
        )

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.F_READY" if overall_pass else "HOLD_REMEDIATE"

    report = {
        "captured_at_utc": captured,
        "phase": "M9.E",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "policy": {
            "future_timestamp_policy": future_policy,
            "forbidden_future_fields": forbidden_future_fields,
            "forbidden_truth_output_ids": forbidden_truth_outputs,
            "contract_blocker_code_on_boundary_breach": "DFULL-RUN-B12.2",
        },
        "sources": {
            "m9d_summary_ref": m9d_summary_key,
            "m9d_snapshot_ref": m9d_snapshot_key,
            "m9c_replay_receipt_ref": m9c_receipt_key,
            "run_scoped_report_ref": run_scoped_report_key,
        },
        "temporal_boundaries": {
            "feature_asof_utc": feature_asof_utc,
            "label_asof_utc": label_asof_utc,
        },
        "boundary_check": {
            "rows_checked": len(boundary_rows),
            "violation_count": len(boundary_violations),
            "samples": boundary_rows[:25],
            "violations": boundary_violations[:25],
        },
        "truth_surface_check": {
            "oracle_store_bucket": oracle_bucket,
            "stream_view_prefix": stream_prefix,
            "active_output_ids": active_stream_view_outputs,
            "forbidden_intersection": truth_output_intersection,
        },
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M9.E",
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
        "phase": "M9.E",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
        "run_scoped_report_key": run_scoped_report_key,
    }

    artifacts = {
        "m9e_leakage_guardrail_report.json": report,
        "m9e_blocker_register.json": register,
        "m9e_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    publish_targets = [
        (f"{prefix}/m9e_leakage_guardrail_report.json", report),
        (f"{prefix}/m9e_blocker_register.json", register),
        (f"{prefix}/m9e_execution_summary.json", summary),
    ]
    if run_scoped_report_key:
        publish_targets.append((run_scoped_report_key, report))

    for key, payload in publish_targets:
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"key": key, "error": type(exc).__name__})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.E artifacts."})
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
