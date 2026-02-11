#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
import yaml


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return loaded


def _check(condition: bool, name: str, detail: str, checks: list[dict[str, str]]) -> bool:
    status = "PASS" if condition else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    return condition


def _write_report(
    *,
    started_at: str,
    checks: list[dict[str, str]],
    decision: str,
    output_root: Path,
    artifact_prefix: str,
    details: dict[str, Any] | None = None,
) -> Path:
    finished_at = _now_utc()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_root / f"{artifact_prefix}_{stamp}.json"
    payload = {
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "decision": decision,
        "checks": checks,
    }
    if details:
        payload["details"] = details
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for item in checks:
        print(f"[{item['status']}] {item['name']}: {item['detail']}")
    print(f"Decision: {decision}")
    print(f"Evidence: {output_path.as_posix()}")
    return output_path


def _print_progress(message: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[progress {stamp}] {message}", flush=True)


def _resolve_pin(value: str | None, env_name: str, required: bool = True) -> str | None:
    if value and value.strip():
        return value.strip()
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    if required:
        raise ValueError(f"missing required pin: {env_name}")
    return None


def _s3_parts(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"expected s3 uri, got: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def _s3_client(region: str):
    return boto3.client("s3", region_name=region)


def _head_s3(client, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def _load_output_ids(ref_path: Path) -> list[str]:
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("output_ids") or []
    else:
        items = payload or []
    return [str(item).strip() for item in items if str(item).strip()]


def _required_refs(profile: dict[str, Any], context_mode: str) -> list[Path]:
    policy = profile.get("policy", {})
    refs: list[Path] = []
    traffic_ref = str(policy.get("traffic_output_ids_ref", "")).strip()
    context_ref = str(policy.get("context_output_ids_ref", "")).strip()
    baseline_ref = str(policy.get("context_output_ids_baseline_ref", "")).strip()
    if traffic_ref:
        refs.append(Path(traffic_ref))
    if context_mode == "fraud":
        if context_ref:
            refs.append(Path(context_ref))
    elif context_mode == "baseline":
        if baseline_ref:
            refs.append(Path(baseline_ref))
    elif context_mode == "both":
        if context_ref:
            refs.append(Path(context_ref))
        if baseline_ref:
            refs.append(Path(baseline_ref))
    elif context_mode == "none":
        pass
    else:
        raise ValueError(f"unsupported context mode: {context_mode}")
    seen: set[str] = set()
    ordered: list[Path] = []
    for ref in refs:
        key = ref.as_posix()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(ref)
    return ordered


def _collect_local_stats(source_root: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    if source_root.is_file():
        return 1, int(source_root.stat().st_size)
    for root, _, files in os.walk(source_root):
        for filename in files:
            path = Path(root) / filename
            try:
                size = path.stat().st_size
            except OSError:
                continue
            file_count += 1
            total_bytes += int(size)
    return file_count, total_bytes


def _collect_s3_stats(client, bucket: str, prefix: str) -> tuple[int, int]:
    count = 0
    total_bytes = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            count += 1
            total_bytes += int(item.get("Size", 0))
    return count, total_bytes


def _pump_stream(stream, prefix: str) -> None:
    if stream is None:
        return
    for line in iter(stream.readline, ""):
        if not line:
            break
        print(f"{prefix}{line.rstrip()}", flush=True)
    stream.close()


def _run_streaming_command(command: list[str]) -> int:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    out_thread = threading.Thread(target=_pump_stream, args=(process.stdout, "[sync] "), daemon=True)
    err_thread = threading.Thread(target=_pump_stream, args=(process.stderr, "[sync:err] "), daemon=True)
    out_thread.start()
    err_thread.start()
    return_code = process.wait()
    out_thread.join(timeout=2.0)
    err_thread.join(timeout=2.0)
    return return_code


def cmd_preflight(args: argparse.Namespace) -> int:
    started = _now_utc()
    checks: list[dict[str, str]] = []
    details: dict[str, Any] = {}
    all_ok = True

    try:
        profile = _load_yaml(Path(args.profile))
    except Exception as exc:
        checks.append({"name": "load_profile", "status": "FAIL", "detail": str(exc)})
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_preflight",
        )
        return 2

    try:
        source_root = _resolve_pin(args.source_root, "DEV_MIN_ORACLE_SYNC_SOURCE")
        engine_run_root = _resolve_pin(args.engine_run_root, "DEV_MIN_ORACLE_ENGINE_RUN_ROOT")
        scenario_id = _resolve_pin(args.scenario_id, "DEV_MIN_ORACLE_SCENARIO_ID")
        stream_view_root = _resolve_pin(args.stream_view_root, "DEV_MIN_ORACLE_STREAM_VIEW_ROOT")
        oracle_root = _resolve_pin(args.oracle_root, "DEV_MIN_ORACLE_ROOT", required=False)
        aws_region = _resolve_pin(args.aws_region, "DEV_MIN_AWS_REGION")
    except ValueError as exc:
        checks.append({"name": "required_pins", "status": "FAIL", "detail": str(exc)})
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_preflight",
        )
        return 2

    details["source_root"] = source_root
    details["engine_run_root"] = engine_run_root
    details["scenario_id"] = scenario_id
    details["stream_view_root"] = stream_view_root

    all_ok &= _check(engine_run_root.startswith("s3://"), "engine_run_root_managed", engine_run_root, checks)
    all_ok &= _check(stream_view_root.startswith("s3://"), "stream_view_root_managed", stream_view_root, checks)
    all_ok &= _check(bool(scenario_id), "scenario_id_set", scenario_id or "missing", checks)

    source_path = Path(source_root)
    all_ok &= _check(source_path.exists(), "source_root_exists", source_root, checks)
    if source_path.exists():
        source_files, source_bytes = _collect_local_stats(source_path)
        details["source_file_count"] = source_files
        details["source_total_bytes"] = source_bytes
        all_ok &= _check(source_files > 0, "source_has_files", f"files={source_files}", checks)

    if oracle_root:
        all_ok &= _check(
            engine_run_root.startswith(oracle_root.rstrip("/") + "/"),
            "engine_root_under_oracle_root",
            f"oracle_root={oracle_root}",
            checks,
        )

    refs_ok = True
    refs: list[Path] = _required_refs(profile, args.context_mode)
    details["output_id_refs"] = [ref.as_posix() for ref in refs]
    combined_output_ids: list[str] = []
    for ref in refs:
        present = ref.exists()
        refs_ok &= present
        _check(present, f"output_ref_{ref.as_posix()}", "present" if present else "missing", checks)
        if present:
            ids = _load_output_ids(ref)
            combined_output_ids.extend(ids)
            all_ok &= _check(bool(ids), f"output_ref_non_empty_{ref.as_posix()}", f"count={len(ids)}", checks)
    combined_unique = sorted(set(combined_output_ids))
    details["required_output_ids"] = combined_unique
    all_ok &= refs_ok and bool(combined_unique)
    if not combined_unique:
        _check(False, "required_output_ids", "none resolved from policy refs", checks)

    if not args.skip_aws_head:
        try:
            client = _s3_client(aws_region)
            engine_bucket, _ = _s3_parts(engine_run_root)
            stream_bucket, _ = _s3_parts(stream_view_root)
            client.head_bucket(Bucket=engine_bucket)
            _check(True, "head_bucket_engine", engine_bucket, checks)
            if stream_bucket != engine_bucket:
                client.head_bucket(Bucket=stream_bucket)
            _check(True, "head_bucket_stream", stream_bucket, checks)
        except Exception as exc:
            all_ok &= _check(False, "aws_bucket_head", str(exc), checks)

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    _write_report(
        started_at=started,
        checks=checks,
        decision=decision,
        output_root=Path(args.output_root),
        artifact_prefix="phase3c1_oracle_preflight",
        details=details,
    )
    return 0 if decision == "PASS" else 2


def cmd_sync(args: argparse.Namespace) -> int:
    started = _now_utc()
    checks: list[dict[str, str]] = []
    details: dict[str, Any] = {}
    all_ok = True

    try:
        source_root = _resolve_pin(args.source_root, "DEV_MIN_ORACLE_SYNC_SOURCE")
        engine_run_root = _resolve_pin(args.engine_run_root, "DEV_MIN_ORACLE_ENGINE_RUN_ROOT")
        aws_region = _resolve_pin(args.aws_region, "DEV_MIN_AWS_REGION")
    except ValueError as exc:
        checks.append({"name": "required_pins", "status": "FAIL", "detail": str(exc)})
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_sync",
        )
        return 2

    source_path = Path(source_root)
    all_ok &= _check(source_path.exists(), "source_root_exists", source_root, checks)
    all_ok &= _check(engine_run_root.startswith("s3://"), "engine_run_root_managed", engine_run_root, checks)
    aws_bin = shutil.which("aws")
    all_ok &= _check(aws_bin is not None, "aws_cli_available", aws_bin or "not found", checks)
    if not all_ok:
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_sync",
        )
        return 2

    source_files, source_bytes = _collect_local_stats(source_path)
    details["source_root"] = source_root
    details["engine_run_root"] = engine_run_root
    details["source_file_count"] = source_files
    details["source_total_bytes"] = source_bytes
    _check(source_files > 0, "source_has_files", f"files={source_files}", checks)
    if source_files <= 0:
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_sync",
            details=details,
        )
        return 2

    bucket, prefix = _s3_parts(engine_run_root)
    client = _s3_client(aws_region)
    try:
        client.head_bucket(Bucket=bucket)
        _check(True, "head_bucket_destination", bucket, checks)
    except Exception as exc:
        _check(False, "head_bucket_destination", str(exc), checks)
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_sync",
            details=details,
        )
        return 2

    progress_seconds = max(float(args.progress_seconds), 5.0)
    stop_event = threading.Event()

    def _progress_worker() -> None:
        while not stop_event.wait(progress_seconds):
            try:
                dst_count, dst_bytes = _collect_s3_stats(client, bucket, prefix)
            except Exception as exc:
                _print_progress(f"destination scan failed: {exc}")
                continue
            file_pct = (dst_count / source_files * 100.0) if source_files else 0.0
            byte_pct = (dst_bytes / source_bytes * 100.0) if source_bytes else 0.0
            _print_progress(
                f"sync destination files={dst_count}/{source_files} ({file_pct:.1f}%) "
                f"bytes={dst_bytes}/{source_bytes} ({byte_pct:.1f}%)"
            )

    command = [aws_bin or "aws", "s3", "sync", source_root, engine_run_root, "--region", aws_region]
    if args.sync_extra_args:
        command.extend(shlex.split(args.sync_extra_args))
    details["sync_command"] = command
    _print_progress(f"starting sync: {' '.join(command)}")
    _print_progress("live aws output is prefixed with [sync] / [sync:err]")

    progress_thread = threading.Thread(target=_progress_worker, daemon=True)
    progress_thread.start()
    run_start = time.monotonic()
    return_code = _run_streaming_command(command)
    elapsed = time.monotonic() - run_start
    stop_event.set()
    progress_thread.join(timeout=2.0)

    dst_count, dst_bytes = _collect_s3_stats(client, bucket, prefix)
    details["destination_file_count"] = dst_count
    details["destination_total_bytes"] = dst_bytes
    details["elapsed_seconds"] = round(elapsed, 2)
    details["sync_return_code"] = return_code
    _check(return_code == 0, "aws_sync_exit_code", f"code={return_code}", checks)
    _check(dst_count >= source_files, "destination_file_floor", f"dest={dst_count},source={source_files}", checks)
    _check(dst_bytes >= source_bytes, "destination_byte_floor", f"dest={dst_bytes},source={source_bytes}", checks)

    decision = "PASS" if return_code == 0 else "FAIL_CLOSED"
    _write_report(
        started_at=started,
        checks=checks,
        decision=decision,
        output_root=Path(args.output_root),
        artifact_prefix="phase3c1_oracle_sync",
        details=details,
    )
    return 0 if decision == "PASS" else 2


