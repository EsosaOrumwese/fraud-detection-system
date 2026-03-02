#!/usr/bin/env python3
"""Build and publish M10.C input-binding + immutability artifacts."""

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


def parse_iso_utc(text: str) -> datetime:
    normalized = text.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def render(pattern: str, values: dict[str, str]) -> str:
    out = pattern
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
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


def s3_head(s3_client: Any, bucket: str, key: str) -> dict[str, Any]:
    obj = s3_client.head_object(Bucket=bucket, Key=key)
    last_modified = obj.get("LastModified")
    return {
        "key": key,
        "etag": str(obj.get("ETag", "")).strip('"'),
        "content_length": int(obj.get("ContentLength", 0)),
        "version_id": str(obj.get("VersionId", "")).strip() or None,
        "last_modified_utc": last_modified.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if hasattr(last_modified, "astimezone")
        else None,
    }


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
        signature = (code, message)
        if signature in seen:
            continue
        seen.add(signature)
        out.append({"code": code, "message": message})
    return out


def parse_csv_set(value: Any) -> set[str]:
    return {x.strip() for x in str(value or "").split(",") if x.strip()}


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M10C_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10C_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10b_execution = env.get("UPSTREAM_M10B_EXECUTION", "").strip()
    upstream_m9_execution = env.get("UPSTREAM_M9_EXECUTION", "").strip()
    upstream_m9h_execution = env.get("UPSTREAM_M9H_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10C_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10C_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10b_execution:
        raise SystemExit("UPSTREAM_M10B_EXECUTION is required.")
    if not upstream_m9_execution:
        raise SystemExit("UPSTREAM_M9_EXECUTION is required.")
    if not upstream_m9h_execution:
        raise SystemExit("UPSTREAM_M9H_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    captured_dt = parse_iso_utc(captured_at)
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "S3_EVIDENCE_BUCKET",
        "S3_RUN_CONTROL_ROOT_PATTERN",
        "LEARNING_REPLAY_BASIS_MODE",
        "LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN",
        "LEARNING_FEATURE_ASOF_REQUIRED",
        "LEARNING_LABEL_ASOF_REQUIRED",
        "LEARNING_LABEL_MATURITY_DAYS_DEFAULT",
        "LEARNING_FUTURE_TIMESTAMP_POLICY",
        "LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS",
        "LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS",
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
        blockers.append({"code": "M10-B3", "message": "Required M10.C handles are missing, placeholder, or wildcard-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != evidence_bucket:
        blockers.append({"code": "M10-B3", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    m10b_summary_key = f"evidence/dev_full/run_control/{upstream_m10b_execution}/m10b_execution_summary.json"
    m9_summary_key = f"evidence/dev_full/run_control/{upstream_m9_execution}/m9_execution_summary.json"
    m10_handoff_key = f"evidence/dev_full/run_control/{upstream_m9h_execution}/m10_handoff_pack.json"

    m10b_summary: dict[str, Any] | None = None
    m9_summary: dict[str, Any] | None = None
    m10_handoff: dict[str, Any] | None = None

    for name, key in [
        ("m10b_summary", m10b_summary_key),
        ("m9_summary", m9_summary_key),
        ("m10_handoff", m10_handoff_key),
    ]:
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            if name == "m10b_summary":
                m10b_summary = payload
            elif name == "m9_summary":
                m9_summary = payload
            else:
                m10_handoff = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B3", "message": f"Required upstream artifact unreadable: {name}."})

    platform_run_id = ""
    scenario_run_id = ""
    if m10b_summary:
        if not bool(m10b_summary.get("overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M10.B summary is not pass posture."})
        if str(m10b_summary.get("next_gate", "")).strip() != "M10.C_READY":
            blockers.append({"code": "M10-B3", "message": "M10.B next_gate is not M10.C_READY."})
        platform_run_id = str(m10b_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10b_summary.get("scenario_run_id", "")).strip()

    if m9_summary:
        if not bool(m9_summary.get("overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M9 summary is not pass posture."})
        if str(m9_summary.get("verdict", "")).strip() != "ADVANCE_TO_M10":
            blockers.append({"code": "M10-B3", "message": "M9 verdict is not ADVANCE_TO_M10."})
        if str(m9_summary.get("next_gate", "")).strip() != "M10_READY":
            blockers.append({"code": "M10-B3", "message": "M9 next_gate is not M10_READY."})
        p = str(m9_summary.get("platform_run_id", "")).strip()
        s = str(m9_summary.get("scenario_run_id", "")).strip()
        if platform_run_id and p and p != platform_run_id:
            blockers.append({"code": "M10-B3", "message": "platform_run_id mismatch between M10.B and M9 summary."})
        if scenario_run_id and s and s != scenario_run_id:
            blockers.append({"code": "M10-B3", "message": "scenario_run_id mismatch between M10.B and M9 summary."})
        if not platform_run_id:
            platform_run_id = p
        if not scenario_run_id:
            scenario_run_id = s

    if m10_handoff:
        if not bool(m10_handoff.get("p12_overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M10 handoff reports p12_overall_pass=false."})
        if str(m10_handoff.get("p12_verdict", "")).strip() != "ADVANCE_TO_P13":
            blockers.append({"code": "M10-B3", "message": "M10 handoff p12_verdict is not ADVANCE_TO_P13."})
        if str(m10_handoff.get("m10_entry_gate", {}).get("next_gate", "")).strip() != "M10_READY":
            blockers.append({"code": "M10-B3", "message": "M10 handoff entry gate is not M10_READY."})
        p = str(m10_handoff.get("platform_run_id", "")).strip()
        s = str(m10_handoff.get("scenario_run_id", "")).strip()
        if platform_run_id and p and p != platform_run_id:
            blockers.append({"code": "M10-B3", "message": "platform_run_id mismatch between M10.B and M10 handoff."})
        if scenario_run_id and s and s != scenario_run_id:
            blockers.append({"code": "M10-B3", "message": "scenario_run_id mismatch between M10.B and M10 handoff."})
        if not platform_run_id:
            platform_run_id = p
        if not scenario_run_id:
            scenario_run_id = s

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B3", "message": "Run scope unresolved for M10.C input binding."})

    required_refs = {
        "m9c_replay_basis_ref": str((m10_handoff or {}).get("required_evidence_refs", {}).get("m9c_replay_basis_ref", "")).strip(),
        "m9d_policy_ref": str((m10_handoff or {}).get("required_evidence_refs", {}).get("m9d_policy_ref", "")).strip(),
        "m9e_leakage_report_ref": str((m10_handoff or {}).get("required_evidence_refs", {}).get("m9e_leakage_report_ref", "")).strip(),
        "m9f_surface_separation_ref": str((m10_handoff or {}).get("required_evidence_refs", {}).get("m9f_surface_separation_ref", "")).strip(),
        "m9g_readiness_snapshot_ref": str((m10_handoff or {}).get("required_evidence_refs", {}).get("m9g_readiness_snapshot_ref", "")).strip(),
    }

    ref_heads: dict[str, Any] = {}
    for ref_name, ref_key in required_refs.items():
        if not ref_key:
            blockers.append({"code": "M10-B3", "message": f"Required handoff reference is missing: {ref_name}."})
            continue
        try:
            ref_heads[ref_name] = s3_head(s3, evidence_bucket, ref_key)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": ref_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B3", "message": f"Required handoff reference unreadable: {ref_name}."})

    run_scoped_prefix = f"evidence/runs/{platform_run_id}/learning/input/" if platform_run_id else ""
    for ref_name in ("m9c_replay_basis_ref", "m9e_leakage_report_ref", "m9g_readiness_snapshot_ref"):
        ref_key = required_refs.get(ref_name, "")
        if run_scoped_prefix and ref_key and not ref_key.startswith(run_scoped_prefix):
            blockers.append({"code": "M10-B3", "message": f"Run-scoped ref does not match required prefix: {ref_name}."})

    replay_receipt_expected = ""
    if platform_run_id:
        replay_pattern = str(handles.get("LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN", "")).strip()
        if replay_pattern:
            replay_receipt_expected = render(replay_pattern, {"platform_run_id": platform_run_id})
            if required_refs.get("m9c_replay_basis_ref", "") and required_refs["m9c_replay_basis_ref"] != replay_receipt_expected:
                blockers.append({"code": "M10-B3", "message": "Replay receipt ref does not match LEARNING_REPLAY_BASIS_RECEIPT_PATH_PATTERN."})

    replay_receipt: dict[str, Any] | None = None
    m9d_snapshot: dict[str, Any] | None = None
    leakage_report: dict[str, Any] | None = None
    m9f_snapshot: dict[str, Any] | None = None
    readiness_snapshot: dict[str, Any] | None = None

    for ref_name, target in [
        ("m9c_replay_basis_ref", "replay_receipt"),
        ("m9d_policy_ref", "m9d_snapshot"),
        ("m9e_leakage_report_ref", "leakage_report"),
        ("m9f_surface_separation_ref", "m9f_snapshot"),
        ("m9g_readiness_snapshot_ref", "readiness_snapshot"),
    ]:
        key = required_refs.get(ref_name, "")
        if not key:
            continue
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            if target == "replay_receipt":
                replay_receipt = payload
            elif target == "m9d_snapshot":
                m9d_snapshot = payload
            elif target == "leakage_report":
                leakage_report = payload
            elif target == "m9f_snapshot":
                m9f_snapshot = payload
            else:
                readiness_snapshot = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B3", "message": f"Required JSON artifact unreadable: {ref_name}."})

    replay_fingerprint = ""
    if replay_receipt:
        replay_mode_expected = str(handles.get("LEARNING_REPLAY_BASIS_MODE", "")).strip()
        replay_mode_actual = str(replay_receipt.get("replay_basis_mode", "")).strip()
        if replay_mode_expected and replay_mode_actual != replay_mode_expected:
            blockers.append({"code": "M10-B3", "message": "Replay basis mode does not match LEARNING_REPLAY_BASIS_MODE."})
        replay_fingerprint = str(replay_receipt.get("replay_basis_fingerprint", "")).strip()
        if not replay_fingerprint:
            blockers.append({"code": "M10-B3", "message": "Replay basis fingerprint is missing."})
        origin_ranges = replay_receipt.get("origin_offset_ranges", [])
        if not isinstance(origin_ranges, list) or len(origin_ranges) == 0:
            blockers.append({"code": "M10-B3", "message": "Replay basis origin_offset_ranges is empty."})
        if str(replay_receipt.get("platform_run_id", "")).strip() != platform_run_id:
            blockers.append({"code": "M10-B3", "message": "Replay receipt platform_run_id mismatch."})
        if str(replay_receipt.get("scenario_run_id", "")).strip() != scenario_run_id:
            blockers.append({"code": "M10-B3", "message": "Replay receipt scenario_run_id mismatch."})

    as_of_alignment = {
        "feature_asof_matches": False,
        "label_asof_matches": False,
        "feature_asof_not_future": False,
        "label_asof_not_future": False,
        "maturity_days_matches": False,
    }
    if m9d_snapshot and leakage_report:
        if not bool(m9d_snapshot.get("overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M9.D policy snapshot is not pass posture."})
        if not bool(leakage_report.get("overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M9.E leakage report is not pass posture."})

        feature_asof_m9d = str(m9d_snapshot.get("feature_asof_utc", "")).strip()
        label_asof_m9d = str(m9d_snapshot.get("label_asof_utc", "")).strip()
        feature_asof_m9e = str(leakage_report.get("temporal_boundaries", {}).get("feature_asof_utc", "")).strip()
        label_asof_m9e = str(leakage_report.get("temporal_boundaries", {}).get("label_asof_utc", "")).strip()
        as_of_alignment["feature_asof_matches"] = feature_asof_m9d != "" and feature_asof_m9d == feature_asof_m9e
        as_of_alignment["label_asof_matches"] = label_asof_m9d != "" and label_asof_m9d == label_asof_m9e

        try:
            feature_dt = parse_iso_utc(feature_asof_m9d)
            label_dt = parse_iso_utc(label_asof_m9d)
            as_of_alignment["feature_asof_not_future"] = feature_dt <= captured_dt
            as_of_alignment["label_asof_not_future"] = label_dt <= captured_dt
        except Exception:
            blockers.append({"code": "M10-B3", "message": "As-of timestamps are missing or unparseable for alignment check."})

        maturity_expected = int(str(handles.get("LEARNING_LABEL_MATURITY_DAYS_DEFAULT", "")).strip())
        maturity_actual = int(m9d_snapshot.get("label_maturity_days", -1))
        as_of_alignment["maturity_days_matches"] = maturity_actual == maturity_expected

    for check_name, ok in as_of_alignment.items():
        if not ok:
            blockers.append({"code": "M10-B3", "message": f"Temporal continuity check failed: {check_name}."})

    policy_expected = {
        "feature_asof_required": bool(handles.get("LEARNING_FEATURE_ASOF_REQUIRED")),
        "label_asof_required": bool(handles.get("LEARNING_LABEL_ASOF_REQUIRED")),
        "future_timestamp_policy": str(handles.get("LEARNING_FUTURE_TIMESTAMP_POLICY", "")).strip(),
        "forbidden_truth_output_ids": parse_csv_set(handles.get("LIVE_RUNTIME_FORBIDDEN_TRUTH_OUTPUT_IDS")),
        "forbidden_future_fields": parse_csv_set(handles.get("LIVE_RUNTIME_FORBIDDEN_FUTURE_FIELDS")),
    }

    leakage_policy_matrix = {
        "future_timestamp_policy_matches": False,
        "forbidden_truth_set_matches": False,
        "forbidden_future_field_set_matches": False,
    }
    if leakage_report:
        policy = leakage_report.get("policy", {})
        leakage_policy_matrix["future_timestamp_policy_matches"] = (
            str(policy.get("future_timestamp_policy", "")).strip() == policy_expected["future_timestamp_policy"]
        )
        leakage_policy_matrix["forbidden_truth_set_matches"] = set(
            policy.get("forbidden_truth_output_ids", []) if isinstance(policy.get("forbidden_truth_output_ids", []), list) else []
        ) == policy_expected["forbidden_truth_output_ids"]
        leakage_policy_matrix["forbidden_future_field_set_matches"] = set(
            policy.get("forbidden_future_fields", []) if isinstance(policy.get("forbidden_future_fields", []), list) else []
        ) == policy_expected["forbidden_future_fields"]

    if m9f_snapshot:
        if not bool(m9f_snapshot.get("overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M9.F separation snapshot is not pass posture."})
        sep = m9f_snapshot.get("separation_results", {})
        if len(sep.get("forbidden_truth_intersection", []) if isinstance(sep.get("forbidden_truth_intersection", []), list) else []) > 0:
            blockers.append({"code": "M10-B3", "message": "M9.F reports forbidden truth intersection."})
        if len(sep.get("future_derived_intersection", []) if isinstance(sep.get("future_derived_intersection", []), list) else []) > 0:
            blockers.append({"code": "M10-B3", "message": "M9.F reports future-derived intersection."})
        if len(sep.get("runtime_ref_leaks", []) if isinstance(sep.get("runtime_ref_leaks", []), list) else []) > 0:
            blockers.append({"code": "M10-B3", "message": "M9.F reports runtime reference leaks."})

    if readiness_snapshot:
        if not bool(readiness_snapshot.get("overall_pass")):
            blockers.append({"code": "M10-B3", "message": "M9.G readiness snapshot is not pass posture."})
        checks = readiness_snapshot.get("run_scoped_artifact_checks", {})
        replay_check = checks.get("m9c_replay_basis_receipt_key", {})
        leakage_check = checks.get("m9e_leakage_guardrail_report_key", {})
        if not bool(replay_check.get("exists")):
            blockers.append({"code": "M10-B3", "message": "M9.G readiness indicates replay basis receipt missing."})
        if not bool(leakage_check.get("exists")):
            blockers.append({"code": "M10-B3", "message": "M9.G readiness indicates leakage report missing."})

    for check_name, ok in leakage_policy_matrix.items():
        if not ok:
            blockers.append({"code": "M10-B3", "message": f"Leakage policy continuity check failed: {check_name}."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.D_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.C",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_refs": {
            "m10b_summary_ref": m10b_summary_key,
            "m9_summary_ref": m9_summary_key,
            "m10_handoff_ref": m10_handoff_key,
        },
        "resolved_handle_values": resolved_handle_values,
        "required_evidence_refs": required_refs,
        "reference_object_meta": ref_heads,
        "replay_basis_expected_ref": replay_receipt_expected or None,
        "replay_basis_fingerprint": replay_fingerprint or None,
        "policy_expected": {
            "feature_asof_required": policy_expected["feature_asof_required"],
            "label_asof_required": policy_expected["label_asof_required"],
            "future_timestamp_policy": policy_expected["future_timestamp_policy"],
            "forbidden_truth_output_ids": sorted(policy_expected["forbidden_truth_output_ids"]),
            "forbidden_future_fields": sorted(policy_expected["forbidden_future_fields"]),
        },
        "temporal_alignment": as_of_alignment,
        "leakage_policy_alignment": leakage_policy_matrix,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.C",
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
        "phase": "M10.C",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10c_input_binding_snapshot.json": snapshot,
        "m10c_blocker_register.json": register,
        "m10c_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.C artifacts."})
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
