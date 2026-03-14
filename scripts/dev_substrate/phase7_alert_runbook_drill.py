#!/usr/bin/env python3
"""Bounded Phase 7 alert-to-runbook drill on the live CloudWatch operator surface."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


RUNBOOK_PATH = "docs/runbooks/dev_full_phase7_ops_gov_runbook.md"
OPERATIONS_DASHBOARD = "fraud-platform-dev-full-operations"
COST_DASHBOARD = "fraud-platform-dev-full-cost-guardrail"
DEFAULT_ALARM = "fraud-platform-dev-full-ig-lambda-errors"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dashboard_markdowns(cw: Any, name: str) -> list[str]:
    body = json.loads(cw.get_dashboard(DashboardName=name)["DashboardBody"])
    texts: list[str] = []
    for widget in body.get("widgets") or []:
        props = dict(widget.get("properties") or {})
        markdown = str(props.get("markdown") or "").strip()
        if markdown:
            texts.append(markdown)
    return texts


def alarm_history(cw: Any, alarm_name: str, limit: int = 20) -> list[dict[str, Any]]:
    items = cw.describe_alarm_history(
        AlarmName=alarm_name,
        HistoryItemType="StateUpdate",
        MaxRecords=limit,
    ).get("AlarmHistoryItems") or []
    return [
        {
            "timestamp_utc": row["Timestamp"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "summary": str(row.get("HistorySummary") or ""),
            "data": str(row.get("HistoryData") or ""),
        }
        for row in items
    ]


def describe_state(cw: Any, alarm_name: str) -> dict[str, str]:
    alarms = cw.describe_alarms(AlarmNames=[alarm_name]).get("MetricAlarms") or []
    if not alarms:
        return {"state": "", "reason": ""}
    row = alarms[0]
    return {
        "state": str(row.get("StateValue") or ""),
        "reason": str(row.get("StateReason") or ""),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Bounded Phase 7 alert-to-runbook drill")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--alarm-name", default=DEFAULT_ALARM)
    ap.add_argument("--pause-seconds", type=float, default=5.0)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    cw = boto3.client("cloudwatch", region_name=args.aws_region)

    blockers: list[str] = []
    runbook = Path(RUNBOOK_PATH)
    if not runbook.exists():
        blockers.append("PHASE7_B_RUNBOOK_MISSING")

    operations_markdown = []
    cost_markdown = []
    try:
        operations_markdown = dashboard_markdowns(cw, OPERATIONS_DASHBOARD)
        cost_markdown = dashboard_markdowns(cw, COST_DASHBOARD)
    except (BotoCoreError, ClientError, KeyError, json.JSONDecodeError):
        blockers.append("PHASE7_B_DASHBOARD_READ_FAIL")

    if not any(RUNBOOK_PATH in text for text in operations_markdown):
        blockers.append("PHASE7_B_OPERATIONS_RUNBOOK_LINK_MISSING")
    if not any(RUNBOOK_PATH in text for text in cost_markdown):
        blockers.append("PHASE7_B_COST_RUNBOOK_LINK_MISSING")

    state_before = {}
    history_before = []
    state_after_alarm = {}
    history_after_alarm = []
    state_after_ok = {}
    history_after_ok = []

    alarm_reason = f"Phase7 alert drill alarm state set at {now_utc()}"
    ok_reason = f"Phase7 alert drill restored OK at {now_utc()}"
    drill_error = ""

    try:
        state_before = describe_state(cw, args.alarm_name)
        history_before = alarm_history(cw, args.alarm_name)

        cw.set_alarm_state(
            AlarmName=args.alarm_name,
            StateValue="ALARM",
            StateReason=alarm_reason,
        )
        time.sleep(args.pause_seconds)
        state_after_alarm = describe_state(cw, args.alarm_name)
        history_after_alarm = alarm_history(cw, args.alarm_name)

        cw.set_alarm_state(
            AlarmName=args.alarm_name,
            StateValue="OK",
            StateReason=ok_reason,
        )
        time.sleep(args.pause_seconds)
        state_after_ok = describe_state(cw, args.alarm_name)
        history_after_ok = alarm_history(cw, args.alarm_name)
    except (BotoCoreError, ClientError) as exc:
        drill_error = f"{type(exc).__name__}:{exc}"
        blockers.append("PHASE7_B_ALERT_STATE_DRILL_FAIL")

    alarm_seen = any(alarm_reason in row["data"] or alarm_reason in row["summary"] for row in history_after_alarm)
    ok_seen = any(ok_reason in row["data"] or ok_reason in row["summary"] for row in history_after_ok)
    if not drill_error and not alarm_seen:
        blockers.append("PHASE7_B_ALERT_ALARM_STATE_NOT_RECORDED")
    if not drill_error and not ok_seen:
        blockers.append("PHASE7_B_ALERT_OK_STATE_NOT_RECORDED")

    summary = {
        "phase": "PHASE7",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "alarm_name": args.alarm_name,
        "runbook_path": RUNBOOK_PATH,
        "operations_dashboard": OPERATIONS_DASHBOARD,
        "cost_dashboard": COST_DASHBOARD,
        "operations_markdown": operations_markdown,
        "cost_markdown": cost_markdown,
        "state_before": state_before,
        "history_before": history_before,
        "state_after_alarm": state_after_alarm,
        "history_after_alarm": history_after_alarm,
        "state_after_ok": state_after_ok,
        "history_after_ok": history_after_ok,
        "alarm_reason": alarm_reason,
        "ok_reason": ok_reason,
        "drill_error": drill_error,
        "overall_pass": len(set(blockers)) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    receipt = {
        "phase": "PHASE7",
        "generated_at_utc": summary["generated_at_utc"],
        "execution_id": args.execution_id,
        "verdict": "PHASE7_ALERT_DRILL_READY" if summary["overall_pass"] else "PHASE7_ALERT_DRILL_HOLD",
        "open_blockers": len(summary["blocker_ids"]),
        "blocker_ids": summary["blocker_ids"],
    }
    dump_json(root / "phase7_alert_runbook_drill.json", summary)
    dump_json(root / "phase7_alert_runbook_drill_receipt.json", receipt)

    if not summary["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
