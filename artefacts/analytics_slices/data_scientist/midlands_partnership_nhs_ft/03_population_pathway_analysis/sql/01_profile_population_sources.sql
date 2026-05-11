WITH event_stream AS (
    SELECT
        flow_id,
        event_type,
        CAST(ts_utc AS TIMESTAMP) AS event_ts_utc
    FROM parquet_scan($event_files, filename := TRUE)
),
case_timeline AS (
    SELECT
        case_id,
        flow_id,
        case_event_type,
        CAST(ts_utc AS TIMESTAMP) AS case_ts_utc
    FROM parquet_scan($case_files, filename := TRUE)
)
SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'event_rows' AS metric_name, COUNT(*)::DOUBLE AS metric_value FROM event_stream
    UNION ALL
    SELECT 'event_distinct_flows', COUNT(DISTINCT flow_id)::DOUBLE FROM event_stream
    UNION ALL
    SELECT 'event_auth_request_rows', COUNT(*)::DOUBLE FROM event_stream WHERE event_type = 'AUTH_REQUEST'
    UNION ALL
    SELECT 'event_auth_response_rows', COUNT(*)::DOUBLE FROM event_stream WHERE event_type = 'AUTH_RESPONSE'
    UNION ALL
    SELECT 'case_event_rows', COUNT(*)::DOUBLE FROM case_timeline
    UNION ALL
    SELECT 'case_distinct_flows', COUNT(DISTINCT flow_id)::DOUBLE FROM case_timeline
    UNION ALL
    SELECT 'case_distinct_cases', COUNT(DISTINCT case_id)::DOUBLE FROM case_timeline
    UNION ALL
    SELECT 'case_opened_rows', COUNT(*)::DOUBLE FROM case_timeline WHERE case_event_type = 'CASE_OPENED'
    UNION ALL
    SELECT 'case_closed_rows', COUNT(*)::DOUBLE FROM case_timeline WHERE case_event_type = 'CASE_CLOSED'
) t
ORDER BY metric_name;
