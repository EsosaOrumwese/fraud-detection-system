COPY (
    WITH trend AS (
        SELECT *
        FROM read_parquet($trend_path)
    ),
    efficiency AS (
        SELECT *
        FROM read_parquet($efficiency_path)
        WHERE priority_attention_flag = 1
    )
    SELECT
        e.month_start_date,
        e.amount_band AS focus_band,
        t.flow_rows AS overall_flow_rows,
        t.case_open_rate AS overall_case_open_rate,
        t.case_truth_rate AS overall_truth_rate,
        t.case_open_rate - FIRST_VALUE(t.case_open_rate) OVER (ORDER BY t.month_start_date) AS case_open_change_from_start,
        t.case_truth_rate - FIRST_VALUE(t.case_truth_rate) OVER (ORDER BY t.month_start_date) AS truth_change_from_start,
        e.flow_share,
        e.case_open_share,
        e.truth_share,
        e.burden_minus_yield_share,
        e.truth_per_case_open,
        e.case_open_gap_to_peer,
        e.case_truth_gap_to_peer
    FROM efficiency e
    JOIN trend t
      ON e.month_start_date = t.month_start_date
    ORDER BY e.month_start_date
) TO $output_path (FORMAT PARQUET);
