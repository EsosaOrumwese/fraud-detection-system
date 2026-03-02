#!/usr/bin/env python3
"""Managed M8.F closure-bundle completeness validator."""

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
            val: Any = raw[1:-1]
        elif raw.lower() == "true":
            val = True
        elif raw.lower() == "false":
            val = False
        else:
            try:
                val = int(raw) if "." not in raw else float(raw)
            except ValueError:
                val = raw
        out[key] = val
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
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(body)


def s3_put_json(s3: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3.head_object(Bucket=bucket, Key=key)


def write_local(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def int_non_negative(v: Any) -> tuple[bool, int]:
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return False, 0
    return (iv >= 0), iv


def main() -> int:
    start = time.time()
    env = dict(os.environ)
    execution_id = env.get("M8F_EXECUTION_ID", "").strip()
    run_dir = Path(env.get("M8F_RUN_DIR", "").strip())
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8e = env.get("UPSTREAM_M8E_EXECUTION", "").strip()
    region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M8F_EXECUTION_ID is required.")
    if not str(run_dir):
        raise SystemExit("M8F_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8e:
        raise SystemExit("UPSTREAM_M8E_EXECUTION is required.")

    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    # 1) Entry gate from M8.E
    upstream_key = f"evidence/dev_full/run_control/{upstream_m8e}/m8e_execution_summary.json"
    upstream: dict[str, Any] | None = None
    try:
        upstream = s3_get_json(s3, evidence_bucket, upstream_key)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
        read_errors.append({"surface": upstream_key, "error": type(exc).__name__})
        blockers.append({"code": "M8-B6", "message": "Upstream M8.E summary unreadable."})

    platform_run_id = env.get("PLATFORM_RUN_ID", "").strip()
    scenario_run_id = env.get("SCENARIO_RUN_ID", "").strip()
    entry_gate_ok = False
    if isinstance(upstream, dict):
        entry_gate_ok = bool(upstream.get("overall_pass")) and str(upstream.get("next_gate", "")).strip() == "M8.F_READY"
        if not entry_gate_ok:
            blockers.append({"code": "M8-B6", "message": "M8.E gate is not M8.F_READY."})
        platform_run_id = platform_run_id or str(upstream.get("platform_run_id", "")).strip()
        scenario_run_id = scenario_run_id or str(upstream.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B6", "message": "Run scope unresolved for M8.F."})

    # 2) Required handles
    object_store_bucket = str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip()
    handle_checks = {
        "S3_OBJECT_STORE_BUCKET": object_store_bucket,
        "S3_EVIDENCE_BUCKET": str(handles.get("S3_EVIDENCE_BUCKET", "")).strip(),
    }
    bad_handles = [k for k, v in handle_checks.items() if is_placeholder(v)]
    if bad_handles:
        blockers.append({"code": "M8-B6", "message": f"Required handles unresolved: {','.join(sorted(bad_handles))}."})
    if handle_checks["S3_EVIDENCE_BUCKET"] and handle_checks["S3_EVIDENCE_BUCKET"] != evidence_bucket:
        blockers.append({"code": "M8-B6", "message": "EVIDENCE_BUCKET does not match handle registry S3_EVIDENCE_BUCKET."})

    required_keys = [
        f"{platform_run_id}/run_completed.json",
        f"{platform_run_id}/obs/platform_run_report.json",
        f"{platform_run_id}/obs/run_report.json",
        f"{platform_run_id}/obs/reconciliation.json",
        f"{platform_run_id}/obs/replay_anchors.json",
        f"{platform_run_id}/obs/environment_conformance.json",
        f"{platform_run_id}/obs/anomaly_summary.json",
    ]

    payloads: dict[str, dict[str, Any]] = {}
    artifact_checks: list[dict[str, Any]] = []

    # 3) Existence + parse + run-scope checks
    if not blockers:
        for key in required_keys:
            row: dict[str, Any] = {
                "bucket": object_store_bucket,
                "key": key,
                "exists": False,
                "readable": False,
                "json_parse_ok": False,
                "run_scope_ok": False,
                "failure_reason": "",
            }
            try:
                s3.head_object(Bucket=object_store_bucket, Key=key)
                row["exists"] = True
                body = s3.get_object(Bucket=object_store_bucket, Key=key)["Body"].read().decode("utf-8")
                row["readable"] = True
                obj = json.loads(body)
                if not isinstance(obj, dict):
                    raise ValueError("json_not_object")
                row["json_parse_ok"] = True
                payloads[key] = obj
                obj_run_id = str(obj.get("platform_run_id", "")).strip()
                row["run_scope_ok"] = (not obj_run_id) or (obj_run_id == platform_run_id)
                if not row["run_scope_ok"]:
                    row["failure_reason"] = f"run_scope_mismatch:{obj_run_id}"
                    blockers.append({"code": "M8-B6", "message": f"Run-scope mismatch in closure artifact: {key}"})
            except (BotoCoreError, ClientError) as exc:
                row["failure_reason"] = f"s3_read_failed:{type(exc).__name__}"
                read_errors.append({"surface": f"s3://{object_store_bucket}/{key}", "error": type(exc).__name__})
                blockers.append({"code": "M8-B6", "message": f"Required closure artifact unreadable: {key}"})
            except (ValueError, json.JSONDecodeError):
                row["failure_reason"] = "json_parse_failed"
                blockers.append({"code": "M8-B6", "message": f"Required closure artifact parse failure: {key}"})
            artifact_checks.append(row)

    # 4) run_completed closure_refs coherence
    run_completed_key = f"{platform_run_id}/run_completed.json"
    run_completed_ref_checks: list[dict[str, Any]] = []
    if run_completed_key in payloads:
        rc = payloads[run_completed_key]
        closure_refs = rc.get("closure_refs") if isinstance(rc.get("closure_refs"), dict) else {}
        expected_refs = {
            "run_report_ref": f"{platform_run_id}/obs/run_report.json",
            "reconciliation_ref": f"{platform_run_id}/obs/reconciliation.json",
            "replay_anchors_ref": f"{platform_run_id}/obs/replay_anchors.json",
            "environment_conformance_ref": f"{platform_run_id}/obs/environment_conformance.json",
            "anomaly_summary_ref": f"{platform_run_id}/obs/anomaly_summary.json",
        }
        for ref_name, expected in expected_refs.items():
            actual = str(closure_refs.get(ref_name, "")).strip()
            ok = actual == expected
            run_completed_ref_checks.append({"ref": ref_name, "expected": expected, "actual": actual, "ok": ok})
            if not ok:
                blockers.append({"code": "M8-B6", "message": f"run_completed closure ref mismatch: {ref_name}"})
    else:
        blockers.append({"code": "M8-B6", "message": "run_completed.json unavailable for closure-ref checks."})

    # 5) Reconciliation coherence checks
    reconciliation_checks: dict[str, Any] = {
        "status_pass": False,
        "checks_all_true": False,
        "deltas_non_negative": False,
        "details": {},
    }
    reconciliation_key = f"{platform_run_id}/obs/reconciliation.json"
    if reconciliation_key in payloads:
        rec = payloads[reconciliation_key]
        status = str(rec.get("status", "")).strip().upper()
        checks_map = rec.get("checks") if isinstance(rec.get("checks"), dict) else {}
        deltas_map = rec.get("deltas") if isinstance(rec.get("deltas"), dict) else {}

        status_pass = status == "PASS"
        checks_all_true = bool(checks_map) and all(bool(v) for v in checks_map.values())

        delta_fields = ["sent_minus_received", "received_minus_admit", "decision_minus_outcome"]
        delta_results = {}
        deltas_non_negative = True
        for field in delta_fields:
            ok, iv = int_non_negative(deltas_map.get(field))
            delta_results[field] = {"ok": ok, "value": iv if ok else deltas_map.get(field)}
            if not ok:
                deltas_non_negative = False

        reconciliation_checks = {
            "status_pass": status_pass,
            "checks_all_true": checks_all_true,
            "deltas_non_negative": deltas_non_negative,
            "details": {
                "status": status,
                "checks": checks_map,
                "deltas": delta_results,
            },
        }

        if not status_pass:
            blockers.append({"code": "M8-B6", "message": "Reconciliation status is not PASS."})
        if not checks_all_true:
            blockers.append({"code": "M8-B6", "message": "Reconciliation checks map contains non-true values."})
        if not deltas_non_negative:
            blockers.append({"code": "M8-B6", "message": "Reconciliation deltas contain negative/non-integer values."})
    else:
        blockers.append({"code": "M8-B6", "message": "reconciliation.json unavailable for coherence checks."})

    # 6) Report coherence checks
    report_checks: dict[str, Any] = {
        "run_report_present": False,
        "platform_run_report_present": False,
        "run_report_sections_ok": False,
        "platform_run_report_sections_ok": False,
    }
    run_report_key = f"{platform_run_id}/obs/run_report.json"
    prr_key = f"{platform_run_id}/obs/platform_run_report.json"
    if run_report_key in payloads:
        rr = payloads[run_report_key]
        report_checks["run_report_present"] = True
        report_checks["run_report_sections_ok"] = isinstance(rr.get("ingress"), dict) and isinstance(rr.get("rtdl"), dict)
        if not report_checks["run_report_sections_ok"]:
            blockers.append({"code": "M8-B6", "message": "run_report.json missing required ingress/rtdl sections."})
    else:
        blockers.append({"code": "M8-B6", "message": "run_report.json unavailable."})

    if prr_key in payloads:
        prr = payloads[prr_key]
        report_checks["platform_run_report_present"] = True
        report_checks["platform_run_report_sections_ok"] = isinstance(prr.get("ingress"), dict) and isinstance(prr.get("rtdl"), dict)
        if not report_checks["platform_run_report_sections_ok"]:
            blockers.append({"code": "M8-B6", "message": "platform_run_report.json missing required ingress/rtdl sections."})
    else:
        blockers.append({"code": "M8-B6", "message": "platform_run_report.json unavailable."})

    blockers = dedupe(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.G_READY" if overall_pass else "HOLD_REMEDIATE"
    elapsed = round(time.time() - start, 3)

    snapshot = {
        "captured_at_utc": now_utc(),
        "phase": "M8.F",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "source_m8e_summary_uri": f"s3://{evidence_bucket}/{upstream_key}",
        "entry_gate_ok": entry_gate_ok,
        "bundle_targets": [{"bucket": object_store_bucket, "key": k} for k in required_keys],
        "artifact_checks": artifact_checks,
        "run_completed_ref_checks": run_completed_ref_checks,
        "reconciliation_checks": reconciliation_checks,
        "report_checks": report_checks,
        "read_errors": read_errors,
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
    }

    blocker_register = {
        "captured_at_utc": now_utc(),
        "phase": "M8.F",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
    }

    summary = {
        "captured_at_utc": now_utc(),
        "phase": "M8.F",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_refs": {"m8e_execution_id": upstream_m8e},
        "bundle_target_count": len(required_keys),
        "read_error_count": len(read_errors),
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
        "durable_artifacts": {
            "m8f_snapshot_key": f"evidence/dev_full/run_control/{execution_id}/m8f_closure_bundle_completeness_snapshot.json",
            "m8f_blocker_register_key": f"evidence/dev_full/run_control/{execution_id}/m8f_blocker_register.json",
            "m8f_execution_summary_key": f"evidence/dev_full/run_control/{execution_id}/m8f_execution_summary.json",
        },
    }

    artifacts = {
        "m8f_closure_bundle_completeness_snapshot.json": snapshot,
        "m8f_blocker_register.json": blocker_register,
        "m8f_execution_summary.json": summary,
    }
    write_local(run_dir, artifacts)

    for name, payload in artifacts.items():
        key = f"evidence/dev_full/run_control/{execution_id}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, key, payload)
        except (BotoCoreError, ClientError) as exc:
            upload_errors.append({"surface": key, "error": type(exc).__name__})

    if upload_errors:
        blockers.append({"code": "M8-B12", "message": "M8.F artifact publication/readback parity failed."})
        blockers = dedupe(blockers)
        overall_pass = len(blockers) == 0
        next_gate = "M8.G_READY" if overall_pass else "HOLD_REMEDIATE"
        snapshot["upload_errors"] = upload_errors
        snapshot["blockers"] = blockers
        snapshot["overall_pass"] = overall_pass
        snapshot["next_gate"] = next_gate
        blocker_register["upload_errors"] = upload_errors
        blocker_register["blocker_count"] = len(blockers)
        blocker_register["blockers"] = blockers
        blocker_register["overall_pass"] = overall_pass
        blocker_register["next_gate"] = next_gate
        summary["upload_errors"] = upload_errors
        summary["blocker_count"] = len(blockers)
        summary["blockers"] = blockers
        summary["overall_pass"] = overall_pass
        summary["next_gate"] = next_gate
        write_local(run_dir, artifacts)

    print(json.dumps({"overall_pass": overall_pass, "blocker_count": len(blockers), "next_gate": next_gate}, indent=2, ensure_ascii=True))
    return 0 if overall_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
