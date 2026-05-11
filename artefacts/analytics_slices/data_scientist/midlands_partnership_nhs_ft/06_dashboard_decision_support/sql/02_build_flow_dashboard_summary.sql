COPY (
    WITH base AS (
        SELECT *
        FROM parquet_scan($dashboard_base_path)
    ),
    headline AS (
        SELECT
            'executive_overview' AS page_name,
            'headline_kpi' AS panel_name,
            split_role,
            metric_name,
            metric_value,
            CAST(NULL AS DATE) AS metric_date,
            CAST(NULL AS VARCHAR) AS category
        FROM (
            SELECT
                split_role,
                COUNT(*) AS flows_in_scope,
                SUM(CASE WHEN risk_band = 'High' THEN 1 ELSE 0 END) AS high_band_flows,
                SUM(CASE WHEN risk_band = 'Medium' THEN 1 ELSE 0 END) AS medium_band_flows,
                AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
                AVG(CASE WHEN has_case_opened = 1 THEN 1.0 ELSE 0.0 END) AS case_open_rate
            FROM base
            GROUP BY 1
        ) src
        UNPIVOT(metric_value FOR metric_name IN (
            flows_in_scope,
            high_band_flows,
            medium_band_flows,
            fraud_truth_rate,
            case_open_rate
        ))
    ),
    high_band_rates AS (
        SELECT
            'executive_overview' AS page_name,
            'headline_kpi' AS panel_name,
            split_role,
            'high_band_truth_rate' AS metric_name,
            AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS metric_value,
            CAST(NULL AS DATE) AS metric_date,
            CAST(NULL AS VARCHAR) AS category
        FROM base
        WHERE risk_band = 'High'
        GROUP BY 1, 2, 3
    ),
    trend AS (
        SELECT
            'executive_overview' AS page_name,
            'weekly_trend' AS panel_name,
            split_role,
            'high_medium_share' AS metric_name,
            AVG(CASE WHEN risk_band IN ('High', 'Medium') THEN 1.0 ELSE 0.0 END) AS metric_value,
            CAST(flow_week_utc AS DATE) AS metric_date,
            'all_scored_flows' AS category
        FROM base
        GROUP BY 1, 2, 3, 6, 7
    ),
    cohort_concentration AS (
        SELECT
            'executive_overview' AS page_name,
            'cohort_concentration' AS panel_name,
            'test' AS split_role,
            'flow_share' AS metric_name,
            COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS metric_value,
            CAST(NULL AS DATE) AS metric_date,
            cohort_label AS category
        FROM base
        WHERE split_role = 'test'
        GROUP BY 1, 2, 3, 4, 6, 7
    ),
    workflow_pathway AS (
        SELECT
            'workflow_and_prioritisation' AS page_name,
            'pathway_stage_truth_rate' AS panel_name,
            'test' AS split_role,
            'fraud_truth_rate' AS metric_name,
            AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS metric_value,
            CAST(NULL AS DATE) AS metric_date,
            pathway_stage AS category
        FROM base
        WHERE split_role = 'test'
        GROUP BY 1, 2, 3, 4, 6, 7
    ),
    workflow_band AS (
        SELECT
            'workflow_and_prioritisation' AS page_name,
            'risk_band_workload' AS panel_name,
            'test' AS split_role,
            'flow_rows' AS metric_name,
            COUNT(*) AS metric_value,
            CAST(NULL AS DATE) AS metric_date,
            risk_band AS category
        FROM base
        WHERE split_role = 'test'
        GROUP BY 1, 2, 3, 4, 6, 7
    ),
    explanation_cohort AS (
        SELECT
            'explanation_and_drillthrough' AS page_name,
            'cohort_truth_rate' AS panel_name,
            'test' AS split_role,
            'fraud_truth_rate' AS metric_name,
            AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS metric_value,
            CAST(NULL AS DATE) AS metric_date,
            cohort_label AS category
        FROM base
        WHERE split_role = 'test'
        GROUP BY 1, 2, 3, 4, 6, 7
    )
    SELECT * FROM headline
    UNION ALL
    SELECT * FROM high_band_rates
    UNION ALL
    SELECT * FROM trend
    UNION ALL
    SELECT * FROM cohort_concentration
    UNION ALL
    SELECT * FROM workflow_pathway
    UNION ALL
    SELECT * FROM workflow_band
    UNION ALL
    SELECT * FROM explanation_cohort
) TO $dashboard_summary_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
