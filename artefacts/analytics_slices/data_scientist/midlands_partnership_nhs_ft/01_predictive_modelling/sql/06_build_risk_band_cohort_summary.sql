COPY (
    WITH scored AS (
        SELECT
            'validation' AS split_role,
            flow_id,
            predicted_probability,
            risk_band,
            target_is_fraud_truth,
            fraud_label,
            is_fraud_bank_view,
            bank_label
        FROM parquet_scan($validation_scores_path)
        UNION ALL
        SELECT
            'test' AS split_role,
            flow_id,
            predicted_probability,
            risk_band,
            target_is_fraud_truth,
            fraud_label,
            is_fraud_bank_view,
            bank_label
        FROM parquet_scan($test_scores_path)
    )
    SELECT
        split_role,
        risk_band,
        COUNT(*) AS rows,
        SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS fraud_truth_rows,
        AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
        AVG(predicted_probability) AS avg_predicted_probability,
        SUM(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END) AS bank_view_positive_rows,
        AVG(CASE WHEN is_fraud_bank_view THEN 1.0 ELSE 0.0 END) AS bank_view_positive_rate
    FROM scored
    GROUP BY split_role, risk_band
    ORDER BY split_role, risk_band
) TO $cohort_summary_output
(
    FORMAT PARQUET,
    COMPRESSION ZSTD
);
