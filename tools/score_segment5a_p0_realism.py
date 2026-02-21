#!/usr/bin/env python3
"""Score Segment 5A P0 realism gates and caveat map."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

SCENARIO_START_UTC = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
SCENARIO_END_UTC = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
WEEK_ALIGNMENT_SHIFT = 72
EXACT_DST_SAMPLE_MOD = 500
NIGHT_HOURS = {0, 1, 2, 3, 4, 5}
EPS = 1e-12


@dataclass(frozen=True)
class RunRef:
    run_id: str
    run_root: Path
    seed: int | None
    manifest_fingerprint: str | None


def _scan(run_root: Path, dataset: str) -> str:
    path = (run_root / "data/layer2/5A" / dataset).as_posix()
    return f"parquet_scan('{path}/**/*.parquet', hive_partitioning=true, union_by_name=true)"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_run_ref(runs_root: Path, run_id: str) -> RunRef:
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    receipt_path = run_root / "run_receipt.json"
    seed: int | None = None
    manifest: str | None = None
    if receipt_path.exists():
        receipt = _load_json(receipt_path)
        if receipt.get("seed") is not None:
            seed = int(receipt["seed"])
        if receipt.get("manifest_fingerprint") is not None:
            manifest = str(receipt["manifest_fingerprint"])
    return RunRef(run_id=run_id, run_root=run_root, seed=seed, manifest_fingerprint=manifest)


def _canonical_channel(raw: str | None) -> str:
    if raw is None:
        return "unknown"
    token = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if token in {"cp", "card_present", "present", "cardpresent"}:
        return "cp"
    if token in {"cnp", "card_not_present", "not_present", "cardnotpresent"}:
        return "cnp"
    if token in {"mixed"}:
        return "mixed"
    return token


def _tz_meta_rows(tzids: list[str]) -> list[tuple[str, int, int]]:
    rows: list[tuple[str, int, int]] = []
    for tzid in sorted(set(tzids)):
        try:
            z = ZoneInfo(tzid)
            off_start = int(SCENARIO_START_UTC.astimezone(z).utcoffset().total_seconds() // 3600)
            off_end = int(SCENARIO_END_UTC.astimezone(z).utcoffset().total_seconds() // 3600)
            dst_shift = off_end - off_start
        except Exception:
            off_start = 0
            dst_shift = 0
        rows.append((tzid, off_start, dst_shift))
    return rows


def _parse_rfc3339_utc(value: str) -> datetime:
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unsupported RFC3339 UTC timestamp: {value}")


def _exact_dst_metrics(con: duckdb.DuckDBPyConnection, run_root: Path) -> dict[str, float | int | str] | None:
    scenario_rows = con.execute(
        f"""
        WITH scenario_bounds AS (
          SELECT scenario_id, horizon_start_utc, horizon_end_utc
          FROM {_scan(run_root, "scenario_manifest")}
        ),
        scenario_horizon AS (
          SELECT scenario_id, MAX(local_horizon_bucket_index) + 1 AS horizon_buckets
          FROM {_scan(run_root, "merchant_zone_scenario_local")}
          GROUP BY 1
        )
        SELECT
          b.scenario_id,
          b.horizon_start_utc,
          b.horizon_end_utc,
          h.horizon_buckets
        FROM scenario_bounds b
        JOIN scenario_horizon h USING (scenario_id)
        """
    ).fetchall()
    if not scenario_rows:
        return None

    grid_rows = con.execute(
        f"""
        SELECT bucket_index, local_day_of_week, local_minutes_since_midnight
        FROM {_scan(run_root, "shape_grid_definition")}
        """
    ).fetchall()
    if not grid_rows:
        return None
    grid_lookup = {(int(dow), int(minutes)): int(bucket) for bucket, dow, minutes in grid_rows}

    tzids = [str(row[0]) for row in con.execute(f"SELECT DISTINCT tzid FROM {_scan(run_root, 'merchant_zone_scenario_local')}").fetchall()]
    if not tzids:
        return None

    scenario_specs: dict[str, tuple[datetime, datetime, int]] = {}
    for scenario_id, start_text, end_text, horizon_buckets in scenario_rows:
        if horizon_buckets is None:
            continue
        horizon_buckets_int = int(horizon_buckets)
        if horizon_buckets_int <= 0:
            continue
        start_utc = _parse_rfc3339_utc(str(start_text))
        end_utc = _parse_rfc3339_utc(str(end_text))
        total_minutes = int((end_utc - start_utc).total_seconds() // 60)
        if total_minutes <= 0:
            continue
        if total_minutes % horizon_buckets_int != 0:
            return None
        bucket_minutes = total_minutes // horizon_buckets_int
        if bucket_minutes <= 0:
            continue
        scenario_specs[str(scenario_id)] = (start_utc, end_utc, bucket_minutes)
    if not scenario_specs:
        return None

    sampled_keys = con.execute(
        f"""
        SELECT scenario_id, tzid, local_horizon_bucket_index
        FROM {_scan(run_root, "merchant_zone_scenario_local")}
        WHERE MOD(HASH(merchant_id, legal_country_iso, tzid, local_horizon_bucket_index), {EXACT_DST_SAMPLE_MOD}) = 0
        GROUP BY 1,2,3
        """
    ).fetchall()
    if not sampled_keys:
        return None

    tz_meta_cache: dict[tuple[str, str], tuple[ZoneInfo | None, int]] = {}
    hm_rows: list[tuple[str, str, int, int, int]] = []
    for scenario_id, tzid_raw, horizon_idx_raw in sampled_keys:
        scenario_id_str = str(scenario_id)
        spec = scenario_specs.get(scenario_id_str)
        if spec is None:
            continue
        tzid = str(tzid_raw)
        horizon_idx = int(horizon_idx_raw)
        start_utc, end_utc, bucket_minutes = spec
        cache_key = (scenario_id_str, tzid)
        if cache_key not in tz_meta_cache:
            try:
                zone = ZoneInfo(tzid)
                off_start = int(start_utc.astimezone(zone).utcoffset().total_seconds() // 3600)
                off_end = int(end_utc.astimezone(zone).utcoffset().total_seconds() // 3600)
                dst_shift_h = off_end - off_start
            except Exception:
                zone = None
                dst_shift_h = 0
            tz_meta_cache[cache_key] = (zone, dst_shift_h)
        zone, dst_shift_h = tz_meta_cache[cache_key]
        if zone is None:
            continue
        utc_dt = start_utc + timedelta(minutes=horizon_idx * bucket_minutes)
        local_dt = utc_dt.astimezone(zone)
        local_minutes = local_dt.hour * 60 + local_dt.minute
        local_minutes = (local_minutes // bucket_minutes) * bucket_minutes
        bucket_index = grid_lookup.get((local_dt.isoweekday(), local_minutes))
        if bucket_index is None:
            continue
        hm_rows.append((scenario_id_str, tzid, horizon_idx, int(bucket_index), int(dst_shift_h)))

    if not hm_rows:
        return None

    con.execute("DROP TABLE IF EXISTS hm_exact")
    con.execute(
        """
        CREATE TEMP TABLE hm_exact(
          scenario_id VARCHAR,
          tzid VARCHAR,
          local_horizon_bucket_index BIGINT,
          bucket_index BIGINT,
          dst_shift_h INTEGER
        )
        """
    )
    con.executemany("INSERT INTO hm_exact VALUES (?, ?, ?, ?, ?)", hm_rows)

    exact_row = con.execute(
        f"""
        WITH s AS (
          SELECT
            scenario_id,
            merchant_id,
            legal_country_iso,
            tzid,
            channel_group,
            local_horizon_bucket_index,
            lambda_local_scenario,
            overlay_factor_total,
            COALESCE(channel_group, '__NULL__') AS channel_key
          FROM {_scan(run_root, "merchant_zone_scenario_local")}
          WHERE MOD(HASH(merchant_id, legal_country_iso, tzid, local_horizon_bucket_index), {EXACT_DST_SAMPLE_MOD}) = 0
        ),
        mapped AS (
          SELECT
            s.scenario_id,
            s.merchant_id,
            s.legal_country_iso,
            s.tzid,
            s.channel_key,
            hm.bucket_index,
            hm.dst_shift_h,
            s.lambda_local_scenario,
            s.overlay_factor_total
          FROM s
          JOIN hm_exact hm
            ON hm.scenario_id = s.scenario_id
           AND hm.tzid = s.tzid
           AND hm.local_horizon_bucket_index = s.local_horizon_bucket_index
        ),
        b_keys AS (
          SELECT DISTINCT
            scenario_id,
            merchant_id,
            legal_country_iso,
            tzid,
            channel_key,
            bucket_index
          FROM mapped
        ),
        b_raw AS (
          SELECT
            scenario_id,
            merchant_id,
            legal_country_iso,
            tzid,
            COALESCE(channel_group, '__NULL__') AS channel_key,
            bucket_index,
            lambda_local_base
          FROM {_scan(run_root, "merchant_zone_baseline_local")}
        ),
        b AS (
          SELECT
            r.scenario_id,
            r.merchant_id,
            r.legal_country_iso,
            r.tzid,
            r.channel_key,
            r.bucket_index,
            r.lambda_local_base
          FROM b_raw r
          JOIN b_keys
            ON b_keys.scenario_id = r.scenario_id
           AND b_keys.merchant_id = r.merchant_id
           AND b_keys.legal_country_iso = r.legal_country_iso
           AND b_keys.tzid = r.tzid
           AND b_keys.bucket_index = r.bucket_index
           AND b_keys.channel_key = r.channel_key
        ),
        j AS (
          SELECT
            m.dst_shift_h,
            ABS(m.lambda_local_scenario - b.lambda_local_base * m.overlay_factor_total) AS err
          FROM mapped m
          JOIN b
            ON b.scenario_id = m.scenario_id
           AND b.merchant_id = m.merchant_id
           AND b.legal_country_iso = m.legal_country_iso
           AND b.tzid = m.tzid
           AND b.bucket_index = m.bucket_index
           AND b.channel_key = m.channel_key
        )
        SELECT
          COUNT(*) AS sampled_rows,
          AVG(CASE WHEN err > 1e-6 THEN 1.0 ELSE 0.0 END) AS overall_mismatch_rate,
          AVG(CASE WHEN dst_shift_h <> 0 THEN CASE WHEN err > 1e-6 THEN 1.0 ELSE 0.0 END END) AS dst_zone_mismatch_rate
        FROM j
        """
    ).fetchone()

    sampled_rows = int(exact_row[0] or 0)
    if sampled_rows <= 0:
        return None
    return {
        "surface": "exact_horizon_grid_mapping_v2",
        "sampled_rows": sampled_rows,
        "overall_mismatch_rate": float(exact_row[1] or 0.0),
        "dst_zone_mismatch_rate": float(exact_row[2] or 0.0),
    }


def _state_statuses(run_root: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for state in ("S0", "S1", "S2", "S3", "S4", "S5"):
        if state == "S0":
            report_paths = sorted((run_root / "data/layer2/5A/s0_gate_receipt").rglob("s0_gate_receipt_5A.json"))
            if report_paths:
                payload = _load_json(report_paths[-1])
                statuses[state] = str(payload.get("status", "UNKNOWN"))
                continue
        state_reports = sorted((run_root / "reports/layer2/5A" / f"state={state}").rglob("run_report.json"))
        if not state_reports:
            statuses[state] = "MISSING"
            continue
        payload = _load_json(state_reports[-1])
        statuses[state] = str(payload.get("status", "UNKNOWN"))
    return statuses


def _cv(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if len(clean) < 2:
        return None
    mu = mean(clean)
    if abs(mu) <= EPS:
        return 0.0
    return float(pstdev(clean) / abs(mu))


def _gate_pass_lte(value: float | None, threshold: float) -> bool:
    return value is not None and math.isfinite(value) and float(value) <= threshold


def _gate_pass_gte(value: float | None, threshold: float) -> bool:
    return value is not None and math.isfinite(value) and float(value) >= threshold


def _severity_for_axis(hard_flags: list[bool], stretch_flags: list[bool]) -> str:
    hard_ok = all(hard_flags) if hard_flags else False
    stretch_ok = all(stretch_flags) if stretch_flags else False
    if hard_ok and stretch_ok:
        return "clear"
    if hard_ok and not stretch_ok:
        return "watch"
    return "material"


def _evaluate_run(ref: RunRef) -> dict[str, Any]:
    con = duckdb.connect()
    con.execute("PRAGMA threads=8")
    run_root = ref.run_root

    # Mass conservation between local and UTC scenario totals by key.
    mass_row = con.execute(
        f"""
        WITH local_tot AS (
          SELECT
            merchant_id, legal_country_iso, tzid, channel_group, scenario_id,
            SUM(lambda_local_scenario) AS local_total
          FROM {_scan(run_root, "merchant_zone_scenario_local")}
          GROUP BY 1,2,3,4,5
        ),
        utc_tot AS (
          SELECT
            merchant_id, legal_country_iso, tzid, channel_group, scenario_id,
            SUM(lambda_utc_scenario) AS utc_total
          FROM {_scan(run_root, "merchant_zone_scenario_utc")}
          GROUP BY 1,2,3,4,5
        ),
        j AS (
          SELECT
            COALESCE(l.local_total, 0.0) AS local_total,
            COALESCE(u.utc_total, 0.0) AS utc_total
          FROM local_tot l
          FULL OUTER JOIN utc_tot u
            USING (merchant_id, legal_country_iso, tzid, channel_group, scenario_id)
        )
        SELECT
          AVG(ABS(local_total - utc_total)) AS mae,
          MAX(ABS(local_total - utc_total)) AS max_abs,
          SUM(local_total) AS local_mass,
          SUM(utc_total) AS utc_mass
        FROM j
        """
    ).fetchone()
    mass_conservation_mae = float(mass_row[0] or 0.0)
    mass_conservation_max_abs = float(mass_row[1] or 0.0)
    local_mass = float(mass_row[2] or 0.0)
    utc_mass = float(mass_row[3] or 0.0)

    # Shape normalization.
    shape_row = con.execute(
        f"""
        WITH sums AS (
          SELECT
            scenario_id, demand_class, legal_country_iso, tzid, channel_group,
            SUM(shape_value) AS shape_sum
          FROM {_scan(run_root, "class_zone_shape")}
          GROUP BY 1,2,3,4,5
        )
        SELECT
          MAX(ABS(shape_sum - 1.0)) AS max_abs_err,
          AVG(ABS(shape_sum - 1.0)) AS mae_err
        FROM sums
        """
    ).fetchone()
    shape_norm_max_abs = float(shape_row[0] or 0.0)
    shape_norm_mae = float(shape_row[1] or 0.0)

    # Channel mass realization and night-share separation.
    channel_df = con.execute(
        f"""
        SELECT channel_group, SUM(lambda_local_base_class) AS mass
        FROM {_scan(run_root, "class_zone_baseline_local")}
        GROUP BY 1
        """
    ).fetchall()
    channel_mass_raw: dict[str, float] = {str(r[0]): float(r[1] or 0.0) for r in channel_df}
    channel_mass: dict[str, float] = {}
    for k, v in channel_mass_raw.items():
        ck = _canonical_channel(k)
        channel_mass[ck] = channel_mass.get(ck, 0.0) + v
    total_channel_mass = sum(channel_mass.values())
    channel_share = {
        k: (v / total_channel_mass if total_channel_mass > 0 else 0.0) for k, v in sorted(channel_mass.items())
    }
    realized_channel_groups_ge10 = sum(1 for v in channel_share.values() if v >= 0.10)

    night_rows = con.execute(
        f"""
        SELECT channel_group, MOD(bucket_index, 24) AS hour_local, SUM(lambda_local_base_class) AS mass
        FROM {_scan(run_root, "class_zone_baseline_local")}
        GROUP BY 1,2
        """
    ).fetchall()
    chan_totals: dict[str, float] = {}
    chan_night: dict[str, float] = {}
    for raw_channel, hour_local, mass in night_rows:
        c = _canonical_channel(str(raw_channel))
        m = float(mass or 0.0)
        chan_totals[c] = chan_totals.get(c, 0.0) + m
        if int(hour_local) in NIGHT_HOURS:
            chan_night[c] = chan_night.get(c, 0.0) + m
    cp_night_share = None
    cnp_night_share = None
    if chan_totals.get("cp", 0.0) > 0:
        cp_night_share = chan_night.get("cp", 0.0) / chan_totals["cp"]
    if chan_totals.get("cnp", 0.0) > 0:
        cnp_night_share = chan_night.get("cnp", 0.0) / chan_totals["cnp"]
    channel_night_gap = None
    if cp_night_share is not None and cnp_night_share is not None:
        channel_night_gap = float(cnp_night_share - cp_night_share)

    # Concentration metrics.
    class_row = con.execute(
        f"""
        WITH class_vol AS (
          SELECT primary_demand_class AS demand_class, SUM(weekly_volume_total_expected) AS vol
          FROM {_scan(run_root, "merchant_class_profile")}
          GROUP BY 1
        ),
        totals AS (
          SELECT SUM(vol) AS total_vol FROM class_vol
        )
        SELECT
          MAX(CASE WHEN t.total_vol > 0 THEN c.vol / t.total_vol ELSE 0 END) AS max_class_share
        FROM class_vol c CROSS JOIN totals t
        """
    ).fetchone()
    max_class_share = float(class_row[0] or 0.0)

    country_row = con.execute(
        f"""
        WITH class_country AS (
          SELECT demand_class, legal_country_iso, SUM(weekly_volume_expected) AS vol
          FROM {_scan(run_root, "merchant_zone_profile")}
          GROUP BY 1,2
        ),
        class_tot AS (
          SELECT demand_class, SUM(vol) AS class_total
          FROM class_country
          GROUP BY 1
        )
        SELECT
          MAX(CASE WHEN ct.class_total > 0 THEN cc.vol / ct.class_total ELSE 0 END) AS max_country_share
        FROM class_country cc
        JOIN class_tot ct USING (demand_class)
        """
    ).fetchone()
    max_country_share_within_class = float(country_row[0] or 0.0)

    # Tail-zone realism metrics (S3-causal surface).
    tail_row = con.execute(
        f"""
        WITH tail_keys AS (
          SELECT merchant_id, legal_country_iso, tzid, channel_group
          FROM {_scan(run_root, "merchant_zone_profile")}
          WHERE demand_subclass = 'tail_zone'
        ),
        tail_weekly AS (
          SELECT
            b.merchant_id,
            b.legal_country_iso,
            b.tzid,
            b.channel_group,
            SUM(b.lambda_local_base) AS weekly_lambda
          FROM {_scan(run_root, "merchant_zone_baseline_local")} b
          INNER JOIN tail_keys t
            USING (merchant_id, legal_country_iso, tzid, channel_group)
          GROUP BY 1,2,3,4
        ),
        tz_all AS (
          SELECT tzid, SUM(lambda_local_base) AS weekly_total
          FROM {_scan(run_root, "merchant_zone_baseline_local")}
          GROUP BY 1
        )
        SELECT
          (SELECT AVG(CASE WHEN weekly_lambda <= 0 THEN 1.0 ELSE 0.0 END) FROM tail_weekly) AS tail_zero_rate,
          (SELECT SUM(CASE WHEN weekly_total > 1.0 THEN 1 ELSE 0 END) FROM tz_all) AS nontrivial_tzids
        """
    ).fetchone()
    tail_zero_rate = float(tail_row[0] or 0.0)
    nontrivial_tzids = int(tail_row[1] or 0)

    # DST mismatch metrics.
    # Keep legacy surface for audit continuity, but use exact horizon->grid mapping
    # for gating when available.
    tzids = [str(r[0]) for r in con.execute(f"SELECT DISTINCT tzid FROM {_scan(run_root, 'merchant_zone_scenario_local')}").fetchall()]
    tz_meta_rows = _tz_meta_rows(tzids)
    con.execute("CREATE OR REPLACE TEMP TABLE tz_meta(tzid VARCHAR, offset_start_h INTEGER, dst_shift_h INTEGER)")
    con.executemany("INSERT INTO tz_meta VALUES (?, ?, ?)", tz_meta_rows)

    dst_row_legacy = con.execute(
        f"""
        WITH b AS (
          SELECT
            merchant_id, legal_country_iso, tzid, channel_group, bucket_index,
            SUM(lambda_local_base) AS lb
          FROM {_scan(run_root, "merchant_zone_baseline_local")}
          GROUP BY 1,2,3,4,5
        ),
        s AS (
          SELECT
            merchant_id, legal_country_iso, tzid, channel_group, local_horizon_bucket_index,
            lambda_local_scenario AS ls,
            overlay_factor_total AS ov
          FROM {_scan(run_root, "merchant_zone_scenario_local")}
          WHERE MOD(HASH(merchant_id, legal_country_iso, tzid, local_horizon_bucket_index), 80) = 0
        ),
        j AS (
          SELECT
            t.dst_shift_h,
            ABS(s.ls - b.lb * s.ov) AS err
          FROM s
          JOIN tz_meta t USING (tzid)
          JOIN b
            ON b.merchant_id = s.merchant_id
           AND b.legal_country_iso = s.legal_country_iso
           AND b.tzid = s.tzid
           AND b.channel_group = s.channel_group
           AND b.bucket_index = MOD(s.local_horizon_bucket_index + t.offset_start_h + {WEEK_ALIGNMENT_SHIFT} + 168000, 168)
        )
        SELECT
          COUNT(*) AS sampled_rows,
          AVG(CASE WHEN err > 1e-6 THEN 1.0 ELSE 0.0 END) AS overall_mismatch_rate,
          AVG(CASE WHEN dst_shift_h <> 0 THEN CASE WHEN err > 1e-6 THEN 1.0 ELSE 0.0 END END) AS dst_zone_mismatch_rate
        FROM j
        """
    ).fetchone()
    dst_sampled_rows_legacy = int(dst_row_legacy[0] or 0)
    overall_mismatch_rate_legacy = float(dst_row_legacy[1] or 0.0)
    dst_zone_mismatch_rate_legacy = float(dst_row_legacy[2] or 0.0)

    exact_dst = _exact_dst_metrics(con, run_root)
    if exact_dst is None:
        dst_metric_surface = "legacy_fixed_offset_start_h_v1"
        dst_sampled_rows = dst_sampled_rows_legacy
        overall_mismatch_rate = overall_mismatch_rate_legacy
        dst_zone_mismatch_rate = dst_zone_mismatch_rate_legacy
    else:
        dst_metric_surface = str(exact_dst["surface"])
        dst_sampled_rows = int(exact_dst["sampled_rows"])
        overall_mismatch_rate = float(exact_dst["overall_mismatch_rate"])
        dst_zone_mismatch_rate = float(exact_dst["dst_zone_mismatch_rate"])

    # Overlay country fairness.
    overlay_row = con.execute(
        f"""
        WITH by_country AS (
          SELECT
            legal_country_iso,
            SUM(lambda_local_scenario) AS total_vol,
            SUM(CASE WHEN ABS(overlay_factor_total - 1.0) > 1e-9 THEN lambda_local_scenario ELSE 0.0 END) AS affected_vol
          FROM {_scan(run_root, "merchant_zone_scenario_local")}
          GROUP BY 1
        ),
        shares AS (
          SELECT
            legal_country_iso,
            total_vol,
            CASE WHEN total_vol > 0 THEN affected_vol / total_vol ELSE 0.0 END AS affected_share
          FROM by_country
          WHERE total_vol > 0
        ),
        top AS (
          SELECT *
          FROM shares
          ORDER BY total_vol DESC, legal_country_iso
          LIMIT 10
        ),
        agg_all AS (
          SELECT
            quantile_cont(affected_share, 0.10) AS p10,
            quantile_cont(affected_share, 0.90) AS p90
          FROM shares
        ),
        agg_top AS (
          SELECT
            SUM(CASE WHEN affected_share <= 1e-12 THEN 1 ELSE 0 END) AS top_zero_count,
            COUNT(*) AS top_n
          FROM top
        )
        SELECT
          agg_all.p10,
          agg_all.p90,
          agg_top.top_zero_count,
          agg_top.top_n
        FROM agg_all CROSS JOIN agg_top
        """
    ).fetchone()
    affected_p10 = float(overlay_row[0] or 0.0)
    affected_p90 = float(overlay_row[1] or 0.0)
    top_zero_count = int(overlay_row[2] or 0)
    top_n = int(overlay_row[3] or 0)
    overlay_p90_p10_ratio = float("inf") if affected_p10 <= EPS else float(affected_p90 / affected_p10)
    no_zero_affected_share_top = top_zero_count == 0

    con.close()

    hard = {
        "mass_conservation_mae_lte_1e-9": _gate_pass_lte(mass_conservation_mae, 1e-9),
        "shape_norm_max_abs_lte_1e-9": _gate_pass_lte(shape_norm_max_abs, 1e-9),
        "channel_realization_ge2_groups_ge10pct": realized_channel_groups_ge10 >= 2,
        "channel_night_gap_cnp_minus_cp_gte_0.08": _gate_pass_gte(channel_night_gap, 0.08),
        "max_class_share_lte_0.55": _gate_pass_lte(max_class_share, 0.55),
        "max_country_share_within_class_lte_0.40": _gate_pass_lte(max_country_share_within_class, 0.40),
        "tail_zero_rate_lte_0.90": _gate_pass_lte(tail_zero_rate, 0.90),
        "nontrivial_tzids_gte_190": _gate_pass_gte(float(nontrivial_tzids), 190.0),
        "overall_mismatch_rate_lte_0.002": _gate_pass_lte(overall_mismatch_rate, 0.002),
        "dst_zone_mismatch_rate_lte_0.005": _gate_pass_lte(dst_zone_mismatch_rate, 0.005),
        "overlay_top_countries_no_zero_affected_share": bool(no_zero_affected_share_top),
        "overlay_p90_p10_ratio_lte_2.0": _gate_pass_lte(overlay_p90_p10_ratio, 2.0),
    }

    stretch = {
        "channel_realization_all_intended_groups": set(channel_share.keys()) >= {"cp", "cnp"},
        "channel_night_gap_cnp_minus_cp_gte_0.12": _gate_pass_gte(channel_night_gap, 0.12),
        "max_class_share_lte_0.50": _gate_pass_lte(max_class_share, 0.50),
        "max_country_share_within_class_lte_0.35": _gate_pass_lte(max_country_share_within_class, 0.35),
        "tail_zero_rate_lte_0.80": _gate_pass_lte(tail_zero_rate, 0.80),
        "nontrivial_tzids_gte_230": _gate_pass_gte(float(nontrivial_tzids), 230.0),
        "overall_mismatch_rate_lte_0.0005": _gate_pass_lte(overall_mismatch_rate, 0.0005),
        "dst_zone_mismatch_rate_lte_0.002": _gate_pass_lte(dst_zone_mismatch_rate, 0.002),
        "overlay_p90_p10_ratio_lte_1.6": _gate_pass_lte(overlay_p90_p10_ratio, 1.6),
    }

    if all(hard.values()) and all(stretch.values()):
        posture = "PASS_BPLUS_ROBUST"
    elif all(hard.values()):
        posture = "PASS_B"
    else:
        posture = "HOLD_REMEDIATE"

    axis = {
        "channel": {
            "severity": _severity_for_axis(
                [hard["channel_realization_ge2_groups_ge10pct"], hard["channel_night_gap_cnp_minus_cp_gte_0.08"]],
                [stretch["channel_realization_all_intended_groups"], stretch["channel_night_gap_cnp_minus_cp_gte_0.12"]],
            )
        },
        "concentration": {
            "severity": _severity_for_axis(
                [hard["max_class_share_lte_0.55"], hard["max_country_share_within_class_lte_0.40"]],
                [stretch["max_class_share_lte_0.50"], stretch["max_country_share_within_class_lte_0.35"]],
            )
        },
        "tail": {
            "severity": _severity_for_axis(
                [hard["tail_zero_rate_lte_0.90"], hard["nontrivial_tzids_gte_190"]],
                [stretch["tail_zero_rate_lte_0.80"], stretch["nontrivial_tzids_gte_230"]],
            )
        },
        "dst": {
            "severity": _severity_for_axis(
                [hard["overall_mismatch_rate_lte_0.002"], hard["dst_zone_mismatch_rate_lte_0.005"]],
                [stretch["overall_mismatch_rate_lte_0.0005"], stretch["dst_zone_mismatch_rate_lte_0.002"]],
            )
        },
        "overlay": {
            "severity": _severity_for_axis(
                [hard["overlay_top_countries_no_zero_affected_share"], hard["overlay_p90_p10_ratio_lte_2.0"]],
                [stretch["overlay_p90_p10_ratio_lte_1.6"]],
            )
        },
    }

    return {
        "run_id": ref.run_id,
        "seed": ref.seed,
        "manifest_fingerprint": ref.manifest_fingerprint,
        "run_root": str(ref.run_root).replace("\\", "/"),
        "state_status": _state_statuses(ref.run_root),
        "metrics": {
            "mass_conservation_mae": mass_conservation_mae,
            "mass_conservation_max_abs": mass_conservation_max_abs,
            "local_mass_total": local_mass,
            "utc_mass_total": utc_mass,
            "shape_norm_max_abs": shape_norm_max_abs,
            "shape_norm_mae": shape_norm_mae,
            "channel_share": channel_share,
            "realized_channel_groups_ge10_count": realized_channel_groups_ge10,
            "cp_night_share": cp_night_share,
            "cnp_night_share": cnp_night_share,
            "channel_night_gap_cnp_minus_cp": channel_night_gap,
            "max_class_share": max_class_share,
            "max_country_share_within_class": max_country_share_within_class,
            "tail_zero_rate": tail_zero_rate,
            "nontrivial_tzids": nontrivial_tzids,
            "tail_metric_surface": "merchant_zone_baseline_local_5A",
            "dst_metric_surface": dst_metric_surface,
            "dst_sampled_rows": dst_sampled_rows,
            "overall_mismatch_rate": overall_mismatch_rate,
            "dst_zone_mismatch_rate": dst_zone_mismatch_rate,
            "dst_sampled_rows_legacy": dst_sampled_rows_legacy,
            "overall_mismatch_rate_legacy": overall_mismatch_rate_legacy,
            "dst_zone_mismatch_rate_legacy": dst_zone_mismatch_rate_legacy,
            "overlay_country_affected_share_p10": affected_p10,
            "overlay_country_affected_share_p90": affected_p90,
            "overlay_country_affected_share_p90_p10_ratio": overlay_p90_p10_ratio,
            "overlay_top_countries_n": top_n,
            "overlay_top_countries_zero_affected_count": top_zero_count,
        },
        "gates": {
            "hard": hard,
            "stretch": stretch,
            "posture": posture,
        },
        "caveat_axes": axis,
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    phase = str(payload.get("phase", "P0"))
    lines: list[str] = [
        f"# Segment 5A {phase} Realism Gateboard",
        "",
        f"- phase decision: `{payload['decision']['result']}`",
        f"- reason: {payload['decision']['reason']}",
        "",
        "## Runs",
        "",
        "| run_id | seed | posture | hard_pass_count | stretch_pass_count |",
        "|---|---:|---|---:|---:|",
    ]
    for run in payload["runs"]:
        hard = run["gates"]["hard"]
        stretch = run["gates"]["stretch"]
        lines.append(
            f"| `{run['run_id']}` | `{run.get('seed')}` | `{run['gates']['posture']}` | "
            f"{sum(1 for v in hard.values() if v)}/{len(hard)} | {sum(1 for v in stretch.values() if v)}/{len(stretch)} |"
        )

    lines.extend(
        [
            "",
            "## Caveat Axes",
            "",
            "| axis | severity |",
            "|---|---|",
        ]
    )
    for axis, data in payload["caveat_map"].items():
        lines.append(f"| `{axis}` | `{data['severity']}` |")

    lines.extend(
        [
            "",
            "## Cross-Seed Stability (available metrics)",
            "",
            "| metric | cv |",
            "|---|---:|",
        ]
    )
    for metric, cv in payload["cross_seed_cv"].items():
        cv_text = "n/a" if cv is None else f"{cv:.6f}"
        lines.append(f"| `{metric}` | {cv_text} |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 5A realism gates")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_5A")
    parser.add_argument("--run-id", action="append", required=True, help="Repeat for each run-id to include (e.g. seed 42, 101)")
    parser.add_argument(
        "--phase",
        default="P0",
        choices=["P0", "P1", "P2", "P3", "P4"],
        help="Scoring phase semantics to apply (default: P0).",
    )
    parser.add_argument(
        "--required-seeds",
        default="",
        help=(
            "Comma-separated required seed set for phase closure. "
            "Defaults: P0=42,101; P1=42; P2=42; P3=42; P4=42."
        ),
    )
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    run_ids = [str(r).strip() for r in args.run_id if str(r).strip()]
    refs = [_resolve_run_ref(runs_root, rid) for rid in run_ids]
    phase = str(args.phase).upper()
    if args.required_seeds.strip():
        required_seeds = {int(token.strip()) for token in args.required_seeds.split(",") if token.strip()}
    elif phase == "P1":
        required_seeds = {42}
    elif phase == "P2":
        required_seeds = {42}
    elif phase == "P3":
        required_seeds = {42}
    elif phase == "P4":
        required_seeds = {42}
    else:
        required_seeds = {42, 101}

    run_payloads = [_evaluate_run(ref) for ref in refs]

    caveat_map: dict[str, dict[str, Any]] = {}
    for axis in ("channel", "concentration", "tail", "dst", "overlay"):
        severities = [r["caveat_axes"][axis]["severity"] for r in run_payloads]
        if "material" in severities:
            sev = "material"
        elif "watch" in severities:
            sev = "watch"
        else:
            sev = "clear"
        caveat_map[axis] = {"severity": sev, "per_run": severities}

    cross_seed_cv = {
        "max_class_share": _cv([r["metrics"]["max_class_share"] for r in run_payloads]),
        "max_country_share_within_class": _cv([r["metrics"]["max_country_share_within_class"] for r in run_payloads]),
        "tail_zero_rate": _cv([r["metrics"]["tail_zero_rate"] for r in run_payloads]),
        "nontrivial_tzids": _cv([float(r["metrics"]["nontrivial_tzids"]) for r in run_payloads]),
        "dst_zone_mismatch_rate": _cv([r["metrics"]["dst_zone_mismatch_rate"] for r in run_payloads]),
        "overlay_p90_p10_ratio": _cv([r["metrics"]["overlay_country_affected_share_p90_p10_ratio"] for r in run_payloads]),
    }

    baseline_locked = all((runs_root / r["run_id"]).exists() for r in run_payloads)
    scorer_complete = True
    caveat_complete = True
    observed_seeds = sorted({int(r["seed"]) for r in run_payloads if r.get("seed") is not None})
    missing_required_seeds = sorted(required_seeds - set(observed_seeds))
    if phase == "P1":
        p1_run_gate_status: dict[str, bool] = {}
        for run in run_payloads:
            hard = run["gates"]["hard"]
            p1_run_gate_status[run["run_id"]] = bool(
                hard["mass_conservation_mae_lte_1e-9"]
                and hard["shape_norm_max_abs_lte_1e-9"]
                and hard["channel_realization_ge2_groups_ge10pct"]
                and hard["channel_night_gap_cnp_minus_cp_gte_0.08"]
            )
        failing_runs = sorted([run_id for run_id, ok in p1_run_gate_status.items() if not ok])
        if baseline_locked and scorer_complete and caveat_complete and not missing_required_seeds and not failing_runs:
            decision = {
                "result": "UNLOCK_P2",
                "reason": "P1 channel realism gate met on required seeds with mass/shape rails intact.",
            }
        else:
            reason = "P1 evidence package incomplete; hold until required-seed gateboard is complete."
            if missing_required_seeds:
                reason = (
                    "Required seed set is incomplete for P1 closure; missing seeds="
                    + ",".join(str(s) for s in missing_required_seeds)
                )
            elif failing_runs:
                reason = "P1 channel realism hard gate failed for run_ids=" + ",".join(failing_runs)
            decision = {
                "result": "HOLD_P1_REOPEN",
                "reason": reason,
            }
    elif phase == "P2":
        p2_run_gate_status: dict[str, bool] = {}
        for run in run_payloads:
            hard = run["gates"]["hard"]
            p2_run_gate_status[run["run_id"]] = bool(
                hard["mass_conservation_mae_lte_1e-9"]
                and hard["shape_norm_max_abs_lte_1e-9"]
                and hard["channel_realization_ge2_groups_ge10pct"]
                and hard["channel_night_gap_cnp_minus_cp_gte_0.08"]
                and hard["max_class_share_lte_0.55"]
                and hard["max_country_share_within_class_lte_0.40"]
            )
        failing_runs = sorted([run_id for run_id, ok in p2_run_gate_status.items() if not ok])
        if baseline_locked and scorer_complete and caveat_complete and not missing_required_seeds and not failing_runs:
            decision = {
                "result": "UNLOCK_P3",
                "reason": "P2 concentration gates met on required seeds with P1 protection rails intact.",
            }
        else:
            reason = "P2 evidence package incomplete; hold until required-seed gateboard is complete."
            if missing_required_seeds:
                reason = (
                    "Required seed set is incomplete for P2 closure; missing seeds="
                    + ",".join(str(s) for s in missing_required_seeds)
                )
            elif failing_runs:
                reason = "P2 concentration/protection hard gate failed for run_ids=" + ",".join(failing_runs)
            decision = {
                "result": "HOLD_P2_REOPEN",
                "reason": reason,
            }
    elif phase == "P3":
        p3_run_gate_status: dict[str, bool] = {}
        for run in run_payloads:
            hard = run["gates"]["hard"]
            p3_run_gate_status[run["run_id"]] = bool(
                hard["mass_conservation_mae_lte_1e-9"]
                and hard["shape_norm_max_abs_lte_1e-9"]
                and hard["channel_realization_ge2_groups_ge10pct"]
                and hard["channel_night_gap_cnp_minus_cp_gte_0.08"]
                and hard["max_class_share_lte_0.55"]
                and hard["max_country_share_within_class_lte_0.40"]
                and hard["tail_zero_rate_lte_0.90"]
                and hard["nontrivial_tzids_gte_190"]
            )
        failing_runs = sorted([run_id for run_id, ok in p3_run_gate_status.items() if not ok])
        if baseline_locked and scorer_complete and caveat_complete and not missing_required_seeds and not failing_runs:
            decision = {
                "result": "UNLOCK_P4",
                "reason": "P3 tail gates met on required seeds with P1/P2 frozen rails intact.",
            }
        else:
            reason = "P3 evidence package incomplete; hold until required-seed gateboard is complete."
            if missing_required_seeds:
                reason = (
                    "Required seed set is incomplete for P3 closure; missing seeds="
                    + ",".join(str(s) for s in missing_required_seeds)
                )
            elif failing_runs:
                reason = "P3 tail/frozen-rail hard gate failed for run_ids=" + ",".join(failing_runs)
            decision = {
                "result": "HOLD_P3_REOPEN",
                "reason": reason,
            }
    elif phase == "P4":
        p4_run_gate_status: dict[str, bool] = {}
        for run in run_payloads:
            hard = run["gates"]["hard"]
            p4_run_gate_status[run["run_id"]] = bool(
                hard["mass_conservation_mae_lte_1e-9"]
                and hard["shape_norm_max_abs_lte_1e-9"]
                and hard["channel_realization_ge2_groups_ge10pct"]
                and hard["channel_night_gap_cnp_minus_cp_gte_0.08"]
                and hard["max_class_share_lte_0.55"]
                and hard["max_country_share_within_class_lte_0.40"]
                and hard["tail_zero_rate_lte_0.90"]
                and hard["nontrivial_tzids_gte_190"]
                and hard["overall_mismatch_rate_lte_0.002"]
                and hard["dst_zone_mismatch_rate_lte_0.005"]
                and hard["overlay_top_countries_no_zero_affected_share"]
                and hard["overlay_p90_p10_ratio_lte_2.0"]
            )
        failing_runs = sorted([run_id for run_id, ok in p4_run_gate_status.items() if not ok])
        if baseline_locked and scorer_complete and caveat_complete and not missing_required_seeds and not failing_runs:
            decision = {
                "result": "UNLOCK_P5",
                "reason": "P4 DST/overlay hard gates met on required seeds with P1-P3 frozen rails intact.",
            }
        else:
            reason = "P4 evidence package incomplete; hold until required-seed gateboard is complete."
            if missing_required_seeds:
                reason = (
                    "Required seed set is incomplete for P4 closure; missing seeds="
                    + ",".join(str(s) for s in missing_required_seeds)
                )
            elif failing_runs:
                reason = "P4 DST/overlay/frozen-rail hard gate failed for run_ids=" + ",".join(failing_runs)
            decision = {
                "result": "HOLD_P4_REOPEN",
                "reason": reason,
            }
    else:
        if baseline_locked and scorer_complete and caveat_complete and not missing_required_seeds:
            decision = {
                "result": "UNLOCK_P1",
                "reason": "P0 baseline authority captured with gateboard + caveat map for seeded run pack.",
            }
        else:
            reason = "P0 evidence package incomplete; hold until baseline/gateboard/caveat map is complete."
            if missing_required_seeds:
                reason = (
                    "Required witness seed set is incomplete for P0 closure; missing seeds="
                    + ",".join(str(s) for s in missing_required_seeds)
                )
            decision = {
                "result": "HOLD_P0_REMEDIATE",
                "reason": reason,
            }

    payload: dict[str, Any] = {
        "phase": phase,
        "segment": "5A",
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "runs_root": str(runs_root).replace("\\", "/"),
        "run_ids": run_ids,
        "required_seeds": sorted(required_seeds),
        "observed_seeds": observed_seeds,
        "missing_required_seeds": missing_required_seeds,
        "runs": run_payloads,
        "caveat_map": caveat_map,
        "cross_seed_cv": cross_seed_cv,
        "decision": decision,
    }

    base_name = "__".join(run_ids)
    out_json = (
        Path(args.out_json)
        if args.out_json
        else runs_root / "reports" / f"segment5a_{phase.lower()}_realism_gateboard_{base_name}.json"
    )
    out_md = (
        Path(args.out_md)
        if args.out_md
        else runs_root / "reports" / f"segment5a_{phase.lower()}_realism_gateboard_{base_name}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(out_md, payload)
    print(str(out_json))
    print(str(out_md))


if __name__ == "__main__":
    main()
