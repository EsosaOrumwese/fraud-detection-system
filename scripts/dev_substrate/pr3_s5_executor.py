#!/usr/bin/env python3
"""Execute PR3-S5 bounded stress, optional soak, and final pack rollup on AWS."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cmd(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], check=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def fresh_platform_run_id() -> str:
    return f"platform_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def fresh_scenario_run_id(*, pr3_execution_id: str, window_label: str, platform_run_id: str) -> str:
    seed = f"{pr3_execution_id}:{window_label}:{platform_run_id}"
    return hashlib.md5(seed.encode("utf-8"), usedforsecurity=False).hexdigest()


def write_identity_receipt(
    path: Path,
    *,
    window_label: str,
    platform_run_id: str,
    scenario_run_id: str,
    inherited_platform_run_id: str,
    inherited_scenario_run_id: str,
) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "window_label": window_label,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "inherited_from_s4": {
            "platform_run_id": inherited_platform_run_id,
            "scenario_run_id": inherited_scenario_run_id,
        },
    }
    write_json(path, payload)


def describe_ecs_service(ecs: Any, *, cluster: str, service: str) -> dict[str, Any]:
    response = ecs.describe_services(cluster=cluster, services=[service])
    services = list(response.get("services") or [])
    if not services:
        raise RuntimeError(f"PR3.S5.ECS_SERVICE_MISSING:{cluster}/{service}")
    details = services[0]
    return {
        "cluster": cluster,
        "service": service,
        "service_arn": str(details.get("serviceArn") or "").strip(),
        "desired_count": int(details.get("desiredCount") or 0),
        "running_count": int(details.get("runningCount") or 0),
        "pending_count": int(details.get("pendingCount") or 0),
        "task_definition": str(details.get("taskDefinition") or "").strip(),
        "deployment_count": len(list(details.get("deployments") or [])),
        "target_group_arns": [
            str(row.get("targetGroupArn") or "").strip()
            for row in list(details.get("loadBalancers") or [])
            if str(row.get("targetGroupArn") or "").strip()
        ],
    }


def wait_for_service_steady(
    ecs: Any,
    *,
    cluster: str,
    service: str,
    timeout_seconds: int = 900,
    fail_on_quota_limit: bool = True,
) -> dict[str, Any]:
    deadline = time.time() + max(15, int(timeout_seconds))
    delay_seconds = 15
    last = describe_ecs_service(ecs, cluster=cluster, service=service)
    while time.time() < deadline:
        response = ecs.describe_services(cluster=cluster, services=[service])
        services = list(response.get("services") or [])
        if not services:
            raise RuntimeError(f"PR3.S5.ECS_SERVICE_MISSING:{cluster}/{service}")
        service_payload = services[0]
        last = {
            "cluster": cluster,
            "service": service,
            "service_arn": str(service_payload.get("serviceArn") or "").strip(),
            "desired_count": int(service_payload.get("desiredCount") or 0),
            "running_count": int(service_payload.get("runningCount") or 0),
            "pending_count": int(service_payload.get("pendingCount") or 0),
            "task_definition": str(service_payload.get("taskDefinition") or "").strip(),
            "deployment_count": len(list(service_payload.get("deployments") or [])),
            "target_group_arns": [
                str(row.get("targetGroupArn") or "").strip()
                for row in list(service_payload.get("loadBalancers") or [])
                if str(row.get("targetGroupArn") or "").strip()
            ],
        }
        if last["running_count"] >= last["desired_count"] and last["pending_count"] == 0:
            return last
        events = list(service_payload.get("events") or [])
        for event in events[:5]:
            message = str(event.get("message") or "")
            if fail_on_quota_limit and "limit on the number of vCPUs you can run concurrently" in message:
                raise RuntimeError(f"PR3.S5.INGRESS.B13_VCPU_QUOTA_LIMIT:{message}")
        time.sleep(delay_seconds)
    raise RuntimeError(
        f"PR3.S5.INGRESS.B14_SERVICE_NOT_STABLE:desired={last['desired_count']}:running={last['running_count']}:pending={last['pending_count']}"
    )


def wait_for_target_group_healthy(
    elbv2: Any,
    *,
    target_group_arn: str,
    expected_healthy_count: int,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    deadline = time.time() + max(15, int(timeout_seconds))
    last: dict[str, Any] = {
        "target_group_arn": target_group_arn,
        "healthy_count": 0,
        "initial_count": 0,
        "unhealthy_count": 0,
        "draining_count": 0,
        "unused_count": 0,
        "other_count": 0,
    }
    while time.time() < deadline:
        payload = elbv2.describe_target_health(TargetGroupArn=target_group_arn)
        descriptions = list(payload.get("TargetHealthDescriptions") or [])
        state_counts = {
            "healthy_count": 0,
            "initial_count": 0,
            "unhealthy_count": 0,
            "draining_count": 0,
            "unused_count": 0,
            "other_count": 0,
        }
        for row in descriptions:
            state = str(((row.get("TargetHealth") or {}).get("State")) or "").strip().lower()
            if state == "healthy":
                state_counts["healthy_count"] += 1
            elif state == "initial":
                state_counts["initial_count"] += 1
            elif state == "unhealthy":
                state_counts["unhealthy_count"] += 1
            elif state == "draining":
                state_counts["draining_count"] += 1
            elif state == "unused":
                state_counts["unused_count"] += 1
            else:
                state_counts["other_count"] += 1
        last = {"target_group_arn": target_group_arn, **state_counts}
        if (
            state_counts["healthy_count"] >= max(1, int(expected_healthy_count))
            and state_counts["initial_count"] == 0
            and state_counts["unhealthy_count"] == 0
        ):
            return last
        time.sleep(15)
    raise RuntimeError(
        "PR3.S5.INGRESS.B15_TARGET_GROUP_NOT_HEALTHY:"
        f"healthy={last['healthy_count']}:initial={last['initial_count']}:"
        f"unhealthy={last['unhealthy_count']}:draining={last['draining_count']}:"
        f"unused={last['unused_count']}:other={last['other_count']}"
    )


def ensure_ingress_service_capacity_once(
    ecs: Any,
    elbv2: Any,
    *,
    cluster: str,
    service: str,
    required_desired_count: int,
    receipt_path: Path,
) -> dict[str, Any]:
    before = describe_ecs_service(ecs, cluster=cluster, service=service)
    required = max(1, int(required_desired_count))
    action = "noop"
    if before["desired_count"] < required:
        ecs.update_service(cluster=cluster, service=service, desiredCount=required)
        action = "scaled_up"
    if action != "noop" or before["running_count"] < required or before["pending_count"] > 0:
        after = wait_for_service_steady(ecs, cluster=cluster, service=service)
    else:
        after = before
    target_group_health: list[dict[str, Any]] = []
    for target_group_arn in after.get("target_group_arns") or []:
        target_group_health.append(
            wait_for_target_group_healthy(
                elbv2,
                target_group_arn=target_group_arn,
                expected_healthy_count=after["desired_count"],
            )
        )
    write_json(
        receipt_path,
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "cluster": cluster,
            "service": service,
            "required_desired_count": required,
            "action": action,
            "before": before,
            "after": after,
            "target_group_health": target_group_health,
        },
    )
    return {
        "cluster": cluster,
        "service": service,
        "original_desired_count": before["desired_count"],
        "required_desired_count": required,
        "current_desired_count": after["desired_count"],
    }


def ensure_ingress_service_capacity(
    ecs: Any,
    elbv2: Any,
    *,
    cluster: str,
    service: str,
    required_desired_count: int,
    receipt_path: Path,
) -> dict[str, Any]:
    baseline = describe_ecs_service(ecs, cluster=cluster, service=service)
    attempts: list[dict[str, Any]] = []
    candidate = max(1, int(required_desired_count))
    floor = max(1, int(baseline["desired_count"] or 1))
    last_error = ""
    while candidate >= floor:
        try:
            result = ensure_ingress_service_capacity_once(
                ecs,
                elbv2,
                cluster=cluster,
                service=service,
                required_desired_count=candidate,
                receipt_path=receipt_path,
            )
            receipt = load_json(receipt_path)
            receipt["attempts"] = attempts + [
                {
                    "required_desired_count": candidate,
                    "result": "success",
                }
            ]
            write_json(receipt_path, receipt)
            return result
        except RuntimeError as exc:
            message = str(exc)
            attempts.append(
                {
                    "required_desired_count": candidate,
                    "result": "failed",
                    "error": message,
                }
            )
            if "PR3.S5.INGRESS.B13_VCPU_QUOTA_LIMIT:" not in message:
                raise
            last_error = message
            ecs.update_service(cluster=cluster, service=service, desiredCount=floor)
            wait_for_service_steady(ecs, cluster=cluster, service=service, fail_on_quota_limit=False)
            candidate -= 8
    write_json(
        receipt_path,
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "cluster": cluster,
            "service": service,
            "required_desired_count": int(required_desired_count),
            "action": "failed_all_candidates",
            "before": baseline,
            "attempts": attempts,
            "error": last_error or "PR3.S5.INGRESS.B13_VCPU_QUOTA_LIMIT",
        },
    )
    raise RuntimeError(last_error or "PR3.S5.INGRESS.B13_VCPU_QUOTA_LIMIT")


def restore_ingress_service_capacity(
    ecs: Any,
    *,
    cluster: str,
    service: str,
    original_desired_count: int,
    receipt_path: Path,
) -> None:
    before = describe_ecs_service(ecs, cluster=cluster, service=service)
    action = "noop"
    if before["desired_count"] != int(original_desired_count):
        ecs.update_service(cluster=cluster, service=service, desiredCount=int(original_desired_count))
        action = "restored_desired_count"
        after = wait_for_service_steady(ecs, cluster=cluster, service=service, fail_on_quota_limit=False)
    else:
        after = before
    write_json(
        receipt_path,
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "cluster": cluster,
            "service": service,
            "original_desired_count": int(original_desired_count),
            "action": action,
            "before": before,
            "after": after,
        },
    )


def load_runtime_manifest(root: Path) -> dict[str, Any]:
    return load_json(root / "g3a_runtime_materialization_manifest.json")


def rematerialize_runtime_for_identity(
    *,
    pr3_execution_id: str,
    root: Path,
    platform_run_id: str,
    scenario_run_id: str,
    region: str,
    namespace: str,
    case_labels_namespace: str,
) -> None:
    manifest = load_runtime_manifest(root)
    image_uri = str(manifest.get("image_uri") or "").strip()
    cmd = [
        "scripts/dev_substrate/pr3_rtdl_materialize.py",
        "--pr3-execution-id",
        pr3_execution_id,
        "--platform-run-id",
        platform_run_id,
        "--scenario-run-id",
        scenario_run_id,
        "--region",
        region,
        "--namespace",
        namespace,
        "--case-labels-namespace",
        case_labels_namespace,
    ]
    if image_uri:
        cmd.extend(["--image-uri", image_uri])
    run_cmd(cmd)


def warm_gate_runtime_for_identity(
    *,
    pr3_execution_id: str,
    state_id: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
) -> None:
    run_cmd(
        [
            "scripts/dev_substrate/pr3_runtime_warm_gate.py",
            "--pr3-execution-id",
            pr3_execution_id,
            "--state-id",
            state_id,
            "--namespace",
            namespace,
            "--case-labels-namespace",
            case_labels_namespace,
            "--platform-run-id",
            platform_run_id,
        ]
    )


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
}}
Path({str(receipt_path)!r}).write_text(json.dumps(payload, indent=2) + "\\n", encoding='utf-8')
"""
    subprocess.run([sys.executable, '-c', code], check=True)


