COPY (
    SELECT
        split_role,
        pathway_stage,
        COUNT(*) AS flow_rows,
        SUM(is_case_selected) AS case_selected_flows,
        AVG(CASE WHEN is_case_selected = 1 THEN 1.0 ELSE 0.0 END) AS case_selection_rate,
        AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
        AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_positive_rate,
        AVG(lifecycle_hours) AS avg_lifecycle_hours,
        MEDIAN(lifecycle_hours) AS median_lifecycle_hours,
        AVG(amount) AS avg_amount
    FROM parquet_scan($population_pathway_base_path)
    GROUP BY 1, 2
    ORDER BY split_role, pathway_stage
) TO $population_pathway_reporting_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
