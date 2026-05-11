WITH event_flows AS (
    SELECT
        flow_id,
        MIN(CAST(ts_utc AS TIMESTAMP)) AS first_event_ts_utc
    FROM parquet_scan($event_files, filename := TRUE)
    GROUP BY 1
),
flow_anchor AS (
    SELECT DISTINCT flow_id
    FROM parquet_scan($anchor_files, filename := TRUE)
),
case_rollup AS (
    SELECT
        flow_id,
        MIN(case_id) AS case_id,
        COUNT(DISTINCT case_id) AS distinct_cases
    FROM parquet_scan($case_files, filename := TRUE)
    GROUP BY 1
),
flow_truth AS (
    SELECT DISTINCT flow_id, is_fraud_truth, fraud_label
    FROM parquet_scan($truth_files, filename := TRUE)
),
flow_bank AS (
    SELECT DISTINCT flow_id, is_fraud_bank_view, bank_label
    FROM parquet_scan($bank_files, filename := TRUE)
),
base AS (
    SELECT
        e.flow_id,
        c.case_id,
        c.distinct_cases,
        t.is_fraud_truth,
        t.fraud_label,
        b.is_fraud_bank_view,
        b.bank_label,
        NTILE(10) OVER (ORDER BY e.first_event_ts_utc, e.flow_id) AS time_split_decile
    FROM event_flows e
    LEFT JOIN flow_anchor a ON e.flow_id = a.flow_id
    LEFT JOIN case_rollup c ON e.flow_id = c.flow_id
    LEFT JOIN flow_truth t ON e.flow_id = t.flow_id
    LEFT JOIN flow_bank b ON e.flow_id = b.flow_id
)
SELECT 'event_distinct_flows' AS metric_name, COUNT(*)::DOUBLE AS metric_value FROM event_flows
UNION ALL
SELECT 'anchor_distinct_flows', COUNT(*)::DOUBLE FROM flow_anchor
UNION ALL
SELECT 'case_distinct_flows', COUNT(*)::DOUBLE FROM case_rollup
UNION ALL
SELECT 'truth_distinct_flows', COUNT(*)::DOUBLE FROM flow_truth
UNION ALL
SELECT 'bank_distinct_flows', COUNT(*)::DOUBLE FROM flow_bank
UNION ALL
SELECT 'case_selected_flows', COUNT(*)::DOUBLE FROM base WHERE case_id IS NOT NULL
UNION ALL
SELECT 'test_case_selected_flows', COUNT(*)::DOUBLE FROM base WHERE case_id IS NOT NULL AND time_split_decile > 8
UNION ALL
SELECT 'flows_with_multiple_cases', SUM(CASE WHEN distinct_cases > 1 THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'truth_positive_case_selected_flows', SUM(CASE WHEN case_id IS NOT NULL AND COALESCE(is_fraud_truth, FALSE) THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'bank_positive_case_selected_flows', SUM(CASE WHEN case_id IS NOT NULL AND COALESCE(is_fraud_bank_view, FALSE) THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'truth_negative_bank_positive_case_selected_flows',
       SUM(CASE WHEN case_id IS NOT NULL AND NOT COALESCE(is_fraud_truth, FALSE) AND COALESCE(is_fraud_bank_view, FALSE) THEN 1 ELSE 0 END)::DOUBLE
FROM base
UNION ALL
SELECT 'truth_positive_bank_negative_case_selected_flows',
       SUM(CASE WHEN case_id IS NOT NULL AND COALESCE(is_fraud_truth, FALSE) AND NOT COALESCE(is_fraud_bank_view, FALSE) THEN 1 ELSE 0 END)::DOUBLE
FROM base
;