def _run_command(command: list[str], *, prefix: str = "", passthrough: bool = False) -> int:
    if passthrough:
        completed = subprocess.run(command, check=False)
        return int(completed.returncode)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    out_thread = threading.Thread(target=_pump_stream, args=(process.stdout, prefix), daemon=True)
    err_thread = threading.Thread(target=_pump_stream, args=(process.stderr, f"{prefix}ERR: "), daemon=True)
    out_thread.start()
    err_thread.start()
    code = process.wait()
    out_thread.join(timeout=2.0)
    err_thread.join(timeout=2.0)
    return code


def cmd_stream_sort(args: argparse.Namespace) -> int:
    started = _now_utc()
    checks: list[dict[str, str]] = []
    details: dict[str, Any] = {}
    all_ok = True

    try:
        profile_path = Path(args.profile)
        profile = _load_yaml(profile_path)
        engine_run_root = _resolve_pin(args.engine_run_root, "DEV_MIN_ORACLE_ENGINE_RUN_ROOT")
        scenario_id = _resolve_pin(args.scenario_id, "DEV_MIN_ORACLE_SCENARIO_ID")
        stream_view_root = _resolve_pin(args.stream_view_root, "DEV_MIN_ORACLE_STREAM_VIEW_ROOT")
        refs = _required_refs(profile, args.context_mode)
    except Exception as exc:
        checks.append({"name": "inputs", "status": "FAIL", "detail": str(exc)})
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_stream_sort",
        )
        return 2

    details["refs"] = [ref.as_posix() for ref in refs]
    details["engine_run_root"] = engine_run_root
    details["scenario_id"] = scenario_id
    details["stream_view_root"] = stream_view_root

    for ref in refs:
        if not ref.exists():
            all_ok &= _check(False, f"ref_exists_{ref.as_posix()}", "missing", checks)
            continue
        output_ids = _load_output_ids(ref)
        all_ok &= _check(bool(output_ids), f"ref_non_empty_{ref.as_posix()}", f"count={len(output_ids)}", checks)
        if not output_ids:
            continue
        _print_progress(f"stream-sort start ref={ref.as_posix()} output_ids={len(output_ids)}")
        command = [
            sys.executable,
            "-m",
            "fraud_detection.oracle_store.stream_sort_cli",
            "--profile",
            args.profile,
            "--engine-run-root",
            engine_run_root,
            "--scenario-id",
            scenario_id,
            "--stream-view-root",
            stream_view_root,
            "--output-ids-ref",
            ref.as_posix(),
        ]
        _print_progress("stream-sort running with passthrough terminal output (duckdb progress enabled if configured)")
        code = _run_command(command, passthrough=True)
        all_ok &= _check(code == 0, f"stream_sort_{ref.as_posix()}", f"exit={code}", checks)
        if code != 0:
            break

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    _write_report(
        started_at=started,
        checks=checks,
        decision=decision,
        output_root=Path(args.output_root),
        artifact_prefix="phase3c1_oracle_stream_sort",
        details=details,
    )
    return 0 if decision == "PASS" else 2


