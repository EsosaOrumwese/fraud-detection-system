from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from typing import Any, Iterable

import polars as pl
import yaml


UTC = timezone.utc
MIN_EVENTS_PER_SCENARIO = 2000


@dataclass
class Scenario:
    scenario_id: str
    scenario_version: str
    is_baseline: bool
    is_stress: bool
    labels: list[str]
    horizon_start_utc: datetime
    horizon_end_utc: datetime
    bucket_duration_minutes: int
    emit_utc_intensities: bool


def _parse_rfc3339(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)


def _format_rfc3339(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _u_det(scenario_id: str, stage: str, *keys: str) -> float:
    msg = "5A.calendar|" + scenario_id + "|" + stage
    if keys:
        msg += "|" + "|".join(keys)
    h = hashlib.sha256(msg.encode("utf-8")).digest()
    x = int.from_bytes(h[:8], "big")
    return (x + 0.5) / 2**64


def _month_iter(start: datetime, end: datetime) -> Iterable[tuple[int, int]]:
    year = start.year
    month = start.month
    while True:
        current = datetime(year, month, 1, tzinfo=UTC)
        if current >= end:
            break
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime, int]:
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=UTC)
    start = datetime(year, month, 1, tzinfo=UTC)
    last_day = (next_month - timedelta(days=1)).day
    return start, next_month, last_day


def _shift_weekend(date: datetime) -> datetime:
    weekday = date.weekday()
    if weekday == 5:
        return date - timedelta(days=1)
    if weekday == 6:
        return date - timedelta(days=2)
    return date


