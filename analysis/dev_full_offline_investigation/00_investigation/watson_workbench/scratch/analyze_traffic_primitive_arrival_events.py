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
)


def parquet_pattern(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def write_csv(df: pd.DataFrame, filename: str) -> None:
    df.to_csv(EXPORT_DIR / filename, index=False)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    pattern = parquet_pattern(ARRIVAL_ROOT)
    con = duckdb.connect()
    con.execute("SET threads TO 8")
    con.execute(f"CREATE OR REPLACE VIEW arrivals AS SELECT * FROM read_parquet('{pattern}', hive_partitioning=true)")

    parquet_files = list(ARRIVAL_ROOT.rglob("*.parquet"))
    schema_df = con.execute("DESCRIBE SELECT * FROM arrivals LIMIT 0").fetchdf()
    write_csv(schema_df, "arrival_events_schema.csv")

    identity_df = con.execute(
        """
        SELECT
            seed,
            manifest_fingerprint,
            parameter_hash,
            scenario_id,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(DISTINCT channel_group)::UBIGINT AS channel_groups,
            COUNT(DISTINCT routing_universe_hash)::UBIGINT AS routing_universe_hashes,
            COUNT(DISTINCT s4_spec_version)::UBIGINT AS spec_versions,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(bucket_index)::BIGINT AS min_bucket_index,
            MAX(bucket_index)::BIGINT AS max_bucket_index
        FROM arrivals
        GROUP BY ALL
        ORDER BY seed, scenario_id
        """
    ).fetchdf()
    write_csv(identity_df, "arrival_events_identity_summary.csv")

    null_exprs = [
        f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)::UBIGINT AS {col}__nulls"
        for col in schema_df["column_name"]
    ]
    nulls_wide = con.execute(
        f"""
        SELECT COUNT(*)::UBIGINT AS rows, {", ".join(null_exprs)}
        FROM arrivals
        """
    ).fetchdf()
    total_rows = int(nulls_wide.loc[0, "rows"])
    null_rows = []
    for col in schema_df["column_name"]:
        null_count = int(nulls_wide.loc[0, f"{col}__nulls"])
        null_rows.append(
            {
                "column": col,
                "null_count": null_count,
                "null_pct": null_count / total_rows if total_rows else None,
            }
        )
    nulls_df = pd.DataFrame(null_rows)
    write_csv(nulls_df, "arrival_events_nulls.csv")

    profile_df = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(DISTINCT channel_group)::UBIGINT AS channels,
            COUNT(DISTINCT bucket_index)::UBIGINT AS bucket_indexes,
            COUNT(DISTINCT tzid_primary)::UBIGINT AS primary_timezones,
            COUNT(DISTINCT tzid_settlement)::UBIGINT AS settlement_timezones,
            COUNT(DISTINCT tzid_operational)::UBIGINT AS operational_timezones,
            SUM(CASE WHEN is_virtual THEN 1 ELSE 0 END)::UBIGINT AS virtual_rows,
            SUM(CASE WHEN NOT is_virtual THEN 1 ELSE 0 END)::UBIGINT AS physical_rows,
            SUM(CASE WHEN edge_id IS NULL THEN 1 ELSE 0 END)::UBIGINT AS edge_null_rows,
            SUM(CASE WHEN site_id IS NULL THEN 1 ELSE 0 END)::UBIGINT AS site_null_rows,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(bucket_index)::BIGINT AS min_bucket_index,
            MAX(bucket_index)::BIGINT AS max_bucket_index
        FROM arrivals
        """
    ).fetchdf()
    write_csv(profile_df, "arrival_events_profile.csv")

    channel_df = con.execute(
        """
        SELECT
            channel_group,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
        FROM arrivals
        GROUP BY channel_group
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(channel_df, "arrival_events_channel_summary.csv")

    virtual_df = con.execute(
        """
        SELECT
            is_virtual,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges,
            SUM(CASE WHEN edge_id IS NULL THEN 1 ELSE 0 END)::UBIGINT AS edge_null_rows
        FROM arrivals
        GROUP BY is_virtual
        ORDER BY is_virtual
        """
    ).fetchdf()
    write_csv(virtual_df, "arrival_events_virtual_summary.csv")

    month_df = con.execute(
        """
        SELECT
            SUBSTR(ts_utc, 1, 7) AS utc_month,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT SUBSTR(ts_utc, 1, 10))::UBIGINT AS active_days
        FROM arrivals
        GROUP BY utc_month
        ORDER BY utc_month
        """
    ).fetchdf()
    write_csv(month_df, "arrival_events_month_summary.csv")

    daily_df = con.execute(
        """
        SELECT
            SUBSTR(ts_utc, 1, 10) AS utc_date,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT channel_group)::UBIGINT AS channels
        FROM arrivals
        GROUP BY utc_date
        ORDER BY utc_date
        """
    ).fetchdf()
    write_csv(daily_df, "arrival_events_daily_summary.csv")

    daily_stats_df = con.execute(
        """
        WITH daily AS (
            SELECT SUBSTR(ts_utc, 1, 10) AS utc_date, COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY utc_date
        )
        SELECT
            COUNT(*)::UBIGINT AS days,
            MIN(rows)::UBIGINT AS min_daily_rows,
            quantile_cont(rows, 0.25) AS p25_daily_rows,
            AVG(rows) AS mean_daily_rows,
            quantile_cont(rows, 0.50) AS median_daily_rows,
            quantile_cont(rows, 0.75) AS p75_daily_rows,
            MAX(rows)::UBIGINT AS max_daily_rows,
            STDDEV_SAMP(rows) AS stddev_daily_rows
        FROM daily
        """
    ).fetchdf()
    write_csv(daily_stats_df, "arrival_events_daily_stats.csv")

    hour_df = con.execute(
        """
        SELECT
            CAST(SUBSTR(ts_utc, 12, 2) AS INTEGER) AS utc_hour,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share
        FROM arrivals
        GROUP BY utc_hour
        ORDER BY utc_hour
        """
    ).fetchdf()
    write_csv(hour_df, "arrival_events_utc_hour_summary.csv")

    merchant_volume_df = con.execute(
        """
        WITH merchant_counts AS (
            SELECT
                merchant_id,
                COUNT(*)::UBIGINT AS rows,
                MIN(arrival_seq)::BIGINT AS min_arrival_seq,
                MAX(arrival_seq)::BIGINT AS max_arrival_seq,
                COUNT(DISTINCT channel_group)::UBIGINT AS channels,
                COUNT(DISTINCT zone_representation)::UBIGINT AS zones
            FROM arrivals
            GROUP BY merchant_id
        )
        SELECT
            COUNT(*)::UBIGINT AS merchants,
            MIN(rows)::UBIGINT AS min_rows_per_merchant,
            quantile_cont(rows::DOUBLE, 0.05) AS p05_rows_per_merchant,
            quantile_cont(rows::DOUBLE, 0.25) AS p25_rows_per_merchant,
            AVG(rows::DOUBLE) AS mean_rows_per_merchant,
            quantile_cont(rows::DOUBLE, 0.50) AS median_rows_per_merchant,
            quantile_cont(rows::DOUBLE, 0.75) AS p75_rows_per_merchant,
            quantile_cont(rows::DOUBLE, 0.95) AS p95_rows_per_merchant,
            MAX(rows)::UBIGINT AS max_rows_per_merchant,
            SUM(CASE WHEN min_arrival_seq = 1 AND max_arrival_seq = rows THEN 0 ELSE 1 END)::UBIGINT AS sequence_span_mismatch_merchants,
            SUM(CASE WHEN channels > 1 THEN 1 ELSE 0 END)::UBIGINT AS multi_channel_merchants,
            SUM(CASE WHEN zones > 1 THEN 1 ELSE 0 END)::UBIGINT AS multi_zone_merchants
        FROM merchant_counts
        """
    ).fetchdf()
    write_csv(merchant_volume_df, "arrival_events_merchant_volume_stats.csv")

    top_merchants_df = con.execute(
        """
        SELECT
            merchant_id,
            COUNT(*)::UBIGINT AS rows,
            MIN(ts_utc) AS first_ts_utc,
            MAX(ts_utc) AS last_ts_utc,
            COUNT(DISTINCT channel_group)::UBIGINT AS channels,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones
        FROM arrivals
        GROUP BY merchant_id
        ORDER BY rows DESC, merchant_id
        LIMIT 25
        """
    ).fetchdf()
    write_csv(top_merchants_df, "arrival_events_top_merchants.csv")

    zone_df = con.execute(
        """
        SELECT
            zone_representation,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
        FROM arrivals
        GROUP BY zone_representation
        ORDER BY rows DESC
        LIMIT 25
        """
    ).fetchdf()
    write_csv(zone_df, "arrival_events_top_zones.csv")

    timezone_df = con.execute(
        """
        SELECT
            tzid_operational,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones
        FROM arrivals
        GROUP BY tzid_operational
        ORDER BY rows DESC
        LIMIT 25
        """
    ).fetchdf()
    write_csv(timezone_df, "arrival_events_top_operational_timezones.csv")

    summary = {
        "parquet_files": len(parquet_files),
        "profile": profile_df.iloc[0].to_dict(),
        "identity_rows": identity_df.to_dict(orient="records"),
        "channel_summary": channel_df.to_dict(orient="records"),
        "virtual_summary": virtual_df.to_dict(orient="records"),
        "month_summary": month_df.to_dict(orient="records"),
        "daily_stats": daily_stats_df.iloc[0].to_dict(),
        "merchant_volume_stats": merchant_volume_df.iloc[0].to_dict(),
        "top_zones": zone_df.head(10).to_dict(orient="records"),
    }
    with (EXPORT_DIR / "arrival_events_investigation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
