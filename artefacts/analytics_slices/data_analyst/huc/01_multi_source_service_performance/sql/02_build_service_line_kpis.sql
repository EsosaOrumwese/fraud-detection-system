COPY (
SELECT
    week_role,
    MIN(week_start_date) AS week_start_date,
    MAX(week_start_date) AS week_end_date,
    SUM(event_rows) AS entry_event_rows,
    COUNT(*) AS flow_rows,
    AVG(CAST(has_case_opened AS DOUBLE)) AS case_open_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(long_lifecycle_flag AS DOUBLE) END) AS long_lifecycle_share,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(very_long_lifecycle_flag AS DOUBLE) END) AS very_long_lifecycle_share,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(is_fraud_truth AS DOUBLE) END) AS case_truth_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(is_fraud_bank_view AS DOUBLE) END) AS bank_case_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN CAST(truth_bank_mismatch_flag AS DOUBLE) END) AS truth_bank_mismatch_rate,
    AVG(CASE WHEN has_case_opened = 1 THEN lifecycle_hours END) AS avg_lifecycle_hours
FROM parquet_scan($service_line_base_path)
GROUP BY week_role
ORDER BY CASE week_role WHEN 'prior' THEN 1 ELSE 2 END
) TO $service_line_kpis_output (FORMAT PARQUET, COMPRESSION ZSTD);