def _sanitize_job_name_fragment(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:64] or "output"


def _resolve_float_arg(value: float | None, env_name: str, default: float) -> float:
    if value is not None:
        return float(value)
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return float(default)
    return float(raw)


def _resolve_int_arg(value: int | None, env_name: str, default: int) -> int:
    if value is not None:
        return int(value)
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return int(default)
    return int(raw)


def _batch_tail_logs(
    logs_client,
    *,
    log_group: str,
    log_stream: str,
    token: str | None,
    prefix: str,
) -> str | None:
    kwargs: dict[str, Any] = {
        "logGroupName": log_group,
        "logStreamName": log_stream,
        "startFromHead": True,
    }
    if token:
        kwargs["nextToken"] = token
    response = logs_client.get_log_events(**kwargs)
    for event in response.get("events", []):
        message = str(event.get("message", "")).rstrip()
        if message:
            print(f"{prefix}{message}", flush=True)
    next_token = response.get("nextForwardToken")
    if next_token == token:
        return token
    return next_token


def _wait_for_batch_job(
    *,
    batch_client,
    logs_client,
    job_id: str,
    job_name: str,
    log_group: str,
    stream_logs: bool,
    poll_seconds: float,
    timeout_seconds: int,
) -> tuple[bool, dict[str, Any]]:
    start_monotonic = time.monotonic()
    seen_status: str | None = None
    log_token: str | None = None
    log_stream: str | None = None

    while True:
        response = batch_client.describe_jobs(jobs=[job_id])
        jobs = response.get("jobs", [])
        if not jobs:
            return False, {"job_id": job_id, "status": "MISSING", "reason": "describe_jobs_empty"}
        job = jobs[0]
        status = str(job.get("status", "UNKNOWN"))
        if status != seen_status:
            _print_progress(f"batch job {job_name} status={status}")
            seen_status = status

        container = job.get("container") or {}
        if not log_stream:
            stream = container.get("logStreamName")
            if stream:
                log_stream = str(stream)
        if stream_logs and log_stream:
            try:
                log_token = _batch_tail_logs(
                    logs_client,
                    log_group=log_group,
                    log_stream=log_stream,
                    token=log_token,
                    prefix=f"[batch:{job_name}] ",
                )
            except Exception as exc:
                _print_progress(f"batch log tail warning job={job_name}: {exc}")

        if status in {"SUCCEEDED", "FAILED"}:
            reason = str(job.get("statusReason") or container.get("reason") or "")
            exit_code = container.get("exitCode")
            return (
                status == "SUCCEEDED",
                {
                    "job_id": job_id,
                    "job_name": job_name,
                    "status": status,
                    "status_reason": reason,
                    "exit_code": exit_code,
                    "log_stream": log_stream,
                },
            )

        if timeout_seconds > 0 and (time.monotonic() - start_monotonic) > float(timeout_seconds):
            return False, {
                "job_id": job_id,
                "job_name": job_name,
                "status": status,
                "status_reason": f"timeout_after_seconds={timeout_seconds}",
                "log_stream": log_stream,
            }

        time.sleep(max(2.0, poll_seconds))


