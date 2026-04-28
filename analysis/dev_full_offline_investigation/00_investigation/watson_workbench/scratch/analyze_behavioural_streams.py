from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
SIX_B_ROOT = RUN_ROOT / "data" / "layer3" / "6B"
EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_streams"
)


STREAMS = {
    "baseline": "s2_event_stream_baseline_6B",
    "with_fraud": "s3_event_stream_with_fraud_6B",
}


def parquet_pattern(dataset_name: str) -> str:
    return str(SIX_B_ROOT / dataset_name / "**" / "*.parquet").replace("\\", "/")


def write_csv(df: pd.DataFrame, filename: str) -> None:
    df.to_csv(EXPORT_DIR / filename, index=False)


def describe_stream(con: duckdb.DuckDBPyConnection, view_name: str, stream_name: str) -> dict[str, object]:
    schema_df = con.execute(f"DESCRIBE SELECT * FROM {view_name} LIMIT 0").fetchdf()
    write_csv(schema_df, f"{stream_name}_schema.csv")

    profile_df = con.execute(
        f"""
        SELECT
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
            COUNT(DISTINCT event_type)::UBIGINT AS event_types,
            MIN(event_seq)::BIGINT AS min_event_seq,
            MAX(event_seq)::BIGINT AS max_event_seq,
            COUNT(DISTINCT event_seq)::UBIGINT AS distinct_event_seq,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(amount) AS min_amount,
            approx_quantile(amount, 0.05) AS p05_amount,
            approx_quantile(amount, 0.25) AS p25_amount,
            AVG(amount) AS mean_amount,
            approx_quantile(amount, 0.50) AS median_amount,
            approx_quantile(amount, 0.75) AS p75_amount,
            approx_quantile(amount, 0.95) AS p95_amount,
            MAX(amount) AS max_amount,
            SUM(amount) AS total_amount
        FROM {view_name}
        """
    ).fetchdf()
    write_csv(profile_df, f"{stream_name}_profile.csv")

    event_type_df = con.execute(
        f"""
        SELECT
            event_type,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            MIN(amount) AS min_amount,
            AVG(amount) AS mean_amount,
            quantile_cont(amount, 0.50) AS median_amount,
            MAX(amount) AS max_amount
        FROM {view_name}
        GROUP BY event_type
        ORDER BY event_type
        """
    ).fetchdf()
    write_csv(event_type_df, f"{stream_name}_event_type_summary.csv")

    event_seq_df = con.execute(
        f"""
        SELECT
            event_seq,
            event_type,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows
        FROM {view_name}
        GROUP BY event_seq, event_type
        ORDER BY event_seq, event_type
        """
    ).fetchdf()
    write_csv(event_seq_df, f"{stream_name}_event_seq_summary.csv")

    month_df = con.execute(
        f"""
        SELECT
            SUBSTR(ts_utc, 1, 7) AS utc_month,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
            SUM(amount) AS total_amount
        FROM {view_name}
        GROUP BY utc_month
        ORDER BY utc_month
        """
    ).fetchdf()
    write_csv(month_df, f"{stream_name}_month_summary.csv")

    daily_stats_df = con.execute(
        f"""
        WITH daily AS (
            SELECT SUBSTR(ts_utc, 1, 10) AS utc_date, COUNT(*)::DOUBLE AS rows
            FROM {view_name}
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
    write_csv(daily_stats_df, f"{stream_name}_daily_stats.csv")

    null_exprs = [
        f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)::UBIGINT AS {col}__nulls"
        for col in schema_df["column_name"]
    ]
    nulls_wide = con.execute(f"SELECT COUNT(*)::UBIGINT AS rows, {', '.join(null_exprs)} FROM {view_name}").fetchdf()
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
    write_csv(nulls_df, f"{stream_name}_nulls.csv")

    return {
        "schema_columns": schema_df["column_name"].tolist(),
        "profile": profile_df.iloc[0].to_dict(),
        "event_type_summary": event_type_df.to_dict(orient="records"),
        "month_summary": month_df.to_dict(orient="records"),
        "daily_stats": daily_stats_df.iloc[0].to_dict(),
        "nulls": nulls_df.to_dict(orient="records"),
    }


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads TO 8")

    file_counts = {}
    for stream_name, dataset_name in STREAMS.items():
        file_counts[stream_name] = len(list((SIX_B_ROOT / dataset_name).rglob("*.parquet")))
        con.execute(
            f"""
            CREATE OR REPLACE VIEW {stream_name} AS
            SELECT * FROM read_parquet('{parquet_pattern(dataset_name)}', hive_partitioning=true)
            """
        )

    baseline_summary = describe_stream(con, "baseline", "baseline")
    fraud_summary = describe_stream(con, "with_fraud", "with_fraud")

    overlay_df = con.execute(
        """
        SELECT
            fraud_flag,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
            COUNT(DISTINCT campaign_id) FILTER (WHERE campaign_id IS NOT NULL)::UBIGINT AS campaigns,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            MIN(amount) AS min_amount,
            AVG(amount) AS mean_amount,
            quantile_cont(amount, 0.50) AS median_amount,
            MAX(amount) AS max_amount,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc
        FROM with_fraud
        GROUP BY fraud_flag
        ORDER BY fraud_flag
        """
    ).fetchdf()
    write_csv(overlay_df, "with_fraud_overlay_summary.csv")

    fraud_by_event_type_df = con.execute(
        """
        SELECT
            event_type,
            fraud_flag,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY event_type) AS share_within_event_type
        FROM with_fraud
        GROUP BY event_type, fraud_flag
        ORDER BY event_type, fraud_flag
        """
    ).fetchdf()
    write_csv(fraud_by_event_type_df, "with_fraud_flag_by_event_type.csv")

    campaign_df = con.execute(
        """
        SELECT
            campaign_id,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            COUNT(DISTINCT event_type)::UBIGINT AS event_types,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(amount) AS min_amount,
            AVG(amount) AS mean_amount,
            quantile_cont(amount, 0.50) AS median_amount,
            MAX(amount) AS max_amount
        FROM with_fraud
        WHERE campaign_id IS NOT NULL
        GROUP BY campaign_id
        ORDER BY rows DESC, campaign_id
        """
    ).fetchdf()
    write_csv(campaign_df, "with_fraud_campaign_summary.csv")

    fraud_month_df = con.execute(
        """
        SELECT
            SUBSTR(ts_utc, 1, 7) AS utc_month,
            fraud_flag,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows
        FROM with_fraud
        GROUP BY utc_month, fraud_flag
        ORDER BY utc_month, fraud_flag
        """
    ).fetchdf()
    write_csv(fraud_month_df, "with_fraud_month_by_flag.csv")

    fraud_flow_shape_df = con.execute(
        """
        WITH per_flow AS (
            SELECT
                flow_id,
                COUNT(*) AS events,
                COUNT(DISTINCT event_type) AS event_types,
                MIN(event_seq) AS min_event_seq,
                MAX(event_seq) AS max_event_seq
            FROM with_fraud
            WHERE fraud_flag
            GROUP BY flow_id
        )
        SELECT
            TRUE AS fraud_flow,
            COUNT(*)::UBIGINT AS flows,
            MIN(events)::UBIGINT AS min_events_per_flow,
            quantile_cont(events::DOUBLE, 0.50) AS median_events_per_flow,
            MAX(events)::UBIGINT AS max_events_per_flow,
            SUM(CASE WHEN events = 2 AND event_types = 2 AND min_event_seq = 0 AND max_event_seq = 1 THEN 0 ELSE 1 END)::UBIGINT AS nonstandard_flow_shapes
        FROM per_flow
        """
    ).fetchdf()
    write_csv(fraud_flow_shape_df, "with_fraud_flow_shape_by_flag.csv")

    baseline_sequence_balance_df = con.execute(
        """
        SELECT
            event_seq,
            event_type,
            COUNT(*)::UBIGINT AS rows,
            approx_count_distinct(flow_id)::UBIGINT AS approx_flows
        FROM baseline
        GROUP BY event_seq, event_type
        ORDER BY event_seq, event_type
        """
    ).fetchdf()
    write_csv(baseline_sequence_balance_df, "baseline_sequence_balance.csv")

    key_fingerprint_df = con.execute(
        """
        SELECT 'baseline' AS stream_name,
               COUNT(*)::UBIGINT AS rows,
               approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
               SUM(hash(flow_id, event_seq))::HUGEINT AS key_hash_sum
        FROM baseline
        UNION ALL
        SELECT 'with_fraud' AS stream_name,
               COUNT(*)::UBIGINT AS rows,
               approx_count_distinct(flow_id)::UBIGINT AS approx_flows,
               SUM(hash(flow_id, event_seq))::HUGEINT AS key_hash_sum
        FROM with_fraud
        """
    ).fetchdf()
    write_csv(key_fingerprint_df, "stream_key_fingerprint.csv")

    fraud_join_to_baseline_df = con.execute(
        """
        WITH fraud_rows AS (
            SELECT flow_id, event_seq, event_type, ts_utc, amount, campaign_id
            FROM with_fraud
            WHERE fraud_flag
        )
        SELECT
            COUNT(*)::UBIGINT AS fraud_rows,
            SUM(CASE WHEN b.flow_id IS NOT NULL THEN 1 ELSE 0 END)::UBIGINT AS matched_baseline_rows,
            SUM(CASE WHEN b.flow_id IS NULL THEN 1 ELSE 0 END)::UBIGINT AS missing_baseline_rows,
            SUM(CASE WHEN b.flow_id IS NOT NULL AND b.event_type = f.event_type THEN 1 ELSE 0 END)::UBIGINT AS same_event_type_rows,
            SUM(CASE WHEN b.flow_id IS NOT NULL AND b.ts_utc = f.ts_utc THEN 1 ELSE 0 END)::UBIGINT AS same_ts_rows,
            SUM(CASE WHEN b.flow_id IS NOT NULL AND b.amount = f.amount THEN 1 ELSE 0 END)::UBIGINT AS same_amount_rows,
            AVG(CASE WHEN b.flow_id IS NOT NULL THEN f.amount - b.amount ELSE NULL END) AS mean_amount_delta,
            MIN(CASE WHEN b.flow_id IS NOT NULL THEN f.amount - b.amount ELSE NULL END) AS min_amount_delta,
            MAX(CASE WHEN b.flow_id IS NOT NULL THEN f.amount - b.amount ELSE NULL END) AS max_amount_delta
        FROM fraud_rows f
        LEFT JOIN baseline b
        ON b.flow_id = f.flow_id
           AND b.event_seq = f.event_seq
           AND b.seed = 42
           AND b.scenario_id = 'baseline_v1'
        """
    ).fetchdf()
    write_csv(fraud_join_to_baseline_df, "fraud_rows_vs_baseline.csv")

    summary = {
        "file_counts": file_counts,
        "baseline": baseline_summary,
        "with_fraud": fraud_summary,
        "overlay_summary": overlay_df.to_dict(orient="records"),
        "campaign_summary": campaign_df.to_dict(orient="records"),
        "fraud_flow_shape": fraud_flow_shape_df.to_dict(orient="records"),
        "baseline_sequence_balance": baseline_sequence_balance_df.to_dict(orient="records"),
        "key_fingerprint": key_fingerprint_df.to_dict(orient="records"),
        "fraud_rows_vs_baseline": fraud_join_to_baseline_df.to_dict(orient="records"),
    }

    with (EXPORT_DIR / "behavioural_streams_investigation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(
        json.dumps(
            {
                "file_counts": file_counts,
                "baseline_rows": baseline_summary["profile"]["rows"],
                "with_fraud_rows": fraud_summary["profile"]["rows"],
                "fraud_overlay": overlay_df.to_dict(orient="records"),
                "fraud_rows_vs_baseline": fraud_join_to_baseline_df.to_dict(orient="records"),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
