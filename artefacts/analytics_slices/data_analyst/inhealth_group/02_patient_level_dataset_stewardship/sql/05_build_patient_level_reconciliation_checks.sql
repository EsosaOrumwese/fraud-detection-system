COPY (
    WITH protected_summary AS (
        SELECT *
        FROM read_parquet($safe_summary_path)
        WHERE amount_band <> '__overall__'
    ),
    reporting_lane AS (
        SELECT
            amount_band,
            flow_rows AS reported_flow_rows,
            case_opened_flow_rows AS reported_case_opened_rows,
            case_truth_rows AS reported_case_truth_rows
        FROM read_parquet($month_band_agg_path)
        WHERE month_role = 'current'
    )
    SELECT
        p.amount_band,
        p.flow_rows AS protected_flow_rows,
        r.reported_flow_rows,
        p.flow_rows - r.reported_flow_rows AS flow_row_delta,
        p.case_opened_rows AS protected_case_opened_rows,
        r.reported_case_opened_rows,
        p.case_opened_rows - r.reported_case_opened_rows AS case_opened_row_delta,
        p.case_truth_rows AS protected_case_truth_rows,
        r.reported_case_truth_rows,
        p.case_truth_rows - r.reported_case_truth_rows AS case_truth_row_delta,
        CASE
            WHEN p.flow_rows = r.reported_flow_rows
             AND p.case_opened_rows = r.reported_case_opened_rows
             AND p.case_truth_rows = r.reported_case_truth_rows
            THEN 1
            ELSE 0
        END AS matched_flag
    FROM protected_summary p
    INNER JOIN reporting_lane r USING (amount_band)
    ORDER BY
        CASE p.amount_band
            WHEN 'under_10' THEN 1
            WHEN '10_to_25' THEN 2
            WHEN '25_to_50' THEN 3
            ELSE 4
        END
) TO $output_path (FORMAT PARQUET, COMPRESSION ZSTD);
