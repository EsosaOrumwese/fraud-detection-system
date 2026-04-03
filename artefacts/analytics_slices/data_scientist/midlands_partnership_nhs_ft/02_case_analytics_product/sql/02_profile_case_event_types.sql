WITH case_timeline AS (
    SELECT
        case_id,
        flow_id,
        case_event_type,
        CAST(ts_utc AS TIMESTAMP) AS case_ts_utc
    FROM parquet_scan($case_timeline_files, filename := TRUE)
)
SELECT
    case_event_type,
    COUNT(*) AS event_rows,
    COUNT(DISTINCT case_id) AS distinct_cases,
    COUNT(DISTINCT flow_id) AS distinct_flows,
    MIN(case_ts_utc) AS min_case_ts_utc,
    MAX(case_ts_utc) AS max_case_ts_utc
FROM case_timeline
GROUP BY case_event_type
ORDER BY event_rows DESC, case_event_type;
