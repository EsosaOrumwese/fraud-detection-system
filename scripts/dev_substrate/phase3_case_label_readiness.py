#!/usr/bin/env python3
"""Execute a bounded Phase 3 Case + Label correctness slice on AWS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = str(env.get("PYTHONPATH") or "").strip()
    root = str(REPO_ROOT)
    env["PYTHONPATH"] = root if not existing else root + os.pathsep + existing
    return env


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cmd(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], check=True, env=child_env())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def fresh_execution_id() -> str:
    return f"phase3_case_label_{utc_stamp()}"


def fresh_platform_run_id() -> str:
    return f"platform_{utc_stamp()}"


def fresh_scenario_run_id(*, execution_id: str, window_label: str, platform_run_id: str) -> str:
    seed = f"{execution_id}:{window_label}:{platform_run_id}"
    return hashlib.md5(seed.encode("utf-8"), usedforsecurity=False).hexdigest()


def stop_wsp_tasks(region: str, receipt_path: Path, reason: str) -> None:
    code = f"""
from datetime import datetime, timezone
import json
from pathlib import Path
import boto3

ecs = boto3.client('ecs', region_name={region!r})
cluster = 'fraud-platform-dev-full-wsp-ephemeral'
task_arns = ecs.list_tasks(cluster=cluster, desiredStatus='RUNNING').get('taskArns', [])
stopped = []
if task_arns:
    described = ecs.describe_tasks(cluster=cluster, tasks=task_arns).get('tasks', [])
    for task in described:
        task_arn = str(task.get('taskArn') or '').strip()
        if not task_arn:
            continue
        ecs.stop_task(cluster=cluster, task=task_arn, reason={reason!r}[:255])
        stopped.append(task_arn.rsplit('/', 1)[-1])
