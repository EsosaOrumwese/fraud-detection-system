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
    / "channel_structure"
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
        SELECT *
        FROM read_parquet('{parquet_pattern(ARRIVAL_ROOT)}', hive_partitioning=true)
        """
    )

    channel_overview = con.execute(
        """
        SELECT
            channel_group,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT merchant_id) * 1.0 / SUM(COUNT(DISTINCT merchant_id)) OVER () AS merchant_share,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(DISTINCT tzid_operational)::UBIGINT AS operational_timezones
        FROM arrivals
        GROUP BY channel_group
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(channel_overview, "channel_overview.csv")

    channel_route = con.execute(
        """
        SELECT
            channel_group,
            is_virtual,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY channel_group) AS share_within_channel,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY is_virtual) AS share_within_route_mode,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
        FROM arrivals
        GROUP BY channel_group, is_virtual
        ORDER BY channel_group, is_virtual
        """
    ).fetchdf()
    write_csv(channel_route, "channel_by_route_mode.csv")

    merchant_channel_stability = con.execute(
        """
        WITH merchant_channels AS (
            SELECT
                merchant_id,
                COUNT(DISTINCT channel_group)::UBIGINT AS channel_count,
                MIN(channel_group) AS assigned_channel,
                COUNT(*)::UBIGINT AS rows
            FROM arrivals
            GROUP BY merchant_id
        )
        SELECT
            channel_count,
            COUNT(*)::UBIGINT AS merchants,
            SUM(rows)::UBIGINT AS rows
        FROM merchant_channels
        GROUP BY channel_count
        ORDER BY channel_count
        """
    ).fetchdf()
    write_csv(merchant_channel_stability, "merchant_channel_stability.csv")

    merchant_volume_by_channel = con.execute(
        """
        WITH merchant_counts AS (
            SELECT
                channel_group,
                merchant_id,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY channel_group, merchant_id
        )
        SELECT
            channel_group,
            COUNT(*)::UBIGINT AS merchants,
            SUM(rows)::UBIGINT AS rows,
            MIN(rows)::UBIGINT AS min_rows_per_merchant,
            quantile_cont(rows, 0.05) AS p05_rows_per_merchant,
            quantile_cont(rows, 0.25) AS p25_rows_per_merchant,
            AVG(rows) AS mean_rows_per_merchant,
            quantile_cont(rows, 0.50) AS median_rows_per_merchant,
            quantile_cont(rows, 0.75) AS p75_rows_per_merchant,
            quantile_cont(rows, 0.95) AS p95_rows_per_merchant,
            MAX(rows)::UBIGINT AS max_rows_per_merchant
        FROM merchant_counts
        GROUP BY channel_group
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(merchant_volume_by_channel, "merchant_volume_by_channel.csv")

    channel_daily = con.execute(
        """
        SELECT
            SUBSTR(ts_utc, 1, 10) AS utc_date,
            channel_group,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants
        FROM arrivals
        GROUP BY utc_date, channel_group
        ORDER BY utc_date, channel_group
        """
    ).fetchdf()
    write_csv(channel_daily, "channel_daily_summary.csv")

    daily_share_stats = con.execute(
        """
        WITH daily AS (
            SELECT
                SUBSTR(ts_utc, 1, 10) AS utc_date,
                channel_group,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY utc_date, channel_group
        ),
        shares AS (
            SELECT
                utc_date,
                channel_group,
                rows,
                rows / SUM(rows) OVER (PARTITION BY utc_date) AS daily_row_share
            FROM daily
        )
        SELECT
            channel_group,
            COUNT(*)::UBIGINT AS days,
            MIN(daily_row_share) AS min_daily_share,
            quantile_cont(daily_row_share, 0.25) AS p25_daily_share,
            AVG(daily_row_share) AS mean_daily_share,
            quantile_cont(daily_row_share, 0.50) AS median_daily_share,
            quantile_cont(daily_row_share, 0.75) AS p75_daily_share,
            MAX(daily_row_share) AS max_daily_share,
            STDDEV_SAMP(daily_row_share) AS stddev_daily_share
        FROM shares
        GROUP BY channel_group
        ORDER BY mean_daily_share DESC
        """
    ).fetchdf()
    write_csv(daily_share_stats, "channel_daily_share_stats.csv")

    summary = {
        "channel_overview": channel_overview.to_dict(orient="records"),
        "channel_by_route_mode": channel_route.to_dict(orient="records"),
        "merchant_channel_stability": merchant_channel_stability.to_dict(orient="records"),
        "merchant_volume_by_channel": merchant_volume_by_channel.to_dict(orient="records"),
        "channel_daily_share_stats": daily_share_stats.to_dict(orient="records"),
    }
    with (EXPORT_DIR / "channel_structure_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
