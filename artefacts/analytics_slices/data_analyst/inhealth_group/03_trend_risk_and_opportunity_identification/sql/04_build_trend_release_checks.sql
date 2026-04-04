COPY (
    SELECT
        'three_month_rows_present' AS check_name,
        CASE WHEN COUNT(*) = 3 THEN 1 ELSE 0 END AS passed_flag,
        COUNT(*)::DOUBLE AS observed_value,
        3::DOUBLE AS expected_value
    FROM read_parquet($trend_path)

    UNION ALL

    SELECT
        'twelve_focus_rows_present' AS check_name,
        CASE WHEN COUNT(*) = 12 THEN 1 ELSE 0 END AS passed_flag,
        COUNT(*)::DOUBLE AS observed_value,
        12::DOUBLE AS expected_value
    FROM read_parquet($focus_path)

    UNION ALL

    SELECT
        'monthly_priority_rows_present' AS check_name,
        CASE WHEN SUM(priority_attention_flag) = 3 THEN 1 ELSE 0 END AS passed_flag,
        SUM(priority_attention_flag)::DOUBLE AS observed_value,
        3::DOUBLE AS expected_value
    FROM read_parquet($focus_path)

    UNION ALL

    SELECT
        'persistent_top_band_is_50_plus' AS check_name,
        CASE
            WHEN COUNT(*) = 3 THEN 1
            ELSE 0
        END AS passed_flag,
        COUNT(*)::DOUBLE AS observed_value,
        3::DOUBLE AS expected_value
    FROM read_parquet($focus_path)
    WHERE priority_attention_flag = 1
      AND amount_band = '50_plus'
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
