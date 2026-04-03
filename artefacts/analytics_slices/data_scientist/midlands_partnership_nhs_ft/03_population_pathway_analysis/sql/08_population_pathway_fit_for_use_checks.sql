SELECT
    metric_name,
    metric_value
FROM (
    SELECT 'base_rows' AS metric_name, COUNT(*)::DOUBLE AS metric_value
    FROM parquet_scan($population_pathway_base_path)

    UNION ALL

    SELECT 'base_distinct_flow_id', COUNT(DISTINCT flow_id)::DOUBLE
    FROM parquet_scan($population_pathway_base_path)

    UNION ALL

    SELECT 'base_duplicate_flow_rows', (COUNT(*) - COUNT(DISTINCT flow_id))::DOUBLE
    FROM parquet_scan($population_pathway_base_path)

    UNION ALL

    SELECT 'base_null_flow_id_rows', COUNT(*)::DOUBLE
    FROM parquet_scan($population_pathway_base_path)
    WHERE flow_id IS NULL

    UNION ALL

    SELECT 'base_null_case_selected_rows', COUNT(*)::DOUBLE
    FROM parquet_scan($population_pathway_base_path)
    WHERE is_case_selected IS NULL

    UNION ALL

    SELECT 'base_case_selected_flows', SUM(is_case_selected)::DOUBLE
    FROM parquet_scan($population_pathway_base_path)

    UNION ALL

    SELECT 'base_case_selected_with_case_id', COUNT(*)::DOUBLE
    FROM parquet_scan($population_pathway_base_path)
    WHERE is_case_selected = 1 AND case_id IS NOT NULL

    UNION ALL

    SELECT 'base_case_selected_missing_case_id', COUNT(*)::DOUBLE
    FROM parquet_scan($population_pathway_base_path)
    WHERE is_case_selected = 1 AND case_id IS NULL

    UNION ALL

    SELECT 'cohort_rows', COUNT(*)::DOUBLE
    FROM parquet_scan($population_cohort_metrics_path)

    UNION ALL

    SELECT 'cohort_distinct_labels', COUNT(DISTINCT cohort_label)::DOUBLE
    FROM parquet_scan($population_cohort_metrics_path)

    UNION ALL

    SELECT 'reporting_rows', COUNT(*)::DOUBLE
    FROM parquet_scan($population_pathway_reporting_path)

    UNION ALL

    SELECT 'kpi_rows', COUNT(*)::DOUBLE
    FROM parquet_scan($population_pathway_kpis_path)
) t
ORDER BY metric_name;
