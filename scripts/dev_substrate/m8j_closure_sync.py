#!/usr/bin/env python3
"""Build and publish M8.J closure sync + cost-outcome artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _read_json_from_s3(s3_client: Any, *, bucket: str, key: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read().decode("utf-8")
        return json.loads(raw), None
    except (BotoCoreError, ClientError) as exc:
        return None, f"s3_read_failed:{type(exc).__name__}:{key}"
    except json.JSONDecodeError:
        return None, f"json_decode_failed:{key}"


def _put_json_and_head(
    s3_client: Any,
    *,
    bucket: str,
    key: str,
    payload: dict[str, Any],
) -> tuple[bool, str | None]:
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=(json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8"),
            ContentType="application/json",
        )
        s3_client.head_object(Bucket=bucket, Key=key)
        return True, None
    except (BotoCoreError, ClientError) as exc:
        return False, f"s3_put_or_head_failed:{type(exc).__name__}:{key}"


def _safe_decimal(text: str, *, field: str) -> Decimal:
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_decimal:{field}:{text}") from exc
    if value <= Decimal("0"):
        raise ValueError(f"non_positive_decimal:{field}:{text}")
    return value


def _parse_utc(text: str | None) -> datetime | None:
    if not text:
        return None
    normalized = str(text).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _month_start_utc(now: datetime) -> str:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date().isoformat()


def _tomorrow_utc(now: datetime) -> str:
    return (now.date() + timedelta(days=1)).isoformat()


def _dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "message": str(blocker.get("message", "")).strip()})
    return out


def _aws_mtd_cost(
    ce_client: Any,
    *,
    start_date: str,
    end_date: str,
) -> tuple[Decimal | None, str | None, str | None]:
    try:
        payload = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
    except (BotoCoreError, ClientError) as exc:
        return None, None, f"ce_get_cost_and_usage_failed:{type(exc).__name__}"
    groups = payload.get("ResultsByTime", [])
    if not groups:
        return None, None, "ce_results_empty"
    total = groups[0].get("Total", {}).get("UnblendedCost", {})
    amount_text = str(total.get("Amount", "")).strip()
    unit = str(total.get("Unit", "")).strip() or None
    if not amount_text:
        return None, unit, "ce_amount_missing"
    try:
        return Decimal(amount_text), unit, None
    except InvalidOperation:
        return None, unit, "ce_amount_invalid"


def _aws_daily_cost_series(
    ce_client: Any,
    *,
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]] | None, str | None, str | None]:
    try:
        payload = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )
    except (BotoCoreError, ClientError) as exc:
        return None, None, f"ce_get_daily_cost_failed:{type(exc).__name__}"
    rows: list[dict[str, Any]] = []
    unit: str | None = None
    for item in payload.get("ResultsByTime", []):
        period = item.get("TimePeriod", {}) if isinstance(item.get("TimePeriod"), dict) else {}
        start = str(period.get("Start", "")).strip()
        end = str(period.get("End", "")).strip()
        total = item.get("Total", {}) if isinstance(item.get("Total"), dict) else {}
        unblended = total.get("UnblendedCost", {}) if isinstance(total.get("UnblendedCost"), dict) else {}
        amount_text = str(unblended.get("Amount", "")).strip()
        row_unit = str(unblended.get("Unit", "")).strip()
        if row_unit:
            unit = row_unit
        if not start or not end or not amount_text:
            return None, unit, "ce_daily_row_invalid"
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            return None, unit, "ce_daily_amount_invalid"
        rows.append({"start_date": start, "end_date": end, "amount": amount})
    if not rows:
        return None, unit, "ce_daily_rows_empty"
    return rows, unit, None


def _window_prorated_cost(
    *,
    daily_rows: list[dict[str, Any]],
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> Decimal:
    total = Decimal("0")
    if window_end_utc <= window_start_utc:
        return total
    for row in daily_rows:
        day_start = _parse_utc(f"{row['start_date']}T00:00:00Z")
        day_end = _parse_utc(f"{row['end_date']}T00:00:00Z")
        if day_start is None or day_end is None or day_end <= day_start:
            continue
        overlap_start = max(day_start, window_start_utc)
        overlap_end = min(day_end, window_end_utc)
        if overlap_end <= overlap_start:
            continue
        overlap_seconds = Decimal(str((overlap_end - overlap_start).total_seconds()))
        day_seconds = Decimal(str((day_end - day_start).total_seconds()))
        if day_seconds <= Decimal("0"):
            continue
        total += row["amount"] * (overlap_seconds / day_seconds)
    return total


def _run_scope_ok(payload: dict[str, Any], *, platform_run_id: str, scenario_run_id: str) -> bool:
    return (
        str(payload.get("platform_run_id", "")).strip() == platform_run_id
        and str(payload.get("scenario_run_id", "")).strip() == scenario_run_id
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M8.J closure sync artifacts")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m8a-execution", required=True)
    parser.add_argument("--upstream-m8b-execution", required=True)
    parser.add_argument("--upstream-m8c-execution", required=True)
    parser.add_argument("--upstream-m8d-execution", required=True)
    parser.add_argument("--upstream-m8e-execution", required=True)
    parser.add_argument("--upstream-m8f-execution", required=True)
    parser.add_argument("--upstream-m8g-execution", required=True)
    parser.add_argument("--upstream-m8h-execution", required=True)
    parser.add_argument("--upstream-m8i-execution", required=True)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--billing-region", default="us-east-1")
    parser.add_argument("--budget-currency", default="USD")
    parser.add_argument("--monthly-limit-amount", default="300")
    parser.add_argument("--alert-1-amount", default="120")
    parser.add_argument("--alert-2-amount", default="210")
    parser.add_argument("--alert-3-amount", default="270")
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m8")
    args = parser.parse_args()

    captured_at = _now_utc()
    now_dt = datetime.now(timezone.utc)
    local_root = Path(args.local_output_root) / args.execution_id
    local_root.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name=args.region)
    ce = boto3.client("ce", region_name=args.billing_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[str] = []
    budget_errors: list[str] = []
    upload_errors: list[str] = []

    try:
        monthly_limit = _safe_decimal(args.monthly_limit_amount, field="monthly_limit_amount")
        alert_1 = _safe_decimal(args.alert_1_amount, field="alert_1_amount")
        alert_2 = _safe_decimal(args.alert_2_amount, field="alert_2_amount")
        alert_3 = _safe_decimal(args.alert_3_amount, field="alert_3_amount")
    except ValueError as exc:
        budget_errors.append(str(exc))
        monthly_limit = Decimal("1")
        alert_1 = Decimal("1")
        alert_2 = Decimal("1")
        alert_3 = Decimal("1")
    if not (alert_1 < alert_2 < alert_3 <= monthly_limit):
        budget_errors.append("budget_threshold_order_invalid")
    if budget_errors:
        blockers.append(
            {
                "code": "M8-B11",
                "message": "Budget envelope inputs are invalid for M8 closure artifacts.",
            }
        )

    contract_artifacts = {
        "m8a_handle_closure_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8a_execution}/m8a_handle_closure_snapshot.json",
        "m8b_runtime_lock_readiness_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8b_execution}/m8b_runtime_lock_readiness_snapshot.json",
        "m8c_closure_input_readiness_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8c_execution}/m8c_closure_input_readiness_snapshot.json",
        "m8d_single_writer_probe_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8d_execution}/m8d_single_writer_probe_snapshot.json",
        "m8e_reporter_execution_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8e_execution}/m8e_reporter_execution_snapshot.json",
        "m8f_closure_bundle_completeness_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8f_execution}/m8f_closure_bundle_completeness_snapshot.json",
        "m8g_non_regression_pack_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8g_execution}/m8g_non_regression_pack_snapshot.json",
        "m8h_governance_close_marker_snapshot": f"evidence/dev_full/run_control/{args.upstream_m8h_execution}/m8h_governance_close_marker_snapshot.json",
        "m8i_p11_rollup_matrix": f"evidence/dev_full/run_control/{args.upstream_m8i_execution}/m8i_p11_rollup_matrix.json",
        "m8i_p11_verdict": f"evidence/dev_full/run_control/{args.upstream_m8i_execution}/m8i_p11_verdict.json",
        "m9_handoff_pack": f"evidence/dev_full/run_control/{args.upstream_m8i_execution}/m9_handoff_pack.json",
    }

    summary_artifacts = {
        "m8a_summary": f"evidence/dev_full/run_control/{args.upstream_m8a_execution}/m8a_execution_summary.json",
        "m8b_summary": f"evidence/dev_full/run_control/{args.upstream_m8b_execution}/m8b_execution_summary.json",
        "m8c_summary": f"evidence/dev_full/run_control/{args.upstream_m8c_execution}/m8c_execution_summary.json",
        "m8d_summary": f"evidence/dev_full/run_control/{args.upstream_m8d_execution}/m8d_execution_summary.json",
        "m8e_summary": f"evidence/dev_full/run_control/{args.upstream_m8e_execution}/m8e_execution_summary.json",
        "m8f_summary": f"evidence/dev_full/run_control/{args.upstream_m8f_execution}/m8f_execution_summary.json",
        "m8g_summary": f"evidence/dev_full/run_control/{args.upstream_m8g_execution}/m8g_execution_summary.json",
        "m8h_summary": f"evidence/dev_full/run_control/{args.upstream_m8h_execution}/m8h_execution_summary.json",
        "m8i_summary": f"evidence/dev_full/run_control/{args.upstream_m8i_execution}/m8i_execution_summary.json",
    }

    contract_payloads: dict[str, dict[str, Any]] = {}
    contract_matrix: list[dict[str, Any]] = []
    for alias, key in contract_artifacts.items():
        payload, err = _read_json_from_s3(s3, bucket=args.evidence_bucket, key=key)
        contract_matrix.append(
            {
                "artifact": alias,
                "s3_key": key,
                "readable": payload is not None and err is None,
                "error": err,
            }
        )
        if err:
            read_errors.append(err)
        if payload is not None:
            contract_payloads[alias] = payload
    if any(not bool(item["readable"]) for item in contract_matrix):
        blockers.append(
            {
                "code": "M8-B12",
                "message": "One or more required M8 contract artifacts are missing/unreadable in durable storage.",
            }
        )

    summary_payloads: dict[str, dict[str, Any]] = {}
    summary_matrix: list[dict[str, Any]] = []
    for alias, key in summary_artifacts.items():
        payload, err = _read_json_from_s3(s3, bucket=args.evidence_bucket, key=key)
        summary_matrix.append(
            {
                "summary": alias,
                "s3_key": key,
                "readable": payload is not None and err is None,
                "error": err,
                "overall_pass": bool(payload.get("overall_pass")) if payload else False,
            }
        )
        if err:
            read_errors.append(err)
        if payload is not None:
            summary_payloads[alias] = payload
    if any(not bool(item["readable"]) for item in summary_matrix):
        blockers.append(
            {
                "code": "M8-B12",
                "message": "One or more required M8 summary artifacts are missing/unreadable in durable storage.",
            }
        )

    all_summary_pass = all(bool(item.get("overall_pass")) for item in summary_matrix if bool(item.get("readable")))
    if not all_summary_pass:
        blockers.append(
            {
                "code": "M8-B11",
                "message": "M8 upstream summary chain is not uniformly green.",
            }
        )

    run_scope_mismatch = any(
        not _run_scope_ok(payload, platform_run_id=args.platform_run_id, scenario_run_id=args.scenario_run_id)
        for payload in summary_payloads.values()
    )
    if run_scope_mismatch:
        blockers.append(
            {
                "code": "M8-B11",
                "message": "M8 summary chain run scope is inconsistent with M8.J active run scope.",
            }
        )

    m8i_summary = summary_payloads.get("m8i_summary", {})
    m8i_verdict_payload = contract_payloads.get("m8i_p11_verdict", {})
    m8i_gate_ok = (
        bool(m8i_summary.get("overall_pass"))
        and str(m8i_summary.get("verdict", "")).strip() == "ADVANCE_TO_M9"
        and str(m8i_summary.get("next_gate", "")).strip() == "M9_READY"
        and str(m8i_verdict_payload.get("verdict", "")).strip() == "ADVANCE_TO_M9"
        and str(m8i_verdict_payload.get("next_gate", "")).strip() == "M9_READY"
    )
    if not m8i_gate_ok:
        blockers.append(
            {
                "code": "M8-B11",
                "message": "M8.I gate posture is not green (`ADVANCE_TO_M9` / `M9_READY`).",
            }
        )

    upstream_times = []
    for payload in summary_payloads.values():
        parsed = _parse_utc(str(payload.get("captured_at_utc", "")))
        if parsed:
            upstream_times.append(parsed)
    phase_start_dt = min(upstream_times) if upstream_times else now_dt
    phase_end_dt = _parse_utc(captured_at) or now_dt
    phase_start = phase_start_dt.isoformat().replace("+00:00", "Z")

    month_start = _month_start_utc(now_dt)
    tomorrow = _tomorrow_utc(now_dt)
    aws_mtd, aws_mtd_unit, aws_mtd_error = _aws_mtd_cost(
        ce,
        start_date=month_start,
        end_date=tomorrow,
    )

    daily_start = phase_start_dt.date().isoformat()
    daily_end = (phase_end_dt.date() + timedelta(days=1)).isoformat()
    aws_daily_rows, aws_daily_unit, aws_daily_error = _aws_daily_cost_series(
        ce,
        start_date=daily_start,
        end_date=daily_end,
    )
    aws_phase_window_cost: Decimal | None = None
    if aws_daily_error:
        blockers.append(
            {
                "code": "M8-B11",
                "message": f"AWS phase-window cost capture failed during M8 closure ({aws_daily_error}).",
            }
        )
    elif aws_daily_rows is not None:
        aws_phase_window_cost = _window_prorated_cost(
            daily_rows=aws_daily_rows,
            window_start_utc=phase_start_dt,
            window_end_utc=phase_end_dt,
        )
        if aws_phase_window_cost >= alert_3:
            blockers.append(
                {
                    "code": "M8-B11",
                    "message": (
                        "M8 closure blocked by phase-window cost hard-stop "
                        f"(aws_phase_window_cost={str(aws_phase_window_cost)}, alert_3={str(alert_3)})."
                    ),
                }
            )

    ce_error = aws_daily_error or aws_mtd_error

    blockers = _dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    verdict = "ADVANCE_TO_M9" if overall_pass else "HOLD_REMEDIATE"
    next_gate = "M9_READY" if overall_pass else "HOLD_REMEDIATE"

    contract_upstream_required_count = len(contract_artifacts)
    contract_upstream_readable_count = sum(1 for item in contract_matrix if bool(item["readable"]))
    contract_total_required_count = 14
    contract_output_required_count = 3
    contract_output_published_count = 0

    run_control_prefix = f"evidence/dev_full/run_control/{args.execution_id}"
    durable_keys = {
        "m8_phase_budget_envelope_key": f"{run_control_prefix}/m8_phase_budget_envelope.json",
        "m8_phase_cost_outcome_receipt_key": f"{run_control_prefix}/m8_phase_cost_outcome_receipt.json",
        "m8_execution_summary_key": f"{run_control_prefix}/m8_execution_summary.json",
        "m8j_blocker_register_key": f"{run_control_prefix}/m8j_blocker_register.json",
        "m8j_execution_summary_key": f"{run_control_prefix}/m8j_execution_summary.json",
    }

    m8_contract_parity = {
        "required_artifact_count_total": contract_total_required_count,
        "required_upstream_artifact_count": contract_upstream_required_count,
        "readable_upstream_artifact_count": contract_upstream_readable_count,
        "required_m8j_output_count": contract_output_required_count,
        "published_m8j_output_count": contract_output_published_count,
        "all_required_available": bool(
            contract_upstream_readable_count == contract_upstream_required_count and contract_output_published_count == contract_output_required_count
        ),
    }

    phase_budget_envelope = {
        "phase": "M8.J",
        "phase_execution_id": args.execution_id,
        "captured_at_utc": captured_at,
        "budget_currency": args.budget_currency,
        "monthly_limit_amount": str(monthly_limit),
        "alert_1_amount": str(alert_1),
        "alert_2_amount": str(alert_2),
        "alert_3_amount": str(alert_3),
        "cost_capture_scope": "aws_phase_window_prorated_pre_m11_databricks_cost_deferred",
        "aws_cost_capture_enabled": True,
        "databricks_cost_capture_enabled": False,
        "aws_cost_attribution_method": "CE_DAILY_PRORATED_BY_WINDOW_SECONDS",
        "aws_phase_window_cost_amount": str(aws_phase_window_cost) if aws_phase_window_cost is not None else None,
        "aws_phase_window_cost_unit": aws_daily_unit or args.budget_currency,
        "aws_mtd_cost_amount_context": str(aws_mtd) if aws_mtd is not None else None,
        "aws_mtd_cost_unit_context": aws_mtd_unit or args.budget_currency,
        "phase_window": {
            "start_utc": phase_start,
            "end_utc": captured_at,
        },
        "m8_contract_parity": m8_contract_parity,
        "overall_pass": "M8-B11" not in {item["code"] for item in blockers},
        "blockers": [item for item in blockers if item["code"] in {"M8-B11"}],
    }

    phase_cost_outcome_receipt = {
        "phase_id": "M8",
        "phase": "M8.J",
        "phase_execution_id": args.execution_id,
        "window_start_utc": phase_start,
        "window_end_utc": captured_at,
        "spend_amount": str(aws_phase_window_cost) if aws_phase_window_cost is not None else None,
        "spend_currency": aws_daily_unit or args.budget_currency,
        "spend_attribution_method": "CE_DAILY_PRORATED_BY_WINDOW_SECONDS",
        "artifacts_emitted": [
            "m8_phase_budget_envelope.json",
            "m8_phase_cost_outcome_receipt.json",
            "m8_execution_summary.json",
            "m8j_execution_summary.json",
            "m8j_blocker_register.json",
        ],
        "decision_or_risk_retired": "M8 closure sync completed; P11 closure artifacts + deterministic handoff to M9 are finalized.",
        "source_components": {
            "aws_phase_window_cost_amount": str(aws_phase_window_cost) if aws_phase_window_cost is not None else None,
            "aws_phase_window_currency": aws_daily_unit or args.budget_currency,
            "aws_mtd_cost_amount_context": str(aws_mtd) if aws_mtd is not None else None,
            "aws_mtd_currency_context": aws_mtd_unit or args.budget_currency,
            "databricks_mtd_cost_amount": None,
            "databricks_capture_mode": "DEFERRED",
        },
    }

    m8_execution_summary = {
        "phase": "M8.J",
        "phase_id": "M8",
        "phase_execution_id": args.execution_id,
        "captured_at_utc": captured_at,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "overall_pass": overall_pass,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "upstream_refs": {
            "m8a_execution_id": args.upstream_m8a_execution,
            "m8b_execution_id": args.upstream_m8b_execution,
            "m8c_execution_id": args.upstream_m8c_execution,
            "m8d_execution_id": args.upstream_m8d_execution,
            "m8e_execution_id": args.upstream_m8e_execution,
            "m8f_execution_id": args.upstream_m8f_execution,
            "m8g_execution_id": args.upstream_m8g_execution,
            "m8h_execution_id": args.upstream_m8h_execution,
            "m8i_execution_id": args.upstream_m8i_execution,
        },
        "m8_contract_parity": m8_contract_parity,
        "durable_artifacts": durable_keys,
    }

    m8j_blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M8.J",
        "phase_id": "M8",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "contract_matrix": contract_matrix,
        "summary_matrix": summary_matrix,
        "read_errors": read_errors,
        "budget_errors": budget_errors,
        "ce_error": ce_error,
    }

    m8j_execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M8.J",
        "phase_id": "M8",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    artifacts = {
        "m8_phase_budget_envelope.json": phase_budget_envelope,
        "m8_phase_cost_outcome_receipt.json": phase_cost_outcome_receipt,
        "m8_execution_summary.json": m8_execution_summary,
        "m8j_blocker_register.json": m8j_blocker_register,
        "m8j_execution_summary.json": m8j_execution_summary,
    }
    for name, payload in artifacts.items():
        _write_json(local_root / name, payload)

    for name, payload in artifacts.items():
        ok, err = _put_json_and_head(
            s3,
            bucket=args.evidence_bucket,
            key=f"{run_control_prefix}/{name}",
            payload=payload,
        )
        if ok and name in {
            "m8_phase_budget_envelope.json",
            "m8_phase_cost_outcome_receipt.json",
            "m8_execution_summary.json",
        }:
            contract_output_published_count += 1
        if not ok and err:
            upload_errors.append(err)

    if upload_errors:
        blockers = list(blockers)
        blockers.append(
            {
                "code": "M8-B12",
                "message": "Failed to publish/readback M8.J run-control artifact set.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m8_contract_parity["published_m8j_output_count"] = contract_output_published_count
    m8_contract_parity["all_required_available"] = bool(
        contract_upstream_readable_count == contract_upstream_required_count and contract_output_published_count == contract_output_required_count
    )
    if not m8_contract_parity["all_required_available"]:
        blockers = list(blockers)
        blockers.append(
            {
                "code": "M8-B12",
                "message": "M8 artifact contract parity is incomplete after M8.J publication.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m8_execution_summary["overall_pass"] = overall_pass
    m8_execution_summary["blockers"] = blockers
    m8_execution_summary["blocker_count"] = len(blockers)
    m8_execution_summary["verdict"] = verdict
    m8_execution_summary["next_gate"] = next_gate
    m8_execution_summary["m8_contract_parity"] = m8_contract_parity
    m8j_blocker_register["blockers"] = blockers
    m8j_blocker_register["blocker_count"] = len(blockers)
    m8j_blocker_register["upload_errors"] = upload_errors
    m8j_execution_summary["overall_pass"] = overall_pass
    m8j_execution_summary["blocker_count"] = len(blockers)
    m8j_execution_summary["verdict"] = verdict
    m8j_execution_summary["next_gate"] = next_gate
    phase_budget_envelope["m8_contract_parity"] = m8_contract_parity
    phase_budget_envelope["overall_pass"] = "M8-B11" not in {item["code"] for item in blockers}
    phase_budget_envelope["blockers"] = [item for item in blockers if item["code"] in {"M8-B11"}]

    _write_json(local_root / "m8_phase_budget_envelope.json", phase_budget_envelope)
    _write_json(local_root / "m8_execution_summary.json", m8_execution_summary)
    _write_json(local_root / "m8j_blocker_register.json", m8j_blocker_register)
    _write_json(local_root / "m8j_execution_summary.json", m8j_execution_summary)

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": m8j_execution_summary.get("overall_pass"),
                "blocker_count": m8j_execution_summary.get("blocker_count"),
                "verdict": m8j_execution_summary.get("verdict"),
                "next_gate": m8j_execution_summary.get("next_gate"),
                "m8_contract_parity": m8_contract_parity,
                "local_output": str(local_root),
                "run_control_prefix": f"s3://{args.evidence_bucket}/{run_control_prefix}/",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
