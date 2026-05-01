from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
ARRIVAL_ROOT = RUN_ROOT / "data" / "layer2" / "5B" / "arrival_events"
EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "traffic_primitives"
    / "branches"
    / "time_grid_exposure_discipline"
)


def parquet_pattern(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def write_csv(df: pd.DataFrame, filename: str) -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(EXPORT_DIR / filename, index=False)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads TO 8")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW arrivals AS
        SELECT
            *,
            CAST(substr(ts_utc, 1, 10) AS DATE) AS utc_date,
            CAST(substr(ts_utc, 12, 2) AS INTEGER) AS utc_hour,
            CAST(floor(bucket_index / 24) AS INTEGER) AS bucket_day_index,
            CAST(bucket_index % 24 AS INTEGER) AS bucket_hour_index
        FROM read_parquet('{parquet_pattern(ARRIVAL_ROOT)}', hive_partitioning=true)
        """
    )

    bucket_grid_summary = con.execute(
        """
        WITH expected AS (
            SELECT range AS bucket_index
            FROM range(2160)
        ),
        observed AS (
            SELECT DISTINCT bucket_index
            FROM arrivals
        ),
        bucket_check AS (
            SELECT e.bucket_index, o.bucket_index IS NOT NULL AS observed
            FROM expected e
            LEFT JOIN observed o USING (bucket_index)
        )
        SELECT
            (SELECT COUNT(*)::UBIGINT FROM arrivals) AS rows,
            (SELECT COUNT(DISTINCT merchant_id)::UBIGINT FROM arrivals) AS merchants,
            (SELECT MIN(bucket_index)::UBIGINT FROM arrivals) AS min_bucket_index,
            (SELECT MAX(bucket_index)::UBIGINT FROM arrivals) AS max_bucket_index,
            (SELECT COUNT(DISTINCT bucket_index)::UBIGINT FROM arrivals) AS observed_buckets,
            2160::UBIGINT AS expected_buckets,
            (SELECT COUNT(*)::UBIGINT FROM bucket_check WHERE observed = false) AS missing_buckets,
            (SELECT COUNT(*)::UBIGINT FROM arrivals WHERE bucket_hour_index <> utc_hour) AS rows_bucket_hour_mismatch,
            (SELECT COUNT(DISTINCT bucket_index)::UBIGINT FROM arrivals WHERE bucket_hour_index <> utc_hour) AS buckets_with_hour_mismatch,
            (SELECT MIN(ts_utc) FROM arrivals) AS first_ts_utc,
            (SELECT MAX(ts_utc) FROM arrivals) AS last_ts_utc
        """
    ).fetchdf()
    write_csv(bucket_grid_summary, "bucket_grid_summary.csv")

    bucket_profile = con.execute(
        """
        SELECT
            bucket_index,
            bucket_day_index,
            bucket_hour_index,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(utc_date) AS utc_date,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT channel_group)::UBIGINT AS channels,
            COUNT(DISTINCT is_virtual)::UBIGINT AS route_modes,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(*) FILTER (WHERE channel_group = 'card_present')::UBIGINT AS card_present_rows,
            COUNT(*) FILTER (WHERE channel_group = 'card_not_present')::UBIGINT AS card_not_present_rows,
            COUNT(*) FILTER (WHERE is_virtual = false)::UBIGINT AS physical_rows,
            COUNT(*) FILTER (WHERE is_virtual = true)::UBIGINT AS virtual_rows
        FROM arrivals
        GROUP BY bucket_index, bucket_day_index, bucket_hour_index
        ORDER BY bucket_index
        """
    ).fetchdf()
    write_csv(bucket_profile, "bucket_profile.csv")

    bucket_distribution_stats = con.execute(
        """
        WITH b AS (
            SELECT
                bucket_index,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT merchant_id)::DOUBLE AS merchants
            FROM arrivals
            GROUP BY bucket_index
        )
        SELECT
            COUNT(*)::UBIGINT AS buckets,
            MIN(rows)::UBIGINT AS min_rows_per_bucket,
            quantile_cont(rows, 0.05) AS p05_rows_per_bucket,
            quantile_cont(rows, 0.25) AS p25_rows_per_bucket,
            quantile_cont(rows, 0.50) AS median_rows_per_bucket,
            AVG(rows) AS mean_rows_per_bucket,
            quantile_cont(rows, 0.75) AS p75_rows_per_bucket,
            quantile_cont(rows, 0.95) AS p95_rows_per_bucket,
            MAX(rows)::UBIGINT AS max_rows_per_bucket,
            MIN(merchants)::UBIGINT AS min_merchants_per_bucket,
            quantile_cont(merchants, 0.50) AS median_merchants_per_bucket,
            AVG(merchants) AS mean_merchants_per_bucket,
            MAX(merchants)::UBIGINT AS max_merchants_per_bucket
        FROM b
        """
    ).fetchdf()
    write_csv(bucket_distribution_stats, "bucket_distribution_stats.csv")

    bucket_hour_profile = con.execute(
        """
        WITH bucket_rows AS (
            SELECT
                bucket_index,
                bucket_hour_index,
                COUNT(*)::DOUBLE AS rows,
                COUNT(*) FILTER (WHERE channel_group = 'card_present')::DOUBLE AS card_present_rows,
                COUNT(*) FILTER (WHERE channel_group = 'card_not_present')::DOUBLE AS card_not_present_rows,
                COUNT(*) FILTER (WHERE is_virtual = false)::DOUBLE AS physical_rows,
                COUNT(*) FILTER (WHERE is_virtual = true)::DOUBLE AS virtual_rows
            FROM arrivals
            GROUP BY bucket_index, bucket_hour_index
        )
        SELECT
            bucket_hour_index AS utc_hour,
            COUNT(*)::UBIGINT AS buckets,
            SUM(rows)::UBIGINT AS rows,
            AVG(rows) AS mean_rows_per_bucket,
            quantile_cont(rows, 0.50) AS median_rows_per_bucket,
            MIN(rows)::UBIGINT AS min_rows_per_bucket,
            MAX(rows)::UBIGINT AS max_rows_per_bucket,
            SUM(card_present_rows)::UBIGINT AS card_present_rows,
            SUM(card_not_present_rows)::UBIGINT AS card_not_present_rows,
            SUM(physical_rows)::UBIGINT AS physical_rows,
            SUM(virtual_rows)::UBIGINT AS virtual_rows
        FROM bucket_rows
        GROUP BY bucket_hour_index
        ORDER BY bucket_hour_index
        """
    ).fetchdf()
    write_csv(bucket_hour_profile, "bucket_hour_profile.csv")

    bucket_hour_by_channel_route = con.execute(
        """
        SELECT
            bucket_hour_index AS utc_hour,
            channel_group,
            CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY channel_group, is_virtual) AS share_within_channel_route,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants
        FROM arrivals
        GROUP BY bucket_hour_index, channel_group, is_virtual
        ORDER BY channel_group, route_mode, utc_hour
        """
    ).fetchdf()
    write_csv(bucket_hour_by_channel_route, "bucket_hour_by_channel_route.csv")

    merchant_exposure = con.execute(
        """
        WITH merchant_counts AS (
            SELECT
                merchant_id,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT bucket_index)::UBIGINT AS buckets,
                COUNT(DISTINCT utc_date)::UBIGINT AS active_dates,
                COUNT(DISTINCT channel_group)::UBIGINT AS channels,
                COUNT(DISTINCT is_virtual)::UBIGINT AS route_modes,
                COUNT(DISTINCT zone_representation)::UBIGINT AS zones
            FROM arrivals
            GROUP BY merchant_id
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (ORDER BY rows DESC, merchant_id) AS merchant_rank,
                SUM(rows) OVER () AS total_rows
            FROM merchant_counts
        )
        SELECT
            merchant_rank,
            merchant_id,
            rows::UBIGINT AS rows,
            rows / total_rows AS row_share,
            SUM(rows) OVER (ORDER BY merchant_rank) / total_rows AS cumulative_row_share,
            buckets,
            active_dates,
            channels,
            route_modes,
            zones
        FROM ranked
        ORDER BY merchant_rank
        """
    ).fetchdf()
    write_csv(merchant_exposure, "merchant_exposure_ranked.csv")

    merchant_exposure_summary = con.execute(
        """
        WITH merchant_counts AS (
            SELECT
                merchant_id,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY merchant_id
        ),
        ranked AS (
            SELECT
                merchant_id,
                rows,
                ROW_NUMBER() OVER (ORDER BY rows DESC, merchant_id) AS merchant_rank,
                SUM(rows) OVER () AS total_rows
            FROM merchant_counts
        ),
        thresholds AS (
            SELECT
                SUM(rows) FILTER (WHERE merchant_rank <= 1) / MAX(total_rows) AS top_1_share,
                SUM(rows) FILTER (WHERE merchant_rank <= 5) / MAX(total_rows) AS top_5_share,
                SUM(rows) FILTER (WHERE merchant_rank <= 10) / MAX(total_rows) AS top_10_share,
                SUM(rows) FILTER (WHERE merchant_rank <= 50) / MAX(total_rows) AS top_50_share,
                SUM(rows) FILTER (WHERE merchant_rank <= 100) / MAX(total_rows) AS top_100_share,
                SUM(rows) FILTER (WHERE merchant_rank <= 405) / MAX(total_rows) AS top_10pct_merchants_share
            FROM ranked
        )
        SELECT
            (SELECT COUNT(*)::UBIGINT FROM merchant_counts) AS merchants,
            (SELECT MIN(rows)::UBIGINT FROM merchant_counts) AS min_rows_per_merchant,
            (SELECT quantile_cont(rows, 0.05) FROM merchant_counts) AS p05_rows_per_merchant,
            (SELECT quantile_cont(rows, 0.25) FROM merchant_counts) AS p25_rows_per_merchant,
            (SELECT quantile_cont(rows, 0.50) FROM merchant_counts) AS median_rows_per_merchant,
            (SELECT AVG(rows) FROM merchant_counts) AS mean_rows_per_merchant,
            (SELECT quantile_cont(rows, 0.75) FROM merchant_counts) AS p75_rows_per_merchant,
            (SELECT quantile_cont(rows, 0.95) FROM merchant_counts) AS p95_rows_per_merchant,
            (SELECT MAX(rows)::UBIGINT FROM merchant_counts) AS max_rows_per_merchant,
            top_1_share,
            top_5_share,
            top_10_share,
            top_50_share,
            top_100_share,
            top_10pct_merchants_share
        FROM thresholds
        """
    ).fetchdf()
    write_csv(merchant_exposure_summary, "merchant_exposure_summary.csv")

    daily_merchant_presence = con.execute(
        """
        SELECT
            utc_date,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants
        FROM arrivals
        GROUP BY utc_date
        ORDER BY utc_date
        """
    ).fetchdf()
    write_csv(daily_merchant_presence, "daily_merchant_presence.csv")

    merchant_day_exception = con.execute(
        """
        WITH all_dates AS (
            SELECT DISTINCT utc_date FROM arrivals
        ),
        all_merchants AS (
            SELECT DISTINCT merchant_id FROM arrivals
        ),
        merchant_dates AS (
            SELECT DISTINCT utc_date, merchant_id FROM arrivals
        ),
        missing AS (
            SELECT d.utc_date, m.merchant_id
            FROM all_dates d
            CROSS JOIN all_merchants m
            LEFT JOIN merchant_dates md
              ON md.utc_date = d.utc_date
             AND md.merchant_id = m.merchant_id
            WHERE md.merchant_id IS NULL
        ),
        context AS (
            SELECT
                a.merchant_id,
                a.utc_date,
                COUNT(*)::UBIGINT AS rows
            FROM arrivals a
            INNER JOIN missing m USING (merchant_id)
            WHERE a.utc_date BETWEEN m.utc_date - INTERVAL 3 DAY AND m.utc_date + INTERVAL 3 DAY
            GROUP BY a.merchant_id, a.utc_date
        )
        SELECT
            m.utc_date AS missing_utc_date,
            m.merchant_id,
            c.utc_date AS context_utc_date,
            COALESCE(c.rows, 0)::UBIGINT AS rows
        FROM missing m
        LEFT JOIN context c USING (merchant_id)
        ORDER BY m.utc_date, m.merchant_id, c.utc_date
        """
    ).fetchdf()
    write_csv(merchant_day_exception, "merchant_day_exception_context.csv")

    summary = {
        "bucket_grid_summary": bucket_grid_summary.to_dict(orient="records")[0],
        "bucket_distribution_stats": bucket_distribution_stats.to_dict(orient="records")[0],
        "merchant_exposure_summary": merchant_exposure_summary.to_dict(orient="records")[0],
        "daily_merchant_presence_min": {
            "min_merchants": int(daily_merchant_presence["merchants"].min()),
            "dates_at_min": daily_merchant_presence.loc[
                daily_merchant_presence["merchants"] == daily_merchant_presence["merchants"].min(),
                "utc_date",
            ].astype(str).tolist(),
        },
        "merchant_day_exception_rows": merchant_day_exception.to_dict(orient="records"),
    }
    (EXPORT_DIR / "time_grid_exposure_discipline_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
