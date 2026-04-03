COPY (
    WITH model_flows AS (
        SELECT DISTINCT
            flow_id
        FROM parquet_scan($model_base_path)
    ),
    case_opened AS (
        SELECT
            CAST(ts_utc AS TIMESTAMP) AS case_ts_utc,
            flow_id,
            case_id
        FROM parquet_scan($case_timeline_glob)
        WHERE case_event_type = 'CASE_OPENED'
    )
    SELECT
        CAST(case_ts_utc AS DATE) AS case_open_date_utc,
        COUNT(*) AS case_open_rows,
        COUNT(DISTINCT case_id) AS distinct_cases,
        COUNT(DISTINCT co.flow_id) AS distinct_flows
    FROM case_opened co
    INNER JOIN model_flows mf
        ON co.flow_id = mf.flow_id
    GROUP BY 1
    ORDER BY 1
) TO $daily_case_opens_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
