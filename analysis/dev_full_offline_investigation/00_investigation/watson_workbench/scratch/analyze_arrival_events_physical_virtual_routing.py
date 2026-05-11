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
    / "physical_virtual_routing"
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

    route_overview = con.execute(
        """
        SELECT
            CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT merchant_id) * 1.0 / SUM(COUNT(DISTINCT merchant_id)) OVER () AS merchant_share,
            COUNT(DISTINCT channel_group)::UBIGINT AS channels,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
            COUNT(DISTINCT tzid_primary)::UBIGINT AS primary_timezones,
            COUNT(DISTINCT tzid_settlement)::UBIGINT AS settlement_timezones,
            COUNT(DISTINCT tzid_operational)::UBIGINT AS operational_timezones,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
        FROM arrivals
        GROUP BY is_virtual
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(route_overview, "route_overview.csv")

    route_consistency = con.execute(
        """
        SELECT
            CASE
                WHEN is_virtual = false AND site_id IS NOT NULL AND edge_id IS NULL THEN 'physical_valid_site_only'
                WHEN is_virtual = true AND edge_id IS NOT NULL AND site_id IS NULL THEN 'virtual_valid_edge_only'
                WHEN site_id IS NULL AND edge_id IS NULL THEN 'invalid_both_null'
                WHEN site_id IS NOT NULL AND edge_id IS NOT NULL THEN 'invalid_both_populated'
                WHEN is_virtual = false AND site_id IS NULL THEN 'invalid_physical_missing_site'
                WHEN is_virtual = false AND edge_id IS NOT NULL THEN 'invalid_physical_has_edge'
                WHEN is_virtual = true AND edge_id IS NULL THEN 'invalid_virtual_missing_edge'
                WHEN is_virtual = true AND site_id IS NOT NULL THEN 'invalid_virtual_has_site'
                ELSE 'other'
            END AS route_key_state,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants
        FROM arrivals
        GROUP BY route_key_state
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(route_consistency, "route_consistency.csv")

    merchant_route_stability = con.execute(
        """
        WITH merchant_routes AS (
            SELECT
                merchant_id,
                COUNT(DISTINCT is_virtual)::UBIGINT AS route_mode_count,
                MIN(CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END) AS assigned_route_mode,
                COUNT(*)::UBIGINT AS rows
            FROM arrivals
            GROUP BY merchant_id
        )
        SELECT
            route_mode_count,
            COUNT(*)::UBIGINT AS merchants,
            SUM(rows)::UBIGINT AS rows
        FROM merchant_routes
        GROUP BY route_mode_count
        ORDER BY route_mode_count
        """
    ).fetchdf()
    write_csv(merchant_route_stability, "merchant_route_stability.csv")

    merchant_volume_by_route = con.execute(
        """
        WITH merchant_counts AS (
            SELECT
                CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
                merchant_id,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT channel_group)::UBIGINT AS channels,
                COUNT(DISTINCT zone_representation)::UBIGINT AS zones,
                COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
                COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
            FROM arrivals
            GROUP BY route_mode, merchant_id
        )
        SELECT
            route_mode,
            COUNT(*)::UBIGINT AS merchants,
            SUM(rows)::UBIGINT AS rows,
            MIN(rows)::UBIGINT AS min_rows_per_merchant,
            quantile_cont(rows, 0.05) AS p05_rows_per_merchant,
            quantile_cont(rows, 0.25) AS p25_rows_per_merchant,
            AVG(rows) AS mean_rows_per_merchant,
            quantile_cont(rows, 0.50) AS median_rows_per_merchant,
            quantile_cont(rows, 0.75) AS p75_rows_per_merchant,
            quantile_cont(rows, 0.95) AS p95_rows_per_merchant,
            MAX(rows)::UBIGINT AS max_rows_per_merchant,
            AVG(zones) AS mean_zones_per_merchant,
            quantile_cont(zones, 0.50) AS median_zones_per_merchant,
            MAX(zones)::UBIGINT AS max_zones_per_merchant,
            AVG(sites) AS mean_sites_per_physical_merchant,
            quantile_cont(sites, 0.50) AS median_sites_per_physical_merchant,
            MAX(sites)::UBIGINT AS max_sites_per_physical_merchant,
            AVG(edges) AS mean_edges_per_virtual_merchant,
            quantile_cont(edges, 0.50) AS median_edges_per_virtual_merchant,
            MAX(edges)::UBIGINT AS max_edges_per_virtual_merchant
        FROM merchant_counts
        GROUP BY route_mode
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(merchant_volume_by_route, "merchant_volume_by_route.csv")

    endpoint_density = con.execute(
        """
        WITH physical_endpoints AS (
            SELECT
                'physical_site' AS endpoint_type,
                site_id AS endpoint_id,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
                COUNT(DISTINCT channel_group)::UBIGINT AS channels,
                COUNT(DISTINCT zone_representation)::UBIGINT AS zones
            FROM arrivals
            WHERE is_virtual = false
            GROUP BY site_id
        ),
        virtual_endpoints AS (
            SELECT
                'virtual_edge' AS endpoint_type,
                edge_id AS endpoint_id,
                COUNT(*)::DOUBLE AS rows,
                COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
                COUNT(DISTINCT channel_group)::UBIGINT AS channels,
                COUNT(DISTINCT zone_representation)::UBIGINT AS zones
            FROM arrivals
            WHERE is_virtual = true
            GROUP BY edge_id
        ),
        endpoints AS (
            SELECT * FROM physical_endpoints
            UNION ALL
            SELECT * FROM virtual_endpoints
        )
        SELECT
            endpoint_type,
            COUNT(*)::UBIGINT AS endpoints,
            SUM(rows)::UBIGINT AS rows,
            MIN(rows)::UBIGINT AS min_rows_per_endpoint,
            quantile_cont(rows, 0.05) AS p05_rows_per_endpoint,
            quantile_cont(rows, 0.25) AS p25_rows_per_endpoint,
            AVG(rows) AS mean_rows_per_endpoint,
            quantile_cont(rows, 0.50) AS median_rows_per_endpoint,
            quantile_cont(rows, 0.75) AS p75_rows_per_endpoint,
            quantile_cont(rows, 0.95) AS p95_rows_per_endpoint,
            MAX(rows)::UBIGINT AS max_rows_per_endpoint,
            AVG(zones) AS mean_zones_per_endpoint,
            quantile_cont(zones, 0.50) AS median_zones_per_endpoint,
            MAX(zones)::UBIGINT AS max_zones_per_endpoint
        FROM endpoints
        GROUP BY endpoint_type
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(endpoint_density, "endpoint_density.csv")

    route_by_channel = con.execute(
        """
        SELECT
            CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
            channel_group,
            COUNT(*)::UBIGINT AS rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY is_virtual) AS share_within_route_mode,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY channel_group) AS share_within_channel,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
        FROM arrivals
        GROUP BY is_virtual, channel_group
        ORDER BY route_mode, rows DESC
        """
    ).fetchdf()
    write_csv(route_by_channel, "route_by_channel.csv")

    route_daily = con.execute(
        """
        SELECT
            SUBSTR(ts_utc, 1, 10) AS utc_date,
            CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
            COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
        FROM arrivals
        GROUP BY utc_date, route_mode
        ORDER BY utc_date, route_mode
        """
    ).fetchdf()
    write_csv(route_daily, "route_daily_summary.csv")

    route_daily_share_stats = con.execute(
        """
        WITH daily AS (
            SELECT
                SUBSTR(ts_utc, 1, 10) AS utc_date,
                CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
                COUNT(*)::DOUBLE AS rows
            FROM arrivals
            GROUP BY utc_date, route_mode
        ),
        shares AS (
            SELECT
                utc_date,
                route_mode,
                rows,
                rows / SUM(rows) OVER (PARTITION BY utc_date) AS daily_row_share
            FROM daily
        )
        SELECT
            route_mode,
            COUNT(*)::UBIGINT AS days,
            MIN(daily_row_share) AS min_daily_share,
            quantile_cont(daily_row_share, 0.25) AS p25_daily_share,
            AVG(daily_row_share) AS mean_daily_share,
            quantile_cont(daily_row_share, 0.50) AS median_daily_share,
            quantile_cont(daily_row_share, 0.75) AS p75_daily_share,
            MAX(daily_row_share) AS max_daily_share,
            STDDEV_SAMP(daily_row_share) AS stddev_daily_share
        FROM shares
        GROUP BY route_mode
        ORDER BY mean_daily_share DESC
        """
    ).fetchdf()
    write_csv(route_daily_share_stats, "route_daily_share_stats.csv")

    top_zones_by_route = con.execute(
        """
        WITH route_zone AS (
            SELECT
                CASE WHEN is_virtual THEN 'virtual' ELSE 'physical' END AS route_mode,
                zone_representation,
                COUNT(*)::UBIGINT AS rows,
                COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
                COUNT(DISTINCT site_id) FILTER (WHERE site_id IS NOT NULL)::UBIGINT AS sites,
                COUNT(DISTINCT edge_id) FILTER (WHERE edge_id IS NOT NULL)::UBIGINT AS edges
            FROM arrivals
            GROUP BY route_mode, zone_representation
        ),
        ranked AS (
            SELECT
                *,
                rows * 1.0 / SUM(rows) OVER (PARTITION BY route_mode) AS share_within_route_mode,
                ROW_NUMBER() OVER (PARTITION BY route_mode ORDER BY rows DESC, zone_representation) AS route_rank
            FROM route_zone
        )
        SELECT *
        FROM ranked
        WHERE route_rank <= 10
        ORDER BY route_mode, route_rank
        """
    ).fetchdf()
    write_csv(top_zones_by_route, "top_zones_by_route.csv")

    summary = {
        "route_overview": route_overview.to_dict(orient="records"),
        "route_consistency": route_consistency.to_dict(orient="records"),
        "merchant_route_stability": merchant_route_stability.to_dict(orient="records"),
        "merchant_volume_by_route": merchant_volume_by_route.to_dict(orient="records"),
        "endpoint_density": endpoint_density.to_dict(orient="records"),
        "route_by_channel": route_by_channel.to_dict(orient="records"),
        "route_daily_share_stats": route_daily_share_stats.to_dict(orient="records"),
    }
    with (EXPORT_DIR / "physical_virtual_routing_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