def wait_dispatch_with_sampling(
    *,
    dispatch_args: list[str],
    snapshot_prefix: str,
    pr3_execution_id: str,
    state_id: str,
    namespace: str,
    case_labels_namespace: str,
    platform_run_id: str,
    warmup_seconds: int,
    sample_period_seconds: int,
) -> None:
    proc = subprocess.Popen([sys.executable, *dispatch_args])
    try:
        time.sleep(max(10, warmup_seconds))
        sample_index = 1
        while proc.poll() is None:
            run_cmd(
                [
                    'scripts/dev_substrate/pr3_runtime_surface_snapshot.py',
                    '--pr3-execution-id',
                    pr3_execution_id,
                    '--state-id',
                    state_id,
                    '--snapshot-label',
                    f'{snapshot_prefix}_during_{sample_index}',
                    '--namespace',
                    namespace,
                    '--case-labels-namespace',
                    case_labels_namespace,
                    '--platform-run-id',
                    platform_run_id,
                ]
            )
            sample_index += 1
            time.sleep(sample_period_seconds)
    finally:
        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, dispatch_args)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pr3-execution-id', required=True)
    ap.add_argument('--run-control-root', default='runs/dev_substrate/dev_full/road_to_prod/run_control')
    ap.add_argument('--aws-region', default='eu-west-2')
    ap.add_argument('--namespace', default='fraud-platform-rtdl')
    ap.add_argument('--case-labels-namespace', default='fraud-platform-case-labels')
    ap.add_argument('--stress-target-eps', type=float, default=6000.0)
    ap.add_argument('--stress-request-eps', type=float, default=6060.0)
    ap.add_argument('--stress-duration-seconds', type=int, default=300)
    ap.add_argument('--stress-warmup-seconds', type=int, default=120)
    ap.add_argument('--stress-lane-count', type=int, default=48)
    ap.add_argument('--stress-stream-speedup', type=float, default=600.0)
    ap.add_argument('--stress-ig-push-concurrency', type=int, default=16)
    ap.add_argument('--stress-output-concurrency', type=int, default=6)
    ap.add_argument('--stress-http-pool-maxsize', type=int, default=1024)
    ap.add_argument('--stress-task-cpu', type=int, default=1024)
    ap.add_argument('--stress-task-memory', type=int, default=2048)
    ap.add_argument('--stress-traffic-output-ids', default='s3_event_stream_with_fraud_6B')
    ap.add_argument('--stress-context-output-ids', default='s3_flow_anchor_with_fraud_6B')
    ap.add_argument('--stress-context-prewarm-seconds', type=int, default=90)
    ap.add_argument('--stress-context-prewarm-request-eps', type=float, default=1200.0)
    ap.add_argument('--stress-context-prewarm-lane-count', type=int, default=16)
    ap.add_argument('--stress-context-prewarm-output-concurrency', type=int, default=4)
    ap.add_argument('--stress-context-prewarm-ig-push-concurrency', type=int, default=8)
    ap.add_argument('--stress-context-prewarm-http-pool-maxsize', type=int, default=512)
    ap.add_argument('--stress-context-prewarm-task-cpu', type=int, default=256)
    ap.add_argument('--stress-context-prewarm-task-memory', type=int, default=1024)
    ap.add_argument('--stress-context-prewarm-output-ids', default='arrival_events_5B,s1_arrival_entities_6B')
    ap.add_argument('--stress-ingress-service-cluster', default='fraud-platform-dev-full-ingress')
    ap.add_argument('--stress-ingress-service-name', default='fraud-platform-dev-full-ig-service')
    ap.add_argument('--stress-ingress-desired-count', type=int, default=32)
    ap.add_argument('--soak-target-eps', type=float, default=3000.0)
    ap.add_argument('--soak-request-eps', type=float, default=3030.0)
    ap.add_argument('--soak-duration-seconds', type=int, default=1800)
    ap.add_argument('--soak-warmup-seconds', type=int, default=120)
    ap.add_argument('--soak-lane-count', type=int, default=40)
    ap.add_argument('--soak-stream-speedup', type=float, default=51.2)
    ap.add_argument('--soak-ig-push-concurrency', type=int, default=4)
    ap.add_argument('--soak-output-concurrency', type=int, default=4)
    ap.add_argument('--soak-http-pool-maxsize', type=int, default=512)
    ap.add_argument('--soak-task-cpu', type=int, default=256)
    ap.add_argument('--soak-task-memory', type=int, default=1024)
    ap.add_argument('--soak-ingress-desired-count', type=int, default=32)
    ap.add_argument('--enable-soak', action='store_true')
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    s4 = load_json(root / 'pr3_s4_execution_receipt.json')
    if str(s4.get('verdict') or '').strip() != 'PR3_S4_READY':
        raise SystemExit(f"PR3-S5 strict upstream invalid: {s4.get('verdict')}")
    bootstrap = load_json(root / 'g3a_control_plane_bootstrap.json')
    inherited_platform_run_id = str(bootstrap.get('platform_run_id') or '').strip()
    inherited_scenario_run_id = str(bootstrap.get('scenario_run_id') or '').strip()
    if not inherited_platform_run_id or not inherited_scenario_run_id:
        raise SystemExit('PR3-S5 requires active platform_run_id and scenario_run_id from S4 control bootstrap')

    stress_platform_run_id = fresh_platform_run_id()
    stress_scenario_run_id = fresh_scenario_run_id(
        pr3_execution_id=args.pr3_execution_id,
        window_label='stress',
        platform_run_id=stress_platform_run_id,
    )
    ecs = boto3.client("ecs", region_name=args.aws_region)
    elbv2 = boto3.client("elbv2", region_name=args.aws_region)
    ingress_capacity_state = {
        "cluster": args.stress_ingress_service_cluster,
        "service": args.stress_ingress_service_name,
        "original_desired_count": describe_ecs_service(
            ecs,
            cluster=args.stress_ingress_service_cluster,
            service=args.stress_ingress_service_name,
        )["desired_count"],
    }
    try:
        ingress_capacity_state = ensure_ingress_service_capacity(
            ecs,
            elbv2,
            cluster=args.stress_ingress_service_cluster,
            service=args.stress_ingress_service_name,
            required_desired_count=args.stress_ingress_desired_count,
            receipt_path=root / 'g3a_stress_ingress_capacity_receipt.json',
        )
        write_identity_receipt(
            root / 'g3a_stress_runtime_identity.json',
            window_label='stress',
            platform_run_id=stress_platform_run_id,
            scenario_run_id=stress_scenario_run_id,
            inherited_platform_run_id=inherited_platform_run_id,
            inherited_scenario_run_id=inherited_scenario_run_id,
        )
        rematerialize_runtime_for_identity(
            pr3_execution_id=args.pr3_execution_id,
            root=root,
            platform_run_id=stress_platform_run_id,
            scenario_run_id=stress_scenario_run_id,
            region=args.aws_region,
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
        )
        warm_gate_runtime_for_identity(
            pr3_execution_id=args.pr3_execution_id,
            state_id="S5",
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=stress_platform_run_id,
        )

        stop_wsp_tasks(args.aws_region, root / 'g3a_stress_preflight_wsp_cleanup.json', 'PR3-S5 pre-stress stale WSP cleanup')
        if args.stress_context_prewarm_seconds > 0:
            stress_context_checkpoint_attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            run_cmd([
                'scripts/dev_substrate/pr3_wsp_replay_dispatch.py',
                '--pr3-execution-id', args.pr3_execution_id,
                '--state-id', 'S5',
                '--window-label', 'stress_context_prewarm',
                '--artifact-prefix', 'g3a_stress_context_prewarm',
                '--blocker-prefix', 'PR3.S5.PREWARM',
                '--region', args.aws_region,
                '--platform-run-id', stress_platform_run_id,
                '--scenario-run-id', stress_scenario_run_id,
                '--checkpoint-attempt-id', stress_context_checkpoint_attempt,
                '--source-posture', 'private_runtime',
                '--assign-public-ip', 'DISABLED',
                '--lane-count', str(args.stress_context_prewarm_lane_count),
                '--expected-window-eps', '1',
                '--target-request-rate-eps', str(args.stress_context_prewarm_request_eps),
                '--duration-seconds', str(args.stress_context_prewarm_seconds),
                '--warmup-seconds', '0',
                '--early-cutoff-seconds', '600',
                '--early-cutoff-floor-ratio', '0.0',
                '--stream-speedup', str(args.stress_stream_speedup),
                '--output-concurrency', str(args.stress_context_prewarm_output_concurrency),
                '--ig-push-concurrency', str(args.stress_context_prewarm_ig_push_concurrency),
                '--http-pool-maxsize', str(args.stress_context_prewarm_http_pool_maxsize),
                '--target-burst-seconds', '0.25',
                '--target-initial-tokens', '0.25',
                '--task-cpu', str(args.stress_context_prewarm_task_cpu),
                '--task-memory', str(args.stress_context_prewarm_task_memory),
                '--traffic-output-ids', '',
                '--context-output-ids', args.stress_context_output_ids,
                '--skip-final-threshold-check',
                '--skip-runtime-identity-probe',
            ])
            stop_wsp_tasks(
                args.aws_region,
                root / 'g3a_stress_context_prewarm_cleanup.json',
                'PR3-S5 stress context prewarm complete',
            )
        run_cmd([
            'scripts/dev_substrate/pr3_runtime_surface_snapshot.py',
            '--pr3-execution-id', args.pr3_execution_id,
            '--state-id', 'S5',
            '--snapshot-label', 'stress_pre',
            '--namespace', args.namespace,
            '--case-labels-namespace', args.case_labels_namespace,
            '--platform-run-id', stress_platform_run_id,
        ])
        stress_checkpoint_attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        wait_dispatch_with_sampling(
            dispatch_args=[
                'scripts/dev_substrate/pr3_wsp_replay_dispatch.py',
                '--pr3-execution-id', args.pr3_execution_id,
                '--state-id', 'S5',
                '--window-label', 'stress',
                '--artifact-prefix', 'g3a_stress',
                '--blocker-prefix', 'PR3.S5.STRESS',
                '--region', args.aws_region,
                    '--platform-run-id', stress_platform_run_id,
                    '--scenario-run-id', stress_scenario_run_id,
                    '--checkpoint-attempt-id', stress_checkpoint_attempt,
                    '--source-posture', 'private_runtime',
                    '--assign-public-ip', 'DISABLED',
                    '--lane-count', str(args.stress_lane_count),
                    '--expected-window-eps', str(args.stress_target_eps),
                    '--target-request-rate-eps', str(args.stress_request_eps),
                '--duration-seconds', str(args.stress_duration_seconds),
                '--warmup-seconds', str(args.stress_warmup_seconds),
                '--early-cutoff-seconds', '120',
                '--early-cutoff-floor-ratio', '0.70',
                '--stream-speedup', str(args.stress_stream_speedup),
                '--output-concurrency', str(args.stress_output_concurrency),
                '--ig-push-concurrency', str(args.stress_ig_push_concurrency),
                '--http-pool-maxsize', str(args.stress_http_pool_maxsize),
                '--target-burst-seconds', '0.5',
                '--target-initial-tokens', '0.5',
                '--task-cpu', str(args.stress_task_cpu),
                '--task-memory', str(args.stress_task_memory),
                '--max-latency-p95-ms', '350',
                '--max-latency-p99-ms', '700',
                '--traffic-output-ids', args.stress_traffic_output_ids,
                '--context-output-ids', args.stress_context_output_ids,
                '--skip-runtime-identity-probe',
            ],
            snapshot_prefix='stress',
            pr3_execution_id=args.pr3_execution_id,
            state_id='S5',
            namespace=args.namespace,
            case_labels_namespace=args.case_labels_namespace,
            platform_run_id=stress_platform_run_id,
            warmup_seconds=max(30, args.stress_warmup_seconds),
            sample_period_seconds=30,
        )
        run_cmd([
            'scripts/dev_substrate/pr3_runtime_surface_snapshot.py',
            '--pr3-execution-id', args.pr3_execution_id,
            '--state-id', 'S5',
            '--snapshot-label', 'stress_post',
            '--namespace', args.namespace,
            '--case-labels-namespace', args.case_labels_namespace,
            '--platform-run-id', stress_platform_run_id,
        ])
        run_cmd([
            'scripts/dev_substrate/pr3_s4_cost_guardrail.py',
            '--pr3-execution-id', args.pr3_execution_id,
            '--state-id', 'S5',
            '--artifact-prefix', 'g3a_stress',
            '--aws-region', args.aws_region,
            '--cluster', 'fraud-platform-dev-full-wsp-ephemeral',
            '--wsp-task-cpu', str(args.stress_task_cpu),
            '--wsp-task-memory', str(args.stress_task_memory),
            '--budget-envelope-usd', '80.0',
            '--receipt-path', 'g3a_stress_cost_receipt.json',
            '--drill-path', 'g3a_stress_cost_guardrail.json',
        ])
        run_cmd(['scripts/dev_substrate/pr3_s5_stress_rollup.py', '--pr3-execution-id', args.pr3_execution_id])

        stress_receipt = load_json(root / 'g3a_stress_execution_receipt.json')
        if args.enable_soak and str(stress_receipt.get('verdict') or '').strip() == 'PR3_S5_STRESS_READY':
            ensure_ingress_service_capacity(
                ecs,
                elbv2,
                cluster=args.stress_ingress_service_cluster,
                service=args.stress_ingress_service_name,
                required_desired_count=args.soak_ingress_desired_count,
                receipt_path=root / 'g3a_soak_ingress_capacity_receipt.json',
            )
            soak_platform_run_id = fresh_platform_run_id()
            soak_scenario_run_id = fresh_scenario_run_id(
                pr3_execution_id=args.pr3_execution_id,
                window_label='soak',
                platform_run_id=soak_platform_run_id,
            )
            write_identity_receipt(
                root / 'g3a_soak_runtime_identity.json',
                window_label='soak',
                platform_run_id=soak_platform_run_id,
                scenario_run_id=soak_scenario_run_id,
                inherited_platform_run_id=inherited_platform_run_id,
                inherited_scenario_run_id=inherited_scenario_run_id,
            )
            rematerialize_runtime_for_identity(
                pr3_execution_id=args.pr3_execution_id,
                root=root,
                platform_run_id=soak_platform_run_id,
                scenario_run_id=soak_scenario_run_id,
                region=args.aws_region,
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
            )
            warm_gate_runtime_for_identity(
                pr3_execution_id=args.pr3_execution_id,
                state_id='S5',
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
                platform_run_id=soak_platform_run_id,
            )
            stop_wsp_tasks(args.aws_region, root / 'g3a_soak_preflight_wsp_cleanup.json', 'PR3-S5 pre-soak stale WSP cleanup')
            run_cmd([
                'scripts/dev_substrate/pr3_runtime_surface_snapshot.py',
                '--pr3-execution-id', args.pr3_execution_id,
                '--state-id', 'S5',
                '--snapshot-label', 'soak_pre',
                '--namespace', args.namespace,
                '--case-labels-namespace', args.case_labels_namespace,
                '--platform-run-id', soak_platform_run_id,
            ])
            soak_checkpoint_attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            wait_dispatch_with_sampling(
                dispatch_args=[
                    'scripts/dev_substrate/pr3_wsp_replay_dispatch.py',
                    '--pr3-execution-id', args.pr3_execution_id,
                    '--state-id', 'S5',
                    '--window-label', 'soak',
                    '--artifact-prefix', 'g3a_soak',
                    '--blocker-prefix', 'PR3.S5.SOAK',
                    '--region', args.aws_region,
                    '--platform-run-id', soak_platform_run_id,
                    '--scenario-run-id', soak_scenario_run_id,
                    '--checkpoint-attempt-id', soak_checkpoint_attempt,
                    '--source-posture', 'private_runtime',
                    '--assign-public-ip', 'DISABLED',
                    '--lane-count', str(args.soak_lane_count),
                    '--expected-window-eps', str(args.soak_target_eps),
                    '--target-request-rate-eps', str(args.soak_request_eps),
                    '--duration-seconds', str(args.soak_duration_seconds),
                    '--warmup-seconds', str(args.soak_warmup_seconds),
                    '--early-cutoff-seconds', '300',
                    '--early-cutoff-floor-ratio', '0.70',
                    '--stream-speedup', str(args.soak_stream_speedup),
                    '--output-concurrency', str(args.soak_output_concurrency),
                    '--ig-push-concurrency', str(args.soak_ig_push_concurrency),
                    '--http-pool-maxsize', str(args.soak_http_pool_maxsize),
                    '--target-burst-seconds', '0.25',
                    '--target-initial-tokens', '0.25',
                    '--task-cpu', str(args.soak_task_cpu),
                    '--task-memory', str(args.soak_task_memory),
                    '--max-latency-p95-ms', '350',
                    '--max-latency-p99-ms', '700',
                    '--skip-runtime-identity-probe',
                ],
                snapshot_prefix='soak',
                pr3_execution_id=args.pr3_execution_id,
                state_id='S5',
                namespace=args.namespace,
                case_labels_namespace=args.case_labels_namespace,
                platform_run_id=soak_platform_run_id,
                warmup_seconds=max(60, args.soak_warmup_seconds),
                sample_period_seconds=120,
            )
            run_cmd([
                'scripts/dev_substrate/pr3_runtime_surface_snapshot.py',
                '--pr3-execution-id', args.pr3_execution_id,
                '--state-id', 'S5',
                '--snapshot-label', 'soak_post',
                '--namespace', args.namespace,
                '--case-labels-namespace', args.case_labels_namespace,
                '--platform-run-id', soak_platform_run_id,
            ])
            run_cmd([
                'scripts/dev_substrate/pr3_s4_cost_guardrail.py',
                '--pr3-execution-id', args.pr3_execution_id,
                '--state-id', 'S5',
                '--artifact-prefix', 'g3a_soak',
                '--aws-region', args.aws_region,
                '--cluster', 'fraud-platform-dev-full-wsp-ephemeral',
                '--wsp-task-cpu', str(args.soak_task_cpu),
                '--wsp-task-memory', str(args.soak_task_memory),
                '--budget-envelope-usd', '170.0',
                '--receipt-path', 'g3a_runtime_cost_receipt.json',
                '--drill-path', 'g3a_drill_cost_guardrail.json',
            ])
            run_cmd(['scripts/dev_substrate/pr3_s5_soak_rollup.py', '--pr3-execution-id', args.pr3_execution_id])
    finally:
        try:
            stop_wsp_tasks(args.aws_region, root / 'g3a_s5_final_wsp_cleanup.json', 'PR3-S5 final WSP cleanup')
        finally:
            try:
                restore_ingress_service_capacity(
                    ecs,
                    cluster=ingress_capacity_state["cluster"],
                    service=ingress_capacity_state["service"],
                    original_desired_count=int(ingress_capacity_state["original_desired_count"]),
                    receipt_path=root / 'g3a_s5_ingress_capacity_restore_receipt.json',
                )
            except Exception as exc:
                write_json(
                    root / 'g3a_s5_ingress_capacity_restore_receipt.json',
                    {
                        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "cluster": ingress_capacity_state["cluster"],
                        "service": ingress_capacity_state["service"],
                        "original_desired_count": int(ingress_capacity_state["original_desired_count"]),
                        "action": "restore_failed",
                        "error": str(exc),
                    },
                )
                raise
    run_cmd(['scripts/dev_substrate/pr3_s5_pack_rollup.py', '--pr3-execution-id', args.pr3_execution_id])


if __name__ == '__main__':
    main()
