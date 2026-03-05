#!/usr/bin/env python3
"""Build and publish M10.G manifest/fingerprint/time-bound audit artifacts."""

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


def parse_iso_utc(text: str) -> datetime:
    normalized = str(text or "").strip().replace("Z", "+00:00")
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


def parse_csv(value: Any) -> list[str]:
    return [x.strip() for x in str(value or "").split(",") if x.strip()]


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
    execution_id = env.get("M10G_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10G_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10f_execution = env.get("UPSTREAM_M10F_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10G_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10G_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10f_execution:
        raise SystemExit("UPSTREAM_M10F_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    captured_dt = parse_iso_utc(captured_at)
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = [
        "OFS_MANIFEST_PATH_PATTERN",
        "OFS_FINGERPRINT_PATH_PATTERN",
        "OFS_TIME_BOUND_AUDIT_PATH_PATTERN",
        "DATASET_FINGERPRINT_REQUIRED_FIELDS",
        "S3_EVIDENCE_BUCKET",
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
        blockers.append({"code": "M10-B7", "message": "Required M10.G handles are missing or placeholder-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != evidence_bucket:
        blockers.append({"code": "M10-B7", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    m10f_summary_key = f"evidence/dev_full/run_control/{upstream_m10f_execution}/m10f_execution_summary.json"
    m10f_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10f_execution}/m10f_iceberg_commit_snapshot.json"
    m10f_summary: dict[str, Any] | None = None
    m10f_snapshot: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        m10f_summary = s3_get_json(s3, evidence_bucket, m10f_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10f_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B7", "message": "M10.F summary unreadable for M10.G entry gate."})

    try:
        m10f_snapshot = s3_get_json(s3, evidence_bucket, m10f_snapshot_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10f_snapshot_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B7", "message": "M10.F snapshot unreadable for M10.G entry gate."})

    if m10f_summary:
        if not bool(m10f_summary.get("overall_pass")):
            blockers.append({"code": "M10-B7", "message": "M10.F summary is not pass posture."})
        if str(m10f_summary.get("next_gate", "")).strip() != "M10.G_READY":
            blockers.append({"code": "M10-B7", "message": "M10.F next_gate is not M10.G_READY."})
        platform_run_id = str(m10f_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10f_summary.get("scenario_run_id", "")).strip()
    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B7", "message": "Run scope unresolved for M10.G synthesis."})

    upstream_m10e_execution = str((m10f_snapshot or {}).get("upstream_m10e_execution", "")).strip()
    m10e_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10e_execution}/m10e_quality_gate_snapshot.json" if upstream_m10e_execution else ""
    m10e_snapshot: dict[str, Any] | None = None
    if not upstream_m10e_execution:
        blockers.append({"code": "M10-B7", "message": "Unable to resolve upstream M10.E execution from M10.F snapshot."})
    else:
        try:
            m10e_snapshot = s3_get_json(s3, evidence_bucket, m10e_snapshot_key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": m10e_snapshot_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B7", "message": "M10.E snapshot unreadable for lineage continuity."})

    upstream_m10d_execution = str((m10e_snapshot or {}).get("upstream_m10d_execution", "")).strip()
    m10d_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10d_execution}/m10d_ofs_build_execution_snapshot.json" if upstream_m10d_execution else ""
    m10d_snapshot: dict[str, Any] | None = None
    if not upstream_m10d_execution:
        blockers.append({"code": "M10-B7", "message": "Unable to resolve upstream M10.D execution from M10.E snapshot."})
    else:
        try:
            m10d_snapshot = s3_get_json(s3, evidence_bucket, m10d_snapshot_key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": m10d_snapshot_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B7", "message": "M10.D snapshot unreadable for lineage continuity."})

    upstream_m10c_execution = str((m10d_snapshot or {}).get("upstream_m10c_execution", "")).strip()
    m10c_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10c_execution}/m10c_input_binding_snapshot.json" if upstream_m10c_execution else ""
    m10c_snapshot: dict[str, Any] | None = None
    if not upstream_m10c_execution:
        blockers.append({"code": "M10-B7", "message": "Unable to resolve upstream M10.C execution from M10.D snapshot."})
    else:
        try:
            m10c_snapshot = s3_get_json(s3, evidence_bucket, m10c_snapshot_key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": m10c_snapshot_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B7", "message": "M10.C snapshot unreadable for lineage continuity."})

    required_refs = dict((m10c_snapshot or {}).get("required_evidence_refs", {}))
    m9c_ref = str(required_refs.get("m9c_replay_basis_ref", "")).strip()
    m9d_ref = str(required_refs.get("m9d_policy_ref", "")).strip()
    m9e_ref = str(required_refs.get("m9e_leakage_report_ref", "")).strip()
    replay_receipt: dict[str, Any] | None = None
    m9d_policy_snapshot: dict[str, Any] | None = None
    leakage_report: dict[str, Any] | None = None
    for ref_name, ref_key in [("m9c_replay_basis_ref", m9c_ref), ("m9d_policy_ref", m9d_ref), ("m9e_leakage_report_ref", m9e_ref)]:
        if not ref_key:
            blockers.append({"code": "M10-B7", "message": f"Required lineage ref missing in M10.C snapshot: {ref_name}."})
            continue
        try:
            payload = s3_get_json(s3, evidence_bucket, ref_key)
            if ref_name == "m9c_replay_basis_ref":
                replay_receipt = payload
            elif ref_name == "m9d_policy_ref":
                m9d_policy_snapshot = payload
            else:
                leakage_report = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": ref_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B7", "message": f"Required lineage ref unreadable for M10.G synthesis: {ref_name}."})

    manifest_key = ""
    fingerprint_key = ""
    audit_key = ""
    if platform_run_id:
        manifest_pattern = str(handles.get("OFS_MANIFEST_PATH_PATTERN", "")).strip()
        fingerprint_pattern = str(handles.get("OFS_FINGERPRINT_PATH_PATTERN", "")).strip()
        audit_pattern = str(handles.get("OFS_TIME_BOUND_AUDIT_PATH_PATTERN", "")).strip()
        if manifest_pattern:
            manifest_key = render(manifest_pattern, {"platform_run_id": platform_run_id})
        if fingerprint_pattern:
            fingerprint_key = render(fingerprint_pattern, {"platform_run_id": platform_run_id})
        if audit_pattern:
            audit_key = render(audit_pattern, {"platform_run_id": platform_run_id})
    if not manifest_key or not fingerprint_key or not audit_key:
        blockers.append({"code": "M10-B7", "message": "Unable to resolve run-scoped OFS artifact paths from handle patterns."})

    fingerprint_fields = parse_csv(handles.get("DATASET_FINGERPRINT_REQUIRED_FIELDS"))
    if not fingerprint_fields:
        blockers.append({"code": "M10-B7", "message": "DATASET_FINGERPRINT_REQUIRED_FIELDS resolved empty."})

    deterministic_surface = dict((m10f_snapshot or {}).get("deterministic_surface", {}))
    replay_basis = str((replay_receipt or {}).get("replay_basis_fingerprint", "")).strip() or str((m10c_snapshot or {}).get("replay_basis_fingerprint", "")).strip()
    feature_asof_utc = str((m9d_policy_snapshot or {}).get("feature_asof_utc", "")).strip()
    label_asof_utc = str((m9d_policy_snapshot or {}).get("label_asof_utc", "")).strip()
    label_maturity_days = str((m9d_policy_snapshot or {}).get("label_maturity_days", "")).strip()
    feature_def_set = str(((m10d_snapshot or {}).get("source_provenance", {}) or {}).get("repo_source_sha256", "")).strip()
    join_scope = str(deterministic_surface.get("table_name", "")).strip()
    cohort_filters = ",".join(sorted(required_refs.keys()))
    ofs_code_release_id = str(((m10d_snapshot or {}).get("source_provenance", {}) or {}).get("repo_source_sha256", "")).strip()
    mf_code_release_id = str((m10c_snapshot or {}).get("execution_id", "")).strip()

    field_source = {
        "replay_basis": replay_basis,
        "feature_asof_utc": feature_asof_utc,
        "label_asof_utc": label_asof_utc,
        "label_maturity_days": label_maturity_days,
        "feature_def_set": feature_def_set,
        "join_scope": join_scope,
        "cohort_filters": cohort_filters,
        "ofs_code_release_id": ofs_code_release_id,
        "mf_code_release_id": mf_code_release_id,
    }
    fingerprint_field_values: dict[str, Any] = {}
    for field in fingerprint_fields:
        value = field_source.get(field, "")
        if str(value).strip() == "":
            blockers.append({"code": "M10-B7", "message": f"Fingerprint required field resolved empty: {field}."})
        fingerprint_field_values[field] = value

    fingerprint_digest = hashlib.sha256(
        json.dumps(fingerprint_field_values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    leakage_boundary = (leakage_report or {}).get("boundary_check", {}) if isinstance((leakage_report or {}).get("boundary_check", {}), dict) else {}
    leakage_violation_count = int(leakage_boundary.get("violation_count", 0))
    forbidden_intersection = ((leakage_report or {}).get("truth_surface_check", {}) or {}).get("forbidden_intersection", [])
    if not isinstance(forbidden_intersection, list):
        forbidden_intersection = []
    forbidden_intersection_count = len(forbidden_intersection)

    feature_asof_not_future = False
    label_asof_not_future = False
    try:
        feature_asof_not_future = parse_iso_utc(feature_asof_utc) <= captured_dt
        label_asof_not_future = parse_iso_utc(label_asof_utc) <= captured_dt
    except Exception:
        blockers.append({"code": "M10-B7", "message": "Unable to parse as-of timestamps for time-bound audit synthesis."})

    audit_overall_pass = (
        leakage_violation_count == 0
        and forbidden_intersection_count == 0
        and feature_asof_not_future
        and label_asof_not_future
    )
    if not audit_overall_pass:
        blockers.append({"code": "M10-B7", "message": "Time-bound audit did not satisfy pass posture."})

    manifest_payload = {
        "captured_at_utc": captured_at,
        "phase": "M10.G",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_executions": {
            "m10c_execution": upstream_m10c_execution,
            "m10d_execution": upstream_m10d_execution,
            "m10e_execution": upstream_m10e_execution,
            "m10f_execution": upstream_m10f_execution,
        },
        "iceberg_surface": deterministic_surface,
        "required_input_refs": required_refs,
        "source_provenance": (m10d_snapshot or {}).get("source_provenance", {}),
    }

    fingerprint_payload = {
        "captured_at_utc": captured_at,
        "phase": "M10.G",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "required_fields": fingerprint_fields,
        "field_values": fingerprint_field_values,
        "fingerprint_sha256": fingerprint_digest,
    }

    audit_payload = {
        "captured_at_utc": captured_at,
        "phase": "M10.G",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "feature_asof_utc": feature_asof_utc,
        "label_asof_utc": label_asof_utc,
        "label_maturity_days": int(label_maturity_days) if str(label_maturity_days).strip().isdigit() else label_maturity_days,
        "future_timestamp_policy": str(((leakage_report or {}).get("policy", {}) or {}).get("future_timestamp_policy", "")).strip(),
        "leakage_future_breach_count": leakage_violation_count,
        "forbidden_truth_intersection_count": forbidden_intersection_count,
        "feature_asof_not_future": feature_asof_not_future,
        "label_asof_not_future": label_asof_not_future,
        "overall_pass": audit_overall_pass,
    }

    if len(blockers) == 0:
        try:
            s3_put_json(s3, evidence_bucket, manifest_key, manifest_payload)
            s3_put_json(s3, evidence_bucket, fingerprint_key, fingerprint_payload)
            s3_put_json(s3, evidence_bucket, audit_key, audit_payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"surface": "run_scoped_ofs_outputs", "error": type(exc).__name__})
            blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more run-scoped M10.G outputs."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.H_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.G",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10f_execution": upstream_m10f_execution,
        "upstream_m10f_summary_key": m10f_summary_key,
        "upstream_m10f_snapshot_key": m10f_snapshot_key,
        "upstream_lineage": {
            "m10e_execution": upstream_m10e_execution,
            "m10e_snapshot_key": m10e_snapshot_key,
            "m10d_execution": upstream_m10d_execution,
            "m10d_snapshot_key": m10d_snapshot_key,
            "m10c_execution": upstream_m10c_execution,
            "m10c_snapshot_key": m10c_snapshot_key,
        },
        "resolved_handle_values": resolved_handle_values,
        "run_scoped_outputs": {
            "manifest_key": manifest_key,
            "fingerprint_key": fingerprint_key,
            "time_bound_audit_key": audit_key,
        },
        "fingerprint_sha256": fingerprint_digest,
        "time_bound_audit_overall_pass": audit_overall_pass,
        "time_bound_audit_leakage_future_breach_count": leakage_violation_count,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.G",
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
        "phase": "M10.G",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10g_manifest_fingerprint_snapshot.json": snapshot,
        "m10g_blocker_register.json": register,
        "m10g_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.G artifacts."})
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