def cmd_stream_sort_managed(args: argparse.Namespace) -> int:
    started = _now_utc()
    checks: list[dict[str, str]] = []
    details: dict[str, Any] = {}
    all_ok = True

    try:
        profile = _load_yaml(Path(args.profile))
        engine_run_root = _resolve_pin(args.engine_run_root, "DEV_MIN_ORACLE_ENGINE_RUN_ROOT")
        scenario_id = _resolve_pin(args.scenario_id, "DEV_MIN_ORACLE_SCENARIO_ID")
        stream_view_root = _resolve_pin(args.stream_view_root, "DEV_MIN_ORACLE_STREAM_VIEW_ROOT")
        aws_region = _resolve_pin(args.aws_region, "DEV_MIN_AWS_REGION")
        batch_job_queue = _resolve_pin(args.batch_job_queue, "DEV_MIN_PHASE3C1_BATCH_JOB_QUEUE")
        batch_job_definition = _resolve_pin(
            args.batch_job_definition, "DEV_MIN_PHASE3C1_BATCH_JOB_DEFINITION"
        )
        batch_job_name_prefix = (
            _resolve_pin(
                args.batch_job_name_prefix,
                "DEV_MIN_PHASE3C1_BATCH_JOB_NAME_PREFIX",
                required=False,
            )
            or "fraud-platform-dev-min-oracle-sort"
        )
        batch_log_group = (
            _resolve_pin(args.batch_log_group, "DEV_MIN_PHASE3C1_BATCH_LOG_GROUP", required=False)
            or "/aws/batch/job"
        )
        poll_seconds = _resolve_float_arg(
            args.batch_poll_seconds, "DEV_MIN_PHASE3C1_BATCH_POLL_SECONDS", 15.0
        )
        timeout_seconds = _resolve_int_arg(
            args.batch_timeout_seconds, "DEV_MIN_PHASE3C1_BATCH_TIMEOUT_SECONDS", 21600
        )
        refs = _required_refs(profile, args.context_mode)
    except Exception as exc:
        checks.append({"name": "inputs", "status": "FAIL", "detail": str(exc)})
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_stream_sort_managed",
        )
        return 2

    if poll_seconds <= 0:
        poll_seconds = 15.0
    if timeout_seconds < 0:
        timeout_seconds = 21600

    details["refs"] = [ref.as_posix() for ref in refs]
    details["engine_run_root"] = engine_run_root
    details["scenario_id"] = scenario_id
    details["stream_view_root"] = stream_view_root
    details["aws_region"] = aws_region
    details["batch_job_queue"] = batch_job_queue
    details["batch_job_definition"] = batch_job_definition
    details["batch_job_name_prefix"] = batch_job_name_prefix
    details["batch_log_group"] = batch_log_group
    details["batch_poll_seconds"] = poll_seconds
    details["batch_timeout_seconds"] = timeout_seconds
    details["wait_for_jobs"] = not args.no_wait
    details["stream_logs"] = not args.no_log_tail

    output_ids: list[str] = []
    for ref in refs:
        if not ref.exists():
            all_ok &= _check(False, f"ref_exists_{ref.as_posix()}", "missing", checks)
            continue
        ids = _load_output_ids(ref)
        all_ok &= _check(bool(ids), f"ref_non_empty_{ref.as_posix()}", f"count={len(ids)}", checks)
        output_ids.extend(ids)
    output_ids = sorted(set(output_ids))
    details["required_output_ids"] = output_ids
    all_ok &= _check(bool(output_ids), "required_output_ids_non_empty", f"count={len(output_ids)}", checks)
    if not all_ok:
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_stream_sort_managed",
            details=details,
        )
        return 2

    batch_client = boto3.client("batch", region_name=aws_region)
    logs_client = boto3.client("logs", region_name=aws_region)

    try:
        queue_probe = batch_client.describe_job_queues(jobQueues=[batch_job_queue])
        queue_present = bool(queue_probe.get("jobQueues"))
        all_ok &= _check(queue_present, "batch_job_queue_exists", batch_job_queue, checks)
    except Exception as exc:
        all_ok &= _check(False, "batch_job_queue_exists", str(exc), checks)
    try:
        definition_probe = batch_client.describe_job_definitions(
            jobDefinitions=[batch_job_definition]
        )
        definition_present = bool(definition_probe.get("jobDefinitions"))
        all_ok &= _check(definition_present, "batch_job_definition_exists", batch_job_definition, checks)
    except Exception as exc:
        all_ok &= _check(False, "batch_job_definition_exists", str(exc), checks)
    if not all_ok:
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_stream_sort_managed",
            details=details,
        )
        return 2

    passthrough_env = [
        "STREAM_SORT_PROGRESS_SECONDS",
        "STREAM_SORT_THREADS",
        "STREAM_SORT_MEMORY_LIMIT",
        "STREAM_SORT_TEMP_DIR",
        "STREAM_SORT_MAX_TEMP_SIZE",
        "STREAM_SORT_PRESERVE_ORDER",
        "STREAM_SORT_CHUNK_DAYS",
        "STREAM_SORT_STATS_RETRIES",
        "STREAM_SORT_STATS_RETRY_DELAY",
    ]
    env_overrides: list[dict[str, str]] = [{"name": "PYTHONUNBUFFERED", "value": "1"}]
    for key in passthrough_env:
        value = os.getenv(key, "").strip()
        if value:
            env_overrides.append({"name": key, "value": value})

    submitted_jobs: list[dict[str, Any]] = []
    ts_stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    for output_id in output_ids:
        fragment = _sanitize_job_name_fragment(output_id)
        job_name = _sanitize_job_name_fragment(f"{batch_job_name_prefix}-{fragment}-{ts_stamp}")
        command = [
            args.container_python,
            "-m",
            "fraud_detection.oracle_store.stream_sort_cli",
            "--profile",
            args.container_profile_path,
            "--engine-run-root",
            engine_run_root,
            "--scenario-id",
            scenario_id,
            "--stream-view-root",
            stream_view_root,
            "--output-id",
            output_id,
        ]
        container_overrides: dict[str, Any] = {"command": command, "environment": env_overrides}
        resource_requirements: list[dict[str, str]] = []
        if args.batch_vcpu and int(args.batch_vcpu) > 0:
            resource_requirements.append({"type": "VCPU", "value": str(int(args.batch_vcpu))})
        if args.batch_memory_mib and int(args.batch_memory_mib) > 0:
            resource_requirements.append({"type": "MEMORY", "value": str(int(args.batch_memory_mib))})
        if resource_requirements:
            container_overrides["resourceRequirements"] = resource_requirements

        _print_progress(
            f"batch submit output_id={output_id} queue={batch_job_queue} definition={batch_job_definition}"
        )
        try:
            response = batch_client.submit_job(
                jobName=job_name,
                jobQueue=batch_job_queue,
                jobDefinition=batch_job_definition,
                containerOverrides=container_overrides,
            )
        except Exception as exc:
            all_ok &= _check(False, f"batch_submit_{output_id}", str(exc), checks)
            break
        job_id = str(response.get("jobId", ""))
        all_ok &= _check(bool(job_id), f"batch_submit_{output_id}", f"job_id={job_id}", checks)
        submitted_jobs.append({"output_id": output_id, "job_id": job_id, "job_name": job_name})

    details["submitted_jobs"] = submitted_jobs
    if not all_ok:
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_stream_sort_managed",
            details=details,
        )
        return 2

    if not args.no_wait:
        completed: list[dict[str, Any]] = []
        for job in submitted_jobs:
            ok, result = _wait_for_batch_job(
                batch_client=batch_client,
                logs_client=logs_client,
                job_id=str(job["job_id"]),
                job_name=str(job["job_name"]),
                log_group=batch_log_group,
                stream_logs=not args.no_log_tail,
                poll_seconds=poll_seconds,
                timeout_seconds=timeout_seconds,
            )
            completed.append(result)
            status = str(result.get("status", "UNKNOWN"))
            detail = f"job_id={result.get('job_id')} status={status}"
            reason = str(result.get("status_reason", "")).strip()
            if reason:
                detail += f" reason={reason}"
            all_ok &= _check(ok, f"batch_complete_{job['output_id']}", detail, checks)
            if not ok:
                break
        details["completed_jobs"] = completed

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    _write_report(
        started_at=started,
        checks=checks,
        decision=decision,
        output_root=Path(args.output_root),
        artifact_prefix="phase3c1_oracle_stream_sort_managed",
        details=details,
    )
    return 0 if decision == "PASS" else 2


