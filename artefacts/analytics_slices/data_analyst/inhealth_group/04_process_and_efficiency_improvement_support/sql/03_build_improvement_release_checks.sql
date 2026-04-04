COPY (
    WITH efficiency AS (
        SELECT *
        FROM read_parquet($efficiency_path)
    ),
    review_support AS (
        SELECT *
        FROM read_parquet($review_path)
    )
    SELECT
        'three_month_rows_present' AS check_name,
        CASE WHEN COUNT(*) = 3 THEN 1 ELSE 0 END AS passed_flag,
        COUNT(*)::DOUBLE AS observed_value,
        3.0 AS expected_value
    FROM review_support

    UNION ALL

    SELECT
        'twelve_efficiency_rows_present' AS check_name,
        CASE WHEN COUNT(*) = 12 THEN 1 ELSE 0 END AS passed_flag,
        COUNT(*)::DOUBLE AS observed_value,
        12.0 AS expected_value
    FROM efficiency

    UNION ALL

    SELECT
        'persistent_focus_band_is_50_plus' AS check_name,
        CASE WHEN COUNT(*) = 3 THEN 1 ELSE 0 END AS passed_flag,
        COUNT(*)::DOUBLE AS observed_value,
        3.0 AS expected_value
    FROM review_support
    WHERE focus_band = '50_plus'

    UNION ALL

    SELECT
        'current_month_burden_gap_positive' AS check_name,
        CASE WHEN burden_minus_yield_share > 0 THEN 1 ELSE 0 END AS passed_flag,
        burden_minus_yield_share AS observed_value,
        0.0 AS expected_value
    FROM (
        SELECT *
        FROM review_support
        ORDER BY month_start_date DESC
        LIMIT 1
    )

    UNION ALL

    SELECT
        'overall_topline_change_small' AS check_name,
        CASE
            WHEN ABS(case_open_change_from_start) <= 0.001
             AND ABS(truth_change_from_start) <= 0.001
            THEN 1 ELSE 0
        END AS passed_flag,
        GREATEST(ABS(case_open_change_from_start), ABS(truth_change_from_start)) AS observed_value,
        0.001 AS expected_value
    FROM (
        SELECT *
        FROM review_support
        ORDER BY month_start_date DESC
        LIMIT 1
    )
) TO $output_path (FORMAT PARQUET);
