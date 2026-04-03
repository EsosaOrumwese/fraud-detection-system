WITH event_flows AS (
    SELECT
        flow_id,
        MIN(CAST(ts_utc AS TIMESTAMP)) AS first_event_ts_utc
    FROM parquet_scan($event_files, filename := TRUE)
    GROUP BY 1
),
flow_anchor AS (
    SELECT
        flow_id,
        COUNT(*) AS anchor_rows
    FROM parquet_scan($anchor_files, filename := TRUE)
    GROUP BY 1
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
    SELECT
        flow_id,
        COUNT(*) AS truth_rows
    FROM parquet_scan($truth_files, filename := TRUE)
    GROUP BY 1
),
flow_bank AS (
    SELECT
        flow_id,
        COUNT(*) AS bank_rows
    FROM parquet_scan($bank_files, filename := TRUE)
    GROUP BY 1
),
base AS (
    SELECT
        e.flow_id,
        a.anchor_rows,
        c.case_id,
        c.distinct_cases,
        t.truth_rows,
        b.bank_rows
    FROM event_flows e
    LEFT JOIN flow_anchor a ON e.flow_id = a.flow_id
    LEFT JOIN case_rollup c ON e.flow_id = c.flow_id
    LEFT JOIN flow_truth t ON e.flow_id = t.flow_id
    LEFT JOIN flow_bank b ON e.flow_id = b.flow_id
)
SELECT 'event_flows_missing_anchor' AS check_name, SUM(CASE WHEN anchor_rows IS NULL THEN 1 ELSE 0 END)::DOUBLE AS check_value FROM base
UNION ALL
SELECT 'event_flows_missing_truth', SUM(CASE WHEN truth_rows IS NULL THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'event_flows_missing_bank_view', SUM(CASE WHEN bank_rows IS NULL THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'case_selected_flows_missing_case_id', SUM(CASE WHEN case_id IS NULL THEN 0 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'flows_with_multiple_case_ids', SUM(CASE WHEN COALESCE(distinct_cases, 0) > 1 THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'flows_with_duplicate_anchor_rows', SUM(CASE WHEN COALESCE(anchor_rows, 0) > 1 THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'flows_with_duplicate_truth_rows', SUM(CASE WHEN COALESCE(truth_rows, 0) > 1 THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'flows_with_duplicate_bank_rows', SUM(CASE WHEN COALESCE(bank_rows, 0) > 1 THEN 1 ELSE 0 END)::DOUBLE FROM base
UNION ALL
SELECT 'event_to_case_link_rate', AVG(CASE WHEN case_id IS NOT NULL THEN 1.0 ELSE 0.0 END) FROM base
UNION ALL
SELECT 'case_selected_truth_coverage_rate', AVG(CASE WHEN case_id IS NOT NULL AND truth_rows IS NOT NULL THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) FROM base
UNION ALL
SELECT 'case_selected_bank_coverage_rate', AVG(CASE WHEN case_id IS NOT NULL AND bank_rows IS NOT NULL THEN 1.0 WHEN case_id IS NOT NULL THEN 0.0 ELSE NULL END) FROM base
;