def _extract_json_block(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if not candidate:
        return None
    for line in reversed(candidate.splitlines()):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def _stream_view_checks(
    *,
    aws_region: str,
    stream_view_root: str,
    output_ids: list[str],
    checks: list[dict[str, str]],
) -> bool:
    if not stream_view_root.startswith("s3://"):
        return _check(False, "stream_view_root_scheme", stream_view_root, checks)
    bucket, base_prefix = _s3_parts(stream_view_root)
    client = _s3_client(aws_region)
    ok = True
    for output_id in output_ids:
        prefix = f"{base_prefix.rstrip('/')}/output_id={output_id}".strip("/")
        manifest_key = f"{prefix}/_stream_view_manifest.json"
        receipt_key = f"{prefix}/_stream_sort_receipt.json"
        has_manifest = _head_s3(client, bucket, manifest_key)
        has_receipt = _head_s3(client, bucket, receipt_key)
        ok &= _check(has_manifest, f"stream_manifest_{output_id}", f"s3://{bucket}/{manifest_key}", checks)
        ok &= _check(has_receipt, f"stream_receipt_{output_id}", f"s3://{bucket}/{receipt_key}", checks)
        part_prefix = f"{prefix}/part-"
        part_count = 0
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=part_prefix):
            for item in page.get("Contents", []):
                key = str(item.get("Key", ""))
                if key.endswith(".parquet"):
                    part_count += 1
        ok &= _check(part_count > 0, f"stream_parts_{output_id}", f"part_files={part_count}", checks)
    return ok


