WITH case_timeline AS (
    SELECT
        case_id,
        case_event_seq,
        flow_id,
        case_event_type,
        CAST(ts_utc AS TIMESTAMP) AS case_ts_utc
    FROM parquet_scan($case_timeline_files, filename := TRUE)
),
flow_truth AS (
    SELECT
        flow_id,
        is_fraud_truth
    FROM parquet_scan($truth_files, filename := TRUE)
),
flow_bank AS (
    SELECT
        flow_id,
        is_fraud_bank_view
    FROM parquet_scan($bank_files, filename := TRUE)
),
flow_anchor AS (
    SELECT
        flow_id,
        CAST(ts_utc AS TIMESTAMP) AS flow_ts_utc,
        amount
    FROM parquet_scan($anchor_files, filename := TRUE)
),
case_rollup AS (
    SELECT
        case_id,
        COUNT(*) AS chronology_rows,
        COUNT(DISTINCT flow_id) AS distinct_flows,
        MIN(case_ts_utc) AS first_case_ts_utc,
        MAX(case_ts_utc) AS last_case_ts_utc,
        SUM(CASE WHEN flow_id IS NULL THEN 1 ELSE 0 END) AS null_flow_rows
    FROM case_timeline
    GROUP BY case_id
),
case_flow_links AS (
    SELECT DISTINCT
        case_id,
        flow_id
    FROM case_timeline
    WHERE case_id IS NOT NULL
      AND flow_id IS NOT NULL
),
case_truth_linkage AS (
    SELECT
        cfl.case_id,
        COUNT(*) AS linked_flows,
        SUM(CASE WHEN ft.flow_id IS NOT NULL THEN 1 ELSE 0 END) AS flows_with_truth,
        SUM(CASE WHEN fb.flow_id IS NOT NULL THEN 1 ELSE 0 END) AS flows_with_bank_view,
        SUM(CASE WHEN fa.flow_id IS NOT NULL THEN 1 ELSE 0 END) AS flows_with_anchor,
        SUM(CASE WHEN ft.is_fraud_truth THEN 1 ELSE 0 END) AS truth_positive_flows,
        SUM(CASE WHEN fb.is_fraud_bank_view THEN 1 ELSE 0 END) AS bank_positive_flows
    FROM case_flow_links cfl
    LEFT JOIN flow_truth ft
        ON cfl.flow_id = ft.flow_id
    LEFT JOIN flow_bank fb
        ON cfl.flow_id = fb.flow_id
    LEFT JOIN flow_anchor fa
        ON cfl.flow_id = fa.flow_id
    GROUP BY cfl.case_id
)
SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'case_timeline_rows' AS metric_name, CAST(COUNT(*) AS DOUBLE) AS metric_value FROM case_timeline
    UNION ALL
    SELECT 'distinct_case_id_count', CAST(COUNT(DISTINCT case_id) AS DOUBLE) FROM case_timeline
    UNION ALL
    SELECT 'distinct_flow_id_in_case_timeline', CAST(COUNT(DISTINCT flow_id) AS DOUBLE) FROM case_timeline
    UNION ALL
    SELECT 'null_case_id_rows', CAST(SUM(CASE WHEN case_id IS NULL THEN 1 ELSE 0 END) AS DOUBLE) FROM case_timeline
    UNION ALL
    SELECT 'null_flow_id_rows', CAST(SUM(CASE WHEN flow_id IS NULL THEN 1 ELSE 0 END) AS DOUBLE) FROM case_timeline
    UNION ALL
    SELECT 'case_grain_rows', CAST(COUNT(*) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'avg_chronology_rows_per_case', AVG(chronology_rows) FROM case_rollup
    UNION ALL
    SELECT 'max_chronology_rows_per_case', CAST(MAX(chronology_rows) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'avg_distinct_flows_per_case', AVG(distinct_flows) FROM case_rollup
    UNION ALL
    SELECT 'max_distinct_flows_per_case', CAST(MAX(distinct_flows) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_single_flow', CAST(SUM(CASE WHEN distinct_flows = 1 THEN 1 ELSE 0 END) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_multiple_flows', CAST(SUM(CASE WHEN distinct_flows > 1 THEN 1 ELSE 0 END) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'avg_null_flow_rows_per_case', AVG(null_flow_rows) FROM case_rollup
    UNION ALL
    SELECT 'cases_with_all_linked_flows_in_truth', CAST(SUM(CASE WHEN linked_flows = flows_with_truth THEN 1 ELSE 0 END) AS DOUBLE) FROM case_truth_linkage
    UNION ALL
    SELECT 'cases_with_all_linked_flows_in_bank_view', CAST(SUM(CASE WHEN linked_flows = flows_with_bank_view THEN 1 ELSE 0 END) AS DOUBLE) FROM case_truth_linkage
    UNION ALL
    SELECT 'cases_with_all_linked_flows_in_anchor', CAST(SUM(CASE WHEN linked_flows = flows_with_anchor THEN 1 ELSE 0 END) AS DOUBLE) FROM case_truth_linkage
    UNION ALL
    SELECT 'cases_with_any_truth_positive_flow', CAST(SUM(CASE WHEN truth_positive_flows > 0 THEN 1 ELSE 0 END) AS DOUBLE) FROM case_truth_linkage
    UNION ALL
    SELECT 'cases_with_any_bank_positive_flow', CAST(SUM(CASE WHEN bank_positive_flows > 0 THEN 1 ELSE 0 END) AS DOUBLE) FROM case_truth_linkage
    UNION ALL
    SELECT 'min_case_ts_epoch', CAST(EPOCH(MIN(first_case_ts_utc)) AS DOUBLE) FROM case_rollup
    UNION ALL
    SELECT 'max_case_ts_epoch', CAST(EPOCH(MAX(last_case_ts_utc)) AS DOUBLE) FROM case_rollup
) m
ORDER BY metric_name;
