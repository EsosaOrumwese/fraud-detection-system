COPY (
    WITH discrepancy_counts AS (
        SELECT COUNT(*) AS discrepancy_rows
        FROM read_parquet($discrepancy_path)
    ),
    gap_check AS (
        SELECT
            MAX(CASE WHEN week_role = 'current' THEN absolute_gap END) AS current_gap
        FROM read_parquet($discrepancy_path)
    ),
    before_after_counts AS (
        SELECT COUNT(*) AS before_after_rows
        FROM read_parquet($before_after_path)
    )
    SELECT
        'two_period_rows_present' AS check_name,
        CAST(discrepancy_rows = 2 AS INTEGER) AS passed_flag,
        CAST(discrepancy_rows AS DOUBLE) AS observed_value,
        2.0 AS expected_value
    FROM discrepancy_counts
    UNION ALL
    SELECT
        'material_gap_detected' AS check_name,
        CAST(current_gap >= 0.01 AS INTEGER) AS passed_flag,
        CAST(current_gap AS DOUBLE) AS observed_value,
        0.01 AS expected_value
    FROM gap_check
    UNION ALL
    SELECT
        'before_after_rows_present' AS check_name,
        CAST(before_after_rows = 6 AS INTEGER) AS passed_flag,
        CAST(before_after_rows AS DOUBLE) AS observed_value,
        6.0 AS expected_value
    FROM before_after_counts
) TO $output_path (FORMAT PARQUET);
