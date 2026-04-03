COPY (
    WITH base AS (
        SELECT
            week_role,
            CAST(entry_event_rows AS DOUBLE) AS entry_event_rows,
            CAST(flow_rows AS DOUBLE) AS flow_rows,
            CAST(case_open_rate AS DOUBLE) AS case_open_rate,
            CAST(long_lifecycle_share AS DOUBLE) AS long_lifecycle_share,
            CAST(case_truth_rate AS DOUBLE) AS case_truth_rate,
            CAST(truth_bank_mismatch_rate AS DOUBLE) AS truth_bank_mismatch_rate,
            CAST(avg_lifecycle_hours AS DOUBLE) AS avg_lifecycle_hours
        FROM read_parquet($kpi_path)
    ),
    current_row AS (
        SELECT * FROM base WHERE week_role = 'current'
    ),
    prior_row AS (
        SELECT * FROM base WHERE week_role = 'prior'
    )
    SELECT
        current_row.week_role,
        current_row.entry_event_rows,
        current_row.flow_rows,
        current_row.case_open_rate,
        current_row.long_lifecycle_share,
        current_row.case_truth_rate,
        current_row.truth_bank_mismatch_rate,
        current_row.avg_lifecycle_hours,
        current_row.flow_rows - prior_row.flow_rows AS flow_rows_delta,
        current_row.entry_event_rows - prior_row.entry_event_rows AS entry_event_rows_delta,
        current_row.case_open_rate - prior_row.case_open_rate AS case_open_rate_delta,
        current_row.long_lifecycle_share - prior_row.long_lifecycle_share AS long_lifecycle_share_delta,
        current_row.case_truth_rate - prior_row.case_truth_rate AS case_truth_rate_delta,
        current_row.truth_bank_mismatch_rate - prior_row.truth_bank_mismatch_rate AS truth_bank_mismatch_rate_delta,
        current_row.avg_lifecycle_hours - prior_row.avg_lifecycle_hours AS avg_lifecycle_hours_delta
    FROM current_row
    CROSS JOIN prior_row
) TO $output_path (FORMAT PARQUET);
