#!/usr/bin/env python3
"""Start M6 stream lane references on EMR on EKS and emit a receipt."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _start_lane_job(
    *,
    emr_client: Any,
    region: str,
    virtual_cluster_id: str,
    execution_role_arn: str,
    release_label: str,
    script_s3_uri: str,
    platform_run_id: str,
    scenario_run_id: str,
    lane_ref: str,
    log_group_name: str,
    log_prefix: str,
    iterations: int,
    sleep_seconds: float,
) -> str:
    response = emr_client.start_job_run(
        name=lane_ref,
        virtualClusterId=virtual_cluster_id,
        executionRoleArn=execution_role_arn,
        releaseLabel=release_label,
        jobDriver={
            "sparkSubmitJobDriver": {
                "entryPoint": script_s3_uri,
                "entryPointArguments": [
                    "--lane-ref",
                    lane_ref,
                    "--platform-run-id",
                    platform_run_id,
                    "--scenario-run-id",
                    scenario_run_id,
                    "--iterations",
                    str(iterations),
                    "--sleep-seconds",
                    str(sleep_seconds),
                ],
                "sparkSubmitParameters": (
                    "--conf spark.executor.instances=1 "
                    "--conf spark.executor.cores=1 "
                    "--conf spark.executor.memory=1G "
                    "--conf spark.driver.memory=1G"
                ),
            }
        },
        configurationOverrides={
            "monitoringConfiguration": {
                "persistentAppUI": "ENABLED",
                "cloudWatchMonitoringConfiguration": {
                    "logGroupName": log_group_name,
                    "logStreamNamePrefix": log_prefix,
                },
            }
        },
        tags={
            "env": "dev_full",
            "fp_phase": "M6.F",
            "fp_resource": "emr_lane_ref_job",
            "region": region,
        },
    )
    job_id = str(response.get("id", "")).strip()
    if not job_id:
        raise RuntimeError(f"EMR start-job-run returned empty id for lane_ref={lane_ref}")
    return job_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit M6 EMR lane refs")
    parser.add_argument("--region", required=True)
    parser.add_argument("--virtual-cluster-id", required=True)
    parser.add_argument("--execution-role-arn", required=True)
    parser.add_argument("--release-label", required=True)
    parser.add_argument("--script-s3-uri", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--wsp-ref", required=True)
    parser.add_argument("--sr-ready-ref", required=True)
    parser.add_argument("--log-group-name", default="/emr-eks/fraud-platform-dev-full")
    parser.add_argument("--iterations", type=int, default=900)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--output-json", default="")
    args = parser.parse_args()

    emr = boto3.client("emr-containers", region_name=args.region)

    wsp_job_id = _start_lane_job(
        emr_client=emr,
        region=args.region,
        virtual_cluster_id=args.virtual_cluster_id,
        execution_role_arn=args.execution_role_arn,
        release_label=args.release_label,
        script_s3_uri=args.script_s3_uri,
        platform_run_id=args.platform_run_id,
        scenario_run_id=args.scenario_run_id,
        lane_ref=args.wsp_ref,
        log_group_name=args.log_group_name,
        log_prefix="wsp-stream",
        iterations=args.iterations,
        sleep_seconds=args.sleep_seconds,
    )

    sr_job_id = _start_lane_job(
        emr_client=emr,
        region=args.region,
        virtual_cluster_id=args.virtual_cluster_id,
        execution_role_arn=args.execution_role_arn,
        release_label=args.release_label,
        script_s3_uri=args.script_s3_uri,
        platform_run_id=args.platform_run_id,
        scenario_run_id=args.scenario_run_id,
        lane_ref=args.sr_ready_ref,
        log_group_name=args.log_group_name,
        log_prefix="sr-ready",
        iterations=args.iterations,
        sleep_seconds=args.sleep_seconds,
    )

    payload: dict[str, Any] = {
        "started_at_utc": _now_utc(),
        "virtual_cluster_id": args.virtual_cluster_id,
        "wsp_ref": args.wsp_ref,
        "wsp_job_id": wsp_job_id,
        "sr_ready_ref": args.sr_ready_ref,
        "sr_ready_job_id": sr_job_id,
        "script_s3_uri": args.script_s3_uri,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
    }

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
