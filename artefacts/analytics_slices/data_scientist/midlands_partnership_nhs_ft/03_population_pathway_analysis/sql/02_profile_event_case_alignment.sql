WITH event_flows AS (
    SELECT
        flow_id,
        MIN(CAST(ts_utc AS TIMESTAMP)) AS first_event_ts_utc,
        MAX(CAST(ts_utc AS TIMESTAMP)) AS last_event_ts_utc,
        COUNT(*) AS event_rows
    FROM parquet_scan($event_files, filename := TRUE)
    GROUP BY 1
),
case_open AS (
    SELECT
        flow_id,
        MIN(CAST(ts_utc AS TIMESTAMP)) FILTER (WHERE case_event_type = 'CASE_OPENED') AS case_opened_ts_utc,
        COUNT(DISTINCT case_id) AS distinct_cases
    FROM parquet_scan($case_files, filename := TRUE)
    GROUP BY 1
)
SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'linked_event_case_flows' AS metric_name, COUNT(*)::DOUBLE AS metric_value
    FROM event_flows e
    JOIN case_open c ON e.flow_id = c.flow_id

    UNION ALL

    SELECT 'exact_event_case_open_ts_match_flows', SUM(CASE WHEN e.first_event_ts_utc = c.case_opened_ts_utc THEN 1 ELSE 0 END)::DOUBLE
    FROM event_flows e
    JOIN case_open c ON e.flow_id = c.flow_id

    UNION ALL

    SELECT 'avg_seconds_event_to_case_open', AVG(DATEDIFF('second', e.first_event_ts_utc, c.case_opened_ts_utc))::DOUBLE
    FROM event_flows e
    JOIN case_open c ON e.flow_id = c.flow_id

    UNION ALL

    SELECT 'flows_with_multiple_cases', SUM(CASE WHEN distinct_cases > 1 THEN 1 ELSE 0 END)::DOUBLE
    FROM case_open
) t
ORDER BY metric_name;
