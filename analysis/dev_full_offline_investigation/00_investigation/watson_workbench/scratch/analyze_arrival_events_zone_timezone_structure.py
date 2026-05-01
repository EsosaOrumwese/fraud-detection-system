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
    / "zone_timezone_structure"
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
            CAST(substr(ts_utc, 12, 2) AS INTEGER) AS utc_hour,
            CAST(substr(ts_local_primary, 12, 2) AS INTEGER) AS primary_local_hour,
            CAST(substr(ts_local_settlement, 12, 2) AS INTEGER) AS settlement_local_hour,
            CAST(substr(ts_local_operational, 12, 2) AS INTEGER) AS operational_local_hour
        FROM read_parquet('{parquet_pattern(ARRIVAL_ROOT)}', hive_partitioning=true)
        """
    )

    overview = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(DISTINCT tzid_primary)::UBIGINT AS primary_timezones,
            COUNT(DISTINCT tzid_settlement)::UBIGINT AS settlement_timezones,
            COUNT(DISTINCT tzid_operational)::UBIGINT AS operational_timezones,
            COUNT(DISTINCT (zone_representation, tzid_primary))::UBIGINT AS zone_primary_pairs,
            COUNT(DISTINCT (zone_representation, tzid_operational))::UBIGINT AS zone_operational_pairs,
            COUNT(DISTINCT (tzid_primary, tzid_settlement, tzid_operational))::UBIGINT AS timezone_triples,
            COUNT(*) FILTER (WHERE zone_representation = tzid_primary)::UBIGINT AS rows_zone_equals_primary_tz,
            COUNT(*) FILTER (WHERE zone_representation = tzid_operational)::UBIGINT AS rows_zone_equals_operational_tz,
            COUNT(*) FILTER (WHERE tzid_primary = tzid_settlement AND tzid_settlement = tzid_operational)::UBIGINT AS rows_all_timezones_equal
        FROM arrivals
        """
    ).fetchdf()
    write_csv(overview, "zone_timezone_overview.csv")

    null_profile = con.execute(
        """
        SELECT
            SUM(CASE WHEN zone_representation IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_zone_representation,
            SUM(CASE WHEN tzid_primary IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_tzid_primary,
            SUM(CASE WHEN tzid_settlement IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_tzid_settlement,
            SUM(CASE WHEN tzid_operational IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_tzid_operational,
            SUM(CASE WHEN utc_hour IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_utc_hour,
            SUM(CASE WHEN primary_local_hour IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_primary_local_hour,
            SUM(CASE WHEN settlement_local_hour IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_settlement_local_hour,
            SUM(CASE WHEN operational_local_hour IS NULL THEN 1 ELSE 0 END)::UBIGINT AS null_operational_local_hour
        FROM arrivals
        """
    ).fetchdf()
    write_csv(null_profile, "zone_timezone_null_profile.csv")

    zone_overview = con.execute(
        """
        SELECT
            zone_representation,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges,
            COUNT(DISTINCT channel_group)::UBIGINT AS channels,
            COUNT(DISTINCT is_virtual)::UBIGINT AS route_modes,
            COUNT(DISTINCT tzid_primary)::UBIGINT AS primary_timezones,
            COUNT(DISTINCT tzid_operational)::UBIGINT AS operational_timezones,
            COUNT(DISTINCT (tzid_primary, tzid_settlement, tzid_operational))::UBIGINT AS timezone_triples,
            COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT merchant_id), 0) AS rows_per_merchant
        FROM arrivals
        GROUP BY zone_representation
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(zone_overview, "zone_overview.csv")

    zone_distribution_stats = con.execute(
        """
        WITH z AS (
            SELECT
                zone_representation,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT merchant_id)::DOUBLE AS merchants,
                COUNT(*)::DOUBLE / NULLIF(COUNT(DISTINCT merchant_id), 0) AS rows_per_merchant
            FROM arrivals
            GROUP BY zone_representation
        )
        SELECT
            COUNT(*)::UBIGINT AS zones,
            MIN(rows)::UBIGINT AS min_rows,
            quantile_cont(rows, 0.05) AS p05_rows,
            quantile_cont(rows, 0.25) AS p25_rows,
            quantile_cont(rows, 0.50) AS median_rows,
            AVG(rows) AS mean_rows,
            quantile_cont(rows, 0.75) AS p75_rows,
            quantile_cont(rows, 0.95) AS p95_rows,
            MAX(rows)::UBIGINT AS max_rows,
            MIN(merchants)::UBIGINT AS min_merchants,
            quantile_cont(merchants, 0.50) AS median_merchants,
            AVG(merchants) AS mean_merchants,
            MAX(merchants)::UBIGINT AS max_merchants,
            MIN(rows_per_merchant) AS min_rows_per_merchant,
            quantile_cont(rows_per_merchant, 0.50) AS median_rows_per_merchant,
            AVG(rows_per_merchant) AS mean_rows_per_merchant,
            MAX(rows_per_merchant) AS max_rows_per_merchant
        FROM z
        """
    ).fetchdf()
    write_csv(zone_distribution_stats, "zone_distribution_stats.csv")

    zone_concentration = con.execute(
        """
        WITH z AS (
            SELECT zone_representation, COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY zone_representation
        ),
        ranked AS (
            SELECT
                zone_representation,
                rows,
                ROW_NUMBER() OVER (ORDER BY rows DESC) AS zone_rank,
                SUM(rows) OVER () AS total_rows
            FROM z
        )
        SELECT
            zone_rank,
            zone_representation,
            rows::UBIGINT AS rows,
            rows / total_rows AS row_share,
            SUM(rows) OVER (ORDER BY zone_rank) / total_rows AS cumulative_row_share
        FROM ranked
        ORDER BY zone_rank
        """
    ).fetchdf()
    write_csv(zone_concentration, "zone_concentration_ranked.csv")

    merchant_zone_distribution = con.execute(
        """
        WITH mz AS (
            SELECT
                merchant_id,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT zone_representation)::DOUBLE AS zones,
                COUNT(DISTINCT tzid_primary)::DOUBLE AS primary_timezones,
                COUNT(DISTINCT tzid_operational)::DOUBLE AS operational_timezones
            FROM arrivals
            GROUP BY merchant_id
        )
        SELECT
            COUNT(*)::UBIGINT AS merchants,
            MIN(zones)::UBIGINT AS min_zones_per_merchant,
            quantile_cont(zones, 0.05) AS p05_zones_per_merchant,
            quantile_cont(zones, 0.25) AS p25_zones_per_merchant,
            quantile_cont(zones, 0.50) AS median_zones_per_merchant,
            AVG(zones) AS mean_zones_per_merchant,
            quantile_cont(zones, 0.75) AS p75_zones_per_merchant,
            quantile_cont(zones, 0.95) AS p95_zones_per_merchant,
            MAX(zones)::UBIGINT AS max_zones_per_merchant,
            MIN(primary_timezones)::UBIGINT AS min_primary_timezones_per_merchant,
            quantile_cont(primary_timezones, 0.50) AS median_primary_timezones_per_merchant,
            MAX(primary_timezones)::UBIGINT AS max_primary_timezones_per_merchant,
            MIN(operational_timezones)::UBIGINT AS min_operational_timezones_per_merchant,
            quantile_cont(operational_timezones, 0.50) AS median_operational_timezones_per_merchant,
            MAX(operational_timezones)::UBIGINT AS max_operational_timezones_per_merchant
        FROM mz
        """
    ).fetchdf()
    write_csv(merchant_zone_distribution, "merchant_zone_distribution.csv")

    merchant_top_zone_dependence = con.execute(
        """
        WITH merchant_zone_rows AS (
            SELECT
                merchant_id,
                zone_representation,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY merchant_id, zone_representation
        ),
        merchant_zone_ranked AS (
            SELECT
                merchant_id,
                zone_representation,
                rows,
                SUM(rows) OVER (PARTITION BY merchant_id) AS merchant_rows,
                ROW_NUMBER() OVER (PARTITION BY merchant_id ORDER BY rows DESC) AS zone_rank
            FROM merchant_zone_rows
        ),
        merchant_summary AS (
            SELECT
                merchant_id,
                MAX(rows / merchant_rows) FILTER (WHERE zone_rank = 1) AS top_zone_row_share,
                COUNT(*)::DOUBLE AS zones
            FROM merchant_zone_ranked
            GROUP BY merchant_id
        )
        SELECT
            COUNT(*)::UBIGINT AS merchants,
            MIN(top_zone_row_share) AS min_top_zone_row_share,
            quantile_cont(top_zone_row_share, 0.05) AS p05_top_zone_row_share,
            quantile_cont(top_zone_row_share, 0.25) AS p25_top_zone_row_share,
            quantile_cont(top_zone_row_share, 0.50) AS median_top_zone_row_share,
            AVG(top_zone_row_share) AS mean_top_zone_row_share,
            quantile_cont(top_zone_row_share, 0.75) AS p75_top_zone_row_share,
            quantile_cont(top_zone_row_share, 0.95) AS p95_top_zone_row_share,
            MAX(top_zone_row_share) AS max_top_zone_row_share
        FROM merchant_summary
        """
    ).fetchdf()
    write_csv(merchant_top_zone_dependence, "merchant_top_zone_dependence.csv")

    timezone_field_relationships = con.execute(
        """
        SELECT
            CASE
                WHEN tzid_primary = tzid_settlement AND tzid_settlement = tzid_operational THEN 'all_three_equal'
                WHEN tzid_primary = tzid_settlement AND tzid_settlement <> tzid_operational THEN 'primary_equals_settlement_only'
                WHEN tzid_primary = tzid_operational AND tzid_primary <> tzid_settlement THEN 'primary_equals_operational_only'
                WHEN tzid_settlement = tzid_operational AND tzid_primary <> tzid_settlement THEN 'settlement_equals_operational_only'
                ELSE 'all_three_different'
            END AS timezone_relationship,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(DISTINCT is_virtual)::UBIGINT AS route_modes
        FROM arrivals
        GROUP BY timezone_relationship
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(timezone_field_relationships, "timezone_field_relationships.csv")

    hour_profile_utc = con.execute(
        """
        SELECT
            utc_hour,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones
        FROM arrivals
        GROUP BY utc_hour
        ORDER BY utc_hour
        """
    ).fetchdf()
    write_csv(hour_profile_utc, "hour_profile_utc.csv")

    hour_profile_local = con.execute(
        """
        WITH hour_rows AS (
            SELECT 'primary' AS clock_field, primary_local_hour AS local_hour, COUNT(*)::UBIGINT AS rows
            FROM arrivals
            GROUP BY local_hour
            UNION ALL
            SELECT 'settlement' AS clock_field, settlement_local_hour AS local_hour, COUNT(*)::UBIGINT AS rows
            FROM arrivals
            GROUP BY local_hour
            UNION ALL
            SELECT 'operational' AS clock_field, operational_local_hour AS local_hour, COUNT(*)::UBIGINT AS rows
            FROM arrivals
            GROUP BY local_hour
        )
        SELECT
            clock_field,
            local_hour,
            rows,
            rows * 1.0 / SUM(rows) OVER (PARTITION BY clock_field) AS row_share
        FROM hour_rows
        ORDER BY clock_field, local_hour
        """
    ).fetchdf()
    write_csv(hour_profile_local, "hour_profile_local.csv")

    zone_hour_profile_top_zones = con.execute(
        """
        WITH top_zones AS (
            SELECT zone_representation
            FROM arrivals
            GROUP BY zone_representation
            ORDER BY COUNT(*) DESC
            LIMIT 30
        ),
        zh AS (
            SELECT
                a.zone_representation,
                a.utc_hour,
                COUNT(*)::DOUBLE AS rows,
                SUM(COUNT(*)) OVER (PARTITION BY a.zone_representation)::DOUBLE AS zone_rows
            FROM arrivals a
            INNER JOIN top_zones z USING (zone_representation)
            GROUP BY a.zone_representation, a.utc_hour
        )
        SELECT
            zone_representation,
            utc_hour,
            rows::UBIGINT AS rows,
            rows / zone_rows AS row_share
        FROM zh
        ORDER BY zone_representation, utc_hour
        """
    ).fetchdf()
    write_csv(zone_hour_profile_top_zones, "zone_hour_profile_top_zones.csv")

    zone_hour_shape_summary = con.execute(
        """
        WITH zone_hours AS (
            SELECT
                zone_representation,
                utc_hour,
                COUNT(*)::DOUBLE AS rows,
                SUM(COUNT(*)) OVER (PARTITION BY zone_representation)::DOUBLE AS zone_rows
            FROM arrivals
            GROUP BY zone_representation, utc_hour
        ),
        ranked AS (
            SELECT
                zone_representation,
                utc_hour,
                rows,
                rows / zone_rows AS row_share,
                zone_rows,
                ROW_NUMBER() OVER (PARTITION BY zone_representation ORDER BY rows DESC, utc_hour) AS peak_rank,
                ROW_NUMBER() OVER (PARTITION BY zone_representation ORDER BY rows ASC, utc_hour) AS trough_rank
            FROM zone_hours
        ),
        summarized AS (
            SELECT
                zone_representation,
                MAX(zone_rows)::UBIGINT AS rows,
                MAX(utc_hour) FILTER (WHERE peak_rank = 1) AS peak_utc_hour,
                MAX(row_share) FILTER (WHERE peak_rank = 1) AS peak_utc_share,
                MAX(utc_hour) FILTER (WHERE trough_rank = 1) AS trough_utc_hour,
                MAX(row_share) FILTER (WHERE trough_rank = 1) AS trough_utc_share,
                SUM(row_share) FILTER (WHERE utc_hour BETWEEN 10 AND 17) AS utc_business_band_share,
                SUM(row_share) FILTER (WHERE utc_hour BETWEEN 3 AND 5) AS utc_early_low_band_share
            FROM ranked
            GROUP BY zone_representation
        )
        SELECT *
        FROM summarized
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(zone_hour_shape_summary, "zone_hour_shape_summary.csv")

    local_vs_utc_peak_summary = con.execute(
        """
        WITH field_hours AS (
            SELECT 'utc' AS clock_field, utc_hour AS hour_value, COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY hour_value
            UNION ALL
            SELECT 'primary_local' AS clock_field, primary_local_hour AS hour_value, COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY hour_value
            UNION ALL
            SELECT 'settlement_local' AS clock_field, settlement_local_hour AS hour_value, COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY hour_value
            UNION ALL
            SELECT 'operational_local' AS clock_field, operational_local_hour AS hour_value, COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY hour_value
        ),
        ranked AS (
            SELECT
                clock_field,
                hour_value,
                rows,
                rows / SUM(rows) OVER (PARTITION BY clock_field) AS row_share,
                ROW_NUMBER() OVER (PARTITION BY clock_field ORDER BY rows DESC, hour_value) AS peak_rank,
                ROW_NUMBER() OVER (PARTITION BY clock_field ORDER BY rows ASC, hour_value) AS trough_rank
            FROM field_hours
        )
        SELECT
            clock_field,
            MAX(hour_value) FILTER (WHERE peak_rank = 1) AS peak_hour,
            MAX(row_share) FILTER (WHERE peak_rank = 1) AS peak_share,
            MAX(hour_value) FILTER (WHERE trough_rank = 1) AS trough_hour,
            MAX(row_share) FILTER (WHERE trough_rank = 1) AS trough_share,
            SUM(row_share) FILTER (WHERE hour_value BETWEEN 10 AND 17) AS business_band_share,
            SUM(row_share) FILTER (WHERE hour_value BETWEEN 3 AND 5) AS early_low_band_share
        FROM ranked
        GROUP BY clock_field
        ORDER BY clock_field
        """
    ).fetchdf()
    write_csv(local_vs_utc_peak_summary, "local_vs_utc_peak_summary.csv")

    zone_hour_shape_rollup = con.execute(
        """
        WITH zone_hours AS (
            SELECT
                zone_representation,
                utc_hour,
                COUNT(*)::DOUBLE AS rows,
                SUM(COUNT(*)) OVER (PARTITION BY zone_representation)::DOUBLE AS zone_rows
            FROM arrivals
            GROUP BY zone_representation, utc_hour
        ),
        ranked AS (
            SELECT
                zone_representation,
                utc_hour,
                rows,
                zone_rows,
                ROW_NUMBER() OVER (PARTITION BY zone_representation ORDER BY rows DESC, utc_hour) AS peak_rank,
                ROW_NUMBER() OVER (PARTITION BY zone_representation ORDER BY rows ASC, utc_hour) AS trough_rank
            FROM zone_hours
        ),
        summarized AS (
            SELECT
                zone_representation,
                MAX(zone_rows)::DOUBLE AS zone_rows,
                MAX(utc_hour) FILTER (WHERE peak_rank = 1) AS peak_utc_hour,
                MAX(utc_hour) FILTER (WHERE trough_rank = 1) AS trough_utc_hour
            FROM ranked
            GROUP BY zone_representation
        )
        SELECT
            COUNT(*)::UBIGINT AS zones,
            COUNT(*) FILTER (WHERE zone_rows >= 100000)::UBIGINT AS zones_with_at_least_100k_rows,
            COUNT(*) FILTER (WHERE peak_utc_hour BETWEEN 10 AND 17)::UBIGINT AS zones_peak_in_global_business_band,
            COUNT(*) FILTER (WHERE zone_rows >= 100000 AND peak_utc_hour BETWEEN 10 AND 17)::UBIGINT AS zones_100k_peak_in_global_business_band,
            COUNT(*) FILTER (WHERE trough_utc_hour BETWEEN 3 AND 5)::UBIGINT AS zones_trough_in_global_low_band,
            COUNT(*) FILTER (WHERE zone_rows >= 100000 AND trough_utc_hour BETWEEN 3 AND 5)::UBIGINT AS zones_100k_trough_in_global_low_band
        FROM summarized
        """
    ).fetchdf()
    write_csv(zone_hour_shape_rollup, "zone_hour_shape_rollup.csv")

    summary = {
        "overview": overview.to_dict(orient="records")[0],
        "zone_distribution_stats": zone_distribution_stats.to_dict(orient="records")[0],
        "merchant_zone_distribution": merchant_zone_distribution.to_dict(orient="records")[0],
        "merchant_top_zone_dependence": merchant_top_zone_dependence.to_dict(orient="records")[0],
        "local_vs_utc_peak_summary": local_vs_utc_peak_summary.to_dict(orient="records"),
        "zone_hour_shape_rollup": zone_hour_shape_rollup.to_dict(orient="records")[0],
    }
    (EXPORT_DIR / "zone_timezone_structure_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
