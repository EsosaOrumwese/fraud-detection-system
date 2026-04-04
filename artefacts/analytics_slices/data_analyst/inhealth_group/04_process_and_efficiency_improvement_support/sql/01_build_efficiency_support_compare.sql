COPY (
    WITH agg AS (
        SELECT *
        FROM read_parquet($agg_path)
    ),
    focus AS (
        SELECT *
        FROM read_parquet($focus_path)
    ),
    base AS (
        SELECT
            a.month_start_date,
            a.amount_band,
            a.flow_rows,
            a.case_opened_rows,
            a.case_truth_rows,
            SUM(a.flow_rows) OVER (PARTITION BY a.month_start_date) AS total_flow_rows,
            SUM(a.case_opened_rows) OVER (PARTITION BY a.month_start_date) AS total_case_opened_rows,
            SUM(a.case_truth_rows) OVER (PARTITION BY a.month_start_date) AS total_case_truth_rows
        FROM agg a
    )
    SELECT
        b.month_start_date,
        b.amount_band,
        b.flow_rows,
        b.case_opened_rows,
        b.case_truth_rows,
        b.flow_rows / NULLIF(b.total_flow_rows, 0) AS flow_share,
        b.case_opened_rows / NULLIF(b.total_case_opened_rows, 0) AS case_open_share,
        b.case_truth_rows / NULLIF(b.total_case_truth_rows, 0) AS truth_share,
        b.case_truth_rows / NULLIF(b.case_opened_rows, 0) AS truth_per_case_open,
        (b.case_opened_rows / NULLIF(b.total_case_opened_rows, 0))
            - (b.case_truth_rows / NULLIF(b.total_case_truth_rows, 0)) AS burden_minus_yield_share,
        f.peer_case_open_rate,
        f.peer_case_truth_rate,
        f.case_open_gap_to_peer,
        f.case_truth_gap_to_peer,
        f.priority_rank,
        f.priority_attention_flag
    FROM base b
    JOIN focus f
      ON b.month_start_date = f.month_start_date
     AND b.amount_band = f.amount_band
    ORDER BY b.month_start_date, f.priority_rank
) TO $output_path (FORMAT PARQUET);
