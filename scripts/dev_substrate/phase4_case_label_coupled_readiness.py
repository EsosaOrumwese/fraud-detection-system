#!/usr/bin/env python3
"""Execute bounded Phase 4 coupled-network readiness on AWS."""

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
SRC_ROOT = REPO_ROOT / "src"


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = str(env.get("PYTHONPATH") or "").strip()
    roots = os.pathsep.join([str(SRC_ROOT), str(REPO_ROOT)])
    env["PYTHONPATH"] = roots if not existing else roots + os.pathsep + existing
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
    return f"phase4_case_label_coupled_{utc_stamp()}"


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


def write_charter(
    path: Path,
    *,
    execution_id: str,
    platform_run_id: str,
    scenario_run_id: str,
    window_start_ts_utc: str,
    window_end_ts_utc: str,
    steady_eps: float,
    burst_eps: float,
    duration_seconds: int,
) -> None:
    payload = {
        "phase": "PHASE4",
        "generated_at_utc": now_utc(),
        "generated_by": "phase4-case-label-coupled-readiness",
        "version": "1.0.0",
        "execution_id": execution_id,
        "mission_id": "dev_full_phase4_case_label_coupled",
        "mission_binding": {
            "window_start_ts_utc": window_start_ts_utc,
            "window_end_ts_utc": window_end_ts_utc,
            "as_of_time_utc": window_end_ts_utc,
            "label_maturity_lag": "3d",
        },
        "phase4_slice": {
            "goal": "bounded_case_label_coupled_network_validation",
            "steady_eps": float(steady_eps),
            "burst_eps": float(burst_eps),
            "duration_seconds": int(duration_seconds),
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
        },
    }
    write_json(path, payload)


def materialize_runtime(
    *,
    execution_id: str,
    platform_run_id: str,
    scenario_run_id: str,
    aws_region: str,
    namespace: str,
    case_labels_namespace: str,
) -> None:
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
            aws_region,
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
        ]
    )


def warm_gate_runtime(
    *,
    execution_id: str,
    run_control_root: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
    expected_case_label_scenario_run_id: str,
) -> None:
    run_cmd(
        [
            "scripts/dev_substrate/pr3_runtime_warm_gate.py",
            "--run-control-root",
            run_control_root,
            "--pr3-execution-id",
            execution_id,
            "--state-id",
            "S4",
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--platform-run-id",
            platform_run_id,
            "--expected-case-label-scenario-run-id",
            expected_case_label_scenario_run_id,
        ]
    )


