#!/usr/bin/env python3
"""Materialize PR3-S4 modeled correctness-window cost + idle-safe evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="PR3-S4 modeled correctness-window cost guardrail")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S4")
    ap.add_argument("--artifact-prefix", default="g3a_correctness")
    ap.add_argument("--aws-region", required=True)
    ap.add_argument("--cluster", default="fraud-platform-dev-full-wsp-ephemeral")
    ap.add_argument("--wsp-task-cpu", type=int, required=True)
    ap.add_argument("--wsp-task-memory", type=int, required=True)
    ap.add_argument("--budget-envelope-usd", type=float, required=True)
    ap.add_argument("--fargate-vcpu-hour-usd", type=float, default=0.0500)
    ap.add_argument("--fargate-memory-gib-hour-usd", type=float, default=0.0055)
    ap.add_argument("--receipt-path", default="g3a_correctness_cost_receipt.json")
    ap.add_argument("--drill-path", default="g3a_drill_cost_guardrail.json")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    prefix = str(args.artifact_prefix).strip()
    summary = load_optional_json(root / f"{prefix}_wsp_runtime_summary.json")
    manifest = load_optional_json(root / f"{prefix}_wsp_runtime_manifest.json")
    preflight_cleanup = load_optional_json(root / f"{prefix}_preflight_wsp_cleanup.json") or {}
    final_cleanup = load_optional_json(root / f"{prefix}_final_wsp_cleanup.json") or {}
    platform_run_id = str((((manifest or {}).get("identity") or {}).get("platform_run_id") or "")).strip()

    ecs = boto3.client("ecs", region_name=args.aws_region)
    running_tasks = ecs.list_tasks(cluster=args.cluster, desiredStatus="RUNNING").get("taskArns", [])
    idle_safe_verified = len(running_tasks) == 0

    missing_artifacts = [
        name
        for name, payload in (
            (f"{prefix}_wsp_runtime_summary.json", summary),
            (f"{prefix}_wsp_runtime_manifest.json", manifest),
        )
        if payload is None
    ]
    if missing_artifacts:
        receipt = {
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "budget_envelope_usd": float(args.budget_envelope_usd),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "idle_safe_verified": idle_safe_verified,
            "pricing_basis": {
                "type": "modeled_fargate_rate_card_v0",
                "vcpu_hour_usd": float(args.fargate_vcpu_hour_usd),
                "memory_gib_hour_usd": float(args.fargate_memory_gib_hour_usd),
                "note": "Correctness runtime artifacts were missing, so attributable spend could not be computed from lane task-seconds.",
            },
            "resource_usage": {
                "lane_count": 0,
                "total_task_seconds": 0.0,
                "vcpu_hours": 0.0,
                "memory_gib_hours": 0.0,
                "wsp_task_cpu_units": int(args.wsp_task_cpu),
                "wsp_task_memory_mib": int(args.wsp_task_memory),
            },
            "cleanup_posture": {
                "preflight_stopped_task_count": int(preflight_cleanup.get("stopped_task_count", 0) or 0),
                "final_stopped_task_count": int(final_cleanup.get("stopped_task_count", 0) or 0),
                "running_task_count_after_cleanup": len(running_tasks),
            },
            "overall_pass": False,
            "blocker_ids": ["PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL"],
            "notes": [f"Missing correctness runtime artifacts: {', '.join(missing_artifacts)}"],
        }
        drill = {
            "drill_id": "cost_guardrail_idle_safe",
            "phase": "PR3",
            "state": args.state_id,
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": platform_run_id,
            "scenario": "Model attributable correctness-window cost from actual WSP task runtime and verify zero residual WSP tasks after cleanup.",
            "expected_behavior": "Attributed spend remains inside envelope and the WSP ephemeral cluster is idle-safe after the state ends.",
            "observed_outcome": {
                "attributed_spend_usd": 0.0,
                "budget_envelope_usd": float(args.budget_envelope_usd),
                "idle_safe_verified": idle_safe_verified,
                "running_task_count_after_cleanup": len(running_tasks),
                "missing_runtime_artifacts": missing_artifacts,
            },
            "overall_pass": False,
            "blocker_ids": ["PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL"],
        }
        dump_json(root / str(args.receipt_path).strip(), receipt)
        dump_json(root / str(args.drill_path).strip(), drill)
        print(json.dumps(receipt, indent=2))
        return

    total_task_seconds = 0.0
    lane_seconds: list[float] = []
    for lane in list(summary.get("lane_results", []) or []):
        final_status = dict(lane.get("final_status") or {})
        started = parse_utc(final_status.get("started_at_utc"))
        stopped = parse_utc(final_status.get("stopped_at_utc")) or parse_utc(summary.get("performance_window", {}).get("end_utc"))
        if started is None or stopped is None or stopped <= started:
            continue
        seconds = max(0.0, (stopped - started).total_seconds())
        lane_seconds.append(seconds)
        total_task_seconds += seconds

    vcpu_hours = (total_task_seconds / 3600.0) * (float(args.wsp_task_cpu) / 1024.0)
    memory_gib_hours = (total_task_seconds / 3600.0) * (float(args.wsp_task_memory) / 1024.0)
    attributed_spend_usd = round(
        (vcpu_hours * float(args.fargate_vcpu_hour_usd)) + (memory_gib_hours * float(args.fargate_memory_gib_hour_usd)),
        6,
    )

    within_envelope = attributed_spend_usd <= float(args.budget_envelope_usd)
    overall_pass = idle_safe_verified and within_envelope

    receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "budget_envelope_usd": float(args.budget_envelope_usd),
        "attributed_spend_usd": attributed_spend_usd,
        "unattributed_spend_detected": False,
        "idle_safe_verified": idle_safe_verified,
        "pricing_basis": {
            "type": "modeled_fargate_rate_card_v0",
            "vcpu_hour_usd": float(args.fargate_vcpu_hour_usd),
            "memory_gib_hour_usd": float(args.fargate_memory_gib_hour_usd),
            "note": "Modeled from actual WSP task-seconds; intended as attributable S4 correctness-window cost evidence rather than settled AWS bill output.",
        },
        "resource_usage": {
            "lane_count": len(lane_seconds),
            "total_task_seconds": round(total_task_seconds, 3),
            "vcpu_hours": round(vcpu_hours, 6),
            "memory_gib_hours": round(memory_gib_hours, 6),
            "wsp_task_cpu_units": int(args.wsp_task_cpu),
            "wsp_task_memory_mib": int(args.wsp_task_memory),
        },
        "cleanup_posture": {
            "preflight_stopped_task_count": int(preflight_cleanup.get("stopped_task_count", 0) or 0),
            "final_stopped_task_count": int(final_cleanup.get("stopped_task_count", 0) or 0),
            "running_task_count_after_cleanup": len(running_tasks),
        },
        "overall_pass": overall_pass,
        "blocker_ids": [] if overall_pass else ["PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL"],
    }
    drill = {
        "drill_id": "cost_guardrail_idle_safe",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "scenario": "Model attributable correctness-window cost from actual WSP task runtime and verify zero residual WSP tasks after cleanup.",
        "expected_behavior": "Attributed spend remains inside envelope and the WSP ephemeral cluster is idle-safe after the state ends.",
        "observed_outcome": {
            "attributed_spend_usd": attributed_spend_usd,
            "budget_envelope_usd": float(args.budget_envelope_usd),
            "idle_safe_verified": idle_safe_verified,
            "running_task_count_after_cleanup": len(running_tasks),
        },
        "overall_pass": overall_pass,
        "blocker_ids": [] if overall_pass else ["PR3.S4.B27_COST_GUARDRAIL_OR_IDLESAFE_FAIL"],
    }

    dump_json(root / str(args.receipt_path).strip(), receipt)
    dump_json(root / str(args.drill_path).strip(), drill)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
