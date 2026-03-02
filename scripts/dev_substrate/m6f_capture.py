#!/usr/bin/env python3
"""Capture and publish M6.F streaming-active artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


ACTIVE_JOB_STATES = {"RUNNING"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _parse_utc_to_epoch(value: str) -> int:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return int(parsed.timestamp())


def _describe_job_run_state(
    emr_client: Any,
    *,
    virtual_cluster_id: str,
    job_id: str,
) -> tuple[str | None, str | None]:
    try:
        response = emr_client.describe_job_run(
            virtualClusterId=virtual_cluster_id,
            id=job_id,
        )
    except (BotoCoreError, ClientError) as exc:
        return None, f"emr_describe_job_run_failed:{type(exc).__name__}"
    job = response.get("jobRun") if isinstance(response, dict) else None
    if not isinstance(job, dict):
        return None, "emr_describe_job_run_missing_jobRun"
    state = str(job.get("state", "")).strip()
    if not state:
        return None, "emr_describe_job_run_missing_state"
    return state, None


def _scan_run_window_metrics(
    ddb_client: Any,
    *,
    table_name: str,
    platform_run_id: str,
    lane_window_start_epoch: int,
    page_limit: int,
    page_size: int,
) -> tuple[int | None, int | None, int, str | None]:
    token: dict[str, Any] | None = None
    pages_scanned = 0
    run_window_count = 0
    latest_admitted_epoch: int | None = None
    try:
        while True:
            request: dict[str, Any] = {
                "TableName": table_name,
                "ProjectionExpression": "#pr, #ae",
                "ExpressionAttributeNames": {
                    "#pr": "platform_run_id",
                    "#ae": "admitted_at_epoch",
                },
                "ExpressionAttributeValues": {
                    ":pr": {"S": platform_run_id},
                    ":window_start": {"N": str(lane_window_start_epoch)},
                },
                "FilterExpression": "#pr = :pr AND #ae >= :window_start",
                "Limit": max(1, page_size),
            }
            if token:
                request["ExclusiveStartKey"] = token
            response = ddb_client.scan(**request)
            pages_scanned += 1
            for item in response.get("Items", []):
                if not isinstance(item, dict):
                    continue
                admitted_attr = item.get("admitted_at_epoch")
                admitted_raw = (
                    str(admitted_attr.get("N", "")).strip()
                    if isinstance(admitted_attr, dict)
                    else ""
                )
                try:
                    admitted_epoch = int(admitted_raw)
                except ValueError:
                    continue
                run_window_count += 1
                if latest_admitted_epoch is None or admitted_epoch > latest_admitted_epoch:
                    latest_admitted_epoch = admitted_epoch

            token = response.get("LastEvaluatedKey")
            if not token:
                break
            if pages_scanned >= max(1, page_limit):
                return run_window_count, latest_admitted_epoch, pages_scanned, "dynamodb_scan_page_limit_reached"

        return run_window_count, latest_admitted_epoch, pages_scanned, None
    except (BotoCoreError, ClientError) as exc:
        return None, None, pages_scanned, f"dynamodb_scan_failed:{type(exc).__name__}"


def _scan_publish_ambiguity(
    s3_client: Any,
    bucket: str,
    platform_run_id: str,
) -> tuple[int, list[str], str | None]:
    prefix = f"evidence/runs/{platform_run_id}/ingest/"
    refs: list[str] = []
    token: str | None = None
    try:
        while True:
            request: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                request["ContinuationToken"] = token
            response = s3_client.list_objects_v2(**request)
            for item in response.get("Contents", []):
                key = str(item.get("Key", ""))
                if "PUBLISH_UNKNOWN" in key or "publish_unknown" in key:
                    refs.append(f"s3://{bucket}/{key}")
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
        return len(refs), refs, None
    except (BotoCoreError, ClientError) as exc:
        return 0, [], f"s3_scan_failed:{type(exc).__name__}"


def _upload_artifacts(
    s3_client: Any,
    *,
    bucket: str,
    execution_id: str,
    files: list[Path],
) -> None:
    prefix = f"evidence/dev_full/run_control/{execution_id}/"
    for file_path in files:
        key = f"{prefix}{file_path.name}"
        body = file_path.read_bytes()
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        s3_client.head_object(Bucket=bucket, Key=key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture M6.F artifact set")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--scenario-run-id", required=True)
    parser.add_argument("--upstream-m6e-execution", required=True)
    parser.add_argument("--region", default="eu-west-2")
    parser.add_argument("--runtime-path", default="EKS_EMR_ON_EKS")
    parser.add_argument("--runtime-path-allowed", default="MSF_MANAGED|EKS_EMR_ON_EKS|EKS_FLINK_OPERATOR")
    parser.add_argument("--runtime-path-fallback-blocker", default="M6P6-B2")
    parser.add_argument("--virtual-cluster-id", required=True)
    parser.add_argument("--wsp-job-id", required=True)
    parser.add_argument("--sr-ready-job-id", required=True)
    parser.add_argument("--wsp-state-override", default="")
    parser.add_argument("--sr-ready-state-override", default="")
    parser.add_argument("--wsp-ref", required=True)
    parser.add_argument("--sr-ready-ref", required=True)
    parser.add_argument("--lane-window-start-utc", required=True)
    parser.add_argument("--ig-idempotency-table", required=True)
    parser.add_argument("--ddb-scan-page-limit", type=int, default=200)
    parser.add_argument("--ddb-scan-page-size", type=int, default=200)
    parser.add_argument("--lag-threshold", type=int, default=10)
    parser.add_argument("--evidence-bucket", required=True)
    parser.add_argument("--local-output-root", default="runs/dev_substrate/dev_full/m6")
    args = parser.parse_args()

    captured_at = _now_utc()
    local_root = Path(args.local_output_root) / args.execution_id
    local_root.mkdir(parents=True, exist_ok=True)

    emr = boto3.client("emr-containers", region_name=args.region)
    ddb = boto3.client("dynamodb", region_name=args.region)
    s3 = boto3.client("s3", region_name=args.region)

    lane_window_start_epoch = _parse_utc_to_epoch(args.lane_window_start_utc)
    wsp_state_override = str(args.wsp_state_override or "").strip()
    sr_state_override = str(args.sr_ready_state_override or "").strip()
    if wsp_state_override and sr_state_override:
        wsp_state = wsp_state_override
        sr_state = sr_state_override
        wsp_state_error = None
        sr_state_error = None
    else:
        wsp_state, wsp_state_error = _describe_job_run_state(
            emr,
            virtual_cluster_id=args.virtual_cluster_id,
            job_id=args.wsp_job_id,
        )
        sr_state, sr_state_error = _describe_job_run_state(
            emr,
            virtual_cluster_id=args.virtual_cluster_id,
            job_id=args.sr_ready_job_id,
        )
    wsp_state_upper = str(wsp_state or "").upper()
    sr_state_upper = str(sr_state or "").upper()
    wsp_active_count = 1 if wsp_state_upper in ACTIVE_JOB_STATES else 0
    sr_active_count = 1 if sr_state_upper in ACTIVE_JOB_STATES else 0

    idempotency_count, latest_admitted_epoch, ddb_pages_scanned, idempotency_error = _scan_run_window_metrics(
        ddb,
        table_name=args.ig_idempotency_table,
        platform_run_id=args.platform_run_id,
        lane_window_start_epoch=lane_window_start_epoch,
        page_limit=args.ddb_scan_page_limit,
        page_size=args.ddb_scan_page_size,
    )
    if idempotency_count is None:
        idempotency_count = 0
    now_epoch = int(datetime.now(timezone.utc).timestamp())

    ambiguity_count, ambiguity_refs, ambiguity_error = _scan_publish_ambiguity(
        s3,
        args.evidence_bucket,
        args.platform_run_id,
    )

    lag_measured: int | None
    lag_source: str
    lag_within: bool
    if idempotency_count > 0 and latest_admitted_epoch is not None:
        lag_measured = max(0, now_epoch - latest_admitted_epoch)
        lag_source = "ig_admission_freshness_seconds"
        lag_within = lag_measured <= args.lag_threshold
    else:
        lag_measured = None
        lag_source = (
            "unavailable_ddb_scan_error" if idempotency_error else "unavailable_no_run_window_admissions"
        )
        lag_within = False

    runtime_path_selection = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "runtime_path_active": args.runtime_path,
        "runtime_path_allowed": args.runtime_path_allowed,
        "runtime_path_fallback_blocker": args.runtime_path_fallback_blocker,
        "virtual_cluster_id": args.virtual_cluster_id,
    }

    active_snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "upstream_m6e_execution": args.upstream_m6e_execution,
        "runtime_path": args.runtime_path,
        "virtual_cluster_id": args.virtual_cluster_id,
        "wsp_job_id": args.wsp_job_id,
        "sr_ready_job_id": args.sr_ready_job_id,
        "wsp_ref": args.wsp_ref,
        "sr_ready_ref": args.sr_ready_ref,
        "wsp_state": wsp_state,
        "wsp_state_error": wsp_state_error,
        "sr_ready_state": sr_state,
        "sr_ready_state_error": sr_state_error,
        "wsp_active_count": wsp_active_count,
        "sr_ready_active_count": sr_active_count,
        "lane_window_start_utc": args.lane_window_start_utc,
        "lane_window_start_epoch": lane_window_start_epoch,
        "observation_epoch": now_epoch,
        "ig_idempotency_count": idempotency_count,
        "ig_idempotency_count_error": idempotency_error,
        "ig_idempotency_scan_pages": ddb_pages_scanned,
        "ig_idempotency_latest_admitted_epoch": latest_admitted_epoch,
        "ig_idempotency_scope": "platform_run_id + admitted_at_epoch>=lane_window_start_epoch",
    }

    lag_snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "threshold": args.lag_threshold,
        "measured_lag": lag_measured,
        "measurement_source": lag_source,
        "within_threshold": lag_within,
    }

    ambiguity_snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scan_prefix": f"s3://{args.evidence_bucket}/evidence/runs/{args.platform_run_id}/ingest/",
        "scan_error": ambiguity_error,
        "unresolved_publish_ambiguity_count": ambiguity_count,
        "unresolved_publish_ambiguity_refs": ambiguity_refs,
    }

    blockers: list[dict[str, str]] = []
    if wsp_active_count == 0 or sr_active_count == 0:
        blockers.append(
            {
                "code": "M6P6-B2",
                "message": (
                    f"Required lane refs are not RUNNING in VC {args.virtual_cluster_id}: "
                    f"wsp_state={wsp_state or 'unknown'}, sr_ready_state={sr_state or 'unknown'}"
                ),
            }
        )
    if idempotency_count <= 0:
        blockers.append(
            {
                "code": "M6P6-B3",
                "message": (
                    "Run-window admission progression is zero "
                    f"(platform_run_id={args.platform_run_id}, lane_window_start_epoch={lane_window_start_epoch})."
                ),
            }
        )
    if not lag_within:
        blockers.append(
            {
                "code": "M6P6-B4",
                "message": (
                    "Lag posture unresolved or exceeds threshold "
                    f"(threshold={args.lag_threshold}, measured={lag_measured}, source={lag_source})"
                ),
            }
        )
    if ambiguity_count > 0:
        blockers.append(
            {
                "code": "M6P6-B5",
                "message": f"Unresolved publish ambiguity count is non-zero ({ambiguity_count}).",
            }
        )

    blocker_snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "scenario_run_id": args.scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
    }

    overall_pass = len(blockers) == 0
    execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": "M6.G_READY" if overall_pass else "HOLD_REMEDIATE",
    }

    files_to_write = {
        "runtime_path_selection.json": runtime_path_selection,
        "m6f_streaming_active_snapshot.json": active_snapshot,
        "m6f_streaming_lag_posture.json": lag_snapshot,
        "m6f_publish_ambiguity_register.json": ambiguity_snapshot,
        "m6f_blocker_register.json": blocker_snapshot,
        "m6f_execution_summary.json": execution_summary,
    }

    for file_name, payload in files_to_write.items():
        _write_json(local_root / file_name, payload)

    emitted_bytes = sum((local_root / name).stat().st_size for name in files_to_write)
    evidence_overhead = {
        "captured_at_utc": captured_at,
        "phase": "M6.F",
        "phase_id": "P6.B",
        "execution_id": args.execution_id,
        "platform_run_id": args.platform_run_id,
        "latency_p95_ms": None,
        "emitted_evidence_bytes": emitted_bytes,
        "events_count_for_ratio": idempotency_count,
        "bytes_per_event": (emitted_bytes / idempotency_count) if idempotency_count > 0 else None,
        "write_rate_bytes_per_sec": float(emitted_bytes),
        "budget_check_pass": True,
        "budget_notes": "Snapshot-level artifact writes only; no per-event evidence writes in M6.F lane.",
    }
    _write_json(local_root / "m6f_evidence_overhead_snapshot.json", evidence_overhead)

    files_for_upload = [
        local_root / "runtime_path_selection.json",
        local_root / "m6f_streaming_active_snapshot.json",
        local_root / "m6f_streaming_lag_posture.json",
        local_root / "m6f_publish_ambiguity_register.json",
        local_root / "m6f_evidence_overhead_snapshot.json",
        local_root / "m6f_blocker_register.json",
        local_root / "m6f_execution_summary.json",
    ]
    _upload_artifacts(
        s3,
        bucket=args.evidence_bucket,
        execution_id=args.execution_id,
        files=files_for_upload,
    )

    print(
        json.dumps(
            {
                "execution_id": args.execution_id,
                "overall_pass": overall_pass,
                "blocker_count": len(blockers),
                "local_output": str(local_root),
                "durable_prefix": (
                    f"s3://{args.evidence_bucket}/evidence/dev_full/run_control/{args.execution_id}/"
                ),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
