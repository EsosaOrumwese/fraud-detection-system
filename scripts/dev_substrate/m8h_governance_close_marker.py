#!/usr/bin/env python3
"""Managed M8.H governance append + closure-marker validator."""

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


def is_placeholder(v: Any) -> bool:
    s = str(v or "").strip().lower()
    if not s:
        return True
    if s in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "placeholder" in s or "to_pin" in s:
        return True
    if "<" in s and ">" in s:
        return True
    return False


def dedupe(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for b in blockers:
        code = str(b.get("code", "")).strip()
        msg = str(b.get("message", "")).strip()
        sig = (code, msg)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": msg})
    return out


def s3_get_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def s3_get_text(s3: Any, bucket: str, key: str) -> str:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def s3_put_json(s3: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3.head_object(Bucket=bucket, Key=key)


def s3_put_text(s3: Any, bucket: str, key: str, text: str, content_type: str) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=text.encode("utf-8"), ContentType=content_type)
    s3.head_object(Bucket=bucket, Key=key)


def write_local(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_ts(ts: str) -> float | None:
    text = str(ts or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def render_pattern(pattern: str, platform_run_id: str) -> str:
    return pattern.replace("{platform_run_id}", platform_run_id)


def main() -> int:
    start = time.time()
    env = dict(os.environ)

    execution_id = env.get("M8H_EXECUTION_ID", "").strip()
    run_dir = Path(env.get("M8H_RUN_DIR", "").strip())
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8g = env.get("UPSTREAM_M8G_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    governance_sample_limit = max(10, int(env.get("M8H_GOV_SAMPLE_LIMIT", "50")))

    if not execution_id:
        raise SystemExit("M8H_EXECUTION_ID is required.")
    if not str(run_dir):
        raise SystemExit("M8H_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8g:
        raise SystemExit("UPSTREAM_M8G_EXECUTION is required.")

    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = {
        "S3_OBJECT_STORE_BUCKET": str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip(),
        "S3_EVIDENCE_BUCKET": str(handles.get("S3_EVIDENCE_BUCKET", "")).strip(),
        "GOV_APPEND_LOG_PATH_PATTERN": str(handles.get("GOV_APPEND_LOG_PATH_PATTERN", "")).strip(),
        "GOV_RUN_CLOSE_MARKER_PATH_PATTERN": str(handles.get("GOV_RUN_CLOSE_MARKER_PATH_PATTERN", "")).strip(),
    }
    unresolved = [k for k, v in required_handles.items() if is_placeholder(v)]
    if unresolved:
        blockers.append({"code": "M8-B8", "message": f"Required handles unresolved: {','.join(sorted(unresolved))}."})
    if required_handles["S3_EVIDENCE_BUCKET"] and required_handles["S3_EVIDENCE_BUCKET"] != evidence_bucket:
        blockers.append({"code": "M8-B8", "message": "EVIDENCE_BUCKET does not match handle registry S3_EVIDENCE_BUCKET."})

    m8g_summary_key = f"evidence/dev_full/run_control/{upstream_m8g}/m8g_execution_summary.json"
    m8g_summary: dict[str, Any] | None = None
    try:
        m8g_summary = s3_get_json(s3, evidence_bucket, m8g_summary_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m8g_summary_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B8", "message": "Upstream M8.G summary unreadable."})

    platform_run_id = ""
    scenario_run_id = ""
    entry_gate_ok = False
    if isinstance(m8g_summary, dict):
        entry_gate_ok = bool(m8g_summary.get("overall_pass")) and str(m8g_summary.get("next_gate", "")).strip() == "M8.H_READY"
        if not entry_gate_ok:
            blockers.append({"code": "M8-B8", "message": "M8.G gate is not M8.H_READY."})
        platform_run_id = str(m8g_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m8g_summary.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B8", "message": "Run scope unresolved from M8.G summary."})

    object_store_bucket = required_handles["S3_OBJECT_STORE_BUCKET"]
    run_completed_key = f"{platform_run_id}/run_completed.json"
    gov_events_key = f"{platform_run_id}/obs/governance/events.jsonl"
    gov_markers_prefix = f"{platform_run_id}/obs/governance/markers/"

    source_truth_checks: dict[str, Any] = {
        "run_completed": {"readable": False, "status_completed": False, "run_scope_ok": False, "has_governance_ref": False},
        "events_schema": {"readable": False, "line_count": 0, "sampled_count": 0, "required_fields_ok": False, "run_scope_ok": False},
        "event_family": {"has_run_report_generated": False},
        "marker_coverage": {"marker_count": 0, "event_id_count": 0, "coverage_ok": False},
        "ordering": {"ts_non_decreasing": False},
    }

    run_completed_payload: dict[str, Any] = {}
    events_text = ""
    event_rows: list[dict[str, Any]] = []
    marker_keys: list[str] = []

    try:
        run_completed_payload = s3_get_json(s3, object_store_bucket, run_completed_key)
        source_truth_checks["run_completed"]["readable"] = True
        source_truth_checks["run_completed"]["status_completed"] = str(run_completed_payload.get("status", "")).strip().upper() == "COMPLETED"
        source_truth_checks["run_completed"]["run_scope_ok"] = str(run_completed_payload.get("platform_run_id", "")).strip() == platform_run_id
        closure_refs = run_completed_payload.get("closure_refs") if isinstance(run_completed_payload.get("closure_refs"), dict) else {}
        gov_ref = str(closure_refs.get("governance_events_ref", "")).strip()
        source_truth_checks["run_completed"]["has_governance_ref"] = bool(gov_ref) and gov_ref == gov_events_key
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": f"s3://{object_store_bucket}/{run_completed_key}", "error": type(exc).__name__})
        blockers.append({"code": "M8-B8", "message": "run_completed source artifact unreadable."})

    try:
        events_text = s3_get_text(s3, object_store_bucket, gov_events_key)
        source_truth_checks["events_schema"]["readable"] = True
    except (BotoCoreError, ClientError) as exc:
        read_errors.append({"surface": f"s3://{object_store_bucket}/{gov_events_key}", "error": type(exc).__name__})
        blockers.append({"code": "M8-B8", "message": "governance events source artifact unreadable."})

    if source_truth_checks["events_schema"]["readable"]:
        lines = [ln for ln in events_text.splitlines() if ln.strip()]
        source_truth_checks["events_schema"]["line_count"] = len(lines)
        sample = lines[:governance_sample_limit]
        source_truth_checks["events_schema"]["sampled_count"] = len(sample)
        required_fields_ok = True
        run_scope_ok = True
        has_run_report_generated = False
        event_ids: set[str] = set()
        prev_ts: float | None = None
        ts_non_decreasing = True
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                blockers.append({"code": "M8-B8", "message": "governance events contain invalid JSON lines."})
                required_fields_ok = False
                run_scope_ok = False
                ts_non_decreasing = False
                continue
            if not isinstance(row, dict):
                required_fields_ok = False
                continue
            event_rows.append(row)
            ev_id = str(row.get("event_id", "")).strip()
            ev_family = str(row.get("event_family", "")).strip()
            ts_utc = str(row.get("ts_utc", "")).strip()
            pins = row.get("pins") if isinstance(row.get("pins"), dict) else {}
            row_run_id = str(pins.get("platform_run_id", "")).strip()
            if not ev_id or not ev_family or not ts_utc or not row_run_id:
                required_fields_ok = False
            if row_run_id != platform_run_id:
                run_scope_ok = False
            if ev_family == "RUN_REPORT_GENERATED":
                has_run_report_generated = True
            event_ids.add(ev_id)
            ts_val = parse_ts(ts_utc)
            if ts_val is None:
                ts_non_decreasing = False
            else:
                if prev_ts is not None and ts_val < prev_ts:
                    ts_non_decreasing = False
                prev_ts = ts_val

        source_truth_checks["events_schema"]["required_fields_ok"] = required_fields_ok
        source_truth_checks["events_schema"]["run_scope_ok"] = run_scope_ok
        source_truth_checks["event_family"]["has_run_report_generated"] = has_run_report_generated
        source_truth_checks["ordering"]["ts_non_decreasing"] = ts_non_decreasing
        source_truth_checks["marker_coverage"]["event_id_count"] = len(event_ids)

        if not required_fields_ok:
            blockers.append({"code": "M8-B8", "message": "governance events schema required-field checks failed."})
        if not run_scope_ok:
            blockers.append({"code": "M8-B8", "message": "governance events run-scope checks failed."})
        if not has_run_report_generated:
            blockers.append({"code": "M8-B8", "message": "governance events missing RUN_REPORT_GENERATED family."})
        if not ts_non_decreasing:
            blockers.append({"code": "M8-B8", "message": "governance append ordering is not monotonic by ts_utc."})

        # Marker coverage.
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=object_store_bucket, Prefix=gov_markers_prefix):
                for item in page.get("Contents", []):
                    key = str(item.get("Key", "")).strip()
                    if key:
                        marker_keys.append(key)
            source_truth_checks["marker_coverage"]["marker_count"] = len(marker_keys)
            marker_ids = {Path(k).stem for k in marker_keys}
            coverage_ok = source_truth_checks["marker_coverage"]["event_id_count"] <= len(marker_ids)
            source_truth_checks["marker_coverage"]["coverage_ok"] = coverage_ok
            if not coverage_ok:
                blockers.append({"code": "M8-B8", "message": "governance marker coverage is below event-id count."})
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": f"s3://{object_store_bucket}/{gov_markers_prefix}", "error": type(exc).__name__})
            blockers.append({"code": "M8-B8", "message": "governance marker prefix unreadable."})

    # Projection to handle-contract governance paths in evidence bucket.
    gov_append_key = render_pattern(required_handles["GOV_APPEND_LOG_PATH_PATTERN"], platform_run_id) if platform_run_id else ""
    gov_closure_marker_key = render_pattern(required_handles["GOV_RUN_CLOSE_MARKER_PATH_PATTERN"], platform_run_id) if platform_run_id else ""

    projection_targets = {
        "gov_append_log_key": gov_append_key,
        "gov_closure_marker_key": gov_closure_marker_key,
        "append_projection_written": False,
        "append_projection_readback": False,
        "marker_projection_written": False,
        "marker_projection_readback": False,
    }

    closure_marker_payload = {
        "generated_at_utc": now_utc(),
        "phase": "M8.H",
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "status": "COMPLETED",
        "source_refs": {
            "run_completed": f"s3://{object_store_bucket}/{run_completed_key}",
            "governance_events": f"s3://{object_store_bucket}/{gov_events_key}",
            "governance_markers_prefix": f"s3://{object_store_bucket}/{gov_markers_prefix}",
        },
        "source_truth_checks": source_truth_checks,
        "closure_refs": run_completed_payload.get("closure_refs", {}),
    }

    if not blockers and gov_append_key and gov_closure_marker_key:
        try:
            s3_put_text(s3, evidence_bucket, gov_append_key, events_text, "application/x-ndjson")
            projection_targets["append_projection_written"] = True
            _ = s3_get_text(s3, evidence_bucket, gov_append_key)
            projection_targets["append_projection_readback"] = True
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": "gov_append_log_projection", "key": gov_append_key, "error": type(exc).__name__})
            blockers.append({"code": "M8-B8", "message": "Failed to materialize governance append projection."})

        try:
            s3_put_json(s3, evidence_bucket, gov_closure_marker_key, closure_marker_payload)
            projection_targets["marker_projection_written"] = True
            _ = s3_get_json(s3, evidence_bucket, gov_closure_marker_key)
            projection_targets["marker_projection_readback"] = True
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            upload_errors.append({"artifact": "gov_closure_marker_projection", "key": gov_closure_marker_key, "error": type(exc).__name__})
            blockers.append({"code": "M8-B8", "message": "Failed to materialize governance closure-marker projection."})

    blockers = dedupe(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.I_READY" if overall_pass else "HOLD_REMEDIATE"
    elapsed = round(time.time() - start, 3)

    snapshot = {
        "captured_at_utc": now_utc(),
        "phase": "M8.H",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "source_m8g_summary_uri": f"s3://{evidence_bucket}/{m8g_summary_key}",
        "source_refs": {
            "run_completed": f"s3://{object_store_bucket}/{run_completed_key}",
            "governance_events": f"s3://{object_store_bucket}/{gov_events_key}",
            "governance_markers_prefix": f"s3://{object_store_bucket}/{gov_markers_prefix}",
        },
        "entry_gate_ok": entry_gate_ok,
        "source_truth_checks": source_truth_checks,
        "projection_targets": projection_targets,
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
    }

    register = {
        "captured_at_utc": now_utc(),
        "phase": "M8.H",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": now_utc(),
        "phase": "M8.H",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_refs": {"m8g_execution_id": upstream_m8g},
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
        "durable_artifacts": {
            "m8h_snapshot_key": f"evidence/dev_full/run_control/{execution_id}/m8h_governance_close_marker_snapshot.json",
            "m8h_blocker_register_key": f"evidence/dev_full/run_control/{execution_id}/m8h_blocker_register.json",
            "m8h_execution_summary_key": f"evidence/dev_full/run_control/{execution_id}/m8h_execution_summary.json",
            "gov_append_log_key": gov_append_key,
            "gov_closure_marker_key": gov_closure_marker_key,
        },
    }

    artifacts = {
        "m8h_governance_close_marker_snapshot.json": snapshot,
        "m8h_blocker_register.json": register,
        "m8h_execution_summary.json": summary,
    }
    write_local(run_dir, artifacts)

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        target_key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, target_key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "key": target_key, "error": type(exc).__name__})

    if upload_errors:
        blockers.append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.H artifacts."})
        blockers = dedupe(blockers)
        overall_pass = False
        next_gate = "HOLD_REMEDIATE"
        elapsed = round(time.time() - start, 3)
        snapshot["blockers"] = blockers
        snapshot["overall_pass"] = False
        snapshot["next_gate"] = next_gate
        snapshot["elapsed_seconds"] = elapsed
        register["upload_errors"] = upload_errors
        register["blockers"] = blockers
        register["blocker_count"] = len(blockers)
        summary["overall_pass"] = False
        summary["blocker_count"] = len(blockers)
        summary["next_gate"] = next_gate
        summary["elapsed_seconds"] = elapsed
        artifacts = {
            "m8h_governance_close_marker_snapshot.json": snapshot,
            "m8h_blocker_register.json": register,
            "m8h_execution_summary.json": summary,
        }
        write_local(run_dir, artifacts)

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "overall_pass": summary["overall_pass"],
                "blocker_count": summary["blocker_count"],
                "next_gate": summary["next_gate"],
                "run_dir": str(run_dir),
                "run_control_prefix": f"s3://{evidence_bucket}/{run_control_prefix}/",
                "gov_append_log_uri": f"s3://{evidence_bucket}/{gov_append_key}" if gov_append_key else "",
                "gov_closure_marker_uri": f"s3://{evidence_bucket}/{gov_closure_marker_key}" if gov_closure_marker_key else "",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
