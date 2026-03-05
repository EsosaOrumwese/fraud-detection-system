#!/usr/bin/env python3
"""Build and publish M10.J closure sync + cost-outcome artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json_from_s3(s3_client: Any, *, bucket: str, key: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read().decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None, f"json_not_object:{key}"
        return payload, None
    except (BotoCoreError, ClientError) as exc:
        return None, f"s3_read_failed:{type(exc).__name__}:{key}"
    except json.JSONDecodeError:
        return None, f"json_decode_failed:{key}"


def put_json_and_head(
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


def parse_utc(text: str | None) -> datetime | None:
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


def dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        message = str(blocker.get("message", "")).strip()
        sig = (code, message)
        if not code or sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": message})
    return out


def run_scope_ok(payload: dict[str, Any], *, platform_run_id: str, scenario_run_id: str) -> bool:
    return (
        str(payload.get("platform_run_id", "")).strip() == platform_run_id
        and str(payload.get("scenario_run_id", "")).strip() == scenario_run_id
    )


def safe_decimal(text: str, *, field: str) -> Decimal:
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_decimal:{field}:{text}") from exc
    if value <= Decimal("0"):
        raise ValueError(f"non_positive_decimal:{field}:{text}")
    return value


def month_start_utc(now: datetime) -> str:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date().isoformat()


def tomorrow_utc(now: datetime) -> str:
    return (now.date() + timedelta(days=1)).isoformat()


def aws_mtd_cost(
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


def aws_daily_cost_series(
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


def window_prorated_cost(
    *,
    daily_rows: list[dict[str, Any]],
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> Decimal:
    total = Decimal("0")
    if window_end_utc <= window_start_utc:
        return total
    for row in daily_rows:
        day_start = parse_utc(f"{row['start_date']}T00:00:00Z")
        day_end = parse_utc(f"{row['end_date']}T00:00:00Z")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M10.J closure sync artifacts")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m10a-execution", required=True)
    parser.add_argument("--upstream-m10b-execution", required=True)
    parser.add_argument("--upstream-m10c-execution", required=True)
    parser.add_argument("--upstream-m10d-execution", required=True)
    parser.add_argument("--upstream-m10e-execution", required=True)
    parser.add_argument("--upstream-m10f-execution", required=True)
    parser.add_argument("--upstream-m10g-execution", required=True)
    parser.add_argument("--upstream-m10h-execution", required=True)
    parser.add_argument("--upstream-m10i-execution", required=True)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--billing-region", default="us-east-1")
    parser.add_argument("--budget-currency", default="USD")
    parser.add_argument("--monthly-limit-amount", default="130")
    parser.add_argument("--alert-1-amount", default="52")
    parser.add_argument("--alert-2-amount", default="91")
    parser.add_argument("--alert-3-amount", default="123")
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m10")
    args = parser.parse_args()

    captured_at = now_utc()
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
        monthly_limit = safe_decimal(args.monthly_limit_amount, field="monthly_limit_amount")
        alert_1 = safe_decimal(args.alert_1_amount, field="alert_1_amount")
        alert_2 = safe_decimal(args.alert_2_amount, field="alert_2_amount")
        alert_3 = safe_decimal(args.alert_3_amount, field="alert_3_amount")
    except ValueError as exc:
        budget_errors.append(str(exc))
        monthly_limit = Decimal("1")
        alert_1 = Decimal("1")
        alert_2 = Decimal("1")
        alert_3 = Decimal("1")
    if not (alert_1 < alert_2 < alert_3 <= monthly_limit):
        budget_errors.append("budget_threshold_order_invalid")
    if budget_errors:
        blockers.append({"code": "M10-B11", "message": "Budget envelope inputs are invalid for M10 closure artifacts."})

    summary_specs = [
        ("M10.A", args.upstream_m10a_execution, "m10a_execution_summary.json", "M10.B_READY"),
        ("M10.B", args.upstream_m10b_execution, "m10b_execution_summary.json", "M10.C_READY"),
        ("M10.C", args.upstream_m10c_execution, "m10c_execution_summary.json", "M10.D_READY"),
        ("M10.D", args.upstream_m10d_execution, "m10d_execution_summary.json", "M10.E_READY"),
        ("M10.E", args.upstream_m10e_execution, "m10e_execution_summary.json", "M10.F_READY"),
        ("M10.F", args.upstream_m10f_execution, "m10f_execution_summary.json", "M10.G_READY"),
        ("M10.G", args.upstream_m10g_execution, "m10g_execution_summary.json", "M10.H_READY"),
        ("M10.H", args.upstream_m10h_execution, "m10h_execution_summary.json", "M10.I_READY"),
        ("M10.I", args.upstream_m10i_execution, "m10i_execution_summary.json", "M11_READY"),
    ]

    summary_payloads: dict[str, dict[str, Any]] = {}
    summary_matrix: list[dict[str, Any]] = []
    upstream_times: list[datetime] = []
    for phase_name, phase_exec, summary_file, expected_next_gate in summary_specs:
        key = f"evidence/dev_full/run_control/{phase_exec}/{summary_file}"
        payload, err = read_json_from_s3(s3, bucket=args.evidence_bucket, key=key)
        row = {
            "phase": phase_name,
            "execution_id": phase_exec,
            "s3_key": key,
            "readable": payload is not None and err is None,
            "error": err,
            "overall_pass": bool(payload.get("overall_pass")) if payload else False,
            "expected_next_gate": expected_next_gate,
            "actual_next_gate": str(payload.get("next_gate", "")).strip() if payload else "",
            "next_gate_ok": bool(payload is not None and str(payload.get("next_gate", "")).strip() == expected_next_gate),
            "run_scope_ok": False,
        }
        summary_matrix.append(row)
        if err:
            read_errors.append(err)
            blockers.append({"code": "M10-B12", "message": f"{phase_name} summary unreadable."})
        if payload is None:
            continue
        summary_payloads[phase_name] = payload
        if not bool(payload.get("overall_pass")):
            blockers.append({"code": "M10-B11", "message": f"{phase_name} summary is not pass."})
        if str(payload.get("next_gate", "")).strip() != expected_next_gate:
            blockers.append({"code": "M10-B11", "message": f"{phase_name} next_gate mismatch."})
        parsed = parse_utc(str(payload.get("captured_at_utc", "")).strip()) or parse_utc(str(payload.get("generated_at_utc", "")).strip())
        if parsed is not None:
            upstream_times.append(parsed)

    all_summary_readable = all(bool(row.get("readable")) for row in summary_matrix)
    if not all_summary_readable:
        blockers.append({"code": "M10-B12", "message": "One or more required M10 summary artifacts are missing/unreadable in durable storage."})

    run_scope_mismatch = False
    for row in summary_matrix:
        payload = summary_payloads.get(str(row["phase"]), {})
        ok = run_scope_ok(payload, platform_run_id=args.platform_run_id, scenario_run_id=args.scenario_run_id)
        row["run_scope_ok"] = ok
        if row["readable"] and not ok:
            run_scope_mismatch = True
            blockers.append({"code": "M10-B11", "message": f"{row['phase']} run-scope mismatch."})
    if run_scope_mismatch:
        blockers.append({"code": "M10-B11", "message": "M10 summary chain run scope is inconsistent with M10.J active run scope."})

    m10i_summary = summary_payloads.get("M10.I", {})
    m10i_key = f"evidence/dev_full/run_control/{args.upstream_m10i_execution}/m10i_p13_gate_verdict.json"
    m10i_verdict_payload, m10i_verdict_err = read_json_from_s3(s3, bucket=args.evidence_bucket, key=m10i_key)
    if m10i_verdict_err:
        read_errors.append(m10i_verdict_err)
        blockers.append({"code": "M10-B12", "message": "M10.I verdict artifact unreadable."})
        m10i_verdict_payload = {}
    m10i_gate_ok = (
        bool(m10i_summary.get("overall_pass"))
        and str(m10i_summary.get("verdict", "")).strip() == "ADVANCE_TO_P14"
        and str(m10i_summary.get("next_gate", "")).strip() == "M11_READY"
        and str((m10i_verdict_payload or {}).get("verdict", "")).strip() == "ADVANCE_TO_P14"
        and str((m10i_verdict_payload or {}).get("next_gate", "")).strip() == "M11_READY"
    )
    if not m10i_gate_ok:
        blockers.append({"code": "M10-B11", "message": "M10.I gate posture is not green (`ADVANCE_TO_P14` / `M11_READY`)."})

    contract_artifacts = {
        "m10a_handle_closure_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10a_execution}/m10a_handle_closure_snapshot.json",
        "m10b_databricks_readiness_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10b_execution}/m10b_databricks_readiness_snapshot.json",
        "m10c_input_binding_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10c_execution}/m10c_input_binding_snapshot.json",
        "m10d_ofs_build_execution_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10d_execution}/m10d_ofs_build_execution_snapshot.json",
        "m10e_quality_gate_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10e_execution}/m10e_quality_gate_snapshot.json",
        "m10f_iceberg_commit_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10f_execution}/m10f_iceberg_commit_snapshot.json",
        "m10g_manifest_fingerprint_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10g_execution}/m10g_manifest_fingerprint_snapshot.json",
        "m10h_rollback_recipe_snapshot": f"evidence/dev_full/run_control/{args.upstream_m10h_execution}/m10h_rollback_recipe_snapshot.json",
        "m10i_p13_rollup_matrix": f"evidence/dev_full/run_control/{args.upstream_m10i_execution}/m10i_p13_rollup_matrix.json",
        "m10i_p13_gate_verdict": m10i_key,
        "m11_handoff_pack": f"evidence/dev_full/run_control/{args.upstream_m10i_execution}/m11_handoff_pack.json",
    }
    contract_matrix: list[dict[str, Any]] = []
    for alias, key in contract_artifacts.items():
        payload, err = read_json_from_s3(s3, bucket=args.evidence_bucket, key=key)
        row = {
            "artifact": alias,
            "s3_key": key,
            "readable": payload is not None and err is None,
            "error": err,
        }
        contract_matrix.append(row)
        if err:
            read_errors.append(err)
    if any(not bool(item["readable"]) for item in contract_matrix):
        blockers.append({"code": "M10-B12", "message": "One or more required M10 contract artifacts are missing/unreadable in durable storage."})

    phase_start_dt = min(upstream_times) if upstream_times else now_dt
    phase_end_dt = parse_utc(captured_at) or now_dt
    phase_start = phase_start_dt.isoformat().replace("+00:00", "Z")

    month_start = month_start_utc(now_dt)
    tomorrow = tomorrow_utc(now_dt)
    aws_mtd, aws_mtd_unit, aws_mtd_error = aws_mtd_cost(
        ce,
        start_date=month_start,
        end_date=tomorrow,
    )
    daily_start = phase_start_dt.date().isoformat()
    daily_end = (phase_end_dt.date() + timedelta(days=1)).isoformat()
    aws_daily_rows, aws_daily_unit, aws_daily_error = aws_daily_cost_series(
        ce,
        start_date=daily_start,
        end_date=daily_end,
    )
    aws_phase_window_cost: Decimal | None = None
    if aws_daily_error:
        blockers.append({"code": "M10-B11", "message": f"AWS phase-window cost capture failed during M10 closure ({aws_daily_error})."})
    elif aws_daily_rows is not None:
        aws_phase_window_cost = window_prorated_cost(
            daily_rows=aws_daily_rows,
            window_start_utc=phase_start_dt,
            window_end_utc=phase_end_dt,
        )
        if aws_phase_window_cost >= alert_3:
            blockers.append(
                {
                    "code": "M10-B11",
                    "message": (
                        "M10 closure blocked by phase-window cost hard-stop "
                        f"(aws_phase_window_cost={str(aws_phase_window_cost)}, alert_3={str(alert_3)})."
                    ),
                }
            )
    ce_error = aws_daily_error or aws_mtd_error

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    verdict = "ADVANCE_TO_M11" if overall_pass else "HOLD_REMEDIATE"
    next_gate = "M11_READY" if overall_pass else "HOLD_REMEDIATE"

    contract_upstream_required_count = len(summary_specs) + len(contract_artifacts)
    contract_upstream_readable_count = sum(1 for row in summary_matrix if bool(row.get("readable"))) + sum(
        1 for row in contract_matrix if bool(row.get("readable"))
    )
    contract_output_required_count = 3
    contract_output_published_count = 0
    contract_total_required_count = contract_upstream_required_count + contract_output_required_count

    run_control_prefix = f"evidence/dev_full/run_control/{args.execution_id}"
    durable_keys = {
        "m10_phase_budget_envelope_key": f"{run_control_prefix}/m10_phase_budget_envelope.json",
        "m10_phase_cost_outcome_receipt_key": f"{run_control_prefix}/m10_phase_cost_outcome_receipt.json",
        "m10_execution_summary_key": f"{run_control_prefix}/m10_execution_summary.json",
        "m10j_blocker_register_key": f"{run_control_prefix}/m10j_blocker_register.json",
        "m10j_execution_summary_key": f"{run_control_prefix}/m10j_execution_summary.json",
    }

    m10_contract_parity = {
        "required_artifact_count_total": contract_total_required_count,
        "required_upstream_artifact_count": contract_upstream_required_count,
        "readable_upstream_artifact_count": contract_upstream_readable_count,
        "required_m10j_output_count": contract_output_required_count,
        "published_m10j_output_count": contract_output_published_count,
        "all_required_available": bool(
            contract_upstream_readable_count == contract_upstream_required_count
            and contract_output_published_count == contract_output_required_count
        ),
    }

    phase_budget_envelope = {
        "phase": "M10.J",
        "phase_execution_id": args.execution_id,
        "captured_at_utc": captured_at,
        "budget_currency": args.budget_currency,
        "monthly_limit_amount": str(monthly_limit),
        "alert_1_amount": str(alert_1),
        "alert_2_amount": str(alert_2),
        "alert_3_amount": str(alert_3),
        "cost_capture_scope": "aws_phase_window_prorated_pre_m11_model_train_databricks_deferred",
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
        "m10_contract_parity": m10_contract_parity,
        "overall_pass": "M10-B11" not in {item["code"] for item in blockers},
        "blockers": [item for item in blockers if item["code"] in {"M10-B11"}],
    }

    phase_cost_outcome_receipt = {
        "phase_id": "M10",
        "phase": "M10.J",
        "phase_execution_id": args.execution_id,
        "window_start_utc": phase_start,
        "window_end_utc": captured_at,
        "spend_amount": str(aws_phase_window_cost) if aws_phase_window_cost is not None else None,
        "spend_currency": aws_daily_unit or args.budget_currency,
        "spend_attribution_method": "CE_DAILY_PRORATED_BY_WINDOW_SECONDS",
        "artifacts_emitted": [
            "m10_phase_budget_envelope.json",
            "m10_phase_cost_outcome_receipt.json",
            "m10_execution_summary.json",
            "m10j_execution_summary.json",
            "m10j_blocker_register.json",
        ],
        "decision_or_risk_retired": "M10 closure sync completed; P13 closure artifacts and deterministic handoff to M11 are finalized.",
        "source_components": {
            "aws_phase_window_cost_amount": str(aws_phase_window_cost) if aws_phase_window_cost is not None else None,
            "aws_phase_window_currency": aws_daily_unit or args.budget_currency,
            "aws_mtd_cost_amount_context": str(aws_mtd) if aws_mtd is not None else None,
            "aws_mtd_currency_context": aws_mtd_unit or args.budget_currency,
            "databricks_mtd_cost_amount": None,
            "databricks_capture_mode": "DEFERRED",
        },
    }

    m10_execution_summary = {
        "phase": "M10.J",
        "phase_id": "M10",
        "phase_execution_id": args.execution_id,
        "captured_at_utc": captured_at,
        "window_start_utc": phase_start,
        "window_end_utc": captured_at,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "overall_pass": overall_pass,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "p13_verdict": str(m10i_summary.get("verdict", "")).strip(),
        "p13_verdict_ref": m10i_key,
        "m11_handoff_ref": contract_artifacts["m11_handoff_pack"],
        "upstream_refs": {
            "m10a_execution_id": args.upstream_m10a_execution,
            "m10b_execution_id": args.upstream_m10b_execution,
            "m10c_execution_id": args.upstream_m10c_execution,
            "m10d_execution_id": args.upstream_m10d_execution,
            "m10e_execution_id": args.upstream_m10e_execution,
            "m10f_execution_id": args.upstream_m10f_execution,
            "m10g_execution_id": args.upstream_m10g_execution,
            "m10h_execution_id": args.upstream_m10h_execution,
            "m10i_execution_id": args.upstream_m10i_execution,
        },
        "m10_contract_parity": m10_contract_parity,
        "durable_artifacts": durable_keys,
    }

    m10j_blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M10.J",
        "phase_id": "M10",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "summary_matrix": summary_matrix,
        "contract_matrix": contract_matrix,
        "read_errors": read_errors,
        "budget_errors": budget_errors,
        "ce_error": ce_error,
    }

    m10j_execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M10.J",
        "phase_id": "M10",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    artifacts = {
        "m10_phase_budget_envelope.json": phase_budget_envelope,
        "m10_phase_cost_outcome_receipt.json": phase_cost_outcome_receipt,
        "m10_execution_summary.json": m10_execution_summary,
        "m10j_blocker_register.json": m10j_blocker_register,
        "m10j_execution_summary.json": m10j_execution_summary,
    }
    for name, payload in artifacts.items():
        write_json(local_root / name, payload)

    for name, payload in artifacts.items():
        ok, err = put_json_and_head(
            s3,
            bucket=args.evidence_bucket,
            key=f"{run_control_prefix}/{name}",
            payload=payload,
        )
        if ok and name in {
            "m10_phase_budget_envelope.json",
            "m10_phase_cost_outcome_receipt.json",
            "m10_execution_summary.json",
        }:
            contract_output_published_count += 1
        if not ok and err:
            upload_errors.append(err)

    if upload_errors:
        blockers = list(blockers)
        blockers.append({"code": "M10-B12", "message": "Failed to publish/readback M10.J run-control artifact set."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m10_contract_parity["published_m10j_output_count"] = contract_output_published_count
    m10_contract_parity["all_required_available"] = bool(
        contract_upstream_readable_count == contract_upstream_required_count
        and contract_output_published_count == contract_output_required_count
    )
    if not m10_contract_parity["all_required_available"]:
        blockers = list(blockers)
        blockers.append({"code": "M10-B12", "message": "M10 artifact contract parity is incomplete after M10.J publication."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m10_execution_summary["overall_pass"] = overall_pass
    m10_execution_summary["blockers"] = blockers
    m10_execution_summary["blocker_count"] = len(blockers)
    m10_execution_summary["verdict"] = verdict
    m10_execution_summary["next_gate"] = next_gate
    m10_execution_summary["m10_contract_parity"] = m10_contract_parity

    m10j_blocker_register["blockers"] = blockers
    m10j_blocker_register["blocker_count"] = len(blockers)
    m10j_blocker_register["upload_errors"] = upload_errors

    m10j_execution_summary["overall_pass"] = overall_pass
    m10j_execution_summary["blocker_count"] = len(blockers)
    m10j_execution_summary["verdict"] = verdict
    m10j_execution_summary["next_gate"] = next_gate

    phase_budget_envelope["m10_contract_parity"] = m10_contract_parity
    phase_budget_envelope["overall_pass"] = "M10-B11" not in {item["code"] for item in blockers}
    phase_budget_envelope["blockers"] = [item for item in blockers if item["code"] in {"M10-B11"}]

    write_json(local_root / "m10_phase_budget_envelope.json", phase_budget_envelope)
    write_json(local_root / "m10_execution_summary.json", m10_execution_summary)
    write_json(local_root / "m10j_blocker_register.json", m10j_blocker_register)
    write_json(local_root / "m10j_execution_summary.json", m10j_execution_summary)

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": m10j_execution_summary.get("overall_pass"),
                "blocker_count": m10j_execution_summary.get("blocker_count"),
                "verdict": m10j_execution_summary.get("verdict"),
                "next_gate": m10j_execution_summary.get("next_gate"),
                "m10_contract_parity": m10_contract_parity,
                "local_output": str(local_root),
                "run_control_prefix": f"s3://{args.evidence_bucket}/{run_control_prefix}/",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
