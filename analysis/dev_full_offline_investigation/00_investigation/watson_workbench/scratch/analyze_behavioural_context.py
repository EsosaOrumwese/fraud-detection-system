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
    / "behavioural_context"
)


DATASETS = {
    "arrival_entities": "s1_arrival_entities_6B",
    "session_index": "s1_session_index_6B",
    "baseline_anchor": "s2_flow_anchor_baseline_6B",
    "fraud_anchor": "s3_flow_anchor_with_fraud_6B",
}


def parquet_pattern(dataset_name: str) -> str:
    return str(SIX_B_ROOT / dataset_name / "**" / "*.parquet").replace("\\", "/")


def write_csv(df: pd.DataFrame, filename: str) -> None:
    df.to_csv(EXPORT_DIR / filename, index=False)


def describe_view(con: duckdb.DuckDBPyConnection, view_name: str, export_prefix: str) -> list[str]:
    schema_df = con.execute(f"DESCRIBE SELECT * FROM {view_name} LIMIT 0").fetchdf()
    write_csv(schema_df, f"{export_prefix}_schema.csv")
    return schema_df["column_name"].tolist()


def null_profile(con: duckdb.DuckDBPyConnection, view_name: str, columns: list[str], export_prefix: str) -> pd.DataFrame:
    null_exprs = [
        f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)::UBIGINT AS {col}__nulls"
        for col in columns
    ]
    nulls_wide = con.execute(
        f"SELECT COUNT(*)::UBIGINT AS rows, {', '.join(null_exprs)} FROM {view_name}"
    ).fetchdf()
    rows = int(nulls_wide.loc[0, "rows"])
    null_rows = []
    for col in columns:
        null_count = int(nulls_wide.loc[0, f"{col}__nulls"])
        null_rows.append(
            {
                "column": col,
                "null_count": null_count,
                "null_pct": null_count / rows if rows else None,
            }
        )
    nulls_df = pd.DataFrame(null_rows)
    write_csv(nulls_df, f"{export_prefix}_nulls.csv")
    return nulls_df


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads TO 8")

    file_counts: dict[str, int] = {}
    schemas: dict[str, list[str]] = {}
    for view_name, dataset_name in DATASETS.items():
        file_counts[view_name] = len(list((SIX_B_ROOT / dataset_name).rglob("*.parquet")))
        con.execute(
            f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT * FROM read_parquet('{parquet_pattern(dataset_name)}', hive_partitioning=true)
            """
        )
        schemas[view_name] = describe_view(con, view_name, view_name)

    arrival_entities_profile = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            approx_count_distinct(party_id)::UBIGINT AS approx_parties,
            approx_count_distinct(account_id)::UBIGINT AS approx_accounts,
            approx_count_distinct(instrument_id)::UBIGINT AS approx_instruments,
            approx_count_distinct(device_id)::UBIGINT AS approx_devices,
            approx_count_distinct(ip_id)::UBIGINT AS approx_ips,
            approx_count_distinct(session_id)::UBIGINT AS approx_sessions,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(arrival_seq)::BIGINT AS min_arrival_seq,
            MAX(arrival_seq)::BIGINT AS max_arrival_seq,
            SUM(hash(merchant_id, arrival_seq))::HUGEINT AS arrival_key_hash_sum
        FROM arrival_entities
        """
    ).fetchdf()
    write_csv(arrival_entities_profile, "arrival_entities_profile.csv")

    null_profile(con, "arrival_entities", schemas["arrival_entities"], "arrival_entities")

    session_profile = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(*)::UBIGINT AS sessions,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            approx_count_distinct(party_id)::UBIGINT AS approx_parties,
            approx_count_distinct(account_id)::UBIGINT AS approx_accounts,
            approx_count_distinct(instrument_id)::UBIGINT AS approx_instruments,
            approx_count_distinct(device_id)::UBIGINT AS approx_devices,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            SUM(arrival_count)::UBIGINT AS represented_arrivals,
            MIN(arrival_count)::UBIGINT AS min_arrival_count,
            approx_quantile(arrival_count, 0.50) AS median_arrival_count,
            approx_quantile(arrival_count, 0.95) AS p95_arrival_count,
            MAX(arrival_count)::UBIGINT AS max_arrival_count,
            MIN(session_start_utc) AS min_session_start_utc,
            MAX(session_end_utc) AS max_session_end_utc
        FROM session_index
        """
    ).fetchdf()
    write_csv(session_profile, "session_index_profile.csv")

    session_arrival_count_summary = con.execute(
        """
        SELECT
            arrival_count,
            COUNT(*)::UBIGINT AS sessions,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS session_share,
            SUM(arrival_count)::UBIGINT AS represented_arrivals
        FROM session_index
        GROUP BY arrival_count
        ORDER BY sessions DESC, arrival_count
        LIMIT 25
        """
    ).fetchdf()
    write_csv(session_arrival_count_summary, "session_index_arrival_count_summary.csv")

    null_profile(con, "session_index", schemas["session_index"], "session_index")

    anchor_profiles = {}
    for view_name in ["baseline_anchor", "fraud_anchor"]:
        fraud_columns = ""
        if view_name == "fraud_anchor":
            fraud_columns = """
            , SUM(CASE WHEN fraud_flag THEN 1 ELSE 0 END)::UBIGINT AS fraud_flows
            , COUNT(DISTINCT campaign_id) FILTER (WHERE campaign_id IS NOT NULL)::UBIGINT AS campaigns
            , SUM(CASE WHEN campaign_id IS NULL THEN 1 ELSE 0 END)::UBIGINT AS campaign_null_rows
            """
        profile = con.execute(
            f"""
            SELECT
                COUNT(*)::UBIGINT AS rows,
                COUNT(*)::UBIGINT AS flows,
                COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
                approx_count_distinct(party_id)::UBIGINT AS approx_parties,
                approx_count_distinct(account_id)::UBIGINT AS approx_accounts,
                approx_count_distinct(instrument_id)::UBIGINT AS approx_instruments,
                approx_count_distinct(device_id)::UBIGINT AS approx_devices,
                approx_count_distinct(ip_id)::UBIGINT AS approx_ips,
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
                SUM(amount) AS total_amount,
                MIN(arrival_seq)::BIGINT AS min_arrival_seq,
                MAX(arrival_seq)::BIGINT AS max_arrival_seq,
                SUM(hash(merchant_id, arrival_seq))::HUGEINT AS arrival_key_hash_sum,
                SUM(hash(flow_id))::HUGEINT AS flow_key_hash_sum
                {fraud_columns}
            FROM {view_name}
            """
        ).fetchdf()
        write_csv(profile, f"{view_name}_profile.csv")
        anchor_profiles[view_name] = profile
        null_profile(con, view_name, schemas[view_name], view_name)

    fraud_anchor_overlay = con.execute(
        """
        SELECT
            fraud_flag,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT campaign_id) FILTER (WHERE campaign_id IS NOT NULL)::UBIGINT AS campaigns,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share,
            MIN(amount) AS min_amount,
            AVG(amount) AS mean_amount,
            approx_quantile(amount, 0.50) AS median_amount,
            MAX(amount) AS max_amount,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc
        FROM fraud_anchor
        GROUP BY fraud_flag
        ORDER BY fraud_flag
        """
    ).fetchdf()
    write_csv(fraud_anchor_overlay, "fraud_anchor_overlay_summary.csv")

    fraud_anchor_campaigns = con.execute(
        """
        SELECT
            campaign_id,
            COUNT(*)::UBIGINT AS flows,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            MIN(amount) AS min_amount,
            AVG(amount) AS mean_amount,
            approx_quantile(amount, 0.50) AS median_amount,
            MAX(amount) AS max_amount
        FROM fraud_anchor
        WHERE campaign_id IS NOT NULL
        GROUP BY campaign_id
        ORDER BY flows DESC, campaign_id
        """
    ).fetchdf()
    write_csv(fraud_anchor_campaigns, "fraud_anchor_campaign_summary.csv")

    fraud_anchor_vs_baseline = con.execute(
        """
        WITH fraud_flows AS (
            SELECT flow_id, ts_utc, amount, fraud_flag, campaign_id
            FROM fraud_anchor
            WHERE fraud_flag
        )
        SELECT
            COUNT(*)::UBIGINT AS fraud_flows,
            SUM(CASE WHEN b.flow_id IS NOT NULL THEN 1 ELSE 0 END)::UBIGINT AS matched_baseline_flows,
            SUM(CASE WHEN b.flow_id IS NULL THEN 1 ELSE 0 END)::UBIGINT AS missing_baseline_flows,
            SUM(CASE WHEN b.flow_id IS NOT NULL AND b.ts_utc = f.ts_utc THEN 1 ELSE 0 END)::UBIGINT AS same_ts_rows,
            SUM(CASE WHEN b.flow_id IS NOT NULL AND b.amount = f.amount THEN 1 ELSE 0 END)::UBIGINT AS same_amount_rows,
            AVG(CASE WHEN b.flow_id IS NOT NULL THEN f.amount - b.amount ELSE NULL END) AS mean_amount_delta,
            MIN(CASE WHEN b.flow_id IS NOT NULL THEN f.amount - b.amount ELSE NULL END) AS min_amount_delta,
            MAX(CASE WHEN b.flow_id IS NOT NULL THEN f.amount - b.amount ELSE NULL END) AS max_amount_delta
        FROM fraud_flows f
        LEFT JOIN baseline_anchor b
        ON b.flow_id = f.flow_id
           AND b.seed = 42
           AND b.scenario_id = 'baseline_v1'
        """
    ).fetchdf()
    write_csv(fraud_anchor_vs_baseline, "fraud_anchor_vs_baseline.csv")

    key_reconciliation = pd.DataFrame(
        [
            {
                "surface": "arrival_entities",
                "rows": int(arrival_entities_profile.loc[0, "rows"]),
                "arrival_key_hash_sum": str(arrival_entities_profile.loc[0, "arrival_key_hash_sum"]),
            },
            {
                "surface": "baseline_anchor",
                "rows": int(anchor_profiles["baseline_anchor"].loc[0, "rows"]),
                "arrival_key_hash_sum": str(anchor_profiles["baseline_anchor"].loc[0, "arrival_key_hash_sum"]),
                "flow_key_hash_sum": str(anchor_profiles["baseline_anchor"].loc[0, "flow_key_hash_sum"]),
            },
            {
                "surface": "fraud_anchor",
                "rows": int(anchor_profiles["fraud_anchor"].loc[0, "rows"]),
                "arrival_key_hash_sum": str(anchor_profiles["fraud_anchor"].loc[0, "arrival_key_hash_sum"]),
                "flow_key_hash_sum": str(anchor_profiles["fraud_anchor"].loc[0, "flow_key_hash_sum"]),
            },
        ]
    )
    write_csv(key_reconciliation, "context_key_reconciliation.csv")

    summary = {
        "file_counts": file_counts,
        "arrival_entities_profile": arrival_entities_profile.iloc[0].to_dict(),
        "session_index_profile": session_profile.iloc[0].to_dict(),
        "baseline_anchor_profile": anchor_profiles["baseline_anchor"].iloc[0].to_dict(),
        "fraud_anchor_profile": anchor_profiles["fraud_anchor"].iloc[0].to_dict(),
        "session_arrival_count_summary": session_arrival_count_summary.to_dict(orient="records"),
        "fraud_anchor_overlay": fraud_anchor_overlay.to_dict(orient="records"),
        "fraud_anchor_campaigns": fraud_anchor_campaigns.to_dict(orient="records"),
        "fraud_anchor_vs_baseline": fraud_anchor_vs_baseline.to_dict(orient="records"),
        "key_reconciliation": key_reconciliation.to_dict(orient="records"),
    }

    with (EXPORT_DIR / "behavioural_context_investigation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    print(
        json.dumps(
            {
                "rows": {
                    "arrival_entities": summary["arrival_entities_profile"]["rows"],
                    "session_index": summary["session_index_profile"]["rows"],
                    "baseline_anchor": summary["baseline_anchor_profile"]["rows"],
                    "fraud_anchor": summary["fraud_anchor_profile"]["rows"],
                },
                "represented_arrivals_in_sessions": summary["session_index_profile"]["represented_arrivals"],
                "fraud_anchor_overlay": summary["fraud_anchor_overlay"],
                "fraud_anchor_vs_baseline": summary["fraud_anchor_vs_baseline"],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
