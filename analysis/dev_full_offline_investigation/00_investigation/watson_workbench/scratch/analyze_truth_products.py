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
    / "truth_products"
)


DATASETS = {
    "flow_truth": "s4_flow_truth_labels_6B",
    "flow_bank": "s4_flow_bank_view_6B",
    "event_labels": "s4_event_labels_6B",
    "case_timeline": "s4_case_timeline_6B",
    "fraud_anchor": "s3_flow_anchor_with_fraud_6B",
    "fraud_stream": "s3_event_stream_with_fraud_6B",
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
    tmp_dir = EXPORT_DIR / "_duckdb_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("SET threads TO 8")
    tmp_dir_sql = str(tmp_dir).replace("\\", "/")
    con.execute(f"SET temp_directory TO '{tmp_dir_sql}'")

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

    flow_truth_profile = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            SUM(CASE WHEN is_fraud_truth THEN 1 ELSE 0 END)::UBIGINT AS truth_positive_flows,
            SUM(CASE WHEN NOT is_fraud_truth THEN 1 ELSE 0 END)::UBIGINT AS truth_negative_flows,
            COUNT(DISTINCT fraud_label) FILTER (WHERE fraud_label IS NOT NULL)::UBIGINT AS non_null_truth_labels,
            SUM(CASE WHEN fraud_label IS NULL THEN 1 ELSE 0 END)::UBIGINT AS fraud_label_null_rows,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            SUM(hash(flow_id))::HUGEINT AS flow_key_hash_sum
        FROM flow_truth
        """
    ).fetchdf()
    write_csv(flow_truth_profile, "flow_truth_profile.csv")
    null_profile(con, "flow_truth", schemas["flow_truth"], "flow_truth")

    flow_truth_label_summary = con.execute(
        """
        SELECT
            is_fraud_truth,
            fraud_label,
            COUNT(*)::UBIGINT AS flows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS flow_share
        FROM flow_truth
        GROUP BY is_fraud_truth, fraud_label
        ORDER BY flows DESC
        """
    ).fetchdf()
    write_csv(flow_truth_label_summary, "flow_truth_label_summary.csv")

    flow_bank_profile = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END)::UBIGINT AS bank_positive_flows,
            SUM(CASE WHEN NOT is_fraud_bank_view THEN 1 ELSE 0 END)::UBIGINT AS bank_negative_flows,
            COUNT(DISTINCT bank_label) FILTER (WHERE bank_label IS NOT NULL)::UBIGINT AS non_null_bank_labels,
            SUM(CASE WHEN bank_label IS NULL THEN 1 ELSE 0 END)::UBIGINT AS bank_label_null_rows,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            SUM(hash(flow_id))::HUGEINT AS flow_key_hash_sum
        FROM flow_bank
        """
    ).fetchdf()
    write_csv(flow_bank_profile, "flow_bank_profile.csv")
    null_profile(con, "flow_bank", schemas["flow_bank"], "flow_bank")

    flow_bank_label_summary = con.execute(
        """
        SELECT
            is_fraud_bank_view,
            bank_label,
            COUNT(*)::UBIGINT AS flows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS flow_share
        FROM flow_bank
        GROUP BY is_fraud_bank_view, bank_label
        ORDER BY flows DESC
        """
    ).fetchdf()
    write_csv(flow_bank_label_summary, "flow_bank_label_summary.csv")

    flow_truth_bank_confusion = con.execute(
        """
        WITH totals AS (
            SELECT
                COUNT(*)::UBIGINT AS total_flows,
                SUM(CASE WHEN is_fraud_truth THEN 1 ELSE 0 END)::UBIGINT AS truth_positive_flows
            FROM flow_truth
        ),
        bank_totals AS (
            SELECT
                SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END)::UBIGINT AS bank_positive_flows
            FROM flow_bank
        ),
        true_positive AS (
            SELECT COUNT(*)::UBIGINT AS flows
            FROM (
                SELECT seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id
                FROM flow_truth
                WHERE is_fraud_truth
            ) t
            JOIN (
                SELECT seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id
                FROM flow_bank
                WHERE is_fraud_bank_view
            ) b
              USING (seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id)
        ),
        cells AS (
            SELECT true AS is_fraud_truth, true AS is_fraud_bank_view, flows
            FROM true_positive
            UNION ALL
            SELECT true, false, truth_positive_flows - flows
            FROM totals, true_positive
            UNION ALL
            SELECT false, true, bank_positive_flows - flows
            FROM bank_totals, true_positive
            UNION ALL
            SELECT false, false, total_flows - truth_positive_flows - bank_positive_flows + flows
            FROM totals, bank_totals, true_positive
        )
        SELECT
            is_fraud_truth,
            is_fraud_bank_view,
            flows,
            flows * 1.0 / SUM(flows) OVER () AS flow_share
        FROM cells
        ORDER BY flows DESC
        """
    ).fetchdf()
    write_csv(flow_truth_bank_confusion, "flow_truth_bank_confusion.csv")

    flow_truth_anchor_reconciliation = con.execute(
        """
        WITH totals AS (
            SELECT
                COUNT(*)::UBIGINT AS total_flows,
                SUM(CASE WHEN is_fraud_truth THEN 1 ELSE 0 END)::UBIGINT AS truth_positive_flows
            FROM flow_truth
        ),
        anchor_totals AS (
            SELECT
                SUM(CASE WHEN fraud_flag THEN 1 ELSE 0 END)::UBIGINT AS anchor_fraud_flows
            FROM fraud_anchor
        ),
        overlap AS (
            SELECT COUNT(*)::UBIGINT AS flows
            FROM (
                SELECT seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id
                FROM flow_truth
                WHERE is_fraud_truth
            ) t
            JOIN (
                SELECT seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id
                FROM fraud_anchor
                WHERE fraud_flag
            ) a
              USING (seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id)
        ),
        cells AS (
            SELECT true AS is_fraud_truth, true AS fraud_flag, flows
            FROM overlap
            UNION ALL
            SELECT true, false, truth_positive_flows - flows
            FROM totals, overlap
            UNION ALL
            SELECT false, true, anchor_fraud_flows - flows
            FROM anchor_totals, overlap
            UNION ALL
            SELECT false, false, total_flows - truth_positive_flows - anchor_fraud_flows + flows
            FROM totals, anchor_totals, overlap
        )
        SELECT
            is_fraud_truth,
            fraud_flag,
            flows,
            flows * 1.0 / SUM(flows) OVER () AS flow_share
        FROM cells
        ORDER BY flows DESC
        """
    ).fetchdf()
    write_csv(flow_truth_anchor_reconciliation, "flow_truth_anchor_reconciliation.csv")

    event_labels_profile = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            COUNT(DISTINCT event_seq)::UBIGINT AS event_seq_values,
            MIN(event_seq)::INTEGER AS min_event_seq,
            MAX(event_seq)::INTEGER AS max_event_seq,
            SUM(CASE WHEN is_fraud_truth THEN 1 ELSE 0 END)::UBIGINT AS truth_positive_event_rows,
            SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END)::UBIGINT AS bank_positive_event_rows,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            SUM(hash(flow_id, event_seq))::HUGEINT AS event_key_hash_sum
        FROM event_labels
        """
    ).fetchdf()
    write_csv(event_labels_profile, "event_labels_profile.csv")
    null_profile(con, "event_labels", schemas["event_labels"], "event_labels")

    event_labels_by_seq = con.execute(
        """
        SELECT
            event_seq,
            COUNT(*)::UBIGINT AS rows,
            SUM(CASE WHEN is_fraud_truth THEN 1 ELSE 0 END)::UBIGINT AS truth_positive_rows,
            SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END)::UBIGINT AS bank_positive_rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share
        FROM event_labels
        GROUP BY event_seq
        ORDER BY event_seq
        """
    ).fetchdf()
    write_csv(event_labels_by_seq, "event_labels_by_seq.csv")

    event_truth_bank_confusion = con.execute(
        """
        SELECT
            is_fraud_truth,
            is_fraud_bank_view,
            COUNT(*)::UBIGINT AS event_rows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share
        FROM event_labels
        GROUP BY is_fraud_truth, is_fraud_bank_view
        ORDER BY event_rows DESC
        """
    ).fetchdf()
    write_csv(event_truth_bank_confusion, "event_truth_bank_confusion.csv")

    event_stream_reconciliation = con.execute(
        """
        SELECT
            's3_event_stream_with_fraud_6B' AS surface,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            COUNT(DISTINCT event_seq)::UBIGINT AS event_seq_values,
            SUM(hash(flow_id, event_seq))::HUGEINT AS event_key_hash_sum
        FROM fraud_stream
        UNION ALL
        SELECT
            's4_event_labels_6B' AS surface,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            COUNT(DISTINCT event_seq)::UBIGINT AS event_seq_values,
            SUM(hash(flow_id, event_seq))::HUGEINT AS event_key_hash_sum
        FROM event_labels
        """
    ).fetchdf()
    write_csv(event_stream_reconciliation, "event_stream_reconciliation.csv")

    case_timeline_profile = con.execute(
        """
        SELECT
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT case_id)::UBIGINT AS cases,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            COUNT(DISTINCT case_event_type)::UBIGINT AS event_types,
            MIN(case_event_seq)::INTEGER AS min_case_event_seq,
            MAX(case_event_seq)::INTEGER AS max_case_event_seq,
            COUNT(DISTINCT seed)::UBIGINT AS seeds,
            COUNT(DISTINCT manifest_fingerprint)::UBIGINT AS manifest_fingerprints,
            COUNT(DISTINCT parameter_hash)::UBIGINT AS parameter_hashes,
            COUNT(DISTINCT scenario_id)::UBIGINT AS scenarios,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc,
            SUM(hash(case_id, case_event_seq))::HUGEINT AS case_event_key_hash_sum
        FROM case_timeline
        """
    ).fetchdf()
    write_csv(case_timeline_profile, "case_timeline_profile.csv")
    null_profile(con, "case_timeline", schemas["case_timeline"], "case_timeline")

    case_event_type_summary = con.execute(
        """
        SELECT
            case_event_type,
            COUNT(*)::UBIGINT AS rows,
            COUNT(DISTINCT case_id)::UBIGINT AS cases,
            COUNT(DISTINCT flow_id)::UBIGINT AS flows,
            MIN(case_event_seq)::INTEGER AS min_case_event_seq,
            MAX(case_event_seq)::INTEGER AS max_case_event_seq,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS row_share
        FROM case_timeline
        GROUP BY case_event_type
        ORDER BY rows DESC
        """
    ).fetchdf()
    write_csv(case_event_type_summary, "case_event_type_summary.csv")

    case_length_summary = con.execute(
        """
        WITH per_case AS (
            SELECT
                case_id,
                COUNT(*)::UBIGINT AS case_events,
                COUNT(DISTINCT flow_id)::UBIGINT AS flows,
                MIN(ts_utc) AS min_ts_utc,
                MAX(ts_utc) AS max_ts_utc
            FROM case_timeline
            GROUP BY case_id
        )
        SELECT
            case_events,
            COUNT(*)::UBIGINT AS cases,
            SUM(flows)::UBIGINT AS represented_flows,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS case_share
        FROM per_case
        GROUP BY case_events
        ORDER BY case_events
        """
    ).fetchdf()
    write_csv(case_length_summary, "case_length_summary.csv")

    case_truth_bank_reconciliation = con.execute(
        """
        WITH case_flows AS (
            SELECT DISTINCT seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id
            FROM case_timeline
        )
        SELECT
            t.is_fraud_truth,
            b.is_fraud_bank_view,
            t.fraud_label,
            b.bank_label,
            COUNT(*)::UBIGINT AS case_flows
        FROM case_flows c
        JOIN flow_truth t
          USING (seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id)
        JOIN flow_bank b
          USING (seed, manifest_fingerprint, parameter_hash, scenario_id, flow_id)
        GROUP BY t.is_fraud_truth, b.is_fraud_bank_view, t.fraud_label, b.bank_label
        ORDER BY case_flows DESC
        """
    ).fetchdf()
    write_csv(case_truth_bank_reconciliation, "case_truth_bank_reconciliation.csv")

    key_reconciliation = pd.DataFrame(
        [
            {
                "surface": "s3_flow_anchor_with_fraud_6B",
                "rows": int(con.execute("SELECT COUNT(*)::UBIGINT FROM fraud_anchor").fetchone()[0]),
                "key_type": "flow_id",
                "key_hash_sum": str(
                    con.execute("SELECT SUM(hash(flow_id))::HUGEINT FROM fraud_anchor").fetchone()[0]
                ),
            },
            {
                "surface": "s4_flow_truth_labels_6B",
                "rows": int(flow_truth_profile.loc[0, "rows"]),
                "key_type": "flow_id",
                "key_hash_sum": str(flow_truth_profile.loc[0, "flow_key_hash_sum"]),
            },
            {
                "surface": "s4_flow_bank_view_6B",
                "rows": int(flow_bank_profile.loc[0, "rows"]),
                "key_type": "flow_id",
                "key_hash_sum": str(flow_bank_profile.loc[0, "flow_key_hash_sum"]),
            },
            {
                "surface": "s3_event_stream_with_fraud_6B",
                "rows": int(
                    event_stream_reconciliation.loc[
                        event_stream_reconciliation["surface"] == "s3_event_stream_with_fraud_6B", "rows"
                    ].iloc[0]
                ),
                "key_type": "flow_id,event_seq",
                "key_hash_sum": str(
                    event_stream_reconciliation.loc[
                        event_stream_reconciliation["surface"] == "s3_event_stream_with_fraud_6B",
                        "event_key_hash_sum",
                    ].iloc[0]
                ),
            },
            {
                "surface": "s4_event_labels_6B",
                "rows": int(event_labels_profile.loc[0, "rows"]),
                "key_type": "flow_id,event_seq",
                "key_hash_sum": str(event_labels_profile.loc[0, "event_key_hash_sum"]),
            },
        ]
    )
    write_csv(key_reconciliation, "key_reconciliation.csv")

    summary = {
        "file_counts": file_counts,
        "profiles": {
            "flow_truth": flow_truth_profile.to_dict(orient="records"),
            "flow_bank": flow_bank_profile.to_dict(orient="records"),
            "event_labels": event_labels_profile.to_dict(orient="records"),
            "case_timeline": case_timeline_profile.to_dict(orient="records"),
        },
        "label_summaries": {
            "flow_truth": flow_truth_label_summary.to_dict(orient="records"),
            "flow_bank": flow_bank_label_summary.to_dict(orient="records"),
            "flow_truth_bank_confusion": flow_truth_bank_confusion.to_dict(orient="records"),
            "event_truth_bank_confusion": event_truth_bank_confusion.to_dict(orient="records"),
            "case_truth_bank_reconciliation": case_truth_bank_reconciliation.to_dict(orient="records"),
        },
    }
    (EXPORT_DIR / "truth_products_investigation_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
