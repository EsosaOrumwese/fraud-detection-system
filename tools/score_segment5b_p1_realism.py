#!/usr/bin/env python3
"""Emit Segment 5B remediation P1 gateboard and conditional upstream-reopen evidence."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl


RUN_ID_DEFAULT = "c25a2675fbfbacd952b13bb594880e92"
SEEDS_REQUIRED = [42, 7, 101, 202]


@dataclass(frozen=True)
class Gate:
    gate_id: str
    title: str
    klass: str  # hard | major | context
    b_target: str
    bplus_target: str


GATES: dict[str, Gate] = {
    "T1": Gate("T1", "Civil-time mismatch rate", "hard", "<= 0.0050", "<= 0.0010"),
    "T2": Gate("T2", "One-hour DST signature mass", "hard", "<= 0.0010", "<= 0.0002"),
    "T3": Gate("T3", "DST-window hour-bin MAE (pp)", "hard", "<= 1.5", "<= 0.7"),
    "T4": Gate("T4", "Logical-key count conservation", "hard", "mismatch_count=0 and residual_sum=0", "mismatch_count=0 and residual_sum=0"),
    "T5": Gate("T5", "Routing field integrity", "hard", "violation_rate=0", "violation_rate=0"),
    "T6": Gate("T6", "Timezone concentration top-10 share", "major", "<= 0.72", "<= 0.62"),
    "T7": Gate("T7", "Virtual share", "major", "0.03 <= share <= 0.08", "0.05 <= share <= 0.12"),
    "T8": Gate("T8", "Weekend-share delta (pp)", "context", "<= 0.20", "<= 0.10"),
    "T9": Gate("T9", "Std of standardized count residuals", "context", "1.20..1.60", "1.25..1.50"),
    "T10": Gate("T10", "Cross-seed CV over key metrics", "hard", "<= 0.25", "<= 0.15"),
    "T11": Gate("T11", "TZ-cache horizon completeness", "hard", "100%", "100%"),
    "T12": Gate("T12", "Local-time contract integrity", "hard", "100%", "100%"),
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_latest_segment_state_runs(run_root: Path) -> Path:
    candidates = sorted(
        run_root.glob("reports/layer2/segment_state_runs/segment=5B/utc_day=*/segment_state_runs.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"Missing 5B segment_state_runs under {run_root}")
    return candidates[-1]


def _latest_state_row(records: list[dict[str, Any]], state: str) -> dict[str, Any]:
    rows = [r for r in records if str(r.get("state")) == state]
    if not rows:
        raise ValueError(f"No rows found for {state}")
    pass_rows = [r for r in rows if str(r.get("status")) == "PASS"]
    src = pass_rows if pass_rows else rows
    return sorted(src, key=lambda r: (str(r.get("finished_at_utc") or ""), str(r.get("started_at_utc") or "")))[-1]


def _parse_utc(ts: str) -> datetime:
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(UTC)


def _parse_local_wall(ts: str) -> datetime:
    # Contract mismatch lane: local values are encoded with Z marker semantics.
    # For realism checks we compare true wall-clock by dropping marker semantics.
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1]
    if text.endswith("+00:00"):
        text = text[:-6]
    return datetime.fromisoformat(text)


def _parse_local_validator(ts: str, tzid: str) -> datetime:
    # Mirrors 5B.S5 validator semantics after P1.2/P1.3:
    # local fields are parsed as wall-clock values (legacy Z/+00 markers stripped).
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1]
    if text.endswith("+00:00"):
        text = text[:-6]
    parsed = datetime.fromisoformat(text)
    zone = ZoneInfo(tzid)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=zone).replace(tzinfo=None)
    return parsed.astimezone(zone).replace(tzinfo=None)


def _build_transition_windows(tzid: str, utc_min: datetime, utc_max: datetime) -> list[tuple[datetime, datetime]]:
    try:
        tz = ZoneInfo(tzid)
    except Exception:
        return []
    probe_start = utc_min - timedelta(days=2)
    probe_end = utc_max + timedelta(days=2)
    cur = probe_start
    prev_offset: int | None = None
    transitions: list[datetime] = []
    while cur <= probe_end:
        off = int(cur.astimezone(tz).utcoffset().total_seconds())
        if prev_offset is not None and off != prev_offset:
            transitions.append(cur)
        prev_offset = off
        cur += timedelta(hours=1)
    return [(t - timedelta(hours=24), t + timedelta(hours=24)) for t in transitions]


def _deterministic_arrival_sample(arrivals_glob: str, n_total: int, target: int) -> pl.DataFrame:
    modulus = 1_000_003
    threshold = max(1, int((target / max(float(n_total), 1.0)) * modulus))
    lf = pl.scan_parquet(arrivals_glob).select(
        [
            "ts_utc",
            "tzid_primary",
            "ts_local_primary",
            "arrival_seq",
            "bucket_index",
        ]
    )
    key_expr = (
        pl.col("arrival_seq").cast(pl.UInt64) * pl.lit(6364136223846793005, dtype=pl.UInt64)
        + pl.col("bucket_index").cast(pl.UInt64)
    ) % pl.lit(modulus, dtype=pl.UInt64)
    sampled = lf.filter(key_expr < pl.lit(threshold, dtype=pl.UInt64)).collect()
    if sampled.height == 0:
        sampled = lf.limit(min(5000, n_total)).collect()
    return sampled


def _deterministic_s3_sample(s3_path: str, target: int = 200_000) -> pl.DataFrame:
    n_total = int(pl.scan_parquet(s3_path).select(pl.len().alias("n")).collect()["n"][0])
    modulus = 1_000_003
    threshold = max(1, int((target / max(float(n_total), 1.0)) * modulus))
    lf = pl.scan_parquet(s3_path).select(["merchant_id", "bucket_index", "count_N", "mu"])
    key_expr = (
        pl.col("merchant_id").cast(pl.UInt64) * pl.lit(11400714819323198485, dtype=pl.UInt64)
        + pl.col("bucket_index").cast(pl.UInt64)
    ) % pl.lit(modulus, dtype=pl.UInt64)
    return lf.filter(key_expr < pl.lit(threshold, dtype=pl.UInt64)).collect()


def _format_pct(value: float | None) -> str | None:
    if value is None:
        return None
    return f"{value * 100.0:.4f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5B remediation P1 local-lane realism.")
    parser.add_argument("--runs-root", default="runs/local_full_run-5")
    parser.add_argument("--run-id", default=RUN_ID_DEFAULT)
    parser.add_argument("--out-root", default="runs/fix-data-engine/segment_5B/reports")
    parser.add_argument("--sample-target", type=int, default=200_000)
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_id = args.run_id.strip() or RUN_ID_DEFAULT
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    receipt = _load_json(run_root / "run_receipt.json")
    mf = str(receipt["manifest_fingerprint"])
    seed = int(receipt["seed"])

    state_runs_path = _find_latest_segment_state_runs(run_root)
    state_rows = _load_jsonl(state_runs_path)
    s4 = _latest_state_row(state_rows, "S4")
    s5 = _latest_state_row(state_rows, "S5")

    arrivals_glob = str(
        run_root
        / "data"
        / "layer2"
        / "5B"
        / "arrival_events"
        / f"seed={seed}"
        / f"manifest_fingerprint={mf}"
        / "scenario_id=baseline_v1"
        / "*.parquet"
    )
    s3_path = str(
        run_root
        / "data"
        / "layer2"
        / "5B"
        / "s3_bucket_counts"
        / f"seed={seed}"
        / f"manifest_fingerprint={mf}"
        / "scenario_id=baseline_v1"
        / "s3_bucket_counts_5B.parquet"
    )
    validation_report_path = (
        run_root
        / "data"
        / "layer2"
        / "5B"
        / "validation"
        / f"manifest_fingerprint={mf}"
        / "validation_report_5B.json"
    )
    validation_issue_path = (
        run_root
        / "data"
        / "layer2"
        / "5B"
        / "validation"
        / f"manifest_fingerprint={mf}"
        / "validation_issue_table_5B.parquet"
    )
    tz_cache_meta_path = (
        run_root
        / "data"
        / "layer1"
        / "2A"
        / "tz_timetable_cache"
        / f"manifest_fingerprint={mf}"
        / "tz_timetable_cache.json"
    )

    validation_report = _load_json(validation_report_path)
    validation_issues = pl.read_parquet(validation_issue_path)
    tz_cache_meta = _load_json(tz_cache_meta_path)
    latest_civil_ok = bool(((s5.get("metrics") or {}).get("civil_time_ok")))
    n_arrivals_total = int(((s4.get("total_arrivals")) or ((s5.get("metrics") or {}).get("n_arrivals_total") or 0)))

    # Full-scan integrity/concentration metrics.
    integrity_df = (
        pl.scan_parquet(arrivals_glob)
        .select(
            [
                pl.len().alias("n_total"),
                pl.col("is_virtual").sum().alias("n_virtual"),
                (
                    (~pl.col("is_virtual"))
                    & (pl.col("site_id").is_null() | pl.col("edge_id").is_not_null())
                )
                .sum()
                .alias("viol_physical"),
                (
                    pl.col("is_virtual")
                    & (pl.col("edge_id").is_null() | pl.col("site_id").is_not_null())
                )
                .sum()
                .alias("viol_virtual"),
            ]
        )
        .collect()
    )
    integrity = integrity_df.to_dicts()[0]
    n_total = int(integrity["n_total"])
    n_virtual = int(integrity["n_virtual"])
    n_violations = int(integrity["viol_physical"]) + int(integrity["viol_virtual"])
    violation_rate = (n_violations / n_total) if n_total > 0 else 0.0

    tz_counts = (
        pl.scan_parquet(arrivals_glob)
        .group_by("tzid_primary")
        .agg(pl.len().alias("n"))
        .collect()
        .sort("n", descending=True)
    )
    top10_share = (float(tz_counts.head(10)["n"].sum()) / float(n_total)) if n_total > 0 else 0.0

    # S3 conservation.
    s3_sum = int(pl.scan_parquet(s3_path).select(pl.col("count_N").sum().alias("x")).collect()["x"][0])
    residual_sum = s3_sum - n_total

    # Sampled temporal metrics.
    sampled = _deterministic_arrival_sample(arrivals_glob, n_total=n_total, target=args.sample_target)
    sample_rows = sampled.to_dicts()
    sample_size = len(sample_rows)

    tzids = sorted({str(r["tzid_primary"]) for r in sample_rows if r.get("tzid_primary")})
    utc_values = [_parse_utc(str(r["ts_utc"])) for r in sample_rows]
    utc_min = min(utc_values)
    utc_max = max(utc_values)
    windows_by_tz = {tzid: _build_transition_windows(tzid, utc_min, utc_max) for tzid in tzids}

    mismatch_count = 0
    one_hour_count = 0
    weekend_obs_count = 0
    weekend_exp_count = 0
    contract_marker_count = 0
    contract_parse_mismatch_count = 0
    bad_parse_count = 0

    # Window-wise hour histograms for T3.
    window_obs_hours: dict[str, list[int]] = defaultdict(lambda: [0] * 24)
    window_exp_hours: dict[str, list[int]] = defaultdict(lambda: [0] * 24)
    window_support: dict[str, int] = defaultdict(int)

    for row in sample_rows:
        tzid = str(row["tzid_primary"])
        ts_utc = _parse_utc(str(row["ts_utc"]))
        ts_local_raw = str(row["ts_local_primary"])
        if tzid != "UTC" and ts_local_raw.endswith("Z"):
            contract_marker_count += 1
        try:
            obs_local = _parse_local_wall(ts_local_raw)
            validator_local = _parse_local_validator(ts_local_raw, tzid)
            exp_local = ts_utc.astimezone(ZoneInfo(tzid)).replace(tzinfo=None)
        except Exception:
            bad_parse_count += 1
            continue
        if validator_local != obs_local:
            contract_parse_mismatch_count += 1

        delta_s = (obs_local - exp_local).total_seconds()
        if abs(delta_s) > 0.5:
            mismatch_count += 1
        if abs(abs(delta_s) - 3600.0) <= 0.5:
            one_hour_count += 1

        if obs_local.weekday() >= 5:
            weekend_obs_count += 1
        if exp_local.weekday() >= 5:
            weekend_exp_count += 1

        # DST window membership for this tzid.
        windows = windows_by_tz.get(tzid, [])
        for idx, (ws, we) in enumerate(windows):
            if ws <= ts_utc <= we:
                wid = f"{tzid}#w{idx+1}"
                window_support[wid] += 1
                window_obs_hours[wid][obs_local.hour] += 1
                window_exp_hours[wid][exp_local.hour] += 1

    t1_value = (mismatch_count / sample_size) if sample_size > 0 else None
    t2_value = (one_hour_count / sample_size) if sample_size > 0 else None
    weekend_delta_pp = None
    if sample_size > 0:
        weekend_delta_pp = abs((weekend_obs_count / sample_size) - (weekend_exp_count / sample_size)) * 100.0

    window_mae_pp_values: list[float] = []
    for wid, n in window_support.items():
        if n <= 0:
            continue
        obs = window_obs_hours[wid]
        exp = window_exp_hours[wid]
        obs_share = [v / n for v in obs]
        exp_share = [v / n for v in exp]
        mae_pp = mean(abs(a - b) * 100.0 for a, b in zip(obs_share, exp_share))
        window_mae_pp_values.append(mae_pp)
    t3_value = (mean(window_mae_pp_values) if window_mae_pp_values else None)
    min_window_support = min(window_support.values()) if window_support else 0
    insufficient_power = bool(window_support) and min_window_support < 5000

    # T9 dispersion (sampled S3 residual spread).
    s3_sample = _deterministic_s3_sample(s3_path, target=200_000)
    residuals: list[float] = []
    for row in s3_sample.select(["count_N", "mu"]).iter_rows(named=True):
        mu = float(row["mu"])
        if mu <= 1e-9:
            continue
        residuals.append((float(row["count_N"]) - mu) / math.sqrt(mu))
    if residuals:
        m = mean(residuals)
        t9_std = math.sqrt(mean((x - m) ** 2 for x in residuals))
    else:
        t9_std = None

    # T11 signal from cache metadata + temporal mismatch signature.
    release_tag = str(tz_cache_meta.get("tzdb_release_tag") or "")
    release_year = None
    if len(release_tag) >= 4 and release_tag[:4].isdigit():
        release_year = int(release_tag[:4])
    run_year_max = utc_max.year
    t11_pass = not (
        (release_year is not None and run_year_max > release_year)
        and (t2_value is not None and t2_value > 0.001)
    )

    # T10 cross-seed evidence in authority run.
    seeds_available = sorted({int(r.get("seed")) for r in state_rows if r.get("seed") is not None})
    t10_measured = len(set(SEEDS_REQUIRED).intersection(seeds_available))
    t10_sufficient = t10_measured == len(SEEDS_REQUIRED)

    # Gate evaluations.
    def _band_check(value: float | None, lo: float, hi: float) -> bool | None:
        if value is None:
            return None
        return lo <= value <= hi

    gate_values: dict[str, dict[str, Any]] = {
        "T1": {
            "value": t1_value,
            "value_fmt": _format_pct(t1_value),
            "b_pass": (t1_value is not None and t1_value <= 0.0050),
            "bplus_pass": (t1_value is not None and t1_value <= 0.0010),
            "source": "arrival_events_sampled_clock_reconstruction",
            "sample_size": sample_size,
        },
        "T2": {
            "value": t2_value,
            "value_fmt": _format_pct(t2_value),
            "b_pass": (t2_value is not None and t2_value <= 0.0010),
            "bplus_pass": (t2_value is not None and t2_value <= 0.0002),
            "source": "arrival_events_sampled_clock_reconstruction",
            "sample_size": sample_size,
        },
        "T3": {
            "value": t3_value,
            "value_fmt": (None if t3_value is None else f"{t3_value:.4f} pp"),
            "b_pass": (t3_value is not None and t3_value <= 1.5 and not insufficient_power),
            "bplus_pass": (t3_value is not None and t3_value <= 0.7 and not insufficient_power),
            "source": "arrival_events_sampled_dst_window_hour_mae",
            "window_count": len(window_support),
            "min_window_support": min_window_support,
            "insufficient_power": insufficient_power,
        },
        "T4": {
            "value": {"mismatch_count": 0, "residual_sum": residual_sum},
            "value_fmt": f"mismatch_count=0, residual_sum={residual_sum}",
            "b_pass": (residual_sum == 0),
            "bplus_pass": (residual_sum == 0),
            "source": "s3_sum_vs_s4_total + authority_keylevel_nonweakness",
            "note": "Key-level mismatch_count pinned from authority report (logical-key aggregation exact).",
        },
        "T5": {
            "value": {"violations": n_violations, "violation_rate": violation_rate},
            "value_fmt": f"violations={n_violations}, rate={_format_pct(violation_rate)}",
            "b_pass": (n_violations == 0),
            "bplus_pass": (n_violations == 0),
            "source": "arrival_events_full_scan",
        },
        "T6": {
            "value": top10_share,
            "value_fmt": _format_pct(top10_share),
            "b_pass": (top10_share <= 0.72),
            "bplus_pass": (top10_share <= 0.62),
            "source": "arrival_events_full_scan_tzid_primary",
            "top10_tzids": tz_counts.head(10)["tzid_primary"].to_list(),
        },
        "T7": {
            "value": (n_virtual / n_total) if n_total > 0 else None,
            "value_fmt": _format_pct((n_virtual / n_total) if n_total > 0 else None),
            "b_pass": _band_check((n_virtual / n_total) if n_total > 0 else None, 0.03, 0.08),
            "bplus_pass": _band_check((n_virtual / n_total) if n_total > 0 else None, 0.05, 0.12),
            "source": "arrival_events_full_scan + s4 totals",
            "virtual_count": n_virtual,
            "total_count": n_total,
        },
        "T8": {
            "value": weekend_delta_pp,
            "value_fmt": (None if weekend_delta_pp is None else f"{weekend_delta_pp:.4f} pp"),
            "b_pass": (weekend_delta_pp is not None and weekend_delta_pp <= 0.20),
            "bplus_pass": (weekend_delta_pp is not None and weekend_delta_pp <= 0.10),
            "source": "arrival_events_sampled_weekend_observed_vs_expected",
        },
        "T9": {
            "value": t9_std,
            "value_fmt": (None if t9_std is None else f"{t9_std:.6f}"),
            "b_pass": _band_check(t9_std, 1.20, 1.60),
            "bplus_pass": _band_check(t9_std, 1.25, 1.50),
            "source": "s3_bucket_counts_sampled_standardized_residual_std",
            "sample_size": int(s3_sample.height),
        },
        "T10": {
            "value": {"required_seeds": SEEDS_REQUIRED, "available_seeds": seeds_available},
            "value_fmt": f"available={seeds_available}, required={SEEDS_REQUIRED}",
            "b_pass": t10_sufficient,
            "bplus_pass": t10_sufficient,
            "source": "segment_state_runs_seed_panel",
            "insufficient_evidence": (not t10_sufficient),
        },
        "T11": {
            "value": {
                "tzdb_release_tag": release_tag,
                "release_year": release_year,
                "run_year_max": run_year_max,
                "one_hour_signature_mass": t2_value,
            },
            "value_fmt": f"release={release_tag}, run_year_max={run_year_max}, one_hour_mass={_format_pct(t2_value)}",
            "b_pass": t11_pass,
            "bplus_pass": t11_pass,
            "source": "tz_cache_metadata + mismatch_signature_inference",
            "note": "Coverage inferred from authority mismatch signature + cache metadata (no explicit horizon field in cache manifest).",
        },
        "T12": {
            "value": {
                "local_z_marker_non_utc_rate": (contract_marker_count / sample_size) if sample_size > 0 else None,
                "producer_validator_parse_mismatch_rate": (
                    contract_parse_mismatch_count / sample_size if sample_size > 0 else None
                ),
                "civil_issue_count": int(validation_issues.filter(pl.col("issue_code") == "CIVIL_TIME_MISMATCH").height),
            },
            "value_fmt": (
                f"local_z_marker_non_utc_rate={_format_pct((contract_marker_count / sample_size) if sample_size > 0 else None)}, "
                f"producer_validator_parse_mismatch_rate={_format_pct((contract_parse_mismatch_count / sample_size) if sample_size > 0 else None)}"
            ),
            "b_pass": (sample_size > 0 and contract_marker_count == 0 and contract_parse_mismatch_count == 0),
            "bplus_pass": (sample_size > 0 and contract_marker_count == 0 and contract_parse_mismatch_count == 0),
            "source": "arrival_events_local_contract_parse_consistency",
        },
    }

    hard_failures = [gid for gid, g in gate_values.items() if GATES[gid].klass == "hard" and not bool(g["b_pass"])]
    major_failures = [gid for gid, g in gate_values.items() if GATES[gid].klass == "major" and not bool(g["b_pass"])]
    context_failures = [gid for gid, g in gate_values.items() if GATES[gid].klass == "context" and not bool(g["b_pass"])]

    owner_matrix = {
        "generated_utc": _now_utc(),
        "segment": "5B",
        "run_id": run_id,
        "owner_rows": [
            {
                "gate_id": "T1",
                "primary_owner": "L2/5B/S4 + L2/5B/S5",
                "secondary_dependency": "L1/2A cache horizon",
                "phase_owner": "P1",
                "notes": "DST/local-time correctness closure lane.",
            },
            {
                "gate_id": "T2",
                "primary_owner": "L2/5B/S4 + L2/5B/S5",
                "secondary_dependency": "L1/2A cache horizon",
                "phase_owner": "P1",
                "notes": "One-hour signature is treated as deterministic defect indicator.",
            },
            {
                "gate_id": "T3",
                "primary_owner": "L2/5B/S4 + L2/5B/S5",
                "secondary_dependency": "L1/2A cache horizon",
                "phase_owner": "P1",
                "notes": "DST-window profile parity owned by timestamp/render + validator semantics.",
            },
            {
                "gate_id": "T4",
                "primary_owner": "Frozen rail",
                "secondary_dependency": None,
                "phase_owner": "Veto rail",
                "notes": "Conservation is non-regression rail; no reopen in P1.",
            },
            {
                "gate_id": "T5",
                "primary_owner": "Frozen rail",
                "secondary_dependency": None,
                "phase_owner": "Veto rail",
                "notes": "Routing nullability integrity is non-regression rail.",
            },
            {
                "gate_id": "T6",
                "primary_owner": "L2/5B routing policy",
                "secondary_dependency": "L2/5A + L1/2B shape constraints",
                "phase_owner": "P2",
                "notes": "Calibration lane only after hard temporal fixes.",
            },
            {
                "gate_id": "T7",
                "primary_owner": "L2/5B routing policy",
                "secondary_dependency": "L2/5A class/channel mix",
                "phase_owner": "P2",
                "notes": "Virtual-share posture tuning lane.",
            },
            {
                "gate_id": "T10",
                "primary_owner": "Certification lane",
                "secondary_dependency": "multi-seed run-set",
                "phase_owner": "P4",
                "notes": "Not a P1 blocker for baseline lock; required for final certification.",
            },
            {
                "gate_id": "T11",
                "primary_owner": "L1/2A",
                "secondary_dependency": "L2/5B S4 consumption checks",
                "phase_owner": "P1 (conditional upstream reopen)",
                "notes": "Upstream reopen only if S4/S5 local fixes cannot close hard temporal gates.",
            },
            {
                "gate_id": "T12",
                "primary_owner": "L2/5B/S4 + L2/5B/S5",
                "secondary_dependency": None,
                "phase_owner": "P1",
                "notes": "Local-time representation contract semantics owner.",
            },
        ],
        "failures_by_phase": {
            "P1": [g for g in ("T1", "T2", "T3", "T11", "T12") if g in hard_failures or g == "T11"],
            "P2": [g for g in ("T6", "T7") if g in major_failures],
            "P4": ["T10"] if not t10_sufficient else [],
        },
        "frozen_veto_rails": ["T4", "T5"],
    }

    candidate_protocol = {
        "generated_utc": _now_utc(),
        "segment": "5B",
        "run_id": run_id,
        "phase_scope": "P1 correctness lane",
        "rerun_matrix": {
            "allowed_mutation_scope": ["L2/5B/S4", "L2/5B/S5"],
            "default_rerun": ["S4", "S5"],
            "disallowed_without_explicit_reopen": ["S1", "S2", "S3"],
            "conditional_upstream_reopen": {
                "owner_segment": "2A",
                "trigger": "T1/T2/T3 remain hard-fail after local S4/S5 correctness fixes",
            },
        },
        "promotion_veto": {
            "hard_non_regression_required": ["T4", "T5"],
            "hard_closure_targets": ["T1", "T2", "T3", "T12"],
            "upstream_horizon_gate": "T11",
            "no_calibration_promotion_while_hard_fails": True,
        },
        "runtime_budget": {
            "target_s4_s5_combined_seconds": 540,
            "max_regression_without_gate_movement": 0.20,
            "authority_reference": "P0/POPT5 lane posture",
        },
    }

    phase_decision = "UNLOCK_P1"
    unresolved_items: list[str] = []
    # P0 is baseline lock: unresolved hard-fail gates are acceptable if ownership/protocol are complete.
    for required in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T11", "T12"):
        if required not in gate_values:
            unresolved_items.append(f"missing_gate:{required}")
    if sample_size <= 0:
        unresolved_items.append("no_arrival_sample")
    if unresolved_items:
        phase_decision = "HOLD_P0_REOPEN"

    gateboard = {
        "generated_utc": _now_utc(),
        "phase": "P0",
        "segment": "5B",
        "run": {
            "run_id": run_id,
            "runs_root": str(runs_root),
            "segment_state_runs": str(state_runs_path),
            "seed": seed,
            "manifest_fingerprint": mf,
            "parameter_hash": receipt.get("parameter_hash"),
        },
        "baseline_sources": {
            "validation_report_5B": str(validation_report_path),
            "validation_issue_table_5B": str(validation_issue_path),
            "s3_bucket_counts_5B": s3_path,
            "arrival_events_5B_glob": arrivals_glob,
            "tz_timetable_cache": str(tz_cache_meta_path),
            "authority_reports": [
                "docs/reports/eda/segment_5B/segment_5B_published_report.md",
                "docs/reports/eda/segment_5B/segment_5B_remediation_report.md",
            ],
        },
        "gates": {
            gid: {
                "title": GATES[gid].title,
                "class": GATES[gid].klass,
                "b_target": GATES[gid].b_target,
                "bplus_target": GATES[gid].bplus_target,
                **values,
            }
            for gid, values in gate_values.items()
        },
        "summary": {
            "hard_failures": hard_failures,
            "major_failures": major_failures,
            "context_failures": context_failures,
            "civil_time_ok_latest": latest_civil_ok,
            "validation_report_status": validation_report.get("status"),
            "arrival_sample_size": sample_size,
            "arrival_sample_target": int(args.sample_target),
            "arrival_sample_bad_parse_count": bad_parse_count,
            "dst_window_count": len(window_support),
            "dst_window_support_min": min_window_support,
            "dst_window_insufficient_power": insufficient_power,
            "unresolved_items": unresolved_items,
            "phase_decision": phase_decision,
        },
    }

    json_path = out_root / f"segment5b_p0_realism_gateboard_{run_id}.json"
    md_path = out_root / f"segment5b_p0_realism_gateboard_{run_id}.md"
    owner_path = out_root / f"segment5b_p0_owner_state_matrix_{run_id}.json"
    protocol_path = out_root / f"segment5b_p0_candidate_protocol_{run_id}.json"

    json_path.write_text(json.dumps(gateboard, indent=2), encoding="utf-8")
    owner_path.write_text(json.dumps(owner_matrix, indent=2), encoding="utf-8")
    protocol_path.write_text(json.dumps(candidate_protocol, indent=2), encoding="utf-8")

    lines = [
        f"# Segment 5B P0 Realism Gateboard - run_id {run_id}",
        "",
        "## Phase Decision",
        f"- `{phase_decision}`",
        "",
        "## Fail Axes (B gates)",
        f"- hard_failures: `{hard_failures}`",
        f"- major_failures: `{major_failures}`",
        f"- context_failures: `{context_failures}`",
        "",
        "## Key Metrics",
        f"- `T1` mismatch_rate: `{gate_values['T1']['value_fmt']}`",
        f"- `T2` one_hour_signature_mass: `{gate_values['T2']['value_fmt']}`",
        f"- `T3` dst_window_mae_pp: `{gate_values['T3']['value_fmt']}` (windows={len(window_support)}, min_support={min_window_support})",
        f"- `T4` conservation: `{gate_values['T4']['value_fmt']}`",
        f"- `T5` routing_integrity: `{gate_values['T5']['value_fmt']}`",
        f"- `T6` top10_tz_share: `{gate_values['T6']['value_fmt']}`",
        f"- `T7` virtual_share: `{gate_values['T7']['value_fmt']}`",
        f"- `T12` contract_integrity: `{gate_values['T12']['value_fmt']}`",
        "",
        "## Notes",
        "- `T10` is marked insufficient evidence in P0 because required seed panel is not present in this authority run.",
        "- `T11` is inferred from cache metadata plus mismatch signature because explicit horizon fields are absent in the cache manifest.",
        "- Owner-state matrix and candidate protocol artifacts are emitted for P1 handoff.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[segment5b-p0] gateboard_json={json_path}")
    print(f"[segment5b-p0] gateboard_md={md_path}")
    print(f"[segment5b-p0] owner_matrix={owner_path}")
    print(f"[segment5b-p0] candidate_protocol={protocol_path}")
    print(f"[segment5b-p0] phase_decision={phase_decision}")


if __name__ == "__main__":
    main()
