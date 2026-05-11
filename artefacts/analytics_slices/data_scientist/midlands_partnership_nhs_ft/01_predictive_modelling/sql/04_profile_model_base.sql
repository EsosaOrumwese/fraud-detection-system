SELECT
    split_role,
    COUNT(*) AS flow_rows,
    SUM(CASE WHEN target_is_fraud_truth THEN 1 ELSE 0 END) AS fraud_truth_rows,
    AVG(CASE WHEN target_is_fraud_truth THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
    MIN(flow_ts_utc) AS min_flow_ts_utc,
    MAX(flow_ts_utc) AS max_flow_ts_utc,
    AVG(amount) AS avg_amount,
    AVG(log_amount) AS avg_log_amount
FROM parquet_scan($model_base_path)
GROUP BY split_role
ORDER BY
    CASE split_role
        WHEN 'train' THEN 1
        WHEN 'validation' THEN 2
        ELSE 3
    END;
