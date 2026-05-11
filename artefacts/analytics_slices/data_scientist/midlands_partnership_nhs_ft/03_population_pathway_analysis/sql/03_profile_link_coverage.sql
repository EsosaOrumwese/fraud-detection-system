WITH event_flows AS (
    SELECT DISTINCT flow_id
    FROM parquet_scan($event_files, filename := TRUE)
),
anchor_flows AS (
    SELECT DISTINCT flow_id
    FROM parquet_scan($anchor_files, filename := TRUE)
),
case_flows AS (
    SELECT DISTINCT flow_id
    FROM parquet_scan($case_files, filename := TRUE)
),
truth_flows AS (
    SELECT DISTINCT flow_id
    FROM parquet_scan($truth_files, filename := TRUE)
),
bank_flows AS (
    SELECT DISTINCT flow_id
    FROM parquet_scan($bank_files, filename := TRUE)
)
SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'event_flows_with_anchor' AS metric_name, COUNT(*)::DOUBLE AS metric_value
    FROM event_flows e
    JOIN anchor_flows a ON e.flow_id = a.flow_id

    UNION ALL

    SELECT 'event_flows_with_case' AS metric_name, COUNT(*)::DOUBLE
    FROM event_flows e
    JOIN case_flows c ON e.flow_id = c.flow_id

    UNION ALL

    SELECT 'event_flows_with_truth' AS metric_name, COUNT(*)::DOUBLE
    FROM event_flows e
    JOIN truth_flows t ON e.flow_id = t.flow_id

    UNION ALL

    SELECT 'event_flows_with_bank_view' AS metric_name, COUNT(*)::DOUBLE
    FROM event_flows e
    JOIN bank_flows b ON e.flow_id = b.flow_id

    UNION ALL

    SELECT 'case_flows_with_truth' AS metric_name, COUNT(*)::DOUBLE
    FROM case_flows c
    JOIN truth_flows t ON c.flow_id = t.flow_id

    UNION ALL

    SELECT 'case_flows_with_bank_view' AS metric_name, COUNT(*)::DOUBLE
    FROM case_flows c
    JOIN bank_flows b ON c.flow_id = b.flow_id
) t
ORDER BY metric_name;
