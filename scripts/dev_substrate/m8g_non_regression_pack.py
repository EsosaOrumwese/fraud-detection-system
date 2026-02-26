#!/usr/bin/env python3
"""Managed M8.G spine non-regression pack validator."""

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


def s3_put_json(s3: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3.head_object(Bucket=bucket, Key=key)


def write_local(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def safe_int(v: Any) -> tuple[bool, int]:
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return False, 0
    return True, iv


def render_pattern(pattern: str, platform_run_id: str) -> str:
    return pattern.replace("{platform_run_id}", platform_run_id)


def main() -> int:
    start = time.time()
    env = dict(os.environ)

    execution_id = env.get("M8G_EXECUTION_ID", "").strip()
    run_dir = Path(env.get("M8G_RUN_DIR", "").strip())
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8f = env.get("UPSTREAM_M8F_EXECUTION", "").strip()
    upstream_m6j = env.get("UPSTREAM_M6J_EXECUTION", "m6j_m6_closure_sync_20260225T194637Z").strip()
    upstream_m7j = env.get("UPSTREAM_M7J_EXECUTION", "m7q_m7_rollup_sync_20260226T031710Z").strip()
    upstream_m7k = env.get("UPSTREAM_M7K_EXECUTION", "m7s_m7k_cert_20260226T000002Z").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M8G_EXECUTION_ID is required.")
    if not str(run_dir):
        raise SystemExit("M8G_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8f:
        raise SystemExit("UPSTREAM_M8F_EXECUTION is required.")

    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = {
        "S3_OBJECT_STORE_BUCKET": str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip(),
        "S3_EVIDENCE_BUCKET": str(handles.get("S3_EVIDENCE_BUCKET", "")).strip(),
        "SPINE_NON_REGRESSION_PACK_PATTERN": str(handles.get("SPINE_NON_REGRESSION_PACK_PATTERN", "")).strip(),
    }
    unresolved = [k for k, v in required_handles.items() if is_placeholder(v)]
    if unresolved:
        blockers.append({"code": "M8-B7", "message": f"Required handles unresolved: {','.join(sorted(unresolved))}."})
    if required_handles["S3_EVIDENCE_BUCKET"] and required_handles["S3_EVIDENCE_BUCKET"] != evidence_bucket:
        blockers.append({"code": "M8-B7", "message": "EVIDENCE_BUCKET does not match handle registry S3_EVIDENCE_BUCKET."})

    m8f_key = f"evidence/dev_full/run_control/{upstream_m8f}/m8f_execution_summary.json"
    m8f_summary: dict[str, Any] | None = None
    try:
        m8f_summary = s3_get_json(s3, evidence_bucket, m8f_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": m8f_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B7", "message": "Upstream M8.F summary unreadable."})

    requested_platform_run_id = env.get("PLATFORM_RUN_ID", "").strip()
    requested_scenario_run_id = env.get("SCENARIO_RUN_ID", "").strip()
    active_platform_run_id = ""
    active_scenario_run_id = ""
    m8f_gate_ok = False
    if isinstance(m8f_summary, dict):
        m8f_gate_ok = bool(m8f_summary.get("overall_pass")) and str(m8f_summary.get("next_gate", "")).strip() == "M8.G_READY"
        if not m8f_gate_ok:
            blockers.append({"code": "M8-B7", "message": "M8.F gate is not M8.G_READY."})
        active_platform_run_id = str(m8f_summary.get("platform_run_id", "")).strip()
        active_scenario_run_id = str(m8f_summary.get("scenario_run_id", "")).strip()
        if requested_platform_run_id and requested_platform_run_id != active_platform_run_id:
            blockers.append({"code": "M8-B7", "message": "Provided PLATFORM_RUN_ID does not match upstream M8.F run scope."})
        if requested_scenario_run_id and requested_scenario_run_id != active_scenario_run_id:
            blockers.append({"code": "M8-B7", "message": "Provided SCENARIO_RUN_ID does not match upstream M8.F run scope."})
    else:
        active_platform_run_id = requested_platform_run_id
        active_scenario_run_id = requested_scenario_run_id

    if not active_platform_run_id or not active_scenario_run_id:
        blockers.append({"code": "M8-B7", "message": "Active run scope unresolved from M8.F."})

    anchor_sources = {
        "m6j": {
            "execution_id": upstream_m6j,
            "key": f"evidence/dev_full/run_control/{upstream_m6j}/m6j_execution_summary.json",
            "expected_next_gate": "M7_READY",
            "phase": "M6.J",
        },
        "m7j": {
            "execution_id": upstream_m7j,
            "key": f"evidence/dev_full/run_control/{upstream_m7j}/m7_execution_summary.json",
            "expected_next_gate": "M8_READY",
            "phase": "M7.J",
        },
        "m7k": {
            "execution_id": upstream_m7k,
            "key": f"evidence/dev_full/run_control/{upstream_m7k}/m7k_throughput_cert_execution_summary.json",
            "expected_next_gate": "M8_READY",
            "phase": "M7.K",
        },
    }

    anchor_payloads: dict[str, dict[str, Any]] = {}
    anchor_gate_checks: list[dict[str, Any]] = []
    certified_platform_run_id = ""
    certified_scenario_run_id = ""

    for name, src in anchor_sources.items():
        row = {
            "anchor": name,
            "phase": src["phase"],
            "execution_id": src["execution_id"],
            "summary_key": src["key"],
            "readable": False,
            "overall_pass": False,
            "expected_next_gate": src["expected_next_gate"],
            "actual_next_gate": "",
            "gate_ok": False,
            "run_scope_ok": False,
        }
        try:
            payload = s3_get_json(s3, evidence_bucket, src["key"])
            anchor_payloads[name] = payload
            row["readable"] = True
            row["overall_pass"] = bool(payload.get("overall_pass"))
            row["actual_next_gate"] = str(payload.get("next_gate", "")).strip()
            row["gate_ok"] = row["overall_pass"] and row["actual_next_gate"] == src["expected_next_gate"]
            if not row["gate_ok"]:
                blockers.append({"code": "M8-B7", "message": f"{src['phase']} anchor gate mismatch."})
            anchor_run = str(payload.get("platform_run_id", "")).strip()
            anchor_scenario = str(payload.get("scenario_run_id", "")).strip()
            if name == "m7j":
                certified_platform_run_id = anchor_run
                certified_scenario_run_id = anchor_scenario
            if name in {"m7j", "m7k"}:
                row["run_scope_ok"] = bool(anchor_run and anchor_scenario)
                if not row["run_scope_ok"]:
                    blockers.append({"code": "M8-B7", "message": f"{src['phase']} anchor missing run scope fields."})
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": src["key"], "error": type(exc).__name__})
            blockers.append({"code": "M8-B7", "message": f"{src['phase']} anchor summary unreadable."})
        anchor_gate_checks.append(row)

    run_scope_parity_checks = {
        "active_platform_run_id": active_platform_run_id,
        "active_scenario_run_id": active_scenario_run_id,
        "certified_platform_run_id": certified_platform_run_id,
        "certified_scenario_run_id": certified_scenario_run_id,
        "platform_run_id_match": bool(active_platform_run_id and certified_platform_run_id and active_platform_run_id == certified_platform_run_id),
        "scenario_run_id_match": bool(active_scenario_run_id and certified_scenario_run_id and active_scenario_run_id == certified_scenario_run_id),
    }
    if not run_scope_parity_checks["platform_run_id_match"] or not run_scope_parity_checks["scenario_run_id_match"]:
        blockers.append({"code": "M8-B7", "message": "Run-scope mismatch between M8 closure and certified M7 anchors."})

    object_store_bucket = required_handles["S3_OBJECT_STORE_BUCKET"]
    run_completed_key = f"{active_platform_run_id}/run_completed.json"
    run_report_key = f"{active_platform_run_id}/obs/run_report.json"
    reconciliation_key = f"{active_platform_run_id}/obs/reconciliation.json"

    closure_payloads: dict[str, dict[str, Any]] = {}
    closure_rows: list[dict[str, Any]] = []
    for key in [run_completed_key, run_report_key, reconciliation_key]:
        row = {
            "bucket": object_store_bucket,
            "key": key,
            "readable": False,
            "json_parse_ok": False,
            "run_scope_ok": False,
            "failure_reason": "",
        }
        try:
            payload = s3_get_json(s3, object_store_bucket, key)
            closure_payloads[key] = payload
            row["readable"] = True
            row["json_parse_ok"] = True
            row_id = str(payload.get("platform_run_id", "")).strip()
            row["run_scope_ok"] = (not row_id) or (row_id == active_platform_run_id)
            if not row["run_scope_ok"]:
                blockers.append({"code": "M8-B7", "message": f"Run-scope mismatch in closure artifact: {key}"})
        except (BotoCoreError, ClientError) as exc:
            row["failure_reason"] = f"s3_read_failed:{type(exc).__name__}"
            read_errors.append({"surface": f"s3://{object_store_bucket}/{key}", "error": type(exc).__name__})
            blockers.append({"code": "M8-B7", "message": f"Required closure artifact unreadable: {key}"})
        except (ValueError, json.JSONDecodeError):
            row["failure_reason"] = "json_parse_failed"
            blockers.append({"code": "M8-B7", "message": f"Required closure artifact parse failure: {key}"})
        closure_rows.append(row)

    reconciliation_checks = {
        "status_pass": False,
        "checks_all_true": False,
        "deltas_non_negative": False,
        "delta_identity_ok": False,
        "details": {},
    }
    if reconciliation_key in closure_payloads and run_report_key in closure_payloads:
        rec = closure_payloads[reconciliation_key]
        rr = closure_payloads[run_report_key]
        status = str(rec.get("status", "")).strip().upper()
        checks_map = rec.get("checks") if isinstance(rec.get("checks"), dict) else {}
        deltas = rec.get("deltas") if isinstance(rec.get("deltas"), dict) else {}
        ingress = rr.get("ingress") if isinstance(rr.get("ingress"), dict) else {}
        rtdl = rr.get("rtdl") if isinstance(rr.get("rtdl"), dict) else {}

        status_pass = status == "PASS"
        checks_all_true = bool(checks_map) and all(bool(v) for v in checks_map.values())

        delta_fields = ["sent_minus_received", "received_minus_admit", "decision_minus_outcome"]
        delta_details: dict[str, Any] = {}
        deltas_non_negative = True
        for name in delta_fields:
            ok, iv = safe_int(deltas.get(name))
            delta_details[name] = {"ok": ok and iv >= 0, "value": iv if ok else deltas.get(name)}
            if (not ok) or iv < 0:
                deltas_non_negative = False

        sent_ok, sent = safe_int(ingress.get("sent"))
        recv_ok, recv = safe_int(ingress.get("received"))
        admit_ok, admit = safe_int(ingress.get("admit"))
        dec_ok, dec = safe_int(rtdl.get("decision"))
        out_ok, out = safe_int(rtdl.get("outcome"))
        identity_ok = (
            sent_ok and recv_ok and admit_ok and dec_ok and out_ok
            and (sent - recv == int(delta_details["sent_minus_received"]["value"]))
            and (recv - admit == int(delta_details["received_minus_admit"]["value"]))
            and (dec - out == int(delta_details["decision_minus_outcome"]["value"]))
        )

        reconciliation_checks = {
            "status_pass": status_pass,
            "checks_all_true": checks_all_true,
            "deltas_non_negative": deltas_non_negative,
            "delta_identity_ok": identity_ok,
            "details": {
                "status": status,
                "checks": checks_map,
                "deltas": delta_details,
                "ingress": ingress,
                "rtdl": rtdl,
            },
        }

        if not status_pass:
            blockers.append({"code": "M8-B7", "message": "Reconciliation status is not PASS."})
        if not checks_all_true:
            blockers.append({"code": "M8-B7", "message": "Reconciliation checks map contains non-true values."})
        if not deltas_non_negative:
            blockers.append({"code": "M8-B7", "message": "Reconciliation deltas contain negative/non-integer values."})
        if not identity_ok:
            blockers.append({"code": "M8-B7", "message": "Reconciliation deltas do not match run_report arithmetic identities."})
    else:
        blockers.append({"code": "M8-B7", "message": "Unable to evaluate reconciliation non-regression checks."})

    non_reg_pattern = required_handles["SPINE_NON_REGRESSION_PACK_PATTERN"]
    non_reg_key = render_pattern(non_reg_pattern, active_platform_run_id) if non_reg_pattern and active_platform_run_id else ""

    blockers = dedupe(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.H_READY" if overall_pass else "HOLD_REMEDIATE"
    elapsed = round(time.time() - start, 3)

    non_regression_pack = {
        "captured_at_utc": now_utc(),
        "phase": "M8.G",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": active_platform_run_id,
        "scenario_run_id": active_scenario_run_id,
        "source_m8f_execution": upstream_m8f,
        "anchor_refs": {
            "m6j_execution_id": upstream_m6j,
            "m7j_execution_id": upstream_m7j,
            "m7k_execution_id": upstream_m7k,
        },
        "anchor_gate_checks": anchor_gate_checks,
        "run_scope_parity_checks": run_scope_parity_checks,
        "closure_artifact_checks": closure_rows,
        "reconciliation_non_regression_checks": reconciliation_checks,
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
    }

    snapshot = {
        "captured_at_utc": now_utc(),
        "phase": "M8.G",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": active_platform_run_id,
        "scenario_run_id": active_scenario_run_id,
        "source_m8f_summary_uri": f"s3://{evidence_bucket}/{m8f_key}",
        "anchor_refs": anchor_sources,
        "anchor_gate_checks": anchor_gate_checks,
        "run_scope_parity_checks": run_scope_parity_checks,
        "reconciliation_non_regression_checks": reconciliation_checks,
        "non_regression_pack_key": non_reg_key,
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
    }

    register = {
        "captured_at_utc": now_utc(),
        "phase": "M8.G",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": active_platform_run_id,
        "scenario_run_id": active_scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": now_utc(),
        "phase": "M8.G",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": active_platform_run_id,
        "scenario_run_id": active_scenario_run_id,
        "upstream_refs": {
            "m8f_execution_id": upstream_m8f,
            "m6j_execution_id": upstream_m6j,
            "m7j_execution_id": upstream_m7j,
            "m7k_execution_id": upstream_m7k,
        },
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
        "durable_artifacts": {
            "m8g_snapshot_key": f"evidence/dev_full/run_control/{execution_id}/m8g_non_regression_pack_snapshot.json",
            "m8g_blocker_register_key": f"evidence/dev_full/run_control/{execution_id}/m8g_blocker_register.json",
            "m8g_execution_summary_key": f"evidence/dev_full/run_control/{execution_id}/m8g_execution_summary.json",
            "non_regression_pack_key": non_reg_key,
        },
    }

    artifacts = {
        "m8g_non_regression_pack_snapshot.json": snapshot,
        "m8g_blocker_register.json": register,
        "m8g_execution_summary.json": summary,
        "non_regression_pack.json": non_regression_pack,
    }
    write_local(run_dir, artifacts)

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        target_key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, target_key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "key": target_key, "error": type(exc).__name__})

    if non_reg_key:
        try:
            s3_put_json(s3, evidence_bucket, non_reg_key, non_regression_pack)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": "non_regression_pack.json", "key": non_reg_key, "error": type(exc).__name__})

    if upload_errors:
        blockers.append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.G artifacts."})
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
        non_regression_pack["blockers"] = blockers
        non_regression_pack["overall_pass"] = False
        non_regression_pack["next_gate"] = next_gate
        artifacts = {
            "m8g_non_regression_pack_snapshot.json": snapshot,
            "m8g_blocker_register.json": register,
            "m8g_execution_summary.json": summary,
            "non_regression_pack.json": non_regression_pack,
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
                "non_regression_pack_uri": f"s3://{evidence_bucket}/{non_reg_key}" if non_reg_key else "",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
