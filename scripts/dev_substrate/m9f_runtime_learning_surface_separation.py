#!/usr/bin/env python3
"""Managed M9.F runtime-vs-learning surface separation closure builder."""

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
INTERFACE_PATH = Path("docs/model_spec/data-engine/interface_pack/data_engine_interface.md")


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


def parse_truth_products_from_interface(path: Path) -> set[str]:
    truth: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    tick = re.compile(r"`([^`]+)`")
    for line in lines:
        lower = line.lower()
        if "truth products" not in lower:
            continue
        for token in tick.findall(line):
            if token.startswith("s4_"):
                truth.add(token.strip())
    return truth


def derive_outputs_with_forbidden_fields(path: Path, forbidden_fields: set[str]) -> set[str]:
    outputs: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    tick = re.compile(r"`([^`]+)`")
    for line in lines:
        if "includes" not in line:
            continue
        tokens = [t.strip() for t in tick.findall(line)]
        if not tokens:
            continue
        output_id = tokens[0]
        fields = set(tokens[1:])
        if fields.intersection(forbidden_fields):
            outputs.add(output_id)
    return outputs


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M9F_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9F_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m9e_execution = env.get("UPSTREAM_M9E_EXECUTION", "").strip()
    upstream_m9b_execution = env.get("UPSTREAM_M9B_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9F_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9F_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m9e_execution:
        raise SystemExit("UPSTREAM_M9E_EXECUTION is required.")
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
        "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS",
        "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS",
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
        blockers.append({"code": "M9-B6", "message": "Required M9.F handles are missing, placeholder, or wildcard-valued."})

    m9e_summary_key = f"evidence/dev_full/run_control/{upstream_m9e_execution}/m9e_execution_summary.json"
    m9e_report_key = f"evidence/dev_full/run_control/{upstream_m9e_execution}/m9e_leakage_guardrail_report.json"
    m9b_snapshot_key = f"evidence/dev_full/run_control/{upstream_m9b_execution}/m9b_handoff_scope_snapshot.json"
    m9e_summary: dict[str, Any] | None = None
    m9e_report: dict[str, Any] | None = None
    m9b_snapshot: dict[str, Any] | None = None
    for key_name, key_value in [("m9e_summary", m9e_summary_key), ("m9e_report", m9e_report_key), ("m9b_snapshot", m9b_snapshot_key)]:
        try:
            payload = s3_get_json(s3, bucket, key_value)
            if key_name == "m9e_summary":
                m9e_summary = payload
            elif key_name == "m9e_report":
                m9e_report = payload
            else:
                m9b_snapshot = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key_value, "error": type(exc).__name__})
            blockers.append({"code": "M9-B6", "message": f"Required upstream artifact unreadable: {key_name}."})

    platform_run_id = ""
    scenario_run_id = ""
    if m9e_summary:
        upstream_ok = bool(m9e_summary.get("overall_pass")) and str(m9e_summary.get("next_gate", "")).strip() == "M9.F_READY"
        if not upstream_ok:
            blockers.append({"code": "M9-B6", "message": "M9.E posture is not pass with next_gate=M9.F_READY."})
        platform_run_id = str(m9e_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m9e_summary.get("scenario_run_id", "")).strip()
    if m9e_report:
        if not platform_run_id:
            platform_run_id = str(m9e_report.get("platform_run_id", "")).strip()
        if not scenario_run_id:
            scenario_run_id = str(m9e_report.get("scenario_run_id", "")).strip()
    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M9-B6", "message": "Active run scope is unresolved for M9.F."})

    forbidden_truth_outputs = [x.strip() for x in str(handles.get("LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS", "")).split(",") if x.strip()]
    forbidden_future_fields = [x.strip() for x in str(handles.get("LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS", "")).split(",") if x.strip()]
    if len(forbidden_truth_outputs) == 0:
        blockers.append({"code": "M9-B6", "message": "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS is empty."})
    if len(forbidden_future_fields) == 0:
        blockers.append({"code": "M9-B6", "message": "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS is empty."})

    active_outputs: list[str] = []
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
            active_outputs = list_stream_view_output_ids(s3, oracle_bucket, stream_prefix)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": f"s3://{oracle_bucket}/{stream_prefix}", "error": type(exc).__name__})
            blockers.append({"code": "M9-B6", "message": "Unable to enumerate active runtime stream-view outputs."})

    interface_truth_products: set[str] = set()
    interface_future_derived_outputs: set[str] = set()
    if INTERFACE_PATH.exists():
        try:
            interface_truth_products = parse_truth_products_from_interface(INTERFACE_PATH)
            interface_future_derived_outputs = derive_outputs_with_forbidden_fields(INTERFACE_PATH, set(forbidden_future_fields))
        except Exception:
            blockers.append({"code": "M9-B6", "message": "Failed to parse interface contract for truth/future-derived output mapping."})
    else:
        blockers.append({"code": "M9-B6", "message": "Interface contract path is missing for separation checks."})

    forbidden_truth_intersection = sorted(set(active_outputs).intersection(set(forbidden_truth_outputs)))
    interface_truth_intersection = sorted(set(active_outputs).intersection(interface_truth_products))
    future_derived_intersection = sorted(set(active_outputs).intersection(interface_future_derived_outputs))

    if forbidden_truth_intersection:
        blockers.append({"code": "M9-B6", "message": "Active runtime outputs intersect forbidden truth output set."})
    if interface_truth_intersection:
        blockers.append({"code": "M9-B6", "message": "Active runtime outputs intersect interface-declared truth products."})
    if future_derived_intersection:
        blockers.append({"code": "M9-B6", "message": "Active runtime outputs intersect outputs carrying forbidden future-derived fields."})

    runtime_ref_leaks: list[str] = []
    runtime_refs = (m9b_snapshot or {}).get("required_evidence_refs", {})
    if isinstance(runtime_refs, dict):
        for _k, v in runtime_refs.items():
            ref = str(v)
            ref_lower = ref.lower()
            if "/learning/" in ref_lower:
                runtime_ref_leaks.append(ref)
            for truth_output in forbidden_truth_outputs:
                if truth_output in ref:
                    runtime_ref_leaks.append(ref)
    else:
        blockers.append({"code": "M9-B6", "message": "M9.B required_evidence_refs is missing or invalid for boundary-ref checks."})

    if runtime_ref_leaks:
        blockers.append({"code": "M9-B6", "message": "Runtime evidence refs leak into learning/truth surfaces."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M9.G_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M9.F",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "sources": {
            "m9e_summary_ref": m9e_summary_key,
            "m9e_report_ref": m9e_report_key,
            "m9b_scope_snapshot_ref": m9b_snapshot_key,
            "interface_contract_path": str(INTERFACE_PATH),
        },
        "oracle_stream_surface": {
            "oracle_store_bucket": oracle_bucket,
            "stream_view_prefix": stream_prefix,
            "active_output_ids": active_outputs,
        },
        "separation_policy": {
            "forbidden_truth_output_ids": forbidden_truth_outputs,
            "forbidden_future_fields": forbidden_future_fields,
            "interface_truth_products": sorted(interface_truth_products),
            "interface_future_derived_outputs": sorted(interface_future_derived_outputs),
        },
        "separation_results": {
            "forbidden_truth_intersection": forbidden_truth_intersection,
            "interface_truth_intersection": interface_truth_intersection,
            "future_derived_intersection": future_derived_intersection,
            "runtime_ref_leaks": sorted(set(runtime_ref_leaks)),
        },
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M9.F",
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
        "phase": "M9.F",
        "phase_id": "P12",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m9f_surface_separation_snapshot.json": snapshot,
        "m9f_blocker_register.json": register,
        "m9f_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    publish_targets = [
        (f"{prefix}/m9f_surface_separation_snapshot.json", snapshot),
        (f"{prefix}/m9f_blocker_register.json", register),
        (f"{prefix}/m9f_execution_summary.json", summary),
    ]
    for key, payload in publish_targets:
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"key": key, "error": type(exc).__name__})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M9-B11", "message": "Failed to publish/readback one or more M9.F artifacts."})
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