def cmd_validate(args: argparse.Namespace) -> int:
    started = _now_utc()
    checks: list[dict[str, str]] = []
    details: dict[str, Any] = {}
    all_ok = True

    try:
        profile_path = Path(args.profile)
        profile = _load_yaml(profile_path)
        engine_run_root = _resolve_pin(args.engine_run_root, "DEV_MIN_ORACLE_ENGINE_RUN_ROOT")
        scenario_id = _resolve_pin(args.scenario_id, "DEV_MIN_ORACLE_SCENARIO_ID")
        stream_view_root = _resolve_pin(args.stream_view_root, "DEV_MIN_ORACLE_STREAM_VIEW_ROOT")
        aws_region = _resolve_pin(args.aws_region, "DEV_MIN_AWS_REGION")
        refs = _required_refs(profile, args.context_mode)
    except Exception as exc:
        checks.append({"name": "inputs", "status": "FAIL", "detail": str(exc)})
        _write_report(
            started_at=started,
            checks=checks,
            decision="FAIL_CLOSED",
            output_root=Path(args.output_root),
            artifact_prefix="phase3c1_oracle_validate",
        )
        return 2

    output_ids: list[str] = []
    for ref in refs:
        if ref.exists():
            output_ids.extend(_load_output_ids(ref))
    output_ids = sorted(set(output_ids))
    details["required_output_ids"] = output_ids
    details["stream_view_root"] = stream_view_root
    details["engine_run_root"] = engine_run_root
    details["scenario_id"] = scenario_id

    if not output_ids:
        all_ok &= _check(False, "required_output_ids", "none resolved", checks)

    oracle_cmd = [
        sys.executable,
        "-m",
        "fraud_detection.oracle_store.cli",
        "--profile",
        args.profile,
        "--engine-run-root",
        engine_run_root,
        "--scenario-id",
        scenario_id,
        "--strict-seal",
    ]
    if output_ids:
        oracle_cmd.extend(["--output-ids", ",".join(output_ids)])

    proc = subprocess.run(oracle_cmd, capture_output=True, text=True, check=False)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    oracle_payload = _extract_json_block(proc.stdout)
    details["oracle_checker_exit_code"] = proc.returncode
    details["oracle_checker_report"] = oracle_payload
    all_ok &= _check(proc.returncode == 0, "oracle_checker_strict", f"exit={proc.returncode}", checks)
    if isinstance(oracle_payload, dict):
        status = str(oracle_payload.get("status", "UNKNOWN"))
        all_ok &= _check(status == "OK", "oracle_checker_status", status, checks)

    if output_ids:
        all_ok &= _stream_view_checks(
            aws_region=aws_region,
            stream_view_root=stream_view_root,
            output_ids=output_ids,
            checks=checks,
        )

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    _write_report(
        started_at=started,
        checks=checks,
        decision=decision,
        output_root=Path(args.output_root),
        artifact_prefix="phase3c1_oracle_validate",
        details=details,
    )
    return 0 if decision == "PASS" else 2


