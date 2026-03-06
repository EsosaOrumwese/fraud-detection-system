#!/usr/bin/env python3
"""Build fresh PR3-S1 steady evidence from managed AWS telemetry surfaces."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_time_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def submit_athena_count_query(
    *,
    athena: Any,
    database: str,
    table: str,
    window_start_utc: str,
    window_end_utc: str,
    output_location: str,
) -> str:
    sql = (
        "SELECT count(*) AS in_window_rows "
        f"FROM {database}.{table} "
        "WHERE COALESCE(CAST(try(from_iso8601_timestamp(ts_utc)) AS timestamp), try(cast(ts_utc AS timestamp))) "
        f"BETWEEN timestamp '{window_start_utc.replace('T', ' ').replace('Z', '')}' "
        f"AND timestamp '{window_end_utc.replace('T', ' ').replace('Z', '')}'"
    )
    response = athena.start_query_execution(
        QueryString=sql,
        ResultConfiguration={"OutputLocation": output_location},
    )
    return str(response["QueryExecutionId"])


def wait_athena_query(athena: Any, query_id: str, *, timeout_seconds: int = 900) -> dict[str, Any]:
    started = time.time()
    while True:
        payload = athena.get_query_execution(QueryExecutionId=query_id)
        status = payload.get("QueryExecution", {}).get("Status", {})
        state = str(status.get("State", "")).upper()
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return payload
        if (time.time() - started) > timeout_seconds:
            raise RuntimeError(f"Athena query timed out: {query_id}")
        time.sleep(2)


def read_athena_count_result(athena: Any, query_id: str) -> int:
    payload = athena.get_query_results(QueryExecutionId=query_id)
    rows = payload.get("ResultSet", {}).get("Rows", [])
    if len(rows) < 2:
        raise RuntimeError(f"Athena result has no data row: {query_id}")
    raw = rows[1].get("Data", [{}])[0].get("VarCharValue", "0")
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Unable to parse Athena count result: {raw}") from exc


def get_cloudwatch_metric(
    *,
    cw: Any,
    metric_name: str,
    dimensions: list[dict[str, str]],
    start_time: datetime,
    end_time: datetime,
    period_seconds: int,
    statistics: list[str] | None = None,
    extended_statistics: list[str] | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "Namespace": "AWS/ApiGateway",
        "MetricName": metric_name,
        "Dimensions": dimensions,
        "StartTime": start_time,
        "EndTime": end_time,
        "Period": period_seconds,
    }
    if statistics:
        kwargs["Statistics"] = statistics
    if extended_statistics:
        kwargs["ExtendedStatistics"] = extended_statistics
    result = cw.get_metric_statistics(**kwargs)
    return list(result.get("Datapoints", []))


def sum_stat(datapoints: list[dict[str, Any]], key: str = "Sum") -> float:
    total = 0.0
    for row in datapoints:
        total += parse_float(row.get(key), 0.0)
    return total


def resolve_weighted_latency(
    latency_rows: list[dict[str, Any]],
    count_rows: list[dict[str, Any]],
) -> tuple[float, float, str]:
    # Prefer weighted means of period-level percentiles by request volume.
    count_by_ts: dict[str, float] = {}
    for row in count_rows:
        ts = row.get("Timestamp")
        if ts is None:
            continue
        count_by_ts[str(ts)] = parse_float(row.get("Sum"), 0.0)

    p95_num = 0.0
    p99_num = 0.0
    weight_total = 0.0
    for row in latency_rows:
        ts = row.get("Timestamp")
        if ts is None:
            continue
        ext = row.get("ExtendedStatistics", {})
        p95 = parse_float(ext.get("p95"), -1.0)
        p99 = parse_float(ext.get("p99"), -1.0)
        if p95 < 0.0 or p99 < 0.0:
            continue
        w = count_by_ts.get(str(ts), 0.0)
        if w <= 0.0:
            continue
        p95_num += p95 * w
        p99_num += p99 * w
        weight_total += w

    if weight_total > 0.0:
        return (p95_num / weight_total, p99_num / weight_total, "weighted_by_count")

    # Fallback is conservative max across observed period-level percentiles.
    p95_vals: list[float] = []
    p99_vals: list[float] = []
    for row in latency_rows:
        ext = row.get("ExtendedStatistics", {})
        p95 = parse_float(ext.get("p95"), -1.0)
        p99 = parse_float(ext.get("p99"), -1.0)
        if p95 >= 0.0:
            p95_vals.append(p95)
        if p99 >= 0.0:
            p99_vals.append(p99)
    if not p95_vals or not p99_vals:
        return (-1.0, -1.0, "unavailable")
    return (max(p95_vals), max(p99_vals), "max_percentile_fallback")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build fresh PR3-S1 steady evidence.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--api-id", default="ehwznd2uw7")
    ap.add_argument("--api-stage", default="v1")
    ap.add_argument("--athena-database", default="fraud_platform_dev_full_m15")
    ap.add_argument("--athena-table", default="m15b_s3_event_stream_with_fraud_6b")
    ap.add_argument(
        "--athena-output-location",
        default="s3://fraud-platform-dev-full-evidence/evidence/dev_full/road_to_prod/athena_results/",
    )
    ap.add_argument("--sample-window-start-utc", default="")
    ap.add_argument("--sample-window-end-utc", default="")
    ap.add_argument("--perf-window-start-utc", default="")
    ap.add_argument("--perf-window-end-utc", default="")
    ap.add_argument("--throughput-mode", default="cloudwatch_count_sum_per_second")
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    t0 = time.perf_counter()
    ts = now_utc()

    root = Path(args.run_control_root)
    pr3_root = root / args.pr3_execution_id
    if not pr3_root.exists():
        raise RuntimeError(f"PR3 execution root missing: {pr3_root}")

    charter = load_json(pr3_root / "g3a_run_charter.active.json")
    mission = charter.get("mission_binding", {})
    charter_window_start_utc = str(mission.get("window_start_ts_utc", "")).strip()
    charter_window_end_utc = str(mission.get("window_end_ts_utc", "")).strip()
    if not charter_window_start_utc or not charter_window_end_utc:
        raise RuntimeError("Mission window missing in g3a_run_charter.active.json")

    sample_window_start_utc = str(args.sample_window_start_utc).strip() or charter_window_start_utc
    sample_window_end_utc = str(args.sample_window_end_utc).strip() or charter_window_end_utc
    perf_window_start_utc = str(args.perf_window_start_utc).strip() or charter_window_start_utc
    perf_window_end_utc = str(args.perf_window_end_utc).strip() or charter_window_end_utc

    sample_window_start = parse_time_utc(sample_window_start_utc)
    sample_window_end = parse_time_utc(sample_window_end_utc)
    perf_window_start = parse_time_utc(perf_window_start_utc)
    perf_window_end = parse_time_utc(perf_window_end_utc)

    sample_window_seconds = max(1.0, (sample_window_end - sample_window_start).total_seconds())
    perf_window_seconds = max(1.0, (perf_window_end - perf_window_start).total_seconds())

    athena = boto3.client("athena", region_name=args.region)
    cw = boto3.client("cloudwatch", region_name=args.region)

    blockers: list[str] = []
    source_notes: list[str] = []

    query_id = ""
    query_state = "UNKNOWN"
    sample_size_events = 0
    query_reason = ""
    try:
        query_id = submit_athena_count_query(
            athena=athena,
            database=args.athena_database,
            table=args.athena_table,
            window_start_utc=sample_window_start_utc,
            window_end_utc=sample_window_end_utc,
            output_location=args.athena_output_location,
        )
        status_payload = wait_athena_query(athena, query_id)
        status = status_payload.get("QueryExecution", {}).get("Status", {})
        query_state = str(status.get("State", "UNKNOWN")).upper()
        query_reason = str(status.get("StateChangeReason", "")).strip()
        if query_state != "SUCCEEDED":
            blockers.append("PR3.FRESH.B01_ATHENA_QUERY_FAILED")
        else:
            sample_size_events = read_athena_count_result(athena, query_id)
            source_notes.append(f"athena_count_query_id={query_id}")
    except (BotoCoreError, ClientError, RuntimeError) as exc:
        blockers.append("PR3.FRESH.B01_ATHENA_QUERY_FAILED")
        query_reason = f"{type(exc).__name__}:{exc}"

    dims = [{"Name": "ApiId", "Value": args.api_id}, {"Name": "Stage", "Value": args.api_stage}]
    latency_rows: list[dict[str, Any]] = []
    count_rows: list[dict[str, Any]] = []
    err4_rows: list[dict[str, Any]] = []
    err5_rows: list[dict[str, Any]] = []
    try:
        latency_rows = get_cloudwatch_metric(
            cw=cw,
            metric_name="Latency",
            dimensions=dims,
            start_time=perf_window_start,
            end_time=perf_window_end,
            period_seconds=600,
            extended_statistics=["p95", "p99"],
        )
        count_rows = get_cloudwatch_metric(
            cw=cw,
            metric_name="Count",
            dimensions=dims,
            start_time=perf_window_start,
            end_time=perf_window_end,
            period_seconds=600,
            statistics=["Sum"],
        )
        err4_rows = get_cloudwatch_metric(
            cw=cw,
            metric_name="4xx",
            dimensions=dims,
            start_time=perf_window_start,
            end_time=perf_window_end,
            period_seconds=600,
            statistics=["Sum"],
        )
        err5_rows = get_cloudwatch_metric(
            cw=cw,
            metric_name="5xx",
            dimensions=dims,
            start_time=perf_window_start,
            end_time=perf_window_end,
            period_seconds=600,
            statistics=["Sum"],
        )
    except (BotoCoreError, ClientError) as exc:
        blockers.append("PR3.FRESH.B02_CLOUDWATCH_METRICS_UNREADABLE")
        source_notes.append(f"cloudwatch_error={type(exc).__name__}:{exc}")

    latency_p95_ms, latency_p99_ms, latency_method = resolve_weighted_latency(latency_rows, count_rows)
    if latency_p95_ms < 0.0 or latency_p99_ms < 0.0:
        blockers.append("PR3.FRESH.B03_LATENCY_PERCENTILES_MISSING")

    total_count = sum_stat(count_rows)
    err4_total = sum_stat(err4_rows)
    err5_total = sum_stat(err5_rows)
    error_rate_pct = ((err4_total + err5_total) / total_count * 100.0) if total_count > 0.0 else 100.0
    if total_count <= 0.0:
        blockers.append("PR3.FRESH.B04_REQUEST_COUNT_ZERO")

    mode = str(args.throughput_mode or "").strip().lower()
    if mode == "athena_sample_window_avg":
        observed_steady_eps = (float(sample_size_events) / sample_window_seconds) if sample_size_events > 0 else 0.0
        throughput_derivation = "athena_sample_window_avg"
    else:
        observed_steady_eps = (float(total_count) / perf_window_seconds) if total_count > 0.0 else 0.0
        throughput_derivation = "cloudwatch_count_sum_per_second"

    evidence_payload = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "evidence_mode": "FRESH_AWS_TELEMETRY_AND_ATHENA_RECOMPUTE",
        "measurement_surface": "IG_ADMITTED_EVENTS_PER_SEC",
        "window": {
            "start_utc": perf_window_start_utc,
            "end_utc": perf_window_end_utc,
            "duration_seconds": perf_window_seconds,
        },
        "sample_window": {
            "start_utc": sample_window_start_utc,
            "end_utc": sample_window_end_utc,
            "duration_seconds": sample_window_seconds,
        },
        "charter_window": {
            "start_utc": charter_window_start_utc,
            "end_utc": charter_window_end_utc,
        },
        "sample_size_events": int(sample_size_events),
        "observed_events_per_second": observed_steady_eps,
        "throughput_derivation": throughput_derivation,
        "error_rate_pct_observed": error_rate_pct,
        "decision_latency_ms_p95": latency_p95_ms if latency_p95_ms >= 0.0 else None,
        "decision_latency_ms_p99": latency_p99_ms if latency_p99_ms >= 0.0 else None,
        "latency_derivation_method": latency_method,
        "cloudwatch_aggregation": {
            "period_seconds": 600,
            "api_id": args.api_id,
            "stage": args.api_stage,
            "count_sum": total_count,
            "4xx_sum": err4_total,
            "5xx_sum": err5_total,
            "latency_datapoints": len(latency_rows),
        },
        "athena_recompute": {
            "database": args.athena_database,
            "table": args.athena_table,
            "query_execution_id": query_id,
            "query_state": query_state,
            "query_state_reason": query_reason,
            "output_location": args.athena_output_location,
            "window_start_utc": sample_window_start_utc,
            "window_end_utc": sample_window_end_utc,
        },
        "overall_pass": len(blockers) == 0,
        "source_notes": source_notes,
    }

    summary_payload = {
        "phase": "PR3",
        "state": "S1",
        "generated_at_utc": ts,
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "verdict": "FRESH_EVIDENCE_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "blocker_count": len(blockers),
        "blockers": blockers,
        "evidence_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/g3a_steady_evidence_fresh.json",
        "elapsed_minutes": round((time.perf_counter() - t0) / 60.0, 3),
    }

    evidence_path = pr3_root / "g3a_steady_evidence_fresh.json"
    summary_path = pr3_root / "g3a_steady_evidence_fresh_summary.json"
    dump_json(evidence_path, evidence_payload)
    dump_json(summary_path, summary_payload)

    print(
        json.dumps(
            {
                "execution_id": args.pr3_execution_id,
                "evidence_ref": str(evidence_path).replace("\\", "/"),
                "summary_ref": str(summary_path).replace("\\", "/"),
                "sample_size_events": sample_size_events,
                "observed_events_per_second": observed_steady_eps,
                "decision_latency_ms_p95": evidence_payload.get("decision_latency_ms_p95"),
                "decision_latency_ms_p99": evidence_payload.get("decision_latency_ms_p99"),
                "error_rate_pct_observed": error_rate_pct,
                "blocker_count": len(blockers),
                "blockers": blockers,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
