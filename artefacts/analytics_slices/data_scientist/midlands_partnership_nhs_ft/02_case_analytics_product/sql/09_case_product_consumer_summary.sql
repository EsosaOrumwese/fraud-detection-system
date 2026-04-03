COPY (
    SELECT
        split_role,
        pathway_stage,
        lifecycle_bucket,
        amount_band,
        COUNT(*) AS case_rows,
        SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS fraud_truth_cases,
        AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
        SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END) AS bank_positive_cases,
        AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_positive_rate,
        AVG(amount) AS avg_amount
    FROM parquet_scan($case_reporting_ready_path)
    GROUP BY
        split_role,
        pathway_stage,
        lifecycle_bucket,
        amount_band
    ORDER BY
        split_role,
        fraud_truth_rate DESC,
        case_rows DESC
) TO $case_product_consumer_summary_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
