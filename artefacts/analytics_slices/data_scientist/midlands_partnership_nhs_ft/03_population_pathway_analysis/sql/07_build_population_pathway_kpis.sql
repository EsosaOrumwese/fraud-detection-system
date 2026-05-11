COPY (
    SELECT
        split_role,
        COUNT(*) AS population_flows,
        SUM(is_case_selected) AS case_selected_flows,
        AVG(CASE WHEN is_case_selected = 1 THEN 1.0 ELSE 0.0 END) AS case_selection_rate,
        SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS truth_positive_flows,
        AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
        SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END) AS bank_positive_flows,
        AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_positive_rate,
        AVG(lifecycle_hours) FILTER (WHERE is_case_selected = 1) AS avg_case_lifecycle_hours,
        MEDIAN(lifecycle_hours) FILTER (WHERE is_case_selected = 1) AS median_case_lifecycle_hours,
        AVG(hours_event_to_case_open) FILTER (WHERE is_case_selected = 1) AS avg_hours_event_to_case_open
    FROM parquet_scan($population_pathway_base_path)
    GROUP BY 1
    ORDER BY split_role
) TO $population_pathway_kpis_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