def capture_snapshot(
    *,
    execution_id: str,
    run_control_root: str,
    state_id: str,
    snapshot_label: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
) -> None:
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
            snapshot_label,
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--platform-run-id",
            platform_run_id,
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute bounded Phase 4 coupled-network readiness.")
    ap.add_argument("--execution-id", default="")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="fraud-platform-case-labels")
    ap.add_argument("--scenario-id", default="baseline_v1")
    ap.add_argument("--window-start-ts-utc", default="2026-02-26T00:00:00Z")
    ap.add_argument("--window-end-ts-utc", default="2026-03-05T00:00:00Z")
    ap.add_argument("--lane-count", type=int, default=54)
    ap.add_argument("--prewarm-duration-seconds", type=int, default=45)
    ap.add_argument("--prewarm-target-request-rate-eps", type=float, default=1500.0)
    ap.add_argument("--prewarm-expected-window-eps", type=float, default=0.0)
    ap.add_argument("--prewarm-ig-push-concurrency", type=int, default=1)
    ap.add_argument("--post-prewarm-settle-seconds", type=int, default=10)
    ap.add_argument("--scored-activation-duration-seconds", type=int, default=20)
    ap.add_argument("--scored-activation-target-request-rate-eps", type=float, default=1500.0)
    ap.add_argument("--scored-activation-expected-window-eps", type=float, default=0.0)
    ap.add_argument("--scored-activation-ig-push-concurrency", type=int, default=1)
    ap.add_argument("--post-scored-activation-settle-seconds", type=int, default=10)
    ap.add_argument("--steady-seconds", type=int, default=90)
    ap.add_argument("--burst-seconds", type=int, default=2)
    ap.add_argument("--recovery-seconds", type=int, default=180)
    ap.add_argument("--presteady-seconds", type=int, default=60)
    ap.add_argument("--presteady-eps", type=float, default=1500.0)
    ap.add_argument("--steady-eps", type=float, default=3000.0)
    ap.add_argument("--burst-eps", type=float, default=6000.0)
    ap.add_argument("--recovery-bound-seconds", type=float, default=180.0)
    ap.add_argument("--recovery-bin-seconds", type=int, default=30)
    ap.add_argument("--stream-speedup", type=float, default=52.9)
    ap.add_argument("--output-concurrency", type=int, default=4)
    ap.add_argument("--ig-push-concurrency", type=int, default=1)
    ap.add_argument("--http-pool-maxsize", type=int, default=512)
    ap.add_argument("--target-burst-seconds", type=float, default=0.25)
    ap.add_argument("--target-initial-tokens", type=float, default=0.25)
    ap.add_argument("--short-upward-transition-blend", type=float, default=(1.0 / 3.0))
    ap.add_argument("--traffic-output-ids", default="s3_event_stream_with_fraud_6B")
    ap.add_argument("--context-output-ids", default="arrival_events_5B,s1_arrival_entities_6B,s3_flow_anchor_with_fraud_6B")
    ap.add_argument("--wsp-task-cpu", type=int, default=256)
    ap.add_argument("--wsp-task-memory", type=int, default=1024)
    ap.add_argument("--cost-budget-envelope-usd", type=float, default=15.0)
    args = ap.parse_args()

    execution_id = str(args.execution_id).strip() or fresh_execution_id()
    root = Path(args.run_control_root) / execution_id
    root.mkdir(parents=True, exist_ok=True)

    window_label = "phase4_coupled"
    platform_run_id = fresh_platform_run_id()
    scenario_run_id = fresh_scenario_run_id(
        execution_id=execution_id,
        window_label=window_label,
        platform_run_id=platform_run_id,
    )
    prewarm_scenario_run_id = fresh_scenario_run_id(
        execution_id=execution_id,
        window_label="phase4_coupled_prewarm",
        platform_run_id=platform_run_id,
    )

    total_duration = int(args.presteady_seconds) + int(args.steady_seconds) + int(args.burst_seconds) + int(args.recovery_seconds)
    charter_payload_path = root / "g4a_run_charter.active.json"
    write_charter(
        charter_payload_path,
        execution_id=execution_id,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        window_start_ts_utc=str(args.window_start_ts_utc).strip(),
        window_end_ts_utc=str(args.window_end_ts_utc).strip(),
        steady_eps=float(args.steady_eps),
        burst_eps=float(args.burst_eps),
        duration_seconds=total_duration,
    )
    write_json(root / "g3a_run_charter.active.json", json.loads(charter_payload_path.read_text(encoding="utf-8")))
    write_json(
        root / "phase4_runtime_identity.json",
        {
            "generated_at_utc": now_utc(),
            "execution_id": execution_id,
            "window_label": window_label,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "prewarm_scenario_run_id": prewarm_scenario_run_id,
            "scenario_id": str(args.scenario_id).strip(),
        },
    )

    try:
        initial_runtime_scenario_run_id = prewarm_scenario_run_id if int(args.prewarm_duration_seconds) > 0 else scenario_run_id
        materialize_runtime(
            execution_id=execution_id,
            platform_run_id=platform_run_id,
            scenario_run_id=initial_runtime_scenario_run_id,
            aws_region=args.aws_region,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
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
                "phase4_control_plane_bootstrap.json",
            ]
        )
        warm_gate_runtime(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
            expected_case_label_scenario_run_id=initial_runtime_scenario_run_id,
        )

        stop_wsp_tasks(args.aws_region, root / "phase4_coupled_preflight_wsp_cleanup.json", "Phase4 preflight stale WSP cleanup")
        if int(args.prewarm_duration_seconds) > 0:
            run_cmd(
                [
                    "scripts/dev_substrate/pr3_wsp_replay_dispatch.py",
                    "--run-control-root",
                    args.run_control_root,
                    "--pr3-execution-id",
                    execution_id,
                    "--state-id",
                    "P4",
                    "--window-label",
                    "phase4_coupled_prewarm",
                    "--artifact-prefix",
                    "phase4_coupled_prewarm",
                    "--blocker-prefix",
                    "PHASE4.COUPLED.PREWARM",
                    "--region",
                    args.aws_region,
                    "--platform-run-id",
                    platform_run_id,
                    "--scenario-run-id",
                    prewarm_scenario_run_id,
                    "--checkpoint-attempt-id",
                    utc_stamp(),
                    "--lane-count",
                    str(args.lane_count),
                    "--expected-window-eps",
                    str(args.prewarm_expected_window_eps),
                    "--target-request-rate-eps",
                    str(args.prewarm_target_request_rate_eps),
                    "--duration-seconds",
                    str(args.prewarm_duration_seconds),
                    "--warmup-seconds",
                    "0",
                    "--early-cutoff-seconds",
                    "15",
                    "--early-cutoff-floor-ratio",
                    "0.5",
                    "--stream-speedup",
                    str(args.stream_speedup),
                    "--output-concurrency",
                    str(args.output_concurrency),
                    "--ig-push-concurrency",
                    str(args.prewarm_ig_push_concurrency),
                    "--http-pool-maxsize",
                    str(args.http_pool_maxsize),
                    "--traffic-output-ids",
                    args.traffic_output_ids,
                    "--context-output-ids",
                    args.context_output_ids,
                    "--skip-runtime-identity-probe",
                    "--allow-runtime-identity-reuse",
                    "--skip-final-threshold-check",
                ]
            )
            stop_wsp_tasks(args.aws_region, root / "phase4_coupled_prewarm_wsp_cleanup.json", "Phase4 prewarm WSP cleanup")
            materialize_runtime(
                execution_id=execution_id,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                aws_region=args.aws_region,
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
            )
            if int(args.scored_activation_duration_seconds) > 0:
                run_cmd(
                    [
                        "scripts/dev_substrate/pr3_wsp_replay_dispatch.py",
                        "--run-control-root",
                        args.run_control_root,
                        "--pr3-execution-id",
                        execution_id,
                        "--state-id",
                        "P4",
                        "--window-label",
                        "phase4_coupled_activation",
                        "--artifact-prefix",
                        "phase4_coupled_activation",
                        "--blocker-prefix",
                        "PHASE4.COUPLED.ACTIVATION",
                        "--region",
                        args.aws_region,
                        "--platform-run-id",
                        platform_run_id,
                        "--scenario-run-id",
                        scenario_run_id,
                        "--checkpoint-attempt-id",
                        utc_stamp(),
                        "--lane-count",
                        str(args.lane_count),
                        "--expected-window-eps",
                        str(args.scored_activation_expected_window_eps),
                        "--target-request-rate-eps",
                        str(args.scored_activation_target_request_rate_eps),
                        "--duration-seconds",
                        str(args.scored_activation_duration_seconds),
                        "--warmup-seconds",
                        "0",
                        "--early-cutoff-seconds",
                        "15",
                        "--early-cutoff-floor-ratio",
                        "0.5",
                        "--stream-speedup",
                        str(args.stream_speedup),
                        "--output-concurrency",
                        str(args.output_concurrency),
                        "--ig-push-concurrency",
                        str(args.scored_activation_ig_push_concurrency),
                        "--http-pool-maxsize",
                        str(args.http_pool_maxsize),
                        "--traffic-output-ids",
                        args.traffic_output_ids,
                        "--context-output-ids",
                        args.context_output_ids,
                        "--skip-runtime-identity-probe",
                        "--allow-runtime-identity-reuse",
                        "--skip-final-threshold-check",
                    ]
                )
                stop_wsp_tasks(args.aws_region, root / "phase4_coupled_activation_wsp_cleanup.json", "Phase4 scored activation WSP cleanup")
                time.sleep(max(0, int(args.post_scored_activation_settle_seconds)))
            time.sleep(max(0, int(args.post_prewarm_settle_seconds)))

        capture_snapshot(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            state_id="P4",
            snapshot_label="pre",
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
        )

        run_cmd(
            [
                "scripts/dev_substrate/phase0_control_ingress_envelope.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--state-id",
                "P4",
                "--artifact-prefix",
                "phase4_coupled",
                "--blocker-prefix",
                "PHASE4.COUPLED",
                "--window-label",
                "phase4_coupled",
                "--summary-phase",
                "PHASE4",
                "--ready-verdict",
                "PHASE4B_READY",
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--generated-by",
                "phase4-case-label-coupled-readiness",
                "--steady-seconds",
                str(args.steady_seconds),
                "--burst-seconds",
                str(args.burst_seconds),
                "--recovery-seconds",
                str(args.recovery_seconds),
                "--presteady-seconds",
                str(args.presteady_seconds),
                "--presteady-eps",
                str(args.presteady_eps),
                "--steady-eps",
                str(args.steady_eps),
                "--burst-eps",
                str(args.burst_eps),
                "--recovery-bound-seconds",
                str(args.recovery_bound_seconds),
                "--recovery-bin-seconds",
                str(args.recovery_bin_seconds),
                "--lane-count",
                str(args.lane_count),
                "--stream-speedup",
                str(args.stream_speedup),
                "--output-concurrency",
                str(args.output_concurrency),
                "--ig-push-concurrency",
                str(args.ig_push_concurrency),
                "--http-pool-maxsize",
                str(args.http_pool_maxsize),
                "--target-burst-seconds",
                str(args.target_burst_seconds),
                "--target-initial-tokens",
                str(args.target_initial_tokens),
                "--short-upward-transition-blend",
                str(args.short_upward_transition_blend),
                "--traffic-output-ids",
                args.traffic_output_ids,
                "--context-output-ids",
                args.context_output_ids,
                "--region",
                args.aws_region,
                "--max-latency-p95-ms",
                "350",
                "--max-latency-p99-ms",
                "700",
            ]
        )

        capture_snapshot(
            execution_id=execution_id,
            run_control_root=args.run_control_root,
            state_id="P4",
            snapshot_label="post",
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=platform_run_id,
        )
        run_cmd(
            [
                "scripts/dev_substrate/pr3_s4_cost_guardrail.py",
                "--run-control-root",
                args.run_control_root,
                "--pr3-execution-id",
                execution_id,
                "--state-id",
                "P4",
                "--artifact-prefix",
                "phase4_coupled",
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
                "phase4_coupled_cost_receipt.json",
                "--drill-path",
                "phase4_coupled_cost_guardrail.json",
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/phase4_case_label_timing_probe.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--namespace",
                args.case_labels_namespace,
                "--artifact-prefix",
                "phase4_coupled",
            ]
        )
        run_cmd(
            [
                "scripts/dev_substrate/phase4_case_label_coupled_rollup.py",
                "--run-control-root",
                args.run_control_root,
                "--execution-id",
                execution_id,
            ]
        )
    finally:
        stop_wsp_tasks(args.aws_region, root / "phase4_coupled_final_wsp_cleanup.json", "Phase4 final WSP cleanup")


if __name__ == "__main__":
    main()
