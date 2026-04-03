COPY (
SELECT
    week_role,
    COUNT(*) AS flow_rows,
    AVG(CAST(event_link_flag AS DOUBLE)) AS event_link_rate,
    AVG(CAST(case_row_link_flag AS DOUBLE)) AS case_row_link_rate,
    AVG(CAST(truth_link_flag AS DOUBLE)) AS truth_link_rate,
    AVG(CAST(bank_link_flag AS DOUBLE)) AS bank_link_rate,
    AVG(CASE WHEN case_row_link_flag = 1 THEN CAST(case_count > 1 AS DOUBLE) END) AS multi_case_flow_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(truth_bank_mismatch_flag AS DOUBLE) END) AS truth_bank_mismatch_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(is_fraud_bank_view AS DOUBLE) END) AS bank_case_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(is_fraud_truth AS DOUBLE) END) AS truth_case_rate
FROM parquet_scan($service_line_base_path)
GROUP BY week_role
ORDER BY CASE week_role WHEN 'prior' THEN 1 ELSE 2 END
) TO $service_line_discrepancy_output (FORMAT PARQUET, COMPRESSION ZSTD);
