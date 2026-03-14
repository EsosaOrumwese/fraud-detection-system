#!/usr/bin/env python3
"""Build PR3-S3 recovery evidence from prestress and recovery artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
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


def to_iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    bounded = max(0.0, min(1.0, float(q)))
    idx = max(0, min(len(ordered) - 1, int((len(ordered) * bounded) + 0.999999) - 1))
    return float(ordered[idx])


def summarize_series(values: list[float]) -> dict[str, float | None]:
    return {
        "count": float(len(values)),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
        "min": min(values) if values else None,
    }


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def align_up_to_period(dt: datetime, period_seconds: int) -> datetime:
    ts = dt.astimezone(timezone.utc).timestamp()
    aligned = ((int(ts) + period_seconds - 1) // period_seconds) * period_seconds
    return datetime.fromtimestamp(aligned, tz=timezone.utc)


def align_down_to_period(dt: datetime, period_seconds: int) -> datetime:
    ts = dt.astimezone(timezone.utc).timestamp()
    aligned = (int(ts) // period_seconds) * period_seconds
    return datetime.fromtimestamp(aligned, tz=timezone.utc)


def snap_value(snapshot: dict[str, Any], component: str, field: str) -> float | None:
    return to_float((((snapshot.get("components") or {}).get(component) or {}).get("summary") or {}).get(field))


def snapshot_platform_run_id(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("platform_run_id", "")).strip()


def snapshot_generated_at(snapshot: dict[str, Any]) -> datetime | None:
    return parse_utc(snapshot.get("generated_at_utc"))


def payload_missing(snapshot: dict[str, Any], component: str, payload_kind: str) -> bool:
    payload = ((((snapshot.get("components") or {}).get(component) or {}).get(f"{payload_kind}_payload")) or {})
    return bool(payload.get("__missing__")) or bool(payload.get("__unreadable__"))


def counter_delta(pre: dict[str, Any], post: dict[str, Any], component: str, field: str) -> float | None:
    start = snap_value(pre, component, field)
    end = snap_value(post, component, field)
    if end is None:
        return None
    if start is None and payload_missing(pre, component, "metrics"):
        start = 0.0
    if start is None:
        return None
    return float(end - start)


def select_counter_window_bounds(
    snapshots: list[dict[str, Any]],
    *,
    measurement_start_utc: datetime | None,
    measurement_end_utc: datetime | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ordered = sorted(
        [row for row in snapshots if snapshot_generated_at(row) is not None],
        key=lambda row: snapshot_generated_at(row) or datetime.min.replace(tzinfo=timezone.utc),
    )
    if not ordered:
        raise RuntimeError("PR3.S3.B19_RECOVERY_COMPONENT_SNAPSHOT_TIMESTAMPS_UNREADABLE")

    baseline = ordered[0]
    baseline_mode = "earliest_available"
    if measurement_start_utc is not None:
        at_or_before = [row for row in ordered if (snapshot_generated_at(row) or measurement_start_utc) <= measurement_start_utc]
        if at_or_before:
            baseline = at_or_before[-1]
            baseline_mode = "latest_at_or_before_measurement_start"
        else:
            at_or_after = [row for row in ordered if (snapshot_generated_at(row) or measurement_start_utc) >= measurement_start_utc]
            if at_or_after:
                baseline = at_or_after[0]
                baseline_mode = "earliest_at_or_after_measurement_start"

    window_end = ordered[-1]
    window_end_mode = "latest_available"
    if measurement_end_utc is not None:
        at_or_before = [row for row in ordered if (snapshot_generated_at(row) or measurement_end_utc) <= measurement_end_utc]
        if at_or_before:
            window_end = at_or_before[-1]
            window_end_mode = "latest_at_or_before_measurement_end"
        else:
            at_or_after = [row for row in ordered if (snapshot_generated_at(row) or measurement_end_utc) >= measurement_end_utc]
            if at_or_after:
                window_end = at_or_after[0]
                window_end_mode = "earliest_at_or_after_measurement_end"

    baseline_ts = snapshot_generated_at(baseline)
    window_end_ts = snapshot_generated_at(window_end)
    meta = {
        "baseline_snapshot_label": baseline.get("snapshot_label"),
        "baseline_snapshot_generated_at_utc": baseline.get("generated_at_utc"),
        "baseline_selection_mode": baseline_mode,
        "window_end_snapshot_label": window_end.get("snapshot_label"),
        "window_end_snapshot_generated_at_utc": window_end.get("generated_at_utc"),
        "window_end_selection_mode": window_end_mode,
        "measurement_start_utc": to_iso_utc(measurement_start_utc),
        "measurement_end_utc": to_iso_utc(measurement_end_utc),
        "baseline_gap_seconds_from_measurement_start": (
            abs((measurement_start_utc - baseline_ts).total_seconds()) if measurement_start_utc and baseline_ts else None
        ),
        "window_end_gap_seconds_from_measurement_end": (
            abs((measurement_end_utc - window_end_ts).total_seconds()) if measurement_end_utc and window_end_ts else None
        ),
    }
    return baseline, window_end, meta


def pick_counter_baseline(
    snapshots: list[dict[str, Any]],
    *,
    measurement_start_utc: datetime | None,
) -> dict[str, Any]:
    if not snapshots:
        raise RuntimeError("PR3.S3.B19_RECOVERY_COMPONENT_SNAPSHOTS_MISSING")
    ordered = sorted(
        [row for row in snapshots if snapshot_generated_at(row) is not None],
        key=lambda row: snapshot_generated_at(row) or datetime.min.replace(tzinfo=timezone.utc),
    )
    if not ordered:
        return snapshots[0]
    if measurement_start_utc is None:
        return ordered[0]
    at_or_before = [row for row in ordered if (snapshot_generated_at(row) or measurement_start_utc) <= measurement_start_utc]
    if at_or_before:
        return at_or_before[-1]
    at_or_after = [row for row in ordered if (snapshot_generated_at(row) or measurement_start_utc) >= measurement_start_utc]
    return at_or_after[0] if at_or_after else ordered[0]


def build_alb_recovery_bins(
    *,
    region: str,
    load_balancer_dimension: str,
    target_group_dimension: str,
    start_time: datetime,
    end_time: datetime,
    period_seconds: int = 60,
) -> list[dict[str, Any]]:
    cw = boto3.client("cloudwatch", region_name=region)
    effective_start = align_up_to_period(start_time, period_seconds)
    effective_end = align_down_to_period(end_time, period_seconds)
    if (effective_end - effective_start).total_seconds() < float(period_seconds):
        return []

    lb_dims = [{"Name": "LoadBalancer", "Value": load_balancer_dimension}]
    tg_dims = lb_dims + [{"Name": "TargetGroup", "Value": target_group_dimension}]

    def sum_points(metric_name: str, dimensions: list[dict[str, str]]) -> dict[str, float]:
        payload = cw.get_metric_statistics(
            Namespace="AWS/ApplicationELB",
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=effective_start,
            EndTime=effective_end,
            Period=period_seconds,
            Statistics=["Sum"],
        )
        rows: dict[str, float] = {}
        for point in payload.get("Datapoints", []):
            stamp = to_iso_utc(point.get("Timestamp"))
            if stamp:
                rows[stamp] = float(point.get("Sum", 0.0) or 0.0)
        return rows

    def latency_points(stat: str) -> dict[str, float]:
        payload = cw.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": "lat",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApplicationELB",
                            "MetricName": "TargetResponseTime",
                            "Dimensions": tg_dims,
                        },
                        "Period": period_seconds,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                }
            ],
            StartTime=effective_start,
            EndTime=effective_end,
        )
        rows: dict[str, float] = {}
        series = (payload.get("MetricDataResults") or [{}])[0]
        for timestamp, value in zip(series.get("Timestamps", []), series.get("Values", []), strict=False):
            stamp = to_iso_utc(timestamp)
            if stamp:
                rows[stamp] = float(value)
        return rows

    request_count = sum_points("RequestCount", lb_dims)
    target_4xx = sum_points("HTTPCode_Target_4XX_Count", tg_dims)
    target_5xx = sum_points("HTTPCode_Target_5XX_Count", tg_dims)
    elb_4xx = sum_points("HTTPCode_ELB_4XX_Count", lb_dims)
    elb_5xx = sum_points("HTTPCode_ELB_5XX_Count", lb_dims)
    p95 = latency_points("p95.0")
    p99 = latency_points("p99.0")

    bins: list[dict[str, Any]] = []
    cursor = effective_start
    while cursor < effective_end:
        stamp = to_iso_utc(cursor)
        total = float(request_count.get(stamp or "", 0.0))
        total_4xx = float(target_4xx.get(stamp or "", 0.0) + elb_4xx.get(stamp or "", 0.0))
        total_5xx = float(target_5xx.get(stamp or "", 0.0) + elb_5xx.get(stamp or "", 0.0))
        admitted = max(0.0, total - total_4xx - total_5xx)
        p95_seconds = p95.get(stamp or "")
        p99_seconds = p99.get(stamp or "")
        bins.append(
            {
                "timestamp_utc": stamp,
                "window_end_utc": to_iso_utc(cursor + timedelta(seconds=period_seconds)),
                "request_count": total,
                "admitted_count": admitted,
                "observed_request_eps": (total / float(period_seconds)) if total > 0.0 else 0.0,
                "observed_admitted_eps": (admitted / float(period_seconds)) if total > 0.0 else 0.0,
                "4xx_total": total_4xx,
                "5xx_total": total_5xx,
                "error_rate_ratio": ((total_4xx + total_5xx) / total) if total > 0.0 else 0.0,
                "4xx_rate_ratio": (total_4xx / total) if total > 0.0 else 0.0,
                "5xx_rate_ratio": (total_5xx / total) if total > 0.0 else 0.0,
                "latency_p95_ms": (p95_seconds * 1000.0) if p95_seconds is not None else None,
                "latency_p99_ms": (p99_seconds * 1000.0) if p99_seconds is not None else None,
            }
        )
        cursor += timedelta(seconds=period_seconds)
    return bins


def sustained_green_start(rows: list[dict[str, Any]], *, pass_key: str, stable_time_key: str) -> str | None:
    for idx, row in enumerate(rows):
        if bool(row.get(pass_key)) and all(bool(next_row.get(pass_key)) for next_row in rows[idx:]):
            return str(row.get(stable_time_key) or "").strip() or None
    return None


def summarize_ingress_bins(
    *,
    bins: list[dict[str, Any]],
    measurement_start_utc: datetime,
    measurement_end_utc: datetime,
    expected_eps: float,
    window_label: str,
    metric_surface_mode: str,
    ingress_surface: dict[str, Any],
    generated_by: str,
    version: str,
    phase: str,
    state: str,
    execution_id: str,
    continuous_prefix: str,
) -> dict[str, Any]:
    request_count_total = float(sum(float(row.get("request_count", 0.0) or 0.0) for row in bins))
    admitted_count = float(sum(float(row.get("admitted_count", 0.0) or 0.0) for row in bins))
    four_xx_total = float(sum(float(row.get("4xx_total", 0.0) or 0.0) for row in bins))
    five_xx_total = float(sum(float(row.get("5xx_total", 0.0) or 0.0) for row in bins))
    covered_seconds = max(0.0, (measurement_end_utc - measurement_start_utc).total_seconds())
    observed_request_eps = request_count_total / covered_seconds if covered_seconds > 0.0 else 0.0
    observed_admitted_eps = admitted_count / covered_seconds if covered_seconds > 0.0 else 0.0
    error_rate_ratio = ((four_xx_total + five_xx_total) / request_count_total) if request_count_total > 0.0 else 0.0
    error_4xx_ratio = (four_xx_total / request_count_total) if request_count_total > 0.0 else 0.0
    error_5xx_ratio = (five_xx_total / request_count_total) if request_count_total > 0.0 else 0.0
    latency_weight = sum(float(row.get("request_count", 0.0) or 0.0) for row in bins if float(row.get("request_count", 0.0) or 0.0) > 0.0)
    latency_p95_ms = (
        sum((float(row.get("latency_p95_ms", 0.0) or 0.0) * float(row.get("request_count", 0.0) or 0.0)) for row in bins if row.get("latency_p95_ms") is not None)
        / latency_weight
        if latency_weight > 0.0
        else None
    )
    latency_p99_ms = (
        sum((float(row.get("latency_p99_ms", 0.0) or 0.0) * float(row.get("request_count", 0.0) or 0.0)) for row in bins if row.get("latency_p99_ms") is not None)
        / latency_weight
        if latency_weight > 0.0
        else None
    )
    pass_window = observed_admitted_eps >= float(expected_eps)
    return {
        "phase": phase,
        "state": state,
        "generated_at_utc": now_utc(),
        "generated_by": generated_by,
        "version": version,
        "execution_id": execution_id,
        "dispatch_mode": "CANONICAL_REMOTE_WSP_REPLAY_CONTINUOUS_DERIVED",
        "verdict": "REMOTE_WSP_WINDOW_READY" if pass_window else "HOLD_REMEDIATE",
        "open_blockers": 0 if pass_window else 1,
        "blocker_ids": ([] if pass_window else [f"DERIVED_{window_label.upper()}_THROUGHPUT_SHORTFALL"]),
        "performance_window": {
            "measurement_start_utc": to_iso_utc(measurement_start_utc),
            "measurement_target_end_utc": to_iso_utc(measurement_end_utc),
            "metric_effective_start_utc": to_iso_utc(measurement_start_utc),
            "metric_effective_end_utc": to_iso_utc(measurement_end_utc),
            "covered_metric_seconds": covered_seconds,
            "metric_period_seconds": 60,
            "metric_bin_count": len(bins),
            "metric_surface_mode": metric_surface_mode,
        },
        "campaign": {
            "expected_window_eps": float(expected_eps),
            "window_label": window_label,
            "derived_from_continuous_prefix": continuous_prefix,
        },
        "observed": {
            "request_count_total": int(request_count_total),
            "admitted_request_count": int(admitted_count),
            "observed_request_eps": observed_request_eps,
            "observed_admitted_eps": observed_admitted_eps,
            "error_rate_ratio": error_rate_ratio,
            "4xx_rate_ratio": error_4xx_ratio,
            "5xx_rate_ratio": error_5xx_ratio,
            "4xx_total": int(four_xx_total),
            "5xx_total": int(five_xx_total),
            "latency_p95_ms": latency_p95_ms,
            "latency_p99_ms": latency_p99_ms,
            "latency_derivation_method": "count_weighted_from_continuous_minute_bins",
            "metric_surface_mode": metric_surface_mode,
        },
        "notes": {
            "derived_from_continuous_prefix": continuous_prefix,
            "ingress_metric_surface": ingress_surface,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build PR3-S3 recovery rollup.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S3")
    ap.add_argument("--prestress-artifact-prefix", default="g3a_s3_prestress")
    ap.add_argument("--recovery-artifact-prefix", default="g3a_s3_recovery")
    ap.add_argument("--continuous-artifact-prefix", default="")
    ap.add_argument("--burst-duration-seconds", type=int, default=300)
    ap.add_argument("--recovery-duration-seconds", type=int, default=180)
    ap.add_argument("--region", default="eu-west-2")
    ap.add_argument("--expected-burst-eps", type=float, default=6000.0)
    ap.add_argument("--expected-steady-eps", type=float, default=3000.0)
    ap.add_argument("--recovery-bound-seconds", type=float, default=180.0)
    ap.add_argument("--max-error-rate-ratio", type=float, default=0.002)
    ap.add_argument("--max-4xx-ratio", type=float, default=0.002)
    ap.add_argument("--max-5xx-ratio", type=float, default=0.0)
    ap.add_argument("--max-latency-p95-ms", type=float, default=350.0)
    ap.add_argument("--max-latency-p99-ms", type=float, default=700.0)
    ap.add_argument("--max-lag-p99-seconds", type=float, default=5.0)
    ap.add_argument("--max-checkpoint-p99-seconds", type=float, default=30.0)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    continuous_prefix = str(args.continuous_artifact_prefix).strip()
    if continuous_prefix:
        continuous_summary = load_json(root / f"{continuous_prefix}_wsp_runtime_summary.json")
        continuous_manifest = load_json(root / f"{continuous_prefix}_wsp_runtime_manifest.json")
        continuous_bins_payload = load_json(root / f"{continuous_prefix}_ingress_bins.json")
        continuous_bins = list(continuous_bins_payload.get("bins", []) or [])
        campaign = dict(continuous_manifest.get("campaign", {}) or {})
        ingress_surface = dict((((continuous_summary.get("notes") or {}).get("ingress_metric_surface")) or {}))
        campaign_start_utc = parse_utc(campaign.get("campaign_start_utc")) or parse_utc(
            continuous_summary.get("performance_window", {}).get("measurement_start_utc")
        )
        if campaign_start_utc is None:
            raise RuntimeError("PR3.S3.B19_CONTINUOUS_CAMPAIGN_START_UNREADABLE")
        prestress_start_utc = campaign_start_utc
        prestress_end_utc = prestress_start_utc + timedelta(seconds=int(args.burst_duration_seconds))
        recovery_start_utc = prestress_end_utc
        recovery_end_utc = recovery_start_utc + timedelta(seconds=int(args.recovery_duration_seconds))
        prestress_bins = [
            row
            for row in continuous_bins
            if (parse_utc(row.get("timestamp_utc")) or prestress_start_utc) >= prestress_start_utc
            and (parse_utc(row.get("timestamp_utc")) or prestress_end_utc) < prestress_end_utc
        ]
        recovery_bins = [
            row
            for row in continuous_bins
            if (parse_utc(row.get("timestamp_utc")) or recovery_start_utc) >= recovery_start_utc
            and (parse_utc(row.get("timestamp_utc")) or recovery_end_utc) < recovery_end_utc
        ]
        prestress_summary = summarize_ingress_bins(
            bins=prestress_bins,
            measurement_start_utc=prestress_start_utc,
            measurement_end_utc=prestress_end_utc,
            expected_eps=float(args.expected_burst_eps),
            window_label="burst_prestress",
            metric_surface_mode=str((continuous_summary.get("performance_window") or {}).get("metric_surface_mode") or ""),
            ingress_surface=ingress_surface,
            generated_by=args.generated_by,
            version=args.version,
            phase="PR3",
            state=args.state_id,
            execution_id=args.pr3_execution_id,
            continuous_prefix=continuous_prefix,
        )
        recovery_summary = summarize_ingress_bins(
            bins=recovery_bins,
            measurement_start_utc=recovery_start_utc,
            measurement_end_utc=recovery_end_utc,
            expected_eps=float(args.expected_steady_eps),
            window_label="recovery",
            metric_surface_mode=str((continuous_summary.get("performance_window") or {}).get("metric_surface_mode") or ""),
            ingress_surface=ingress_surface,
            generated_by=args.generated_by,
            version=args.version,
            phase="PR3",
            state=args.state_id,
            execution_id=args.pr3_execution_id,
            continuous_prefix=continuous_prefix,
        )
        prestress_manifest = dict(continuous_manifest)
        recovery_manifest = dict(continuous_manifest)
        dump_json(root / f"{args.prestress_artifact_prefix}_wsp_runtime_summary.json", prestress_summary)
        dump_json(root / f"{args.recovery_artifact_prefix}_wsp_runtime_summary.json", recovery_summary)
        dump_json(root / f"{args.prestress_artifact_prefix}_wsp_runtime_manifest.json", prestress_manifest)
        dump_json(root / f"{args.recovery_artifact_prefix}_wsp_runtime_manifest.json", recovery_manifest)
    else:
        prestress_summary = load_json(root / f"{args.prestress_artifact_prefix}_wsp_runtime_summary.json")
        recovery_summary = load_json(root / f"{args.recovery_artifact_prefix}_wsp_runtime_summary.json")
        recovery_manifest = load_json(root / f"{args.recovery_artifact_prefix}_wsp_runtime_manifest.json")
        prestress_manifest = load_json(root / f"{args.prestress_artifact_prefix}_wsp_runtime_manifest.json")
    snapshots = sorted(
        [load_json(path) for path in root.glob(f"g3a_{str(args.state_id).strip().lower()}_component_snapshot_*.json")],
        key=lambda row: str(row.get("generated_at_utc", "")),
    )

    blockers: list[str] = []
    if not snapshots:
        blockers.append("PR3.B19_RECOVERY_EVIDENCE_INCOMPLETE:component_snapshots_missing")

    prestress_admitted_eps = float(((prestress_summary.get("observed") or {}).get("observed_admitted_eps")) or 0.0)
    if int(prestress_summary.get("open_blockers", 1) or 0) > 0 or prestress_admitted_eps < float(args.expected_burst_eps):
        blockers.append(
            f"PR3.B17_RECOVERY_PROFILE_NOT_EXECUTED:prestress_observed={prestress_admitted_eps:.3f}:target={float(args.expected_burst_eps):.3f}"
        )

    recovery_observed = dict(recovery_summary.get("observed", {}) or {})
    recovery_window = dict(recovery_summary.get("performance_window", {}) or {})
    if continuous_prefix:
        recovery_start_utc = parse_utc(recovery_window.get("measurement_start_utc"))
        recovery_end_utc = parse_utc(recovery_window.get("measurement_target_end_utc") or recovery_window.get("metric_effective_end_utc"))
        ingress_surface = dict((((recovery_summary.get("notes") or {}).get("ingress_metric_surface")) or {}))
    else:
        recovery_start_utc = parse_utc(recovery_window.get("measurement_start_utc"))
        recovery_end_utc = parse_utc(recovery_window.get("measurement_target_end_utc") or recovery_window.get("metric_effective_end_utc"))
        ingress_surface = dict(((recovery_summary.get("notes") or {}).get("ingress_metric_surface")) or {})
    if recovery_start_utc is None or recovery_end_utc is None:
        blockers.append("PR3.B19_RECOVERY_EVIDENCE_INCOMPLETE:recovery_window_missing")
    if str(ingress_surface.get("mode", "")).upper() != "ALB":
        blockers.append(f"PR3.B19_RECOVERY_EVIDENCE_INCOMPLETE:unsupported_ingress_surface={ingress_surface.get('mode')}")

    recovery_platform_run_id = str((((recovery_manifest.get("identity") or {}).get("platform_run_id")) or "")).strip()
    recovery_snapshots = [row for row in snapshots if snapshot_platform_run_id(row) == recovery_platform_run_id]
    if not recovery_snapshots:
        blockers.append(f"PR3.B19_RECOVERY_EVIDENCE_INCOMPLETE:recovery_snapshots_missing:platform_run_id={recovery_platform_run_id}")

    ingress_bins: list[dict[str, Any]] = []
    if continuous_prefix:
        ingress_bins = recovery_bins
    elif recovery_start_utc and recovery_end_utc and str(ingress_surface.get("mode", "")).upper() == "ALB":
        ingress_bins = build_alb_recovery_bins(
            region=args.region,
            load_balancer_dimension=str(ingress_surface.get("load_balancer_dimension", "")).strip(),
            target_group_dimension=str(ingress_surface.get("target_group_dimension", "")).strip(),
            start_time=recovery_start_utc,
            end_time=recovery_end_utc,
        )
    if not ingress_bins:
        blockers.append("PR3.B19_RECOVERY_EVIDENCE_INCOMPLETE:ingress_bins_missing")

    for row in ingress_bins:
        row["pass"] = (
            float(row.get("observed_admitted_eps", 0.0) or 0.0) >= float(args.expected_steady_eps)
            and float(row.get("error_rate_ratio", 1.0) or 0.0) <= float(args.max_error_rate_ratio)
            and float(row.get("4xx_rate_ratio", 1.0) or 0.0) <= float(args.max_4xx_ratio)
            and float(row.get("5xx_rate_ratio", 1.0) or 0.0) <= float(args.max_5xx_ratio)
            and to_float(row.get("latency_p95_ms")) is not None
            and float(row.get("latency_p95_ms", 0.0) or 0.0) <= float(args.max_latency_p95_ms)
            and to_float(row.get("latency_p99_ms")) is not None
            and float(row.get("latency_p99_ms", 0.0) or 0.0) <= float(args.max_latency_p99_ms)
        )

    ingress_green_utc = sustained_green_start(ingress_bins, pass_key="pass", stable_time_key="window_end_utc")

    counter_baseline = pick_counter_baseline(recovery_snapshots, measurement_start_utc=recovery_start_utc) if recovery_snapshots else {}
    counter_window_start, counter_window_end, counter_window_meta = (
        select_counter_window_bounds(recovery_snapshots, measurement_start_utc=recovery_start_utc, measurement_end_utc=recovery_end_utc)
        if recovery_snapshots
        else ({}, {}, {})
    )

    component_rows: list[dict[str, Any]] = []
    lag_values: list[float] = []
    checkpoint_values: list[float] = []
    ordered_recovery = sorted(
        [row for row in recovery_snapshots if snapshot_generated_at(row) is not None],
        key=lambda row: snapshot_generated_at(row) or datetime.min.replace(tzinfo=timezone.utc),
    )
    for snap in ordered_recovery:
        generated_at = snapshot_generated_at(snap)
        if generated_at is None:
            continue
        ofp_lag = snap_value(snap, "ofp", "lag_seconds")
        checkpoint_numeric = [
            float(v)
            for v in [
                snap_value(snap, "ieg", "checkpoint_age_seconds"),
                snap_value(snap, "ofp", "checkpoint_age_seconds"),
                snap_value(snap, "dla", "checkpoint_age_seconds"),
            ]
            if v is not None
        ]
        checkpoint_max = max(checkpoint_numeric) if checkpoint_numeric else None
        dl_mode = str((((snap.get("components") or {}).get("dl") or {}).get("summary") or {}).get("decision_mode") or "").strip()
        bad_required_signals = list((((snap.get("components") or {}).get("dl") or {}).get("summary") or {}).get("bad_required_signals") or [])
        counter_checks: dict[str, float | None] = {}
        for metric_id, component, field in [
            ("df_fail_closed_delta", "df", "fail_closed_total"),
            ("df_quarantine_delta", "df", "publish_quarantine_total"),
            ("al_quarantine_delta", "al", "publish_quarantine_total"),
            ("al_ambiguous_delta", "al", "publish_ambiguous_total"),
            ("dla_append_failure_delta", "dla", "append_failure_total"),
            ("dla_replay_divergence_delta", "dla", "replay_divergence_total"),
            ("archive_write_error_delta", "archive_writer", "write_error_total"),
            ("archive_payload_mismatch_delta", "archive_writer", "payload_mismatch_total"),
        ]:
            counter_checks[metric_id] = counter_delta(counter_baseline, snap, component, field)
        row = {
            "snapshot_label": snap.get("snapshot_label"),
            "generated_at_utc": snap.get("generated_at_utc"),
            "ofp_lag_seconds": ofp_lag,
            "checkpoint_max_seconds": checkpoint_max,
            "dl_decision_mode": dl_mode,
            "dl_bad_required_signals": bad_required_signals,
            **counter_checks,
        }
        row["pass"] = (
            ofp_lag is not None
            and float(ofp_lag) <= float(args.max_lag_p99_seconds)
            and checkpoint_max is not None
            and float(checkpoint_max) <= float(args.max_checkpoint_p99_seconds)
            and dl_mode == "NORMAL"
            and len(bad_required_signals) == 0
            and all(value is not None and float(value) <= 0.0 for value in counter_checks.values())
        )
        component_rows.append(row)
        if ofp_lag is not None:
            lag_values.append(float(ofp_lag))
        if checkpoint_max is not None:
            checkpoint_values.append(float(checkpoint_max))

    component_green_utc = sustained_green_start(component_rows, pass_key="pass", stable_time_key="generated_at_utc")

    stable_utc = None
    if ingress_green_utc and component_green_utc:
        stable_utc = max(parse_utc(ingress_green_utc), parse_utc(component_green_utc))
    recovery_elapsed_seconds = (
        (stable_utc - recovery_start_utc).total_seconds() if stable_utc is not None and recovery_start_utc is not None else None
    )

    final_counter_deltas = {
        "df_fail_closed_total_delta": counter_delta(counter_window_start, counter_window_end, "df", "fail_closed_total") if recovery_snapshots else None,
        "df_publish_quarantine_total_delta": counter_delta(counter_window_start, counter_window_end, "df", "publish_quarantine_total") if recovery_snapshots else None,
        "al_publish_quarantine_total_delta": counter_delta(counter_window_start, counter_window_end, "al", "publish_quarantine_total") if recovery_snapshots else None,
        "al_publish_ambiguous_total_delta": counter_delta(counter_window_start, counter_window_end, "al", "publish_ambiguous_total") if recovery_snapshots else None,
        "dla_append_failure_total_delta": counter_delta(counter_window_start, counter_window_end, "dla", "append_failure_total") if recovery_snapshots else None,
        "dla_replay_divergence_total_delta": counter_delta(counter_window_start, counter_window_end, "dla", "replay_divergence_total") if recovery_snapshots else None,
        "archive_write_error_total_delta": counter_delta(counter_window_start, counter_window_end, "archive_writer", "write_error_total") if recovery_snapshots else None,
        "archive_payload_mismatch_total_delta": counter_delta(counter_window_start, counter_window_end, "archive_writer", "payload_mismatch_total") if recovery_snapshots else None,
    }

    final_recovery_pass = (
        float(recovery_observed.get("observed_admitted_eps", 0.0) or 0.0) >= float(args.expected_steady_eps)
        and float(recovery_observed.get("error_rate_ratio", 1.0) or 0.0) <= float(args.max_error_rate_ratio)
        and float(recovery_observed.get("4xx_rate_ratio", 1.0) or 0.0) <= float(args.max_4xx_ratio)
        and float(recovery_observed.get("5xx_rate_ratio", 1.0) or 0.0) <= float(args.max_5xx_ratio)
        and to_float(recovery_observed.get("latency_p95_ms")) is not None
        and float(recovery_observed.get("latency_p95_ms", 0.0) or 0.0) <= float(args.max_latency_p95_ms)
        and to_float(recovery_observed.get("latency_p99_ms")) is not None
        and float(recovery_observed.get("latency_p99_ms", 0.0) or 0.0) <= float(args.max_latency_p99_ms)
    )

    lag_summary = summarize_series(lag_values)
    checkpoint_summary = summarize_series(checkpoint_values)
    if lag_summary["p99"] is None or float(lag_summary["p99"] or 0.0) > float(args.max_lag_p99_seconds):
        blockers.append(f"PR3.B20_STABLE_DEFINITION_UNSATISFIED:lag_p99={lag_summary['p99']}:max={float(args.max_lag_p99_seconds):.3f}")
    if checkpoint_summary["p99"] is None or float(checkpoint_summary["p99"] or 0.0) > float(args.max_checkpoint_p99_seconds):
        blockers.append(
            f"PR3.B20_STABLE_DEFINITION_UNSATISFIED:checkpoint_p99={checkpoint_summary['p99']}:max={float(args.max_checkpoint_p99_seconds):.3f}"
        )
    if not final_recovery_pass:
        blockers.append("PR3.B20_STABLE_DEFINITION_UNSATISFIED:recovery_window_metrics")
    for metric_id, value in final_counter_deltas.items():
        if value is None or float(value) > 0.0:
            blockers.append(f"PR3.B20_STABLE_DEFINITION_UNSATISFIED:{metric_id}={value}")
    if stable_utc is None:
        blockers.append("PR3.B20_STABLE_DEFINITION_UNSATISFIED:stable_utc_unresolved")
    elif recovery_elapsed_seconds is None or float(recovery_elapsed_seconds) > float(args.recovery_bound_seconds):
        blockers.append(
            f"PR3.B18_RECOVERY_BOUND_BREACH:observed={recovery_elapsed_seconds}:max={float(args.recovery_bound_seconds):.3f}"
        )

    scorecard = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "window_label": "recovery",
        "prestress": {
            "platform_run_id": str((((prestress_manifest.get("identity") or {}).get("platform_run_id")) or "")).strip(),
            "scenario_run_id": str((((prestress_manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip(),
            "observed_burst_eps": prestress_admitted_eps,
            "target_burst_eps": float(args.expected_burst_eps),
            "open_blockers": int(prestress_summary.get("open_blockers", 0) or 0),
        },
        "recovery": {
            "platform_run_id": recovery_platform_run_id,
            "scenario_run_id": str((((recovery_manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip(),
            "observed_admitted_eps": float(recovery_observed.get("observed_admitted_eps", 0.0) or 0.0),
            "target_steady_eps": float(args.expected_steady_eps),
            "4xx_total": int(recovery_observed.get("4xx_total", 0) or 0),
            "5xx_total": int(recovery_observed.get("5xx_total", 0) or 0),
            "latency_p95_ms": to_float(recovery_observed.get("latency_p95_ms")),
            "latency_p99_ms": to_float(recovery_observed.get("latency_p99_ms")),
            "error_rate_ratio": float(recovery_observed.get("error_rate_ratio", 0.0) or 0.0),
            "covered_metric_seconds": float(recovery_window.get("covered_metric_seconds", 0.0) or 0.0),
            "metric_bin_count": int(recovery_window.get("metric_bin_count", 0) or 0),
            "stable_utc": to_iso_utc(stable_utc),
            "recovery_seconds": recovery_elapsed_seconds,
            "bound_seconds": float(args.recovery_bound_seconds),
        },
        "stable_definition": {
            "throughput_floor_eps": float(args.expected_steady_eps),
            "error_rate_max_ratio": float(args.max_error_rate_ratio),
            "4xx_rate_max_ratio": float(args.max_4xx_ratio),
            "5xx_rate_max_ratio": float(args.max_5xx_ratio),
            "latency_p95_max_ms": float(args.max_latency_p95_ms),
            "latency_p99_max_ms": float(args.max_latency_p99_ms),
            "lag_p99_max_seconds": float(args.max_lag_p99_seconds),
            "checkpoint_p99_max_seconds": float(args.max_checkpoint_p99_seconds),
        },
        "checks": {
            "prestress_executed": not any(item.startswith("PR3.B17") for item in blockers),
            "recovery_metrics_pass": final_recovery_pass,
            "lag_p99_pass": lag_summary["p99"] is not None and float(lag_summary["p99"] or 0.0) <= float(args.max_lag_p99_seconds),
            "checkpoint_p99_pass": checkpoint_summary["p99"] is not None and float(checkpoint_summary["p99"] or 0.0) <= float(args.max_checkpoint_p99_seconds),
            "counter_deltas_zero": all(value is not None and float(value) <= 0.0 for value in final_counter_deltas.values()),
            "stable_utc_resolved": stable_utc is not None,
            "recovery_bound_met": recovery_elapsed_seconds is not None and float(recovery_elapsed_seconds) <= float(args.recovery_bound_seconds),
        },
    }

    timeline = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "prestress_end_utc": prestress_summary.get("performance_window", {}).get("end_utc")
        or prestress_summary.get("performance_window", {}).get("measurement_target_end_utc"),
        "recovery_start_utc": to_iso_utc(recovery_start_utc),
        "recovery_end_utc": to_iso_utc(recovery_end_utc),
        "ingress_first_sustained_green_utc": ingress_green_utc,
        "component_first_sustained_green_utc": component_green_utc,
        "stable_utc": to_iso_utc(stable_utc),
        "recovery_seconds": recovery_elapsed_seconds,
        "ingress_bins": ingress_bins,
        "component_samples": component_rows,
    }

    bound_report = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "recovery_bound_seconds": float(args.recovery_bound_seconds),
        "observed_recovery_seconds": recovery_elapsed_seconds,
        "recovery_bound_met": recovery_elapsed_seconds is not None and float(recovery_elapsed_seconds) <= float(args.recovery_bound_seconds),
        "lag_summary": lag_summary,
        "checkpoint_summary": checkpoint_summary,
        "final_counter_deltas": final_counter_deltas,
        "counter_window": counter_window_meta,
        "open_blockers": sorted(set(blockers)),
    }

    receipt = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "prestress_platform_run_id": str((((prestress_manifest.get("identity") or {}).get("platform_run_id")) or "")).strip(),
        "recovery_platform_run_id": recovery_platform_run_id,
        "verdict": "PR3_S3_READY" if len(blockers) == 0 else "HOLD_REMEDIATE",
        "next_state": "PR3-S4" if len(blockers) == 0 else "PR3-S3",
        "open_blockers": len(sorted(set(blockers))),
        "blocker_ids": sorted(set(blockers)),
        "evidence_refs": {
            "prestress_summary_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/{args.prestress_artifact_prefix}_wsp_runtime_summary.json",
            "recovery_summary_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/{args.recovery_artifact_prefix}_wsp_runtime_summary.json",
            "scorecard_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/g3a_scorecard_recovery.json",
            "timeline_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/g3a_recovery_timeline.json",
            "bound_report_ref": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/g3a_recovery_bound_report.json",
        },
        "checks": scorecard["checks"],
    }

    dump_json(root / "g3a_scorecard_recovery.json", scorecard)
    dump_json(root / "g3a_recovery_timeline.json", timeline)
    dump_json(root / "g3a_recovery_bound_report.json", bound_report)
    dump_json(root / "pr3_s3_execution_receipt.json", receipt)
    dump_json(
        Path(args.run_control_root) / "pr3_latest.json",
        {
            "phase": "PR3",
            "execution_id": args.pr3_execution_id,
            "latest_state": args.state_id,
            "latest_receipt": f"runs/dev_substrate/dev_full/road_to_prod/run_control/{args.pr3_execution_id}/pr3_s3_execution_receipt.json",
            "updated_at_utc": now_utc(),
        },
    )

    print(
        json.dumps(
            {
                "execution_id": args.pr3_execution_id,
                "state": args.state_id,
                "verdict": receipt["verdict"],
                "next_state": receipt["next_state"],
                "open_blockers": receipt["open_blockers"],
                "timeline_ref": receipt["evidence_refs"]["timeline_ref"],
                "recovery_seconds": recovery_elapsed_seconds,
                "blocker_ids": receipt["blocker_ids"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
