from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = REPO_ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
EXPORT_ROOT = (
    REPO_ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_streams"
)
BRANCH_EXPORT = EXPORT_ROOT / "branches" / "time_coverage_and_april_spillover"
TRAFFIC_EXPORT = (
    REPO_ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "traffic_primitives"
)


STREAMS = {
    "baseline": RUN_ROOT / "data" / "layer3" / "6B" / "s2_event_stream_baseline_6B",
    "with_fraud": RUN_ROOT / "data" / "layer3" / "6B" / "s3_event_stream_with_fraud_6B",
}


def parquet_glob(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def export(con: duckdb.DuckDBPyConnection, sql: str, path: Path) -> pd.DataFrame:
    df = con.execute(sql).fetchdf()
    df.to_csv(path, index=False)
    return df


def main() -> None:
    BRANCH_EXPORT.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='6GB'")

    for name, stream_path in STREAMS.items():
        con.execute(
            f"""
            CREATE OR REPLACE VIEW {name}_stream AS
            SELECT *
            FROM read_parquet('{parquet_glob(stream_path)}', hive_partitioning = true)
            """
        )

    profile_rows = []
    for stream_name in STREAMS:
        profile = read_csv_if_exists(EXPORT_ROOT / f"{stream_name}_profile.csv")
        month = read_csv_if_exists(EXPORT_ROOT / f"{stream_name}_month_summary.csv")
        if not profile.empty:
            profile_rows.append(
                {
                    "stream": stream_name,
                    "rows": int(profile.loc[0, "rows"]),
                    "min_ts_utc": profile.loc[0, "min_ts_utc"],
                    "max_ts_utc": profile.loc[0, "max_ts_utc"],
                    "april_rows": int(
                        month.loc[month["utc_month"] == "2026-04", "rows"].iloc[0]
                    )
                    if not month.empty and (month["utc_month"] == "2026-04").any()
                    else None,
                }
            )

    arrival_profile = read_csv_if_exists(TRAFFIC_EXPORT / "arrival_events_profile.csv")
    if not arrival_profile.empty:
        profile_rows.append(
            {
                "stream": "arrival_events_5B",
                "rows": int(arrival_profile.loc[0, "rows"]),
                "min_ts_utc": arrival_profile.loc[0, "min_ts_utc"],
                "max_ts_utc": arrival_profile.loc[0, "max_ts_utc"],
                "april_rows": 0,
            }
        )
    pd.DataFrame(profile_rows).to_csv(BRANCH_EXPORT / "time_horizon_profile.csv", index=False)

    monthly_frames = []
    for stream_name in STREAMS:
        month = read_csv_if_exists(EXPORT_ROOT / f"{stream_name}_month_summary.csv")
        if not month.empty:
            month.insert(0, "stream", stream_name)
            monthly_frames.append(month)
    arrival_month = read_csv_if_exists(TRAFFIC_EXPORT / "arrival_events_month_summary.csv")
    if not arrival_month.empty:
        arrival_month = arrival_month.rename(columns={"merchants": "active_merchants"})
        arrival_month.insert(0, "stream", "arrival_events_5B")
        monthly_frames.append(arrival_month)
    pd.concat(monthly_frames, ignore_index=True, sort=False).to_csv(
        BRANCH_EXPORT / "monthly_boundary_counts.csv", index=False
    )

    april_side_frames = []
    boundary_day_frames = []
    boundary_minute_frames = []
    terminal_event_frames = []

    for stream_name in STREAMS:
        april_side_frames.append(
            export(
                con,
                f"""
                SELECT
                    '{stream_name}' AS stream,
                    event_seq,
                    event_type,
                    COUNT(*) AS rows,
                    COUNT(DISTINCT flow_id) AS distinct_flows,
                    MIN(ts_utc) AS min_ts_utc,
                    MAX(ts_utc) AS max_ts_utc,
                    SUM(amount) AS total_amount,
                    AVG(amount) AS mean_amount
                FROM {stream_name}_stream
                WHERE ts_utc >= '2026-04-01'
                GROUP BY event_seq, event_type
                ORDER BY event_seq, event_type
                """,
                BRANCH_EXPORT / f"{stream_name}_april_rows_by_event_side.csv",
            )
        )

        boundary_day_frames.append(
            export(
                con,
                f"""
                SELECT
                    '{stream_name}' AS stream,
                    SUBSTR(ts_utc, 1, 10) AS utc_date,
                    event_seq,
                    event_type,
                    COUNT(*) AS rows,
                    COUNT(DISTINCT flow_id) AS distinct_flows,
                    MIN(ts_utc) AS min_ts_utc,
                    MAX(ts_utc) AS max_ts_utc
                FROM {stream_name}_stream
                WHERE ts_utc >= '2026-03-30'
                GROUP BY utc_date, event_seq, event_type
                ORDER BY utc_date, event_seq, event_type
                """,
                BRANCH_EXPORT / f"{stream_name}_boundary_days_by_event_side.csv",
            )
        )

        boundary_minute_frames.append(
            export(
                con,
                f"""
                SELECT
                    '{stream_name}' AS stream,
                    SUBSTR(ts_utc, 1, 16) AS utc_minute,
                    event_seq,
                    event_type,
                    COUNT(*) AS rows,
                    COUNT(DISTINCT flow_id) AS distinct_flows,
                    MIN(ts_utc) AS min_ts_utc,
                    MAX(ts_utc) AS max_ts_utc
                FROM {stream_name}_stream
                WHERE ts_utc >= '2026-03-31T23:50'
                  AND ts_utc < '2026-04-01T00:10'
                GROUP BY utc_minute, event_seq, event_type
                ORDER BY utc_minute, event_seq, event_type
                """,
                BRANCH_EXPORT / f"{stream_name}_boundary_minutes_by_event_side.csv",
            )
        )

        terminal_event_frames.append(
            export(
                con,
                f"""
                WITH ranked AS (
                    SELECT
                        '{stream_name}' AS stream,
                        flow_id,
                        event_seq,
                        event_type,
                        ts_utc,
                        amount,
                        ROW_NUMBER() OVER (ORDER BY ts_utc DESC, flow_id DESC, event_seq DESC) AS recency_rank
                    FROM {stream_name}_stream
                    WHERE ts_utc >= '2026-04-01'
                )
                SELECT *
                FROM ranked
                WHERE recency_rank <= 25
                ORDER BY recency_rank
                """,
                BRANCH_EXPORT / f"{stream_name}_latest_april_events_sample.csv",
            )
        )

    pd.concat(april_side_frames, ignore_index=True).to_csv(
        BRANCH_EXPORT / "april_rows_by_event_side.csv", index=False
    )
    pd.concat(boundary_day_frames, ignore_index=True).to_csv(
        BRANCH_EXPORT / "boundary_days_by_event_side.csv", index=False
    )
    pd.concat(boundary_minute_frames, ignore_index=True).to_csv(
        BRANCH_EXPORT / "boundary_minutes_by_event_side.csv", index=False
    )
    pd.concat(terminal_event_frames, ignore_index=True).to_csv(
        BRANCH_EXPORT / "latest_april_events_sample.csv", index=False
    )

    april_flow_shape = export(
        con,
        """
        WITH april_flows AS (
            SELECT 'baseline' AS stream, flow_id
            FROM baseline_stream
            WHERE ts_utc >= '2026-04-01'
            UNION ALL
            SELECT 'with_fraud' AS stream, flow_id
            FROM with_fraud_stream
            WHERE ts_utc >= '2026-04-01'
        ),
        all_events_for_april_flows AS (
            SELECT
                af.stream,
                af.flow_id,
                b.event_seq,
                b.event_type,
                b.ts_utc
            FROM april_flows af
            JOIN baseline_stream b
              ON af.flow_id = b.flow_id
            WHERE af.stream = 'baseline'
            UNION ALL
            SELECT
                af.stream,
                af.flow_id,
                w.event_seq,
                w.event_type,
                w.ts_utc
            FROM april_flows af
            JOIN with_fraud_stream w
              ON af.flow_id = w.flow_id
            WHERE af.stream = 'with_fraud'
        )
        SELECT
            stream,
            COUNT(DISTINCT flow_id) AS april_touched_flows,
            COUNT(*) AS event_rows_for_april_touched_flows,
            SUM(CASE WHEN event_seq = 0 THEN 1 ELSE 0 END) AS request_rows,
            SUM(CASE WHEN event_seq = 1 THEN 1 ELSE 0 END) AS response_rows,
            SUM(CASE WHEN ts_utc < '2026-04-01' THEN 1 ELSE 0 END) AS pre_april_event_rows,
            SUM(CASE WHEN ts_utc >= '2026-04-01' THEN 1 ELSE 0 END) AS april_event_rows,
            MIN(ts_utc) AS min_ts_utc,
            MAX(ts_utc) AS max_ts_utc
        FROM all_events_for_april_flows
        GROUP BY stream
        ORDER BY stream
        """,
        BRANCH_EXPORT / "april_touched_flow_shape.csv",
    )

    latency_frames = []
    for stream_name in STREAMS:
        latency_frames.append(
            export(
                con,
                f"""
                WITH april_responses AS (
                    SELECT
                        flow_id,
                        ts_utc AS response_ts_utc,
                        amount AS response_amount
                    FROM {stream_name}_stream
                    WHERE ts_utc >= '2026-04-01'
                      AND event_seq = 1
                ),
                paired_requests AS (
                    SELECT
                        r.flow_id,
                        q.ts_utc AS request_ts_utc,
                        r.response_ts_utc,
                        q.amount AS request_amount,
                        r.response_amount,
                        DATE_DIFF(
                            'millisecond',
                            STRPTIME(q.ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ'),
                            STRPTIME(r.response_ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ')
                        ) / 1000.0 AS request_to_response_seconds
                    FROM april_responses r
                    JOIN {stream_name}_stream q
                      ON r.flow_id = q.flow_id
                     AND q.event_seq = 0
                )
                SELECT
                    '{stream_name}' AS stream,
                    COUNT(*) AS paired_flows,
                    MIN(request_ts_utc) AS min_request_ts_utc,
                    MAX(request_ts_utc) AS max_request_ts_utc,
                    MIN(response_ts_utc) AS min_response_ts_utc,
                    MAX(response_ts_utc) AS max_response_ts_utc,
                    MIN(request_to_response_seconds) AS min_request_to_response_seconds,
                    QUANTILE_CONT(request_to_response_seconds, 0.25) AS p25_request_to_response_seconds,
                    MEDIAN(request_to_response_seconds) AS median_request_to_response_seconds,
                    QUANTILE_CONT(request_to_response_seconds, 0.75) AS p75_request_to_response_seconds,
                    MAX(request_to_response_seconds) AS max_request_to_response_seconds,
                    AVG(request_to_response_seconds) AS mean_request_to_response_seconds
                FROM paired_requests
                """,
                BRANCH_EXPORT / f"{stream_name}_april_touched_flow_latency_summary.csv",
            )
        )

    pd.concat(latency_frames, ignore_index=True).to_csv(
        BRANCH_EXPORT / "april_touched_flow_latency_summary.csv", index=False
    )

    summary = {
        "time_horizon_profile": profile_rows,
        "april_rows_by_event_side": pd.concat(april_side_frames, ignore_index=True).to_dict(
            orient="records"
        ),
        "april_touched_flow_shape": april_flow_shape.to_dict(orient="records"),
        "april_touched_flow_latency": pd.concat(latency_frames, ignore_index=True).to_dict(
            orient="records"
        ),
    }
    (BRANCH_EXPORT / "time_coverage_and_april_spillover_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
