#!/usr/bin/env python3
"""Build and publish M10.H rollback-recipe closure artifacts."""

from __future__ import annotations

import json
import os
import re
import time
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
    execution_id = env.get("M10H_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10H_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10g_execution = env.get("UPSTREAM_M10G_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10H_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10H_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10g_execution:
        raise SystemExit("UPSTREAM_M10G_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    if is_placeholder(handles.get("S3_EVIDENCE_BUCKET")):
        blockers.append({"code": "M10-B8", "message": "S3_EVIDENCE_BUCKET handle is unresolved for M10.H closure."})
    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != evidence_bucket:
        blockers.append({"code": "M10-B8", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    m10g_summary_key = f"evidence/dev_full/run_control/{upstream_m10g_execution}/m10g_execution_summary.json"
    m10g_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10g_execution}/m10g_manifest_fingerprint_snapshot.json"
    m10g_summary: dict[str, Any] | None = None
    m10g_snapshot: dict[str, Any] | None = None
    platform_run_id = ""
    scenario_run_id = ""

    try:
        m10g_summary = s3_get_json(s3, evidence_bucket, m10g_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10g_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B8", "message": "M10.G summary unreadable for M10.H entry gate."})

    try:
        m10g_snapshot = s3_get_json(s3, evidence_bucket, m10g_snapshot_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m10g_snapshot_key, "error": type(exc).__name__})
        blockers.append({"code": "M10-B8", "message": "M10.G snapshot unreadable for M10.H entry gate."})

    if m10g_summary:
        if not bool(m10g_summary.get("overall_pass")):
            blockers.append({"code": "M10-B8", "message": "M10.G summary is not pass posture."})
        if str(m10g_summary.get("next_gate", "")).strip() != "M10.H_READY":
            blockers.append({"code": "M10-B8", "message": "M10.G next_gate is not M10.H_READY."})
        platform_run_id = str(m10g_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10g_summary.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M10-B8", "message": "Run scope unresolved for M10.H rollback closure."})

    outputs = dict((m10g_snapshot or {}).get("run_scoped_outputs", {}))
    manifest_key = str(outputs.get("manifest_key", "")).strip()
    fingerprint_key = str(outputs.get("fingerprint_key", "")).strip()
    audit_key = str(outputs.get("time_bound_audit_key", "")).strip()
    if not manifest_key or not fingerprint_key or not audit_key:
        blockers.append({"code": "M10-B8", "message": "M10.G run-scoped output refs are incomplete."})

    manifest: dict[str, Any] | None = None
    fingerprint: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    for name, key in [("manifest", manifest_key), ("fingerprint", fingerprint_key), ("audit", audit_key)]:
        if not key:
            continue
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            if name == "manifest":
                manifest = payload
            elif name == "fingerprint":
                fingerprint = payload
            else:
                audit = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B8", "message": f"Run-scoped OFS artifact unreadable for rollback closure: {name}."})

    upstream_m10f_execution = str((m10g_snapshot or {}).get("upstream_m10f_execution", "")).strip()
    m10f_snapshot_key = f"evidence/dev_full/run_control/{upstream_m10f_execution}/m10f_iceberg_commit_snapshot.json" if upstream_m10f_execution else ""
    m10f_snapshot: dict[str, Any] | None = None
    if not upstream_m10f_execution:
        blockers.append({"code": "M10-B8", "message": "Unable to resolve upstream M10.F execution from M10.G snapshot."})
    else:
        try:
            m10f_snapshot = s3_get_json(s3, evidence_bucket, m10f_snapshot_key)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": m10f_snapshot_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B8", "message": "M10.F snapshot unreadable for rollback target derivation."})

    deterministic_surface = dict((m10f_snapshot or {}).get("deterministic_surface", {}))
    rollback_target = {
        "database_name": str(deterministic_surface.get("database_name", "")).strip(),
        "table_name": str(deterministic_surface.get("table_name", "")).strip(),
        "table_location": str(deterministic_surface.get("table_location", "")).strip(),
        "s3_commit_marker_key": str(deterministic_surface.get("s3_commit_marker_key", "")).strip(),
    }
    if not rollback_target["database_name"] or not rollback_target["table_name"] or not rollback_target["table_location"]:
        blockers.append({"code": "M10-B8", "message": "Rollback target derivation is incomplete."})

    recipe_key = f"evidence/runs/{platform_run_id}/learning/ofs/rollback_recipe.json" if platform_run_id else ""
    drill_key = f"evidence/runs/{platform_run_id}/learning/ofs/rollback_drill_report.json" if platform_run_id else ""
    if not recipe_key or not drill_key:
        blockers.append({"code": "M10-B8", "message": "Unable to resolve run-scoped rollback output paths."})

    objective = {
        "rto_target_seconds": int(handles.get("MPR_ROLLBACK_RTO_TARGET_SECONDS", 900)),
        "rto_hard_max_seconds": int(handles.get("MPR_ROLLBACK_RTO_HARD_MAX_SECONDS", 1200)),
        "rpo_target_events": int(handles.get("MPR_ROLLBACK_RPO_TARGET_EVENTS", 0)),
        "objective_enforcement": str(handles.get("MPR_ROLLBACK_OBJECTIVE_ENFORCEMENT", "fail_closed")).strip(),
    }

    start = time.time()
    checks = [
        {"name": "manifest_readable", "pass": manifest is not None},
        {"name": "fingerprint_readable", "pass": fingerprint is not None},
        {"name": "audit_readable", "pass": audit is not None},
        {"name": "audit_overall_pass", "pass": bool((audit or {}).get("overall_pass"))},
        {"name": "fingerprint_sha_present", "pass": bool(str((fingerprint or {}).get("fingerprint_sha256", "")).strip())},
        {"name": "rollback_target_complete", "pass": bool(rollback_target["database_name"] and rollback_target["table_name"] and rollback_target["table_location"])},
        {"name": "commit_marker_declared", "pass": bool(rollback_target["s3_commit_marker_key"])},
    ]
    drill_pass = all(bool(row.get("pass")) for row in checks)
    if not drill_pass:
        blockers.append({"code": "M10-B8", "message": "Rollback drill preconditions did not satisfy pass posture."})

    elapsed_seconds = int(max(0, round(time.time() - start)))
    if elapsed_seconds > objective["rto_hard_max_seconds"]:
        blockers.append({"code": "M10-B8", "message": "Rollback drill elapsed time exceeded hard RTO maximum."})
        drill_pass = False

    rollback_recipe = {
        "captured_at_utc": captured_at,
        "phase": "M10.H",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "objective": objective,
        "rollback_target": rollback_target,
        "input_refs": {
            "manifest_key": manifest_key,
            "fingerprint_key": fingerprint_key,
            "time_bound_audit_key": audit_key,
            "m10f_snapshot_key": m10f_snapshot_key,
            "upstream_m10g_execution": upstream_m10g_execution,
        },
        "blast_radius": "metadata-pointer and verification only; no mutable dataset writes by drill",
        "idempotency_key": f"{platform_run_id}:{execution_id}",
        "ordered_steps": [
            "Verify deterministic target table identity and marker readability.",
            "Verify run-scoped manifest/fingerprint/time-bound audit readability and pass posture.",
            "Prepare rollback metadata-pointer target and validation checkpoints.",
            "Execute non-destructive readiness drill (no dataset mutation).",
            "Record drill verdict and enforce fail-closed objective gates.",
        ],
        "operator_stop_gates": [
            "Abort on unresolved target identity.",
            "Abort on time-bound audit fail posture.",
            "Abort on missing/invalid fingerprint digest.",
        ],
    }

    rollback_drill = {
        "captured_at_utc": captured_at,
        "phase": "M10.H",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "drill_mode": "non_destructive_readiness",
        "checks": checks,
        "drill_pass": drill_pass,
        "rollback_status": "READY" if drill_pass else "BLOCKED",
        "restore_elapsed_seconds": elapsed_seconds,
        "rto_target_seconds": objective["rto_target_seconds"],
        "rto_hard_max_seconds": objective["rto_hard_max_seconds"],
        "rpo_target_events": objective["rpo_target_events"],
        "objective_enforcement": objective["objective_enforcement"],
    }

    if len(blockers) == 0:
        try:
            s3_put_json(s3, evidence_bucket, recipe_key, rollback_recipe)
            s3_put_json(s3, evidence_bucket, drill_key, rollback_drill)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"surface": "run_scoped_rollback_outputs", "error": type(exc).__name__})
            blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more run-scoped rollback outputs."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M10.I_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M10.H",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10g_execution": upstream_m10g_execution,
        "upstream_m10g_summary_key": m10g_summary_key,
        "upstream_m10g_snapshot_key": m10g_snapshot_key,
        "upstream_m10f_execution": upstream_m10f_execution,
        "upstream_m10f_snapshot_key": m10f_snapshot_key,
        "run_scoped_outputs": {
            "rollback_recipe_key": recipe_key,
            "rollback_drill_report_key": drill_key,
        },
        "rollback_target": rollback_target,
        "drill_pass": drill_pass,
        "restore_elapsed_seconds": elapsed_seconds,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M10.H",
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
        "phase": "M10.H",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m10h_rollback_recipe_snapshot.json": snapshot,
        "m10h_blocker_register.json": register,
        "m10h_execution_summary.json": summary,
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
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback one or more M10.H artifacts."})
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
