#!/usr/bin/env python3
"""Managed M7.K entry/cert artifact builder.

This script is intended for GitHub Actions execution only.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


HANDLES_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_handles(path: Path) -> dict[str, Any]:
    rx = re.compile(r"^\* `([^`]+)\s*=\s*(.+)`$")
    out: dict[str, Any] = {}
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


def is_placeholder(value: Any) -> bool:
    s = str(value).strip().lower()
    return s in {"", "tbd", "todo", "none"} or "to_pin" in s or "placeholder" in s or s.startswith("<")


def s3_get_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    payload = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(payload)


def s3_put_json(s3: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3.head_object(Bucket=bucket, Key=key)


def write_local_artifacts(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        sig = (str(blocker.get("code", "")), str(blocker.get("message", "")))
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": sig[0], "message": sig[1]})
    return out


def month_start_utc(now_dt: datetime) -> str:
    return now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d")


def tomorrow_utc(now_dt: datetime) -> str:
    return (now_dt + timedelta(days=1)).strftime("%Y-%m-%d")


def fetch_aws_mtd_cost(ce: Any) -> dict[str, Any]:
    now_dt = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "captured_at_utc": now_dt.isoformat().replace("+00:00", "Z"),
        "ok": False,
        "amount": None,
        "currency": "USD",
        "error": None,
    }
    try:
        payload = ce.get_cost_and_usage(
            TimePeriod={"Start": month_start_utc(now_dt), "End": tomorrow_utc(now_dt)},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        rows = payload.get("ResultsByTime", [])
        if rows:
            total = rows[0].get("Total", {}).get("UnblendedCost", {})
            amount = str(total.get("Amount", "")).strip()
            currency = str(total.get("Unit", "USD")).strip() or "USD"
            if amount:
                result["amount"] = Decimal(amount)
                result["currency"] = currency
                result["ok"] = True
            else:
                result["error"] = "ce_amount_missing"
        else:
            result["error"] = "ce_results_empty"
    except Exception as exc:
        result["error"] = f"ce_get_cost_and_usage_failed:{type(exc).__name__}"
    return result


def as_decimal(value: Any, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return default


def build_cost_artifacts(
    *,
    handles: dict[str, Any],
    mode: str,
    execution_id: str,
    platform_run_id: str,
    scenario_run_id: str,
    phase_start_utc: str,
    phase_end_utc: str,
    pre_cost: dict[str, Any],
    post_cost: dict[str, Any],
    artifacts_emitted: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    currency = str(handles.get("BUDGET_CURRENCY", "USD")).strip() or "USD"
    monthly_limit = as_decimal(handles.get("DEV_FULL_MONTHLY_BUDGET_LIMIT_USD", "0"), Decimal("0"))
    alert_1 = as_decimal(handles.get("DEV_FULL_BUDGET_ALERT_1_USD", "0"), Decimal("0"))
    alert_2 = as_decimal(handles.get("DEV_FULL_BUDGET_ALERT_2_USD", "0"), Decimal("0"))
    alert_3 = as_decimal(handles.get("DEV_FULL_BUDGET_ALERT_3_USD", "0"), Decimal("0"))
    aws_cost_capture_enabled = bool(handles.get("AWS_COST_CAPTURE_ENABLED", True))
    databricks_cost_capture_enabled = bool(handles.get("DATABRICKS_COST_CAPTURE_ENABLED", False))
    cost_capture_scope = str(handles.get("COST_CAPTURE_SCOPE", "aws_only_pre_m11_databricks_cost_deferred")).strip()
    phase_name = "M7.K.A" if mode == "entry" else "M7.K"

    pre_amount = pre_cost.get("amount")
    post_amount = post_cost.get("amount")
    delta_amount = None
    if isinstance(pre_amount, Decimal) and isinstance(post_amount, Decimal):
        delta_amount = post_amount - pre_amount
        currency = str(post_cost.get("currency", currency)).strip() or currency

    capture_errors: list[str] = []
    if pre_cost.get("error"):
        capture_errors.append(f"pre:{pre_cost['error']}")
    if post_cost.get("error"):
        capture_errors.append(f"post:{post_cost['error']}")

    budget_envelope = {
        "phase": phase_name,
        "phase_id": "M7",
        "phase_execution_id": execution_id,
        "captured_at_utc": phase_end_utc,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "budget_currency": currency,
        "monthly_limit_amount": str(monthly_limit),
        "alert_1_amount": str(alert_1),
        "alert_2_amount": str(alert_2),
        "alert_3_amount": str(alert_3),
        "cost_capture_scope": cost_capture_scope,
        "aws_cost_capture_enabled": aws_cost_capture_enabled,
        "databricks_cost_capture_enabled": databricks_cost_capture_enabled,
        "phase_window": {
            "start_utc": phase_start_utc,
            "end_utc": phase_end_utc,
        },
        "aws_mtd_pre_amount": str(pre_amount) if isinstance(pre_amount, Decimal) else None,
        "aws_mtd_post_amount": str(post_amount) if isinstance(post_amount, Decimal) else None,
        "aws_mtd_delta_amount": str(delta_amount) if isinstance(delta_amount, Decimal) else None,
        "capture_errors": capture_errors,
    }

    phase_cost_outcome_receipt = {
        "phase_id": "M7",
        "phase_execution_id": execution_id,
        "phase": phase_name,
        "window_start_utc": phase_start_utc,
        "window_end_utc": phase_end_utc,
        "spend_amount_estimated": str(delta_amount) if isinstance(delta_amount, Decimal) else None,
        "spend_currency": currency,
        "aws_mtd_pre_amount": str(pre_amount) if isinstance(pre_amount, Decimal) else None,
        "aws_mtd_post_amount": str(post_amount) if isinstance(post_amount, Decimal) else None,
        "artifacts_emitted": artifacts_emitted,
        "decision_or_risk_retired": (
            "M7.K throughput cert entry gate validated."
            if mode == "entry"
            else "M7.K throughput certification verdict emitted from bounded non-waived cert run."
        ),
        "source_components": {
            "aws_cost_capture_enabled": aws_cost_capture_enabled,
            "aws_ce_pre_capture_ok": bool(pre_cost.get("ok")),
            "aws_ce_post_capture_ok": bool(post_cost.get("ok")),
            "aws_ce_pre_error": pre_cost.get("error"),
            "aws_ce_post_error": post_cost.get("error"),
            "databricks_cost_capture_enabled": databricks_cost_capture_enabled,
            "databricks_capture_mode": "DEFERRED",
            "capture_scope": cost_capture_scope,
        },
        "note": "Per-run spend estimate is MTD post minus MTD pre and may lag due AWS billing latency.",
    }
    return budget_envelope, phase_cost_outcome_receipt


def scan_recent_admissions(ddb: Any, table_name: str, platform_run_id: str, window_minutes: int) -> dict[str, Any]:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    min_epoch = now_epoch - max(1, window_minutes) * 60
    params: dict[str, Any] = {
        "TableName": table_name,
        "FilterExpression": "#pr = :rid AND attribute_exists(#ae) AND #ae >= :min_epoch",
        "ProjectionExpression": "#ae",
        "ExpressionAttributeNames": {"#pr": "platform_run_id", "#ae": "admitted_at_epoch"},
        "ExpressionAttributeValues": {
            ":rid": {"S": platform_run_id},
            ":min_epoch": {"N": str(min_epoch)},
        },
    }
    epochs: list[int] = []
    while True:
        page = ddb.scan(**params)
        for item in page.get("Items", []):
            node = item.get("admitted_at_epoch", {})
            raw = node.get("N")
            if raw is None:
                continue
            try:
                epochs.append(int(raw))
            except ValueError:
                continue
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            break
        params["ExclusiveStartKey"] = last_key
    if not epochs:
        return {
            "source": "ddb_recent_window",
            "window_minutes": window_minutes,
            "window_min_epoch": min_epoch,
            "window_max_epoch": now_epoch,
            "count": 0,
            "first_admitted_epoch": None,
            "latest_admitted_epoch": None,
            "observed_window_seconds": max(1, window_minutes * 60),
        }
    first = min(epochs)
    latest = max(epochs)
    return {
        "source": "ddb_recent_window",
        "window_minutes": window_minutes,
        "window_min_epoch": min_epoch,
        "window_max_epoch": now_epoch,
        "count": len(epochs),
        "first_admitted_epoch": first,
        "latest_admitted_epoch": latest,
        "observed_window_seconds": max(1, latest - first),
    }


def entry_mode(env: dict[str, str], handles: dict[str, Any], s3: Any, ddb: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_id = env["PLATFORM_RUN_ID"]
    scenario_id = env["SCENARIO_RUN_ID"]
    upstream = env["UPSTREAM_M7J_EXECUTION"]
    bucket = env["EVIDENCE_BUCKET"]
    execution_id = env["M7K_EXECUTION_ID"]

    blockers: list[dict[str, str]] = []
    required = [
        "THROUGHPUT_CERT_REQUIRED",
        "THROUGHPUT_CERT_ALLOW_WAIVER",
        "THROUGHPUT_CERT_MIN_SAMPLE_EVENTS",
        "THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR",
        "THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND",
        "THROUGHPUT_CERT_WINDOW_MINUTES",
        "THROUGHPUT_CERT_MAX_ERROR_RATE_PCT",
        "THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT",
        "THROUGHPUT_CERT_EVIDENCE_PATH_PATTERN",
        "THROUGHPUT_CERT_RAMP_PROFILE",
        "RECEIPT_SUMMARY_PATH_PATTERN",
        "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
        "QUARANTINE_SUMMARY_PATH_PATTERN",
        "FP_BUS_CONTROL_V1",
        "DDB_IG_IDEMPOTENCY_TABLE",
        "IG_EDGE_MODE",
        "P7_OFFSET_PROOF_MODE_BY_IG_EDGE",
    ]
    missing = [k for k in required if k not in handles]
    placeholders = [k for k in required if k in handles and is_placeholder(handles[k])]
    if missing or placeholders:
        blockers.append({"code": "M7-B18", "message": f"Missing/placeholder handles (missing={missing}, placeholders={placeholders})."})

    try:
        cert_required = bool(handles["THROUGHPUT_CERT_REQUIRED"])
        allow_waiver = bool(handles["THROUGHPUT_CERT_ALLOW_WAIVER"])
        target_hour = int(handles["THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR"])
        target_sec = int(handles["THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND"])
        ramp = [int(x.strip()) for x in str(handles["THROUGHPUT_CERT_RAMP_PROFILE"]).split("|") if x.strip()]
        if not cert_required:
            blockers.append({"code": "M7-B18", "message": "THROUGHPUT_CERT_REQUIRED must be true."})
        if allow_waiver:
            blockers.append({"code": "M7-B18", "message": "THROUGHPUT_CERT_ALLOW_WAIVER must be false."})
        if abs(target_hour - target_sec * 3600) > max(1000, int(target_sec * 0.05)):
            blockers.append({"code": "M7-B18", "message": "target/hour and target/sec pins are inconsistent."})
        if not ramp or ramp != sorted(ramp):
            blockers.append({"code": "M7-B18", "message": "THROUGHPUT_CERT_RAMP_PROFILE must be monotonic."})
    except Exception:
        blockers.append({"code": "M7-B18", "message": "Throughput pins are unreadable."})

    try:
        upstream_summary = s3_get_json(s3, bucket, f"evidence/dev_full/run_control/{upstream}/m7_execution_summary.json")
        if not bool(upstream_summary.get("overall_pass")):
            blockers.append({"code": "M7-B18", "message": "Upstream M7.J overall_pass=false."})
        if str(upstream_summary.get("verdict", "")).strip() != "ADVANCE_TO_M8":
            blockers.append({"code": "M7-B18", "message": "Upstream M7.J verdict is not ADVANCE_TO_M8."})
        if str(upstream_summary.get("next_gate", "")).strip() != "M8_READY":
            blockers.append({"code": "M7-B18", "message": "Upstream M7.J next_gate is not M8_READY."})
        if str(upstream_summary.get("platform_run_id", "")).strip() != run_id:
            blockers.append({"code": "M7-B18", "message": "platform_run_id mismatch vs upstream."})
        if str(upstream_summary.get("scenario_run_id", "")).strip() != scenario_id:
            blockers.append({"code": "M7-B18", "message": "scenario_run_id mismatch vs upstream."})
    except Exception:
        blockers.append({"code": "M7-B18", "message": "Upstream M7.J summary unreadable."})

    sentinel = {}
    for hk in ["RECEIPT_SUMMARY_PATH_PATTERN", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", "QUARANTINE_SUMMARY_PATH_PATTERN"]:
        key = str(handles.get(hk, "")).replace("{platform_run_id}", run_id)
        try:
            payload = s3_get_json(s3, bucket, key)
            sentinel[hk] = {"s3_key": key, "readable": True, "phase": payload.get("phase"), "execution_id": payload.get("execution_id")}
        except Exception:
            sentinel[hk] = {"s3_key": key, "readable": False}
            blockers.append({"code": "M7-B19", "message": f"Sentinel surface unreadable for {hk}."})

    ddb_status: dict[str, Any] = {"table": handles.get("DDB_IG_IDEMPOTENCY_TABLE"), "active": False}
    try:
        desc = ddb.describe_table(TableName=str(ddb_status["table"]))
        ddb_status["status"] = str(desc["Table"].get("TableStatus", "UNKNOWN"))
        ddb_status["active"] = ddb_status["status"] == "ACTIVE"
        if not ddb_status["active"]:
            blockers.append({"code": "M7-B19", "message": "DDB_IG_IDEMPOTENCY_TABLE is not ACTIVE."})
    except Exception:
        blockers.append({"code": "M7-B19", "message": "DDB_IG_IDEMPOTENCY_TABLE unreadable."})

    blockers = dedupe_blockers(blockers)
    ok = len(blockers) == 0
    captured = now_utc()
    snapshot = {
        "captured_at_utc": captured,
        "phase": "M7.K.A",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "overall_pass": ok,
        "verdict": "ENTRY_READY" if ok else "HOLD_REMEDIATE",
        "next_gate": "M7.K.B_READY" if ok else "HOLD_REMEDIATE",
        "required_handle_count": len(required),
        "resolved_handle_count": len(required) - len(missing),
        "missing_handles": missing,
        "placeholder_handles": placeholders,
        "control_ingress_sentinel": sentinel,
        "ddb_ig_table_status": ddb_status,
    }
    register = {
        "captured_at_utc": captured,
        "phase": "M7.K.A",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "captured_at_utc": captured,
        "phase": "M7.K.A",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "overall_pass": ok,
        "blocker_count": len(blockers),
        "verdict": "ENTRY_READY" if ok else "HOLD_REMEDIATE",
        "next_gate": "M7.K.B_READY" if ok else "HOLD_REMEDIATE",
    }
    return snapshot, register, summary


def cert_mode(env: dict[str, str], handles: dict[str, Any], s3: Any, ddb: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_id = env["PLATFORM_RUN_ID"]
    scenario_id = env["SCENARIO_RUN_ID"]
    upstream = env["UPSTREAM_M7J_EXECUTION"]
    upstream_entry = env["UPSTREAM_M7K_ENTRY_EXECUTION"]
    bucket = env["EVIDENCE_BUCKET"]
    execution_id = env["M7K_EXECUTION_ID"]

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    captured = now_utc()

    try:
        m7 = s3_get_json(s3, bucket, f"evidence/dev_full/run_control/{upstream}/m7_execution_summary.json")
        if not bool(m7.get("overall_pass")) or str(m7.get("verdict", "")).strip() != "ADVANCE_TO_M8":
            blockers.append({"code": "M7-B18", "message": "Upstream M7.J posture invalid."})
    except Exception:
        blockers.append({"code": "M7-B18", "message": "Upstream M7.J summary unreadable."})
        m7 = {}
    try:
        entry = s3_get_json(s3, bucket, f"evidence/dev_full/run_control/{upstream_entry}/m7k_entry_execution_summary.json")
        if not bool(entry.get("overall_pass")):
            blockers.append({"code": "M7-B18", "message": "Upstream M7.K.A posture invalid."})
    except Exception:
        blockers.append({"code": "M7-B18", "message": "Upstream M7.K.A summary unreadable."})

    sentinel_payloads: dict[str, dict[str, Any]] = {}
    for hk in ["RECEIPT_SUMMARY_PATH_PATTERN", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", "QUARANTINE_SUMMARY_PATH_PATTERN"]:
        key = str(handles.get(hk, "")).replace("{platform_run_id}", run_id)
        try:
            sentinel_payloads[hk] = {"s3_key": key, "readable": True, "payload": s3_get_json(s3, bucket, key)}
        except Exception as exc:
            sentinel_payloads[hk] = {"s3_key": key, "readable": False}
            blockers.append({"code": "M7-B19", "message": f"Sentinel unreadable for {hk}."})
            read_errors.append({"surface": hk, "error": type(exc).__name__})

    receipt = sentinel_payloads.get("RECEIPT_SUMMARY_PATH_PATTERN", {}).get("payload", {})
    offsets = sentinel_payloads.get("KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", {}).get("payload", {})
    quarantine = sentinel_payloads.get("QUARANTINE_SUMMARY_PATH_PATTERN", {}).get("payload", {})

    admit = int(((receipt.get("counts_by_decision") or {}).get("ADMIT") or 0))
    total = int(receipt.get("total_receipts") or admit or 0)
    dup = int(((receipt.get("counts_by_decision") or {}).get("DUPLICATE") or 0))
    unk = int(((receipt.get("counts_by_decision") or {}).get("UNKNOWN") or 0))
    q_count = int(quarantine.get("quarantine_count") or 0)
    proxy = offsets.get("admission_proxy") or {}
    first = proxy.get("first_admitted_epoch")
    last = proxy.get("latest_admitted_epoch")
    if first is not None and last is not None and int(last) > int(first):
        window_seconds = int(last) - int(first)
    else:
        window_seconds = max(1, int(handles.get("THROUGHPUT_CERT_WINDOW_MINUTES", 60)) * 60)

    window_minutes = int(handles.get("THROUGHPUT_CERT_WINDOW_MINUTES", 60))
    min_sample = int(handles.get("THROUGHPUT_CERT_MIN_SAMPLE_EVENTS", 0))
    target_eps = Decimal(str(int(handles.get("THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND", 0))))
    allow_waiver = bool(handles.get("THROUGHPUT_CERT_ALLOW_WAIVER", True))
    max_error = Decimal(str(handles.get("THROUGHPUT_CERT_MAX_ERROR_RATE_PCT", 0)))
    max_retry = Decimal(str(handles.get("THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT", 0)))
    ramp = [int(x.strip()) for x in str(handles.get("THROUGHPUT_CERT_RAMP_PROFILE", "")).split("|") if x.strip()]

    sample_source = "receipt_summary"
    try:
        recent = scan_recent_admissions(ddb, str(handles.get("DDB_IG_IDEMPOTENCY_TABLE", "")), run_id, window_minutes)
        if int(recent.get("count", 0)) > 0:
            sample_source = "ddb_recent_window"
            total = int(recent["count"])
            admit = int(recent["count"])
            first = recent.get("first_admitted_epoch")
            last = recent.get("latest_admitted_epoch")
            window_seconds = int(recent["observed_window_seconds"])
    except Exception as exc:
        read_errors.append({"surface": "ddb_recent_window", "error": type(exc).__name__})
    observed_eps = Decimal(str(admit)) / Decimal(str(max(1, window_seconds)))
    sample_ok = total >= min_sample
    throughput_ok = observed_eps >= target_eps
    error_pct = (Decimal(str(unk + q_count)) / Decimal(str(max(1, total)))) * Decimal("100")
    retry_pct = (Decimal(str(dup)) / Decimal(str(max(1, total)))) * Decimal("100")
    error_ok = error_pct <= max_error
    retry_ok = retry_pct <= max_retry
    ramp_rows: list[dict[str, Any]] = []
    for stage in ramp:
        stage_eps = Decimal(str(stage)) / Decimal("3600")
        ramp_rows.append({
            "stage_target_events_per_hour": stage,
            "stage_target_events_per_second": float(stage_eps),
            "observed_events_per_second": float(observed_eps),
            "stage_pass": observed_eps >= stage_eps,
        })
    ramp_ok = all(row["stage_pass"] for row in ramp_rows) if ramp_rows else False

    component_modes: list[dict[str, Any]] = []
    refs = m7.get("upstream_refs") or {}
    rollup_map = {
        refs.get("p8e_execution_id"): "p8e_rtdl_gate_rollup_matrix.json",
        refs.get("p9e_execution_id"): "p9e_decision_chain_rollup_matrix.json",
        refs.get("p10e_execution_id"): "p10e_case_labels_rollup_matrix.json",
    }
    for rollup_exec, rollup_file in rollup_map.items():
        if not rollup_exec or not rollup_file:
            continue
        try:
            roll = s3_get_json(s3, bucket, f"evidence/dev_full/run_control/{rollup_exec}/{rollup_file}")
            for row in roll.get("upstream_rows", []):
                sk = str(row.get("summary_s3_key", ""))
                if not sk.endswith("_execution_summary.json"):
                    continue
                pk = sk.replace("_execution_summary.json", "_performance_snapshot.json")
                try:
                    perf = s3_get_json(s3, bucket, pk)
                    component_modes.append({
                        "execution_id": row.get("execution_id"),
                        "performance_snapshot_key": pk,
                        "throughput_gate_mode": perf.get("throughput_gate_mode"),
                        "sample_size": perf.get("sample_size_total_receipts", perf.get("sample_size")),
                    })
                except Exception as exc:
                    read_errors.append({"surface": pk, "error": type(exc).__name__})
        except Exception as exc:
            read_errors.append({"surface": f"rollup:{rollup_exec}", "error": type(exc).__name__})

    provisional = [c for c in component_modes if str(c.get("throughput_gate_mode", "")).strip() == "waived_low_sample"]

    if allow_waiver:
        blockers.append({"code": "M7-B18", "message": "THROUGHPUT_CERT_ALLOW_WAIVER must be false."})
    # Component provisional snapshots are retained for context only. M7.K gates on
    # fresh non-waived certification metrics from current run-scope sentinel data.
    if not sample_ok:
        blockers.append({"code": "M7-B18", "message": f"Sample-size gate failed ({total} < {min_sample})."})
    if not throughput_ok:
        blockers.append({"code": "M7-B18", "message": f"Throughput gate failed ({str(observed_eps)} eps < {str(target_eps)} eps)."})
    if not ramp_ok:
        blockers.append({"code": "M7-B18", "message": "Ramp profile stage gates failed."})
    if not error_ok:
        blockers.append({"code": "M7-B18", "message": "Error-rate gate failed."})
    if not retry_ok:
        blockers.append({"code": "M7-B18", "message": "Retry-ratio gate failed."})

    ddb_status = "UNREADABLE"
    try:
        d = ddb.describe_table(TableName=str(handles.get("DDB_IG_IDEMPOTENCY_TABLE", "")))
        ddb_status = str(d["Table"].get("TableStatus", "UNKNOWN"))
        if ddb_status != "ACTIVE":
            blockers.append({"code": "M7-B19", "message": "DDB_IG_IDEMPOTENCY_TABLE is not ACTIVE."})
    except Exception:
        blockers.append({"code": "M7-B19", "message": "DDB_IG_IDEMPOTENCY_TABLE unreadable."})

    blockers = dedupe_blockers(blockers)
    ok = len(blockers) == 0
    verdict = "THROUGHPUT_CERTIFIED" if ok else "HOLD_REMEDIATE"
    next_gate = "M8_READY" if ok else "HOLD_REMEDIATE"

    plan = {
        "captured_at_utc": captured,
        "phase": "M7.K",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "upstream_m7j_execution": upstream,
        "upstream_m7k_entry_execution": upstream_entry,
        "pins": {
            "THROUGHPUT_CERT_REQUIRED": bool(handles.get("THROUGHPUT_CERT_REQUIRED", False)),
            "THROUGHPUT_CERT_ALLOW_WAIVER": allow_waiver,
            "THROUGHPUT_CERT_MIN_SAMPLE_EVENTS": min_sample,
            "THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR": int(handles.get("THROUGHPUT_CERT_TARGET_EVENTS_PER_HOUR", 0)),
            "THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND": int(handles.get("THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND", 0)),
            "THROUGHPUT_CERT_WINDOW_MINUTES": int(handles.get("THROUGHPUT_CERT_WINDOW_MINUTES", 60)),
            "THROUGHPUT_CERT_MAX_ERROR_RATE_PCT": str(max_error),
            "THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT": str(max_retry),
            "THROUGHPUT_CERT_RAMP_PROFILE": ramp,
        },
    }
    sentinel_snapshot = {
        "captured_at_utc": captured,
        "phase": "M7.K",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "receipt_summary": {"total_receipts": total, "admit_count": admit, "duplicate_count": dup, "unknown_count": unk},
        "sample_source": sample_source,
        "offset_window": {"first_admitted_epoch": first, "latest_admitted_epoch": last, "observed_window_seconds": window_seconds},
        "quarantine_count": q_count,
        "ddb_ig_table_status": ddb_status,
        "surfaces": {k: {"s3_key": v.get("s3_key"), "readable": v.get("readable")} for k, v in sentinel_payloads.items()},
    }
    cert_snapshot = {
        "captured_at_utc": captured,
        "phase": "M7.K",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "sample_size_events": total,
        "sample_size_gate_min": min_sample,
        "sample_size_gate_pass": sample_ok,
        "observed_events_per_second": str(observed_eps),
        "target_events_per_second": str(target_eps),
        "throughput_gate_pass": throughput_ok,
        "error_rate_pct_observed": str(error_pct),
        "error_rate_pct_max": str(max_error),
        "error_gate_pass": error_ok,
        "retry_ratio_pct_observed": str(retry_pct),
        "retry_ratio_pct_max": str(max_retry),
        "retry_gate_pass": retry_ok,
        "ramp_rows": ramp_rows,
        "ramp_gate_pass": ramp_ok,
        "component_modes": component_modes,
        "provisional_component_count": len(provisional),
        "overall_pass": ok,
    }
    blocker_register = {
        "captured_at_utc": captured,
        "phase": "M7.K",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
    }
    verdict_obj = {
        "captured_at_utc": captured,
        "phase": "M7.K",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "overall_pass": ok,
        "verdict": verdict,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
    }
    summary = {
        "captured_at_utc": captured,
        "phase": "M7.K",
        "execution_id": execution_id,
        "platform_run_id": run_id,
        "scenario_run_id": scenario_id,
        "overall_pass": ok,
        "verdict": verdict,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "blockers": blockers,
    }
    return plan, sentinel_snapshot, cert_snapshot, blocker_register, verdict_obj, summary


def main() -> int:
    env = dict(os.environ)
    mode = env.get("M7K_MODE", "").strip().lower()
    execution_id = env.get("M7K_EXECUTION_ID", "").strip()
    run_dir = Path(env.get("M7K_RUN_DIR", "").strip())
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    if mode not in {"entry", "cert"}:
        raise SystemExit("M7K_MODE must be 'entry' or 'cert'.")
    if not execution_id or not str(run_dir):
        raise SystemExit("M7K execution metadata is missing.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")

    phase_start_utc = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3")
    ddb = boto3.client("dynamodb")
    ce = boto3.client("ce", region_name="us-east-1")
    prefix = f"evidence/dev_full/run_control/{execution_id}"
    pre_cost = fetch_aws_mtd_cost(ce)

    if mode == "entry":
        snapshot, register, summary = entry_mode(env, handles, s3, ddb)
        artifacts = {
            "m7k_entry_snapshot.json": snapshot,
            "m7k_entry_blocker_register.json": register,
            "m7k_entry_execution_summary.json": summary,
        }
    else:
        if not env.get("UPSTREAM_M7K_ENTRY_EXECUTION", "").strip():
            raise SystemExit("UPSTREAM_M7K_ENTRY_EXECUTION is required when M7K_MODE=cert.")
        plan, sentinel, cert_snapshot, register, verdict, summary = cert_mode(env, handles, s3, ddb)
        artifacts = {
            "m7k_throughput_cert_plan.json": plan,
            "m7k_control_ingress_sentinel_snapshot.json": sentinel,
            "m7k_throughput_cert_snapshot.json": cert_snapshot,
            "m7k_throughput_cert_blocker_register.json": register,
            "m7k_throughput_cert_verdict.json": verdict,
            "m7k_throughput_cert_execution_summary.json": summary,
        }

    phase_end_utc = now_utc()
    post_cost = fetch_aws_mtd_cost(ce)
    budget_envelope, phase_cost_outcome_receipt = build_cost_artifacts(
        handles=handles,
        mode=mode,
        execution_id=execution_id,
        platform_run_id=env["PLATFORM_RUN_ID"],
        scenario_run_id=env["SCENARIO_RUN_ID"],
        phase_start_utc=phase_start_utc,
        phase_end_utc=phase_end_utc,
        pre_cost=pre_cost,
        post_cost=post_cost,
        artifacts_emitted=list(artifacts.keys()) + ["m7k_phase_budget_envelope.json", "m7k_phase_cost_outcome_receipt.json"],
    )
    artifacts["m7k_phase_budget_envelope.json"] = budget_envelope
    artifacts["m7k_phase_cost_outcome_receipt.json"] = phase_cost_outcome_receipt

    write_local_artifacts(run_dir, artifacts)
    upload_errors = []
    for name, payload in artifacts.items():
        try:
            s3_put_json(s3, bucket, f"{prefix}/{name}", payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "error": type(exc).__name__})

    if upload_errors:
        if mode == "entry":
            register = artifacts["m7k_entry_blocker_register.json"]
            summary = artifacts["m7k_entry_execution_summary.json"]
            register["blockers"].append({"code": "M7-B18", "message": "Failed to publish/readback M7.K.A artifacts."})
            register["blocker_count"] = len(register["blockers"])
            register["upload_errors"] = upload_errors
            summary["overall_pass"] = False
            summary["verdict"] = "HOLD_REMEDIATE"
            summary["next_gate"] = "HOLD_REMEDIATE"
            summary["blocker_count"] = register["blocker_count"]
        else:
            register = artifacts["m7k_throughput_cert_blocker_register.json"]
            summary = artifacts["m7k_throughput_cert_execution_summary.json"]
            verdict = artifacts["m7k_throughput_cert_verdict.json"]
            register["blockers"].append({"code": "M7-B18", "message": "Failed to publish/readback M7.K artifacts."})
            register["blocker_count"] = len(register["blockers"])
            register["upload_errors"] = upload_errors
            summary["overall_pass"] = False
            summary["verdict"] = "HOLD_REMEDIATE"
            summary["next_gate"] = "HOLD_REMEDIATE"
            summary["blocker_count"] = register["blocker_count"]
            summary["blockers"] = register["blockers"]
            verdict["overall_pass"] = False
            verdict["verdict"] = "HOLD_REMEDIATE"
            verdict["next_gate"] = "HOLD_REMEDIATE"
            verdict["blocker_count"] = register["blocker_count"]
        write_local_artifacts(run_dir, artifacts)

    out = {
        "mode": mode,
        "execution_id": execution_id,
        "overall_pass": artifacts["m7k_entry_execution_summary.json"]["overall_pass"] if mode == "entry" else artifacts["m7k_throughput_cert_execution_summary.json"]["overall_pass"],
        "blocker_count": artifacts["m7k_entry_execution_summary.json"]["blocker_count"] if mode == "entry" else artifacts["m7k_throughput_cert_execution_summary.json"]["blocker_count"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{bucket}/{prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