def cmd_run(args: argparse.Namespace) -> int:
    preflight_args = argparse.Namespace(**vars(args))
    sync_args = argparse.Namespace(**vars(args))
    sort_args = argparse.Namespace(**vars(args))
    validate_args = argparse.Namespace(**vars(args))
    if cmd_preflight(preflight_args) != 0:
        return 2
    if cmd_sync(sync_args) != 0:
        return 2
    if cmd_stream_sort(sort_args) != 0:
        return 2
    return cmd_validate(validate_args)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default="config/platform/profiles/dev_min.yaml", help="Path to dev_min profile")
    parser.add_argument(
        "--output-root",
        default="runs/fraud-platform/dev_substrate/phase3",
        help="Directory for phase evidence artifacts",
    )
    parser.add_argument(
        "--context-mode",
        choices=["fraud", "baseline", "both", "none"],
        default="fraud",
        help="Context output-id selection mode",
    )
    parser.add_argument("--source-root", help="Oracle source root override (default DEV_MIN_ORACLE_SYNC_SOURCE)")
    parser.add_argument(
        "--engine-run-root",
        help="Destination Oracle engine run root override (default DEV_MIN_ORACLE_ENGINE_RUN_ROOT)",
    )
    parser.add_argument("--scenario-id", help="Scenario id override (default DEV_MIN_ORACLE_SCENARIO_ID)")
    parser.add_argument(
        "--stream-view-root",
        help="Stream view root override (default DEV_MIN_ORACLE_STREAM_VIEW_ROOT)",
    )
    parser.add_argument("--oracle-root", help="Oracle root override (default DEV_MIN_ORACLE_ROOT)")
    parser.add_argument("--aws-region", help="AWS region override (default DEV_MIN_AWS_REGION)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dev-substrate Phase 3.C.1 Oracle authority lock runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight", help="Validate O1 pins and readiness before sync")
    _add_common_args(preflight_parser)
    preflight_parser.add_argument("--skip-aws-head", action="store_true", help="Skip S3 head_bucket checks")
    preflight_parser.set_defaults(handler=cmd_preflight)

    sync_parser = subparsers.add_parser("sync", help="Run landing sync with terminal progress")
    _add_common_args(sync_parser)
    sync_parser.add_argument(
        "--progress-seconds",
        type=float,
        default=15.0,
        help="Polling interval for destination progress snapshots",
    )
    sync_parser.add_argument(
        "--sync-extra-args",
        default="",
        help="Extra args appended to aws s3 sync command (quoted)",
    )
    sync_parser.set_defaults(handler=cmd_sync)

    sort_parser = subparsers.add_parser("stream-sort", help="Run stream sort for required output-id refs")
    _add_common_args(sort_parser)
    sort_parser.set_defaults(handler=cmd_stream_sort)

    managed_sort_parser = subparsers.add_parser(
        "stream-sort-managed",
        help="Submit stream sort jobs to AWS Batch (managed compute lane)",
    )
    _add_common_args(managed_sort_parser)
    managed_sort_parser.add_argument(
        "--batch-job-queue",
        help="AWS Batch job queue (default DEV_MIN_PHASE3C1_BATCH_JOB_QUEUE)",
    )
    managed_sort_parser.add_argument(
        "--batch-job-definition",
        help="AWS Batch job definition (default DEV_MIN_PHASE3C1_BATCH_JOB_DEFINITION)",
    )
    managed_sort_parser.add_argument(
        "--batch-job-name-prefix",
        help="Batch job name prefix (default DEV_MIN_PHASE3C1_BATCH_JOB_NAME_PREFIX)",
    )
    managed_sort_parser.add_argument(
        "--batch-log-group",
        help="CloudWatch Logs group for batch jobs (default DEV_MIN_PHASE3C1_BATCH_LOG_GROUP or /aws/batch/job)",
    )
    managed_sort_parser.add_argument(
        "--batch-poll-seconds",
        type=float,
        help="Batch status/log polling interval seconds (default DEV_MIN_PHASE3C1_BATCH_POLL_SECONDS or 15)",
    )
    managed_sort_parser.add_argument(
        "--batch-timeout-seconds",
        type=int,
        help="Per-job timeout seconds while waiting (default DEV_MIN_PHASE3C1_BATCH_TIMEOUT_SECONDS or 21600)",
    )
    managed_sort_parser.add_argument(
        "--container-python",
        default="python",
        help="Python executable inside container image",
    )
    managed_sort_parser.add_argument(
        "--container-profile-path",
        default="config/platform/profiles/dev_min.yaml",
        help="Profile path inside container image filesystem",
    )
    managed_sort_parser.add_argument(
        "--batch-vcpu",
        type=int,
        help="Optional Batch container VCPU override",
    )
    managed_sort_parser.add_argument(
        "--batch-memory-mib",
        type=int,
        help="Optional Batch container MEMORY (MiB) override",
    )
    managed_sort_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit jobs and return without waiting for completion",
    )
    managed_sort_parser.add_argument(
        "--no-log-tail",
        action="store_true",
        help="Disable CloudWatch log tail while waiting",
    )
    managed_sort_parser.set_defaults(handler=cmd_stream_sort_managed)

    validate_parser = subparsers.add_parser("validate", help="Run strict Oracle + stream-view validation")
    _add_common_args(validate_parser)
    validate_parser.set_defaults(handler=cmd_validate)

    run_parser = subparsers.add_parser("run", help="Run preflight -> sync -> stream-sort -> validate")
    _add_common_args(run_parser)
    run_parser.add_argument("--skip-aws-head", action="store_true", help="Skip S3 head_bucket checks")
    run_parser.add_argument(
        "--progress-seconds",
        type=float,
        default=15.0,
        help="Polling interval for destination progress snapshots",
    )
    run_parser.add_argument(
        "--sync-extra-args",
        default="",
        help="Extra args appended to aws s3 sync command (quoted)",
    )
    run_parser.set_defaults(handler=cmd_run)

    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
