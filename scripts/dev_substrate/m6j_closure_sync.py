#!/usr/bin/env python3
"""Build and publish M6.J closure + cost-outcome artifacts."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build M6.J closure artifacts")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m6d-execution", required=True)
    parser.add_argument("--upstream-m6g-execution", required=True)
    parser.add_argument("--upstream-m6i-execution", required=True)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--billing-region", default="us-east-1")
    parser.add_argument("--budget-currency", default="USD")
    parser.add_argument("--monthly-limit-amount", default="300")
    parser.add_argument("--alert-1-amount", default="120")
    parser.add_argument("--alert-2-amount", default="210")
    parser.add_argument("--alert-3-amount", default="270")
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m6")
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

    required_artifacts = {
        "m6d_summary": f"evidence/dev_full/run_control/{args.upstream_m6d_execution}/m6d_execution_summary.json",
        "m6d_verdict": f"evidence/dev_full/run_control/{args.upstream_m6d_execution}/m6d_p5_gate_verdict.json",
        "m6g_summary": f"evidence/dev_full/run_control/{args.upstream_m6g_execution}/m6g_execution_summary.json",
        "m6g_verdict": f"evidence/dev_full/run_control/{args.upstream_m6g_execution}/m6g_p6_gate_verdict.json",
        "m6i_summary": f"evidence/dev_full/run_control/{args.upstream_m6i_execution}/m6i_execution_summary.json",
        "m6i_verdict": f"evidence/dev_full/run_control/{args.upstream_m6i_execution}/m6i_p7_gate_verdict.json",
        "m7_handoff_pack": f"evidence/dev_full/run_control/{args.upstream_m6i_execution}/m7_handoff_pack.json",
    }
    payloads: dict[str, dict[str, Any]] = {}
    for alias, key in required_artifacts.items():
        payload, err = _read_json_from_s3(s3, bucket=args.evidence_bucket, key=key)
        if err:
            read_errors.append(err)
            continue
        if payload is not None:
            payloads[alias] = payload
    if read_errors:
        blockers.append(
            {
                "code": "M6-B12",
                "message": "Required upstream closure artifacts are missing/unreadable in durable storage.",
            }
        )

    m6d_summary = payloads.get("m6d_summary", {})
    m6d_verdict = payloads.get("m6d_verdict", {})
    m6g_summary = payloads.get("m6g_summary", {})
    m6g_verdict = payloads.get("m6g_verdict", {})
    m6i_summary = payloads.get("m6i_summary", {})
    m6i_verdict = payloads.get("m6i_verdict", {})

    m6d_pass = bool(m6d_summary.get("overall_pass"))
    m6d_verdict_ok = str(m6d_verdict.get("verdict", "")).strip() in {"ADVANCE_TO_P6", ""}
    m6g_pass = bool(m6g_summary.get("overall_pass"))
    m6g_verdict_ok = str(m6g_verdict.get("verdict", "")).strip() == "ADVANCE_TO_P7"
    m6i_pass = bool(m6i_summary.get("overall_pass"))
    m6i_verdict_value = str(m6i_verdict.get("verdict", m6i_summary.get("verdict", ""))).strip()
    m6i_verdict_ok = m6i_verdict_value == "ADVANCE_TO_M7"

    if not (m6d_pass and m6d_verdict_ok and m6g_pass and m6g_verdict_ok and m6i_pass and m6i_verdict_ok):
        blockers.append(
            {
                "code": "M6-B10",
                "message": "Upstream M6 closure chain is not verdict-consistent (`M6.D`, `M6.G`, `M6.I`).",
            }
        )

    if budget_errors:
        blockers.append(
            {
                "code": "M6-B12",
                "message": "Budget envelope inputs are invalid for M6 closure artifacts.",
            }
        )

    month_start = _month_start_utc(now_dt)
    tomorrow = _tomorrow_utc(now_dt)
    aws_mtd, aws_unit, ce_error = _aws_mtd_cost(
        ce,
        start_date=month_start,
        end_date=tomorrow,
    )
    if ce_error:
        blockers.append(
            {
                "code": "M6-B12",
                "message": f"AWS cost capture failed during M6 closure ({ce_error}).",
            }
        )
    if aws_mtd is not None and aws_mtd >= alert_3:
        blockers.append(
            {
                "code": "M6-B13",
                "message": (
                    "M6 closure blocked by cost hard-stop "
                    f"(aws_mtd_cost={str(aws_mtd)}, alert_3={str(alert_3)})."
                ),
            }
        )

    blockers = _dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    verdict = "ADVANCE_TO_M7" if overall_pass else "HOLD_REMEDIATE"
    next_gate = "M7_READY" if overall_pass else "HOLD_REMEDIATE"

    upstream_times = []
    for key in ("m6d_summary", "m6g_summary", "m6i_summary"):
        parsed = _parse_utc(str(payloads.get(key, {}).get("captured_at_utc", "")))
        if parsed:
            upstream_times.append(parsed)
    phase_start = min(upstream_times).isoformat().replace("+00:00", "Z") if upstream_times else captured_at

    phase_budget_envelope = {
        "phase": "M6.J",
        "phase_execution_id": args.execution_id,
        "captured_at_utc": captured_at,
        "budget_currency": args.budget_currency,
        "monthly_limit_amount": str(monthly_limit),
        "alert_1_amount": str(alert_1),
        "alert_2_amount": str(alert_2),
        "alert_3_amount": str(alert_3),
        "cost_capture_scope": "aws_only_pre_m11_databricks_cost_deferred",
        "aws_cost_capture_enabled": True,
        "databricks_cost_capture_enabled": False,
        "phase_window": {
            "start_utc": phase_start,
            "end_utc": captured_at,
        },
        "overall_pass": "M6-B12" not in {item["code"] for item in blockers},
        "blockers": [item for item in blockers if item["code"] in {"M6-B12"}],
    }

    phase_cost_outcome_receipt = {
        "phase_id": "M6",
        "phase": "M6.J",
        "phase_execution_id": args.execution_id,
        "window_start_utc": phase_start,
        "window_end_utc": captured_at,
        "spend_amount": str(aws_mtd) if aws_mtd is not None else None,
        "spend_currency": aws_unit or args.budget_currency,
        "artifacts_emitted": [
            "m6_phase_budget_envelope.json",
            "m6_phase_cost_outcome_receipt.json",
            "m6_execution_summary.json",
            "m6j_execution_summary.json",
            "m6j_blocker_register.json",
        ],
        "decision_or_risk_retired": "M6 closure sync completed; M7 entry verdict emitted from deterministic P5/P6/P7 closure chain.",
        "source_components": {
            "aws_mtd_cost_amount": str(aws_mtd) if aws_mtd is not None else None,
            "aws_currency": aws_unit or args.budget_currency,
            "databricks_mtd_cost_amount": None,
            "databricks_capture_mode": "DEFERRED",
        },
    }

    m6_execution_summary = {
        "phase": "M6.J",
        "phase_id": "M6",
        "phase_execution_id": args.execution_id,
        "captured_at_utc": captured_at,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "overall_pass": overall_pass,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "upstream_chain": {
            "required_count": 3,
            "green_count": int(m6d_pass and m6d_verdict_ok) + int(m6g_pass and m6g_verdict_ok) + int(m6i_pass and m6i_verdict_ok),
            "all_green": bool(m6d_pass and m6d_verdict_ok and m6g_pass and m6g_verdict_ok and m6i_pass and m6i_verdict_ok),
        },
        "upstream_refs": {
            "m6d_execution_id": args.upstream_m6d_execution,
            "m6g_execution_id": args.upstream_m6g_execution,
            "m6i_execution_id": args.upstream_m6i_execution,
        },
    }

    m6j_blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M6.J",
        "phase_id": "M6",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "budget_errors": budget_errors,
        "ce_error": ce_error,
    }

    m6j_execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.J",
        "phase_id": "M6",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    artifacts = {
        "m6_phase_budget_envelope.json": phase_budget_envelope,
        "m6_phase_cost_outcome_receipt.json": phase_cost_outcome_receipt,
        "m6_execution_summary.json": m6_execution_summary,
        "m6j_blocker_register.json": m6j_blocker_register,
        "m6j_execution_summary.json": m6j_execution_summary,
    }
    for name, payload in artifacts.items():
        _write_json(local_root / name, payload)

    run_control_prefix = f"evidence/dev_full/run_control/{args.execution_id}"
    upload_errors: list[str] = []
    for name, payload in artifacts.items():
        ok, err = _put_json_and_head(
            s3,
            bucket=args.evidence_bucket,
            key=f"{run_control_prefix}/{name}",
            payload=payload,
        )
        if not ok and err:
            upload_errors.append(err)

    if upload_errors:
        blockers = list(blockers)
        blockers.append(
            {
                "code": "M6-B12",
                "message": "Failed to publish/readback M6.J run-control artifact set.",
            }
        )
        blockers = _dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"
        m6_execution_summary["overall_pass"] = overall_pass
        m6_execution_summary["blockers"] = blockers
        m6_execution_summary["blocker_count"] = len(blockers)
        m6_execution_summary["verdict"] = verdict
        m6_execution_summary["next_gate"] = next_gate
        m6j_blocker_register["blockers"] = blockers
        m6j_blocker_register["blocker_count"] = len(blockers)
        m6j_blocker_register["upload_errors"] = upload_errors
        m6j_execution_summary["overall_pass"] = overall_pass
        m6j_execution_summary["blocker_count"] = len(blockers)
        m6j_execution_summary["verdict"] = verdict
        m6j_execution_summary["next_gate"] = next_gate
        _write_json(local_root / "m6_execution_summary.json", m6_execution_summary)
        _write_json(local_root / "m6j_blocker_register.json", m6j_blocker_register)
        _write_json(local_root / "m6j_execution_summary.json", m6j_execution_summary)

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": m6j_execution_summary.get("overall_pass"),
                "blocker_count": m6j_execution_summary.get("blocker_count"),
                "verdict": m6j_execution_summary.get("verdict"),
                "next_gate": m6j_execution_summary.get("next_gate"),
                "local_output": str(local_root),
                "run_control_prefix": f"s3://{args.evidence_bucket}/{run_control_prefix}/",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
