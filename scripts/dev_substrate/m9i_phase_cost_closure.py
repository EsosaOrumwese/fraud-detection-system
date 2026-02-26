#!/usr/bin/env python3
"""Build and publish M9.I phase budget + cost-outcome closure artifacts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
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


def parse_utc(text: str | None) -> datetime | None:
    if not text:
        return None
    normalized = str(text).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def month_start_utc(now_dt: datetime) -> str:
    return now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date().isoformat()


def tomorrow_utc(now_dt: datetime) -> str:
    return (now_dt.date() + timedelta(days=1)).isoformat()


def as_decimal(text: Any, field: str) -> Decimal:
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid_decimal:{field}:{text}") from exc
    if value <= Decimal("0"):
        raise ValueError(f"non_positive_decimal:{field}:{text}")
    return value


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


def aws_mtd_cost(ce_client: Any, start_date: str, end_date: str) -> tuple[Decimal | None, str | None, str | None]:
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
    env = dict(os.environ)
    execution_id = env.get("M9I_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9I_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    billing_region = env.get("BILLING_REGION", "us-east-1").strip() or "us-east-1"

    if not execution_id:
        raise SystemExit("M9I_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9I_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")

    upstream_execs = {
        "m9a": env.get("UPSTREAM_M9A_EXECUTION", "").strip(),
        "m9b": env.get("UPSTREAM_M9B_EXECUTION", "").strip(),
        "m9c": env.get("UPSTREAM_M9C_EXECUTION", "").strip(),
        "m9d": env.get("UPSTREAM_M9D_EXECUTION", "").strip(),
        "m9e": env.get("UPSTREAM_M9E_EXECUTION", "").strip(),
        "m9f": env.get("UPSTREAM_M9F_EXECUTION", "").strip(),
        "m9g": env.get("UPSTREAM_M9G_EXECUTION", "").strip(),
        "m9h": env.get("UPSTREAM_M9H_EXECUTION", "").strip(),
    }
    missing_upstreams = [k for k, v in upstream_execs.items() if not v]
    if missing_upstreams:
        raise SystemExit(f"Missing upstream execution ids: {','.join(missing_upstreams)}")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    now_dt = datetime.now(timezone.utc)
    handles = parse_handles(HANDLES_PATH)

    s3 = boto3.client("s3", region_name=aws_region)
    ce = boto3.client("ce", region_name=billing_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[str] = []
    budget_errors: list[str] = []
    upload_errors: list[str] = []

    required_cost_handles = {
        "DEV_FULL_MONTHLY_BUDGET_LIMIT_USD": handles.get("DEV_FULL_MONTHLY_BUDGET_LIMIT_USD"),
        "DEV_FULL_BUDGET_ALERT_1_USD": handles.get("DEV_FULL_BUDGET_ALERT_1_USD"),
        "DEV_FULL_BUDGET_ALERT_2_USD": handles.get("DEV_FULL_BUDGET_ALERT_2_USD"),
        "DEV_FULL_BUDGET_ALERT_3_USD": handles.get("DEV_FULL_BUDGET_ALERT_3_USD"),
        "BUDGET_CURRENCY": handles.get("BUDGET_CURRENCY"),
        "COST_CAPTURE_SCOPE": handles.get("COST_CAPTURE_SCOPE"),
        "AWS_COST_CAPTURE_ENABLED": handles.get("AWS_COST_CAPTURE_ENABLED"),
    }
    unresolved = [k for k, v in required_cost_handles.items() if is_placeholder(v)]
    if unresolved:
        blockers.append({"code": "M9-B10", "message": f"Required cost handles unresolved: {','.join(sorted(unresolved))}."})

    handle_evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if handle_evidence_bucket and handle_evidence_bucket != evidence_bucket:
        blockers.append({"code": "M9-B10", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    summary_specs = [
        ("M9.A", upstream_execs["m9a"], "m9a_execution_summary.json", "M9.B_READY"),
        ("M9.B", upstream_execs["m9b"], "m9b_execution_summary.json", "M9.C_READY"),
        ("M9.C", upstream_execs["m9c"], "m9c_execution_summary.json", "M9.D_READY"),
        ("M9.D", upstream_execs["m9d"], "m9d_execution_summary.json", "M9.E_READY"),
        ("M9.E", upstream_execs["m9e"], "m9e_execution_summary.json", "M9.F_READY"),
        ("M9.F", upstream_execs["m9f"], "m9f_execution_summary.json", "M9.G_READY"),
        ("M9.G", upstream_execs["m9g"], "m9g_execution_summary.json", "M9.H_READY"),
        ("M9.H", upstream_execs["m9h"], "m9h_execution_summary.json", "M10_READY"),
    ]

    contract_artifacts = {
        "m9a_handle_closure_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9a']}/m9a_handle_closure_snapshot.json",
        "m9b_handoff_scope_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9b']}/m9b_handoff_scope_snapshot.json",
        "m9c_replay_basis_receipt": f"evidence/dev_full/run_control/{upstream_execs['m9c']}/m9c_replay_basis_receipt.json",
        "m9d_asof_maturity_policy_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9d']}/m9d_asof_maturity_policy_snapshot.json",
        "m9e_leakage_guardrail_report": f"evidence/dev_full/run_control/{upstream_execs['m9e']}/m9e_leakage_guardrail_report.json",
        "m9f_surface_separation_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9f']}/m9f_surface_separation_snapshot.json",
        "m9g_learning_input_readiness_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9g']}/m9g_learning_input_readiness_snapshot.json",
        "m9h_p12_rollup_matrix": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m9h_p12_rollup_matrix.json",
        "m9h_p12_gate_verdict": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m9h_p12_gate_verdict.json",
        "m10_handoff_pack": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m10_handoff_pack.json",
    }

    contract_matrix: list[dict[str, Any]] = []
    for alias, key in contract_artifacts.items():
        row = {"artifact": alias, "s3_key": key, "readable": False, "error": None}
        try:
            s3.head_object(Bucket=evidence_bucket, Key=key)
            row["readable"] = True
        except (BotoCoreError, ClientError) as exc:
            row["error"] = type(exc).__name__
            read_errors.append(f"{alias}:{type(exc).__name__}:{key}")
        contract_matrix.append(row)
    if any(not bool(row["readable"]) for row in contract_matrix):
        blockers.append({"code": "M9-B10", "message": "Required M9 contract artifacts are missing/unreadable."})

    summary_matrix: list[dict[str, Any]] = []
    summary_payloads: dict[str, dict[str, Any]] = {}
    platform_values: list[str] = []
    scenario_values: list[str] = []
    upstream_times: list[datetime] = []
    for phase_name, phase_exec, summary_file, expected_next_gate in summary_specs:
        key = f"evidence/dev_full/run_control/{phase_exec}/{summary_file}"
        row: dict[str, Any] = {
            "phase": phase_name,
            "execution_id": phase_exec,
            "s3_key": key,
            "readable": False,
            "error": None,
            "overall_pass": False,
            "actual_next_gate": "",
            "expected_next_gate": expected_next_gate,
            "next_gate_ok": False,
            "run_scope_ok": False,
        }
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            summary_payloads[phase_name] = payload
            row["readable"] = True
            row["overall_pass"] = bool(payload.get("overall_pass"))
            row["actual_next_gate"] = str(payload.get("next_gate", "")).strip()
            row["next_gate_ok"] = row["actual_next_gate"] == expected_next_gate
            p = str(payload.get("platform_run_id", "")).strip()
            s = str(payload.get("scenario_run_id", "")).strip()
            if p:
                platform_values.append(p)
            if s:
                scenario_values.append(s)
            t = parse_utc(str(payload.get("captured_at_utc", "")).strip())
            if t is not None:
                upstream_times.append(t)
            if phase_name == "M9.H":
                verdict = str(payload.get("verdict", "")).strip()
                if verdict != "ADVANCE_TO_P13":
                    blockers.append({"code": "M9-B10", "message": "M9.H verdict is not ADVANCE_TO_P13."})
            if not row["overall_pass"]:
                blockers.append({"code": "M9-B10", "message": f"{phase_name} summary is not pass."})
            if not row["next_gate_ok"]:
                blockers.append({"code": "M9-B10", "message": f"{phase_name} next_gate mismatch."})
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            row["error"] = type(exc).__name__
            read_errors.append(f"{phase_name}:{type(exc).__name__}:{key}")
            blockers.append({"code": "M9-B10", "message": f"{phase_name} summary unreadable."})
        summary_matrix.append(row)

    platform_unique = sorted(set([x for x in platform_values if x]))
    scenario_unique = sorted(set([x for x in scenario_values if x]))
    platform_run_id = platform_unique[0] if len(platform_unique) == 1 else ""
    scenario_run_id = scenario_unique[0] if len(scenario_unique) == 1 else ""
    if len(platform_unique) != 1:
        blockers.append({"code": "M9-B10", "message": "platform_run_id is inconsistent across M9 summaries."})
    if len(scenario_unique) != 1:
        blockers.append({"code": "M9-B10", "message": "scenario_run_id is inconsistent across M9 summaries."})

    for row in summary_matrix:
        phase_payload = summary_payloads.get(str(row["phase"]), {})
        p = str(phase_payload.get("platform_run_id", "")).strip()
        s = str(phase_payload.get("scenario_run_id", "")).strip()
        row["run_scope_ok"] = bool(platform_run_id and scenario_run_id and p == platform_run_id and s == scenario_run_id)
        if row["readable"] and not row["run_scope_ok"]:
            blockers.append({"code": "M9-B10", "message": f"{row['phase']} run-scope mismatch."})

    phase_start = min(upstream_times).isoformat().replace("+00:00", "Z") if upstream_times else captured_at

    try:
        monthly_limit = as_decimal(required_cost_handles["DEV_FULL_MONTHLY_BUDGET_LIMIT_USD"], "DEV_FULL_MONTHLY_BUDGET_LIMIT_USD")
        alert_1 = as_decimal(required_cost_handles["DEV_FULL_BUDGET_ALERT_1_USD"], "DEV_FULL_BUDGET_ALERT_1_USD")
        alert_2 = as_decimal(required_cost_handles["DEV_FULL_BUDGET_ALERT_2_USD"], "DEV_FULL_BUDGET_ALERT_2_USD")
        alert_3 = as_decimal(required_cost_handles["DEV_FULL_BUDGET_ALERT_3_USD"], "DEV_FULL_BUDGET_ALERT_3_USD")
    except ValueError as exc:
        budget_errors.append(str(exc))
        monthly_limit = Decimal("1")
        alert_1 = Decimal("1")
        alert_2 = Decimal("1")
        alert_3 = Decimal("1")
    if not (alert_1 < alert_2 < alert_3 <= monthly_limit):
        budget_errors.append("budget_threshold_order_invalid")
    if budget_errors:
        blockers.append({"code": "M9-B10", "message": "Budget envelope inputs are invalid for M9.I closure."})

    aws_capture_enabled = bool(required_cost_handles["AWS_COST_CAPTURE_ENABLED"])
    cost_capture_scope = str(required_cost_handles["COST_CAPTURE_SCOPE"])
    budget_currency = str(required_cost_handles["BUDGET_CURRENCY"])
    databricks_capture_enabled = bool(handles.get("DATABRICKS_COST_CAPTURE_ENABLED", False))

    aws_mtd: Decimal | None = None
    aws_unit: str | None = budget_currency
    ce_error: str | None = None
    if aws_capture_enabled:
        start_date = month_start_utc(now_dt)
        end_date = tomorrow_utc(now_dt)
        aws_mtd, aws_unit, ce_error = aws_mtd_cost(ce, start_date, end_date)
        if ce_error:
            blockers.append({"code": "M9-B10", "message": f"AWS cost capture failed ({ce_error})."})
    else:
        blockers.append({"code": "M9-B10", "message": "AWS_COST_CAPTURE_ENABLED must be true for M9.I closure."})

    if aws_mtd is not None and aws_mtd >= alert_3:
        blockers.append(
            {
                "code": "M9-B10",
                "message": (
                    "Phase cost hard-stop triggered at alert_3 "
                    f"(aws_mtd_cost={str(aws_mtd)}, alert_3={str(alert_3)})."
                ),
            }
        )

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    verdict = "ADVANCE_TO_M9J" if overall_pass else "HOLD_REMEDIATE"
    next_gate = "M9.J_READY" if overall_pass else "HOLD_REMEDIATE"

    contract_upstream_required_count = len(contract_artifacts) + len(summary_specs)
    contract_upstream_readable_count = sum(1 for row in contract_matrix if bool(row["readable"])) + sum(
        1 for row in summary_matrix if bool(row["readable"])
    )
    contract_output_required_count = 2
    contract_output_published_count = 0
    contract_total_required_count = contract_upstream_required_count + contract_output_required_count

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    durable_keys = {
        "m9_phase_budget_envelope_key": f"{run_control_prefix}/m9_phase_budget_envelope.json",
        "m9_phase_cost_outcome_receipt_key": f"{run_control_prefix}/m9_phase_cost_outcome_receipt.json",
        "m9i_blocker_register_key": f"{run_control_prefix}/m9i_blocker_register.json",
        "m9i_execution_summary_key": f"{run_control_prefix}/m9i_execution_summary.json",
    }

    m9_contract_parity = {
        "required_artifact_count_total": contract_total_required_count,
        "required_upstream_artifact_count": contract_upstream_required_count,
        "readable_upstream_artifact_count": contract_upstream_readable_count,
        "required_m9i_output_count": contract_output_required_count,
        "published_m9i_output_count": contract_output_published_count,
        "all_required_available": bool(
            contract_upstream_readable_count == contract_upstream_required_count
            and contract_output_published_count == contract_output_required_count
        ),
    }

    phase_budget_envelope = {
        "phase": "M9.I",
        "phase_id": "M9",
        "phase_execution_id": execution_id,
        "captured_at_utc": captured_at,
        "budget_currency": budget_currency,
        "monthly_limit_amount": str(monthly_limit),
        "alert_1_amount": str(alert_1),
        "alert_2_amount": str(alert_2),
        "alert_3_amount": str(alert_3),
        "cost_capture_scope": cost_capture_scope,
        "aws_cost_capture_enabled": aws_capture_enabled,
        "databricks_cost_capture_enabled": databricks_capture_enabled,
        "phase_window": {"start_utc": phase_start, "end_utc": captured_at},
        "m9_contract_parity": m9_contract_parity,
        "overall_pass": "M9-B10" not in {item["code"] for item in blockers},
        "blockers": [item for item in blockers if item["code"] in {"M9-B10"}],
    }

    phase_cost_outcome_receipt = {
        "phase_id": "M9",
        "phase": "M9.I",
        "phase_execution_id": execution_id,
        "window_start_utc": phase_start,
        "window_end_utc": captured_at,
        "spend_amount": str(aws_mtd) if aws_mtd is not None else None,
        "spend_currency": aws_unit or budget_currency,
        "artifacts_emitted": [
            "m9_phase_budget_envelope.json",
            "m9_phase_cost_outcome_receipt.json",
            "m9i_execution_summary.json",
            "m9i_blocker_register.json",
        ],
        "decision_or_risk_retired": "M9 cost-outcome closure completed; P12 verdict + M10 handoff economics are now explicit.",
        "source_components": {
            "aws_mtd_cost_amount": str(aws_mtd) if aws_mtd is not None else None,
            "aws_currency": aws_unit or budget_currency,
            "databricks_mtd_cost_amount": None,
            "databricks_capture_mode": "DEFERRED" if not databricks_capture_enabled else "ENABLED_PENDING",
        },
    }

    blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M9.I",
        "phase_id": "M9",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "contract_matrix": contract_matrix,
        "summary_matrix": summary_matrix,
        "read_errors": read_errors,
        "budget_errors": budget_errors,
        "ce_error": ce_error,
    }

    execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M9.I",
        "phase_id": "M9",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "upstream_refs": {
            "m9a_execution_id": upstream_execs["m9a"],
            "m9b_execution_id": upstream_execs["m9b"],
            "m9c_execution_id": upstream_execs["m9c"],
            "m9d_execution_id": upstream_execs["m9d"],
            "m9e_execution_id": upstream_execs["m9e"],
            "m9f_execution_id": upstream_execs["m9f"],
            "m9g_execution_id": upstream_execs["m9g"],
            "m9h_execution_id": upstream_execs["m9h"],
        },
        "m9_contract_parity": m9_contract_parity,
        "durable_artifacts": durable_keys,
    }

    artifacts = {
        "m9_phase_budget_envelope.json": phase_budget_envelope,
        "m9_phase_cost_outcome_receipt.json": phase_cost_outcome_receipt,
        "m9i_blocker_register.json": blocker_register,
        "m9i_execution_summary.json": execution_summary,
    }
    write_local_artifacts(run_dir, artifacts)

    for name, payload in artifacts.items():
        key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, key, payload)
            if name in {"m9_phase_budget_envelope.json", "m9_phase_cost_outcome_receipt.json"}:
                contract_output_published_count += 1
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append(f"{name}:{type(exc).__name__}:{key}")

    if upload_errors:
        blockers = list(blockers)
        blockers.append({"code": "M9-B11", "message": "Failed to publish/readback M9.I artifact set."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m9_contract_parity["published_m9i_output_count"] = contract_output_published_count
    m9_contract_parity["all_required_available"] = bool(
        contract_upstream_readable_count == contract_upstream_required_count
        and contract_output_published_count == contract_output_required_count
    )
    if not m9_contract_parity["all_required_available"]:
        blockers = list(blockers)
        blockers.append({"code": "M9-B10", "message": "M9 artifact contract parity is incomplete after M9.I publication."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    execution_summary["overall_pass"] = overall_pass
    execution_summary["blocker_count"] = len(blockers)
    execution_summary["verdict"] = verdict
    execution_summary["next_gate"] = next_gate
    execution_summary["m9_contract_parity"] = m9_contract_parity
    blocker_register["blockers"] = blockers
    blocker_register["blocker_count"] = len(blockers)
    blocker_register["upload_errors"] = upload_errors
    phase_budget_envelope["m9_contract_parity"] = m9_contract_parity
    phase_budget_envelope["overall_pass"] = "M9-B10" not in {item["code"] for item in blockers}
    phase_budget_envelope["blockers"] = [item for item in blockers if item["code"] in {"M9-B10"}]

    artifacts["m9_phase_budget_envelope.json"] = phase_budget_envelope
    artifacts["m9i_execution_summary.json"] = execution_summary
    artifacts["m9i_blocker_register.json"] = blocker_register
    write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": execution_summary["overall_pass"],
        "blocker_count": execution_summary["blocker_count"],
        "verdict": execution_summary["verdict"],
        "next_gate": execution_summary["next_gate"],
        "m9_contract_parity": m9_contract_parity,
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{evidence_bucket}/{run_control_prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