def _bucket_align(ts: datetime, bucket_minutes: int) -> datetime:
    minutes = ts.hour * 60 + ts.minute
    aligned = (minutes // bucket_minutes) * bucket_minutes
    return ts.replace(hour=aligned // 60, minute=aligned % 60, second=0, microsecond=0)


def _clamp_window(start: datetime, end: datetime, horizon_start: datetime, horizon_end: datetime) -> tuple[datetime, datetime] | None:
    clamped_start = max(start, horizon_start)
    clamped_end = min(end, horizon_end)
    if clamped_end <= clamped_start:
        return None
    return clamped_start, clamped_end


def _render_number(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _event_id(row: dict[str, Any], existing: set[str]) -> str:
    lines = [
        f"type={row['event_type']}",
        f"start={row['start_utc']}",
        f"end={row['end_utc']}",
        f"shape={row['shape_kind']}",
        f"amp={_render_number(row['amplitude'])}",
        f"peak={_render_number(row['amplitude_peak'])}",
        f"rin={_render_number(row['ramp_in_buckets'])}",
        f"rout={_render_number(row['ramp_out_buckets'])}",
        f"global={_render_number(row['scope_global'])}",
        f"country={_render_number(row['country_iso'])}",
        f"tzid={_render_number(row['tzid'])}",
        f"class={_render_number(row['demand_class'])}",
        f"merchant={_render_number(row['merchant_id'])}",
    ]
    base = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    event_id = "EVT-" + base[:24]
    if event_id not in existing:
        return event_id
    idx = 2
    while True:
        candidate = f"{event_id}-{idx}"
        if candidate not in existing:
            return candidate
        idx += 1


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_scenarios(path: Path) -> list[Scenario]:
    data = _load_yaml(path)
    scenarios = []
    for row in data["scenarios"]:
        scenarios.append(
            Scenario(
                scenario_id=row["scenario_id"],
                scenario_version=row["scenario_version"],
                is_baseline=bool(row["is_baseline"]),
                is_stress=bool(row["is_stress"]),
                labels=row.get("labels", []),
                horizon_start_utc=_parse_rfc3339(row["horizon_start_utc"]),
                horizon_end_utc=_parse_rfc3339(row["horizon_end_utc"]),
                bucket_duration_minutes=int(row["bucket_duration_minutes"]),
                emit_utc_intensities=bool(row["emit_utc_intensities"]),
            )
        )
    return scenarios


def _load_zone_universe(zone_alloc_path: Path) -> tuple[list[str], list[str]]:
    df = pl.read_parquet(zone_alloc_path, columns=["legal_country_iso", "tzid"])
    countries = df.select(pl.col("legal_country_iso").unique().sort()).to_series().to_list()
    tzids = df.select(pl.col("tzid").unique().sort()).to_series().to_list()
    return countries, tzids


def _validate_event_bounds(event: dict[str, Any], overlay_policy: dict) -> None:
    event_def = overlay_policy["event_types"][event["event_type"]]
    bounds = event_def["amplitude_bounds"]
    if event["shape_kind"] == "constant":
        if event["amplitude"] is None:
            raise ValueError("constant event missing amplitude")
        if not (bounds[0] <= event["amplitude"] <= bounds[1]):
            raise ValueError(f"{event['event_type']} amplitude out of bounds")
    else:
        if event["amplitude_peak"] is None:
            raise ValueError("ramp event missing amplitude_peak")
        if not (bounds[0] <= event["amplitude_peak"] <= bounds[1]):
            raise ValueError(f"{event['event_type']} amplitude_peak out of bounds")


def _amplitude_in_bounds(event_type: str, overlay_policy: dict, scenario_id: str, stage: str, *keys: str) -> float:
    bounds = overlay_policy["event_types"][event_type]["amplitude_bounds"]
    u = _u_det(scenario_id, stage, *keys)
    return bounds[0] + (bounds[1] - bounds[0]) * u


def _ensure_scope(event: dict[str, Any]) -> None:
    if event["scope_global"]:
        if any(event[key] is not None for key in ("country_iso", "tzid", "demand_class", "merchant_id")):
            raise ValueError("global scope cannot combine with other predicates")
    else:
        if not any(event[key] is not None for key in ("country_iso", "tzid", "demand_class", "merchant_id")):
            raise ValueError("event scope is empty")
    if event["merchant_id"] is not None and (event["country_iso"] is not None or event["tzid"] is not None):
        raise ValueError("merchant scope is exclusive")


def _event_row(
    manifest_fingerprint: str,
    scenario_id: str,
    event_type: str,
    start: datetime,
    end: datetime,
    shape_kind: str,
    amplitude: float | None,
    amplitude_peak: float | None,
    ramp_in: int | None,
    ramp_out: int | None,
    scope_global: bool,
    country_iso: str | None,
    tzid: str | None,
    demand_class: str | None,
    merchant_id: int | None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "manifest_fingerprint": manifest_fingerprint,
        "scenario_id": scenario_id,
        "event_id": None,
        "event_type": event_type,
        "start_utc": _format_rfc3339(start),
        "end_utc": _format_rfc3339(end),
        "shape_kind": shape_kind,
        "amplitude": amplitude,
        "amplitude_peak": amplitude_peak,
        "ramp_in_buckets": ramp_in,
        "ramp_out_buckets": ramp_out,
        "scope_global": scope_global,
        "country_iso": country_iso,
        "tzid": tzid,
        "demand_class": demand_class,
        "merchant_id": merchant_id,
        "notes": notes,
    }


def _generate_events(
    scenario: Scenario,
    manifest_fingerprint: str,
    overlay_policy: dict,
    demand_classes: set[str],
    countries: list[str],
    tzids: list[str],
) -> list[dict[str, Any]]:
    bucket_minutes = scenario.bucket_duration_minutes
    horizon_start = scenario.horizon_start_utc
    horizon_end = scenario.horizon_end_utc
    events: list[dict[str, Any]] = []

    required_classes = ["consumer_daytime", "evening_weekend", "online_24h", "office_hours", "online_bursty"]
    for cls in required_classes:
        if cls not in demand_classes:
            raise ValueError(f"Required demand_class missing: {cls}")

    # PAYDAY events
    for country in countries:
        for year, month in _month_iter(horizon_start, horizon_end):
            month_start, month_end, last_day = _month_bounds(year, month)
            choices = [15, 25, last_day]
            u = _u_det(scenario.scenario_id, "payday_rule", country, f"{year:04d}-{month:02d}")
            choice = choices[int(u * len(choices))]
            pay_date = _shift_weekend(datetime(year, month, choice, tzinfo=UTC))
            pay_start = datetime(pay_date.year, pay_date.month, pay_date.day, tzinfo=UTC)
            pay_end = pay_start + timedelta(hours=48)
            clamped = _clamp_window(pay_start, pay_end, horizon_start, horizon_end)
            if not clamped:
                continue
            pay_start, pay_end = clamped
            ramp_in = max(2, int(6 * 60 / bucket_minutes))
            ramp_out = max(4, int(24 * 60 / bucket_minutes))
            events.extend(
                [
                    _event_row(
                        manifest_fingerprint,
                        scenario.scenario_id,
                        "PAYDAY",
                        pay_start,
                        pay_end,
                        "ramp",
                        None,
                        1.25,
                        ramp_in,
                        ramp_out,
                        False,
                        country,
                        None,
                        "consumer_daytime",
                        None,
                        notes="payday uplift",
                    ),
                    _event_row(
                        manifest_fingerprint,
                        scenario.scenario_id,
                        "PAYDAY",
                        pay_start,
                        pay_end,
                        "ramp",
                        None,
                        1.20,
                        ramp_in,
                        ramp_out,
                        False,
                        country,
                        None,
                        "evening_weekend",
                        None,
                        notes="payday uplift",
                    ),
                    _event_row(
                        manifest_fingerprint,
                        scenario.scenario_id,
                        "PAYDAY",
                        pay_start,
                        pay_end,
                        "ramp",
                        None,
                        1.30,
                        ramp_in,
                        ramp_out,
                        False,
                        country,
                        None,
                        "online_24h",
                        None,
                        notes="payday uplift",
                    ),
                ]
            )

    # HOLIDAY events
    for country in countries:
        for year, month in _month_iter(horizon_start, horizon_end):
            month_start, month_end, last_day = _month_bounds(year, month)
            u = _u_det(scenario.scenario_id, "holiday_count", country, f"{year:04d}-{month:02d}")
            n_holidays = 1 + int(u < 0.60)
            used_days = set()
            for idx in range(n_holidays):
                for attempt in range(1, last_day + 2):
                    u_day = _u_det(scenario.scenario_id, "holiday_day", country, f"{year:04d}-{month:02d}", str(idx), str(attempt))
                    day = 1 + int(u_day * last_day)
                    if day in used_days:
                        continue
                    holiday_date = datetime(year, month, day, tzinfo=UTC)
                    used_days.add(day)
                    start = datetime(year, month, day, tzinfo=UTC)
                    end = start + timedelta(hours=24)
                    clamped = _clamp_window(start, end, horizon_start, horizon_end)
                    if not clamped:
                        break
                    start, end = clamped
                    events.extend(
                        [
                            _event_row(
                                manifest_fingerprint,
                                scenario.scenario_id,
                                "HOLIDAY",
                                start,
                                end,
                                "constant",
                                0.65,
                                None,
                                None,
                                None,
                                False,
                                country,
                                None,
                                "office_hours",
                                None,
                                notes="holiday dampening",
                            ),
                            _event_row(
                                manifest_fingerprint,
                                scenario.scenario_id,
                                "HOLIDAY",
                                start,
                                end,
                                "constant",
                                0.85,
                                None,
                                None,
                                None,
                                False,
                                country,
                                None,
                                "consumer_daytime",
                                None,
                                notes="holiday dampening",
                            ),
                            _event_row(
                                manifest_fingerprint,
                                scenario.scenario_id,
                                "HOLIDAY",
                                start,
                                end,
                                "constant",
                                1.03,
                                None,
                                None,
                                None,
                                False,
                                country,
                                None,
                                "online_24h",
                                None,
                                notes="holiday mild uplift online",
                            ),
                        ]
                    )
                    break

    # CAMPAIGN events (global monthly)
    for year, month in _month_iter(horizon_start, horizon_end):
        month_start, month_end, last_day = _month_bounds(year, month)
        window_start = max(month_start, horizon_start)
        window_end = min(month_end, horizon_end)
        duration_days = 7
        available_days = max(1, (window_end - window_start).days - duration_days)
        u = _u_det(scenario.scenario_id, "campaign_start", f"{year:04d}-{month:02d}")
        offset = int(u * available_days)
        start = _bucket_align(window_start + timedelta(days=offset), bucket_minutes)
        end = start + timedelta(days=duration_days)
        clamped = _clamp_window(start, end, horizon_start, horizon_end)
        if clamped:
            start, end = clamped
            peak = 1.80 if scenario.is_stress else 1.35
            ramp_in = int(24 * 60 / bucket_minutes)
            ramp_out = int(24 * 60 / bucket_minutes)
            events.append(
                _event_row(
                    manifest_fingerprint,
                    scenario.scenario_id,
                    "CAMPAIGN",
                    start,
                    end,
                    "ramp",
                    None,
                    peak,
                    ramp_in,
                    ramp_out,
                    False,
                    None,
                    None,
                    "online_bursty",
                    None,
                    notes="global campaign",
                )
            )

    # CAMPAIGN events (stress-only major markets)
    if scenario.is_stress:
        ranked = sorted(
            ((country, _u_det(scenario.scenario_id, "major_market_rank", country)) for country in countries),
            key=lambda item: item[1],
            reverse=True,
        )
        for country, _ in ranked[: min(20, len(ranked))]:
            duration_days = 5
            available_days = max(1, (horizon_end - horizon_start).days - duration_days)
            u = _u_det(scenario.scenario_id, "major_campaign_start", country)
            offset = int(u * available_days)
            start = _bucket_align(horizon_start + timedelta(days=offset), bucket_minutes)
            end = start + timedelta(days=duration_days)
            clamped = _clamp_window(start, end, horizon_start, horizon_end)
            if not clamped:
                continue
            start, end = clamped
            ramp_in = int(12 * 60 / bucket_minutes)
            ramp_out = int(12 * 60 / bucket_minutes)
            events.append(
                _event_row(
                    manifest_fingerprint,
                    scenario.scenario_id,
                    "CAMPAIGN",
                    start,
                    end,
                    "ramp",
                    None,
                    1.55,
                    ramp_in,
                    ramp_out,
                    False,
                    country,
                    None,
                    "online_24h",
                    None,
                    notes="major market campaign",
                )
            )

    # OUTAGE events
    horizon_days = (horizon_end - horizon_start).days
    n_outage = ceil(horizon_days * 0.6)
    horizon_minutes = int((horizon_end - horizon_start).total_seconds() / 60)
    total_buckets = horizon_minutes // bucket_minutes
    for idx in range(1, n_outage + 1):
        u = _u_det(scenario.scenario_id, "outage_tzid", str(idx))
        tzid = tzids[int(u * len(tzids))]
        u_start = _u_det(scenario.scenario_id, "outage_start", tzid, str(idx))
        bucket_index = int(u_start * total_buckets)
        start = horizon_start + timedelta(minutes=bucket_index * bucket_minutes)
        start = _bucket_align(start, bucket_minutes)
        u_dur = _u_det(scenario.scenario_id, "outage_duration", tzid, str(idx))
        duration_hours = [2, 4, 8][int(u_dur * 3)]
        end = start + timedelta(hours=duration_hours)
        clamped = _clamp_window(start, end, horizon_start, horizon_end)
        if not clamped:
            continue
        start, end = clamped
        events.append(
            _event_row(
                manifest_fingerprint,
                scenario.scenario_id,
                "OUTAGE",
                start,
                end,
                "constant",
                0.05,
                None,
                None,
                None,
                False,
                None,
                tzid,
                None,
                None,
                notes="localized outage",
            )
        )

    # STRESS events
    if scenario.is_stress:
        u = _u_det(scenario.scenario_id, "stress_global_duration")
        duration_days = 14 + int(u * 8)
        available_days = max(1, (horizon_end - horizon_start).days - duration_days)
        u_start = _u_det(scenario.scenario_id, "stress_global_start")
        offset = int(u_start * available_days)
        start = _bucket_align(horizon_start + timedelta(days=offset), bucket_minutes)
        end = start + timedelta(days=duration_days)
        clamped = _clamp_window(start, end, horizon_start, horizon_end)
        if clamped:
            start, end = clamped
            events.append(
                _event_row(
                    manifest_fingerprint,
                    scenario.scenario_id,
                    "STRESS",
                    start,
                    end,
                    "constant",
                    1.60,
                    None,
                    None,
                    None,
                    True,
                    None,
                    None,
                    None,
                    None,
                    notes="global stress",
                )
            )

        u_count = _u_det(scenario.scenario_id, "stress_country_count")
        n_country = 2 + int(u_count * 3)
        ranked = sorted(
            ((country, _u_det(scenario.scenario_id, "stress_country_rank", country)) for country in countries),
            key=lambda item: item[1],
            reverse=True,
        )
        for country, _ in ranked[: min(n_country, len(ranked))]:
            u = _u_det(scenario.scenario_id, "stress_country_duration", country)
            duration_days = 7 + int(u * 8)
            available_days = max(1, (horizon_end - horizon_start).days - duration_days)
            u_start = _u_det(scenario.scenario_id, "stress_country_start", country)
            offset = int(u_start * available_days)
            start = _bucket_align(horizon_start + timedelta(days=offset), bucket_minutes)
            end = start + timedelta(days=duration_days)
            clamped = _clamp_window(start, end, horizon_start, horizon_end)
            if not clamped:
                continue
            start, end = clamped
            events.append(
                _event_row(
                    manifest_fingerprint,
                    scenario.scenario_id,
                    "STRESS",
                    start,
                    end,
                    "constant",
                    1.85,
                    None,
                    None,
                    None,
                    False,
                    country,
                    None,
                    None,
                    None,
                    notes="country stress",
                )
            )

    min_events = MIN_EVENTS_PER_SCENARIO
    max_events = overlay_policy["calendar_validation"]["max_events_per_scenario"]
    if len(events) < min_events:
        extra_classes = sorted(demand_classes.difference(required_classes))
        if extra_classes:
            extras: list[dict[str, Any]] = []
            for event in events:
                if event["event_type"] not in {"PAYDAY", "HOLIDAY"}:
                    continue
                if event["demand_class"] not in required_classes:
                    continue
                for extra_class in extra_classes:
                    extra = dict(event)
                    extra["demand_class"] = extra_class
                    if event["event_type"] == "PAYDAY":
                        extra["amplitude_peak"] = _amplitude_in_bounds(
                            "PAYDAY",
                            overlay_policy,
                            scenario.scenario_id,
                            "payday_extra_amp",
                            extra_class,
                            str(event.get("country_iso") or "global"),
                            str(event.get("start_utc") or ""),
                        )
                        extra["amplitude"] = None
                    else:
                        extra["amplitude"] = _amplitude_in_bounds(
                            "HOLIDAY",
                            overlay_policy,
                            scenario.scenario_id,
                            "holiday_extra_amp",
                            extra_class,
                            str(event.get("country_iso") or "global"),
                            str(event.get("start_utc") or ""),
                        )
                        extra["amplitude_peak"] = None
                        extra["ramp_in_buckets"] = None
                        extra["ramp_out_buckets"] = None
                    note = event.get("notes") or ""
                    extra["notes"] = (note + " | class-extended").strip()
                    extras.append(extra)
            for extra in extras:
                if len(events) >= min_events:
                    break
                if len(events) + 1 > max_events:
                    break
                events.append(extra)
        if len(events) < min_events:
            raise ValueError(f"Event count {len(events)} below realism floor {min_events}")

    # validate bounds + scope
    for event in events:
        _validate_event_bounds(event, overlay_policy)
        _ensure_scope(event)

    return events


def _overlap_sample(events: list[dict[str, Any]], scenario: Scenario, max_overlap: int) -> int:
    horizon_minutes = int((scenario.horizon_end_utc - scenario.horizon_start_utc).total_seconds() / 60)
    total_buckets = horizon_minutes // scenario.bucket_duration_minutes

    def active(event: dict[str, Any], bucket_start: datetime, bucket_end: datetime) -> bool:
        start = _parse_rfc3339(event["start_utc"])
        end = _parse_rfc3339(event["end_utc"])
        return start < bucket_end and end > bucket_start

    def match(scope: dict[str, Any], event: dict[str, Any]) -> bool:
        if event["scope_global"]:
            return True
        for key in ("country_iso", "tzid", "demand_class", "merchant_id"):
            value = event[key]
            if value is not None and scope.get(key) != value:
                return False
        return True

    max_seen = 0
    n_events = len(events)
    for idx in range(1, 1001):
        u_row = _u_det(scenario.scenario_id, "overlap_row", str(idx))
        u_bucket = _u_det(scenario.scenario_id, "overlap_bucket", str(idx))
        row_idx = int(u_row * n_events)
        bucket_idx = int(u_bucket * total_buckets)
        bucket_start = scenario.horizon_start_utc + timedelta(minutes=bucket_idx * scenario.bucket_duration_minutes)
        bucket_end = bucket_start + timedelta(minutes=scenario.bucket_duration_minutes)
        scope = {
            "country_iso": events[row_idx]["country_iso"],
            "tzid": events[row_idx]["tzid"],
            "demand_class": events[row_idx]["demand_class"],
            "merchant_id": events[row_idx]["merchant_id"],
        }
        overlap = 0
        for event in events:
            if match(scope, event) and active(event, bucket_start, bucket_end):
                overlap += 1
        max_seen = max(max_seen, overlap)
        if overlap > max_overlap:
            raise ValueError(f"Overlap {overlap} exceeds max {max_overlap}")
    return max_seen


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-fingerprint", required=True)
    parser.add_argument("--zone-alloc-path", type=Path, required=True)
    parser.add_argument(
        "--horizon-config",
        type=Path,
        default=Path("config/layer2/5A/scenario/scenario_horizon_config_5A.v1.yaml"),
    )
    parser.add_argument(
        "--overlay-policy",
        type=Path,
        default=Path("config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml"),
    )
    parser.add_argument(
        "--class-policy",
        type=Path,
        default=Path("config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Root for data/layer2/5A/scenario_calendar outputs.",
    )
    args = parser.parse_args()

    overlay_policy = _load_yaml(args.overlay_policy)
    class_policy = _load_yaml(args.class_policy)
    scenarios = _load_scenarios(args.horizon_config)
    demand_classes = {row["demand_class"] for row in class_policy["demand_class_catalog"]}
    countries, tzids = _load_zone_universe(args.zone_alloc_path)

    for scenario in scenarios:
        events = _generate_events(
            scenario,
            args.manifest_fingerprint,
            overlay_policy,
            demand_classes,
            countries,
            tzids,
        )

        max_events = overlay_policy["calendar_validation"]["max_events_per_scenario"]
        if not (MIN_EVENTS_PER_SCENARIO <= len(events) <= max_events):
            raise ValueError(
                f"Event count {len(events)} outside realism bounds [{MIN_EVENTS_PER_SCENARIO}, {max_events}]"
            )

        event_ids = set()
        for event in events:
            event_id = _event_id(event, event_ids)
            event["event_id"] = event_id
            event_ids.add(event_id)

        max_overlap = overlay_policy["calendar_validation"]["max_overlap_events_per_row_bucket"]
        max_seen = _overlap_sample(events, scenario, max_overlap)

        events_by_type = {}
        for event in events:
            events_by_type[event["event_type"]] = events_by_type.get(event["event_type"], 0) + 1

        country_coverage = len({event["country_iso"] for event in events if event["country_iso"] is not None})
        tzid_coverage = len({event["tzid"] for event in events if event["tzid"] is not None})

        columns = {
            "manifest_fingerprint": [event["manifest_fingerprint"] for event in events],
            "scenario_id": [event["scenario_id"] for event in events],
            "event_id": [event["event_id"] for event in events],
            "event_type": [event["event_type"] for event in events],
            "start_utc": [event["start_utc"] for event in events],
            "end_utc": [event["end_utc"] for event in events],
            "shape_kind": [event["shape_kind"] for event in events],
            "amplitude": [event["amplitude"] for event in events],
            "amplitude_peak": [event["amplitude_peak"] for event in events],
            "ramp_in_buckets": [event["ramp_in_buckets"] for event in events],
            "ramp_out_buckets": [event["ramp_out_buckets"] for event in events],
            "scope_global": [event["scope_global"] for event in events],
            "country_iso": [event["country_iso"] for event in events],
            "tzid": [event["tzid"] for event in events],
            "demand_class": [event["demand_class"] for event in events],
            "merchant_id": [event["merchant_id"] for event in events],
            "notes": [event["notes"] for event in events],
        }
        schema = {
            "manifest_fingerprint": pl.Utf8,
            "scenario_id": pl.Utf8,
            "event_id": pl.Utf8,
            "event_type": pl.Utf8,
            "start_utc": pl.Utf8,
            "end_utc": pl.Utf8,
            "shape_kind": pl.Utf8,
            "amplitude": pl.Float64,
            "amplitude_peak": pl.Float64,
            "ramp_in_buckets": pl.Int64,
            "ramp_out_buckets": pl.Int64,
            "scope_global": pl.Boolean,
            "country_iso": pl.Utf8,
            "tzid": pl.Utf8,
            "demand_class": pl.Utf8,
            "merchant_id": pl.UInt64,
            "notes": pl.Utf8,
        }
        df = pl.DataFrame(columns, schema=schema)
        output_dir = (
            args.output_root
            / "data/layer2/5A/scenario_calendar"
            / f"manifest_fingerprint={args.manifest_fingerprint}"
            / f"scenario_id={scenario.scenario_id}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "scenario_calendar_5A.parquet"
        df.write_parquet(output_path)

        provenance = {
            "manifest_fingerprint": args.manifest_fingerprint,
            "scenario_id": scenario.scenario_id,
            "inputs": {
                "scenario_horizon_config": {
                    "path": str(args.horizon_config),
                    "sha256": _hash_file(args.horizon_config),
                },
                "scenario_overlay_policy": {
                    "path": str(args.overlay_policy),
                    "sha256": _hash_file(args.overlay_policy),
                },
                "merchant_class_policy": {
                    "path": str(args.class_policy),
                    "sha256": _hash_file(args.class_policy),
                },
                "zone_alloc": {
                    "path": str(args.zone_alloc_path),
                    "sha256": _hash_file(args.zone_alloc_path),
                },
            },
            "generation": {
                "countries": len(countries),
                "tzids": len(tzids),
                "event_counts": events_by_type,
            },
            "summary": {
                "total_events": len(events),
                "country_coverage": country_coverage,
                "tzid_coverage": tzid_coverage,
                "max_overlap_sample": max_seen,
            },
        }
        provenance_path = output_dir / "scenario_calendar_5A.provenance.json"
        provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8", newline="\n")

        print(f"Wrote {output_path} ({len(events)} events)")


if __name__ == "__main__":
    main()
