COPY (
    WITH agg_counts AS (
        SELECT COUNT(*) AS agg_rows
        FROM read_parquet($agg_path)
    ),
    summary_counts AS (
        SELECT
            COUNT(*) AS summary_rows,
            MIN(CASE WHEN flow_rows IS NOT NULL
                         AND case_open_rate IS NOT NULL
                         AND case_truth_rate IS NOT NULL
                         AND truth_link_rate IS NOT NULL
                     THEN 1 ELSE 0 END) AS summary_complete_flag
        FROM read_parquet($summary_path)
    ),
    follow_up_counts AS (
        SELECT COUNT(*) AS follow_up_rows
        FROM read_parquet($follow_up_path)
    )
    SELECT
        'month_band_rows_present' AS check_name,
        CAST(agg_rows = 8 AS INTEGER) AS passed_flag,
        CAST(agg_rows AS DOUBLE) AS observed_value,
        8.0 AS expected_value
    FROM agg_counts
    UNION ALL
    SELECT
        'monthly_summary_present' AS check_name,
        CAST(summary_rows = 1 AS INTEGER) AS passed_flag,
        CAST(summary_rows AS DOUBLE) AS observed_value,
        1.0 AS expected_value
    FROM summary_counts
    UNION ALL
    SELECT
        'monthly_summary_complete' AS check_name,
        CAST(summary_complete_flag = 1 AS INTEGER) AS passed_flag,
        CAST(summary_complete_flag AS DOUBLE) AS observed_value,
        1.0 AS expected_value
    FROM summary_counts
    UNION ALL
    SELECT
        'follow_up_rows_present' AS check_name,
        CAST(follow_up_rows = 4 AS INTEGER) AS passed_flag,
        CAST(follow_up_rows AS DOUBLE) AS observed_value,
        4.0 AS expected_value
    FROM follow_up_counts
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
