WITH analytics_base AS (
    SELECT *
    FROM parquet_scan($case_analytics_product_path)
),
model_ready AS (
    SELECT *
    FROM parquet_scan($case_model_ready_path)
),
reporting_ready AS (
    SELECT *
    FROM parquet_scan($case_reporting_ready_path)
)
SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'analytics_base_rows' AS metric_name, CAST(COUNT(*) AS DOUBLE) AS metric_value FROM analytics_base
    UNION ALL
    SELECT 'analytics_base_distinct_case_id', CAST(COUNT(DISTINCT case_id) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'analytics_base_distinct_flow_id', CAST(COUNT(DISTINCT flow_id) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'analytics_base_duplicate_case_rows', CAST(COUNT(*) - COUNT(DISTINCT case_id) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'analytics_base_null_case_id_rows', CAST(SUM(CASE WHEN case_id IS NULL THEN 1 ELSE 0 END) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'analytics_base_null_flow_id_rows', CAST(SUM(CASE WHEN flow_id IS NULL THEN 1 ELSE 0 END) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'analytics_base_negative_lifecycle_rows', CAST(SUM(CASE WHEN lifecycle_hours < 0 THEN 1 ELSE 0 END) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'model_ready_rows', CAST(COUNT(*) AS DOUBLE) FROM model_ready
    UNION ALL
    SELECT 'model_ready_distinct_case_id', CAST(COUNT(DISTINCT case_id) AS DOUBLE) FROM model_ready
    UNION ALL
    SELECT 'reporting_ready_rows', CAST(COUNT(*) AS DOUBLE) FROM reporting_ready
    UNION ALL
    SELECT 'reporting_ready_distinct_case_id', CAST(COUNT(DISTINCT case_id) AS DOUBLE) FROM reporting_ready
    UNION ALL
    SELECT 'target_non_null_rows', CAST(SUM(CASE WHEN target_is_fraud_truth IS NOT NULL THEN 1 ELSE 0 END) AS DOUBLE) FROM analytics_base
    UNION ALL
    SELECT 'bank_view_non_null_rows', CAST(SUM(CASE WHEN is_fraud_bank_view IS NOT NULL THEN 1 ELSE 0 END) AS DOUBLE) FROM analytics_base
) m
ORDER BY metric_name;