payload = {{
    'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    'cluster': cluster,
    'stopped_tasks': stopped,
    'stopped_task_count': len(stopped),
    'reason': {reason!r},
}}
Path({str(receipt_path)!r}).write_text(json.dumps(payload, indent=2) + "\\n", encoding='utf-8')
"""
    subprocess.run([sys.executable, "-c", code], check=True, env=child_env())


def wait_dispatch_with_sampling(
    *,
    dispatch_args: list[str],
    execution_id: str,
    run_control_root: str,
    state_id: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
    warmup_seconds: int,
    sample_period_seconds: int,
) -> None:
    proc = subprocess.Popen([sys.executable, *dispatch_args], env=child_env())
    try:
        time.sleep(max(10, int(warmup_seconds)))
        sample_index = 1
        while proc.poll() is None:
            run_cmd(
                [
                    "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
                    "--run-control-root",
                    run_control_root,
                    "--pr3-execution-id",
                    execution_id,
                    "--state-id",
                    state_id,
                    "--snapshot-label",
                    f"during_{sample_index}",
                    "--namespace",
                    namespace,
                    "--case-labels-namespace",
                    case_labels_namespace,
                    "--platform-run-id",
                    platform_run_id,
                ]
            )
            sample_index += 1
            time.sleep(max(5, int(sample_period_seconds)))
    finally:
        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, dispatch_args)


def write_charter(
    path: Path,
    *,
    execution_id: str,
    platform_run_id: str,
    scenario_run_id: str,
    window_start_ts_utc: str,
    window_end_ts_utc: str,
    expected_window_eps: float,
    min_processed_events: int,
    duration_seconds: int,
) -> None:
    payload = {
        "phase": "PHASE3",
        "generated_at_utc": now_utc(),
        "generated_by": "phase3-case-label-readiness",
        "version": "1.0.0",
        "execution_id": execution_id,
        "mission_id": "dev_full_phase3_case_label",
        "mission_binding": {
            "window_start_ts_utc": window_start_ts_utc,
            "window_end_ts_utc": window_end_ts_utc,
            "as_of_time_utc": window_end_ts_utc,
            "label_maturity_lag": "3d",
        },
        "phase3_slice": {
            "goal": "bounded_case_label_plane_correctness",
            "expected_window_eps": float(expected_window_eps),
            "min_processed_events": int(min_processed_events),
            "duration_seconds": int(duration_seconds),
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
        },
    }
    write_json(path, payload)


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute bounded Phase 3 Case + Label readiness.")
    ap.add_argument("--execution-id", default="")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="fraud-platform-case-labels")
    ap.add_argument("--scenario-id", default="baseline_v1")
    ap.add_argument("--window-start-ts-utc", default="2026-02-26T00:00:00Z")
    ap.add_argument("--window-end-ts-utc", default="2026-03-05T00:00:00Z")
    ap.add_argument("--lane-count", type=int, default=54)
    ap.add_argument("--target-request-rate-eps", type=float, default=3000.0)
    ap.add_argument("--expected-window-eps", type=float, default=3000.0)
    ap.add_argument("--min-processed-events", type=int, default=100000)
    ap.add_argument("--duration-seconds", type=int, default=60)
    ap.add_argument("--warmup-seconds", type=int, default=15)
    ap.add_argument("--sample-period-seconds", type=int, default=15)
    ap.add_argument("--early-cutoff-seconds", type=int, default=30)
    ap.add_argument("--early-cutoff-floor-ratio", type=float, default=0.70)
    ap.add_argument("--stream-speedup", type=float, default=52.9)
    ap.add_argument("--output-concurrency", type=int, default=4)
    ap.add_argument("--ig-push-concurrency", type=int, default=1)
    ap.add_argument("--http-pool-maxsize", type=int, default=512)
    ap.add_argument("--traffic-output-ids", default="s3_event_stream_with_fraud_6B")
    ap.add_argument("--context-output-ids", default="arrival_events_5B,s1_arrival_entities_6B,s3_flow_anchor_with_fraud_6B")
    ap.add_argument("--wsp-task-cpu", type=int, default=256)
    ap.add_argument("--wsp-task-memory", type=int, default=1024)
    ap.add_argument("--cost-budget-envelope-usd", type=float, default=15.0)
    args = ap.parse_args()

    execution_id = str(args.execution_id).strip() or fresh_execution_id()
    root = Path(args.run_control_root) / execution_id
    root.mkdir(parents=True, exist_ok=True)

    window_label = "phase3_case_label"
    platform_run_id = fresh_platform_run_id()
    scenario_run_id = fresh_scenario_run_id(
        execution_id=execution_id,
        window_label=window_label,
        platform_run_id=platform_run_id,
    )

    write_charter(
        root / "g3a_run_charter.active.json",
        execution_id=execution_id,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        window_start_ts_utc=str(args.window_start_ts_utc).strip(),
        window_end_ts_utc=str(args.window_end_ts_utc).strip(),
        expected_window_eps=float(args.expected_window_eps),
        min_processed_events=int(args.min_processed_events),
        duration_seconds=int(args.duration_seconds),
    )
    write_json(
        root / "phase3_runtime_identity.json",
        {
            "generated_at_utc": now_utc(),
            "execution_id": execution_id,
            "window_label": window_label,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "scenario_id": str(args.scenario_id).strip(),
        },
    )

    checkpoint_attempt_id = utc_stamp()
    try:
        run_cmd(
            [
                "scripts/dev_substrate/pr3_rtdl_materialize.py",
                "--pr3-execution-id",
                execution_id,
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--region",
                args.aws_region,
                "--namespace",
                args.namespace,
                "--case-labels-namespace",
                args.case_labels_namespace,
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/pr3_control_plane_bootstrap.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--platform-run-id",
                platform_run_id,
                "--aws-region",
                args.aws_region,
                "--scenario-id",
                args.scenario_id,
                "--namespace",
                args.namespace,
                "--bootstrap-summary-name",
                "phase3_control_plane_bootstrap.json",
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/pr3_runtime_warm_gate.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--state-id",
                "P3",
                "--namespace",
                args.namespace,
                "--case-labels-namespace",
                args.case_labels_namespace,
                "--platform-run-id",
                platform_run_id,
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--state-id",
                "P3",
                "--snapshot-label",
                "pre",
                "--namespace",
                args.namespace,
                "--case-labels-namespace",
                args.case_labels_namespace,
                "--platform-run-id",
                platform_run_id,
            ]
        )

        stop_wsp_tasks(args.aws_region, root / "phase3_case_label_preflight_wsp_cleanup.json", "Phase3 preflight stale WSP cleanup")

        dispatch_args = [
            "scripts/dev_substrate/pr3_wsp_replay_dispatch.py",
            "--run-control-root",
            args.run_control_root,
            "--pr3-execution-id",
            execution_id,
            "--state-id",
            "P3",
            "--window-label",
            window_label,
            "--artifact-prefix",
            "phase3_case_label",
            "--blocker-prefix",
            "PHASE3.CASELABEL",
            "--region",
            args.aws_region,
            "--platform-run-id",
            platform_run_id,
            "--scenario-run-id",
            scenario_run_id,
            "--checkpoint-attempt-id",
            checkpoint_attempt_id,
            "--lane-count",
            str(args.lane_count),
            "--expected-window-eps",
            str(args.expected_window_eps),
            "--target-request-rate-eps",
            str(args.target_request_rate_eps),
            "--duration-seconds",
            str(args.duration_seconds),
            "--warmup-seconds",
            str(args.warmup_seconds),
            "--early-cutoff-seconds",
            str(args.early_cutoff_seconds),
            "--early-cutoff-floor-ratio",
            str(args.early_cutoff_floor_ratio),
            "--stream-speedup",
            str(args.stream_speedup),
            "--output-concurrency",
            str(args.output_concurrency),
            "--ig-push-concurrency",
            str(args.ig_push_concurrency),
            "--http-pool-maxsize",
            str(args.http_pool_maxsize),
            "--max-latency-p95-ms",
            "350",
            "--max-latency-p99-ms",
            "700",
            "--traffic-output-ids",
            args.traffic_output_ids,
            "--context-output-ids",
            args.context_output_ids,
            "--skip-runtime-identity-probe",
        ]
        wait_dispatch_with_sampling(
            dispatch_args=dispatch_args,
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            state_id="P3",
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
            warmup_seconds=max(10, int(args.warmup_seconds)),
            sample_period_seconds=max(5, int(args.sample_period_seconds)),
        )

        run_cmd(
            [
                "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--state-id",
                "P3",
                "--snapshot-label",
                "post",
                "--namespace",
                args.namespace,
                "--case-labels-namespace",
                args.case_labels_namespace,
                "--platform-run-id",
                platform_run_id,
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/pr3_s4_cost_guardrail.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--state-id",
                "P3",
                "--artifact-prefix",
                "phase3_case_label",
                "--aws-region",
                args.aws_region,
                "--cluster",
                "fraud-platform-dev-full-wsp-ephemeral",
                "--wsp-task-cpu",
                str(args.wsp_task_cpu),
                "--wsp-task-memory",
                str(args.wsp_task_memory),
                "--budget-envelope-usd",
                str(args.cost_budget_envelope_usd),
                "--receipt-path",
                "phase3_case_label_cost_receipt.json",
                "--drill-path",
                "phase3_case_label_cost_guardrail.json",
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/phase3_case_label_rollup.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
            ]
        )
    finally:
        stop_wsp_tasks(args.aws_region, root / "phase3_case_label_final_wsp_cleanup.json", "Phase3 final WSP cleanup")


if __name__ == "__main__":
    main()
