WITH case_timeline AS (
    SELECT
        case_id,
        flow_id,
        case_event_type,
        CAST(ts_utc AS TIMESTAMP) AS case_ts_utc
    FROM parquet_scan($case_timeline_files, filename := TRUE)
),
case_rollup AS (
    SELECT
        case_id,
        COUNT(DISTINCT flow_id) AS distinct_flows_per_case,
        MIN(case_ts_utc) AS first_case_ts_utc,
        MAX(case_ts_utc) AS last_case_ts_utc,
        MAX(CASE WHEN case_event_type = 'CASE_OPENED' THEN 1 ELSE 0 END) AS has_case_opened,
        MAX(CASE WHEN case_event_type = 'CASE_CLOSED' THEN 1 ELSE 0 END) AS has_case_closed,
        MAX(CASE WHEN case_event_type = 'CUSTOMER_DISPUTE_FILED' THEN 1 ELSE 0 END) AS has_customer_dispute,
        MAX(CASE WHEN case_event_type = 'CHARGEBACK_INITIATED' THEN 1 ELSE 0 END) AS has_chargeback_initiated,
        MAX(CASE WHEN case_event_type = 'CHARGEBACK_DECISION' THEN 1 ELSE 0 END) AS has_chargeback_decision,
        MAX(CASE WHEN case_event_type = 'DETECTION_EVENT_ATTACHED' THEN 1 ELSE 0 END) AS has_detection_event_attached
    FROM case_timeline
    GROUP BY case_id
),
flow_rollup AS (
    SELECT
        flow_id,
        COUNT(DISTINCT case_id) AS distinct_cases_per_flow
    FROM case_timeline
    GROUP BY flow_id
)
SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'flows_with_single_case' AS metric_name, CAST(SUM(CASE WHEN distinct_cases_per_flow = 1 THEN 1 ELSE 0 END) AS DOUBLE) AS metric_value FROM flow_rollup
    UNION ALL
    SELECT 'flows_with_multiple_cases', CAST(SUM(CASE WHEN distinct_cases_per_flow > 1 THEN 1 ELSE 0 END) AS DOUBLE) FROM flow_rollup
    UNION ALL
    SELECT 'cases_with_case_opened', CAST(SUM(has_case_opened) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_case_closed', CAST(SUM(has_case_closed) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_customer_dispute', CAST(SUM(has_customer_dispute) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_chargeback_initiated', CAST(SUM(has_chargeback_initiated) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_chargeback_decision', CAST(SUM(has_chargeback_decision) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_detection_event_attached', CAST(SUM(has_detection_event_attached) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'avg_case_lifecycle_hours', AVG((EPOCH(last_case_ts_utc) - EPOCH(first_case_ts_utc)) / 3600.0) FROM case_rollup
    UNION ALL
    SELECT 'max_case_lifecycle_hours', MAX((EPOCH(last_case_ts_utc) - EPOCH(first_case_ts_utc)) / 3600.0) FROM case_rollup
) m
ORDER BY metric_name;
