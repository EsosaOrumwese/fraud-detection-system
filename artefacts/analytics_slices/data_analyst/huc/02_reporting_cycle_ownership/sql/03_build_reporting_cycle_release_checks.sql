COPY (
    WITH kpi_counts AS (
        SELECT COUNT(*) AS period_rows
        FROM read_parquet($kpi_path)
    ),
    segment_counts AS (
        SELECT COUNT(*) AS current_segment_rows
        FROM read_parquet($segment_path)
        WHERE week_role = 'current'
    ),
    discrepancy_counts AS (
        SELECT COUNT(*) AS discrepancy_rows
        FROM read_parquet($discrepancy_path)
    )
    SELECT
        'period_rows_present' AS check_name,
        CAST(period_rows = 2 AS INTEGER) AS passed_flag,
        CAST(period_rows AS DOUBLE) AS observed_value,
        2.0 AS expected_value
    FROM kpi_counts
    UNION ALL
    SELECT
        'current_segments_present' AS check_name,
        CAST(current_segment_rows = 4 AS INTEGER) AS passed_flag,
        CAST(current_segment_rows AS DOUBLE) AS observed_value,
        4.0 AS expected_value
    FROM segment_counts
    UNION ALL
    SELECT
        'discrepancy_rows_present' AS check_name,
        CAST(discrepancy_rows = 2 AS INTEGER) AS passed_flag,
        CAST(discrepancy_rows AS DOUBLE) AS observed_value,
        2.0 AS expected_value
    FROM discrepancy_counts
) TO $output_path (FORMAT PARQUET);
